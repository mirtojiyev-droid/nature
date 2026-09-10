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


def draw_pill(draw: ImageDraw.ImageDraw, xy: list[int], fill: str, outline: str | None = None, width: int = 0) -> None:
    """To'liq dumaloq uchli ("pill" shaklidagi) to'rtburchak — statuslar, belgilar
    (badge) uchun zamonaviy ko'rinish."""
    x0, y0, x1, y1 = xy
    radius = (y1 - y0) / 2
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
