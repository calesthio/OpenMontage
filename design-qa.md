**Source Visual Truth**
- `/Users/a60/Documents/自动化视频/OpenMontage/docs/ui-mockups/chiling-product-v5-flow-board.png`
- `/Users/a60/Documents/自动化视频/OpenMontage/docs/ui-mockups/chiling-product-v5-create.png`
- `/Users/a60/Documents/自动化视频/OpenMontage/docs/ui-mockups/chiling-product-v5-review.png`

**Implementation Evidence**
- Local URL: `http://127.0.0.1:5174`
- Viewport: `1440x1100`
- Screenshots:
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/01-login-cli.png`
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/create.png`
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/review.png`
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/generating.png`
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/delivery.png`
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/api-generating-empty.png`
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/api-works.png`
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/worker-dashboard.png`
- Full-view comparison evidence:
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/compare-create.png`
  - `/Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench/qa-screenshots/compare-review.png`
- Focused region comparison: create and review were compared because they contain the densest form, preview, and approval controls. Login, generating, and delivery were inspected as full-state screenshots because their visible hierarchy is simpler.

**Findings**
- No actionable P0/P1/P2 findings remain.
- [P3] Create page is more vertically expanded than the compact reference.
  Location: `web/chiling-workbench/app.js`, create screen markup.
  Evidence: source design keeps settings compact; implementation exposes additional editable text/script controls and therefore scrolls on 1440x1100.
  Impact: acceptable for the productized prototype because the user specifically asked for editable image, prompt, copy, and input parameters.
  Fix: if the next iteration targets pixel fidelity over product completeness, collapse script editing behind a secondary section or drawer.

**Required Fidelity Surfaces**
- Fonts and typography: uses Apple/PingFang/system stack, heavy display headings, compact nav labels, and deliberate button/input typography. No browser-default control typography observed.
- Spacing and layout rhythm: preserves airy Apple-style cards, rounded navigation, soft shadows, three-step create flow, review side rail, generation feedback, and delivery package structure.
- Colors and visual tokens: preserves light gray canvas, white translucent surfaces, black primary controls, restrained red/blue/green/amber status tokens, and soft radial background.
- Image quality and asset fidelity: uses supplied real reference/portrait assets in phone previews. No placeholder boxes or exposed provider/model names in UI.
- Copy and content: product name is `赤灵AI运营工作台`; UI language describes user tasks only. Internal model/API/provider names are absent.

**Patches Made Since QA**
- Added `web/chiling-workbench/app.js` with local state, routing, form editing, uploads, review actions, generation feedback, and delivery actions.
- Added `web/chiling-workbench/api-client.js` with mock/real task API adapter for create task, poll task, list tasks, and list deliverables.
- Added `web/chiling-workbench/worker.py` with local `/tasks` API, static frontend hosting, dynamic `/config.js`, task persistence, and pipeline handoff package writing.
- Added `web/chiling-workbench/pipeline_bridge.py` to turn Web tasks into `reference-video-analysis` project intake plus queue entries without executing paid/video providers.
- Added `/pipeline-queue` and the Team Review queue panel so operators can see user-safe backend status, next action, and blockers.
- Added `/tasks/:taskId/operations` and a Generating-page operation panel with reference source, analysis, copy extraction, human review, and generation approval states.
- Added `/tasks/:taskId/operations/actions` for safe local-only reference analysis and copy extraction actions; generation approval remains blocked.
- Added `/tasks/:taskId/review-draft` and a Review-page editable analysis summary so safe action outputs can be reviewed before generation.
- Added `/tasks/:taskId/review-approval` and Review-page save/approve controls; approval records the reviewed version without starting generation.
- Added `/tasks/:taskId/generation-approval` and the generation approval confirmation phrase gate; it only marks production readiness and does not start paid generation.
- Added `/tasks/:taskId/production-prep` and a Generating-page production prep card with safe parameters, assets, review text, and readiness state.
- Added `/tasks/:taskId/production-request` and a second confirmation phrase for submitting the approved prep package to controlled production without starting generation.
- Added `/production-requests` and a Team Review production execution queue for operator-facing requested jobs.
- Added `/tasks/:taskId/production-claim` and a claim button so operators can move requested jobs into execution-in-progress state.
- Added `/production-service/status` and a Team Review production service diagnostics card with user-safe `未启用` / `待配置` / `可连接` states.
- Added `/production-service/configuration` and a Data-page admin production service configuration checklist.
- Added `/production-audit-log` and a Data-page production execution audit timeline.
- Added `/tasks/:taskId/detail` and a task detail drawer that groups 生产准备包, 人工审核记录, 生产执行审计, and 交付物.
- Added `/tasks/:taskId/production-execute` as a disabled-by-default controlled production service placeholder with a server-approved production service preflight path.
- Added `/tasks/:taskId/production-complete` and a delivery backfill button so operators can mark completed results into the delivery area.
- Added HTTP smoke coverage for create → review → approval → production request → claim → delivery backfill.
- Fixed Worker progress refresh so tasks cannot auto-complete by elapsed time before delivery backfill.
- Added hash routes for direct visual QA of `#dashboard`, `#create`, `#review`, `#generating`, and `#delivery`.
- Increased review column width and script editor height to prevent cramped preview and text scrolling.
- Added `web/chiling-workbench/README.md` with local run instructions.

