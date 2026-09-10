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
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import fcntl
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


# Har bir bot uchun qulf fayli shu papkaga yoziladi (fcntl.flock — jarayonlar
# ORASIDA ham ishlaydi, oddiy threading.Lock'dan farqli — pastdagi job() funksiyasidagi
# izohga qarang).
_LOCK_DIR = Path(__file__).parent

# Bir vaqtning o'zida nechta bot ISHLASHI (fn() bajarilishi) mumkinligini cheklovchi
# umumiy semafor — operativ xotirani nazoratda ushlab turish uchun. Standart 1 =
# botlar hech qachon bir vaqtda ishlamaydi (kam xotirali serverlar uchun xavfsiz).
_MAX_CONCURRENT_JOBS = max(1, _env_int("HUB_MAX_CONCURRENT_JOBS", 1))
_concurrency_semaphore = threading.Semaphore(_MAX_CONCURRENT_JOBS)

# Har bir botning OXIRGI marta haqiqatan ishga tushirilgan vaqti shu faylga yoziladi
# (diskka, jarayon xotirasiga emas) — MUHIM: `schedule` kutubxonasining o'zi bu
# ma'lumotni faqat JARAYON XOTIRASIDA saqlaydi, ya'ni hub jarayoni QAYTA ISHGA
# TUSHGANDA (Render qayta deploy qilganda, yoki avval ko'rgan xotira yetishmasligi
# sababli avtomatik qayta ishga tushganda) bu holat YO'QOLADI — va hub "ishga tushgan
# zahoti barcha botlarni bir marta darhol ishga tushirish" mantig'i tufayli, HAR BIR
# qayta ishga tushishda barcha botlar QAYTADAN, oxirgi marta qachon ishlagani UMUMAN
# HISOBGA OLINMASDAN darhol ishga tushirilardi. Agar server tez-tez qayta ishga
# tushsa (masalan xotira muammosi tufayli), bu "botlar vaqtga qaramasdan, tasodifiy
# ishlayapti" bo'lib ko'rinishiga olib kelardi. Shu faylga yozib qo'yish orqali, qayta
# ishga tushgandan keyin ham hub "oxirgi marta qachon ishlaganini" biladi va shunga
# yarasha to'g'ri vaqtda keyingi ishga tushirishni rejalashtiradi.
_SCHEDULE_STATE_FILE = Path(__file__).parent / "hub_schedule_state.json"


