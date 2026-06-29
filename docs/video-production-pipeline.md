# Pipeline Sản Xuất Video Chuẩn — Kênh Thiền Đạo

SOP đọc-làm-theo cho mọi video kênh **Thiền Đạo - Giác Ngộ Tâm Trí**, sản xuất bằng OpenMontage. Nạp sẵn các quyết định đã đúc kết qua 3 video đầu (`projects/bon-mua-cua-hoi-tho`, `tap-trung-thien-dinh`, `hieu-doi-truyen-cam-hung`).

- **Bản phân tích "tại sao":** [`plans/reports/brainstorm-260630-0037-thien-dao-standard-video-pipeline-report.md`](../plans/reports/brainstorm-260630-0037-thien-dao-standard-video-pipeline-report.md)
- **Khâu dựng (Stage 6–7):** dùng recipe library `scripts/video/montage_lib.py`
- **Lịch nội dung / chiến lược kênh:** [`plans/260629-2354-thien-dao-4-week-content-calendar`](../plans/260629-2354-thien-dao-4-week-content-calendar/plan.md)

---

## Điều kiện môi trường (ĐỌC TRƯỚC)

Các default dưới đây đúng **trên máy hiện tại**, KHÔNG phải chân lý vĩnh viễn. Đổi máy / đổi key → chạy lại **Stage 0** rồi cập nhật.

- ElevenLabs TTS ✓ · Google Imagen 4 ✓ (cần service-account JSON) · Veo qua Gemini REST ✓
- **fal.ai = 403** (Veo/Kling/Seedance/flux qua fal đều bị chặn — FAL_KEY không có quyền)
- FFmpeg ✓ · **Remotion ✗ (chưa cài)** / HyperFrames ✓
- Registry báo "available" theo *có env var*, KHÔNG theo *key đúng* → silent-availability. Tin lần chạy thật, không tin nhãn.

---

## Pipeline 9 Stage

Bám flow OpenMontage `research → proposal → script → scene_plan → assets → edit → compose`, thêm Publish.

### Stage 0 — Preflight (1 lần/máy, hoặc khi đổi key)
- **Làm:** `registry.provider_menu_summary()` → xác nhận envelope thực.
- **Output:** danh sách provider thật sự chạy được (xem Điều kiện môi trường).
- **Gate:** không bắt đầu sản xuất tới khi biết rõ provider nào sống.

### Stage 1 — Concept & Brief
- **Output:** brief — lane, tiêu đề, thời lượng, nền tảng, tone, phụ đề (y/n).
- **Default khoá:** lane = **guided practice** ưu tiên (philosophy = playlist phụ, không trộn timeline thực hành). Nền tảng = **16:9 YouTube 1080p**.
- **Title formula:** `[Lợi ích/Kết quả] + [Thời lượng] + [Phương pháp]`, front-load keyword, **không emoji giữa dòng**.
- **Gate:** brief khớp lane; nếu philosophy essay → đánh dấu "biến thể essay" (xem §Tách lõi/thiền).

### Stage 2 — Script
- **Output:** `artifacts/script.md` (full, có cue cảnh) **+** `artifacts/script-narration-only.md` (chỉ lời cho TTS).
- **Default khoá:** chương tuyến tính (định→tuệ với thiền), mỗi chương 3–5′, có **câu chuyển chương** giữ retention; mở bằng ẩn dụ mạnh.
- **Cạm bẫy:** TTS chỉ đọc file narration-only — đừng để cue cảnh lọt vào giọng.

### Stage 3 — Narration (lõi, dễ sai nhất)
- **Output:** `assets/audio/chuong-*.mp3` + `narration-full.mp3`.
- **Default khoá:** ElevenLabs **giọng "Chau Nguyen"** (cloned) + model **`eleven_v3`**, stability 0.5 / similarity 0.75 / style 0.
- **BẮT BUỘC:** **re-fetch voice_id mỗi lần** — `GET https://api.elevenlabs.io/v1/voices` (header `xi-api-key`), tìm `name=="Chau Nguyen"` (category cloned). **KHÔNG hardcode** (id đổi khi user re-clone).
- **Nhịp thiền:** ElevenLabs không có speaking_rate → nhịp = **chèn silence**: 0.7s/câu · 1.8s/đoạn · 3.5s cho dòng `…`. Render **từng câu** → ghép FFmpeg concat (wav LINEAR16 24k mono) → encode mp3.
- **Gate:** render **SAMPLE 1 chương** cho user duyệt **trước** khi render full.
- **Fallback:** google_tts `vi-VN-Chirp3-HD-<Charon/Iapetus>` rate≈0.82 — **cần service-account JSON** (`GOOGLE_APPLICATION_CREDENTIALS`), API key bị 401.

