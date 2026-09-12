"""
Kripto bozor boti — kripto_bot_mobil.html'dagi mantiqning to'liq Python porti.

MUHIM (manba tarixi): dastlab Binance API ishlatilgan edi, lekin Binance.com AQSh va
ba'zi bulut serverlari (shu jumladan Render) IP diapazonlaridan kirishni geografik
sabablarga ko'ra bloklagani (HTTP 451) uchun CoinGecko'ga o'tkazildi. CoinGecko'da
fyuchers ma'lumotlari (funding rate, Open Interest, Long/Short nisbati) mavjud emas —
shuning uchun bu bot endi faqat narx/hajm/RSI'ga asoslanadi.

Har ishga tushganda:
  1. CoinGecko'dan eng katta bozor-qiymatli coinlarni oladi, likvidlik bo'yicha filtrlaydi.
  2. Eng ko'p o'sgan/tushgan TOP_N coinni tanlaydi, RSI hisoblaydi.
  3. Har bir coin uchun alohida karta (PNG) chizib, kanalga joylaydi.
  4. (yoqilgan bo'lsa) "Kuzatish ro'yxati" — hajm portlashi ko'rsatayotgan (erta signal)
     coinlarni skanerlab, alohida joylaydi.
  5. (yoqilgan bo'lsa) So'nggi kripto yangiliklarini bitta matnli xabar sifatida joylaydi.

ESLATMA (tezlik): CoinGecko'ning bepul API'si so'rov chastotasini qattiq cheklaydi
(kalitsiz 5-15/daqiqa, "Demo" kalit bilan 30/daqiqa — .env'da COINGECKO_API_KEY).
Shuning uchun bu bot bir marta ishga tushishi Binance versiyasiga qaraganda ancha
sekinroq (bir necha daqiqa) davom etishi mumkin — bu normal, xato emas.
"""
import logging
import os
import time

from dotenv import load_dotenv

from shared.telegram_poster import TelegramPoster
from . import coingecko_api
from .analysis import calculate_rsi, get_top_movers, rsi_explanation
from .breakout_scanner import breakout_notes, scan_breakout_candidates
from .captions import build_breakout_caption, build_caption_single, build_poll_question
from .card_builder import build_breakout_card_image, build_coin_card_image
from .news_fetcher import build_news_caption, fetch_latest_news

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.lower() == "true"


def _enrich_with_rsi_and_candles(coins: list[dict], candles_map: dict) -> list[dict]:
    """Har bir coinga /ohlc'dan olingan sham ma'lumotini ("candles") va shu
    ma'lumotdan hisoblangan RSI'ni qo'shadi — endi ikkalasi ham BITTA CoinGecko
    so'rovidan kelib chiqadi (avval RSI uchun /market_chart, shamlar uchun
    alohida /ohlc kerak bo'lardi — bu ikki barobar sekinroq bo'lardi)."""
    enriched = []
    for coin in coins:
        candles = candles_map.get(coin["symbol"])
        rsi = None
        if candles and len(candles) >= 15:
            closes = [c["close"] for c in candles]
            rsi = calculate_rsi(closes)
        enriched.append({**coin, "rsi": rsi, "rsi_note": rsi_explanation(rsi), "candles": candles})
    return enriched


