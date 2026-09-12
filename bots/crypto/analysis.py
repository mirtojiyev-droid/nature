"""RSI hisoblash va narx o'zgarishlarini o'zbekcha izohli matnga aylantirish.

Eslatma: funding rate / OI / long-short (fyuchers) funksiyalari bu yerdan olib
tashlangan — CoinGecko'ga o'tilgach (Binance geografik cheklovi tufayli), bu
ma'lumotlar manbada umuman mavjud emas."""


def calculate_rsi(closes: list[float], period: int = 14) -> float | None:
    """Wilder'ning KLASSIK RSI(14) usuli — professional savdo platformalari
    (TradingView, MetaTrader va h.k.) ishlatadigan aynan shu formula.

    MUHIM (foydalanuvchi tahlili asosida tuzatilgan): avvalgi versiya har safar
    FAQAT so'nggi 14 ta o'zgarishning oddiy o'rtachasini olardi — bu "silliqlash
    xotirasi"ni yo'qotadi va TradingView/Binance kabi platformalar ko'rsatadigan
    RSI qiymatidan sezilarli farq qilishi mumkin edi. Wilder usulida esa har bir
    keyingi qiymat OLDINGI silliqlangan o'rtachaga asoslanib hisoblanadi
    (eksponensial silliqlash) — bu klassik, hamma tan olgan RSI ta'rifi."""
    if not closes or len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 50.0 if avg_gain == 0 else 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 1)


def rsi_explanation(rsi: float | None) -> str:
    if rsi is None:
        return "RSI: ma'lumot yetarli emas"
    if rsi < 30:
        return f"RSI {rsi} — narx so'nggi kunlarga nisbatan tez tushgan"
    if rsi > 70:
        return f"RSI {rsi} — narx so'nggi kunlarga nisbatan tez ko'tarilgan"
    return f"RSI {rsi} — o'rtacha, keskin harakat kuzatilmagan"


def rsi_status_short(rsi: float | None) -> str:
    """Kartadagi kichik RSI belgisi uchun juda qisqa holat so'zi."""
    if rsi is None:
        return "Ma'lumot yo'q"
    if rsi < 30:
        return "Sotib olingan"
    if rsi > 70:
        return "Qizib ketgan"
    return "O'rtacha"


def format_volume(volume: float) -> str:
    """Katta hajm raqamini o'qish oson formatga o'tkazadi: 48_600_000_000 -> "$48.6B"."""
    if volume >= 1_000_000_000:
        return f"${volume/1_000_000_000:.1f}B"
    if volume >= 1_000_000:
        return f"${volume/1_000_000:.1f}M"
    if volume >= 1_000:
        return f"${volume/1_000:.1f}K"
    return f"${volume:.0f}"


def get_top_movers(pairs: list[dict], top_n: int) -> tuple[list[dict], list[dict]]:
    """Eng ko'p o'sgan va eng ko'p tushgan `top_n` tadan coinni qaytaradi.

    MUHIM: agar likvid juftliklar soni juda kam bo'lsa (masalan atigi 15 ta, top_n=10),
    oddiy `sorted[:10]` + `sorted[-10:]` yondashuvi bir xil coinlarni IKKALA ro'yxatga
    ham qo'shib qo'yishi mumkin edi (masalan 5-10 oralig'idagi coinlar ham "gainer" ham
    "loser" sifatida chiqib ketardi). Shuning uchun "losers" ro'yxati "gainers"da
    bo'lmagan qolgan coinlar ichidan tanlanadi — ikkalasi hech qachon kesishmaydi."""
    sorted_pairs = sorted(pairs, key=lambda p: p["price_change_pct"], reverse=True)
    gainers = sorted_pairs[:top_n]
    remaining = sorted_pairs[top_n:]
    losers = list(reversed(remaining[-top_n:])) if remaining else []
    return gainers, losers


def enrich_with_rsi(coins: list[dict], klines_map: dict) -> list[dict]:
    enriched = []
    for coin in coins:
        k = klines_map.get(coin["symbol"])
        rsi = calculate_rsi(k["closes"]) if k else None
        enriched.append({**coin, "rsi": rsi, "rsi_note": rsi_explanation(rsi)})
    return enriched


def signed_num(value: float, decimals: int) -> str:
    v = f"{value:.{decimals}f}"
    return f"+{v}" if value >= 0 else v
