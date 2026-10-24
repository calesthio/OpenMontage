# Prompt chuẩn — series "Dưới tán hoa"

Chuẩn viết prompt ảnh và video cho một chuỗi cảnh **diễn ra ở cùng một chỗ**.
Rút ra từ bản dựng 2 (anime 9:16, Ngày 10) sau khi phải sinh lại 3 trong 8 cảnh.

Đây là **luật**, không phải kịch bản: các khối cụ thể của từng tập viết thẳng
trong script sinh ảnh của tập đó, không chép vào đây.

---

## 1. Chuyện gì đã hỏng

Ba lỗi, 39 credits, đều truy về được đúng một câu prompt:

| Cảnh | Câu prompt đã viết | Model dựng ra | Vì sao |
|---|---|---|---|
| 4 | "she kneels on **the dry grass** and digs a small hole" | đào hố giữa bãi cỏ khô | Prompt tự mâu thuẫn: cảnh 5 và 8 viết "dark soil… edged with brick". Không phải model sai — **bản thân bộ prompt viết hai chỗ khác nhau** |
| 6 | "she tips a watering can over **the patch of soil**" | một dải đất hẹp cạnh lối đi, đã có cây mọc | "the patch" là mạo từ xác định trỏ vào thứ model chưa từng thấy. Mỗi ảnh sinh độc lập, **không tồn tại "the patch"** — model tự bịa một cái |
| 7 | "she has stood up and looks back over the patch of freshly turned soil" | đứng giẫm lên chính luống vừa gieo | Câu này nói cô **nhìn gì**, không nói cô **đứng ở đâu**. Chỗ trống thì model tự điền |

Prompt video lặp lại đúng khoảng trống đó: "she tips the watering can" không cấm
đi lại, nên clip cho cô vừa đi vừa tưới.

## 2. Nguyên nhân gốc

Bản dựng 2 ghim **nhân vật** rất chặt — dài tóc, kiểu váy, tay lửng, giày vải —
và kết quả là qua 8 cảnh trang phục và tóc không lệch một lần nào. Kỹ thuật đó
đúng và đã chứng minh được.

Nhưng **bối cảnh** thì chỉ được tả như phông nền: "khu vườn rộng bỏ hoang, cỏ
vàng, viền gạch thấp". Trong khi với một chuỗi 8 cảnh cùng một chỗ, bối cảnh
chính là thứ duy nhất khiến người xem tin đây là **một sự việc liên tục**. Nó
phải được ghim chặt ngang nhân vật.

Không cần kỹ thuật mới. Chỉ cần đem kỷ luật đã dùng cho danh từ thứ nhất áp
sang danh từ thứ hai.

## 3. Năm khối (trước là ba)

`STYLE` → `CHARACTER` → **`STAGE`** → **`ACTION`** → **`KHÔNG-CÓ-GÌ`**

Ba khối đầu **dán nguyên văn vào mọi prompt**, không diễn đạt lại. Diễn đạt lại
là cách trôi bắt đầu.

### STYLE — khoá phong cách
Ghim medium, bảng màu, chất ánh sáng, khung hình. Đặt **đầu tiên** để render
không bao giờ trôi về photoreal.

### CHARACTER — khoá người
Chỉ dùng thuộc tính **đo được**: độ dài tóc, màu tóc, kiểu váy, độ dài tay áo,
loại giày. Bỏ tính từ cảm xúc ("thanh thoát", "dịu dàng") — không tái lập được.

### STAGE — khoá chỗ đứng  ← khối mới, khối gánh việc
Ba câu, không thiếu câu nào:

1. **Một mảnh địa hình, tả bằng thuộc tính đo được.**
   "a wide rectangular raised bed of bare dark tilled soil, edged with a low
   red-brick wall, an old white-framed glasshouse standing directly behind it,
   dry pale-gold grass all around."
