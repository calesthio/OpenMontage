# 中转站（第三方 API Relay）配置说明

OpenMontage 可以完全通过第三方 API 中转站完成生图、生视频和 TTS，不需要任何官方供应商的 API Key。
一个中转站可以提供多个模型，不同模型也可以来自不同中转站；每个模型在 OpenMontage 里都是一个独立工具，
走标准流水线、检查点、预算和审查。

- 配置文件：`relay_providers.yaml`（从 [`relay_providers.example.yaml`](../relay_providers.example.yaml) 复制，已被 git 忽略）
- 密钥：只放在 `.env` / 环境变量里，配置文件中只写变量名
- 命令行：`python -m tools.relay check | list | models | resume | mock-server`
- Agent 使用说明：[`.agents/skills/relay-providers/SKILL.md`](../.agents/skills/relay-providers/SKILL.md)

---

## 0. 团队成员快速开始（已配置好的团队中转站）

仓库里的 [`relay_providers.team.yaml`](../relay_providers.team.yaml) 是已真实验证过的团队配置（不含密钥）。

```bash
git clone https://github.com/YueHua46/OpenMontage && cd OpenMontage
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt
```

在 `.env` 中写（Key 找管理员要，不要通过 git/群聊传）：

```
OPENMONTAGE_RELAY_CONFIG=relay_providers.team.yaml
TSTSTS_MEDIA_API_KEY=你的Key
```

然后 `python -m tools.relay check` 确认 `api_key_set: true`。Codex 用户再执行一次
`cp .codex/prompts/relay-video.md ~/.codex/prompts/`；需要本机装好 ffmpeg。

---

## 1. 五分钟上手

```bash
# 1) 复制示例配置
cp relay_providers.example.yaml relay_providers.yaml

# 2) 在 .env 中写入密钥（变量名与配置里的 api_key_env 一致）
echo "MYRELAY_API_KEY=你的key" >> .env

# 3) 校验配置（不联网，不打印密钥）
python -m tools.relay check

# 4) 查看这个 Key 在中转站上实际能用哪些模型（GET /v1/models，免费）
python -m tools.relay models --relay myrelay

# 5) 跑 Mock 测试（本地假中转站，不计费）
python -m pytest tests/tools/test_relay_providers.py tests/tools/test_relay_e2e.py

# 6) 都通过后，把 relay_providers.yaml 中该中转站的 live 改为 true
```

然后直接对 Codex / Claude 说需求即可，例如：

> 我给你 `inbox/` 里的四张图和 `music_library/night.mp3`，你自己决定怎么做一条 30 秒的电影感视频。

Agent 会分析素材、推断时长/画幅/风格、规划分镜和每个镜头用哪个模型，把完整方案和费用估算交给你确认后再生成。

---

## 2. 配置结构

```yaml
routing:
  paid_provider_policy: relay_only   # 只允许中转站工具和免费/本地工具参与选择

relays:
  <中转站名>:
    base_url: https://relay.example.com    # 只写域名会自动补 /v1（Ark 协议补 /api/v3）
    api_key_env: MYRELAY_API_KEY           # 环境变量名
    auth_header: Authorization             # 可选，默认 Authorization
    auth_scheme: Bearer                    # 可选；裸 key 用 ""
    extra_headers_env: {X-Org: MY_ORG_ID}  # 可选，需要额外鉴权头时从环境变量取
    live: false                            # 真实计费开关
    trust_env_proxy: true                  # 是否使用系统 HTTP(S)_PROXY
    allow_insecure_http: false             # 非本机 http:// 默认拒绝
    models:
      - name: 显示/工具名用的短名
        model: 中转站的准确模型ID
        protocol: openai_images | openai_videos | openai_video_generations | ark_seedance | generic_async | openai_speech | openai_chat
        capabilities: [...]                # 必须显式声明
        image_input: data_uri | base64 | multipart | url
        limits: {...}                      # 允许的时长、尺寸、画幅、音色等
        defaults: {...}                    # 默认参数
        pricing: {...}                     # 用于预算控制
        poll: {interval_seconds: 5, timeout_seconds: 900}
        request: {...}                     # 覆盖或定义请求映射
        tool_name: 可选，自定义工具名
        agent_skills: [seedance-2-0]       # 可选，模型族的提示词技能
        best_for: [...]                    # 可选，帮助选择器打分
```

