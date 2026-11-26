import hashlib
import io
import json
import time
import zipfile

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from beakdown_core.build_map import ImplementationRef
from beakdown_mcp import tools


@pytest.fixture
def staged(tmp_path):
    source = tmp_path / "Registration.tsx"
    source.write_text(
        "export const capacity = 20;\nexport const emailRequired = true;\n"
    )
    image = tmp_path / "screen.png"
    Image.new("RGB", (320, 200), "white").save(image)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    args = dict(
        title="Registration build",
        target="Local fixture",
        include_analysis=False,
        project_root=str(tmp_path),
        screens=[
            {
                "id": "registration",
                "title": "Registration",
                "screenshot_path": str(image),
            },
            {
                "id": "confirmation",
                "title": "Confirmation",
                "screenshot_path": str(image),
            },
        ],
        build_map={
            "rules": [
                {
                    "id": "capacity",
                    "title": "Stop at capacity",
                    "description": "Stop accepting registrations at 20 people.",
                    "screen_ids": ["registration", "confirmation"],
                    "review": "confirmed",
                    "revision": 99,
                }
            ],
            "implementation": [
                {
                    "id": "form",
                    "title": "Registration form",
                    "path": "Registration.tsx",
                    "line_start": 1,
                    "line_end": 2,
                    "rule_ids": ["capacity"],
                    "excerpt": "injected source",
                    "source_sha256": "injected hash",
                }
            ],
            "checks": [
                {
                    "id": "capacity_check",
                    "title": "Capacity check",
                    "rule_ids": ["capacity"],
                    "implementation_ids": ["form"],
                    "status": "passed",
                    "detail": "Fixture runner reported capacity = 20.",
                    "checked_at": "2026-11-26T12:00:00Z",
                    "evidence_ids": ["fixture-run-1"],
                    "source_hashes": {"form": digest},
                }
            ],
        },
    )
    yield args, source
    if tools._manager:
        tools._manager.close()
        tools._manager = None


def create(args):
    result = tools.create_investigation_session(**args)
    return result, tools.get_session_result(result["session_id"], result["token"])


def client_for(result):
    return httpx.Client(
        base_url=f"http://127.0.0.1:{tools.manager().port}/api/session/{result['session_id']}",
        headers={"Authorization": f"Bearer {result['token']}"},
    )


def test_page_rule_code_check_roundtrip_and_edit(staged):
    args, source = staged
    result, state = create(args)
    build = state["investigation"]["build_map"]
    assert build["rules"][0]["review"] == "unreviewed"
    assert build["rules"][0]["revision"] == 1
    assert build["implementation"][0]["excerpt"] == source.read_text().strip()
    assert build["implementation"][0]["snapshot_status"] == "captured"
    assert build["checks"][0]["status"] == "passed"
    with client_for(result) as client:
        assert (
            client.post("/rules/capacity/review", json={"revision": 1}).status_code
            == 409
        )
        response = client.post(
            "/rules/capacity/review",
            json={
                "revision": 0,
                "description": "Accept 25 registrations.",
                "review": "disputed",
                "reviewer_note": "Venue capacity increased.",
            },
        )
        assert response.status_code == 200
        updated = response.json()["investigation"]["build_map"]
        assert updated["rules"][0]["revision"] == 2
        assert updated["checks"][0]["status"] == "stale"
        assert updated["checks"][0]["rule_revisions"] == {"capacity": 1}
        assert source.read_text().startswith("export const capacity = 20")
        assert client.post("/approve", json={"revision": 0}).status_code == 409
        assert client.post("/approve", json={"revision": 1}).json()["approved"]
        final = tools.get_session_result(result["session_id"], result["token"])
        assert (
            final["investigation"]["build_map"]["rules"][0]["reviewer_note"]
            == "Venue capacity increased."
        )
        archive = client.get("/export")
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
            assert "Accept 25 registrations" in z.read("report.md").decode()
            assert "Registration.tsx" in z.read("report.md").decode()
            assert (
                json.loads(z.read("report.json"))["investigation"]["build_map"][
                    "checks"
                ][0]["status"]
                == "stale"
            )
            assert str(source.parent) not in z.read("report.json").decode()
        assert (
            client.post("/rules/capacity/review", json={"revision": 2}).status_code
            == 409
        )


def test_source_changes_invalidate_and_block_stale_approval(staged):
    args, source = staged
    result, _ = create(args)
    source.write_text(
        "export const capacity = 25;\nexport const emailRequired = true;\n"
    )
    with client_for(result) as client:
        assert client.post("/approve", json={"revision": 0}).status_code == 409
        state = tools.get_session_result(result["session_id"], result["token"])
        assert state["revision"] == 1 and not state["approved"]
        assert (
            state["investigation"]["build_map"]["implementation"][0]["snapshot_status"]
            == "changed"
        )
        assert state["investigation"]["build_map"]["checks"][0]["status"] == "stale"
        # Earlier source snapshot is retained for inspection, never silently replaced.
        assert (
            "capacity = 20"
            in state["investigation"]["build_map"]["implementation"][0]["excerpt"]
        )
        source.unlink()
        state = tools.refresh_build_evidence(result["session_id"], result["token"])
        assert state["revision"] == 2
        assert (
            state["investigation"]["build_map"]["implementation"][0]["snapshot_status"]
            == "unavailable"
        )


