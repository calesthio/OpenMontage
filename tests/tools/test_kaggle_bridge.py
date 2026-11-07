#!/usr/bin/env python3
"""Failing tests first (TDD) for tools/kaggle_bridge/kaggle_bridge.py.

Uses a FAKE `kaggle` executable placed first on PATH (well, passed as
kaggle_cmd) that simulates push/status/output behaviours. stdlib only;
subprocess without shell=True. No token value is ever printed, logged,
committed or passed on a command line.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402

FAKE_KAGGLE_SCRIPT = r'''#!/usr/bin/env python3
"""Fake kaggle CLI for testing the bridge tool (stdlib only)."""
import sys
import os
import json
import hashlib

STATE_PATH = os.environ.get("FAKE_KAGGLE_STATE", "/tmp/fake_kaggle_state.json")


def load_state():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return {
            "mode": "ok",
            "status_seq": ["queued", "running", "complete"],
            "status_idx": 0,
        }


def save_state(s):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f)
    os.replace(tmp, STATE_PATH)


def main():
    argv = sys.argv[1:]
    if not argv:
        print("usage: fake-kaggle <cmd> [args]", file=sys.stderr)
        return 1
    cmd = argv[0]
    state = load_state()
    mode = state.get("mode", "ok")
    if cmd == "kernels":
        sub = argv[1] if len(argv) > 1 else ""
        if sub == "init":
            folder = None
            for i, a in enumerate(argv):
                if a == "-p" and i + 1 < len(argv):
                    folder = argv[i + 1]
            if folder:
                os.makedirs(folder, exist_ok=True)
                meta = {
                    "id": "forts845/INSERT_KERNEL_SLUG_HERE",
                    "title": "INSERT_TITLE_HERE",
                    "code_file": "INSERT_CODE_FILE_PATH_HERE",
                    "language": "python",
                    "kernel_type": "script",
                    "is_private": "true",
                    "enable_gpu": "false",
                    "enable_tpu": "false",
                    "enable_internet": "false",
                    "machine_shape": "",
                    "dataset_sources": [],
                    "competition_sources": [],
                    "kernel_sources": [],
                    "model_sources": [],
                }
                with open(os.path.join(folder, "kernel-metadata.json"), "w") as fh:
                    json.dump(meta, fh, indent=2)
            return 0
        elif sub == "push":
            if mode == "conflict":
                print(
                    "ERROR: 409 Conflict - kernel version already exists",
                    file=sys.stderr,
                )
                return 1
            if mode == "auth_fail":
                print(
                    "Authentication required to call the Kaggle API.",
                    file=sys.stderr,
                )
                return 1
            print("Successfully pushed kernel")
            return 0
        elif sub == "status":
            if mode == "error":
                print("error")
                return 0
            if mode == "never":
                print("running")
                return 0
            if mode == "unknown":
                print("weird_status")
                return 0
            seq = state.get("status_seq", ["queued", "running", "complete"])
            idx = state.get("status_idx", 0)
            if idx < len(seq):
                st = seq[idx]
                state["status_idx"] = idx + 1
            else:
                st = seq[-1]
            save_state(state)
            print(st)
            return 0
        elif sub == "output":
            dest = None
            for i, a in enumerate(argv):
                if a == "-p" and i + 1 < len(argv):
                    dest = argv[i + 1]
            if mode == "empty_output":
                return 0
            if dest:
                os.makedirs(dest, exist_ok=True)
                wav = b"RIFF....WAVE...."
                sha = hashlib.sha256(wav).hexdigest()
                if mode == "sha_mismatch":
                    manifest_sha = "deadbeef" * 8  # wrong on purpose
                else:
                    manifest_sha = sha
                manifest = {
                    "job_id": "job1",
                    "sha256": manifest_sha,
                    "duration_seconds": 1.0,
                    "sample_rate": 24000,
                    "channels": 1,
                    "library_versions": {},
                    "license_facts": {},
                }
                with open(os.path.join(dest, "job1.wav"), "wb") as fh:
                    fh.write(wav)
                with open(os.path.join(dest, "manifest.json"), "w") as fh:
                    json.dump(manifest, fh)
            return 0
        else:
            print("unknown subcommand", file=sys.stderr)
            return 1
    else:
        print("unknown command", file=sys.stderr)
        return 1


sys.exit(main())
'''


def write_fake_kaggle(tmp_path, mode="ok"):
    """Write the fake kaggle script into tmp_path/bin and reset state.
    Returns the fake's path to pass as kaggle_cmd."""
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    fake = bindir / "kaggle"
    fake.write_text(FAKE_KAGGLE_SCRIPT)
    fake.chmod(0o755 | stat.S_IXUSR)
    state = {
        "mode": mode,
        "status_seq": ["queued", "running", "complete"],
        "status_idx": 0,
    }
    state_path = os.environ.get(
        "FAKE_KAGGLE_STATE", "/tmp/fake_kaggle_state.json"
    )
    with open(state_path, "w") as f:
        json.dump(state, f)
    return str(fake)