### 2.1 协议（protocol）

| 协议 | 类型 | 接口 | 能力上限 |
|---|---|---|---|
| `openai_images` | 图 | `POST /images/generations`（JSON）；图生图 `POST /images/edits`（multipart，字段 `image[]`） | 文生图、图生图 |
| `openai_videos` | 视频 | `POST /videos`（multipart，首帧作为 `input_reference` 文件）→ `GET /videos/{id}` → `GET /videos/{id}/content`（带鉴权下载） | 文生视频、图生视频 |
| `openai_video_generations` | 视频 | `POST /video/generations`（JSON，首帧放 `input_reference`）→ `GET /videos/{id}` | 文生视频、图生视频 |
| `ark_seedance` | 视频 | 火山方舟兼容：`POST /contents/generations/tasks` → `GET .../tasks/{id}`；**复用现有 `seedance_ark` 适配器的请求构建与校验** | 文生、图生、首尾帧、参考图 |
| `generic_async` | 图/视频 | 完全声明式：提交、任务 ID 路径、轮询、状态值、结果 URL 全部可配 | 由你在模板里接入的变量决定 |
| `openai_speech` | TTS | `POST /audio/speech` → 音频字节 | 文本转语音 |
| `openai_chat` | 文本 | 只做登记，不生成工具（规划由 Agent 自己完成） | — |

> 不要假设所有中转站都是 OpenAI 兼容。字段不同的，用 `request:` 覆盖预设；完全不同的，用 `generic_async`。

### 2.2 能力（capabilities）

| 类型 | 可选能力 |
|---|---|
| image | `text_to_image`, `image_to_image` |
| video | `text_to_video`, `image_to_video`（首帧）, `first_last_frame`（首尾帧）, `reference_to_video`（参考图） |
| tts | `text_to_speech` |

**没有声明的能力就是不支持**：调用时会返回 `unsupported_capability`，不会丢掉图片假装成功；
选择器在排序阶段就会把不支持的模型排除（例如只支持文生视频的模型不会被选去做图生视频）。

### 2.3 本地图片作为首帧（image_input）

| 取值 | 发送方式 | 适用 |
|---|---|---|
| `data_uri`（默认） | `data:image/png;base64,...` 放在 JSON 字段里 | 大多数 JSON 接口 |
| `base64` | 纯 base64 字符串 | 部分国内中转 |
| `multipart` | 作为文件上传 | `openai_videos`、`/images/edits` |
| `url` | 只接受公网 URL | 只认 URL 的接口；本地文件会被明确拒绝 |

OpenMontage **不会**为了拿 URL 而把你的图片偷偷传到别的图床或其他付费平台。

文件会先做格式校验（PNG/JPEG/WEBP/GIF/BMP）和大小限制（`limits.max_image_mb`，默认 10MB）。

### 2.4 价格（pricing）与预算

```yaml
pricing: {currency: CNY, cny_per_usd: 7.2, per_second: 0.6}   # 按秒
pricing: {per_request: 0.5}                                    # 按次（USD）
pricing: {currency: CNY, per_image: 0.3}                       # 按张
pricing: {per_1k_chars: 0.015}                                 # TTS 按千字符
```

- `estimate_cost()` 按这里计算并换算成美元，接入 `tools/cost_tracker.py` 的 estimate → reserve → reconcile。
- 没配价格：预算系统无法计费，调用会被拒绝（`price_required`），除非你同意后 Agent 传 `allow_unpriced: true`。
- 轮询超时的那次调用报 `cost_usd: 0` 和 `committed_cost_usd`；恢复成功的那次才报实际费用——同一个任务只记一次。

### 2.5 参数限制（limits）与默认值（defaults）

```yaml
limits:
  durations: [5, 10]                 # 或 duration_range: [4, 15]
  aspect_ratios: ["16:9", "9:16"]
  resolutions: [720p, 1080p]
  sizes: ["1280x720", "720x1280"]
  size_map: {"16:9": "1280x720", "9:16": "720x1280"}   # 画幅 → size
  max_reference_images: 4
  max_image_mb: 10
  max_chars: 4000                    # TTS
  voices: [alloy, nova]              # TTS
defaults:
  duration: 5
  aspect_ratio: "16:9"
  resolution: 720p
  params: {watermark: false}         # 固定附加到请求体的字段
```

