"""
Bir nechta video faylni (masalan AI orqali yaratilgan bir nechta qisqa klipni, yoki
localfootage/'dagi bir necha faylni) BITTA uzunroq videoga birlashtiradi — ffmpeg'ning
`concat` FILTRI orqali (oddiy "concat demuxer" emas, chunki u BARCHA fayllar bir xil
kodek/o'lcham/fps bo'lishini talab qiladi — bizning fayllarimiz turli manbalardan
kelgani uchun bu deyarli hech qachon to'g'ri kelmaydi).

Filtr yondashuvi har bir klipni BIR XIL o'lcham/fps/formatga keltirib, SO'NG
birlashtiradi — shuning uchun turli xil manba fayllar (masalan bittasi Runway'dan
720x1280, ikkinchisi Kling'dan 720x1280 boshqa fps bilan) muammosiz ishlaydi.

Audio olib tashlanadi (chiqish ovozsiz) — chunki bu videolar odatda keyinroq
music_mixer.py orqali fon musiqasi bilan birlashtiriladi, va turli manbalardagi
o'ziga xos (ba'zan yo'q) audio izlarini saqlashning ma'nosi yo'q.
"""
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920  # 9:16 vertikal (Shorts/Reels) - kanalning standart formati
DEFAULT_FPS = 30


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def combine_videos(
    clip_paths: list[Path], output_path: Path,
    width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, fps: int = DEFAULT_FPS,
    crf: int = 20,
) -> bool:
    """`clip_paths`dagi videolarni berilgan tartibda bitta `output_path` videosiga
    birlashtiradi. Muvaffaqiyatli bo'lsa True, xatolik bo'lsa (ffmpeg yo'q, fayl
    o'qilmadi va h.k.) False qaytaradi — chaqiruvchi shu holatda faqat BITTA (masalan
    birinchi) klipni ishlatishga qaytishi mumkin."""
    if not clip_paths:
        logger.warning("combine_videos: bo'sh ro'yxat berildi.")
        return False
    if len(clip_paths) == 1:
        # Birlashtirishga hojat yo'q - shunchaki nusxalaymiz (formatni bir xillashtirib).
        return _normalize_single(clip_paths[0], output_path, width, height, fps, crf)

    if not ffmpeg_available():
        logger.warning("ffmpeg topilmadi - videolarni birlashtirib bo'lmaydi.")
        return False

    missing = [p for p in clip_paths if not p.exists()]
    if missing:
        logger.warning("Birlashtirish uchun berilgan fayllardan ba'zilari topilmadi: %s", missing)
        return False

    inputs = []
    filter_parts = []
    for i, path in enumerate(clip_paths):
        inputs += ["-i", str(path)]
        filter_parts.append(
            f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}[v{i}]"
        )
    concat_inputs = "".join(f"[v{i}]" for i in range(len(clip_paths)))
    filter_complex = ";".join(filter_parts) + f";{concat_inputs}concat=n={len(clip_paths)}:v=1:a=0[outv]"

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=True)
        return output_path.exists() and output_path.stat().st_size > 0
    except subprocess.CalledProcessError as exc:
        logger.warning("Videolarni birlashtirishda ffmpeg xatoligi: %s", exc.stderr[-800:] if exc.stderr else exc)
        return False
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("Videolarni birlashtirishda kutilmagan xatolik: %s", exc)
        return False


def _normalize_single(src: Path, output_path: Path, width: int, height: int, fps: int, crf: int) -> bool:
    if not ffmpeg_available():
        shutil.copyfile(src, output_path)
        return True
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-pix_fmt", "yuv420p",
        "-an",
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=180, check=True)
        return output_path.exists() and output_path.stat().st_size > 0
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("Video formatini bir xillashtirishda xatolik: %s", exc)
        return False
