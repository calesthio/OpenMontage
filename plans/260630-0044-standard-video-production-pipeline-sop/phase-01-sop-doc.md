---
phase: 1
title: SOP doc
status: completed
priority: P1
dependencies: []
---

# Phase 1: SOP doc

## Overview
Viết `docs/video-production-pipeline.md` — SOP 9 stage đọc-làm-theo cho mọi video kênh Thiền Đạo, nạp sẵn locked defaults + fallback tree. Đây là nguồn sự thật quy trình; Phase 2 (script) chỉ hiện thực hoá khâu dựng của doc này.

## Requirements
- Functional: phủ đủ Stage 0–8 từ brainstorm report; mỗi stage có Output · Default khoá · Quality gate · Cạm bẫy.
- Functional: bảng Locked Defaults + cây quyết định fallback (text/ascii).
- Functional: tách rõ "lõi dùng chung" vs "tham số riêng thiền".
- Non-functional: tiếng Việt, concise (hy sinh ngữ pháp), ≤ docs.maxLoc (800 dòng), không trùng lặp brainstorm report (doc là bản thực thi, không phải bản phân tích).

## Architecture
Nguồn nội dung = brainstorm report §4–§7. Doc này là bản "operational" rút gọn: bỏ phần so sánh hướng A/B/C/D, giữ pipeline + defaults + fallback. Cấu trúc:
1. Mục đích + phạm vi + điều kiện môi trường (Stage 0 envelope thực: ElevenLabs✓, Imagen✓ service-account, Veo-qua-Gemini✓, fal=403, FFmpeg✓, Remotion✗/HyperFrames✓).
2. 9 stage stage-by-stage.
3. Bảng Locked Defaults (Phụ lục A report).
4. Cây fallback (Phụ lục B report).
5. Split lõi-chung / riêng-thiền (report §5).
6. Trỏ tới `scripts/video/montage_lib.py` (recipe library, Phase 2) cho Stage 6–7.

## Related Code Files
- Create: `docs/video-production-pipeline.md`
- Read (nguồn): `plans/reports/brainstorm-260630-0037-thien-dao-standard-video-pipeline-report.md`
- Reference (không sửa lần này): `docs/codebase-summary.md` / `docs/system-architecture.md` nếu tồn tại — chỉ để khớp giọng doc.

## Implementation Steps
1. Đọc lại brainstorm report để lấy nội dung đã chốt.
2. Viết doc theo cấu trúc trên; mỗi stage 1 khối ngắn (Output/Default/Gate/Cạm bẫy).
3. Nhúng bảng Locked Defaults + cây fallback nguyên trạng từ report (đã súc tích).
4. Thêm mục "Điều kiện môi trường" cảnh báo default đúng-theo-máy (Veo-qua-Gemini, fal=403, service-account JSON, Remotion chưa cài) → chạy lại Stage 0 nếu đổi máy/key.
5. Thêm liên kết tới recipe library `montage_lib.py` (Phase 2) cho Stage 6–7 và tới plan lịch nội dung.
6. Kiểm độ dài < 800 dòng; cắt phần lý thuyết thừa.

## Success Criteria
- [ ] `docs/video-production-pipeline.md` tồn tại, đủ Stage 0–8.
- [ ] Có bảng Locked Defaults + cây fallback.
- [ ] Có mục split lõi-chung/riêng-thiền + cảnh báo điều kiện môi trường.
- [ ] Trỏ tới recipe library + plan lịch nội dung.
- [ ] ≤ 800 dòng, tiếng Việt, không sao chép nguyên phần phân tích A/B/C/D của report.

## Risk Assessment
- **Trùng lặp report** → doc thành bản nhái. Mitigation: doc chỉ giữ phần thực thi (pipeline+defaults+fallback), report giữ phần "tại sao".
- **Default lỗi thời theo máy** → Mitigation: mục điều kiện môi trường ghi rõ, không trình bày như chân lý vĩnh viễn.
