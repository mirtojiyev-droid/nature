"""Har soatda futbolga oid qiziqarli, ishonchli (Wikipedia manbali) fakt joylaydi.

ISHONCHLILIK HAQIDA: mavzular oldindan qo'lda tanlangan (trivia_topics.py — sifat va
relevantlikni kafolatlash uchun), lekin har birining MATNI har safar Wikipedia'dan
JONLI olinadi (statik/qotib qolgan matn emas) — bu ensiklopedik, manbali va doimiy
tahrirlanib turadigan kontent, shuning uchun "ishonchlilik darajasi yuqori" talabiga
javob beradi. Claude yoki boshqa AI hech qanday fakt TO'QIB CHIQARMAYDI — faqat
Wikipedia'ning mavjud matnini tarjima qilib beradi."""
import html
import logging
import random

from shared.hashtags import format_hashtags
from shared.translator import translate_to_uzbek
from shared.wikipedia import InfoFetcher

from . import state
from .trivia_topics import TRIVIA_TOPICS

logger = logging.getLogger(__name__)


def _pick_next_topic() -> str:
    used = state.get_used_trivia_topics()
    pool = [t for t in TRIVIA_TOPICS if t not in used] or list(TRIVIA_TOPICS)
    return random.choice(pool)


def _build_caption(summary: str) -> str:
    lines = [
        "⚽ <b>Bilasizmi?</b>",
        "",
        html.escape(summary),
        "",
        format_hashtags(["futbol", "football", "qiziqarli", "bilasizmi"]),
    ]
    return "\n".join(lines)


def post_trivia(poster, translate_enabled: bool = True) -> bool:
    topic = _pick_next_topic()
    try:
        summary = InfoFetcher().fetch_summary(topic)
    except Exception:  # noqa: BLE001
        logger.exception("'%s' uchun Wikipedia ma'lumotini olishda xatolik.", topic)
        return False

    if not summary:
        logger.info("'%s' uchun Wikipedia'dan ma'lumot topilmadi, bu safar o'tkazib yuborildi.", topic)
        return False

    sentences = summary.split(". ")
    short = ". ".join(sentences[:3]).strip()
    if not short.endswith("."):
        short += "."
    if translate_enabled:
        short = translate_to_uzbek(short)

    caption = _build_caption(short)
    ok = poster.post_text(caption)
    if ok:
        state.mark_trivia_posted(topic)
        logger.info("Qiziqarli fakt joylandi: %s", topic)
    else:
        logger.error("Qiziqarli faktni joylashda xatolik: %s", topic)
    return ok
