"""
Video yuklab olish moduli (yt-dlp asosida).
"""
import logging
import os
import shutil
import time

import yt_dlp

log = logging.getLogger("trend_repost.downloader")

# Telegram Bot API orqali 50MB dan katta fayl yuborib bo'lmaydi
# (telegram_bot.py'dagi MAX_UPLOAD_BYTES). Shu limitdan biroz kichikroq
# fayl tanlash uchun format qidiruvda filesize chegarasi sifatida
# ishlatiladi — aks holda (ayniqsa uzun videolarda) yt-dlp eng yuqori
# sifatni tanlab, yuzlab MB fayl yuklab olishi mumkin, keyin esa Telegram
# uni rad etadi (behuda trafik va vaqt).
_MAX_UPLOAD_MB = 45

# Tarmoq bir joyda "osilib" qolsa (masalan YouTube sekinlashtirsa),
# cheksiz kutmasdan, shu vaqtdan keyin xato berib, keyingi videoga
# o'tish uchun. Oldin 30 sek + 5 marta retry edi — bu eng yomon holatda
# bitta muvaffaqiyatsiz video uchun ~150 soniyagacha "osilib qolish"ga
# olib kelardi. Botning umumiy sekinligiga shu ham hissa qo'shgani uchun
# pasaytirildi: haqiqatan ishlayotgan sekin yuklashlarga xalaqit
# bermaydi (progress_hooks orqali har 5 sekundda log chiqadi), lekin
# haqiqatan osilib qolgan ulanishni tezroq tashlab, keyingi nomzodga
# o'tadi.
_SOCKET_TIMEOUT_SEC = 15


class DownloadError(Exception):
    pass


def _make_progress_hook():
    """yt-dlp'ning o'z progress-barini yashirgan holda (quiet=True), lekin
    baribir vaqti-vaqti bilan bizning log formatimizda "hali ishlayapti,
    muzlab qolgani yo'q" degan xabar chiqarish uchun."""
    state = {"last_log": 0.0}

    def hook(d):
        status = d.get("status")
        if status == "downloading":
            now = time.monotonic()
            if now - state["last_log"] >= 5:
                pct = (d.get("_percent_str") or "").strip()
                speed = (d.get("_speed_str") or "").strip()
                eta = (d.get("_eta_str") or "").strip()
                log.info("Yuklanmoqda: %s (%s, ETA %s)", pct or "?", speed or "?", eta or "?")
                state["last_log"] = now
        elif status == "finished":
            log.info("Yuklab olindi, birlashtirilmoqda (agar kerak bo'lsa)...")

    return hook


def download_video(video_url: str, download_dir: str = "downloads",
                    cookies_file: str = None) -> str:
    """Berilgan URL'dagi videoni yuklab, lokal fayl yo'lini qaytaradi.

    Xato bo'lsa (video o'chirilgan, xususiy, mintaqaviy cheklangan,
    tarmoq uzilib ketgani va h.k.) DownloadError ko'taradi — chaqiruvchi
    kod bitta video muvaffaqiyatsiz bo'lsa ham davom eta olishi uchun.

    cookies_file: agar YouTube "sign in to confirm you're not a bot" kabi
        botga qarshi xato bersa, brauzerdan eksport qilingan cookies.txt
        fayl yo'lini shu yerga bering (masalan .env'dagi
        YTDLP_COOKIES_FILE orqali).

        MUHIM (tuzatilgan xato): yt-dlp har bir ishlatishdan keyin YouTube'ning
        yangilangan sessiya cookie'larini SHU FAYLGA QAYTA YOZISHGA urinadi.
        Agar `cookies_file` faqat-o'qish-uchun joyda bo'lsa (masalan Render'ning
        "Secret Files" — bu doim shunday, xavfsizlik uchun read-only), yozish
        urinishi "Read-only file system" xatosi bilan qulab tushardi va BUTUN
        botni to'xtatib qo'yardi (DownloadError sifatida ushlanmagani uchun).
        Shuning uchun bu funksiya cookie faylini avval YOZISH MUMKIN BO'LGAN
        joyga (download_dir ichiga) nusxalab, yt-dlp'ga o'sha nusxani beradi —
        asl (read-only) fayl hech qachon o'zgartirilmaydi/buzilmaydi.

    Format tanlash: avval Telegram limitidan (50MB) kichikroq (~45MB)
    fayl beradigan formatlar qidiriladi; agar YouTube bunday format uchun
    aniq hajm ma'lumotini bermasa (ba'zi formatlarda shunday), 480p
    balandlikka cheklangan formatga tushiladi — bu odatda uzun videolarni
    ham Telegram limiti ichida ushlab turadi.

    Tarmoq "osilib qolishi": har bir ulanish uchun ~15 soniyalik
    socket_timeout qo'yilgan — agar YouTube sekinlashtirsa/ulanish
    javob bermay qolsa, cheksiz kutish o'rniga xato beriladi va yt-dlp
    3 martagacha o'zining ichki retry mexanizmi bilan qayta uradi, oxiri
    baribir bo'lmasa DownloadError ko'tariladi (skript "muzlab qolmaydi").
    """
    os.makedirs(download_dir, exist_ok=True)

    format_selector = (
        f"bestvideo[filesize<{_MAX_UPLOAD_MB}M][ext=mp4]+bestaudio[filesize<10M][ext=m4a]/"
        f"best[filesize<{_MAX_UPLOAD_MB}M][ext=mp4]/"
        "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/"
        "best[height<=480][ext=mp4]/"
        "best[height<=480]/worst"
    )

    ydl_opts = {
        "format": format_selector,
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(download_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": _SOCKET_TIMEOUT_SEC,
        "retries": 3,
        "fragment_retries": 3,
        "progress_hooks": [_make_progress_hook()],
    }
    if cookies_file:
        try:
            writable_cookies = os.path.join(download_dir, "cookies_writable.txt")
            shutil.copyfile(cookies_file, writable_cookies)
            ydl_opts["cookiefile"] = writable_cookies
        except OSError as exc:
            log.warning("Cookie faylini yozish mumkin bo'lgan joyga nusxalab bo'lmadi (%s), cookiesiz davom etiladi: %s", cookies_file, exc)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            filepath = ydl.prepare_filename(info)
            # merge_output_format mp4 bo'lsa, kengaytma mp4'ga o'zgargan bo'lishi mumkin
            if not os.path.exists(filepath):
                root, _ = os.path.splitext(filepath)
                candidate = root + ".mp4"
                if os.path.exists(candidate):
                    filepath = candidate
            if not os.path.exists(filepath):
                raise DownloadError(f"Yuklangan fayl topilmadi: {filepath}")
            return filepath
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"yt-dlp video yuklay olmadi ({video_url}): {exc}") from exc
    except OSError as exc:
        # Masalan cookie faylini saqlashda kutilmagan fayl-tizimi xatosi (yt-dlp
        # __exit__ bosqichida) — DownloadError EMAS, lekin xuddi shunday: bitta
        # nomzod muvaffaqiyatsiz bo'lishi butun botni yiqitmasligi kerak.
        raise DownloadError(f"Fayl tizimi xatoligi ({video_url}): {exc}") from exc
