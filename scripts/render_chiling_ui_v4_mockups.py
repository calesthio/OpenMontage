#!/usr/bin/env python3
"""Render v4 high-fidelity mockups for 赤灵AI运营工作台."""

from __future__ import annotations

import math
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
class V4Palette:
    night: str = "#070912"
    night_2: str = "#0D111E"
    panel: str = "#121826"
    panel_2: str = "#171F31"
    panel_light: str = "#F8F1E9"
    text: str = "#F6F0EA"
    text_dark: str = "#111827"
    muted: str = "#8B95A8"
    muted_light: str = "#B6BECF"
    line: str = "#2A3348"
    line_light: str = "#E8DDD2"
    red: str = "#E63B3F"
    red_hot: str = "#FF4B45"
    red_dark: str = "#9F161D"
    gold: str = "#F0B35B"
    green: str = "#35D28D"
    blue: str = "#5AA7FF"
    violet: str = "#8C6CFF"
    cream: str = "#FFF5EA"


P = V4Palette()


def font(size: int, medium: bool = False) -> ImageFont.FreeTypeFont:
    preferred = FONT_MEDIUM if medium else FONT_REGULAR
    path = preferred if Path(preferred).exists() else FONT_FALLBACK
    return ImageFont.truetype(path, size=size)


def hex_rgb(value: str) -> tuple[int, int, int]:
    clean = value.lstrip("#")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)


def rgba(value: str, alpha: int) -> tuple[int, int, int, int]:
    return (*hex_rgb(value), alpha)


def text_size(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), value, font=face)
    return box[2] - box[0], box[3] - box[1]


def rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    radius: int,
    fill: str | tuple[int, int, int, int],
    outline: str | tuple[int, int, int, int] | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_glow(image: Image.Image, center: tuple[int, int], radius: int, color: str, alpha: int) -> None:
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    x_pos, y_pos = center
    layer_draw.ellipse((x_pos - radius, y_pos - radius, x_pos + radius, y_pos + radius), fill=rgba(color, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(radius // 2))
    image.alpha_composite(layer)


def base_canvas() -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), hex_rgb(P.night) + (255,))
    pixels = image.load()
    top = hex_rgb("#070912")
    bottom = hex_rgb("#17101A")
    for y_pos in range(HEIGHT):
        ratio = y_pos / HEIGHT
        row_color = tuple(int(top[channel] * (1 - ratio) + bottom[channel] * ratio) for channel in range(3))
        for x_pos in range(WIDTH):
            pixels[x_pos, y_pos] = (*row_color, 255)
    draw_glow(image, (214, 90), 280, P.red, 72)
    draw_glow(image, (1180, 190), 320, P.violet, 42)
    draw_glow(image, (1080, 920), 420, P.red_dark, 52)
    draw = ImageDraw.Draw(image)
    for x_pos in range(0, WIDTH, 64):
        draw.line((x_pos, 0, x_pos, HEIGHT), fill=rgba("#FFFFFF", 10), width=1)
    for y_pos in range(0, HEIGHT, 64):
        draw.line((0, y_pos, WIDTH, y_pos), fill=rgba("#FFFFFF", 8), width=1)
    return image


def glass_panel(
    image: Image.Image,
    box: tuple[int, int, int, int],
    radius: int = 28,
    fill: str = P.panel,
    alpha: int = 184,
    outline_alpha: int = 46,
    shadow_alpha: int = 64,
) -> ImageDraw.ImageDraw:
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rounded_rectangle((box[0], box[1] + 18, box[2], box[3] + 18), radius=radius, fill=(0, 0, 0, shadow_alpha))
    shadow = shadow.filter(ImageFilter.GaussianBlur(24))
    image.alpha_composite(shadow)
    draw = ImageDraw.Draw(image)
    rounded(draw, box, radius, rgba(fill, alpha), rgba("#FFFFFF", outline_alpha), 1)
    draw.line((box[0] + radius, box[1] + 1, box[2] - radius, box[1] + 1), fill=rgba("#FFFFFF", 32), width=1)
    return draw


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fill: str,
    color: str = P.text,
    size: int = 14,
    padding_x: int = 14,
    padding_y: int = 7,
    outline: str | None = None,
) -> tuple[int, int, int, int]:
    face = font(size, medium=True)
    width, height = text_size(draw, text, face)
    box = (xy[0], xy[1], xy[0] + width + padding_x * 2, xy[1] + height + padding_y * 2)
    rounded(draw, box, (box[3] - box[1]) // 2, fill, outline)
    draw.text((xy[0] + padding_x, xy[1] + padding_y - 2), text, fill=color, font=face)
    return box


def button(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    primary: bool = True,
    loading: bool = False,
) -> None:
    if primary:
        fill = P.red
        outline = P.red_hot
        color = "#FFFFFF"
    else:
        fill = "#1A2233"
        outline = "#3A455B"
        color = P.text
    rounded(draw, box, 18, fill, outline, 1)
    face = font(17, medium=True)
    label = f"⟳  {text}" if loading else text
    width, height = text_size(draw, label, face)
    draw.text(((box[0] + box[2] - width) // 2, (box[1] + box[3] - height) // 2 - 2), label, fill=color, font=face)


def draw_nav(draw: ImageDraw.ImageDraw, active: str = "生产台") -> None:
    rounded(draw, (34, 34, WIDTH - 34, 108), 28, rgba("#0B101C", 232), rgba("#FFFFFF", 32))
    draw.ellipse((70, 58, 96, 84), fill=P.red)
    draw.text((108, 56), "赤灵AI运营工作台", fill=P.text, font=font(24, medium=True))
    draw.text((292, 63), "内容复刻 · 批量生产 · 审核交付", fill=P.muted_light, font=font(14))
    nav_items = ["生产台", "作品", "素材库", "团队审核", "数据"]
    nav_x = 540
    for item in nav_items:
        label_width = text_size(draw, item, font(15, medium=True))[0]
        if item == active:
            rounded(draw, (nav_x - 18, 55, nav_x + label_width + 18, 88), 16, P.cream, rgba("#FFFFFF", 26))
            draw.ellipse((nav_x - 8, 68, nav_x, 76), fill=P.red_hot)
        draw.text((nav_x, 62), item, fill=P.red_dark if item == active else P.muted_light, font=font(15, medium=True))
        nav_x += label_width + 54
    button(draw, (WIDTH - 188, 54, WIDTH - 60, 92), "新建作品", True)


def crop_round(path: Path, size: tuple[int, int], radius: int) -> Image.Image:
    if path.is_file():
        source = Image.open(path).convert("RGB")
    else:
        source = placeholder_preview(size, "样例预览")
    fitted = ImageOps.fit(source, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.35))
    rounded_image = fitted.convert("RGBA")
    mask = Image.new("L", size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    rounded_image.putalpha(mask)
    return rounded_image


def placeholder_preview(size: tuple[int, int], label: str) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, hex_rgb("#20283A"))
    draw = ImageDraw.Draw(image)
    for y_pos in range(height):
        ratio = y_pos / max(height - 1, 1)
        top = hex_rgb("#232C42")
        bottom = hex_rgb("#4B1822")
        color = tuple(int(top[channel] * (1 - ratio) + bottom[channel] * ratio) for channel in range(3))
        draw.line((0, y_pos, width, y_pos), fill=color)
    draw.ellipse((width * 0.36, height * 0.16, width * 0.64, height * 0.34), fill="#F0B35B")
    draw.rounded_rectangle(
        (width * 0.24, height * 0.37, width * 0.76, height * 0.70),
        radius=max(18, width // 6),
        fill="#E63B3F",
    )
    draw.rounded_rectangle(
        (width * 0.14, height * 0.77, width * 0.86, height * 0.84),
        radius=12,
        fill=(8, 11, 18),
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


def draw_phone(image: Image.Image, box: tuple[int, int, int, int], image_path: Path, caption: str, progress: int | None = None) -> None:
    draw = ImageDraw.Draw(image)
    rounded(draw, box, 34, "#080B12", rgba("#FFFFFF", 32), 1)
    screen_box = (box[0] + 22, box[1] + 24, box[2] - 22, box[3] - 52)
    preview = crop_round(image_path, (screen_box[2] - screen_box[0], screen_box[3] - screen_box[1]), 24)
    image.alpha_composite(preview, (screen_box[0], screen_box[1]))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(screen_box, radius=24, fill=(0, 0, 0, 42))
    image.alpha_composite(overlay)
    draw = ImageDraw.Draw(image)
    pill(draw, (box[0] + 42, box[3] - 82), caption, rgba("#000000", 172), "#FFFFFF", size=13)
    if progress is not None:
        bar_box = (box[0] + 36, box[3] - 34, box[2] - 36, box[3] - 24)
        rounded(draw, bar_box, 5, rgba("#FFFFFF", 28))
        fill_box = (bar_box[0], bar_box[1], bar_box[0] + int((bar_box[2] - bar_box[0]) * progress / 100), bar_box[3])
        rounded(draw, fill_box, 5, P.red_hot)


def draw_metric(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, value: str, note: str, color: str) -> None:
    rounded(draw, box, 24, "#151C2B", "#2B354A")
    draw.text((box[0] + 22, box[1] + 18), label, fill=P.muted_light, font=font(14))
    draw.text((box[0] + 22, box[1] + 46), value, fill=P.text, font=font(34, medium=True))
    draw.text((box[0] + 85, box[1] + 57), note, fill=P.muted, font=font(13))
    draw.ellipse((box[2] - 44, box[1] + 24, box[2] - 22, box[1] + 46), fill=color)


def draw_progress_ring(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, percent: int, color: str) -> None:
    box = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    draw.arc(box, start=0, end=360, fill=rgba("#FFFFFF", 38), width=12)
    draw.arc(box, start=-90, end=-90 + int(360 * percent / 100), fill=color, width=12)
    draw.text((center[0] - 32, center[1] - 26), f"{percent}%", fill=P.text, font=font(30, medium=True))
    draw.text((center[0] - 36, center[1] + 14), "处理中", fill=P.muted_light, font=font(14))


def draw_stage_list(
    draw: ImageDraw.ImageDraw,
    x_pos: int,
    y_pos: int,
    stages: list[tuple[str, str]],
    active_index: int,
    compact: bool = False,
) -> None:
    gap = 58 if not compact else 48
    for index, (title, detail) in enumerate(stages):
        y_item = y_pos + index * gap
        if index < active_index:
            fill = P.green
            mark = "✓"
            text_color = P.text
        elif index == active_index:
            fill = P.red_hot
            mark = "•"
            text_color = P.text
        else:
            fill = rgba("#FFFFFF", 34)
            mark = ""
            text_color = P.muted_light
        draw.ellipse((x_pos, y_item, x_pos + 24, y_item + 24), fill=fill)
        if mark:
            mark_width, mark_height = text_size(draw, mark, font(14, medium=True))
            draw.text((x_pos + 12 - mark_width / 2, y_item + 12 - mark_height / 2 - 1), mark, fill="#FFFFFF", font=font(14, medium=True))
        if index < len(stages) - 1:
            draw.line((x_pos + 12, y_item + 29, x_pos + 12, y_item + gap - 8), fill=rgba("#FFFFFF", 26), width=2)
        draw.text((x_pos + 42, y_item - 1), title, fill=text_color, font=font(16, medium=True))
        draw.text((x_pos + 42, y_item + 25), detail, fill=P.muted, font=font(13))


def screen_command_center() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image)
    draw_nav(draw, "生产台")

    draw.text((72, 164), "内容生产驾驶舱", fill=P.text, font=font(48, medium=True))
    draw.text((74, 224), "从参考视频到成片交付，所有状态都清楚可见。", fill=P.muted_light, font=font(19))
    pill(draw, (74, 266), "内部技术名已隐藏", "#102A22", P.green, size=14, outline=P.green)
    pill(draw, (226, 266), "生成过程实时反馈", "#2A151A", P.red_hot, size=14, outline=P.red_hot)

    glass_panel(image, (72, 332, 770, 548), 34, P.panel, 178)
    draw = ImageDraw.Draw(image)
    draw.text((112, 370), "快速开始", fill=P.text, font=font(28, medium=True))
    draw.text((112, 408), "粘贴视频链接或上传本地视频，下一步进入人工审核。", fill=P.muted_light, font=font(15))
    rounded(draw, (112, 454, 594, 510), 18, rgba("#FFFFFF", 18), rgba("#FFFFFF", 42))
    draw.text((138, 472), "粘贴抖音 / 视频链接…", fill=P.muted, font=font(17))
    button(draw, (612, 454, 732, 510), "导入", True)

    draw_metric(draw, (72, 588, 286, 706), "待审核", "3", "需确认", P.gold)
    draw_metric(draw, (310, 588, 524, 706), "生产中", "2", "预计 12 分", P.red_hot)
    draw_metric(draw, (548, 588, 770, 706), "已交付", "18", "本周完成", P.green)

    glass_panel(image, (824, 150, 1282, 776), 38, P.panel, 164)
    draw = ImageDraw.Draw(image)
    draw.text((868, 190), "当前生产任务", fill=P.text, font=font(28, medium=True))
    draw.text((868, 229), "工程纠纷口播复刻", fill=P.muted_light, font=font(16))
    draw_progress_ring(draw, (1052, 340), 84, 64, P.red_hot)
    draw_stage_list(
        draw,
        878,
        470,
        [
            ("解析参考", "已识别画面节奏与文案"),
            ("整理文案", "已生成可编辑口播稿"),
            ("生成画面", "正在生产第 1 条"),
            ("合成字幕", "等待画面完成"),
            ("质检交付", "预计 6 分钟后完成"),
        ],
        active_index=2,
    )
    draw_phone(image, (1092, 438, 1244, 744), REFERENCE_FRAME, "预览帧", progress=64)

    glass_panel(image, (72, 752, 1282, 934), 30, P.panel, 150)
    draw = ImageDraw.Draw(image)
    draw.text((112, 790), "最近作品", fill=P.text, font=font(24, medium=True))
    rows = [
        ("工程纠纷口播复刻", "生产中", "画面生成 64%，预计 6 分钟", P.red_hot),
        ("律师私域引流短片", "待审核", "2 项授权需要确认", P.gold),
        ("本地生活探店模板", "已交付", "成片与字幕可下载", P.green),
    ]
    row_x = 112
    for title, status, detail, color in rows:
        rounded(draw, (row_x, 832, row_x + 360, 900), 22, "#151C2B", "#2B354A")
        draw.ellipse((row_x + 22, 858, row_x + 34, 870), fill=color)
        draw.text((row_x + 50, 847), title, fill=P.text, font=font(17, medium=True))
        draw.text((row_x + 50, 874), f"{status} · {detail}", fill=P.muted_light, font=font(13))
        row_x += 388
    return image.convert("RGB")


def screen_create() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image)
    draw_nav(draw, "生产台")

    glass_panel(image, (72, 142, 928, 912), 38, P.panel, 176)
    draw = ImageDraw.Draw(image)
    draw.text((118, 188), "创建作品", fill=P.text, font=font(38, medium=True))
    draw.text((118, 238), "三步完成设置：导入参考、设置生成、提交审核。", fill=P.muted_light, font=font(17))
    step_labels = ["导入参考", "设置生成", "提交审核"]
    step_x = 120
    for index, label in enumerate(step_labels):
        active = index == 0
        fill = P.red if active else "#1A2233"
        rounded(draw, (step_x, 292, step_x + 186, 340), 24, fill, "#3A455B")
        draw.text((step_x + 24, 306), f"{index + 1}. {label}", fill=P.text if active else P.muted_light, font=font(16, medium=True))
        step_x += 208

    draw.text((118, 394), "输入参考内容", fill=P.text, font=font(28, medium=True))
    panels = [
        ((118, 444, 500, 560), "参考视频", "粘贴链接，或上传本地视频", "选择文件", P.red_hot),
        ((526, 444, 878, 560), "人物 / 品牌素材", "上传授权图片或从素材库选择", "素材库", P.gold),
    ]
    for box, title, subtitle, action, color in panels:
        rounded(draw, box, 26, "#151C2B", color, 1)
        draw.ellipse((box[0] + 26, box[1] + 34, box[0] + 74, box[1] + 82), fill=rgba(color, 52), outline=rgba(color, 128))
        draw.text((box[0] + 98, box[1] + 30), title, fill=P.text, font=font(21, medium=True))
        draw.text((box[0] + 98, box[1] + 64), subtitle, fill=P.muted_light, font=font(14))
        draw.text((box[2] - 102, box[1] + 47), action, fill=color, font=font(15, medium=True))

    draw.text((118, 622), "生成设置", fill=P.text, font=font(26, medium=True))
    settings = [
        ("成片时长", "15 秒内", "可手动缩短"),
        ("清晰度", "标准 480p / 高清 720p", "默认标准"),
        ("生成数量", "1 条", "单批最多 5 条"),
        ("字幕风格", "口播短句", "句尾无标点"),
    ]
    for index, (label, value, helper) in enumerate(settings):
        col = index % 2
        row = index // 2
        x_pos = 118 + col * 390
        y_pos = 672 + row * 102
        rounded(draw, (x_pos, y_pos, x_pos + 360, y_pos + 72), 22, "#151C2B", "#2B354A")
        draw.text((x_pos + 22, y_pos + 16), label, fill=P.muted_light, font=font(14))
        draw.text((x_pos + 132, y_pos + 14), value, fill=P.text, font=font(19, medium=True))
        draw.text((x_pos + 132, y_pos + 44), helper, fill=P.muted, font=font(12))

    button(draw, (678, 826, 878, 880), "查看方案", True)
    button(draw, (532, 826, 656, 880), "保存草稿", False)

    glass_panel(image, (972, 142, 1328, 912), 38, P.panel, 156)
    draw = ImageDraw.Draw(image)
    draw.text((1012, 188), "实时预览", fill=P.text, font=font(27, medium=True))
    draw.text((1012, 226), "素材上传后会在这里预览裁切和字幕位置。", fill=P.muted_light, font=font(14))
    draw_phone(image, (1050, 282, 1248, 736), PORTRAIT_IMAGE, "肖像素材", progress=None)
    pill(draw, (1012, 786), "提交后进入人工审核", "#2A151A", P.red_hot, size=14, outline=P.red_hot)
    draw.text((1012, 828), "审核通过前不会开始生产，避免误用素材。", fill=P.muted_light, font=font(14))
    return image.convert("RGB")


def screen_generating() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image)
    draw_nav(draw, "作品")

    rounded(draw, (890, 124, 1328, 186), 24, rgba(P.green, 28), rgba(P.green, 80))
    draw.ellipse((922, 146, 940, 164), fill=P.green)
    draw.text((956, 143), "已提交，生产任务已进入队列", fill=P.text, font=font(17, medium=True))
    draw.text((956, 166), "可离开页面，完成后会在交付区提示。", fill=P.muted_light, font=font(12))

    glass_panel(image, (72, 150, 830, 900), 38, P.panel, 172)
    draw = ImageDraw.Draw(image)
    draw.text((118, 200), "生成中", fill=P.text, font=font(45, medium=True))
    draw.text((118, 258), "系统正在处理画面和字幕，请勿重复提交。", fill=P.muted_light, font=font(18))
    button(draw, (118, 316, 292, 368), "正在生产", True, loading=True)
    button(draw, (314, 316, 460, 368), "后台运行", False)
    draw_progress_ring(draw, (470, 526), 144, 64, P.red_hot)
    for ring_index in range(3):
        ring_radius = 176 + ring_index * 24
        draw.arc((470 - ring_radius, 526 - ring_radius, 470 + ring_radius, 526 + ring_radius), 210, 330, fill=rgba(P.red_hot, 34 - ring_index * 8), width=2)
    draw.text((150, 724), "当前阶段", fill=P.muted_light, font=font(15))
    draw.text((150, 754), "正在生成第 1 条画面", fill=P.text, font=font(26, medium=True))
    draw.text((150, 792), "预计还需 6 分钟，失败会自动重试一次。", fill=P.muted_light, font=font(16))
    draw_phone(image, (628, 314, 790, 756), REFERENCE_FRAME, "实时预览", progress=64)

    glass_panel(image, (876, 214, 1328, 900), 34, P.panel, 168)
    draw = ImageDraw.Draw(image)
    draw.text((918, 260), "任务抽屉", fill=P.text, font=font(28, medium=True))
    draw.text((918, 300), "用户随时知道现在卡在哪一步。", fill=P.muted_light, font=font(15))
    draw_stage_list(
        draw,
        922,
        360,
        [
            ("解析参考", "已完成，节奏和镜头已整理"),
            ("整理文案", "已完成，字幕规则已应用"),
            ("生成画面", "第 1/1 条，64%"),
            ("合成字幕", "等待画面完成"),
            ("质检交付", "预计 6 分钟"),
        ],
        active_index=2,
    )
    rounded(draw, (918, 690, 1288, 806), 24, rgba(P.red, 22), rgba(P.red, 72))
    draw.text((950, 724), "为什么要显示这些？", fill=P.text, font=font(19, medium=True))
    draw.text((950, 758), "避免用户误以为按钮无效，同时减少重复提交。", fill=P.muted_light, font=font(14))
    button(draw, (1088, 828, 1288, 878), "查看后台任务", False)
    return image.convert("RGB")


def screen_review() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image)
    draw_nav(draw, "团队审核")

    glass_panel(image, (72, 142, 1328, 900), 38, P.panel, 170)
    draw = ImageDraw.Draw(image)
    draw.text((118, 190), "人工审核", fill=P.text, font=font(42, medium=True))
    pill(draw, (318, 196), "待人工确认", "#2A2114", P.gold, size=14, outline=P.gold)
    button(draw, (1138, 188, 1278, 236), "批量生产", True)

    draw_phone(image, (118, 286, 346, 778), REFERENCE_FRAME, "参考视频")
    glass_panel(image, (388, 286, 782, 778), 30, P.panel_2, 172)
    draw = ImageDraw.Draw(image)
    draw.text((428, 330), "文案与字幕", fill=P.text, font=font(25, medium=True))
    draw.text((428, 368), "可直接编辑，保存后再进入生产。", fill=P.muted_light, font=font(14))
    rounded(draw, (428, 414, 742, 574), 24, P.cream, "#F0DCC7")
    script_lines = ["在这些案子上面", "我积累了充足的实战经验", "如果你身边刚好缺一位靠谱律师朋友", "不妨留个关注"]
    line_y = 442
    for line in script_lines:
        draw.text((458, line_y), line, fill=P.text_dark, font=font(18))
        line_y += 32
    draw.line((458, 552, 650, 552), fill=P.red_hot, width=2)
    pill(draw, (428, 612), "短句显示", "#102135", P.blue, size=13, outline=P.blue)
    pill(draw, (530, 612), "句尾无标点", "#102A22", P.green, size=13, outline=P.green)
    button(draw, (428, 694, 572, 744), "保存修改", False)

    glass_panel(image, (824, 250, 1286, 812), 34, P.panel_2, 180)
    draw = ImageDraw.Draw(image)
    draw.text((866, 296), "审核详情侧栏", fill=P.text, font=font(27, medium=True))
    draw.text((866, 336), "从列表滑出，不打断主页面。", fill=P.muted_light, font=font(14))
    checks = [
        ("素材授权", "已确认", P.green),
        ("肖像授权", "已确认", P.green),
        ("字幕规则", "已确认", P.green),
        ("画面方向", "需确认", P.gold),
    ]
    check_y = 394
    for label, state, color in checks:
        draw.ellipse((866, check_y, 892, check_y + 26), fill=color)
        if color == P.green:
            draw.line((873, check_y + 14, 878, check_y + 19), fill="#FFFFFF", width=3)
            draw.line((878, check_y + 19, 886, check_y + 8), fill="#FFFFFF", width=3)
        else:
            draw.line((879, check_y + 7, 879, check_y + 16), fill="#FFFFFF", width=3)
            draw.ellipse((877, check_y + 20, 881, check_y + 24), fill="#FFFFFF")
        draw.text((912, check_y + 1), label, fill=P.text, font=font(17, medium=True))
        draw.text((1138, check_y + 2), state, fill=color, font=font(15))
        check_y += 52
    rounded(draw, (866, 632, 1244, 712), 22, P.cream, "#F0DCC7")
    draw.text((896, 658), "审核意见", fill=P.text_dark, font=font(17, medium=True))
    draw.text((896, 686), "确认肖像授权后再进入生产。", fill="#687085", font=font(14))
    button(draw, (866, 744, 1016, 792), "退回修改", False)
    button(draw, (1038, 744, 1244, 792), "确认并生成", True)
    return image.convert("RGB")


def screen_delivery() -> Image.Image:
    image = base_canvas()
    draw = ImageDraw.Draw(image)
    draw_nav(draw, "作品")

    glass_panel(image, (72, 142, 1328, 900), 38, P.panel, 166)
    draw = ImageDraw.Draw(image)
    draw.text((118, 190), "成品交付", fill=P.text, font=font(42, medium=True))
    pill(draw, (318, 196), "已完成", "#102A22", P.green, size=14, outline=P.green)
    draw.text((118, 244), "交付包包含成片、字幕文件和审核记录，可直接归档。", fill=P.muted_light, font=font(17))
    draw_phone(image, (118, 316, 386, 810), REFERENCE_FRAME, "最终成片", progress=100)

    glass_panel(image, (448, 316, 1268, 810), 34, P.panel_2, 178)
    draw = ImageDraw.Draw(image)
    draw.text((492, 364), "下载与归档", fill=P.text, font=font(28, medium=True))
    items = [
        ("成片文件", "可直接发布", "下载视频", P.red_hot),
        ("字幕文件", "可二次校对", "下载字幕", P.blue),
        ("审核记录", "留存流程证据", "查看记录", P.gold),
    ]
    item_y = 430
    for title, detail, action, color in items:
        rounded(draw, (492, item_y, 1208, item_y + 78), 22, "#151C2B", "#2B354A")
        draw.ellipse((524, item_y + 26, 550, item_y + 52), fill=rgba(color, 70))
        draw.text((574, item_y + 18), title, fill=P.text, font=font(19, medium=True))
        draw.text((574, item_y + 47), detail, fill=P.muted_light, font=font(13))
        draw.text((1086, item_y + 28), action, fill=color, font=font(16, medium=True))
        item_y += 102
    button(draw, (492, 732, 692, 786), "下载交付包", True)
    button(draw, (720, 732, 914, 786), "复制分享路径", False)
    rounded(draw, (944, 704, 1208, 786), 22, "#102A22", P.green)
    draw.text((974, 728), "发布前提醒", fill=P.green, font=font(18, medium=True))
    draw.text((974, 756), "再次确认人物授权和平台发布规范。", fill=P.muted_light, font=font(13))
    return image.convert("RGB")


def screen_flow_board(paths: dict[str, Path]) -> Image.Image:
    board = Image.new("RGBA", (1920, 1280), hex_rgb(P.night) + (255,))
    draw_glow(board, (260, 70), 340, P.red, 82)
    draw_glow(board, (1650, 150), 420, P.violet, 48)
    draw = ImageDraw.Draw(board)
    for x_pos in range(0, 1920, 64):
        draw.line((x_pos, 0, x_pos, 1280), fill=rgba("#FFFFFF", 10), width=1)
    for y_pos in range(0, 1280, 64):
        draw.line((0, y_pos, 1920, y_pos), fill=rgba("#FFFFFF", 8), width=1)
    draw.text((88, 70), "赤灵AI运营工作台 · v4 高保真产品设计", fill=P.text, font=font(42, medium=True))
    draw.text((88, 128), "更强品牌感、生成中反馈、任务抽屉、审核闭环；仍然不暴露内部模型与接口。", fill=P.muted_light, font=font(22))
    pill(draw, (1450, 86), "赤红流光", "#2A151A", P.red_hot, size=16, outline=P.red_hot)
    pill(draw, (1586, 86), "生成反馈", "#102A22", P.green, size=16, outline=P.green)

    placements = [
        ("生产驾驶舱", paths["command"], (88, 200)),
        ("创建作品", paths["create"], (1016, 200)),
        ("生成中反馈", paths["generating"], (88, 740)),
        ("人工审核", paths["review"], (1016, 740)),
    ]
    for title, path, origin in placements:
        source = Image.open(path).convert("RGB").resize((760, 512), Image.Resampling.LANCZOS)
        x_pos, y_pos = origin
        shadow = Image.new("RGBA", board.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((x_pos + 10, y_pos + 24, x_pos + 770, y_pos + 536), 30, fill=(0, 0, 0, 100))
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))
        board.alpha_composite(shadow)
        mask = Image.new("L", source.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, source.size[0], source.size[1]), 28, fill=255)
        source_rgba = source.convert("RGBA")
        source_rgba.putalpha(mask)
        board.alpha_composite(source_rgba, origin)
        border_draw = ImageDraw.Draw(board)
        border_draw.rounded_rectangle((x_pos, y_pos, x_pos + 760, y_pos + 512), 28, outline=rgba("#FFFFFF", 42), width=1)
        draw = ImageDraw.Draw(board)
        draw.text((x_pos, y_pos - 44), title, fill=P.text, font=font(25, medium=True))
    draw.line((874, 456, 1000, 456), fill=P.red_hot, width=4)
    draw.polygon([(1000, 456), (978, 444), (978, 468)], fill=P.red_hot)
    draw.line((874, 996, 1000, 996), fill=P.red_hot, width=4)
    draw.polygon([(1000, 996), (978, 984), (978, 1008)], fill=P.red_hot)
    draw.text((880, 414), "导入设置", fill=P.red_hot, font=font(17, medium=True))
    draw.text((880, 954), "确认生成", fill=P.red_hot, font=font(17, medium=True))
    return board.convert("RGB")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "command": OUT_DIR / "chiling-product-v4-command-center.png",
        "create": OUT_DIR / "chiling-product-v4-create.png",
        "generating": OUT_DIR / "chiling-product-v4-generating-feedback.png",
        "review": OUT_DIR / "chiling-product-v4-review.png",
        "delivery": OUT_DIR / "chiling-product-v4-delivery.png",
    }
    screen_command_center().save(paths["command"])
    screen_create().save(paths["create"])
    screen_generating().save(paths["generating"])
    screen_review().save(paths["review"])
    screen_delivery().save(paths["delivery"])
    board_path = OUT_DIR / "chiling-product-v4-flow-board.png"
    screen_flow_board(paths).save(board_path)
    for path in [board_path, *paths.values()]:
        print(path)


if __name__ == "__main__":
    main()
