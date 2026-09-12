"""Pillow bilan zamonaviy, "fintech ilova"ga o'xshash karta dizaynlari chizish uchun
umumiy yordamchi funksiyalar (gradient fon, yumshoq soya) — kripto va futbol
botlarining ikkalasi ham shundan foydalanadi, dizayn bir xil sifat darajasida bo'lishi
uchun."""
from PIL import Image, ImageDraw, ImageFilter


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def vertical_gradient(size: tuple[int, int], top_color: str, bottom_color: str) -> Image.Image:
    """Yuqoridan pastga silliq rang o'tishi (gradient) — tekis rangdan ancha "jonli"
    va zamonaviy ko'rinadi."""
    width, height = size
    top = hex_to_rgb(top_color)
    bottom = hex_to_rgb(bottom_color)
    column = Image.new("RGB", (1, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        column.putpixel((0, y), (
            round(top[0] + (bottom[0] - top[0]) * t),
            round(top[1] + (bottom[1] - top[1]) * t),
            round(top[2] + (bottom[2] - top[2]) * t),
        ))
    return column.resize((width, height))


def diagonal_gradient(size: tuple[int, int], top_left: str, bottom_right: str) -> Image.Image:
    """Diagonal (chapdan-yuqoridan o'ngga-pastga) rang o'tishi — vertikaldan ko'ra
    biroz dinamikroq ko'rinish beradi, karta fonlari uchun ishlatiladi."""
    width, height = size
    tl = hex_to_rgb(top_left)
    br = hex_to_rgb(bottom_right)
    img = Image.new("RGB", size)
    px = img.load()
    max_d = (width - 1) + (height - 1)
    for y in range(height):
        for x in range(0, width, 2):  # 2px qadam bilan — 2x tezroq, sifatga деyarli ta'sir qilmaydi
            t = (x + y) / max_d
            color = (
                round(tl[0] + (br[0] - tl[0]) * t),
                round(tl[1] + (br[1] - tl[1]) * t),
                round(tl[2] + (br[2] - tl[2]) * t),
            )
            px[x, y] = color
            if x + 1 < width:
                px[x + 1, y] = color
    return img


def paste_soft_shadow(base: Image.Image, xy: list[int], radius: int, color: str = "#000000",
                       opacity: int = 110, offset: tuple[int, int] = (0, 10), blur: int = 22) -> None:
    """`base` (RGBA rasm) ustiga, `xy` to'rtburchagi ostiga yumshoq, xiralashgan soya
    chizadi — kartalarga "havoda suzib turgan" chuqurlik hissi beradi. Soya chizilgach,
    haqiqiy to'rtburchak (fill bilan) shundan KEYIN chizilishi kerak (shadow pastda,
    karta ustida qolishi uchun)."""
    x0, y0, x1, y1 = xy
    ox, oy = offset
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle([x0 + ox, y0 + oy, x1 + ox, y1 + oy], radius=radius, fill=(*hex_to_rgb(color), opacity))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(shadow)


def draw_soft_glow_circle(base: Image.Image, cx: int, cy: int, radius: int, color: str,
                           opacity: int = 90, blur: int = 30) -> None:
    """Doira atrofida yumshoq "porlash" (glow) effekti — masalan gerb/rank belgisi
    orqasida, e'tiborni tortadigan urg'u sifatida."""
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(*hex_to_rgb(color), opacity))
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(glow)


def draw_soft_glow_rect(base: Image.Image, xy: list[int], color: str,
                         opacity: int = 110, blur: int = 36) -> None:
    """To'rtburchak (masalan katta "hero" raqam yoki status belgisi) atrofida
    yumshoq porlash — "neon" uslubidagi kartalarga xos, e'tiborni birinchi
    navbatda eng muhim raqamga (masalan foiz o'zgarishi) tortish uchun."""
    x0, y0, x1, y1 = xy
    glow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) / 3, fill=(*hex_to_rgb(color), opacity))
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    base.alpha_composite(glow)


def draw_triangle(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: str, pointing: str = "up") -> None:
    """Oddiy uchburchak (yuqoriga/pastga qaragan o'q) — DejaVu Sans shriftida emoji
    (▲/▼/⚽ va h.k.) yo'qligi sababli, bunday belgilarni HAR DOIM shrift bilan emas,
    to'g'ridan-to'g'ri chizib beramiz — shunda barcha muhitda bir xil, aniq ko'rinadi."""
    h = size
    w = size * 0.9
    if pointing == "up":
        points = [(cx, cy - h / 2), (cx - w / 2, cy + h / 2), (cx + w / 2, cy + h / 2)]
    else:
        points = [(cx, cy + h / 2), (cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2)]
    draw.polygon(points, fill=color)


