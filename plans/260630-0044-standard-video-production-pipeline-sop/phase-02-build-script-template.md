---
phase: 2
title: Recipe library + offset helper
status: completed
priority: P1
dependencies:
  - 1
---

# Phase 2: Recipe library + offset helper

> Đổi hướng sau ck:predict --chain reason (CAUTION → library): KHÔNG làm driver monolithic + config schema. Thay bằng **thư viện recipe** + per-video thin driver. Lý do: 3 video cũ khác nhau nhiều → 1 config schema bị over-fit; giá trị thật là DRY hoá recipe FFmpeg đã chứng minh.

## Overview
Trích 6 recipe FFmpeg đã chạy thật từ `projects/bon-mua-cua-hoi-tho/build_meditation_video.py` thành thư viện thuần `scripts/video/montage_lib.py` (hàm tham số hoá, không global) + 1 helper tính offset narration. Mỗi video giữ thin driver bespoke import lib. Phủ Stage 6–7 (Edit & Mix + Compose) của SOP.

## Requirements
- Functional: `montage_lib.py` cung cấp **≤6 hàm** (bề mặt chặt, không thành bãi rác):
  1. `concat_segments(paths, out, reencode=True)` — re-encode an toàn 30fps/yuv420p khi segment khác tham số; `-c copy` khi đồng nhất.
  2. `build_narration_track(cues, total, out, reverb=False)` — per-cue `adelay` tới offset tuyệt đối + `bass`/`aecho` tuỳ chọn + `amix normalize=0`. **Scale:** với video dài (hàng trăm cue) KHÔNG amix N input 1 lần (OOM / arg-too-long) → gộp theo **batch/cây** (mix từng nhóm ~30 cue rồi mix các nhóm). Bỏ qua cue rỗng/`…`.
  3. `duck_mux(video, narration, music, out, music_vol, loudnorm_I=-16)` — music `atrim`+`volume`+`afade`, **sidechain duck**, `amix duration=first`, `alimiter`/loudnorm.
  4. `make_card(scene_or_bg, text_big, text_small, dur, out)` — intro/outro card, `drawtext` **`textfile=`** UTF-8 + arialbd.ttf, fade alpha.
  5. `remux_audio(video_silent, audio, out)` — `-c:v copy -map 0:v -map 1:a` đổi nhạc không dựng lại hình. **Guard bắt buộc:** chỉ nhận video **silent/clean** (không sẵn audio track) → kiểm bằng ffprobe, raise nếu video đã có audio (tránh 2 lớp nhạc chồng — bẫy thật).
  6. `slow_loop_scene(scene, dur, out, pts=1.2)` — stream-loop + setpts phủ độ dài.
- Functional: helper `narration_offsets_from_durations(sentences, gaps)` — tính offset tuyệt đối từ độ dài từng câu TTS (+ khoảng lặng), cho phép **manual override**. Triệt lớp lỗi offset thủ công (bug `narration_dry`).
- Security: **không `shell=True` với text người dùng** — truyền path/text qua subprocess **arg list**; drawtext luôn qua `textfile=`. (Sửa rủi ro injection từ script gốc dùng `shell=True` + f-string.)
- **Robustness (vá sau ck:scenario):**
  - **Idempotent compose:** mỗi segment render ra file riêng, **skip nếu đã tồn tại** (sống sót crash/Ctrl-C giữa render dài; theo pattern "tự skip clip đã có" của script gốc). Render dở phải re-runnable, không mất toàn bộ.
  - **Fail-fast:** asset path thiếu → raise `missing asset <path>` rõ ràng (KHÔNG tạo video đen/câm). FFmpeg nonzero → in `stderr[-1500:]` rồi raise (giữ pattern gốc).
  - **Overflow check:** với mỗi cue kiểm `offset+dur ≤ total`; cảnh báo nếu narration tràn khỏi độ dài video.
  - **Encoding/locale:** ép `PYTHONUTF8`/utf-8 cho drawtext tiếng Việt; parse `ffprobe duration` an toàn (không vỡ vì locale dấu phẩy thập phân). Kiểm font tồn tại trước drawtext, lỗi rõ nếu thiếu.
