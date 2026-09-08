"""RSI hisoblash va narx o'zgarishlarini o'zbekcha izohli matnga aylantirish —
kripto_bot_mobil.html'dagi analysis mantiqining porti.

Eslatma: funding rate / OI / long-short (fyuchers) funksiyalari bu yerdan olib
tashlangan — CoinGecko'ga o'tilgach (Binance geografik cheklovi tufayli), bu
ma'lumotlar manbada umuman mavjud emas."""


def calculate_rsi(closes: list[float], period: int = 14) -> float | None:
    if not closes or len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gains.append(delta if delta > 0 else 0)
        losses.append(-delta if delta < 0 else 0)
    last_gains = gains[-period:]
    last_losses = losses[-period:]
    avg_gain = sum(last_gains) / period
    avg_loss = sum(last_losses) / period
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
