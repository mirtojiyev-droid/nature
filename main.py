"""
Bot Hub — UCHTA mustaqil Telegram botni (tabiat, kripto, futbol) BITTA jarayonda,
bitta VPS'da, har biri o'z vaqt jadvali bilan ishlaydigan qilib boshqaradi.

Nega bitta jarayon: barchasi asosan tarmoq so'rovlari bilan band (CPU emas), shuning
uchun bitta kichik VPS'da (masalan 1 CPU / 1-2GB RAM) barchasi bemalol sig'adi — uchta
alohida serverga pul to'lash shart emas.

Har bir bot (`bots/nature`, `bots/crypto`, `bots/football`) TO'LIQ mustaqil:
o'zining bot tokeni, kanal ID'si va sozlamalariga ega (.env'da alohida prefikslar
bilan). Bittasi xato bersa ham (masalan Binance vaqtincha ishlamasa), boshqalari
ta'sirlanmaydi — har bir "job" o'zining try/except ichida ishlaydi.

MUHIM (ip-oqim/threading va operativ xotira haqide): har bir bot o'z ALOHIDA
ip-oqimida (thread) ishga tushiriladi, bittasi (masalan tabiat boti ffmpeg bilan)
bir necha daqiqa band bo'lishi mumkin, lekin bu ikkinchisini (masalan kripto botini,
aynan shu daqiqada post qilishi kerak bo'lgan) KECHIKTIRMAYDI.

LEKIN: agar bir nechta bot BIR VAQTDA ishlasa (masalan hub ishga tushgan zahoti, yoki
ikkita botning jadvali tasodifan bir xil daqiqaga to'g'ri kelib qolsa), ularning
operativ xotira sarfi QO'SHILIB ketadi — bu, ayniqsa Render/Railway kabi platformalarning
arzon tariflarida (odatda 512MB-1GB), "out of memory" xatosiga olib kelishi mumkin
(ffmpeg 4K video qayta kodlashda o'zi bir necha yuz
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
from bots.nature.schedule_config import NATURE_DAILY_SCHEDULE  # noqa: E402


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# MUHIM (foydalanuvchi bilan aniqlangan muammo): Render (va aksariyat bulut
# serverlari) soat mintaqasi sifatida UTC'ni ishlatadi — `schedule` kutubxonasi ham,
# `datetime.now()` ham serverning O'ZI ko'radigan (ya'ni UTC) vaqtni ishlatadi.
# `bots/nature/schedule_config.py`dagi vaqtlar esa ATAYLAB O'ZBEKISTON MAHALLIY
# VAQTIDA yozilgan (masalan "18:00" — mahalliy kechqurun, dengiz/yomg'ir kabi
# tinchlantiruvchi kontent uchun mo'ljallangan) — bu ikkisi orasidagi farq
# NATURE_TZ_OFFSET_HOURS orqali tuzatiladi (standart: 5 — O'zbekiston UTC+5).
# Agar serveringiz boshqa mintaqada joylashgan bo'lsa yoki hisob-kitobda xato
# bo'lsa, shu qiymatni .env'da osongina o'zgartirishingiz mumkin.
NATURE_TZ_OFFSET_HOURS = _env_int("NATURE_TZ_OFFSET_HOURS", 5)


def _shift_time_str(time_str: str, offset_hours: int) -> str:
    """"HH:MM" formatidagi MAHALLIY vaqtni serverning (UTC) soat ko'rsatkichiga
    o'tkazadi — masalan mahalliy "18:00" (UTC+5 bilan) serverda "13:00" bo'lib
    ro'yxatdan o'tkaziladi. Kun chegarasidan oshib/kamayib ketishi (masalan mahalliy
    "02:00" UTC+5'da avvalgi kunning "21:00"si bo'ladi) avtomatik hisobga olinadi."""
    h, m = map(int, time_str.split(":"))
    total_minutes = (h * 60 + m - offset_hours * 60) % (24 * 60)
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


# Har bir bot uchun qulf fayli shu papkaga yoziladi (fcntl.flock — jarayonlar
# ORASIDA ham ishlaydi, oddiy threading.Lock'dan farqli — pastdagi job() funksiyasidagi
# izohga qarang).
_LOCK_DIR = Path(__file__).parent

# Bir vaqtning o'zida nechta bot ISHLASHI (fn() bajarilishi) mumkinligini cheklovchi
# umumiy semafor — operativ xotirani nazoratda ushlab turish uchun. Standart 1 =
# kripto/futbol hech qachon bir vaqtda ishlamaydi (kam xotirali serverlar uchun xavfsiz).
#
# MUHIM (haqiqiy voqeada aniqlangan jiddiy xato): AVVAL bu BITTA semafor UCHALA botga
# (tabiat, kripto, futbol) ham umumiy edi. Amalda esa kripto boti CoinGecko'ning qattiq
# tezlik chegarasi tufayli 20-30+ daqiqa davom etishi mumkin — shu vaqt ichida u
# semaforni "ushlab" turadi. Agar aynan shu payt tabiat botining KUNLIK JADVALDAGI aniq
# vaqti (masalan 06:00) kelib qolsa, tabiat boti indamay NAVBATDA qolib ketardi — hatto
# soatlab! Va eng yomoni, "[tabiat] ishga tushmoqda..." logi ham semaforni OLGANDAN
# KEYIN chiqadi, shuning uchun bu holat logda umuman ko'rinmasdi ("tabiat boti
# ishlamayapti" bo'lib ko'rinardi, aslida faqat KUTIB turgan edi).
#
# Yechim: tabiat botiga ALOHIDA, faqat o'ziga tegishli semafor beriladi — u endi
# kripto/futbolni HECH QACHON kutmaydi (aynan tabiat botining ishi ANIQ VAQTGA bog'liq,
# kripto/futbol esa bir necha daqiqa kechiksa ham muammo emas). Kripto va futbol
# o'zaro hamon HUB_MAX_CONCURRENT_JOBS orqali cheklanadi.
_MAX_CONCURRENT_JOBS = max(1, _env_int("HUB_MAX_CONCURRENT_JOBS", 1))
_concurrency_semaphore = threading.Semaphore(_MAX_CONCURRENT_JOBS)
_nature_semaphore = threading.Semaphore(1)
_BOT_SEMAPHORES = {"tabiat": _nature_semaphore}

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
        # Har bir bot O'ZIGA mos semaforni ishlatadi — tabiat boti ALOHIDA (hech qachon
        # kripto/futbolni kutmaydi), kripto/futbol esa umumiy semaforni bo'lishadi
        # (HUB_MAX_CONCURRENT_JOBS orqali cheklanadi). Batafsil sabab uchun yuqoridagi
        # semafor e'lonlaridagi izohga qarang.
        sem = _BOT_SEMAPHORES.get(name, _concurrency_semaphore)
        # MUHIM (diagnostika uchun tuzatilgan): avval "[name] ishga tushmoqda..." logi
        # semaforni OLGANDAN KEYIN chiqardi — agar bot navbatda kutayotgan bo'lsa, bu
        # kutish logda UMUMAN ko'rinmasdi. Endi navbatda turish HAM aniq ko'rinadi.
        if not sem.acquire(blocking=False):
            logger.info("[%s] boshqa bot band, navbatda kutilmoqda...", name)
            sem.acquire()
        try:
            logger.info("[%s] ishga tushmoqda...", name)
            fn()
        finally:
            sem.release()
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
    ]

    last_run_times = _load_last_run_times()
    now = time.time()
    scheduled_count = 0

    for name, channel_env, interval_env, default_interval, fn, label in bot_configs:
        if not os.getenv(channel_env):
            logger.info("%s boti o'chirilgan (%s sozlanmagan).", label, channel_env)
            continue

        # MUHIM (foydalanuvchi bilan kelishilgan o'sish rejasi): tabiat boti standart
        # bo'yicha endi har 30 daqiqada (kuniga 48 marta) emas, balki KUNLIK,
        # kategoriya-vaqtga bog'langan jadval bo'yicha (kuniga 12 marta, har biri aniq
        # vaqtda va aniq mavzu turida — bots/nature/schedule_config.py) ishlaydi. Buni
        # o'chirib, eski (interval-based) rejimga qaytish uchun .env'da
        # NATURE_USE_DAILY_SCHEDULE=false qiling.
        if name == "tabiat" and os.getenv("NATURE_USE_DAILY_SCHEDULE", "true").lower() == "true":
            # MUHIM: schedule_config.py'dagi vaqtlar MAHALLIY vaqtda yozilgan, lekin
            # `schedule` kutubxonasi serverning (UTC) soatini ishlatadi — shuning uchun
            # ro'yxatdan o'tkazishdan oldin har birini _shift_time_str() bilan UTC'ga
            # aylantiramiz (NATURE_TZ_OFFSET_HOURS orqali).
            server_schedule = [
                (_shift_time_str(t, NATURE_TZ_OFFSET_HOURS), fk) for t, fk in NATURE_DAILY_SCHEDULE
            ]
            for server_time_str, facet_key in server_schedule:
                schedule.every().day.at(server_time_str).do(
                    threaded_job, name, lambda fk=facet_key: run_nature(forced_facet_key=fk)
                )
            scheduled_count += 1
            logger.info(
                "%s boti KUNLIK jadval bo'yicha ishlaydi (kuniga %d marta, mahalliy vaqt (UTC+%d): %s).",
                label, len(NATURE_DAILY_SCHEDULE), NATURE_TZ_OFFSET_HOURS,
                ", ".join(f"{t} {k}" for t, k in NATURE_DAILY_SCHEDULE),
            )

            # MUHIM (foydalanuvchi savoli asosida aniqlangan va tuzatilgan kamchilik):
            # yuqoridagi `schedule.every().day.at(...)` FAQAT KELAJAKDAGI eng yaqin
            # vaqtni rejalashtiradi. Agar jarayon aynan bir jadval vaqtidan (masalan
            # 08:00) SAL KEYIN qayta ishga tushsa (Render qayta deploy qildi, yoki
            # xotira sababli avtomatik restart bo'ldi) va ESKI jarayon 08:00'ni hali
            # ulgurmagan bo'lsa — bu post hech qachon joylanmasdan, to'g'ridan-to'g'ri
            # ERTANGI 08:00'gacha "yo'qolib" qolardi (chunki eng yaqin kelajakdagi 08:00
            # — bu ertaga). Kripto/futbolda bu muammo yo'q edi, chunki ular pastdagi
            # "yaqinda ishlaganmi" tekshiruvidan o'tadi — lekin tabiat undan oldin
            # `continue` bilan chiqib ketardi. Endi: bugungi eng so'nggi "o'tib ketgan"
            # jadval vaqtini topamiz (SERVER/UTC vaqtida, `now_dt` ham server vaqti
            # bo'lgani uchun), va agar tabiat o'sha vaqtdan beri ISHLAMAGAN bo'lsa
            # (last_run_times orqali — bu ham diskka yozilgani uchun qayta ishga
            # tushishlar orasida saqlanadi), DARHOL o'sha vaqtning qirrasi bilan bir
            # marta (o'tkazib yubormaslik uchun) ishga tushiramiz.
            now_dt = datetime.now()
            passed_today = [
                (datetime.combine(now_dt.date(), datetime.strptime(t, "%H:%M").time()), fk)
                for t, fk in server_schedule
                if datetime.combine(now_dt.date(), datetime.strptime(t, "%H:%M").time()) <= now_dt
            ]
            if passed_today:
                latest_slot_dt, latest_facet_key = max(passed_today, key=lambda x: x[0])
                last = last_run_times.get(name)
                if last is None or datetime.fromtimestamp(last) < latest_slot_dt:
                    logger.info(
                        "  -> %s eng so'nggi jadval vaqti (server/UTC %s, qirra: %s) o'tkazib yuborilgan "
                        "bo'lishi mumkin (jarayon qayta ishga tushgan) — darhol shu qirra bilan bir marta "
                        "ishga tushiriladi.",
                        label, latest_slot_dt.strftime("%H:%M"), latest_facet_key,
                    )
                    threaded_job(name, lambda fk=latest_facet_key: run_nature(forced_facet_key=fk))
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
