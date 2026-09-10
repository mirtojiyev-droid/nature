"""Coin/breakout kartalarini PNG rasm sifatida, zamonaviy "fintech ilova" uslubida
chizadi (gradient fon, yumshoq soyalar, pill-shaklidagi belgilar) — shared/canvas.py
umumiy chizish vositalaridan foydalanadi.
"""
from io import BytesIO

from PIL import Image, ImageDraw

from shared.canvas import diagonal_gradient, draw_pill, draw_triangle, paste_soft_shadow
from shared.fonts import get_font
from .analysis import signed_num

IMG_WIDTH = 1080
OUTER_PAD = 32          # rasm chekkasi va karta orasidagi bo'shliq (soya uchun joy qoldiradi)
CARD_RADIUS = 30
ACCENT_BAR_W = 10        # kartaning chap chetidagi rangli chiziq kengligi
CONTENT_X = 74           # accent chiziqdan keyingi matn boshlanish nuqtasi
CARD_RIGHT_PAD = 40

HEADER_Y = 44            # karta ichidagi yuqori qatorning (badge/symbol/pct) markazi
CHIP_ROW_Y = 108         # narx/RSI chip'lari qatori
NOTES_START_Y = 156
NOTE_LINE_HEIGHT = 34
BOTTOM_PAD = 30

# --- Rang palitrasi: chuqurroq, boyroq va "jonli" (avvalgi tekis ranglardan farqli) ---
PAGE_BG = "#05070B"

GRAD_UP = ("#0E3B28", "#081F16")
ACCENT_UP = "#22E37E"
TEXT_UP = "#3DFFA0"

GRAD_DOWN = ("#3D1220", "#210911")
ACCENT_DOWN = "#FF4D6D"
TEXT_DOWN = "#FF6B84"

GRAD_BREAKOUT = ("#3D2E0A", "#231A04")
ACCENT_BREAKOUT = "#FFC94D"
TEXT_BREAKOUT = "#FFD97A"

CARD_TEXT = "#F3F5FA"
CHIP_BG = "#00000055"
CHIP_TEXT = "#C7CDDB"
NOTE_TEXT = "#D8DCEA"
NOTE_BULLET_ALPHA = 255


def format_price(price: float) -> str:
    if price < 0.001:
        return f"{price:,.6f}"
    if price < 1:
        return f"{price:,.4f}"
    if price < 100:
        return f"{price:,.2f}"
    return f"{price:,.1f}"


def _card_height(n_notes: int) -> int:
    notes_block = n_notes * NOTE_LINE_HEIGHT if n_notes else -14
    return NOTES_START_Y + notes_block + BOTTOM_PAD


def _draw_chip(draw: ImageDraw.ImageDraw, x: int, y_center: int, text: str, font) -> int:
    """Kichik "chip" (pastki-qavariq to'rtburchak) ichida matn chizadi, chipning
    KENGLIGINI (keyingi chip qayerdan boshlanishi kerakligini) qaytaradi."""
    text_w = draw.textlength(text, font=font)
    pad_x = 20
    chip_w = text_w + pad_x * 2
    chip_h = 44
    draw.rounded_rectangle(
        [x, y_center - chip_h / 2, x + chip_w, y_center + chip_h / 2],
        radius=chip_h / 2, fill=CHIP_BG,
    )
    draw.text((x + chip_w / 2, y_center), text, font=font, fill=CHIP_TEXT, anchor="mm")
    return chip_w


