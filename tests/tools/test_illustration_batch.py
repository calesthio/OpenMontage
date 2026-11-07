#!/usr/bin/env python3
"""Red-then-green tests for tools/illustration/illustration_batch.py.

Uses a fake `kaggle` CLI (stdlib only) so no network, no paid routes, no API
keys. Covers: build job folder, push, fetch output, verify manifest
(job_id + sha256/bytes per file), label overlay, and manifest output.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.illustration.illustration_batch import (  # noqa: E402
    IllustrationBatchTool,
    apply_illustration_label,
    build_manifest,
)

FAKE_KAGGLE = str(Path(__file__).resolve().parent.parent / "fake_kaggle_cli.py")
TMP = Path("/tmp/kilo_illustration_batch")
TMP.mkdir(parents=True, exist_ok=True)


def _write_fake_kaggle():
    """Fake kaggle CLI: push = success; output = writes a manifest + images."""
    script = (
        "#!/usr/bin/env python3\n"
        "import sys, os, json, hashlib\n"
        "cmd = sys.argv[1:]\n"
        "if cmd[0:2] == [\"kernels\", \"push\"]:\n"
        "    sys.exit(0)\n"
        "if cmd[0:2] == [\"kernels\", \"output\"]:\n"
        "    dest = cmd[cmd.index(\"-p\") + 1]\n"
        "    os.makedirs(dest, exist_ok=True)\n"
        "    from PIL import Image\n"
        "    imgs = []\n"
        "    for name, color in ((\"img_A_3000.png\", (20, 30, 40)),\n"
        "                     (\"img_B_3001.png\", (60, 70, 80))):\n"
        "        p = os.path.join(dest, name)\n"
        "        Image.new(\"RGB\", (1280, 720), color).save(p, \"PNG\")\n"
        "        with open(p, \"rb\") as f:\n"
        "            data = f.read()\n"
        "        imgs.append({\"file\": name,\n"
        "                    \"sha256\": hashlib.sha256(data).hexdigest(),\n"
        "                    \"bytes\": len(data), \"prompt\": \"x\", \"seed\": 3000})\n"
        "    manifest = {\"job_id\": os.environ.get(\"FAKE_JOB_ID\", \"illustration-batch-1\"),\n"
        "                \"generator\": \"AI\", \"rights_basis\": \"ai_generated_illustration\",\n"
        "                \"images\": imgs, \"created_utc\": \"2026-10-20T00:00:00Z\"}\n"
        "    with open(os.path.join(dest, \"manifest.json\"), \"w\") as f:\n"
        "        json.dump(manifest, f)\n"
        "    sys.exit(0)\n"
        "print(\"unknown fake kaggle cmd:\", cmd, file=sys.stderr)\n"
        "sys.exit(2)\n"
    )
    Path(FAKE_KAGGLE).write_text(script)
    Path(FAKE_KAGGLE).chmod(0o755)


def test_apply_illustration_label_adds_chip():
    from PIL import Image
    src = TMP / "src.png"
    img = Image.new("RGB", (1280, 720), (20, 30, 40))
    img.save(src)
    out = TMP / "labeled.png"
    apply_illustration_label(src, out)
    assert out.is_file()
    labeled = Image.open(out).convert("RGB")
    assert labeled.size == (1280, 720)
    # bottom-right chip region should not equal background
    px = labeled.load()
    assert px[1200, 680] != (20, 30, 40)


def test_build_manifest_records_sha_bytes():
    img1 = TMP / "i1.png"; img1.write_bytes(b"AAAA")
    img2 = TMP / "i2.png"; img2.write_bytes(b"BBBBBBBB")
    manifest = build_manifest("illustration-batch-1",
                              [(img1, "orbit", 3000, 1280, 720),
                               (img2, "cupola", 3001, 1280, 720)],
                              model="SDXL-Lightning", accelerator="T4")
    assert manifest["job_id"] == "illustration-batch-1"
    assert manifest["generator"] == "AI"
    assert manifest["rights_basis"] == "ai_generated_illustration"
    assert len(manifest["images"]) == 2
    for ent in manifest["images"]:
        assert "sha256" in ent and "bytes" in ent and ent["bytes"] > 0
    assert manifest["images"][0]["bytes"] == 4
    assert manifest["images"][1]["bytes"] == 8


def test_batch_end_to_end_with_fake_kaggle():
    _write_fake_kaggle()
    os.environ["FAKE_JOB_ID"] = "illustration-batch-1"
    # point the tool at the fake kaggle CLI
    tool = IllustrationBatchTool()
    job_folder = TMP / "job"
    res = tool.execute({
        "command": "run_batch",
        "kaggle_cmd": "python3",
        "fake_kaggle": FAKE_KAGGLE,
        "job_folder": str(job_folder),
        "job_id": "illustration-batch-1",
        "kernel_slug": "forts845/illustration-batch",
        "job": {"prompts": [{"subject": "orbit diagram", "seed": 3000},
                            {"subject": "cupola window", "seed": 3001}],
                "model": "SDXL-Lightning", "aspect": "1280x720"},
        "enable_gpu": True,
        "enable_internet": True,
        "fetch_dest": str(TMP / "output"),
    })
    assert res.success, res.error
    out_dir = TMP / "output"
    assert (out_dir / "manifest.json").is_file()
    manifest = json.loads((out_dir / "manifest.json").read_text())
    assert manifest["job_id"] == "illustration-batch-1"
    # verify sha256/bytes match actual files
    for ent in manifest["images"]:
        p = out_dir / ent["file"]
        assert p.is_file()
        import hashlib
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        assert h == ent["sha256"]
        assert p.stat().st_size == ent["bytes"]
    # labeled images exist for each fetched image
    for ent in manifest["images"]:
        labeled = out_dir / f"{Path(ent['file']).stem}_labeled.png"
        assert labeled.is_file(), labeled
    # batch manifest present
    assert (out_dir / "batch_manifest.json").is_file()
