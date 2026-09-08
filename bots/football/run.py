"""
Futbol boti — futbol_bot_mobil.html'dagi mantiqning to'liq Python porti.

Har ishga tushganda (yoqilgan ligalar bo'yicha):
  1. So'nggi N kunlik natijalarni oladi va joylaydi — LEKIN faqat ILGARI JOYLANMAGAN
     o'yinlarni (state.py orqali kuzatiladi). Bu muhim tuzatish: avval bu tekshiruv
     yo'q edi, shuning uchun bot har ishga tushganda "so'nggi N kunlik natijalar"ni
     qaytadan olib, bir xil o'yinni QAYTA-QAYTA post qilardi.
  2. Xuddi shunday, faqat ilgari joylanmagan kelgusi o'yinlarni joylaydi.
  3. (yoqilgan bo'lsa) Faqat ILGARI JOYLANMAGAN futbol yangiliklarini joylaydi.
  4. (yoqilgan bo'lsa) Har ishga tushganda BITTA qiziqarli futbol fakti (Wikipedia
     manbali, ishonchli) joylaydi — bot odatda har soatda ishga tushishi kutiladi.
  5. (yoqilgan bo'lsa) Kuniga taxminan 2 marta (FOOTBALL_SPOTLIGHT_MIN_HOURS oralig'ida)
     mashhur futbolchi haqida — hozirgi klubi va tarjimai holi (Wikipedia'dan) —
     alohida post joylaydi.
"""
import logging
import os
import time

from dotenv import load_dotenv

from shared.telegram_poster import TelegramPoster
from . import state
from .captions import build_fixture_caption, build_news_caption, build_result_caption
from .card_builder import build_fixture_card_image, build_result_card_image
from .match_filter import collect_recent_results, collect_upcoming_fixtures
from .news_fetcher import fetch_latest_news
from .sportsdb_api import LEAGUES
from .spotlight import post_player_spotlight
from .trivia import post_trivia

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
    enable_trivia = _env_bool("FOOTBALL_ENABLE_TRIVIA", True)
    enable_spotlight = _env_bool("FOOTBALL_ENABLE_SPOTLIGHT", True)
    spotlight_min_hours = _env_float("FOOTBALL_SPOTLIGHT_MIN_HOURS", 11.0)
    translate_enabled = _env_bool("FOOTBALL_TRANSLATE_TO_UZBEK", True)

    leagues = _selected_leagues()
    if not leagues:
        logger.warning("Hech qanday liga tanlanmagan (FOOTBALL_LEAGUES noto'g'ri sozlangan bo'lishi mumkin).")
        return 1
    logger.info("Tanlangan ligalar: %s", ", ".join(l["name"] for l in leagues))

    poster = TelegramPoster(bot_token, channel_id)
    sent_total = 0

    if enable_results:
        logger.info("So'nggi natijalar olinmoqda (ilgari joylanmaganlari)...")
        already_posted = state.get_posted_ids("posted_results")
        results = collect_recent_results(
            leagues, days_back, already_posted, lambda name: logger.info("  Tekshirilmoqda: %s", name),
        )
        if results:
            logger.info("%d ta YANGI natija topildi, yuborilmoqda...", len(results))
            posted_ids = []
            for i, match in enumerate(results):
                image = build_result_card_image(match)
                caption = build_result_caption(match)
                if poster.post_photo_bytes(image, caption):
                    sent_total += 1
                    posted_ids.append(match["idEvent"])
                    logger.info(
                        "  [%d/%d] %s %s-%s %s yuborildi.",
                        i + 1, len(results), match["strHomeTeam"], match["intHomeScore"],
                        match["intAwayScore"], match["strAwayTeam"],
                    )
                else:
                    logger.error("%s - %s natijasini yuborishda xatolik.", match["strHomeTeam"], match["strAwayTeam"])
                time.sleep(post_delay)
            state.mark_posted(posted_ids, "posted_results")
        else:
            logger.info("So'nggi %d kunda tanlangan ligalarda YANGI natija topilmadi.", days_back)

    if enable_fixtures:
        logger.info("Yaqin kunlardagi o'yinlar olinmoqda (ilgari joylanmaganlari)...")
        already_posted = state.get_posted_ids("posted_fixtures")
        fixtures = collect_upcoming_fixtures(
            leagues, days_forward, already_posted, lambda name: logger.info("  Tekshirilmoqda: %s", name),
        )
        if fixtures:
            logger.info("%d ta YANGI o'yin topildi, yuborilmoqda...", len(fixtures))
            posted_ids = []
            for i, match in enumerate(fixtures):
                image = build_fixture_card_image(match)
                caption = build_fixture_caption(match)
                if poster.post_photo_bytes(image, caption):
                    sent_total += 1
                    posted_ids.append(match["idEvent"])
                    logger.info("  [%d/%d] %s — %s yuborildi.", i + 1, len(fixtures), match["strHomeTeam"], match["strAwayTeam"])
                else:
                    logger.error("%s — %s o'yinini yuborishda xatolik.", match["strHomeTeam"], match["strAwayTeam"])
                time.sleep(post_delay)
            state.mark_posted(posted_ids, "posted_fixtures")
        else:
            logger.info("Kelgusi %d kunda tanlangan ligalarda YANGI o'yin topilmadi.", days_forward)

    if enable_news:
        logger.info("Futbol yangiliklari olinmoqda (ilgari joylanmaganlari)...")
        try:
            all_news = fetch_latest_news(news_count)
            already_posted = state.get_posted_ids("posted_news")
            new_news = [n for n in all_news if n["link"] not in already_posted]
            caption = build_news_caption(new_news)
            if caption:
                if poster.post_text(caption):
                    sent_total += 1
                    state.mark_posted([n["link"] for n in new_news], "posted_news")
                    logger.info("Yangiliklar xabari yuborildi (%d ta yangi).", len(new_news))
                else:
                    logger.error("Yangiliklar xabarini yuborishda xatolik.")
            else:
                logger.info("Yangi (ilgari joylanmagan) yangilik topilmadi.")
        except Exception:  # noqa: BLE001
            logger.exception("Yangiliklarni olishda xatolik.")

    if enable_trivia:
        logger.info("Qiziqarli futbol fakti tayyorlanmoqda...")
        try:
            if post_trivia(poster, translate_enabled):
                sent_total += 1
        except Exception:  # noqa: BLE001
            logger.exception("Qiziqarli fakt joylashda xatolik.")

    if enable_spotlight and state.should_post_spotlight(spotlight_min_hours):
        logger.info("Futbolchi sharhi (spotlight) tayyorlanmoqda...")
        try:
            if post_player_spotlight(poster, translate_enabled):
                sent_total += 1
        except Exception:  # noqa: BLE001
            logger.exception("Futbolchi sharhini joylashda xatolik.")

    logger.info("Futbol bot ishi yakunlandi. Jami %d ta xabar yuborildi.", sent_total)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(run_once())
