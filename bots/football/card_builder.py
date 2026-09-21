"""O'yin natijasi/fixture kartasini zamonaviy "translyatsiya tabloi" uslubida PNG
rasm sifatida chizadi — gradient fon, yumshoq soyalar va porlash effektlari bilan
(shared/canvas.py umumiy vositalaridan foydalanadi).

MUHIM SODDALASHTIRISH: JS versiyasida jamoa gerbini (crest) olish uchun to'rtta CORS
proxy ketma-ket sinalardi (brauzer cheklovi tufayli). Server tomonidagi Python
skriptida bunday cheklov yo'q — gerb rasmi to'g'ridan-to'g'ri bitta so'rov bilan olinadi.
"""
import logging
from io import BytesIO

import requests
from PIL import Image, ImageDraw

from shared.canvas import diagonal_gradient, draw_soft_glow_circle, paste_soft_shadow
from shared.fonts import get_font

logger = logging.getLogger(__name__)

CARD_W = 1080
CARD_PAD = 34
CARD_H_BASE = 480
COLOR_STATUS_FINISHED = "#22E37E"
COLOR_STATUS_UPCOMING = "#FFC94D"
COLOR_GOAL_TEXT = "#F2D98C"
COLOR_CARD_TEXT = "#F3F5FA"
COLOR_SUBTEXT = "#9AA6C3"

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
    # Gerb ortida yumshoq "porlash" — e'tiborni markazga tortadi, kartaga chuqurlik beradi
    draw_soft_glow_circle(base_img, cx, cy, radius + 22, accent_color, opacity=70, blur=28)

    draw.ellipse([cx - radius - 8, cy - radius - 8, cx + radius + 8, cy + radius + 8], fill="#FFFFFF")
    draw.ellipse([cx - radius - 8, cy - radius - 8, cx + radius + 8, cy + radius + 8], outline=accent_color, width=3)

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
    card_h = CARD_H_BASE + (max_goal_lines * 26 + 16 if max_goal_lines > 0 else 0)

    total_h = card_h + 2 * CARD_PAD
    img = Image.new("RGBA", (CARD_W, total_h), "#04050A")

    card_x, card_y, card_w = CARD_PAD, CARD_PAD, CARD_W - 2 * CARD_PAD

    # Yumshoq soya, so'ng gradient fon (liganing to'q rangidan biroz yorug'roq nuqtadan
    # to'liq to'q rangga — chuqurlik va zamonaviylik hissi uchun)
    paste_soft_shadow(img, [card_x, card_y, card_x + card_w, card_y + card_h], 30, opacity=140, offset=(0, 14), blur=30)
    grad = diagonal_gradient((card_w, card_h), _lighten(league_meta["dark"], 0.35), league_meta["dark"])
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card_w, card_h], radius=30, fill=255)
    img.paste(grad, (card_x, card_y), mask)

    draw = ImageDraw.Draw(img)

    # Liga pill (yuqori chap) — endi ozgina soya bilan, ko'proq "qavariq" ko'rinadi
    pill_font = get_font(21, "bold")
    pill_pad_x, pill_h = 22, 44
    pill_text_w = draw.textlength(league_meta["short"], font=pill_font)
    pill_w = pill_text_w + pill_pad_x * 2
    pill_x, pill_y = card_x + 30, card_y + 30
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], radius=pill_h / 2, fill=league_meta["accent"])
    draw.text((pill_x + pill_w / 2, pill_y + pill_h / 2), league_meta["short"], font=pill_font, fill="#0B0D16", anchor="mm")

    # Sana (yuqori o'ng)
    date_font = get_font(21)
    draw.text((card_x + card_w - 30, pill_y + pill_h / 2), date_str, font=date_font, fill=COLOR_SUBTEXT, anchor="rm")

    # Crestlar
    mid_y = card_y + 224
    crest_r = 72
    home_cx = card_x + 196
    away_cx = card_x + card_w - 196
    _draw_crest(img, draw, home_cx, mid_y, crest_r, home_badge_url, _initials(home_name), league_meta["accent"])
    _draw_crest(img, draw, away_cx, mid_y, crest_r, away_badge_url, _initials(away_name), league_meta["accent"])

    # Jamoa nomlari
    name_font = get_font(27, "bold")
    name_y = mid_y + crest_r + 48
    draw.text((home_cx, name_y), _truncate_to_width(draw, home_name, 270, name_font), font=name_font, fill=COLOR_CARD_TEXT, anchor="ms")
    draw.text((away_cx, name_y), _truncate_to_width(draw, away_name, 270, name_font), font=name_font, fill=COLOR_CARD_TEXT, anchor="ms")

    # Gol urganlar (ism + daqiqa) — rangli nuqta + matn (emoji shrift muammosi tufayli
    # ⚽ belgisi ATAYLAB ishlatilmaydi, buning o'rniga chizilgan nuqta ishlatiladi)
    if max_goal_lines > 0:
        goal_font = get_font(17, "bold")
        goals_start_y = name_y + 30
        for i, g in enumerate(home_goals_shown):
            gy = goals_start_y + i * 26
            text = f"{g['minute']}'  {_truncate_to_width(draw, _last_name(g['player']), 200, goal_font)}"
            draw.ellipse([home_cx - 130, gy - 5, home_cx - 122, gy + 3], fill=league_meta["accent"])
            draw.text((home_cx - 112, gy - 1), text, font=goal_font, fill=COLOR_GOAL_TEXT, anchor="lm")
        if home_extra > 0:
            draw.text((home_cx, goals_start_y + len(home_goals_shown) * 26), f"+{home_extra} ko'proq", font=goal_font, fill=COLOR_GOAL_TEXT, anchor="ms")
        for i, g in enumerate(away_goals_shown):
            gy = goals_start_y + i * 26
            text = f"{g['minute']}'  {_truncate_to_width(draw, _last_name(g['player']), 200, goal_font)}"
            draw.ellipse([away_cx - 130, gy - 5, away_cx - 122, gy + 3], fill=league_meta["accent"])
            draw.text((away_cx - 112, gy - 1), text, font=goal_font, fill=COLOR_GOAL_TEXT, anchor="lm")
        if away_extra > 0:
            draw.text((away_cx, goals_start_y + len(away_goals_shown) * 26), f"+{away_extra} ko'proq", font=goal_font, fill=COLOR_GOAL_TEXT, anchor="ms")

    # Markaziy blok: hisob yoki VS — endi o'zining soyasi bilan, "suzib turgan" ko'rinishda
    box_w, box_h = 232, 116
    box_x, box_y = card_x + card_w / 2 - box_w / 2, mid_y - box_h / 2
    paste_soft_shadow(img, [box_x, box_y, box_x + box_w, box_y + box_h], 22, opacity=120, offset=(0, 6), blur=16)
    draw.rounded_rectangle([box_x, box_y, box_x + box_w, box_y + box_h], radius=22, fill="#FFFFFF")

    if center_type == "score":
        draw.text((card_x + card_w / 2, mid_y), f"{home_score} - {away_score}", font=get_font(64, "bold"), fill="#0B0D16", anchor="mm")
    else:
        draw.text((card_x + card_w / 2, mid_y - 18), "VS", font=get_font(38, "bold"), fill=league_meta["accent"], anchor="mm")
        draw.text((card_x + card_w / 2, mid_y + 26), time_str or "", font=get_font(27, "bold"), fill="#0B0D16", anchor="mm")

    # Status pill (pastda)
    status_font = get_font(23, "bold")
    status_y = card_y + card_h - 48
    status_text_w = draw.textlength(status_text, font=status_font)
    status_pill_w = status_text_w + 48
    status_pill_x = card_x + card_w / 2 - status_pill_w / 2
    draw.rounded_rectangle([status_pill_x, status_y - 24, status_pill_x + status_pill_w, status_y + 24], radius=24, fill=status_color)
    draw.text((card_x + card_w / 2, status_y), status_text, font=status_font, fill="#0B0D16", anchor="mm")

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _lighten(hex_color: str, amount: float) -> str:
    """Rangni oq tomon `amount` (0-1) nisbatida yorug'lashtiradi — gradient fonning
    "yuqori-chap" nuqtasi uchun (liganing to'q rangidan biroz yorug'roq)."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = round(r + (255 - r) * amount)
    g = round(g + (255 - g) * amount)
    b = round(b + (255 - b) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


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
