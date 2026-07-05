#!/usr/bin/env python3
"""Render v5 calm, Apple-inspired UI mockups for 赤灵AI运营工作台."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps


OUT_DIR = Path("docs/ui-mockups")
WIDTH = 1440
HEIGHT = 1024
REFERENCE_FRAME = Path("projects/reference-f64e5145/artifacts/reference-render/subtitle-qa/frame-08s.png")
PORTRAIT_IMAGE = Path("projects/reference-f64e5145/assets/images/49fdd40a2933df3a8fc710d79f78878a5de305e02b4ca1e4d28265a2517b11.png")

FONT_REGULAR = "/System/Library/Fonts/STHeiti Light.ttc"
FONT_MEDIUM = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_FALLBACK = "/Library/Fonts/Arial Unicode.ttf"


@dataclass(frozen=True)
class Palette:
    bg: str = "#F5F5F7"
    surface: str = "#FFFFFF"
    surface_2: str = "#FBFBFD"
    ink: str = "#1D1D1F"
    ink_2: str = "#343437"
    muted: str = "#6E6E73"
    muted_2: str = "#9A9AA0"
    line: str = "#E5E5EA"
    line_2: str = "#D8D8DF"
    red: str = "#D73532"
    red_soft: str = "#FFF0EF"
    blue: str = "#007AFF"
    blue_soft: str = "#EEF6FF"
    green: str = "#34C759"
    green_soft: str = "#ECFAF0"
    amber: str = "#FF9F0A"
    amber_soft: str = "#FFF7E8"
    graphite: str = "#2C2C2E"


P = Palette()


def font(size: int, medium: bool = False) -> ImageFont.FreeTypeFont:
    preferred = FONT_MEDIUM if medium else FONT_REGULAR
    path = preferred if Path(preferred).exists() else FONT_FALLBACK
    return ImageFont.truetype(path, size=size)


def hex_rgb(value: str) -> tuple[int, int, int]:
    clean = value.lstrip("#")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)


def text_size(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), value, font=face)
    return box[2] - box[0], box[3] - box[1]


def rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: str,
    outline: str | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def soft_shadow(
    image: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    blur: int = 22,
    alpha: int = 24,
    y_offset: int = 10,
) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    shifted = (box[0], box[1] + y_offset, box[2], box[3] + y_offset)
    draw.rounded_rectangle(shifted, radius=radius, fill=(0, 0, 0, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    image.alpha_composite(layer)


def panel(
    image: Image.Image,
    box: tuple[int, int, int, int],
    radius: int = 30,
    fill: str = P.surface,
    outline: str = P.line,
    shadow: bool = True,
) -> ImageDraw.ImageDraw:
    if shadow:
        soft_shadow(image, box, radius)
    draw = ImageDraw.Draw(image)
    rounded(draw, box, radius, fill, outline)
    return draw


def canvas() -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), hex_rgb(P.bg) + (255,))
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-160, -180, 520, 420), fill=(215, 53, 50, 26))
    glow_draw.ellipse((980, -120, 1640, 480), fill=(0, 122, 255, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(80))
    image.alpha_composite(glow)
    return image


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    fill: str,
    color: str,
    size: int = 14,
    padding_x: int = 13,
    padding_y: int = 7,
    outline: str | None = None,
) -> tuple[int, int, int, int]:
    face = font(size, medium=True)
    width, height = text_size(draw, value, face)
    box = (xy[0], xy[1], xy[0] + width + padding_x * 2, xy[1] + height + padding_y * 2)
    rounded(draw, box, (box[3] - box[1]) // 2, fill, outline)
    draw.text((xy[0] + padding_x, xy[1] + padding_y - 2), value, fill=color, font=face)
    return box


def button(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    value: str,
    primary: bool = True,
    loading: bool = False,
) -> None:
    fill = P.ink if primary else P.surface_2
    color = "#FFFFFF" if primary else P.ink
    outline = P.ink if primary else P.line
    rounded(draw, box, 19, fill, outline)
    face = font(16, medium=True)
    label = f"◌  {value}" if loading else value
    width, height = text_size(draw, label, face)
    draw.text(((box[0] + box[2] - width) // 2, (box[1] + box[3] - height) // 2 - 2), label, fill=color, font=face)


def nav(draw: ImageDraw.ImageDraw, active: str = "生产台") -> None:
    rounded(draw, (42, 32, WIDTH - 42, 98), 28, "#FFFFFF", P.line)
    draw.text((76, 53), "赤灵AI运营工作台", fill=P.ink, font=font(23, medium=True))
    draw.text((260, 59), "内容复刻 · 审核 · 交付", fill=P.muted, font=font(14))
    items = ["生产台", "作品", "素材库", "团队审核", "数据"]
    x_pos = 546
    for item in items:
        label_width = text_size(draw, item, font(15, medium=True))[0]
        if item == active:
            rounded(draw, (x_pos - 18, 48, x_pos + label_width + 18, 82), 17, P.ink, P.ink)
            draw.text((x_pos, 56), item, fill="#FFFFFF", font=font(15, medium=True))
        else:
            draw.text((x_pos, 56), item, fill=P.muted, font=font(15, medium=True))
        x_pos += label_width + 54
    button(draw, (WIDTH - 178, 46, WIDTH - 66, 84), "新建", True)


def screen_login() -> Image.Image:
    image = canvas()
    draw = ImageDraw.Draw(image)

    draw.text((76, 58), "赤灵AI运营工作台", fill=P.ink, font=font(24, medium=True))
    draw.text((260, 64), "内容复刻 · 审核 · 交付", fill=P.muted, font=font(14))
    pill(draw, (WIDTH - 236, 54), "企业内部使用", P.surface, P.ink, size=14, outline=P.line)

    panel(image, (82, 146, 734, 894), 42)
    panel(image, (782, 146, 1304, 894), 42, fill=P.surface_2)
    draw = ImageDraw.Draw(image)

    draw.text((138, 218), "欢迎回来", fill=P.ink, font=font(52, medium=True))
    draw.text((140, 286), "登录后继续处理作品、审核文案和下载交付包。", fill=P.muted, font=font(18))

    draw.text((140, 374), "账号", fill=P.ink, font=font(16, medium=True))
    rounded(draw, (140, 404, 602, 462), 18, P.surface_2, P.line)
    draw.text((164, 423), "手机号 / 企业邮箱", fill=P.muted_2, font=font(16))

    draw.text((140, 498), "密码", fill=P.ink, font=font(16, medium=True))
    rounded(draw, (140, 528, 602, 586), 18, P.surface_2, P.line)
    draw.text((164, 548), "请输入密码", fill=P.muted_2, font=font(16))
    draw.text((548, 548), "显示", fill=P.blue, font=font(14, medium=True))

    draw.ellipse((142, 626, 160, 644), outline=P.line_2, width=2)
    draw.text((174, 622), "保持登录状态", fill=P.muted, font=font(14))
    draw.text((492, 622), "忘记密码？", fill=P.blue, font=font(14, medium=True))

    button(draw, (140, 684, 602, 742), "登录工作台", True)
    button(draw, (140, 762, 602, 820), "验证码登录", False)

    rounded(draw, (140, 834, 602, 854), 10, P.line)
    draw.text((282, 870), "登录即代表已获得团队授权", fill=P.muted, font=font(13))

    draw.text((846, 218), "今天的工作会从这里开始", fill=P.ink, font=font(32, medium=True))
    draw.text((848, 266), "少打扰，强反馈；让运营人员知道下一步该做什么。", fill=P.muted, font=font(16))

    rounded(draw, (846, 344, 1244, 692), 32, P.surface, P.line)
    draw.text((886, 388), "当前工作台概览", fill=P.ink, font=font(24, medium=True))
    metric(draw, (886, 448, 1062, 546), "待审核", "3", "需确认", P.amber)
    metric(draw, (1084, 448, 1220, 546), "生产中", "2", "进行中", P.ink)
    rounded(draw, (886, 584, 1220, 642), 20, P.surface_2, P.line)
    draw.ellipse((914, 607, 926, 619), fill=P.green)
    draw.text((944, 596), "工程纠纷口播复刻", fill=P.ink, font=font(16, medium=True))
    draw.text((944, 620), "生成进度 64%，预计 6 分钟", fill=P.muted, font=font(13))

    rounded(draw, (846, 732, 1244, 816), 28, P.green_soft, "#CBEFD6")
    draw.text((886, 758), "安全提示", fill=P.green, font=font(20, medium=True))
    draw.text((886, 788), "内部素材和人物肖像仅限授权团队成员访问。", fill=P.muted, font=font(14))
    return image.convert("RGB")


def crop_round(path: Path, size: tuple[int, int], radius: int, center_y: float = 0.36) -> Image.Image:
    if path.is_file():
        source = Image.open(path).convert("RGB")
    else:
        source = placeholder_preview(size, "样例预览")
    fitted = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS, centering=(0.5, center_y))
    result = fitted.convert("RGBA")
    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    result.putalpha(mask)
    return result


def placeholder_preview(size: tuple[int, int], label: str) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, hex_rgb("#F1F1F4"))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        top = hex_rgb("#F8F8FA")
        bottom = hex_rgb("#FFD8D6")
        color = tuple(int(top[channel] * (1 - ratio) + bottom[channel] * ratio) for channel in range(3))
        draw.line((0, y, width, y), fill=color)
    draw.ellipse((width * 0.36, height * 0.16, width * 0.64, height * 0.34), fill="#FFBD8A")
    draw.rounded_rectangle(
        (width * 0.24, height * 0.37, width * 0.76, height * 0.70),
        radius=max(18, width // 6),
        fill=P.red,
    )
    draw.rounded_rectangle(
        (width * 0.14, height * 0.77, width * 0.86, height * 0.84),
        radius=12,
        fill=P.ink,
    )
    face = font(max(12, width // 12), medium=True)
    text_width, text_height = text_size(draw, label, face)
    draw.text(
        ((width - text_width) / 2, height * 0.79 - text_height / 2),
        label,
        fill="#FFFFFF",
        font=face,
    )
    return image


def phone_preview(
    image: Image.Image,
    box: tuple[int, int, int, int],
    path: Path,
    label: str,
    progress: int | None = None,
    center_y: float = 0.36,
) -> None:
    draw = ImageDraw.Draw(image)
    rounded(draw, box, 34, "#111113", "#2B2B30")
    screen_box = (box[0] + 18, box[1] + 20, box[2] - 18, box[3] - 56)
    preview = crop_round(path, (screen_box[2] - screen_box[0], screen_box[3] - screen_box[1]), 24, center_y)
    image.alpha_composite(preview, (screen_box[0], screen_box[1]))
    draw = ImageDraw.Draw(image)
    pill(draw, (box[0] + 34, box[3] - 88), label, "#111113", "#FFFFFF", size=12)
    if progress is not None:
        rounded(draw, (box[0] + 34, box[3] - 32, box[2] - 34, box[3] - 24), 4, "#3A3A3C")
        progress_width = int((box[2] - box[0] - 68) * progress / 100)
        rounded(draw, (box[0] + 34, box[3] - 32, box[0] + 34 + progress_width, box[3] - 24), 4, P.red)


def metric(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, value: str, helper: str, color: str) -> None:
    rounded(draw, box, 24, P.surface, P.line)
    draw.text((box[0] + 22, box[1] + 18), label, fill=P.muted, font=font(14))
    draw.text((box[0] + 22, box[1] + 46), value, fill=P.ink, font=font(34, medium=True))
    draw.text((box[0] + 76, box[1] + 58), helper, fill=P.muted, font=font(13))
    draw.ellipse((box[2] - 42, box[1] + 25, box[2] - 24, box[1] + 43), fill=color)


def progress_circle(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, percent: int) -> None:
    box = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    draw.arc(box, 0, 360, fill=P.line, width=12)
    draw.arc(box, -90, -90 + int(360 * percent / 100), fill=P.ink, width=12)
    draw.text((center[0] - 31, center[1] - 28), f"{percent}%", fill=P.ink, font=font(30, medium=True))
    draw.text((center[0] - 34, center[1] + 12), "处理中", fill=P.muted, font=font(14))


def stages(draw: ImageDraw.ImageDraw, x_pos: int, y_pos: int, active: int, compact: bool = False) -> None:
    data = [
        ("解析参考", "已完成"),
        ("整理文案", "已完成"),
        ("生成画面", "第 1/1 条 · 64%"),
        ("合成字幕", "等待画面完成"),
        ("质检交付", "预计 6 分钟"),
    ]
    gap = 54 if not compact else 47
    for index, (title, detail) in enumerate(data):
        y_item = y_pos + index * gap
        if index < active:
            fill = P.green
            mark = "✓"
        elif index == active:
            fill = P.ink
            mark = "•"
        else:
            fill = "#D1D1D6"
            mark = ""
        draw.ellipse((x_pos, y_item, x_pos + 24, y_item + 24), fill=fill)
        if mark:
            face = font(13, medium=True)
            width, height = text_size(draw, mark, face)
            draw.text((x_pos + 12 - width / 2, y_item + 12 - height / 2 - 1), mark, fill="#FFFFFF", font=face)
        if index < len(data) - 1:
            draw.line((x_pos + 12, y_item + 30, x_pos + 12, y_item + gap - 8), fill=P.line_2, width=2)
        draw.text((x_pos + 42, y_item - 1), title, fill=P.ink if index <= active else P.muted, font=font(16, medium=True))
        draw.text((x_pos + 42, y_item + 25), detail, fill=P.muted, font=font(13))


def screen_dashboard() -> Image.Image:
    image = canvas()
    draw = ImageDraw.Draw(image)
    nav(draw, "生产台")
    draw.text((72, 156), "今天要生产什么？", fill=P.ink, font=font(48, medium=True))
    draw.text((74, 218), "导入参考视频，确认文案和授权后，系统进入后台生产。", fill=P.muted, font=font(19))
    pill(draw, (74, 262), "安静反馈", P.surface, P.ink, size=14, outline=P.line)
    pill(draw, (166, 262), "不暴露内部模型", P.surface, P.ink, size=14, outline=P.line)

    panel(image, (72, 336, 748, 530), 34)
    draw = ImageDraw.Draw(image)
    draw.text((112, 374), "快速开始", fill=P.ink, font=font(28, medium=True))
    draw.text((112, 412), "粘贴视频链接或上传本地视频。", fill=P.muted, font=font(15))
    rounded(draw, (112, 458, 560, 508), 18, P.surface_2, P.line)
    draw.text((136, 474), "粘贴抖音 / 视频链接…", fill=P.muted_2, font=font(16))
    button(draw, (582, 458, 708, 508), "导入", True)

    metric(draw, (72, 574, 286, 688), "待审核", "3", "需确认", P.amber)
    metric(draw, (310, 574, 524, 688), "生产中", "2", "预计 12 分", P.ink)
    metric(draw, (548, 574, 748, 688), "已交付", "18", "本周完成", P.green)

    panel(image, (800, 148, 1296, 742), 36)
    draw = ImageDraw.Draw(image)
    draw.text((846, 192), "当前生产任务", fill=P.ink, font=font(28, medium=True))
    draw.text((846, 230), "工程纠纷口播复刻", fill=P.muted, font=font(16))
    progress_circle(draw, (1004, 356), 82, 64)
    stages(draw, 846, 490, active=2, compact=True)
    phone_preview(image, (1120, 438, 1260, 708), REFERENCE_FRAME, "预览", progress=64)

    panel(image, (72, 738, 1296, 922), 32)
    draw = ImageDraw.Draw(image)
    draw.text((112, 778), "最近作品", fill=P.ink, font=font(24, medium=True))
    rows = [
        ("工程纠纷口播复刻", "生产中 · 画面生成 64%，预计 6 分钟", P.ink),
        ("律师私域引流短片", "待审核 · 2 项授权需要确认", P.amber),
        ("本地生活探店模板", "已交付 · 成片与字幕可下载", P.green),
    ]
    x_pos = 112
    for title, detail, color in rows:
        rounded(draw, (x_pos, 832, x_pos + 358, 890), 20, P.surface_2, P.line)
        draw.ellipse((x_pos + 20, 855, x_pos + 32, 867), fill=color)
        draw.text((x_pos + 50, 844), title, fill=P.ink, font=font(16, medium=True))
        draw.text((x_pos + 50, 868), detail, fill=P.muted, font=font(13))
        x_pos += 388
    return image.convert("RGB")


def screen_create() -> Image.Image:
    image = canvas()
    draw = ImageDraw.Draw(image)
    nav(draw, "生产台")
    panel(image, (72, 138, 912, 916), 36)
    panel(image, (952, 138, 1308, 916), 36)
    draw = ImageDraw.Draw(image)

    draw.text((118, 188), "创建作品", fill=P.ink, font=font(40, medium=True))
    draw.text((118, 240), "三步完成设置：导入参考、设置生成、提交审核。", fill=P.muted, font=font(16))
    step_labels = ["1. 导入参考", "2. 设置生成", "3. 提交审核"]
    x_pos = 118
    for index, label in enumerate(step_labels):
        active = index == 0
        rounded(draw, (x_pos, 294, x_pos + 190, 342), 24, P.ink if active else P.surface_2, P.line)
        draw.text((x_pos + 26, 308), label, fill="#FFFFFF" if active else P.muted, font=font(15, medium=True))
        x_pos += 214

    draw.text((118, 402), "输入参考内容", fill=P.ink, font=font(27, medium=True))
    for box, title, sub, action, color in [
        ((118, 454, 496, 562), "参考视频", "粘贴链接，或上传本地视频", "选择文件", P.red),
        ((530, 454, 862, 562), "人物 / 品牌素材", "上传授权图片或从素材库选择", "素材库", P.amber),
    ]:
        rounded(draw, box, 24, P.surface_2, color)
        draw.ellipse((box[0] + 26, box[1] + 33, box[0] + 72, box[1] + 79), fill=color)
        draw.text((box[0] + 96, box[1] + 28), title, fill=P.ink, font=font(20, medium=True))
        draw.text((box[0] + 96, box[1] + 60), sub, fill=P.muted, font=font(13))
        draw.text((box[2] - 100, box[1] + 45), action, fill=color, font=font(14, medium=True))

    draw.text((118, 624), "生成设置", fill=P.ink, font=font(26, medium=True))
    settings = [
        ("成片时长", "15 秒内", "可手动缩短"),
        ("清晰度", "标准 480p / 高清 720p", "默认标准"),
        ("生成数量", "1 条", "单批最多 5 条"),
        ("字幕风格", "口播短句", "句尾无标点"),
    ]
    for index, (label, value, helper) in enumerate(settings):
        col = index % 2
        row = index // 2
        x = 118 + col * 390
        y = 674 + row * 92
        rounded(draw, (x, y, x + 356, y + 66), 20, P.surface_2, P.line)
        draw.text((x + 20, y + 15), label, fill=P.muted, font=font(13))
        draw.text((x + 132, y + 13), value, fill=P.ink, font=font(18, medium=True))
        draw.text((x + 132, y + 41), helper, fill=P.muted, font=font(12))
    button(draw, (666, 834, 862, 886), "查看方案", True)
    button(draw, (526, 834, 646, 886), "保存草稿", False)

    draw.text((994, 188), "实时预览", fill=P.ink, font=font(27, medium=True))
    draw.text((994, 226), "素材上传后预览裁切和字幕位置。", fill=P.muted, font=font(14))
    phone_preview(image, (1040, 288, 1222, 734), PORTRAIT_IMAGE, "肖像素材", center_y=0.38)
    pill(draw, (994, 794), "提交后进入人工审核", P.red_soft, P.red, size=13, outline="#FFD3D1")
    draw.text((994, 834), "审核通过前不会开始生产，避免误用素材。", fill=P.muted, font=font(14))
    return image.convert("RGB")


def screen_generating() -> Image.Image:
    image = canvas()
    draw = ImageDraw.Draw(image)
    nav(draw, "作品")
    panel(image, (72, 152, 806, 898), 36)
    panel(image, (856, 224, 1308, 898), 34)
    draw = ImageDraw.Draw(image)
    rounded(draw, (882, 128, 1308, 186), 24, P.green_soft, "#CFEFD7")
    draw.ellipse((916, 150, 934, 168), fill=P.green)
    draw.text((954, 145), "已提交，生产任务已进入队列", fill=P.ink, font=font(17, medium=True))
    draw.text((954, 168), "可以离开页面，完成后会在交付区提示。", fill=P.muted, font=font(12))

    draw.text((118, 206), "生成中", fill=P.ink, font=font(44, medium=True))
    draw.text((118, 262), "系统正在处理画面和字幕，请勿重复提交。", fill=P.muted, font=font(17))
    button(draw, (118, 322, 282, 374), "正在生产", True, loading=True)
    button(draw, (304, 322, 440, 374), "后台运行", False)
    progress_circle(draw, (432, 536), 134, 64)
    phone_preview(image, (616, 330, 770, 760), REFERENCE_FRAME, "实时预览", progress=64)
    draw.text((134, 738), "当前阶段", fill=P.muted, font=font(14))
    draw.text((134, 768), "正在生成第 1 条画面", fill=P.ink, font=font(25, medium=True))
    draw.text((134, 806), "预计还需 6 分钟，失败会自动重试一次。", fill=P.muted, font=font(15))

    draw.text((902, 274), "任务抽屉", fill=P.ink, font=font(28, medium=True))
    draw.text((902, 314), "用户随时知道现在进行到哪一步。", fill=P.muted, font=font(14))
    stages(draw, 906, 374, active=2)
    rounded(draw, (902, 700, 1268, 790), 24, P.surface_2, P.line)
    draw.text((932, 728), "为什么显示这些？", fill=P.ink, font=font(18, medium=True))
    draw.text((932, 758), "减少重复提交，也让等待变得确定。", fill=P.muted, font=font(14))
    button(draw, (1090, 824, 1268, 874), "查看后台任务", False)
    return image.convert("RGB")


def check_row(draw: ImageDraw.ImageDraw, x: int, y: int, title: str, state: str, color: str, ok: bool = True) -> None:
    draw.ellipse((x, y, x + 26, y + 26), fill=color)
    if ok:
        draw.line((x + 7, y + 14, x + 12, y + 19), fill="#FFFFFF", width=3)
        draw.line((x + 12, y + 19, x + 20, y + 8), fill="#FFFFFF", width=3)
    else:
        draw.line((x + 13, y + 7, x + 13, y + 16), fill="#FFFFFF", width=3)
        draw.ellipse((x + 11, y + 20, x + 15, y + 24), fill="#FFFFFF")
    draw.text((x + 46, y + 1), title, fill=P.ink, font=font(17, medium=True))
    draw.text((x + 248, y + 2), state, fill=color, font=font(14, medium=True))


def screen_review() -> Image.Image:
    image = canvas()
    draw = ImageDraw.Draw(image)
    nav(draw, "团队审核")
    panel(image, (72, 146, 1308, 906), 36)
    draw = ImageDraw.Draw(image)
    draw.text((118, 198), "人工审核", fill=P.ink, font=font(42, medium=True))
    pill(draw, (304, 204), "待人工确认", P.amber_soft, P.amber, size=13, outline="#FFE1A8")
    button(draw, (1150, 196, 1260, 240), "批量生产", True)

    phone_preview(image, (118, 304, 346, 786), REFERENCE_FRAME, "参考视频")
    rounded(draw, (386, 304, 782, 786), 30, P.surface_2, P.line)
    draw.text((428, 350), "文案与字幕", fill=P.ink, font=font(25, medium=True))
    draw.text((428, 386), "可直接编辑，保存后再进入生产。", fill=P.muted, font=font(14))
    rounded(draw, (428, 432, 742, 592), 24, P.surface, P.line)
    script_lines = ["在这些案子上面", "我积累了充足的实战经验", "如果你身边刚好缺一位靠谱律师朋友", "不妨留个关注"]
    line_y = 460
    for line in script_lines:
        draw.text((458, line_y), line, fill=P.ink, font=font(18))
        line_y += 32
    draw.line((458, 570, 650, 570), fill=P.red, width=2)
    pill(draw, (428, 630), "短句显示", P.blue_soft, P.blue, size=13, outline="#CDE5FF")
    pill(draw, (532, 630), "句尾无标点", P.green_soft, P.green, size=13, outline="#CBEFD6")
    button(draw, (428, 714, 570, 764), "保存修改", False)

    rounded(draw, (824, 264, 1274, 826), 30, P.surface_2, P.line)
    draw.text((866, 310), "审核详情侧栏", fill=P.ink, font=font(27, medium=True))
    draw.text((866, 350), "从列表滑出，不打断主页面。", fill=P.muted, font=font(14))
    check_row(draw, 866, 408, "素材授权", "已确认", P.green)
    check_row(draw, 866, 462, "肖像授权", "已确认", P.green)
    check_row(draw, 866, 516, "字幕规则", "已确认", P.green)
    check_row(draw, 866, 570, "画面方向", "需确认", P.amber, ok=False)
    rounded(draw, (866, 666, 1234, 746), 22, P.surface, P.line)
    draw.text((894, 690), "审核意见", fill=P.ink, font=font(17, medium=True))
    draw.text((894, 718), "确认肖像授权后再进入生产。", fill=P.muted, font=font(14))
    button(draw, (866, 768, 1014, 814), "退回修改", False)
    button(draw, (1034, 768, 1234, 814), "确认并生成", True)
    return image.convert("RGB")


def screen_delivery() -> Image.Image:
    image = canvas()
    draw = ImageDraw.Draw(image)
    nav(draw, "作品")
    panel(image, (72, 146, 1308, 906), 36)
    draw = ImageDraw.Draw(image)
    draw.text((118, 198), "成品交付", fill=P.ink, font=font(42, medium=True))
    pill(draw, (300, 204), "已完成", P.green_soft, P.green, size=13, outline="#CBEFD6")
    draw.text((118, 250), "交付包包含成片、字幕文件和审核记录，可直接归档。", fill=P.muted, font=font(16))
    phone_preview(image, (118, 328, 382, 812), REFERENCE_FRAME, "最终成片", progress=100)
    rounded(draw, (448, 328, 1268, 812), 32, P.surface_2, P.line)
    draw.text((492, 376), "下载与归档", fill=P.ink, font=font(28, medium=True))
    items = [
        ("成片文件", "可直接发布", "下载视频", P.red),
        ("字幕文件", "可二次校对", "下载字幕", P.blue),
        ("审核记录", "留存流程证据", "查看记录", P.amber),
    ]
    y = 442
    for title, detail, action, color in items:
        rounded(draw, (492, y, 1208, y + 78), 22, P.surface, P.line)
        draw.ellipse((524, y + 27, 550, y + 53), fill=color)
        draw.text((574, y + 18), title, fill=P.ink, font=font(18, medium=True))
        draw.text((574, y + 47), detail, fill=P.muted, font=font(13))
        draw.text((1088, y + 29), action, fill=color, font=font(15, medium=True))
        y += 102
    button(draw, (492, 736, 690, 788), "下载交付包", True)
    button(draw, (720, 736, 914, 788), "复制分享路径", False)
    rounded(draw, (944, 716, 1208, 788), 22, P.green_soft, "#CBEFD6")
    draw.text((974, 737), "发布前提醒", fill=P.green, font=font(18, medium=True))
    draw.text((974, 765), "再次确认人物授权和平台规范。", fill=P.muted, font=font(13))
    return image.convert("RGB")


def screen_flow_board(paths: dict[str, Path]) -> Image.Image:
    board = Image.new("RGBA", (1920, 1280), hex_rgb(P.bg) + (255,))
    glow = Image.new("RGBA", board.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((-200, -220, 640, 520), fill=(215, 53, 50, 24))
    glow_draw.ellipse((1280, -220, 2140, 520), fill=(0, 122, 255, 18))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    board.alpha_composite(glow)
    draw = ImageDraw.Draw(board)
    draw.text((88, 72), "赤灵AI运营工作台 · v5 简约产品设计", fill=P.ink, font=font(44, medium=True))
    draw.text((88, 132), "苹果式克制：浅色系统、强留白、少装饰、清楚反馈，适合长时间运营使用。", fill=P.muted, font=font(22))
    pill(draw, (1470, 88), "耐看", P.surface, P.ink, size=16, outline=P.line)
    pill(draw, (1560, 88), "低审美疲劳", P.surface, P.ink, size=16, outline=P.line)

    placements = [
        ("生产台", paths["dashboard"], (88, 210)),
        ("创建作品", paths["create"], (1016, 210)),
        ("生成中反馈", paths["generating"], (88, 748)),
        ("人工审核", paths["review"], (1016, 748)),
    ]
    for title, path, origin in placements:
        source = Image.open(path).convert("RGB").resize((760, 512), Image.Resampling.LANCZOS)
        x, y = origin
        soft_shadow(board, (x, y, x + 760, y + 512), 28, blur=26, alpha=30, y_offset=14)
        mask = Image.new("L", source.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, source.size[0], source.size[1]), radius=28, fill=255)
        source_rgba = source.convert("RGBA")
        source_rgba.putalpha(mask)
        board.alpha_composite(source_rgba, origin)
        draw = ImageDraw.Draw(board)
        draw.rounded_rectangle((x, y, x + 760, y + 512), radius=28, outline=P.line_2, width=1)
        draw.text((x, y - 44), title, fill=P.ink, font=font(25, medium=True))
    draw.line((874, 466, 998, 466), fill=P.ink, width=3)
    draw.polygon([(998, 466), (978, 456), (978, 476)], fill=P.ink)
    draw.line((874, 1004, 998, 1004), fill=P.ink, width=3)
    draw.polygon([(998, 1004), (978, 994), (978, 1014)], fill=P.ink)
    draw.text((888, 424), "导入设置", fill=P.ink, font=font(16, medium=True))
    draw.text((888, 962), "确认生成", fill=P.ink, font=font(16, medium=True))
    return board.convert("RGB")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "login": OUT_DIR / "chiling-product-v5-login.png",
        "dashboard": OUT_DIR / "chiling-product-v5-dashboard.png",
        "create": OUT_DIR / "chiling-product-v5-create.png",
        "generating": OUT_DIR / "chiling-product-v5-generating-feedback.png",
        "review": OUT_DIR / "chiling-product-v5-review.png",
        "delivery": OUT_DIR / "chiling-product-v5-delivery.png",
    }
    screen_login().save(paths["login"])
    screen_dashboard().save(paths["dashboard"])
    screen_create().save(paths["create"])
    screen_generating().save(paths["generating"])
    screen_review().save(paths["review"])
    screen_delivery().save(paths["delivery"])
    board_path = OUT_DIR / "chiling-product-v5-flow-board.png"
    screen_flow_board(paths).save(board_path)
    for path in [board_path, *paths.values()]:
        print(path)


if __name__ == "__main__":
    main()
