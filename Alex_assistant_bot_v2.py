# ============================================================
#  MEXC FUTURES SIGNAL BOT v2.1 — Fintech Exam Part B
#  ✅ FIX: Timestamp đúng giờ Hà Nội (UTC+7)
#  ✅ FIX: Danh sách 20 mã đã xác nhận trên MEXC Demo
#
#  Alpha 1 : RSI(14)          — phát hiện quá mua / quá bán
#  Alpha 2 : Volume Spike     — phát hiện khối lượng bất thường
#  Alpha 3 : Bollinger Bands  — phát hiện breakout / mean-revert
#  Phân tích: Tổng hợp 3 alpha → đưa ra lời khuyên cụ thể
#  Thông báo: Terminal Dashboard + Telegram
# ============================================================


# ====================================================
# CELL 1 — CÀI THƯ VIỆN (chạy cell này TRƯỚC TIÊN)
# ====================================================
# Trên Google Colab, tạo cell riêng và chạy dòng này:
# !pip install requests pandas numpy pytz -q


import requests
import pandas as pd
import numpy as np
import time
import datetime
import csv
import os
import pytz

# ✅ FIX TIMEZONE: Luôn dùng giờ Hà Nội thực tế (UTC+7)
VN_TZ = pytz.timezone("Asia/Ho_Chi_Minh")


# ============================================================
# ★ BƯỚC BẮT BUỘC: ĐIỀN THÔNG TIN CỦA BẠN VÀO ĐÂY ★
# ============================================================

TELEGRAM_TOKEN   = "8751459921:AAEnefnZ6O1mfP8QmCBj92fCKtgfqbieBVY"
# Lấy từ @BotFather trên Telegram
# Ví dụ: "7123456789:AAHdqTcvCHxxxxxxxxxxxxxxxxx"

TELEGRAM_CHAT_ID = "8172586515"
# Lấy từ @userinfobot trên Telegram
# Ví dụ: "123456789"


# ============================================================
# CẤU HÌNH BOT
# ============================================================

# --- Danh sách 20 cặp quét — ĐÃ XÁC NHẬN có trên MEXC Demo ---
PAIRS = [
    # Crypto majors
    "BTC_USDT",        "ETH_USDT",        "SOL_USDT",
    "XRP_USDT",        "DOGE_USDT",       "SUI_USDT",
    # Crypto mid
    "LINK_USDT",       "ARB_USDT",        "SEI_USDT",
    "TRX_USDT",        "SHIB_USDT",       "PEPE_USDT",
    # Cổ phiếu tokenized
    "NVDA_USDT",       "TSLA_USDT",       "META_USDT",
    "MSTR_USDT",       "PLTR_USDT",       "AMD_USDT",
    # Hàng hóa
    "XAUT_USDT",       "WTI_USDT",
]

# --- Tham số chỉ báo ---
RSI_PERIOD        = 14     # Số nến tính RSI
RSI_OVERSOLD      = 32     # RSI < 32 → quá bán (an toàn hơn 30)
RSI_OVERBOUGHT    = 68     # RSI > 68 → quá mua (an toàn hơn 70)
VOLUME_MULTIPLIER = 2.0    # Volume > 2x MA20 → bất thường
BB_PERIOD         = 20     # Số nến Bollinger Bands
BB_STD            = 2.0    # Độ lệch chuẩn Bollinger Bands
KLINE_LIMIT       = 120    # Số nến lấy về (cần đủ để tính chỉ báo)
KLINE_INTERVAL    = "Min15"# Khung thời gian nến (15 phút)

# --- Cấu hình an toàn (phong cách conservative) ---
SAFE_LEVERAGE     = 3      # Đòn bẩy khuyến nghị tối đa
SAFE_SIZE_STRONG  = 20     # % vốn vào khi tín hiệu STRONG
SAFE_SIZE_MEDIUM  = 10     # % vốn vào khi tín hiệu MEDIUM
SAFE_SIZE_WEAK    = 0      # % vốn vào khi tín hiệu WEAK (không vào)
STOP_LOSS_PCT     = 1.5    # % stop-loss mỗi lệnh
TAKE_PROFIT_PCT   = 3.0    # % take-profit mỗi lệnh (tỷ lệ 1:2)

