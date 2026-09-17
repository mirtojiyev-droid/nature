"""
`places.py` + `facets.py`dagi (qidiruv uchun qisqa so'z) ma'lumotlarni AI video
generatsiyasi uchun BOY, tasviriy prompt matniga aylantiradi. Oddiy qidiruv so'zi
("Ha Long Bay Vietnam waterfall") AI videoga to'g'ridan-to'g'ri berilsa, natija
juda umumiy/tekis chiqadi — AI modellar kamera harakati, yorug'lik, kayfiyat kabi
SINEMATIK tafsilotlarga juda яxshi javob beradi."""
import random

CAMERA_STYLES = [
    "slow cinematic drone flyover",
    "smooth aerial tracking shot",
    "gentle push-in camera movement",
    "steady wide establishing shot",
    "slow motion close-up",
]
LIGHTING_MOODS = [
    "golden hour sunlight, warm glowing light",
    "soft morning mist, gentle diffused light",
    "dramatic sunset colors, orange and pink sky",
    "crisp clear daylight, vivid saturated colors",
    "blue hour twilight, soft cool tones",
]
QUALITY_SUFFIX = (
    "hyper-realistic, 4K nature documentary cinematography, highly detailed, "
    "no text, no watermark, no people"
)


def build_ai_prompt(place_name_en: str, facet_suffix: str) -> str:
    """`place_name_en` — inglizcha joy nomi (masalan places.py'dagi "query" maydoni),
    `facet_suffix` — facets.py'dagi qirra so'zi (masalan "waterfall", "sunset",
    bo'sh ham bo'lishi mumkin — umumiy manzara)."""
    subject = f"{place_name_en} {facet_suffix}".strip()
    camera = random.choice(CAMERA_STYLES)
    lighting = random.choice(LIGHTING_MOODS)
    return f"{camera} of {subject}, {lighting}, {QUALITY_SUFFIX}"


def build_filename(place_name_en: str, facet_label_en: str, provider: str) -> str:
    """localfootage/README.txt'da tushuntirilgan konventsiyaga mos, tavsiflovchi fayl
    nomi yasaydi (bot fayl nomidagi so'zlarni kunlik mavzu/qirra so'roviga solishtiradi)."""
    import re
    slug_parts = re.findall(r"[a-zA-Z0-9]+", f"{place_name_en} {facet_label_en}".lower())
    slug = "_".join(slug_parts) or "nature_clip"
    return f"{slug}_ai_{provider}.mp4"