- Non-functional: hàm thuần, không đọc global/biến môi trường; tự-document bằng comment; snake_case. Giữ nguyên chuỗi filter đã chạy thật, chỉ tham số hoá giá trị (không tái cấu trúc graph).

## Architecture
- **Library** `scripts/video/montage_lib.py`: 6 hàm recipe + helper offset. Mỗi hàm nhận tham số rõ ràng, trả path output, raise lỗi có thông điệp khi FFmpeg fail.
- **Per-video thin driver**: mỗi project giữ `build.py` riêng (bespoke timeline) **import** lib — bon-mua/tap-trung làm reference driver, KHÔNG ép vào 1 schema chung. Orb pacer (`render_breath_segment`) ở lại driver bon-mua như code riêng-thiền, KHÔNG nhồi vào lib.
- **TTS tách rời**: driver quyết định provider/voice (ElevenLabs re-fetch voice_id, hoặc google_tts, hoặc đọc file narration sẵn). Lib chỉ lo dựng/mix, không gọi TTS.

Recipe gốc tham chiếu (đã đọc): narration amix dòng 188–198; final mux dòng 200–211; card `render_text_segment` dòng 122–133; concat dòng 181–186; slow loop dòng 112/132.

## Related Code Files
- Create: `scripts/video/montage_lib.py`
- Create: `scripts/video/README.md` (mô tả 6 hàm + ví dụ thin driver tối thiểu)
- Read (nguồn trích): `projects/bon-mua-cua-hoi-tho/build_meditation_video.py`, `rebuild_audio_bells.py`, `rebuild_audio_dry.py`
- Reference: `docs/video-production-pipeline.md` (Phase 1) — lib là hiện thực Stage 6–7.

## Implementation Steps
1. Tạo `scripts/video/` (kiểm `scripts/` đã có chưa).
2. Port 6 recipe generic từ script gốc thành hàm thuần, bỏ global, nhận tham số, subprocess arg-list (bỏ `shell=True` cho text).
3. Viết `narration_offsets_from_durations()` (auto từ duration + manual override).
4. Viết `README.md` với ví dụ thin driver gọi lib dựng intro+1 segment+outro.
5. Thêm robustness: skip-existing segment, fail-fast missing-asset, overflow check, remux silent-source guard, ép PYTHONUTF8 + parse duration an toàn + check font.
6. Comment rõ recipe nhạy cảm: sidechain duck, loudnorm, drawtext textfile, escape font Windows (`C\:/...` giữ nguyên cách đã chạy).
7. KHÔNG tạo config schema / driver monolithic (YAGNI — đã bỏ sau reason loop).

## Success Criteria
- [ ] `scripts/video/montage_lib.py` (≤6 hàm + offset helper) + `README.md` tồn tại.
- [ ] Hàm thuần, không global; subprocess arg-list, không `shell=True` cho text người dùng.
- [ ] `narration_offsets_from_durations` có auto + manual override.
- [ ] Recipe sidechain duck / loudnorm / drawtext UTF-8 / remux có mặt + comment.
- [ ] `build_narration_track` mix theo batch/cây (chịu được hàng trăm cue, không OOM).
- [ ] Segment render idempotent (skip-existing) → re-runnable sau crash.
- [ ] `remux_audio` raise khi nhận video đã có audio (guard 2-lớp-nhạc).
- [ ] Fail-fast: missing asset + narration overflow được raise/cảnh báo rõ.
- [ ] Không tạo config schema monolithic.

## Risk Assessment
- **Filter graph dễ vỡ khi general hoá** → giữ nguyên chuỗi filter bon-mua đã chạy, chỉ tham số hoá.
- **Lib phình thành bãi rác** → cứng giới hạn ≤6 hàm; logic riêng-thiền (orb) ở lại driver.
- **Path/escape Windows** → giữ cách escape font gốc; test trên máy này.
