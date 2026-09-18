"""
Ba'zi tashqi API'lar (masalan TheSportsDB — futbol boti uchun) vaqtni UTC formatida
beradi. Bu modul UTC sana+vaqtni MAHALLIY vaqtga o'tkazadi — kun chegarasidan
oshib/kamayib ketishini ham (masalan o'yin UTC 23:30'da bo'lsa, UTC+5'da bu ertangi
kunning 04:30'si bo'ladi) to'g'ri hisoblab.
"""
from datetime import datetime, timedelta


def utc_to_local(date_str: str, time_str: str, offset_hours: int) -> tuple[str, str]:
    """`date_str` — "YYYY-MM-DD", `time_str` — "HH:MM:SS" yoki "HH:MM" (ikkalasi ham
    UTC bo'yicha). Qaytaradi: (mahalliy_sana, mahalliy_vaqt) — ikkalasi ham xuddi shu
    formatda ("YYYY-MM-DD", "HH:MM"). Kiritilgan qiymatlar noto'g'ri formatda bo'lsa
    (parslab bo'lmasa), ValueError ko'taradi — chaqiruvchi shu holatni ushlab, asl
    (UTC) qiymat bilan davom etishi kerak."""
    time_str = time_str[:8]  # ba'zan "18:00:00+00:00" kabi qo'shimcha qism kelishi mumkin
    fmt = "%H:%M:%S" if time_str.count(":") == 2 else "%H:%M"
    dt_utc = datetime.strptime(f"{date_str} {time_str}", f"%Y-%m-%d {fmt}")
    dt_local = dt_utc + timedelta(hours=offset_hours)
    return dt_local.strftime("%Y-%m-%d"), dt_local.strftime("%H:%M")
