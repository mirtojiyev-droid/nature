"""
Pixabay API orqali berilgan query bo'yicha tabiat rasm yoki videosini topib beradi.
Pexels'ga qo'shimcha (zaxira) manba sifatida ishlatiladi — ba'zan Pexels'da topilmagan
narsa Pixabay'da topilishi mumkin, shu bilan umumiy topilish ehtimoli oshadi.
Bepul, litsenziyasi ochiq: https://pixabay.com/service/terms/
API kalit: https://pixabay.com/api/docs/ (bepul, ro'yxatdan o'tib olinadi)
"""
import logging
import random

import requests

logger = logging.getLogger(__name__)

PIXABAY_PHOTO_URL = "https://pixabay.com/api/"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"

# media_fetcher.py'dagi bilan bir xil mantiq: juda katta fayllardan qochish uchun chegara.
MAX_VIDEO_DIMENSION = 1920


def _rank_and_pick(items: list, key_fn, top_n: int = 5):
    if not items:
        return None
    ranked = sorted(items, key=key_fn, reverse=True)
    top = ranked[: min(top_n, len(ranked))]
    return random.choice(top)


def _pick_best_pixabay_video_file(videos: dict) -> dict | None:
    """`videos` — {'large':..., 'medium':..., 'small':..., 'tiny':...} ko'rinishidagi dict.
    Har biri width/height/url'ga ega. Eng yuqori sifatli, lekin MAX_VIDEO_DIMENSION'dan
    oshmagan variantni tanlaydi."""
    candidates = [
        info for info in videos.values()
        if info and info.get("url") and info.get("width") and info.get("height")
    ]
    if not candidates:
        return None

    def resolution(c):
        return c["width"] * c["height"]

    within_cap = [c for c in candidates if max(c["width"], c["height"]) <= MAX_VIDEO_DIMENSION]
    if within_cap:
        return max(within_cap, key=resolution)
    return min(candidates, key=resolution)


class PixabayFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_photo(self, query: str, prefer_vertical: bool = True) -> str | None:
        """Pixabay rasm API'si `orientation` parametrini qo'llab-quvvatlaydi, shuning uchun
        vertikal/gorizontal so'rovni to'g'ridan-to'g'ri berish mumkin. Natijalar orasidan
        eng yuqori original o'lchamlisi (sifatlisi) tanlanadi."""
        orientation = "vertical" if prefer_vertical else "horizontal"
        try:
            resp = requests.get(
                PIXABAY_PHOTO_URL,
                params={
                    "key": self.api_key,
                    "q": query,
                    "image_type": "photo",
                    "orientation": orientation,
                    "per_page": 20,
                    "safesearch": "true",
                },
                timeout=20,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            if not hits:
                logger.info("Pixabay'da '%s' (%s) uchun rasm topilmadi", query, orientation)
                return None
            chosen = _rank_and_pick(hits, lambda h: (h.get("imageWidth") or 0) * (h.get("imageHeight") or 0))
            return chosen.get("largeImageURL")
        except requests.RequestException as exc:
            logger.warning("Pixabay rasm so'rovida xatolik (%s): %s", query, exc)
            return None

    def fetch_video(self, query: str, prefer_vertical: bool = True) -> str | None:
        """Pixabay video API'sida `orientation` parametri yo'q, shuning uchun har bir
        natijaning o'zi (video fayl width/height'i) tekshirilib, vertikal yoki gorizontal
        ekanligi aniqlanadi va faqat so'ralgan formatga mos kelganlar orasidan eng yuqori
        sifatlisi tanlanadi. Mos keladigan hech narsa topilmasa None qaytadi — chaqiruvchi
        (main.py) shu holatda boshqa orientatsiya bilan qayta urinadi."""
        try:
            resp = requests.get(
                PIXABAY_VIDEO_URL,
                params={
                    "key": self.api_key,
                    "q": query,
                    "per_page": 20,
                    "safesearch": "true",
                },
                timeout=20,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            if not hits:
                logger.info("Pixabay'da '%s' uchun video topilmadi", query)
                return None

            matching = []
            for hit in hits:
                best_file = _pick_best_pixabay_video_file(hit.get("videos", {}))
                if not best_file:
                    continue
                is_vertical = best_file["height"] > best_file["width"]
                if is_vertical == prefer_vertical:
                    matching.append(best_file)

            if not matching:
                logger.info(
                    "Pixabay'da '%s' uchun %s formatdagi video topilmadi",
                    query,
                    "vertikal" if prefer_vertical else "gorizontal",
                )
                return None

            chosen = _rank_and_pick(matching, lambda f: f["width"] * f["height"])
            return chosen["url"]
        except requests.RequestException as exc:
            logger.warning("Pixabay video so'rovida xatolik (%s): %s", query, exc)
            return None
