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

from .config import allowed_topics
from shared.data_dir import get_data_dir

logger = logging.getLogger(__name__)

WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
# MUHIM: HUB_DATA_DIR (.env) berilsa, bu fayl Render Persistent Disk'ga yoziladi va
# DEPLOY QILINGANDA HAM saqlanib qoladi — shared/data_dir.py'ga qarang.
CACHE_FILE = get_data_dir("nature", Path(__file__).parent) / "topic_pool_cache.json"
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

# Kino, qo'shiq, kitob va h.k. nomlari bilan chalkashib ketmasligi uchun chetlab o'tiladigan
# naqshlar. MUHIM (tuzatilgan xato): haqiqiy Wikipedia sahifalari deyarli har doim
# qo'shimcha so'zlar bilan nomlanadi — masalan "(2005 film)", "(American band)",
# "(TV series)" — shunchaki "(film)" emas. Avvalgi versiya aynan shu sababdan ishlamay
# qolgan edi (regex faqat qavs ichida ANIQ o'sha bitta so'z bo'lsagina ushlagan, real
# holatlarning deyarli barchasini o'tkazib yuborgan) — natijada 2005-yilgi "The Cave"
# dahshat filmi "g'or" (cave) qidiruvida joy sifatida qabul qilinib, kanalga film haqida
# ma'lumot post qilingan edi. Endi `\b...\b` va `[^)]*` bilan, qavs ichida boshqa so'zlar
# bo'lsa ham, kalit so'z topilsa yetarli.
_EXCLUDE_PATTERNS = re.compile(
    r"\([^)]*\b(band|album|film|movie|song|single|EP|TV series|television series|"
    r"miniseries|video game|novel|book|disambiguation|company|magazine|comics|"
    r"opera|musical|podcast|film series)\b[^)]*\)",
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


def _search_term(term: str, limit: int = 50, max_retries: int = 2) -> list[str]:
    for attempt in range(1, max_retries + 1):
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
            if resp.status_code == 429:
                if attempt >= max_retries:
                    logger.warning("Wikipedia so'rov chastotasi chegarasiga (429) yetdik ('%s'), bu safar o'tkazib yuboriladi.", term)
                    return []
                wait = float(resp.headers.get("Retry-After", 2 * attempt))
                logger.info("'%s' uchun 429 (rate-limit), %.0fs kutib qayta urinilmoqda...", term, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            results = resp.json().get("query", {}).get("search", [])
            return [r["title"] for r in results if _is_valid_title(r["title"])]
        except requests.RequestException as exc:
            logger.warning("Wikipedia qidiruvida xatolik ('%s'): %s", term, exc)
            return []
    return []


def _active_search_terms() -> list[str]:
    """Standart bo'yicha to'liq `SEARCH_TERMS` (24 ta) ishlatiladi. Agar
    foydalanuvchi .env'da NATURE_TOPICS bilan mavzularni CHEKLAGAN bo'lsa
    (masalan "ocean,forest,mountain"), FAQAT shu kalit so'zlarga mos keladigan
    (qisman moslik ham hisoblanadi — masalan "ocean" -> "coral reef" ga mos
    kelmaydi, lekin aynan shu so'zning o'zi ro'yxatda bo'lmasa, foydalanuvchi
    bergan so'z TO'G'RIDAN-TO'G'RI qo'shimcha qidiruv termini sifatida
    ishlatiladi) so'zlar bilan qidiriladi. Bu ham natijani mavzu bo'yicha
    cheklaydi, ham (kamroq so'z = kamroq Wikipedia so'rovi) havzani ANCHA
    TEZROQ yig'adi — bu esa Render qayta ishga tushishlari/deploylari
    tugallanishga ulgurmagan siklni to'xtatib qo'yish xavfini kamaytiradi."""
    topics = allowed_topics()
    if not topics:
        return SEARCH_TERMS

    active = []
    for topic in topics:
        matches = [term for term in SEARCH_TERMS if topic in term or term in topic]
        if matches:
            active.extend(m for m in matches if m not in active)
        elif topic not in active:
            # Foydalanuvchi ro'yxatda YO'Q so'z bergan (masalan "ocean") — baribir
            # to'g'ridan-to'g'ri Wikipedia qidiruv termini sifatida ishlatiladi,
            # chunki bu ham Pixabay/Pexels'da haqiqiy natija beradigan so'z bo'lishi
            # mumkin.
            active.append(topic)
    return active or SEARCH_TERMS


def _fetch_fresh_pool() -> dict[str, str]:
    """Har bir joy nomini QAYSI qidiruv termini (kategoriya, masalan "mountain
    range", "wetland" — yoki NATURE_TOPICS orqali cheklangan bo'lsa, shu
    ro'yxatdagi so'z) orqali topilganini ham saqlab qaytaradi — {joy_nomi:
    kategoriya}. Bu kategoriya keyinroq run.py'da "umumiy manzarasi" qirrasi
    uchun (aniq joy nomi bo'yicha Pixabay'da hech narsa topilmasa) TEMATIK
    JIHATDAN TO'G'RI zaxira qidiruv so'zi sifatida ishlatiladi (masalan noyob
    "Khentii Mountains" nomi o'rniga "mountain range" — bu haqiqatan ham o'sha
    joy haqida, umuman aloqasiz umumiy so'z emas)."""
    terms = _active_search_terms()
    pool: dict[str, str] = {}
    for i, term in enumerate(terms):
        titles = _search_term(term)
        for title in titles:
            pool.setdefault(title, term)  # birinchi topilgan kategoriya saqlanadi
        logger.info("'%s' bo'yicha %d ta joy topildi (jami havza: %d)", term, len(titles), len(pool))
        if i < len(terms) - 1:
            # Wikipedia'ni ketma-ket ko'p so'rov bilan band qilib, 429 (Too Many
            # Requests) xatosiga uchramaslik uchun har bir so'rov orasida kichik pauza.
            time.sleep(0.4)
    return pool


def _load_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("topic_pool_cache.json o'qib bo'lmadi: %s", exc)
        return None


# Oxirgi marta yuklangan/yig'ilgan {joy_nomi: kategoriya} bog'lanishi — modul
# xotirasida saqlanadi, get_place_category() shundan o'qiydi. get_topic_pool()
# chaqirilishi shart (odatda har run_once() boshida chaqiriladi allaqachon).
_last_category_map: dict[str, str] = {}


def get_place_category(place_name: str) -> str | None:
    """`place_name` (masalan "Khentii Mountains") qaysi qidiruv kategoriyasidan
    (masalan "mountain range") topilganini qaytaradi — topilmasa (masalan
    places.py'dagi qo'lda yozilgan seed joy bo'lsa) None. run.py buni "umumiy
    manzarasi" qirrasi uchun tematik jihatdan to'g'ri zaxira qidiruv so'zi
    sifatida ishlatadi (aniq, noyob joy nomi Pixabay'da topilmasa)."""
    return _last_category_map.get(place_name)


def get_topic_pool(seed_places: list[str] | None = None) -> list[str]:
    """Joylar havzasini qaytaradi. Agar keshlangan (va 1 haftadan yosh) bo'lsa, undan foydalanadi,
    aks holda Wikipedia'dan yangisini yig'ib, keshlaydi. Tarmoq ishlamasa yoki hech narsa
    topilmasa, eski kesh yoki seed (places.py) ro'yxat bilan davom etadi — bot hech qachon
    shu sababdan to'xtamasligi kerak."""
    global _last_category_map
    seed = seed_places or []
    active_terms = _active_search_terms()

    cache = _load_cache()
    if cache:
        age = time.time() - cache.get("fetched_at", 0)
        cached_pool = cache.get("pool")
        # MUHIM (NATURE_TOPICS bilan mos ishlashi uchun qo'shildi): agar
        # foydalanuvchi .env'da NATURE_TOPICS'ni O'ZGARTIRSA (masalan mavzularni
        # cheklasa yoki kengaytirsa), lekin eski (boshqa mavzular bilan
        # yig'ilgan) kesh hali 1 haftadan yosh bo'lsa — eski keshni ishlatish
        # noto'g'ri bo'lar edi (yangi sozlama e'tiborga olinmagan bo'lardi).
        # Shuning uchun kesh qaysi qidiruv terminlari bilan yig'ilganini ham
        # saqlaymiz va mos kelmasa, keshni chetlab o'tib, DARHOL qayta yig'amiz.
        cached_terms = cache.get("search_terms")
        terms_match = cached_terms is None or sorted(cached_terms) == sorted(active_terms)
        if age < CACHE_MAX_AGE_SECONDS and cached_pool and terms_match:
            if isinstance(cached_pool, dict):
                _last_category_map = cached_pool
                pool = sorted(set(cached_pool.keys()) | set(seed))
            else:
                _last_category_map = {}
                pool = sorted(set(cached_pool) | set(seed))
            logger.info("Joylar havzasi keshdan yuklandi: %d ta joy.", len(pool))
            return pool

    logger.info("Wikipedia'dan yangi joylar havzasi yig'ilmoqda (bir necha o'n soniya vaqt olishi mumkin)...")
    fresh_pool = _fetch_fresh_pool()

    if not fresh_pool:
        logger.warning("Wikipedia'dan hech narsa olinmadi, eski kesh yoki seed ro'yxat bilan davom etamiz.")
        if cache and cache.get("pool"):
            cached_pool = cache["pool"]
            if isinstance(cached_pool, dict):
                _last_category_map = cached_pool
                return sorted(set(cached_pool.keys()) | set(seed))
            _last_category_map = {}
            return sorted(set(cached_pool) | set(seed))
        return seed

    _last_category_map = fresh_pool
    try:
        CACHE_FILE.write_text(
            json.dumps(
                {"fetched_at": time.time(), "pool": fresh_pool, "search_terms": active_terms},
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Joylar havzasini keshga saqlab bo'lmadi: %s", exc)

    return sorted(set(fresh_pool.keys()) | set(seed))