不在 `limits` 内的参数会在**发送前**被拒绝并列出允许值，不会偷偷改成别的值。

---

## 3. 自定义协议（generic_async）

模板里的 `{{变量}}`：整串只有一个变量时保留原类型（数字还是数字）；变量为空时整个字段会被删除，不会发 `null`。

可用变量：`model` `prompt` `negative_prompt` `duration` `duration_str` `aspect_ratio` `resolution`
`size` `width` `height` `seed` `first_frame` `first_frame_file` `last_frame` `last_frame_file`
`reference_images`（视频）；图片模型另有 `images` `quality`。

```yaml
- name: wan-i2v
  model: wan2.5-i2v
  protocol: generic_async
  kind: video
  capabilities: [image_to_video]
  image_input: base64
  request:
    submit:
      method: POST
      path: /v2/video/submit
      body_format: json            # 或 multipart（配合 files: {字段名: "{{first_frame_file}}"}）
      body:
        model: "{{model}}"
        input: {prompt: "{{prompt}}", first_frame_image: "{{first_frame}}"}
        parameters: {duration: "{{duration}}"}
    response:
      task_id: "data.task_id|task_id"     # 点号路径，| 分隔备选
      error: "message|error.message"
    poll:
      path: /v2/video/tasks/{task_id}
      status: "data.status"
      success: [SUCCESS]
      failure: [FAILED, CANCELED]
      error: "data.fail_reason"
      result_url: "data.video_url|data.results.0.url"
    download:                              # 可选：结果需带鉴权从中转站下载时
      path: /v2/video/tasks/{task_id}/file
```

配置校验会检查：声明了 `image_to_video` 却没在 `submit` 中使用 `{{first_frame}}`/`{{first_frame_file}}` 的，直接报错——防止首帧被静默丢弃。

覆盖预设同理（深度合并），例如某中转的 `/video/generations` 用 `image` 字段、轮询走自己的路径：

```yaml
protocol: openai_video_generations
request:
  submit: {body: {image: "{{first_frame}}", input_reference: null}}
  poll: {path: "/video/generations/{task_id}", result_url: "data.url"}
```

---

## 4. 异步任务、超时恢复与本地保存

每次生成都会在 `output_path` 旁写一个 `<文件名>.relay-job.json`，**在付费请求发出之前**就写好。

| 情况 | 行为 |
|---|---|
| 轮询超时 | 返回 `status: pending`，不算失败；**用同样的参数再调用一次**（或 `resume_job`、或 `python -m tools.relay resume <job.json>`）会继续轮询同一个任务，不会重新提交 |
| 提交时网络超时 / 网关 502、504 | 记为 `submit_unknown`（中转站可能已受理并扣费）；再次调用会拒绝重复提交，需你去中转站后台核对后，同意才传 `confirm_resubmit: true` |
| 任务失败 | 识别 `failed/error/cancelled/expired` 等状态并给出中转站返回的原因；重试是新的付费请求，需要确认 |
| 4xx 拒绝 | 视为未受理；`model_not_found` 会提示用 `python -m tools.relay models` 查看该 Key 可用模型 |
| 成功 | **立即下载到本地**（`.part` 临时文件 + 原子替换，免费重试 3 次），视频用 ffprobe 校验确有视频流；远程 URL 只作出处记录 |
| 下载失败 | 任务保持"已成功"，再次调用只重新下载，不重新提交 |
| 本地文件被删 | 再次调用会从记录的结果重新下载（URL 未过期时），费用记 0 |
| 同一 output_path 换了提示词 | 拒绝（`job_conflict`），避免覆盖；每个镜头/每次重拍用不同文件名 |

job 文件里只有任务 ID、状态、模型、请求摘要（图片只存哈希），**不含密钥，也不含 base64 图片**。

---

## 5. 精确选择与"禁止擅自换供应商"

- 每个模型一个工具：`relay_<中转站>_<模型短名>`，`hosting_provider` = 中转站名。
- 选择器支持：`preferred_tool`（精确到工具，永不回退）、`hosting_provider` + `model`（精确到中转站和模型 ID）。
- `paid_provider_policy: relay_only`：选择器只会在中转站工具和免费/本地工具中挑；其他收费官方供应商（即使 .env 里有它们的 Key）不会被选中。临时放开需你同意后传 `allow_non_relay_paid: true`，或设置环境变量 `OPENMONTAGE_PAID_PROVIDER_POLICY=any`。
- 视频选择器原本会在某些工具上把本地首帧自动上传到 fal.ai；中转站工具刻意不暴露 `image_url` 字段，首帧始终直接发给你配置的中转站。
- 指定的工具不可用（缺 Key、不支持该操作）时，返回原因且**不尝试任何其他供应商**。

