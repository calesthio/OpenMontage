# OpenMontage × seedance-product-scene 产品素材工作流设计

## 1. 背景

目标用户是不熟悉视频制作和 API 配置的普通用户。用户应当只需在 Codex 对话中描述产品、上传产品图，然后按步骤做少量选择，就能得到可交付的商品场景图、商品视频、营销文案和配乐。

OpenMontage 负责流水线、审批门、项目目录、资产清单、渲染和验证。Codex 当前会话负责交互、创作判断和文案生成。火山方舟只负责图像与视频模型调用。

## 2. 成功标准

一个普通用户能够在 Codex 对话中完成以下闭环：

1. 上传一张清晰的产品图，并填写产品名称和已知卖点。
2. 从轻奢、自然、科技、办公四种标准场景中看到预览。
3. 选择 1–3 种场景做完整套装。
4. 确认三段式分镜、8 秒、9:16、无画面文字和免版权配乐方案。
5. 为每种入选场景确认一套 3 张 Seedream 场景图。
6. 为每种入选场景生成并确认 1 条 8 秒 Seedance 视频。
7. 为每种入选场景得到种草型、高级型、详情页转化型三套文案。
8. 为每种入选场景从 3 条免版权音乐候选中确认 1 条，并合入视频。
9. 在同一项目目录中得到全部原图、视频、配乐、文案、来源记录和最终交付清单。

## 3. 范围

### 3.1 已确认的范围

- 交互入口：Codex 对话，不开发独立网页。
- 产品输入：单产品、一张产品图。
- 场景预览：四种标准场景各生成 1 张；用户选择 1–3 种。
- 完整套装：每个入选场景生成 3 张候选图、1 条视频、3 套文案、1 条配乐。
- 分镜：三段式，细节特写 → 使用场景 → 产品定格。
- 视频规格：8 秒、9:16，默认 720p。
- 视频语言：按场景自适应运镜。
- 成片：不烧录标题、字幕或 CTA。
- 文案：全部产出种草型、高级型、详情页转化型。
- 音乐：Pixabay 免版权曲库，每种入选场景给 3 条候选，试听后由用户确认。
- 文案生成：当前 Codex 会话模型，不调用火山文本模型。
- 图像和视频：火山方舟 Seedream 5.0 Pro 与 Seedance 2.5。

### 3.2 非目标

- 不实现浏览器或桌面 GUI。
- 不实现商品批量导入或电商后台同步。
- 不生成产品不存在的材料、功效、认证或促销事实。
- 不在用户未确认的情况下一次生成所有场景的完整视频。
- 不新增独立文本生成 API Key。
- 不替换现有 fal.ai、Replicate、Atlas 等图片/视频供应商。

### 3.3 反目标

- 用户看不懂下一步该做什么。
- 图片主体漂移后仍继续生成视频。
- 静默换模型、静默扣费或静默切供应商。
- 任意 AI 系统编造产品卖点。
- 配乐来源或授权不可追溯。

## 4. 用户流程

```text
产品图 + 产品名称 + 已知卖点
        │
        ▼
确认四场景预览预算
        │
        ▼
生成 4 张场景预览图
        │
        ▼
用户选择 1–3 种完整套装
        │
        ▼
确认三段式分镜、规格、文案和音乐计划
        │
        ▼
每个入选场景生成 3 张 Seedream 候选图
        │
        ▼
每个场景由用户选择 1 张
        │
        ▼
每个场景生成 1 条 Seedance 视频
        │
        ▼
用户逐条确认视频
        │
        ▼
Codex 生成三套文案
        │
        ▼
每场景提供 3 条音乐候选
        │
        ▼
用户试听并选择
        │
        ▼
混音、ffprobe 验证、交付清单
```

任何创作选择都必须提供 3–4 个枚举选项，并记录用户选择。每次人工门最多提出一个需要用户决定的问题。

## 5. 架构

### 5.1 配置桥

新增 `lib/seedance_config.py`：

- 默认读取 `~/.seedance/config.json`。
- `SEEDANCE_CONFIG_PATH` 可覆盖位置。
- 环境变量优先：`ARK_API_KEY`、`ARK_BASE_URL`、`ARK_SEEDREAM_MODEL`、`ARK_SEEDANCE_MODEL`。
- 输出键名和掩码，不输出完整 Key。
- 配置缺失、JSON 损坏或字段无效时返回面向小白的错误说明。
- 不修改用户已有配置，除非用户明确要求。

