"""Run a tiny local HTTP API for the reference-video workflow UI."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_client_contract import build_client_state, prepare_client_action
from scripts.reference_job_queue import get_job_status, list_jobs, start_action
from scripts.reference_project_manager import (
    create_reference_project,
    import_reference_source,
)


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    payload: dict[str, Any] | str
    content_type: str = "application/json; charset=utf-8"


CONSOLE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>OpenMontage Reference Console</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --text: #161922;
      --muted: #687083;
      --line: #dfe4ee;
      --accent: #2856f6;
      --danger: #b42318;
      --safe: #067647;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 40px 0;
    }
    header {
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-end;
      margin-bottom: 24px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: clamp(30px, 4vw, 48px);
      line-height: 1;
      letter-spacing: -0.04em;
    }
    p { color: var(--muted); line-height: 1.65; margin: 0; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      box-shadow: 0 18px 50px rgba(25, 34, 61, 0.08);
    }
	    .project-bar {
	      display: grid;
	      grid-template-columns: minmax(0, 1fr) auto;
	      gap: 12px;
	      margin-bottom: 18px;
	    }
	    .setup-grid {
	      display: grid;
	      grid-template-columns: repeat(2, minmax(0, 1fr));
	      gap: 14px;
	      margin-bottom: 18px;
	    }
	    .setup-card {
	      border: 1px solid var(--line);
	      border-radius: 16px;
	      padding: 16px;
	      background: #fbfcff;
	    }
	    .setup-card h2 {
	      margin: 0 0 10px;
	      font-size: 16px;
	    }
	    .setup-card .row {
	      display: grid;
	      grid-template-columns: minmax(0, 1fr) auto;
	      gap: 10px;
	    }
    input {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 13px 14px;
      color: var(--text);
      font: inherit;
      background: white;
    }
    button {
      border: 0;
      border-radius: 14px;
      padding: 13px 16px;
      color: white;
      background: var(--accent);
      font: 700 14px/1 Inter, ui-sans-serif, system-ui, sans-serif;
      cursor: pointer;
    }
    button.secondary { background: #1f2937; }
    button:disabled { opacity: .45; cursor: not-allowed; }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      background: #fbfcff;
    }
    .metric strong { display: block; margin-top: 6px; font-size: 18px; }
    .actions {
      display: grid;
      gap: 12px;
      margin-top: 18px;
    }
    .jobs {
      display: grid;
      gap: 10px;
      margin-top: 18px;
    }
    .action {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      background: white;
    }
    .job {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      background: #fbfcff;
    }
    .job strong { display: block; margin-bottom: 6px; }
    .guidance {
      margin: 8px 0 0;
      color: #344054;
      line-height: 1.55;
    }
    .blocked-reason {
      color: var(--danger);
      font-weight: 700;
    }
    .prepared-command {
      display: none;
      margin-top: 18px;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      background: #f8fafc;
    }
    .prepared-command h2 {
      margin: 0 0 8px;
      font-size: 18px;
    }
    .prepared-command textarea {
      width: 100%;
      min-height: 92px;
      margin-top: 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      color: #101828;
      background: white;
      font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
    }
    .prepared-command .row {
      margin-top: 12px;
    }
    .tag {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 5px 9px;
      margin-top: 8px;
      color: var(--muted);
      background: #eef2ff;
      font-size: 12px;
      font-weight: 700;
    }
    .tag.risk-paid_generation,
    .tag.risk-delivery_export,
    .tag.risk-production_approval,
    .tag.risk-manual_review { color: var(--danger); background: #fff1f0; }
    .tag.risk-local { color: var(--safe); background: #ecfdf3; }
    pre {
      overflow: auto;
      white-space: pre-wrap;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      margin: 18px 0 0;
      min-height: 96px;
      background: #101828;
      color: #e4e7ec;
    }
	    @media (max-width: 760px) {
	      header, .project-bar, .action, .setup-grid, .setup-card .row { grid-template-columns: 1fr; display: grid; }
	      .job { grid-template-columns: 1fr; }
	      .grid { grid-template-columns: 1fr; }
	      button { width: 100%; }
	    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>OpenMontage Reference Console</h1>
        <p>加载授权参考视频项目状态，人工确认风险动作，然后复制后端准备好的安全命令。</p>
      </div>
      <button class="secondary" id="refreshButton">刷新状态</button>
    </header>

	    <section class="panel">
	      <div class="setup-grid">
	        <div class="setup-card">
	          <h2>1. 创建项目</h2>
	          <div class="row">
	            <input id="projectName" placeholder="Reference Demo">
	            <button id="createProjectButton">创建</button>
	          </div>
	        </div>
	        <div class="setup-card">
	          <h2>2. 导入本地视频</h2>
	          <div class="row">
	            <input id="sourcePath" placeholder="/path/to/reference.mp4">
	            <button id="importSourceButton">导入</button>
	          </div>
	        </div>
	      </div>
	      <div class="project-bar">
	        <input id="projectDir" placeholder="/Users/a60/Documents/自动化视频/OpenMontage/projects/reference-demo">
	        <button id="loadButton">加载项目</button>
      </div>
      <div class="grid" id="summary"></div>
      <div class="actions" id="actions"></div>
      <div class="jobs" id="jobs"></div>
      <section class="prepared-command" id="preparedCommand">
        <h2>已准备命令</h2>
        <p>命令只会在确认后的准备结果里出现。复制或下载前，请再次核对费用、范围和审批状态。</p>
        <textarea id="preparedCommandText" readonly></textarea>
        <div class="row">
          <button id="prepared-command-copy" type="button">复制命令</button>
          <button id="prepared-command-download" class="secondary" type="button">下载 .sh</button>
        </div>
      </section>
      <pre id="output">等待加载项目状态。</pre>
    </section>
  </main>

	  <script>
	    const stateEndpoint = "/api/reference/state";
	    const prepareEndpoint = "/api/reference/actions/prepare";
	    const executeEndpoint = "/api/reference/actions/execute";
	    const jobStatusEndpoint = "/api/reference/jobs/status";
	    const jobListEndpoint = "/api/reference/jobs/list";
	    const createProjectEndpoint = "/api/reference/projects/create";
	    const importSourceEndpoint = "/api/reference/projects/import-source";
	    const projectNameInput = document.querySelector("#projectName");
	    const sourcePathInput = document.querySelector("#sourcePath");
	    const projectDirInput = document.querySelector("#projectDir");
	    const summaryNode = document.querySelector("#summary");
	    const actionsNode = document.querySelector("#actions");
	    const jobsNode = document.querySelector("#jobs");
	    const preparedCommandNode = document.querySelector("#preparedCommand");
	    const preparedCommandTextNode = document.querySelector("#preparedCommandText");
	    const preparedCommandCopyButton = document.querySelector("#prepared-command-copy");
	    const preparedCommandDownloadButton = document.querySelector("#prepared-command-download");
    const outputNode = document.querySelector("#output");

    function projectDir() {
      return projectDirInput.value.trim();
    }

    function setOutput(payload) {
      outputNode.textContent = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
    }

    function renderPreparedCommand(payload) {
      const command = payload && payload.status === "ready_to_execute" ? payload.command : "";
      if (!command) {
        preparedCommandNode.style.display = "none";
        preparedCommandTextNode.value = "";
        return;
      }
      preparedCommandTextNode.value = command;
      preparedCommandNode.style.display = "block";
    }

    async function copyPreparedCommand() {
      const command = preparedCommandTextNode.value;
      if (!command) {
        setOutput("暂无可复制命令。");
        return;
      }
      await navigator.clipboard.writeText(command);
      setOutput({status: "copied", message: "命令已复制到剪贴板。"});
    }

    function downloadPreparedCommand() {
      const command = preparedCommandTextNode.value;
      if (!command) {
        setOutput("暂无可下载命令。");
        return;
      }
      const blob = new Blob([`#!/usr/bin/env bash\nset -euo pipefail\n${command}\n`], {type: "text/x-shellscript"});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "openmontage-prepared-command.sh";
      link.click();
      URL.revokeObjectURL(url);
      setOutput({status: "download_ready", filename: link.download});
    }

    function metric(label, value) {
      return `<div class="metric"><p>${label}</p><strong>${value || "—"}</strong></div>`;
    }

    function renderActionGuidance(action) {
      const guidance = action.operator_guidance || {};
      return `
        <p class="guidance">${guidance.summary || action.execution_note || ""}</p>
        <p class="guidance">${guidance.next_step || ""}</p>
        ${guidance.blocked_reason ? `<p class="guidance blocked-reason">阻断原因：${guidance.blocked_reason}</p>` : ""}
      `;
    }

    function prepareButtonLabel(action) {
      const guidance = action.operator_guidance || {};
      if (guidance.prepare_button_label) {
        return guidance.prepare_button_label;
      }
      return action.execution_mode === "manual_review" ? "查看复核要求" : "准备命令";
    }

    function renderState(state) {
      summaryNode.innerHTML = [
        metric("Phase", state.phase),
        metric("Status", state.status && state.status.status),
        metric("Actions", String((state.actions || []).length)),
      ].join("");
      actionsNode.innerHTML = (state.actions || []).map((action) => `
        <article class="action">
          <div>
            <strong>${action.label}</strong>
            <p>${action.script || "manual review"}</p>
            ${renderActionGuidance(action)}
            <span class="tag risk-${action.risk}">${action.risk}</span>
            <span class="tag">${action.execution_mode || "prepare_only"}</span>
            ${action.requires_confirmation ? `<span class="tag">需要确认：${action.confirmation_phrase}</span>` : ""}
          </div>
	          <div>
	            ${action.can_execute ? `<button data-execute-action-id="${action.id}">${(action.operator_guidance || {}).execute_button_label || "执行安全动作"}</button>` : ""}
	            <button data-action-id="${action.id}" ${action.enabled ? "" : "disabled"}>${prepareButtonLabel(action)}</button>
	          </div>
	        </article>
	      `).join("");
	      actionsNode.querySelectorAll("button[data-action-id]").forEach((button) => {
	        button.addEventListener("click", () => prepareAction(button.dataset.actionId, state.actions));
	      });
	      actionsNode.querySelectorAll("button[data-execute-action-id]").forEach((button) => {
	        button.addEventListener("click", () => executeAction(button.dataset.executeActionId));
	      });
      setOutput(state);
    }

    function renderJobs(payload) {
      const jobs = payload.jobs || [];
      if (!jobs.length) {
        jobsNode.innerHTML = "";
        return;
      }
      jobsNode.innerHTML = jobs.map((job) => `
        <article class="job">
          <div>
            <strong>${job.label || job.action_id || job.job_id}</strong>
            <p>${job.status}${job.returncode === undefined ? "" : ` · returncode ${job.returncode}`}</p>
            <span class="tag risk-${job.risk}">${job.risk || "job"}</span>
          </div>
          <button class="secondary" data-job-id="${job.job_id}">查看状态</button>
        </article>
      `).join("");
      jobsNode.querySelectorAll("button[data-job-id]").forEach((button) => {
        button.addEventListener("click", () => pollJobStatus(button.dataset.jobId));
      });
    }

    async function loadJobs() {
      if (!projectDir()) {
        return;
      }
      const url = `${jobListEndpoint}?project_dir=${encodeURIComponent(projectDir())}`;
      const response = await fetch(url);
      if (response.ok) {
        renderJobs(await response.json());
      }
    }

    async function loadState() {
      if (!projectDir()) {
        setOutput("请先填写项目目录。");
        return;
      }
      const url = `${stateEndpoint}?project_dir=${encodeURIComponent(projectDir())}`;
      const response = await fetch(url);
      renderState(await response.json());
      await loadJobs();
    }

    async function prepareAction(actionId, actions) {
      const action = actions.find((candidate) => candidate.id === actionId);
      let confirmation = "";
      if (action && action.requires_confirmation) {
        confirmation = window.prompt(`请输入确认短语：${action.confirmation_phrase}`) || "";
      }
      const response = await fetch(prepareEndpoint, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          project_dir: projectDir(),
          action_id: actionId,
          confirmation_phrase: confirmation,
        }),
      });
		      const payload = await response.json();
		      renderPreparedCommand(payload);
		      setOutput(payload);
		    }

	    async function createProject() {
	      const projectName = projectNameInput.value.trim();
	      if (!projectName) {
	        setOutput("请先填写项目名。");
	        return;
	      }
	      const response = await fetch(createProjectEndpoint, {
	        method: "POST",
	        headers: {"Content-Type": "application/json"},
	        body: JSON.stringify({project_name: projectName}),
	      });
	      const payload = await response.json();
	      if (payload.project_dir) {
	        projectDirInput.value = payload.project_dir;
	      }
	      setOutput(payload);
	      if (response.ok && projectDir()) {
	        await loadState();
	      }
	    }

		    async function importSource() {
	      if (!projectDir()) {
	        setOutput("请先创建或填写项目目录。");
	        return;
	      }
	      const sourcePath = sourcePathInput.value.trim();
	      if (!sourcePath) {
	        setOutput("请先填写本地视频路径。");
	        return;
	      }
	      const response = await fetch(importSourceEndpoint, {
	        method: "POST",
	        headers: {"Content-Type": "application/json"},
	        body: JSON.stringify({
	          project_dir: projectDir(),
	          source_path: sourcePath,
	        }),
	      });
	      setOutput(await response.json());
	      if (response.ok) {
		        await loadState();
		      }
		    }

	    async function executeAction(actionId) {
	      if (!projectDir()) {
	        setOutput("请先填写项目目录。");
	        return;
	      }
	      const response = await fetch(executeEndpoint, {
	        method: "POST",
	        headers: {"Content-Type": "application/json"},
	        body: JSON.stringify({
	          project_dir: projectDir(),
	          action_id: actionId,
	        }),
	      });
	      const payload = await response.json();
	      setOutput(payload);
	      await loadJobs();
	      if (response.ok && payload.job_id) {
	        await pollJobStatus(payload.job_id);
	      }
	    }

    async function pollJobStatus(jobId) {
      if (!projectDir() || !jobId) {
        return;
      }
      for (let attempt = 0; attempt < 60; attempt += 1) {
        const url = `${jobStatusEndpoint}?project_dir=${encodeURIComponent(projectDir())}&job_id=${encodeURIComponent(jobId)}`;
        const response = await fetch(url);
        const payload = await response.json();
        setOutput(payload);
        await loadJobs();
        if (payload.status !== "running") {
          await loadState();
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1500));
      }
      setOutput({status: "poll_timeout", job_id: jobId});
    }

		    document.querySelector("#createProjectButton").addEventListener("click", createProject);
	    document.querySelector("#importSourceButton").addEventListener("click", importSource);
	    document.querySelector("#loadButton").addEventListener("click", loadState);
	    document.querySelector("#refreshButton").addEventListener("click", loadState);
	    preparedCommandCopyButton.addEventListener("click", copyPreparedCommand);
	    preparedCommandDownloadButton.addEventListener("click", downloadPreparedCommand);
  </script>
</body>
</html>
"""