def draw_candlestick_chart(draw: ImageDraw.ImageDraw, xy: list[int], candles: list[dict],
                            up_color: str = "#22E37E", down_color: str = "#FF4D6D",
                            wick_width: int = 2) -> None:
    """Yaponcha shamlar (candlestick) grafikasi — berilgan to'rtburchak ichiga,
    `candles` ro'yxatidagi (eng eskisidan eng yangisiga) har bir {"open","high",
    "low","close"} nuqtasi uchun bitta sham chizadi. Narx o'sgan bo'lsa (close >=
    open) yashil, tushgan bo'lsa qizil — klassik konventsiya."""
    if not candles:
        return
    x0, y0, x1, y1 = xy
    width, height = x1 - x0, y1 - y0
    n = len(candles)

    all_highs = [c["high"] for c in candles]
    all_lows = [c["low"] for c in candles]
    price_max, price_min = max(all_highs), min(all_lows)
    price_range = price_max - price_min or 1.0

    def y_for(price: float) -> float:
        return y1 - (price - price_min) / price_range * height

    slot_w = width / n
    body_w = max(slot_w * 0.55, 1.5)

    for i, c in enumerate(candles):
        cx = x0 + slot_w * (i + 0.5)
        is_up = c["close"] >= c["open"]
        color = up_color if is_up else down_color

        wick_top, wick_bottom = y_for(c["high"]), y_for(c["low"])
        draw.line([cx, wick_top, cx, wick_bottom], fill=color, width=wick_width)

        body_top = y_for(max(c["open"], c["close"]))
        body_bottom = y_for(min(c["open"], c["close"]))
        if body_bottom - body_top < 2:  # deyarli o'zgarishsiz sham - ozgina qalinlik beramiz, ko'rinmas bo'lib qolmasin
            body_bottom = body_top + 2
        draw.rectangle([cx - body_w / 2, body_top, cx + body_w / 2, body_bottom], fill=color)


def draw_pill(draw: ImageDraw.ImageDraw, xy: list[int], fill: str, outline: str | None = None, width: int = 0) -> None:
    """To'liq dumaloq uchli ("pill" shaklidagi) to'rtburchak — statuslar, belgilar
    (badge) uchun zamonaviy ko'rinish."""
    x0, y0, x1, y1 = xy
    radius = (y1 - y0) / 2
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


# RSI gauge (speedometer) uchun rang shkalasi: past (0) - qizil, o'rta (50) - sariq,
# yuqori (100) - yashil. Bu klassik "bozor holati" gauge'iga o'xshash, tushunarli.
_GAUGE_STOPS = [(0.0, "#FF4D6D"), (0.5, "#FFC94D"), (1.0, "#22E37E")]


def _gauge_color_at(t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    for i in range(len(_GAUGE_STOPS) - 1):
        t0, c0 = _GAUGE_STOPS[i]
        t1, c1 = _GAUGE_STOPS[i + 1]
        if t0 <= t <= t1:
            local_t = (t - t0) / (t1 - t0) if t1 > t0 else 0
            rgb0, rgb1 = hex_to_rgb(c0), hex_to_rgb(c1)
            return tuple(round(rgb0[i] + (rgb1[i] - rgb0[i]) * local_t) for i in range(3))
    return hex_to_rgb(_GAUGE_STOPS[-1][1])


def draw_gauge(draw: ImageDraw.ImageDraw, cx: int, cy: int, radius: int, value: float,
               thickness: int = 20, label: str | None = None, value_font=None, label_font=None) -> None:
    """0-100 oralig'idagi qiymatni (masalan RSI) yarim-doira "spidometr" shaklida,
    qizil-sariq-yashil rang shkalasi va ko'rsatkich (strelka/igna) bilan chizadi.
    PIL'ning `arc()` funksiyasida 180->360 gradus TEPA yarim doirani beradi (chapda
    180=0-qiymat, o'ngda 360/0=100-qiymat) — aynan spidometrga kerakli shakl."""
    segments = 60
    for i in range(segments):
        t0, t1 = i / segments, (i + 1) / segments
        angle0 = 180 + t0 * 180
        angle1 = 180 + t1 * 180
        color = _gauge_color_at((t0 + t1) / 2)
        draw.arc([cx - radius, cy - radius, cx + radius, cy + radius], angle0, angle1, fill=color, width=thickness)

    # Ko'rsatkich (strelka) — qiymatga mos burchakda, markazdan tashqariga qarab
    import math
    value_t = max(0.0, min(100.0, value)) / 100.0
    needle_angle = math.radians(180 + value_t * 180)
    needle_len = radius - thickness / 2 - 4
    nx = cx + needle_len * math.cos(needle_angle)
    ny = cy + needle_len * math.sin(needle_angle)
    draw.line([cx, cy, nx, ny], fill="#FFFFFF", width=7)
    pivot_r = 11
    draw.ellipse([cx - pivot_r, cy - pivot_r, cx + pivot_r, cy + pivot_r], fill="#FFFFFF")

    if label and value_font:
        draw.text((cx, cy + radius * 0.32), f"{value:.0f}", font=value_font, fill="#FFFFFF", anchor="mm")
    if label and label_font:
        draw.text((cx, cy + radius * 0.32 + 40), label, font=label_font, fill="#C7CDDB", anchor="mm")
