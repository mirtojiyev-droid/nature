"""
Joriy "oyna" (4 soatlik davr) mavzusini (joyini) va shu oyna davomida qaysi
"qirralar" (facets.py) allaqachon ishlatilganini kuzatib boradi. Oyna almashsa
(har 4 soatda), yangi mavzu tanlanadi va qirralar ro'yxati boshidan boshlanadi.

NEGA 4 SOAT (kun emas): bot har 30 daqiqada ishga tushadi — 4 soatlik oynada shuncha
vaqt ichida 8 marta post qilinadi (12 ta qirradan 8 tasi ishlatiladi, hech biri
takrorlanmaydi), so'ng mavzu yangilanadi. Shu tarzda kanal kuniga bir emas, olti xil
joyni ko'rsatadi, lekin har bir joy uchun baribir bir nechta turli qirra (video/rasm)
bilan "chuqurroq" tanishtiradi — bitta postdan keyin darhol boshqa joyga sakrab
ketavermaydi.
"""
import json
import logging
import random
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent / "window_state.json"
HISTORY_FILE = Path(__file__).parent / "theme_history.json"
WINDOW_HOURS = 4
# Kunlik 6 ta oyna (24/4) bor; so'nggi ~7 kunlik mavzular imkon qadar takrorlanmasin.
HISTORY_AVOID_WINDOWS = 7 * (24 // WINDOW_HOURS)


def _current_window_id() -> str:
    """Joriy 4 soatlik oynaning identifikatorini qaytaradi, masalan "2026-09-08-2"
    (soat 08:00-12:00 oralig'i uchun). Lokal vaqt bo'yicha hisoblanadi."""
    now = datetime.now()
    return f"{now.date().isoformat()}-{now.hour // WINDOW_HOURS}"


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
    history = history[-HISTORY_AVOID_WINDOWS:]
    _save_json(HISTORY_FILE, history)


def get_current_theme(pool: list[str]) -> str:
    """Joriy 4 soatlik oynaning mavzusini (joyini) qaytaradi. Shu oyna uchun hali
    tanlanmagan bo'lsa, havzadan (imkon qadar so'nggi kunlarda ishlatilmagan) birini
    tasodifiy tanlaydi va oyna tugaguncha shu bilan qoladi."""
    window = _current_window_id()
    state = _load_json(STATE_FILE, {})

    if state.get("window") == window and state.get("theme"):
        return state["theme"]

    if not pool:
        raise ValueError("Joylar havzasi bo'sh — na Wikipedia'dan, na seed ro'yxatdan joy topilmadi.")

    history = set(_load_history())
    candidates = [p for p in pool if p not in history] or pool
    theme = random.choice(candidates)

    _save_json(STATE_FILE, {"window": window, "theme": theme, "used_facets": []})
    _remember_theme_in_history(theme)
    logger.info("Yangi oyna (%s) uchun mavzu tanlandi: %s", window, theme)
    return theme


def pick_next_facet(facets: list[dict]) -> tuple[int, dict]:
    """Joriy oyna uchun hali ishlatilmagan qirrani tanlaydi. Hammasi ishlatilgan bo'lsa
    (masalan oyna kutilganidan uzoqroq davom etsa), ro'yxat qaytadan boshidan aylanadi -
    bu muammo emas, chunki har safar bir xil so'rov uchun ham tasodifiy boshqa
    rasm/video qaytishi mumkin."""
    window = _current_window_id()
    state = _load_json(STATE_FILE, {"window": window, "theme": None, "used_facets": []})

    used = set(state.get("used_facets", [])) if state.get("window") == window else set()
    all_indices = list(range(len(facets)))
    unused = [i for i in all_indices if i not in used]

    if not unused:
        unused = all_indices

    idx = random.choice(unused)
    return idx, facets[idx]


def mark_facet_used(idx: int) -> None:
    window = _current_window_id()
    state = _load_json(STATE_FILE, {"window": window, "theme": None, "used_facets": []})

    used = set(state.get("used_facets", [])) if state.get("window") == window else set()
    used.add(idx)
    state["used_facets"] = sorted(used)
    state["window"] = window
    _save_json(STATE_FILE, state)
