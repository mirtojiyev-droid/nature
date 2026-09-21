"""
Tabiat botining KUNLIK, kategoriya-vaqtga bog'langan jadvali — foydalanuvchi bilan
kelishilgan o'sish rejasi asosida ("har soatda 24 ta emas, kuniga 10-12 ta, har biri
aniq vaqtda va aniq kategoriyada"). Har bir yozuv: (soat:daqiqa, facet.py'dagi FACETS
ro'yxatining "key" maydoni).

MUHIM: bu yerdagi vaqtlar — MAHALLIY (O'zbekiston) vaqtda yozilgan (shuning uchun
18:00 = kechqurun, dengiz/yomg'ir kabi tinchlantiruvchi kontent uchun to'g'ri vaqt).
Serverning o'zi odatda UTC soatida ishlaydi — bu farqni `main.py` avtomatik
(`NATURE_TZ_OFFSET_HOURS`, standart 5 — O'zbekiston UTC+5) hisobga oladi, shuning
uchun bu yerda hech narsani UTC'ga o'zingiz o'girishingiz shart emas — shunchaki
xohlagan MAHALLIY vaqtingizni yozing.

Bu jadval FAQAT `NATURE_USE_DAILY_SCHEDULE=true` bo'lganda ishlatiladi (standart —
main.py'ga qarang). `false` qilib qo'ysangiz, bot eski usulda — `NATURE_INTERVAL_MINUTES`
oralig'ida, tasodifiy navbat bilan qirra tanlab — ishlashda davom etadi.
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
]
