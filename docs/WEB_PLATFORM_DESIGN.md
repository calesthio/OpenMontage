# OpenMontage Web 平台 — 产品与技术设计文档

> 版本: v1 (Design Locked)
> 状态: 需求已对齐(5 轮 × 5 问 = 25 项决策),待进入实现
> 作者: Architect/PM 协同设计
> 关联文档: [`AGENT_GUIDE.md`](../AGENT_GUIDE.md) · [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md)

---

## 0. 一句话定位

把 OpenMontage 这套"Agent 即编排器"的 CLI 视频生产平台,产品化为一个 **单组织团队版的 Web 工作台**:用户用业务语言("营销宣传片")发起任务,后台由无头 Claude Agent 驱动现有 pipeline,用户在关键节点审批,全程进度透明可见,最终下载成片。

---

## 1. 需求对齐结论(25 项决策)

### 第一轮 · 产品定位与用户模型
| # | 决策 | 选择 |
|---|------|------|
| 1 | 目标用户 | **团队内部工具**(懂业务、隐藏工具层) |
| 2 | 主交互范式 | **混合式**:v1 Wizard,演进加 Chat |
| 3 | 用户模型 | **单组织多用户团队版** |
| 4 | pipeline 暴露 | **按内容类型映射,隐藏 pipeline 名词** |
| 5 | 核心卖点 | **进度透明 + 人工审批(human-in-the-loop)** |

### 第二轮 · 技术架构与集成路径
| # | 决策 | 选择 |
|---|------|------|
| 1 | pipeline 驱动 | **Claude Agent SDK 无头运行**(复用现有 skill/tool) |
| 2 | 进程拓扑 | **FastAPI 旁车**起步,演进到消息队列 |
| 3 | 长任务模型 | **后台 job + 状态持久化** |
| 4 | 进度反馈 | **SSE(Server-Sent Events)** |
| 5 | 产物存储 | **存储抽象层**(本地为主,可切对象存储) |

### 第三轮 · 数据模型与功能边界
| # | 决策 | 选择 |
|---|------|------|
| 1 | 真相源 | **文件系统为真相源,DB 仅索引/元数据/job 状态** |
| 2 | 数据库 | **PostgreSQL + Prisma** |
| 3 | v1 范围 | **只打通 cinematic 营销片**,结构可扩展 |
| 4 | 资产复用 | **v1 做品牌 Kit 复用** |
| 5 | 审批交互 | **批准/打回+反馈**起步,**内联编辑**快速跟进 |

### 第四轮 · UI/UX 与信息架构
| # | 决策 | 选择 |
|---|------|------|
| 1 | 应用骨架 | **侧边栏 Dashboard** |
| 2 | 创建入口 | **内容类型卡片 → 分步 Wizard** |
| 3 | 进度可视化 | **阶段 Stepper + 实时事件流(含缩略图)** |
| 4 | 设计系统 | **shadcn/ui + Tailwind** |
| 5 | 视觉调性 | **暗色优先(dark-first)** |

### 第五轮 · 工程落地与交付
| # | 决策 | 选择 |
|---|------|------|
| 1 | 仓库拓扑 | **同仓库 monorepo**(`web/` + `server/`) |
| 2 | Agent Runner | **Python `claude-agent-sdk`,跑在 FastAPI 内** |
| 3 | 认证 | **v1 共享口令门禁**,schema 预留多用户字段 |
| 4 | 部署 | **Docker Compose 一键起全套** |
| 5 | 交付节奏 | **垂直切片优先** |

> **关键协调点**:round1-Q3(团队版)与 round5-Q3(v1 不做认证)的张力,通过"v1 口令门禁 + DB schema 预留 `User`/`Org`/`owner_id`(可空)字段"解决。后续接 NextAuth OAuth 时无需数据迁移。

---

## 2. 系统架构

### 2.1 总览

