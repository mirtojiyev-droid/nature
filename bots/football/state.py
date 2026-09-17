"""
Futbol boti uchun saqlanuvchi holat:
1. Qaysi natija/fixture/yangilik postlari ALLAQACHON joylangani — bir xil o'yin yoki
   yangilik bir necha marta ketma-ket ishga tushirishda QAYTA joylanib ketmasligi uchun
   (avval bunday tekshiruv yo'q edi: masalan "so'nggi 2 kunlik natijalar" har safar
   qaytadan olinardi va bot har ishga tushganda BIR XIL o'yinni qayta-qayta post
   qilardi — bu asosiy tuzatilgan xato).
2. Futbolchi sharhi (spotlight) postlari orasidagi vaqtni (kuniga ~2 marta bo'lishi
   uchun) va so'nggi qaysi futbolchilar tanlanganini (tez orada takrorlanmasligi uchun).
3. Qiziqarli fakt (trivia) postlarida so'nggi qaysi mavzular ishlatilganini (tez orada
   takrorlanmasligi uchun).
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent / "posted_state.json"

# Natija/fixture/yangilik ID'lari shuncha kundan keyin holat faylidan tozalanadi
# (fayl cheksiz o'smasligi uchun) — FOOTBALL_DAYS_BACK/FORWARD standart qiymatlaridan
# (2 kun) ancha uzoqroq, shu bilan har qanday oqilona sozlamada takrorlanishning oldi
# olinadi.
DEDUP_KEEP_DAYS = 10
SPOTLIGHT_HISTORY_SIZE = 25  # so'nggi shuncha futbolchi tez orada takrorlanmaydi
TRIVIA_HISTORY_SIZE = 40  # so'nggi shuncha mavzu tez orada takrorlanmaydi

_DEFAULTS = {
    "posted_results": {},
    "posted_fixtures": {},
    "posted_news": {},
    "spotlight_history": [],
    "last_spotlight_at": None,
    "trivia_history": [],
}


def _load() -> dict:
    if not STATE_FILE.exists():
        return {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v) for k, v in _DEFAULTS.items()}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Holat faylini o'qib bo'lmadi, boshidan boshlanadi: %s", exc)
        data = {}
    for key, default in _DEFAULTS.items():
        data.setdefault(key, default)
    return data


def _save(state: dict) -> None:
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Holat faylini saqlab bo'lmadi: %s", exc)


# ---------------------------------------------------------------------------
# Natija / fixture / yangilik takrorlanishining oldini olish
# ---------------------------------------------------------------------------

def get_posted_ids(bucket: str) -> set[str]:
    """`bucket`: "posted_results", "posted_fixtures" yoki "posted_news"."""
    return set(_load().get(bucket, {}).keys())


def mark_posted(ids: list[str], bucket: str) -> None:
    if not ids:
        return
    state = _load()
    posted = state.setdefault(bucket, {})
    now_iso = datetime.now().isoformat()
    for _id in ids:
        posted[str(_id)] = now_iso
    cutoff = (datetime.now() - timedelta(days=DEDUP_KEEP_DAYS)).isoformat()
    state[bucket] = {k: v for k, v in posted.items() if v >= cutoff}
    _save(state)


# ---------------------------------------------------------------------------
# Futbolchi sharhi (kuniga ~2 marta)
# ---------------------------------------------------------------------------

def should_post_spotlight(min_hours_between: float) -> bool:
    last = _load().get("last_spotlight_at")
    if not last:
        return True
    try:
        elapsed_hours = (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 3600
    except ValueError:
        return True
    return elapsed_hours >= min_hours_between


def get_used_spotlight_names() -> set[str]:
    return set(_load().get("spotlight_history", []))


def mark_spotlight_posted(name: str) -> None:
    state = _load()
    history = state.get("spotlight_history", [])
    history.append(name)
    state["spotlight_history"] = history[-SPOTLIGHT_HISTORY_SIZE:]
    state["last_spotlight_at"] = datetime.now().isoformat()
    _save(state)


# ---------------------------------------------------------------------------
# Qiziqarli faktlar (har soatda)
# ---------------------------------------------------------------------------

def get_used_trivia_topics() -> set[str]:
    return set(_load().get("trivia_history", []))


def mark_trivia_posted(topic: str) -> None:
    state = _load()
    history = state.get("trivia_history", [])
    history.append(topic)
    state["trivia_history"] = history[-TRIVIA_HISTORY_SIZE:]
    _save(state)
