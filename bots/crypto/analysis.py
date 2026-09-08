"""RSI hisoblash va fyuchers ko'rsatkichlarini (funding, OI, long/short) o'zbekcha
izohli matnga aylantirish — kripto_bot_mobil.html'dagi analysis mantiqining porti."""


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


def funding_note(funding_rate: float | None) -> str:
    if funding_rate is None:
        return "Funding: fyuchers mavjud emas"
    pct = funding_rate * 100
    if pct > 0.001:
        return f"Funding {signed_num(pct, 3)}% — 'long' (o'sishga garov) qilganlar ko'proq"
    if pct < -0.001:
        return f"Funding {signed_num(pct, 3)}% — 'short' (tushishga garov) qilganlar ko'proq"
    return f"Funding {signed_num(pct, 3)}% — long va short deyarli muvozanatda"


def oi_note(oi_change_pct: float | None) -> str:
    if oi_change_pct is None:
        return "OI: fyuchers mavjud emas"
    if oi_change_pct > 1:
        return f"OI {signed_num(oi_change_pct, 1)}% — bozorga yangi pul kirmoqda"
    if oi_change_pct < -1:
        return f"OI {signed_num(oi_change_pct, 1)}% — pozitsiyalar yopilmoqda"
    return "OI deyarli o'zgarmagan"


def long_short_note(long_pct: float | None, short_pct: float | None) -> str:
    if long_pct is None or short_pct is None:
        return "Long/Short: fyuchers mavjud emas"
    return f"Treyderlarning {long_pct:.0f}% long, {short_pct:.0f}% short pozitsiyada"


def enrich_with_futures(coins: list[dict], futures_map: dict) -> list[dict]:
    enriched = []
    for coin in coins:
        m = futures_map.get(coin["symbol"], {})
        funding_rate = m.get("funding_rate")
        oi_change_pct = m.get("oi_change_pct")
        long_pct = m.get("long_pct")
        short_pct = m.get("short_pct")
        has_futures = funding_rate is not None or oi_change_pct is not None or long_pct is not None
        enriched.append({
            **coin,
            "funding_rate": funding_rate, "oi_change_pct": oi_change_pct,
            "long_pct": long_pct, "short_pct": short_pct,
            "has_futures": has_futures,
            "funding_note": funding_note(funding_rate) if has_futures else None,
            "oi_note": oi_note(oi_change_pct) if has_futures else None,
            "long_short_note": long_short_note(long_pct, short_pct) if has_futures else None,
        })
    return enriched
