import base64
import hashlib
import io
import json
import time
import zipfile

import httpx
import pytest
from beakdown_core.investigation import Region, load_screens, rea_images
from beakdown_mcp import tools
from PIL import Image
from pydantic import ValidationError


@pytest.fixture
def screenshot(tmp_path):
    path = tmp_path / "screen.png"
    Image.new("RGB", (320, 200), "#dbeae3").save(path)
    return path


@pytest.fixture
def service():
    yield tools.manager()
    tools.manager().close()
    tools._manager = None


def test_local_image_contract(screenshot):
    screens, assets = load_screens(
        [{"id": "home", "title": "Home", "screenshot_path": str(screenshot)}]
    )
    screen = screens[0]
    assert (screen.width, screen.height) == (320, 200)
    assert screen.image_id in assets
    assert screen.source_sha256 == hashlib.sha256(screenshot.read_bytes()).hexdigest()
    assert screen.evidence.operation == "manual_capture"
    with Image.open(io.BytesIO(assets[screen.image_id])) as image:
        assert image.format == "WEBP"


@pytest.mark.parametrize(
    "region",
    [
        {"x": 0.9, "y": 0, "width": 0.2, "height": 0.1},
        {"x": -1, "y": 0, "width": 0.2, "height": 0.1},
    ],
)
def test_bad_region_rejected(region):
    with pytest.raises(ValidationError):
        Region(**region)


def test_no_html_or_relative_image(tmp_path):
    html = tmp_path / "screen.html"
    html.write_text("<script>alert(1)</script>")
    with pytest.raises(Exception):
        load_screens([{"id": "home", "title": "Home", "screenshot_path": str(html)}])
    with pytest.raises(ValueError, match="absolute"):
        load_screens([{"id": "home", "title": "Home", "screenshot_path": "screen.png"}])


def record_for(screenshot):
    data = screenshot.read_bytes()
    artifact = {
        "data_base64": base64.b64encode(data).decode(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "media_type": "image/png",
    }
    return {
        "evidence_id": "ev_actual",
        "operation": "capture_browser_scenario",
        "provider": {"name": "REA test provider"},
        "confidence": "observed",
        "limitations": ["One route only"],
        "normalized_result": {
            "steps": [
                {
                    "step_id": "no-image",
                    "artifacts": {"screenshot": {"state": "not_requested"}},
                },
                {
                    "step_id": "home",
                    "after_url": {"url": "https://example.test"},
                    "artifacts": {
                        "screenshot": {"state": "captured", "value": artifact}
                    },
                },
            ],
            "completeness": {"status": "incomplete"},
        },
    }


def test_rea_bundle_retains_provenance_and_digest(screenshot, tmp_path):
    record = record_for(screenshot)
    path = tmp_path / "bundle.json"
    path.write_text(
        json.dumps(
            {"result": {"records": [record, {**record, "evidence_id": "ev_other"}]}}
        )
    )
    screens, _ = load_screens(
        [
            {
                "id": "home",
                "title": "Home",
                "rea_evidence_path": str(path),
                "rea_evidence_id": "ev_actual",
                "capture_index": 0,
            }
        ]
    )
    assert screens[0].evidence.evidence_id == "ev_actual"
    assert screens[0].url == "https://example.test"
    assert "One route only" in screens[0].evidence.limitations
    assert any("incomplete" in v for v in screens[0].evidence.limitations)
    record["normalized_result"]["steps"][1]["artifacts"]["screenshot"]["value"][
        "sha256"
    ] = "tampered"
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="digest mismatch"):
        load_screens([{"id": "home", "title": "Home", "rea_evidence_path": str(path)}])


def test_rea_native_and_web_formats(screenshot):
    data = screenshot.read_bytes()
    image = {
        "base64": base64.b64encode(data).decode(),
        "sha256": hashlib.sha256(data).hexdigest(),
        "mime_type": "image/png",
    }
    native = {
        "evidence_id": "native",
        "operation": "capture_native_ui_scenario",
        "normalized_result": {
            "initial": {"screenshot": image},
            "steps": [{"index": 0, "after": {"screenshot": image}}],
        },
    }
    assert len(rea_images(native)[1]) == 2
    web = {
        "evidence_id": "web",
        "operation": "capture_web_screenshot",
        "normalized_result": {
            "artifact": image,
            "target": {"url": "https://example.test"},
        },
    }
    assert len(rea_images(web)[1]) == 1


def test_investigation_review_and_export(screenshot, service):
    result = tools.create_investigation_session(
        title="Review",
        target="Demo app",
        screens=[{"id": "home", "title": "Home", "screenshot_path": str(screenshot)}],
        findings=[
            {
                "id": "layout",
                "screen_id": "home",
                "title": "Layout",
                "detail": "Visible navigation",
                "confidence": "observed",
                "review": "confirmed",
                "reviewer_note": "injected",
            }
        ],
    )
    sid, token = result["session_id"], result["token"]
    state = tools.get_session_result(sid, token)
    assert state["kind"] == "investigation"
    assert state["investigation"]["findings"][0]["review"] == "unreviewed"
    assert state["investigation"]["findings"][0]["reviewer_note"] == ""
    assert "token" not in json.dumps(state)
    image_id = state["investigation"]["screens"][0]["image_id"]
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(base_url=f"http://127.0.0.1:{service.port}") as client:
        assert client.get(f"/api/session/{sid}/assets/{image_id}").status_code == 401
        assert (
            client.get(
                f"/api/session/{sid}/assets/{image_id}", headers=headers
            ).headers["content-type"]
            == "image/webp"
        )
        assert (
            client.get(
                f"/api/session/{sid}/assets/missing", headers=headers
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/api/session/{sid}/findings/layout/review",
                headers=headers,
                json={"revision": 1, "review": "disputed"},
            ).status_code
            == 409
        )
        response = client.post(
            f"/api/session/{sid}/findings/layout/review",
            headers=headers,
            json={
                "revision": 0,
                "review": "disputed",
                "reviewer_note": "Needs another capture",
            },
        )
        assert response.status_code == 200
        assert response.json()["revision"] == 1
        assert (
            client.post(
                f"/api/session/{sid}/approve", headers=headers, json={"revision": 0}
            ).status_code
            == 409
        )
        assert client.post(
            f"/api/session/{sid}/approve", headers=headers, json={"revision": 1}
        ).json()["approved"]
        final = tools.get_session_result(sid, token)
        assert (
            final["investigation"]["findings"][0]["reviewer_note"]
            == "Needs another capture"
        )
        assert (
            client.post(
                f"/api/session/{sid}/findings/layout/review",
                headers=headers,
                json={"revision": 2},
            ).status_code
            == 409
        )
        exported = client.get(f"/api/session/{sid}/export", headers=headers)
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            report = json.loads(archive.read("report.json"))
            assert report["investigation"]["status"] == "approved"
            assert "Needs another capture" in archive.read("report.md").decode()
            assert f"screenshots/{image_id}.webp" in archive.namelist()
            assert token.encode() not in archive.read("report.json")
        service.sessions[sid].expires = time.monotonic() - 1
        assert (
            client.get(
                f"/api/session/{sid}/assets/{image_id}", headers=headers
            ).status_code
            == 410
        )


def test_reference_validation(screenshot):
    with pytest.raises(ValidationError, match="unknown screen"):
        tools.create_investigation_session(
            title="Review",
            target="Demo",
            screens=[
                {"id": "home", "title": "Home", "screenshot_path": str(screenshot)}
            ],
            connections=[{"source": "home", "target": "missing"}],
        )
