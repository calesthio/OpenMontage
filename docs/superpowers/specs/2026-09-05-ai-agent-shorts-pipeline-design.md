# AI-agent Shorts pipeline — design

Kênh dạy dùng AI agent cho công việc hằng ngày. Mỗi tập là một Short 45-90 giây,
9:16, quay màn hình thật của agent đang làm việc, thuyết minh giọng trẻ VieNeu.
Mục tiêu của tài liệu này: pipeline tự động ra video từ một file spec, tái dùng
pipeline `screen-demo` có sẵn trong OpenMontage. Chưa bàn chiến lược nội dung.

## Quyết định đã chốt

| Việc | Chọn | Vì |
|---|---|---|
| Phạm vi | pipeline trước, chiến lược kênh sau | kênh là sản phẩm demo của pipeline |
| Format | screen-demo, faceless | khớp tool đang có, rẻ nhất |
| Giọng | VieNeu preset giọng trẻ (không dùng giọng clone "Toàn"), chọn preset sau khi nghe thử | |
| Nền tảng | Shorts/TikTok 45-90s, 1080x1920 | |
| Nguồn màn hình | quay thật, tự động | không dùng TerminalScene tổng hợp |
| Chủ thể | Claude Code terminal, agent điều khiển trình duyệt, chat web (claude.ai/ChatGPT) | |
| Kiến trúc | A: episode spec + capture driver + screen-demo pipeline nguyên bản | 80% việc đã có trong repo |
| render_runtime | remotion (HyperFrames có sẵn nhưng không thêm gì cho format này) | phụ đề word-level, zoom-crop có sẵn |
| composition_mode | templated | 3 tập/tuần cần nhìn giống nhau |

Hai quyết định cuối ghi vào decision_log một lần cho cả kênh, không hỏi lại mỗi tập.

## 1. Episode spec

Một file YAML mỗi tập tại `episodes/<slug>.yaml`, là đầu vào duy nhất.

```yaml
slug: claude-code-doc-mail-moi-sang
title: "Để AI đọc mail giúp bạn mỗi sáng"
hook: "Sáng nào cũng 40 mail chưa đọc? Giao cho agent."   # 3 giây đầu
voice: "Ngọc Linh"            # preset VieNeu
target_seconds: 60
review_capture: true          # gate người duyệt sau khi quay
steps:
  - surface: terminal        # terminal | browser | chat
    action: "Tóm tắt 10 mail mới nhất trong Gmail, gắn nhãn việc cần trả lời"
    narration: "Gõ một câu, agent tự mở Gmail và đọc."
    hold: 8                  # giây tối đa giữ bước này trên màn hình
  - surface: browser
    url: "https://mail.google.com"
    action: "Cuộn tới nhãn 'Cần trả lời', mở mail đầu"
    narration: "Kết quả nằm ngay trong hộp thư, không copy đi đâu."
    hold: 6
cta: "Theo dõi để xem tập sau: agent tự trả lời mail."
```

- `action` là ngôn ngữ tự nhiên. `terminal`: prompt gõ vào Claude Code.
  `browser`/`chat`: chỉ thị cho agent điều khiển Playwright.
- `narration` viết trước để kiểm soát thời lượng; được sửa sau khi quay để khớp output thật.
- Spec không chứa zoom, callout, font. Đó là việc của scene_plan và playbook.
- Validate ở đầu pipeline: tổng `hold` + hook + CTA ≤ `target_seconds`; mỗi step có `narration`.

Bỏ qua: template tập, biến chèn, kế thừa spec. Thêm khi có tập thứ 10.

## 2. Capture driver

Tool mới `tools/capture/episode_capture.py`. Đọc `steps`, trả về một MP4 dọc
1080x1920 mỗi bước tại `projects/<slug>/assets/video/step_<n>.mp4`, kèm
`capture_log.json` ghi thời điểm bắt đầu/kết thúc mỗi hành động.

**terminal**
- Mở Windows Terminal cửa sổ mới, kích thước cố định 1080x1920, font 22pt,
  cwd là một repo mẫu riêng (không phải OpenMontage).
- Chạy `claude -p "<action>"` như process riêng. Phiên đang dựng video không tham gia.
- `screen_recorder` ghi đúng vùng cửa sổ, `duration = hold + 10`, `fps 30`.
- Dừng khi Claude Code kết thúc hoặc hết thời gian. Đoạn thừa cắt ở stage edit.

**browser**
- Playwright persistent context (`user_data_dir` riêng đã đăng nhập Gmail, Sheets...),
  viewport 1080x1920, `recordVideo` cùng kích thước. Không quay màn hình, không crop.
