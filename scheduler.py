"""
Botni DOIMIY (24/7) ishlab turadigan, HAR N DAQIQADA (.env'dagi POST_INTERVAL_MINUTES,
standart 30) avtomatik post joylaydigan qilib ishga tushiradi.

Bu skript to'xtamasdan ishlab turadi. VPS'da (Hetzner, DigitalOcean va h.k.) systemd
xizmati sifatida ishga tushirilishi uchun mo'ljallangan (README.md'ga qarang) — shunda
kompyuteringiz o'chirilgan bo'lsa ham kanal ishlashda davom etadi.

Windows'da ham sinab ko'rish uchun oddiy `python scheduler.py` bilan ishga tushirsa
bo'ladi, lekin doimiy ishlashi uchun terminal ochiq turishi kerak — 30 daqiqalik yuqori
chastota tufayli **VPS'ga joylash qat'iy tavsiya etiladi** (Windows Task Scheduler bilan
har 30 daqiqada ishga tushirish ham texnik jihatdan mumkin, lekin unchalik qulay emas).
"""
import logging
import os
import sys
import time

import schedule
from dotenv import load_dotenv

from main import run_once

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def job():
    logger.info("Rejalashtirilgan vaqt keldi, post joylanmoqda...")
    try:
        run_once()
    except Exception:  # noqa: BLE001 - scheduler hech qachon butunlay to'xtab qolmasligi kerak
        logger.exception("Postni joylashda kutilmagan xatolik yuz berdi, keyingi safar qayta urinamiz.")


def main() -> None:
    interval_minutes = int(os.getenv("POST_INTERVAL_MINUTES", "30"))
    schedule.every(interval_minutes).minutes.do(job)
    logger.info(
        "Scheduler ishga tushdi. Har %d daqiqada post joylanadi. To'xtatish uchun Ctrl+C.",
        interval_minutes,
    )

    # Ishga tushgan zahoti birinchi postni darhol joylaymiz (30 daqiqa kutib o'tirmasdan).
    job()

    while True:
        schedule.run_pending()
        time.sleep(15)


if __name__ == "__main__":
    main()
