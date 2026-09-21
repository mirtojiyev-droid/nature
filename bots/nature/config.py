"""
Tabiat botining ".env" orqali sozlanadigan xatti-harakatini bir joyga jamlaydigan
modul — foydalanuvchi endi HAR SAFAR KOD O'ZGARTIRIB QAYTA YUKLAMASDAN, faqat
.env orqali quyidagilarni boshqarishi mumkin:

  - NATURE_MIN_VIDEO_PX / NATURE_MIN_PHOTO_PX — minimal sifat chegarasi (va
    bosqichma-bosqich pasayadigan zaxira darajalari — masalan 1080p topilmasa,
    avtomatik 720p bilan qayta qidiriladi, butunlay rad etish o'rniga).
  - NATURE_ALLOW_ORIENTATION_FALLBACK — vertikal format topilmasa, gorizontal
    videoni ham qabul qilib, ffmpeg orqali kerakli formatga (crop) moslashtirish.
  - NATURE_SOURCE_ORDER — qidiruv saytlari va ularning tartibi (masalan
    "pixabay,pexels,wikimedia"). Yangi manba qo'shish uchun run.py'dagi
    `_SOURCE_ADAPTERS` ro'yxatiga bitta yozuv qo'shish kifoya — bu yerdagi
    tartib/yoqish-o'chirish esa .env orqali, kod o'zgartirmasdan boshqariladi.
  - NATURE_MEDIA_MODE — "video_first" (standart), "video_only" yoki "photo_only".
  - NATURE_TOPICS — mavzularni qat'iy cheklash (masalan "ocean,forest,mountain").

MUHIM: bu funksiyalar (module-level konstanta emas) sifatida yozilgan, chunki
run.py ichida `load_dotenv()` `run_once()` FUNKSIYASI ICHIDA chaqiriladi — bu
modul esa run.py boshida IMPORT qilinadi (.env hali yuklanmagan paytda). Agar
qiymatlar import vaqtida hisoblansa, .env'dagi o'zgarish e'tiborga olinmay
qolardi (bots/nature/quality.py'dagi bir xil eslatmaga qarang).
"""
import os

DEFAULT_MIN_VIDEO_TIERS = [1080, 720]
DEFAULT_MIN_PHOTO_TIERS = [1600, 1080]
DEFAULT_SOURCE_ORDER = ["pixabay", "pexels", "wikimedia"]
VALID_MEDIA_MODES = ("video_first", "video_only", "photo_only")