def _first_query_value(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key) or []
    value = values[0].strip() if values else ""
    return value or None


def _error(status_code: int, status: str, message: str) -> ApiResponse:
    return ApiResponse(status_code, {"status": status, "error": message})


def _state_response(query: dict[str, list[str]]) -> ApiResponse:
    project_dir = _first_query_value(query, "project_dir")
    if not project_dir:
        return _error(400, "bad_request", "Missing required query parameter: project_dir")
    return ApiResponse(200, build_client_state(project_dir))


def _prepare_response(body: dict[str, Any] | None) -> ApiResponse:
    payload = body or {}
    project_dir = str(payload.get("project_dir") or "").strip()
    action_id = str(payload.get("action_id") or "").strip()
    confirmation_phrase = payload.get("confirmation_phrase")
    if not project_dir:
        return _error(400, "bad_request", "Missing required JSON field: project_dir")
    if not action_id:
        return _error(400, "bad_request", "Missing required JSON field: action_id")
    result = prepare_client_action(
        project_dir,
        action_id,
        confirmation_phrase=str(confirmation_phrase) if confirmation_phrase is not None else None,
    )
    return ApiResponse(
        200 if result.get("status") == "ready_to_execute" else 409,
        result,
    )


def _execute_response(body: dict[str, Any] | None) -> ApiResponse:
    payload = body or {}
    project_dir = str(payload.get("project_dir") or "").strip()
    action_id = str(payload.get("action_id") or "").strip()
    confirmation_phrase = payload.get("confirmation_phrase")
    if not project_dir:
        return _error(400, "bad_request", "Missing required JSON field: project_dir")
    if not action_id:
        return _error(400, "bad_request", "Missing required JSON field: action_id")
    try:
        result = start_action(
            project_dir,
            action_id,
            confirmation_phrase=str(confirmation_phrase) if confirmation_phrase is not None else None,
        )
    except ValueError as error:
        return ApiResponse(
            409,
            {
                "version": "1.0",
                "status": "blocked",
                "project_dir": str(Path(project_dir).expanduser().resolve()),
                "action_id": action_id,
                "blocked_reason": str(getattr(error, "reason", "action_blocked")),
                "error": str(error),
            },
        )
    return ApiResponse(202, result)


