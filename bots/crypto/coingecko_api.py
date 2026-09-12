"""
CoinGecko ochiq API'si orqali narx, hajm va tarixiy narx (RSI uchun) ma'lumotlarini
oladi. Binance.com ko'plab hududlardan (AQSh va ba'zi bulut IP diapazonlaridan)
kirishni geografik jihatdan bloklagani (HTTP 451) uchun shu bilan almashtirildi —
CoinGecko esa bunday cheklovga ega emas, istalgan server joylashuvidan ishlaydi.

MUHIM FARQLAR (Binance'ga nisbatan):

1. FYUCHERS MA'LUMOTLARI YO'Q — funding rate, Open Interest, Long/Short nisbati
   CoinGecko'da UMUMAN MAVJUD EMAS (u faqat spot narx/market-cap agregatori, fyuchers
   birjalarini kuzatmaydi). Shuning uchun bu ma'lumotlar butun kripto botidan olib
   tashlangan — coin kartalarida endi faqat narx, 24soatlik o'zgarish va RSI ko'rsatiladi.

2. SO'ROV CHASTOTASI ANCHA CHEKLANGAN — CoinGecko'ning o'zi rasman shunday deydi:
   kalitsiz (public) atigi 5-15 so'rov/daqiqa. Bepul ro'yxatdan o'tib "Demo" API
   kalit olsangiz (https://www.coingecko.com/en/api/pricing — ro'yxatdan o'tish
   bepul, karta talab qilinmaydi), 30 so'rov/daqiqaga barqaror ko'tariladi — .env'da
   COINGECKO_API_KEY qiling. Shu sababli bu modul har bir so'rov orasida SEZILARLI
   kutish (delay) qiladi, va kalit yo'q bo'lsa yanada ehtiyotkorroq (sekinroq) ishlaydi.
"""
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"

# 401 (kalit limiti tugagan) birinchi marta uchraganda True bo'ladi — shundan keyin
# navbatdagi har bir coin uchun behuda so'rov yubormasdan, darhol to'xtash mumkin
# (limit qayta tiklanmaguncha keyingi so'rovlar ham baribir 401 qaytaradi).
_quota_exhausted = False


def is_quota_exhausted() -> bool:
    return _quota_exhausted

# So'rovlar orasidagi standart kutish — CoinGecko'ning rasmiy chegarasidan xavfsiz
# pastroq turish uchun. API kalit bo'lsa (30/daqiqa chegara) tezroq, bo'lmasa
# (5-15/daqiqa) ancha ehtiyotkorroq.
def request_delay_seconds() -> float:
    return 2.2 if os.getenv("COINGECKO_API_KEY") else 4.5


def _headers() -> dict:
    key = os.getenv("COINGECKO_API_KEY")
    return {"x-cg-demo-api-key": key} if key else {}


def _get(path: str, params: dict | None = None, max_retries: int = 3) -> dict | list | None:
    """Umumiy GET so'rovi — 429 (rate limit) javobini kutib qayta urinadi, boshqa
    xatolarda logga yozib None qaytaradi (chaqiruvchi shu holatda o'sha coin/bosqichni
    o'tkazib yuborishi kerak, butun botni to'xtatmasdan).

    MUHIM (haqiqiy voqeada aniqlangan muammo): avval 401 (kalit limiti tugagan/
    noto'g'ri kalit) va boshqa HTTP xatolar bir xil, umumiy "CoinGecko xatoligi"
    deb logga yozilardi — bu 429 (vaqtinchalik, soniyalar ichida o'tadigan) bilan
    401 (KUNLIK/OYLIK LIMIT TUGAGAN — shu kun/oy davomida boshqa hech narsa
    ishlamaydi) orasidagi farqni yashirib qo'yardi. Natijada foydalanuvchi nima
    uchun ba'zi coinlarga sham chizilib, ba'zilariga chizilmasligini logdan bila
    olmasdi. Endi 401 xatosi ALOHIDA, ANIQ xabar bilan ajratiladi."""
    url = f"{BASE_URL}{path}"
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=_headers(), timeout=20)
        except requests.RequestException as exc:
            logger.warning("CoinGecko so'rovida tarmoq xatoligi (%s): %s", path, exc)
            return None

        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After", 15))
            logger.info("CoinGecko so'rov chastotasi chegarasiga yetdik, %.0fs kutilmoqda...", wait)
            time.sleep(wait)
            continue

        if resp.status_code == 401:
            global _quota_exhausted
            _quota_exhausted = True
            logger.error(
                "OGOHLANTIRISH: CoinGecko API kalitingiz rad etildi (401) — bu odatda "
                "KUNLIK YOKI OYLIK SO'ROV LIMITINGIZ TUGAGANI degani (vaqtinchalik "
                "429 emas — bu limit qayta tiklanmaguncha DAVOM ETADI). Shu sababdan "
                "ba'zi coinlarga ma'lumot (sham, RSI) chizilmay qolgan bo'lishi mumkin. "
                "coingecko.com/en/api/pricing sahifasida limit holatingizni tekshiring."
            )
            return None

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            logger.warning("CoinGecko xatoligi (%s): %s", path, exc)
            return None

        return resp.json()

    logger.warning("CoinGecko so'rovi %d urinishdan keyin ham rate-limit sababli muvaffaqiyatsiz (%s).", max_retries, path)
    return None


