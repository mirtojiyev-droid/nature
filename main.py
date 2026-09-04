"""
Tabiat kanali uchun avtomatik post qiluvchi bot — "kunlik mavzu" rejimi.

Har ishga tushganda:
  1. Bugungi mavzuni (joyni) aniqlaydi — kun davomida bir xil joy qoladi, ertasiga yangisi
     tanlanadi (topics.py orqali Wikipedia'ning keng qidiruvidan avtomatik topilgan
     minglab joy ichidan, places.py'dagi qo'lda tuzilgan ro'yxat esa zaxira/seed sifatida).
  2. Bugun hali ishlatilmagan bitta "qirra"ni tanlaydi (facets.py: sharshara, sohil, tog',
     quyosh botishi, havodan ko'rinishi va h.k. — mavzuning turli go'zal qirralari).
  3. Pexels'dan shu joy + qirra bo'yicha avval VIDEO (asosiy kontent), so'ng RASM qidiradi.
  4. Wikipedia'dan joy haqida umumiy ma'lumot oladi (kun davomida bir marta, keshlanadi)
     va kerak bo'lsa o'zbek tiliga tarjima qiladi.
  5. Caption tayyorlab, kanalga videoni va rasmni (ikkalasini ham, topilsa) joylaydi.
  6. Qirrani "ishlatildi" deb belgilaydi.

Har 30 daqiqada bir ishga tushirish uchun scheduler.py'dan foydalaning (README.md'ga qarang).
"""
import html
import json
import logging
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from facets import FACETS, build_query_variants
from info_fetcher import InfoFetcher
from local_footage import find_local_video
from media_fetcher import MediaFetcher, download_file
from music_mixer import prepare_video_for_posting
from pixabay_fetcher import PixabayFetcher
from places import PLACES
from state import get_today_theme, mark_facet_used, pick_next_facet
from telegram_poster import TelegramPoster
from topics import get_topic_pool
from translator import translate_to_uzbek
from wikimedia_fetcher import WikimediaFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

SUMMARY_CACHE_FILE = Path(__file__).parent / "today_summary_cache.json"


