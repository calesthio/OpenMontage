# Kênh logistics giải thích — playbook dựng

Rút ra từ hai video của kênh `aps.logistics` (TikTok), đo bằng ffmpeg chứ không phỏng đoán:

| | Video "thuế 12,5%" | Video "Thông tư 28" | Bản `sau-rieng` v7 của ta |
|---|---|---|---|
| Thời lượng | 130 s | 113 s | 105 s |
| Cắt cứng | 10 | **5** | 26 |
| Hoạt động hình ảnh TB | 7,6 | **8,7** | 6,5 |
| Người dẫn lên hình | ~30 % | ~18 % | ~11 % |

## Bài học lớn nhất: động lượng không đến từ cắt

Video "Thông tư 28" chỉ cắt **5 lần trong 113 giây** — một cắt mỗi 22 giây — nhưng vẫn là bản
động nhất trong ba bản. Bản của ta cắt 26 lần mà vẫn kém động hơn.

Vì động lượng của họ nằm **bên trong shot**: camera bay liên tục trên bản đồ vệ tinh, tài liệu
cuộn không ngừng, chữ bay vào rồi bay ra, dải highlight quét dọc trang. Cắt nhiều mà mỗi shot
đứng yên thì vẫn chán; một shot dài mà mọi thứ trong đó đang chuyển động thì không.

**Quy tắc:** trước khi thêm một cú cắt, hỏi "shot này còn gì đang chuyển động không?". Nếu không,
sửa shot chứ đừng cắt.

## Cấu trúc 5 hồi

| Hồi | Thời lượng | Việc phải làm |
|---|---|---|
| 1. Nghịch lý | 0–15 s | Hai vật **giống hệt nhau**, kết quả **khác nhau** |
| 2. Loại trừ | 15–23 s | Nêu rồi gạch bỏ các đáp án sai, tiết lộ khái niệm thật |
| 3. Sự kiện | 23–51 s | Ngày ban hành, cơ quan, số hiệu văn bản, ảnh chụp văn bản |
| 4. Nội dung | 51–86 s | Phần giáo dục: danh sách nhóm, nguyên tắc, bảng tra |
| 5. Hậu quả + hành động | 86–107 s | Điều gì xảy ra nếu không làm, và việc cần làm ngay |

### Hồi 1 phải là một nghịch lý, không phải một lời chào
Video mở bằng **hai con tàu container giống hệt nhau** nằm cạnh nhau trên biển, cùng nhãn
"CÙNG 1 LÔ HÀNG / CÙNG 1 SẢN PHẨM". Rồi kết quả tách đôi: tàu A chữ trắng "THÔNG QUAN SUÔN SẺ",
tàu B chữ đỏ "BỊ GIỮ HÀNG TẠI CẢNG". Người xem buộc phải biết vì sao — và câu trả lời bị giữ lại
đến giây 23.

Mẫu áp dụng được: hai xe container, hai tờ khai, hai vườn, hai container cùng mã.

### Hồi 2: loại trừ trước, tiết lộ sau
"CHẤT LƯỢNG HÀNG HÓA" và "GIÁ TRỊ LÔ HÀNG" hiện lên rồi mờ đi, sau đó chữ **HS** khổ khổng lồ màu
cam đập vào giữa khung. Đừng nói đáp án ngay; hãy dọn sạch các đáp án sai trước.

## Tài liệu thật là nhân vật chính, không phải minh họa

Khoảng **35 % thời lượng** là ảnh chụp văn bản pháp luật và bảng phụ lục mã HS thật. Cách dùng:

1. Trang cuộn chậm và **liên tục** — không bao giờ đứng yên.
2. Một **dải cam trong suốt** quét lên đúng câu đang được đọc, đồng bộ từng câu.
3. Bảng phụ lục thật cũng lên hình, các dòng liên quan tô nền cam.
4. Ghi nguồn nhỏ dưới đáy.

