"""TheSportsDB (bepul, "123" umumiy test kaliti bilan) orqali o'yin natijalari,
kelgusi o'yinlar va gol jadvalini oladi — futbol_bot_mobil.html'dagi porti."""
import logging

import requests

logger = logging.getLogger(__name__)

SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/123"

LEAGUES = [
    {"id": "4328", "name": "Premer-liga", "short": "APL", "accent": "#B026FF", "dark": "#1B0E2E"},
    {"id": "4335", "name": "La Liga", "short": "LA LIGA", "accent": "#FF7A00", "dark": "#2E1B05"},
    {"id": "4332", "name": "Seriya A", "short": "SERIE A", "accent": "#00A3FF", "dark": "#04263A"},
    {"id": "4331", "name": "Bundesliga", "short": "BUNDESLIGA", "accent": "#FF3B3B", "dark": "#320305"},
    {"id": "4334", "name": "Ligue 1", "short": "LIGUE 1", "accent": "#FFD400", "dark": "#241F02"},
    {"id": "4480", "name": "Chempionlar Ligasi", "short": "UCL", "accent": "#5B7CFF", "dark": "#0A1330"},
    {"id": "4794", "name": "O'zbekiston Superligasi", "short": "UZ SUPERLIGA", "accent": "#00D1B2", "dark": "#04262B"},
]

# Jonli/tugamagan o'yinlarni "yakunlandi" deb ko'rsatib yubormaslik uchun tekshiruv.
_NOT_FINISHED_TOKENS = {
    "NS", "1H", "2H", "HT", "ET", "P", "BT", "LIVE",
    "Q1", "Q2", "Q3", "Q4", "OT", "IN1", "IN2", "IN3", "IN4", "IN5",
}
_NOT_FINISHED_SUBSTRINGS = ("NOT STARTED", "POSTPONED", "CANCEL", "SUSPEND", "INTERRUPT", "ABANDON")


def is_match_finished(ev: dict) -> bool:
    status = str(ev.get("strStatus") or "").strip()
    if not status:
        return True  # status bo'sh - odatda eski, yakunlangan yozuvlar
    s = status.upper()
    if s in _NOT_FINISHED_TOKENS:
        return False
    if any(sub in s for sub in _NOT_FINISHED_SUBSTRINGS):
        return False
    return True  # "FT", "AET", "PEN", "Match Finished" va h.k. hammasi shu yerga tushadi


def get_past_events(league_id: str) -> list[dict]:
    resp = requests.get(f"{SPORTSDB_BASE}/eventspastleague.php", params={"id": league_id}, timeout=20)
    resp.raise_for_status()
    return resp.json().get("events") or []


def get_next_events(league_id: str) -> list[dict]:
    resp = requests.get(f"{SPORTSDB_BASE}/eventsnextleague.php", params={"id": league_id}, timeout=20)
    resp.raise_for_status()
    return resp.json().get("events") or []


def get_goal_timeline(event_id: str | None) -> list[dict]:
    if not event_id:
        return []
    try:
        resp = requests.get(f"{SPORTSDB_BASE}/lookuptimeline.php", params={"id": event_id}, timeout=20)
        if not resp.ok:
            return []
        timeline = resp.json().get("timeline") or []
        goals = []
        for t in timeline:
            # Faqat "Goal" turidagi va o'yinchi ismi bor yozuvlarni olamiz - ismsiz/bo'sh
            # yozuvlar chalkash "?" ko'rinishida chiqmasligi uchun.
            if t.get("strTimeline") and "goal" in t["strTimeline"].lower() and t.get("strPlayer"):
                try:
                    minute_sort = int(t.get("intTime") or 0)
                except (TypeError, ValueError):
                    minute_sort = 0
                goals.append({
                    "minute": t.get("intTime") or "?",
                    "minute_sort": minute_sort,
                    "player": t["strPlayer"],
                    "is_home": t.get("strHome") == "Yes",
                })
        goals.sort(key=lambda g: g["minute_sort"])
        return goals
    except requests.RequestException:
        return []


def search_player_photo(name: str) -> str | None:
    """Futbolchi sharhi (spotlight) posti uchun rasm URL'ini qidiradi. TheSportsDB'ning
    futbolchi ma'lumotlari bazasi (klub, pozitsiya va h.k.) jamoat tomonidan
    to'ldiriladi va eskirgan bo'lishi mumkin — shuning uchun bu funksiyadan FAQAT
    rasm uchun foydalaniladi, matn/bio uchun emas (bio har doim Wikipedia'dan olinadi,
    u ancha tezroq yangilanadi)."""
    try:
        resp = requests.get(f"{SPORTSDB_BASE}/searchplayers.php", params={"p": name}, timeout=15)
        if not resp.ok:
            return None
        players = resp.json().get("player") or []
        if not players:
            return None
        p = players[0]
        return p.get("strCutout") or p.get("strRender") or p.get("strThumb")
    except requests.RequestException:
        return None
