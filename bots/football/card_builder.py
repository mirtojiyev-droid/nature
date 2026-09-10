"""O'yin natijasi/fixture kartasini "translyatsiya tabloi" uslubida PNG rasm sifatida
chizadi — futbol_bot_mobil.html'dagi Canvas mantiqining Pillow porti.

MUHIM SODDALASHTIRISH: JS versiyasida jamoa gerbini (crest) olish uchun to'rtta CORS
proxy ketma-ket sinalardi (brauzer cheklovi tufayli). Server tomonidagi Python
skriptida bunday cheklov yo'q — gerb rasmi to'g'ridan-to'g'ri bitta so'rov bilan olinadi.
"""
import logging
from io import BytesIO

import requests
from PIL import Image, ImageDraw

from shared.fonts import get_font

logger = logging.getLogger(__name__)

CARD_W = 1080
CARD_PAD = 26
CARD_H_BASE = 480
COLOR_STATUS_FINISHED = "#00D97E"
COLOR_STATUS_UPCOMING = "#FFC94D"
COLOR_GOAL_TEXT = "#F2C94C"

_crest_cache: dict[str, bytes | None] = {}


def _fetch_crest_bytes(url: str | None) -> bytes | None:
    if not url:
        return None
    if url in _crest_cache:
        return _crest_cache[url]
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.content
    except requests.RequestException as exc:
        logger.info("Jamoa gerbini olib bo'lmadi (%s): %s", url, exc)
        data = None
    _crest_cache[url] = data
    return data


def _initials(name: str) -> str:
    words = [w for w in str(name).split() if w]
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    return str(name)[:2].upper()


def _last_name(full_name: str) -> str:
    words = [w for w in str(full_name).strip().split() if w]
    return words[-1] if words else full_name


def _truncate_to_width(draw: ImageDraw.ImageDraw, text: str, max_width: int, font) -> str:
    if draw.textlength(text, font=font) <= max_width:
        return text
    t = text
    while len(t) > 1 and draw.textlength(t + "…", font=font) > max_width:
        t = t[:-1]
    return t + "…"


def _circular_crop(img: Image.Image, size: int) -> Image.Image:
    img = img.convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    img.putalpha(mask)
    return img


def _draw_crest(base_img: Image.Image, draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int,
                 badge_url: str | None, fallback_text: str, accent_color: str) -> None:
    draw.ellipse([cx - radius - 6, cy - radius - 6, cx + radius + 6, cy + radius + 6], fill="#FFFFFF")

    raw = _fetch_crest_bytes(badge_url)
    if raw:
        try:
            crest = Image.open(BytesIO(raw))
            crest = _circular_crop(crest, radius * 2)
            base_img.paste(crest, (cx - radius, cy - radius), crest)
            return
        except Exception as exc:  # noqa: BLE001 - buzuq rasm bo'lsa fallback'ga o'tamiz
            logger.info("Gerb rasmini ochib bo'lmadi: %s", exc)

    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=accent_color)
    draw.text((cx, cy), fallback_text, font=get_font(round(radius * 0.75), "bold"), fill="#FFFFFF", anchor="mm")


