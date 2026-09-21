"""
Ba'zan stock-kutubxonadan (Pixabay) yuklab olingan fayl texnik jihatdan
"buzuq" bo'lishi mumkin — masalan butunlay qora ekran, yoki bir xil rangdan iborat
placeholder kadr. Bunday fayl o'lcham/format jihatidan barcha filtrlardan muvaffaqiyatli
o'tadi (chunki piksel soni katta bo'lishi mumkin), lekin ko'rinishda mazmunsiz.

Bu modul PIL orqali rasmning rang xilma-xilligini (standart og'ish/entropy) tekshirib,
"deyarli bir xil rangdan iborat" fayllarni aniqlaydi — video uchun bir nechta kadr
tanlab, har birini shu tarzda tekshiradi.
"""
import logging
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# Standart og'ish shu qiymatdan past bo'lsa (0-255 shkalada), rasm "deyarli bir xil
# rangdan iborat" deb hisoblanadi — haqiqiy tabiat manzaralari (osmon, suv kabi silliq
# yuzalar bo'lsa ham) odatda bundan ancha yuqori qiymat beradi.
BLANK_STDDEV_THRESHOLD = 8.0


def _image_stddev(img: Image.Image) -> float:
    """Rasmning barcha kanallari (R,G,B) bo'yicha o'rtacha standart og'ishini
    qaytaradi — past qiymat = rang deyarli bir xil (bo'sh/qora ekran belgisi)."""
    small = img.convert("RGB").resize((160, 160))
    stat_values = []
    for channel in small.split():
        hist = channel.histogram()
        n = sum(hist)
        if n == 0:
            continue
        mean = sum(i * c for i, c in enumerate(hist)) / n
        variance = sum(((i - mean) ** 2) * c for i, c in enumerate(hist)) / n
        stat_values.append(variance ** 0.5)
    return sum(stat_values) / len(stat_values) if stat_values else 0.0


def is_blank_image_bytes(image_bytes: bytes) -> bool:
    """Rasm baytlari deyarli bir xil rangdan iborat bo'lsa (qora ekran, placeholder
    va h.k.) True qaytaradi. Rasmni ochib bo'lmasa (buzuq fayl), bu ham "yaroqsiz"
    deb hisoblanadi (True qaytadi) — xavfsiz tomonga og'ish."""
    try:
        img = Image.open(__import__("io").BytesIO(image_bytes))
        img.load()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rasmni ochib bo'lmadi (buzuq fayl bo'lishi mumkin): %s", exc)
        return True
    stddev = _image_stddev(img)
    if stddev < BLANK_STDDEV_THRESHOLD:
        logger.warning("Rasm deyarli bir xil rangdan iborat (stddev=%.1f) - bo'sh/buzuq deb belgilandi.", stddev)
        return True
    return False


def is_blank_video_file(video_path: Path, sample_count: int = 3) -> bool:
    """Video faylidan bir nechta kadr (boshi, o'rtasi, oxiri) tanlab, har birini
    is_blank_image_bytes() bilan tekshiradi. FAQAT hammasi bo'sh bo'lsa True qaytaradi
    (bitta-ikkita kadr tasodifan qora bo'lishi normal — masalan sahna almashinuvi
    fade-in/out effekti; lekin BARCHA tanlangan kadrlar bo'sh bo'lsa, bu butun video
    aslida bo'sh ekanidan dalolat beradi)."""
    ffprobe_duration = _get_duration(video_path)
    if ffprobe_duration is None or ffprobe_duration <= 0:
        return False  # davomiylikni aniqlab bo'lmasa, tekshiruvni o'tkazib yuboramiz (band qilmaymiz)

    timestamps = [ffprobe_duration * frac for frac in (0.15, 0.5, 0.85)][:sample_count]
    blank_count = 0
    checked = 0
    with tempfile.TemporaryDirectory() as tmp_dir:
        for i, ts in enumerate(timestamps):
            frame_path = Path(tmp_dir) / f"frame_{i}.jpg"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-ss", str(ts), "-i", str(video_path), "-frames:v", "1", "-q:v", "3", str(frame_path)],
                    capture_output=True, timeout=20, check=True,
                )
            except (subprocess.SubprocessError, OSError):
                continue
            if not frame_path.exists():
                continue
            checked += 1
            if is_blank_image_bytes(frame_path.read_bytes()):
                blank_count += 1

    if checked == 0:
        return False  # birorta kadr ham olinmadi - tekshiruvni o'tkazib yuboramiz
    return blank_count == checked


def _get_duration(video_path: Path) -> float | None:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True, text=True, timeout=15, check=True,
        )
        return float(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError, OSError):
        return None
