"""Tests for math_animate scene_code safety scan (issue #219).

math_animate executes caller-supplied Python via Manim. The static scan blocks
the constructs an attack needs (system/network/subprocess/secret access) while
leaving genuine math-animation scenes untouched, and can be bypassed only with
an explicit allow_unsafe_code opt-out.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.graphics.math_animate import MathAnimate  # noqa: E402

SAFE_SCENE = (
    "from manim import *\n"
    "import numpy as np\n"
    "import math\n"
    "class Demo(Scene):\n"
    "    def construct(self):\n"
    "        self.play(Create(Circle(radius=np.pi / math.tau)))\n"
)


def test_safe_scene_passes_scan():
    assert MathAnimate._scan_scene_code(SAFE_SCENE) == []


@pytest.mark.parametrize(
    "snippet, needle",
    [
        ("import os\nos.environ", "import 'os'"),
        ("import subprocess", "import 'subprocess'"),
        ("import socket", "import 'socket'"),
        ("from urllib.request import urlopen", "from 'urllib.request' import ..."),
        ("import requests", "import 'requests'"),
    ],
)
def test_blocks_dangerous_imports(snippet, needle):
    code = f"from manim import *\n{snippet}\nclass S(Scene):\n    def construct(self):\n        pass\n"
    violations = MathAnimate._scan_scene_code(code)
    assert needle in violations


@pytest.mark.parametrize("call", ["eval", "exec", "compile", "open", "__import__"])
def test_blocks_dangerous_calls(call):
    code = (
        "from manim import *\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        f"        {call}('x')\n"
    )
    assert f"use of '{call}'" in MathAnimate._scan_scene_code(code)


def test_blocks_no_import_builtins_secret_read():
    # Regression for the reported bypass: no dangerous import, secret read via
    # __builtins__ indexing. The whole expression roots on the bare __builtins__
    # name (the 'open' inside [] is a string literal), so blocking that name
    # blocks the payload.
    code = (
        "from manim import *\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        __builtins__['open']('.env').read()\n"
    )
    assert "use of '__builtins__'" in MathAnimate._scan_scene_code(code)


def test_blocks_getattr_reflection_bypass():
    # getattr-based attribute reflection is a classic denylist evasion; blocking
    # the getattr name removes the primitive.
    code = (
        "from manim import *\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        cls = getattr(object(), '__class__')\n"
    )
    assert "use of 'getattr'" in MathAnimate._scan_scene_code(code)


def test_blocks_aliased_dangerous_builtin():
    # Binding a blocked builtin to another name must still trip on the name use.
    code = (
        "from manim import *\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        f = open\n"
        "        f('.env')\n"
    )
    assert "use of 'open'" in MathAnimate._scan_scene_code(code)


def test_blocks_sandbox_escape_dunders():
    code = (
        "from manim import *\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        ().__class__.__bases__[0].__subclasses__()\n"
    )
    violations = MathAnimate._scan_scene_code(code)
    assert "attribute access '.__bases__'" in violations
    assert "attribute access '.__subclasses__'" in violations


def test_syntax_error_defers_to_manim():
    # A parse failure must not mask as a safety violation; Manim reports it.
    assert MathAnimate._scan_scene_code("class S(Scene):\n  def construct(self)\n") == []


def test_execute_blocks_dangerous_code_before_running_manim(monkeypatch):
    # Pretend manim is installed so execute() reaches the safety gate rather
    # than short-circuiting on a missing binary. The scan must reject before any
    # subprocess runs.
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/manim")

    def boom(*a, **k):  # subprocess must never be reached
        raise AssertionError("subprocess.run should not be called for blocked code")

    monkeypatch.setattr("subprocess.run", boom)

    dangerous = (
        "from manim import *\n"
        "import os\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        print(os.environ)\n"
    )
    result = MathAnimate().execute({"scene_code": dangerous})
    assert result.success is False
    assert "safety scan" in result.error
    assert "allow_unsafe_code" in result.error


def test_allow_unsafe_code_bypasses_scan(monkeypatch):
    # With the opt-out, execution proceeds past the scan to Manim (which we stub
    # to fail); the failure must NOT be the safety-scan message.
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/manim")

    class FakeProc:
        returncode = 1
        stderr = "manim ran"
        stdout = ""

    monkeypatch.setattr("subprocess.run", lambda *a, **k: FakeProc())

    dangerous = (
        "from manim import *\n"
        "import os\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        print(os.environ)\n"
    )
    result = MathAnimate().execute({"scene_code": dangerous, "allow_unsafe_code": True})
    assert result.success is False
    assert "safety scan" not in (result.error or "")
