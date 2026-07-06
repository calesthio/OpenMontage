"""Shared MLX-runtime environment resolution for the ``mlx_*`` provider family.

Every MLX provider shells out to the sibling ``mlx-movie-director`` repo's
``run.py``. The availability contract is identical across them, so it is defined
once here and the providers delegate via ``resolve_mlx_env()``.

Env contract (mirrors the MLX repo's own CLAUDE.md):

* ``MLX_MOVIE_DIRECTOR_DIR``  — repo root containing ``python/mlx-movie-director/run.py``.
* ``MLX_VENV_PYTHON``         — the MLX venv interpreter (default
  ``<MLX_MOVIE_DIRECTOR_DIR>/python/venv/bin/python``). Per-machine, NOT auto-created.

The resolution is pure filesystem (+ an optional LM Studio socket probe for the
caption provider) — no subprocess spawn, so ``get_status()`` stays cheap.
"""

from __future__ import annotations

import os
import platform
import socket
from typing import Any

# Where the MLX repo lives. Configured by the OM deployment; the provider is
# UNAVAILABLE without it (we do not guess a sibling path — explicit config only).
MLX_DIR_ENV = "MLX_MOVIE_DIRECTOR_DIR"
MLX_PYTHON_ENV = "MLX_VENV_PYTHON"

# Relative layout inside the MLX repo (stable per the MLX repo's CLAUDE.md).
RUN_PY_REL = "python/mlx-movie-director/run.py"
VENV_PYTHON_REL = "python/venv/bin/python"
MODELS_REL = "mlx-models"

# Subdirectories under mlx-models/ whose presence implies at least one usable
# generation model is staged. transformer + vae are the minimum stack. Only the
# generation providers (mlx_image / mlx_video) need this — caption does not.
REQUIRED_MODEL_SUBDIRS = ("transformer", "vae")

# LM Studio (the local VLM server that run.py `caption` talks to). The caption
# provider needs this reachable; generation providers do not.
LM_STUDIO_HOST = "localhost"
LM_STUDIO_PORT = 1234
LM_STUDIO_URL = f"http://{LM_STUDIO_HOST}:{LM_STUDIO_PORT}/v1"


def lm_studio_reachable(timeout: float = 0.5) -> bool:
	"""True if a TCP connection to the LM Studio server port succeeds.

	Cheap socket probe (no HTTP) — used by ``mlx_caption``'s availability gate so
	the menu can show ANALYZE::mlx as unavailable when LM Studio isn't running,
	rather than failing at execute() time.
	"""
	try:
		with socket.create_connection((LM_STUDIO_HOST, LM_STUDIO_PORT), timeout=timeout):
			return True
	except OSError:
		return False


def resolve_mlx_env(
	*,
	need_models: bool = True,
	need_lm_studio: bool = False,
) -> dict[str, Any]:
	"""Resolve the MLX repo dir + venv interpreter (+ optional checks).

	Returns a dict with: ``mlx_dir``, ``run_py``, ``venv_python``, ``arm64``,
	``ok`` (bool), ``reason`` (str when not ok). Pure filesystem + socket — no
	subprocess spawn, so ``get_status()`` stays cheap.

	Parameters
	----------
	need_models:
		Generation providers (mlx_image / mlx_video) require the ``mlx-models``
		stack staged AND Apple Silicon. Caption does not (it talks to LM Studio).
	need_lm_studio:
		The caption provider requires LM Studio listening on localhost:1234.
		Generation providers do not.
	"""
	mlx_dir = os.environ.get(MLX_DIR_ENV)
	arm64 = platform.machine() in ("arm64", "aarch64")

	if not mlx_dir:
		return {
			"ok": False,
			"reason": f"{MLX_DIR_ENV} is not set (point it at the mlx-movie-director repo root).",
			"arm64": arm64,
		}
	mlx_dir = os.path.expanduser(mlx_dir)
	run_py = os.path.join(mlx_dir, RUN_PY_REL)
	if not os.path.isfile(run_py):
		return {
			"ok": False,
			"reason": f"{MLX_DIR_ENV}={mlx_dir} has no {RUN_PY_REL}.",
			"arm64": arm64,
			"mlx_dir": mlx_dir,
		}

	venv_python = os.environ.get(MLX_PYTHON_ENV) or os.path.join(mlx_dir, VENV_PYTHON_REL)
	if not os.path.isfile(venv_python):
		return {
			"ok": False,
			"reason": (
				f"MLX venv interpreter not found at {venv_python}. Recreate it: "
				f"uv venv {mlx_dir}/python/venv --python 3.12 && "
				f"uv pip install -r {mlx_dir}/python/mlx-movie-director/requirements.txt "
				f"--python {mlx_dir}/python/venv/bin/python"
			),
			"arm64": arm64,
			"mlx_dir": mlx_dir,
			"run_py": run_py,
		}

	if need_models:
		models_dir = os.path.join(mlx_dir, MODELS_REL)
		missing_subdirs = [s for s in REQUIRED_MODEL_SUBDIRS if not os.path.isdir(os.path.join(models_dir, s))]
		if missing_subdirs:
			return {
				"ok": False,
				"reason": (
					f"MLX models incomplete under {models_dir}: missing {missing_subdirs}. "
					f"Stage models before use."
				),
				"arm64": arm64,
				"mlx_dir": mlx_dir,
				"run_py": run_py,
				"venv_python": venv_python,
			}
		if not arm64:
			return {
				"ok": False,
				"reason": f"MLX runs on Apple Silicon only (got {platform.machine()}).",
				"arm64": False,
				"mlx_dir": mlx_dir,
				"run_py": run_py,
				"venv_python": venv_python,
			}

	if need_lm_studio and not lm_studio_reachable():
		return {
			"ok": False,
			"reason": (
				f"LM Studio not reachable at {LM_STUDIO_URL}. Start it and load a "
				f"vision model (e.g. Qwen3-VL 4B) — run.py `caption` talks to it."
			),
			"arm64": arm64,
			"mlx_dir": mlx_dir,
			"run_py": run_py,
			"venv_python": venv_python,
		}

	return {
		"ok": True,
		"arm64": arm64,
		"mlx_dir": mlx_dir,
		"run_py": run_py,
		"venv_python": venv_python,
	}