2. **Máy đặt đâu so với mảnh đó.** ("from behind her, looking across the bed
   toward the glasshouse")
3. **Chân nhân vật ở đâu.** ← câu bị quên, và là câu đắt nhất.
   "both feet on the grass outside the brick edge; she does not step on the soil."

Không bao giờ dùng "the patch", "the spot", "that area". Model không có trí
nhớ giữa các lần sinh — mạo từ xác định là một lời mời bịa.

### ACTION — một nhịp, cộng thứ đứng yên
Một hành động cho 6–10 giây. Rồi nói rõ **cái gì không đổi**:
"She does not walk. The bed stays empty — nothing is growing in it."

### Vật mang thương hiệu — có ở khối STAGE thì phải có ở mọi khung

Nếu `STAGE` chứa một vật mang logo (biển tên, tấm bảng, bao bì), vật đó phải
mang logo ở **mọi cảnh nó xuất hiện**, không chỉ những cảnh cận.

Đừng tự trấn an rằng "ở 720p tấm bảng nhỏ thì trống hay có logo cũng như nhau".
Trên nền đất trống, mắt người xem đi thẳng tới vật nhân tạo duy nhất trong
khung. Bảng trống ở bốn cảnh rồi có logo ở hai cảnh là lỗi liên tục đúng nghĩa,
không khác gì đổi bối cảnh.

Cách làm: mọi prompt tả mặt bảng **trống** — gpt-image và Veo đều bóp méo chữ có
dấu — rồi in logo vào từng khung bằng `scripts/stamp_logo_on_sign.py`, mỗi cảnh
một `--roi`. Giữ bảng ROI ngay trong script sinh của tập đó.

Hai chốt của công cụ in: nó **không biết có vật gì che tấm bảng**, nhân chồng
lên cả bàn tay đứng trước — bố cục phải để mặt bảng trống trải, tay đặt ở mép
dưới thì được, ngón tay giữa mặt bảng thì không. Và luôn in từ **bản gốc chưa
in**; in đè hai lần là logo chồng lên chính nó.

### KHÔNG-CÓ-GÌ — nói cái vắng mặt bằng câu khẳng định
Veo và gpt-image không có negative prompt. Nêu từng mâu thuẫn mà **riêng cảnh
này** có thể đẻ ra:
- cảnh 6: "The bed is empty — no plants, no seedlings, nothing growing in it yet."
- cảnh 8: "The soil is bare — there is NO seed lying on top of it."

## 4. Prompt ảnh — khung

```
{STYLE}{CHARACTER}{STAGE}
{ACTION: một nhịp + cái gì đứng yên}
{KHÔNG-CÓ-GÌ: mâu thuẫn riêng của cảnh này, viết khẳng định}
```

Với cảnh chỉ có bàn tay (3, 5, 8) thì bỏ CHARACTER, giữ STAGE — cận cảnh vẫn
phải cho thấy đúng nền đất và đúng viền gạch, nếu không cắt về cảnh rộng là lộ.

## 5. Prompt video — khung

Flow **sinh lại** chứ không phát ảnh, nên mọi ràng buộc phải nhắc lại. Prompt
video thêm ba thứ prompt ảnh không có:

```
{Máy: khối MOTION + hướng đi — slow push-in / slow rise / slow drift.
 KHÔNG dùng "locked-off", xem mục 7}
{ACTION: đúng một nhịp, viết lại từ prompt ảnh}
{ĐỨNG YÊN: cái gì không được đổi, viết thẳng}
{ambient: hai đến ba tiếng động hiện trường}
no dialogue, no music, no voices.
```

Ghi chú đã đo được:
- **Chữ và logo trong khung**: thứ giữ được chúng nguyên vẹn là câu "the sign
  itself stays perfectly still and unchanged — the lettering does not move, warp
  or alter" — **không phải** việc khoá máy. Ngày 10 dùng hai thứ cùng lúc nên
  không tách được thứ nào gánh việc, và đã quy công nhầm cho locked-off. Ngày 8
  tách ra đo: cảnh 8 giữ câu văn, bỏ locked-off, cho máy dâng lên — chuyển động
  4.49, và mặt biển giữ nguyên chữ suốt 8 giây. Câu văn gánh việc, khoá máy thì
  không. Xem mục 7.
- **Viết prompt bằng tiếng Anh** kể cả dự án tiếng Việt: bám thuật ngữ máy và
  ống kính chặt hơn hẳn.
- **Bắt buộc có `ambient:`** — thiếu thì Veo tự bịa lời thoại lẩm bẩm.
- Một nhịp một clip. Hai hành động đẻ ra một cú cắt mình không đặt và không sửa được.

## 6. Checklist trước khi tiêu credit

Chạy trên **toàn bộ** bảng prompt, trước cảnh đầu tiên:

- [ ] Mọi cảnh ngoại cảnh có khối `STAGE` giống nhau **từng chữ**?
- [ ] Có cảnh nào tả nền đất khác các cảnh còn lại không? (đây là lỗi cảnh 4)
- [ ] Có chữ "the patch" / "the spot" / "that area" nào còn sót? (lỗi cảnh 6)
- [ ] Mọi cảnh có người: đã nói **chân đứng ở đâu** chưa? (lỗi cảnh 7)
- [ ] Mỗi cảnh có đúng một hành động?
- [ ] Cảnh nào có thứ đã bị chôn/phủ ở cảnh trước — đã viết câu khẳng định là nó không lộ ra chưa?
- [ ] Prompt video có `ambient:` và `no dialogue` chưa?

Sau khi sinh xong: `python scripts/flow_continuity_check.py <clip-dir>`, rồi
quét bốn lượt theo `.agents/skills/flow-video/SKILL.md`. **Sửa xong một cảnh
phải quét lại cả tám** — sửa cảnh 4 mới lòi cảnh 6, sửa cảnh 6 mới lòi cảnh 7.

---

## 7. Chuyển động — đo, đừng tả

Bổ sung sau Ngày 8, khi ba cảnh về đúng như prompt viết mà nhìn vẫn như ảnh tĩnh.

### Chuyện gì đã hỏng

Ba cảnh mở đầu prompt bằng `"Locked-off ..."`. Flow làm đúng y lời. Nhưng đứng
cạnh các tập đã đăng thì lộ ra là ảnh chụp có gió — và **không ai phát hiện được
bằng cách xem từng cảnh một**, vì một cảnh tĩnh nhìn riêng không hỏng; nó chỉ
hỏng khi nằm cạnh một cảnh có chuyển động.

Cách bắt: `scripts/clip_motion.py` — sai khác trung bình giữa hai khung liên
tiếp, đo ở 10fps trên bản xám 96×170. Con số không có đơn vị, chỉ có nghĩa khi
so với clip khác đo cùng cách.

### Dải chuẩn của series

Đo trên tập đã đăng của `@duoitanhoaflowershop`:

| | mean |
|---|---|
| Cảnh có hình | **1.9 – 8.7** — không cảnh nào đứng yên |
| Thẻ chữ nền đen | 0.5 — thứ duy nhất gần như tĩnh trong cả bài |

- Dưới **1.5**: đọc ra thành ảnh tĩnh. (Ngày 8 lần đầu: 0.50 / 1.20 / 1.21)
- Trên **12**: nhanh hơn mọi thứ series từng đăng. (Ngày 8 lần đầu: 17.52)

Kết quả sau khi dán khối `MOTION` vào Ngày 8 và sinh lại:

| cảnh | trước | sau |
|---|---|---|
| 03 | 0.50 | **3.29** |
| 06 | 1.21 | **2.14** |
| 07 | 2.59 + một cú cắt Veo tự chèn ở 1.4s | **3.76**, hết cắt |
| 08 | 1.20, có người tự bước vào khung | **4.49**, khung sạch |

### Bốn luật

1. **Không cảnh nào locked-off.** Từ `"locked-off"` đã bị gỡ khỏi từ vựng viết
   prompt của series này — nó là tiếng Anh đúng cho thứ mình gõ ra và sai cho
   thứ mình cần. Dán khối `MOTION` vào **mọi** cảnh thay vì tả máy từng cảnh một.
2. **Chạy liên tục, biên độ nhỏ, tốc độ đều.** Không dừng, không tăng tốc. Khung
   cuối chỉ khác khung đầu một chút.
3. **Tốc độ mới là luật, hướng thì không.** Lần đầu mình rút ra "cảnh dưới lòng
   đất phải dâng lên" từ đúng **một** cảnh của **một** tập tham chiếu, rồi để cái
   luật bịa đó đẩy mình đi cắt một khung mở mới từ clip Veo cũ — nhét nét vẽ máy
   vào giữa một bộ tranh vẽ tay, đúng thứ mục 3 sinh ra để chặn. Hướng máy do
   khung mở quyết định: mở ở mặt đất thì chỉ có chúi xuống mới tới được rễ. Cái
   sai của lần đầu là **17.52 so với trần 8.7 của dải chuẩn**, không phải chiều đi.
4. **Một clip một cú máy.** `--cuts` bắt cú cắt Veo tự chèn (Ngày 8 cảnh 7 có một
   cú ở 1.4s). Không sửa được bằng prompt sau khi đã sinh — phải làm lại.

### Chốt sau khi sinh

```
python scripts/clip_motion.py projects/<tập>/assets/video --cuts
```

Chạy trước `flow_continuity_check.py`. Continuity check bắt lỗi **giữa** các
cảnh; cái này bắt lỗi **bên trong** một cảnh, và đó là chỗ Ngày 8 trượt.

### Khung mở phải là tranh gốc

Tập nào dùng khung mở do người gửi sang thì **chỉ** những khung đó được mở cảnh.
Cắt một khung ra từ clip đã sinh để lấp cảnh thiếu là đưa nét vẽ của model vào
giữa bộ tranh vẽ tay — ở khung tĩnh trông giống, nhưng Flow sinh lại từ nó nên
sai lệch được nhân lên suốt clip. Thiếu khung cho một nhịp thì **dùng lại một
khung có sẵn với cú máy khác**, đừng chế khung mới. `check()` của tập giữ danh
sách tên file gốc và chặn mọi khung ngoài danh sách.

### Cảnh không có gì trong khung mang phong cách

Cảnh "xuống lòng đất" của Ngày 8 trôi sang **ảnh chụp hai lần**, một lần ở khâu
sinh ảnh và một lần ở khâu sinh clip, dù `STYLE` luôn nằm đầu prompt. Lý do:
trong một khung chỉ có đất thì **không còn vật gì mang phong cách** để model
bám — không cửa kính, không khăn hoa, không nhà kính. Khung rộng có những thứ
đó nên không bao giờ trôi.

Hai chốt cho loại cảnh này:
- **Nhắc lại chất liệu ở CUỐI prompt**, không chỉ ở đầu. Vị trí cuối có trọng số
  cao hơn. Viết khẳng định: "it is a drawing, not a photograph: no photographic
  texture, no camera bokeh".
- **Giới hạn quãng đi của máy sao cho khung luôn còn một mảng mang phong cách.**
  Cảnh 5 mở từ ảnh macro trên mặt đất rồi chúi hẳn xuống, nên đến giữa clip trong
  khung chỉ còn đất — hết mốc mặt đất (Veo chôn luôn cái cây) và hết vật mang
  phong cách (render thành ảnh chụp). Cách chữa **không phải** vẽ thêm khung mở:
  đã thử vẽ một khung mặt cắt và nó ra hình cắt bổ kiểu sách sinh học, lạc khỏi
  chất macro của cả tập. Cách chữa là **ghim đường mặt đất ở lại trong khung**:
  "the surface of the soil stays visible as a clear horizontal line across the TOP
  of the frame for the entire shot". Chồi lúc nào cũng nhìn thấy ở trên nên không
  thể bị chôn, và trong khung lúc nào cũng còn mảng vẽ tay nên không trôi.

  Luật rút ra rộng hơn cảnh này: **một cú máy không được đi tới chỗ mà trong khung
  không còn gì thuộc về khung mở nữa.**

### Máy đẩy vào thì phải ghim nền lại bằng lời

Ngày 8 hỏng đúng kiểu này ở **hai** cảnh, nên không phải ngẫu nhiên:

| cảnh | Veo tự thêm gì | lúc nào |
|---|---|---|
| 3 | nền nhoè ra rồi **thay bằng một căn phòng khác** (bàn tròn, tách, mái kính) | 12.5s |
| 7 | một **chùm cỏ khô mọc ra giữa khung**, trước mặt nhân vật | 2.8s |

Cơ chế giống nhau: máy đẩy vào thì nền mất nét, mất nét thì với model nó thành
**khoảng trống**, và khoảng trống thì được lấp. `HOLD` không cứu được vì `HOLD`
liệt kê những vật **phải giữ nguyên**, không cấm việc **thêm vật mới**.

Nên mọi cảnh có push-in phải có thêm hai câu:

1. Tả thẳng nền là gì, kể cả khi nó nhoè: *"the background stays exactly what it
   is in the opening frame: the pale rim of the pot, the wooden sign, and beyond
   them the white window frames with the sunrise and the garden, softly out of
   focus."*
2. Cấm **thêm** bằng câu khẳng định, gọi tên đúng thứ nó hay bịa: *"that
   background must not dissolve, fade out or change into any other room, and no
   new plant, spray of dry grass, vase, table, cups or ornament ever appears in
   it."*

Và giới hạn quãng đẩy: *"closing in only a little — a short move that never
becomes a close-up."* Đẩy càng sâu thì phần khung mở còn lại càng ít.

### Rà bằng contact sheet, không bằng khung đầu/cuối

Cả hai lỗi trên đều **nằm giữa cảnh** và khung đầu lẫn khung cuối đều bình
thường. Xem hai đầu là không thấy. Rà bằng một khung mỗi 0.5 giây:

```
ffmpeg -i clip.mp4 -vf "fps=2,scale=200:-1,tile=6x2:margin=3:padding=3" -frames:v 1 sheet.png
```

`clip_motion.py` in kèm **thời điểm đỉnh** của mỗi clip — đó là chỗ đi xem trước
tiên. Cảnh 3 đỉnh 16.0, dưới ngưỡng cắt 20 nên đã bị bỏ qua; chính đỉnh đó là cú
tráo nền.

### Một con số ngoài dải là tín hiệu, không phải đề tài để tranh luận

Cảnh 5 đo 13.4, vượt trần 12. Lần đọc đầu tiên đã gạt nó đi bằng lý do "cảnh đi
xuyên hai nơi nên dải không áp dụng" — kết luận rút ra từ một dải 8 khung thu
nhỏ. Mở ra xem đúng cỡ thì clip hỏng hai chỗ: cây bị chôn trong đất, và render
đã thành ảnh chụp. **Phép đo đúng, lời bào chữa sai.**

Ngoài dải thì mở clip ra xem đúng cỡ, ở vài thời điểm, rồi mới kết luận. Nếu vẫn
thấy không áp dụng được thì phải nói bằng **thứ nhìn thấy trên màn hình**, không
bao giờ bằng lý lẽ về nguồn gốc của ngưỡng.

### Transition — đo trên tập đã đăng, đừng chọn theo cảm tính

Đo 6 nhát cắt của tập tham chiếu ở 30fps:

| nhát cắt | trải dài | loại |
|---|---|---|
| 5.10 / 10.20 / 15.30 / 20.40 / 34.20 | 0–0.06s | **cắt cứng** |
| 27.97 | **0.47s** | **chuyển mềm** |

**5/6 là cắt cứng.** Đúng một chỗ dùng chuyển mềm, và đó là chỗ nối hai cảnh
**dưới lòng đất** — hai góc nhìn của cùng một thế giới, trong cùng một khoảnh
khắc. Đổ hiệu ứng vào mọi nhát cắt không phải là làm cho mượt, đó là bỏ văn phạm
của series.

Luật: **cắt cứng mặc định. Chuyển mềm chỉ dùng khi hai cảnh liền nhau là cùng
một nơi trong cùng một khoảnh khắc**, và tối đa một chỗ trong cả bài.

Ngày 8 đặt ở `06` → `07`: cùng cô gái, cùng chỗ ngồi, hai nhịp liền nhau, rơi
đúng câu lật "Có lẽ chúng ta cũng vậy…".

```
python scripts/stitch_duoi_tan_hoa.py --dir <clips> --out <mp4>   --open-text "" --end-text "" --dissolve-into 7
```

Chuyển mềm là chồng lấn nên **bản master ngắn đi** đúng bằng độ dài của nó
(Ngày 8: 60.10 → 59.82s). Nhớ tính lại nếu đang canh theo `.srt`.

### Caption

Series đăng caption cháy vào hình, nhưng **đó là việc của khâu sau**. Bản master
giao ra để trần — không `drawtext`, không thẻ chữ. Đóng bài bằng thẻ chữ trên
**nền đen** (không phải chữ đè lên hình cuối) nếu tập đó cần.
