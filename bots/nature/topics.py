"""
Wikipedia orqali dunyo bo'ylab tabiiy diqqatga sazovor joylarni avtomatik topib, katta va
doimiy yangilanadigan joylar havzasini (pool) shakllantiradi.

places.py'dagi qo'lda yozilgan 69 ta joydan farqli ravishda, bu modul "butun internet bo'ylab"
(Wikipedia orqali — dunyodagi eng katta va ochiq bilim manbasi) minglab real joyni avtomatik
kashf qiladi. Natija bir haftaga keshlanadi, shuning uchun har safar Wikipedia'ga
murojaat qilinmaydi.
"""
import json
import logging
import re
import time
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
CACHE_FILE = Path(__file__).parent / "topic_pool_cache.json"
CACHE_MAX_AGE_SECONDS = 7 * 24 * 3600  # 1 hafta

# Tabiat mavzusidagi turli qidiruv so'zlari — har biri Wikipedia'dan ko'plab real joy
# haqidagi maqolani topib beradi. Ro'yxat qancha uzun bo'lsa, havza shuncha boy bo'ladi.
SEARCH_TERMS = [
    "national park", "waterfall", "island", "mountain range", "lake",
    "desert", "cave", "rainforest", "beach", "canyon", "volcano",
    "nature reserve", "valley", "fjord", "coral reef", "glacier",
    "hot spring", "sand dunes", "wildlife sanctuary", "mangrove forest",
    "archipelago", "peninsula", "gorge", "wetland",
]

# Kino, qo'shiq, kitob va h.k. nomlari bilan chalkashib ketmasligi uchun chetlab o'tiladigan naqshlar
_EXCLUDE_PATTERNS = re.compile(
    r"\((band|album|film|song|TV series|video game|novel|disambiguation|company|magazine|comics)\)",
    re.IGNORECASE,
)


def _is_valid_title(title: str) -> bool:
    if len(title) < 3:
        return False
    if title.lower().startswith("list of"):
        return False
    if _EXCLUDE_PATTERNS.search(title):
        return False
    return True


def _search_term(term: str, limit: int = 50) -> list[str]:
    try:
        resp = requests.get(
            WIKI_SEARCH_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": term,
                "srlimit": limit,
                "format": "json",
            },
            timeout=20,
            headers={"User-Agent": "NatureChannelBot/1.0"},
        )
        resp.raise_for_status()
        results = resp.json().get("query", {}).get("search", [])
        return [r["title"] for r in results if _is_valid_title(r["title"])]
    except requests.RequestException as exc:
        logger.warning("Wikipedia qidiruvida xatolik ('%s'): %s", term, exc)
        return []


def _fetch_fresh_pool() -> list[str]:
    pool: set[str] = set()
    for term in SEARCH_TERMS:
        titles = _search_term(term)
        pool.update(titles)
        logger.info("'%s' bo'yicha %d ta joy topildi (jami havza: %d)", term, len(titles), len(pool))
    return sorted(pool)


def _load_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("topic_pool_cache.json o'qib bo'lmadi: %s", exc)
        return None


def get_topic_pool(seed_places: list[str] | None = None) -> list[str]:
    """Joylar havzasini qaytaradi. Agar keshlangan (va 1 haftadan yosh) bo'lsa, undan foydalanadi,
    aks holda Wikipedia'dan yangisini yig'ib, keshlaydi. Tarmoq ishlamasa yoki hech narsa
    topilmasa, eski kesh yoki seed (places.py) ro'yxat bilan davom etadi — bot hech qachon
    shu sababdan to'xtamasligi kerak."""
    seed = seed_places or []

    cache = _load_cache()
    if cache:
        age = time.time() - cache.get("fetched_at", 0)
        if age < CACHE_MAX_AGE_SECONDS and cache.get("pool"):
            pool = sorted(set(cache["pool"]) | set(seed))
            logger.info("Joylar havzasi keshdan yuklandi: %d ta joy.", len(pool))
            return pool

    logger.info("Wikipedia'dan yangi joylar havzasi yig'ilmoqda (bir necha o'n soniya vaqt olishi mumkin)...")
    fresh_pool = _fetch_fresh_pool()

    if not fresh_pool:
        logger.warning("Wikipedia'dan hech narsa olinmadi, eski kesh yoki seed ro'yxat bilan davom etamiz.")
        if cache and cache.get("pool"):
            return sorted(set(cache["pool"]) | set(seed))
        return seed

    try:
        CACHE_FILE.write_text(
            json.dumps({"fetched_at": time.time(), "pool": fresh_pool}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Joylar havzasini keshga saqlab bo'lmadi: %s", exc)

    return sorted(set(fresh_pool) | set(seed))
