"""
Bot Hub — TO'RTTA mustaqil Telegram botni (tabiat, kripto, futbol, YouTube-repost)
BITTA jarayonda, bitta VPS'da, har biri o'z vaqt jadvali bilan ishlaydigan qilib
boshqaradi.

Nega bitta jarayon: barchasi asosan tarmoq so'rovlari bilan band (CPU emas), shuning
uchun bitta kichik VPS'da (masalan 1 CPU / 1-2GB RAM) barchasi bemalol sig'adi — to'rtta
alohida serverga pul to'lash shart emas.

Har bir bot (`bots/nature`, `bots/crypto`, `bots/football`, `bots/youtube`) TO'LIQ
mustaqil: o'zining bot tokeni, kanal ID'si va sozlamalariga ega (.env'da alohida
prefikslar bilan). Bittasi xato bersa ham (masalan Binance vaqtincha ishlamasa),
boshqalari ta'sirlanmaydi — har bir "job" o'zining try/except ichida ishlaydi.

MUHIM (ip-oqim/threading va operativ xotira haqide): har bir bot o'z ALOHIDA
ip-oqimida (thread) ishga tushiriladi, bittasi (masalan tabiat boti ffmpeg bilan, yoki
YouTube boti video yuklab olish bilan) bir necha daqiqa band bo'lishi mumkin, lekin bu
ikkinchisini (masalan kripto botini, aynan shu daqiqada post qilishi kerak bo'lgan)
KECHIKTIRMAYDI.

LEKIN: agar bir nechta bot BIR VAQTDA ishlasa (masalan hub ishga tushgan zahoti, yoki
ikkita botning jadvali tasodifan bir xil daqiqaga to'g'ri kelib qolsa), ularning
operativ xotira sarfi QO'SHILIB ketadi — bu, ayniqsa Render/Railway kabi platformalarning
arzon tariflarida (odatda 512MB-1GB), "out of memory" xatosiga olib kelishi mumkin
(ffmpeg 4K video qayta kodlashda yoki YouTube video yuklab olishda o'zi bir necha yuz
MB talab qilishi mumkin). Shuning uchun `HUB_MAX_CONCURRENT_JOBS` (.env) orqali BIR
VAQTDA nechta bot ishlashi mumkinligini cheklaymiz:
  - Standart (va kam xotirali serverlar uchun tavsiya etiladigan) qiymat: 1 — ya'ni
    botlar HAR DOIM birin-ketin ishlaydi, hech qachon bir vaqtda ishlamaydi (xavfsiz,
    lekin bittasi band bo'lsa boshqasi biroz kutadi).
  - Agar serveringizda operativ xotira yetarli bo'lsa (masalan 2GB+), buni 2 yoki 3'ga
    oshirib, botlarning bir-birini kutmasdan parallel ishlashiga ruxsat berishingiz
    mumkin (tezroq, lekin xotira cho'qqisi balandroq).
Bundan tashqari, har bir bot uchun alohida qulf (Lock) ham bor — shu bot allaqachon
ishlab turgan bo'lsa (masalan interval juda qisqa qilib qo'yilsa-yu, oldingi ishga
tushirish hali tugamagan bo'lsa), shu bot safar shunchaki o'tkazib yuboriladi (o'zining
ikkita nusxasi bir vaqtda ishlab, bir xil faylni ustma-ust yozib qo'ymasligi uchun).

Ishga tushirish: `python main.py` (bu papkadan, hub root'idan). Doimiy (24/7) ishlashi
uchun `bot-hub.service` (systemd) orqali joylang — README.md'ga qarang.
"""
import logging
import os
import sys
import threading
import time

