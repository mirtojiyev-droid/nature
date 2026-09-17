"""
Rasmga video overlay (music_mixer.py'dagi _build_overlay_filter) bilan BIR XIL vizual
uslubda — pastki chap burchakda yarim shaffof fon + oq matn (joy nomi + kanal
brendi) — "lower-third" chizadi. Shunda video va rasm postlari bir xil "pro"
brendlashga ega bo'ladi.
"""
import io
import logging

from PIL import Image, ImageDraw

from shared.fonts import get_font

logger = logging.getLogger(__name__)


def add_branding_overlay(photo_bytes: bytes, location_text: str, brand_label: str) -> bytes | None:
    """`photo_bytes`ga joy nomi + brend matnini chizib, natijani PNG bayt sifatida
    qaytaradi. Har qanday sababdan (buzuq rasm va h.k.) muvaffaqiyatsiz bo'lsa, None
    qaytaradi — chaqiruvchi bu holatda asl (overlay'siz) rasmni joylashda davom
    etishi kerak."""
    try:
        img = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    except Exception as exc:  # noqa: BLE001 - rasm formatidan qat'i nazar xavfsiz davom etish uchun
        logger.warning("Rasmni ochib bo'lmadi, overlay qo'shilmaydi: %s", exc)
        return None

    W, H = img.size
    draw = ImageDraw.Draw(img, "RGBA")

    # Shrift o'lchamlarini rasm o'lchamiga nisbatan moslashtiramiz (video overlay'dagi
    # kabi qattiq piksel emas — chunki rasm o'lchamlari juda xilma-xil bo'lishi mumkin).
    loc_font_size = max(28, round(W * 0.045))
    brand_font_size = max(16, round(W * 0.026))
    pad_x, pad_y = round(W * 0.02), round(W * 0.012)

    loc_font = get_font(loc_font_size, "bold")
    brand_font = get_font(brand_font_size, "regular")

    margin = round(W * 0.045)
    bottom = H - margin

    def draw_pill_text(text: str, font, y_bottom: int, box_color=(0, 0, 0, 110)) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        box = [margin, y_bottom - text_h - pad_y * 2, margin + text_w + pad_x * 2, y_bottom]
        draw.rounded_rectangle(box, radius=min(14, text_h // 2), fill=box_color)
        draw.text((margin + pad_x, y_bottom - pad_y - text_h - bbox[1]), text, font=font, fill="white")
        return box[1]  # yuqori chegara - keyingi (yuqoridagi) qatorni shunga nisbatan joylashtirish uchun

    top_of_brand = draw_pill_text(brand_label, brand_font, bottom, box_color=(0, 0, 0, 90)) if brand_label else bottom
    gap = round(W * 0.012)
    draw_pill_text(location_text, loc_font, top_of_brand - gap)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