```
┌─────────────────────────────────────────────────────────────┐
│ Browser (暗色 UI, shadcn/ui)                                  │
│  Dashboard · 内容类型卡片 · Wizard · 进度 Stepper · 审批面板    │
└───────────────┬──────────────────────────┬──────────────────┘
                │ REST (创建/审批/查询)       │ SSE (进度事件流)
                ▼                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Next.js (App Router) — 前端 + BFF                             │
│  · API routes 作为 BFF                                        │
│  · Prisma → Postgres (用户/项目元数据/job 状态/品牌Kit)        │
│  · 口令门禁中间件 (v1)                                         │
│  · SSE 代理 → FastAPI                                         │
│  · 静态/媒体文件服务 (经存储抽象层)                            │
└───────────────┬─────────────────────────────────────────────┘
                │ REST + SSE (内部)
                ▼
┌─────────────────────────────────────────────────────────────┐
│ FastAPI 旁车 (Python) — Agent 执行器                          │
│  · POST /jobs        启动后台生产任务                          │
│  · GET  /jobs/{id}/events  SSE 进度流                         │
│  · POST /jobs/{id}/approve 审批回执                            │
│  · 后台 worker: Stage Runner                                  │
│        └─ claude-agent-sdk (无头 agent)                       │
│              └─ Tool Bridge → 现有 tools/ (118 个 BaseTool)    │
│        └─ 写 checkpoint + artifacts (现有 lib/checkpoint.py)   │
│        └─ 写 job/stage 状态 → Postgres                         │
└───────────────┬─────────────────────────────────────────────┘
                │ 读写
                ▼
┌─────────────────────────────────────────────────────────────┐
│ 文件系统 (真相源)  projects/<id>/{artifacts,assets,renders}/  │
│ Postgres (索引)    users, orgs, projects, jobs, stages,       │
│                    brand_kits, events                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心模式:Stage Runner(本设计的关键创新点)

round2-Q1 选了"Agent 驱动",round5-Q5 要"可控的审批门"。两者通过 **Stage Runner** 调和:

- **不是**让一个 agent 一口气从头跑到尾(不可控、审批门难插入)。
- **而是** Python 侧写一个轻量 `StageRunner`,它读取 pipeline manifest 的阶段列表与 `human_approval_default`,**逐阶段**调用 Agent SDK:
  1. 取当前 stage 的 director skill(MD)+ 上游 artifacts 作为 agent 上下文
  2. 启动无头 agent 执行**这一个阶段**的创意工作(agent 自由读 skill、调工具)
  3. agent 产出 artifact → 经 schema 校验 → 写 checkpoint
  4. 若该 stage `human_approval_default: true` → job 置为 `awaiting_approval`,**暂停**,等用户 REST 回执
  5. 用户批准 → 进入下一 stage;打回 → 带反馈重跑当前 stage(复用 reviewer "max 2 rounds")

> **设计原则**:创意决策(写脚本、提概念)100% 由 agent 完成(尊重架构哲学);阶段流转与审批门由确定性的 Python 包一层(满足可控性)。**现有 markdown skill / YAML manifest / Python 工具零改动**。

### 2.3 Tool Bridge(Agent SDK ↔ 现有工具)

Agent SDK 需要能调用现有 118 个 `BaseTool`。方案:

- 注册一个通用桥接工具 `run_openmontage_tool(name, inputs)`,内部走 `tools/tool_registry.py` 的发现与分发机制。
- 外加文件读取能力(`Read`/`Glob`)让 agent 读取 `skills/`、`pipeline_defs/`、`schemas/`。
- agent 的每一次 `tool_use` / `tool_result` / 文本输出 → 映射为 SSE 进度事件推给前端。

### 2.4 进度事件流(SSE)

FastAPI 在 agent 运行时发出结构化事件,Next.js 代理给浏览器:

```jsonc
{ "type": "stage_started",  "stage": "script", "ts": "..." }
{ "type": "tool_call",      "tool": "maas_video", "summary": "生成场景1(城市排队)", "ts": "..." }
{ "type": "asset_ready",    "kind": "image", "url": "/media/.../product_shot.png", "thumb": "...", "ts": "..." }
{ "type": "stage_completed","stage": "script", "artifact": "script", "ts": "..." }
{ "type": "awaiting_approval","stage": "script", "preview": {...}, "ts": "..." }
{ "type": "job_completed",  "render_url": "/media/.../final.mp4", "ts": "..." }
{ "type": "error",          "stage": "assets", "message": "...", "ts": "..." }
```

事件落库(`events` 表)以支持断线重连后回放(SSE `Last-Event-ID`)。

---

## 3. 数据模型(Prisma schema 概要)

> DB 仅存元数据/状态/索引。artifact 内容仍是磁盘 JSON。

```prisma
// 多用户字段 v1 预留(可空),口令门禁阶段不强制
model Org   { id String @id; name String; createdAt DateTime @default(now()); projects Project[]; brandKits BrandKit[] }
model User  { id String @id; orgId String?; email String? @unique; name String?; role String @default("member") }

