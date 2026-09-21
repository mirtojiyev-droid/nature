"""Coin/breakout kartalarini PNG rasm sifatida chizadi — 3-versiya, ChatGPT/Gemini
tahlillari asosida qayta ishlangan.

MUHIM QAROR (nima o'zgardi, va nima ATAYLAB o'zgartirilMAdi):
1. FORMAT 16:9'dan 4:5'ga (1080x1350) o'tkazildi — Telegram mobil-feedida ancha
   ko'proq joy egallaydi, e'tiborni ko'proq tortadi.
2. FOIZ O'ZGARISHI endi "hero" (eng katta, markaziy) element — chunki odam
   birinchi navbatda "qancha o'sdi/tushdi"ni bilishni xohlaydi, RSI emas.
3. HAJM (VOLUME) bloki qo'shildi — bu odamni haqiqatan qiziqtiradigan, avval
   butunlay ko'rsatilmagan kuchli ko'rsatkich edi.
4. RSI endi KICHIK, ikkinchi darajali belgi (gauge emas, kompakt pill) —
   asosiy "qahramon" coin va foiz bo'lsin, RSI yordamchi ma'lumot.
5. Fon to'liq qora ("#05070B") o'rniga chuqur ko'k-yashil gradient — Telegram
   feedida ko'proq "premium" va yorqinroq ko'rinadi.
6. ATAYLAB QO'SHILMAGAN: "Entry", "Target", "Stop Loss" narxlari va
   "MASSIVE MOVE INCOMING" kabi shoshiltiruvchi sarlavhalar. Bizning ma'lumot
   manbamiz (narx, RSI, hajm) bunday aniq narx maqsadlarini hisoblashga
   yetarli emas — buni ko'rsatish o'ylab topilgan raqamlarni haqiqiy tahlil
   qilib ko'rsatish bo'lardi, bu odamlarni chalg'itishi mumkin. Status matni
   FAQAT haqiqatan hisoblangan ma'lumotlarga (RSI, hajm nisbati) asoslanadi.
"""
from io import BytesIO

from PIL import Image, ImageDraw

from shared.canvas import diagonal_gradient, draw_candlestick_chart, draw_pill, draw_soft_glow_rect, draw_triangle, paste_soft_shadow
from shared.fonts import get_font
from .analysis import format_volume, rsi_status_short, signed_num

IMG_WIDTH = 1080
IMG_HEIGHT = 1620
OUTER_PAD = 40
CARD_RADIUS = 36
ACCENT_BAR_H = 10   # endi TEPADA gorizontal chiziq (portret formatga mosroq)

BRAND_LABEL = "Crypto bozor"

PAGE_BG = "#05070B"

# Har bir turkum uchun: fon gradienti, urg'u rangi, matn rangi, status pill matni
PALETTES = {
    "up": {
        "grad": ("#0A2F22", "#071A14"), "accent": "#22E37E", "text": "#3DFFA0",
        "status_label": "TOP GAINER", "status_icon": "\U0001F680",
    },
    "down": {
        "grad": ("#33101C", "#1C0910"), "accent": "#FF4D6D", "text": "#FF6B84",
        "status_label": "TOP LOSER", "status_icon": "\u26A0\uFE0F",
    },
    "breakout": {
        "grad": ("#332708", "#1E1704"), "accent": "#FFC94D", "text": "#FFD97A",
        "status_label": "BREAKOUT RADAR", "status_icon": "\u26A1",
    },
}

CARD_TEXT = "#F3F5FA"
SUB_TEXT = "#B7C0D6"
CHIP_BG = "#00000055"
BRAND_TEXT = "#8993AC"


def format_price(price: float) -> str:
    if price < 0.001:
        return f"{price:,.6f}"
    if price < 1:
        return f"{price:,.4f}"
    if price < 100:
        return f"{price:,.2f}"
    return f"{price:,.1f}"


def _momentum_status(rsi: float | None, pct: float) -> str:
    """Katta, jonli, LEKIN faqat haqiqatan hisoblangan ma'lumotga (RSI+foiz)
    asoslangan xulosa — o'ylab topilgan narx maqsadlari EMAS."""
    if rsi is not None and rsi > 70 and pct > 0:
        return "Kuchli xarid bosimi"
    if rsi is not None and rsi < 30 and pct < 0:
        return "Kuchli sotuv bosimi"
    if abs(pct) >= 8:
        return "Yuqori volatillik"
    return "Barqaror harakat"


