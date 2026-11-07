#!/usr/bin/env python3
"""Generate per-kernel run.py with shots embedded inline (no repo path dependency)."""

import json
from pathlib import Path

SHOT_LIST = Path("/workspaces/OpenMontage/tools/kaggle_bridge/jobs/pilot-render/shot_list.json")
TEMPLATE = Path("/workspaces/OpenMontage/scripts/k3_run_template.py")

data = json.loads(SHOT_LIST.read_text())
all_shots = data["shots"]

groups = {
    1: [1, 2, 3, 4],
    2: [5, 6, 7],
    3: [8, 9, 10],
}

for gnum, sections in groups.items():
    shots = [s for s in all_shots if s["section"] in sections]
    shots_var = "SHOTS = " + json.dumps(shots, ensure_ascii=False) + "\n"
    # JSON true/false/null -> Python True/False/None
    shots_var = shots_var.replace(": false", ": False").replace(": true", ": True").replace(": null", ": None")
    out_dir = Path(f"/workspaces/OpenMontage/tools/kaggle_bridge/jobs/k3-klein-frames-{gnum}")
    run_py = out_dir / "run.py"
    template = TEMPLATE.read_text()
    # Replace the SHOT_LIST read block with inline SHOTS
    marker_start = "# --- LOAD SHOTS ---"
    marker_end = "# --- END LOAD SHOTS ---"
    if marker_start in template:
        before = template.split(marker_start)[0]
        after = template.split(marker_end)[1]
        new_content = before + marker_start + "\n" + shots_var + marker_end + after
    else:
        new_content = shots_var + "\n" + template
    run_py.write_text(new_content)
    print(f"Wrote {run_py} ({len(shots)} shots, {len(new_content)} bytes)")
