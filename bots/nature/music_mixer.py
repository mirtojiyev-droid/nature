"""
Topilgan videoni Telegram uchun eng mos formatga (H.264/AAC, mp4) keltiradi va, agar
music/ papkasida trek bo'lsa, fon musiqasi qo'shadi — ikkalasi ham bitta ffmpeg
chaqiruvida bajariladi.

Nega kodek normalizatsiyasi kerak: Pixabay har doim to'g'ridan-to'g'ri H.264 mp4
beradi, lekin Wikimedia Commons (wikimedia_fetcher.py) ko'pincha VP9/webm yoki Theora/ogv
formatida fayl beradi — bu formatlar barcha Telegram mijozlarida ishonchli ko'rinavermaydi.
Shuning uchun manba H.264 bo'lmasa, ffmpeg orqali qayta kodlanadi. Manba allaqachon H.264
bo'lsa VA allaqachon TARGET_MAX_DIMENSION (4K) dan oshmasa (odatiy holat — Pixabay),
video striim shunchaki nusxalanadi (tezroq, sifat yo'qolmaydi).

SIFAT vs TELEGRAM HAJM CHEGARASI: fetch bosqichida (media_fetcher.py/pixabay_fetcher.py/
wikimedia_fetcher.py) endi 4K'gacha video qabul qilinadi, lekin Telegram Bot API orqali
oddiy bot fayl yuborishda ~50MB qattiq chegara bor. Shuning uchun bu modul avval eng
yuqori sifat (4K, TARGET_MAX_DIMENSION) bilan tayyorlaydi, natijani hajm bo'yicha
tekshiradi, va agar 50MB'dan oshib ketsa — AVTOMATIK ravishda pastroq o'lchamda (2560,
so'ng 1920) qayta kodlab, hajmga sig'guncha davom etadi. Shunday qilib, odatiy qisqa
tabiat kliplari uchun har doim eng yuqori mumkin bo'lgan sifat ishlatiladi, lekin uzunroq
klip hajm chegarasiga urilib, post butunlay yo'qolib qolmaydi.

ffmpeg topilmasa yoki xatolik yuz bersa, xatolik bermaydi — shunchaki False qaytaradi, va
chaqiruvchi (main.py) original (yuklab olingan, lekin ishlov berilmagan) faylni joylashda
davom etadi.
"""
import logging
import os
import random
import shutil
import subprocess
from pathlib import Path

from shared.resource_guard import heavy_operation

logger = logging.getLogger(__name__)

MUSIC_DIR = Path(__file__).parent / "music"
FADE_SECONDS = 2
MUSIC_EXTENSIONS = (".mp3", ".m4a", ".wav", ".ogg")

# Video ustiga yoziladigan brend matni ("pro" ko'rinish uchun, quyidagi
# _build_overlay_filter() orqali) — kanal nomingizni shu yerda o'zgartiring, yoki
# .env'dagi NATURE_BRAND_LABEL orqali qayta belgilang.
DEFAULT_BRAND_LABEL = "Nature Channel"

_FONT_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]

# Telegram Bot API orqali oddiy bot fayl yuborishning standart qattiq chegarasi.
TELEGRAM_MAX_VIDEO_BYTES = 50 * 1024 * 1024

# Eng yuqori maqsadli sifat — standart 4K (UHD). Agar shu sifatdagi natija Telegram
# hajm chegarasidan oshib ketsa, ketma-ket pastroq bosqichlar bilan qayta uriniladi.
#
# MUHIM (kam xotirali serverlar uchun): 4K'da ffmpeg (libx264) qayta kodlash bir necha
# yuz MB'gacha operativ xotira talab qilishi mumkin. Render/Railway kabi platformalarning
# eng arzon tariflari (odatda 512MB) uchun bu YETARLI BO'LMASLIGI mumkin va "out of
# memory" xatosiga olib kelishi mumkin. Shuning uchun eng yuqori bosqich .env orqali
# pasaytirilishi mumkin: NATURE_MAX_VIDEO_QUALITY_PX=1920 (yoki 1280) qiling.
_DEFAULT_FALLBACK_TIERS = [3840, 2560, 1920, 1280]