def _get_cached_summary(theme: str, info: InfoFetcher, translate_enabled: bool) -> str | None:
    """Bir xil mavzu uchun Wikipedia ma'lumotini kun davomida (har 30 daqiqada) qayta-qayta
    so'ramaslik uchun keshlaydi — tezroq ishlaydi va ortiqcha tarmoq/tarjima so'rovlarining
    oldini oladi."""
    today = date.today().isoformat()
    cache = {}
    if SUMMARY_CACHE_FILE.exists():
        try:
            cache = json.loads(SUMMARY_CACHE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache = {}

    if cache.get("date") == today and cache.get("theme") == theme:
        return cache.get("summary")

    summary = info.fetch_summary(theme)
    if translate_enabled and summary:
        summary = translate_to_uzbek(summary)

    try:
        SUMMARY_CACHE_FILE.write_text(
            json.dumps({"date": today, "theme": theme, "summary": summary}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Summary keshini saqlab bo'lmadi: %s", exc)

    return summary


def build_caption(theme: str, facet_label: str, summary: str | None) -> str:
    # Telegram parse_mode="HTML" bilan yuborilgani uchun, dinamik matndagi &, <, >
    # kabi belgilar albatta escape qilinishi shart — aks holda Telegram "can't parse
    # entities" xatosi bilan butun postni rad etadi.
    theme_esc = html.escape(theme)
    facet_esc = html.escape(facet_label)
    header = f"🌍 <b>{theme_esc}</b> — {facet_esc}"
    if summary:
        sentences = summary.split(". ")
        short = ". ".join(sentences[:3]).strip()
        if not short.endswith("."):
            short += "."
        body = f"\n\n{html.escape(short)}"
    else:
        body = ""
    footer = "\n\n#tabiat #sayohat #dunyo #4K #nature #world"
    return header + body + footer


def _fetch_with_fallback(sources: list[tuple[str, callable]], variants: list[str], kind: str) -> tuple[str, str] | None:
    """Bir nechta qidiruv so'zi (eng aniqdan eng umumiyga) va bir nechta manba (Pexels,
    so'ng Pixabay) bo'yicha ketma-ket urinib ko'radi — birinchi topilgan natijani qaytaradi.
    Bu Pexels/Pixabay video kutubxonasi kichik bo'lgani uchun juda spetsifik so'rovlarda
    ko'pincha hech narsa topilmasligi muammosini hal qiladi.

    Qaytaradi: (manba_nomi, url) yoki hech narsa topilmasa None."""
    for query in variants:
        for name, fetch_fn in sources:
            url = fetch_fn(query)
            if url:
                logger.info("%s topildi — manba: %s, so'rov: '%s'", kind, name, query)
                return name, url
    logger.info("%s uchun hech qanday manba/so'rov birikmasida natija topilmadi.", kind)
    return None


def run_once() -> int:
    """Bitta postni tanlaydi va joylaydi. scheduler.py ichidan har 30 daqiqada chaqiriladi,
    yoki Task Scheduler/cron bilan qo'lda ham ishga tushirish mumkin."""
    load_dotenv()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    pexels_key = os.getenv("PEXELS_API_KEY")
    pixabay_key = os.getenv("PIXABAY_API_KEY")
    translate_enabled = os.getenv("TRANSLATE_TO_UZBEK", "true").lower() == "true"
    post_photo_too = os.getenv("POST_PHOTO_TOO", "true").lower() == "true"

    missing = [
        name
        for name, val in [
            ("TELEGRAM_BOT_TOKEN", bot_token),
            ("TELEGRAM_CHANNEL_ID", channel_id),
            ("PEXELS_API_KEY", pexels_key),
        ]
        if not val
    ]
    if missing:
        logger.error("Quyidagi .env sozlamalari yo'q: %s. README.md'ga qarang.", ", ".join(missing))
        return 1

    seed_places = [p["query"] for p in PLACES]
    pool = get_topic_pool(seed_places=seed_places)
    theme = get_today_theme(pool)

    facet_idx, facet = pick_next_facet(FACETS)
    variants = build_query_variants(theme, facet)
    logger.info("Bugungi mavzu: %s | Qirra: %s | Qidiruv variantlari: %s", theme, facet["label"], variants)

    media = MediaFetcher(pexels_key)
    pixabay = PixabayFetcher(pixabay_key) if pixabay_key else None
    wikimedia = WikimediaFetcher()  # API kalit shart emas, doim faol qo'shimcha manba
    info = InfoFetcher()

    def _video_sources(prefer_vertical: bool):
        # Pexels avval sinaladi (asosiy manba), Pixabay ikkinchi zaxira, Wikimedia Commons
        # esa uchinchi (har doim mavjud, kalit talab qilmaydi) zaxira — uchtasi birlashganda
        # video topilish ehtimoli yanada oshadi. Har birida natijalar sifat (o'lcham) bo'yicha
        # saralanib, eng yaxshisi tanlanadi.
        sources = [("Pexels", lambda q, pv=prefer_vertical: media.fetch_video(q, prefer_vertical=pv))]
        if pixabay:
            sources.append(("Pixabay", lambda q, pv=prefer_vertical: pixabay.fetch_video(q, prefer_vertical=pv)))
        sources.append(("Wikimedia Commons", lambda q, pv=prefer_vertical: wikimedia.fetch_video(q, prefer_vertical=pv)))
        return sources

    def _photo_sources(prefer_vertical: bool):
        sources = [("Pexels", lambda q, pv=prefer_vertical: media.fetch_photo(q, prefer_vertical=pv))]
        if pixabay:
            sources.append(("Pixabay", lambda q, pv=prefer_vertical: pixabay.fetch_photo(q, prefer_vertical=pv)))
        sources.append(("Wikimedia Commons", lambda q, pv=prefer_vertical: wikimedia.fetch_photo(q, prefer_vertical=pv)))
        return sources

    summary = _get_cached_summary(theme, info, translate_enabled)
    caption = build_caption(theme, facet["label"], summary)

    poster = TelegramPoster(bot_token, channel_id)

    # Video asosiy kontent hisoblanadi (foydalanuvchi so'ragani kabi), shuning uchun avval
    # videoni sinaymiz.
    #
    # 0-ustuvorlik: localfootage/ papkasida foydalanuvchi o'zi (masalan Shutterstock,
    # Envato Elements, iStock, Storyblocks, Motion Array kabi pullik kutubxonadan qonuniy
    # yuklab olib) joylagan, joriy so'rovga fayl nomi bo'yicha mos keladigan premium video
    # bo'lsa, u eng birinchi ishlatiladi (README.md'ga qarang — bu manba avtomatik
    # ulanmagan, chunki bunday kutubxonalar bepul API taklif qilmaydi va litsenziyasi
    # faqat qo'lda yuklab olishga ruxsat beradi).
    #
    # Mos lokal video topilmasa, avtomatik bepul manbalarga (Pexels/Pixabay/Wikimedia
    # Commons) o'tiladi: avval telefon ekraniga to'liq mos vertikal (portret, "short"
    # formatiga o'xshash) video qidiriladi — shunday videolar ko'proq topilishi/joylanishi
    # uchun. Vertikal hech narsa topilmasa, gorizontal (landscape, "uzun" format) bilan
    # qayta uriniladi — bo'sh qolgandan ko'ra shu ham yaxshi, lekin sifat baribir saralanadi.
    #
    # Ikkala holatda ham, video diskka tayyorlanadi/yuklab olinadi va ffmpeg orqali
    # Telegram uchun mos formatga keltiriladi hamda (topilsa) fon musiqasi qo'shiladi.
    video_posted = False

    local_video = find_local_video(variants, prefer_vertical=True)
    if local_video:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            final_path = tmp_path / "final_video.mp4"
            if prepare_video_for_posting(local_video, final_path):
                video_posted = poster.post_video_file(final_path, caption)
            else:
                video_posted = poster.post_video_file(local_video, caption)
            if not video_posted:
                logger.error("Lokal video (%s) joylashda xatolik.", local_video.name)

    if not video_posted:
        video_result = _fetch_with_fallback(_video_sources(True), variants, "Video (vertikal/telefon uchun)")
        if not video_result:
            video_result = _fetch_with_fallback(_video_sources(False), variants, "Video (gorizontal)")
        if video_result:
            source_name, video_url = video_result
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                # Manba URL'idagi kengaytmani saqlab qolamiz (masalan Wikimedia Commons'dan
                # .webm/.ogv kelishi mumkin) — shunda ffmpeg mavjud bo'lmagan taqdirda ham,
                # asl fayl to'g'ri kengaytma bilan joylanadi.
                url_suffix = Path(urlparse(video_url).path).suffix
                raw_path = tmp_path / f"raw_video{url_suffix or '.mp4'}"
                if download_file(video_url, raw_path):
                    final_path = tmp_path / "final_video.mp4"
                    if prepare_video_for_posting(raw_path, final_path):
                        video_posted = poster.post_video_file(final_path, caption)
                    else:
                        video_posted = poster.post_video_file(raw_path, caption)
                else:
                    # Diskka yuklab bo'lmasa, to'g'ridan-to'g'ri URL orqali joylashga
                    # urinamiz (musiqasiz, lekin postsiz qolgandan yaxshi).
                    video_posted = poster.post_video(video_url, caption)
                if not video_posted:
                    logger.error("'%s' (%s) uchun videoni joylashda xatolik.", theme, facet["label"])

    photo_posted = False
    if post_photo_too:
        photo_result = _fetch_with_fallback(_photo_sources(True), variants, "Rasm (vertikal/telefon uchun)")
        if not photo_result:
            photo_result = _fetch_with_fallback(_photo_sources(False), variants, "Rasm (gorizontal)")
        if photo_result:
            _, photo_url = photo_result
            photo_posted = poster.post_photo(photo_url, caption)
            if not photo_posted:
                logger.error("'%s' (%s) uchun rasmni joylashda xatolik.", theme, facet["label"])

    if video_posted or photo_posted:
        mark_facet_used(facet_idx)
        logger.info(
            "Muvaffaqiyatli joylandi: %s (%s) — video: %s, rasm: %s",
            theme,
            facet["label"],
            "ha" if video_posted else "yo'q",
            "ha" if photo_posted else "yo'q",
        )
        return 0

    logger.error("'%s' (%s) uchun na video, na rasm joylanmadi. Bu safar o'tkazib yuborildi.", theme, facet["label"])
    return 1


if __name__ == "__main__":
    sys.exit(run_once())
