"""Smoke-test the local reference console contract without paid providers."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlencode
from urllib import request

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_local_api import build_server, route_request


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class _ApiClient:
    def __init__(self, *, base_url: str | None = None, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout_seconds = timeout_seconds

    def json_response(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.base_url:
            return self._http_json_response(method, path, body)
        return self._router_json_response(method, path, body)

    def _router_json_response(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = route_request(method, path, body)
        payload = response.payload if isinstance(response.payload, dict) else {"body": response.payload}
        return {
            "status_code": response.status_code,
            "ok": 200 <= response.status_code < 300,
            "payload": payload,
        }

    def _http_json_response(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        url = f"{self.base_url}{path}"
        http_request = request.Request(url, data=data, headers=headers, method=method.upper())
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw or "{}")
            status_code = int(response.status)
        return {
            "status_code": status_code,
            "ok": 200 <= status_code < 300,
            "payload": payload,
        }

    def text_response(self, method: str, path: str) -> dict[str, Any]:
        if self.base_url:
            return self._http_text_response(method, path)
        return self._router_text_response(method, path)

    def _router_text_response(self, method: str, path: str) -> dict[str, Any]:
        response = route_request(method, path)
        payload = response.payload if isinstance(response.payload, str) else json.dumps(response.payload)
        return {
            "status_code": response.status_code,
            "ok": 200 <= response.status_code < 300,
            "payload": payload,
        }

    def _http_text_response(self, method: str, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        http_request = request.Request(url, headers={"Accept": "text/html"}, method=method.upper())
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            payload = response.read().decode("utf-8")
            status_code = int(response.status)
        return {
            "status_code": status_code,
            "ok": 200 <= status_code < 300,
            "payload": payload,
        }


@contextmanager
def _api_client(
    *,
    server_mode: str,
    host: str,
    port: int,
    request_timeout_seconds: float,
) -> Iterator[tuple[_ApiClient, dict[str, Any]]]:
    if server_mode == "router":
        yield _ApiClient(timeout_seconds=request_timeout_seconds), {
            "server_mode": "router",
            "base_url": None,
        }
        return

    server = build_server(host, port)
    actual_host, actual_port = server.server_address[:2]
    base_url = f"http://{actual_host}:{actual_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield _ApiClient(base_url=base_url, timeout_seconds=request_timeout_seconds), {
            "server_mode": "http",
            "base_url": base_url,
        }
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def _query(path: str, **params: str) -> str:
    return f"{path}?{urlencode(params)}"


def _public_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: _public_payload(value)
            for key, value in payload.items()
            if key not in {"command", "argv"}
        }
    if isinstance(payload, list):
        return [_public_payload(item) for item in payload]
    return payload


def _console_payload(html: str) -> dict[str, Any]:
    markers = {
        "has_title": "OpenMontage Reference Console" in html,
        "has_state_endpoint": "/api/reference/state" in html,
        "has_execute_endpoint": "/api/reference/actions/execute" in html,
        "has_jobs_list": "/api/reference/jobs/list" in html,
        "has_guidance_renderer": "renderActionGuidance" in html,
        "has_prepared_panel": "renderPreparedCommand" in html,
        "has_copy_button": "copyPreparedCommand" in html and "prepared-command-copy" in html,
        "has_download_button": "downloadPreparedCommand" in html and "prepared-command-download" in html,
        "no_raw_shell": ".venv/bin/python" not in html,
    }
    return {
        "status": "ok" if all(markers.values()) else "failed",
        "markers": markers,
    }


def _step(stage: str, status: str, detail: str | None = None) -> dict[str, str]:
    payload = {"stage": stage, "status": status}
    if detail:
        payload["detail"] = detail
    return payload


def _base_payload(
    *,
    status: str,
    server_payload: dict[str, Any] | None = None,
    steps: list[dict[str, str]] | None = None,
    failure_stage: str | None = None,
    recommended_action: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": "1.0",
        "status": status,
        **(server_payload or {}),
        "failure_stage": failure_stage,
        "recommended_action": recommended_action,
        "steps": steps or [],
        "paid_generation_started": False,
    }
    if error:
        payload["error"] = error
    return payload


def _find_action(state: dict[str, Any], action_id: str) -> dict[str, Any] | None:
    for action in state.get("actions") or []:
        if action.get("id") == action_id:
            return action
    return None


def _poll_job(
    *,
    client: _ApiClient,
    project_dir: str,
    job_id: str,
    timeout_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_payload: dict[str, Any] = {}
    while time.monotonic() <= deadline:
        status = client.json_response(
            "GET",
            _query(
                "/api/reference/jobs/status",
                project_dir=project_dir,
                job_id=job_id,
            ),
        )
        last_payload = status["payload"]
        if last_payload.get("status") != "running":
            return last_payload
        time.sleep(interval_seconds)
    return {
        **last_payload,
        "status": "timeout",
        "job_id": job_id,
    }


def run_smoke(
    *,
    project_name: str,
    source_path: str | Path,
    projects_root: str | Path | None = None,
    action_id: str = "analyze_imported_reference",
    wait: bool = True,
    timeout_seconds: float = 30.0,
    interval_seconds: float = 0.2,
    server_mode: str = "router",
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    request_timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Run the safe local console contract from project creation through a job."""

    source = Path(source_path).expanduser().resolve()
    create_body: dict[str, Any] = {"project_name": project_name}
    if projects_root is not None:
        create_body["projects_root"] = str(Path(projects_root).expanduser().resolve())

    if server_mode not in {"router", "http"}:
        return {
            "version": "1.0",
            "status": "blocked",
            "failure_stage": "server_mode",
            "recommended_action": "choose_supported_server_mode",
            "steps": [_step("server_mode", "failed", server_mode)],
            "error": f"Unsupported server_mode: {server_mode}",
            "paid_generation_started": False,
        }

    with _api_client(
        server_mode=server_mode,
        host=host,
        port=port,
        request_timeout_seconds=request_timeout_seconds,
    ) as (client, server_payload):
        return _run_smoke_with_client(
            client=client,
            server_payload=server_payload,
            create_body=create_body,
            source=source,
            action_id=action_id,
            wait=wait,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
        )


