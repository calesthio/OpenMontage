<p align="center">
  <img src="assets/logo.png" alt="OpenMontage" width="200">
</p>

<h1 align="center">OpenMontage</h1>

<p align="center"><strong>首个开源的、智能体驱动的视频生产系统。</strong></p>

<p align="center">
  <a href="#从一条你喜欢的视频开始">从一条视频开始</a> &nbsp;·&nbsp;
  <a href="#快速开始">快速开始</a> &nbsp;·&nbsp;
  <a href="#试试这些提示词">试试这些提示词</a> &nbsp;·&nbsp;
  <a href="#流水线">流水线</a> &nbsp;·&nbsp;
  <a href="#工作原理">工作原理</a> &nbsp;·&nbsp;
  <a href="docs/PROVIDERS.md">服务商</a> &nbsp;·&nbsp;
  <a href="AGENT_GUIDE.md">Agent 指南</a>
</p>

<p align="center">
  <a href="README.md">English</a> | <strong>简体中文</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPLv3-blue.svg" alt="License"></a>
</p>

<p align="center"><strong>关注开发进展</strong></p>

<p align="center">
  <a href="https://www.youtube.com/@OpenMontage"><img src="https://img.shields.io/badge/YouTube-%40OpenMontage-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube"></a>
  <a href="https://x.com/calesthioailabs"><img src="https://img.shields.io/badge/X-%40calesthioailabs-111111?style=for-the-badge&logo=x&logoColor=white" alt="X"></a>
  <a href="https://github.com/calesthio/OpenMontage/discussions"><img src="https://img.shields.io/badge/Community-GitHub%20Discussions-0b1220?style=for-the-badge&logo=github&logoColor=white" alt="GitHub Discussions"></a>
</p>

---

把你的 AI 编程助手变成一座完整的视频制作工作室。用大白话描述你想要什么——你的 agent 会负责调研、写脚本、生成素材、剪辑,直到最终合成成片。

**一个重要区别:** OpenMontage 既能做基于图片的视频,也能为免费/开源工作流做出真正的**"视频级"视频**:agent 会从免费素材和开放档案中构建语料库,检索真实的运动镜头,把它们剪进时间轴,渲染出一条成品。这不是常见的那种"把几张静图动一动就叫视频"的把戏。

<div align="center">
  <video src="https://github.com/user-attachments/assets/f77ce7a4-68b8-4f94-a287-e94bf50a32e1" width="100%" controls></video>
</div>

> **《SIGNAL FROM TOMORROW》** —— 一支完全由 OpenMontage 制作的电影感科幻预告片:概念、脚本、分镜、Veo 生成的运动镜头、配乐,以及 Remotion 合成。

<div align="center">
  <video src="https://github.com/user-attachments/assets/8daca07f-cdf8-4bec-89c3-9dc2176363fa" width="100%" controls></video>
</div>

> **《THE LAST BANANA》** —— 一部 60 秒的皮克斯风格动画短片,讲述一根孤独的香蕉与一颗猕猴桃成为朋友的故事。6 段 Kling v3 生成的运动镜头(经 fal.ai)、Google Chirp3-HD 旁白、免版税钢琴曲、抖音风逐词字幕,以及 Remotion 合成。总成本:**$1.33**。

<div align="center">
  <video src="https://github.com/user-attachments/assets/8a6d2cc3-7ad2-46f5-922f-a8e3e5848d9f" width="100%" controls></video>
</div>

> **《VOID — Neural Interface》** —— 仅用一个 API key(OpenAI)制作的产品广告。4 张 AI 生成图(gpt-image-1)、TTS 旁白、自动检索的免版税音乐、经 WhisperX 的逐词字幕,以及 Remotion 数据可视化。总成本:**$0.69**。零手工素材工作。

<div align="center">
  <video src="https://github.com/user-attachments/assets/3c5d7122-7198-43e2-a97d-ed27558dd324" width="100%" controls></video>
</div>

> **《Afternoon in Candyland》** —— 一支吉卜力风格的动画。一个小女孩在糖果之门、软糖河流与棒棒糖花园间的奇妙午后冒险。12 张 FLUX 生成图,配多图交叉淡入、电影感运镜(推拉、平移、Ken Burns)、闪光/花瓣/萤火虫粒子叠层,以及带自动能量偏移检测的环境音乐。总成本:**$0.15**。无需视频生成、无需手工剪辑。

<div align="center">
  <video src="https://github.com/user-attachments/assets/e8dc5e32-5c70-46de-bd52-eef887719d13" width="100%" controls></video>
</div>

