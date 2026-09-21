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
    ("00:00", "night"),
    ("00:30", "lake"),
    ("01:00", "valley"),
    ("01:30", "general"),
    ("02:00", "forest"),
    ("02:30", "mountain"),
    ("03:00", "night"),
    ("03:30", "waterfall"),
    ("04:00", "lake"),
    ("04:30", "general"),
    ("05:00", "forest"),
    ("05:30", "sunrise"),
    ("06:00", "birds"),
    ("06:30", "mountain"),
    ("07:00", "wildlife"),
    ("07:30", "general"),
    ("08:00", "forest"),
    ("08:30", "aerial"),
    ("09:00", "beach"),
    ("09:30", "waterfall"),
    ("10:00", "valley"),
    ("10:30", "wildlife"),
    ("11:00", "mountain"),
    ("11:30", "general"),
    ("12:00", "forest"),
    ("12:30", "beach"),
    ("13:00", "aerial"),
    ("13:30", "lake"),
    ("14:00", "mountain"),
    ("14:30", "wildlife"),
    ("15:00", "valley"),
    ("15:30", "beach"),
    ("16:00", "birds"),
    ("16:30", "aerial"),
    ("17:00", "forest"),
    ("17:30", "general"),
    ("18:00", "mountain"),
    ("18:30", "sunset"),
    ("19:00", "waterfall"),
    ("19:30", "beach"),
    ("20:00", "rain"),
    ("20:30", "general"),
    ("21:00", "aerial"),
    ("21:30", "wildlife"),
    ("22:00", "night"),
    ("22:30", "lake"),
    ("23:00", "rain"),
    ("23:30", "valley"),
]
