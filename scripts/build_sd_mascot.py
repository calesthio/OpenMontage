"""Biến sprite sheet do gpt-image-2 sinh (lưới 4x4 trên nền magenta) thành dải
ngang 16 frame WebP trong suốt, căn chân về cùng baseline, cùng kích thước frame.

Dùng:  python scripts/build_sd_mascot.py <thư mục sheet> <thư mục ra>
Mỗi <action>.png trong thư mục sheet -> <action>.webp dải 16 x (FRAME_W x FRAME_H).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

FRAME_W, FRAME_H = 240, 300
COLS, ROWS = 4, 4
KEY = np.array([255, 0, 255], dtype=np.int16)
# ponytail: ngưỡng cố định, đủ cho nền magenta phẳng; chỉnh nếu model tô nền lệch màu.
KEY_TOL = 90
FOOT_MARGIN = 14  # px chừa dưới chân để bóng không đè
# Thước đo chung cho MỌI sheet: căn bậc hai diện tích pixel đục của nhân vật.
# Diện tích gần như không đổi theo pose (giơ tay, bước chân) nên mọi action ra cùng
# cỡ; lấy median trong action để 1 frame lệch không làm giật cỡ. Chuẩn: frame idle
# cao IDLE_H px sau khi scale, các action khác theo cùng tỉ lệ diện tích.
IDLE_H = 250


def key_out(rgb: np.ndarray) -> np.ndarray:
    """Trả về alpha 0..255: xa magenta = đục, gần = trong. Mềm ở rìa để đỡ răng cưa."""
    d = np.abs(rgb.astype(np.int16) - KEY).sum(axis=-1)
    a = np.clip((d - KEY_TOL * 0.6) / (KEY_TOL * 0.8), 0, 1)
    return (a * 255).astype(np.uint8)


def despill(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Rìa nhân vật bị nhiễm tím: ép kênh R/B không vượt G quá nhiều ở vùng bán trong."""
    out = rgb.astype(np.int16).copy()
    edge = (alpha > 0) & (alpha < 250)
    g = out[..., 1]
    out[..., 0][edge] = np.minimum(out[..., 0][edge], g[edge] + 40)
    out[..., 2][edge] = np.minimum(out[..., 2][edge], g[edge] + 40)
    return np.clip(out, 0, 255).astype(np.uint8)


def cells(sheet: Image.Image):
    w, h = sheet.size
    cw, ch = w // COLS, h // ROWS
    for r in range(ROWS):
        for c in range(COLS):
            yield sheet.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))


def normalise(cell: Image.Image) -> Image.Image:
    """Cắt bbox, scale để cao nhất = FRAME_H - margin, đặt chân sát đáy, giữa ngang."""
    rgb = np.asarray(cell.convert("RGB"))
    a = key_out(rgb)
    # Opening 3px trên alpha: xoá đốm magenta lệch màu còn sót (1-2px) mà không
    # ăn mòn nét vẽ ở độ phân giải 2x.
    a = np.array(Image.fromarray(a).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3)))
    # Bỏ khối pixel chạm mép cell (chân/đuôi của cell bên cạnh lọt sang), trừ khối
    # lớn nhất (thân nhân vật). Chữ Z, đuôi rời... nổi giữa cell nên được giữ.
    solid = a > 40
    labels, n = ndimage.label(solid)
    if n > 1:
        sizes = ndimage.sum(solid, labels, range(1, n + 1))
        main = int(np.argmax(sizes)) + 1
        edge = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
        for lab in edge:
            if lab != 0 and lab != main:
                a[labels == lab] = 0
        solid = a > 40
    rgba = np.dstack([despill(rgb, a), a])
    # bbox chỉ tính hàng/cột có >= 6 px đục, để một vệt nhỏ không kéo bbox rộng ra.
    ys = np.where(solid.sum(axis=1) >= 6)[0]
    xs = np.where(solid.sum(axis=0) >= 6)[0]
    if len(ys) == 0 or len(xs) == 0:
        return Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 0))
    crop = Image.fromarray(rgba).crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    return crop


def sqrt_area(frame: Image.Image) -> float:
    return float(np.sqrt((np.asarray(frame)[..., 3] > 128).sum()))


def pack(frames: list[Image.Image], target: float) -> Image.Image:
    """target = sqrt(diện tích) mong muốn, áp cho TỪNG frame.

    Đã thử: scale chung cả action (giật cỡ khi đổi hàng của sheet), scale theo
    hàng (frame đứng của jump vẫn to hơn idle 8% -> giật khi idle<->jump), bề rộng
    bờm (tay giơ che bờm, lệch 10-27%). Diện tích từng frame là ổn định nhất: mọi
    frame đứng ở mọi action đều bằng nhau; giá phải trả là 3-4 frame ngồi thụp
    của jump (chi chồng lên nhau, diện tích nhìn thấy giảm) bị phóng ~8% trong
    ~0,15s, đọc như squash nên chấp nhận được.
    """
    strip = Image.new("RGBA", (FRAME_W * len(frames), FRAME_H), (0, 0, 0, 0))
    scales = [target / sqrt_area(f) for f in frames]
    for i, f in enumerate(frames):
        scale = scales[i]
        g = f.resize((max(1, round(f.width * scale)), max(1, round(f.height * scale))), Image.LANCZOS)
        # Quá khổ (tay chỉ dài, nhảy giơ tay): cắt bớt rìa thay vì thu nhỏ cả nhân vật.
        if g.width > FRAME_W or g.height > FRAME_H - FOOT_MARGIN:
            left = max(0, (g.width - FRAME_W) // 2)
            top = max(0, g.height - (FRAME_H - FOOT_MARGIN))
            g = g.crop((left, top, min(g.width, left + FRAME_W), g.height))
        x = i * FRAME_W + (FRAME_W - g.width) // 2
        y = FRAME_H - FOOT_MARGIN - g.height
        strip.alpha_composite(g, (x, y))
    return strip


def build(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    all_frames = {p.stem: [normalise(c) for c in cells(Image.open(p))] for p in sorted(src.glob("*.png"))}
    if "idle" not in all_frames:
        sys.exit("cần idle.png làm chuẩn cỡ")
    idle = all_frames["idle"]
    idle_scale = IDLE_H / float(np.median([f.height for f in idle]))
    target = float(np.median([sqrt_area(f) for f in idle])) * idle_scale
    for name, frames in all_frames.items():
        sheet_path = src / f"{name}.png"
        strip = pack(frames, target)
        # Độ lệch cỡ còn lại giữa các frame (sau scale): >5% là mắt thấy phồng/xẹp.
        areas = [sqrt_area(strip.crop((i * FRAME_W, 0, (i + 1) * FRAME_W, FRAME_H))) for i in range(len(frames))]
        spread = (max(areas) - min(areas)) / float(np.median(areas)) * 100
        print(f"  {name}: size spread across frames {spread:.1f}%")
        # WebP alpha nhẹ hơn PNG 5-8 lần; mọi trình duyệt từ 2020 đều đọc được.
        out = dst / f"{sheet_path.stem}.webp"
        strip.save(out, "WEBP", quality=82, method=6)
        print(sheet_path.stem, "->", len(frames), "frames,", out.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    build(Path(sys.argv[1]), Path(sys.argv[2]))