def _run_smoke_with_client(
    *,
    client: _ApiClient,
    server_payload: dict[str, Any],
    create_body: dict[str, Any],
    source: Path,
    action_id: str,
    wait: bool,
    timeout_seconds: float,
    interval_seconds: float,
) -> dict[str, Any]:
    steps: list[dict[str, str]] = []
    health = client.json_response("GET", "/api/reference/health")
    steps.append(_step("health", "passed" if health["ok"] else "failed"))
    console_response = client.text_response("GET", "/")
    console = _console_payload(str(console_response["payload"]))
    steps.append(_step("load_console", "passed" if console_response["ok"] and console["status"] == "ok" else "failed"))
    if not console_response["ok"] or console["status"] != "ok":
        return _public_payload(
            {
                **_base_payload(
                    status="blocked",
                    server_payload=server_payload,
                    steps=steps,
                    failure_stage="load_console",
                    recommended_action="check_reference_console_ui",
                    error="console_ui_contract_failed",
                ),
                "error": "console_ui_contract_failed",
                "health": health["payload"],
                "console": console,
            }
        )
    project = client.json_response("POST", "/api/reference/projects/create", create_body)
    steps.append(_step("create_project", "passed" if project["ok"] else "failed"))
    if not project["ok"]:
        return _public_payload(
            {
                **_base_payload(
                    status="blocked",
                    server_payload=server_payload,
                    steps=steps,
                    failure_stage="create_project",
                    recommended_action="check_project_name_and_projects_root",
                    error="project_create_failed",
                ),
                "error": "project_create_failed",
                "health": health["payload"],
                "console": console,
                "project": project["payload"],
            }
        )

    project_payload = project["payload"]
    project_dir = str(project_payload["project_dir"])
    imported = client.json_response(
        "POST",
        "/api/reference/projects/import-source",
        {
            "project_dir": project_dir,
            "source_path": str(source),
        },
    )
    steps.append(_step("import_source", "passed" if imported["ok"] else "failed"))
    if not imported["ok"]:
        return _public_payload(
            {
                **_base_payload(
                    status="blocked",
                    server_payload=server_payload,
                    steps=steps,
                    failure_stage="import_source",
                    recommended_action="check_local_video_path",
                    error="source_import_failed",
                ),
                "error": "source_import_failed",
                "health": health["payload"],
                "console": console,
                "project": project_payload,
                "import_source": imported["payload"],
            }
        )

    state = client.json_response(
        "GET",
        _query("/api/reference/state", project_dir=project_dir),
    )["payload"]
    steps.append(_step("load_state", "passed"))
    action = _find_action(state, action_id)
    steps.append(_step("select_action", "passed" if action and action.get("can_execute") is True else "failed"))
    if not action or action.get("can_execute") is not True:
        return _public_payload(
            {
                **_base_payload(
                    status="blocked",
                    server_payload=server_payload,
                    steps=steps,
                    failure_stage="select_action",
                    recommended_action="choose_can_execute_action",
                    error=f"Action is not a safe auto-executable action: {action_id}",
                ),
                "error": f"Action is not a safe auto-executable action: {action_id}",
                "health": health["payload"],
                "console": console,
                "project": project_payload,
                "import_source": imported["payload"],
                "initial_state": state,
                "action": action,
            }
        )

    job_response = client.json_response(
        "POST",
        "/api/reference/actions/execute",
        {
            "project_dir": project_dir,
            "action_id": action_id,
        },
    )
    steps.append(_step("execute_action", "passed" if job_response["ok"] else "failed"))
    job = job_response["payload"]
    final_job = job
    if job_response["ok"] and wait and job.get("job_id"):
        final_job = _poll_job(
            client=client,
            project_dir=project_dir,
            job_id=str(job["job_id"]),
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
        )
        steps.append(_step("poll_job", "passed" if final_job.get("status") == "succeeded" else "failed"))
    else:
        steps.append(_step("poll_job", "skipped" if not wait else "failed"))

    jobs = client.json_response(
        "GET",
        _query("/api/reference/jobs/list", project_dir=project_dir),
    )["payload"]
    steps.append(_step("list_jobs", "passed"))
    final_state = client.json_response(
        "GET",
        _query("/api/reference/state", project_dir=project_dir),
    )["payload"]
    steps.append(_step("final_state", "passed"))
    passed = bool(job_response["ok"]) and final_job.get("status") == "succeeded"
    status = "passed" if passed else "job_failed"
    failure_stage = None if passed else "job"
    recommended_action = None if passed else "inspect_job_log"

    return _public_payload(
        {
            **_base_payload(
                status=status,
                server_payload=server_payload,
                steps=steps,
                failure_stage=failure_stage,
                recommended_action=recommended_action,
            ),
            "health": health["payload"],
            "console": console,
            "project": project_payload,
            "import_source": imported["payload"],
            "initial_state": state,
            "action": action,
            "job": final_job,
            "jobs": jobs,
            "final_state": final_state,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_path", help="Local reference video path to import.")
    parser.add_argument("--project-name", default="Reference Console Smoke")
    parser.add_argument("--projects-root")
    parser.add_argument("--action-id", default="analyze_imported_reference")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--interval-seconds", type=float, default=0.2)
    parser.add_argument("--server-mode", choices=["router", "http"], default="router")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--request-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--no-wait", action="store_true")
    args = parser.parse_args(argv)

    payload = run_smoke(
        project_name=args.project_name,
        source_path=args.source_path,
        projects_root=args.projects_root,
        action_id=args.action_id,
        wait=not args.no_wait,
        timeout_seconds=args.timeout_seconds,
        interval_seconds=args.interval_seconds,
        server_mode=args.server_mode,
        host=args.host,
        port=args.port,
        request_timeout_seconds=args.request_timeout_seconds,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
