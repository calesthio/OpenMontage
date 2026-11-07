# Nghề gói hoa — chuẩn nghiệp vụ cho prompt ảnh và video

Dùng khi sinh **bất kỳ** cảnh nào có người bó hoa, gói hoa, thắt nơ: video tiệm
hoa, ASMR gói quà, quảng cáo hoa tươi, POV nghề.

Đây là **luật nghiệp vụ**, không phải kịch bản. Kịch bản từng bài viết trong
script sinh của bài đó. File này chỉ trả lời một câu: *người làm nghề thật sự
làm gì, theo thứ tự nào, và tay nào cầm gì.*

Đi kèm `.agents/skills/flow-video/references/shot-sequence-prompts.md` — file kia
lo **bối cảnh không trôi**, file này lo **thao tác không vô lý**.

---

## 1. Chuyện gì đã hỏng

Bài `tiem-hoa-cam-tu-cau`, cảnh 06 "quấn giấy ngoài". Prompt viết:

> "The hands fold the dove-grey handmade paper around the outside of the white
> collar, closing it into a wide cone…"

Clip về đúng y lời — và **bó hoa treo lơ lửng giữa không trung** trong khi hai
bàn tay đang bận gấp giấy. 12 credit. Không ai gói hoa được như thế.

Lỗi không ở model. Prompt nói hai tay **làm gì**, không nói **cái gì đang giữ bó
hoa**. Chỗ trống thì model tự điền, và nó điền bằng thứ vô lý nhất trong khung.

Đây đúng là lỗi cảnh 7 của Ngày 10 ("nói cô nhìn gì, không nói cô đứng ở đâu"),
chỉ khác là danh từ bị bỏ quên lần này là **bó hoa** chứ không phải nhân vật.

---

## 2. Luật gánh việc: hai tay chỉ rảnh khi có thứ khác giữ bó

Trong khung có hai bàn tay đang thao tác thì bó hoa **bắt buộc** đang tì vào một
trong đúng ba thứ sau. Không có thứ tư:

| # | Cái giữ | Trông thế nào | Dùng ở nhịp nào |
|---|---|---|---|
| 1 | **Mặt bàn** | bó dựng đứng, gốc đã cắt bằng tì xuống mặt bàn, tự chịu lực | lót vải, quấn giấy, thắt nơ |
| 2 | **Bình / xô nước** | bó cắm trong bình, thân bình giữ | lúc nghỉ giữa các bước, lúc chuẩn bị giấy |
| 3 | **Chính bàn tay kia** | một tay cầm ở **điểm bó**, tay đó **không làm gì khác** | dựng xoắn ốc, cắt gốc |

Một bó hand-tied buộc đúng thì **tự đứng được trên gốc của nó** — đó là phép thử
nghề, và đó cũng là lý do thợ có hai tay rảnh để gói. Prompt phải nói ra điều đó
bằng lời, không được để người đọc tự suy.

Khối dán vào mọi cảnh loại này:

```
The bouquet stands upright on the counter, its cut stem ends resting on the
surface and taking its own weight. It is never held up in mid-air and never
floats: whenever both hands are working on the wrapping, the counter is what
holds the bouquet.
```

---

## 3. Trình tự chuẩn — spiral hand-tied

Thứ tự này **không đảo được**. Đảo một bước là lộ ngay với người trong nghề, và
với người xem thường thì nó vẫn "sai sai" mà họ không gọi tên được.

| # | Bước | Tay trái | Tay phải | Bó tì vào |
|---|---|---|---|---|
| 1 | Sơ chế | cầm cành | tuốt lá dưới điểm bó, tỉa gai | — |
| 2 | Dựng xoắn ốc | cầm bó ở **điểm bó**, lỏng, bằng ngón cái + ngón trỏ | cài từng cành **nghiêng 20–30°, luôn cùng một chiều** | tay trái |
| 3 | Xoay | xoay bó **1/4 vòng** sau mỗi cành | cài cành tiếp | tay trái |
| 4 | **Buộc** | vẫn cầm bó | quấn dây gai / băng dính hoa **3–4 vòng** quanh điểm bó, siết | tay trái |
| 5 | **Cắt gốc** | cầm bó đã buộc | kéo cắt gốc bằng nhau, **chéo 45°** | tay trái |
| 6 | Đặt xuống | — | — | **mặt bàn** — từ đây hai tay mới rảnh |
| 7 | Gói | — | — | mặt bàn |