## 6. 真实计费开关（live）

- `live: false`（默认）：对真实中转站的计费请求在发出前被拒绝（`live_disabled`），`dry_run` 仍可用于查看请求映射。
- 本机地址（`127.0.0.1` / `localhost`）永远视为 Mock，可直接运行。
- 建议顺序：`check` → `models` → Mock 测试 → 对一个模型 `dry_run` 核对请求体 → `live: true` → 先生成一个样片 → 再批量。

`dry_run` 示例（Agent 会在第一次付费前展示给你）：

```python
video_selector.execute({"preferred_tool": "relay_myrelay_kling_v2_1", "prompt": "...",
                        "reference_image_path": "inbox/a.png", "dry_run": True,
                        "output_path": "projects/demo/assets/video/s1.mp4"})
# → endpoint / path / body（图片显示为 <data-uri image/png ...>）/ estimated_cost_usd
```

## 7. Mock 中转站

```bash
python -m tools.relay mock-server --port 8765 --key test-key
```

然后把某个中转站的 `base_url` 临时指向 `http://127.0.0.1:8765`，即可手动走完整流程（不计费）。
提示词里加 `[slow:N]`（需要 N 次轮询）、`[fail]`（任务失败）、`[504]`（提交结果未知）、`[400]`（模型不存在）可模拟各种异常。

## 8. 安全清单

- 配置文件里出现 `api_key/token/secret/password` 字面值或 `sk-...` 形式的值 → 整个文件拒绝加载。
- `base_url` 不允许内嵌账号密码或 `?key=`；非本机 `http://` 默认拒绝。
- 密钥只发往中转站自身的域名；结果文件若在 CDN 上，下载时不带密钥；带密钥的请求不跟随跨域重定向。
- 错误信息中的密钥会被替换为 `[REDACTED]`。
- 注意：如果你的系统设置了 `HTTP(S)_PROXY` 指向本机代理（如 127.0.0.1:7897），OpenMontage 测试套件的"禁止联网"保护对 `requests` 不再有效（流量经本机代理出去）。运行测试前建议清掉代理环境变量；中转站测试会自动清除。

## 9. 常见问题

**Q：连接测试通过，但生图/生视频返回 403 或 404？**
多半是 `base_url` 少了 `/v1`。只写域名时会自动补；如果你写了别的路径，就按你写的用。

**Q：报 `model_not_found` / "无可用渠道"？**
中转站按 Key 分组提供模型。运行 `python -m tools.relay models --relay <名字>` 查看这个 Key 实际可用的模型 ID，再改配置。

**Q：一个模型既能文生视频也能图生视频，但中转站两种接口字段不同？**
在同一个中转站下配置两个条目（不同 `name`），分别声明能力和 `request` 映射。

**Q：想让 Codex / Claude 知道这些？**
不需要额外操作。仓库的 `AGENTS.md`（Codex）和 `CLAUDE.md`（Claude Code）都指向 `AGENT_GUIDE.md`，其中已写明中转站的发现方式；Agent 会读取 `.agents/skills/relay-providers/SKILL.md` 学会具体用法。

另外提供了一键入口 `/relay-video`：

- Claude Code：在本仓库中直接输入 `/relay-video inbox/ 里的图和 song.mp3，做一条 30 秒电影感视频`（文件 `.claude/commands/relay-video.md`；技能镜像在 `.claude/skills/relay-providers/`）。
- Codex：Codex 只读取用户目录下的自定义 prompt，先执行一次
  `cp .codex/prompts/relay-video.md ~/.codex/prompts/`，重启后即可用 `/relay-video`。

这属于 **Skill（技能/说明文档）** 方式，不需要 MCP：Codex 和 Claude Code 本身就能在仓库里运行命令和 Python。
只有当你想在不能执行本地命令的客户端（例如纯聊天界面）里调用 OpenMontage 时，才需要再包一层 MCP 服务。
