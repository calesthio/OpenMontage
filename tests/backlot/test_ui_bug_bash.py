"""Browser regressions from the Backlot UI bug bash."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request

import pytest

from lib.checkpoint import CANONICAL_STAGE_ARTIFACTS, init_project, write_checkpoint
from lib.pipeline_loader import get_stage_order, load_pipeline
from scripts import backlot_screenshot_stage
from tests.contracts.test_phase0_contracts import sample_artifact


pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402


APPROVAL_CASES = [
    ("gate-research", "framework-smoke", "research", "research_brief", "Test Topic"),
    ("gate-idea", "hybrid", "idea", "brief", "Did you know?"),
    ("gate-proposal", "cinematic", "proposal", "proposal_packet", "The Surprising Truth About X"),
    ("gate-script", "cinematic", "script", "script", "Hello world"),
    ("gate-scene-plan", "cinematic", "scene_plan", "scene_plan", "Host on camera"),
    ("gate-assets", "cinematic", "assets", "asset_manifest", "asset-1"),
    ("gate-edit", "documentary-montage", "edit", "edit_decisions", "cut-1"),
    ("gate-compose", "cinematic", "compose", "render_report", "renders/output.mp4"),
    ("gate-publish", "cinematic", "publish", "publish_log", "youtube"),
]


def _complete_predecessors(root, project_id: str, pipeline_type: str, stage: str) -> None:
    order = get_stage_order(load_pipeline(pipeline_type))
    for predecessor in order[: order.index(stage)]:
        artifact_name = CANONICAL_STAGE_ARTIFACTS.get(predecessor)
        if artifact_name:
            artifact = sample_artifact(artifact_name)
            if artifact_name == "edit_decisions":
                artifact["render_runtime"] = "ffmpeg"
            artifacts = {artifact_name: artifact}
        else:
            artifacts = {}
        write_checkpoint(
            root,
            project_id,
            predecessor,
            "completed",
            artifacts,
            pipeline_type=pipeline_type,
            human_approved=True,
        )


def _build_approval_projects() -> None:
    root = backlot_screenshot_stage.STAGE_DIR
    for project_id, pipeline_type, stage, artifact_name, _visible_text in APPROVAL_CASES:
        artifact = sample_artifact(artifact_name)
        if artifact_name == "edit_decisions":
            artifact["render_runtime"] = "ffmpeg"
        review_summary = (
            {
                "critical": 0,
                "suggestions": 1,
                "nitpicks": 0,
                "review_focus_met": "9/9",
                "schema_validation": "proposal_packet PASS",
            }
            if stage == "proposal"
            else "Artifact is ready for human review."
        )
        init_project(
            project_id,
            title=f"Approval fixture: {stage}",
            pipeline_type=pipeline_type,
            pipeline_dir=root,
        )
        _complete_predecessors(root, project_id, pipeline_type, stage)
        write_checkpoint(
            root,
            project_id,
            stage,
            "awaiting_human",
            {artifact_name: artifact},
            pipeline_type=pipeline_type,
            review={
                "round": 1,
                "decision": "pass",
                "critical": 0,
                "suggestions": 1,
                "nitpicks": 0,
                "summary": review_summary,
            },
        )

    # A manifest-declared custom stage/artifact proves the fallback is driven
    # by the stage contract rather than a hardcoded canonical-stage list.
    init_project(
        "gate-character-design",
        title="Approval fixture: character design",
        pipeline_type="character-animation",
        pipeline_dir=root,
    )
    _complete_predecessors(
        root,
        "gate-character-design",
        "character-animation",
        "character_design",
    )
    write_checkpoint(
        root,
        "gate-character-design",
        "character_design",
        "awaiting_human",
        {"character_design": {
            "version": "1.0",
            "characters": [{
                "id": "ada",
                "display_name": "Ada",
                "role": "explorer",
                "body_type": "round",
                "style": "flat graphic",
                "silhouette_notes": "Round explorer with a bright orange field jacket",
                "required_emotions": ["curious"],
                "required_actions": ["wave"],
            }],
        }},
        pipeline_type="character-animation",
    )


@pytest.fixture(scope="module")
def staged_backlot_server():
    backlot_screenshot_stage.build_stage()
    _build_approval_projects()
    port = 4897
    env = dict(os.environ)
    env["OPENMONTAGE_PROJECTS_DIR"] = str(backlot_screenshot_stage.STAGE_DIR)
    server = subprocess.Popen(
        [sys.executable, "-m", "backlot", "serve", "--port", str(port)],
        cwd=backlot_screenshot_stage.REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1):
                break
        except Exception:
            time.sleep(0.2)
    else:
        server.terminate()
        raise RuntimeError("Backlot server did not become healthy")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


def test_project_pages_fit_mobile_and_tablet_widths(staged_backlot_server):
    project_paths = [
        "/p/signal-in-the-static?static=1",
        "/p/the-slow-orchard?static=1",
        "/p/the-last-lighthouse?static=1",
        "/p/paper-boats?static=1",
        "/p/gate-proposal?static=1",
        "/p/gate-character-design?static=1",
    ]
    viewports = [
        {"width": 390, "height": 844},
        {"width": 768, "height": 1024},
    ]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            for viewport in viewports:
                page.set_viewport_size(viewport)
                for path in project_paths:
                    page.goto(staged_backlot_server + path, wait_until="networkidle")
                    page.wait_for_timeout(300)
                    sizes = page.evaluate(
                        """() => ({
                            scrollWidth: document.documentElement.scrollWidth,
                            clientWidth: document.documentElement.clientWidth
                        })"""
                    )
                    assert sizes["scrollWidth"] <= sizes["clientWidth"], (
                        path,
                        viewport,
                        sizes,
                    )
        finally:
            browser.close()


def test_static_navigation_invalid_route_and_active_takes(staged_backlot_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1560, "height": 1000})
        try:
            page.goto(staged_backlot_server + "/?static=1", wait_until="networkidle")
            href = page.locator("a.lib-card").first.get_attribute("href")
            assert href and "static=1" in href

            response = page.goto(
                staged_backlot_server + "/p/..%2FAGENT_GUIDE.md?static=1",
                wait_until="networkidle",
            )
            assert response and response.status == 200
            assert "PROJECT NOT FOUND" in page.locator("body").inner_text()

            page.goto(staged_backlot_server + "/p/the-last-lighthouse?static=1", wait_until="networkidle")
            page.wait_for_timeout(300)
            assert page.locator(".takes .tk.active").count() >= 1
        finally:
            browser.close()


@pytest.mark.parametrize(
    ("project_id", "_pipeline_type", "stage", "artifact_name", "visible_text"),
    APPROVAL_CASES,
)
def test_every_canonical_gate_promotes_its_artifact_before_approval(
    staged_backlot_server,
    project_id,
    _pipeline_type,
    stage,
    artifact_name,
    visible_text,
):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(
                staged_backlot_server + f"/p/{project_id}?static=1",
                wait_until="networkidle",
            )
            review = page.locator(f'.approval-review[data-stage="{stage}"]')
            assert review.is_visible()
            assert review.get_by_text("PENDING APPROVAL", exact=True).is_visible()
            assert "[object Object]" not in review.inner_text()
            artifact = review.locator(f'[data-artifact="{artifact_name}"]')
            assert artifact.is_visible()
            assert visible_text in artifact.inner_text()

            review.get_by_role("button", name="OPEN FULL ARTIFACT").click()
            assert page.locator(".drawer").is_visible()
            assert visible_text in page.locator(".drawer").inner_text()
        finally:
            browser.close()


def test_script_gate_keeps_script_visible_and_marks_pending_approval(staged_backlot_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(staged_backlot_server + "/p/gate-script?static=1", wait_until="networkidle")
            assert page.locator(".script-card").is_visible()
            assert page.locator(".script-pending").inner_text() == "PENDING APPROVAL"
        finally:
            browser.close()


def test_manifest_declared_custom_gate_uses_generic_review_fallback(staged_backlot_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(
                staged_backlot_server + "/p/gate-character-design?static=1",
                wait_until="networkidle",
            )
            review = page.locator('.approval-review[data-stage="character_design"]')
            assert review.is_visible()
            artifact = review.locator('[data-artifact="character_design"]')
            assert artifact.is_visible()
            assert "Ada" in artifact.inner_text()
            assert "Round explorer" in artifact.inner_text()
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# Deep audit, round 2 (2026-11-11): what a full re-render used to throw away,
# keyboard operation, and project ids that are not URL-safe.
# ---------------------------------------------------------------------------

RENDER_PROJECT = "/p/the-last-lighthouse?static=1"


def _rerender(page) -> None:
    """Trigger a full board rebuild, the same path an SSE refresh takes."""
    page.locator(".theme-toggle").click()
    page.wait_for_timeout(250)


def test_playing_render_survives_a_board_rebuild(staged_backlot_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(staged_backlot_server + RENDER_PROJECT, wait_until="networkidle")
            if not page.evaluate(
                "document.createElement('video').canPlayType('video/mp4; codecs=\"avc1.42E01E\"')"
            ):
                pytest.skip("this browser build cannot decode the H.264 fixture render")
            page.evaluate(
                """async () => {
                    const v = document.querySelector('.render-hero video');
                    v.muted = true; v.loop = true;
                    await v.play();
                }"""
            )
            page.wait_for_timeout(700)
            before = page.evaluate(
                "(() => { const v = document.querySelector('.render-hero video');"
                " return {paused: v.paused, t: v.currentTime, muted: v.muted}; })()"
            )
            assert before["paused"] is False and before["t"] > 0

            _rerender(page)
            page.wait_for_timeout(400)
            after = page.evaluate(
                "(() => { const v = document.querySelector('.render-hero video');"
                " return {paused: v.paused, t: v.currentTime, muted: v.muted,"
                "         count: document.querySelectorAll('.render-hero video').length}; })()"
            )
            assert after["count"] == 1
            assert after["paused"] is False, "a board rebuild paused the render"
            assert after["muted"] is True, "a board rebuild reset the mute state"
            assert after["t"] > 0
        finally:
            browser.close()


def test_open_artifact_keeps_its_scroll_position_across_a_rebuild(staged_backlot_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(staged_backlot_server + RENDER_PROJECT, wait_until="networkidle")
            page.locator('nav.rail .stage[data-fk="stage:scene_plan"]').click()
            pre = page.locator(".drawer pre").first
            pre.evaluate("n => { n.scrollTop = 160; }")
            assert pre.evaluate("n => n.scrollTop") == 160

            _rerender(page)
            assert page.locator(".drawer pre").first.evaluate("n => n.scrollTop") == 160
        finally:
            browser.close()


def test_board_controls_are_operable_from_the_keyboard(staged_backlot_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(staged_backlot_server + RENDER_PROJECT, wait_until="networkidle")

            # Every operable element is a focusable button.
            unreachable = page.evaluate(
                """() => [...document.querySelectorAll(
                        'nav.rail .stage, .script-card.script-preview, .rp-btn,'
                        + ' .render-meta .v, .scene-card .narr[title]')]
                      .filter(n => n.getAttribute('role') !== 'button' || n.tabIndex !== 0)
                      .map(n => n.className)"""
            )
            assert unreachable == []

            # Enter opens a stage drawer and focus stays on that stage, even
            # though the whole board was rebuilt underneath it.
            stage = page.locator('nav.rail .stage[data-fk="stage:script"]')
            stage.focus()
            page.keyboard.press("Enter")
            assert page.locator('.drawer[data-stage="script"]').is_visible()
            assert page.evaluate("document.activeElement.getAttribute('data-fk')") == "stage:script"
            assert stage.get_attribute("aria-expanded") == "true"
            page.keyboard.press("Space")
            assert page.locator(".drawer").count() == 0

            # The script dialog takes focus, traps Tab, locks the page behind
            # it, and gives focus back to the card that opened it.
            card = page.locator(".script-card.script-preview")
            card.focus()
            page.keyboard.press("Enter")
            modal = page.locator("#modal")
            assert modal.get_attribute("role") == "dialog"
            assert modal.get_attribute("aria-modal") == "true"
            assert "open" in (modal.get_attribute("class") or "")
            assert page.evaluate("document.activeElement.className") == "modal-close"
            assert page.evaluate("getComputedStyle(document.body).overflow") == "hidden"
            page.keyboard.press("Tab")
            assert page.evaluate("document.activeElement.className") == "modal-close"
            page.keyboard.press("Escape")
            assert "open" not in (modal.get_attribute("class") or "")
            assert page.evaluate("getComputedStyle(document.body).overflow") != "hidden"
            assert page.evaluate("document.activeElement.getAttribute('data-fk')") == "script-card"

            # Replay: the start button hands focus to the transport.
            start = page.locator('.rp-btn[data-fk="replay-start"]')
            start.focus()
            page.keyboard.press("Enter")
            assert page.locator(".replay-bar input[type=range]").is_visible()
            assert page.evaluate("document.activeElement.getAttribute('data-fk')") == "replay-toggle"
            page.locator('.rp-btn[data-fk="replay-stop"]').focus()
            page.keyboard.press("Enter")
            assert page.locator(".replay-bar input[type=range]").count() == 0
            assert page.evaluate("document.activeElement.getAttribute('data-fk')") == "replay-start"
        finally:
            browser.close()


def test_small_text_controls_are_tappable_on_a_phone(staged_backlot_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True
        )
        page = context.new_page()
        try:
            page.goto(staged_backlot_server + RENDER_PROJECT, wait_until="networkidle")
            page.locator("nav.rail .stage").first.tap()
            heights = page.evaluate(
                """() => [...document.querySelectorAll('.drawer .close, .render-meta .v')]
                      .map(n => Math.round(n.getBoundingClientRect().height))"""
            )
            assert heights and min(heights) >= 24, heights
            sizes = page.evaluate(
                "({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth})"
            )
            assert sizes["sw"] <= sizes["cw"], sizes
        finally:
            browser.close()


@pytest.mark.parametrize("project_id", ["my project #1", "50% off?", "a&b=c", "ไทย-โปรเจกต์"])
def test_library_links_to_projects_whose_ids_are_not_url_safe(staged_backlot_server, project_id):
    """A folder name is not a URL: '#', '?' and '%' must be escaped in links."""
    init_project(
        project_id,
        title=f"Odd id {project_id}",
        pipeline_type="framework-smoke",
        pipeline_dir=backlot_screenshot_stage.STAGE_DIR,
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(staged_backlot_server + "/?static=1", wait_until="networkidle")
            hrefs = page.evaluate(
                "() => [...document.querySelectorAll('a.lib-card')].map(a => a.getAttribute('href'))"
            )
            from urllib.parse import quote

            href = f"/p/{quote(project_id, safe='')}?static=1"
            assert href in hrefs, hrefs
            page.goto(staged_backlot_server + href, wait_until="networkidle")
            assert "PROJECT NOT FOUND" not in page.locator("body").inner_text()
            assert page.locator("header.slate h1").inner_text().lower() == f"odd id {project_id}".lower()
        finally:
            browser.close()


def test_malformed_escape_in_the_address_shows_not_found(staged_backlot_server):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        try:
            page.goto(staged_backlot_server + "/p/50%?static=1", wait_until="networkidle")
            assert "PROJECT NOT FOUND" in page.locator("body").inner_text()
            assert errors == []
        finally:
            browser.close()


def test_unchanged_state_is_not_rebuilt_and_a_stale_response_never_wins(staged_backlot_server):
    """Live mode: a change notification that leaves the state as it was must
    not rebuild the page, and an older response may not overwrite a newer one."""
    root = backlot_screenshot_stage.STAGE_DIR
    project_id = "live-refresh"
    init_project(project_id, title="Live refresh", pipeline_type="framework-smoke", pipeline_dir=root)
    write_checkpoint(root, project_id, "research", "in_progress", {}, pipeline_type="framework-smoke")
    stale_body = None

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        held = []

        def hold_first(route):
            # Keep the very first state request pending; let later ones through.
            if not held:
                held.append(route)
            else:
                route.continue_()

        try:
            import urllib.request

            with urllib.request.urlopen(
                f"{staged_backlot_server}/api/project/{project_id}/state"
            ) as response:
                stale_body = response.read()

            page.route("**/api/project/*/state", hold_first)
            page.goto(f"{staged_backlot_server}/p/{project_id}", wait_until="domcontentloaded")
            page.wait_for_timeout(500)
            assert len(held) == 1

            # A newer state arrives over SSE while the first request hangs.
            write_checkpoint(
                root, project_id, "research", "completed",
                {"research_brief": sample_artifact("research_brief")},
                pipeline_type="framework-smoke", human_approved=True,
            )
            page.wait_for_selector('nav.rail .stage.done[data-fk="stage:research"]', timeout=15000)

            # The held (older) response lands last: it must be ignored.
            held[0].fulfill(status=200, content_type="application/json", body=stale_body)
            page.wait_for_timeout(500)
            assert page.locator('nav.rail .stage.done[data-fk="stage:research"]').count() == 1

            # A file change that leaves the board state alone: no rebuild.
            page.evaluate(
                """() => { window.__rebuilds = 0;
                    const app = document.getElementById('app');
                    new MutationObserver((muts) => {
                        if (muts.some(m => m.target === app && m.removedNodes.length)) window.__rebuilds++;
                    }).observe(app, {childList: true}); }"""
            )
            (root / project_id / "assets" / "images" / "scratch.txt").write_text("x", encoding="utf-8")
            page.wait_for_timeout(1800)
            assert page.evaluate("window.__rebuilds") == 0
        finally:
            browser.close()
