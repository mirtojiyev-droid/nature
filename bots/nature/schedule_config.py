"""
Tabiat botining KUNLIK, kategoriya-vaqtga bog'langan jadvali — foydalanuvchi bilan
kelishilgan o'sish rejasi asosida ("har soatda 24 ta emas, kuniga 10-12 ta, har biri
aniq vaqtda va aniq kategoriyada"). Har bir yozuv: (soat:daqiqa, facet.py'dagi FACETS
ro'yxatining "key" maydoni).

Bu jadval FAQAT `NATURE_USE_DAILY_SCHEDULE=true` bo'lganda ishlatiladi (standart —
main.py'ga qarang). `false` qilib qo'ysangiz, bot eski usulda — `NATURE_INTERVAL_MINUTES`
oralig'ida, tasodifiy navbat bilan qirra tanlab — ishlashda davom etadi.

Vaqtni yoki kategoriyani o'zgartirish uchun shu ro'yxatni to'g'ridan-to'g'ri tahrirlang
— vaqtlar SERVERNING soat mintaqasiga (odatda UTC) nisbatan, mahalliy vaqt EMAS
ekanini unutmang (agar mahalliy vaqtga moslashtirmoqchi bo'lsangiz, har bir vaqtga
farqni qo'lda qo'shib/ayirib chiqing).
"""

NATURE_DAILY_SCHEDULE = [
    ("00:00", "general"),
    ("02:00", "night"),
    ("04:00", "lake"),
    ("06:00", "sunrise"),
    ("08:00", "wildlife"),
    ("10:00", "beach"),
    ("12:00", "forest"),
    ("14:00", "mountain"),
    ("16:00", "birds"),
    ("18:00", "sunset"),
    ("20:00", "rain"),
    ("22:00", "aerial"),
    ("22:25", "aerial"),
    ("22:30", "aerial"),
    ("22:35", "aerial"),
    ("22:40", "aerial"),
    ("22:45", "aerial"),
    ("22:50", "aerial"),
    ("22:55", "aerial"),
    ("23:00", "aerial"),
]
