"""
Pixabay API orqali berilgan query bo'yicha tabiat rasm yoki videosini topib beradi.
Tabiat botining ASOSIY (yagona avtomatik) manbasi — foydalanuvchi Pexels bilan
Pixabay'ni qo'lda solishtirib, Pixabay'da vizual jihatdan ancha chiroyli/e'tiborni
tortadigan kontent ko'proq ekanini aniqlagach, Pexels butunlay olib tashlangan.
Wikimedia Commons — kalitsiz, har doim mavjud — oxirgi zaxira manba sifatida qoladi.
Bepul, litsenziyasi ochiq: https://pixabay.com/service/terms/
API kalit: https://pixabay.com/api/docs/ (bepul, ro'yxatdan o'tib olinadi — SHART,
run.py'dagi run_once() shu kalitsiz ishlamaydi).
"""
import logging
import random
import re

import requests

from .config import allow_orientation_fallback
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
    variantiga yoki keyingi manbaga (Wikimedia) o'tadi — bu noto'g'ri
    mazmundagi post joylashdan ANCHA yaxshi."""
    query_words = _keywords(query)
    if not query_words:
        return hits
    return [h for h in hits if _keywords(h.get("tags", "")) & query_words]

PIXABAY_PHOTO_URL = "https://pixabay.com/api/"
PIXABAY_VIDEO_URL = "https://pixabay.com/api/videos/"

# media_fetcher.py'dagi bilan bir xil mantiq: standart 4K, .env orqali pasaytiriladi
# (bots/nature/quality.py'ga qarang).

# Bu qiymatlar endi ZAXIRA sifatida qoladi (funksiyalarga min_dimension berilmasa
# ishlatiladi) — asosiy chegara endi run.py orqali config.py'dagi
# min_video_dimension_tiers()/min_photo_dimension_tiers()'dan (bosqichma-bosqich
# pasayadigan, .env orqali sozlanadigan) uzatiladi.
MIN_VIDEO_DIMENSION = 1080
MIN_PHOTO_DIMENSION = 1600


def _rank_and_pick(items: list, key_fn, top_n: int = 5):
    if not items:
        return None
    ranked = sorted(items, key=key_fn, reverse=True)
    top = ranked[: min(top_n, len(ranked))]
    return random.choice(top)


def _pick_best_pixabay_video_file(videos: dict, min_dimension: int) -> dict | None:
    """`videos` — {'large':..., 'medium':..., 'small':..., 'tiny':...} ko'rinishidagi dict.
    Har biri width/height/url'ga ega. `min_dimension` va MAX_VIDEO_DIMENSION (HD dan
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

    within_cap = [c for c in candidates if short_side(c) >= min_dimension and max(c["width"], c["height"]) <= max_video_dimension()]
    if within_cap:
        return max(within_cap, key=resolution)

    above_cap = [c for c in candidates if short_side(c) >= min_dimension]
    if above_cap:
        return min(above_cap, key=resolution)

    return None


def _orientation_sort_key(is_vertical: bool, prefer_vertical: bool):
    """Afzal ko'rilgan orientatsiyaga mos kelganlarni OLDINGA chiqaradi (0),
    qarshi orientatsiyadagilarni orqaga suradi (1) — lekin BUTUNLAY chetlab
    tashlamaydi (allow_orientation_fallback yoqilgan bo'lsa). Shu tarzda bitta
    so'rovning o'zida ham afzal, ham (kerak bo'lsa) zaxira format nomzodlari
    birga qaytariladi, alohida ikkinchi to'liq qidiruv siklisiz."""
    return 0 if is_vertical == prefer_vertical else 1


class PixabayFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def _find_matching_photos(self, query: str, prefer_vertical: bool, min_dimension: int) -> list[dict]:
        """Ichki yordamchi — `fetch_photo` va `fetch_photo_candidates` uchun umumiy.

        MUHIM (universal sozlash uchun o'zgartirildi): avval to'g'ridan-to'g'ri
        Pixabay API'ning `orientation` parametri orqali FAQAT bitta orientatsiya
        so'ralardi — hech narsa topilmasa, run.py butun so'rovni QAYTADAN
        (`prefer_vertical=False` bilan) boshdan boshlashga majbur edi. Endi
        `orientation` parametri BERILMAYDI (ikkala orientatsiya ham bitta
        so'rovda qaytadi), va NATURE_ALLOW_ORIENTATION_FALLBACK yoqilgan bo'lsa,
        afzal ko'rilgan format oldinga chiqarilib, qarshi format ZAXIRA sifatida
        SHU RO'YXATNING O'ZIDA saqlanadi — alohida ikkinchi to'liq qidiruv
        siklisiz."""
        try:
            resp = requests.get(
                PIXABAY_PHOTO_URL,
                params={
                    "key": self.api_key, "q": query, "image_type": "photo",
                    "per_page": 20, "safesearch": "true",
                },
                timeout=20,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except requests.RequestException as exc:
            logger.warning("Pixabay rasm so'rovida xatolik (%s): %s", query, exc)
            return []

        if not hits:
            logger.info("Pixabay'da '%s' uchun rasm topilmadi", query)
            return []
        relevant = _filter_by_relevance(hits, query)
        good = [
            h for h in relevant
            if min(h.get("imageWidth") or 0, h.get("imageHeight") or 0) >= min_dimension
        ]
        if allow_orientation_fallback():
            eligible = good
        else:
            eligible = [
                h for h in good
                if ((h.get("imageHeight") or 0) > (h.get("imageWidth") or 0)) == prefer_vertical
            ]
        if not eligible:
            logger.info(
                "Pixabay'da '%s' uchun %dpx+ sifatli/mos rasm topilmadi",
                query, min_dimension,
            )
        return sorted(
            eligible,
            key=lambda h: (
                _orientation_sort_key((h.get("imageHeight") or 0) > (h.get("imageWidth") or 0), prefer_vertical),
                -((h.get("imageWidth") or 0) * (h.get("imageHeight") or 0)),
            ),
        )

    def fetch_photo(self, query: str, prefer_vertical: bool = True, min_dimension: int = MIN_PHOTO_DIMENSION) -> str | None:
        """Pixabay rasm API'si `orientation` parametrini qo'llab-quvvatlaydi, shuning uchun
        vertikal/gorizontal so'rovni to'g'ridan-to'g'ri berish mumkin. `fullHDURL` mavjud
        bo'lsa (ba'zi hisoblarda Pixabay shuni beradi — 1920px+), u ishlatiladi; bo'lmasa
        `largeImageURL`. Bir nechta nomzod kerak bo'lsa, `fetch_photo_candidates()`ga
        qarang."""
        good = self._find_matching_photos(query, prefer_vertical, min_dimension)
        if not good:
            return None
        chosen = _rank_and_pick(good[:5], lambda h: (h.get("imageWidth") or 0) * (h.get("imageHeight") or 0))
        return chosen.get("fullHDURL") or chosen.get("largeImageURL")

    def fetch_photo_candidates(self, query: str, prefer_vertical: bool = True, max_results: int = 4,
                                min_dimension: int = MIN_PHOTO_DIMENSION) -> list[str]:
        """Bir nechta nomzod havolasini (eng yaxshisidan boshlab) qaytaradi — video
        uchun `fetch_video_candidates`dagi bir xil sababga ko'ra (birinchi nomzod
        yuklab bo'lmasa yoki buzuq/bo'sh chiqsa, keyingisini sinash uchun).
        `min_dimension` — run.py orqali config.py'dagi bosqichma-bosqich pasayadigan
        sifat darajalaridan (masalan avval 1600px, topilmasa 1080px) uzatiladi."""
        good = self._find_matching_photos(query, prefer_vertical, min_dimension)
        return [h.get("fullHDURL") or h.get("largeImageURL") for h in good[:max_results]]

    def _find_matching_video_files(self, query: str, prefer_vertical: bool, min_dimension: int) -> list[dict]:
        """Ichki yordamchi — so'rovga mos, sifat talablariga javob beradigan barcha
        video fayllarni TOPILGAN TARTIBDA (eng yaxshisidan eng yomoniga) qaytaradi.
        `fetch_video` (bitta eng yaxshisini) va `fetch_video_candidates` (bir nechta
        nomzodni, agar birinchisi yuklab bo'lmasa yoki sifat nazoratidan o'tmasa,
        keyingisini sinab ko'rish uchun) shu yerdan foydalanadi.

        MUHIM: qarshi orientatsiyadagi (masalan gorizontal, vertikal so'ralganda)
        videolar BUTUNLAY chetlab tashlanmaydi (NATURE_ALLOW_ORIENTATION_FALLBACK
        yoqilgan bo'lsa) — ular ro'yxat OXIRIGA suriladi va har biriga `is_vertical`
        belgisi qo'shiladi, shunda run.py/music_mixer.py kerak bo'lsa ffmpeg orqali
        markazdan kesib (crop) kerakli formatga moslashi mumkin."""
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
            best_file = _pick_best_pixabay_video_file(hit.get("videos", {}), min_dimension)
            if not best_file:
                continue
            is_vertical = best_file["height"] > best_file["width"]
            if is_vertical == prefer_vertical or allow_orientation_fallback():
                best_file["is_vertical"] = is_vertical
                matching.append(best_file)

        if not matching:
            logger.info(
                "Pixabay'da '%s' uchun %dp+ sifatli video topilmadi",
                query, min_dimension,
            )
        return sorted(
            matching,
            key=lambda f: (_orientation_sort_key(f["is_vertical"], prefer_vertical), -(f["width"] * f["height"])),
        )

    def fetch_video(self, query: str, prefer_vertical: bool = True, min_dimension: int = MIN_VIDEO_DIMENSION) -> str | None:
        """Faqat BITTA (eng yaxshi, tasodifiy tanlangan) video havolasini qaytaradi.
        Bir nechta nomzod kerak bo'lsa (masalan biri yuklab bo'lmasa, keyingisini
        sinash uchun), `fetch_video_candidates()`dan foydalaning."""
        matching = self._find_matching_video_files(query, prefer_vertical, min_dimension)
        if not matching:
            return None
        chosen = _rank_and_pick(matching[:5], lambda f: f["width"] * f["height"])
        return chosen["url"]

    def fetch_video_candidates(self, query: str, prefer_vertical: bool = True, max_results: int = 4,
                                min_dimension: int = MIN_VIDEO_DIMENSION) -> list[dict]:
        """`fetch_video`dan farqli — BIR NECHTA nomzod ma'lumotini (eng yaxshisidan
        boshlab, har biri {"url", "width", "height", "is_vertical"}) ro'yxat
        sifatida qaytaradi. run.py buni "birinchi nomzod yuklab bo'lmasa yoki sifat
        nazoratidan (ffmpeg qayta ishlash, bo'sh-kadr tekshiruvi) o'tmasa —
        keyingisini sinash" uchun ishlatadi, shunda faqat BITTA muammoli fayl
        tufayli butun post rasm bilan cheklanib qolmaydi. `min_dimension` — run.py
        orqali config.py'dagi bosqichma-bosqich pasayadigan sifat darajalaridan
        uzatiladi."""
        matching = self._find_matching_video_files(query, prefer_vertical, min_dimension)
        return [
            {"url": f["url"], "width": f["width"], "height": f["height"], "is_vertical": f["is_vertical"]}
            for f in matching[:max_results]
        ]
