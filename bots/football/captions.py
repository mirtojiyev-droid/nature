import html
import os

from shared.hashtags import format_hashtags, slugify_hashtag
from shared.timezone_utils import utc_to_local

# MUHIM (foydalanuvchi tomonidan aniqlangan muammo): TheSportsDB o'yin vaqtini UTC
# bo'yicha beradi — avval bu UTC qiymat "(UTC)" deb yorliqlanib, o'zgartirilmasdan
# ko'rsatilardi (masalan O'zbekiston vaqti bilan 18:00'da bo'ladigan o'yin "13:00
# (UTC)" deb chiqardi — texnik jihatdan to'g'ri, lekin chalkash). Endi mahalliy
# vaqtga o'girib ko'rsatiladi (standart: UTC+5, O'zbekiston — FOOTBALL_TZ_OFFSET_HOURS
# orqali .env'da o'zgartirish mumkin).
FOOTBALL_TZ_OFFSET_HOURS = int(os.getenv("FOOTBALL_TZ_OFFSET_HOURS", "5"))

# Kanalning umumiy (eng mashhur/mavzuga mos) hashteglari — har bir post turida ham bor.
CHANNEL_HASHTAGS = ["futbol", "football"]


def local_date_time(match: dict) -> tuple[str, str]:
    """`match`dagi UTC sana+vaqtni mahalliy sana+vaqtga o'girib qaytaradi (ikkalasini
    BIRGA — chunki vaqt zonasi farqi soat chegarasidan oshib/kamayib ketsa, SANA ham
    o'zgarishi mumkin, masalan UTC 23:30 -> mahalliy (UTC+5) ertangi kun 04:30).
    Parslab bo'lmasa, asl (UTC) qiymatlarni "(UTC)" bilan belgilab qaytaradi."""
    if not match.get("strTime") or not match.get("dateEvent"):
        return match.get("dateEvent", ""), "vaqt aniq emas"
    try:
        return utc_to_local(match["dateEvent"], match["strTime"], FOOTBALL_TZ_OFFSET_HOURS)
    except (ValueError, KeyError):
        return match["dateEvent"], f"{match['strTime'][:5]} (UTC)"


def _match_hashtags(match: dict) -> list[str]:
    league_short = match.get("leagueMeta", {}).get("short", "")
    return [
        *CHANNEL_HASHTAGS,
        slugify_hashtag(match["strHomeTeam"]),
        slugify_hashtag(match["strAwayTeam"]),
        slugify_hashtag(league_short) if league_short else slugify_hashtag(match.get("leagueName", "")),
    ]


def build_result_caption(match: dict) -> str:
    lines = [
        f"⚽ <b>{html.escape(match['strHomeTeam'])} {match['intHomeScore']} - {match['intAwayScore']} {html.escape(match['strAwayTeam'])}</b>",
        f"{match['leagueName']}  ·  {match['dateEvent']}",
    ]
    goals = match.get("goals") or []
    if goals:
        lines.append("")
        for g in goals:
            team = match["strHomeTeam"] if g["is_home"] else match["strAwayTeam"]
            lines.append(f"⚽ {g['minute']}' {html.escape(g['player'])} ({html.escape(team)})")
        if not match.get("goalsComplete"):
            lines.append("")
            lines.append("<i>Eslatma: gol tafsilotlari to'liq bo'lmasligi mumkin (manba ma'lumoti yetarli emas).</i>")
    lines.append("")
    lines.append(format_hashtags(_match_hashtags(match)))
    return "\n".join(lines)


def build_fixture_caption(match: dict) -> str:
    local_date, local_time = local_date_time(match)
    lines = [
        f"🕒 <b>{html.escape(match['strHomeTeam'])} — {html.escape(match['strAwayTeam'])}</b>",
        f"{match['leagueName']}  ·  {local_date}  ·  {local_time}",
        "",
        format_hashtags(_match_hashtags(match)),
    ]
    return "\n".join(lines)


def build_news_caption(news_items: list[dict]) -> str | None:
    if not news_items:
        return None
    lines = ["📰 <b>So'nggi futbol yangiliklari</b>", ""]
    for item in news_items:
        lines.append(f"• <a href=\"{item['link']}\">{html.escape(item['title'])}</a>")
    lines.append("")
    lines.append(format_hashtags([*CHANNEL_HASHTAGS, "yangiliklar", "sport"]))
    return "\n".join(lines)