def _draw_status_pill(base: Image.Image, draw, cx_left: int, y: int, palette: dict) -> int:
    text = f"{palette['status_icon']} {palette['status_label']}"
    font = get_font(30, "bold")
    text_w = draw.textlength(text, font=font)
    pad_x, h = 26, 56
    w = text_w + pad_x * 2
    # Yumshoq porlash (glow) — statusni "chaqiruvchi belgi"dek his qildiradi,
    # neon-uslubidagi zamonaviy trading-ilova dizaynlariga xos urg'u.
    draw_soft_glow_rect(base, [cx_left, y, cx_left + w, y + h], palette["accent"], opacity=130, blur=30)
    draw_pill(draw, [cx_left, y, cx_left + w, y + h], fill=palette["accent"])
    draw.text((cx_left + w / 2, y + h / 2), text, font=font,
              fill="#08110C" if palette is not PALETTES["breakout"] else "#241A04", anchor="mm")
    return h


def _draw_stat_block(draw, x: int, y: int, w: int, label: str, value: str, accent: str, value_font_size=44) -> int:
    """Ikki qatorli statistik blok (masalan "24H VOLUME" / "$48.6B") — chap
    tekislangan, kichik katta-harfli yorliq + katta qiymat."""
    draw.text((x, y), label, font=get_font(20, "bold"), fill=accent, anchor="lm")
    draw.text((x, y + 40), value, font=get_font(value_font_size, "bold"), fill=CARD_TEXT, anchor="lm")
    return 40 + value_font_size


