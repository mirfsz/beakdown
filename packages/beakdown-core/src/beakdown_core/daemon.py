import asyncio
import io
import json
import secrets
import socket
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .investigation import Investigation
from .analysis import evidence_tables
from .build_map import AppRule, refresh_sources
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


class InvestigationSession:
    def __init__(self, investigation, assets, project_root=None):
        self.token = secrets.token_urlsafe(32)
        self.investigation = investigation
        self.project_root = project_root
        self.assets = assets
        self.arrows = {}
        self.state = "running" if investigation.analysis else "ready"
        self.error = None
        self.revision = 0
        self.lock = threading.RLock()
        self.expires = time.monotonic() + 3600


class FindingReview(BaseModel):
    revision: int
    review: str = "unreviewed"
    reviewer_note: str = ""


class RuleEdit(BaseModel):
    revision: int
    title: str | None = None
    description: str | None = None
    rationale: str | None = None
    review: str = "unreviewed"
    reviewer_note: str = ""


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
        if not isinstance(token, str):
            raise HTTPException(401, "Invalid session credentials")
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

    def compute_analysis(self, session, document, revision):
        try:
            result, arrows = run_pipeline(
                document.analysis, input_tables=evidence_tables(document)
            )
            with session.lock:
                if session.revision == revision:
                    session.investigation.analysis, session.arrows = result, arrows
                    session.state, session.error = "ready", None
        except Exception as exc:
            with session.lock:
                if session.revision == revision:
                    session.state, session.error = "error", str(exc)

    def queue_analysis(self, session):
        session.state, session.error, session.arrows = "running", None, {}
        for node in session.investigation.analysis.nodes:
            node.preview = None
        self.pool.submit(
            self.compute_analysis,
            session,
            session.investigation.model_copy(deep=True),
            session.revision,
        )

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

    def create_investigation(
        self, investigation: Investigation, assets, project_root=None
    ):
        for sid, old in list(self.sessions.items()):
            if time.monotonic() > old.expires:
                self.sessions.pop(sid, None)
        if len(self.sessions) >= 32:
            raise ValueError("Session capacity reached; sessions expire after one hour")
        session = InvestigationSession(investigation, assets, project_root)
        sid = investigation.investigation_id
        self.sessions[sid] = session
        if investigation.analysis:
            self.queue_analysis(session)
        return {
            "session_id": sid,
            "token": session.token,
            "url": f"http://127.0.0.1:{self.port}/#session={sid}&token={session.token}",
        }

    def refresh_build(self, session):
        if (
            not isinstance(session, InvestigationSession)
            or not session.investigation.build_map
        ):
            raise HTTPException(409, "No build map is attached")
        with session.lock:
            if (
                session.state == "running"
                or session.investigation.status != "pending_approval"
            ):
                raise HTTPException(
                    409,
                    "Wait for computation or create a new session for a decided report",
                )
            if refresh_sources(session.investigation.build_map, session.project_root):
                session.revision += 1
                if session.investigation.analysis:
                    self.queue_analysis(session)
        return self.result(session)

    def result(self, session):
        with session.lock:
            if isinstance(session, InvestigationSession):
                return {
                    "kind": "investigation",
                    "state": session.state,
                    "error": session.error,
                    "revision": session.revision,
                    "approved": session.investigation.status == "approved",
                    "investigation": session.investigation.model_dump(mode="json"),
                }
            return {
                "kind": "pipeline",
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
                document = (
                    session.investigation
                    if isinstance(session, InvestigationSession)
                    else None
                )
                pipeline = document.analysis if document else session.pipeline
                status = document.status if document else pipeline.status
                if pipeline is None:
                    raise HTTPException(409, "No analysis pipeline is attached")
                if (
                    session.state not in ("ready", "error")
                    or status != "pending_approval"
                    or body.revision != session.revision
                ):
                    raise HTTPException(409, "Session changed or is not editable")
                updated = pipeline.model_copy(deep=True)
                node = next((n for n in updated.nodes if n.id == body.node_id), None)
                if node is None:
                    raise HTTPException(404, "Unknown node")
                node.sql_or_expr = body.sql_or_expr
                updated = PipelineSpec.model_validate(updated.model_dump())
                session.revision += 1
                if document:
                    document.analysis = updated
                    self.queue_analysis(session)
                else:
                    session.state, session.error = "running", None
                    self.pool.submit(self.compute, session, updated)
            return self.result(session)

        @app.get("/api/session/{sid}/assets/{image_id}")
        def asset(sid: str, image_id: str, request: Request):
            session = auth(sid, request)
            if (
                not isinstance(session, InvestigationSession)
                or image_id not in session.assets
            ):
                raise HTTPException(404, "Screenshot not found")
            return Response(session.assets[image_id], media_type="image/webp")

        @app.post("/api/session/{sid}/findings/{finding_id}/review")
        def review_finding(
            sid: str, finding_id: str, body: FindingReview, request: Request
        ):
            session = auth(sid, request)
            if not isinstance(session, InvestigationSession):
                raise HTTPException(404)
            with session.lock:
                if (
                    body.revision != session.revision
                    or session.investigation.status != "pending_approval"
                ):
                    raise HTTPException(409, "Report changed or already decided")
                if session.state == "running":
                    raise HTTPException(
                        409,
                        "Wait for analysis to finish before reviewing another finding",
                    )
                if (
                    body.review not in ("unreviewed", "confirmed", "disputed")
                    or len(body.reviewer_note) > 5000
                ):
                    raise HTTPException(
                        422, "Invalid review or note exceeds 5000 characters"
                    )
                finding = next(
                    (f for f in session.investigation.findings if f.id == finding_id),
                    None,
                )
                if finding is None:
                    raise HTTPException(404, "Finding not found")
                finding.review, finding.reviewer_note = body.review, body.reviewer_note
                session.revision += 1
                if session.investigation.analysis:
                    self.queue_analysis(session)
            return self.result(session)

        @app.post("/api/session/{sid}/build/refresh")
        def refresh_build(sid: str, body: Decision, request: Request):
            session = auth(sid, request)
            with session.lock:
                if body.revision != session.revision:
                    raise HTTPException(409, "Report changed; reload before refreshing")
                return self.refresh_build(session)

        @app.post("/api/session/{sid}/rules/{rule_id}/review")
        def review_rule(sid: str, rule_id: str, body: RuleEdit, request: Request):
            from .build_map import invalidate_checks

            session = auth(sid, request)
            if (
                not isinstance(session, InvestigationSession)
                or not session.investigation.build_map
            ):
                raise HTTPException(404, "No build map is attached")
            with session.lock:
                if (
                    body.revision != session.revision
                    or session.state == "running"
                    or session.investigation.status != "pending_approval"
                ):
                    raise HTTPException(
                        409, "Report changed, computing or already decided"
                    )
                build = session.investigation.build_map
                rule = next((r for r in build.rules if r.id == rule_id), None)
                if not rule:
                    raise HTTPException(404, "Rule not found")
                values = {
                    k: v
                    for k, v in body.model_dump(exclude={"revision"}).items()
                    if v is not None
                }
                try:
                    updated = AppRule.model_validate({**rule.model_dump(), **values})
                except ValueError as exc:
                    raise HTTPException(422, str(exc)) from exc
                changed = any(
                    getattr(updated, key) != getattr(rule, key)
                    for key in ("title", "description", "rationale")
                )
                if changed:
                    updated.revision += 1
                    invalidate_checks(
                        build,
                        [rule.id],
                        "Rule intent changed; implement the revision and run its checks again.",
                    )
                build.rules[build.rules.index(rule)] = updated
                session.revision += 1
                if session.investigation.analysis:
                    self.queue_analysis(session)
            return self.result(session)

        @app.get("/api/session/{sid}/export")
        def export(sid: str, request: Request):
            session = auth(sid, request)
            if not isinstance(session, InvestigationSession):
                raise HTTPException(404)
            with session.lock:
                buffer = io.BytesIO()
                report = self.result(session)
                report["format_version"] = 1
                # Assets use normalized, content-addressed names, never caller paths.
                with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("report.json", json.dumps(report, indent=2))
                    for image_id, data in session.assets.items():
                        archive.writestr(f"screenshots/{image_id}.webp", data)
                    document = session.investigation
                    lines = [
                        f"# {document.title}",
                        "",
                        document.summary,
                        "",
                        "## Findings",
                        "",
                    ]
                    for finding in document.findings:
                        lines.extend(
                            [
                                f"### {finding.title}",
                                f"{finding.confidence} · {finding.review}",
                                "",
                                finding.detail,
                                "",
                                f"Evidence: {', '.join(finding.evidence_ids) or 'No additional evidence cited'}",
                                f"Reviewer: {finding.reviewer_note}",
                                "",
                            ]
                        )
                    lines.extend(
                        ["## Limitations", *[f"- {v}" for v in document.limitations]]
                    )
                    if document.build_map:
                        lines.extend(
                            [
                                "",
                                "## Pages, rules and implementation",
                                "",
                                "Links and check outcomes supplied by the investigating agent; source snapshots do not prove enforcement.",
                            ]
                        )
                        for rule in document.build_map.rules:
                            lines.extend(
                                [
                                    "",
                                    f"### {rule.title}",
                                    f"Pages: {', '.join(rule.screen_ids)} · {rule.origin} · {rule.review} · revision {rule.revision}",
                                    rule.description,
                                    rule.rationale,
                                    f"Reviewer: {rule.reviewer_note}",
                                ]
                            )
                        for ref in document.build_map.implementation:
                            lines.extend(
                                [
                                    "",
                                    f"### {ref.title}",
                                    f"{ref.path}:{ref.line_start}–{ref.line_end} · {ref.snapshot_status}",
                                    f"Rules: {', '.join(ref.rule_ids)}",
                                    f"SHA256: {ref.source_sha256}",
                                    "````",
                                    ref.excerpt,
                                    "````",
                                ]
                            )
                        for check in document.build_map.checks:
                            lines.extend(
                                [
                                    "",
                                    f"### {check.title}",
                                    f"Agent-reported: {check.status} · {check.checked_at}",
                                    f"Rules: {', '.join(check.rule_ids)}",
                                    check.detail,
                                    f"Evidence: {', '.join(check.evidence_ids)}",
                                    check.stale_reason,
                                ]
                            )
                    if document.analysis:
                        lines.extend(
                            ["", "## Executed analysis", "", document.analysis.title]
                        )
                        for node in document.analysis.nodes:
                            lines.extend(
                                [
                                    "",
                                    f"### {node.title}",
                                    "```sql",
                                    node.sql_or_expr or "",
                                    "```",
                                    f"Output rows: {node.preview.total_rows if node.preview else 'Not available'}",
                                ]
                            )
                        for node_id, data in session.arrows.items():
                            archive.writestr(f"analysis/{node_id}.arrow", data)
                    archive.writestr("report.md", "\n".join(lines))
                return Response(
                    buffer.getvalue(),
                    media_type="application/zip",
                    headers={
                        "Content-Disposition": 'attachment; filename="beakdown-report.zip"'
                    },
                )

        @app.post("/api/session/{sid}/{action}")
        def decide(sid: str, action: str, body: Decision, request: Request):
            session = auth(sid, request)
            if action not in ("approve", "reject"):
                raise HTTPException(404)
            with session.lock:
                document = (
                    session.investigation
                    if isinstance(session, InvestigationSession)
                    else session.pipeline
                )
                if (
                    session.state != "ready"
                    or body.revision != session.revision
                    or document.status != "pending_approval"
                ):
                    raise HTTPException(409, "Session changed or already decided")
                if (
                    isinstance(session, InvestigationSession)
                    and document.build_map
                    and action == "approve"
                ):
                    if refresh_sources(document.build_map, session.project_root):
                        session.revision += 1
                        if document.analysis:
                            self.queue_analysis(session)
                        raise HTTPException(
                            409,
                            "Linked source changed. Review stale checks and the new revision before approving.",
                        )
                document.status = "approved" if action == "approve" else "rejected"
                if isinstance(session, InvestigationSession) and document.analysis:
                    document.analysis.status = document.status
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
                if not isinstance(credentials, dict):
                    await ws.close(code=1008)
                    return
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