**Điểm bó** nằm khoảng **1/3 từ đầu hoa xuống**. Đó là chỗ tay người nhận sẽ cầm,
chỗ dây buộc quấn, và chỗ ruy băng thắt sau cùng. Cả ba trùng nhau — không phải
ba chỗ khác nhau.

### Ba lỗi thứ tự hay gặp nhất

1. **Cắt gốc trước khi buộc.** Bó chưa buộc mà cắt là bung. Trong hình thì thấy
   ngay: một bó rời rạc bị dốc ngược lên cho kéo cắt.
2. **Đổi chiều xoắn giữa chừng.** Xoắn ốc chỉ đúng khi mọi cành nghiêng cùng một
   chiều. Prompt phải nói "always in the same direction".
3. **Thắt nơ trước khi khép giấy.** Nơ là bước cuối cùng, thắt đè lên giấy đã
   khép, đúng tại điểm bó.

---

## 4. Các kiểu gói

Chọn **một** kiểu cho cả bài. Trộn hai kiểu giữa các cảnh là lỗi liên tục, không
phải là phong phú.

### 4.1 Korean flat-wrap — kiểu đang thịnh trên TikTok

Giấy chống nước mờ, màu trầm (kem, hồng bụi, xanh xám, oải hương, than chì),
**từ hai lớp trở lên**.

1. Đặt 2 tờ **chồng lệch nhau ~45°** trên mặt bàn phẳng
2. Đặt bó đã buộc **nằm chéo**, đầu hoa gần góc trên
3. Gấp góc dưới lên ôm lấy gốc
4. **Cuộn bó sang phải**, để giấy tự xếp nếp quanh gốc
5. Thắt ruy băng tại điểm bó
6. Mở và chỉnh miệng giấy phía trên cho nó **ôm khung quanh hoa**, không trùm lên hoa

**Chốt sống còn: không vuốt phẳng nếp gấp.** Nếp là chủ ý, là thứ làm nên kiểu
này. Prompt nào tả giấy "smooth, neat, crisp" là giết đúng đặc trưng của nó.
Viết "the paper pleats naturally and the creases are left as they fall".

### 4.2 Bát kem (cream bowl / 奶油碗) — biến thể của 4.1

Thêm **một lớp lót trong** trước lớp giấy ngoài:

1. Vải không dệt trắng quàng quanh **đầu hoa**, tạo cái "bát" nông ôm lấy khối hoa
2. Rồi mới lớp giấy Hàn ở ngoài
3. Nơ satin bản to tại điểm bó

Chỉ hợp với **hoa đầu tròn khối đặc**: mẫu đơn, cẩm tú cầu, mao lương, hồng vườn
nở to. Hoa cành thưa (lay ơn, thiên điểu) làm kiểu này ra cái bát rỗng.

### 4.3 Phễu (cone)

1–2 tờ gấp thành phễu thuôn, gốc chụm xuống dưới. Nhanh, rẻ, kiểu bán ở siêu thị
— **ít trang trọng**, không hợp cảnh quà tặng.

### 4.4 Kraft mộc

Giấy kraft nâu + dây gai. Hoa vườn, hoa đồng nội, tông mộc.

### 4.5 Cellophane trong

Chỉ để **giao hàng**, không phải kiểu trình bày. Đưa vào cảnh quà tặng là sai
ngữ cảnh.

### 4.6 Bọc gốc giữ nước (wet wrap) — không phải kiểu gói, là kỹ thuật kèm theo

Khăn giấy ẩm quanh 5–7 cm gốc → bọc nilon hoặc giấy bạc → chun. Giữ hoa 4–8 giờ.
Nằm **dưới** lớp giấy trang trí, thường không thấy trong khung — nhưng nếu cảnh
có cận gốc bó đã hoàn thiện thì phải có, không thì lộ ra là hoa sẽ héo.

---

## 5. Vật liệu — chọn theo dịp

| Vật liệu | Hợp với |
|---|---|
| Giấy kraft + dây gai | mộc, hoa vườn, đời thường |
| Giấy lụa / tissue | hoa mảnh, tông nhẹ |
| Giấy Hàn chống nước | kiểu Hàn, quà tặng, cao cấp |
| Ruy băng lụa / satin bản to | cô dâu, cao cấp |
| Vải lanh / muslin | garden style |
| Cellophane | chỉ giao hàng |

---

## 6. Khối prompt

Hai khối dán nguyên văn, cộng một câu riêng cho từng cảnh.

```
{SUPPORT: bó tì vào cái gì — mục 2}
{ORDER: cảnh này là bước thứ mấy, và bó đang ở trạng thái quấn nào}
{ACTION: đúng một nhịp}
{SPEED: tốc độ thực 1x — xem mục 7}
```

