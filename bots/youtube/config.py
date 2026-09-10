"""
Konfiguratsiya moduli.
Barcha sozlamalar .env faylidan yoki muhit o'zgaruvchilaridan o'qiladi.

Diqqat: barcha o'zgaruvchilar `YOUTUBE_` prefiksi bilan (bot_hub'dagi boshqa
botlar — NATURE_/CRYPTO_/FOOTBALL_ — bilan bir xil konventsiya, bitta umumiy
.env faylida nomlar to'qnashib qolmasligi uchun). TELEGRAM_BOT_TOKEN alohida
berilmasa, boshqa botlar kabi umumiy TELEGRAM_BOT_TOKEN'ga tushiladi.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_BOT_DIR = Path(__file__).parent


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("YOUTUBE_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("YOUTUBE_TELEGRAM_CHANNEL_ID", "")

REGION_CODE = os.getenv("YOUTUBE_REGION_CODE", "UZ")
VIDEO_CATEGORY_ID = os.getenv("YOUTUBE_VIDEO_CATEGORY_ID", "10")  # 10 = Music

_exclude_categories_raw = os.getenv("YOUTUBE_EXCLUDE_CATEGORY_IDS", "20")  # 20 = Gaming
EXCLUDE_CATEGORY_IDS = {c.strip() for c in _exclude_categories_raw.split(",") if c.strip()}

_exclude_keywords_raw = os.getenv("YOUTUBE_EXCLUDE_KEYWORDS", "roblox,gameplay,minecraft,fortnite,gta,pubg,free fire")
EXCLUDE_KEYWORDS = [k.strip() for k in _exclude_keywords_raw.split(",") if k.strip()]
MAX_RESULTS = _int_env("YOUTUBE_MAX_RESULTS", 100)
MIN_VIEWS = _int_env("YOUTUBE_MIN_VIEWS", 100_000)
MAX_AGE_HOURS = _int_env("YOUTUBE_MAX_AGE_HOURS", 168)
MAX_DURATION_SEC = _int_env("YOUTUBE_MAX_DURATION_SEC", 180)

# Har bir ishga tushirishda joylanadigan postlar uchtaga bo'linadi:
#   POSTS_TRENDING     — hozir eng tez o'sayotgan (views_per_hour eng
#                         yuqori) — "trendni egallab turgan".
#   POSTS_MOST_VIEWED  — xom ko'rishlar soni bo'yicha eng ko'p ko'rilgan.
#   POSTS_NEWEST       — eng yaqinda chop etilgan.
# Har bir video faqat bitta turkumda ishlatiladi (takrorlanmaydi).
# MAX_POSTS_PER_RUN standart bo'yicha shu uchtasining yig'indisi (5),
# lekin xohlasangiz .env'da alohida ham belgilashingiz mumkin.
POSTS_TRENDING = _int_env("YOUTUBE_POSTS_TRENDING", 1)
POSTS_MOST_VIEWED = _int_env("YOUTUBE_POSTS_MOST_VIEWED", 2)
POSTS_NEWEST = _int_env("YOUTUBE_POSTS_NEWEST", 2)
MAX_POSTS_PER_RUN = _int_env("YOUTUBE_MAX_POSTS_PER_RUN", POSTS_TRENDING + POSTS_MOST_VIEWED + POSTS_NEWEST)

# MAX_POSTS_PER_RUN ichidan kamida shuncha tasi o'zbekcha (yoki o'zbekcha
# deb taxmin qilingan) kontent bo'lishi kafolatlanadi — agar tanlangan
# postlar orasida o'zbekcha bo'lmaganlari ko'proq bo'lsa ham, qolgan
# nomzodlar orasidan eng ko'p ko'rilgan o'zbekcha nomzod bilan
# almashtiriladi. O'zbekcha nomzod umuman topilmasa, bu talab
# e'tiborsiz qoldiriladi (xato bermaydi).
MIN_UZBEK_PER_RUN = _int_env("YOUTUBE_MIN_UZBEK_PER_RUN", 1)

# Har bir "turkum" (trending/most-viewed/newest) ichida ustunlik
# beriladigan tillar — vergul bilan ajratilgan ISO 639-1 kodlar.
# Standart: ingliz, rus, o'zbek — kanal asosiy auditoriyasi shu
# tillarda so'zlashadi. Bu qattiq filtr emas — shu tillardagi nomzodlar
# bo'lsa, ular ustunroq tanlanadi, lekin ular yetmasa boshqa tildagi
# (masalan tez-tez trend bo'lib qoladigan turkcha) nomzodlar ham
# ishlatilaveradi.
_preferred_langs_raw = os.getenv("YOUTUBE_PREFERRED_LANGUAGES", "en,ru,uz")
PREFERRED_LANGUAGES = [l.strip().lower() for l in _preferred_langs_raw.split(",") if l.strip()]

# Imkon qadar KAM ko'rsatiladigan tillar — vergul bilan ajratilgan
# ISO 639-1 kodlar. Standart: hind tili. Diqqat: bu ham qattiq filtr
# emas — agar biror turkumda faqat shu tildagi nomzod qolgan bo'lsa,
# baribir ishlatiladi (aks holda bot hech narsa joylay olmay qolishi
# mumkin edi, bu aynan STRICT_LANGUAGE_FILTER'ning muammosi edi).
_avoid_langs_raw = os.getenv("YOUTUBE_AVOID_LANGUAGES", "hi")
AVOID_LANGUAGES = [l.strip().lower() for l in _avoid_langs_raw.split(",") if l.strip()]

# REGION_CODE'dan tashqari, qidiruv qilinadigan qo'shimcha mintaqalar
# (vergul bilan ajratilgan). Faqat bitta mintaqada (masalan UZ) qidirish
# ko'pincha shu mintaqada mashhur, lekin kanal auditoriyasiga mos
# bo'lmagan tildagi (masalan hind) kontentni ustun qo'yib yuboradi —
# qo'shimcha mintaqalar (masalan AQSH, Rossiya) natijalarni xilma-
# xillashtirib, ingliz/rus tilidagi kontentni ham faol topishga
# yordam beradi. Bo'sh qoldirsangiz, faqat REGION_CODE'da qidiriladi.
_extra_regions_raw = os.getenv("YOUTUBE_EXTRA_REGION_CODES", "US,RU")
EXTRA_REGION_CODES = [r.strip().upper() for r in _extra_regions_raw.split(",") if r.strip()]

# Diqqat: bot endi so'z (matn) bo'yicha qidiruv ISHLATMAYDI (SEARCH_QUERY,
# RELEVANCE_LANGUAGE, STRICT_LANGUAGE_FILTER, INCLUDE_AI_MUSIC
# sozlamalari olib tashlandi) — bularning barchasi baribir global eng
# ko'p ko'rilgan (ko'pincha hind-tilidagi) kontentni qaytarishga moyil
# edi. Endi faqat YouTube'ning rasmiy TREND jadvalidan (REGION_CODE +
# EXTRA_REGION_CODES) foydalaniladi — batafsili youtube_trends.py
# modul docstring'ida.

# Qaysi uzunlikdagi videolar qidirilsin:
#   short — faqat Shorts (<= MAX_DURATION_SEC)
#   long  — faqat uzun videolar (MAX_DURATION_SEC dan MAX_LONG_DURATION_SEC gacha), Shorts'siz
#   both  — ikkalasi ham
# Standart "long" — musiqa Shorts'ga unchalik mos kelmagani uchun, Shorts
# manbasi umuman chaqirilmaydi va Shorts uzunlikdagi videolar filtr
# bosqichida ham butunlay chiqarib tashlanadi.
_video_length_mode_raw = os.getenv("YOUTUBE_VIDEO_LENGTH_MODE", "long").strip().lower()
VIDEO_LENGTH_MODE = _video_length_mode_raw if _video_length_mode_raw in ("short", "long", "both") else "long"
# "long" yoki "both" rejimida ruxsat etilgan eng katta davomiylik (soniya).
MAX_LONG_DURATION_SEC = _int_env("YOUTUBE_MAX_LONG_DURATION_SEC", 900)

DOWNLOAD_DIR = os.getenv("YOUTUBE_DOWNLOAD_DIR") or str(_BOT_DIR / "downloads")
POSTED_LOG_FILE = os.getenv("YOUTUBE_POSTED_LOG_FILE") or str(_BOT_DIR / "posted.json")
# YouTube "sign in to confirm you're not a bot" xatosi chiqsa, brauzerdan
# eksport qilingan cookies.txt fayl yo'lini shu yerga bering.
YTDLP_COOKIES_FILE = os.getenv("YOUTUBE_YTDLP_COOKIES_FILE", "") or None


def validate() -> None:
    """Ishga tushishdan oldin zarur sozlamalar borligini tekshiradi."""
    missing = []
    if not YOUTUBE_API_KEY:
        missing.append("YOUTUBE_API_KEY")
    if not TELEGRAM_BOT_TOKEN:
        missing.append("YOUTUBE_TELEGRAM_BOT_TOKEN (yoki TELEGRAM_BOT_TOKEN)")
    if not TELEGRAM_CHANNEL_ID:
        missing.append("YOUTUBE_TELEGRAM_CHANNEL_ID")
    if missing:
        raise RuntimeError(
            "Quyidagi .env o'zgaruvchilari to'ldirilmagan: " + ", ".join(missing)
        )
