#!/usr/bin/env python3
import sys, os, json, hashlib
cmd = sys.argv[1:]
if cmd[0:2] == ["kernels", "push"]:
    sys.exit(0)
if cmd[0:2] == ["kernels", "output"]:
    dest = cmd[cmd.index("-p") + 1]
    os.makedirs(dest, exist_ok=True)
    from PIL import Image
    imgs = []
    for name, color in (("img_A_3000.png", (20, 30, 40)),
                     ("img_B_3001.png", (60, 70, 80))):
        p = os.path.join(dest, name)
        Image.new("RGB", (1280, 720), color).save(p, "PNG")
        with open(p, "rb") as f:
            data = f.read()
        imgs.append({"file": name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "bytes": len(data), "prompt": "x", "seed": 3000})
    manifest = {"job_id": os.environ.get("FAKE_JOB_ID", "illustration-batch-1"),
                "generator": "AI", "rights_basis": "ai_generated_illustration",
                "images": imgs, "created_utc": "2026-10-20T00:00:00Z"}
    with open(os.path.join(dest, "manifest.json"), "w") as f:
        json.dump(manifest, f)
    sys.exit(0)
print("unknown fake kaggle cmd:", cmd, file=sys.stderr)
sys.exit(2)
