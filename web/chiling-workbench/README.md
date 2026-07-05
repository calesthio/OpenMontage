# 赤灵AI运营工作台 Web 原型

这是基于 v5 简约产品设计稿落地的静态可交互原型，用于验证登录、生产台、创建作品、人工审核、生成反馈和成品交付流程。

## 启动静态原型

```bash
cd /Users/a60/Documents/自动化视频/OpenMontage/web/chiling-workbench
python3 -m http.server 5174
```

然后打开：

```text
http://127.0.0.1:5174
```

静态模式会使用浏览器 `localStorage` 模拟任务。

## A+ frontend structure

The workbench remains buildless. `app.js` bootstraps the app and imports browser-native modules from `src/`.

- `src/format.js` and `src/task-model.js` contain pure helpers.
- `src/state.js` creates initial state and default form data.
- `src/actions.js` owns injected frontend action boundaries such as task creation.
- `src/polling.js` owns task polling without calling the API adapter directly.
- `src/components/` contains reusable UI renderers.
- `src/views/` contains page-level renderers.
- `api-client.js` remains the API/localStorage adapter.
- `worker.py` remains the local Worker/API bridge.

## 启动本地 Worker

```bash
cd /Users/a60/Documents/自动化视频/OpenMontage
.venv/bin/python web/chiling-workbench/worker.py --port 5180
```

然后打开：

```text
http://127.0.0.1:5180
```

Worker 模式会：

- 同时托管前端页面和 `/tasks` API。
- 把任务数据保存到 `web/chiling-workbench/.worker-data/`。
- 把每个任务的前端交接包写到 `projects/chiling-web-tasks/<taskId>/artifacts/web-task-request.json`。
- 同步创建 `reference-video-analysis` 流水线入口，写入 `projects/chiling-reference-pipeline/` 和 `pipeline/chiling-reference-pipeline/`。
- 只做任务闭环和交接包，不直接执行付费视频生成。
- 任务不会因为等待时间自动完成；必须由操作员回填交付后才进入交付区。

本地 HTTP 端到端冒烟测试：

```bash
cd /Users/a60/Documents/自动化视频/OpenMontage
.venv/bin/python -m pytest tests/scripts/test_chiling_worker_bridge.py::test_chiling_worker_http_smoke_runs_full_delivery_flow -q
```

如果当前沙箱不允许绑定本地端口，该测试会自动跳过；在本机授权端口绑定后可真实跑完整接口链路。

## 当前交互

- 登录后进入生产台。
- 快速导入会跳到创建作品。
- 参考视频、肖像图、文案、时长、清晰度、生成条数都可以编辑。
- 单条时长限制为 1-15 秒，单批数量限制为 1-5 条。
- 人工审核页可以清理字幕短句结尾标点。
- 团队审核页会展示后台生产队列，显示状态、下一步动作和阻塞提示。
- 团队审核页会展示生产服务诊断，显示真实生产服务未启用、待配置或可连接。
- 数据页会展示管理员生产服务配置清单；不在页面填写密钥，敏感内容仅服务端配置。
- 数据页会展示生产执行审计，串联提交、领取、执行尝试、人工回填和交付节点。
- 作品、后台生产队列和生产执行队列均可打开任务详情抽屉，集中查看生产准备包、人工审核记录、生产执行审计和交付物。
- 点击确认生成后会创建任务，进入生成反馈页，并轮询任务进度。
- 生成页会展示后台操作面板，分节点显示参考解析、文案提取、人工确认和生成审批状态。
- 人工审核页可同步安全动作产出的解析摘要和文案草稿，并继续人工修改。
- 生成完成后进入成品交付页，交付物来自任务接口或本地模拟任务。

## API 接入约定

当前默认使用 `localStorage` 模拟任务接口。使用 `worker.py` 访问时，`/config.js` 会自动把接口指向当前 Worker。同理，后续接真实后端时，只需要在页面加载前设置：

```html
<script>
  window.CHILING_API_BASE = "https://your-api.example.com";
</script>
```

前端会调用以下接口：

```text
POST /tasks
GET /tasks
GET /pipeline-queue
GET /production-requests
GET /production-service/status
GET /production-service/configuration
GET /production-audit-log
GET /tasks/:taskId
GET /tasks/:taskId/detail
GET /tasks/:taskId/operations
POST /tasks/:taskId/operations/actions
GET /tasks/:taskId/review-draft
POST /tasks/:taskId/review-approval
POST /tasks/:taskId/generation-approval
GET /tasks/:taskId/production-prep
POST /tasks/:taskId/production-request
POST /tasks/:taskId/production-claim
POST /tasks/:taskId/production-execute
POST /tasks/:taskId/production-complete
GET /tasks/:taskId/deliverables
```

`POST /tasks` 请求体会包含：

```json
{
  "referenceUrl": "参考视频链接",
  "duration": 15,
  "resolution": "480p",
  "count": 1,
  "subtitleStyle": "short",
  "script": "人工审核后的文案",
  "referenceName": "参考视频文件名",
  "portraitName": "肖像图片文件名"
}
```

