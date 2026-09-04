"""
Wikimedia Commons orqali qo'shimcha (uchinchi) bepul manba sifatida rasm va video qidiradi.
Commons — dunyodagi eng katta ochiq litsenziyali (Creative Commons / Public Domain) media
arxivi bo'lib, API kalit talab qilmaydi (butunlay bepul va ro'yxatdan o'tmasdan ishlatiladi).
Pexels/Pixabay'da topilmagan noyob joylar (masalan kamroq mashhur sharsharalar, milliy
bog'lar) ko'pincha aynan Commons'da topiladi, chunki u Wikipedia maqolalarida ishlatiladigan
millionlab faylni o'z ichiga oladi.

Muhim farq: Commons'dagi video fayllar ko'pincha VP9/webm yoki Theora/ogv formatida
bo'ladi (Pexels/Pixabay kabi to'g'ridan-to'g'ri H.264 mp4 emas) — shuning uchun bu yerdan
kelgan videolar main.py'da music_mixer.prepare_video_for_posting orqali har doim
Telegram-mos H.264 formatga qayta kodlanadi.
"""
import logging
import random

import requests

logger = logging.getLogger(__name__)

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"

# Wikimedia API'dan foydalanish odob-axloq qoidalariga ko'ra, so'rovlarda aniq
# User-Agent yuborish tavsiya etiladi (kim/nima so'rov yuborayotganini bildirish uchun).
HEADERS = {"User-Agent": "NatureChannelBot/1.0 (Telegram tabiat kanali uchun avtomatik bot)"}

# Juda kichik (eskiz/piktogramma) fayllarni chetlab o'tish uchun minimal o'lcham.
MIN_DIMENSION = 400
# Rasm fayli hajmi shu qiymatdan katta bo'lsa o'tkazib yuboriladi (Telegram rasm
# yuklash chegarasiga mos, xavfsizlik uchun ancha pastroq qilib qo'yilgan).
MAX_PHOTO_BYTES = 10 * 1024 * 1024
# Video fayli hajmi shu qiymatdan katta bo'lsa o'tkazib yuboriladi — juda katta original
# fayllarni yuklab olish/qayta kodlash vaqti va serverga ortiqcha yuk tushirmaslik uchun.
MAX_VIDEO_BYTES = 150 * 1024 * 1024


def _rank_and_pick(items: list, key_fn, top_n: int = 5):
    if not items:
        return None
    ranked = sorted(items, key=key_fn, reverse=True)
    top = ranked[: min(top_n, len(ranked))]
    return random.choice(top)


def _search_commons(query: str, filetype: str, limit: int = 20) -> list[dict]:
    """Commons'da fayl qidiradi. `filetype`: CirrusSearch'ning "filetype:" kalit so'zi
    uchun qiymat — rasm uchun "bitmap", video uchun "video"."""
    try:
        resp = requests.get(
            COMMONS_API_URL,
            headers=HEADERS,
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{query} filetype:{filetype}",
                "gsrnamespace": 6,  # 6 = File: nomlar maydoni
                "gsrlimit": limit,
                "prop": "imageinfo",
                "iiprop": "url|size|mime",
                "format": "json",
            },
            timeout=20,
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        return list(pages.values())
    except requests.RequestException as exc:
        logger.warning("Wikimedia Commons so'rovida xatolik (%s, %s): %s", query, filetype, exc)
        return []
    except ValueError:
        logger.warning("Wikimedia Commons javobini o'qib bo'lmadi (%s, %s)", query, filetype)
        return []


class WikimediaFetcher:
    """Pexels/PixabayFetcher bilan bir xil interfeys: fetch_photo(query, prefer_vertical),
    fetch_video(query, prefer_vertical). API kalit shart emas — doim faol manba sifatida
    ishlatilishi mumkin."""

    def fetch_photo(self, query: str, prefer_vertical: bool = True) -> str | None:
        pages = _search_commons(query, "bitmap")
        candidates = []
        for page in pages:
            info_list = page.get("imageinfo")
            if not info_list:
                continue
            info = info_list[0]
            mime = info.get("mime", "")
            width, height = info.get("width") or 0, info.get("height") or 0
            size = info.get("size") or 0
            url = info.get("url")
            if not url or mime == "image/svg+xml" or not mime.startswith("image/"):
                continue
            if width < MIN_DIMENSION or height < MIN_DIMENSION:
                continue
            if size and size > MAX_PHOTO_BYTES:
                continue
            is_vertical = height > width
            if is_vertical != prefer_vertical:
                continue
            candidates.append({"url": url, "score": width * height})

        chosen = _rank_and_pick(candidates, lambda c: c["score"])
        if not chosen:
            logger.info("Wikimedia Commons'da '%s' uchun mos rasm topilmadi", query)
            return None
        return chosen["url"]

    def fetch_video(self, query: str, prefer_vertical: bool = True) -> str | None:
        pages = _search_commons(query, "video")
        candidates = []
        for page in pages:
            info_list = page.get("imageinfo")
            if not info_list:
                continue
            info = info_list[0]
            mime = info.get("mime", "")
            width, height = info.get("width") or 0, info.get("height") or 0
            size = info.get("size") or 0
            url = info.get("url")
            if not url or not mime.startswith("video/"):
                continue
            if not width or not height:
                continue
            if size and size > MAX_VIDEO_BYTES:
                continue
            is_vertical = height > width
            if is_vertical != prefer_vertical:
                continue
            candidates.append({"url": url, "score": width * height})

        chosen = _rank_and_pick(candidates, lambda c: c["score"])
        if not chosen:
            logger.info(
                "Wikimedia Commons'da '%s' uchun %s formatdagi video topilmadi",
                query,
                "vertikal" if prefer_vertical else "gorizontal",
            )
            return None
        return chosen["url"]
