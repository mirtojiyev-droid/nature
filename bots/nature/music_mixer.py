"""
Topilgan videoni Telegram uchun eng mos formatga (H.264/AAC, mp4) keltiradi va, agar
music/ papkasida trek bo'lsa, fon musiqasi qo'shadi — ikkalasi ham bitta ffmpeg
chaqiruvida bajariladi.

Nega kodek normalizatsiyasi kerak: Pexels/Pixabay har doim to'g'ridan-to'g'ri H.264 mp4
beradi, lekin Wikimedia Commons (wikimedia_fetcher.py) ko'pincha VP9/webm yoki Theora/ogv
formatida fayl beradi — bu formatlar barcha Telegram mijozlarida ishonchli ko'rinavermaydi.
Shuning uchun manba H.264 bo'lmasa, ffmpeg orqali qayta kodlanadi. Manba allaqachon H.264
bo'lsa VA allaqachon TARGET_MAX_DIMENSION (4K) dan oshmasa (odatiy holat — Pexels/Pixabay),
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
import random
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

MUSIC_DIR = Path(__file__).parent / "music"
FADE_SECONDS = 2
MUSIC_EXTENSIONS = (".mp3", ".m4a", ".wav", ".ogg")

# Telegram Bot API orqali oddiy bot fayl yuborishning standart qattiq chegarasi.
TELEGRAM_MAX_VIDEO_BYTES = 50 * 1024 * 1024

# Eng yuqori maqsadli sifat — 4K (UHD). Agar shu sifatdagi natija Telegram hajm
# chegarasidan oshib ketsa, ketma-ket pastroq bosqichlar bilan qayta uriniladi.
TARGET_MAX_DIMENSION = 3840
FALLBACK_DIMENSIONS = [3840, 2560, 1920]  # 4K -> 2.5K -> Full HD


def _scale_filter(max_dimension: int) -> str:
    return f"scale='min({max_dimension},iw)':'min({max_dimension},ih)':force_original_aspect_ratio=decrease"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _pick_music_track() -> Path | None:
    if not MUSIC_DIR.exists():
        return None
    tracks = [p for p in MUSIC_DIR.iterdir() if p.suffix.lower() in MUSIC_EXTENSIONS]
    if not tracks:
        return None
    return random.choice(tracks)


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
                       duration: float | None, track: Path | None, crf: int) -> list[str]:
    if force_reencode:
        video_args = ["-vf", _scale_filter(max_dimension), "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p"]
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


def prepare_video_for_posting(video_path: Path, output_path: Path) -> bool:
    """video_path'dagi videoni Telegram uchun mos H.264/AAC mp4'ga keltiradi (kerak bo'lsa)
    va topilsa fon musiqasi qo'shadi, natijani output_path'ga saqlaydi.

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

    last_error = None
    success = False
    for attempt_idx, max_dimension in enumerate(FALLBACK_DIMENSIONS):
        # Birinchi urinishda, agar manba allaqachon H.264 bo'lsa, striim nusxalanadi
        # (tezroq, sifat yo'qolmaydi). Hajm 50MB'dan oshib, keyingi (pastroq) bosqichga
        # o'tilsa, endi albatta qayta kodlash orqali kichraytiriladi.
        force_reencode = (codec != "h264") or (attempt_idx > 0)
        crf = 23 if attempt_idx == 0 else 26  # pastroq bosqichlarda biroz ko'proq siqiladi
        cmd = _build_ffmpeg_cmd(video_path, output_path, max_dimension, force_reencode, duration, track, crf)

        try:
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
            logger.warning("Barcha sifat bosqichlarida ham video Telegram hajm chegarasidan katta chiqdi — eng pastki (%dpx) variant baribir joylanadi.", FALLBACK_DIMENSIONS[-1])

    if not success:
        logger.warning("ffmpeg orqali videoni tayyorlab bo'lmadi, asl fayl joylanadi: %s", last_error)
        return False

    if track:
        logger.info("Video tayyorlandi (musiqa: %s).", track.name)
    else:
        logger.info("Video tayyorlandi (musiqasiz).")
    return True