Đây là thứ tạo uy tín cho kênh thiên hướng giáo dục: người xem **thấy văn bản gốc**, không phải
nghe kể lại. Trong repo, `ArticleShot` đã làm được bước 1–2; cần bổ sung khả năng highlight nhiều
vùng theo nhiều mốc thời gian thay vì một vùng duy nhất.

## Người dẫn xuất hiện muộn và ít

Lần đầu ở **giây 50**, tức gần nửa video. Tổng cộng khoảng 20 giây trong 113 giây. Chỉ dùng ở hai
chỗ: lúc cảnh báo hậu quả, và lúc đưa lời khuyên cuối — những chỗ cần "người nói với người".

Người dẫn **không phải xương sống** của video. Đồ họa mới là. Đừng mở bằng mặt người.

## Chữ

- Chữ hoa, đậm, **không có nền chip**, chỉ đổ bóng nhẹ.
- Cam `#F5A623` cho từ khóa, trắng cho phần còn lại. Đỏ chỉ dành cho hậu quả xấu.
- Cỡ rất lớn: cụm từ khóa chiếm 1/3 chiều ngang khung.
- Đặt **so le trái/phải quanh vật thể**, không phải luôn căn giữa dưới.
- Ngày tháng và số hiệu phóng cực lớn: "01.06 2026" chiếm nửa khung hình.

## Phụ đề: đừng chạy đè lên đồ họa

- Khi đang có đồ họa: **chữ trên màn hình chính là phụ đề**, cỡ lớn, có thiết kế.
- Chỉ khi người dẫn lên hình mới có phụ đề nhỏ ở dưới, chữ trắng **không nền**.

Bản `sau-rieng` v7 chạy phụ đề nền tối suốt 105 giây, kể cả trên các shot `hero` vốn đã có chữ lớn.
Đó là hai lớp chữ đánh nhau. **Việc cần sửa lần sau:** tắt `CaptionBar` trên `hero` và `map` có
`note`, chỉ bật trên `presenter`, `photo` và `article`.

## Kết bằng việc cần làm

B-roll cảng nhìn từ trên cao + một câu mệnh lệnh: "RÀ SOÁT LẠI MÃ HS". Không phải câu hỏi tu từ.
Bản của ta kết bằng "Còn cửa nào khác?" — hợp thể loại bình luận hơn là thể loại hướng dẫn.

## Checklist trước khi render

- [ ] Hồi 1 có phải một nghịch lý hai vế không?
- [ ] Đáp án thật có bị giữ lại ít nhất 20 giây không?
- [ ] Có ít nhất một ảnh chụp văn bản gốc, cuộn liên tục, highlight theo câu không?
- [ ] Mọi shot có ít nhất một thứ đang chuyển động không?
- [ ] Người dẫn có xuất hiện sau giây 40 và dưới 25 % thời lượng không?
- [ ] Phụ đề có bị tắt trên các shot đã có chữ lớn không?
- [ ] Câu cuối có phải một việc cần làm không?

## Đo chuyển động: nhìn khung hình trước, tin con số sau

Chỉ số hoạt động hình ảnh (`ffmpeg tblend difference`) đo lượng pixel đổi giữa hai
khung, và nó không phân biệt chuyển động cố ý với lỗi dựng. Ở tập "Cửa khẩu thông
minh", hàm rung ca-bin nhận nhầm thời gian tuyệt đối của cả phim thay vì tuổi của
từng cảnh. Số dịch chuyển cộng dồn không giới hạn, nên từ giây 72 ảnh nền trượt ra
khỏi khung và để lộ một đường ghép dọc. Chỉ số vẫn tăng đều qua ba vòng sửa.

Quy tắc rút ra:

- Bất kỳ hàm chuyển động nào cũng nhận **tuổi trong cảnh**, không nhận thời gian phim.
- Số hạng tuyến tính theo thời gian phải có trần, hoặc phải nhỏ hơn phần dư overscan.
- Trước khi tin một chỉ số đã cải thiện, trích khung hình ở nửa sau của phim và nhìn.
  Nửa đầu luôn đúng vì lỗi cộng dồn chưa kịp lớn.