复用并调整 `tools/video/seedance_ark.py`，使其可通过同一个配置桥获得 Key、Base URL 和默认视频模型。

### 5.2 Seedream 图片工具

新增 `tools/graphics/seedream_ark_image.py`：

- 工具名：`seedream_ark_image`
- capability：`image_generation`
- provider：`ark`
- 输入：产品图、prompt、模型、尺寸、张数、输出目录。
- 输出：每张图的路径、模型、prompt、来源和耗时。
- 支持 ARK 返回的 base64 和临时 URL。
- 默认模型：`doubao-seedream-5-0-pro-260628`。
- 默认不加水印。
- 不自动切换供应商。

新增 `schemas/tools/seedream_ark_image.schema.json`。

### 5.3 Seedance 视频工具

复用 `tools/video/seedance_ark.py`，无需复制一套新的 Seedance 客户端。工作流将选中的场景图作为 reference image，提交 8 秒、9:16、720p 的三段式视频任务。

视频 prompt 使用固定的产品锁定和三段分镜：

```text
GLOBAL STYLE
SCENE
PRODUCT LOCK
SHOT 1: 0–3 seconds ...
SHOT 2: 3–6 seconds ...
SHOT 3: 6–8 seconds ...
OPTICS / CAMERA
PHYSICS
LIGHTING
AUDIO: no music, no dialogue, no sound effects
```

音频后期单独添加，Seedance 生成阶段关闭原生音频，避免和用户选中的配乐冲突。

### 5.4 文案

文案不经过火山模型。Codex 根据以下输入生成：

- 用户提供的产品名称和卖点；
- 产品图；
- 选中场景；
- 确认后的视频内容；
- 目标平台与用户选定的三种文案风格。

输出 `product_copy` artifact，包含三套变体：

- `grassroots`
- `premium`
- `conversion`

每套包含主标题、副标题、3–4 个亮点和社交文案。所有未被用户提供的事实必须放入 `assumptions` 或不写。

### 5.5 音乐

每个入选场景使用 `pixabay_music` 的候选搜索模式一次返回最多三条结果。skill 向用户展示标题、作者、时长和授权，等待用户选择后才下载选中的曲目到 `assets/music/`。

为保持现有调用兼容，`pixabay_music` 增加：

- `operation="search"`：只搜索，不写音频文件，返回最多 `max_results` 条候选及受限的 Pixabay 下载地址；
- `operation="download"`：下载用户选中的 Pixabay 候选；
- `operation="search_and_download"`：保留原有“搜索并下载第一条”行为。

下载地址必须来自允许的 Pixabay CDN 域名，避免把通用 URL 下载器暴露给模型。

选择后用 `video_compose` 的 encode 路径或现有音频合入能力将音乐加入视频，并通过 `ffprobe` 验证：

- 视频时长接近 8 秒；
- 有音频流；
- 无空白或损坏文件；
- 最终文件位于 `renders/`。

### 5.6 流水线

新增 `pipeline_defs/seedance-product-scene.yaml`，阶段如下：

| 阶段 | 产物 | 用户门 |
|---|---|---|
| `idea` | `brief` | 确认产品图、事实和输入质量 |
| `proposal` | `proposal_packet`、`decision_log` | 确认预览预算与总体路线 |
| `style_preview` | `asset_manifest` | 选择 1–3 种完整套装 |
| `scene_plan` | `scene_plan` | 确认三段式分镜和场景运镜 |
| `assets` | `asset_manifest` | 每个场景选 1 张主图 |
| `video_assets` | `asset_manifest` | 逐场景确认视频 |
| `copy` | `product_copy` | 确认三套文案 |
| `music` | `product_delivery` 草稿 | 每个场景选择 1 条音乐 |
| `compose` | `render_report`、`final_review` | 自动执行 |
| `publish` | `product_delivery`、`publish_log` | 确认交付清单 |

`style_preview`、`video_assets`、`copy` 和 `music` 是非标准阶段，但 manifest schema 允许新增阶段。checkpoint 通过 pipeline manifest 获取阶段顺序和审批门。