model Project {
  id          String   @id @default(cuid())
  orgId       String?
  ownerId     String?              // v1 可空,接 auth 后回填
  name        String
  contentType String                // "marketing_film" → 映射 cinematic
  pipeline    String                // "cinematic"
  status      String   @default("draft") // draft|running|awaiting_approval|completed|failed
  dirPath     String                // projects/<id>/  (文件真相源指针)
  brandKitId  String?
  createdAt   DateTime @default(now())
  jobs        Job[]
}

model Job {
  id         String   @id @default(cuid())
  projectId  String
  status     String   @default("queued") // queued|running|awaiting_approval|completed|failed|cancelled
  currentStage String?
  costUsd    Float    @default(0)
  startedAt  DateTime?
  finishedAt DateTime?
  stages     Stage[]
  events     Event[]
}

model Stage {
  id        String  @id @default(cuid())
  jobId     String
  name      String                  // research|proposal|script|scene_plan|assets|edit|compose|publish
  status    String  @default("pending") // pending|running|awaiting_approval|approved|rejected|done
  artifact  String?                 // artifact 名(内容在磁盘)
  feedback  String?                 // 打回时用户反馈
  rounds    Int     @default(0)
  updatedAt DateTime @updatedAt
}

model Event {
  id        String   @id @default(cuid())
  jobId     String
  seq       Int                     // SSE Last-Event-ID
  type      String
  payload   Json
  createdAt DateTime @default(now())
}

model BrandKit {
  id        String @id @default(cuid())
  orgId     String?
  name      String
  logoPath  String?
  colors    Json?                   // {primary, secondary, accent}
  fonts     Json?
  slogan    String?
  notes     String?
  createdAt DateTime @default(now())
}
```

> **双写协调**:Prisma 持有 schema/迁移的真相源(Next.js 侧)。FastAPI 用 SQLAlchemy(async)/asyncpg 读写同一组表(只写 `Job`/`Stage`/`Event` 状态),不做迁移。表结构以 Prisma 为准。

---

## 4. 内容类型映射(round1-Q4)

UI 永不出现 pipeline 技术名词,通过映射表桥接:

| 用户看到(业务语言) | 底层 pipeline | v1 状态 |
|---------------------|---------------|---------|
| 营销宣传片 | `cinematic` | ✅ 可用 |
| 解说视频 | `animated-explainer` | 🔒 即将上线 |
| 播客剪辑 | `podcast-repurpose` | 🔒 即将上线 |
| 产品演示 | `screen-demo` | 🔒 即将上线 |
| 短视频批量 | `clip-factory` | 🔒 即将上线 |
| ...(其余 7 条) | ... | 🔒 即将上线 |

映射表是配置(`web/config/content-types.ts`),新增内容类型只改配置 + 提供该 pipeline 的 Wizard 表单 schema,不改架构。

---

## 5. 关键用户流程(v1 垂直切片)

```
1. 口令门禁 → 进入 Dashboard
2. 点"新建" → 内容类型卡片页(营销片可点,其余灰显"即将上线")
3. 选"营销宣传片" → Wizard:
     Step1 品牌信息(可挂载已存品牌 Kit)
     Step2 风格 / 时长 / 旁白开关 / 视频&图像模型(默认 ltx-2.3 / flux2)
     Step3 确认 → 提交
