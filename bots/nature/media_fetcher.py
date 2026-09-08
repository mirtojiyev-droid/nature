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
# variant sifatida tanlaymiz — 3840 = 4K (UHD). Bundan kattaroq (masalan 8K) fayllar
# Telegram'ga yuklashda hajm chegarasiga urilishi va sekin ishlov berilishi mumkin,
# shuning uchun 4K yuqori chegara sifatida qoldiriladi.
MAX_VIDEO_DIMENSION = 3840

# Bundan PASTROQ o'lchamdagi video/rasm UMUMAN qabul qilinmaydi — sifatsiz (masalan
# 480p) kontentni "hech bo'lmasa nimadir topildi" deb nashr qilishning oldini olish
# uchun. Shu chegaradan past variant topilsa, fetch_video/fetch_photo None qaytaradi va
# main.py boshqa manbaga yoki keyingi so'rov variantiga o'tadi — kerak bo'lsa, hech
# narsa topilmay postni o'tkazib yuborish past sifatli kontent joylashdan yaxshiroq.
MIN_VIDEO_DIMENSION = 1080  # qisqa tomoni kamida ~1080p bo'lishi kerak
MIN_PHOTO_DIMENSION = 1600  # qisqa tomoni kamida shuncha piksel bo'lishi kerak


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
    """`video_files` ichidan MIN_VIDEO_DIMENSION va MAX_VIDEO_DIMENSION oralig'idagi eng
    yuqori sifatli faylni tanlaydi. Agar shu oraliqda hech narsa bo'lmasa:
    - MAX'dan kattaroq (masalan 8K) variantlar bo'lsa, ular orasidan eng kichigi
      tanlanadi (baribir yuqori sifatli, faqat cheklangan hajmga siqib qo'yiladi keyinroq);
    - lekin barcha variantlar MIN_VIDEO_DIMENSION'dan PAST bo'lsa, None qaytariladi — past
      sifatli video umuman qabul qilinmaydi, chaqiruvchi boshqa manba/so'rovga o'tadi."""
    def short_side(f):
        return min(f.get("width") or 0, f.get("height") or 0)

    def resolution(f):
        return (f.get("width") or 0) * (f.get("height") or 0)

    valid = [f for f in video_files if f.get("width") and f.get("height")]
    within_cap = [f for f in valid if short_side(f) >= MIN_VIDEO_DIMENSION and max(f["width"], f["height"]) <= MAX_VIDEO_DIMENSION]
    if within_cap:
        return max(within_cap, key=resolution)

    above_cap = [f for f in valid if short_side(f) >= MIN_VIDEO_DIMENSION]
    if above_cap:
        return min(above_cap, key=resolution)

    return None


class MediaFetcher:
    def __init__(self, api_key: str):
        self.headers = {"Authorization": api_key}

    def fetch_photo(self, query: str, prefer_vertical: bool = True) -> str | None:
        """Berilgan query bo'yicha rasm URL'ini qaytaradi — natijalar orasidan eng yuqori
        original o'lchamlisi (sifatlisi) tanlanadi va `src["original"]` (Pexels'ning eng
        yuqori sifatli, hech qanday siqilmagan varianti — ko'pincha 4K va undan yuqori)
        qaytariladi, `large2x` (~1880px'ga cheklangan) emas. `photo["width"/"height"]`
        (Pexels'ning haqiqiy original o'lchami) MIN_PHOTO_DIMENSION'dan past bo'lgan
        natijalar butunlay chetlab o'tiladi — past sifatli rasm hech qachon tanlanmaydi.
        `prefer_vertical=True` bo'lsa, telefonda to'liq ekranga mos vertikal (portret) rasm
        qidiriladi; topilmasa chaqiruvchi (main.py) buni gorizontal (landscape) bilan qayta
        chaqiradi."""
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
            good = [
                p for p in photos
                if min(p.get("width") or 0, p.get("height") or 0) >= MIN_PHOTO_DIMENSION
            ]
            if not good:
                logger.info(
                    "Pexels'da '%s' (%s) uchun %dpx+ sifatli rasm topilmadi (%d natija bor edi, hammasi past sifatli)",
                    query, orientation, MIN_PHOTO_DIMENSION, len(photos),
                )
                return None
            chosen = _rank_and_pick(good, lambda p: (p.get("width") or 0) * (p.get("height") or 0))
            return chosen["src"].get("original") or chosen["src"]["large2x"]
        except requests.RequestException as exc:
            logger.error("Pexels rasm so'rovida xatolik (%s): %s", query, exc)
            return None

    def fetch_video(self, query: str, prefer_vertical: bool = True) -> str | None:
        """Berilgan query bo'yicha eng mos videoning to'g'ridan-to'g'ri fayl URL'ini
        qaytaradi. Natijalar orasidan eng yuqori sifatlisi (o'lchami) tanlanadi, so'ng shu
        videoning fayl variantlaridan ham eng sifatlisi (MIN_VIDEO_DIMENSION va
        MAX_VIDEO_DIMENSION — ya'ni HD dan 4K'gacha — oralig'ida) tanlanadi. Shu oraliqda
        hech qanday fayl variant topilmasa (masalan faqat past sifatli 480p fayllar mavjud
        bo'lsa), bu video butunlay o'tkazib yuboriladi — past sifatli video hech qachon
        tanlanmaydi. `prefer_vertical=True` bo'lsa, telefon ekraniga mos vertikal ("short"
        formatiga o'xshash) video qidiriladi."""
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
            # Har bir video-elementning O'ZINING eng sifatli fayl variantini oldindan
            # aniqlaymiz, so'ng shular orasidan eng yaxshisini tanlaymiz — aks holda avval
            # "eng sifatli video elementi" tanlab, keyin uning fayllari orasida sifatli
            # variant topilmay qolishi (va shu bilan butun postni yo'qotish) mumkin edi.
            candidates = []
            for v in videos:
                best_file = _pick_best_video_file(v.get("video_files", []))
                if best_file:
                    candidates.append(best_file)
            if not candidates:
                logger.info(
                    "Pexels'da '%s' (%s) uchun %dp+ sifatli video topilmadi",
                    query, orientation, MIN_VIDEO_DIMENSION,
                )
                return None
            chosen = _rank_and_pick(candidates, lambda f: (f.get("width") or 0) * (f.get("height") or 0))
            return chosen["link"]
        except requests.RequestException as exc:
            logger.error("Pexels video so'rovida xatolik (%s): %s", query, exc)
            return None
