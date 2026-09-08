"""
Bot Hub — uchta mustaqil Telegram botni (tabiat, kripto, futbol) BITTA jarayonda,
bitta VPS'da, har biri o'z vaqt jadvali bilan ishlaydigan qilib boshqaradi.

Nega bitta jarayon: uchtasi ham asosan tarmoq so'rovlari bilan band (CPU emas), shuning
uchun bitta kichik VPS'da (masalan 1 CPU / 1-2GB RAM) barchasi bemalol sig'adi — uchta
alohida serverga pul to'lash shart emas.

Har bir bot (`bots/nature`, `bots/crypto`, `bots/football`) TO'LIQ mustaqil: o'zining
bot tokeni, kanal ID'si va sozlamalariga ega (.env'da alohida prefikslar bilan). Bittasi
xato bersa ham (masalan Binance vaqtincha ishlamasa), boshqalari ta'sirlanmaydi — har bir
"job" o'zining try/except ichida ishlaydi.

MUHIM (ip-oqim/threading haqida): har bir bot o'z ALOHIDA ip-oqimida (thread) ishga
tushiriladi, bittasi (masalan tabiat boti, ffmpeg bilan video qayta kodlab, bir necha
daqiqa band bo'lishi mumkin) ikkinchisini (masalan kripto botini, aynan shu daqiqada post
qilishi kerak bo'lgan) KECHIKTIRMASLIGI uchun. Har bir botning o'zi uchun alohida qulf
(Lock) bor — shu bot allaqachon ishlab turgan bo'lsa (masalan oldingi ishga tushirish hali
tugamagan bo'lsa), shu bot safar shunchaki o'tkazib yuboriladi (ikkita nusxasi bir vaqtda
ishlab, bir xil faylni ustma-ust yozib qo'ymasligi uchun) — lekin bu boshqa botlarga
ta'sir qilmaydi.

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


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Har bir bot uchun alohida qulf — bitta botning ikkita nusxasi BIR VAQTDA ishlab
# ketmasligi uchun (masalan interval juda qisqa qilib qo'yilsa-yu, oldingi ishga
# tushirish hali tugamagan bo'lsa). Turli botlar bir-birining qulfiga tegmaydi, shuning
# uchun parallel ishlashda davom etadi.
_locks = {"tabiat": threading.Lock(), "kripto": threading.Lock(), "futbol": threading.Lock()}


def job(name: str, fn) -> None:
    """Har bir botni shu wrapper orqali ishga tushiramiz — biror bot ichida kutilmagan
    xatolik chiqsa ham (kod xatosi, tarmoq muammosi va h.k.), scheduler butunlay
    to'xtab qolmaydi, faqat shu bot safar o'tkazib yuboriladi."""
    lock = _locks[name]
    if not lock.acquire(blocking=False):
        logger.warning("[%s] oldingi ishga tushirish hali tugamagan — bu safar o'tkazib yuboriladi.", name)
        return
    try:
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
    football_interval = _env_int("FOOTBALL_INTERVAL_MINUTES", 240)  # standart: har 4 soatda

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