- Đừng lấy chỉ số của video tham khảo làm mốc phải đạt. Quay thật và ảnh tĩnh có hai
  trần khác nhau; ép ảnh tĩnh chạm mốc của quay thật chỉ đẻ ra thủ thuật, không đẻ ra
  retention.

## Cắt nhanh mà vẫn chán: đếm số ảnh, đừng đếm số cảnh

Tập "Cửa khẩu thông minh" cắt 24 cảnh trong 99 giây, trung bình 4,1 giây một cảnh,
nghe thì nhanh. Nhưng 19 cảnh có hình chỉ dùng 7 tấm ảnh, nên thực tế có sáu đoạn
dài 5 đến 13 giây mà người xem nhìn đúng một bức hình dù nghe thấy tiếng cắt. Nhịp
cắt là thứ đo được trên timeline; thứ người xem cảm nhận là hình có đổi hay không.

Quy tắc rút ra:

- Trước khi render, đếm ảnh chứ đừng đếm cảnh. Không cảnh nào kề nhau được dùng chung
  một tấm. Cảnh chen giữa phải là hình thật (bản đồ, ảnh báo), không phải chữ trên nền đen.
- Một tấm ảnh dùng quá 2 lần trong cả phim là dấu hiệu thiếu nguyên liệu, không phải
  dấu hiệu tiết kiệm.
- Khi hết quota sinh ảnh, ghi lại đúng những chỗ đang lặp rồi quay lại lấp, đừng bù
  bằng cách tăng biên độ chuyển động. Chuyển động giả trên ảnh cũ không thay được ảnh mới.
- Thẻ số nào cũng nên có ảnh nền. Chữ trên nền đen là khung chết dài bằng cả câu thoại.

## Đọc đúng phạm vi của một cụm từ trước khi thiết kế cả phim quanh nó

Tập "Cửa khẩu thông minh" dựng cả phim quanh cụm "phương tiện không người lái" trong
tiêu đề bài báo, và giả định luôn rằng đó là chiếc xe container chạy suốt quốc lộ. Sai.
Đọc kỹ đoạn định nghĩa (không chỉ tiêu đề) thì "phương tiện vận tải thông minh không
người lái" (IGV) chỉ hoạt động trong hàng rào của khu vực cửa khẩu; xe đầu kéo có tài
xế vẫn chạy tuyến đường dài như cũ, chỉ dừng lại ở hàng rào để bàn giao container.

Hậu quả: thiết bị chủ đạo của phim ("TÀI XẾ: KHÔNG" từ giây 0) sai suốt từ đầu, và phải
dựng lại toàn bộ — giọng đọc, ảnh, bản đồ, HUD.

Quy tắc rút ra:

- Trước khi khoá một thiết bị dựng phim (một dòng HUD không đổi, một hành trình trên
  bản đồ) vào một danh từ trong tiêu đề, tìm đúng đoạn văn bản pháp lý định nghĩa danh
  từ đó và đọc hết câu, không dừng ở tiêu đề bài báo diễn giải nó.
- Hỏi cụ thể: phạm vi hoạt động của chủ thể này tới đâu? Toàn bộ hành trình, hay chỉ
  một đoạn, một khu vực? Câu trả lời quyết định cả HUD lẫn bản đồ có được vẽ hay không.
- Một cụm từ có hai nghĩa dễ gây sai này là "không người lái": có thể là suốt hành
  trình, có thể chỉ một chặng ngắn có hàng rào. Luôn xác minh trước khi dựng.
- Khi thiết bị dựng phim là một trạng thái đổi theo thời gian (có tài xế → không tài
  xế), nó phải đổi đúng khung hình sự kiện thật xảy ra, không đổi ở giây 0 cho tiện.
