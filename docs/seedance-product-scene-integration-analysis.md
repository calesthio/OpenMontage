# OpenMontage × seedance-product-scene 实现分析

> 分析日期：2026-10-22  
> 技能源：`~/.codex/skills/seedance-product-scene/`  
> OpenMontage 工作区：`feat/seedance-product-scene`

## 1. 结论

整合应采用“原生工具 + OpenMontage 流水线 + Codex 交互”的组合，而不是把 skill 的独立 CLI 脚本整体搬进仓库。

- Seedream：新增 OpenMontage 原生 `BaseTool`，复用 skill 中已经验证过的火山 ARK 图片请求格式。
- Seedance：直接复用现有 `seedance_ark`，不创建第二套视频客户端。
- 文案：由当前 Codex 模型生成，不用 skill 的静态文案模板，也不调用火山文本模型。
- 音乐：复用现有 `pixabay_music`，每场景用三条不同查询生成三个候选，等待用户试听确认。
- 分镜与审批：由新增 pipeline manifest 和 director skills 驱动，不写进 Python 编排器。
- 最终合成：无画面文字版本使用 FFmpeg/`video_compose`，音乐通过 `audio_path` 合入并用 ffprobe 验证。

## 2. 当前注册表状态

| 工具 | 能力 | 状态 | 结论 |
|---|---|---|---|
| `seedance_ark` | `video_generation` | available | 复用 |
| `pixabay_music` | `music_search` | available | 复用；实验性抓取 |
| `audio_mixer` | `audio_processing` | available | 复用 |
| `video_compose` | `video_post` | available | 复用 FFmpeg 路径 |

`seedance_ark` 现在可以通过 `~/.seedance/config.json` 取得 Key、Base URL 和视频模型。测试中不得使用开发者真实配置。

## 3. 两侧实现对照

| Capability | Skill implementation | OpenMontage implementation | Reuse decision | Gap | Owner task |
|---|---|---|---|---|---|
| 配置读取 | 直接读取 `~/.seedance/config.json` | 原 ARK 工具读取 `ARK_API_KEY` | 新增共享配置桥 | 环境变量和 skill 配置未统一 | Part 1，已完成 |
| Seedream 生图 | `seedance_client.py` 调用 `POST /images/generations` | `seedream_image` 只走 fal.ai | 新增原生 `seedream_ark_image` | OpenMontage 无 ARK 图生图工具 | Task 6 |
| Seedance 视频 | 脚本提交、轮询、下载 | `seedance_ark` 具备异步任务、轮询、下载、成本和安全校验 | 直接复用 | 无核心缺口 | 已完成 |
| 产品图编码 | 转 base64 data URL | ARK 视频工具已有本地参考图编码 | 新图工具复用同样约定 | 需独立图片输入校验 | Task 6 |
| 场景预设 | 四种静态中文 prompt | 无产品场景预设 | 放到 Layer 3 skill | 缺少可审计的 OpenMontage 知识层 | Task 10 |
| 分镜 | 一条运镜 prompt | `scene_plan` artifact | 新建三段式场景计划 | 需明确 0–3/3–6/6–8 秒 | Task 9–10 |
| 图片确认 | 显示三张并等待选择 | checkpoint human gate | 新建 `assets` 门 | 需要按场景循环确认 | Task 9–10 |
| 视频确认 | 展示视频后等待确认 | checkpoint human gate | 新建 `video_assets` 门 | 需要逐场景记录确认 | Task 9–10 |
| 文案 | 四种固定模板 | 无产品文案 artifact | 由当前 Codex 生成三套变体 | 需要 schema 和事实约束 | Task 8、10 |
| 音乐 | skill 未实现 | `pixabay_music` 返回并下载第一条结果 | 每场景调用三次不同 query | 现有工具不返回候选列表 | Task 10–11 |
| 混音 | skill 关闭视频音频 | `audio_mixer`、`video_compose.audio_path` | 使用现有 FFmpeg 工具 | 需处理 8 秒裁切和淡入淡出 | Task 11 |
| 项目持久化 | 输出到普通目录 | `projects/<id>/` + artifacts/checkpoints | 使用 OpenMontage 约定 | 无 | Task 9–13 |
| 审批 | 对话按步骤提问 | manifest `human_approval_default` | 把创作决策写成阶段门 | 需要新增非标准阶段 | Task 9–10 |

## 4. 为什么图片工具必须原生化

skill 脚本具备完整的 ARK 图片调用示例，但它不适合直接作为 OpenMontage production tool：

1. 脚本是命令行入口，不是 `BaseTool`，不会进入 registry。
2. 它自行打印和退出进程，与 `ToolResult` 契约不兼容。
3. 它把输出视为普通目录，不记录 OpenMontage artifact provenance。
4. 它没有统一成本、重试、脱敏、事件和缓存接口。
5. 它直接读取配置，无法被 selector 或预算系统发现。