4. 后台启动 Job → 跳转项目详情页
5. 详情页:阶段 Stepper(research→...→publish)+ 实时事件流(缩略图)
6. 到 proposal / script 审批门 → 弹审批面板:
     - 看 AI 产出(概念/脚本)
     - [批准] 继续 / [打回] 写反馈让 AI 重做
7. assets/compose 自动跑 → 实时看片段/图片缩略图陆续就绪
8. publish 完成 → 项目详情展示成片播放器 + 下载按钮
```

---

## 6. 技术栈清单

| 层 | 选型 |
|----|------|
| 前端框架 | Next.js (App Router) + TypeScript |
| UI | shadcn/ui + Tailwind CSS,**暗色优先** |
| 状态/数据 | React Server Components + Prisma Client(BFF) |
| 数据库 | PostgreSQL |
| ORM | Prisma(TS 侧迁移真相源)+ SQLAlchemy/asyncpg(Python 侧只读写状态) |
| Agent 执行器 | FastAPI + `claude-agent-sdk`(Python) |
| 实时通信 | SSE |
| 容器化 | Docker Compose(web + server + postgres) |
| 复用资产 | 现有 `tools/`、`lib/`、`skills/`、`pipeline_defs/`、`schemas/`(零改动) |

---

## 7. 演进路线(v1 之后)

| 项 | v1 | 演进 |
|----|----|----|
| 任务执行 | FastAPI 内后台 worker | → Redis + BullMQ/Celery 队列(并发扩展) |
| 存储 | 本地文件系统(经抽象层) | → S3/MinIO/OSS(多机/CDN) |
| 认证 | 共享口令门禁 | → NextAuth OAuth(Google/GitHub) |
| 审批 | 批准/打回+反馈 | → proposal/script 内联编辑 |
| 交互 | Wizard 表单 | → Chat 嵌入(自然语言入口) |
| 内容类型 | 仅营销片 | → 解说/播客/产品演示... |
| 资产复用 | 品牌 Kit | → 完整资产库(借力 `clip_embedder.py`) |

---

## 8. 风险与对策

| 风险 | 等级 | 对策 |
|------|------|------|
| Agent SDK 能否真正无头驱动现有 pipeline | 🔴 最高 | **M1 垂直切片第一优先级验证**,失败则退回 Stage Runner 内用确定性工具调用 + 仅创意节点用 LLM |
| 非确定性导致产出不稳定 | 🟡 | checkpoint + schema 校验 + 审批门兜底;reviewer max 2 rounds |
| MaaS 工具不稳定(已见 TTS 502) | 🟡 | 工具 `fallback_tools` 机制;SSE 暴露失败事件;允许重跑单 stage |
| 长任务超时/中断 | 🟡 | checkpoint 可恢复;Job 状态持久化;前端可关页面再回来 |
| Python/Node 混合仓库复杂度 | 🟢 | 目录隔离(`web/` `server/`)+ Docker Compose 统一环境 |

---

## 9. 里程碑总览

| 里程碑 | 目标 | 验收标准 |
|--------|------|----------|
| **M0** 脚手架与基础设施 | monorepo 骨架可起 | `docker compose up` 起 web+server+postgres,健康检查通过 |
| **M1** 垂直切片(端到端) | 打穿最大风险 | 口令进入→选营销片→填表→agent 跑通→SSE 看进度→审批→出片→下载 |
| **M2** 进度可视化打磨 | 卖点落地 | Stepper + 事件流 + 缩略图 + 断线重连完整 |
| **M3** 品牌 Kit | 团队复用 | 建/管品牌 Kit,新项目可挂载并注入 proposal |
| **M4** 审批内联编辑 | 掌控感 | proposal/script 关键字段可内联改并存回 artifact |
| **M5** 健壮性与演进准备 | 生产就绪 | 错误恢复、单 stage 重跑、存储抽象层、auth 接口预留 |

详细任务见任务列表(TaskList)。

---

*本文档为需求锁定版本。进入实现前如有架构调整,在此文档记录变更。*