- `action` được agent dịch thành lệnh Playwright lúc chạy theo skill playwright-recording.
  Chờ theo phần tử, không chờ theo giây.

**chat** (claude.ai / ChatGPT)
- Như browser, cùng persistent context; step `chat` cũng cần `url` (claude.ai hoặc chatgpt.com). Gõ `action` vào ô chat, chờ streaming dừng
  (nút Stop biến mất), cuộn về đầu câu trả lời.

**Chung**
- Không nối file ở đây; nối là việc của edit.
- Trước bước đầu tiên, driver chụp một ảnh kiểm tra. Nếu `review_capture: true`
  (mặc định cho 10 tập đầu), pipeline dừng ở gate để người duyệt xem ảnh và các step MP4.
- Ghi thất bại thì báo blocker theo AGENT_GUIDE, không tự đổi sang TerminalScene.

Bỏ qua: blur tự động, ghi âm hệ thống, nhiều màn hình. Thêm khi có tập lộ dữ liệu thật.

## 3. Hậu kỳ qua pipeline screen-demo

Không stage mới. Mỗi stage nhận thêm spec và `capture_log.json`.

| Stage | Với kênh này |
|---|---|
| idea | brief sinh thẳng từ spec, không hỏi lại |
| script | không transcribe. Narration từ spec, timestamp từ capture_log. Agent được sửa narration để khớp output đã quay |
| scene_plan | mỗi step một scene. Terminal: zoom vào dòng output cuối. Browser: không zoom |
| assets | TTS VieNeu theo từng câu; phụ đề word-level; nhạc nền một track dùng chung cả kênh, tìm bằng pixabay_music, tải một lần vào `music_library/` |
| edit | `silence_cutter` bỏ đoạn agent "nghĩ" quá 2 giây; tăng tốc 3x output dài; cắt đệm cuối mỗi step |
| compose | Remotion 1080x1920; phụ đề to ở 1/3 dưới; hook là text card 3 giây đầu; CTA card cuối |
| publish | chỉ lưu local `renders/final.mp4`. Registry chưa có tool đăng YouTube/TikTok, đăng tay |

Playbook riêng `playbooks/ai-agent-shorts.yaml`: font, màu phụ đề, vị trí card,
thời lượng hook. Tất cả tập đọc chung.

Bỏ qua: cắt Shorts từ tập dài, thumbnail, đăng tự động. Thêm khi có 10 tập.

## 4. Chạy một tập, gate và lỗi

**Lệnh chạy**

```
python -m episodes run episodes/<slug>.yaml
```

Thứ tự: validate spec → `init_project` → `python -m backlot open` → capture →
pipeline screen-demo từ idea tới compose. Không daemon, không hàng đợi.

**Gate người duyệt** (manifest screen-demo quy định, giữ nguyên)
- Sau capture: xem ảnh kiểm tra và step MP4. Bật bằng `review_capture`.
- Sau script: đọc narration đã sửa. Gate quan trọng nhất.
- Sau assets: nghe TTS câu hook; giọng không ổn thì đổi preset trong spec.
- edit và compose tự chạy.

`approval_policy: auto` trong spec bỏ hai gate đầu, ghi decision_log
`category: "approval_policy"`.

**Lỗi**
- Capture hỏng: dừng, giữ step đã ghi, báo bước nào và lý do. Chạy lại chỉ ghi lại
  bước đó nhờ checkpoint.
- Vượt `target_seconds` sau edit: báo con số, đề xuất cắt bước nào, không tự cắt.
- Thiếu preset TTS, thiếu nhạc: blocker trước render, không render câm.

**Chi phí**: toàn bộ local, không API trả tiền. Token của phiên Claude Code diễn viên
và 10-15 phút máy mỗi tập.

## 5. Kiểm thử

- `tests/test_episode_spec.py`: spec hợp lệ qua; vượt thời lượng và thiếu narration bị chặn.
- `tests/tools/test_episode_capture.py`: driver với surface giả trả đúng số file và
  capture_log đúng cấu trúc; không mở trình duyệt thật.
- `episodes/smoke.yaml`: 1 step browser tới trang tĩnh, chạy end-to-end ra `final.mp4`,
  kiểm bằng ffprobe.

## Ngoài phạm vi

Chiến lược nội dung, lịch đăng, thumbnail, đăng tự động, cắt từ tập dài, blur tự động,
template spec. Mỗi thứ có điều kiện thêm ghi ở phần tương ứng.
