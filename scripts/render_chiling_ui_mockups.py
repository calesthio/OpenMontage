#!/usr/bin/env python3
"""Render productized UI mockups for 赤灵AI运营工作台."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


OUT_DIR = Path("docs/ui-mockups")
WIDTH = 1440
HEIGHT = 1024


@dataclass(frozen=True)
class Palette:
    bg: str = "#F7F3EE"
    surface: str = "#FFFFFF"
    surface_warm: str = "#FFF8F3"
    ink: str = "#121722"
    ink_soft: str = "#303746"
    muted: str = "#7A818C"
    faint: str = "#E9DFD5"
    faint_2: str = "#F1E9E0"
    accent: str = "#D93032"
    accent_dark: str = "#B72227"
    red_soft: str = "#FFF1EE"
    green: str = "#1E9F64"
    green_soft: str = "#EAF8F1"
    blue: str = "#2563EB"
    blue_soft: str = "#EEF4FF"
    amber: str = "#C7811D"
    amber_soft: str = "#FFF6DF"
    sidebar: str = "#111722"
    sidebar_2: str = "#1A2230"
    line: str = "#E5DBD1"


PALETTE = Palette()


FONT_REGULAR = "/System/Library/Fonts/STHeiti Light.ttc"
FONT_MEDIUM = "/System/Library/Fonts/STHeiti Medium.ttc"
FONT_FALLBACK = "/Library/Fonts/Arial Unicode.ttf"


def font(size: int, medium: bool = False) -> ImageFont.FreeTypeFont:
    preferred = FONT_MEDIUM if medium else FONT_REGULAR
    path = preferred if Path(preferred).exists() else FONT_FALLBACK
    return ImageFont.truetype(path, size=size)


def canvas() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), PALETTE.bg)
    draw = ImageDraw.Draw(image)
    for x_pos in range(0, WIDTH, 64):
        draw.line((x_pos, 0, x_pos, HEIGHT), fill="#F0E9E1", width=1)
    for y_pos in range(0, HEIGHT, 64):
        draw.line((0, y_pos, WIDTH, y_pos), fill="#F0E9E1", width=1)
    return image


def text_size(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), value, font=face)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def rounded(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int = 18,
    fill: str = PALETTE.surface,
    outline: str | None = None,
    width: int = 1,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def shadowed_panel(
    image: Image.Image,
    xy: tuple[int, int, int, int],
    radius: int = 30,
    fill: str = PALETTE.surface,
    outline: str | None = None,
    shadow: tuple[int, int, int, int] = (18, 22, 35, 28),
) -> ImageDraw.ImageDraw:
    shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    offset_xy = (xy[0], xy[1] + 12, xy[2], xy[3] + 12)
    shadow_draw.rounded_rectangle(offset_xy, radius=radius, fill=shadow)
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(18))
    image.alpha_composite(shadow_layer)
    draw = ImageDraw.Draw(image)
    rounded(draw, xy, radius=radius, fill=fill, outline=outline or PALETTE.line)
    return draw


def draw_label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, color: str = PALETTE.muted) -> None:
    draw.text(xy, value, fill=color, font=font(17))


def draw_title(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, size: int = 28) -> None:
    draw.text(xy, value, fill=PALETTE.ink, font=font(size, medium=True))


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    value: str,
    fill: str,
    color: str,
    padding_x: int = 15,
    padding_y: int = 8,
    size: int = 15,
) -> tuple[int, int, int, int]:
    face = font(size, medium=True)
    text_width, text_height = text_size(draw, value, face)
    box = (
        xy[0],
        xy[1],
        xy[0] + text_width + padding_x * 2,
        xy[1] + text_height + padding_y * 2,
    )
    rounded(draw, box, radius=(box[3] - box[1]) // 2, fill=fill)
    draw.text((xy[0] + padding_x, xy[1] + padding_y - 1), value, fill=color, font=face)
    return box


def button(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    value: str,
    primary: bool = True,
    muted: bool = False,
) -> None:
    if primary:
        fill, outline, color = PALETTE.accent, PALETTE.accent, "#FFFFFF"
    elif muted:
        fill, outline, color = "#F5F0EA", "#F5F0EA", PALETTE.ink_soft
    else:
        fill, outline, color = PALETTE.surface, PALETTE.line, PALETTE.accent
    rounded(draw, xy, radius=18, fill=fill, outline=outline, width=1)
    face = font(17, medium=True)
    text_width, text_height = text_size(draw, value, face)
    draw.text(
        ((xy[0] + xy[2] - text_width) // 2, (xy[1] + xy[3] - text_height) // 2 - 2),
        value,
        fill=color,
        font=face,
    )


def draw_topbar(draw: ImageDraw.ImageDraw, active: str = "作品") -> None:
    rounded(draw, (40, 38, WIDTH - 40, 112), radius=30, fill=PALETTE.sidebar)
    draw.text((72, 62), "赤灵AI运营工作台", fill="#FFFFFF", font=font(24, medium=True))
    nav_items = ["作品", "素材库", "团队审核", "数据概览"]
    nav_x = 338
    for item in nav_items:
        is_active = item == active
        item_width = text_size(draw, item, font(16, medium=True))[0] + 34
        if is_active:
            rounded(draw, (nav_x - 16, 58, nav_x + item_width - 4, 92), radius=17, fill=PALETTE.sidebar_2)
        draw.text((nav_x, 66), item, fill="#FFFFFF" if is_active else "#A9B0BC", font=font(16, medium=True))
        nav_x += item_width + 22
    button(draw, (WIDTH - 208, 56, WIDTH - 68, 96), "新建作品", primary=True)


def metric_card(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], label: str, value: str, note: str) -> None:
    rounded(draw, xy, radius=22, fill=PALETTE.surface, outline=PALETTE.line)
    draw.text((xy[0] + 26, xy[1] + 20), label, fill=PALETTE.muted, font=font(16))
    draw.text((xy[0] + 26, xy[1] + 49), value, fill=PALETTE.ink, font=font(34, medium=True))
    draw.text((xy[0] + 83, xy[1] + 62), note, fill=PALETTE.muted, font=font(15))


def work_row(
    draw: ImageDraw.ImageDraw,
    y_pos: int,
    title: str,
    status: str,
    status_color: str,
    status_fill: str,
    detail: str,
    action: str,
    active: bool = False,
) -> None:
    fill = "#FFFFFF" if not active else "#FFF8F3"
    outline = PALETTE.line if not active else "#F0B2A8"
    rounded(draw, (80, y_pos, WIDTH - 80, y_pos + 72), radius=20, fill=fill, outline=outline, width=2 if active else 1)
    dot_color = status_color
    draw.ellipse((104, y_pos + 29, 116, y_pos + 41), fill=dot_color)
    draw.text((134, y_pos + 22), title, fill=PALETTE.ink, font=font(18, medium=True))
    pill(draw, (420, y_pos + 19), status, fill=status_fill, color=status_color, size=14)
    draw.text((585, y_pos + 25), detail, fill=PALETTE.muted, font=font(16))
    button(draw, (WIDTH - 216, y_pos + 16, WIDTH - 104, y_pos + 56), action, primary=False, muted=not active)
    if active:
        draw.text((WIDTH - 380, y_pos + 27), "点击后右侧滑出审核详情", fill=PALETTE.accent, font=font(14))


def screen_dashboard() -> Image.Image:
    image = canvas().convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw_topbar(draw, "作品")

    draw.text((80, 158), "今天要推进哪条内容？", fill=PALETTE.ink, font=font(36, medium=True))
    draw.text((80, 205), "导入参考视频，系统会整理文案、画面节奏和可编辑的生产方案。", fill=PALETTE.muted, font=font(18))
    button(draw, (80, 250, 230, 296), "开始新作品", primary=True)
    button(draw, (250, 250, 392, 296), "查看审核队列", primary=False)

    metric_card(draw, (80, 338, 304, 432), "待审核", "3", "需人工确认")
    metric_card(draw, (328, 338, 552, 432), "生成中", "2", "预计 12 分钟")
    metric_card(draw, (576, 338, 800, 432), "已交付", "18", "本周完成")

    rounded(draw, (860, 158, WIDTH - 80, 432), radius=30, fill=PALETTE.surface, outline=PALETTE.line)
    draw.text((900, 198), "快速导入", fill=PALETTE.ink, font=font(24, medium=True))
    draw.text((900, 235), "粘贴视频链接，或上传本地视频。人物素材可稍后补充。", fill=PALETTE.muted, font=font(16))
    rounded(draw, (900, 282, WIDTH - 126, 338), radius=17, fill="#FBF8F4", outline=PALETTE.line)
    draw.text((926, 300), "粘贴抖音/视频链接…", fill="#A4A1A0", font=font(17))
    button(draw, (WIDTH - 282, 352, WIDTH - 126, 396), "进入设置", primary=True)

    draw.text((80, 494), "最近作品", fill=PALETTE.ink, font=font(25, medium=True))
    draw.text((80, 526), "每条作品都能看到当前状态，点开即可审核或下载。", fill=PALETTE.muted, font=font(16))
    work_row(draw, 572, "工程纠纷口播复刻", "已交付", PALETTE.green, PALETTE.green_soft, "可下载成品与字幕", "打开")
    work_row(draw, 656, "律师私域引流短片", "待审核", PALETTE.amber, PALETTE.amber_soft, "请检查文案和人物授权", "去审核", active=True)
    work_row(draw, 740, "本地生活探店模板", "生成中", PALETTE.blue, PALETTE.blue_soft, "系统正在处理画面", "查看")

    rounded(draw, (1110, 590, 1356, 798), radius=26, fill=PALETTE.surface_warm, outline="#F1C8C0")
    draw.text((1140, 626), "审核详情预览", fill=PALETTE.ink, font=font(22, medium=True))
    draw.text((1140, 664), "点击待审核作品后，右侧会滑出详情侧栏。", fill=PALETTE.muted, font=font(15))
    pill(draw, (1140, 710), "2 项需确认", PALETTE.red_soft, PALETTE.accent, size=14)
    draw.line((1108, 696, 1082, 682), fill=PALETTE.accent, width=3)
    draw.polygon([(1082, 682), (1098, 679), (1091, 693)], fill=PALETTE.accent)
    draw.text((1030, 652), "悬停/点击", fill=PALETTE.accent, font=font(14, medium=True))
    return image.convert("RGB")


def stepper(draw: ImageDraw.ImageDraw, active_index: int) -> None:
    labels = ["导入参考", "设置生成", "提交审核"]
    x_positions = [360, 660, 960]
    for index, label in enumerate(labels, start=1):
        x_pos = x_positions[index - 1]
        complete = index < active_index
        active = index == active_index
        fill = PALETTE.accent if active or complete else "#E9E1D7"
        color = "#FFFFFF" if active or complete else "#8E877F"
        draw.ellipse((x_pos, 168, x_pos + 36, 204), fill=fill)
        step_face = font(15, medium=True)
        text_width, text_height = text_size(draw, str(index), step_face)
        draw.text((x_pos + 18 - text_width / 2, 186 - text_height / 2 - 1), str(index), fill=color, font=step_face)
        draw.text((x_pos + 50, 177), label, fill=PALETTE.ink_soft if active else PALETTE.muted, font=font(16, medium=True))
        if index < 3:
            draw.line((x_pos + 160, 186, x_pos + 268, 186), fill="#E3D8CE", width=3)


def input_panel(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    title: str,
    subtitle: str,
    action: str,
    selected: bool = False,
) -> None:
    fill = PALETTE.surface_warm if selected else "#FBFAF8"
    outline = "#F0B2A8" if selected else PALETTE.line
    rounded(draw, xy, radius=24, fill=fill, outline=outline, width=2 if selected else 1)
    icon_x, icon_y = xy[0] + 30, xy[1] + 34
    draw.ellipse((icon_x, icon_y, icon_x + 44, icon_y + 44), fill=PALETTE.accent if selected else "#FFE0DA")
    draw.polygon(
        [(icon_x + 18, icon_y + 13), (icon_x + 18, icon_y + 31), (icon_x + 32, icon_y + 22)],
        fill="#FFFFFF" if selected else PALETTE.accent,
    )
    draw.text((xy[0] + 94, xy[1] + 30), title, fill=PALETTE.ink, font=font(21, medium=True))
    draw.text((xy[0] + 94, xy[1] + 64), subtitle, fill=PALETTE.muted, font=font(15))
    draw.text((xy[2] - 118, xy[1] + 46), action, fill=PALETTE.accent, font=font(15, medium=True))


def setting_row(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], label: str, value: str, helper: str) -> None:
    rounded(draw, xy, radius=20, fill=PALETTE.surface, outline=PALETTE.line)
    draw.text((xy[0] + 22, xy[1] + 18), label, fill=PALETTE.muted, font=font(15))
    draw.text((xy[0] + 160, xy[1] + 16), value, fill=PALETTE.ink, font=font(20, medium=True))
    draw.text((xy[0] + 160, xy[1] + 47), helper, fill="#9A948F", font=font(13))


def screen_create() -> Image.Image:
    image = canvas().convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw_topbar(draw, "作品")
    shadowed_panel(image, (104, 138, WIDTH - 104, HEIGHT - 72), radius=34, fill="#FFFCF8")
    draw = ImageDraw.Draw(image)
    draw.text((148, 174), "创建新作品", fill=PALETTE.ink, font=font(30, medium=True))
    draw.text((148, 215), "三步完成设置，先看方案再进入生产。", fill=PALETTE.muted, font=font(17))
    button(draw, (WIDTH - 260, 172, WIDTH - 148, 214), "保存草稿", primary=False, muted=True)
    stepper(draw, 1)

    draw.text((148, 268), "输入参考内容", fill=PALETTE.ink, font=font(28, medium=True))
    draw.text((148, 306), "用户只需要提供参考视频和授权素材，复杂处理交给系统。", fill=PALETTE.muted, font=font(16))
    input_panel(draw, (148, 354, 690, 476), "参考视频", "粘贴链接，或上传本地视频文件", "选择文件", selected=True)
    input_panel(draw, (720, 354, 1292, 476), "人物 / 品牌素材", "上传团队授权图片，或从素材库选择", "素材库")

    draw.text((148, 536), "生成设置", fill=PALETTE.ink, font=font(25, medium=True))
    setting_row(draw, (148, 580, 596, 652), "成片时长", "15 秒内", "可按素材自动适配，也可手动缩短")
    setting_row(draw, (628, 580, 1076, 652), "清晰度", "标准 480p / 高清 720p", "默认标准，发布前可切高清")
    setting_row(draw, (148, 682, 596, 754), "生成数量", "1 条", "默认 1 条，单批最多 5 条")
    setting_row(draw, (628, 682, 1076, 754), "字幕风格", "口播短句", "自动去掉句尾标点，便于观看")

    rounded(draw, (1100, 580, 1292, 754), radius=24, fill=PALETTE.red_soft, outline="#F4C2BA")
    draw.text((1126, 616), "交互提示", fill=PALETTE.accent, font=font(20, medium=True))
    draw.text((1126, 656), "所有设置项都支持编辑。", fill=PALETTE.ink_soft, font=font(15))
    draw.text((1126, 688), "提交前会进入人工审核。", fill=PALETTE.ink_soft, font=font(15))
    button(draw, (1028, 824, 1292, 880), "下一步：查看方案", primary=True)
    return image.convert("RGB")


def checkbox(draw: ImageDraw.ImageDraw, x_pos: int, y_pos: int, label: str, done: bool = True, warn: bool = False) -> None:
    color = PALETTE.green if done else PALETTE.amber if warn else PALETTE.muted
    fill = PALETTE.green if done else PALETTE.amber if warn else "#D9D5CF"
    draw.ellipse((x_pos, y_pos, x_pos + 26, y_pos + 26), fill=fill)
    if done:
        draw.line((x_pos + 7, y_pos + 14, x_pos + 12, y_pos + 19), fill="#FFFFFF", width=3)
        draw.line((x_pos + 12, y_pos + 19, x_pos + 20, y_pos + 8), fill="#FFFFFF", width=3)
    else:
        draw.line((x_pos + 13, y_pos + 7, x_pos + 13, y_pos + 15), fill="#FFFFFF", width=3)
        draw.ellipse((x_pos + 11, y_pos + 19, x_pos + 15, y_pos + 23), fill="#FFFFFF")
    draw.text((x_pos + 42, y_pos + 2), label, fill=PALETTE.ink_soft, font=font(16, medium=True))
    draw.text((x_pos + 230, y_pos + 2), "已确认" if done else "需确认", fill=color, font=font(15))


def screen_review() -> Image.Image:
    image = canvas().convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw_topbar(draw, "团队审核")
    rounded(draw, (64, 142, WIDTH - 64, HEIGHT - 60), radius=34, fill="#FFFCF8", outline=PALETTE.line)
    draw.text((104, 182), "作品审核 · 工程纠纷口播", fill=PALETTE.ink, font=font(29, medium=True))
    pill(draw, (452, 184), "待人工确认", PALETTE.amber_soft, PALETTE.amber, size=14)
    button(draw, (WIDTH - 254, 176, WIDTH - 104, 220), "批量生产", primary=True)

    rounded(draw, (104, 268, 418, 710), radius=28, fill=PALETTE.sidebar, outline=PALETTE.sidebar)
    rounded(draw, (134, 304, 388, 640), radius=22, fill="#273145", outline="#273145")
    draw.ellipse((246, 438, 286, 478), fill=PALETTE.accent)
    draw.polygon([(263, 449), (263, 467), (278, 458)], fill="#FFFFFF")
    draw.text((184, 660), "参考视频预览", fill="#B7C0CE", font=font(15))

    rounded(draw, (448, 268, 820, 710), radius=28, fill=PALETTE.surface, outline=PALETTE.line)
    draw.text((486, 306), "文案审核", fill=PALETTE.ink, font=font(24, medium=True))
    draw.text((486, 342), "可直接改文案，保存后再进入生成。", fill=PALETTE.muted, font=font(15))
    rounded(draw, (486, 386, 782, 552), radius=18, fill="#FFFCF8", outline=PALETTE.line)
    script_lines = ["在这些案子上面", "我积累了充足的实战经验", "如果你身边刚好缺一位靠谱律师朋友", "不妨留个关注"]
    line_y = 414
    for line in script_lines:
        draw.text((512, line_y), line, fill=PALETTE.ink_soft, font=font(18))
        line_y += 31
    draw.line((512, 530, 700, 530), fill=PALETTE.accent, width=2)
    draw.text((486, 584), "字幕规则", fill=PALETTE.ink_soft, font=font(16, medium=True))
    pill(draw, (576, 576), "短句显示", PALETTE.blue_soft, PALETTE.blue, size=13)
    pill(draw, (680, 576), "句尾无标点", PALETTE.green_soft, PALETTE.green, size=13)
    button(draw, (486, 638, 620, 684), "保存修改", primary=False)

    rounded(draw, (850, 236, WIDTH - 94, 782), radius=30, fill=PALETTE.surface_warm, outline="#F0B2A8")
    draw.text((888, 278), "审核详情侧栏", fill=PALETTE.ink, font=font(25, medium=True))
    draw.text((888, 316), "从作品列表点击“去审核”后滑出，审核项不打断主页面。", fill=PALETTE.muted, font=font(15))
    checkbox(draw, 888, 370, "素材授权", True)
    checkbox(draw, 888, 420, "肖像授权", True)
    checkbox(draw, 888, 470, "字幕规则", True)
    checkbox(draw, 888, 520, "画面方向", False, warn=True)
    rounded(draw, (888, 580, WIDTH - 134, 672), radius=18, fill="#FFFFFF", outline=PALETTE.line)
    draw.text((914, 606), "审核意见", fill=PALETTE.ink_soft, font=font(17, medium=True))
    draw.text((914, 636), "确认肖像授权后再进入生产。", fill=PALETTE.muted, font=font(15))
    button(draw, (888, 710, 1038, 758), "退回修改", primary=False)
    button(draw, (1060, 710, WIDTH - 134, 758), "确认并生成", primary=True)

    rounded(draw, (1268, 388, 1328, 506), radius=22, fill="#FFFFFF", outline=PALETTE.line)
    draw.text((1287, 414), "侧栏", fill=PALETTE.accent, font=font(15, medium=True))
    draw.text((1293, 456), "⌄", fill=PALETTE.accent, font=font(28, medium=True))
    return image.convert("RGB")


def screen_delivery() -> Image.Image:
    image = canvas().convert("RGBA")
    draw = ImageDraw.Draw(image)
    draw_topbar(draw, "作品")
    rounded(draw, (76, 142, WIDTH - 76, HEIGHT - 70), radius=34, fill="#FFFCF8", outline=PALETTE.line)
    draw.text((120, 184), "成品交付", fill=PALETTE.ink, font=font(31, medium=True))
    pill(draw, (282, 185), "已完成", PALETTE.green_soft, PALETTE.green, size=14)
    draw.text((120, 226), "交付包包含成片、字幕文件、审核记录，可直接下载归档。", fill=PALETTE.muted, font=font(17))

    rounded(draw, (120, 296, 458, 780), radius=30, fill=PALETTE.sidebar, outline=PALETTE.sidebar)
    rounded(draw, (172, 340, 406, 704), radius=24, fill="#263246", outline="#263246")
    draw.ellipse((250, 404, 328, 482), fill="#F5C49C")
    rounded(draw, (228, 496, 350, 648), radius=55, fill=PALETTE.accent)
    rounded(draw, (210, 650, 368, 684), radius=15, fill="#070A0F")
    draw.text((244, 657), "私域律师口播", fill="#FFFFFF", font=font(15))

    rounded(draw, (510, 296, WIDTH - 120, 780), radius=30, fill=PALETTE.surface, outline=PALETTE.line)
    draw.text((550, 338), "最终文件", fill=PALETTE.ink, font=font(25, medium=True))
    delivery_items = [
        ("成片文件", "可直接发布", "下载视频", PALETTE.accent),
        ("字幕文件", "可二次校对", "下载字幕", PALETTE.blue),
        ("审核记录", "留存流程证据", "查看记录", PALETTE.amber),
    ]
    item_y = 392
    for title, subtitle, action, color in delivery_items:
        rounded(draw, (550, item_y, WIDTH - 168, item_y + 82), radius=22, fill="#FFFCF8", outline=PALETTE.line)
        draw.text((584, item_y + 20), title, fill=PALETTE.ink, font=font(19, medium=True))
        draw.text((584, item_y + 49), subtitle, fill=PALETTE.muted, font=font(14))
        draw.text((WIDTH - 286, item_y + 30), action, fill=color, font=font(16, medium=True))
        item_y += 104
    button(draw, (550, 708, 758, 762), "下载交付包", primary=True)
    button(draw, (786, 708, 982, 762), "复制分享路径", primary=False)

    rounded(draw, (1030, 610, WIDTH - 168, 762), radius=24, fill=PALETTE.green_soft, outline="#BFEAD1")
    draw.text((1060, 644), "发布前提醒", fill=PALETTE.green, font=font(20, medium=True))
    draw.text((1060, 682), "请再次确认人物授权和平台发布规范。", fill=PALETTE.ink_soft, font=font(15))
    return image.convert("RGB")


def screen_flow_board(paths: dict[str, Path]) -> Image.Image:
    image = Image.new("RGB", (1920, 1280), PALETTE.bg)
    draw = ImageDraw.Draw(image)
    for x_pos in range(0, 1920, 64):
        draw.line((x_pos, 0, x_pos, 1280), fill="#F0E9E1", width=1)
    for y_pos in range(0, 1280, 64):
        draw.line((0, y_pos, 1920, y_pos), fill="#F0E9E1", width=1)
    draw.text((88, 70), "赤灵AI运营工作台 · v3 产品化 UI", fill=PALETTE.ink, font=font(44, medium=True))
    draw.text(
        (88, 126),
        "隐藏内部技术与模型名称，只呈现用户任务、审核状态和可操作入口。",
        fill=PALETTE.muted,
        font=font(22),
    )
    pill(draw, (1512, 84), "业务动作优先", PALETTE.green_soft, PALETTE.green, size=16)
    pill(draw, (1666, 84), "多状态交互", PALETTE.red_soft, PALETTE.accent, size=16)

    placements = [
        ("首页 / 任务队列", paths["dashboard"], (88, 190)),
        ("创建作品 / 参数设置", paths["create"], (1016, 190)),
        ("人工审核 / 侧栏弹出", paths["review"], (88, 738)),
        ("成品交付 / 下载归档", paths["delivery"], (1016, 738)),
    ]
    for title, path, origin in placements:
        source = Image.open(path).convert("RGB")
        thumb = source.resize((760, 540), Image.Resampling.LANCZOS)
        x_pos, y_pos = origin
        shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((x_pos + 10, y_pos + 22, x_pos + 770, y_pos + 562), radius=28, fill=(18, 22, 35, 32))
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        image = image.convert("RGBA")
        image.alpha_composite(shadow)
        image = image.convert("RGB")
        mask = Image.new("L", thumb.size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle((0, 0, thumb.size[0], thumb.size[1]), radius=28, fill=255)
        image.paste(thumb, origin, mask)
        draw = ImageDraw.Draw(image)
        draw.text((x_pos, y_pos - 42), title, fill=PALETTE.ink, font=font(24, medium=True))

    draw.line((895, 455, 1000, 455), fill=PALETTE.accent, width=4)
    draw.polygon([(1000, 455), (980, 444), (980, 466)], fill=PALETTE.accent)
    draw.line((895, 1004, 1000, 1004), fill=PALETTE.accent, width=4)
    draw.polygon([(1000, 1004), (980, 993), (980, 1015)], fill=PALETTE.accent)
    draw.text((884, 410), "新建作品", fill=PALETTE.accent, font=font(17, medium=True))
    draw.text((884, 958), "确认生成", fill=PALETTE.accent, font=font(17, medium=True))
    return image


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "dashboard": OUT_DIR / "chiling-product-v3-dashboard.png",
        "create": OUT_DIR / "chiling-product-v3-create.png",
        "review": OUT_DIR / "chiling-product-v3-review.png",
        "delivery": OUT_DIR / "chiling-product-v3-delivery.png",
    }
    screen_dashboard().save(paths["dashboard"])
    screen_create().save(paths["create"])
    screen_review().save(paths["review"])
    screen_delivery().save(paths["delivery"])
    board_path = OUT_DIR / "chiling-product-v3-flow-board.png"
    screen_flow_board(paths).save(board_path)
    for path in [board_path, *paths.values()]:
        print(path)


if __name__ == "__main__":
    main()
