"""
Tabiat kanali uchun avtomatik post qiluvchi bot — "4 soatlik mavzu" rejimi.

Har ishga tushganda (30 daqiqada bir):
  1. Joriy 4 soatlik oynaning mavzusini (joyni) aniqlaydi — oyna davomida bir xil joy
     qoladi (shu oynada 8 marta, har biri turli qirra bilan post qilinadi), oyna
     tugagach yangisi tanlanadi (topics.py orqali Wikipedia'ning keng qidiruvidan
     avtomatik topilgan minglab joy ichidan, places.py'dagi qo'lda tuzilgan ro'yxat esa
     zaxira/seed sifatida).
  2. Joriy oynada hali ishlatilmagan bitta "qirra"ni tanlaydi (facets.py: sharshara,
     sohil, tog', quyosh botishi, havodan ko'rinishi va h.k. — mavzuning turli go'zal
     qirralari).
  3. Pexels'dan shu joy + qirra bo'yicha avval VIDEO (asosiy kontent, 4K'gacha), so'ng
     RASM qidiradi (Pexels -> Pixabay -> Wikimedia Commons ketma-ketligida).
  4. Caption tayyorlab (FAQAT joy nomi + qirra + hashteglar — pastga qarang), kanalga
     videoni va rasmni (ikkalasini ham, topilsa) joylaydi.
  5. Qirrani "ishlatildi" deb belgilaydi.

MUHIM (ataylab olib tashlangan xususiyat): avval caption'da Wikipedia'dan olingan
qisqacha ma'lumot (izoh) ham bo'lardi. Bu olib tashlandi — chunki ba'zan (masalan joy
nomi bilan bir xil nomdagi kino/qo'shiq bo'lsa) noto'g'ri ma'lumot berish xavfi bor edi.
Endi caption FAQAT joy nomi, qirra va hashteglar — hech qanday qo'shimcha matn yo'q,
demak bunday xato ham UMUMAN mumkin emas.

Bu modul mustaqil ishga tushirilishi ham mumkin (`python -m bots.nature.run`, hub papkasidan),
lekin odatiy holatda hub'ning `main.py`'si buni scheduler orqali chaqiradi (README.md'ga qarang).
"""
import html
import logging
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from .facets import FACETS, build_hashtags, build_query_variants
from .local_footage import find_local_video
from .media_fetcher import MediaFetcher, download_file
from .music_mixer import prepare_video_for_posting
from .pixabay_fetcher import PixabayFetcher
from .places import PLACES
from .state import get_current_theme, mark_facet_used, pick_next_facet
from shared.telegram_poster import TelegramPoster
from shared.hashtags import format_hashtags
from .topics import get_topic_pool
from .wikimedia_fetcher import WikimediaFetcher

logger = logging.getLogger(__name__)


def build_caption(theme: str, facet: dict) -> str:
    # Telegram parse_mode="HTML" bilan yuborilgani uchun, dinamik matndagi &, <, >
    # kabi belgilar albatta escape qilinishi shart — aks holda Telegram "can't parse
    # entities" xatosi bilan butun postni rad etadi.
    #
    # MUHIM (ataylab soddalashtirilgan): avval bu yerda Wikipedia'dan olingan qisqacha
    # ma'lumot (summary) ham qo'shilardi. LEKIN bu xavfli bo'lib chiqdi — Wikipedia
    # qidiruvi ba'zan noto'g'ri (masalan xuddi shu nomdagi kino/qo'shiq haqidagi)
    # maqolaga tushib qolishi mumkin edi (topics.py'dagi filtr tuzatilgan bo'lsa-da,
    # bunday xato boshqa ko'rinishda ham chiqishi mumkin). Shuning uchun endi caption
    # FAQAT joy nomi va qirra — hech qanday qo'shimcha matn/izoh yo'q, demak noto'g'ri
    # ma'lumot berish xavfi ham UMUMAN yo'q.
    theme_esc = html.escape(theme)
    facet_esc = html.escape(facet["label"])
    header = f"🌍 <b>{theme_esc}</b> — {facet_esc}"
    footer = "\n\n" + format_hashtags(build_hashtags(theme, facet))
    return header + footer


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

    bot_token = os.getenv("NATURE_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("NATURE_TELEGRAM_CHANNEL_ID")
    pexels_key = os.getenv("PEXELS_API_KEY")
    pixabay_key = os.getenv("PIXABAY_API_KEY")
    post_photo_too = os.getenv("NATURE_POST_PHOTO_TOO", "true").lower() == "true"

    missing = [
        name
        for name, val in [
            ("NATURE_TELEGRAM_BOT_TOKEN (yoki TELEGRAM_BOT_TOKEN)", bot_token),
            ("NATURE_TELEGRAM_CHANNEL_ID", channel_id),
            ("PEXELS_API_KEY", pexels_key),
        ]
        if not val
    ]
    if missing:
        logger.error("Quyidagi .env sozlamalari yo'q: %s. README.md'ga qarang.", ", ".join(missing))
        return 1

    seed_places = [p["query"] for p in PLACES]
    pool = get_topic_pool(seed_places=seed_places)
    theme = get_current_theme(pool)

    facet_idx, facet = pick_next_facet(FACETS)
    variants = build_query_variants(theme, facet)
    logger.info("Joriy mavzu: %s | Qirra: %s | Qidiruv variantlari: %s", theme, facet["label"], variants)

    media = MediaFetcher(pexels_key)
    pixabay = PixabayFetcher(pixabay_key) if pixabay_key else None
    wikimedia = WikimediaFetcher()  # API kalit shart emas, doim faol qo'shimcha manba

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

    caption = build_caption(theme, facet)

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
    # `python -m bots.nature.run` orqali mustaqil sinash uchun (hub papkasidan ishga
    # tushirilishi kerak, aks holda `shared` moduli topilmaydi).
    import sys
    sys.exit(run_once())
