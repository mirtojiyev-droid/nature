import html

from shared.hashtags import format_hashtags, slugify_hashtag

# Kanalning umumiy (eng mashhur/mavzuga mos) hashteglari — har bir post turida ham bor.
CHANNEL_HASHTAGS = ["futbol", "football"]


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
            lines.append("<i> </i>")
    lines.append("")
    lines.append(format_hashtags(_match_hashtags(match)))
    return "\n".join(lines)


def build_fixture_caption(match: dict) -> str:
    time_str = f"{match['strTime'][:5]} (UTC)" if match.get("strTime") else "vaqt aniq emas"
    lines = [
        f"🕒 <b>{html.escape(match['strHomeTeam'])} — {html.escape(match['strAwayTeam'])}</b>",
        f"{match['leagueName']}  ·  {match['dateEvent']}  ·  {time_str}",
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
