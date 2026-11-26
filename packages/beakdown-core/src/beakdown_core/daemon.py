import asyncio
import secrets
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
from .models import PipelineSpec
from .runner import run_pipeline


class Session:
    def __init__(self, pipeline, allowed_paths):
        self.token = secrets.token_urlsafe(32)
        self.pipeline = pipeline
        self.arrows = {}
        self.state = "running"
        self.error = None
        self.revision = 0
        self.lock = threading.RLock()
        self.expires = time.monotonic() + 3600
        self.allowed_paths = allowed_paths


class Edit(BaseModel):
    node_id: str
    sql_or_expr: str
    revision: int


class Decision(BaseModel):
    revision: int


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.app = FastAPI()
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.socket.listen(128)
        self.port = self.socket.getsockname()[1]
        self._routes()
        self.server = uvicorn.Server(
            uvicorn.Config(self.app, log_level="error", access_log=False)
        )
        self.thread = threading.Thread(
            target=self.server.run, kwargs={"sockets": [self.socket]}, daemon=True
        )
        self.thread.start()

    def authorize(self, sid, token):
        session = self.sessions.get(sid)
        if not session or not secrets.compare_digest(token or "", session.token):
            raise HTTPException(401, "Invalid session credentials")
        if time.monotonic() > session.expires:
            raise HTTPException(410, "Session expired")
        return session

    def compute(self, session, pipeline):
        try:
            result, arrows = run_pipeline(pipeline, session.allowed_paths)
            with session.lock:
                session.pipeline, session.arrows = result, arrows
                session.state = "ready"
        except Exception as exc:
            with session.lock:
                session.state, session.error = "error", str(exc)

    def create(self, pipeline, allowed_paths=()):
        for sid, old in list(self.sessions.items()):
            if time.monotonic() > old.expires:
                self.sessions.pop(sid, None)
        if len(self.sessions) >= 32:
            raise ValueError("Session capacity reached; sessions expire after one hour")
        session = Session(pipeline, allowed_paths)
        self.sessions[pipeline.pipeline_id] = session
        self.pool.submit(self.compute, session, pipeline)
        return {
            "session_id": pipeline.pipeline_id,
            "token": session.token,
            "url": f"http://127.0.0.1:{self.port}/#session={pipeline.pipeline_id}&token={session.token}",
        }

    def result(self, session):
        with session.lock:
            return {
                "state": session.state,
                "error": session.error,
                "revision": session.revision,
                "approved": session.pipeline.status == "approved",
                "pipeline": session.pipeline.model_dump(mode="json"),
            }

    def _routes(self):
        app = self.app

        @app.middleware("http")
        async def protect(request: Request, call_next):
            if request.headers.get("host") != f"127.0.0.1:{self.port}":
                return Response(status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != f"http://127.0.0.1:{self.port}":
                return Response(status_code=403)
            response = await call_next(request)
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        def auth(sid, request):
            return self.authorize(
                sid, request.headers.get("authorization", "").removeprefix("Bearer ")
            )

        @app.get("/api/session/{sid}")
        def read(sid: str, request: Request):
            return self.result(auth(sid, request))

        @app.get("/api/session/{sid}/arrow/{node}")
        def arrow(sid: str, node: str, request: Request):
            session = auth(sid, request)
            if node not in session.arrows:
                raise HTTPException(404, "Preview unavailable")
            return Response(
                session.arrows[node], media_type="application/vnd.apache.arrow.stream"
            )

        @app.post("/api/session/{sid}/edit")
        def edit(sid: str, body: Edit, request: Request):
            session = auth(sid, request)
            with session.lock:
                if (
                    session.state != "ready"
                    or session.pipeline.status != "pending_approval"
                    or body.revision != session.revision
                ):
                    raise HTTPException(409, "Session changed or is not editable")
                pipeline = session.pipeline.model_copy(deep=True)
                node = next((n for n in pipeline.nodes if n.id == body.node_id), None)
                if node is None:
                    raise HTTPException(404, "Unknown node")
                node.sql_or_expr = body.sql_or_expr
                pipeline = PipelineSpec.model_validate(pipeline.model_dump())
                session.state, session.error = "running", None
                session.revision += 1
                self.pool.submit(self.compute, session, pipeline)
            return self.result(session)

        @app.post("/api/session/{sid}/{action}")
        def decide(sid: str, action: str, body: Decision, request: Request):
            session = auth(sid, request)
            if action not in ("approve", "reject"):
                raise HTTPException(404)
            with session.lock:
                if (
                    session.state != "ready"
                    or body.revision != session.revision
                    or session.pipeline.status != "pending_approval"
                ):
                    raise HTTPException(409, "Session changed or already decided")
                session.pipeline.status = (
                    "approved" if action == "approve" else "rejected"
                )
                session.revision += 1
            return self.result(session)

        @app.websocket("/api/session/{sid}/events")
        async def events(ws: WebSocket, sid: str):
            if ws.headers.get("origin") != f"http://127.0.0.1:{self.port}":
                await ws.close(code=1008)
                return
            await ws.accept()
            try:
                credentials = await asyncio.wait_for(ws.receive_json(), 5)
                session = self.authorize(sid, credentials.get("token"))
                while True:
                    self.authorize(sid, credentials.get("token"))
                    await ws.send_json(self.result(session))
                    await asyncio.sleep(1)
            except (WebSocketDisconnect, HTTPException, asyncio.TimeoutError):
                await ws.close()

        ui = Path(__file__).parent / "web"
        if not ui.exists():
            ui = Path(__file__).resolve().parents[3] / "beakdown-ui" / "dist"
        if ui.exists():
            app.mount("/", StaticFiles(directory=ui, html=True), name="ui")
        else:

            @app.get("/")
            def missing_ui():
                return Response(
                    "Build the UI with pnpm build, then restart the MCP server.",
                    status_code=503,
                )

    def close(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)
        self.pool.shutdown(wait=True)
        self.socket.close()
