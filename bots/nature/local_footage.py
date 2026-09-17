"""
Foydalanuvchi o'zi (masalan Shutterstock, Envato Elements, iStock/Getty, Storyblocks,
Motion Array kabi pullik obuna asosidagi kutubxonalardan qonuniy yuklab olgan) tayyorlagan
premium/sinematik video kliplarni shu modul boshqaradigan `localfootage/` papkasiga
qo'ysa, bot ularni bepul avtomatik manbalardan (Pexels/Pixabay/Wikimedia Commons) OLDIN,
ENG BIRINCHI navbatda ishlatishga harakat qiladi.

Nega bu kutubxonalar to'g'ridan-to'g'ri (Pexels/Pixabay/Wikimedia Commons kabi) botga
ulanmagan: ular barchasi pullik obuna/litsenziya asosida ishlaydi va Pexels/Pixabay'dan
farqli o'laroq, ochiq, bepul, o'z-o'zidan ro'yxatdan o'tiladigan qidiruv+yuklab olish
API'siga ega emas — API olish uchun odatda alohida biznes-hamkorlik arizasi kerak, va
yuklab olish har doim pullik. Bundan ham muhimi: ularning litsenziya shartlari kontentni
FAQAT inson tomonidan qo'lda tanlab, aniq bir loyiha uchun yuklab olishga ruxsat beradi —
avtomatik bot orqali skanerlash/yuklab olish (hatto to'langan obuna bilan ham) shartlarni
buzadi. Shuning uchun bu integratsiyani bot ichida to'liq avtomatlashtirib bo'lmaydi.

Buning o'rniga: agar sizda shu platformalardan biriga obuna bo'lsa, o'zingiz saytda
qo'lda ko'rib, yoqqan videongizni yuklab oling (bu — litsenziya talab qilgan "inson
tomonidan tanlash" qadami) va shu papkaga joylang. Fayl nomini tavsiflovchi so'zlar
bilan ataylab qo'ysangiz (masalan "waterfall_night_storm_dramatic.mp4"), bot uni kunlik
mavzu/qirra so'roviga mos kelganda avtomatik tanlab, joylashtiradi.
"""
import logging
import random
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

LOCAL_FOOTAGE_DIR = Path(__file__).parent / "localfootage"
VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".avi")

_WORD_RE = re.compile(r"[a-zA-Z0-9']+")


def _keywords(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text)}


def _list_local_videos() -> list[Path]:
    if not LOCAL_FOOTAGE_DIR.exists():
        return []
    return [p for p in LOCAL_FOOTAGE_DIR.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]


def _is_vertical(path: Path) -> bool | None:
    """Videoning haqiqiy o'lchamini ffprobe orqali tekshiradi. ffprobe topilmasa yoki
    xatolik bo'lsa None qaytaradi (orientatsiya bo'yicha filtrlanmaydi, lekin fayl
    baribir kalit so'z mos kelgani uchun nomzod bo'lib qoladi)."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                str(path),
            ],
            capture_output=True, text=True, timeout=15, check=True,
        )
        width_str, height_str = result.stdout.strip().split("x")
        return int(height_str) > int(width_str)
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def find_local_video(variants: list[str], prefer_vertical: bool = True) -> Path | None:
    """`variants` ro'yxatini (eng aniq so'rovdan eng umumiygacha) navbat bilan tekshiradi
    — fayl nomida shu so'rovning kamida bitta so'zi uchrasa, mos nomzod deb hisoblanadi.
    Bir nechta mos fayl topilsa, orientatsiyasi (vertikal/gorizontal) so'ralganiga to'g'ri
    kelganlar afzal ko'riladi; lekin hech biri to'g'ri kelmasa ham, qo'lda tanlab
    qo'yilgan sifatli kontentni shunchaki o'tkazib yubormaslik uchun, mos kelgan fayllar
    orasidan baribir biri tanlanadi.

    music/ papkasidagi kabi — bu papka bo'sh bo'lsa (yoki hech qanday fayl nomi joriy
    so'rovlarga mos kelmasa), None qaytadi va chaqiruvchi (main.py) odatdagidek
    Pexels/Pixabay/Wikimedia Commons kaskadiga o'tadi."""
    videos = _list_local_videos()
    if not videos:
        return None

    for query in variants:
        query_words = _keywords(query)
        if not query_words:
            continue
        matches = [p for p in videos if _keywords(p.stem) & query_words]
        if not matches:
            continue
        oriented = [p for p in matches if _is_vertical(p) == prefer_vertical]
        pool = oriented or matches
        chosen = random.choice(pool)
        logger.info("Lokal premium video topildi — fayl: %s, mos so'rov: '%s'", chosen.name, query)
        return chosen

    return None
