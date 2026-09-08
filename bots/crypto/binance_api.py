"""
Binance ochiq (kalit talab qilmaydigan) API'lari orqali narx, hajm va fyuchers
ma'lumotlarini oladi. Bu — kripto_bot_mobil.html'dagi JS mantiqning Python porti.

MUHIM FARQ: brauzer versiyasida CORS proxy kerak edi (brauzer xavfsizlik siyosati
tufayli). Server tomonidagi Python skriptida bunday cheklov yo'q — to'g'ridan-to'g'ri
so'rov yuboriladi, proxy shart emas.

MUHIM (geografik cheklov): Binance.com ko'plab hudud/IP manzillardan (ayniqsa AQSh, va
ko'pincha bulut xizmatlari — AWS/GCP/Render/Railway va h.k. — IP diapazonlaridan)
kirishni TAQIQLAYDI (HTTP 451 "Service unavailable from a restricted location").
Bu — sizning kodingizdagi xato emas, Binance'ning o'zining geofencing siyosati. Agar
serveringiz shunday hududda joylashgan bo'lsa, bot ISHLAMAYDI va bu haqda aniq xabar
(BinanceGeoBlockedError) beradi — .env yoki kodni tuzatish yordam bermaydi, faqat
serverni boshqa hududga (masalan Frankfurt, Singapur) ko'chirish yoki Binance'ni
boshqa manbaga (masalan CoinGecko) almashtirish yordam beradi.
"""
import logging
import time

import requests

logger = logging.getLogger(__name__)

SPOT_BASE = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"


class BinanceGeoBlockedError(Exception):
    """Binance so'rovni geografik joylashuv sababli rad etganda ko'tariladi (HTTP 451
    yoki javobda "restricted location"/"Eligibility" so'zlari uchrasa)."""


def _check_geo_block(resp: requests.Response) -> None:
    if resp.status_code == 451 or "restricted location" in resp.text.lower() or "eligibility" in resp.text.lower():
        raise BinanceGeoBlockedError(
            "Binance bu server joylashgan hududdan (IP manzildan) kirishni rad etdi "
            "(odatda AQSh yoki ba'zi bulut xizmatlari IP diapazonlari uchun). Bu "
            "Binance'ning geografik cheklovi — kodni yoki .env'ni tuzatish yordam "
            "bermaydi. Yechim: (1) serverni boshqa hududga (masalan Render'da "
            "Frankfurt yoki Singapur) ko'chiring, yoki (2) ma'lumot manbasini "
            "Binance'dan boshqasiga (masalan CoinGecko) almashtiring."
        )


def get_all_24hr_tickers() -> list[dict]:
    resp = requests.get(f"{SPOT_BASE}/api/v3/ticker/24hr", timeout=20)
    _check_geo_block(resp)
    resp.raise_for_status()
    return resp.json()


def filter_usdt_pairs(tickers: list[dict], min_quote_volume: float = 1_000_000) -> list[dict]:
    """USDT juftliklarini, "leveraged token" (UP/DOWN/BULL/BEAR) larni chetlab o'tib va
    minimal likvidlik (kunlik savdo hajmi) chegarasidan past bo'lganlarni tashlab, filtrlaydi."""
    result = []
    excluded = ("UPUSDT", "DOWNUSDT", "BULLUSDT", "BEARUSDT")
    for t in tickers:
        symbol = t.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        if any(x in symbol for x in excluded):
            continue
        try:
            quote_volume = float(t["quoteVolume"])
            price_change_pct = float(t["priceChangePercent"])
            last_price = float(t["lastPrice"])
        except (KeyError, ValueError, TypeError):
            continue
        if quote_volume < min_quote_volume:
            continue
        result.append({
            "symbol": symbol,
            "last_price": last_price,
            "price_change_pct": price_change_pct,
            "quote_volume": quote_volume,
        })
    return result


def get_klines_full(symbol: str, interval: str = "1h", limit: int = 100) -> dict | None:
    try:
        resp = requests.get(
            f"{SPOT_BASE}/api/v3/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        closes = [float(k[4]) for k in data]
        volumes = [float(k[7]) for k in data]
        return {"closes": closes, "volumes": volumes}
    except (requests.RequestException, ValueError, IndexError) as exc:
        logger.warning("Klines olishda xatolik (%s): %s", symbol, exc)
        return None


def get_klines_batch(symbols: list[str], interval: str = "1h", limit: int = 100, delay: float = 0.15) -> dict:
    result = {}
    for symbol in symbols:
        klines = get_klines_full(symbol, interval, limit)
        if klines:
            result[symbol] = klines
        time.sleep(delay)
    return result


def get_all_funding_rates() -> dict:
    try:
        resp = requests.get(f"{FUTURES_BASE}/fapi/v1/premiumIndex", timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return {d["symbol"]: float(d["lastFundingRate"]) for d in data if "lastFundingRate" in d}
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning("Funding rate ro'yxatini olishda xatolik: %s", exc)
        return {}


def get_open_interest_change(symbol: str, period: str = "1h", limit: int = 25) -> float | None:
    try:
        resp = requests.get(
            f"{FUTURES_BASE}/futures/data/openInterestHist",
            params={"symbol": symbol, "period": period, "limit": limit},
            timeout=20,
        )
        if not resp.ok:
            return None
        data = resp.json()
        if not data:
            return None
        oi_values = [float(d["sumOpenInterest"]) for d in data]
        oi_before, oi_now = oi_values[0], oi_values[-1]
        if oi_before == 0:
            return None
        return round((oi_now - oi_before) / oi_before * 100, 2)
    except (requests.RequestException, ValueError, KeyError):
        return None


def get_long_short_ratio(symbol: str, period: str = "5m", limit: int = 1) -> tuple[float | None, float | None]:
    try:
        resp = requests.get(
            f"{FUTURES_BASE}/futures/data/globalLongShortAccountRatio",
            params={"symbol": symbol, "period": period, "limit": limit},
            timeout=20,
        )
        if not resp.ok:
            return None, None
        data = resp.json()
        if not data:
            return None, None
        latest = data[-1]
        long_pct = round(float(latest["longAccount"]) * 1000) / 10
        short_pct = round(float(latest["shortAccount"]) * 1000) / 10
        return long_pct, short_pct
    except (requests.RequestException, ValueError, KeyError):
        return None, None


def get_futures_metrics_batch(symbols: list[str], funding_map: dict, delay: float = 0.2) -> dict:
    result = {}
    for symbol in symbols:
        funding_rate = funding_map.get(symbol)
        oi_change_pct = get_open_interest_change(symbol)
        time.sleep(delay)
        long_pct, short_pct = get_long_short_ratio(symbol)
        time.sleep(delay)
        result[symbol] = {
            "funding_rate": funding_rate,
            "oi_change_pct": oi_change_pct,
            "long_pct": long_pct,
            "short_pct": short_pct,
        }
    return result
