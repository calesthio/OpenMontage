# Seedance 产品场景工作流

这是一个面向非技术用户的产品素材工作流。你只需要准备一张产品图，在 Codex
对话中按提示做选择，系统会生成场景图、产品视频、营销文案和配乐。

## 第一次使用

配置火山方舟 ARK API Key：

```bash
python3 ~/.codex/skills/seedance-product-scene/scripts/seedance_client.py init
```

配置保存在 `~/.seedance/config.json`。OpenMontage 会直接读取它，不需要把 Key
粘贴到仓库。也可以使用 `ARK_API_KEY` 环境变量，或通过
`SEEDANCE_CONFIG_PATH` 指定另一份配置文件。

检查配置：

```bash
python -c 'from lib.seedance_config import load_seedance_config, mask_api_key; c=load_seedance_config(); print(mask_api_key(c.api_key), c.image_model, c.video_model)'
```

## 开始制作

在 Codex 中打开 OpenMontage，然后说：

```text
我想用这个产品图做多风格营销素材。产品叫「清透精华液」，
已知卖点只有：轻盈质地、适合日常护肤、包装简洁。
目标平台是小红书，不要编造材料或功效。
```

然后上传产品图。系统会依次询问：

1. 产品图、产品名和已确认卖点是否完整。
2. 是否生成 4 张风格预览：轻奢、自然、科技、办公。
3. 你希望完整制作哪 1–3 种风格。
4. 三段式分镜、8 秒、9:16 和文案方向是否确认。
5. 每种风格的 3 张场景图中选哪一张。
6. 每条 8 秒视频是否满意。
7. 三种文案是否保留或修改。
8. 三种免版权音乐候选中选择哪一首。
9. 最终交付清单是否确认。

每一步都会停下等你审批，不会因为一句“继续”自动跨越后续创作门。

## 产出

```text
projects/<project-id>/
├── assets/input/product.png
├── assets/images/previews/<style>/
├── assets/images/<style>/
├── assets/video/<style>/
├── assets/music/<style>/
├── artifacts/product_copy.json
├── artifacts/product_delivery.json
├── decision_log.json
└── renders/<style>/final.mp4
```

种子图片使用 `doubao-seedream-5-0-pro-260628`。视频使用
`doubao-seedance-2-5-260628`。文案由当前 Codex 会话生成，不使用火山文本模型。

## 成本

- 先生成 4 张预览，不直接批量生成所有视频。
- 完整风格默认包含 3 张图、1 条视频、3 套文案和 1 首音乐。
- 未知价格会显示“需要报价”，不会显示成免费。
- 重新生成会增加成本；第三次以上需要先说明具体调整方向。

## 常见问题

### 图片主体变了

不要继续生成视频。选择“重新生成”或“调细节”，并在提示中强调包装、比例、
颜色和文字保持不变。

### 视频任务超时

保留任务 ID。先在 OpenMontage 项目记录中查询原任务，不要重复提交付费任务。

### 音乐搜索失败

Pixabay 搜索是实验性网页接口。系统会停止并给出重试、用户上传或暂不加音乐等选项。

### 401 / 403 / 429

- 401：检查 ARK Key 是否完整、是否过期。
- 403：确认 Seedream/Seedance 模型已开通。
- 429：等待、检查额度或充值。

任何错误信息都不会打印完整 API Key。