**Implementation Checklist**
- Login routes into dashboard.
- Main nav switches between production desk, works, asset library, team review, and data pages.
- Create page supports editable URL, duration, resolution, count, subtitle style, script, and file upload controls.
- Duration clamps to 1-15 seconds and batch count clamps to 1-5 items.
- Review page supports subtitle punctuation cleanup and generation submission.
- Generating page creates or reads a task, shows progress, task drawer, loading button, and status feedback.
- Delivery page reads task deliverables from API adapter and exposes mock download/view/copy actions.
- Works page reads task list from API adapter and can reopen completed or in-progress tasks.
- Worker mode serves the app at `http://127.0.0.1:5180` and points the frontend to the same-origin `/tasks` API.
- Worker task creation attaches `pipeline_handoff`, including reference project path, source artifact path, queue item path, next stage, and `paid_generation_allowed: false`.
- Team Review reads `/pipeline-queue` and renders user-facing queue rows without model, provider, shell command, or internal pipeline naming.
- Generating reads `/tasks/:taskId/operations` and renders user-facing operation steps without enabling paid generation from the UI.
- Executable operation buttons only appear for safe local nodes. Locked approval nodes remain disabled and return blocked status if called directly.
- Review page can sync safe operation outputs into editable analysis summary and script draft fields before final confirmation.
- Review save/approve persists edited summary and script, marks human review complete, and keeps generation approval locked.
- 生成审批确认短语 must be `确认进入生产`; approval marks the task ready for production and 不会启动付费生成.
- 生产准备包 only appears as ready after review approval plus generation phrase approval; it does not expose model, provider, command, or internal pipeline names.
- 提交生产请求 requires the phrase `确认提交生产`; it writes a handoff request only and still 不会启动付费生成.
- 生产执行队列 only lists tasks with submitted production requests; it remains read-only and 不会启动付费生成.
- 领取任务 only marks a job as 执行中 and records the operator handoff; it still 不会启动付费生成.
- 生产服务诊断 displays only user-safe service readiness and does not expose model, provider, endpoint, API, or secret names.
- 生产服务配置 appears in the Data page as an admin-only checklist; it is read-only and 不在页面填写密钥.
- 生产执行审计 records 提交生产请求, 领取任务, 尝试执行生产服务, 生产服务预检, 人工回填交付, and 进入交付区 without exposing commands, paths, providers, models, or secrets.
- 任务详情 opens from Works, 后台生产队列, and 生产执行队列; it shows 生产准备包, 人工审核记录, 生产执行审计, and 交付物 without exposing commands, paths, providers, models, or secrets.
- 执行生产服务 is present but disabled by default; approved production service preflight returns 等待服务端执行器接管, writes audit records, and still 不会启动付费生成.
- 标记交付 only backfills video/subtitle/audit placeholders into delivery; it still 不会启动付费生成.
- Worker tasks must not enter completed/delivery state until delivery backfill exists; elapsed time can only advance progress up to 99%.
- Production service preflight smoke checked in Worker mode on port 5181; Data page shows 执行审批 已就绪 and 生产服务预检 / 等待执行器接管, with screenshot saved at `web/chiling-workbench/qa-screenshots/production-preflight-audit.png`.

**Functional Checks**
- `node --check web/chiling-workbench/api-client.js`
- `node --check web/chiling-workbench/app.js`
- `.venv/bin/python -m py_compile web/chiling-workbench/worker.py web/chiling-workbench/pipeline_bridge.py`
- `.venv/bin/python -m pytest tests/scripts/test_chiling_pipeline_bridge.py tests/scripts/test_chiling_worker_bridge.py tests/scripts/test_chiling_frontend_queue_contract.py -q`
- `.venv/bin/python -m pytest tests/scripts/test_chiling_worker_bridge.py::test_chiling_worker_http_smoke_runs_full_delivery_flow -q`
- `curl http://127.0.0.1:5180/health`
- `curl -X POST http://127.0.0.1:5180/tasks`
- `node /private/tmp/test-chiling-api-client.js`
- `git diff --check`

**2026-07-05 Drawer QA**
- Checked `http://127.0.0.1:5181/#works` with a live Worker task and opened `查看详情`.
- Screenshot: `web/chiling-workbench/qa-screenshots/task-detail-drawer.png`
- Result: `关闭` stays on one line, drawer sections are readable, and Worker/static task progress remains capped at 99% until delivery backfill.

final result: passed
