---
title: intent-analyst Meta Skill — Design (Intent Analysis for OpenMontage Pipeline Routing)
type: brainstorm-report
date: 2026-06-30
slug: intent-analyst-meta-skill-design
parent_report: brainstorm-260630-2346-videoagent-architecture-pipeline-applicability-report.md
inspiration: HKUDS/VideoAgent — Intent Analysis (explicit + implicit sub-intents → intent-to-agent mapping)
modes: [brainstorm]
status: design-approved (no implementation)
---

# intent-analyst Meta Skill — Brainstorm Report

## 1. Problem statement

OpenMontage chọn pipeline kiểu **"match hoặc hỏi"** (AGENT_GUIDE Rule Zero step 1: match request → pipeline trong `pipeline_defs/`, hỏi nếu unclear) — phán đoán ngầm, không artifact, không phân rã ngầm ý. VideoAgent có **Intent Analysis** (phân rã yêu cầu thành sub-intent tường minh + ngầm định → map intent→agent). Port pattern này thành meta skill `intent-analyst.md` chạy trước pipeline-selection để: route chuẩn hơn, phát hiện implicit needs, hỗ trợ request ghép (compound).

## 2. Scout findings (grounded)

- **Chưa có** bước intent-decomposition chính thức trong OpenMontage.
- **Đã có 3 skill "hiểu user"** dễ chồng lấn: `skills/meta/onboarding.md` (first-contact mơ hồ → capability menu), `skills/meta/creative-intake.md` (7-question brief, xuất `intake_brief` informal), `skills/meta/video-reference-analyst.md` (URL tham chiếu → VideoAnalysisBrief).
- Substrate intent→pipeline sẵn có: bảng "Best For" trong `AGENT_GUIDE.md` + field `best_for` mỗi pipeline manifest.
- Convention meta skill: **instruction-only, KHÔNG schema** (creative-intake xuất artifact informal, không validate) — phải tôn trọng.

## 3. Decisions captured (Discovery Phase)

| # | Quyết định | Chọn |
|---|---|---|
| Output | Hình thức triển khai | **Meta skill mới (A)** — `skills/meta/intent-analyst.md` + wiring |
| Multi-pipeline | Route ghép? | **Có, hỗ trợ compound** (chuỗi pipeline) |
| Concept seed | Sinh concept? | **Chỉ định tuyến + capability** (không sinh concept) |
| Trigger | Khi nào chạy? | **Luôn chạy** (kèm fast-path cho request rõ) |

## 4. Approaches evaluated

| Approach | Mô tả | Verdict |
|---|---|---|
| **A. Meta skill độc lập** | `intent-analyst.md` chạy ở Rule Zero step 1, conditional fast-path, xuất `intent_map` informal | ✅ **Chọn** — đúng convention, rõ ràng, tái dùng |
| B. Nhúng vào Rule Zero + creative-intake | Không file mới; thêm bước implicit-intent vào skill cũ | ❌ Dễ bị chôn vùi, trigger không ổn định |
| C. Schema + reflection loop | `intent_brief` validate JSON + reflection (bám VideoAgent sát) | ❌ Over-engineer; phá convention meta-skill không schema (YAGNI) |

## 5. Final design (approved)

### 5.1 Ranh giới vai trò (chống trùng lặp — trọng yếu)

| Skill | Câu hỏi trả lời | Khi nào | Output |
|---|---|---|---|
| `onboarding` | User làm được gì với setup? | First-contact mơ hồ | Capability menu + starter prompts |
| `video-reference-analyst` | Video tham chiếu làm gì? | Có URL/file tham chiếu | VideoAnalysisBrief |
| **`intent-analyst`** | **Request cần pipeline + capability nào?** | **Mọi actionable request, trước pipeline-selection** | **`intent_map` informal** |
| `creative-intake` | Brief còn thiếu gì? | Sau khi biết hướng | `intake_brief` informal |

Luồng: `onboarding`/`reference-analyst` (entry) → **`intent-analyst` (route)** → pipeline selection → `creative-intake` (lấp brief) → research.

Nguyên tắc cứng: **intent-analyst KHÔNG hỏi user** — chỉ đánh dấu `open_ambiguities` để creative-intake xử lý. Tránh thẩm vấn 2 lần.

### 5.2 Cấu trúc `intent_map` (informal, không schema)

```
explicit_intents:   [user nói thẳng]
implicit_intents:   [suy ra: hook giữ chân, platform→tỉ lệ khung, nhạc nền...]
routed_pipelines:   [1..n; compound được; mỗi cái kèm lý do + thứ tự]
capability_needs:   [tts, image_gen, music, video_gen → map capability registry]
open_ambiguities:   [điều creative-intake cần làm rõ — KHÔNG tự hỏi]
confidence:         high | medium | low
```

