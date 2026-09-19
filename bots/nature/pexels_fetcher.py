"""
Pexels API orqali berilgan query bo'yicha tabiat rasm yoki videosini topib beradi.

MUHIM (foydalanuvchi so'rovi bilan QAYTA qo'shildi): avval Pexels butunlay olib
tashlangan edi (Pixabay foydalanuvchi solishtirishida ko'proq yoqqani uchun). Keyinroq
foydalanuvchi Pexels'dagi videolar ham chiroyli chiqayotganini va Pixabay ba'zan
(ayniqsa noyob/kam qidiriladigan joy nomlari uchun) yetarli natija bermayotganini
payqadi. Shuning uchun Pexels endi QO'SHIMCHA (ikkinchi, Pixabay'dan KEYIN sinaladigan)
manba sifatida qaytarildi — bu ikkalasining kuchli tomonlaridan (Pixabay'ning
foydalanuvchi ma'qullagan vizual uslubi + Pexels'ning kengroq kutubxonasi va haqiqiy
4K video imkoniyati) birga foydalanish imkonini beradi.

Bepul API kalit: https://www.pexels.com/api/ (ro'yxatdan o'tib olinadi, ixtiyoriy —
sozlanmasa, bot shunchaki Pexels'ni chetlab o'tib, Pixabay+Wikimedia bilan davom etadi).
"""
import logging

import requests

from .config import allow_orientation_fallback
from .quality import max_video_dimension

logger = logging.getLogger(__name__)

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
MIN_VIDEO_DIMENSION = 1080  # zaxira standart (min_dimension berilmasa)
MIN_PHOTO_DIMENSION = 1600


def _orientation_sort_key(is_vertical: bool, prefer_vertical: bool):
    """pixabay_fetcher.py'dagi bir xil nomdagi funksiyaga qarang: afzal
    orientatsiyani oldinga chiqaradi, qarshisini (butunlay chetlamasdan) orqaga
    suradi."""
    return 0 if is_vertical == prefer_vertical else 1


class PexelsFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._headers = {"Authorization": api_key}

    def _find_matching_video_files(self, query: str, prefer_vertical: bool, min_dimension: int) -> list[dict]:
        """MUHIM (universal sozlash uchun o'zgartirildi): avval `orientation`
        so'rov parametri ("portrait"/"landscape") orqali FAQAT bitta format
        so'ralardi. Endi bu parametr yuborilmaydi (Pexels ikkala formatni ham
        aralash qaytaradi) va natijalar Python tomonida saralanadi — afzal
        format oldinda, qarshi format (agar NATURE_ALLOW_ORIENTATION_FALLBACK
        yoqilgan bo'lsa) zaxira sifatida ro'yxat oxirida."""
        try:
            resp = requests.get(
                PEXELS_VIDEO_URL,
                params={"query": query, "per_page": 15},
                headers=self._headers, timeout=20,
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
        except requests.RequestException as exc:
            logger.warning("Pexels video so'rovida xatolik (%s): %s", query, exc)
            return []

        matching = []
        max_dim = max_video_dimension()
        allow_fallback = allow_orientation_fallback()
        for video in videos:
            best_file = None
            for vf in video.get("video_files", []):
                w, h = vf.get("width") or 0, vf.get("height") or 0
                if not w or not h:
                    continue
                if min(w, h) < min_dimension or max(w, h) > max_dim:
                    continue
                is_vertical = h > w
                if is_vertical != prefer_vertical and not allow_fallback:
                    continue
                if best_file is None or w * h > best_file["width"] * best_file["height"]:
                    best_file = {"url": vf["link"], "width": w, "height": h, "is_vertical": is_vertical}
            if best_file:
                matching.append(best_file)

        if not matching:
            logger.info(
                "Pexels'da '%s' uchun %dp+ sifatli video topilmadi",
                query, min_dimension,
            )
        return sorted(
            matching,
            key=lambda f: (_orientation_sort_key(f["is_vertical"], prefer_vertical), -(f["width"] * f["height"])),
        )

    def fetch_video_candidates(self, query: str, prefer_vertical: bool = True, max_results: int = 4,
                                min_dimension: int = MIN_VIDEO_DIMENSION) -> list[dict]:
        matching = self._find_matching_video_files(query, prefer_vertical, min_dimension)
        return [
            {"url": f["url"], "width": f["width"], "height": f["height"], "is_vertical": f["is_vertical"]}
            for f in matching[:max_results]
        ]

    def _find_matching_photos(self, query: str, prefer_vertical: bool, min_dimension: int) -> list[dict]:
        try:
            resp = requests.get(
                PEXELS_PHOTO_URL,
                params={"query": query, "per_page": 15},
                headers=self._headers, timeout=20,
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
        except requests.RequestException as exc:
            logger.warning("Pexels rasm so'rovida xatolik (%s): %s", query, exc)
            return []

        allow_fallback = allow_orientation_fallback()
        good = []
        for photo in photos:
            w, h = photo.get("width") or 0, photo.get("height") or 0
            if min(w, h) < min_dimension:
                continue
            is_vertical = h > w
            if is_vertical != prefer_vertical and not allow_fallback:
                continue
            url = (photo.get("src") or {}).get("original")
            if url:
                good.append({"url": url, "score": w * h, "is_vertical": is_vertical})

        if not good:
            logger.info("Pexels'da '%s' uchun mos rasm topilmadi", query)
        return sorted(
            good,
            key=lambda p: (_orientation_sort_key(p["is_vertical"], prefer_vertical), -p["score"]),
        )

    def fetch_photo_candidates(self, query: str, prefer_vertical: bool = True, max_results: int = 4,
                                min_dimension: int = MIN_PHOTO_DIMENSION) -> list[str]:
        good = self._find_matching_photos(query, prefer_vertical, min_dimension)
        return [p["url"] for p in good[:max_results]]