def run_once() -> int:
    load_dotenv()

    bot_token = os.getenv("CRYPTO_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("CRYPTO_TELEGRAM_CHANNEL_ID")
    if not bot_token or not channel_id:
        logger.error("CRYPTO_TELEGRAM_BOT_TOKEN (yoki TELEGRAM_BOT_TOKEN) va CRYPTO_TELEGRAM_CHANNEL_ID kerak.")
        return 1

    top_n = _env_int("CRYPTO_TOP_N", 10)
    min_volume = _env_float("CRYPTO_MIN_VOLUME", 1_000_000)
    post_delay = _env_float("CRYPTO_POST_DELAY_SECONDS", 2.5)
    news_count = _env_int("CRYPTO_NEWS_COUNT", 5)
    # CoinGecko'ning qattiq so'rov chastotasi chegarasi tufayli, standart tekshirish
    # hajmi Binance versiyasidagidan (60) ancha kichraytirilgan — aks holda bitta
    # ishga tushirish o'nlab daqiqa davom etib ketishi mumkin edi.
    breakout_scan_size = _env_int("CRYPTO_BREAKOUT_SCAN_SIZE", 20)
    breakout_top_n = _env_int("CRYPTO_BREAKOUT_TOP_N", 5)
    volume_multiplier = _env_float("CRYPTO_VOLUME_MULTIPLIER", 3.0)
    enable_breakout = _env_bool("CRYPTO_ENABLE_BREAKOUT", True)
    enable_news = _env_bool("CRYPTO_ENABLE_NEWS", True)
    enable_poll = _env_bool("CRYPTO_ENABLE_POLL", True)
    translate_news = _env_bool("CRYPTO_TRANSLATE_TO_UZBEK", True)

    poster = TelegramPoster(bot_token, channel_id)

    logger.info("CoinGecko'dan bozor ma'lumotlari olinmoqda...")
    all_coins = coingecko_api.get_market_data(pages=2)
    if not all_coins:
        logger.error("KRIPTO BOT TO'XTATILDI: CoinGecko'dan hech qanday ma'lumot olinmadi (tarmoq/rate-limit muammosi bo'lishi mumkin).")
        return 1

    liquid_coins = coingecko_api.filter_by_volume(all_coins, min_volume)
    logger.info("Tahlil uchun %d ta likvid coin topildi (jami %d tadan).", len(liquid_coins), len(all_coins))

    gainers, losers = get_top_movers(liquid_coins, top_n)
    shortlist = gainers + losers
    shortlist_symbols = {c["symbol"] for c in shortlist}

    # MUHIM (optimallashtirilgan): avval RSI uchun /market_chart, sham grafigi uchun
    # ALOHIDA /ohlc so'rovi kerak bo'lardi (har bir coin uchun IKKI so'rov, ya'ni
    # CoinGecko'ning qattiq tezlik chegarasida ikki barobar sekinroq). Endi FAQAT
    # /ohlc chaqiriladi — undagi "close" narxlaridan RSI ham hisoblanadi, sham
    # tanalari esa to'g'ridan-to'g'ri o'sha ma'lumotdan olinadi. Bitta so'rov —
    # ikkita natija.
    logger.info("Narx tarixi (RSI + sham grafigi uchun) olinmoqda (%d ta coin, CoinGecko tezlik chegarasi tufayli bu bir necha daqiqa davom etishi mumkin)...", len(shortlist))
    candles_map = {}
    for coin in shortlist:
        # MUHIM (haqiqiy voqeada aniqlangan xato): agar kalit limiti (401) allaqachon
        # tugagan bo'lsa, qolgan HAR BIR coin uchun ham baribir 401 qaytadi — bu holda
        # yana so'rov yuborib, yana kutish shunchaki VAQT YO'QOTISH (limit shu kun/oy
        # davomida qayta tiklanmaydi). Shuning uchun birinchi 401'dan keyin darhol
        # to'xtaymiz, qolganlarga esa "sham/RSI yo'q" holatida davom etamiz.
        if coingecko_api.is_quota_exhausted():
            logger.warning(
                "CoinGecko kalit limiti tugagani aniqlandi — qolgan %d ta coin uchun "
                "sham/RSI so'ralmaydi (ular kartada shamsiz, RSI'siz chiqadi).",
                len(shortlist) - len(candles_map),
            )
            break
        candles = coingecko_api.get_ohlc_candles(coin["cg_id"], max_candles=48)
        if candles:
            candles_map[coin["symbol"]] = candles
        time.sleep(coingecko_api.request_delay_seconds())

    if candles_map:
        logger.info("Sham/RSI ma'lumoti %d/%d ta coin uchun muvaffaqiyatli olindi.", len(candles_map), len(shortlist))

    top_gainers = _enrich_with_rsi_and_candles(gainers, candles_map)
    top_losers = _enrich_with_rsi_and_candles(losers, candles_map)

    sent = 0
    total = len(top_gainers) + len(top_losers)
    logger.info("Jami %d ta alohida coin xabari yuborilmoqda...", total)

    for i, coin in enumerate(top_gainers):
        rank = i + 1
        image = build_coin_card_image(coin, True, rank)
        caption = build_caption_single(coin, True, rank)
        if poster.post_photo_bytes(image, caption):
            sent += 1
            logger.info("  [%d/%d] %s (o'suvchi #%d) yuborildi.", sent, total, coin["symbol"], rank)
            if enable_poll:
                question, options = build_poll_question(coin["symbol"])
                poster.post_poll(question, options)
        else:
            logger.error("%s (o'suvchi #%d) yuborishda xatolik.", coin["symbol"], rank)
        time.sleep(post_delay)

    for i, coin in enumerate(top_losers):
        rank = i + 1
        image = build_coin_card_image(coin, False, rank)
        caption = build_caption_single(coin, False, rank)
        if poster.post_photo_bytes(image, caption):
            sent += 1
            logger.info("  [%d/%d] %s (tushuvchi #%d) yuborildi.", sent, total, coin["symbol"], rank)
            if enable_poll:
                question, options = build_poll_question(coin["symbol"])
                poster.post_poll(question, options)
        else:
            logger.error("%s (tushuvchi #%d) yuborishda xatolik.", coin["symbol"], rank)
        time.sleep(post_delay)

    if enable_breakout:
        logger.info("Kuzatish ro'yxati uchun %d ta qo'shimcha coin skanerlanmoqda...", breakout_scan_size)
        remaining = [c for c in liquid_coins if c["symbol"] not in shortlist_symbols]
        remaining.sort(key=lambda c: c["quote_volume"], reverse=True)
        remaining = remaining[:breakout_scan_size]
        try:
            candidates = scan_breakout_candidates(
                remaining,
                volume_multiplier=volume_multiplier,
                top_n=breakout_top_n,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Kuzatish ro'yxatini skanerlashda xatolik.")
            candidates = []

        if candidates:
            logger.info("%d ta nomzod topildi, yuborilmoqda...", len(candidates))
            for i, cand in enumerate(candidates):
                rank = i + 1
                # Sham grafigi uchun: breakout_scanner allaqachon /market_chart orqali
                # RSI+hajmni olgan (haqiqiy OHLC emas, faqat yopilish narxlari) — karta
                # uchun haqiqiy shamlar kerak bo'lgani sababli, FAQAT yakuniy (kichik
                # sonli, odatda ~5 ta) nomzodlarga alohida /ohlc so'rovi qilinadi —
                # skanerlangan barcha (ko'p sonli) nomzodlarga emas, shuning uchun
                # qo'shimcha tezlik-chegarasi yuki sezilarli emas.
                cand["candles"] = coingecko_api.get_ohlc_candles(cand["cg_id"], max_candles=48)
                time.sleep(coingecko_api.request_delay_seconds())
                notes = breakout_notes(cand)
                image = build_breakout_card_image(cand, rank, notes)
                caption = build_breakout_caption(cand, rank, notes)
                if poster.post_photo_bytes(image, caption):
                    logger.info("  [%d/%d] %s (kuzatish #%d) yuborildi.", rank, len(candidates), cand["symbol"], rank)
                else:
                    logger.error("%s (kuzatish #%d) yuborishda xatolik.", cand["symbol"], rank)
                time.sleep(post_delay)
        else:
            logger.info("Hozircha kuzatish uchun mos nomzod topilmadi.")

    if enable_news:
        logger.info("So'nggi kripto yangiliklari olinmoqda...")
        try:
            news_items = fetch_latest_news(news_count, translate=translate_news)
            caption = build_news_caption(news_items)
            if caption:
                if poster.post_text(caption):
                    logger.info("Yangiliklar xabari yuborildi (%d ta).", len(news_items))
                else:
                    logger.error("Yangiliklar xabarini yuborishda xatolik.")
            else:
                logger.info("Yangilik topilmadi, xabar yuborilmadi.")
        except Exception:  # noqa: BLE001
            logger.exception("Yangiliklarni olishda xatolik.")

    logger.info("Kripto bot ishi yakunlandi. Jami %d ta coin xabari yuborildi.", sent)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_once())
