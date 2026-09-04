"""
Bitta kunlik mavzuning (joyning) turli "go'zal go'shalari" — kun davomida bir xil joy haqida
bir necha xil qirradan post qilish uchun. Har birida: caption'da ko'rinadigan o'zbekcha
yorliq, va Pexels qidiruviga qo'shiladigan inglizcha so'z (bo'sh bo'lsa, faqat joy nomining
o'zi bilan qidiriladi — "umumiy manzara").
"""

FACETS = [
    {"label": "umumiy manzarasi", "suffix": ""},
    {"label": "sharsharasi", "suffix": "waterfall"},
    {"label": "sohili", "suffix": "beach coast"},
    {"label": "tog' manzarasi", "suffix": "mountain peak"},
    {"label": "yovvoyi tabiati", "suffix": "wildlife animals"},
    {"label": "quyosh botishi", "suffix": "sunset"},
    {"label": "quyosh chiqishi", "suffix": "sunrise"},
    {"label": "havodan ko'rinishi", "suffix": "aerial drone view"},
    {"label": "o'rmoni", "suffix": "forest trees"},
    {"label": "ko'li yoki daryosi", "suffix": "lake river"},
    {"label": "vodiysi", "suffix": "valley landscape"},
    {"label": "tungi manzarasi", "suffix": "night stars"},
]


def build_query(base_place: str, facet: dict) -> str:
    """Joy nomi va qirra bo'yicha Pexels uchun qidiruv so'zini yasaydi."""
    if facet["suffix"]:
        return f"{base_place} {facet['suffix']}"
    return base_place


def build_query_variants(base_place: str, facet: dict) -> list[str]:
    """Eng mosdan eng umumiyga qarab qidiruv variantlari ro'yxatini qaytaradi.

    Wikipedia'dan topilgan joy nomlari ko'pincha juda spetsifik bo'ladi (masalan
    "Angel Falls"), va shu nom + qirra so'zi birga qidirilsa (masalan "Angel Falls
    waterfall sunset"), stock-video kutubxonalarida deyarli hech qachon aniq mos natija
    topilmaydi — video kutubxonalari rasm kutubxonalariga qaraganda ancha kichikroq.
    Shuning uchun, agar eng aniq variant natija bermasa, bosqichma-bosqich soddaroq
    (lekin baribir mavzuga yaqin) variantlarga o'tiladi, toki natija topilmaguncha."""
    variants = []
    if facet["suffix"]:
        variants.append(f"{base_place} {facet['suffix']}")
    variants.append(base_place)
    if facet["suffix"]:
        variants.append(facet["suffix"])
    variants.append("beautiful nature landscape")

    seen = set()
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique
