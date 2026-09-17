"""Pillow uchun shrift yuklovchi. Ubuntu/Debian VPS'da odatda DejaVu Sans o'rnatilgan
bo'ladi (`fonts-dejavu-core` paketi — ko'p distributivlarda standart o'rnatilgan).
Topilmasa, Pillow'ning ichki bitmap shriftiga (kichik, lekin xatosiz) tushiladi —
bot hech qachon shrift yo'qligi sababli qulab tushmaydi."""
import logging

from PIL import ImageFont

logger = logging.getLogger(__name__)

_REGULAR_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
]
_BOLD_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
]
_ITALIC_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Oblique.ttf",
]

_cache: dict[tuple[str, int], "ImageFont.FreeTypeFont"] = {}
_warned = False


def _first_existing(paths: list[str]) -> str | None:
    import os
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def get_font(size: int, weight: str = "regular") -> "ImageFont.ImageFont":
    """`weight`: "regular", "bold" yoki "italic". Topilmasa Pillow standart shriftiga
    (o'lchamsiz, kichik) tushiladi — faqat bir marta ogohlantirish yoziladi."""
    global _warned
    key = (weight, size)
    if key in _cache:
        return _cache[key]

    paths = {"bold": _BOLD_PATHS, "italic": _ITALIC_PATHS}.get(weight, _REGULAR_PATHS)
    path = _first_existing(paths)
    if path:
        font = ImageFont.truetype(path, size)
    else:
        if not _warned:
            logger.warning(
                "DejaVu Sans shrifti topilmadi (fonts-dejavu-core o'rnatilmagan bo'lishi mumkin) — "
                "kartalar standart (kichik) shrift bilan chiziladi. `sudo apt install fonts-dejavu-core` tavsiya etiladi."
            )
            _warned = True
        font = ImageFont.load_default()
    _cache[key] = font
    return font
