# Flow đổi nền tảng — 2026-09-05

Ghi lại tại thời điểm `flow_video` chết hàng loạt ở Ngày 7. Đây là **hồ sơ điều
tra**, không phải hướng dẫn dùng: mục 4 là việc còn phải làm.

## 1. Triệu chứng

Cả ba clip đầu fail sau ~14s, cùng một câu:

```
Flow driver error: Page.evaluate: SyntaxError:
Unexpected token '<', "<!doctype "... is not valid JSON
```

Fail nhanh và giống hệt nhau. SKILL.md gọi đúng tên: *"một loạt lỗi liên tiếp là
Flow đổi, không phải prompt sai."*

## 2. Nguyên nhân

`lib/flow_driver.py` gọi `fetch('/fx/api/auth/session')` bằng **đường dẫn tương
đối**, rồi `.json()`. Đo được:

| Kiểm tra | Kết quả |
|---|---|
| `/fx/api/auth/session` trên `flow.google.com` | 200, `text/html`, trả vỏ app |
| `/api/auth/session` | 200, `text/html` |
| `/fx/api/trpc/media.list` | 200, `text/html` |
| `labs.google/fx/tools/flow` | **redirect** sang `flow.google.com` |
| DOM `__NEXT_DATA__` | không còn |
| DOM `[ng-version]` | **có** |
| XHR khi tải trang | `POST /_/AiSandboxAngularFrontend/data/batchexecute` |
| token `ya29.` trong window / storage / HTML | **không có ở đâu** |

Flow **không đổi đường dẫn — nó được viết lại**: Next.js + tRPC trên
`labs.google/fx` → **Angular + batchexecute** trên `flow.google.com`, xác thực
bằng cookie chứ không bằng bearer token.

Hệ quả: cả tầng API của driver (`auth/session`, `uploadImage`, `media
.getMediaUrlRedirect`) không còn tồn tại, và **không thể vá bằng cách sửa URL**
— không có token để gọi `aisandbox-pa.googleapis.com` nữa.

## 3. Giao diện mới, đo trực tiếp

Điều tra trên tab thật, không tiêu credit.

- **Ô nhập prompt là `div[contenteditable=true]`**, placeholder
  `Bạn muốn tạo những gì?`. **Không phải `<textarea>`** — `<textarea>` duy nhất
  trên trang là `g-recaptcha-response`. Driver cũ nhắm sai phần tử.
- **Nút gửi**: `button[aria-label="Bắt đầu tạo"]` (icon `arrow_forward`).
- **Pill cài đặt**: `button[aria-label="Điều kiện kích hoạt cài đặt"]`, chữ hiện
  `Video · 720p · 8 giây / crop_16_9 / x2`.
- **Gắn ảnh**: `button[aria-label="Thêm thành phần vào ô nhập câu lệnh"]` (icon
  `add`) → mục `Tải nội dung nghe nhìn lên`. Mục này **không có
  `<input type=file>` trong DOM** — nó mở hộp thoại file của hệ điều hành, nên
  phải bắt bằng `page.expect_file_chooser()`.
  - Locator phải dùng `get_by_role("button", name=...)`: chuỗi đó khớp cả một
    `div[role=tooltip]`, `get_by_text` sẽ vi phạm strict mode.
  - Đã thử thật: upload thành công, ảnh gắn vào prompt bar.
- **Host media mới: `https://flow-content.google/image/<id>`**. Sau khi upload,
  thumbnail xuất hiện ở 40×40, 141×250 và 257×457 từ host này.
- Lưới dự án **không mount `<video>`** — chỉ thumbnail. Player chỉ xuất hiện khi
  mở tile, đúng lý do `_reveal_players()` tồn tại trong driver cũ.

## 4. Lấy video về máy — đường đi và sáu cái bẫy

Đường đúng: **menu của tile → `Tải xuống` → `720p Kích thước gốc`**. Ra đúng bản
gốc: 720×1280, 24fps, đúng 8.000 giây, có tiếng. Mất ~19 giây cả chuỗi.

Không dùng src của player. Nó chỉ tồn tại khi player đang mount, và **đổi host
khi clip nguội** (`flow.google.com/asb/<token>` thay vì
`flow-content.google/video/<id>`).

Sáu chỗ đã cắn, theo thứ tự gặp:

1. **`<video>` không tự mount.** Clip probe có mount nên bản driver đầu tin vào
   đó; shot thật xong mà không mount player nào, `wait_generation` ngồi hết 810s
   trong khi clip đã ở trên màn hình. Nhận diện clip bằng **tile**
   (`flow-video-tile`, mới nhất đứng đầu), không bằng player.
2. **Click tile là điều hướng** sang `/project/<id>/edit/<scene>`, nơi không có
   `flow-video-tile` nào. Mọi lỗi "menu không mở" giữa chừng đều do chính cú
   click này đẩy trang đi dưới chân selector. Driver phải quay về lưới trước —
   và nạp lại luôn, vì menu cũ để lại backdrop trong suốt chặn cú hover kế tiếp.
3. **Submenu mở bằng hover, và phải là *di chuyển ngang qua* mục cha.** Nhảy một
   phát vào giữa mục thì không mở. Click vào mục cha thì đóng cả menu.