def _parse_int_list(raw: str) -> list[int] | None:
    try:
        values = [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError:
        return None
    return values or None


def min_video_dimension_tiers() -> list[int]:
    """Video uchun minimal (qisqa tomon) piksel chegarasi — BOSQICHMA-BOSQICH
    pasayadigan ro'yxat. Standart: [1080, 720] — avval 1080p+ qidiriladi, hech
    narsa topilmasa, butunlay rad etish o'rniga 720p+ bilan qayta uriniladi.

    .env orqali: NATURE_MIN_VIDEO_PX=720 (bitta qiymat — pastroq zaxira
    darajalar avtomatik qo'shiladi) yoki NATURE_MIN_VIDEO_PX=1080,720,480
    (to'liq ro'yxat, vergul bilan, tartib muhim)."""
    raw = os.getenv("NATURE_MIN_VIDEO_PX", "").strip()
    if not raw:
        return list(DEFAULT_MIN_VIDEO_TIERS)
    if "," in raw:
        return _parse_int_list(raw) or list(DEFAULT_MIN_VIDEO_TIERS)
    try:
        primary = int(raw)
    except ValueError:
        return list(DEFAULT_MIN_VIDEO_TIERS)
    tiers = [primary]
    for fallback in (720, 480):
        if fallback < primary:
            tiers.append(fallback)
    return tiers


def min_photo_dimension_tiers() -> list[int]:
    """`min_video_dimension_tiers()` bilan bir xil mantiq, rasm uchun (standart:
    [1600, 1080]). .env: NATURE_MIN_PHOTO_PX."""
    raw = os.getenv("NATURE_MIN_PHOTO_PX", "").strip()
    if not raw:
        return list(DEFAULT_MIN_PHOTO_TIERS)
    if "," in raw:
        return _parse_int_list(raw) or list(DEFAULT_MIN_PHOTO_TIERS)
    try:
        primary = int(raw)
    except ValueError:
        return list(DEFAULT_MIN_PHOTO_TIERS)
    tiers = [primary]
    if 1080 < primary:
        tiers.append(1080)
    return tiers


def allow_orientation_fallback() -> bool:
    """True bo'lsa (standart), afzal ko'rilgan format (masalan vertikal)da hech
    narsa topilmasa, QARSHI formatdagi (gorizontal) video/rasm ham nomzod
    sifatida qabul qilinadi (keyin video uchun ffmpeg markazdan kesib — crop —
    kerakli formatga moslaydi). MUHIM SABAB: Pixabay/Pexels'dagi tabiat
    videolarining aksariyati kino/dron uslubida GORIZONTAL tushirilgan —
    faqat "sof vertikal" talab qilish nomzodlar sonini keskin kamaytirar,
    natijada ko'p postlar video topilmagani uchun faqat rasm bilan qolar edi."""
    return os.getenv("NATURE_ALLOW_ORIENTATION_FALLBACK", "true").lower() == "true"


def media_mode() -> str:
    """"video_first" (standart — avval video, so'ng alohida rasm ham
    joylanadi), "video_only" (faqat video, rasm hech qachon joylanmaydi) yoki
    "photo_only" (faqat rasm, video umuman qidirilmaydi) — NATURE_MEDIA_MODE
    orqali."""
    mode = os.getenv("NATURE_MEDIA_MODE", "video_first").strip().lower()
    return mode if mode in VALID_MEDIA_MODES else "video_first"


def source_order() -> list[str]:
    """Manbalar TARTIBI va qaysilari YOQILGANI — NATURE_SOURCE_ORDER orqali
    (masalan "pixabay,pexels,wikimedia" yoki faqat "pixabay,wikimedia" — Pexels
    butunlay chetlab o'tiladi). API kaliti sozlanmagan manba (masalan
    PEXELS_API_KEY bo'sh bo'lsa "pexels") baribir run.py'da avtomatik chetlab
    o'tiladi, hatto shu ro'yxatda ko'rsatilgan bo'lsa ham."""
    raw = os.getenv("NATURE_SOURCE_ORDER", "").strip()
    if not raw:
        return list(DEFAULT_SOURCE_ORDER)
    order = [item.strip().lower() for item in raw.split(",") if item.strip()]
    return order or list(DEFAULT_SOURCE_ORDER)


def wikipedia_discovery_enabled() -> bool:
    """True bo'lsa (standart), bot Wikipedia orqali minglab qo'shimcha joy
    nomini avtomatik kashf qiladi (topics.py) — bu ko'proq xilma-xillik beradi,
    lekin Wikipedia'ning to'liq matn qidiruvi ba'zan tabiatga aloqasi yo'q
    natija (masalan tarixiy voqea) qaytarishi mumkin (filtrlangan bo'lsa ham).

    NATURE_ENABLE_WIKI_DISCOVERY=false qilib qo'yilsa, Wikipedia BUTUNLAY
    chetlab o'tiladi — bot FAQAT places.py'dagi qo'lda tekshirilgan 69 ta
    haqiqiy joy nomi bilan ishlaydi (bular ham to'g'ridan-to'g'ri Pixabay/
    Pexels'dan qidiriladi — Wikipedia hech qachon rasm/video BERMAYDI, faqat
    QIDIRUV SO'ZI/JOY NOMI manbai bo'lib xizmat qiladi). Bu kamroq xilma-xillik
    degani, lekin tabiatga aloqasi yo'q mavzu postlanish ehtimoli NOLGA
    tushadi, chunki 69 ta joyning har biri qo'lda tanlangan haqiqiy tabiat
    manzili."""
    return os.getenv("NATURE_ENABLE_WIKI_DISCOVERY", "true").strip().lower() != "false"


def allowed_topics() -> list[str] | None:
    """Foydalanuvchi qat'iy mavzular ro'yxati bersa (NATURE_TOPICS=ocean,forest,
    mountain — vergul bilan), bot Wikipedia orqali FAQAT shu kalit so'zlar
    bo'yicha joy qidiradi (topics.py'dagi keng, standart 24 ta so'zlik ro'yxat
    o'rniga) — bu ham natijani mavzu bo'yicha cheklaydi, ham havzani tezroq
    yig'ish orqali umumiy sikl vaqtini qisqartiradi. Bo'sh bo'lsa, None
    qaytaradi — standart (keng) rejim ishlaydi."""
    raw = os.getenv("NATURE_TOPICS", "").strip()
    if not raw:
        return None
    topics = [t.strip().lower() for t in raw.split(",") if t.strip()]
    return topics or None
