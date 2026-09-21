"""
Doimiy (persistent) ma'lumotlar papkasi — Render Persistent Disk bilan ishlash uchun.

MUAMMO: Render'da (va shunga o'xshash platformalarda) konteynerning fayl tizimi
ODDIY qayta ishga tushirishda (OOM restart, xato bo'lib qayta ko'tarilish) odatda
saqlanib qoladi, LEKIN har safar YANGI DEPLOY qilinganda (git push, "Manual Deploy")
konteyner BUTUNLAY yangidan yaratiladi va o'sha paytgacha yozilgan barcha fayllar
(topic_pool_cache.json, hub_schedule_state.json, window_state.json va h.k.)
YO'QOLADI. Natijada har deploydan keyin tabiat boti Wikipedia'dan 1000+ ta joyni
qaytadan so'rashga majbur bo'ladi — bu esa 429 (rate-limit) xavfini oshiradi va
ishga tushish vaqtini uzaytiradi.

YECHIM: Render Dashboard'da xizmatga bitta arzon Persistent Disk (masalan 1 GB)
ulab, uni biror papkaga (masalan /var/data) bog'lang, so'ng .env'da:

    HUB_DATA_DIR=/var/data

deb ko'rsating. Shundan keyin barcha kesh/holat fayllari o'sha diskka yoziladi va
DEPLOY QILINGANDA HAM saqlanib qoladi.

HUB_DATA_DIR ko'rsatilmasa (standart holat), hech narsa buzilmaydi — fayllar
avvalgidek loyihaning o'z papkalarida saqlanadi (masalan bots/nature/ ichida);
faqat bu holda deploy qilinganda kesh yo'qolishi mumkinligini bilib qo'ying.
"""
from __future__ import annotations

import os
from pathlib import Path


def get_data_dir(subfolder: str, default_dir: Path) -> Path:
    """
    `subfolder` uchun ma'lumotlar papkasini qaytaradi.

    HUB_DATA_DIR muhit o'zgaruvchisi berilgan bo'lsa: <HUB_DATA_DIR>/<subfolder>
    (Render Persistent Disk — deploy qilinganda ham saqlanadi).

    Aks holda: default_dir (masalan shu modul joylashgan papka — avvalgi xatti-harakat).
    """
    base = os.environ.get("HUB_DATA_DIR", "").strip()
    if not base:
        return default_dir

    target = Path(base) / subfolder
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Disk ulanmagan yoki yo'l noto'g'ri bo'lsa — jim tarzda eski papkaga qaytamiz,
        # bot butunlay ishdan to'xtab qolmasligi uchun.
        return default_dir
    return target