# Leveraged/exotic tokenlarni chetlab o'tish uchun (masalan "BTCUP", "3X-LONG-BTC")
_EXCLUDED_SUBSTRINGS = ("UP", "DOWN", "BULL", "BEAR", "3L", "3S", "2L", "2S")


def get_market_data(pages: int = 2, per_page: int = 250) -> list[dict]:
    """Market-cap bo'yicha eng katta `pages * per_page` tadan coinni bitta (yoki bir
    necha) so'rovda oladi. Har biri: symbol, last_price, price_change_pct,
    quote_volume (taxminiy — 24soatlik USD savdo hajmi), va keyingi bosqichlarda
    (RSI/hajm tarixi) kerak bo'ladigan `cg_id`."""
    all_coins = []
    for page in range(1, pages + 1):
        data = _get("/coins/markets", {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": per_page,
            "page": page,
            "price_change_percentage": "24h",
        })
        if not data:
            break
        for c in data:
            symbol = (c.get("symbol") or "").upper()
            if not symbol or any(x in symbol for x in _EXCLUDED_SUBSTRINGS):
                continue
            price = c.get("current_price")
            change = c.get("price_change_percentage_24h")
            volume = c.get("total_volume")
            if price is None or change is None or volume is None:
                continue
            all_coins.append({
                "symbol": symbol,
                "cg_id": c["id"],
                "last_price": float(price),
                "price_change_pct": float(change),
                "quote_volume": float(volume),
            })
        time.sleep(request_delay_seconds())
        if len(data) < per_page:
            break  # oxirgi sahifa
    return all_coins


def filter_by_volume(coins: list[dict], min_quote_volume: float = 1_000_000) -> list[dict]:
    return [c for c in coins if c["quote_volume"] >= min_quote_volume]


def get_market_chart(cg_id: str, days: int = 2) -> dict | None:
    """`cg_id` (masalan "bitcoin") uchun so'nggi `days` kunlik narx va hajm tarixini
    qaytaradi — {"closes": [...], "volumes": [...]} shaklida (eng eskisidan
    eng yangisiga qarab tartiblangan, Binance klines bilan bir xil format,
    shunda analysis.py/breakout_scanner.py o'zgarishsiz ishlayveradi).
    `days=2` odatda soatlik granulярlikni beradi (~48 nuqta) — RSI(14) uchun yetarli."""
    data = _get(f"/coins/{cg_id}/market_chart", {"vs_currency": "usd", "days": days})
    if not data or "prices" not in data:
        return None
    closes = [p[1] for p in data.get("prices", [])]
    volumes = [v[1] for v in data.get("total_volumes", [])]
    if not closes:
        return None
    return {"closes": closes, "volumes": volumes}


def get_ohlc_candles(cg_id: str, max_candles: int = 48) -> list[dict] | None:
    """`cg_id` uchun yaponcha sham (candlestick) ma'lumotini qaytaradi —
    [{"open":.., "high":.., "low":.., "close":.., "ts":..}, ...] shaklida,
    eng eskisidan eng yangisiga qarab.

    MUHIM (CoinGecko bepul tarifi cheklovi): "har soatda bitta sham"
    (interval=hourly) parametri FAQAT CoinGecko'ning PULLIK tarifida ishlaydi.
    Bepul ("Demo") tarifda granulярlik so'ralgan kun soniga qarab AVTOMATIK
    belgilanadi va o'zgartirib bo'lmaydi:
      - 1-2 kun: har 30 daqiqada bitta sham
      - 3-30 kun: har 4 soatda bitta sham
    Shuning uchun bu yerda `days=1` ishlatiladi (30 daqiqalik shamlar, taxminan
    48 tasi — foydalanuvchi bilan kelishilgan variant). Agar kelajakda
    CoinGecko'ning pullik tarifiga o'tsangiz, shu funksiyani `interval=hourly`
    parametri bilan yangilab, haqiqiy soatlik (va uzunroq tarixli) shamlarga
    o'tish mumkin bo'ladi."""
    data = _get(f"/coins/{cg_id}/ohlc", {"vs_currency": "usd", "days": 1})
    if not data:
        return None
    candles = [
        {"ts": c[0], "open": c[1], "high": c[2], "low": c[3], "close": c[4]}
        for c in data
    ]
    return candles[-max_candles:]
