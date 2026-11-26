"""Run after pnpm build: uv run --with playwright python tests/browser_smoke.py

Uses a local image fixture, never a private app. Chrome must be installed;
set BEAKDOWN_BROWSER to a Chromium executable for another installation.
"""

import json
import os
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from beakdown_mcp import tools
from PIL import Image, ImageDraw
from playwright.sync_api import expect, sync_playwright


def main():
    with TemporaryDirectory() as directory:
        screenshot = Path(directory) / "fixture.png"
        image = Image.new("RGB", (1280, 800), "#f2f6f3")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 210, 800), fill="#284f43")
        draw.text((260, 70), "Browser verification fixture", fill="#284f43")
        image.save(screenshot)
        result = tools.create_investigation_session(
            title="Browser verification",
            target="Local test fixture",
            screens=[
                {"id": "home", "title": "Home", "screenshot_path": str(screenshot)},
                {
                    "id": "settings",
                    "title": "Settings",
                    "screenshot_path": str(screenshot),
                },
            ],
            findings=[
                {
                    "id": "nav",
                    "screen_id": "home",
                    "title": "Visible navigation",
                    "detail": "The local fixture has a navigation region.",
                    "confidence": "observed",
                    "region": {"x": 0, "y": 0, "width": 0.16, "height": 1},
                },
                {
                    "id": "persist",
                    "screen_id": "home",
                    "title": "Persistence unknown",
                    "detail": "No storage was inspected.",
                    "confidence": "unknown",
                },
            ],
            connections=[
                {
                    "source": "home",
                    "target": "settings",
                    "label": "Inferred connection",
                    "confidence": "inferred",
                }
            ],
            limitations=["This is a generated test image, not an application audit."],
        )
        try:
            with sync_playwright() as p:
                executable = os.environ.get("BEAKDOWN_BROWSER")
                browser = p.chromium.launch(
                    headless=True,
                    **(
                        {"executable_path": executable}
                        if executable and executable != "chromium"
                        else ({} if executable == "chromium" else {"channel": "chrome"})
                    ),
                )
                page = browser.new_page(viewport={"width": 1600, "height": 1100})
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(result["url"])
                page.wait_for_load_state("networkidle")
                expect(page.locator(".screen-card img")).to_have_count(2)
                expect(page.locator(".analysis-node")).to_have_count(3)
                expect(page.locator(".execution-status")).to_have_text(
                    "Executed locally"
                )
                page.get_by_role("button", name="Data flow", exact=True).click()
                expect(page.locator(".investigation-stage")).not_to_be_visible()
                page.get_by_role("button", name="Both", exact=True).click()
                expect(page.locator(".investigation-stage")).to_be_visible()
                page.get_by_role("button", name="This screen", exact=True).click()
                page.get_by_role("button", name="Inspect screen home").first.click()
                expect(page.locator(".inspector-heading h2")).to_have_text("Home")
                page.get_by_role("button", name="Edit SQL", exact=True).click()
                page.locator(".analysis-editor textarea").fill(
                    "SELECT * FROM audit_findings ORDER BY id DESC"
                )
                page.get_by_role("button", name="Recompute", exact=True).click()
                expect(page.locator(".execution-status")).to_have_text(
                    "Executed locally"
                )
                expect(page.locator(".analysis-table tbody tr")).to_have_count(2)
                page.wait_for_function("""() => {
                  const card=document.querySelector('.screen-card').getBoundingClientRect();
                  const canvas=document.querySelector('.screenshot-canvas').getBoundingClientRect();
                  return card.y>=canvas.y-2 && card.bottom<=canvas.bottom+2;
                }""")
                page.set_viewport_size({"width": 1280, "height": 900})
                page.wait_for_function("""() => {
                  const node=document.querySelector('.analysis-node strong');
                  return node.getBoundingClientRect().height >= 12;
                }""")
                assert page.evaluate("location.hash") == ""
                page.get_by_role("button", name="unknown", exact=True).click()
                expect(page.locator(".finding-card")).to_have_count(1)
                expect(
                    page.get_by_role("heading", name="Persistence unknown")
                ).to_be_visible()
                page.get_by_role("button", name="All findings", exact=True).click()
                page.get_by_role(
                    "button", name="Inspect screenshot", exact=True
                ).click()
                expect(page.get_by_role("dialog")).to_be_visible()
                page.keyboard.press("Escape")
                expect(page.get_by_role("dialog")).to_have_count(0)
                card = page.locator(".finding-card").filter(
                    has=page.get_by_role("heading", name="Visible navigation")
                )
                card.get_by_text("Evidence & review", exact=True).click()
                card.get_by_role("textbox").fill("Please inspect a second viewport.")
                card.get_by_role("button", name="Dispute", exact=True).click()
                expect(card.locator(".review-state")).to_have_text("disputed")
                expect(page.locator(".execution-status")).to_have_text(
                    "Executed locally"
                )
                with page.expect_download() as download:
                    page.get_by_role("button", name="Export report").click()
                file = download.value.path()
                with zipfile.ZipFile(file) as archive:
                    report = json.loads(archive.read("report.json"))
                    assert (
                        report["investigation"]["findings"][0]["review"] == "disputed"
                    )
                    assert any(n.startswith("screenshots/") for n in archive.namelist())
                page.reload()
                expect(page.locator(".investigation-app")).to_be_visible()
                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(400)
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
                page.wait_for_function("""() => {
                  const card=document.querySelector('.screen-card').getBoundingClientRect();
                  const canvas=document.querySelector('.screenshot-canvas').getBoundingClientRect();
                  return card.y>=canvas.y-2 && card.bottom<=canvas.bottom+2 && card.x>=canvas.x-2 && card.right<=canvas.right+2;
                }""")
                page.get_by_role("button", name="Approve review").click()
                expect(
                    page.get_by_role("button", name="Copy resumption prompt")
                ).to_be_visible()
                final = tools.get_session_result(result["session_id"], result["token"])
                assert (
                    final["approved"]
                    and final["investigation"]["findings"][0]["review"] == "disputed"
                )
                assert not errors, errors
                browser.close()
                print(
                    "PASS: screenshots, annotations, filtering, dialog, correction, export, reload, mobile and approval"
                )
        finally:
            tools.manager().close()
            tools._manager = None


if __name__ == "__main__":
    main()
