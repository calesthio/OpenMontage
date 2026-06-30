---
title: VideoAgent (HKUDS) Architecture Study + Pipeline Applicability for OpenMontage
type: brainstorm-report
date: 2026-06-30
slug: videoagent-architecture-pipeline-applicability
source_repo: https://github.com/HKUDS/VideoAgent
source_paper: https://arxiv.org/abs/2606.23327
session_goal: Explain VideoAgent architecture; map applicable patterns to OpenMontage
modes: [brainstorm]
status: analysis-only (no implementation)
---

# VideoAgent → OpenMontage: Brainstorm Report

## 1. Problem statement

User request: study lại kiến trúc repo HKUDS/VideoAgent, phân tích pipeline/pattern nào áp dụng được cho OpenMontage. Goal phiên: **giải thích kiến trúc** (không implement), kèm map cả 4 hướng áp dụng.

## 2. VideoAgent — kiến trúc (grounded từ source)

Bản chất: **"LLM-as-compiler"** — không chạy pipeline cố định; LLM (backbone Claude) biên dịch yêu cầu NL thành **DAG agent có kiểu** (cạnh nối output-param → input-param), kèm vòng reflection.

### Abstraction lõi

| Thành phần | File | Vai trò |
|---|---|---|
| **Role = BaseTool tự mô tả** | `environment/agents/base.py` | Mỗi role có `InputSchema`/`OutputSchema` (Pydantic) + `execute()`. `FunctionRegistry.auto_register("environment/roles")` quét thư mục → metadata `{name, description=docstring, input_params, output_params}` **kèm type + mô tả từng param**. |
| **Intent layer** | `environment/config/intents.yml` + `multi.py:intents_analysis` | `intents.yml` map intent (vd `Rhythm-cut`, `Commentary`, `Singing Voice Conversion`) → list role. LLM chọn nhiều intent liên quan → `get_tools_by_intents` gom tập role ứng viên (thu hẹp không gian tool). |
| **Graph Designer** | `environment/config/graph.txt` (prompt) + `multi.py:generate_agent_graph` | LLM nhận yêu cầu + metadata role → JSON 5 trường: `Feasibility`, `Agent Graph` (DAG: mỗi output có `links[]` trỏ `{agent kế: input param}`), `Agent Chain` (topo order), `User Input Graph` (param no-in-degree → user nhập), `Reasoning`. Ràng buộc cứng: link trỏ input có thật + **kiểu khớp** (file-path ≠ dir-path). |
| **Reflection loop** | `multi.py` (`MAX_Retries=3`) | Cả intent lẫn graph có biến thể "reflection": validate fail (thiếu trường / JSON hỏng / graph vô lý) → feed lại artifact cũ + lý do → LLM refine. Đây là "two-step self-evaluation" cho success rate ~0.95. |
| **Multi-modal / Video-RAG** | `tools/videorag` + ImageBind; roles `vid_searcher`, `vid_preloader` | Storyboard Agent: material bank **pre-caption**, embedding đa modal, phân rã query → sub-query → retrieve clip khớp ngữ nghĩa cho từng beat. |

### Runtime flow

```
User NL → Intent Analysis (LLM chọn intents)
        → get_tools_by_intents (role metadata có typed I/O)
        → Graph Designer (LLM sinh DAG + Chain + UserInputGraph)
        → Feasible & valid JSON? — No (<3 lần) → Reflection (graph cũ + lý do) → lặp
                                  — Yes → chạy Agent Chain theo topo
        → videorag/ImageBind retrieve clip từ caption bank (khi footage-led)
```

### Phạm vi chức năng (3 trụ): Understanding (QA, summarization), Editing (movie edit, commentary, video overview), Remaking (meme, music/SVC, cross-cultural). Roles creative-remaking OpenMontage chưa có: **rhythm-cut (beat-synced)**, **commentary**, **news**, **SVC**, **stand-up**, **cross-talk**.

Backbone: Claude (`config/llm.py`). GPU ≥8GB cho model local (CosyVoice/fish-speech TTS, DiffSinger hát, seed-vc, ImageBind).

## 3. Đối chiếu OpenMontage

| Khía cạnh | VideoAgent | OpenMontage |
|---|---|---|
| Định tuyến | Workflow **động** do LLM biên dịch (DAG) | Pipeline **cố định** khai báo YAML + director skill |
| Tool contract | Typed I/O schema từng param (nối dây được) | Contract giàu (`capability`, `provider`, `supports`, `fallback_tools`, `agent_skills`) **nhưng thiếu typed param-level I/O** |
| Self-eval | Reflection có validate cứng + metric | Reviewer advisory, max 2 vòng, **không block/không đo** |
| Footage | Video-RAG retrieval over caption bank | Thiên **generation**; footage-led pipeline chưa có semantic retrieval |
| Triết lý chung | Agent-first, Python = tool | Agent-first, Python = tool (**tương thích substrate**) |