def _fallback_dimensions() -> list[int]:
    """FALLBACK_DIMENSIONS ro'yxatini NATURE_MAX_VIDEO_QUALITY_PX bilan cheklab
    qaytaradi. .env o'zgarishi darhol ta'sir qiladi (modul yuklanganda emas, har safar
    prepare_video_for_posting chaqirilganda hisoblanadi)."""
    try:
        cap = int(os.getenv("NATURE_MAX_VIDEO_QUALITY_PX", "3840"))
    except ValueError:
        cap = 3840
    tiers = [t for t in _DEFAULT_FALLBACK_TIERS if t <= cap]
    return tiers or [cap]


def _scale_filter(max_dimension: int) -> str:
    return f"scale='min({max_dimension},iw)':'min({max_dimension},ih)':force_original_aspect_ratio=decrease"


def _crop_to_vertical_filter(max_dimension: int) -> str:
    """MUHIM (universal manba-orientatsiya qo'llab-quvvatlash uchun qo'shildi):
    manba video GORIZONTAL (kino/dron uslubida tushirilgan, ko'pchilik Pixabay/
    Pexels tabiat kliplari shunday) bo'lsa-yu, vertikal (9:16, Stories/Shorts
    ko'rinishi) chiqish kerak bo'lsa, oddiy `scale` filtri (yon tomonlariga
    qora chiziq/padding qo'shadi) o'rniga MARKAZDAN KESIB (crop) 9:16 nisbatga
    keltiradi — natija to'liq ekranni egallaydi, qora chiziqlarsiz. Manba
    balandligi 9:16 nisbatdan "torroq" (juda keng panorama) bo'lsa, avval
    kenglik bo'yicha kesib, keyin belgilangan o'lchamgacha kattalashtiriladi."""
    return (
        f"crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',"
        f"scale='min({max_dimension},iw)':'min({max_dimension*16//9},ih)':force_original_aspect_ratio=decrease"
    )


def _first_existing_font(paths: list[str]) -> str | None:
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def _escape_drawtext(text: str) -> str:
    """ffmpeg'ning drawtext filtri uchun matnni xavfsiz qiladi — filtr sintaksisida
    maxsus ma'noga ega belgilarni (: ' \\ % ,) escape qiladi. Buni qilmasak, masalan
    joy nomida qo'shtirnoq yoki ikki nuqta bo'lsa (masalan "Xi'an" yoki "12:00"),
    butun ffmpeg buyrug'i sintaksis xatosi bilan ishlamay qolardi."""
    return (
        text.replace("\\", "\\\\\\\\")
        .replace(":", "\\:")
        .replace("'", "\u2019")  # oddiy qo'shtirnoq - ffmpeg filtr ichida muammoli, tipografik variantga almashtiramiz
        .replace("%", "\\%")
        .replace(",", "\\,")
    )


