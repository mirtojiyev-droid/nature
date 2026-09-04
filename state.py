"""
Kunlik mavzu (joy) va shu kun davomida qaysi "qirralar" (facets.py) allaqachon
ishlatilganini kuzatib boradi. Kun almashsa, yangi mavzu tanlanadi va qirralar ro'yxati
boshidan boshlanadi.
"""
import json
import logging
import random
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent / "daily_state.json"
HISTORY_FILE = Path(__file__).parent / "theme_history.json"
HISTORY_AVOID_DAYS = 30  # so'nggi shuncha kunlik mavzu imkon qadar takrorlanmaydi


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("%s o'qib bo'lmadi, standart holatdan boshlanadi: %s", path.name, exc)
        return default


def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_history() -> list[str]:
    return _load_json(HISTORY_FILE, [])


def _remember_theme_in_history(theme: str) -> None:
    history = _load_history()
    history.append(theme)
    history = history[-HISTORY_AVOID_DAYS:]
    _save_json(HISTORY_FILE, history)


def get_today_theme(pool: list[str]) -> str:
    """Bugungi kunning mavzusini (joyini) qaytaradi. Bugun uchun hali tanlanmagan bo'lsa,
    havzadan (imkon qadar so'nggi kunlarda ishlatilmagan) birini tasodifiy tanlaydi va
    kun davomida shu bilan qoladi."""
    today = date.today().isoformat()
    state = _load_json(STATE_FILE, {})

    if state.get("date") == today and state.get("theme"):
        return state["theme"]

    if not pool:
        raise ValueError("Joylar havzasi bo'sh — na Wikipedia'dan, na seed ro'yxatdan joy topilmadi.")

    history = set(_load_history())
    candidates = [p for p in pool if p not in history] or pool
    theme = random.choice(candidates)

    _save_json(STATE_FILE, {"date": today, "theme": theme, "used_facets": []})
    _remember_theme_in_history(theme)
    logger.info("Bugungi yangi mavzu tanlandi: %s", theme)
    return theme


def pick_next_facet(facets: list[dict]) -> tuple[int, dict]:
    """Bugungi mavzu uchun hali ishlatilmagan qirrani tanlaydi. Hammasi ishlatilgan bo'lsa,
    ro'yxat qaytadan boshidan aylanadi — bu muammo emas, chunki Pexels har safar bir xil
    so'rov uchun ham tasodifiy boshqa rasm/video qaytarishi mumkin."""
    today = date.today().isoformat()
    state = _load_json(STATE_FILE, {"date": today, "theme": None, "used_facets": []})

    used = set(state.get("used_facets", [])) if state.get("date") == today else set()
    all_indices = list(range(len(facets)))
    unused = [i for i in all_indices if i not in used]

    if not unused:
        unused = all_indices

    idx = random.choice(unused)
    return idx, facets[idx]


def mark_facet_used(idx: int) -> None:
    today = date.today().isoformat()
    state = _load_json(STATE_FILE, {"date": today, "theme": None, "used_facets": []})

    used = set(state.get("used_facets", [])) if state.get("date") == today else set()
    used.add(idx)
    state["used_facets"] = sorted(used)
    state["date"] = today
    _save_json(STATE_FILE, state)
