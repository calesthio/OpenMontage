"""Server/API tests for Backlot.

These cover the deterministic eval surface in internal/evals/BACKLOT_EVAL_PLAN.md:
API shape, path safety, media/thumb serving, range requests, and loose
performance budgets.
"""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backlot import server as server_mod
from backlot import state as state_mod


@pytest.fixture
def projects_root(tmp_path, monkeypatch):
    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(state_mod, "PROJECTS_DIR", root)
    monkeypatch.setattr(server_mod, "PROJECTS_DIR", root)
    monkeypatch.setattr(server_mod, "_summary_cache", {})
    monkeypatch.setattr(server_mod, "_PROJECTS_ROOT_STR", __import__("os").path.normcase(str(root.resolve())))
    monkeypatch.setattr(server_mod, "THUMB_CACHE_DIR", tmp_path / "thumbs")
    return root


@pytest.fixture
def client(projects_root, monkeypatch):
    async def no_watch():
        return None

    monkeypatch.setattr(server_mod, "_watch_projects", no_watch)
    with TestClient(server_mod.create_app()) as c:
        yield c


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _make_project(root: Path, project_id: str = "film") -> Path:
    project = root / project_id
    (project / "artifacts").mkdir(parents=True)
    (project / "assets" / "images").mkdir(parents=True)
    (project / "assets" / "video").mkdir(parents=True)
    (project / "renders").mkdir(parents=True)
    _write_json(
        project / "project.json",
        {
            "project_id": project_id,
            "title": "Film",
            "pipeline_type": "cinematic",
            "created_at": "2026-07-02T00:00:00Z",
        },
    )
    _write_json(
        project / "checkpoint_script.json",
        {
            "version": "1.0",
            "project_id": project_id,
            "pipeline_type": "cinematic",
            "stage": "script",
            "status": "awaiting_human",
            "timestamp": "2026-07-02T00:01:00Z",
            "artifacts": {},
        },
    )
    return project


def _write_png(path: Path, color: tuple[int, int, int] = (200, 40, 80)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (24, 16), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    path.write_bytes(buf.getvalue())


class TestBacklotServerApi:
    def test_health(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True, "app": "backlot"}

    def test_projects_shape_and_state(self, client, projects_root):
        _make_project(projects_root, "film")

        projects = client.get("/api/projects")
        assert projects.status_code == 200
        body = projects.json()
        assert len(body) == 1
        assert body[0]["project_id"] == "film"
        assert body[0]["awaiting_human"] is True
        assert "stage_states" in body[0]

        state = client.get("/api/project/film/state")
        assert state.status_code == 200
        state_body = state.json()
        assert state_body["project_id"] == "film"
        assert state_body["title"] == "Film"
        assert state_body["stages"]

    @pytest.mark.parametrize(
        ("url", "status"),
        [
            ("/api/project/../state", 404),
            ("/api/project/C:/state", 400),
            ("/api/project/nope/state", 404),
        ],
    )
    def test_project_id_rejects_bad_or_unknown_ids(self, client, url, status):
        response = client.get(url)
        assert response.status_code == status

    def test_media_rejects_path_traversal(self, client, projects_root):
        _make_project(projects_root, "film")
        response = client.get("/media/film/%2E%2E/project.json")
        assert response.status_code == 403

    def test_media_serves_range_requests(self, client, projects_root):
        project = _make_project(projects_root, "film")
        media = project / "renders" / "final.mp4"
        media.write_bytes(b"0123456789")

        response = client.get("/media/film/renders/final.mp4", headers={"Range": "bytes=2-5"})

        assert response.status_code == 206
        assert response.content == b"2345"
        assert response.headers["content-range"].startswith("bytes 2-5/10")

    def test_thumb_downscales_image_and_passes_through_non_media(self, client, projects_root):
        project = _make_project(projects_root, "film")
        _write_png(project / "assets" / "images" / "sc1.png")
        text = project / "artifacts" / "note.txt"
        text.write_text("hello", encoding="utf-8")

        image = client.get("/thumb/film/assets/images/sc1.png?w=320")
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/jpeg"
        assert image.content.startswith(b"\xff\xd8")

        passthrough = client.get("/thumb/film/artifacts/note.txt")
        assert passthrough.status_code == 200
        assert passthrough.content == b"hello"


class TestBacklotPerformanceBudgets:
    def test_projects_and_state_stay_within_loose_budgets(self, client, projects_root):
        for i in range(25):
            project = _make_project(projects_root, f"film-{i:02d}")
            _write_json(
                project / "artifacts" / "scene_plan.json",
                {"version": "1.0", "scenes": [{"id": "sc1", "start_seconds": 0, "end_seconds": 1}]},
            )

        t0 = time.perf_counter()
        cold = client.get("/api/projects")
        cold_s = time.perf_counter() - t0
        assert cold.status_code == 200
        assert cold_s < 2.0

        t1 = time.perf_counter()
        warm = client.get("/api/projects")
        warm_s = time.perf_counter() - t1
        assert warm.status_code == 200
        assert warm_s < 0.150

        t2 = time.perf_counter()
        state = client.get("/api/project/film-00/state")
        state_s = time.perf_counter() - t2
        assert state.status_code == 200
        assert state_s < 0.400

    def test_image_thumb_generation_stays_within_budget(self, client, projects_root):
        project = _make_project(projects_root, "film")
        _write_png(project / "assets" / "images" / "sc1.png")

        t0 = time.perf_counter()
        response = client.get("/thumb/film/assets/images/sc1.png?w=640")
        elapsed = time.perf_counter() - t0

        assert response.status_code == 200
        assert elapsed < 1.5


class TestFindingsFixes:
    """Regression tests for dogfood findings F-03 (thumb video fallback)."""

    def test_thumb_never_serves_raw_video_bytes(self, client, projects_root):
        p = _make_project(projects_root, "vid")
        fake_video = p / "renders" / "final.mp4"
        fake_video.parent.mkdir(parents=True, exist_ok=True)
        # Not a real video: ffmpeg poster extraction will fail.
        fake_video.write_bytes(b"\x00" * 4096)
        res = client.get("/thumb/vid/renders/final.mp4")
        assert res.status_code == 404  # never the raw video bytes (F-03)
