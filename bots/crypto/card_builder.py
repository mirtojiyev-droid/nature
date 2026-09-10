"""Coin/breakout kartalarini PNG rasm sifatida chizadi — kripto_bot_mobil.html'dagi
Canvas chizish mantiqining Pillow (server-side) porti. Piksel o'lchamlari JS versiyasi
bilan bir xil (1080px eni) — vizual natija deyarli bir xil ko'rinadi.
"""
from io import BytesIO

from PIL import Image, ImageDraw

from shared.fonts import get_font
from .analysis import signed_num

IMG_WIDTH = 1080
MARGIN_X = 36
NAME_ROW_Y = 38
PRICE_ROW_Y = 82
NOTES_START_Y = 118
NOTE_LINE_HEIGHT = 32
BOTTOM_PAD = 22
PAD = 26

BG = "#0F1220"
SUBTEXT = "#9AA0B4"
NOTE_COLOR = "#C7CBDB"
CARD_UP = "#12321F"
CARD_DOWN = "#3A1620"
TEXT_UP = "#3DDC84"
TEXT_DOWN = "#FF5D6C"
CARD_TEXT = "#E8E9F3"
CARD_BREAKOUT = "#332A12"
TEXT_BREAKOUT = "#FFC94D"


def format_price(price: float) -> str:
    if price < 0.001:
        return f"{price:,.6f}"
    if price < 1:
        return f"{price:,.4f}"
    if price < 100:
        return f"{price:,.2f}"
    return f"{price:,.1f}"


def _card_height(n_notes: int) -> int:
    return NOTES_START_Y + n_notes * NOTE_LINE_HEIGHT + BOTTOM_PAD


def _draw_card_core(draw: ImageDraw.ImageDraw, y_top: int, rank: int, symbol: str,
                     price_pct_text: str, price_line: str, notes: list[str],
                     card_color: str, text_color: str) -> int:
    h = _card_height(len(notes))
    draw.rounded_rectangle([MARGIN_X, y_top, IMG_WIDTH - MARGIN_X, y_top + h], radius=22, fill=card_color)

    badge_x, badge_y = MARGIN_X + 46, y_top + 46
    draw.ellipse([badge_x - 28, badge_y - 28, badge_x + 28, badge_y + 28], fill=text_color)
    draw.text((badge_x, badge_y), str(rank), font=get_font(35, "bold"), fill="#ffffff", anchor="mm")

    name_x = badge_x + 55
    draw.text((name_x, y_top + NAME_ROW_Y), symbol, font=get_font(56, "bold"), fill=CARD_TEXT, anchor="lm")

    pct_x = IMG_WIDTH - MARGIN_X - 30
    draw.text((pct_x, y_top + NAME_ROW_Y), price_pct_text, font=get_font(58, "bold"), fill=text_color, anchor="rm")

    draw.text((name_x, y_top + PRICE_ROW_Y), price_line, font=get_font(31), fill=SUBTEXT, anchor="lm")

    for i, note in enumerate(notes):
        draw.text((name_x, y_top + NOTES_START_Y + i * NOTE_LINE_HEIGHT), note,
                   font=get_font(29, "italic"), fill=NOTE_COLOR, anchor="lm")
    return h


def _get_note_lines(coin: dict) -> list[str]:
    # Eslatma: avvalgi (Binance) versiyada bu yerda funding/OI/long-short qatorlari
    # ham bo'lardi. CoinGecko'da bunday fyuchers ma'lumoti mavjud emas, shuning uchun
    # endi faqat RSI izohi ko'rsatiladi.
    return [coin["rsi_note"]]


def _render(notes: list[str], draw_fn) -> bytes:
    h = _card_height(len(notes))
    total_h = h + 2 * PAD
    img = Image.new("RGB", (IMG_WIDTH, total_h), BG)
    draw = ImageDraw.Draw(img)
    draw_fn(draw)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_coin_card_image(coin: dict, is_up: bool, rank: int) -> bytes:
    notes = _get_note_lines(coin)
    symbol = coin["symbol"].replace("USDT", "")
    rsi = coin.get("rsi")
    price_line = (
        f"Narx: {format_price(coin['last_price'])}  ·  RSI {rsi:.1f}" if rsi is not None
        else f"Narx: {format_price(coin['last_price'])}  ·  RSI —"
    )
    price_pct_text = f"{signed_num(coin['price_change_pct'], 1)}%"
    card_color = CARD_UP if is_up else CARD_DOWN
    text_color = TEXT_UP if is_up else TEXT_DOWN

    return _render(notes, lambda draw: _draw_card_core(
        draw, PAD, rank, symbol, price_pct_text, price_line, notes, card_color, text_color,
    ))


def build_breakout_card_image(candidate: dict, rank: int, notes: list[str]) -> bytes:
    symbol = candidate["symbol"].replace("USDT", "")
    rsi = candidate.get("rsi")
    price_line = (
        f"Narx: {format_price(candidate['last_price'])}  ·  RSI {rsi:.1f}" if rsi is not None
        else f"Narx: {format_price(candidate['last_price'])}  ·  RSI —"
    )
    price_pct_text = f"{signed_num(candidate['price_change_pct'], 1)}%"

    return _render(notes, lambda draw: _draw_card_core(
        draw, PAD, rank, symbol, price_pct_text, price_line, notes, CARD_BREAKOUT, TEXT_BREAKOUT,
    ))
