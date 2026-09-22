"""
Wikimedia Commons orqali qo'shimcha (uchinchi) bepul manba sifatida rasm va video qidiradi.
Commons — dunyodagi eng katta ochiq litsenziyali (Creative Commons / Public Domain) media
arxivi bo'lib, API kalit talab qilmaydi (butunlay bepul va ro'yxatdan o'tmasdan ishlatiladi).
Pixabay'da topilmagan noyob joylar (masalan kamroq mashhur sharsharalar, milliy
bog'lar) ko'pincha aynan Commons'da topiladi, chunki u Wikipedia maqolalarida ishlatiladigan
millionlab faylni o'z ichiga oladi.

Muhim farq: Commons'dagi video fayllar ko'pincha VP9/webm yoki Theora/ogv formatida
bo'ladi (Pixabay kabi to'g'ridan-to'g'ri H.264 mp4 emas) — shuning uchun bu yerdan
kelgan videolar main.py'da music_mixer.prepare_video_for_posting orqali har doim
Telegram-mos H.264 formatga qayta kodlanadi.
"""
import logging
import random

import requests

from .config import allow_orientation_fallback
from .quality import max_video_dimension

logger = logging.getLogger(__name__)

COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php"

# Wikimedia API'dan foydalanish odob-axloq qoidalariga ko'ra, so'rovlarda aniq
# User-Agent yuborish tavsiya etiladi (kim/nima so'rov yuborayotganini bildirish uchun).
HEADERS = {"User-Agent": "NatureChannelBot/1.0 (Telegram tabiat kanali uchun avtomatik bot)"}

# Rasm/video qabul qilinishi uchun minimal o'lcham (piksel, qisqa tomon). Avval 400px
# edi — bu deyarli eskiz/piktogramma darajasi va past sifatli natijalarga yo'l ochardi.
# Commons — juda katta arxiv bo'lgani uchun, ancha yuqori chegara qo'yish (natijalar
# kamayishiga qaramay) sifatni kafolatlash uchun arzon.
MIN_DIMENSION = 1600  # rasm uchun
MIN_VIDEO_DIMENSION = 1080  # video uchun (qisqa tomon, taxminan 1080p)
# Video uchun yuqori chegara ham — standart 4K, .env orqali pasaytiriladi
# (bots/nature/quality.py'ga qarang). Bundan kattaroq (masalan 8K original skan)
# fayllar hech qachon tanlanmaydi, ular Telegram yuklash/qayta kodlash uchun amaliy emas.
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


def _orientation_sort_key(is_vertical: bool, prefer_vertical: bool):
    """pixabay_fetcher.py'dagi bir xil nomdagi funksiyaga qarang."""
    return 0 if is_vertical == prefer_vertical else 1


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
    """PixabayFetcher bilan bir xil interfeys: fetch_photo(query, prefer_vertical),
    fetch_video(query, prefer_vertical). API kalit shart emas — doim faol manba sifatida
    ishlatilishi mumkin."""

    def _find_matching_photos(self, query: str, prefer_vertical: bool, min_dimension: int) -> list[dict]:
        """Ichki yordamchi — `fetch_photo` va `fetch_photo_candidates` uchun umumiy."""
        allow_fallback = allow_orientation_fallback()
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
            if width < min_dimension or height < min_dimension:
                continue
            if size and size > MAX_PHOTO_BYTES:
                continue
            is_vertical = height > width
            if is_vertical != prefer_vertical and not allow_fallback:
                continue
            candidates.append({"url": url, "score": width * height, "is_vertical": is_vertical})
        return sorted(
            candidates,
            key=lambda c: (_orientation_sort_key(c["is_vertical"], prefer_vertical), -c["score"]),
        )

    def fetch_photo(self, query: str, prefer_vertical: bool = True, min_dimension: int = MIN_DIMENSION) -> str | None:
        candidates = self._find_matching_photos(query, prefer_vertical, min_dimension)
        chosen = _rank_and_pick(candidates[:5], lambda c: c["score"])
        if not chosen:
            logger.info("Wikimedia Commons'da '%s' uchun mos rasm topilmadi", query)
            return None
        return chosen["url"]

    def fetch_photo_candidates(self, query: str, prefer_vertical: bool = True, max_results: int = 4,
                                min_dimension: int = MIN_DIMENSION) -> list[dict]:
        """Bir nechta nomzod ma'lumotini qaytaradi (pixabay_fetcher.py'dagi bir xil
        nomdagi metodga qarang). Commons'da har bir fayl uchun BITTA (rendition'siz)
        URL bor, shuning uchun `id` sifatida to'g'ridan-to'g'ri URL'ning o'zi
        ishlatiladi - baribir doimiy/o'zgarmas."""
        candidates = self._find_matching_photos(query, prefer_vertical, min_dimension)
        return [{"url": c["url"], "id": c["url"]} for c in candidates[:max_results]]

    def _find_matching_video_candidates(self, query: str, prefer_vertical: bool, min_dimension: int) -> list[dict]:
        """Ichki yordamchi — `fetch_video` va `fetch_video_candidates` uchun umumiy
        (pixabay_fetcher.py'dagi bir xil naqshga qarang)."""
        allow_fallback = allow_orientation_fallback()
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
            if min(width, height) < min_dimension:
                continue  # past sifatli video — chetlab o'tiladi
            if max(width, height) > max_video_dimension():
                continue  # amaliy emas (8K va undan katta) — chetlab o'tiladi
            if size and size > MAX_VIDEO_BYTES:
                continue
            is_vertical = height > width
            if is_vertical != prefer_vertical and not allow_fallback:
                continue
            candidates.append({"url": url, "score": width * height, "is_vertical": is_vertical})
        return sorted(
            candidates,
            key=lambda c: (_orientation_sort_key(c["is_vertical"], prefer_vertical), -c["score"]),
        )

    def fetch_video(self, query: str, prefer_vertical: bool = True, min_dimension: int = MIN_VIDEO_DIMENSION) -> str | None:
        candidates = self._find_matching_video_candidates(query, prefer_vertical, min_dimension)
        chosen = _rank_and_pick(candidates[:5], lambda c: c["score"])
        if not chosen:
            logger.info(
                "Wikimedia Commons'da '%s' uchun video topilmadi",
                query,
            )
            return None
        return chosen["url"]

    def fetch_video_candidates(self, query: str, prefer_vertical: bool = True, max_results: int = 4,
                                min_dimension: int = MIN_VIDEO_DIMENSION) -> list[dict]:
        """Bir nechta nomzod ma'lumotini (eng yaxshisidan boshlab, har biri
        {"url", "width", "height", "is_vertical"}) qaytaradi — pixabay_fetcher.py'dagi
        bir xil nomdagi metodga qarang (foydalanish sababi)."""
        candidates = self._find_matching_video_candidates(query, prefer_vertical, min_dimension)
        return [
            {"url": c["url"], "is_vertical": c["is_vertical"], "score": c["score"], "id": c["url"]}
            for c in candidates[:max_results]
        ]