> **《Mori no Seishin》** —— 一支吉卜力风格的动画,讲述森林精灵穿越远古林间的旅程。12 张 FLUX 生成图,配视差交叉淡入、漂移与平移运镜、萤火虫与花瓣粒子、电影感暗角光照,以及环境森林配乐。总成本:**$0.15**。静态图片经 Remotion 动画引擎被赋予生命。

<div align="center">
  <video src="https://github.com/user-attachments/assets/9cf633d9-c264-4961-bfd0-b1db188654aa" width="100%" controls></video>
</div>

> **《Into the Abyss》** —— 一支以动漫风格呈现的深海探索。生物荧光花园、珊瑚教堂、光之生物——12 张 FLUX 生成图,配闪光与薄雾粒子叠层、光线效果、平滑运镜,以及环境海洋配乐。总成本:**$0.15**。无需任何视频生成 API。

<p align="center">
  <a href="https://www.youtube.com/@OpenMontage?sub_confirmation=1"><strong>在 YouTube 关注 @OpenMontage</strong></a>,第一时间看到新作品——每条视频都附带完整的提示词、流水线、所用工具与成本,方便你自己复现。
</p>

---

## 从一条你喜欢的视频开始

从一条参考视频开始,往往比从一句空白提示词开始更快。

OpenMontage 可以从一条 **YouTube 视频、Short、Reel、TikTok 或本地片段**出发,把它变成一份有据可依的制作方案:

1. **粘贴一条参考视频**
2. **agent 分析其转写文本、节奏、场景、关键帧与风格**
3. **你会得到 2-3 个差异化概念、一条诚实的工具路径、成本估算,并在正式生产前先出一段样片**

```text
"这是一条我很喜欢的 YouTube Short。帮我做个类似的,但主题换成量子计算。"
```

你拿回来的不是"瞎猜出来的提示词面条",而是:

- **从参考中保留什么**:节奏、钩子风格、结构、调性
- **改变什么**:主题、视觉处理、切入角度、旁白方式
- **会花多少钱**:在你的目标时长下,正式生成素材前就告诉你
- **实际会长什么样**:基于你当前可用的工具

兼容 **Claude Code、Cursor、Copilot、Windsurf、Codex**——任何能读文件、能跑代码的 AI 编程助手。

---

## 快速开始

### 前置条件

