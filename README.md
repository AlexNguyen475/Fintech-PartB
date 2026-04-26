# 📡 MEXC Futures Signal Bot v2.0

> **Môn:** Công nghệ Tài chính (Fintech) — Đề thi Giữa kỳ  
> **Phần:** B — Robo-Advisor & Trading Futures (Tiền giả lập MEXC Demo)  
> **Phong cách:** An toàn — ưu tiên bảo toàn vốn, tỷ lệ Risk:Reward = 1:2  
> **Ngôn ngữ:** Python 3.10+  
> **Nền tảng chạy:** Google Colab (hoặc máy tính cá nhân)

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Kiến trúc và luồng dữ liệu](#2-kiến-trúc-và-luồng-dữ-liệu)
3. [Ba Alpha (chỉ báo kỹ thuật)](#3-ba-alpha-chỉ-báo-kỹ-thuật)
4. [Hệ thống lời khuyên](#4-hệ-thống-lời-khuyên)
5. [Hướng dẫn cài đặt và chạy](#5-hướng-dẫn-cài-đặt-và-chạy)
6. [Cấu trúc file log](#6-cấu-trúc-file-log)
7. [Ví dụ tín hiệu thực tế](#7-ví-dụ-tín-hiệu-thực-tế)
8. [Giải thích kinh tế từng Alpha](#8-giải-thích-kinh-tế-từng-alpha)
9. [Câu hỏi thường gặp](#9-câu-hỏi-thường-gặp)

---

## 1. Tổng quan hệ thống

Bot tự động quét **20 cặp USDT-M Futures** trên MEXC mỗi 30 giây, tính toán 3 chỉ báo kỹ thuật độc lập, tổng hợp tín hiệu và đưa ra **lời khuyên giao dịch cụ thể** (vào lệnh nào, bao nhiêu vốn, đặt stop-loss ở đâu, chốt lời ở đâu) gửi thẳng vào Telegram của người dùng.

**Điểm khác biệt so với bot thông thường:**
- Không chỉ phát tín hiệu mua/bán — mà **giải thích tại sao** và **hướng dẫn thực hiện**
- Hệ thống **điểm hội tụ 0–3**: chỉ khuyến nghị vào lệnh khi ≥ 2 alpha đồng thuận
- Phong cách **an toàn**: size nhỏ, đòn bẩy thấp, tỷ lệ Risk:Reward luôn ≥ 1:2
- Tránh spam Telegram: mỗi tín hiệu chỉ gửi 1 lần trong ~2.5 phút

---

## 2. Kiến trúc và luồng dữ liệu

```
┌─────────────────────────────────────────────────────────┐
│                  MEXC PUBLIC REST API                   │
│         (Không cần API key — hoàn toàn công khai)       │
└────────────────────────┬────────────────────────────────┘
                         │  Dữ liệu nến OHLCV (15 phút)
                         ▼
┌─────────────────────────────────────────────────────────┐
│              MODULE 1: THU THẬP DỮ LIỆU                 │
│  • Quét song song 20 cặp USDT-M Futures                 │
│  • Lấy 120 nến gần nhất (khung 15 phút)                 │
│  • Tự động retry nếu API lỗi                            │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│            MODULE 2: TÍNH TOÁN 3 ALPHA                  │
│  Alpha 1: RSI(14)        — đo quá mua / quá bán         │
│  Alpha 2: Volume Spike   — phát hiện khối lượng đột biến│
│  Alpha 3: Bollinger Bands— xác định vùng giá bất thường │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│         MODULE 3: TỔNG HỢP & ĐIỂM HỘI TỤ               │
│  • Tính điểm hội tụ (0–3 alpha cùng hướng)              │
│  • Phân loại: STRONG (3) / MEDIUM (2) / WEAK (1)        │
│  • Sinh lời khuyên: size, đòn bẩy, SL, TP              │
└──────────┬──────────────────────────┬───────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────┐       ┌──────────────────────────────┐
│ Terminal Dashboard│       │      Telegram Notification   │
│ (in mỗi 30 giây) │       │ (gửi khi MEDIUM hoặc STRONG) │
└──────────────────┘       └──────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────┐
│              FILE LOG: signals_log.csv                   │
│  Ghi nhận mọi tín hiệu để phân tích và nộp bài          │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Ba Alpha (chỉ báo kỹ thuật)

### Alpha 1 — RSI (Relative Strength Index)

| Tham số | Giá trị | Lý do chọn |
|---------|---------|------------|
| Chu kỳ | 14 nến | Tiêu chuẩn ngành, phổ biến nhất |
| Ngưỡng quá bán | < 32 | An toàn hơn 30 — tránh tín hiệu sớm |
| Ngưỡng quá mua | > 68 | An toàn hơn 70 — tránh tín hiệu sớm |

**Công thức:**
```
RS  = Trung bình tăng N kỳ / Trung bình giảm N kỳ
RSI = 100 - (100 / (1 + RS))
```

**Điều kiện phát tín hiệu:**
- RSI < 32 → **Tín hiệu LONG** (thị trường bán quá mức, kỳ vọng hồi phục)
- RSI > 68 → **Tín hiệu SHORT** (thị trường mua quá mức, kỳ vọng điều chỉnh)

---

### Alpha 2 — Volume Spike (Khối lượng bất thường)

| Tham số | Giá trị | Lý do chọn |
|---------|---------|------------|
| Chu kỳ MA | 20 nến | Đủ dài để phản ánh xu hướng volume trung bình |
| Ngưỡng spike | > 2.0x | Tín hiệu rõ ràng, tránh nhiễu nhỏ |

**Công thức:**
```
MA20_volume = Trung bình động 20 kỳ của khối lượng
Ratio       = Volume_hiện_tại / MA20_volume
Spike       = True nếu Ratio ≥ 2.0
```

**Điều kiện phát tín hiệu:**
- Volume > 2x MA20 → **Cảnh báo có lực lớn vào thị trường**
- Kết hợp với RSI: tăng độ tin cậy tín hiệu lên đáng kể

---

### Alpha 3 — Bollinger Bands (Dải Bollinger)

| Tham số | Giá trị | Lý do chọn |
|---------|---------|------------|
| Chu kỳ MA | 20 nến | Chuẩn phổ biến nhất |
| Số lần σ | 2.0 | Bao phủ ~95% biến động thông thường |

**Công thức:**
```
MA20  = Trung bình động 20 kỳ
σ     = Độ lệch chuẩn 20 kỳ
Upper = MA20 + 2σ
Lower = MA20 - 2σ
%B    = (Giá - Lower) / (Upper - Lower)
```

**Điều kiện phát tín hiệu:**
- %B ≤ 0.05 (giá chạm/dưới dải dưới) → **LONG**
- %B ≥ 0.95 (giá chạm/trên dải trên) → **SHORT**

---

## 4. Hệ thống lời khuyên

### Điểm hội tụ (Confluence Score)

Bot tính điểm từ 0 đến 3, mỗi alpha đồng hướng được +1 điểm:

```
+1 điểm  →  RSI xác nhận hướng (quá mua hoặc quá bán)
+1 điểm  →  Volume Spike xảy ra cùng thời điểm
+1 điểm  →  Bollinger Bands cùng hướng với RSI
```

### Bảng quyết định (phong cách AN TOÀN)

| Điểm | Xếp loại | Hành động | Size vốn | Đòn bẩy |
|------|----------|-----------|----------|---------|
| 3/3  | 🔥 STRONG | Vào lệnh | 20% vốn demo | Tối đa 3x |
| 2/3  | ⚡ MEDIUM | Cân nhắc vào | 10% vốn demo | Tối đa 3x |
| 1/3  | 💡 WEAK | Quan sát thêm | 0% (không vào) | — |
| 0/3  | NEUTRAL | Đứng ngoài | 0% | — |

### Cách tính Stop-Loss và Take-Profit

```
Stop-Loss   = Giá vào ± 1.5%  (âm với hướng lệnh)
Take-Profit = Giá vào ± 3.0%  (dương với hướng lệnh)
Risk:Reward = 1 : 2
```

**Ví dụ thực tế — Lệnh LONG BTC @ 94,000 USDT:**
```
Stop-Loss   = 94,000 × (1 - 1.5%) = 92,590 USDT
Take-Profit = 94,000 × (1 + 3.0%) = 96,820 USDT
Nếu thua: mất 1,410 USDT/BTC
Nếu thắng: lãi 2,820 USDT/BTC
```

---

## 5. Hướng dẫn cài đặt và chạy

### Bước 1 — Tạo Telegram Bot

1. Mở Telegram → tìm **@BotFather** → gửi `/newbot`
2. Đặt tên và username cho bot
3. Nhận **Token** (dạng `7123456789:AAHdq...`) → lưu lại
4. Tìm **@userinfobot** → gửi `/start` → nhận **Chat ID** (dạng `123456789`) → lưu lại

### Bước 2 — Mở Google Colab

Truy cập [colab.research.google.com](https://colab.research.google.com) → Tạo notebook mới

### Bước 3 — Cài thư viện

Tạo cell đầu tiên, dán và chạy:
```python
!pip install requests pandas numpy -q
```

### Bước 4 — Dán code và cấu hình

Tạo cell thứ hai, dán toàn bộ code từ file `mexc_signal_bot_v2.py`.

Tìm phần **BƯỚC BẮT BUỘC** ở đầu file và điền:
```python
TELEGRAM_TOKEN   = "token_bạn_lấy_từ_BotFather"
TELEGRAM_CHAT_ID = "chat_id_bạn_lấy_từ_userinfobot"
```

### Bước 5 — Chạy bot

Tạo cell thứ ba:
```python
run_bot()
```

Nhấn **Shift + Enter** → Bot khởi động, kiểm tra Telegram để xác nhận.

### Bước 6 — Giữ Colab không timeout

Mở **Developer Tools** của trình duyệt (phím F12) → tab **Console** → dán:
```javascript
function keepAlive() {
    console.log("Giữ Colab sống: " + new Date().toLocaleTimeString());
    document.querySelector("colab-connect-button").click();
}
setInterval(keepAlive, 60000);
```

---

## 6. Cấu trúc file log

Bot tự động ghi tín hiệu vào file `signals_log.csv` trong thư mục chạy.

| Cột | Kiểu | Ý nghĩa |
|-----|------|---------|
| `timestamp` | ISO 8601 | Thời điểm phát hiện tín hiệu |
| `symbol` | string | Cặp giao dịch (VD: BTC_USDT) |
| `price` | float | Giá tại thời điểm phát hiện |
| `rsi` | float | Giá trị RSI(14) |
| `rsi_dir` | string | LONG / SHORT / NEUTRAL |
| `rsi_desc` | string | Mô tả tín hiệu RSI |
| `vol_ratio` | float | Tỷ lệ volume / MA20 |
| `vol_spike` | bool | True nếu volume > 2x MA20 |
| `bb_signal` | string | LONG / SHORT / NEUTRAL |
| `bb_pct_b` | float | Vị trí giá trong dải Bollinger (0–1) |
| `bb_upper` | float | Dải trên Bollinger |
| `bb_lower` | float | Dải dưới Bollinger |
| `strength` | string | STRONG / MEDIUM / WEAK |
| `score` | int | Điểm hội tụ (0–3) |
| `action` | string | Lệnh khuyến nghị |
| `size_pct` | int | % vốn khuyến nghị |
| `leverage` | int | Đòn bẩy khuyến nghị |

---

## 7. Ví dụ tín hiệu thực tế

### Ví dụ 1 — Tín hiệu STRONG LONG

```
Terminal:
════════════════════════════════════════════════════════════════════════
  📡 MEXC FUTURES SIGNAL BOT v2  |  Lần quét #12  |  2026-04-25 14:30:00
  🛡  Phong cách: AN TOÀN  |  Đòn bẩy tối đa: 3x  |  SL: 1.5%  TP: 3.0%
════════════════════════════════════════════════════════════════════════
  🔥 STRONG  📈  SOL_USDT  @  142.5  📊 VOL 2.8x
  ├─ Alpha1  RSI = 28.4 < 32 → QUÁ BÁN
  ├─ Alpha2  Volume ratio = 2.8x MA20 ← SPIKE!
  ├─ Alpha3  BB Signal = LONG (%B = 0.03 | Lower=140.2 Upper=155.8)
  ├─ Điểm hội tụ: 3/3 alpha cùng hướng
  │
  ├─ 💬 LỆNH      : ✅ VÀO LỆNH LONG
  ├─ 📐 SIZE      : 20% vốn demo  |  Đòn bẩy: 3x
  ├─ 📌 VÀO LỆNH  : Vào MUA (LONG) với 20% vốn demo, đòn bẩy tối đa 3x.
  ├─ 🛑 STOP-LOSS  : Đặt Stop-Loss cách giá vào 1.5% xuống dưới điểm vào.
  ├─ 🎯 TAKE-PROFIT: Đặt Take-Profit cách giá vào 3.0% lên trên điểm vào.
  └─ ⚠ RỦI RO    : Không dùng quá 20% vốn. Thua 3 lệnh liên tiếp → dừng.
```

**Telegram nhận được:**
```
🔥 STRONG  📈 LONG
💎 SOL_USDT  @  142.5

📊 PHÂN TÍCH 3 ALPHA
• Alpha1 RSI : RSI = 28.4 < 32 → QUÁ BÁN
• Alpha2 VOL : ratio = 2.8x MA20
📊 VOLUME SPIKE (2.8x MA20)
• Alpha3 BB  : LONG (%B=0.03)
• Điểm hội tụ: 3/3 alpha cùng hướng

💬 KHUYẾN NGHỊ
• Lệnh     : ✅ VÀO LỆNH LONG
• Size     : 20% vốn  |  Đòn bẩy: 3x
• Stop-Loss : 1.5% xuống dưới điểm vào
• Take-Profit: 3.0% lên trên điểm vào
• Rủi ro   : Không dùng quá 20% vốn cho 1 lệnh.

🕐 2026-04-25T14:30:00.123+07:00
```

---

## 8. Giải thích kinh tế từng Alpha

### Tại sao chọn RSI?

Crypto giao dịch 24/7, thiếu market maker chuyên nghiệp như thị trường chứng khoán truyền thống. Điều này khiến **hành vi đám đông** (FOMO mua, panic bán) tạo ra các đỉnh và đáy cực đoan thường xuyên hơn. RSI đo lường chính xác trạng thái cực đoan đó và kỳ vọng giá sẽ mean-revert về giá trị hợp lý.

### Tại sao chọn Volume Spike?

Dữ liệu thực nghiệm cho thấy **smart money** (quỹ đầu tư lớn, whale) thường để lại dấu vết qua volume trước khi giá di chuyển mạnh. Khi volume đột biến > 2x trung bình mà giá chưa phản ứng mạnh, đây là cơ hội vào lệnh theo hướng RSI với xác suất cao hơn.

### Tại sao chọn Bollinger Bands?

Bollinger Bands đóng vai trò **xác nhận thứ ba** — khi RSI quá bán VÀ giá đang ở dải dưới BB, hai tín hiệu độc lập cùng chỉ về một hướng, làm tăng đáng kể xác suất thắng. Đây là nguyên tắc **hội tụ alpha** (alpha confluence) phổ biến trong quỹ định lượng.

### Tại sao chọn phong cách AN TOÀN?

Tham chiếu từ **bài học Knight Capital (2012)**: sử dụng đòn bẩy cao và size lớn mà không có hệ thống quản lý rủi ro đã khiến công ty mất 440 triệu USD trong 45 phút. Phong cách an toàn với đòn bẩy 3x, size 10–20%, stop-loss 1.5% giúp tài khoản demo sống sót đủ lâu để học và tích lũy đủ 10+ lệnh như đề thi yêu cầu.

---

## 9. Câu hỏi thường gặp

**Q: Bot có tự đặt lệnh không?**  
A: Không. Bot chỉ phân tích và gửi tín hiệu. Người dùng tự vào lệnh thủ công trên MEXC Demo — đúng với yêu cầu đề thi (Manual Trade).

**Q: Bot dùng API key của MEXC không?**  
A: Không cần. Bot chỉ dùng MEXC Public REST API — hoàn toàn miễn phí và không cần đăng nhập.

**Q: Colab bị timeout thì sao?**  
A: Dùng đoạn JavaScript giữ Colab sống (Bước 6). File log vẫn được lưu trong phiên Colab đang chạy.

**Q: Tại sao bot không gửi tín hiệu WEAK qua Telegram?**  
A: Để tránh spam. Tín hiệu WEAK chỉ có 1/3 alpha xác nhận — xác suất thắng thấp và không đủ điều kiện vào lệnh theo phong cách an toàn.

**Q: Làm sao tải file log về máy từ Colab?**  
A: Chạy lệnh sau trong một cell mới:
```python
from google.colab import files
files.download("signals_log.csv")
```

---

*README này là tài liệu kỹ thuật nộp kèm theo Phần B — Đề thi Giữa kỳ môn Công nghệ Tài chính.*