任务对象建议返回：

```json
{
  "id": "task_001",
  "title": "参考视频复刻",
  "status": "processing",
  "progress": 64,
  "payload": {},
  "stages": [
    { "name": "解析参考", "state": "done", "detail": "完成" },
    { "name": "生成画面", "state": "active", "detail": "64%" }
  ]
}
```

`GET /pipeline-queue` 返回用户可读的后台队列摘要，不暴露底层模型、供应商、命令或内部管线字段：

```json
[
  {
    "taskId": "task_001",
    "title": "参考视频复刻",
    "statusLabel": "排队中",
    "sourceState": "素材已导入",
    "nextAction": "解析参考",
    "approvalRequired": true,
    "queueItemReady": true
  }
]
```

`GET /production-requests` 返回操作员可见的生产执行队列，只包含已提交生产请求的任务：

```json
[
  {
    "taskId": "task_001",
    "title": "参考视频复刻",
    "statusLabel": "等待生产",
    "nextAction": "操作员执行",
    "durationSeconds": 10,
    "resolution": "480p",
    "batchCount": 2,
    "executionStarted": false,
    "paidGenerationStarted": false
  }
]
```

生产执行队列仍是只读视图；当前版本不会从该页面直接调用正式生成。

`GET /production-service/status` 返回用户安全的生产服务诊断，不暴露底层模型、供应商、接口地址或密钥名称：

```json
{
  "status": "disabled",
  "statusLabel": "未启用",
  "ready": false,
  "summary": "真实生产服务未启用，当前不会启动付费生成。",
  "executionAllowed": false,
  "paidGenerationStarted": false
}
```

可返回 `disabled`、`missing_configuration` 或 `ready`。其中 `ready` 只表示连接配置就绪；只有服务端开关、连接配置和执行审批三项同时满足时，页面才允许发起生产服务预检。预检不会排队正式生成，也不会启动付费生成。

`GET /production-service/configuration` 返回管理员可读的生产服务配置清单，不返回密钥值、供应商名称、模型名称或服务端环境变量名：

```json
{
  "title": "生产服务配置",
  "editable": false,
  "secretInputAllowed": false,
  "items": [
    { "label": "服务开关", "state": "ok" },
    { "label": "连接配置", "state": "blocked" },
    { "label": "执行审批", "state": "locked" },
    { "label": "密钥托管", "state": "server_only" }
  ],
  "paidGenerationStarted": false
}
```

该页面只做管理员检查和配置待办提示；不在页面填写密钥，也不会启动付费生成。

`GET /production-audit-log` 返回生产执行审计时间线，用于追踪提交生产请求、领取任务、尝试执行生产服务、生产服务预检、人工回填交付和进入交付区：

```json
{
  "events": [
    {
      "label": "提交生产请求",
      "detail": "已进入受控生产队列。",
      "actor": "审核员",
      "state": "done",
      "paidGenerationStarted": false
    },
    {
      "label": "尝试执行生产服务",
      "detail": "真实生产服务未启用，未启动付费生成。",
      "actor": "操作员",
      "state": "blocked",
      "paidGenerationStarted": false
    }
  ],
  "paidGenerationStarted": false
}
```

审计日志只展示用户可理解的操作节点，不返回底层供应商、模型、命令、文件路径或密钥信息。

`GET /tasks/:taskId/detail` 返回任务详情抽屉使用的用户安全摘要，按四个部分组织：生产准备包、人工审核记录、生产执行审计和交付物：

```json
{
  "taskId": "task_001",
  "title": "参考视频复刻",
  "statusLabel": "处理中",
  "progress": 64,
  "paidGenerationStarted": false,
  "sections": [
    {
      "title": "生产准备包",
      "state": "ready",
      "items": [
        { "label": "生产参数", "value": "8s · 480p · 1条", "state": "done" }
      ]
    },
    {
      "title": "人工审核记录",
      "items": [
        { "label": "解析摘要", "value": "已人工确认", "state": "done" }
      ]
    },
    {
      "title": "生产执行审计",
      "items": [
        { "label": "尝试执行生产服务", "value": "未启动付费生成 · 操作员", "state": "blocked" }
      ]
    },
    {
      "title": "交付物",
      "items": [
        { "label": "成品视频", "value": "成品视频.mp4", "state": "done" }
      ]
    }
  ]
}
```

任务详情只展示运营人员可理解的信息，不返回命令、内部路径、供应商、模型、接口或密钥字段。

`POST /tasks/:taskId/production-claim` 用于操作员领取任务，把生产请求标记为执行中：

```json
{
  "operatorName": "操作员"
}
```

返回：

```json
{
  "status": "execution_in_progress",
  "executionStarted": true,
  "paidGenerationStarted": false
}
```

领取任务只改变工单状态并写入操作记录，不会自动调用正式生成。

`POST /tasks/:taskId/production-execute` 是预留给真实生产服务的受控执行入口。当前默认关闭：

```json
{
  "operatorName": "操作员"
}
```

默认返回：

```json
{
  "status": "disabled",
  "adapterExecutionStarted": false,
  "paidGenerationStarted": false
}
```

服务端生产开关、连接配置和执行审批都就绪后，会返回预检状态：

```json
{
  "status": "preflight_ready",
  "adapterExecutionStarted": false,
  "serverExecutionQueued": false,
  "paidGenerationStarted": false,
  "nextAction": "等待服务端执行器接管"
}
```

页面按钮显示为“执行生产服务”。当前入口只做安全占位、生产服务预检和审计记录；在未显式接入服务端执行器前，不会自动生成或扣费。

`POST /tasks/:taskId/production-complete` 用于操作员回填执行结果并标记交付：

```json
{
  "videoName": "成品视频.mp4",
  "subtitleName": "字幕文件.srt",
  "auditNote": "人工回填完成"
}
```

返回：

```json
{
  "status": "completed",
  "deliveryReady": true,
  "paidGenerationStarted": false
}
```

标记交付只把已执行结果挂回任务交付区，不会自动调用正式生成。

`GET /tasks/:taskId/operations` 返回任务级操作面板，前端只展示用户可理解的生产节点：

```json
{
  "taskId": "task_001",
  "title": "参考视频复刻",
  "safeAutoExecute": false,
  "steps": [
    { "title": "参考素材", "stateLabel": "已完成", "actionLabel": "已导入" },
    { "title": "参考解析", "stateLabel": "可处理", "actionLabel": "开始解析" },
    { "title": "文案提取", "stateLabel": "等待中", "actionLabel": "等待解析" },
    { "title": "人工确认", "stateLabel": "需前置确认", "actionLabel": "等待文案" },
    { "title": "生成审批", "stateLabel": "需前置确认", "actionLabel": "等待人工批准" }
  ]
}
```

`POST /tasks/:taskId/operations/actions` 仅允许安全本地动作，不会触发正式生成：

```json
{
  "operationId": "reference_analysis"
}
```

当前可执行动作：

- `reference_analysis`：本地推进参考解析节点，写入安全操作记录。
- `copy_extract`：本地推进文案提取节点，写入安全操作记录。
- `generation_approval`：保持锁定，只返回阻塞状态，必须走人工审批。

`GET /tasks/:taskId/review-draft` 返回人工审核页可编辑草稿：

```json
{
  "taskId": "task_001",
  "editable": true,
  "analysisSummary": "参考结构已完成本地整理。",
  "scriptDraft": "第一句\n第二句",
  "subtitleRule": "短句句尾不显示标点。",
  "reviewChecks": ["素材授权", "肖像授权", "字幕规则", "画面方向"]
}
```

`POST /tasks/:taskId/review-approval` 保存或确认人工审核稿，不会触发正式生成：

```json
{
  "analysisSummary": "人工确认后的解析摘要",
  "script": "第一句\n第二句",
  "approved": true
}
```

返回 `status: "saved"` 表示仅保存草稿，返回 `status: "approved"` 表示审核已通过并等待生成审批。

`POST /tasks/:taskId/generation-approval` 是进入生产前的强确认门，不会自动调用正式生成：

```json
{
  "confirmationPhrase": "确认进入生产"
}
```

只有人工审核已通过且确认短语完全匹配时，才会返回：

```json
{
  "status": "ready_for_production",
  "productionPrepared": true,
  "paidGenerationStarted": false
}
```

返回 `status: "blocked"` 表示还缺人工审核或确认短语不匹配。无论成功或阻塞，`paidGenerationStarted` 都必须保持 `false`；该接口只写入生产准备记录，真实生成仍需进入 OpenMontage 管线审批和执行阶段。

`GET /tasks/:taskId/production-prep` 返回生成审批后的生产准备包，不会自动调用正式生成：

```json
{
  "status": "ready",
  "constraints": {
    "durationSeconds": 12,
    "maxDurationSeconds": 15,
    "resolution": "480p",
    "batchCount": 1,
    "maxBatchCount": 5
  },
  "assets": {
    "referenceName": "参考视频已就绪",
    "portraitName": "肖像图已就绪"
  },
  "paidGenerationStarted": false
}
```

当人工审核或生成审批未完成时，返回 `status: "blocked"`。该准备包只展示生产参数、审核文案、素材状态和下一步动作，不暴露底层模型、供应商或内部管线名称。

`POST /tasks/:taskId/production-request` 用于提交生产请求，仍不会自动调用正式生成：

```json
{
  "confirmationPhrase": "确认提交生产"
}
```

只有生产准备包已就绪且确认短语完全匹配时，才会返回：

```json
{
  "status": "production_requested",
  "executionStarted": false,
  "paidGenerationStarted": false
}
```

返回 `status: "blocked"` 表示准备包未就绪或确认短语不匹配。该接口只把审核后的准备包提交给受控生产队列；真实执行仍由后续生产流程接管。

## 产品约束

- 用户界面不展示底层模型、供应商或接口名称。
- 当前版本不包含数字人生产入口。
- 这是前端静态原型，已预留真实后端任务接口适配层。
- 本地 Worker 遵守 OpenMontage 规则：真实生产必须再进入管线、审批和工具选择流程。
