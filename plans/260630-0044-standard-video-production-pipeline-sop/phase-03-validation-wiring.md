---
phase: 3
title: Validation & wiring
status: completed
priority: P2
dependencies:
  - 1
  - 2
---

# Phase 3: Validation & wiring

> Cập nhật theo hướng library (Phase 2): validate **hàm trong lib** + 1 skeleton long-form, KHÔNG validate 1 config run monolithic.

## Overview
Chứng minh các hàm `montage_lib.py` tái tạo được kết quả thật trên asset project cũ, exercise cả khâu dựng của format long-form (ngủ 30–60′ — format tăng trưởng chính nhưng chưa từng build), rồi nối doc ↔ lib ↔ plan lịch nội dung.

## Requirements
- Functional: thin driver dùng lib dựng lại từ asset có sẵn của `projects/bon-mua-cua-hoi-tho` → video hợp lệ (exercise concat + narration_track + duck_mux + make_card + remux).
- Functional: **long-form `validate` skeleton** — 1 thin driver tối thiểu dựng cấu trúc video ngủ (intro + N block lặp dài + outro) bằng asset placeholder/sẵn có, đủ exercise đường dài (đóng giả định probe #1: format ngủ chưa được chứng minh). **Phải exercise hàng trăm cue narration** để chứng minh batch/cây amix (#scenario #4), KHÔNG chỉ vài block.
- Functional: QA gate theo SOP Stage 8 — `ffprobe` (codec/độ phân giải/duration) + `silencedetect` (timeline giọng) + đo audio level.
- Functional: **Copyright gate CỨNG (blocking, không tuỳ chọn)** — `ffprobe -show_entries format_tags` kiểm không còn tag nhạc bản quyền (Kevin MacLeod...); xác nhận nhạc = AI/Content-ID-safe. Là điều kiện chặn publish, không phải gợi ý.
- Functional: tham chiếu chéo — doc trỏ lib; lib README trỏ doc; cập nhật plan lịch nội dung trỏ SOP doc.
- Non-functional: không sửa file render đã đăng của project (chỉ đọc asset, ghi ra path tạm).

## Architecture
- Viết thin driver tạm `scripts/video/_validate_bonmua.py` import lib, ánh xạ timeline thật bon-mua → gọi các hàm; chạy → so độ dài/segment với log gốc (`TOTAL DURATION`).
- Viết thin driver tạm `scripts/video/_validate_longform.py` — cấu trúc ngủ rút gọn (vài block thay vì hàng trăm) đủ kiểm đường dựng dài + duck_mux + offset helper.
- QA bằng lệnh ffprobe/silencedetect (hoặc helper nhỏ) kiểm output.
- Wiring: thêm 1 dòng link trong `plans/260629-2354-thien-dao-4-week-content-calendar/plan.md` mục "Quy tắc áp cho MỌI video" → `docs/video-production-pipeline.md`.

## Related Code Files
- Create: `scripts/video/_validate_bonmua.py`, `scripts/video/_validate_longform.py` (driver tạm, có thể giữ làm ví dụ)
- Modify: `plans/260629-2354-thien-dao-4-week-content-calendar/plan.md` (thêm link SOP doc)
- Modify: `docs/video-production-pipeline.md` (chốt link lib sau khi lib ổn)
- Read: asset trong `projects/bon-mua-cua-hoi-tho/assets/`

## Implementation Steps
1. Viết `_validate_bonmua.py` từ timeline thật bon-mua, gọi hàm lib; chạy → không lỗi + ra video tạm.
2. Viết `_validate_longform.py` cấu trúc ngủ rút gọn; chạy → exercise concat dài + narration offset helper + duck_mux.
3. QA: `ffprobe` (1080p? duration khớp?), `silencedetect` (giọng đúng nhịp), đo loudness cả 2 output, **`ffprobe format_tags` (copyright gate cứng — không còn tag nhạc bản quyền)**.
4. So tổng thời lượng / số segment với log gốc bon-mua để xác nhận tái tạo trung thực.
5. Cập nhật cross-reference: doc↔lib README, calendar plan→doc.
6. Ghi hạn chế còn tồn (validate chỉ xác nhận recipe FFmpeg, không xác nhận provider/asset-gen theo máy).

## Success Criteria
- [ ] Driver bon-mua qua lib ra video hợp lệ; thời lượng/segment khớp log gốc (sai số chấp nhận được).
- [ ] Long-form skeleton chạy qua lib không lỗi (đường dựng dài + offset helper + duck được exercise), có **hàng trăm cue** chứng minh batch amix không OOM.
- [ ] ffprobe + silencedetect pass cả 2.
- [ ] Copyright gate cứng: `ffprobe format_tags` xác nhận không còn tag nhạc bản quyền trên output.
- [ ] Calendar plan có link tới SOP doc; doc↔lib README trỏ nhau.
- [ ] Không động vào render đã đăng.

## Risk Assessment
- **Asset cũ thiếu/đổi path** → dùng `tap-trung-thien-dinh` hoặc placeholder; ghi rõ phạm vi validate.
- **Tốn TTS/Veo quota** → chỉ validate khâu dựng (dùng narration/clip/placeholder sẵn), KHÔNG sinh asset mới.
- **Long-form skeleton ≠ video ngủ thật** → skeleton chỉ chứng minh đường dựng chịu được độ dài + cấu trúc lặp; không thay video thật. Ghi chú rõ.
