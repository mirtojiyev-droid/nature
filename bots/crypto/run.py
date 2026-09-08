"""
Kripto bozor boti — kripto_bot_mobil.html'dagi mantiqning to'liq Python porti.

Har ishga tushganda:
  1. Binance'dan barcha USDT juftliklarini oladi, likvidlik bo'yicha filtrlaydi.
  2. Eng ko'p o'sgan/tushgan TOP_N coinni tanlaydi, RSI hisoblaydi.
  3. (yoqilgan bo'lsa) Fyuchers ma'lumotlarini (funding, OI, long/short) qo'shadi.
  4. Har bir coin uchun alohida karta (PNG) chizib, kanalga joylaydi.
  5. (yoqilgan bo'lsa) "Kuzatish ro'yxati" — hajm portlashi/OI to'planishi bo'yicha
     erta signal beruvchi coinlarni skanerlab, alohida joylaydi.
  6. (yoqilgan bo'lsa) So'nggi kripto yangiliklarini bitta matnli xabar sifatida joylaydi.
"""
import logging
import os
import time

from dotenv import load_dotenv

from shared.telegram_poster import TelegramPoster
from . import binance_api
from .analysis import enrich_with_futures, enrich_with_rsi, get_top_movers
from .breakout_scanner import breakout_notes, scan_breakout_candidates
from .captions import build_breakout_caption, build_caption_single
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
    breakout_scan_size = _env_int("CRYPTO_BREAKOUT_SCAN_SIZE", 60)
    breakout_top_n = _env_int("CRYPTO_BREAKOUT_TOP_N", 5)
    volume_multiplier = _env_float("CRYPTO_VOLUME_MULTIPLIER", 3.0)
    oi_threshold = _env_float("CRYPTO_OI_THRESHOLD", 15.0)
    price_quiet = _env_float("CRYPTO_PRICE_QUIET", 5.0)
    enable_futures = _env_bool("CRYPTO_ENABLE_FUTURES", True)
    enable_breakout = _env_bool("CRYPTO_ENABLE_BREAKOUT", True)
    enable_news = _env_bool("CRYPTO_ENABLE_NEWS", True)

    poster = TelegramPoster(bot_token, channel_id)

    logger.info("Binance'dan barcha juftliklar olinmoqda...")
    tickers = binance_api.get_all_24hr_tickers()
    usdt_pairs = binance_api.filter_usdt_pairs(tickers, min_volume)
    logger.info("Tahlil uchun %d ta likvid USDT juftlik topildi.", len(usdt_pairs))

    gainers, losers = get_top_movers(usdt_pairs, top_n)
    shortlist = [c["symbol"] for c in gainers + losers]

    logger.info("RSI hisoblanmoqda (%d ta coin)...", len(shortlist))
    klines_map = binance_api.get_klines_batch(shortlist, "1h", 100, delay=0.15)

    top_gainers = enrich_with_rsi(gainers, klines_map)
    top_losers = enrich_with_rsi(losers, klines_map)

    if enable_futures:
        logger.info("Fyuchers ma'lumotlari olinmoqda (Funding, OI, Long/Short)...")
        try:
            funding_map = binance_api.get_all_funding_rates()
        except Exception:  # noqa: BLE001
            logger.warning("Funding rate olinmadi, bo'sh xarita bilan davom etiladi.")
            funding_map = {}
        futures_map = binance_api.get_futures_metrics_batch(shortlist, funding_map, delay=0.2)
        top_gainers = enrich_with_futures(top_gainers, futures_map)
        top_losers = enrich_with_futures(top_losers, futures_map)
    else:
        top_gainers = enrich_with_futures(top_gainers, {})
        top_losers = enrich_with_futures(top_losers, {})

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
        else:
            logger.error("%s (tushuvchi #%d) yuborishda xatolik.", coin["symbol"], rank)
        time.sleep(post_delay)

    if enable_breakout:
        logger.info("Kuzatish ro'yxati uchun %d ta qo'shimcha coin skanerlanmoqda...", breakout_scan_size)
        remaining = [p for p in usdt_pairs if p["symbol"] not in shortlist]
        remaining.sort(key=lambda p: p["quote_volume"], reverse=True)
        remaining = remaining[:breakout_scan_size]
        try:
            candidates = scan_breakout_candidates(
                remaining,
                volume_multiplier=volume_multiplier,
                oi_accum_threshold=oi_threshold,
                price_quiet_threshold=price_quiet,
                top_n=breakout_top_n,
                delay=0.15,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Kuzatish ro'yxatini skanerlashda xatolik.")
            candidates = []

        if candidates:
            logger.info("%d ta nomzod topildi, yuborilmoqda...", len(candidates))
            for i, cand in enumerate(candidates):
                rank = i + 1
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
            news_items = fetch_latest_news(news_count)
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