因此保留其请求协议和产品 prompt 知识，但实现一个新的原生工具。

## 5. 为什么视频不重复实现

`seedance_ark` 已经覆盖：

- 官方异步 create/query/cancel；
- 2.0 Standard/Fast/Mini 与 2.5；
- 本地图片 data URL；
- 任务轮询、结果下载；
- 临时 URL 和错误脱敏；
- token 估算和未知价格保护；
- 本地 ffprobe 输出验证。

产品流程只需要传入：

```python
{
    "operation": "image_to_video",
    "prompt": "<three-shot product prompt>",
    "reference_image_path": "<selected scene image>",
    "model_variant": "2.5",
    "duration": 8,
    "aspect_ratio": "9:16",
    "resolution": "720p",
    "generate_audio": False,
    "output_path": "<project>/assets/video/<style>/seedance-output.mp4",
}
```

## 6. 路径、prompt 和任务结果映射

| 数据 | 来源 | 持久化位置 | Artifact 字段 |
|---|---|---|---|
| 输入产品图 | 用户上传 | `assets/input/product.png` | `brief.product_image_path` |
| 预览 prompt | scene director | checkpoint/decision log | `prompt` |
| 场景图 | `seedream_ark_image` | `assets/images/<style>/` | `asset_manifest.assets[].path` |
| 选中图片 | 用户审批 | decision log + delivery | `selected_image` |
| Seedance prompt | video director | asset metadata | `prompt` |
| task_id | `seedance_ark` | checkpoint/decision log | `task_id` |
| 原始视频 | 工具下载 | `assets/video/<style>/` | `asset_manifest.assets[].path` |
| 音乐候选 | `pixabay_music` | `assets/music/<style>/candidates/` | `music_candidates` |
| 选中音乐 | 用户审批 | decision log + delivery | `selected_music.path` |
| 最终视频 | `video_compose` | `renders/<style>/final.mp4` | `product_delivery.outputs.video` |

任何远程临时 URL 都只用于下载，不作为最终 artifact 路径。

## 7. 文案实现决策

skill 的文案函数是四组固定模板，只能作为兜底参考，不能作为默认产品文案，因为它无法知道用户产品的具体卖点，容易产生不实描述。

默认实现：

- 当前 Codex 会话读取用户输入、产品图和已确认场景；
- 产出 `grassroots`、`premium`、`conversion` 三套文案；
- 每套包含标题、副标题、3–4 个亮点和社交文案；
- 未提供的事实写入 `assumptions`，不得自行补造；
- artifact 记录 `generation_source: "codex_active_session"`；
- 不申请或调用任何火山文本模型。

## 8. 音乐实现决策

`pixabay_music` 每次只返回并下载第一条匹配结果，因此采用以下流程：

1. 根据场景生成三条不同音乐查询；
2. 分别调用 `pixabay_music`，输出到 `candidates/01.mp3`、`02.mp3`、`03.mp3`；
3. 如果重复，换一条查询重试一次；
4. 展示标题、作者、时长、授权和绝对路径，等待用户试听选择；
5. 用用户选中的曲目合入视频；
6. 该工具是实验性网页抓取，失败时停止并展示 3–4 个替代方向，不静默切换。

音乐选择是创作决策，不能由程序自动选第一条。

## 9. 创作审批与技术细节

必须由用户审批：

- 场景与套装数量；
- 图片风格和最终图片；
- 分镜、运镜、视频时长和比例；
- 最终视频；
- 三套文案是否接受；
- 音乐候选和最终曲目；
- 新的画面文字、CTA 或品牌元素；
- 供应商、模型或预算变更。

实现者可以自行决定：

- 文件名、内部函数名和测试组织；
- ARK base64 与 URL 两种返回的解析细节；
- 临时文件清理；
- JSON schema 字段的合理技术约束；
- 在不改变用户体验的情况下修复 registry 或 selector 适配。

## 10. 未决实现的处理

当前没有阻塞整体设计的未知项。仍存在两个必须在实现时验证的风险：

1. Pixabay 页面抓取是实验性接口，三条查询可能返回重复曲目或失效。
2. ARK Seedream 返回可能同时存在 URL、base64 或错误结构，需要严格测试。

这两个风险均有明确降级路径：音乐停止并询问用户；图片响应校验失败则不写文件、不进入视频。

## 11. 整合边界

- 保留 skill 作为独立 CLI 能力，不删除、不改写用户现有配置。
- OpenMontage 新增路径独立注册，不改变现有 fal.ai Seedream 行为。
- 视频 JSON 交互和审批由 pipeline skill 驱动，不新增 Python orchestrator。
- 最终实现必须提供离线 mock E2E，验证不会意外产生付费请求。