def _build_overlay_filter(location_text: str | None, brand_label: str | None) -> str | None:
    """Video pastki qismiga joy nomi + kanal brendini "pro" ko'rinishda (yarim shaffof
    fon + oq matn, lower-third uslubi) chizadigan drawtext filtr zanjirini yasaydi.
    `location_text` berilmasa (None/bo'sh), overlay UMUMAN qo'shilmaydi — chaqiruvchi
    buni ixtiyoriy sifatida ishlatishi mumkin."""
    if not location_text:
        return None
    bold_font = _first_existing_font(_FONT_BOLD_PATHS)
    regular_font = _first_existing_font(_FONT_REGULAR_PATHS)
    if not bold_font:
        # Shrift fayli topilmasa, drawtext filtri ishlay olmaydi (fontfile shart) -
        # overlay'siz davom etamiz, bot baribir ishlashda davom etadi.
        logger.info("DejaVu Sans-Bold shrifti topilmadi - video ustiga matn qo'yilmaydi.")
        return None
    regular_font = regular_font or bold_font

    loc_escaped = _escape_drawtext(location_text)
    parts = [
        f"drawtext=fontfile='{bold_font}':text='{loc_escaped}':fontsize=52:fontcolor=white:"
        f"x=56:y=h-160:box=1:boxcolor=black@0.42:boxborderw=18"
    ]
    if brand_label:
        brand_escaped = _escape_drawtext(brand_label)
        parts.append(
            f"drawtext=fontfile='{regular_font}':text='{brand_escaped}':fontsize=30:fontcolor=white@0.88:"
            f"x=56:y=h-88:box=1:boxcolor=black@0.32:boxborderw=12"
        )
    return ",".join(parts)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _is_valid_audio_file(path: Path) -> bool:
    """`path` haqiqatan ochiladigan, audio oqimiga ega faylmi — tekshiradi. MUHIM
    (haqiqiy voqeada aniqlangan muammo): foydalanuvchi music/ papkasiga qo'shgan
    ba'zi fayllar (masalan noodatiy kodlash/buzuq meta-ma'lumot bilan) ffmpeg'ning
    `-stream_loop` + filtr birikmasida barcha sifat darajalarida ham xato berishiga
    sabab bo'lgan edi — bitta buzuq musiqa fayli tufayli BUTUN video (barcha 4
    urinish ham) muvaffaqiyatsiz bo'lib qolardi. Endi bunday fayl OLDINDAN
    aniqlanadi va o'tkazib yuboriladi (boshqa trek sinaladi, yoki musiqasiz
    davom etiladi) — bitta buzuq faylning butun videoni "yiqitishi" oldini oladi."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=20,
        )
        return result.returncode == 0 and "audio" in result.stdout
    except (subprocess.SubprocessError, OSError):
        return False


def _pick_music_track() -> Path | None:
    if not MUSIC_DIR.exists():
        return None
    tracks = [p for p in MUSIC_DIR.iterdir() if p.suffix.lower() in MUSIC_EXTENSIONS]
    random.shuffle(tracks)
    for track in tracks:
        if _is_valid_audio_file(track):
            return track
        logger.warning("Musiqa fayli (%s) buzuq/noto'g'ri formatda ko'rinadi - o'tkazib yuborildi.", track.name)
    return None


def _get_duration_seconds(path: Path) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return float(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError) as exc:
        logger.warning("Video davomiyligini aniqlab bo'lmadi: %s", exc)
        return None


def _get_video_codec(path: Path) -> str | None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, text=True, timeout=30, check=True,
        )
        codec = result.stdout.strip()
        return codec or None
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("Video kodekini aniqlab bo'lmadi: %s", exc)
        return None


def _build_ffmpeg_cmd(video_path: Path, output_path: Path, max_dimension: int, force_reencode: bool,
                       duration: float | None, track: Path | None, crf: int,
                       overlay_filter: str | None = None, crop_to_vertical: bool = False) -> list[str]:
    if force_reencode:
        vf = _crop_to_vertical_filter(max_dimension) if crop_to_vertical else _scale_filter(max_dimension)
        if overlay_filter:
            vf = f"{vf},{overlay_filter}"
        video_args = ["-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p"]
    else:
        video_args = ["-c:v", "copy"]

    if track and duration and duration > 0:
        fade_start = max(duration - FADE_SECONDS, 0)
        return [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-stream_loop", "-1", "-i", str(track),
            "-filter_complex",
            f"[1:a]atrim=0:{duration},afade=t=out:st={fade_start}:d={FADE_SECONDS}[aout]",
            "-map", "0:v", "-map", "[aout]",
            *video_args,
            "-c:a", "aac",
            "-shortest",
            str(output_path),
        ]
    return [
        "ffmpeg", "-y",
        "-i", str(video_path),
        *video_args,
        "-c:a", "aac",
        str(output_path),
    ]


def prepare_video_for_posting(video_path: Path, output_path: Path,
                               location_text: str | None = None, brand_label: str | None = None,
                               crop_to_vertical: bool = False) -> bool:
    """video_path'dagi videoni Telegram uchun mos H.264/AAC mp4'ga keltiradi (kerak bo'lsa)
    va topilsa fon musiqasi qo'shadi, natijani output_path'ga saqlaydi.

    `location_text` berilsa (masalan joy nomi), video pastki qismiga "pro" ko'rinishdagi
    (yarim shaffof fon + oq matn) brendlash matni bitta ffmpeg bosqichida qo'shiladi —
    alohida ikkinchi qayta kodlash bosqichi KERAK EMAS (samaradorlik uchun muhim).
    `brand_label` berilmasa, `.env`dagi NATURE_BRAND_LABEL yoki standart qiymat ishlatiladi.

    `crop_to_vertical=True` bo'lsa (run.py manba GORIZONTAL ekanini, lekin
    VERTIKAL chiqish kerakligini aniqlaganda beradi — NATURE_ALLOW_ORIENTATION_
    FALLBACK yoqilgan bo'lganda ko'p uchraydigan holat), video markazdan
    kesib (crop) 9:16 formatga keltiriladi (qora chiziqlar bilan to'ldirish
    o'rniga) — bu holatda albatta qayta kodlanadi (stream-copy ishlatilmaydi).

    Eng yuqori sifat (4K, TARGET_MAX_DIMENSION) bilan boshlanadi. Manba allaqachon H.264
    bo'lsa va qayta kodlash shart bo'lmasa, video striim shunchaki nusxalanadi (tez, sifat
    yo'qolmaydi). Natija tayyorlangach hajmi tekshiriladi — agar TELEGRAM_MAX_VIDEO_BYTES
    (~50MB, Telegram Bot API'ning oddiy bot uchun standart yuklash chegarasi) dan oshsa,
    FALLBACK_DIMENSIONS ro'yxatidagi keyingi (pastroq) o'lchamda avtomatik qayta kodlab
    qayta uriniladi — toki hajmga sig'guncha yoki variantlar tugaguncha. Shu tarzda,
    odatiy qisqa tabiat kliplari uchun har doim eng yuqori mumkin bo'lgan sifat (4K)
    ishlatiladi, lekin uzunroq/og'irroq klip Telegram chegarasiga urilib, post butunlay
    yo'qolib qolmaydi — faqat avtomatik pastroq sifatga tushiriladi.

    music/ papkasida trek topilsa, video uzunligiga moslab (kesib, oxirida asta
    pasaytirib) qo'shiladi; topilmasa, faqat kodek/o'lcham moslashtiriladi.

    Muvaffaqiyatli bo'lsa True, aks holda (ffmpeg yo'q yoki xatolik) False qaytaradi — bu
    holatda chaqiruvchi original (ishlov berilmagan) faylni joylashda davom etadi."""
    if not ffmpeg_available():
        logger.info("ffmpeg (yoki ffprobe) topilmadi, video asl holida joylanadi.")
        return False

    duration = _get_duration_seconds(video_path)
    codec = _get_video_codec(video_path)
    track = _pick_music_track()
    if not track:
        logger.info("music/ papkasida musiqa fayli topilmadi — faqat kodek/o'lcham moslashtiriladi.")

    brand_label = brand_label or os.getenv("NATURE_BRAND_LABEL", DEFAULT_BRAND_LABEL)
    overlay_filter = _build_overlay_filter(location_text, brand_label)
    if overlay_filter:
        logger.info("Video ustiga brendlash matni qo'shiladi: '%s' / '%s'", location_text, brand_label)

    last_error = None
    success = False
    fallback_dimensions = _fallback_dimensions()
    for attempt_idx, max_dimension in enumerate(fallback_dimensions):
        # Birinchi urinishda, agar manba allaqachon H.264 bo'lsa VA overlay so'ralmagan
        # bo'lsa, striim nusxalanadi (tezroq, sifat yo'qolmaydi). Overlay so'ralgan bo'lsa,
        # matnni "kuydirish" uchun albatta qayta kodlash SHART (stream-copy orqali matn
        # qo'shib bo'lmaydi) — shuning uchun bu holatda force_reencode har doim True.
        force_reencode = (codec != "h264") or (attempt_idx > 0) or bool(overlay_filter) or crop_to_vertical
        crf = 23 if attempt_idx == 0 else 26  # pastroq bosqichlarda biroz ko'proq siqiladi
        cmd = _build_ffmpeg_cmd(video_path, output_path, max_dimension, force_reencode, duration, track, crf,
                                 overlay_filter, crop_to_vertical)

        try:
            # MUHIM (OOM-qulash sikli tuzatildi — shared/resource_guard.py'ga
            # qarang): ffmpeg operativ xotira jihatidan og'ir, shuning uchun
            # kripto botining karta chizish bosqichi bilan BIR VAQTDA ishlamasligi
            # uchun umumiy "og'ir operatsiya" semafori bilan o'raladi.
            with heavy_operation("nature-ffmpeg"):
                subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
        except subprocess.SubprocessError as exc:
            # MUHIM: bu urinish muvaffaqiyatsiz bo'ldi deb `success`ni ATAYLAB False'da
            # qoldiramiz — ffmpeg xatolik bilan chiqqanda ham output_path'da chala/buzuq
            # fayl qolib ketishi mumkin (masalan disk to'lib qolgani uchun), va faqat
            # "fayl mavjudmi" tekshiruvi bunday holatni noto'g'ri "muvaffaqiyat" deb
            # hisoblashi mumkin edi. Shuning uchun muvaffaqiyat FAQAT shu pastdagi
            # muvaffaqiyatli subprocess.run() dan keyin, aniq belgilanadi.
            last_error = exc
            success = False
            logger.warning("ffmpeg orqali videoni (%dpx) tayyorlashda xatolik: %s", max_dimension, exc)
            continue

        size = output_path.stat().st_size if output_path.exists() else 0
        if size == 0:
            last_error = "ffmpeg muvaffaqiyatli tugadi, lekin natija fayli bo'sh chiqdi"
            success = False
            logger.warning("Video %dpx bosqichida bo'sh fayl chiqdi, keyingi bosqich sinaladi.", max_dimension)
            continue

        success = True
        if size <= TELEGRAM_MAX_VIDEO_BYTES:
            if attempt_idx > 0:
                logger.info(
                    "Video %dpx sifatda %.1fMB'ga siqildi (Telegram 50MB chegarasiga sig'ish uchun avtomatik pasaytirildi).",
                    max_dimension, size / (1024 * 1024),
                )
            break
        logger.warning(
            "Tayyorlangan video %.1fMB — Telegram'ning ~50MB chegarasidan katta, pastroq sifat bilan qayta urinilmoqda.",
            size / (1024 * 1024),
        )
    else:
        if success:
            logger.warning("Barcha sifat bosqichlarida ham video Telegram hajm chegarasidan katta chiqdi — eng pastki (%dpx) variant baribir joylanadi.", fallback_dimensions[-1])

    if not success:
        # MUHIM (chalkashtiruvchi eski matn tuzatildi): bu funksiya False qaytarganda,
        # chaqiruvchi (run.py) ENDI xom faylni joylamaydi — bu nomzod butunlay rad
        # etiladi va navbatdagi nomzod sinaladi. Shuning uchun matn "hech qanday fayl
        # joylanmaydi" deb aniq yozilgan, avvalgi ("asl fayl joylanadi") noto'g'ri edi.
        logger.warning("ffmpeg orqali videoni hech qanday sifat darajasida tayyorlab bo'lmadi (bu nomzod rad etiladi): %s", last_error)
        return False

    if track:
        logger.info("Video tayyorlandi (musiqa: %s).", track.name)
    else:
        logger.info("Video tayyorlandi (musiqasiz).")
    return True