4. **Các dòng submenu là `<flow-menu-item>` không có hộp bao.**
   `getBoundingClientRect()` trả rỗng nên mọi locator và mọi vòng
   `querySelectorAll` đều đi lướt qua. `document.elementFromPoint` thấy chúng.
   Chỉ nhận text ngắn: ở mép trên `elementFromPoint` trả về **cả khối** chứa mọi
   dòng, mà text khối đó cũng chứa "Kích thước gốc" — click vào đó là trúng dòng
   `270p Ảnh GIF động`.
5. **Chuẩn hoá Unicode.** Đây là cái đắt nhất. Flow trả nhãn có dấu ở dạng khác
   với chuỗi trong code, nên `"Kích thước gốc" in text` là False trong khi hai
   chuỗi hiện ra y hệt nhau và in ra debugger cũng y hệt nhau. Driver báo "Flow
   không mở submenu" cả chục lượt trong khi ảnh chụp cùng khoảnh khắc cho thấy
   submenu đang mở. So chuỗi tiếng Việt phải qua `unicodedata.normalize("NFC")`.
6. **Click chuột thật lên dòng đó không làm gì cả.** Click trúng đúng phần tử,
   menu đóng, không có file ở đâu, và **bảng `downloads` trong History của
   Chrome rỗng** — tức trình duyệt chưa từng bắt đầu tải. Phải gọi `.click()`
   trên `<button>` bên trong bằng script.

Và chỗ nhận file: **`expect_download` không bao giờ bắn** khi gắn qua CDP vào
trình duyệt có sẵn — Playwright không sở hữu download của nó. Tự chỉ định thư
mục bằng `Browser.setDownloadBehavior` (`allowAndName`) rồi quét thư mục đó;
file được đặt tên GUID không phần mở rộng.

## 5. Gắn ảnh: chế độ Khung hình khác chế độ Thành phần

Cái nút `+` đã dò được ở mục 3 là *thêm thành phần*. Bật `Khung hình` thì nó
biến mất, thanh prompt đổi thành hai ô **`Bắt đầu`** / **`Kết thúc`**, và ô đó
**chỉ chọn được thứ đã nằm trong thư viện dự án** — không upload tại chỗ. Nên
gắn ảnh là hai bước:

1. Upload vào thư viện qua nút toolbar `Trình đơn thêm nội dung nghe nhìn` →
   mục `Tải lên` (vẫn là `expect_file_chooser`, vẫn không có `input[type=file]`).
2. Bấm ô `Bắt đầu` → picker → gõ tên vào ô tìm → bấm asset. Bấm asset là **áp
   dụng luôn và đóng picker**; nút `Thêm vào câu lệnh` chỉ dành cho chọn nhiều.

Hai cái bẫy ở bước 2, cả hai đều đã cắn:

- Thư viện nhận file **trước khi** picker liệt kê nó. Hỏi một lần thì hỏng ở
  shot thật đầu tiên dù chạy tay đã qua — phải gõ lại ô tìm cho tới khi thấy.
- Nút asset **không có tên khả truy cập bằng tên file**, nên
  `get_by_role(name=...)` trượt. Khớp bằng `innerText`.

Ảnh được upload dưới **tên mới mỗi lần**: picker phân biệt bằng tên file, mà
một tập dùng lại sáu bức cho tám shot thì picker sẽ có tám dòng cùng tên và
không cách nào biết shot này định lấy dòng nào.

## 6. Những chỗ khác đã cắn khi viết lại

- Panel cài đặt toàn `[role=radio]` **không có `aria-label`**, text là ligature
  Material Symbols xuống dòng rồi mới tới nhãn (`"videocam
Video"`). Khớp theo
  **một dòng** của `innerText`, đừng khớp chuỗi con — `x1` sẽ dính `x10`.
- Bấm pill là **toggle**. Bấm mù vào panel đang mở thì đóng nó lại, rồi mọi
  selector sau đó timeout với thông báo về cái radio chứ không về cái panel.
- Angular để lại `.cdk-overlay-backdrop` trong suốt sau khi đóng overlay; nó ăn
  mọi cú click sau đó mà không hiện dấu hiệu gì.
- `Locator.type` mặc định timeout 30s. Prompt của series dài hơn 2300 ký tự,
  hết giờ vào khoảng phím thứ 1200 — giữa câu, settings đã set, chưa sinh gì.
  Timeout phải co theo độ dài chuỗi.
- Trình duyệt này thường mở sẵn nửa tá tab project. `_find_flow_page` phải ưu
  tiên đúng `project_url`, nếu không cả tập rơi vào project ngẫu nhiên.

## 7. Một cái bẫy tốn tiền
Pill đang là **`x2`** và **`crop_16_9`**. `flow_video` không phơi nút x1–x4, nên
nó chạy theo giá trị sẵn có trong tab: mỗi clip sẽ tốn **gấp đôi** credit và ra
**16:9** thay vì 9:16. Driver viết lại **set cả hai một cách tường minh rồi đọc ngược pill**
và từ chối submit nếu pill không khớp — đo được là pill nói đúng cái sắp mua
(`Video · 720p · 8 giây crop_9_16 x1`), và panel còn ghi luôn giá: 8 giây = 12
tín dụng, 10 giây = 15, khớp bảng đo tay của Ngày 8.