def _job_status_response(query: dict[str, list[str]]) -> ApiResponse:
    project_dir = _first_query_value(query, "project_dir")
    job_id = _first_query_value(query, "job_id")
    if not project_dir:
        return _error(400, "bad_request", "Missing required query parameter: project_dir")
    if not job_id:
        return _error(400, "bad_request", "Missing required query parameter: job_id")
    try:
        return ApiResponse(200, get_job_status(project_dir, job_id))
    except ValueError as error:
        return _error(404, "not_found", str(error))


def _job_list_response(query: dict[str, list[str]]) -> ApiResponse:
    project_dir = _first_query_value(query, "project_dir")
    if not project_dir:
        return _error(400, "bad_request", "Missing required query parameter: project_dir")
    project_path = Path(project_dir).expanduser().resolve()
    return ApiResponse(
        200,
        {
            "version": "1.0",
            "status": "ok",
            "project_dir": str(project_path),
            "jobs": list_jobs(project_path),
        },
    )


def _create_project_response(body: dict[str, Any] | None) -> ApiResponse:
    payload = body or {}
    project_name = str(payload.get("project_name") or "").strip()
    if not project_name:
        return _error(400, "bad_request", "Missing required JSON field: project_name")
    try:
        result = create_reference_project(
            project_name=project_name,
            projects_root=payload.get("projects_root"),
        )
    except ValueError as error:
        return _error(400, "bad_request", str(error))
    return ApiResponse(201, result)


