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

from .quality import max_video_dimension

logger = logging.getLogger(__name__)

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
MIN_VIDEO_DIMENSION = 1080  # Full HD dan past sifat qabul qilinmaydi
MIN_PHOTO_DIMENSION = 1600


class PexelsFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._headers = {"Authorization": api_key}

    def _find_matching_video_files(self, query: str, prefer_vertical: bool) -> list[dict]:
        try:
            resp = requests.get(
                PEXELS_VIDEO_URL,
                params={"query": query, "per_page": 15, "orientation": "portrait" if prefer_vertical else "landscape"},
                headers=self._headers, timeout=20,
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
        except requests.RequestException as exc:
            logger.warning("Pexels video so'rovida xatolik (%s): %s", query, exc)
            return []

        matching = []
        max_dim = max_video_dimension()
        for video in videos:
            best_file = None
            for vf in video.get("video_files", []):
                w, h = vf.get("width") or 0, vf.get("height") or 0
                if not w or not h:
                    continue
                if min(w, h) < MIN_VIDEO_DIMENSION or max(w, h) > max_dim:
                    continue
                is_vertical = h > w
                if is_vertical != prefer_vertical:
                    continue
                if best_file is None or w * h > best_file["width"] * best_file["height"]:
                    best_file = {"url": vf["link"], "width": w, "height": h}
            if best_file:
                matching.append(best_file)

        if not matching:
            logger.info(
                "Pexels'da '%s' uchun %s formatdagi %dp+ sifatli video topilmadi",
                query, "vertikal" if prefer_vertical else "gorizontal", MIN_VIDEO_DIMENSION,
            )
        return sorted(matching, key=lambda f: f["width"] * f["height"], reverse=True)

    def fetch_video_candidates(self, query: str, prefer_vertical: bool = True, max_results: int = 4) -> list[str]:
        matching = self._find_matching_video_files(query, prefer_vertical)
        return [f["url"] for f in matching[:max_results]]

    def _find_matching_photos(self, query: str, prefer_vertical: bool) -> list[dict]:
        try:
            resp = requests.get(
                PEXELS_PHOTO_URL,
                params={"query": query, "per_page": 15, "orientation": "portrait" if prefer_vertical else "landscape"},
                headers=self._headers, timeout=20,
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
        except requests.RequestException as exc:
            logger.warning("Pexels rasm so'rovida xatolik (%s): %s", query, exc)
            return []

        good = []
        for photo in photos:
            w, h = photo.get("width") or 0, photo.get("height") or 0
            if min(w, h) < MIN_PHOTO_DIMENSION:
                continue
            is_vertical = h > w
            if is_vertical != prefer_vertical:
                continue
            url = (photo.get("src") or {}).get("original")
            if url:
                good.append({"url": url, "score": w * h})

        if not good:
            logger.info("Pexels'da '%s' uchun mos rasm topilmadi", query)
        return sorted(good, key=lambda p: p["score"], reverse=True)

    def fetch_photo_candidates(self, query: str, prefer_vertical: bool = True, max_results: int = 4) -> list[str]:
        good = self._find_matching_photos(query, prefer_vertical)
        return [p["url"] for p in good[:max_results]]
