"""
Bitta (4 soatlik oynadagi) mavzuning (joyning) turli "go'zal go'shalari" — oyna davomida
bir xil joy haqida bir necha xil qirradan post qilish uchun. Har birida: caption'da
KO'RINMAYDIGAN (faqat Pixabay qidiruvi uchun ishlatiladigan) inglizcha so'z, va
shu qirraga xos, qidiruvda kuchli hashteglar ro'yxati.

MUHIM (foydalanuvchi so'rovi bilan o'zgartirilgan): avval caption'da qirra nomi ham
ko'rinardi ("🌍 Joy nomi — sharsharasi" kabi). Endi caption FAQAT joy nomidan iborat —
qirra hech qanday izoh/matn sifatida ko'rinmaydi, faqat (1) qidiruv so'zini tanlashda va
(2) hashteg ro'yxatini boyitishda ICHKI ravishda ishlatiladi.
"""

FACETS = [
    {"key": "general", "label": "umumiy manzarasi", "suffix": "",
     "hashtags": ["sayohat", "travel"]},
    {"key": "waterfall", "label": "sharsharasi", "suffix": "waterfall",
     "hashtags": ["sharshara", "waterfall"]},
    {"key": "beach", "label": "sohili", "suffix": "beach coast",
     "hashtags": ["plyaj", "beach"]},
    {"key": "mountain", "label": "tog' manzarasi", "suffix": "mountain peak",
     "hashtags": ["toglar", "mountains"]},
    {"key": "wildlife", "label": "yovvoyi tabiati", "suffix": "wildlife animals",
     "hashtags": ["hayvonotolami", "wildlife"]},
    {"key": "sunset", "label": "quyosh botishi", "suffix": "sunset",
     "hashtags": ["quyoshbotishi", "sunset"]},
    {"key": "sunrise", "label": "quyosh chiqishi", "suffix": "sunrise",
     "hashtags": ["quyoshchiqishi", "sunrise"]},
    {"key": "aerial", "label": "havodan ko'rinishi", "suffix": "aerial drone view",
     "hashtags": ["dronvideo", "aerial"]},
    {"key": "forest", "label": "o'rmoni", "suffix": "forest trees",
     "hashtags": ["ormon", "forest"]},
    {"key": "lake", "label": "ko'li yoki daryosi", "suffix": "lake river",
     "hashtags": ["kol", "river"]},
    {"key": "valley", "label": "vodiysi", "suffix": "valley landscape",
     "hashtags": ["vodiy", "valley"]},
    {"key": "night", "label": "tungi manzarasi", "suffix": "night stars",
     "hashtags": ["tungisman", "stars"]},
    {"key": "birds", "label": "qushlari", "suffix": "birds flying",
     "hashtags": ["qushlar", "birds"]},
    {"key": "rain", "label": "yomg'iri", "suffix": "rain",
     "hashtags": ["yomgir", "rain"]},
]

FACETS_BY_KEY = {f["key"]: f for f in FACETS}

# Kanalning hashteglari — HAR doim shu ikkitasi + joy nomi qo'shiladi (jami 3 ta).
# MUHIM (foydalanuvchi qarori bilan yanada soddalashtirilgan): avval bu yerga qirraga
# xos hashteg(lar) ham (masalan "river", "sunset") qo'shilardi — lekin foydalanuvchi
# buni caption/overlay'dagi "qoldiq izoh" sifatida qabul qildi (garchi caption va
# video/rasm overlay'ining o'zi allaqachon FAQAT joy nomidan iborat bo'lsa-da — hashteg
# orqali qirra turi "sizib chiqib" ketardi). Endi hashteglar FAQAT umumiy (#Nature,
# #naturephotography) + joy nomidan iborat — hech qanday tur/kategoriya oshkor
# qilinmaydi.
CHANNEL_HASHTAGS = ["Nature", "naturephotography"]


def build_query(base_place: str, facet: dict) -> str:
    """Joy nomi va qirra bo'yicha Pixabay uchun qidiruv so'zini yasaydi."""
    if facet["suffix"]:
        return f"{base_place} {facet['suffix']}"
    return base_place


def build_hashtags(theme: str, facet: dict) -> list[str]:
    """Post tagiga qo'shiladigan hashteglar ro'yxatini tayyorlaydi.

    MUHIM (foydalanuvchi qarori — yakuniy o'zgartirish): avval bu yerga joy nomi
    ham hashteg sifatida qo'shilardi (masalan #IndusValley). Lekin foydalanuvchi
    aynan bir xil rasm/video Wikipedia'dan olingan turli (ba'zan noto'g'ri yoki
    bir-biriga mos kelmaydigan) joy nomlari bilan bir necha marta chiqayotganini
    aniqladi — bu ishonchsizlik uyg'otardi. Qaror: hozircha ANIQ joy nomi
    caption'da HAM, hashteg'da HAM umuman ko'rsatilmaydi (build_caption'ga
    qarang, endi faqat kanal nomi/belgisi chiqadi) — FAQAT kanalning umumiy
    hashteglari qoladi. `theme`/`facet` parametrlari kelajakda qayta yoqilishi
    mumkinligi uchun saqlab qo'yilgan (signature buzilmasin deb), hozircha
    ishlatilmaydi."""
    return list(CHANNEL_HASHTAGS)


def build_query_variants(base_place: str, facet: dict, fallback_category: str | None = None) -> list[str]:
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

    `fallback_category` — MUHIM (haqiqiy voqeada aniqlangan muammo tuzatildi):
    "umumiy manzarasi" qirrasi (bo'sh suffix) uchun avval FAQAT xom joy nomining o'zi
    qidirilardi (masalan noyob "Khentii Mountains") — bunday noyob nomlar bilan
    Pixabay'da deyarli HECH QACHON video topilmasdi (kutubxona juda kichik). Endi
    topics.py bu joy Wikipedia'da QAYSI KATEGORIYADAN (masalan "mountain range")
    topilganini biladi va shu yerga uzatadi — bu haligacha TEMATIK JIHATDAN TO'G'RI
    (haqiqatan ham o'sha joy haqida), umuman aloqasiz umumiy so'z emas."""
    variants = []
    if facet["suffix"]:
        variants.append(f"{base_place} {facet['suffix']}")
    variants.append(base_place)
    if facet["suffix"]:
        variants.append(facet["suffix"])
    elif fallback_category:
        variants.append(fallback_category)

    seen = set()
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique
