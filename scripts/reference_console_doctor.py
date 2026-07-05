"""Check whether the local reference-video web console is reachable."""

from __future__ import annotations

import argparse
import json
from urllib import request


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _console_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/"


def _health_url(host: str, port: int) -> str:
    return f"http://{host}:{port}/api/reference/health"


def _start_command(host: str, port: int) -> str:
    return (
        ".venv/bin/python scripts/reference_local_api.py "
        f"--host {host} --port {port}"
    )


def probe_console(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 1.0,
) -> dict:
    console_url = _console_url(host, port)
    health_url = _health_url(host, port)
    start_command = _start_command(host, port)
    try:
        health_request = request.Request(health_url, headers={"Accept": "application/json"})
        with request.urlopen(health_request, timeout=timeout) as response:
            health_payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as error:
        return {
            "version": "1.0",
            "status": "stopped",
            "service_running": False,
            "console_url": console_url,
            "health_url": health_url,
            "health": None,
            "error": str(error),
            "recommended_action": "start_console",
            "start_command": start_command,
            "open_command": f"open {console_url}",
        }
    return {
        "version": "1.0",
        "status": "running",
        "service_running": True,
        "console_url": console_url,
        "health_url": health_url,
        "health": health_payload,
        "error": None,
        "recommended_action": "open_console",
        "start_command": start_command,
        "open_command": f"open {console_url}",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args(argv)
    print(
        json.dumps(
            probe_console(host=args.host, port=args.port, timeout=args.timeout),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
