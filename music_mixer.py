"""
Topilgan videoni Telegram uchun eng mos formatga (H.264/AAC, mp4) keltiradi va, agar
music/ papkasida trek bo'lsa, fon musiqasi qo'shadi — ikkalasi ham bitta ffmpeg
chaqiruvida bajariladi.

Nega kodek normalizatsiyasi kerak: Pexels/Pixabay har doim to'g'ridan-to'g'ri H.264 mp4
beradi, lekin Wikimedia Commons (wikimedia_fetcher.py) ko'pincha VP9/webm yoki Theora/ogv
formatida fayl beradi — bu formatlar barcha Telegram mijozlarida ishonchli ko'rinavermaydi.
Shuning uchun manba H.264 bo'lmasa, ffmpeg orqali qayta kodlanadi (va bir yo'la juda katta
o'lchamdagi original ~1920px'gacha kichraytiriladi — fayl hajmini nazoratda ushlab turish
uchun). Manba allaqachon H.264 bo'lsa (Pexels/Pixabay), video striim shunchaki nusxalanadi
(tezroq, sifat yo'qolmaydi).

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

# Qayta kodlashda videoning uzun tomoni shu qiymatdan oshmaydi (piksel) — fayl hajmini
# nazoratda ushlab turish va Telegram'ga yuklashni tezlashtirish uchun.
MAX_OUTPUT_DIMENSION = 1920
SCALE_FILTER = f"scale='min({MAX_OUTPUT_DIMENSION},iw)':'min({MAX_OUTPUT_DIMENSION},ih)':force_original_aspect_ratio=decrease"


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


def prepare_video_for_posting(video_path: Path, output_path: Path) -> bool:
    """video_path'dagi videoni Telegram uchun mos H.264/AAC mp4'ga keltiradi (kerak bo'lsa)
    va topilsa fon musiqasi qo'shadi, natijani output_path'ga saqlaydi.

    - Manba allaqachon H.264 bo'lsa: video striim nusxalanadi (tez, sifat yo'qolmaydi).
    - Boshqa kodek bo'lsa (masalan Wikimedia Commons'dan VP9/webm): H.264'ga qayta kodlanadi
      va bir yo'la MAX_OUTPUT_DIMENSION'gacha kichraytiriladi.
    - music/ papkasida trek topilsa, video uzunligiga moslab (kesib, oxirida asta
      pasaytirib) qo'shiladi; topilmasa, faqat kodek normalizatsiyasi bilan cheklanadi.

    Muvaffaqiyatli bo'lsa True, aks holda (ffmpeg yo'q yoki xatolik) False qaytaradi — bu
    holatda chaqiruvchi original (ishlov berilmagan) faylni joylashda davom etadi."""
    if not ffmpeg_available():
        logger.info("ffmpeg (yoki ffprobe) topilmadi, video asl holida joylanadi.")
        return False

    duration = _get_duration_seconds(video_path)
    codec = _get_video_codec(video_path)
    needs_reencode = codec != "h264"

    if needs_reencode:
        video_args = ["-vf", SCALE_FILTER, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
        logger.info("Video kodeki '%s' — Telegram uchun H.264'ga qayta kodlanadi.", codec)
    else:
        video_args = ["-c:v", "copy"]

    track = _pick_music_track()

    if track and duration and duration > 0:
        fade_start = max(duration - FADE_SECONDS, 0)
        cmd = [
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
    else:
        if not track:
            logger.info("music/ papkasida musiqa fayli topilmadi — faqat kodek moslashtiriladi.")
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            *video_args,
            "-c:a", "aac",
            str(output_path),
        ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
    except subprocess.SubprocessError as exc:
        logger.warning("ffmpeg orqali videoni tayyorlashda xatolik, asl fayl joylanadi: %s", exc)
        return False

    if track:
        logger.info("Video tayyorlandi (musiqa: %s, qayta kodlash: %s).", track.name, needs_reencode)
    else:
        logger.info("Video tayyorlandi (musiqasiz, qayta kodlash: %s).", needs_reencode)
    return True
