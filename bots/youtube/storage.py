"""
Oddiy JSON-fayl asosidagi "qayta joylamaslik" (dedupe) xotirasi.
"""
import json
import os
from datetime import datetime, timezone


def load_posted(log_file: str) -> dict:
    if not os.path.exists(log_file):
        return {}
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def load_posted_ids(log_file: str) -> set:
    """Faqat ID'lar to'plamini qaytaradi — bir ishga tushirish davomida
    ko'plab nomzodni tekshirish kerak bo'lganda (masalan har bir nomzod
    uchun is_posted() chaqirish o'rniga), buni bir marta yuklab, natijani
    o'zingiz saqlab, shu to'plam ichida tekshirish ancha tezroq: har bir
    tekshiruv uchun butun faylni qayta o'qib, qayta JSON-parse qilishning
    hojati qolmaydi (posted.json vaqt o'tishi bilan kattalashgani sayin
    bu farq sezilarli bo'ladi)."""
    return set(load_posted(log_file).keys())


def is_posted(log_file: str, video_id: str) -> bool:
    """Bitta video uchun tekshiruv — har chaqiruvda faylni qayta o'qiydi.
    Bir nechta videoni ketma-ket tekshirish kerak bo'lsa (masalan
    main.py'ning asosiy tsiklida), buning o'rniga load_posted_ids()'ni
    bir marta chaqirib, natijadagi to'plam ichida `video_id in ids`
    tekshiring — bu ancha tezroq."""
    return video_id in load_posted(log_file)


def mark_posted(log_file: str, video_id: str, meta: dict) -> None:
    data = load_posted(log_file)
    data[video_id] = {
        **meta,
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
