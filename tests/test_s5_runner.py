"""Static guards for tools/kaggle_bridge/s5_bakeoff_run.py (S5-2).

The kernel copy is only exercised on Kaggle, so these tests catch the cheap
mistakes locally before burning a GPU run:
  * the module compiles;
  * `global X` is declared before the first use of X in that function
    (the S5 SDXL run 1 died on exactly this: a SyntaxError);
  * no bitsandbytes / CPU fallback / git-main diffusers in the runner;
  * fp16 and the two-attempt install rule are still in place.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNNER = REPO / "tools/kaggle_bridge/s5_bakeoff_run.py"
SRC = RUNNER.read_text(encoding="utf-8")
TREE = ast.parse(SRC)


def _funcs(tree):
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def test_runner_compiles():
    compile(SRC, str(RUNNER), "exec")


def test_global_declared_before_use():
    for fn in _funcs(TREE):
        names = set()
        decl_line = {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Global):
                for n in node.names:
                    names.add(n)
                    decl_line[n] = node.lineno
        if not names:
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id in names:
                    assert node.lineno > decl_line[node.id], (
                        f"{fn.name}: '{node.id}' used at line {node.lineno} "
                        f"before 'global {node.id}' at line {decl_line[node.id]}")


def test_no_forbidden_routes():
    low = SRC.lower()
    assert "import bitsandbytes" not in low, "no bitsandbytes in the S5 runner"
    assert "bitsandbytesconfig" not in low, "no 4-bit quantisation in the S5 runner"
    assert "git+https://github.com/huggingface/diffusers" not in SRC, \
        "S5 uses released diffusers only"
    assert "torch.float16" in SRC or "float16" in SRC, "fp16 only"
    assert "cpu_fallback" in SRC


def test_two_install_attempts_max():
    assert "ATTEMPTS_COMMON" in SRC and "ATTEMPTS_ZIMAGE" in SRC
    import importlib.util
    spec = importlib.util.spec_from_file_location("s5_runner", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["s5_runner"] = mod
    spec.loader.exec_module(mod)  # module-level only; main() is guarded
    assert len(mod.ATTEMPTS_COMMON) == 2
    assert len(mod.ATTEMPTS_ZIMAGE) == 2


def test_black_nan_oom_accounting_present():
    for token in ("black_count", "nan_count", "oom_count", "peak_vram_mb",
                  "steady_state_sec_per_image", "load_seconds"):
        assert token in SRC, f"manifest field {token} missing"


def test_probe_classes_per_model():
    import importlib.util
    spec = importlib.util.spec_from_file_location("s5_runner_probe", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["s5_runner_probe"] = mod
    spec.loader.exec_module(mod)
    assert mod.PROBE_CLASSES["zimage"] == ["ZImagePipeline"]
    assert mod.PROBE_CLASSES["klein"][0] == "Flux2Pipeline"
    assert mod.PROBE_CLASSES["sdxl"] == ["StableDiffusionXLPipeline"]


def test_klein_uses_vendor_class_and_offload():
    assert '"Flux2KleinPipeline"' in SRC, "klein needs the FLUX.2 klein class"
    assert "enable_model_cpu_offload()" in SRC
    # offload must be enabled at load time for klein, before generation
    assert SRC.index("enable_model_cpu_offload()") < SRC.index("for rj in renders")
