"""Actual demo capture → page/rule/code/check review → human change → export."""

import json
import os
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from beakdown_mcp import tools
from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from examples.build_map_demo import create_manifest


def main():
    with TemporaryDirectory() as directory:
        manifest = create_manifest(directory)
        args = json.loads(manifest.read_text())
        assert [c["status"] for c in args["build_map"]["checks"]].count("passed") == 3
        assert [c["status"] for c in args["build_map"]["checks"]].count("failed") == 1
        result = tools.create_investigation_session(**args)
        try:
            with sync_playwright() as p:
                executable = os.environ.get("BEAKDOWN_BROWSER")
                options = (
                    {"executable_path": executable}
                    if executable and executable != "chromium"
                    else ({} if executable == "chromium" else {"channel": "chrome"})
                )
                browser = p.chromium.launch(headless=True, **options)
                page = browser.new_page(
                    viewport={"width": 1600, "height": 1100},
                    permissions=["clipboard-read", "clipboard-write"],
                )
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(result["url"])
                page.wait_for_load_state("networkidle")
                expect(page.locator(".build-map-panel")).to_be_visible()
                expect(page.locator(".analysis-panel")).to_have_count(0)
                page.locator(".screen-nav").filter(has_text="Settings").click()
                page.locator(".rule-choice").filter(
                    has_text="Keep workspace changes after reload"
                ).click()
                expect(page.locator(".rule-description")).to_contain_text(
                    "must remain after reloading"
                )
                page.get_by_role("button", name="Code (1)", exact=True).click()
                expect(page.locator(".source-location")).to_contain_text(
                    "examples/demo-site/index.html"
                )
                page.get_by_text("Inspect captured source", exact=True).click()
                expect(page.locator(".source-reference pre")).to_contain_text(
                    'getElementById("save")'
                )
                page.get_by_role("button", name="Checks (1)", exact=True).click()
                expect(page.locator(".verification-check .trace-state")).to_have_text(
                    "failed"
                )
                expect(page.locator(".verification-check")).to_contain_text(
                    "browser read 'Fieldwork Studio'"
                )
                page.get_by_role("button", name="Intent", exact=True).click()
                captures = os.environ.get("BEAKDOWN_CAPTURE_DIR")
                if captures:
                    output = Path(captures)
                    output.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(output / "desktop.png"))
                    page.set_viewport_size({"width": 1280, "height": 900})
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(output / "user-1280.png"))
                    page.set_viewport_size({"width": 390, "height": 844})
                    page.wait_for_timeout(300)
                    page.screenshot(path=str(output / "mobile.png"), full_page=True)
                page.set_viewport_size({"width": 1280, "height": 900})
                page.get_by_role("button", name="Edit rule", exact=True).click()
                page.get_by_label("Required behavior", exact=True).fill(
                    "Persist the workspace name for each signed-in user after reload."
                )
                page.get_by_label("Note for the agent", exact=True).fill(
                    "Implement real storage before we ship."
                )
                page.get_by_role(
                    "button", name="Save change request", exact=True
                ).click()
                expect(page.locator(".rule-heading .trace-state")).to_have_text(
                    "change requested"
                )
                expect(page.locator(".rule-description")).to_contain_text(
                    "each signed-in user"
                )
                page.get_by_role("button", name="Checks (1)", exact=True).click()
                expect(page.locator(".verification-check .trace-state")).to_have_text(
                    "stale"
                )
                expect(page.locator(".verification-check")).to_contain_text(
                    "Rule intent changed"
                )
                page.get_by_role("button", name="Intent", exact=True).click()
                page.get_by_role("button", name="Copy change request for agent").click()
                expect(
                    page.get_by_role("button", name="Change request copied")
                ).to_be_visible()
                assert "Persist the workspace name" in page.evaluate(
                    "navigator.clipboard.readText()"
                )
                page.evaluate(
                    """() => Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async () => { throw new DOMException('Blocked for test', 'NotAllowedError'); } } })"""
                )
                page.get_by_role("button", name="Change request copied").click()
                fallback = page.get_by_role("textbox", name="Change request text")
                expect(fallback).to_be_visible()
                expect(fallback).to_contain_text("Persist the workspace name")
                fallback.focus()
                if captures:
                    page.screenshot(path=str(output / "clipboard-fallback.png"))
                page.get_by_role("button", name="This page", exact=True).click()
                page.get_by_role("searchbox", name="Search rules").fill(
                    "nonexistent rule"
                )
                expect(
                    page.get_by_role("heading", name="No matching rules")
                ).to_be_visible()
                page.get_by_role("searchbox", name="Search rules").fill("")
                page.locator(".rule-choice").filter(
                    has_text="Keep the workspace reachable"
                ).click()
                page.locator(".rule-pages").get_by_role(
                    "button", name="Projects", exact=True
                ).click()
                expect(page.locator(".inspector-heading h2")).to_have_text("Projects")
                page.get_by_role("button", name="Accept rule", exact=True).click()
                expect(page.locator(".rule-heading .trace-state")).to_have_text(
                    "accepted"
                )
                page.get_by_role("combobox", name="Inspection layer").select_option(
                    "analysis"
                )
                expect(page.locator(".analysis-panel")).to_be_visible()
                page.get_by_role("combobox", name="Inspection layer").select_option(
                    "build"
                )
                with page.expect_download() as download:
                    page.get_by_role("button", name="Export report", exact=True).click()
                with zipfile.ZipFile(download.value.path()) as archive:
                    state = json.loads(archive.read("report.json"))
                    rule = next(
                        r
                        for r in state["investigation"]["build_map"]["rules"]
                        if r["id"] == "durable_storage"
                    )
                    assert (
                        rule["reviewer_note"]
                        == "Implement real storage before we ship."
                    )
                    assert (
                        "Persist the workspace name"
                        in archive.read("report.md").decode()
                    )
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                page.get_by_role("button", name="Approve review", exact=True).click()
                expect(
                    page.get_by_role("button", name="Copy resumption prompt")
                ).to_be_visible()
                final = tools.get_session_result(result["session_id"], result["token"])
                assert final["approved"]
                assert not errors, errors
                browser.close()
                print(
                    "PASS: actual browser checks, page-rule-code links, source excerpt, failed evidence, rule edit, stale checks, change request, cross-page navigation, data analysis, export, mobile and approval"
                )
        finally:
            tools.manager().close()
            tools._manager = None


if __name__ == "__main__":
    main()
