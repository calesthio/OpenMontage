"""Browser regressions from the Backlot UI bug bash."""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request

import pytest

from lib.checkpoint import init_project, write_checkpoint
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
