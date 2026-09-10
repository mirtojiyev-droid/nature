"""Postlar tagiga qo'shiladigan hashteglarni tayyorlash uchun umumiy yordamchi
funksiyalar — tabiat, kripto va futbol botlarining barchasi shu moduldan foydalanadi.
"""
import re


def slugify_hashtag(text: str) -> str:
    """Ixtiyoriy matnni (joy nomi, jamoa nomi va h.k.) hashteg sifatida ishlatsa
    bo'ladigan shaklga keltiradi: bo'shliq/tinish belgilarini olib tashlab, har bir
    so'zni CamelCase qilib birlashtiradi. Masalan "Angel Falls" -> "AngelFalls",
    "Manchester United" -> "ManchesterUnited". Hashteglarda bo'shliq yoki apostrof
    bo'lishi mumkin emas — Telegram ularni alohida (yarim) hashteg deb o'qiydi."""
    words = re.findall(r"[A-Za-z0-9]+", text.replace("'", ""))
    parts = [w[0].upper() + w[1:] if len(w) > 1 else w.upper() for w in words if w]
    return "".join(parts)


def format_hashtags(tags: list[str]) -> str:
    """Hashteg ro'yxatini takrorlarsiz (katta-kichik harfga qaramasdan), bo'sh
    bo'lmagan, "#" bilan boshlanadigan bitta qatorga aylantiradi."""
    seen = set()
    result = []
    for t in tags:
        if not t:
            continue
        t = t if t.startswith("#") else f"#{t}"
        if len(t) <= 1:
            continue
        key = t.lower()
        if key not in seen:
            seen.add(key)
            result.append(t)
    return " ".join(result)
