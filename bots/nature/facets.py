"""
Bitta (4 soatlik oynadagi) mavzuning (joyning) turli "go'zal go'shalari" — oyna davomida
bir xil joy haqida bir necha xil qirradan post qilish uchun. Har birida: caption'da ko'rinadigan o'zbekcha
yorliq, va Pexels qidiruviga qo'shiladigan inglizcha so'z (bo'sh bo'lsa, faqat joy nomining
o'zi bilan qidiriladi — "umumiy manzara").
"""

FACETS = [
    {"label": "umumiy manzarasi", "suffix": "", "hashtags": ["sayohat", "travel"]},
    {"label": "sharsharasi", "suffix": "waterfall", "hashtags": ["sharshara", "waterfall"]},
    {"label": "sohili", "suffix": "beach coast", "hashtags": ["plyaj", "beach"]},
    {"label": "tog' manzarasi", "suffix": "mountain peak", "hashtags": ["toglar", "mountains"]},
    {"label": "yovvoyi tabiati", "suffix": "wildlife animals", "hashtags": ["hayvonotolami", "wildlife"]},
    {"label": "quyosh botishi", "suffix": "sunset", "hashtags": ["quyoshbotishi", "sunset"]},
    {"label": "quyosh chiqishi", "suffix": "sunrise", "hashtags": ["quyoshchiqishi", "sunrise"]},
    {"label": "havodan ko'rinishi", "suffix": "aerial drone view", "hashtags": ["dronvideo", "aerial"]},
    {"label": "o'rmoni", "suffix": "forest trees", "hashtags": ["ormon", "forest"]},
    {"label": "ko'li yoki daryosi", "suffix": "lake river", "hashtags": ["kol", "river"]},
    {"label": "vodiysi", "suffix": "valley landscape", "hashtags": ["vodiy", "valley"]},
    {"label": "tungi manzarasi", "suffix": "night stars", "hashtags": ["tungisman", "stars"]},
]

# Kanalning "asosiy", eng mashhur/umumiy hashteglari — mavzu/qirradan qat'i nazar HAR
# doim qo'shiladi (kanal nomiga/mavzusiga moslab: tabiat/sayohat kanali).
CHANNEL_HASHTAGS = ["tabiat", "nature"]


def build_query(base_place: str, facet: dict) -> str:
    """Joy nomi va qirra bo'yicha Pexels uchun qidiruv so'zini yasaydi."""
    if facet["suffix"]:
        return f"{base_place} {facet['suffix']}"
    return base_place


def build_hashtags(theme: str, facet: dict) -> list[str]:
    """Post tagiga qo'shiladigan hashteglar ro'yxatini tayyorlaydi: kanalning umumiy
    (eng mashhur/mavzuga mos) hashteglari + shu joyga xos hashteg + shu qirraga xos
    hashteg(lar) — kamida 4 tadan iborat bo'ladi."""
    from shared.hashtags import slugify_hashtag

    tags = list(CHANNEL_HASHTAGS)
    place_tag = slugify_hashtag(theme)
    if place_tag:
        tags.append(place_tag)
    tags.extend(facet.get("hashtags", []))
    return tags


def build_query_variants(base_place: str, facet: dict) -> list[str]:
    """Eng mosdan eng umumiyga qarab qidiruv variantlari ro'yxatini qaytaradi.

    Wikipedia'dan topilgan joy nomlari ko'pincha juda spetsifik bo'ladi (masalan
    "Angel Falls"), va shu nom + qirra so'zi birga qidirilsa (masalan "Angel Falls
    waterfall sunset"), stock-video kutubxonalarida deyarli hech qachon aniq mos natija
    topilmaydi — video kutubxonalari rasm kutubxonalariga qaraganda ancha kichikroq.
    Shuning uchun, agar eng aniq variant natija bermasa, bosqichma-bosqich soddaroq
    (lekin baribir mavzuga yaqin) variantlarga o'tiladi, toki natija topilmaguncha.

    MUHIM: bu yerda ataylab umuman mavzuga bog'liq bo'lmagan ("beautiful nature
    landscape" kabi) so'rov QO'SHILMAYDI. Avvalgi versiyada shunday umumiy so'rov oxirgi
    zaxira sifatida bor edi — natijada hech qanday variant topilmasa, bot mavzuga
    aloqasi yo'q tasodifiy tabiat videosini topib, "moslashtirib" nashr qilib yuborardi.
    Endi eng oxirgi variant ham hali mavzu bilan bog'liq (kamida qirra so'zi orqali);
    shu ham topilmasa, main.py o'sha safar postni butunlay o'tkazib yuboradi — bu
    mavzuga mos kelmaydigan kontent joylashdan ancha yaxshi."""
    variants = []
    if facet["suffix"]:
        variants.append(f"{base_place} {facet['suffix']}")
    variants.append(base_place)
    if facet["suffix"]:
        variants.append(facet["suffix"])

    seen = set()
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique
