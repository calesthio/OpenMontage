from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKBENCH = ROOT / "web" / "chiling-workbench"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_chiling_workbench_uses_browser_modules_for_app_code():
    index = read(WORKBENCH / "index.html")
    app = read(WORKBENCH / "app.js")
    views = "\n".join(read(path) for path in sorted((WORKBENCH / "src" / "views").glob("*.js")))

    assert '<script src="./app.js" type="module"></script>' in index
    assert 'from "./src/format.js"' in app
    assert 'from "../task-model.js"' in views
    assert 'from "./src/state.js"' in app


def test_chiling_workbench_keeps_user_safe_frontend_boundaries():
    modules = [
        WORKBENCH / "app.js",
        WORKBENCH / "src" / "action-safety.js",
        WORKBENCH / "src" / "format.js",
        WORKBENCH / "src" / "task-model.js",
        WORKBENCH / "src" / "state.js",
        WORKBENCH / "src" / "dom.js",
        WORKBENCH / "src" / "actions.js",
        WORKBENCH / "src" / "polling.js",
        WORKBENCH / "src" / "components" / "ui.js",
        WORKBENCH / "src" / "components" / "topbar.js",
        *sorted((WORKBENCH / "src" / "views").glob("*.js")),
    ]
    source = "\n".join(
        read(path)
        for path in modules
    )

    assert "RUNNINGHUB" not in source
    assert "DOUBAO" not in source
    assert "ARK_API_KEY" not in source
    assert "CHILING_PRODUCTION_SERVICE" not in source
    assert "reference-video-analysis" not in source


def test_chiling_workbench_has_shared_component_modules():
    app = read(WORKBENCH / "app.js")
    ui = read(WORKBENCH / "src" / "components" / "ui.js")
    topbar = read(WORKBENCH / "src" / "components" / "topbar.js")
    views = "\n".join(read(path) for path in sorted((WORKBENCH / "src" / "views").glob("*.js")))

    assert 'from "../components/ui.js"' in views
    assert 'from "./src/components/topbar.js"' in app
    assert "export function button" in ui
    assert "export function panel" in ui
    assert "export function phonePreview" in ui
    assert "export function metric" in ui
    assert "export function pill" in ui
    assert "export function renderTopbar" in topbar


def test_chiling_workbench_dom_helper_module_exists():
    app = read(WORKBENCH / "app.js")
    dom = read(WORKBENCH / "src" / "dom.js")

    assert 'from "./src/dom.js"' in app
    assert "export function find" in dom
    assert "export function findAll" in dom
    assert "export function bindDelegatedClick" in dom


def test_chiling_workbench_primary_view_modules_exist():
    app = read(WORKBENCH / "app.js")

    for module_name in ["login", "dashboard", "create"]:
        path = WORKBENCH / "src" / "views" / f"{module_name}.js"
        assert path.is_file(), module_name
        assert f'from "./src/views/{module_name}.js"' in app
        assert "export function render" in read(path)


def test_chiling_workbench_workflow_view_modules_exist():
    app = read(WORKBENCH / "app.js")

    for module_name in ["review", "generating", "delivery", "admin", "detail-drawer"]:
        path = WORKBENCH / "src" / "views" / f"{module_name}.js"
        assert path.is_file(), module_name
        assert "export function render" in read(path)

    assert 'from "./src/views/review.js"' in app
    assert 'from "./src/views/generating.js"' in app
    assert 'from "./src/views/delivery.js"' in app
    assert 'from "./src/views/admin.js"' in app
    assert 'from "./src/views/detail-drawer.js"' in app


def test_chiling_workbench_action_and_polling_modules_exist():
    app = read(WORKBENCH / "app.js")
    actions = read(WORKBENCH / "src" / "actions.js")
    polling = read(WORKBENCH / "src" / "polling.js")

    assert 'from "./src/actions.js"' in app
    assert 'from "./src/polling.js"' in app
    assert "export function createActions" in actions
    assert "export function createPollingController" in polling
    assert "window.ChilingTaskApi" not in polling


def test_chiling_workbench_css_has_a_plus_sections_and_responsive_rules():
    styles = read(WORKBENCH / "styles.css")

    for marker in [
        "/* 1. Design tokens */",
        "/* 2. Base */",
        "/* 3. Layout */",
        "/* 4. Components */",
        "/* 5. Pages */",
        "/* 6. Responsive */",
    ]:
        assert marker in styles

    assert "@media (max-width: 1180px)" in styles
    assert "@media (max-width: 760px)" in styles
    assert "min-width: 0" in styles
    assert "overflow-wrap: anywhere" in styles
