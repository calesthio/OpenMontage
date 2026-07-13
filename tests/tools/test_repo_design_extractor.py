"""Focused tests for the repo design-system scanner.

Builds fixture mini-repos in tmp_path and asserts framework detection,
CSS-custom-property parsing with file+line provenance, candidate-file
classification, node degradation, caps, and determinism. No network.
"""

import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.base_tool import BaseTool, ToolStatus, ToolTier, ToolRuntime
from tools.tool_registry import ToolRegistry
from tools.analysis.repo_design_extractor import RepoDesignExtractor


@pytest.fixture
def next_repo(tmp_path):
    """Minimal Next.js + Tailwind repo with tokens, fonts, screens, components."""
    repo = tmp_path / "next-app"
    (repo / "app" / "settings").mkdir(parents=True)
    (repo / "components" / "ui").mkdir(parents=True)
    (repo / "node_modules" / "junk").mkdir(parents=True)

    (repo / "package.json").write_text(
        '{"name":"mini","dependencies":{"next":"14.0.0","react":"18.2.0"},'
        '"devDependencies":{"tailwindcss":"3.4.0"}}'
    )
    (repo / "tailwind.config.js").write_text(
        'module.exports = { theme: { extend: { colors: { brand: "#6366f1" } } } };'
    )
    (repo / "app" / "globals.css").write_text(
        ":root {\n"
        "  --background: #0a0a0f;\n"
        "  --primary: #6366f1;\n"
        "}\n"
        '@font-face { font-family: "Cal Sans"; src: url(/cal.woff2); }\n'
    )
    (repo / "app" / "layout.tsx").write_text(
        'import { Inter } from "next/font/google"\n'
        "export default function Layout({children}) { return <body>{children}</body> }\n"
    )
    (repo / "app" / "page.tsx").write_text("export default function Page(){return null}")
    (repo / "app" / "settings" / "page.tsx").write_text(
        "export default function Page(){return null}"
    )
    (repo / "components" / "ui" / "button.tsx").write_text("export function Button(){}")
    (repo / "node_modules" / "junk" / "x.css").write_text(":root { --evil: red; }")
    return repo


@pytest.fixture
def vue_repo(tmp_path):
    repo = tmp_path / "vue-app"
    (repo / "src" / "views").mkdir(parents=True)
    (repo / "src" / "components").mkdir(parents=True)
    (repo / "package.json").write_text('{"dependencies":{"vue":"3.4.0"}}')
    (repo / "src" / "views" / "Dashboard.vue").write_text("<template><main/></template>")
    (repo / "src" / "components" / "StatCard.vue").write_text("<template><div/></template>")
    return repo


# ---- Contract ----

class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(RepoDesignExtractor, BaseTool)

    def test_identity(self):
        t = RepoDesignExtractor()
        assert t.name == "repo_design_extractor"
        assert t.capability == "analysis"
        assert t.runtime == ToolRuntime.LOCAL
        assert t.tier == ToolTier.ANALYZE
        assert "repo-design-extraction" in t.agent_skills

    def test_always_available_and_free(self):
        t = RepoDesignExtractor()
        assert t.get_status() == ToolStatus.AVAILABLE
        assert t.estimate_cost({}) == 0.0


# ---- Registry discovery ----

class TestDiscovery:
    def test_discoverable(self):
        reg = ToolRegistry()
        reg.discover("tools")
        assert reg.get("repo_design_extractor") is not None

    def test_capability_routing(self):
        reg = ToolRegistry()
        reg.discover("tools")
        names = [t.name for t in reg.get_by_capability("analysis")]
        assert "repo_design_extractor" in names


# ---- Scan behavior ----

