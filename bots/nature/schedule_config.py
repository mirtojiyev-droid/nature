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
    ("00:30", "general"),
    ("01:00", "night"),
    ("01:30", "general"),
    ("02:00", "night"),
    ("02:30", "night"),
    ("03:00", "wildlife"),
    ("03:30", "wildlife"),
    ("04:00", "lake"),
    ("04:30", "lake"),
    ("05:00", "lake"),
    ("05:30", "mountain"),
    ("06:00", "mountain"),
    ("06:30", "sunrise"),
    ("07:00", "sunrise"),
    ("07:30", "sunrise"),
    ("08:00", "wildlife"),
    ("08:30", "birds"),
    ("09:00", "beach"),
    ("09:30", "rain"),
    ("10:00", "beach"),
    ("10:30", "rain"),
    ("11:00", "mountain"),
    ("11:30", "mountain"),
    ("12:00", "forest"),
    ("12:30", "forest"),
    ("13:00", "aerial"),
    ("13:30", "aerial"),
    ("14:00", "mountain"),
    ("14:30", "mountain"),
    ("15:00", "mountain"),
    ("15:30", "autumn"),
    ("16:00", "birds"),
    ("16:30", "sunset"),
    ("17:00", "sunset"),
    ("17:30", "snow"),
    ("18:00", "sunset"),
    ("18:30", "sunset"),
    ("19:00", "flowers"),
    ("19:30", "flowers"),
    ("20:00", "rain"),
    ("20:30", "rain"),
    ("21:00", "snow"),
    ("21:30", "rain"),
    ("22:00", "aerial"),
    ("22:30", "aerial"),
    ("23:00", "aerial"),
    ("23:30", "rain"),
]