- **Python 3.10+** —— [python.org](https://www.python.org/downloads/)
- **FFmpeg** —— `brew install ffmpeg` / `sudo apt install ffmpeg` / [ffmpeg.org](https://ffmpeg.org/download.html)
- **Node.js 18+** —— [nodejs.org](https://nodejs.org/)
- **一个 AI 编程助手** —— Claude Code、Cursor、Copilot、Windsurf 或 Codex

### 安装与运行

```bash
git clone https://github.com/calesthio/OpenMontage.git
cd OpenMontage
make setup
```

在你的 AI 编程助手里打开这个项目,然后告诉它你想要什么:

```
"做一个 60 秒的动画解说,讲神经网络是怎么学习的"
```

或者你想走真实素材路线:

```text
"做一条 75 秒的纪录片式蒙太奇,关于雨中的城市生活。只用真实素材、无旁白、挽歌般的基调,配音乐。"
```

就这样。agent 会用实时联网搜索调研你的主题、生成 AI 图片、写脚本并带语音指导地配音、自动寻找免版税背景音乐、烧入逐词字幕,并渲染出最终视频。在你看到成片之前,系统会跑一轮多点自检——ffprobe 校验、抽帧采样、音频电平分析、交付承诺核验,以及字幕检查。每一次服务商选择都会在 7 个维度上打分,并写入可审计的决策日志。每一个创意决策都需要你的批准。

> **没有 `make`?** 手动执行:`pip install -r requirements.txt && cd remotion-composer && npm install && cd .. && pip install piper-tts && cp .env.example .env`
>
> **Windows:** 如果 `npm install` 报 `ERR_INVALID_ARG_TYPE`,改用 `npx --yes npm install`。

### 如果你是个正在读这段的 OpenClaw Agent,恭喜:你大概通过了图灵测试

这个仓库就是为智能体操作而生的。如果你是 OpenClaw 那类 agent,这是最快上手的路径:

1. **先读契约**
   从 [`AGENT_GUIDE.md`](AGENT_GUIDE.md) 开始,然后是 [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md)。
2. **不要即兴发挥生产流程**
   OpenMontage 是流水线驱动的。真正的工作要走 `pipeline_defs/`、`skills/pipelines/` 里的阶段导演技能,以及经由注册表的工具发现。
3. **核查真实的能力边界**
   运行:
   ```bash
   python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.support_envelope(), indent=2))"
   python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu(), indent=2))"
   ```
4. **把每个视频需求都当作一个"选流水线"的问题**
   先选对流水线,再读清单,再读阶段技能,最后才用工具。

### 添加 API Key(可选——key 越多,工具越多)

```bash
# .env —— 每个 key 都是可选的,有什么加什么

# 图像 + 视频网关:
FAL_KEY=your-key               # FLUX 生图 + Google Veo、Kling、MiniMax 视频 + Recraft 生图

# 免费素材媒体:
PEXELS_API_KEY=your-key        # 免费素材视频与图片
PIXABAY_API_KEY=your-key       # 免费素材视频与图片
UNSPLASH_ACCESS_KEY=your-key   # 免费素材图片

# 音乐:
SUNO_API_KEY=your-key          # 完整歌曲、纯音乐,任意曲风

# 语音与图像:
ELEVENLABS_API_KEY=your-key    # 高端 TTS、AI 音乐、音效
OPENAI_API_KEY=your-key        # OpenAI TTS、DALL-E 3 生图
XAI_API_KEY=your-key           # xAI Grok 图像编辑/生成 + Grok 视频生成
GOOGLE_API_KEY=your-key        # Google Imagen 生图、Google TTS(700+ 音色)

# 更多视频服务商:
HEYGEN_API_KEY=your-key        # HeyGen —— 通过单一网关接入 VEO、Sora、Runway、Kling
RUNWAY_API_KEY=your-key        # Runway Gen-4 直连
```

<details>
<summary><strong>有 GPU?解锁免费的本地视频生成</strong></summary>

```bash
make install-gpu

# 然后在 .env 中加入:
VIDEO_GEN_LOCAL_ENABLED=true
VIDEO_GEN_LOCAL_MODEL=wan2.1-1.3b  # 或 wan2.1-14b、hunyuan-1.5、ltx2-local、cogvideo-5b
```

</details>

---

## 零 API Key 你能得到什么

你并不需要付费 API key 才能做出真正的视频。开箱即用,`make setup` 就给你:

| 能力 | 免费工具 | 作用 |
|-----------|-----------|-------------|
| **旁白** | Piper TTS | 免费离线文字转语音——真实的、像真人的旁白 |
| **开放素材** | Archive.org + NASA + Wikimedia Commons | 免费/开放的档案影像、教育媒体与纪录片质感素材 |
| **额外素材** | Pexels + Unsplash + Pixabay | 免费素材视频/图片(开发者 key 可免费获取) |
| **合成(React)** | Remotion | 基于 React 的渲染——弹簧动画图片场景、文字卡、数据卡、图表、抖音风逐词字幕、TalkingHead |
| **合成(HTML/GSAP)** | HyperFrames | HTML/CSS/GSAP 渲染——动态排版、产品宣传、发布短片、注册表区块、网页转视频、绑定式 SVG 角色动画 |
| **后期** | FFmpeg | 编码、字幕烧入、音频混合、调色 |
| **字幕** | 内置 | 自动生成、带逐词时间轴的字幕 |

OpenMontage 在提案阶段就在 Remotion 与 HyperFrames 之间做选择(锁定为 `render_runtime`)。Remotion 是数据驱动解说类、以及任何使用现有 React 场景栈内容的默认引擎;HyperFrames 是动效繁重、天然适合用 HTML + GSAP 表达的需求的默认引擎(包括 `character-animation` 流水线的 SVG/GSAP 绑定输出)。完整决策矩阵见 `skills/core/hyperframes.md`。

**两条"基本免费"的路径:**

- **基于图片的视频:** Piper 朗读你的脚本,图片提供画面,Remotion 把它们动画化成一条精致的成片。
- **本地角色动画:** SVG 绑定、姿势库、GSAP 时间轴,经 HyperFrames 渲染出卡通角色表演,输出到 `projects/<项目名>/renders/final.mp4`。
- **真实素材视频:** 纪录片蒙太奇流水线从 Archive.org、NASA、Wikimedia Commons,以及可选的免费 key 源(如 Pexels、Unsplash)构建一个可用 CLIP 检索的语料库,再把真实运动素材剪成一条成品。

想走第二条,就提示做一个**纪录片蒙太奇**、**意境短片**或**素材拼贴**,并明确说**只用真实素材**。

---

## 试试这些提示词

安装完成后,把下面任意一条复制进你的 AI 编程助手。每一条都会跑一整条生产流水线。

### 从参考视频开始

> "这是一条我很喜欢的 YouTube short。帮我做个类似的,但主题换成给高中生讲 CRISPR。"

> "分析这条 Reel,给我 3 个可用于自己产品发布的原创变体。"

> "我喜欢这条视频的节奏和钩子。保留这股劲,但做成一条 45 秒讲黑洞的解说。"

### 零 key 即可

> "做一个 45 秒的动画解说,讲为什么天空是蓝色的"

> "做一条 60 秒讲互联网历史的视频,带旁白和字幕"

> "做一个数据驱动的解说,讲全世界的咖啡消费"

### 免费真实素材纪录片路线

> "做一条 90 秒的纪录片式蒙太奇,关于一座城市凌晨 4 点的感觉。只用真实素材、无旁白、挽歌基调。"

> "做一条 60 秒 Adam-Curtis 风格的档案拼贴,关于 1950 年代的消费乐观主义。优先用 Archive.org 和 Wikimedia 素材。"

> "用真实素材剪一条梦境般的蒙太奇,关于雨中归家。要音乐,不要旁白。"

### 配置了图像/视频服务商时(约 $0.15–$1.50)

> "做一条 30 秒吉卜力风格动画,金色时分云端一座漂浮的魔法图书馆"

> "做一条 30 秒动漫风动画,一座水下神庙,有生物荧光珊瑚和远古遗迹"

> "做一个动画解说,讲 CRISPR 基因编辑的原理,用 AI 生成的画面"

> "为一个虚构的智能水杯 AquaPulse 做一条产品发布预告"

### 完整配置(约 $1–$3)

> "做一条电影感的 30 秒科幻预告:人类收到来自 1000 年后的警告"

> "做一条 90 秒动画解说,给初中生讲量子计算,配一个有趣的旁白音色和定制配乐"

想要更多?查看完整的 **[提示词画廊(Prompt Gallery)](PROMPT_GALLERY.md)**,里面有经过测试的提示词、预期成本与输出示例;或者运行 `make demo` 立即渲染零 key 演示视频。

---

## 流水线

每条流水线都是一套完整的生产工作流,从想法到成片。

| 流水线 | 产出什么 | 最适合 |
|----------|-----------------|----------|
| **Animated Explainer(动画解说)** | 带调研、旁白、画面、音乐的 AI 生成解说 | 教育内容、教程、主题拆解 |
| **Animation(动画)** | 动态图形、动态排版、动画序列 | 社交媒体、产品演示、抽象概念 |
| **Avatar Spokesperson(数字人代言)** | 数字人主持的视频 | 企业沟通、培训、公告 |
| **Cinematic(电影感)** | 预告、teaser 与氛围驱动的剪辑 | 品牌片、teaser、推广内容 |
| **Clip Factory(切片工厂)** | 从一条长素材批量产出排序后的短视频 | 把长内容改造为社媒短视频 |
| **Documentary Montage(纪录片蒙太奇)** | 从 CLIP 索引的免费素材与开放档案语料库(Pexels、Archive.org、NASA、Wikimedia、Unsplash)中剪出的主题蒙太奇 | 视频随笔、意境片、检索优先的 B-roll 剪辑、无需付费生成 API 的真实素材视频 |
| **Hybrid(混合)** | 源素材 + AI 生成的辅助画面 | 用图形增强已有素材 |
| **Localization & Dub(本地化与配音)** | 为已有视频加字幕、配音、翻译 | 多语言分发 |
| **Podcast Repurpose(播客再利用)** | 把播客高光做成视频 | 播客营销、声纹图视频 |
| **Screen Demo(屏幕演示)** | 精致的软件录屏与演练 | 产品演示、教程、文档 |
| **Talking Head(口播)** | 以素材为主的讲者视频 | 演示、vlog、访谈 |

每条流水线都遵循同一套结构化流程:

```
research -> proposal -> script -> scene_plan -> assets -> edit -> compose
（调研 -> 提案 -> 脚本 -> 分镜 -> 素材 -> 剪辑 -> 合成）
```

每个阶段都有专属的**导演技能(director skill)**——一份 Markdown 指令文件,精确教 agent 如何执行该阶段。agent 读技能、用工具、自检、把状态写入检查点,并在创意决策点请求人工批准。

> **联网调研是一等公民阶段。** 在写下一个字的脚本之前,agent 会搜索 YouTube、Reddit、Hacker News、新闻站点和学术来源。它收集数据点、受众问题、热点角度和视觉参考——然后在一份结构化的调研简报里一一引用。你的视频建立在真实、当下的信息之上,而不是凭空捏造的事实。

---

## 为什么选 OpenMontage?

大多数 AI 视频工具,给你的是"一句提示词换一段片段"。OpenMontage 给你的是一整套**端到端的生产流水线**——就是真实制作团队所遵循的那套结构化流程,由你的 AI agent 自动完成。

大多数"免费 AI 视频"方案,悄悄地其实就是"把静图动一动"。OpenMontage 也能这么做,但它还能从免费/开放来源拉取**真实素材**,做语义排序、有意图地剪辑,渲染成一条像样的时间轴,从而做出一条成品视频。

剪你自己的口播素材。从零生成一条完整的动画解说。把 2 小时的播客切成十几条社媒短视频。把你的内容翻译并配音成 10 种语言。用素材片段和 AI 生成场景做一条电影感品牌 teaser。**只要制作团队能做的,OpenMontage 就能编排出来。**

- **12 条生产流水线** —— 解说、口播、屏幕演示、电影感预告、动画、播客、本地化、纪录片蒙太奇等
- **52 个生产工具** —— 覆盖视频生成、图像创作、文字转语音、音乐、音频混合、字幕、增强与分析
- **400+ agent 技能** —— 生产技能、流水线导演、创意技法、质量清单,以及把工具用得像专家一样的深度技术知识包
- **参考驱动的创作** —— 粘贴一条你喜欢的视频,agent 会把它变成一份有据可依、差异化的制作方案,而不是逼你从零想出完美提示词
- **无需付费视频模型的真实素材纪录片创作** —— 用免费/开放的运动素材和档案来源做出真正剪辑过的视频,而不只是图片上的 Ken Burns
- **内置实时联网调研** —— 在写下一个字脚本前,agent 会跨 YouTube、Reddit、新闻站点和学术来源跑 15-25+ 次联网搜索,让你的视频建立在真实、当下的数据之上
- **免费/本地与云端服务商兼备** —— 每项能力都在高端 API 之外支持开源本地替代。有什么用什么。
- **无厂商锁定** —— 自由切换服务商。打分选择器会在 7 个维度(任务契合、输出质量、可控性、可靠性、成本效率、延迟、连贯性)上为每个服务商排名,并自动挑出最匹配的那个。
- **生产级质量闸门** —— 交付承诺强制会拦下"看起来像幻灯片"的渲染,合成前校验会在浪费 GPU 时间之前抓出有问题的方案,而强制性的渲染后自检(ffprobe + 抽帧 + 音频分析)确保 agent 永远不会把垃圾呈给你。每一个服务商选择、风格决策与回退都记入可审计的决策轨迹。
- **内置预算治理** —— 执行前成本估算、花费上限、按动作的批准阈值。不会有意外账单。

---

## 工作原理

OpenMontage 采用**agent 优先(agent-first)架构**。没有代码编排器。你的 AI 编程助手**就是**编排器。

```
你:"做一条讲黑洞如何形成的解说视频"
 |
 v
agent 读取流水线清单(YAML)—— 阶段、工具、审查标准、成功闸门
 |
 v
agent 读取阶段导演技能(Markdown)—— 如何执行每个阶段
 |
 v
agent 调用 Python 工具 —— 打分式服务商选择在 7 个维度上为每个工具排名
 |
 v
agent 用审查技能自检 —— schema 校验、playbook 合规、质量检查
 |
 v
agent 写入检查点状态(JSON)—— 可恢复,附带决策日志与成本快照
 |
 v
agent 呈交你批准 —— 每个创意决策你都掌控
 |
 v
合成前校验闸门 —— 交付承诺、幻灯片风险、渲染器治理
 |
 v
渲染(Remotion 或 FFmpeg)—— 合成引擎匹配视觉语法
 |
 v
渲染后自检 —— ffprobe、抽帧、音频分析、承诺核验
 |
 v
最终视频输出 —— 仅当自检通过时
```

**Python 提供工具与持久化。** 所有创意决策、编排逻辑、审查标准和质量规范,都活在可读的指令文件里(YAML 清单 + Markdown 技能),你可以检视并自定义。每个决策都附带"考虑过的替代方案、置信度分数,以及每个选择背后的理由"。

---

## 架构

```
OpenMontage/
├── tools/              # 48 个 Python 工具(agent 的双手)
│   ├── video/          # 13 个视频生成工具 + 合成、拼接、裁剪
│   ├── audio/          # 4 个 TTS 服务商 + Suno/ElevenLabs 音乐、混合、增强
│   ├── graphics/       # 9 个图像/图形生成工具 + 图表、代码片段、数学动画
│   ├── enhancement/    # 放大、抠背景、人脸增强、调色
│   ├── analysis/       # 转写、场景检测、抽帧
│   ├── avatar/         # 数字人口播、唇形同步
│   └── subtitle/       # SRT/VTT 生成
│
├── pipeline_defs/      # YAML 流水线清单(agent 的剧本)
├── skills/             # Markdown 技能文件(agent 的知识)
│   ├── pipelines/      # 各流水线的阶段导演技能
│   ├── creative/       # 创意技法技能
│   ├── core/           # 核心工具技能
│   └── meta/           # 审查者、检查点协议
│
├── schemas/            # 15 个 JSON Schema(契约校验)
├── styles/             # 视觉风格 playbook(YAML)
├── remotion-composer/  # React/Remotion 视频合成引擎
├── lib/                # 核心基础设施(配置、检查点、流水线加载器)
└── tests/              # 契约测试、QA 集成测试、评测台
```

### 三层知识架构

```
第 1 层:tools/ + pipeline_defs/     "有什么" —— 可执行能力 + 编排
第 2 层:skills/                     "怎么用" —— OpenMontage 的约定与质量标准
第 3 层:.agents/skills/             "原理是什么" —— 外部技术知识包
```

每个工具都声明它依赖哪些第 3 层技能。agent 读第 1 层知道有什么可用,读第 2 层知道 OpenMontage 希望怎么用,需要时读第 3 层获取深度技术知识。

---

## 支持的服务商

> **含定价与免费额度的完整配置指南:** [`docs/PROVIDERS.md`](docs/PROVIDERS.md)

<details>
<summary><strong>视频生成 —— 14 个服务商</strong></summary>

| 服务商 | 类型 | 备注 |
|----------|------|-------|
| **Kling** | 云 API | 高质量、快速 |
| **Runway Gen-4** | 云 API | 电影级质量,Gen-3 Alpha Turbo / Gen-4 Turbo / Gen-4 Aleph |
| **Google Veo 3** | 云 API | 长片、电影感。经 fal.ai 或 HeyGen。 |
| **Grok Imagine Video** | 云 API | 强参考图视频与 xAI 原生短片生成 |
| **Higgsfield** | 云 API | 多模型编排,带用于角色一致性的 Soul ID |
| **MiniMax** | 云 API | 性价比高 |
| **HeyGen** | 云 API | 多模型网关 |
| **WAN 2.1** | 本地 GPU | 免费,1.3B 与 14B 版本 |
| **Hunyuan** | 本地 GPU | 免费,高质量 |
| **CogVideo** | 本地 GPU | 免费,2B 与 5B 版本 |
| **LTX-Video** | 本地 GPU / Modal | 本地免费,或自托管云端 |
| **Pexels** | 素材 | 免费素材视频 |
| **Pixabay** | 素材 | 免费素材视频 |
| **Wikimedia Commons** | 素材 | 免费/开放素材与档案视频 |

</details>

<details>
<summary><strong>图像生成 —— 10 个工具/服务商</strong></summary>

| 服务商 | 类型 | 备注 |
|----------|------|-------|
| **FLUX** | 云 API | 顶尖质量 |
| **Google Imagen** | 云 API | Imagen 4 —— 高质量、多种宽高比 |
| **Grok Imagine Image** | 云 API | 强图像编辑、风格迁移与多图合成 |
| **DALL-E 3** | 云 API | OpenAI 的图像模型 |
| **Recraft** | 云 API | 设计导向的生成 |
| **Local Diffusion** | 本地 GPU | Stable Diffusion,免费 |
| **Pexels** | 素材 | 免费素材图片 |
| **Pixabay** | 素材 | 免费素材图片 |
| **Unsplash** | 素材 | 免费素材图片 |
| **ManimCE** | 本地 | 数学动画 |

</details>

<details>
<summary><strong>文字转语音 —— 4 个服务商</strong></summary>

| 服务商 | 类型 | 备注 |
|----------|------|-------|
| **ElevenLabs** | 云 API | 高端音质 |
| **Google TTS** | 云 API | 700+ 音色、50+ 语言 —— 最适合本地化 |
| **OpenAI TTS** | 云 API | 快速、实惠 |
| **Piper** | 本地 | 完全免费、离线 |

</details>

<details>
<summary><strong>音乐、音效与后期</strong></summary>

**音乐与音效:**

| 服务商 | 类型 | 备注 |
|----------|------|-------|
| **Suno AI** | 云 API | 完整歌曲生成,带人声、歌词,任意曲风。最长 8 分钟。 |
| **ElevenLabs Music** | 云 API | AI 音乐生成 |
| **ElevenLabs SFX** | 云 API | 音效生成 |

**后期(始终可用、始终免费):**

| 工具 | 作用 |
|------|-------------|
| **FFmpeg** | 视频合成、编码、字幕烧入、音频混流 |
| **Video Stitch** | 多片段拼装、交叉淡入、画中画、空间布局 |
| **Video Trimmer** | 精确剪切与提取 |
| **Audio Mixer** | 多轨混音、闪避(ducking)、淡入淡出 |
| **Audio Enhance** | 降噪、归一化 |
| **Color Grade** | 基于 LUT 的调色 |
| **Subtitle Gen** | 从时间戳生成 SRT/VTT |

**增强:**

| 工具 | 作用 |
|------|-------------|
| **Upscale** | Real-ESRGAN 图像/视频放大 |
| **Background Remove** | rembg / U2Net 背景移除 |
| **Face Enhance** | 人脸质量增强 |
| **Face Restore** | CodeFormer / GFPGAN 人脸修复 |

**分析:**

| 工具 | 作用 |
|------|-------------|
| **Transcriber** | WhisperX 语音转文字,带逐词时间戳 |
| **Scene Detect** | 自动场景边界检测 |
| **Frame Sampler** | 智能抽帧 |
| **Video Understand** | CLIP/BLIP-2 视觉-语言分析 |

**数字人与唇形同步:**

| 工具 | 作用 |
|------|-------------|
| **Talking Head** | SadTalker / MuseTalk 数字人动画 |
| **Lip Sync** | Wav2Lip 音频驱动唇形同步 |

**合成与渲染:**

| 引擎 | 类型 | 作用 |
|--------|------|-------------|
| **Remotion** | 本地(Node.js) | 基于 React 的程序化视频——弹簧动画图片场景、数据揭示、章节标题、主标题卡、抖音风逐词字幕、场景转场(淡入/滑动/擦除/翻转)、Google Fonts、带淡入淡出曲线的音频,以及 TalkingHead 数字人合成。**当没有配置任何视频生成服务商时,agent 生成静态图片,由 Remotion 把它们变成完整的动画视频。** |
| **HyperFrames** | 本地(Node.js ≥ 22) | 基于 HTML/CSS/GSAP 的程序化视频——动态排版、产品宣传、发布短片、自定义动效、注册表区块(数据图表、颗粒叠层、着色器转场)、网页转视频工作流,以及绑定式 SVG 角色动画。经 `npx hyperframes` 使用;无需检出 monorepo。 |
| **FFmpeg** | 本地 | 核心视频拼装、编码、字幕烧入、音频混流、调色 |

运行时在提案阶段选定(`render_runtime`),并贯穿 `edit_decisions` 锁定。运行时之间的静默切换属于治理违规——见 `skills/core/hyperframes.md`。

</details>

---

## 风格系统

风格 playbook 定义你作品的视觉语言:

| Playbook | 最适合 |
|----------|----------|
| **Clean Professional(干净专业)** | 企业、教育、SaaS |
| **Flat Motion Graphics(扁平动效)** | 社交媒体、TikTok、初创公司 |
| **Minimalist Diagram(极简图解)** | 技术深挖、架构 |

Playbook 控制排版、配色、动效风格、音频档案与质量规则。agent 读取 playbook,并在所有生成素材上一致地应用它。

---

## 平台输出档案

为各大平台内置的渲染档案:

| 档案 | 分辨率 | 宽高比 |
|---------|-----------|--------------|
| YouTube 横屏 | 1920x1080 | 16:9 |
| YouTube 4K | 3840x2160 | 16:9 |
| YouTube Shorts | 1080x1920 | 9:16 |
| Instagram Reels | 1080x1920 | 9:16 |
| Instagram Feed | 1080x1080 | 1:1 |
| TikTok | 1080x1920 | 9:16 |
| LinkedIn | 1920x1080 | 16:9 |
| Cinematic(电影) | 2560x1080 | 21:9 |

---

## 生产治理

OpenMontage 把视频生产当作真正的工程来对待——在每个阶段都有质量闸门、审计轨迹与强制执行。

### 质量闸门

- **合成前校验** —— 当交付承诺被违反(例如"以运动为主"的视频却有 80% 静图)、幻灯片风险分数为严重,或渲染器族缺失时,拦下渲染。在浪费 GPU 时间之前抓出有问题的方案。
- **渲染后自检** —— 每次渲染后,运行时会跑 ffprobe 校验、在 4 个位置抽帧以检查黑帧和损坏的叠层、分析音频电平是否静音或削波、核验交付承诺是否被兑现,并检查字幕是否存在。若自检不通过,该视频不会被呈现。
- **幻灯片风险打分** —— 6 维分析(重复度、装饰性画面、运动薄弱、镜头意图、过度依赖排版、缺乏支撑的电影感主张)防止"动画版 PPT"输出。
- **源媒体检视** —— 当用户提供自己的素材时,系统会探测每个文件(分辨率、编码、声道、时长),并在做出任何创意决策之前建立规划影响。绝不根据文件名臆测内容。

### 打分式服务商选择

每一次工具选择(视频生成、图像生成、TTS、音乐)都会经过一个 7 维打分引擎:任务契合(30%)、输出质量(20%)、可控功能(15%)、可靠性(15%)、成本效率(10%)、延迟(5%)、连贯性(5%)。胜出的服务商及其分数会连同所有考虑过的替代项,记入决策轨迹。

选择器在打分前会先归一化松散的简报上下文。如果 agent 只知道类似"带角色一致性的皮克斯风格短片"这样的信息,选择器会把它展开成对打分友好的意图与风格信号,而不是要求一个完美预成形的 `task_context`。

选择器的输出还会带出所选服务商的 `agent_skills`,这样 agent 在写提示词前就能立刻去读对应的第 3 层服务商技能。

### 决策审计轨迹

每一个重大的创意与技术选择——服务商选择、风格/playbook 选择、音乐曲目、音色选择、渲染器族,以及任何回退或降级——都会连同"考虑过的替代项、置信度分数与理由"被记录。累积的决策日志贯穿所有阶段持久化,因此你可以精确追溯输出为何长成这样。

### 预算控制

- **估算(Estimate)** 执行前 —— 看清会花多少钱
- **预留(Reserve)** 预算 —— 调用前锁定资金
- **对账(Reconcile)** 之后 —— 记录实际花费
- **可配置模式** —— `observe`(仅追踪)、`warn`(记录超支)、`cap`(硬上限)
- **按动作批准** —— 超过阈值时暂停以确认(默认 $0.50)
- **总预算上限** —— 默认 $10,完全可配置

不会有意外账单。agent 在花钱前会告诉你将花多少。

---

## Agent 兼容性

OpenMontage 兼容任何能读文件、能执行 Python 的 AI 编程助手。为以下平台内置了专属指令文件:

| 平台 | 配置文件 |
|----------|------------|
| **Claude Code** | `CLAUDE.md` |
| **Cursor** | `CURSOR.md` + `.cursor/rules/` |
| **GitHub Copilot** | `COPILOT.md` + `.github/copilot-instructions.md` |
| **Codex** | `CODEX.md` |
| **Windsurf** | `.windsurfrules` |

所有平台文件都指向共享的 `AGENT_GUIDE.md`(操作指南与 agent 契约)和 `PROJECT_CONTEXT.md`(架构参考)。

> **即将推出:** 经 **Ollama** 与 **LM Studio** 的本地 LLM 支持——无需任何云端 LLM 即可运行完整生产流水线。

---

## 参与贡献

OpenMontage 天生为扩展而建。最常见的两类贡献:

### 新增一个工具

1. 在合适的 `tools/` 子目录创建一个 Python 文件
2. 继承 `BaseTool` 并实现工具契约
3. 注册表会自动发现它——无需手动注册
4. 如果该工具需要用法指导,补一个技能文件

### 新增一条流水线

1. 在 `pipeline_defs/` 创建一个 YAML 清单
2. 在 `skills/pipelines/<你的流水线>/` 创建阶段导演技能
3. 复用已有工具——或按需新增

完整技术参考见 `docs/ARCHITECTURE.md`,完整服务商指南(配置、定价、免费额度)见 `docs/PROVIDERS.md`,agent 契约见 `AGENT_GUIDE.md`。

### 加入社区

我们用 [GitHub Discussions](https://github.com/calesthio/OpenMontage/discussions) 分享作品与想法:

- **[Show and Tell](https://github.com/calesthio/OpenMontage/discussions/categories/show-and-tell)** —— 分享你做的视频、好用的提示词,或你发现的创意工作流
- **[Ideas](https://github.com/calesthio/OpenMontage/discussions/categories/ideas)** —— 建议新的流水线、工具、风格 playbook 或集成
- **[Q&A](https://github.com/calesthio/OpenMontage/discussions/categories/q-a)** —— 就配置、流水线或排障提问

做了很酷的东西?发到 Show and Tell——我们很想看看你做了什么。

---

## 联系

获取更新、发布与幕后构建笔记,关注 [@calesthioailabs](https://x.com/calesthioailabs)。

报告 bug、提功能需求与讨论工作流,请用 [GitHub Issues](https://github.com/calesthio/OpenMontage/issues) 和 [GitHub Discussions](https://github.com/calesthio/OpenMontage/discussions),让一切都可见、可行动。

---

## 测试

```bash
# 跑契约测试(无需 API key)
make test-contracts

# 跑全部测试
make test
```

---

## 许可证

[GNU AGPLv3](LICENSE)

---

**OpenMontage** —— 生产级视频,带真正的质量强制,由你的 AI 助手编排。

如果这个项目对你有用,点个 star 对我们意义重大——它能帮更多人发现它。
