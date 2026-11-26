import time
from urllib.parse import urlsplit

import httpx
from beakdown_mcp import tools


def test_session_lifecycle():
    result = tools.create_handoff_session(
        "Review",
        [
            dict(
                id="data",
                title="Data",
                operation_type="load",
                sql_or_expr="SELECT 1 AS id",
            )
        ],
        [],
    )
    service = tools.manager()
    root = f"http://127.0.0.1:{service.port}"
    sid, token = result["session_id"], result["token"]
    assert not urlsplit(result["url"]).query
    headers = {"Authorization": f"Bearer {token}"}
    try:
        for _ in range(100):
            state = tools.get_session_result(sid, token)
            if state["state"] != "running":
                break
            time.sleep(0.05)
        assert state["state"] == "ready", state
        with httpx.Client(base_url=root) as client:
            assert client.get(f"/api/session/{sid}").status_code == 401
            assert (
                client.get(
                    f"/api/session/{sid}",
                    headers={**headers, "Origin": "https://evil.example"},
                ).status_code
                == 403
            )
            assert (
                client.get(
                    f"/api/session/{sid}/arrow/data", headers=headers
                ).status_code
                == 200
            )
            assert (
                client.post(
                    f"/api/session/{sid}/approve",
                    headers=headers,
                    json={"revision": 99},
                ).status_code
                == 409
            )
            response = client.post(
                f"/api/session/{sid}/approve", headers=headers, json={"revision": 0}
            )
            assert response.status_code == 200
            assert tools.get_session_result(sid, token)["approved"] is True
            assert (
                client.post(
                    f"/api/session/{sid}/edit",
                    headers=headers,
                    json={"revision": 1, "node_id": "data", "sql_or_expr": "SELECT 2"},
                ).status_code
                == 409
            )
    finally:
        service.close()
        tools._manager = None


def test_edit_recomputes_and_invalidates_revision():
    result = tools.create_handoff_session(
        "Edit",
        [
            dict(
                id="data",
                title="Data",
                operation_type="load",
                sql_or_expr="SELECT 1 AS id",
            )
        ],
        [],
    )
    service = tools.manager()
    sid, token = result["session_id"], result["token"]
    headers = {"Authorization": f"Bearer {token}"}

    def ready():
        for _ in range(100):
            state = tools.get_session_result(sid, token)
            if state["state"] != "running":
                return state
            time.sleep(0.02)
        raise AssertionError("Timed out")

    try:
        assert ready()["state"] == "ready"
        with httpx.Client(base_url=f"http://127.0.0.1:{service.port}") as client:
            response = client.post(
                f"/api/session/{sid}/edit",
                headers=headers,
                json={
                    "revision": 0,
                    "node_id": "data",
                    "sql_or_expr": "SELECT 2 AS id",
                },
            )
            assert response.status_code == 200
            state = ready()
            assert state["pipeline"]["nodes"][0]["preview"]["sample_data"] == [
                {"id": 2}
            ]
            assert (
                client.post(
                    f"/api/session/{sid}/approve", headers=headers, json={"revision": 0}
                ).status_code
                == 409
            )
            assert (
                client.post(
                    f"/api/session/{sid}/approve", headers=headers, json={"revision": 1}
                ).status_code
                == 200
            )
    finally:
        service.close()
        tools._manager = None


def test_websocket_authentication():
    from starlette.testclient import TestClient

    result = tools.create_handoff_session(
        "Events",
        [
            dict(
                id="data",
                title="Data",
                operation_type="load",
                sql_or_expr="SELECT 1 AS id",
            )
        ],
        [],
    )
    service = tools.manager()
    try:
        with TestClient(service.app) as client:
            with client.websocket_connect(
                f"/api/session/{result['session_id']}/events",
                headers={"origin": f"http://127.0.0.1:{service.port}"},
            ) as ws:
                ws.send_json({"token": result["token"]})
                assert ws.receive_json()["pipeline"]["title"] == "Events"
    finally:
        service.close()
        tools._manager = None