def tool():
    return KaggleBridgeTool()


# ---------------------------------------------------------------------------
# Command: build_job_folder
# ---------------------------------------------------------------------------


def test_build_job_folder_creates_files(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    job_folder = tmp_path / "jobs" / "job1"
    res = tool().execute(
        {
            "command": "build_job_folder",
            "job_folder": str(job_folder),
            "job_id": "job1",
            "kernel_slug": "forts845/of-bridge-runner",
            "job": {
                "job_id": "job1",
                "created_at": "2026-10-17T00:00:00Z",
                "script": "hello world",
            },
            "run_py": "print('hello')\n",
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    assert (job_folder / "kernel-metadata.json").exists()
    assert (job_folder / "job.json").exists()
    assert (job_folder / "run.py").exists()
    meta = json.loads((job_folder / "kernel-metadata.json").read_text())
    assert meta["id"] == "forts845/of-bridge-runner"
    assert meta["code_file"] == "run.py"
    assert meta["enable_gpu"] is False or meta["enable_gpu"] == "false"
    assert meta["enable_internet"] is False or meta["enable_internet"] == "false"
    jj = json.loads((job_folder / "job.json").read_text())
    assert jj["job_id"] == "job1"


def test_build_job_folder_uses_init_template(tmp_path):
    """kernel-metadata.json must come from `kaggle kernels init`, not guessed."""
    fake = write_fake_kaggle(tmp_path, "ok")
    job_folder = tmp_path / "jobs" / "job2"
    res = tool().execute(
        {
            "command": "build_job_folder",
            "job_folder": str(job_folder),
            "job_id": "job2",
            "kernel_slug": "forts845/of-bridge-runner",
            "job": {"job_id": "job2"},
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    meta = json.loads((job_folder / "kernel-metadata.json").read_text())
    # init template fields must be preserved/overridden, not invented from scratch
    assert "enable_tpu" in meta or "machine_shape" in meta


def test_build_job_folder_enable_gpu_internet_true(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    job_folder = tmp_path / "jobs" / "job_gpu"
    res = tool().execute(
        {
            "command": "build_job_folder",
            "job_folder": str(job_folder),
            "job_id": "job_gpu",
            "kernel_slug": "forts845/of-bridge-runner",
            "job": {"job_id": "job_gpu"},
            "enable_gpu": True,
            "enable_internet": True,
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    meta = json.loads((job_folder / "kernel-metadata.json").read_text())
    assert meta["enable_gpu"] is True
    assert meta["enable_internet"] is True


def test_build_job_folder_enable_gpu_internet_false_default(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    job_folder = tmp_path / "jobs" / "job_cpu"
    res = tool().execute(
        {
            "command": "build_job_folder",
            "job_folder": str(job_folder),
            "job_id": "job_cpu",
            "kernel_slug": "forts845/of-bridge-runner",
            "job": {"job_id": "job_cpu"},
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    meta = json.loads((job_folder / "kernel-metadata.json").read_text())
    assert meta["enable_gpu"] is False
    assert meta["enable_internet"] is False


# ---------------------------------------------------------------------------
# Command: push (happy + failure paths)
# ---------------------------------------------------------------------------


def test_push_ok(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    job_folder = tmp_path / "jobs" / "job1"
    job_folder.mkdir(parents=True)
    (job_folder / "kernel-metadata.json").write_text("{}")
    res = tool().execute(
        {
            "command": "push",
            "job_folder": str(job_folder),
            "kernel_slug": "forts845/of-bridge-runner",
            "timeout": 3600,
            "accelerator": "cpu",
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    assert res.data["push"]["status"] == "OK"


def test_push_auth_failure_blocked(tmp_path):
    fake = write_fake_kaggle(tmp_path, "auth_fail")
    job_folder = tmp_path / "jobs" / "job1"
    job_folder.mkdir(parents=True)
    (job_folder / "kernel-metadata.json").write_text("{}")
    res = tool().execute(
        {
            "command": "push",
            "job_folder": str(job_folder),
            "kernel_slug": "forts845/of-bridge-runner",
            "timeout": 3600,
            "accelerator": "cpu",
            "kaggle_cmd": fake,
        }
    )
    assert not res.success
    assert res.data["push"]["status"] == "BLOCKED"


def test_push_conflict_bounded_retry_then_blocked(tmp_path):
    fake = write_fake_kaggle(tmp_path, "conflict")
    job_folder = tmp_path / "jobs" / "job1"
    job_folder.mkdir(parents=True)
    (job_folder / "kernel-metadata.json").write_text("{}")
    res = tool().execute(
        {
            "command": "push",
            "job_folder": str(job_folder),
            "kernel_slug": "forts845/of-bridge-runner",
            "timeout": 3600,
            "accelerator": "cpu",
            "kaggle_cmd": fake,
            "max_retries": 2,
            "retry_backoff": 0,
        }
    )
    assert not res.success
    assert res.data["push"]["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Command: poll
# ---------------------------------------------------------------------------


def test_poll_status_sequence_complete(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    state_path = os.environ.get(
        "FAKE_KAGGLE_STATE", "/tmp/fake_kaggle_state.json"
    )
    with open(state_path) as f:
        state = json.load(f)
    state["status_seq"] = ["queued", "running", "complete"]
    state["status_idx"] = 0
    with open(state_path, "w") as f:
        json.dump(state, f)
    res = tool().execute(
        {
            "command": "poll",
            "kernel_slug": "forts845/of-bridge-runner",
            "total_timeout": 60,
            "backoff": 0,
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    assert res.data["poll"]["status"] == "complete"
    assert "queued" in res.data["poll"]["status_strings"]
    assert "running" in res.data["poll"]["status_strings"]
    assert "complete" in res.data["poll"]["status_strings"]


def test_poll_kernel_worker_status_complete(tmp_path):
    """Kaggle returns '<slug> has status "KernelWorkerStatus.COMPLETE"'; the
    bridge must parse the token and treat COMPLETE as terminal success."""
    fake = write_fake_kaggle(tmp_path, "ok")
    state_path = os.environ.get("FAKE_KAGGLE_STATE", "/tmp/fake_kaggle_state.json")
    with open(state_path) as f:
        state = json.load(f)
    slug = "forts845/of-bridge-runner"
    state["status_seq"] = [
        f'{slug} has status "KernelWorkerStatus.QUEUED"',
        f'{slug} has status "KernelWorkerStatus.RUNNING"',
        f'{slug} has status "KernelWorkerStatus.COMPLETE"',
    ]
    state["status_idx"] = 0
    with open(state_path, "w") as f:
        json.dump(state, f)
    res = tool().execute(
        {
            "command": "poll",
            "kernel_slug": slug,
            "total_timeout": 60,
            "backoff": 0,
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    assert res.data["poll"]["status"] == "complete"
    assert any("COMPLETE" in s for s in res.data["poll"]["status_strings"])


def test_poll_error_status_failed(tmp_path):
    fake = write_fake_kaggle(tmp_path, "error")
    res = tool().execute(
        {
            "command": "poll",
            "kernel_slug": "forts845/of-bridge-runner",
            "total_timeout": 30,
            "backoff": 0,
            "kaggle_cmd": fake,
        }
    )
    assert not res.success
    assert res.data["poll"]["status"] == "error"


def test_poll_never_finishing_blocked(tmp_path):
    fake = write_fake_kaggle(tmp_path, "never")
    res = tool().execute(
        {
            "command": "poll",
            "kernel_slug": "forts845/of-bridge-runner",
            "total_timeout": 1,
            "backoff": 0,
            "kaggle_cmd": fake,
        }
    )
    assert not res.success
    assert res.data["poll"]["status"] == "BLOCKED"


def test_poll_unknown_status_blocked(tmp_path):
    fake = write_fake_kaggle(tmp_path, "unknown")
    res = tool().execute(
        {
            "command": "poll",
            "kernel_slug": "forts845/of-bridge-runner",
            "total_timeout": 1,
            "backoff": 0,
            "kaggle_cmd": fake,
        }
    )
    assert not res.success
    assert res.data["poll"]["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Command: fetch_output
# ---------------------------------------------------------------------------


def test_fetch_output_writes_files(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    dest = tmp_path / "out"
    res = tool().execute(
        {
            "command": "fetch_output",
            "kernel_slug": "forts845/of-bridge-runner",
            "dest": str(dest),
            "file_pattern": "*",
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    assert (dest / "job1.wav").exists()
    assert (dest / "manifest.json").exists()


def test_fetch_empty_output_blocked(tmp_path):
    fake = write_fake_kaggle(tmp_path, "empty_output")
    dest = tmp_path / "out"
    res = tool().execute(
        {
            "command": "fetch_output",
            "kernel_slug": "forts845/of-bridge-runner",
            "dest": str(dest),
            "file_pattern": "*",
            "kaggle_cmd": fake,
        }
    )
    assert not res.success
    assert res.data["output"]["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Command: verify
# ---------------------------------------------------------------------------


def test_verify_sha256_match_ok(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    dest = tmp_path / "out"
    tool().execute(
        {
            "command": "fetch_output",
            "kernel_slug": "forts845/of-bridge-runner",
            "dest": str(dest),
            "file_pattern": "*",
            "kaggle_cmd": fake,
        }
    )
    res = tool().execute(
        {
            "command": "verify",
            "output_folder": str(dest),
            "job_id": "job1",
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    assert res.data["verify"]["manifest_valid"] is True
    assert res.data["verify"]["sha256_match"] is True


def test_verify_sha256_mismatch_reject(tmp_path):
    fake = write_fake_kaggle(tmp_path, "sha_mismatch")
    dest = tmp_path / "out"
    tool().execute(
        {
            "command": "fetch_output",
            "kernel_slug": "forts845/of-bridge-runner",
            "dest": str(dest),
            "file_pattern": "*",
            "kaggle_cmd": fake,
        }
    )
    res = tool().execute(
        {
            "command": "verify",
            "output_folder": str(dest),
            "job_id": "job1",
            "kaggle_cmd": fake,
        }
    )
    assert not res.success
    assert res.data["verify"]["sha256_match"] is False


def test_verify_missing_manifest_reject(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    dest = tmp_path / "out"
    tool().execute(
        {
            "command": "fetch_output",
            "kernel_slug": "forts845/of-bridge-runner",
            "dest": str(dest),
            "file_pattern": "*",
            "kaggle_cmd": fake,
        }
    )
    # remove manifest to simulate missing
    (dest / "manifest.json").unlink()
    res = tool().execute(
        {
            "command": "verify",
            "output_folder": str(dest),
            "job_id": "job1",
            "kaggle_cmd": fake,
        }
    )
    assert not res.success
    assert res.data["verify"]["manifest_valid"] is False


def _write_image(dest, name, content=b"imgdata"):
    p = dest / name
    p.write_bytes(content)
    return p


def test_verify_multi_image_manifest_ok(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    dest = tmp_path / "out"
    dest.mkdir(parents=True, exist_ok=True)
    p1 = _write_image(dest, "a.png", b"AAA")
    p2 = _write_image(dest, "b.png", b"BBBB")
    manifest = {
        "job_id": "jobimg",
        "images": [
            {"file": "a.png", "sha256": hashlib.sha256(b"AAA").hexdigest(), "bytes": 3},
            {"file": "b.png", "sha256": hashlib.sha256(b"BBBB").hexdigest(), "bytes": 4},
        ],
    }
    (dest / "manifest.json").write_text(json.dumps(manifest))
    res = tool().execute(
        {
            "command": "verify",
            "output_folder": str(dest),
            "job_id": "jobimg",
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    assert res.data["verify"]["sha256_match"] is True
    assert res.data["verify"]["manifest_valid"] is True
    imgs = res.data["verify"]["images"]
    assert len(imgs) == 2
    assert all(i["sha256_match"] for i in imgs)


def test_verify_multi_image_manifest_sha_mismatch_reject(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    dest = tmp_path / "out"
    dest.mkdir(parents=True, exist_ok=True)
    _write_image(dest, "a.png", b"AAA")
    manifest = {
        "job_id": "jobimg",
        "images": [
            {"file": "a.png", "sha256": "deadbeef" * 8, "bytes": 3},
        ],
    }
    (dest / "manifest.json").write_text(json.dumps(manifest))
    res = tool().execute(
        {
            "command": "verify",
            "output_folder": str(dest),
            "job_id": "jobimg",
            "kaggle_cmd": fake,
        }
    )
    assert not res.success
    assert res.data["verify"]["sha256_match"] is False


# ---------------------------------------------------------------------------
# Token safety: token never appears in args/result JSON
# ---------------------------------------------------------------------------


def test_token_not_in_result_json(tmp_path, monkeypatch):
    fake = write_fake_kaggle(tmp_path, "ok")
    job_folder = tmp_path / "jobs" / "job1"
    job_folder.mkdir(parents=True)
    (job_folder / "kernel-metadata.json").write_text("{}")
    monkeypatch.setenv("KAGGLE_API_TOKEN", "faketoken1234567890")
    token = os.environ["KAGGLE_API_TOKEN"]
    res = tool().execute(
        {
            "command": "push",
            "job_folder": str(job_folder),
            "kernel_slug": "forts845/of-bridge-runner",
            "timeout": 3600,
            "accelerator": "cpu",
            "kaggle_cmd": fake,
        }
    )
    payload = json.dumps(res.data)
    assert token not in payload
    assert "KAGGLE_API_TOKEN" not in payload


# ---------------------------------------------------------------------------
# Composite: run_job
# ---------------------------------------------------------------------------


def test_run_job_end_to_end_ok(tmp_path):
    fake = write_fake_kaggle(tmp_path, "ok")
    job_folder = tmp_path / "jobs" / "job1"
    res = tool().execute(
        {
            "command": "run_job",
            "job_folder": str(job_folder),
            "job_id": "job1",
            "kernel_slug": "forts845/of-bridge-runner",
            "job": {
                "job_id": "job1",
                "created_at": "2026-10-17T00:00:00Z",
                "script": "hello",
            },
            "run_py": "print('hello')\n",
            "timeout": 3600,
            "accelerator": "cpu",
            "fetch_dest": str(tmp_path / "out"),
            "file_pattern": "*",
            "kaggle_cmd": fake,
        }
    )
    assert res.success, res.error
    assert res.data["verdict"] == "PASS"
    assert res.data["push"]["status"] == "OK"
    assert res.data["poll"]["status"] == "complete"
    assert res.data["verify"]["sha256_match"] is True
