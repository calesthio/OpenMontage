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
    assert "dunder attribute access '.__class__'" in violations
    assert "dunder attribute access '.__bases__'" in violations
    assert "dunder attribute access '.__subclasses__'" in violations


def test_blocks_builtins_module_via_print_self():
    # Regression for the reported no-import bypass: print.__self__ is the
    # builtins module, reachable without an import, a bare open/__builtins__/
    # getattr, or a blocked name. Blocking all reflection dunders closes it.
    code = (
        "from manim import *\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        print.__self__.open('.env').read()\n"
    )
    assert "dunder attribute access '.__self__'" in MathAnimate._scan_scene_code(code)


def test_super_init_is_allowed():
    # A legitimate custom Mobject with super().__init__() must not be blocked —
    # __init__ (and __name__) are the only permitted dunders.
    code = (
        "from manim import *\n"
        "class Widget(VGroup):\n"
        "    def __init__(self, **kwargs):\n"
        "        super().__init__(**kwargs)\n"
        "        self.add(Circle())\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Widget())\n"
    )
    assert MathAnimate._scan_scene_code(code) == []


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


# --- Regression tests for issue #864: a blocked module reached through an
# imported module's attribute (denylist evasion via re-export). The old scan
# saw only the import root (`zipfile` is not blocked) and the attribute name
# (`.os` is not a dunder), so all of these passed with zero violations.


def test_blocks_os_via_reexported_module():
    code = (
        "from manim import *\n"
        "import zipfile\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        zipfile.os.system('id')\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_blocks_os_via_reexport_inside_construct():
    code = (
        "from manim import *\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        import tarfile\n"
        "        tarfile.os.popen('id').read()\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_blocks_aliased_reexport():
    code = (
        "from manim import *\n"
        "import zipfile as z\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        z.os.system('id')\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_blocks_reexport_via_rebinding():
    code = (
        "from manim import *\n"
        "import zipfile\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        x = zipfile\n"
        "        x.os.system('id')\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_blocks_from_import_of_blocked_name():
    code = (
        "from manim import *\n"
        "from zipfile import os\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        os.system('id')\n"
    )
    violations = MathAnimate._scan_scene_code(code)
    assert any("dangerous name(s): os" in v for v in violations)


def test_blocks_star_import_from_non_manim():
    code = (
        "from manim import *\n"
        "from zipfile import *\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        pass\n"
    )
    assert "from 'zipfile' import *" in MathAnimate._scan_scene_code(code)


def test_safe_scene_attribute_access_still_passes():
    # numpy/math attribute access used by the safe scene must keep passing.
    assert MathAnimate._scan_scene_code(SAFE_SCENE) == []


# --- Follow-ups to the PR #865 review (Copilot, 2026-11-05; calesthio,
# 2026-11-07): the first version of the fix only matched the blocked
# module's literal attribute spelling (`zipfile.os`) and only tracked plain
# Name rebinding, so renamed re-exports (`random._os` is the real `os`
# module) and alias forms (attribute, tuple-unpacking and container
# aliases) still passed with zero violations. The scan now resolves
# attribute chains against the real modules, so all of these are blocked.


def test_blocks_renamed_reexport_random_os():
    code = (
        "from manim import *\n"
        "import random\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        random._os.getcwd()\n"
    )
    violations = MathAnimate._scan_scene_code(code)
    assert any(
        "._os" in v and "re-exports blocked module 'os'" in v for v in violations
    )


def test_blocks_reexport_via_attribute_alias():
    # Copilot: `self.z = zipfile; self.z.os.getcwd()` passed the scan.
    code = (
        "from manim import *\n"
        "import zipfile\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        self.z = zipfile\n"
        "        self.z.os.getcwd()\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_blocks_renamed_reexport_via_attribute_alias():
    code = (
        "from manim import *\n"
        "import random\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        self.z = random\n"
        "        self.z._os.getcwd()\n"
    )
    violations = MathAnimate._scan_scene_code(code)
    assert any("re-exports blocked module 'os'" in v for v in violations)


def test_blocks_reexport_via_tuple_unpacking():
    # Copilot: `z, = (zipfile,); z.os.getcwd()` passed the scan.
    code = (
        "from manim import *\n"
        "import zipfile\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        z, = (zipfile,)\n"
        "        z.os.system('id')\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_blocks_renamed_reexport_via_tuple_unpacking():
    code = (
        "from manim import *\n"
        "import random\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        r, = (random,)\n"
        "        r._os.getcwd()\n"
    )
    violations = MathAnimate._scan_scene_code(code)
    assert any("re-exports blocked module 'os'" in v for v in violations)


def test_blocks_reexport_via_container():
    # Copilot: `z = [zipfile]; z[0].os.getcwd()` passed the scan.
    code = (
        "from manim import *\n"
        "import zipfile\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        z = [zipfile]\n"
        "        z[0].os.system('id')\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_blocks_reexport_via_dict_container():
    code = (
        "from manim import *\n"
        "import zipfile\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        z = {'k': zipfile}\n"
        "        z['k'].os.system('id')\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_blocks_renamed_reexport_via_container():
    code = (
        "from manim import *\n"
        "import random\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        z = [random]\n"
        "        z[0]._os.getcwd()\n"
    )
    violations = MathAnimate._scan_scene_code(code)
    assert any("re-exports blocked module 'os'" in v for v in violations)


def test_blocks_blocked_module_via_rebinding():
    # Once a binding IS the blocked module, any attribute use on it is a
    # violation, not just the access that reached it.
    code = (
        "from manim import *\n"
        "import zipfile\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        o = zipfile.os\n"
        "        o.system('id')\n"
    )
    assert (
        "blocked module 'os' attribute '.system'"
        in MathAnimate._scan_scene_code(code)
    )


def test_blocks_renamed_blocked_module_via_rebinding():
    code = (
        "from manim import *\n"
        "import random\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        o = random._os\n"
        "        o.getcwd()\n"
    )
    assert (
        "blocked module 'os' attribute '.getcwd'"
        in MathAnimate._scan_scene_code(code)
    )


def test_blocks_from_import_of_renamed_reexport():
    code = (
        "from manim import *\n"
        "from random import _os\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        _os.getcwd()\n"
    )
    violations = MathAnimate._scan_scene_code(code)
    assert any("re-exported blocked module '_os'" in v for v in violations)


def test_blocks_reexport_via_for_loop_alias():
    code = (
        "from manim import *\n"
        "import zipfile\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        for z in [zipfile]:\n"
        "            z.os.system('id')\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_blocks_reexport_via_function_default():
    code = (
        "from manim import *\n"
        "import zipfile\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        def f(m=zipfile):\n"
        "            m.os.system('id')\n"
    )
    assert "imported module attribute '.os'" in MathAnimate._scan_scene_code(code)


def test_safe_attribute_and_container_use_still_passes():
    # Legitimate scenes use attribute assignment, tuple unpacking and
    # containers too; none of that may be blocked.
    code = (
        "from manim import *\n"
        "import numpy as np\n"
        "import random\n"
        "class S(Scene):\n"
        "    def construct(self):\n"
        "        self.dot = Dot()\n"
        "        a, b = np.pi, np.e\n"
        "        shapes = [Circle(), Square()]\n"
        "        self.play(Create(shapes[0]))\n"
        "        self.play(Create(Circle(radius=random.random())))\n"
    )
    assert MathAnimate._scan_scene_code(code) == []
