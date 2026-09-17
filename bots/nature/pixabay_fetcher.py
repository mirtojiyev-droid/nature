"""
Pixabay API orqali berilgan query bo'yicha tabiat rasm yoki videosini topib beradi.
Pexels'ga qo'shimcha (zaxira) manba sifatida ishlatiladi — ba'zan Pexels'da topilmagan
narsa Pixabay'da topilishi mumkin, shu bilan umumiy topilish ehtimoli oshadi.
Bepul, litsenziyasi ochiq: https://pixabay.com/service/terms/
API kalit: https://pixabay.com/api/docs/ (bepul, ro'yxatdan o'tib olinadi)
"""
import logging
import random
import re

import requests

from .quality import max_video_dimension

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-zA-Z0-9']+")


def _keywords(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)}


def _filter_by_relevance(hits: list, query: str) -> list:
    """Pixabay har bir hit uchun qo'lda qo'yilgan `tags` (masalan "waterfall, forest,
    nature") maydonini beradi. Bu — so'rov so'zi bilan hitning HAQIQATAN aloqasi
    borligini tekshirish uchun qo'shimcha ishonch signali (faqat o'lcham bo'yicha
    saralash so'rovga umuman aloqasi yo'q, lekin API javobida kelgan natijani ham
    "eng sifatlisi" deb tanlab qo'yishi mumkin edi).

    MUHIM (foydalanuvchi tomonidan aniqlangan xato tuzatildi): AVVAL hech qanday hit
    mos kelmasa, baribir BARCHA hitlar bilan davom etilardi ("aks holda hech narsa
    topilmay qolar edi" degan mulohaza bilan) — lekin aynan shu "zaxira yo'l" orqali
    so'rovga umuman aloqasi yo'q kontent (masalan "ocean" so'ralganda o'rmon videosi)
    sizib o'tib ketardi. Endi mos kelmasa, BO'SH ro'yxat qaytariladi — chaqiruvchi
    (run.py'dagi _fetch_with_fallback) bu holatda avtomatik ravishda soddaroq so'rov
    variantiga yoki keyingi manbaga (Pexels/Wikimedia) o'tadi — bu noto'g'ri
    mazmundagi post joylashdan ANCHA yaxshi."""
    query_words = _keywords(query)
    if not query_words:
        return hits
    return [h for h in hits if _keywords(h.get("tags", "")) & query_words]

PIXABAY_PHOTO_URL = "https://pixabay.com/api/"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"

# media_fetcher.py'dagi bilan bir xil mantiq: standart 4K, .env orqali pasaytiriladi
# (bots/nature/quality.py'ga qarang).

# Bu chegaralardan PASTROQ hech narsa qabul qilinmaydi (past sifatni butunlay rad etish).
MIN_VIDEO_DIMENSION = 1080
MIN_PHOTO_DIMENSION = 1600


def _rank_and_pick(items: list, key_fn, top_n: int = 5):
    if not items:
        return None
    ranked = sorted(items, key=key_fn, reverse=True)
    top = ranked[: min(top_n, len(ranked))]
    return random.choice(top)


def _pick_best_pixabay_video_file(videos: dict) -> dict | None:
    """`videos` — {'large':..., 'medium':..., 'small':..., 'tiny':...} ko'rinishidagi dict.
    Har biri width/height/url'ga ega. MIN_VIDEO_DIMENSION va MAX_VIDEO_DIMENSION (HD dan
    4K'gacha) oralig'idagi eng yuqori sifatli variantni tanlaydi. Shu oraliqda hech narsa
    bo'lmasa (masalan faqat 'tiny'/'small' past sifatli variantlar mavjud bo'lsa), None
    qaytaradi — past sifatli fayl hech qachon tanlanmaydi."""
    candidates = [
        info for info in videos.values()
        if info and info.get("url") and info.get("width") and info.get("height")
    ]
    if not candidates:
        return None

    def short_side(c):
        return min(c["width"], c["height"])

    def resolution(c):
        return c["width"] * c["height"]

    within_cap = [c for c in candidates if short_side(c) >= MIN_VIDEO_DIMENSION and max(c["width"], c["height"]) <= max_video_dimension()]
    if within_cap:
        return max(within_cap, key=resolution)

    above_cap = [c for c in candidates if short_side(c) >= MIN_VIDEO_DIMENSION]
    if above_cap:
        return min(above_cap, key=resolution)

    return None


class PixabayFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_photo(self, query: str, prefer_vertical: bool = True) -> str | None:
        """Pixabay rasm API'si `orientation` parametrini qo'llab-quvvatlaydi, shuning uchun
        vertikal/gorizontal so'rovni to'g'ridan-to'g'ri berish mumkin. Natijalar avval
        so'rov so'zlari bilan `tags` mos kelishi bo'yicha filtrlanadi (mavzuga aloqasi
        yo'q natijalarni chetlab o'tish uchun), so'ng MIN_PHOTO_DIMENSION'dan past
        o'lchamdagilar butunlay chiqarib tashlanadi, va qolganlar orasidan eng yuqori
        o'lchamlisi (sifatlisi) tanlanadi. `fullHDURL` mavjud bo'lsa (ba'zi hisoblarda
        Pixabay shuni beradi — 1920px+), u ishlatiladi; bo'lmasa `largeImageURL`."""
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
            relevant = _filter_by_relevance(hits, query)
            good = [
                h for h in relevant
                if min(h.get("imageWidth") or 0, h.get("imageHeight") or 0) >= MIN_PHOTO_DIMENSION
            ]
            if not good:
                logger.info(
                    "Pixabay'da '%s' (%s) uchun %dpx+ sifatli/mos rasm topilmadi",
                    query, orientation, MIN_PHOTO_DIMENSION,
                )
                return None
            chosen = _rank_and_pick(good, lambda h: (h.get("imageWidth") or 0) * (h.get("imageHeight") or 0))
            return chosen.get("fullHDURL") or chosen.get("largeImageURL")
        except requests.RequestException as exc:
            logger.warning("Pixabay rasm so'rovida xatolik (%s): %s", query, exc)
            return None

    def _find_matching_video_files(self, query: str, prefer_vertical: bool) -> list[dict]:
        """Ichki yordamchi — so'rovga mos, sifat talablariga javob beradigan barcha
        video fayllarni TOPILGAN TARTIBDA (eng yaxshisidan eng yomoniga) qaytaradi.
        `fetch_video` (bitta eng yaxshisini) va `fetch_video_candidates` (bir nechta
        nomzodni, agar birinchisi yuklab bo'lmasa yoki sifat nazoratidan o'tmasa,
        keyingisini sinab ko'rish uchun) shu yerdan foydalanadi."""
        try:
            resp = requests.get(
                PIXABAY_VIDEO_URL,
                params={"key": self.api_key, "q": query, "per_page": 20, "safesearch": "true"},
                timeout=20,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except requests.RequestException as exc:
            logger.warning("Pixabay video so'rovida xatolik (%s): %s", query, exc)
            return []

        if not hits:
            logger.info("Pixabay'da '%s' uchun video topilmadi", query)
            return []

        hits = _filter_by_relevance(hits, query)
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
                "Pixabay'da '%s' uchun %s formatdagi %dp+ sifatli video topilmadi",
                query, "vertikal" if prefer_vertical else "gorizontal", MIN_VIDEO_DIMENSION,
            )
        return sorted(matching, key=lambda f: f["width"] * f["height"], reverse=True)

    def fetch_video(self, query: str, prefer_vertical: bool = True) -> str | None:
        """Faqat BITTA (eng yaxshi, tasodifiy tanlangan) video havolasini qaytaradi.
        Bir nechta nomzod kerak bo'lsa (masalan biri yuklab bo'lmasa, keyingisini
        sinash uchun), `fetch_video_candidates()`dan foydalaning."""
        matching = self._find_matching_video_files(query, prefer_vertical)
        if not matching:
            return None
        chosen = _rank_and_pick(matching, lambda f: f["width"] * f["height"])
        return chosen["url"]

    def fetch_video_candidates(self, query: str, prefer_vertical: bool = True, max_results: int = 4) -> list[str]:
        """`fetch_video`dan farqli — BIR NECHTA nomzod havolasini (eng yaxshisidan
        boshlab) ro'yxat sifatida qaytaradi. run.py buni "birinchi nomzod yuklab
        bo'lmasa yoki sifat nazoratidan (ffmpeg qayta ishlash, bo'sh-kadr tekshiruvi)
        o'tmasa — keyingisini sinash" uchun ishlatadi, shunda faqat BITTA muammoli
        fayl tufayli butun post rasm bilan cheklanib qolmaydi."""
        matching = self._find_matching_video_files(query, prefer_vertical)
        return [f["url"] for f in matching[:max_results]]