def _draw_card(base: Image.Image, rank: int, symbol: str, pct_value: float,
               price: float, volume: float | None, volume_ratio: float | None,
               rsi: float | None, candles: list[dict] | None, palette: dict) -> None:
    x0, y0, x1, y1 = OUTER_PAD, OUTER_PAD, IMG_WIDTH - OUTER_PAD, IMG_HEIGHT - OUTER_PAD
    card_w, card_h = x1 - x0, y1 - y0

    paste_soft_shadow(base, [x0, y0, x1, y1], CARD_RADIUS, opacity=140, offset=(0, 16), blur=32)

    grad = diagonal_gradient((card_w, card_h), palette["grad"][0], palette["grad"][1])
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card_w, card_h], radius=CARD_RADIUS, fill=255)
    base.paste(grad, (x0, y0), mask)

    draw = ImageDraw.Draw(base)

    # Tepadagi rangli chiziq (portret formatda "chap chiziq" o'rniga)
    top_accent_mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(top_accent_mask).rounded_rectangle([0, 0, card_w, ACCENT_BAR_H * 3], radius=CARD_RADIUS, fill=255)
    top_layer = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    ImageDraw.Draw(top_layer).rectangle([0, 0, card_w, ACCENT_BAR_H], fill=palette["accent"])
    base.paste(top_layer, (x0, y0), Image.composite(top_layer.split()[3], Image.new("L", (card_w, card_h), 0), top_accent_mask))

    pad = 56
    cursor_y = y0 + 56

    # 1) Brendlash (kichik, yuqorida)
    brand_r = 12
    draw.ellipse([x0 + pad - brand_r, cursor_y - brand_r, x0 + pad + brand_r, cursor_y + brand_r], fill=palette["accent"])
    draw.text((x0 + pad + brand_r + 10, cursor_y), BRAND_LABEL, font=get_font(22, "bold"), fill=BRAND_TEXT, anchor="lm")
    if rank:
        rank_text = f"#{rank}"
        draw.text((x1 - pad, cursor_y), rank_text, font=get_font(24, "bold"), fill=SUB_TEXT, anchor="rm")
    cursor_y += 90

    # 2) Status pill (TOP GAINER / TOP LOSER / BREAKOUT RADAR)
    pill_h = _draw_status_pill(base, draw, x0 + pad, cursor_y, palette)
    cursor_y += pill_h + 70

    # 3) Symbol nomi (katta)
    draw.text((x0 + pad, cursor_y), symbol, font=get_font(84, "bold"), fill=CARD_TEXT, anchor="lm")
    cursor_y += 150

    # 4) HERO: foiz o'zgarishi — ENG KATTA, markaziy element, orqasida yumshoq
    # porlash (glow) bilan — e'tiborni birinchi navbatda shu raqamga tortadi.
    pct_text = f"{signed_num(pct_value, 2)}%"
    hero_font = get_font(172, "bold")
    tri_size = 68
    tri_cx = x0 + pad + tri_size / 2
    hero_text_x = x0 + pad + tri_size + 24
    hero_text_w = draw.textlength(pct_text, font=hero_font)
    draw_soft_glow_rect(
        base, [hero_text_x - 20, cursor_y - 20, hero_text_x + hero_text_w + 20, cursor_y + 160],
        palette["accent"], opacity=90, blur=50,
    )
    draw_triangle(draw, tri_cx, cursor_y + 90, tri_size, palette["text"], pointing="up" if pct_value >= 0 else "down")
    draw.text((hero_text_x, cursor_y), pct_text, font=hero_font, fill=palette["text"], anchor="lm")
    cursor_y += 230

    # 5) Narx (hero'dan kichikroq, lekin aniq)
    draw.text((x0 + pad, cursor_y), f"${format_price(price)}", font=get_font(54, "bold"), fill=CARD_TEXT, anchor="lm")
    cursor_y += 130

    # 6) Ajratuvchi chiziq
    draw.line([x0 + pad, cursor_y, x1 - pad, cursor_y], fill="#FFFFFF22", width=2)
    cursor_y += 56

    # 6.5) Yaponcha shamlar (candlestick) grafigi — narxning so'nggi harakati.
    # MUHIM: CoinGecko bepul tarifida "haqiqiy soatlik" granulярlik yo'q (bu faqat
    # pullik tarifda ishlaydi) — shuning uchun bu yerda 30 daqiqalik shamlar
    # ko'rsatiladi (odatda ~48 tasi), va sarlavhada aniq shunday deb yozilgan —
    # "soatlik" deb noto'g'ri da'vo qilinmaydi.
    if candles:
        chart_h = 260
        chart_label = f"NARX HARAKATI \u2014 {len(candles)} x 30 DAQIQALIK SHAM"
        draw.text((x0 + pad, cursor_y), chart_label, font=get_font(20, "bold"), fill=palette["accent"], anchor="lm")
        cursor_y += 36
        draw_candlestick_chart(
            draw, [x0 + pad, cursor_y, x1 - pad, cursor_y + chart_h],
            candles, up_color=PALETTES["up"]["accent"], down_color=PALETTES["down"]["accent"],
        )
        cursor_y += chart_h + 50
    else:
        cursor_y += 20

    # 7) Statistik bloklar: HAJM (chap) + RSI (o'ng, kichikroq)
    col_w = (card_w - 2 * pad) / 2
    if volume is not None:
        vol_label = "24H VOLUME"
        vol_value = format_volume(volume)
        if volume_ratio:
            vol_value += f"  \u26A1{volume_ratio:.1f}x"
        _draw_stat_block(draw, x0 + pad, cursor_y, col_w, vol_label, vol_value, palette["accent"], value_font_size=52)

    rsi_label = "RSI (14)"
    rsi_value = f"{rsi:.0f}" if rsi is not None else "\u2014"
    rsi_status = rsi_status_short(rsi)
    rsi_x = x0 + pad + col_w + 20
    draw.text((rsi_x, cursor_y), rsi_label, font=get_font(20, "bold"), fill=palette["accent"], anchor="lm")
    draw.text((rsi_x, cursor_y + 48), rsi_value, font=get_font(52, "bold"), fill=CARD_TEXT, anchor="lm")
    rsi_val_w = draw.textlength(rsi_value, font=get_font(52, "bold"))
    draw.text((rsi_x + rsi_val_w + 18, cursor_y + 62), rsi_status, font=get_font(24), fill=SUB_TEXT, anchor="lm")
    cursor_y += 140

    # 8) Status xulosasi (faqat haqiqiy ma'lumotga asoslangan, raqamsiz)
    cursor_y += 40
    status_text = _momentum_status(rsi, pct_value)
    box_h = 96
    draw.rounded_rectangle([x0 + pad, cursor_y, x1 - pad, cursor_y + box_h], radius=18, fill=CHIP_BG)
    draw.text((x0 + pad * 1.5, cursor_y + box_h / 2), f"\U0001F4CA {status_text}", font=get_font(34, "bold"), fill=palette["text"], anchor="lm")

    # 9) Pastki qism: brend + disclaimer
    footer_y = y1 - 54
    draw.text((x0 + pad, footer_y), BRAND_LABEL, font=get_font(20, "bold"), fill=BRAND_TEXT, anchor="lm")
    draw.text((x1 - pad, footer_y), "Tahliliy ma'lumot, moliyaviy maslahat emas",
              font=get_font(17), fill=SUB_TEXT, anchor="rm")


def _render(draw_fn) -> bytes:
    img = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), PAGE_BG)
    draw_fn(img)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def build_coin_card_image(coin: dict, is_up: bool, rank: int) -> bytes:
    palette = PALETTES["up"] if is_up else PALETTES["down"]
    return _render(lambda base: _draw_card(
        base, rank, coin["symbol"].replace("USDT", ""), coin["price_change_pct"],
        coin["last_price"], coin.get("quote_volume"), None, coin.get("rsi"),
        coin.get("candles"), palette,
    ))


def build_breakout_card_image(candidate: dict, rank: int, notes: list[str]) -> bytes:
    return _render(lambda base: _draw_card(
        base, rank, candidate["symbol"].replace("USDT", ""), candidate["price_change_pct"],
        candidate["last_price"], candidate.get("quote_volume"), candidate.get("volume_ratio"),
        candidate.get("rsi"), candidate.get("candles"), PALETTES["breakout"],
    ))
