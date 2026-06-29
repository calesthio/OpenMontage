---
title: Pipeline sản xuất video chuẩn Thiền Đạo — SOP doc + build script template
description: >-
  Codify pipeline de-facto từ 3 video đã làm thành 1 SOP doc (docs/) + 1 build
  script template tham số hoá cho khâu dựng FFmpeg
status: completed
priority: P2
branch: main
tags:
  - pipeline
  - sop
  - video
  - thien-dao
  - ffmpeg
blockedBy: []
blocks: []
created: '2026-06-29T16:46:23.054Z'
createdBy: 'ck:plan'
source: skill
---

# Pipeline sản xuất video chuẩn Thiền Đạo — SOP doc + build script template

## Overview

Biến pipeline de-facto (đúc kết qua 3 video `projects/` + 12 memory file) thành 2 artifact tái dùng:
1. **`docs/video-production-pipeline.md`** — SOP 9 stage đọc-làm-theo + bảng locked defaults + cây fallback + tách lõi-chung vs riêng-thiền.
2. **`scripts/video/montage_lib.py`** — recipe library (≤6 hàm FFmpeg thuần + offset helper) cho khâu dựng (concat, narration amix, mix nhạc ducked, intro/outro cards, remux) trích từ `projects/bon-mua-cua-hoi-tho/build_meditation_video.py`; mỗi video giữ thin driver import lib.

> Hướng artifact #2 đổi từ "driver template + config schema" → "recipe library + thin drivers" sau ck:predict --chain reason (tránh over-fit 1 config cho 3 video khác nhau; DRY hoá recipe đã chứng minh).

Nguồn brainstorm: [`plans/reports/brainstorm-260630-0037-thien-dao-standard-video-pipeline-report.md`](../reports/brainstorm-260630-0037-thien-dao-standard-video-pipeline-report.md).

**Nguyên tắc:** YAGNI/KISS — không tạo `pipeline_defs/*.yaml` (Rule Zero) lần này; doc + script đủ phủ nhu cầu. Không sửa tool OpenMontage.

## Phases

| Phase | Name | Status |
|-------|------|--------|
| 1 | [SOP doc](./phase-01-sop-doc.md) | Completed |
| 2 | [Recipe library + offset helper](./phase-02-build-script-template.md) | Completed |
| 3 | [Validation & wiring](./phase-03-validation-wiring.md) | Completed |

## Acceptance Criteria

- [x] `docs/video-production-pipeline.md` tồn tại, phủ đủ 9 stage (0–8) + locked defaults + fallback tree + split lõi/thiền.
- [x] `scripts/video/montage_lib.py` cung cấp ≤6 hàm thuần + offset helper; subprocess arg-list (không `shell=True` cho text); không config schema monolithic.
- [x] Lib tái tạo đúng recipe đã chứng minh: concat re-encode an toàn, narration delay+reverb amix, music sidechain duck + loudnorm I=-16, intro/outro card drawtext UTF-8, remux `-c:v copy`.
- [x] Driver bon-mua qua lib + long-form skeleton chạy ra video hợp lệ (ffprobe + silencedetect pass); bon-mua = build rút gọn 247.5s (gốc 692s), long-form = 240-cue batch-amix + đường dựng dài 132s.
- [x] Doc ↔ lib README tham chiếu chéo; doc link plan lịch nội dung.

## Dependencies

- **Liên quan (không block):** [`plans/260629-2354-thien-dao-4-week-content-calendar`](../260629-2354-thien-dao-4-week-content-calendar/plan.md) — định *cái gì/khi nào*; plan này định *làm thế nào*. Mục "Quy tắc áp cho MỌI video" trong calendar nên trỏ tới SOP doc sau khi tạo. Hai plan chạy độc lập, không có blocker cứng.