def _draw_card_core(base: Image.Image, y_top: int, rank: int, symbol: str,
                     pct_value: float, price_line_parts: list[str], notes: list[str],
                     grad_colors: tuple[str, str], accent_color: str, text_color: str) -> int:
    h = _card_height(len(notes))
    x0, x1 = OUTER_PAD, IMG_WIDTH - OUTER_PAD
    y1 = y_top + h

    # 1) Yumshoq soya (kartaning o'zidan OLDIN chizilishi kerak — pastda qolishi uchun)
    paste_soft_shadow(base, [x0, y_top, x1, y1], CARD_RADIUS, opacity=130, offset=(0, 12), blur=26)

    # 2) Kartaning gradient foni (chap-yuqoridan o'ng-pastga, kartaning o'z hajmida)
    card_w, card_h = x1 - x0, y1 - y_top
    grad = diagonal_gradient((card_w, card_h), grad_colors[0], grad_colors[1])
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card_w, card_h], radius=CARD_RADIUS, fill=255)
    base.paste(grad, (x0, y_top), mask)

    draw = ImageDraw.Draw(base)

    # 3) Chap chetdagi rangli urg'u chizig'i (faqat kartaning chap burchaklariga mos
    # yumaloqlangan holda — kichik alohida forma sifatida, kartaning ustiga qo'yiladi)
    accent_mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(accent_mask).rounded_rectangle([0, 0, ACCENT_BAR_W * 2, card_h], radius=CARD_RADIUS, fill=255)
    accent_layer = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    ImageDraw.Draw(accent_layer).rectangle([0, 0, ACCENT_BAR_W, card_h], fill=accent_color)
    base.paste(accent_layer, (x0, y_top), Image.composite(accent_layer.split()[3], Image.new("L", (card_w, card_h), 0), accent_mask))

    # 4) Reyting (rank) belgisi — gradient-ga o'xshash effekt uchun to'q rang halqa + ichida raqam
    badge_cx, badge_cy = x0 + ACCENT_BAR_W + 54, y_top + HEADER_Y + 8
    badge_r = 34
    draw.ellipse([badge_cx - badge_r, badge_cy - badge_r, badge_cx + badge_r, badge_cy + badge_r], fill=accent_color)
    draw.ellipse([badge_cx - badge_r + 4, badge_cy - badge_r + 4, badge_cx + badge_r - 4, badge_cy + badge_r - 4],
                 outline="#00000030", width=2)
    draw.text((badge_cx, badge_cy), str(rank), font=get_font(34, "bold"), fill="#08110C" if accent_color != ACCENT_BREAKOUT else "#241A04", anchor="mm")

    # 5) Symbol nomi (katta, qalin)
    name_x = badge_cx + badge_r + 26
    draw.text((name_x, badge_cy), symbol, font=get_font(58, "bold"), fill=CARD_TEXT, anchor="lm")

    # 6) Foiz o'zgarishi — pill badge + uchburchak ikonka (emoji EMAS, chizilgan shakl)
    pct_text = f"{signed_num(pct_value, 1)}%"
    pct_font = get_font(40, "bold")
    pct_text_w = draw.textlength(pct_text, font=pct_font)
    tri_size = 26
    pill_pad_x = 24
    pill_gap = 10
    pill_h = 64
    pill_w = tri_size + pill_gap + pct_text_w + pill_pad_x * 2
    pill_x1 = x1 - CARD_RIGHT_PAD
    pill_x0 = pill_x1 - pill_w
    pill_y0 = badge_cy - pill_h / 2
    pill_y1 = badge_cy + pill_h / 2
    draw_pill(draw, [pill_x0, pill_y0, pill_x1, pill_y1], fill="#00000040")
    tri_cx = pill_x0 + pill_pad_x + tri_size / 2
    draw_triangle(draw, tri_cx, badge_cy, tri_size, text_color, pointing="up" if pct_value >= 0 else "down")
    draw.text((tri_cx + tri_size / 2 + pill_gap, badge_cy), pct_text, font=pct_font, fill=text_color, anchor="lm")

    # 7) Narx/RSI — chip'lar qatorida
    chip_x = name_x
    chip_font = get_font(26, "bold")
    for part in price_line_parts:
        chip_w = _draw_chip(draw, chip_x, y_top + CHIP_ROW_Y, part, chip_font)
        chip_x += chip_w + 14

    # 8) Izohlar — rangli nuqta + matn
    note_font = get_font(27)
    for i, note in enumerate(notes):
        ny = y_top + NOTES_START_Y + i * NOTE_LINE_HEIGHT
        draw.ellipse([name_x - 2, ny - 5, name_x + 8, ny + 5], fill=accent_color)
        draw.text((name_x + 22, ny), note, font=note_font, fill=NOTE_TEXT, anchor="lm")

    return h


def _render(notes: list[str], draw_fn) -> bytes:
    h = _card_height(len(notes))
    total_h = h + 2 * OUTER_PAD
    img = Image.new("RGBA", (IMG_WIDTH, total_h), PAGE_BG)
    draw_fn(img)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _get_note_lines(coin: dict) -> list[str]:
    # Eslatma: avvalgi (Binance) versiyada bu yerda funding/OI/long-short qatorlari
    # ham bo'lardi. CoinGecko'da bunday fyuchers ma'lumoti mavjud emas, shuning uchun
    # endi faqat RSI izohi ko'rsatiladi.
    return [coin["rsi_note"]]


def build_coin_card_image(coin: dict, is_up: bool, rank: int) -> bytes:
    notes = _get_note_lines(coin)
    symbol = coin["symbol"].replace("USDT", "")
    rsi = coin.get("rsi")
    price_parts = [f"Narx: {format_price(coin['last_price'])}", f"RSI {rsi:.1f}" if rsi is not None else "RSI —"]
    grad = GRAD_UP if is_up else GRAD_DOWN
    accent = ACCENT_UP if is_up else ACCENT_DOWN
    text_color = TEXT_UP if is_up else TEXT_DOWN

    return _render(notes, lambda base: _draw_card_core(
        base, OUTER_PAD, rank, symbol, coin["price_change_pct"], price_parts, notes, grad, accent, text_color,
    ))


def build_breakout_card_image(candidate: dict, rank: int, notes: list[str]) -> bytes:
    symbol = candidate["symbol"].replace("USDT", "")
    rsi = candidate.get("rsi")
    price_parts = [f"Narx: {format_price(candidate['last_price'])}", f"RSI {rsi:.1f}" if rsi is not None else "RSI —"]

    return _render(notes, lambda base: _draw_card_core(
        base, OUTER_PAD, rank, symbol, candidate["price_change_pct"], price_parts, notes,
        GRAD_BREAKOUT, ACCENT_BREAKOUT, TEXT_BREAKOUT,
    ))