def _draw_match_card(
    league_meta: dict, date_str: str, home_name: str, away_name: str,
    home_badge_url: str | None, away_badge_url: str | None,
    center_type: str, home_score=None, away_score=None, time_str: str | None = None,
    status_text: str = "", status_color: str = "#FFFFFF", goals: list[dict] | None = None,
) -> bytes:
    all_goals = goals or []
    home_goals_all = [g for g in all_goals if g["is_home"]]
    away_goals_all = [g for g in all_goals if not g["is_home"]]
    home_goals_shown = home_goals_all[:3]
    away_goals_shown = away_goals_all[:3]
    home_extra = len(home_goals_all) - len(home_goals_shown)
    away_extra = len(away_goals_all) - len(away_goals_shown)
    home_line_count = len(home_goals_shown) + (1 if home_extra > 0 else 0)
    away_line_count = len(away_goals_shown) + (1 if away_extra > 0 else 0)
    max_goal_lines = max(home_line_count, away_line_count)
    card_h = CARD_H_BASE + (max_goal_lines * 24 + 16 if max_goal_lines > 0 else 0)

    total_h = card_h + 2 * CARD_PAD
    img = Image.new("RGB", (CARD_W, total_h), "#0F1220")
    draw = ImageDraw.Draw(img)

    card_x, card_y, card_w = CARD_PAD, CARD_PAD, CARD_W - 2 * CARD_PAD
    draw.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=26, fill=league_meta["dark"])

    # Liga pill (yuqori chap)
    pill_font = get_font(20, "bold")
    pill_pad_x, pill_h = 18, 40
    pill_text_w = draw.textlength(league_meta["short"], font=pill_font)
    pill_w = pill_text_w + pill_pad_x * 2
    pill_x, pill_y = card_x + 28, card_y + 28
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], radius=pill_h / 2, fill=league_meta["accent"])
    draw.text((pill_x + pill_pad_x, pill_y + pill_h / 2), league_meta["short"], font=pill_font, fill="#0B0D16", anchor="lm")

    # Sana (yuqori o'ng)
    date_font = get_font(20)
    draw.text((card_x + card_w - 28, pill_y + pill_h / 2), date_str, font=date_font, fill="#9AA0B4", anchor="rm")

    # Crestlar
    mid_y = card_y + 220
    crest_r = 70
    home_cx = card_x + 190
    away_cx = card_x + card_w - 190
    _draw_crest(img, draw, home_cx, mid_y, crest_r, home_badge_url, _initials(home_name), league_meta["accent"])
    _draw_crest(img, draw, away_cx, mid_y, crest_r, away_badge_url, _initials(away_name), league_meta["accent"])

    # Jamoa nomlari
    name_font = get_font(26, "bold")
    name_y = mid_y + crest_r + 44
    draw.text((home_cx, name_y), _truncate_to_width(draw, home_name, 260, name_font), font=name_font, fill="#E8E9F3", anchor="ms")
    draw.text((away_cx, name_y), _truncate_to_width(draw, away_name, 260, name_font), font=name_font, fill="#E8E9F3", anchor="ms")

    # Gol urganlar (ism + daqiqa) — har bir jamoa ostida
    # (Eslatma: emoji belgilar odatiy DejaVu Sans shriftida ko'rinmaydi — shuning uchun
    # bu yerda faqat matn ishlatiladi, emoji faqat Telegram caption matnida ko'rinadi.)
    if max_goal_lines > 0:
        goal_font = get_font(16)
        goals_start_y = name_y + 26
        for i, g in enumerate(home_goals_shown):
            text = f"{g['minute']}' {_truncate_to_width(draw, _last_name(g['player']), 220, goal_font)}"
            draw.text((home_cx, goals_start_y + i * 24), text, font=goal_font, fill=COLOR_GOAL_TEXT, anchor="ms")
        if home_extra > 0:
            draw.text((home_cx, goals_start_y + len(home_goals_shown) * 24), f"+{home_extra} ko'proq", font=goal_font, fill=COLOR_GOAL_TEXT, anchor="ms")
        for i, g in enumerate(away_goals_shown):
            text = f"{g['minute']}' {_truncate_to_width(draw, _last_name(g['player']), 220, goal_font)}"
            draw.text((away_cx, goals_start_y + i * 24), text, font=goal_font, fill=COLOR_GOAL_TEXT, anchor="ms")
        if away_extra > 0:
            draw.text((away_cx, goals_start_y + len(away_goals_shown) * 24), f"+{away_extra} ko'proq", font=goal_font, fill=COLOR_GOAL_TEXT, anchor="ms")

    # Markaziy blok: hisob yoki VS
    box_w, box_h = 220, 108
    box_x, box_y = card_x + card_w / 2 - box_w / 2, mid_y - box_h / 2
    draw.rounded_rectangle([box_x, box_y, box_x + box_w, box_y + box_h], radius=20, fill="#FFFFFF")

    if center_type == "score":
        draw.text((card_x + card_w / 2, mid_y), f"{home_score} - {away_score}", font=get_font(62, "bold"), fill="#0B0D16", anchor="mm")
    else:
        draw.text((card_x + card_w / 2, mid_y - 16), "VS", font=get_font(40, "bold"), fill=league_meta["accent"], anchor="mm")
        draw.text((card_x + card_w / 2, mid_y + 26), time_str or "", font=get_font(28, "bold"), fill="#0B0D16", anchor="mm")

    # Status pill (pastda)
    status_font = get_font(22, "bold")
    status_y = card_y + card_h - 46
    status_text_w = draw.textlength(status_text, font=status_font)
    status_pill_w = status_text_w + 40
    status_pill_x = card_x + card_w / 2 - status_pill_w / 2
    draw.rounded_rectangle([status_pill_x, status_y - 22, status_pill_x + status_pill_w, status_y + 22], radius=22, fill=status_color)
    draw.text((card_x + card_w / 2, status_y), status_text, font=status_font, fill="#0B0D16", anchor="mm")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_result_card_image(match: dict) -> bytes:
    # Faqat gollar soni hisobga ANIQ mos kelsa ko'rsatamiz — aks holda noto'liq
    # ro'yxat chalg'ituvchi bo'lishi mumkin (manba ma'lumoti kamchil).
    goals = match["goals"] if match.get("goalsComplete") else []
    return _draw_match_card(
        league_meta=match["leagueMeta"], date_str=match["dateEvent"],
        home_name=match["strHomeTeam"], away_name=match["strAwayTeam"],
        home_badge_url=match.get("strHomeTeamBadge"), away_badge_url=match.get("strAwayTeamBadge"),
        center_type="score", home_score=match["intHomeScore"], away_score=match["intAwayScore"],
        status_text="YAKUNLANDI", status_color=COLOR_STATUS_FINISHED, goals=goals,
    )


def build_fixture_card_image(match: dict) -> bytes:
    time_str = f"{match['strTime'][:5]} UTC" if match.get("strTime") else "Vaqt aniq emas"
    return _draw_match_card(
        league_meta=match["leagueMeta"], date_str=match["dateEvent"],
        home_name=match["strHomeTeam"], away_name=match["strAwayTeam"],
        home_badge_url=match.get("strHomeTeamBadge"), away_badge_url=match.get("strAwayTeamBadge"),
        center_type="vs", time_str=time_str,
        status_text="YAQINLASHMOQDA", status_color=COLOR_STATUS_UPCOMING,
    )