`ORDER` là câu hay bị quên nhất. Mỗi cảnh phải nói bó hoa **đã đi tới đâu**:
trần → đã buộc → đã cắt gốc → có lót trong → có giấy ngoài → có nơ. Không nói thì
model quấn ngược, và cảnh 5 lại về với cái nơ mà cảnh 7 mới thắt.

Viết bằng câu khẳng định, vì Veo và gpt-image đều không có negative prompt:
"no ribbon and no bow are on the bouquet yet", không viết "chưa thắt nơ".

---

## 7. Tốc độ — nói riêng, đừng để lẫn với tốc độ máy

Thợ hoa làm **nhanh và dứt khoát**. Tay họ không ngập ngừng.

Nhưng khối `MOTION` của chuẩn shot-sequence bảo máy "drifts slowly", và Veo áp
luôn cái "slowly" đó lên hành động — clip về ở nửa tốc độ, nhìn như slow motion.
Nhịp của **hành động** phải nói tách khỏi nhịp của **máy**:

```
Everything runs at normal real-time speed: the hands move at a florist's
brisk, practised working pace, quick and unhesitating. This is real-time
footage at 1x, not slow motion and not a slowed-down clip.
```

---

## 8. Checklist trước khi tiêu credit

Chạy trên **toàn bộ** bảng prompt, trước cảnh đầu tiên:

- [ ] Cảnh nào có hai tay thao tác — đã nói bó hoa tì vào đâu chưa? (mục 2)
- [ ] Cắt gốc có nằm **sau** buộc không?
- [ ] Buộc có quấn **3–4 vòng quanh điểm bó** không, hay chỉ "tie it"?
- [ ] Lớp lót trong có trước lớp giấy ngoài không?
- [ ] Nơ có nằm **sau** khi giấy đã khép không?
- [ ] Điểm bó, chỗ buộc dây, chỗ thắt nơ — có phải **cùng một chỗ** không?
- [ ] Kiểu Hàn: có câu nào tả giấy "phẳng, gọn" không? Phải là "nếp tự nhiên".
- [ ] Mỗi cảnh có nói bó đang ở **trạng thái quấn** nào không?
- [ ] Mọi prompt video có khối `SPEED` chưa?
- [ ] Cả bài dùng **một** kiểu gói chứ không trộn?

---

## 9. Lỗi model hay đẻ ra, và câu chữa

| Lỗi | Câu chữa, viết khẳng định |
|---|---|
| Bó lơ lửng dưới hai tay đang gói | "The bouquet stands upright on the counter, its cut stem ends resting on the surface and taking its own weight." |
| Tay thứ ba mọc ra để giữ bó | "Only two hands are in the frame." |
| Cắt gốc khi bó chưa buộc | "The binding twine is already wrapped three times around the binding point and the bunch is tied." |
| Nơ xuất hiện sớm | "No ribbon and no bow are on the bouquet yet." |
| Giấy Hàn ra phẳng lì như bìa | "The paper pleats naturally around the stems and the creases are left exactly as they fall." |
| Cành cài ngược chiều xoắn | "Every stem lies at the same angle and spirals in the same direction." |
| Slow motion | khối `SPEED`, mục 7 |
| Biển hiệu / chữ tự mọc trong tiệm | "Every surface in the shop is blank: no chalkboards, no signs, no posters, no price cards, no lettering of any kind anywhere in the frame." |

---

## Nguồn

- [Floral Design Institute — Hand-Tied Bouquet Tutorial](https://www.floraldesigninstitute.com/blogs/flower-school-video-library/hand-tied-bouequet-tutorial) — thứ tự dựng xoắn, cầm lỏng bằng ngón cái + ngón trỏ, buộc 3 vòng rồi mới cắt, bó phải tự đứng được
- [Singapore Florist — How to Wrap a Bouquet](https://www.singaporeflorist.com.sg/blogs/news/how-to-wrap-a-bouquet) — spiral 20°, xoay 1/4 vòng, điểm bó ở 1/3, quy trình Korean waterproof wrap 5 bước
- [Lover Florals — Different Types of Wrapping Styles](https://www.loverflorals.com/hk-rose-bouquet-blog/different-types-of-wrapping-styles-for-flower-bouquets) — phân biệt cone / hand-tied / Korean flat-wrap / transparent showcase
- [LocalFlower — How to Wrap Flowers: Florist Techniques & Materials](https://localflower.ca/blog/how-to-wrap-flowers) — chọn vật liệu theo dịp, kỹ thuật bọc gốc giữ nước
