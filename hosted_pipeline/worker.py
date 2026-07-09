"""Fly worker entrypoint for hosted OpenMontage stage execution.

M0 keeps the worker alive and preflights the runtime. M1 will attach this
process to the durable job queue that invokes `StageExecutor`.
"""

from __future__ import annotations

import json
import os
import signal
import time

from tools.tool_registry import registry


def _provider_summary() -> dict:
    registry.discover()
    return registry.provider_menu_summary()


def main() -> int:
    stop = False

    def _handle_stop(signum, frame):  # noqa: ANN001
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    print("[worker] OpenMontage hosted worker booting", flush=True)
    print(
        "[worker] render_concurrency="
        f"{os.environ.get('RAY_RENDER_CONCURRENCY', '1')} "
        "browser="
        f"{os.environ.get('REMOTION_BROWSER_EXECUTABLE', '')}",
        flush=True,
    )
    try:
        summary = _provider_summary()
        print("[worker] provider_menu_summary=" + json.dumps(summary, sort_keys=True), flush=True)
    except Exception as exc:  # pragma: no cover - boot diagnostic only
        print(f"[worker] preflight failed: {exc}", flush=True)

    while not stop:
        time.sleep(5)
    print("[worker] stopping", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