def _import_source_response(body: dict[str, Any] | None) -> ApiResponse:
    payload = body or {}
    project_dir = str(payload.get("project_dir") or "").strip()
    source_path = str(payload.get("source_path") or "").strip()
    if not project_dir:
        return _error(400, "bad_request", "Missing required JSON field: project_dir")
    if not source_path:
        return _error(400, "bad_request", "Missing required JSON field: source_path")
    try:
        result = import_reference_source(project_dir=project_dir, source_path=source_path)
    except ValueError as error:
        return _error(400, "bad_request", str(error))
    return ApiResponse(200, result)


def route_request(
    method: str,
    raw_path: str,
    body: dict[str, Any] | None = None,
) -> ApiResponse:
    """Route a local API request without starting an HTTP server."""

    parsed = urlparse(raw_path)
    path = parsed.path
    query = parse_qs(parsed.query)
    normalized_method = method.upper()
    if normalized_method == "GET" and path == "/":
        return ApiResponse(200, CONSOLE_HTML, "text/html; charset=utf-8")
    if normalized_method == "GET" and path == "/api/reference/health":
        return ApiResponse(200, {"status": "ok", "service": "reference_local_api"})
    if normalized_method == "GET" and path == "/api/reference/state":
        return _state_response(query)
    if normalized_method == "POST" and path == "/api/reference/actions/prepare":
        return _prepare_response(body)
    if normalized_method == "POST" and path == "/api/reference/actions/execute":
        return _execute_response(body)
    if normalized_method == "GET" and path == "/api/reference/jobs/status":
        return _job_status_response(query)
    if normalized_method == "GET" and path == "/api/reference/jobs/list":
        return _job_list_response(query)
    if normalized_method == "POST" and path == "/api/reference/projects/create":
        return _create_project_response(body)
    if normalized_method == "POST" and path == "/api/reference/projects/import-source":
        return _import_source_response(body)
    known_path = path in {
        "/api/reference/health",
        "/api/reference/state",
        "/api/reference/actions/prepare",
        "/api/reference/actions/execute",
        "/api/reference/jobs/status",
        "/api/reference/jobs/list",
        "/api/reference/projects/create",
        "/api/reference/projects/import-source",
    }
    if known_path:
        return _error(405, "method_not_allowed", f"Method not allowed: {normalized_method}")
    return _error(404, "not_found", f"Unknown route: {path}")


class ReferenceApiHandler(BaseHTTPRequestHandler):
    server_version = "OpenMontageReferenceApi/1.0"

    def _json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _send_api_response(self, response: ApiResponse) -> None:
        if response.content_type.startswith("application/json"):
            payload = json.dumps(response.payload, ensure_ascii=False, indent=2).encode("utf-8")
        else:
            payload = str(response.payload).encode("utf-8")
        self.send_response(response.status_code)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self._send_api_response(ApiResponse(200, {"status": "ok"}))

    def do_GET(self) -> None:
        self._send_api_response(route_request("GET", self.path))

    def do_POST(self) -> None:
        self._send_api_response(route_request("POST", self.path, self._json_body()))


def build_server(host: str, port: int) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ReferenceApiHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = build_server(args.host, args.port)
    print(f"Reference local API listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