def _load_last_run_times() -> dict:
    if not _SCHEDULE_STATE_FILE.exists():
        return {}
    try:
        return json.loads(_SCHEDULE_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Jadval holatini o'qib bo'lmadi, boshidan boshlanadi: %s", exc)
        return {}


def _save_last_run_time(name: str) -> None:
    state = _load_last_run_times()
    state[name] = time.time()
    try:
        _SCHEDULE_STATE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except OSError as exc:
        logger.warning("Jadval holatini saqlab bo'lmadi: %s", exc)


def job(name: str, fn) -> None:
    """Har bir botni shu wrapper orqali ishga tushiramiz — biror bot ichida kutilmagan
    xatolik chiqsa ham (kod xatosi, tarmoq muammosi va h.k.), scheduler butunlay
    to'xtab qolmaydi, faqat shu bot safar o'tkazib yuboriladi.

    MUHIM (tuzatilgan xato — ba'zida ikki marta post qilinishi): avval bu yerda faqat
    `threading.Lock` ishlatilardi — bu FAQAT bitta jarayon ICHIDA himoya qiladi. Render
    (yoki boshqa platforma) qayta deploy qilganda, ESKI va YANGI jarayon bir necha
    soniya BIR VAQTDA ishlab turishi mumkin — ikkalasi ham o'zining alohida xotirasida
    "men band emasman" deb o'ylab, ikkalasi ham bir xil botni ishga tushirib, IKKI
    MARTA bir xil narsani post qilib yuborishi mumkin edi. Shuning uchun endi jarayonlar
    ORASIDA ham ishlaydigan FAYL qulfi (`fcntl.flock`) ishlatiladi — ikkinchi jarayon
    qulfni ololmay, darhol (kutmasdan) o'zining urinishini bekor qiladi."""
    lock_path = _LOCK_DIR / f".{name}.lock"
    lock_file = open(lock_path, "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        logger.warning(
            "[%s] boshqa jarayon (yoki shu jarayonning oldingi ishga tushirishi) hali band — "
            "bu safar o'tkazib yuboriladi (masalan qayta deploy paytida eski/yangi jarayon "
            "bir zumga bir vaqtda ishlab turgan bo'lishi mumkin).",
            name,
        )
        lock_file.close()
        return
    try:
        # Ishga tushirish DARHOL (fn() hali navbatda kutayotgan bo'lsa ham) qayd etiladi
        # — schedule kutubxonasining o'zi ham "last_run"ni aynan shu daqiqada (chaqiruv
        # boshida, tugashini kutmasdan) belgilaydi, shu bilan izchil turish uchun.
        _save_last_run_time(name)
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
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def threaded_job(name: str, fn) -> None:
    """`job`ni alohida (orqa fon, daemon) ip-oqimda ishga tushiradi — shu bot uzoq
    band bo'lib qolsa ham (masalan tabiat boti ffmpeg bilan), scheduler'ning asosiy
    sikli (va shu bilan boshqa botlarning o'z vaqtida ishga tushishi) bloklanmaydi."""
    threading.Thread(target=job, args=(name, fn), name=f"bot-{name}", daemon=True).start()


def setup_schedule() -> bool:
    """Barcha yoqilgan botlarni `schedule`ga ro'yxatdan o'tkazadi va kerak bo'lsa
    darhol (yoki keyinroq, agar yaqinda ishlagan bo'lsa) ishga tushiradi. Kamida bitta
    bot sozlangan bo'lsa True, aks holda False qaytaradi (sinov uchun ham qulay —
    `main()`dagi cheksiz tsiklga kirmasdan alohida chaqirsa bo'ladi)."""
    bot_configs = [
        ("tabiat", "NATURE_TELEGRAM_CHANNEL_ID", "NATURE_INTERVAL_MINUTES", 30, run_nature, "Tabiat"),
        ("kripto", "CRYPTO_TELEGRAM_CHANNEL_ID", "CRYPTO_INTERVAL_MINUTES", 60, run_crypto, "Kripto"),
        ("futbol", "FOOTBALL_TELEGRAM_CHANNEL_ID", "FOOTBALL_INTERVAL_MINUTES", 60, run_football, "Futbol"),
        ("youtube", "YOUTUBE_TELEGRAM_CHANNEL_ID", "YOUTUBE_INTERVAL_MINUTES", 120, run_youtube, "YouTube-repost"),
    ]

    last_run_times = _load_last_run_times()
    now = time.time()
    scheduled_count = 0

    for name, channel_env, interval_env, default_interval, fn, label in bot_configs:
        if not os.getenv(channel_env):
            logger.info("%s boti o'chirilgan (%s sozlanmagan).", label, channel_env)
            continue

        interval = _env_int(interval_env, default_interval)
        j = schedule.every(interval).minutes.do(threaded_job, name, fn)
        scheduled_count += 1
        logger.info("%s boti har %d daqiqada ishlaydi.", label, interval)

        # MUHIM: agar bu bot yaqinda (o'z intervalidan kamroq vaqt oldin) allaqachon
        # ishlagan bo'lsa — bu ma'lumot oldingi (hozir qayta ishga tushgan) jarayon
        # ishidan qolgan bo'lishi mumkin — uni HOZIR yana darhol ishga tushirmaymiz,
        # aksincha, `schedule`ning navbatdagi ishga tushirish vaqtini ham shunga mos
        # ravishda TO'G'RILAYMIZ (registratsiya vaqtidan emas, aslida OXIRGI marta
        # ishlagan vaqtdan boshlab hisoblab). Shu bilan qayta-qayta ishga tushishlar
        # (masalan xotira muammosi tufayli) botlarni belgilangan jadvaldan tezroq-tezroq
        # ishga tushirib yubormaydi.
        last = last_run_times.get(name)
        if last is not None and (now - last) < interval * 60:
            next_run_at = datetime.fromtimestamp(last) + timedelta(minutes=interval)
            j.next_run = next_run_at
            remaining_min = (next_run_at.timestamp() - now) / 60
            logger.info(
                "  -> %s yaqinda (%.0f daqiqa oldin) allaqachon ishlagan (jarayon qayta ishga tushgan bo'lishi mumkin) — "
                "darhol emas, %.0f daqiqadan keyin ishga tushadi.",
                label, (now - last) / 60, remaining_min,
            )
        else:
            threaded_job(name, fn)

    return scheduled_count > 0


def main() -> None:
    if not setup_schedule():
        logger.error("Hech qanday bot sozlanmagan — .env faylini to'ldiring (README.md'ga qarang). To'xtatildi.")
        return

    logger.info("Hub ishga tushdi, botlar o'z jadvali bo'yicha ishlaydi. To'xtatish uchun Ctrl+C.")
    while True:
        schedule.run_pending()
        time.sleep(15)


if __name__ == "__main__":
    main()
