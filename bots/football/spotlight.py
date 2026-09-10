"""Kuniga taxminan 2 marta (run.py'da FOOTBALL_SPOTLIGHT_MIN_HOURS orqali sozlanadi)
mashhur futbolchi haqida post: hozir qaysi klubda o'ynayotgani va tarjimai holi
Wikipedia'dan (ishonchli, doimo yangilanib turadigan manba) olinadi.

MUHIM (halollik): "texnik imkoniyati" haqida haqiqiy skaut-tahlili avtomatik va
ishonchli tarzda generatsiya qilib bo'lmaydi — shuning uchun bu bot HECH QANDAY
o'zi to'qib chiqargan texnik tavsif yozmaydi. Buning o'rniga Wikipedia maqolasining
boshlang'ich (lead) qismini (odatda futbolchining pozitsiyasi, o'ynash uslubi va
albatta HOZIRGI klubi tilga olinadi) o'zbek tiliga tarjima qilib beradi — bu ancha
ishonchli, chunki manba sifatida ko'rsatiladi va Wikipedia'ning o'zi doimiy
tahrirlanib, yangilanib turadi (transfer bo'lganda odatda tez orada aks etadi)."""
import html
import logging
import random

from shared.hashtags import format_hashtags, slugify_hashtag
from shared.translator import translate_to_uzbek
from shared.wikipedia import InfoFetcher

from . import state
from .players import PLAYERS
from .sportsdb_api import search_player_photo

logger = logging.getLogger(__name__)


def _pick_next_player() -> str:
    used = state.get_used_spotlight_names()
    pool = [p for p in PLAYERS if p not in used] or list(PLAYERS)
    return random.choice(pool)


def _build_caption(name: str, bio: str | None) -> str:
    lines = [f"🌟 <b>{html.escape(name)}</b>"]
    if bio:
        lines.append("")
        lines.append(html.escape(bio))
    else:
        lines.append("")
        lines.append("<i>Bu futbolchi haqida qo'shimcha ma'lumot hozircha topilmadi.</i>")
    lines.append("")
    lines.append(format_hashtags(["futbol", "football", slugify_hashtag(name), "yulduz"]))
    return "\n".join(lines)


def post_player_spotlight(poster, translate_enabled: bool = True) -> bool:
    name = _pick_next_player()
    logger.info("Futbolchi sharhi uchun tanlandi: %s", name)

    bio = None
    try:
        summary = InfoFetcher().fetch_summary(name)
        if summary:
            sentences = summary.split(". ")
            bio = ". ".join(sentences[:4]).strip()
            if not bio.endswith("."):
                bio += "."
            if translate_enabled:
                bio = translate_to_uzbek(bio)
    except Exception:  # noqa: BLE001 - bio topilmasa ham (fallback matn bilan) post qilishda davom etamiz
        logger.exception("'%s' uchun Wikipedia ma'lumotini olishda xatolik.", name)

    photo_url = search_player_photo(name)
    caption = _build_caption(name, bio)

    ok = poster.post_photo(photo_url, caption) if photo_url else poster.post_text(caption)
    if ok:
        state.mark_spotlight_posted(name)
        logger.info("Futbolchi sharhi joylandi: %s", name)
    else:
        logger.error("Futbolchi sharhini joylashda xatolik: %s", name)
    return ok
