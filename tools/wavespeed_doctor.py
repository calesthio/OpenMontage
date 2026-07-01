"""No-network WaveSpeed setup diagnostics."""

from __future__ import annotations

import json

from lib.wavespeed_config import wavespeed_doctor_report
from tools.base_tool import _load_dotenv


def main() -> int:
    _load_dotenv()
    report = wavespeed_doctor_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["ok"]:
        print("OK: WaveSpeed auth and profile model IDs are configured. No paid task was submitted.")
        return 0
    print("FAIL: WaveSpeed setup is incomplete. No paid task was submitted.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
