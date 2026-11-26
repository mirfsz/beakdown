"""Capture and check the fictional local app, then write a reviewable build map.

uv run --with playwright python examples/build_map_demo.py --output /absolute/folder
uv run beakdown-review /absolute/folder/investigation.json

Requires Chrome, or BEAKDOWN_BROWSER=chromium with Playwright Chromium installed.
All check outcomes below come from actual browser observations of the local demo.
"""

import argparse
import functools
import hashlib
import http.server
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright


def create_manifest(output):
    root = Path(__file__).resolve().parents[1]
    source = root / "examples/demo-site/index.html"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    lines = source.read_text().splitlines()
    output = Path(output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    captured_at = datetime.now(timezone.utc).isoformat()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(source.parent))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    screens, checks, records = [], [], []

    def check(id, title, rule, ref, passed, detail):
        evidence_id = "demo_" + id
        record = {
            "id": evidence_id,
            "checked_at": captured_at,
            "status": "passed" if passed else "failed",
            "detail": detail,
            "source_sha256": digest,
        }
        records.append(record)
        checks.append(
            {
                "id": id,
                "title": title,
                "rule_ids": [rule],
                "implementation_ids": [ref],
                "status": record["status"],
                "method": "automated",
                "command": "uv run --with playwright python examples/build_map_demo.py --output /absolute/folder",
                "detail": detail,
                "evidence_ids": [evidence_id],
                "checked_at": captured_at,
                "source_hashes": {ref: digest},
            }
        )

    try:
        with sync_playwright() as p:
            executable = os.environ.get("BEAKDOWN_BROWSER")
            options = (
                {"executable_path": executable}
                if executable and executable != "chromium"
                else ({} if executable == "chromium" else {"channel": "chrome"})
            )
            browser = p.chromium.launch(headless=True, **options)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(f"http://127.0.0.1:{server.server_port}")
            for id in ("overview", "projects", "settings"):
                if id != "overview":
                    page.locator(f'nav a[href="#{id}"]').click()
                page.screenshot(path=str(output / f"{id}.png"))
                screens.append(
                    {
                        "id": id,
                        "title": id.title(),
                        "description": "Captured page of the fictional Fieldwork demonstration app.",
                        "screenshot_path": str(output / f"{id}.png"),
                        "captured_at": captured_at,
                    }
                )
                assert page.locator("nav a").count() == 3
                assert (
                    page.locator(f'nav a[href="#{id}"]').get_attribute("class")
                    == "active"
                )
                if id == "projects":
                    headings = page.locator("th").all_text_contents()
                    check(
                        "columns",
                        "Project table exposes delivery context",
                        "project_context",
                        "project_table",
                        headings == ["Project", "Phase", "Status", "Owner"],
                        f"Browser read table headings: {headings}. There are {page.locator('tbody tr').count()} fictional project rows.",
                    )
            check(
                "navigation",
                "All pages retain workspace navigation",
                "shared_navigation",
                "navigation_source",
                True,
                "Browser visited Overview, Projects and Settings by clicking the sidebar. Each page retained all three links and marked its active destination.",
            )
            page.locator("input").first.fill("Renamed demo workspace")
            page.get_by_role("button", name="Save changes").click()
            feedback = page.locator("#saved").inner_text()
            check(
                "feedback",
                "Save action displays feedback",
                "save_feedback",
                "save_handler",
                "saved" in feedback,
                f"After clicking Save changes, the visible status was: {feedback}",
            )
            page.screenshot(path=str(output / "settings.png"))
            page.reload()
            actual = page.locator("input").first.input_value()
            check(
                "persistence",
                "Workspace name survives a reload",
                "durable_storage",
                "save_handler",
                actual == "Renamed demo workspace",
                f"Expected 'Renamed demo workspace' after reload; browser read {actual!r}. The fictional demo does not persist this change.",
            )
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    def ref(id, title, needle, span, rules, pages):
        start = next(i for i, line in enumerate(lines, 1) if needle in line)
        return {
            "id": id,
            "title": title,
            "path": "examples/demo-site/index.html",
            "line_start": start,
            "line_end": min(start + span, len(lines)),
            "layer": "ui",
            "rule_ids": rules,
            "screen_ids": pages,
        }

    manifest = {
        "title": "Fieldwork · pages, rules & implementation",
        "target": "Fictional local app · actual browser checks",
        "summary": "A working demonstration of tracing page intent into source and checks. Three browser checks pass; the proposed persistence requirement fails against this demo. Inspect the rule, see its code, and request a change.",
        "project_root": str(root),
        "include_analysis": True,
        "screens": screens,
        "findings": [
            {
                "id": "storage_gap",
                "screen_id": "settings",
                "title": "Save feedback does not establish persistence",
                "detail": "The browser displayed save feedback, but reloading restored the original workspace name. See the durable-storage rule and its failed check.",
                "confidence": "observed",
                "category": "behavior",
                "evidence_ids": ["demo_feedback", "demo_persistence"],
            }
        ],
        "connections": [
            {"source": "overview", "target": "projects", "label": "Click Projects"},
            {"source": "projects", "target": "settings", "label": "Click Settings"},
        ],
        "limitations": [
            "Fictional local demonstration app. These are example acceptance criteria, not requirements attributed to an external product.",
            "Source links are declared by this demo script. Check outcomes are agent-reported browser observations, not independent certification.",
            "The browser checks only these routes and actions; no production backend was inspected.",
        ],
        "build_map": {
            "rules": [
                {
                    "id": "shared_navigation",
                    "title": "Keep the workspace reachable",
                    "description": "Every page must expose Overview, Projects and Settings, with the current destination marked.",
                    "screen_ids": ["overview", "projects", "settings"],
                    "origin": "requirement",
                    "rationale": "A shared navigation requirement for this fictional demo.",
                    "evidence_ids": ["demo_navigation"],
                },
                {
                    "id": "project_context",
                    "title": "Show delivery context",
                    "description": "Projects must show each project's phase, status and owner.",
                    "screen_ids": ["projects"],
                    "origin": "requirement",
                    "evidence_ids": ["demo_columns"],
                },
                {
                    "id": "save_feedback",
                    "title": "Acknowledge a save action",
                    "description": "Saving workspace details displays a visible status message.",
                    "screen_ids": ["settings"],
                    "origin": "observed",
                    "evidence_ids": ["demo_feedback"],
                },
                {
                    "id": "durable_storage",
                    "title": "Keep workspace changes after reload",
                    "description": "A saved workspace name must remain after reloading the Settings page.",
                    "screen_ids": ["settings"],
                    "origin": "requirement",
                    "rationale": "Proposed demo acceptance criterion. Intentionally unmet by the current demo, exposing a useful implementation gap.",
                    "evidence_ids": ["demo_persistence"],
                },
            ],
            "implementation": [
                ref(
                    "navigation_source",
                    "Shared sidebar and destinations",
                    "  <nav>",
                    9,
                    ["shared_navigation"],
                    ["overview", "projects", "settings"],
                ),
                ref(
                    "project_table",
                    "Project table rendering",
                    "    const table = () =>",
                    20,
                    ["project_context"],
                    ["projects"],
                ),
                ref(
                    "save_handler",
                    "Save feedback handler",
                    '.getElementById("save")',
                    10,
                    ["save_feedback", "durable_storage"],
                    ["settings"],
                ),
            ],
            "checks": checks,
        },
    }
    (output / "check-evidence.json").write_text(json.dumps(records, indent=2))
    path = output / "investigation.json"
    path.write_text(json.dumps(manifest, indent=2))
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        help="Folder outside the repository for actual captures",
    )
    print(create_manifest(parser.parse_args().output))