Context informal chuyển cho pipeline-selection + creative-intake. Không validate.

### 5.3 Compound routing

- Phát hiện ≥2 deliverable độc lập → đề xuất **chuỗi pipeline** (vd `animated-explainer` → `clip-factory`) kèm thứ tự + luồng dữ liệu giữa các pipeline (output cái trước → input cái sau).
- Mỗi pipeline trong chuỗi vẫn chạy full Rule Zero riêng (preflight, checkpoint). intent-analyst **chỉ đề xuất**, không tự thực thi.
- `confidence: low` / compound mơ hồ → trình chuỗi cho user xác nhận trước khi vào pipeline đầu.

### 5.4 Fast-path (hòa giải "luôn chạy")

- Request khớp đúng 1 pipeline + capability rõ → `intent_map` rút gọn 3 dòng + 1 câu xác nhận → đi tiếp ngay.
- Request mơ hồ/ghép/ngầm ý → `intent_map` đầy đủ; confidence không cao thì trình user.
- "Luôn chạy" = luôn **phân loại**, không phải luôn **thẩm vấn**.

### 5.5 Source of truth

intent-analyst đọc bảng "Best For" trong `AGENT_GUIDE.md` + `best_for` mỗi manifest để map — **không hardcode** danh sách pipeline (chống drift).

## 6. Touchpoints (khi implement)

- **Tạo mới:** `skills/meta/intent-analyst.md`
- **Sửa:**
  - `AGENT_GUIDE.md` — Rule Zero step 1: chèn intent-analyst trước "identify pipeline"; thêm vào reading order.
  - `skills/meta/creative-intake.md` — nhận `intent_map`, không lặp phân rã; chỉ xử lý `open_ambiguities`.
  - `skills/meta/onboarding.md` — handoff sang intent-analyst khi user chuyển sang actionable request.
  - `skills/meta/video-reference-analyst.md` — handoff: VideoAnalysisBrief → intent-analyst.
  - `skills/INDEX.md` — đăng ký skill mới.

## 7. Scope boundary (OUT)

Không JSON schema, không reflection loop, không sinh concept seed, không đổi code/tool Python, không thêm pipeline mới.

## 8. Acceptance criteria

1. Với 1 actionable request, agent sinh `intent_map` (explicit + implicit + routed_pipelines + capability_needs + confidence) **trước** pipeline-selection.
2. Request rõ ràng 1-pipeline → fast-path 3 dòng, không thêm câu hỏi.
3. Request ghép → đề xuất chuỗi pipeline kèm thứ tự + luồng dữ liệu, chờ user xác nhận.
4. intent-analyst không hỏi user trực tiếp; ambiguity đẩy sang creative-intake.
5. Không trùng lặp thẩm vấn với creative-intake (kiểm bằng đọc cả 2 skill sau sửa).
6. Map pipeline đọc từ AGENT_GUIDE, không hardcode.

## 9. Success metrics

- Tỉ lệ route đúng pipeline ngay lần đầu tăng (ít phải đổi pipeline giữa chừng).
- Request ghép được nhận diện + lên chuỗi đúng thay vì làm thiếu deliverable.
- Số câu hỏi lặp giữa intent-analyst và creative-intake ≈ 0.
- Request rõ ràng không bị chậm thêm (fast-path).

## 10. Risks & mitigations

| Rủi ro | Giảm thiểu |
|---|---|
| Trùng creative-intake | Bảng ranh giới §5.1 + quy tắc "không hỏi, chỉ đánh dấu open_ambiguities" |
| Ceremony thừa cho request rõ | Fast-path §5.4 |
| Route sai pipeline | confidence thấp → xác nhận user; không tự thực thi compound |
| Drift với pipeline list | Đọc "Best For" AGENT_GUIDE làm nguồn sự thật |
| Compound thực thi sai thứ tự | intent-analyst chỉ đề xuất; mỗi pipeline chạy Rule Zero riêng |

## 11. Next steps

- Handoff `/ck:plan` (default mode) với report này làm context — đây là thêm meta skill + wiring (instruction-only, không refactor logic nghiệp vụ nên không cần `--tdd`).

## 12. Unresolved questions

- `confidence` nên là enum (high/medium/low) hay bỏ, để agent tự phán đoán bằng văn xuôi? (hiện chốt enum cho rõ).
- Compound routing: có giới hạn số pipeline trong 1 chuỗi không (vd tối đa 3) để tránh kế hoạch phình to?
- Có cần ví dụ mẫu (few-shot) trong skill cho 2-3 case compound điển hình của user (thiền/nhạc long-form) không?