### Stage 4 — Visuals
- **Output:** `assets/reference/*.png` + `assets/video/*.mp4`.
- **Default khoá:**
  1. Sinh **ảnh reference thiền giả** bằng `google_imagen` (imagen-4.0, **16:9** — ref 3:4 gây viền đen).
  2. Sinh clip **Veo qua Gemini REST**: `POST .../models/veo-3.1-generate-preview:predictLongRunning?key=$GOOGLE_API_KEY`. image2video giữ nhân vật rất tốt. **KHÔNG gửi `generateAudio`** (400); Veo tự thêm audio → tách khi dựng; xuất 720p.
- **Style khoá (thiền):** central subject = **hành giả/Phật phát hào quang vàng kim** (cảnh trống bị reject), palette vàng kim + xanh thẳm, ánh sáng từ trong, đối xứng.
- **Cạm bẫy quota:** Veo giới hạn theo **NGÀY** (~9–16 clip), `429` không nâng bằng tiền → rải lịch nhiều ngày **hoặc** fallback **Imagen + Ken Burns** (chấp nhận lặp clip vài chương).

### Stage 5 — Music
- **Output:** `assets/music/bed.mp3`.
- **Default khoá:** **chỉ nhạc AI sinh mới** (`music_gen`/ElevenLabs Music/suno) hoặc `music_library/meditation-ambient-ai-safe.mp3`. Loop bằng `acrossfade=d=5`.
- **CẤM tuyệt đối:** Kevin MacLeod / incompetech / CC-BY lạ → dù hợp pháp vẫn dính **YouTube Content ID claim**.
- **Cạm bẫy:** ElevenLabs Music quota **riêng** với TTS (Music 402 không ảnh hưởng TTS).

### Stage 6 — Edit & Mix → `montage_lib.py`
- **Output:** track narration+music ducked / `master-mixed.mp3`.
- **Default khoá:** sidechain duck (nhạc ~**-11dB** dưới giọng), loudnorm **I=-16 TP=-1.5**, nhạc **fade vào sau intro** (intro giọng-only). amix duration=first.
- **Cạm bẫy chí mạng:** **dùng đúng file nguồn** — chọn bản dry/wet đã đăng (bug từng xảy ra: bản wet đặt outro ở 1.5s → chồng giọng). `montage_lib` dùng offset helper để tránh lỗi offset thủ công.

### Stage 7 — Compose → `montage_lib.py`
- **Output:** `renders/final.mp4` (16:9 1080p) + `renders/final-clean.mp4` (silent, để remux nhạc về sau).
- **Default khoá:** **luôn** intro title card (~5s) + main + outro "Đăng ký kênh" (~6s, nút đỏ ĐĂNG KÝ). Concat FFmpeg re-encode 30fps/yuv420p + aformat 44100 stereo. Engine = **FFmpeg** (Remotion chưa cài).
- **Tiếng Việt:** drawtext **`textfile=`** (UTF-8) cho MỌI text (title/small/label), font `C:/Windows/Fonts/arialbd.ttf` — không gõ trực tiếp dấu vào filter. Ép `PYTHONUTF8`.
- **Phụ đề:** thiền **mặc định KHÔNG**. Essay có thể bật (xem split bên dưới).
- **Tối ưu:** đổi nhạc không dựng lại hình → `remux_audio` (`-c:v copy`), **chỉ remux lên bản silent/clean** (guard tránh 2 lớp nhạc).

### Stage 8 — QA · Thumbnail · Publish
- **QA gate:** `ffprobe` (codec/độ phân giải/duration) + `silencedetect` (timeline giọng) + đo audio level. Không đạt → không xuất.
- **Copyright gate (CỨNG, chặn publish):** `ffprobe -show_entries format_tags` xác nhận không còn tag nhạc bản quyền; bước YouTube "Kiểm tra → Bản quyền: Không phát hiện vấn đề".
- **Thumbnail:** `youtube-thumbnail-design/generate.py`, layout **facecam** (monk trái + panel navy/gold phải + logo sen "Thiền Đạo"). Map `GOOGLE_API_KEY`→`GEMINI_API_KEY` (**strip inline `#` comment**, định dạng mới `AQ.Ab8…`), `PYTHONUTF8=1`, nén `<2MB` (`ffmpeg scale=1280:720 -q:v 3 .jpg`).
- **Publish:** YouTube **không cho thay file** → upload mới + set bản cũ **Private**. Chrome `file_upload` <10MB → **bước chọn file user tự thao tác**; phần điền tiêu đề/mô tả tự động. Gõ tiếng Việt qua automation dễ sai dấu → screenshot kiểm lại.

---

## Bảng Locked Defaults