# --- Vận hành ---
SCAN_INTERVAL     = 30     # Quét lại mỗi 30 giây
LOG_FILE          = "signals_log.csv"
ALERT_ONLY_MEDIUM_UP = True  # Chỉ gửi Telegram khi MEDIUM trở lên


# ============================================================
# TIỆN ÍCH CHUNG
# ============================================================

def now():
    """Giờ thực tế Hà Nội (UTC+7) — đã fix timezone Colab"""
    return datetime.datetime.now(VN_TZ).strftime("%Y-%m-%d %H:%M:%S")

def now_iso():
    """Giờ thực tế Hà Nội dạng ISO 8601 — đã fix timezone Colab"""
    return datetime.datetime.now(VN_TZ).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] \
           + "+07:00"

def send_telegram(msg: str):
    """Gửi tin nhắn đến Telegram của bạn."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       msg,
            "parse_mode": "HTML"
        }, timeout=10)
        if r.status_code != 200:
            print(f"  [Telegram lỗi {r.status_code}] {r.text[:100]}")
    except Exception as e:
        print(f"  [Telegram exception] {e}")

def log_signal(row: dict):
    """Ghi tín hiệu vào file CSV để nộp bài."""
    exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=row.keys())
        if not exists:
            w.writeheader()
        w.writerow(row)


# ============================================================
# LẤY DỮ LIỆU MEXC PUBLIC API
# ============================================================

def fetch_klines(symbol: str) -> pd.DataFrame | None:
    """
    Lấy dữ liệu nến OHLCV từ MEXC Futures Public API.
    Không cần API key — hoàn toàn công khai.
    """
    url = f"https://contract.mexc.com/api/v1/contract/kline/{symbol}"
    try:
        r = requests.get(url, params={
            "interval": KLINE_INTERVAL,
            "limit":    KLINE_LIMIT
        }, timeout=10)
        d = r.json().get("data")
        if not d:
            return None
        df = pd.DataFrame({
            "time":   d["time"],
            "open":   pd.to_numeric(d["open"]),
            "high":   pd.to_numeric(d["high"]),
            "low":    pd.to_numeric(d["low"]),
            "close":  pd.to_numeric(d["close"]),
            "volume": pd.to_numeric(d["vol"]),
        }).sort_values("time").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"  [API lỗi {symbol}] {e}")
        return None


# ============================================================
# TÍNH TOÁN 3 ALPHA
# ============================================================

def calc_rsi(closes: pd.Series) -> float | None:
    """
    Alpha 1 — RSI(14)
    Công thức: RSI = 100 − 100/(1 + RS)
               RS  = trung bình tăng / trung bình giảm trong N kỳ
    Ý nghĩa  : Đo lường tốc độ và cường độ biến động giá.
               RSI < 32 → bán quá mức → khả năng hồi phục (LONG)
               RSI > 68 → mua quá mức → khả năng điều chỉnh (SHORT)
    """
    if len(closes) < RSI_PERIOD + 1:
        return None
    delta    = closes.diff()
    gain     = delta.clip(lower=0).rolling(RSI_PERIOD).mean()
    loss     = (-delta.clip(upper=0)).rolling(RSI_PERIOD).mean()
    rs       = gain / loss.replace(0, np.nan)
    rsi_val  = 100 - (100 / (1 + rs))
    return round(float(rsi_val.iloc[-1]), 2)

def calc_volume_spike(volumes: pd.Series) -> dict:
    """
    Alpha 2 — Volume Spike
    Công thức: ratio = volume_hiện_tại / MA20(volume)
    Ý nghĩa  : Volume đột biến > 2x MA20 = có lực lớn vào thị trường.
               Smart money thường để lại dấu vết volume trước khi giá bứt phá.
    """
    if len(volumes) < 21:
        return {"ratio": 0.0, "spike": False, "current": 0.0, "ma20": 0.0}
    ma20    = float(volumes.rolling(20).mean().iloc[-1])
    current = float(volumes.iloc[-1])
    ratio   = current / ma20 if ma20 > 0 else 0.0
    return {
        "ratio":   round(ratio, 2),
        "spike":   ratio >= VOLUME_MULTIPLIER,
        "current": round(current, 2),
        "ma20":    round(ma20, 2),
    }

def calc_bollinger(closes: pd.Series) -> dict:
    """
    Alpha 3 — Bollinger Bands (MA20 ± 2σ)
    Công thức: Upper = MA20 + 2×StdDev
               Lower = MA20 − 2×StdDev
    Ý nghĩa  : Xác định vùng giá bất thường. Khi giá chạm/phá dải:
               → Lower: quá bán, kỳ vọng hồi về MA (LONG)
               → Upper: quá mua, kỳ vọng về MA (SHORT)
               → %B cho biết giá đang ở đâu trong dải (0=lower, 1=upper)
    """
    if len(closes) < BB_PERIOD:
        return {"signal": "NEUTRAL", "pct_b": 0.5,
                "upper": 0.0, "lower": 0.0, "mid": 0.0}
    ma    = closes.rolling(BB_PERIOD).mean()
    std   = closes.rolling(BB_PERIOD).std()
    upper = float((ma + BB_STD * std).iloc[-1])
    lower = float((ma - BB_STD * std).iloc[-1])
    mid   = float(ma.iloc[-1])
    price = float(closes.iloc[-1])
    pct_b = (price - lower) / (upper - lower) if (upper - lower) > 0 else 0.5

    if pct_b <= 0.05:
        sig = "LONG"     # chạm/dưới dải dưới
    elif pct_b >= 0.95:
        sig = "SHORT"    # chạm/trên dải trên
    else:
        sig = "NEUTRAL"

    return {
        "signal": sig,
        "pct_b":  round(pct_b, 3),
        "upper":  round(upper, 5),
        "lower":  round(lower, 5),
        "mid":    round(mid, 5),
        "price":  round(price, 5),
    }


# ============================================================
# PHÂN TÍCH + LỜI KHUYÊN (phong cách AN TOÀN)
# ============================================================

def build_advice(rsi: float, vol: dict, bb: dict, rsi_dir: str) -> dict:
    """
    Tổng hợp 3 alpha → xếp loại tín hiệu → đưa ra lời khuyên cụ thể.

    Điểm số hội tụ (0–3):
      +1 nếu RSI xác nhận hướng
      +1 nếu Volume Spike xảy ra
      +1 nếu BB cùng hướng với RSI
    Score 3 → STRONG | Score 2 → MEDIUM | Score 1 → WEAK | Score 0 → NEUTRAL
    """
    if rsi_dir == "NEUTRAL":
        return {
            "strength":   "NEUTRAL",
            "score":       0,
            "action":     "⏸ ĐỨNG NGOÀI",
            "leverage":    0,
            "size_pct":    0,
            "entry_note": "Không có tín hiệu rõ ràng. Chờ cơ hội tốt hơn.",
            "sl_note":    "",
            "tp_note":    "",
            "risk_note":  "",
        }

    score = 1  # RSI đã xác nhận hướng
    if vol["spike"]:
        score += 1
    if bb["signal"] == rsi_dir:
        score += 1

    # Xếp loại
    if score == 3:
        strength = "🔥 STRONG"
        size_pct = SAFE_SIZE_STRONG
        action   = f"✅ VÀO LỆNH {'LONG' if rsi_dir=='LONG' else 'SHORT'}"
    elif score == 2:
        strength = "⚡ MEDIUM"
        size_pct = SAFE_SIZE_MEDIUM
        action   = f"🔶 CÂN NHẮC {'LONG' if rsi_dir=='LONG' else 'SHORT'} (thận trọng)"
    else:  # score == 1
        strength = "💡 WEAK"
        size_pct = 0
        action   = "⏸ QUAN SÁT THÊM — chưa đủ điều kiện vào lệnh"

    # Lời khuyên cụ thể (phong cách an toàn)
    if score >= 2:
        entry_note = (
            f"Vào {'MUA (LONG)' if rsi_dir=='LONG' else 'BÁN KHỐNG (SHORT)'} "
            f"với {size_pct}% vốn demo, đòn bẩy tối đa {SAFE_LEVERAGE}x."
        )
        sl_note = (
            f"Đặt Stop-Loss cách giá vào {STOP_LOSS_PCT}% "
            f"({'xuống dưới' if rsi_dir=='LONG' else 'lên trên'} điểm vào)."
        )
        tp_note = (
            f"Đặt Take-Profit cách giá vào {TAKE_PROFIT_PCT}% "
            f"({'lên trên' if rsi_dir=='LONG' else 'xuống dưới'} điểm vào). "
            f"Tỷ lệ Risk:Reward = 1:{int(TAKE_PROFIT_PCT/STOP_LOSS_PCT)}."
        )
        risk_note = (
            "⚠ Không dùng quá 20% vốn cho 1 lệnh. "
            "Nếu thua 3 lệnh liên tiếp → dừng giao dịch, xem lại chiến lược."
        )
    else:
        entry_note = "Chỉ 1/3 alpha xác nhận. Rủi ro cao, không khuyến nghị vào lệnh lúc này."
        sl_note    = ""
        tp_note    = ""
        risk_note  = "Kiên nhẫn chờ tín hiệu MEDIUM hoặc STRONG."

    return {
        "strength":   strength,
        "score":       score,
        "action":     action,
        "leverage":    SAFE_LEVERAGE if score >= 2 else 0,
        "size_pct":    size_pct,
        "entry_note": entry_note,
        "sl_note":    sl_note,
        "tp_note":    tp_note,
        "risk_note":  risk_note,
    }


def analyze(symbol: str) -> dict | None:
    """Phân tích đầy đủ 1 cặp và trả về dict tín hiệu + lời khuyên."""
    df = fetch_klines(symbol)
    if df is None or len(df) < 30:
        return None

    closes  = df["close"]
    volumes = df["volume"]

    rsi = calc_rsi(closes)
    vol = calc_volume_spike(volumes)
    bb  = calc_bollinger(closes)

    if rsi is None:
        return None

    price = float(closes.iloc[-1])

    # Xác định hướng RSI
    if rsi < RSI_OVERSOLD:
        rsi_dir  = "LONG"
        rsi_desc = f"RSI = {rsi} < {RSI_OVERSOLD} → QUÁ BÁN"
    elif rsi > RSI_OVERBOUGHT:
        rsi_dir  = "SHORT"
        rsi_desc = f"RSI = {rsi} > {RSI_OVERBOUGHT} → QUÁ MUA"
    else:
        rsi_dir  = "NEUTRAL"
        rsi_desc = f"RSI = {rsi} (trung tính)"

    advice = build_advice(rsi, vol, bb, rsi_dir)

    # Không trả về tín hiệu NEUTRAL (không đáng chú ý)
    if advice["strength"] == "NEUTRAL":
        return None

    return {
        # Thông tin cơ bản
        "timestamp":   now_iso(),
        "symbol":      symbol,
        "price":       price,
        # Alpha 1
        "rsi":         rsi,
        "rsi_dir":     rsi_dir,
        "rsi_desc":    rsi_desc,
        # Alpha 2
        "vol_ratio":   vol["ratio"],
        "vol_spike":   vol["spike"],
        # Alpha 3
        "bb_signal":   bb["signal"],
        "bb_pct_b":    bb["pct_b"],
        "bb_upper":    bb["upper"],
        "bb_lower":    bb["lower"],
        # Lời khuyên
        "strength":    advice["strength"],
        "score":       advice["score"],
        "action":      advice["action"],
        "size_pct":    advice["size_pct"],
        "leverage":    advice["leverage"],
        "entry_note":  advice["entry_note"],
        "sl_note":     advice["sl_note"],
        "tp_note":     advice["tp_note"],
        "risk_note":   advice["risk_note"],
    }


# ============================================================
# HIỂN THỊ TERMINAL DASHBOARD
# ============================================================

SEP = "=" * 72

def print_dashboard(signals: list, scan_count: int):
    print(f"\n{SEP}")
    print(f"  📡 MEXC FUTURES SIGNAL BOT v2  |  Lần quét #{scan_count}  |  {now()}")
    print(f"  🛡  Phong cách: AN TOÀN  |  Đòn bẩy tối đa: {SAFE_LEVERAGE}x  |  "
          f"SL: {STOP_LOSS_PCT}%  TP: {TAKE_PROFIT_PCT}%")
    print(SEP)

    if not signals:
        print("  ✅ Không có tín hiệu đáng chú ý lúc này.")
        print(f"  🔄 Đang theo dõi {len(PAIRS)} cặp — quét lại sau {SCAN_INTERVAL}s...")
    else:
        strong = [s for s in signals if "STRONG" in s["strength"]]
        medium = [s for s in signals if "MEDIUM" in s["strength"]]
        weak   = [s for s in signals if "WEAK"   in s["strength"]]

        print(f"  🚨 Phát hiện {len(signals)} tín hiệu "
              f"({len(strong)} STRONG | {len(medium)} MEDIUM | {len(weak)} WEAK)\n")

        for s in signals:
            dir_emoji = "📈" if s["rsi_dir"] == "LONG" else "📉"
            vol_tag   = f"  📊 VOL {s['vol_ratio']}x" if s["vol_spike"] else ""
            print(f"  {s['strength']}  {dir_emoji}  {s['symbol']}  @  {s['price']}{vol_tag}")
            print(f"  ├─ Alpha1  {s['rsi_desc']}")
            print(f"  ├─ Alpha2  Volume ratio = {s['vol_ratio']}x MA20"
                  + (" ← SPIKE!" if s["vol_spike"] else ""))
            print(f"  ├─ Alpha3  BB Signal = {s['bb_signal']}  "
                  f"(%B = {s['bb_pct_b']}  |  Lower={s['bb_lower']}  Upper={s['bb_upper']})")
            print(f"  ├─ Điểm hội tụ: {s['score']}/3 alpha cùng hướng")
            print(f"  │")
            print(f"  ├─ 💬 LỆNH     : {s['action']}")
            if s["size_pct"] > 0:
                print(f"  ├─ 📐 SIZE     : {s['size_pct']}% vốn demo  |  Đòn bẩy: {s['leverage']}x")
                print(f"  ├─ 📌 VÀO LỆNH : {s['entry_note']}")
                print(f"  ├─ 🛑 STOP-LOSS : {s['sl_note']}")
                print(f"  ├─ 🎯 TAKE-PROFIT: {s['tp_note']}")
            print(f"  └─ ⚠ RỦI RO   : {s['risk_note']}")
            print()

    print(f"  ⏱  Quét tiếp theo sau {SCAN_INTERVAL} giây...")
    print(SEP)


# ============================================================
# GỬI TELEGRAM VỚI LỜI KHUYÊN ĐẦY ĐỦ
# ============================================================

def notify_telegram_signal(s: dict):
    dir_emoji = "📈 LONG" if s["rsi_dir"] == "LONG" else "📉 SHORT"
    vol_line  = (f"\n📊 <b>VOLUME SPIKE</b> ({s['vol_ratio']}x MA20)"
                 if s["vol_spike"] else "")

    if s["size_pct"] > 0:
        trade_block = (
            f"\n\n💬 <b>KHUYẾN NGHỊ</b>\n"
            f"• Lệnh     : {s['action']}\n"
            f"• Size     : {s['size_pct']}% vốn  |  Đòn bẩy: {s['leverage']}x\n"
            f"• Vào lệnh : {s['entry_note']}\n"
            f"• Stop-Loss : {s['sl_note']}\n"
            f"• Take-Profit: {s['tp_note']}\n"
            f"• Rủi ro   : {s['risk_note']}"
        )
    else:
        trade_block = (
            f"\n\n💬 <b>KHUYẾN NGHỊ</b>\n"
            f"• {s['action']}\n"
            f"• {s['risk_note']}"
        )

    msg = (
        f"{s['strength']}  {dir_emoji}\n"
        f"💎 <b>{s['symbol']}</b>  @  <code>{s['price']}</code>\n\n"
        f"📊 <b>PHÂN TÍCH 3 ALPHA</b>\n"
        f"• Alpha1 RSI : {s['rsi_desc']}\n"
        f"• Alpha2 VOL : ratio = {s['vol_ratio']}x MA20{vol_line}\n"
        f"• Alpha3 BB  : {s['bb_signal']} (%B={s['bb_pct_b']})\n"
        f"• Điểm hội tụ: {s['score']}/3 alpha cùng hướng"
        f"{trade_block}\n\n"
        f"🕐 {s['timestamp']}"
    )
    send_telegram(msg)


# ============================================================
# VÒNG LẶP CHÍNH
# ============================================================

def run_bot():
    """Khởi động bot — quét liên tục mỗi SCAN_INTERVAL giây."""

    # Kiểm tra token
    if "ĐIỀN" in TELEGRAM_TOKEN or "ĐIỀN" in TELEGRAM_CHAT_ID:
        print("=" * 60)
        print("⚠️  CHƯA ĐIỀN TELEGRAM_TOKEN hoặc TELEGRAM_CHAT_ID!")
        print("   Hãy điền vào phần CẤU HÌNH ở đầu file rồi chạy lại.")
        print("=" * 60)
        return

    # Thông báo khởi động qua Telegram
    start_msg = (
        "🤖 <b>MEXC Signal Bot v2 đã khởi động!</b>\n\n"
        f"📋 Quét {len(PAIRS)} cặp USDT-M Futures\n"
        f"🔍 Alpha 1: RSI({RSI_PERIOD})\n"
        f"🔍 Alpha 2: Volume Spike (>{VOLUME_MULTIPLIER}x MA20)\n"
        f"🔍 Alpha 3: Bollinger Bands (MA{BB_PERIOD} ± {BB_STD}σ)\n\n"
        f"🛡 Phong cách: AN TOÀN\n"
        f"   Đòn bẩy tối đa: {SAFE_LEVERAGE}x\n"
        f"   Size STRONG: {SAFE_SIZE_STRONG}% vốn\n"
        f"   Size MEDIUM: {SAFE_SIZE_MEDIUM}% vốn\n"
        f"   Stop-Loss: {STOP_LOSS_PCT}% | Take-Profit: {TAKE_PROFIT_PCT}%\n\n"
        f"⏱ Tần suất quét: mỗi {SCAN_INTERVAL} giây\n"
        f"🕐 Bắt đầu: {now()}"
    )
    send_telegram(start_msg)
    print("\n🚀 Bot khởi động thành công! Kiểm tra Telegram của bạn.")
    print(f"   Đang quét {len(PAIRS)} cặp mỗi {SCAN_INTERVAL} giây...\n")

    scan_count  = 0
    sent_signals = set()   # Tránh spam cùng 1 tín hiệu liên tiếp

    while True:
        scan_count += 1
        signals = []

        for symbol in PAIRS:
            result = analyze(symbol)
            if result:
                signals.append(result)
                log_signal({k: v for k, v in result.items()
                            if k not in ("entry_note","sl_note","tp_note","risk_note")})
            time.sleep(0.4)  # tránh rate-limit MEXC

        # Sắp xếp: STRONG → MEDIUM → WEAK
        order = {"🔥 STRONG": 0, "⚡ MEDIUM": 1, "💡 WEAK": 2}
        signals.sort(key=lambda x: order.get(x["strength"], 9))

        # In terminal
        print_dashboard(signals, scan_count)

        # Gửi Telegram (chỉ MEDIUM + STRONG, tránh spam)
        for s in signals:
            key = f"{s['symbol']}_{s['rsi_dir']}_{s['strength']}"
            if key not in sent_signals:
                if ALERT_ONLY_MEDIUM_UP and "WEAK" not in s["strength"]:
                    notify_telegram_signal(s)
                    sent_signals.add(key)
                    time.sleep(0.5)

        # Reset cache tín hiệu sau 5 lần quét (~2.5 phút)
        if scan_count % 5 == 0:
            sent_signals.clear()

        time.sleep(SCAN_INTERVAL)


# ============================================================
# ĐIỂM KHỞI CHẠY
# ============================================================

if __name__ == "__main__":
    run_bot()