### 5.7 知识与阶段技能

新增 Layer 3：`.agents/skills/seedance-product-scene/SKILL.md`，吸收本地 skill 的交互、场景、提示词、错误处理和成本意识，并改为通过 OpenMontage registry 调用工具。

新增 `skills/pipelines/seedance-product-scene/`：

- `executive-producer.md`
- `idea-director.md`
- `proposal-director.md`
- `scene-director.md`
- `asset-director.md`
- `video-director.md`
- `copy-director.md`
- `music-director.md`
- `compose-director.md`
- `publish-director.md`

Python 不负责流程编排或创作决策；审批和选项由 skill 指导 Codex 执行。

## 6. 数据与目录

```text
projects/<project-id>/
├── artifacts/
│   ├── brief.json
│   ├── proposal_packet.json
│   ├── scene_plan.json
│   ├── asset_manifest.json
│   ├── product_copy.json
│   ├── render_report.json
│   └── product_delivery.json
├── assets/
│   ├── input/product.png
│   ├── images/style-preview/
│   ├── images/<style>/
│   ├── video/<style>/
│   ├── music/<style>/
│   └── copy/
├── renders/
│   └── <style>/final.mp4
└── decision_log.json
```

每条图像、视频和音乐记录必须包含 provider、model、prompt/query、来源、成本或免费授权、生成时间和场景 ID。

## 7. 审批与不确定性规则

### 7.1 创建型决策

以下选择必须经用户批准：

- 场景预览和完整套装数量；
- 场景风格；
- 视频运镜语言；
- 分镜结构；
- 视频时长和画幅；
- 最终图片；
- 最终视频；
- 文案风格；
- 音乐候选和最终歌曲；
- 任何新增画面文字、CTA 或品牌元素；
- 任何供应商、模型、分辨率或预算变更。

每次提供 3–4 个互斥选项，默认推荐项标出，用户可以选择编号或文字描述。

### 7.2 不确定实现

出现以下情况时停止，不继续消耗：

- ARK 返回结构无法安全解析；
- 产品主体无法保持；
- 需要的信息在现有 API 中没有；
- 音乐候选去重失败；
- 视频混音或 ffprobe 验证失败；
- 现有工具无法在不破坏 OpenMontage 架构的前提下完成需求；
- 两个已确认决策互相冲突。

停止时说明：已尝试什么、哪里失败、是否有费用、有哪些 3–4 个可选解决方向、推荐哪一个。

## 8. 成本与安全

- 真实生成前显示场景数、图片数、视频数和未知价格。
- 未知价格不显示为 0。
- API Key 不写入 Git，不出现在 prompt、产物、日志或聊天。
- 首次真实生成只做用户确认的预览批，不后台批量生成完整视频。
- 每个最终视频生成前再次确认模型、时长、比例、数量和费用估算。
- 音乐只下载免版税候选，记录标题、作者和授权。

## 9. 错误处理

| 场景 | 用户看到的内容 | 系统行为 |
|---|---|---|
| 无配置 | 需要配置 ARK Key，并按 6 步说明操作 | 停止 |
| 401 | Key 可能不对或过期 | 停止 |
| 403 | 模型未开通或无权限 | 停止 |
| 429 | 调用频繁或额度不足 | 停止 |
| 图片主体漂移 | 说明哪张不合格 | 不进入视频 |
| 视频失败 | 显示任务 ID 和可恢复状态 | 不扣第二次提交 |
| 音乐搜索失败 | 展示试听来源不可用的原因 | 提供换候选或用户上传 |
| 混音失败 | 显示验证失败原因 | 保留原始视频和音乐 |

## 10. 自检结论

按“一个没看过仓库的实现者”视角检查后，以下内容均已确定：

- 交互入口和运行环境；
- 用户选择范围；
- 图片、视频、文案和音乐路径；
- 不需要火山文本模型；
- 主要审批门；
- 项目目录和数据来源；
- 失败时停止而不是自动替换。

未决决定只在真实商品内容层面出现，例如具体产品事实、当前批次要选哪些场景和哪首音乐。这些不属于框架实现，必须在该次生产时询问用户。
