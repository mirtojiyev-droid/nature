"""
Pexels API orqali berilgan query bo'yicha tabiat rasm yoki videosini topib beradi.
Pexels bepul, litsenziyasi ochiq (attribution shart emas), API kalit kerak: https://www.pexels.com/api/
"""
import logging
import random
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def download_file(url: str, dest_path: Path, timeout: int = 60) -> bool:
    """Berilgan URL'dagi faylni (video/rasm) diskka yuklab oladi — musiqa qo'shish kabi
    lokal ishlov berish kerak bo'lganda ishlatiladi. Xatolik bo'lsa False qaytaradi,
    chaqiruvchi shu holatda asl URL bilan (yuklab olmasdan) davom etishi mumkin."""
    try:
        resp = requests.get(url, stream=True, timeout=timeout)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                f.write(chunk)
        return True
    except (requests.RequestException, OSError) as exc:
        logger.warning("Faylni yuklab olishda xatolik (%s): %s", url, exc)
        return False

PEXELS_PHOTO_URL = "https://api.pexels.com/v1/search"
PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"

# Video faylni bu o'lchamdan (uzun tomoni, piksel) katta bo'lmagan eng yuqori sifatli
# variant sifatida tanlaymiz — juda katta (4K/UHD) fayllar Telegram'ga yuklashda muammo
# tug'dirishi (hajm chegarasi) va sekinroq ishlov berilishi mumkin, shu bilan birga past
# sifatli variantlardan ancha yaxshiroq ko'rinadi.
MAX_VIDEO_DIMENSION = 1920


def _rank_and_pick(items: list, key_fn, top_n: int = 5):
    """Ro'yxatni sifat (odatda o'lcham/resolution) bo'yicha kamayish tartibida saralaydi va
    eng yaxshi `top_n` tadan tasodifiy birini tanlaydi — sifatga ustunlik beradi, lekin
    har safar bir xil natija chiqavermasligi uchun ozgina xilma-xillik saqlaydi."""
    if not items:
        return None
    ranked = sorted(items, key=key_fn, reverse=True)
    top = ranked[: min(top_n, len(ranked))]
    return random.choice(top)


def _pick_best_video_file(video_files: list) -> dict | None:
    """`video_files` ichidan eng yuqori sifatli, lekin MAX_VIDEO_DIMENSION'dan oshmagan
    faylni tanlaydi. Barchasi katta bo'lsa (kamdan-kam), eng kichigini tanlaydi — hech
    narsa qaytarmasdan postni butunlay o'tkazib yubormaslik uchun."""
    def resolution(f):
        return (f.get("width") or 0) * (f.get("height") or 0)

    within_cap = [
        f for f in video_files
        if f.get("width") and f.get("height") and max(f["width"], f["height"]) <= MAX_VIDEO_DIMENSION
    ]
    if within_cap:
        return max(within_cap, key=resolution)
    if video_files:
        return min(video_files, key=resolution)
    return None


class MediaFetcher:
    def __init__(self, api_key: str):
        self.headers = {"Authorization": api_key}

    def fetch_photo(self, query: str, prefer_vertical: bool = True) -> str | None:
        """Berilgan query bo'yicha rasm URL'ini qaytaradi — natijalar orasidan eng yuqori
        original o'lchamlisi (sifatlisi) tanlanadi. `prefer_vertical=True` bo'lsa, telefonda
        to'liq ekranga mos vertikal (portret) rasm qidiriladi; topilmasa chaqiruvchi
        (main.py) buni gorizontal (landscape) bilan qayta chaqiradi."""
        orientation = "portrait" if prefer_vertical else "landscape"
        try:
            resp = requests.get(
                PEXELS_PHOTO_URL,
                headers=self.headers,
                params={"query": query, "per_page": 15, "orientation": orientation},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            photos = data.get("photos", [])
            if not photos:
                logger.info("Pexels'da '%s' (%s) uchun rasm topilmadi", query, orientation)
                return None
            chosen = _rank_and_pick(photos, lambda p: (p.get("width") or 0) * (p.get("height") or 0))
            return chosen["src"]["large2x"]
        except requests.RequestException as exc:
            logger.error("Pexels rasm so'rovida xatolik (%s): %s", query, exc)
            return None

    def fetch_video(self, query: str, prefer_vertical: bool = True) -> str | None:
        """Berilgan query bo'yicha eng mos videoning to'g'ridan-to'g'ri fayl URL'ini
        qaytaradi. Natijalar orasidan eng yuqori sifatlisi (o'lchami) tanlanadi, so'ng shu
        videoning fayl variantlaridan ham eng sifatlisi (lekin MAX_VIDEO_DIMENSION'dan
        oshmagani) tanlanadi. `prefer_vertical=True` bo'lsa, telefon ekraniga mos vertikal
        ("short" formatiga o'xshash) video qidiriladi."""
        orientation = "portrait" if prefer_vertical else "landscape"
        try:
            resp = requests.get(
                PEXELS_VIDEO_URL,
                headers=self.headers,
                params={"query": query, "per_page": 15, "orientation": orientation},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            videos = data.get("videos", [])
            if not videos:
                logger.info("Pexels'da '%s' (%s) uchun video topilmadi", query, orientation)
                return None
            chosen = _rank_and_pick(videos, lambda v: (v.get("width") or 0) * (v.get("height") or 0))
            best_file = _pick_best_video_file(chosen.get("video_files", []))
            if not best_file:
                return None
            return best_file["link"]
        except requests.RequestException as exc:
            logger.error("Pexels video so'rovida xatolik (%s): %s", query, exc)
            return None