| Capability | Tool/Provider | Model/Tham số | Điều kiện |
|---|---|---|---|
| TTS chính | `elevenlabs_tts` | giọng Chau Nguyen, `eleven_v3`, stab 0.5/sim 0.75/style 0 | re-fetch voice_id; ELEVENLABS_API_KEY |
| TTS dự phòng | `google_tts` | `vi-VN-Chirp3-HD-Charon/Iapetus`, rate 0.82 | **service-account JSON** |
| Ảnh | `google_imagen` | `imagen-4.0-generate-001`, 16:9 | service-account; flux=403 |
| Video | Veo qua Gemini REST | `veo-3.1-generate-preview`, image2video | GOOGLE_API_KEY; quota/ngày; fal=403 |
| Nhạc | `music_gen` / asset AI-safe | loop acrossfade d=5 | tránh Content ID |
| Mix | `montage_lib.duck_mux` | duck -11dB, loudnorm I=-16 TP=-1.5 | dùng đúng file dry/wet |
| Compose | `montage_lib` (FFmpeg) | 30fps yuv420p, aformat 44100 stereo, drawtext textfile | Remotion chưa cài |
| Thumbnail | Gemini generate.py | layout facecam, <2MB | strip `#`, PYTHONUTF8=1 |

## Cây quyết định fallback

```
TTS:   ElevenLabs Chau Nguyen (eleven_v3)
        └─ lỗi/quota → google_tts Chirp3-HD (cần service-account JSON)
Ảnh:   google_imagen 4
        └─ flux_image luôn 403 → không thử lại
Video: Veo qua Gemini (image2video)
        ├─ 403 fal → đã đi đường Gemini, bỏ fal
        └─ 429 quota/ngày → Imagen + Ken Burns (chấp nhận lặp)
Nhạc:  music_gen AI mới
        └─ 402 ElevenLabs Music → suno_music / asset AI-safe sẵn
```

---

## Tách "lõi dùng chung" vs "tham số riêng thiền"

Pipeline dùng cho **mọi** video kênh, nhưng phần lớn default sinh từ video thiền — tách rõ để không khoá cứng nhầm:

| | **Lõi dùng chung** (mọi video) | **Tham số riêng thiền** (chỉnh khi đổi thể loại) |
|---|---|---|
| Giọng | ElevenLabs Chau Nguyen + eleven_v3, re-fetch voice_id | nhịp silence DÀI (0.7/1.8/3.5s) → essay rút ngắn |
| Nhạc | chỉ nhạc AI/Content-ID-safe | ambient nhẹ → essay có thể bed mạnh hơn |
| Dựng | `montage_lib` FFmpeg, sidechain duck, loudnorm I=-16 | — |
| Format | intro card + outro "Đăng ký kênh", 16:9 1080p | hào quang vàng kim, đối xứng (riêng thiền) |
| Phụ đề | (theo thể loại) | thiền = KHÔNG; essay song ngữ karaoke có thể bật |
| Publish | upload mới + cũ Private, thumbnail facecam | — |

---

## Project layout chuẩn

```
projects/<slug>/
├── artifacts/   # script.md, script-narration-only.md, brief, youtube-publish.md
├── assets/
│   ├── audio/   # chuong-*.mp3, narration-full.mp3
│   ├── images/  reference/  # ảnh thiền giả (Imagen)
│   ├── video/   # clip Veo
│   └── music/   # bed.mp3 (AI-safe)
└── renders/     # final.mp4 + final-clean.mp4 (silent)
```
Thin driver dựng mỗi video import `scripts/video/montage_lib.py` (xem `scripts/video/README.md`).

## Kiểm chứng (validation)

Khâu dựng (Stage 6–7) được kiểm bằng 2 driver tạm (chạy trên asset thật, KHÔNG sinh asset/TTS mới):
- `scripts/video/_validate_bonmua.py` — dựng lại bon-mua rút gọn qua lib (card + slow-loop + concat + narration track + duck + remux guard) + QA gate.
- `scripts/video/_validate_longform.py` — đường dài format ngủ: PROOF1 batch-amix 240 cue → 8 batch (không OOM); PROOF2 đường dựng dài (concat + offset helper + duck).
- QA gate Stage 8 ở `scripts/video/_qa.py`: ffprobe (codec/res/duration), silencedetect (timeline giọng), **copyright gate cứng** (`format_tags` không chứa marker Content-ID/CC-BY).

Phạm vi: validation chỉ xác nhận **recipe FFmpeg** + đường dựng; KHÔNG xác nhận provider/asset-gen theo máy (ElevenLabs/Imagen/Veo — chạy lại Stage 0 nếu đổi máy/key). Long-form skeleton chứng minh đường dựng chịu được độ dài + cấu trúc lặp, KHÔNG thay video ngủ thật.

---

## Câu hỏi chưa giải quyết

- Format ngủ 30–60′ (động cơ tăng trưởng theo lịch nội dung): đường dựng đã được skeleton chứng minh (`_validate_longform.py`) nhưng **chưa có video thật end-to-end** (cần asset Veo/narration thật) — cần build + xác nhận khớp pipeline.
- Biến thể philosophy essay: cờ tham số trong cùng pipeline hay tách riêng (phụ đề song ngữ karaoke, nhịp nhanh)?
