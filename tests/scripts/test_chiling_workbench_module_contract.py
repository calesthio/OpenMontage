from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKBENCH = ROOT / "web" / "chiling-workbench"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_chiling_workbench_uses_browser_modules_for_app_code():
    index = read(WORKBENCH / "index.html")
    app = read(WORKBENCH / "app.js")

    assert '<script src="./app.js" type="module"></script>' in index
    assert 'from "./src/format.js"' in app
    assert 'from "./src/task-model.js"' in app
    assert 'from "./src/state.js"' in app


def test_chiling_workbench_keeps_user_safe_frontend_boundaries():
    source = "\n".join(
        read(path)
        for path in [
            WORKBENCH / "app.js",
            WORKBENCH / "src" / "format.js",
            WORKBENCH / "src" / "task-model.js",
            WORKBENCH / "src" / "state.js",
        ]
    )

    assert "RUNNINGHUB" not in source
    assert "DOUBAO" not in source
    assert "ARK_API_KEY" not in source
    assert "CHILING_PRODUCTION_SERVICE" not in source
    assert "reference-video-analysis" not in source
