"""ACE-Step 1.5 music generation via a locally-hosted REST API.

ACE-Step 1.5 is a Hybrid LM + Diffusion Transformer music model with an
MIT license — output is fully owned. Unlike `music_gen` (ElevenLabs API,
paid) or `musicgen_local` (instrumental only, Meta MusicGen), ACE-Step
supports lyrics, vocals, BPM/key/time-signature control, and compositions
up to 10 minutes — at $0 per track on local hardware.

This tool talks to a local `acestep-api` REST server (default
http://127.0.0.1:8001) running in ACE-Step's own `uv`-managed Python env
at `ACESTEP_HOME` (default `~/ACE-Step-1.5`). Isolation is mandatory —
ACE-Step pins `torch==2.7.1+cu128` from a custom PyTorch index and that
wheel conflicts with the torch that `musicgen_local` + `f5tts` already
use in OpenMontage's main env.

Auto-start: if the server isn't responding on `/health`, this tool launches
`uv run --no-sync acestep-api` as a detached background process, writes
the PID to `~/.cache/openmontage/acestep_server.pid`, and polls until the
server is ready. First boot of a fresh install downloads model weights
(XL turbo DiT ~9 GB + 1.7B LM) and can take several minutes. Subsequent
boots are warm in ~30 seconds.

We only ever stop processes whose PID we captured ourselves — never broad
image-name kills — so the server is safe to share with other workloads on
the same machine. The server is left running between calls so subsequent
jobs don't pay the cold-start cost.

Configuration via environment variables:
  - `ACESTEP_HOME`            ACE-Step repo location (default ~/ACE-Step-1.5)
  - `ACESTEP_API_HOST`        Bind/connect host (default 127.0.0.1)
  - `ACESTEP_API_PORT`        Bind/connect port (default 8001)
  - `ACESTEP_CHECKPOINTS_DIR` Override weights directory (default <home>/checkpoints).
                              ACE-Step's api_server hardcodes the path to
                              <repo>/checkpoints, so to keep weights outside
                              the checkout, point this var at the real
                              location AND symlink/junction
                              <home>/checkpoints to it.
  - `CUDA_VISIBLE_DEVICES`    Pin to a specific GPU; otherwise the tool
                              auto-pins to the largest visible GPU.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


# --- Configurable via env, with sensible cross-platform defaults ---
DEFAULT_ACESTEP_HOME = str(Path.home() / "ACE-Step-1.5")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
DEFAULT_DIT_MODEL = "acestep-v15-xl-turbo"
DEFAULT_LM_MODEL = "acestep-5Hz-lm-1.7B"
DEFAULT_LM_BACKEND = "vllm"

# Where we stash the server PID + log so future invocations / sessions can
# tell whether a server we previously launched is still alive without
# touching processes we didn't spawn.
PID_FILE = Path.home() / ".cache" / "openmontage" / "acestep_server.pid"
LOG_FILE = Path.home() / ".cache" / "openmontage" / "acestep_server.log"


def stop_server_tree(pid_file: Path = PID_FILE, graceful_seconds: float = 3.0) -> dict[str, Any]:
    """Stop the acestep-api server tree rooted at the captured PID and clear the file.

    Only ever stops processes whose PID we recorded at launch — walks that PID's
    descendant tree, never matches by image name. Tries graceful terminate first
    (TERM on POSIX, kill() on Windows which sends WM_CLOSE/TerminateProcess),
    waits up to `graceful_seconds`, then force-kills survivors.

    Returns a dict describing what happened — empty children/parent lists mean
    the PID file was missing or already stale. Callers can decide to log/surface.
    """
    result: dict[str, Any] = {
        "pid_file": str(pid_file),
        "parent_pid": None,
        "children_pids": [],
        "stopped": [],
        "survivors": [],
        "pid_file_removed": False,
        "notes": [],
    }

    if not pid_file.exists():
        result["notes"].append("PID file does not exist; nothing to stop")
        return result

    try:
        parent_pid = int(pid_file.read_text().strip())
    except (ValueError, OSError) as exc:
        result["notes"].append(f"could not parse PID file: {exc}")
        try:
            pid_file.unlink()
            result["pid_file_removed"] = True
        except OSError:
            pass
        return result

    result["parent_pid"] = parent_pid

    try:
        import psutil  # local import — keep tool importable without psutil
    except ImportError:
        result["notes"].append(
            "psutil not installed; falling back to platform-specific stop"
        )
        return _stop_server_tree_no_psutil(pid_file, parent_pid, result)

    try:
        parent = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        result["notes"].append(f"PID {parent_pid} not running (stale PID file)")
        try:
            pid_file.unlink()
            result["pid_file_removed"] = True
        except OSError:
            pass
        return result

    descendants = parent.children(recursive=True)
    result["children_pids"] = [p.pid for p in descendants]
    targets = descendants + [parent]  # stop children first to avoid orphans

    for p in targets:
        try:
            p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    gone, alive = psutil.wait_procs(targets, timeout=graceful_seconds)
    result["stopped"].extend(p.pid for p in gone)

    for p in alive:
        try:
            p.kill()
            result["stopped"].append(p.pid)
            result["notes"].append(f"PID {p.pid} required SIGKILL/force")
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            result["survivors"].append({"pid": p.pid, "reason": str(exc)})

    try:
        pid_file.unlink()
        result["pid_file_removed"] = True
    except OSError as exc:
        result["notes"].append(f"could not remove PID file: {exc}")

    return result


def _stop_server_tree_no_psutil(
    pid_file: Path, parent_pid: int, result: dict[str, Any]
) -> dict[str, Any]:
    """Fallback when psutil isn't installed. Tree-kill semantics on both OSes.

    Windows: `taskkill /F /T /PID <pid>` — forced tree-kill rooted at OUR captured PID.
    POSIX: SIGTERM then SIGKILL to the *process group*. We launched the server
        with `start_new_session=True` so the captured PID is its own process
        group leader (pgid == pid); signaling the group atomically reaches the
        whole tree, matching Windows `/T` semantics. Same image-name-safety
        contract — the group ID is the PID we recorded ourselves, not a broad
        match.
    """
    if sys.platform == "win32":
        try:
            cp = subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(parent_pid)],
                capture_output=True, text=True, timeout=10,
            )
            if cp.returncode == 0:
                result["stopped"].append(parent_pid)
            else:
                result["notes"].append(
                    f"taskkill failed (rc={cp.returncode}): "
                    f"{(cp.stderr or cp.stdout or '').strip()}"
                )
        except Exception as exc:
            result["notes"].append(f"taskkill invocation failed: {exc}")
    else:
        import signal as _sig
        try:
            os.killpg(parent_pid, _sig.SIGTERM)
            time.sleep(2.0)
            try:
                os.kill(parent_pid, 0)
                os.killpg(parent_pid, _sig.SIGKILL)
                result["notes"].append(f"process group {parent_pid} required SIGKILL")
            except ProcessLookupError:
                pass
            result["stopped"].append(parent_pid)
        except ProcessLookupError:
            result["notes"].append(f"PID {parent_pid} already dead")
        except PermissionError as exc:
            result["notes"].append(
                f"insufficient permission to signal process group {parent_pid}: {exc}"
            )
        except Exception as exc:
            result["notes"].append(f"failed to signal process group {parent_pid}: {exc}")

    try:
        pid_file.unlink()
        result["pid_file_removed"] = True
    except OSError as exc:
        result["notes"].append(f"could not remove PID file: {exc}")

    return result


# Generous bounds for first-run model download. Subsequent boots are fast.
SERVER_BOOT_TIMEOUT_SECONDS = 600  # 10 min — allows first-time model download
JOB_POLL_INTERVAL_SECONDS = 2.0
# Per-job server-side ceiling. ACE-Step's own default of 600s routinely
# fires on a contended GPU because the LM Phase 2 alone can take 15+
# minutes under memory pressure. We lift it to 30 min and pad the client
# poll above it so the server's structured failure surfaces before the
# client gives up.
SERVER_GENERATION_TIMEOUT_SECONDS = 1800
CLIENT_POLL_TIMEOUT_PAD_SECONDS = 120

# Warn when free VRAM on the active GPU drops below this. Sustained
# generation under heavy contention has produced 100-1000x LM slowdowns.
GPU_MIN_FREE_VRAM_WARN_MB = 6000


class AceStepMusic(BaseTool):
    name = "acestep_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "acestep"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    # Not modeled as python:/cmd: because the dependency is "a uv env at
    # ACESTEP_HOME with weights downloaded" — too compound for the simple
    # check_dependencies probes. get_status() does the real check.
    dependencies = []
    install_instructions = (
        "ACE-Step 1.5 runs in its own uv-managed env to avoid torch wheel\n"
        "conflicts with OpenMontage's main env. One-time setup:\n"
        "  1. Install uv:\n"
        "       Linux/macOS: curl -LsSf https://astral.sh/uv/install.sh | sh\n"
        "       Windows:     powershell -ExecutionPolicy Bypass -c \"irm https://astral.sh/uv/install.ps1 | iex\"\n"
        "  2. git clone https://github.com/ace-step/ACE-Step-1.5 ~/ACE-Step-1.5\n"
        "       (or set ACESTEP_HOME to a different clone location)\n"
        "  3. cd <acestep home> && uv sync\n"
        "First boot downloads ~10 GB of weights into <acestep_home>/checkpoints.\n"
        "To keep weights outside the git checkout, set ACESTEP_CHECKPOINTS_DIR\n"
        "to the real location AND symlink (or Windows directory-junction)\n"
        "<acestep_home>/checkpoints at it — ACE-Step's api_server hardcodes the\n"
        "weights path to <repo>/checkpoints, so the symlink is what redirects.\n"
        "The tool auto-launches the REST server (acestep-api) on first use."
    )
    fallback = "musicgen_local"
    fallback_tools = ["musicgen_local", "freesound_music", "music_gen", "pixabay_music"]
    agent_skills = ["acestep", "music"]

    capabilities = [
        "generate_music",
        "instrumental_only",
        "generate_with_lyrics",
        "generate_with_vocals",
        "offline_generation",
        "bpm_control",
        "key_control",
        "long_form_up_to_10_min",
    ]
    supports = {
        "voice_cloning": False,
        "lyrics": True,
        "offline": True,
        "duration_control": True,
        "seed": True,
        "bpm": True,
        "key_scale": True,
        "cover_from_reference": True,
    }
    best_for = [
        "songs with vocals + lyrics (jingles, branded outros) — MIT-licensed, owned output",
        "longer instrumental beds (60s+) with explicit BPM/key/time-signature control",
        "atmospheric underscore when MusicGen feels generic — ACE-Step XL is rated between Suno v4.5 and v5",
        "fully offline music generation with zero per-track cost",
    ]
    not_good_for = [
        "sub-10-second stings (server overhead dominates; use sound_effects)",
        "low-VRAM machines (<12 GB) — XL-turbo + 1.7B LM falls back to CPU offload below that and slows 50-100x",
        "voice cloning — use f5tts for speech, not music",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Music description. Layer genre, instruments, mood, era, "
                    "production style, vocal character (or 'instrumental'). "
                    "Don't put BPM/key in the prompt — use the bpm/key_scale params. "
                    "Example: 'slow somber piano underscore, sparse arrangement, "
                    "contemplative documentary score, warm strings building'."
                ),
            },
            "lyrics": {
                "type": "string",
                "default": "",
                "description": (
                    "Optional lyrics. Use structure tags like [Verse]/[Chorus]/[Bridge]. "
                    "UPPERCASE for high intensity, (parentheses) for backing vocals. "
                    "Empty string = instrumental."
                ),
            },
            "duration_seconds": {
                "type": "number",
                "default": 30,
                "minimum": 10,
                "maximum": 600,
                "description": "Target duration. ACE-Step generates very close to the requested length.",
            },
            "bpm": {
                "type": "integer",
                "minimum": 30,
                "maximum": 300,
                "description": "Tempo. Omit to let the LM choose based on prompt.",
            },
            "key_scale": {
                "type": "string",
                "default": "",
                "description": "Key/scale, e.g. 'C Major', 'A Minor'. Empty = LM decides.",
            },
            "time_signature": {
                "type": "string",
                "default": "",
                "description": "Time signature: '2', '3', '4', or '6'. Empty = LM decides.",
            },
            "model": {
                "type": "string",
                "default": DEFAULT_DIT_MODEL,
                "description": "DiT checkpoint name. Default acestep-v15-xl-turbo.",
            },
            "inference_steps": {
                "type": "integer",
                "default": 8,
                "minimum": 1,
                "maximum": 200,
                "description": "Diffusion steps. Turbo models: 1-20 (8 recommended). Base: 32-64.",
            },
            "thinking": {
                "type": "boolean",
                "default": True,
                "description": (
                    "Use the 5Hz LM to generate audio codes before DiT (Chain-of-Thought "
                    "planning). Strongly recommended for quality."
                ),
            },
            "audio_format": {
                "type": "string",
                "default": "mp3",
                "enum": ["mp3", "wav", "flac", "opus", "aac"],
            },
            "seed": {
                "type": "integer",
                "default": 42,
                "description": "Locks the random seed for reproducibility.",
            },
            "output_path": {
                "type": "string",
                "description": "Where to write the generated audio.",
            },
            "shutdown_after_generation": {
                "type": "boolean",
                "default": False,
                "description": (
                    "If True, stop the acestep-api server (parent + descendants) "
                    "after the audio is written and clear the PID file. "
                    "Default False — leaves the server warm for back-to-back "
                    "jobs. Set True for one-shot runs so the ~12-18 GB of VRAM "
                    "the model holds is released immediately."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=16000, vram_mb=12000, disk_mb=20000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout", "5xx"])
    idempotency_key_fields = ["prompt", "lyrics", "duration_seconds", "model", "seed", "bpm", "key_scale"]
    side_effects = [
        "writes audio file to output_path",
        "may launch a background acestep-api server (PID tracked in ~/.cache/openmontage/acestep_server.pid)",
        "first run downloads ~10 GB of model weights into ACE-Step's HuggingFace cache",
    ]
    user_visible_verification = [
        "Listen for prompt fidelity, lyric accuracy (if any), and natural arrangement",
        "Check that BPM/key requests match what came out",
    ]

    # ---- status & launch ----

    @staticmethod
    def _acestep_home() -> Path:
        return Path(os.environ.get("ACESTEP_HOME", DEFAULT_ACESTEP_HOME))

    @classmethod
    def _default_checkpoints_dir(cls) -> str:
        return str(cls._acestep_home() / "checkpoints")

    @staticmethod
    def _server_url() -> str:
        host = os.environ.get("ACESTEP_API_HOST", DEFAULT_HOST)
        port = os.environ.get("ACESTEP_API_PORT", str(DEFAULT_PORT))
        return f"http://{host}:{port}"

    def _server_healthy(self, timeout: float = 1.0, require_models: bool = True) -> bool:
        """Probe /health. By default also requires models to be initialized.

        `/health` returns 200 as soon as uvicorn is up, but `models_initialized`
        stays false until the DiT (and optionally LM) are loaded. If we declare
        ready on the bare 200 we'd race the model load on the first job.
        Pass require_models=False if you just want to know the HTTP server
        is reachable.
        """
        url = f"{self._server_url()}/health"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                if resp.status != 200:
                    return False
                if not require_models:
                    return True
                body = json.loads(resp.read().decode("utf-8"))
                return bool((body.get("data") or {}).get("models_initialized"))
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            return False

    def get_status(self) -> ToolStatus:
        """AVAILABLE if the server is up OR the local env is provisioned.

        We don't block on a slow health probe here because the registry
        calls get_status() during discovery and we don't want every
        `registry.discover()` to pay the probe latency. The probe lives
        in execute() instead.
        """
        home = self._acestep_home()
        if not (home / "pyproject.toml").exists():
            return ToolStatus.UNAVAILABLE
        if not (home / ".venv").exists():
            # Env hasn't been provisioned yet (uv sync hasn't run).
            return ToolStatus.DEGRADED
        return ToolStatus.AVAILABLE

    @staticmethod
    def _find_uv_exe(env: dict[str, str]) -> Optional[str]:
        """Locate the `uv` executable. PATH first, then standard install dirs."""
        import shutil as _sh
        uv_exe = _sh.which("uv")
        if uv_exe:
            return uv_exe

        home = Path.home()
        candidates: list[Path] = []
        if sys.platform == "win32":
            candidates.extend([
                home / ".local" / "bin" / "uv.exe",
                Path(env.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "uv.exe",
            ])
        else:
            candidates.extend([
                home / ".local" / "bin" / "uv",
                home / ".cargo" / "bin" / "uv",
                Path("/usr/local/bin/uv"),
            ])
        for c in candidates:
            if c.is_file():
                return str(c)
        return None

    def _launch_server(self) -> int:
        """Spawn the acestep-api server detached and return its PID.

        On Windows: CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS so the
        server outlives this Python process. On POSIX: start_new_session=True
        for the same effect. stdout/stderr go to a log file so we can
        diagnose boot failures.
        """
        home = self._acestep_home()
        if not (home / "pyproject.toml").exists():
            raise RuntimeError(
                f"ACE-Step home at {home} does not contain pyproject.toml. "
                f"Clone the repo or set ACESTEP_HOME."
            )

        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        # Force UTF-8 stdout/stderr in the spawned server so warnings that
        # contain non-ASCII (✓, em-dashes, etc.) don't crash startup. The
        # ACE-Step LM init path prints a warning with Unicode chars that
        # blows up on Windows cp1252 stdout with `UnicodeEncodeError:
        # 'charmap' codec can't encode characters` and triggers
        # "Application startup failed. Exiting." No-op on Linux/macOS.
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # Make CUDA's device numbering match what `nvidia-smi` shows. The
        # CUDA runtime's default is FASTEST_FIRST, which silently reorders
        # devices on multi-GPU machines — a perceived `CUDA_VISIBLE_DEVICES=1`
        # can end up pinning to a different physical card than the user
        # intended. PCI_BUS_ID makes the numbering match nvidia-smi so user
        # pinning Just Works.
        env.setdefault("CUDA_DEVICE_ORDER", "PCI_BUS_ID")

        # Auto-pin to the largest GPU if the user hasn't already chosen one.
        # ACE-Step needs ~12 GB for the XL turbo path; running on a smaller
        # GPU auto-enables CPU offload and slows generation 50-100x.
        chosen_gpu = self._auto_select_gpu(env)
        if chosen_gpu is not None:
            env["CUDA_VISIBLE_DEVICES"] = chosen_gpu

        # Pre-configure the server with our chosen models so we don't have
        # to call /v1/init after boot.
        env.setdefault("ACESTEP_CONFIG_PATH", DEFAULT_DIT_MODEL)
        env.setdefault("ACESTEP_LM_MODEL_PATH", DEFAULT_LM_MODEL)
        env.setdefault("ACESTEP_LM_BACKEND", DEFAULT_LM_BACKEND)
        env.setdefault("ACESTEP_API_HOST", DEFAULT_HOST)
        env.setdefault("ACESTEP_API_PORT", str(DEFAULT_PORT))
        # Don't prompt for updates on startup.
        env.setdefault("ACESTEP_NO_UPDATE_CHECK", "true")
        # Eagerly initialize models at startup so the first job doesn't race
        # the (multi-GB) download/load. _server_healthy() will not return
        # True until models_initialized is set.
        env.setdefault("ACESTEP_NO_INIT", "false")
        env.setdefault("ACESTEP_INIT_LLM", "true")
        # Lift the server's per-job hard ceiling — see SERVER_GENERATION_TIMEOUT_SECONDS.
        env.setdefault("ACESTEP_GENERATION_TIMEOUT", str(SERVER_GENERATION_TIMEOUT_SECONDS))
        # ACE-Step's api_server.py computes the checkpoints path from the
        # repo root, so this env var only reaches CLI helpers (acestep-download
        # etc.). To redirect the actual weights, see install_instructions —
        # the mechanism is a symlink/junction at <repo>/checkpoints.
        env.setdefault("ACESTEP_CHECKPOINTS_DIR", self._default_checkpoints_dir())

        uv_exe = self._find_uv_exe(env)
        if uv_exe is None:
            install_hint = (
                "  powershell -ExecutionPolicy Bypass -c \"irm https://astral.sh/uv/install.ps1 | iex\""
                if sys.platform == "win32"
                else "  curl -LsSf https://astral.sh/uv/install.sh | sh"
            )
            raise RuntimeError("uv executable not found. Install with:\n" + install_hint)

        cmd = [
            uv_exe, "run", "--no-sync",
            "acestep-api",
            "--host", env["ACESTEP_API_HOST"],
            "--port", env["ACESTEP_API_PORT"],
        ]

        # Detach so the server outlives this process.
        popen_extras: dict[str, Any] = {}
        if sys.platform == "win32":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            popen_extras["creationflags"] = (
                DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
            )
        else:
            popen_extras["start_new_session"] = True

        log_fh = open(LOG_FILE, "ab", buffering=0)
        proc = subprocess.Popen(
            cmd,
            cwd=str(home),
            env=env,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            **popen_extras,
        )

        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(proc.pid))
        return proc.pid

    def _wait_for_server(self, timeout: float = SERVER_BOOT_TIMEOUT_SECONDS) -> bool:
        """Poll /health until 200 or timeout. Returns True on success."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._server_healthy(timeout=2.0):
                return True
            time.sleep(2.0)
        return False

    @staticmethod
    def _pid_is_alive(pid: int) -> bool:
        """Check whether a PID is currently running.

        Only ever inspect — never kill by image name. This is a shared-machine
        safe pattern: we'd rather wait for an unknown workload than risk
        killing one that isn't ours.
        """
        if pid <= 0:
            return False
        if sys.platform == "win32":
            try:
                import ctypes
                PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
                handle = ctypes.windll.kernel32.OpenProcess(
                    PROCESS_QUERY_LIMITED_INFORMATION, False, pid
                )
                if not handle:
                    return False
                exit_code = ctypes.c_ulong()
                ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                ctypes.windll.kernel32.CloseHandle(handle)
                # 259 = STILL_ACTIVE
                return exit_code.value == 259
            except Exception:
                return False
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False

    def _cleanup_stale_pid_file(self) -> None:
        """If a PID file points at a dead process, remove it so the next
        launch path is clean. Only safe to call once we've already determined
        the server isn't responding on its health port.
        """
        if not PID_FILE.exists():
            return
        try:
            pid = int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            PID_FILE.unlink(missing_ok=True)
            return
        if not self._pid_is_alive(pid):
            PID_FILE.unlink(missing_ok=True)

    def _ensure_server(self) -> Optional[str]:
        """If the server isn't healthy, launch it and wait. Returns error or None."""
        if self._server_healthy():
            return None

        # The server isn't responding. If we have a PID file pointing at a
        # dead process, clear it before launching. Without this, a previous
        # server crash leaves a stale PID that misleads future debugging.
        self._cleanup_stale_pid_file()

        try:
            pid = self._launch_server()
        except Exception as exc:
            return f"Failed to launch acestep-api: {exc}"

        if not self._wait_for_server():
            return (
                f"acestep-api server (PID {pid}) did not become healthy within "
                f"{SERVER_BOOT_TIMEOUT_SECONDS}s. Check log at {LOG_FILE}."
            )
        return None

    # ---- GPU selection + contention pre-flight ----

    @staticmethod
    def _auto_select_gpu(env: dict[str, str]) -> Optional[str]:
        """Pick the GPU with the most total VRAM and return its PCI-bus
        index as a string, suitable for `CUDA_VISIBLE_DEVICES`.

        Returns None if:
          - the user has already set `CUDA_VISIBLE_DEVICES` (respect it),
          - `nvidia-smi` is unavailable (let CUDA decide),
          - only one GPU is present (no choice to make).

        Auto-pinning prevents ACE-Step from falling onto a smaller GPU
        and silently enabling CPU offload (50-100x slowdown). Pairs with
        CUDA_DEVICE_ORDER=PCI_BUS_ID so the index matches nvidia-smi.
        """
        if env.get("CUDA_VISIBLE_DEVICES"):
            return None
        import shutil as _sh
        smi = _sh.which("nvidia-smi")
        if not smi:
            return None
        try:
            proc = subprocess.run(
                [smi, "--query-gpu=index,name,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0:
            return None

        gpus: list[tuple[int, str, int]] = []
        for line in proc.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            try:
                idx = int(parts[0])
                total_mb = int(parts[2])
            except ValueError:
                continue
            gpus.append((idx, parts[1], total_mb))
        if len(gpus) < 2:
            return None  # no ambiguity

        gpus.sort(key=lambda t: t[2], reverse=True)
        chosen_idx, chosen_name, chosen_mb = gpus[0]
        sys.stderr.write(
            f"[acestep_music] Auto-pinning to GPU {chosen_idx} ({chosen_name}, "
            f"{chosen_mb} MiB) via CUDA_VISIBLE_DEVICES; other GPUs visible: "
            f"{[(i, n, m) for i, n, m in gpus[1:]]}. "
            f"Override by setting CUDA_VISIBLE_DEVICES yourself.\n"
        )
        return str(chosen_idx)

    @staticmethod
    def _check_gpu_contention() -> Optional[str]:
        """Return a human-readable warning if free VRAM is low on any visible
        CUDA device, else None. Uses nvidia-smi so we don't need to import
        torch (which would pull the wrong wheel into the main env's path).
        """
        import shutil as _sh
        smi = _sh.which("nvidia-smi")
        if not smi:
            return None
        try:
            proc = subprocess.run(
                [smi, "--query-gpu=index,name,memory.free,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0 or not proc.stdout.strip():
            return None

        warnings = []
        for line in proc.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 4:
                continue
            try:
                idx = int(parts[0])
                free_mb = int(parts[2])
                total_mb = int(parts[3])
            except ValueError:
                continue
            # Only flag GPUs that are big enough to plausibly host ACE-Step
            # in the first place — a 4 GB integrated GPU isn't a contention
            # concern. The XL turbo + 1.7B LM need ~12 GB.
            if total_mb < 12000:
                continue
            if free_mb < GPU_MIN_FREE_VRAM_WARN_MB:
                warnings.append(
                    f"GPU {idx} ({parts[1]}): only {free_mb} MiB free of "
                    f"{total_mb} MiB. ACE-Step will share VRAM with whatever "
                    f"else is loaded; expect LM phase to slow 10-100x."
                )
        return " | ".join(warnings) if warnings else None

    # ---- API client ----

    def _api_post(self, path: str, payload: dict[str, Any], timeout: float = 60.0) -> dict:
        url = f"{self._server_url()}{path}"
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _submit_task(self, inputs: dict[str, Any]) -> str:
        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "lyrics": inputs.get("lyrics", ""),
            "audio_duration": float(inputs.get("duration_seconds", 30)),
            "audio_format": inputs.get("audio_format", "mp3"),
            "inference_steps": int(inputs.get("inference_steps", 8)),
            "thinking": bool(inputs.get("thinking", True)),
            "model": inputs.get("model", DEFAULT_DIT_MODEL),
            "use_random_seed": False,
            "seed": int(inputs.get("seed", 42)),
            "batch_size": 1,
        }
        if inputs.get("bpm"):
            payload["bpm"] = int(inputs["bpm"])
        if inputs.get("key_scale"):
            payload["key_scale"] = inputs["key_scale"]
        if inputs.get("time_signature"):
            payload["time_signature"] = inputs["time_signature"]

        resp = self._api_post("/release_task", payload, timeout=60.0)
        data = resp.get("data") or {}
        task_id = data.get("task_id")
        if not task_id:
            raise RuntimeError(f"No task_id in response: {resp}")
        return task_id

    def _poll_result(self, task_id: str, timeout: float) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self._api_post(
                "/query_result", {"task_id_list": [task_id]}, timeout=30.0
            )
            entries = resp.get("data") or []
            if entries:
                entry = entries[0]
                status = entry.get("status")
                if status == 1:
                    # `result` is a JSON-encoded string in the API spec.
                    raw_result = entry.get("result")
                    if isinstance(raw_result, str):
                        result_list = json.loads(raw_result)
                    else:
                        result_list = raw_result or []
                    if not result_list:
                        raise RuntimeError(f"Task {task_id} succeeded but returned no result entries")
                    return result_list[0]
                if status == 2:
                    raise RuntimeError(f"Task {task_id} failed: {entry}")
            time.sleep(JOB_POLL_INTERVAL_SECONDS)
        raise TimeoutError(f"Task {task_id} did not complete within {timeout:.0f}s")

    def _download_audio(self, file_url_path: str, output_path: Path) -> None:
        """Fetch the generated audio file via /v1/audio.

        The result's `file` field looks like `/v1/audio?path=...` — a path
        relative to the API server.
        """
        if file_url_path.startswith("/"):
            url = f"{self._server_url()}{file_url_path}"
        else:
            url = file_url_path

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as resp:
            output_path.write_bytes(resp.read())

    # ---- execute ----

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # XL turbo on a 24 GB GPU: ~10s gen + LM CoT planning + audio encode + safety margin.
        duration = float(inputs.get("duration_seconds", 30))
        return 30.0 + 0.5 * duration

    def _job_timeout_seconds(self, inputs: dict[str, Any]) -> float:
        """Client-side polling timeout, deliberately set above the server's
        ACESTEP_GENERATION_TIMEOUT so the server returns a structured failure
        before our urllib polling gives up. Adds duration-proportional headroom
        because longer tracks scale both LM Phase 2 and the diffusion loop.
        """
        duration = float(inputs.get("duration_seconds", 30))
        # 5x track duration covers the worst-case observed (LM Phase 2 alone
        # ran ~10x duration on a contended GPU; diffusion runs in parallel of
        # the same time scale). Floor at the server ceiling plus its pad.
        scaled = max(
            SERVER_GENERATION_TIMEOUT_SECONDS,
            5.0 * duration + 600.0,
        )
        return scaled + CLIENT_POLL_TIMEOUT_PAD_SECONDS

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()

        # 0. Sanity: home directory configured?
        if not self._acestep_home().exists():
            return ToolResult(
                success=False,
                error=(
                    f"ACE-Step home not found at {self._acestep_home()}. "
                    f"Clone the repo or set ACESTEP_HOME. {self.install_instructions}"
                ),
                duration_seconds=round(time.time() - start, 2),
            )

        # 0.5. GPU contention warning. ACE-Step's LM Phase 2 has been observed
        # to slow from ~110 codes/s to <1 code/s when free VRAM is tight. We
        # don't refuse to run — the user may want music anyway and the server
        # ceiling will catch a true hang — but surface it so the user knows
        # why a 30-second job is taking 15 minutes.
        contention = self._check_gpu_contention()
        if contention:
            sys.stderr.write(f"[acestep_music] GPU contention detected: {contention}\n")

        # 1. Make sure the server is up.
        boot_error = self._ensure_server()
        if boot_error:
            return ToolResult(
                success=False,
                error=boot_error,
                duration_seconds=round(time.time() - start, 2),
            )

        # 2. Submit + poll.
        try:
            task_id = self._submit_task(inputs)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"acestep-api /release_task failed: {exc}",
                duration_seconds=round(time.time() - start, 2),
            )

        job_timeout = self._job_timeout_seconds(inputs)
        try:
            result = self._poll_result(task_id, timeout=job_timeout)
        except TimeoutError as exc:
            hint = (
                f" GPU contention warning at start: {contention}." if contention else
                " Check ~/.cache/openmontage/acestep_server.log for the LM/diffusion"
                " progress; if the LM phase is decoding at <100 tok/s the GPU is"
                " under contention and another workload should finish first."
            )
            return ToolResult(
                success=False,
                error=(
                    f"acestep-api task {task_id} timed out after {job_timeout:.0f}s. "
                    f"{exc}.{hint}"
                ),
                duration_seconds=round(time.time() - start, 2),
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"acestep-api task {task_id} failed: {exc}",
                duration_seconds=round(time.time() - start, 2),
            )

        # 3. Download.
        file_path = result.get("file")
        if not file_path:
            return ToolResult(
                success=False,
                error=f"acestep-api result missing 'file' field: {result}",
                duration_seconds=round(time.time() - start, 2),
            )

        audio_format = inputs.get("audio_format", "mp3")
        default_out = Path(f"acestep_music_{task_id[:8]}.{audio_format}")
        output_path = Path(inputs.get("output_path", default_out))

        try:
            self._download_audio(file_path, output_path)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"audio download from acestep-api failed: {exc}",
                duration_seconds=round(time.time() - start, 2),
            )

        metas = result.get("metas") or {}

        # Optional one-shot cleanup: stop the server tree we launched so the
        # VRAM is released. Default is to leave it warm for follow-up jobs.
        shutdown_info: Optional[dict[str, Any]] = None
        if inputs.get("shutdown_after_generation"):
            try:
                shutdown_info = stop_server_tree()
            except Exception as exc:
                shutdown_info = {"error": f"shutdown_after_generation failed: {exc}"}

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": result.get("dit_model", inputs.get("model", DEFAULT_DIT_MODEL)),
                "lm_model": result.get("lm_model"),
                "prompt": inputs["prompt"],
                "lyrics_used": bool(inputs.get("lyrics")),
                "task_id": task_id,
                "duration_seconds": metas.get("duration") or inputs.get("duration_seconds"),
                "bpm": metas.get("bpm"),
                "key_scale": metas.get("keyscale"),
                "time_signature": metas.get("timesignature"),
                "seed_value": result.get("seed_value"),
                "output": str(output_path),
                "format": audio_format,
                "license": "MIT (ACE-Step) — output is fully owned",
                "server_shutdown": shutdown_info,
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=int(inputs.get("seed", 42)),
            model=inputs.get("model", DEFAULT_DIT_MODEL),
        )