def test_review_only_does_not_stale_checks_and_unbound_results_do(staged):
    args, _ = staged
    result, _ = create(args)
    with client_for(result) as client:
        response = client.post(
            "/rules/capacity/review", json={"revision": 0, "review": "confirmed"}
        )
        assert (
            response.json()["investigation"]["build_map"]["checks"][0]["status"]
            == "passed"
        )
    args["build_map"]["checks"][0]["source_hashes"] = {}
    _, state = create(args)
    assert state["investigation"]["build_map"]["checks"][0]["status"] == "stale"


def test_no_root_means_no_source_reads(staged):
    args, _ = staged
    args.pop("project_root")
    args["build_map"]["implementation"][0]["path"] = "does-not-exist.ts"
    _, state = create(args)
    ref = state["investigation"]["build_map"]["implementation"][0]
    assert ref["snapshot_status"] == "reference_only"
    assert ref["excerpt"] == ref["source_sha256"] == ""


@pytest.mark.parametrize(
    "path", ["../outside.ts", "/etc/passwd", "file:///etc/passwd", "..\\outside.ts"]
)
def test_source_path_traversal_rejected(path):
    with pytest.raises(ValidationError):
        ImplementationRef(id="ref", title="Source", path=path, rule_ids=["rule"])


def test_symlink_secret_and_out_of_range_rejected(staged, tmp_path):
    args, source = staged
    secret = source.parent / ".env"
    secret.write_text("SECRET=test-fixture-only")
    link = source.parent / "visible.ts"
    link.symlink_to(secret)
    args["build_map"]["implementation"][0]["path"] = "visible.ts"
    with pytest.raises(ValueError, match="credential"):
        create(args)
    link.unlink()
    outside = tmp_path.parent / (tmp_path.name + "-outside.ts")
    outside.write_text("outside")
    try:
        link.symlink_to(outside)
        with pytest.raises(ValueError, match="escapes"):
            create(args)
    finally:
        outside.unlink()
    args["build_map"]["implementation"][0]["path"] = "Registration.tsx"
    args["build_map"]["implementation"][0]["line_end"] = 20
    with pytest.raises(ValueError, match="line range"):
        create(args)


def test_dangling_links_and_unsubstantiated_pass_rejected(staged):
    args, _ = staged
    args["build_map"]["rules"][0]["screen_ids"] = ["missing"]
    with pytest.raises(ValidationError, match="unknown screen"):
        create(args)
    args["build_map"]["rules"][0]["screen_ids"] = ["registration"]
    args["build_map"]["checks"][0]["evidence_ids"] = []
    with pytest.raises(ValidationError, match="evidence IDs"):
        create(args)


def test_rule_change_recomputes_attached_analysis(staged):
    args, _ = staged
    args["include_analysis"] = True
    args["analysis_pipeline"] = {
        "title": "Rule checks",
        "nodes": [
            {
                "id": "checks",
                "title": "Check freshness",
                "operation_type": "load",
                "sql_or_expr": "SELECT status FROM audit_checks",
            }
        ],
        "edges": [],
    }
    result, _ = create(args)

    def ready():
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = tools.get_session_result(result["session_id"], result["token"])
            if state["state"] != "running":
                assert state["state"] == "ready", state.get("error")
                return state
            time.sleep(0.01)
        pytest.fail("Build analysis did not complete")

    state = ready()
    assert state["investigation"]["analysis"]["nodes"][0]["preview"]["sample_data"] == [
        {"status": "passed"}
    ]
    with client_for(result) as client:
        assert (
            client.post(
                "/rules/capacity/review",
                json={
                    "revision": 0,
                    "description": "Allow 25 attendees.",
                    "review": "disputed",
                },
            ).status_code
            == 200
        )
    state = ready()
    assert state["investigation"]["analysis"]["nodes"][0]["preview"]["sample_data"] == [
        {"status": "stale"}
    ]


def test_build_analysis_cannot_shadow_case_insensitive_input_names(staged):
    args, _ = staged
    args["include_analysis"] = True
    args["analysis_pipeline"] = {
        "title": "Invalid input alias",
        "nodes": [
            {
                "id": "AUDIT_RULES",
                "title": "Shadow",
                "operation_type": "load",
                "sql_or_expr": "SELECT 1 AS value",
            }
        ],
        "edges": [],
    }
    with pytest.raises(ValidationError, match="shadow"):
        create(args)
