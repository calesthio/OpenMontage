"""Minimal KEY=VALUE .env reader shared by the tutorial CLIs.

Deliberately tiny: no interpolation, no multi-line values. Shell environment
should always win over the file (callers do `{**parse_env_file(p), **os.environ}`).
"""

from __future__ import annotations

import re
from pathlib import Path


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        return out
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if not (len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"')):
            val = re.split(r"\s+#", val, maxsplit=1)[0].rstrip()  # "VAL   # comment"
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            out[key] = val
    return out
