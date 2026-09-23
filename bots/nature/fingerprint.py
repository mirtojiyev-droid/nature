"""
Media "barmoq izi" (fingerprint) — BIR XIL kontentni URL/ID'dan qat'i nazar tanib olish.

NEGA KERAK: ID bo'yicha tekshiruv faqat BITTA manba ichida ishlaydi. Amalda bir xil
video/rasm bir nechta joyda uchraydi:
  - bitta muallif bir xil klipni Pixabay'ga HAM, Pexels'ga HAM yuklaydi (ID'lar boshqa);
  - Wikimedia'da bir xil rasm turli fayl nomi bilan qayta yuklangan bo'ladi;
  - bir xil video turli sifatda (720p/1080p) — fayl baytlari butunlay boshqa.
Shuning uchun kontentning O'ZIDAN hisoblangan perceptual hash (dHash) saqlanadi:
o'lcham/sifat/siqish o'zgarsa ham deyarli bir xil qoladi.

  - Rasm: 64-bitli dHash (9x8 kulrang kichraytirish).
  - Video: 20%, 50%, 80% nuqtalaridagi 3 ta kadrning dHash'i. Kamida 2 ta kadr
    o'xshash bo'lsa — bir xil video deb hisoblanadi.
"""
from __future__ import annotations

import hashlib
import io
import logging
import subprocess
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

VIDEO_SAMPLE_POINTS = (0.2, 0.5, 0.8)


def dhash(img: Image.Image) -> int:
    small = img.convert("L").resize((9, 8), Image.LANCZOS)
    px = list(small.getdata())
    value = 0
    for row in range(8):
        for col in range(8):
            left = px[row * 9 + col]
            right = px[row * 9 + col + 1]
            value = (value << 1) | (1 if left > right else 0)
    return value


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def photo_fingerprint(photo_bytes: bytes) -> dict:
    fp = {"sha256": sha256_bytes(photo_bytes)}
    try:
        fp["phash"] = [dhash(Image.open(io.BytesIO(photo_bytes)))]
    except Exception as exc:  # noqa: BLE001 - buzilgan rasm fingerprint'siz qoladi
        logger.debug("Rasm dHash hisoblanmadi: %s", exc)
    return fp


def _duration(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=20, check=True,
        ).stdout.strip()
        return float(out)
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def _frame_at(path: Path, ts: float) -> Image.Image | None:
    try:
        out = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{ts:.2f}", "-i", str(path),
             "-frames:v", "1", "-vf", "scale=64:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, timeout=30, check=True,
        ).stdout
        return Image.open(io.BytesIO(out)) if out else None
    except (subprocess.SubprocessError, OSError, Exception):  # noqa: BLE001
        return None


def video_fingerprint(path: Path) -> dict:
    fp: dict = {}
    sha = sha256_file(path)
    if sha:
        fp["sha256"] = sha
    dur = _duration(path)
    if not dur or dur <= 0:
        return fp
    hashes = []
    for p in VIDEO_SAMPLE_POINTS:
        frame = _frame_at(path, dur * p)
        if frame is not None:
            hashes.append(dhash(frame))
    if len(hashes) == len(VIDEO_SAMPLE_POINTS):
        fp["phash"] = hashes
    return fp


def is_similar(kind: str, a: list[int], b: list[int], photo_threshold: int = 6, video_threshold: int = 10) -> bool:
    if not a or not b:
        return False
    if kind == "photo":
        return hamming(a[0], b[0]) <= photo_threshold
    if len(a) != len(b):
        return False
    close = sum(1 for x, y in zip(a, b) if hamming(x, y) <= video_threshold)
    return close >= 2