class TestScan:
    def test_framework_and_styling_detection(self, next_repo):
        res = RepoDesignExtractor().execute({"repo_path": str(next_repo)})
        assert res.success
        assert res.data["framework"] == "next"
        assert "tailwind" in res.data["styling_systems"]
        assert "css-variables" in res.data["styling_systems"]

    def test_vue_framework_detection(self, vue_repo):
        res = RepoDesignExtractor().execute({"repo_path": str(vue_repo)})
        assert res.success
        assert res.data["framework"] == "vue"
        # views become screen candidates; components indexed
        assert any(s["path"].endswith("Dashboard.vue") for s in res.data["screen_candidates"])
        assert any(c["name"] == "StatCard" for c in res.data["components_index"])

    def test_css_vars_carry_file_and_line_provenance(self, next_repo):
        res = RepoDesignExtractor().execute({"repo_path": str(next_repo)})
        by_name = {v["name"]: v for v in res.data["css_custom_properties"]}
        assert by_name["--primary"]["value"] == "#6366f1"
        assert by_name["--primary"]["file"] == "app/globals.css"
        assert by_name["--primary"]["line"] == 3
        assert by_name["--background"]["line"] == 2

    def test_node_modules_skipped(self, next_repo):
        res = RepoDesignExtractor().execute({"repo_path": str(next_repo)})
        assert not any(v["name"] == "--evil" for v in res.data["css_custom_properties"])
        assert not any("node_modules" in c["path"] for c in res.data["candidate_files"])

    def test_candidate_classification(self, next_repo):
        res = RepoDesignExtractor().execute({"repo_path": str(next_repo)})
        kinds = {c["path"]: c["kind"] for c in res.data["candidate_files"]}
        assert kinds["tailwind.config.js"] == "tailwind_config"
        assert kinds["app/globals.css"] == "css_variables"
        assert kinds["app/layout.tsx"] == "app_shell"

    def test_fonts_from_font_face_and_next_font(self, next_repo):
        res = RepoDesignExtractor().execute({"repo_path": str(next_repo)})
        families = {(f["family"], f["source"]) for f in res.data["fonts"]}
        assert ("Cal Sans", "font-face") in families
        assert ("Inter", "next/font") in families

    def test_app_router_routes(self, next_repo):
        res = RepoDesignExtractor().execute({"repo_path": str(next_repo)})
        routes = {s["path"]: s["route"] for s in res.data["screen_candidates"]}
        assert routes["app/page.tsx"] == "/"
        assert routes["app/settings/page.tsx"] == "/settings"
        # layout is not a screen
        assert "app/layout.tsx" not in routes

    def test_tailwind_theme_via_node_or_null(self, next_repo):
        """With node present the JS config evaluates; without it, degrades to null."""
        res = RepoDesignExtractor().execute({"repo_path": str(next_repo)})
        theme = res.data["tailwind_theme"]
        if shutil.which("node"):
            assert theme["extend"]["colors"]["brand"] == "#6366f1"
        else:
            assert theme is None

    def test_degrades_to_null_without_node(self, next_repo, monkeypatch):
        monkeypatch.setattr(shutil, "which", lambda _: None)
        res = RepoDesignExtractor().execute({"repo_path": str(next_repo)})
        assert res.success
        assert res.data["tailwind_theme"] is None

    def test_max_files_reports_truncation(self, next_repo):
        res = RepoDesignExtractor().execute({"repo_path": str(next_repo), "max_files": 2})
        assert res.success
        assert res.data["truncated"] is True
        assert res.data["files_scanned"] == 2

    def test_deterministic(self, next_repo):
        t = RepoDesignExtractor()
        a = t.execute({"repo_path": str(next_repo)}).data
        b = t.execute({"repo_path": str(next_repo)}).data
        assert a == b

    def test_writes_scan_report_artifact(self, next_repo, tmp_path):
        out = tmp_path / "artifacts" / "scan.json"
        res = RepoDesignExtractor().execute(
            {"repo_path": str(next_repo), "output_path": str(out)}
        )
        assert res.success
        assert res.artifacts == [str(out)]
        assert out.exists()

    def test_missing_repo_errors(self, tmp_path):
        res = RepoDesignExtractor().execute({"repo_path": str(tmp_path / "nope")})
        assert not res.success
        assert "not a directory" in res.error

    def test_never_writes_into_target_repo(self, next_repo):
        before = sorted(p.relative_to(next_repo) for p in next_repo.rglob("*"))
        RepoDesignExtractor().execute({"repo_path": str(next_repo)})
        after = sorted(p.relative_to(next_repo) for p in next_repo.rglob("*"))
        assert before == after
