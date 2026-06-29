# Brainstorm: Pipeline làm video chuẩn cho kênh Thiền Đạo (TĐ-SVP)

- **Ngày:** 2026-06-30
- **Loại:** Brainstorm report (chỉ đề xuất, chưa triển khai)
- **Chế độ:** không flag (--html/--wiki không bật)
- **Nguồn:** 3 video đã làm trong `projects/` + 12 memory file đúc kết
- **Quyết định người dùng:** output = báo cáo brainstorm · phạm vi = tổng quát cho mọi video kênh · default = khoá sẵn cái đã chứng minh

---

## 1. Vấn đề & yêu cầu

Bạn đã sản xuất ≥3 video cho kênh **Thiền Đạo - Giác Ngộ Tâm Trí** bằng OpenMontage. Qua nhiều vòng sample, một quy trình de-facto rất nhất quán đã hình thành — nhưng nó nằm rải rác trong memory + build script. Việc cần làm: **codify thành 1 pipeline chuẩn tái dùng**, khoá sẵn các lựa chọn đã chứng minh để mỗi video mới chạy nhanh, ít quyết định lại, ít sai lầm lặp.

**Yêu cầu chốt:**
- Output: 1 báo cáo (file này). Chưa tạo pipeline manifest / build script / SOP doc.
- Phạm vi: dùng chung mọi video kênh (không khoá cứng theo thiền).
- Default: khoá cái đã chứng minh (giọng, provider, cách dựng).
- Acceptance: đọc báo cáo là biết chạy stage-by-stage cho video tiếp theo, biết default nào lấy sẵn, biết fallback khi hỏng.
- Out-of-scope: viết code, tạo `pipeline_defs/*.yaml`, sửa tool OpenMontage.

---

## 2. Tài sản hiện có (đầu vào pipeline)

| Project | Nội dung | Thời lượng | Visual | Giọng |
|---|---|---|---|---|
| `tap-trung-thien-dinh` | "Làm Thế Nào Để Tập Trung Sâu" | 30:43 | Veo (video-led) + Imagen/KenBurns ch8-9 | Chau Nguyen eleven_v3 |
| `bon-mua-cua-hoi-tho` | Thiền 16 phép quán niệm hơi thở | 11.5′ | Seedance + orb "quả bóng nhịp thở" | Chirp3-HD-Charon r0.70 |
| `hieu-doi-truyen-cam-hung` | Video cảm hứng | — | Imagen | có intro/outro cards |

Layout chuẩn đã dùng nhất quán: `projects/<slug>/{artifacts,assets/{audio,images,video,music,reference},renders}` + build script Python ở gốc project.

---

## 3. Các hướng đã cân nhắc

**A. Giữ nguyên de-facto (không codify).** Mỗi video lục lại memory + copy build script cũ.
- ✅ Không tốn công. ❌ Mỗi lần phải nhớ lại 12 cạm bẫy; người mới/agent mới dễ lặp lỗi (hardcode voice_id, dùng nhạc Content ID, sai file narration).

**B. Codify thành SOP doc (`docs/`).** 1 markdown đọc-làm-theo.
- ✅ Nhanh, dễ chỉnh, không lệ thuộc kiến trúc. ❌ Agent không tự chạy được; vẫn thủ công.

**C. OpenMontage pipeline chính thức (`pipeline_defs/guided-meditation.yaml` + director skills).**
- ✅ Đúng Rule Zero, agent tự orchestrate. ❌ Tốn công nhất; nhiều default đúng *trên máy này* nên khó general hoá vào skill dùng chung.

**D. Build script template tham số hoá.**
- ✅ Thực dụng, khớp cách dựng FFmpeg hiện tại. ❌ Chỉ phủ khâu dựng cuối, không phủ research→script→assets.

→ **Báo cáo này = nền chung cho cả 4.** Nó đặc tả pipeline + locked defaults một cách trung lập, để sau muốn đẩy lên B/C/D đều dùng lại được. (Người dùng chọn: chỉ làm báo cáo trước.)

---

## 4. Pipeline đề xuất — "Thiền Đạo Standard Video Pipeline" (TĐ-SVP)

Bám flow OpenMontage `research → proposal → script → scene_plan → assets → edit → compose`, thêm Publish. Mỗi stage: **Output · Default khoá · Quality gate · Cạm bẫy**.

### Stage 0 — Preflight (1 lần/máy, hoặc khi đổi key)
- **Output:** capability envelope thực tế.
- **Làm:** `registry.provider_menu_summary()`.
- **Sự thật môi trường (máy hiện tại):** ElevenLabs TTS ✓ · Imagen 4 ✓ (service-account JSON) · Veo-qua-Gemini ✓ · **fal.ai = 403** (Veo/Kling/Seedance/flux qua fal đều chặn) · FFmpeg ✓ · **Remotion ✗ / HyperFrames ✓**.
- **Cạm bẫy:** registry báo "available" theo *có env var*, không theo *key đúng* → silent-availability. Đừng tin nhãn, tin lần chạy thật.

### Stage 1 — Concept & Brief
- **Output:** brief (lane, tiêu đề, thời lượng, nền tảng, tone, phụ đề y/n).
- **Default khoá:** lane = **guided practice** ưu tiên (philosophy = playlist phụ, không pha vào timeline thực hành). Nền tảng = **16:9 YouTube 1080p**. Title formula = `[Lợi ích/Kết quả] + [Thời lượng] + [Phương pháp]`, **không emoji giữa dòng**.
- **Gate:** brief khớp lane; nếu là philosophy essay → đánh dấu "biến thể essay" (xem §5).

### Stage 2 — Script
- **Output:** `artifacts/script.md` (full, có cue cảnh) **+** `artifacts/script-narration-only.md` (chỉ lời cho TTS).
- **Default khoá:** cấu trúc chương tuyến tính (định→tuệ với thiền), mỗi chương 3-5′, có **câu chuyển chương** giữ retention; mở bằng ẩn dụ mạnh.
- **Cạm bẫy:** TTS phải đọc file narration-only — đừng để cue cảnh lọt vào giọng.

### Stage 3 — Narration (lõi, dễ sai nhất)
- **Output:** `assets/audio/chuong-*.mp3` + `narration-full.mp3`.
- **Default khoá:** ElevenLabs **giọng "Chau Nguyen"** (cloned) + model **`eleven_v3`**, stability 0.5 / similarity 0.75 / style 0.
- **BẮT BUỘC:** **re-fetch voice_id mỗi lần** — `GET https://api.elevenlabs.io/v1/voices` (header `xi-api-key`), tìm `name=="Chau Nguyen"` category cloned. **KHÔNG hardcode** (id đã đổi `kjjym…`→`rMfGA…` khi user re-clone).
- **Nhịp thiền:** ElevenLabs không có speaking_rate → nhịp = **chèn silence**: 0.7s/câu · 1.8s/đoạn · 3.5s cho dòng `…`. Render **từng câu** → ghép FFmpeg concat (wav LINEAR16 24k mono) → encode mp3.
- **Gate:** render **SAMPLE 1 chương** cho user duyệt **trước** khi render full.
- **Fallback:** google_tts `vi-VN-Chirp3-HD-<Charon/Iapetus>` r≈0.82 — **cần service-account JSON** (`GOOGLE_APPLICATION_CREDENTIALS`), API key bị 401.

### Stage 4 — Visuals
- **Output:** `assets/reference/*.png` + `assets/video/*.mp4`.
- **Default khoá:**
  1. Sinh **ảnh reference thiền giả** bằng **`google_imagen`** (imagen-4.0, **16:9** — ref 3:4 gây viền đen).
  2. Sinh clip **Veo qua Gemini REST** trực tiếp: `POST .../models/veo-3.1-generate-preview:predictLongRunning?key=$GOOGLE_API_KEY`, image2video giữ nhân vật rất tốt. **KHÔNG gửi `generateAudio`** (400); Veo tự thêm audio → tách khi dựng; xuất 720p.
- **Style khoá (thiền):** central subject = **hành giả/Phật phát hào quang vàng kim** (cảnh trống bị reject), palette vàng kim + xanh thẳm, ánh sáng từ trong, đối xứng.
- **Cạm bẫy quota:** Veo giới hạn theo **NGÀY** (~9-16 clip), `429` không nâng bằng tiền → lên lịch nhiều ngày **hoặc** fallback **Imagen + Ken Burns** (chấp nhận lặp clip ở vài chương).
- **Fallback chain:** flux_image (403) → google_imagen; Veo (403/quota) → Imagen+KenBurns.

### Stage 5 — Music
- **Output:** `assets/music/bed.mp3`.
- **Default khoá:** **chỉ nhạc AI sinh mới** (`music_gen`/ElevenLabs Music) hoặc `music_library/meditation-ambient-ai-safe.mp3`. Loop bằng `acrossfade=d=5`.
- **CẤM tuyệt đối:** Kevin MacLeod / incompetech / CC-BY lạ → dù hợp pháp vẫn dính **YouTube Content ID claim**.
- **Cạm bẫy:** ElevenLabs Music quota **riêng** với TTS (Music 402 không ảnh hưởng TTS). suno_music dùng được (đã fix 3 bug shape), trả track ~4′ → cắt/offset.

### Stage 6 — Edit & Mix
- **Output:** `renders/master-mixed.mp3` (hoặc track narration+music ducked).
- **Default khoá:** sidechain duck (nhạc ~**-11dB** dưới giọng), loudnorm **I=-16 TP=-1.5**, nhạc **fade vào sau intro** (intro để giọng-only). amix duration=first.
- **Cạm bẫy chí mạng:** **dùng đúng file nguồn** — bản bon-mua đăng dùng `narration_dry.m4a` (bản wet bị bug đặt outro ở 1.5s → chồng giọng). Luôn đọc build script gốc để biết file nào là bản đã đăng.
- **Lưu ý tool:** `audio_mixer.py` ops `full_mix`/`duck` từng lỗi filter graph → mix bằng lệnh ffmpeg sidechain trực tiếp cho chắc.

### Stage 7 — Compose / Render
- **Output:** `renders/final.mp4` (16:9 1080p) + `final-clean.mp4`.
- **Default khoá:** **luôn** intro title card (~5s) + main + outro "Đăng ký kênh" (~6s, nút đỏ ĐĂNG KÝ). Concat FFmpeg re-encode 30fps/yuv420p + aformat 44100 stereo. Engine = **FFmpeg** (Remotion chưa cài máy này).
- **Tiếng Việt:** drawtext **`textfile=`** (UTF-8), font `C:/Windows/Fonts/arialbd.ttf` — không gõ trực tiếp dấu vào filter.
- **Phụ đề:** với thiền **mặc định KHÔNG** (user chốt). Essay có thể bật (xem §5).
- **Tối ưu:** thay/đổi audio mà không dựng lại hình → remux `-c:v copy -map 0:v -map 1:a`.

### Stage 8 — QA · Thumbnail · Publish
- **QA gate:** ffprobe (độ phân giải/codec) + frame sampling (black/overlay) + **silencedetect** kiểm timeline giọng + đo audio level. Không đạt → không xuất.
- **Thumbnail:** `youtube-thumbnail-design/generate.py`, layout **facecam** (monk trái + panel navy/gold phải + logo sen "Thiền Đạo"). Map `GOOGLE_API_KEY`→`GEMINI_API_KEY` (**strip inline `#` comment**, định dạng mới `AQ.Ab8…`), `PYTHONUTF8=1`, nén `<2MB` (`ffmpeg scale=1280:720 -q:v 3 .jpg`).
- **Publish:** YouTube **không cho thay file** → upload mới + set bản cũ **Private**. Chrome `file_upload` <10MB → **bước chọn file user tự thao tác**, phần điền tiêu đề/mô tả tự động. Gõ tiếng Việt qua automation dễ sai dấu → screenshot kiểm lại. Bước "Kiểm tra → Bản quyền: Không phát hiện vấn đề" = xác nhận nhạc sạch.

---

## 5. Tách "lõi dùng chung" vs "tham số riêng thiền"

Vì phạm vi là *tổng quát cho mọi video kênh*, mà phần lớn default sinh từ video thiền — tách rõ để không khoá cứng nhầm:

| | **Lõi dùng chung** (mọi video) | **Tham số riêng thiền** (chỉnh khi đổi thể loại) |
|---|---|---|
| Giọng | ElevenLabs Chau Nguyen + eleven_v3, re-fetch voice_id | nhịp silence DÀI (0.7/1.8/3.5s) → essay rút ngắn |
| Nhạc | chỉ nhạc AI/Content-ID-safe | ambient nhẹ → essay có thể bed mạnh hơn |
| Dựng | FFmpeg, sidechain duck, loudnorm I=-16 | — |
| Format | intro card + outro "Đăng ký kênh", 16:9 1080p | hào quang vàng kim, đối xứng (riêng thiền) |
| Phụ đề | (theo thể loại) | thiền = KHÔNG; essay song ngữ karaoke có thể bật |
| Publish | upload mới + cũ Private, thumbnail facecam | — |

---

## 6. Phụ lục A — Bảng Locked Defaults

| Capability | Tool/Provider | Model/Tham số | Điều kiện |
|---|---|---|---|
| TTS chính | `elevenlabs_tts` | giọng Chau Nguyen, `eleven_v3`, stab 0.5/sim 0.75/style 0 | re-fetch voice_id; ELEVENLABS_API_KEY |
| TTS dự phòng | `google_tts` | `vi-VN-Chirp3-HD-Charon/Iapetus`, rate 0.82 | **service-account JSON** |
| Ảnh | `google_imagen` | `imagen-4.0-generate-001`, 16:9 | service-account; flux=403 |
| Video | Veo qua Gemini REST | `veo-3.1-generate-preview`, image2video | GOOGLE_API_KEY; quota/ngày; fal=403 |
| Nhạc | `music_gen` / asset AI-safe | loop acrossfade d=5 | tránh Content ID |
| Mix | ffmpeg sidechain | duck -11dB, loudnorm I=-16 TP=-1.5 | dùng đúng file dry/wet |
| Compose | FFmpeg concat | 30fps yuv420p, aformat 44100 stereo, drawtext textfile | Remotion chưa cài |
| Thumbnail | Gemini generate.py | layout facecam, <2MB | strip `#`, PYTHONUTF8=1 |

## 7. Phụ lục B — Cây quyết định fallback

```
TTS:   ElevenLabs Chau Nguyen (eleven_v3)
        └─ lỗi/quota → google_tts Chirp3-HD (cần service-account JSON)
Ảnh:   google_imagen 4
        └─ flux_image luôn 403 → không thử lại
Video: Veo qua Gemini (image2video)
        ├─ 403 fal → đã đi đường Gemini, bỏ fal
        └─ 429 quota/ngày → Imagen + Ken Burns (chấp nhận lặp)
Nhạc:  music_gen AI mới
        └─ 402 ElevenLabs Music → suno_music (đã fix) / asset AI-safe sẵn
```

---

## 8. Rủi ro & lưu ý

- **Lệ thuộc 1 máy:** Veo-qua-Gemini, fal=403, service-account JSON, Remotion chưa cài — đúng *trên máy hiện tại*, không phải chân lý. Nếu chuyển máy/đổi key, chạy lại Stage 0.
- **Silent-availability:** registry over-report "available". Quality gate ở Stage 0 + sample gate ở Stage 3 là chốt chặn chính.
- **Veo quota là nút thắt sản xuất** lớn nhất cho video-led dài → kế hoạch nội dung nên rải clip qua nhiều ngày hoặc thiết kế ít clip/lặp có chủ đích (kiểu orb bon-mua).
- **Bản quyền nhạc** là rủi ro doanh thu cao nhất khi upload → Stage 5 + QA Content-ID là bắt buộc.

---

## 9. Success metrics

- Mỗi video mới chạy hết 8 stage **không lặp lại** 12 cạm bẫy đã ghi.
- Voice_id luôn đúng (không lỗi 1 lần nào do hardcode).
- 0 video dính Content ID claim.
- Time-to-publish giảm so với 3 video đầu (đo bằng số vòng sample cần thiết).

---

## 10. Next steps

1. (Khi sẵn sàng) Nâng báo cáo này lên dạng thực thi: **SOP doc** (`docs/`) hoặc **OpenMontage pipeline** (`pipeline_defs/guided-meditation.yaml` + director skills) hoặc **build script template** tham số hoá.
2. Tạo `music_library/meditation-ambient-ai-safe.mp3` làm bed mặc định nếu chưa cố định.
3. Chuẩn hoá 1 thumbnail template facecam tái dùng (navy+gold, sen logo).

---

## 11. Câu hỏi chưa giải quyết

- Khi nào muốn đẩy báo cáo → artifact thực thi (B/C/D)? Hình thức nào ưu tiên?
- Biến thể "philosophy essay" có cần pipeline riêng (phụ đề song ngữ karaoke, nhịp nhanh) hay chỉ là cờ tham số trong cùng pipeline?
- Có chuẩn hoá thời lượng/cadence cố định cho lane guided (vd tuần 1 video 15-20′) để khoá vào Stage 1 không?