## 4. Bốn hướng áp dụng (đánh giá thẳng)

| # | Pattern | Giá trị | Hợp triết lý | Effort |
|---|---|---|---|---|
| 1 | Graph workflow synthesis | Cao | ⚠️ đụng Rule Zero | Cao |
| 2 | Intent Analysis (explicit+implicit) | Trung bình–cao | ✅ | Thấp |
| 3 | Self-eval loop có metric | Trung bình | ✅ | Trung bình |
| 4 | Video-RAG / clip retrieval | Cao nhất (gap chức năng) | ✅ | Cao nhất |
| 5 | Creative pipelines (rhythm-cut/commentary/SVC) | Trung bình | ✅ | Trung bình–cao mỗi cái |

### #1 Graph workflow synthesis — mạnh nhất, rủi ro triết lý cao
- Substrate sẵn: `base_tool.py` + `capability_catalog()`/`support_envelope()`. Thiếu: **typed I/O schema từng param**.
- Áp dụng: chỉ làm **escape hatch** khi request không khớp pipeline nào — KHÔNG thay pipeline cố định.
- Cảnh báo: đụng Rule Zero ("mọi production qua fixed pipeline, không ad-hoc"). Adopt nguyên xi → phá governance + mất chất lượng director-skill.

### #2 Intent Analysis — quick win, hợp nhất
- Thêm meta skill `intent-analyst.md` chạy trước pipeline-selection: phân rã sub-intent tường minh + ngầm định → map pipeline + tổ hợp capability + concept tốt hơn. Hợp với "Reference Video Entry Point" + onboarding hiện có.

### #3 Self-eval gate có metric
- Ở `scene_plan`/`edit`: validate cứng artifact theo `schemas/artifacts/` → fail thì reflection-refine (giống graph designer), thay vì "note and proceed". Tận dụng schema sẵn có.

### #4 Video-RAG / clip retrieval — giá trị cao nhất, nặng nhất
- Capability mới `video_searcher` + `storyboard`: pre-caption material bank (tận dụng `analysis` capability: transcription/scene-detect/frame-sampling), embedding, retrieve clip cho từng beat của `scene_plan`.
- v1 rẻ: caption-text-only retrieval (không GPU). v2: ImageBind/CLIP multimodal (cần GPU/cloud).
- Là **dự án con riêng** — không gộp chung phiên.

### #5 Creative pipelines — để sau
- `rhythm-cut` (beat-synced) + `commentary` hợp content thiền/nhạc. Là pipeline mới (manifest + 7 director skill), không đổi kiến trúc. Brainstorm từng cái riêng.

## 5. Khuyến nghị thứ tự
1. **#2 Intent Analysis** — quick win, nâng routing ngay.
2. **#3 Self-eval gate** — tái dùng schema, nâng chất lượng artifact.
3. **#4 Video-RAG** — dự án con riêng, giá trị cao nhất.
4. **#1 Graph synthesis** — chỉ dạng escape hatch, sau #2/#3.
5. **#5** — pipeline mới, brainstorm riêng từng cái.

## 6. Success metrics (nếu triển khai)
- #2: tỉ lệ chọn đúng pipeline ngay lần đầu tăng; ít vòng hỏi lại.
- #3: tỉ lệ artifact pass schema lần đầu; số finding critical giảm.
- #4: recall/IoU clip retrieval (theo metric của paper: Recall, embedding-match, temporal IoU).
- #1: tỉ lệ graph "Feasible" + chạy được không lỗi nối-dây.

## 7. Rủi ro chính
- #1 phá Rule Zero nếu không giới hạn là fallback.
- #4 phụ thuộc GPU nếu chọn multimodal embedding — mitigate bằng v1 text-only.
- Mất chất lượng director-skill nếu chuyển quá nhiều case sang workflow động.

## 8. Unresolved questions
- OpenMontage có sẵn sàng bổ sung **typed param-level I/O schema** vào tool contract không? (điều kiện tiên quyết cho #1, hữu ích cho #3).
- Material bank cho #4 lấy từ đâu (user upload / stock / footage cũ)? Quy mô bao nhiêu clip?
- Backbone embedding cho #4: chấp nhận GPU local (ImageBind) hay ưu tiên cloud/text-only?
- Ưu tiên thực thi sắp tới: nâng routing/quality (#2/#3) hay mở chức năng footage-led (#4)?
