"""
Futbol boti — futbol_bot_mobil.html'dagi mantiqning to'liq Python porti.

Har ishga tushganda (yoqilgan ligalar bo'yicha):
  1. So'nggi N kunlik natijalarni oladi, har biriga gol jadvali (kim, necha daqiqada)
     bilan birga karta (PNG) chizib, kanalga joylaydi.
  2. Kelgusi N kunlik o'yinlarni oladi va joylaydi.
  3. (yoqilgan bo'lsa) So'nggi futbol yangiliklarini bitta matnli xabar sifatida joylaydi.
"""
import logging
import os
import time

from dotenv import load_dotenv

from shared.telegram_poster import TelegramPoster
from .captions import build_fixture_caption, build_news_caption, build_result_caption
from .card_builder import build_fixture_card_image, build_result_card_image
from .match_filter import collect_recent_results, collect_upcoming_fixtures
from .news_fetcher import fetch_latest_news
from .sportsdb_api import LEAGUES

logger = logging.getLogger(__name__)

# .env'da FOOTBALL_LEAGUES="4328,4335,4794" kabi vergul bilan ID ro'yxati berilishi
# mumkin — bo'sh bo'lsa (standart), barcha LEAGUES ishlatiladi.


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


def _selected_leagues() -> list[dict]:
    raw = os.getenv("FOOTBALL_LEAGUES", "").strip()
    if not raw:
        return LEAGUES
    ids = {x.strip() for x in raw.split(",") if x.strip()}
    return [l for l in LEAGUES if l["id"] in ids]


def run_once() -> int:
    load_dotenv()

    bot_token = os.getenv("FOOTBALL_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("FOOTBALL_TELEGRAM_CHANNEL_ID")
    if not bot_token or not channel_id:
        logger.error("FOOTBALL_TELEGRAM_BOT_TOKEN (yoki TELEGRAM_BOT_TOKEN) va FOOTBALL_TELEGRAM_CHANNEL_ID kerak.")
        return 1

    days_back = _env_int("FOOTBALL_DAYS_BACK", 2)
    days_forward = _env_int("FOOTBALL_DAYS_FORWARD", 2)
    post_delay = _env_float("FOOTBALL_POST_DELAY_SECONDS", 2.5)
    news_count = _env_int("FOOTBALL_NEWS_COUNT", 5)
    enable_results = _env_bool("FOOTBALL_ENABLE_RESULTS", True)
    enable_fixtures = _env_bool("FOOTBALL_ENABLE_FIXTURES", True)
    enable_news = _env_bool("FOOTBALL_ENABLE_NEWS", True)

    leagues = _selected_leagues()
    if not leagues:
        logger.warning("Hech qanday liga tanlanmagan (FOOTBALL_LEAGUES noto'g'ri sozlangan bo'lishi mumkin).")
        return 1
    logger.info("Tanlangan ligalar: %s", ", ".join(l["name"] for l in leagues))

    poster = TelegramPoster(bot_token, channel_id)
    sent_total = 0

    if enable_results:
        logger.info("So'nggi natijalar olinmoqda...")
        results = collect_recent_results(leagues, days_back, lambda name: logger.info("  Tekshirilmoqda: %s", name))
        if results:
            logger.info("%d ta natija topildi, yuborilmoqda...", len(results))
            for i, match in enumerate(results):
                image = build_result_card_image(match)
                caption = build_result_caption(match)
                if poster.post_photo_bytes(image, caption):
                    sent_total += 1
                    logger.info(
                        "  [%d/%d] %s %s-%s %s yuborildi.",
                        i + 1, len(results), match["strHomeTeam"], match["intHomeScore"],
                        match["intAwayScore"], match["strAwayTeam"],
                    )
                else:
                    logger.error("%s - %s natijasini yuborishda xatolik.", match["strHomeTeam"], match["strAwayTeam"])
                time.sleep(post_delay)
        else:
            logger.info("So'nggi %d kunda tanlangan ligalarda natija topilmadi.", days_back)

    if enable_fixtures:
        logger.info("Yaqin kunlardagi o'yinlar olinmoqda...")
        fixtures = collect_upcoming_fixtures(leagues, days_forward, lambda name: logger.info("  Tekshirilmoqda: %s", name))
        if fixtures:
            logger.info("%d ta o'yin topildi, yuborilmoqda...", len(fixtures))
            for i, match in enumerate(fixtures):
                image = build_fixture_card_image(match)
                caption = build_fixture_caption(match)
                if poster.post_photo_bytes(image, caption):
                    sent_total += 1
                    logger.info("  [%d/%d] %s — %s yuborildi.", i + 1, len(fixtures), match["strHomeTeam"], match["strAwayTeam"])
                else:
                    logger.error("%s — %s o'yinini yuborishda xatolik.", match["strHomeTeam"], match["strAwayTeam"])
                time.sleep(post_delay)
        else:
            logger.info("Kelgusi %d kunda tanlangan ligalarda o'yin topilmadi.", days_forward)

    if enable_news:
        logger.info("Futbol yangiliklari olinmoqda...")
        try:
            news_items = fetch_latest_news(news_count)
            caption = build_news_caption(news_items)
            if caption:
                if poster.post_text(caption):
                    sent_total += 1
                    logger.info("Yangiliklar xabari yuborildi (%d ta).", len(news_items))
                else:
                    logger.error("Yangiliklar xabarini yuborishda xatolik.")
            else:
                logger.info("Yangilik topilmadi.")
        except Exception:  # noqa: BLE001
            logger.exception("Yangiliklarni olishda xatolik.")

    logger.info("Futbol bot ishi yakunlandi. Jami %d ta xabar yuborildi.", sent_total)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_once())