import schedule
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("hub.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("hub")

from bots.crypto import run_once as run_crypto  # noqa: E402
from bots.football import run_once as run_football  # noqa: E402
from bots.nature import run_once as run_nature  # noqa: E402
from bots.youtube import run_once as run_youtube  # noqa: E402


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Har bir bot uchun alohida qulf — bitta botning ikkita nusxasi BIR VAQTDA ishlab
# ketmasligi uchun (masalan interval juda qisqa qilib qo'yilsa-yu, oldingi ishga
# tushirish hali tugamagan bo'lsa).
_locks = {
    "tabiat": threading.Lock(), "kripto": threading.Lock(),
    "futbol": threading.Lock(), "youtube": threading.Lock(),
}

# Bir vaqtning o'zida nechta bot ISHLASHI (fn() bajarilishi) mumkinligini cheklovchi
# umumiy semafor — operativ xotirani nazoratda ushlab turish uchun. Standart 1 =
# botlar hech qachon bir vaqtda ishlamaydi (kam xotirali serverlar uchun xavfsiz).
_MAX_CONCURRENT_JOBS = max(1, _env_int("HUB_MAX_CONCURRENT_JOBS", 1))
_concurrency_semaphore = threading.Semaphore(_MAX_CONCURRENT_JOBS)


def job(name: str, fn) -> None:
    """Har bir botni shu wrapper orqali ishga tushiramiz — biror bot ichida kutilmagan
    xatolik chiqsa ham (kod xatosi, tarmoq muammosi va h.k.), scheduler butunlay
    to'xtab qolmaydi, faqat shu bot safar o'tkazib yuboriladi."""
    lock = _locks[name]
    if not lock.acquire(blocking=False):
        logger.warning("[%s] oldingi ishga tushirish hali tugamagan — bu safar o'tkazib yuboriladi.", name)
        return
    try:
        # Boshqa bot(lar) allaqachon ruxsat etilgan maksimal sonda ishlab turgan bo'lsa,
        # shu yerda NAVBATDA kutadi (o'tkazib yubormaydi) — operativ xotira nazoratda
        # qolishi uchun, HUB_MAX_CONCURRENT_JOBS qancha bo'lsa shuncha bot bir vaqtda
        # ishlaydi, qolganlari o'z navbatini kutadi.
        with _concurrency_semaphore:
            logger.info("[%s] ishga tushmoqda...", name)
            fn()
    except Exception:  # noqa: BLE001 - hub hech qachon shu sababdan to'xtamasligi kerak
        logger.exception("[%s] kutilmagan xatolik yuz berdi, keyingi safar qayta urinamiz.", name)
    else:
        logger.info("[%s] tugadi.", name)
    finally:
        lock.release()


def threaded_job(name: str, fn) -> None:
    """`job`ni alohida (orqa fon, daemon) ip-oqimda ishga tushiradi — shu bot uzoq
    band bo'lib qolsa ham (masalan tabiat boti ffmpeg bilan), scheduler'ning asosiy
    sikli (va shu bilan boshqa botlarning o'z vaqtida ishga tushishi) bloklanmaydi."""
    threading.Thread(target=job, args=(name, fn), name=f"bot-{name}", daemon=True).start()


def main() -> None:
    nature_interval = _env_int("NATURE_INTERVAL_MINUTES", 30)
    crypto_interval = _env_int("CRYPTO_INTERVAL_MINUTES", 60)
    football_interval = _env_int("FOOTBALL_INTERVAL_MINUTES", 60)  # standart: har soatda (trivia posti uchun)
    youtube_interval = _env_int("YOUTUBE_INTERVAL_MINUTES", 120)  # standart: har 2 soatda

    if os.getenv("NATURE_TELEGRAM_CHANNEL_ID"):
        schedule.every(nature_interval).minutes.do(threaded_job, "tabiat", run_nature)
        logger.info("Tabiat boti har %d daqiqada ishlaydi.", nature_interval)
    else:
        logger.info("Tabiat boti o'chirilgan (NATURE_TELEGRAM_CHANNEL_ID sozlanmagan).")

    if os.getenv("CRYPTO_TELEGRAM_CHANNEL_ID"):
        schedule.every(crypto_interval).minutes.do(threaded_job, "kripto", run_crypto)
        logger.info("Kripto boti har %d daqiqada ishlaydi.", crypto_interval)
    else:
        logger.info("Kripto boti o'chirilgan (CRYPTO_TELEGRAM_CHANNEL_ID sozlanmagan).")

    if os.getenv("FOOTBALL_TELEGRAM_CHANNEL_ID"):
        schedule.every(football_interval).minutes.do(threaded_job, "futbol", run_football)
        logger.info("Futbol boti har %d daqiqada ishlaydi.", football_interval)
    else:
        logger.info("Futbol boti o'chirilgan (FOOTBALL_TELEGRAM_CHANNEL_ID sozlanmagan).")

    if os.getenv("YOUTUBE_TELEGRAM_CHANNEL_ID"):
        schedule.every(youtube_interval).minutes.do(threaded_job, "youtube", run_youtube)
        logger.info("YouTube-repost boti har %d daqiqada ishlaydi.", youtube_interval)
    else:
        logger.info("YouTube-repost boti o'chirilgan (YOUTUBE_TELEGRAM_CHANNEL_ID sozlanmagan).")

    if not schedule.get_jobs():
        logger.error("Hech qanday bot sozlanmagan — .env faylini to'ldiring (README.md'ga qarang). To'xtatildi.")
        return

    # Ishga tushgan zahoti sozlangan botlarning har birini bir marta darhol (parallel,
    # bir-birini kutmasdan) ishga tushiramiz — navbatdagi intervalni kutib o'tirmasdan.
    for j in schedule.get_jobs():
        j.job_func()

    logger.info("Hub ishga tushdi, botlar o'z jadvali bo'yicha ishlaydi. To'xtatish uchun Ctrl+C.")
    while True:
        schedule.run_pending()
        time.sleep(15)


if __name__ == "__main__":
    main()
