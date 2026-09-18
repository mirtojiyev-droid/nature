"""
Tabiat kanali uchun avtomatik post qiluvchi bot.

Standart holatda KUNLIK, kategoriya-vaqtga bog'langan jadval bo'yicha ishlaydi (kuniga
12 marta, har biri aniq vaqtda va aniq "qirra" — sharshara, sohil, quyosh botishi va
h.k. — bilan; bots/nature/schedule_config.py'ga qarang, main.py orqali chaqiriladi).
Eski (tasodifiy, 30 daqiqalik interval) rejimga `.env`dagi NATURE_USE_DAILY_SCHEDULE=false
orqali qaytish mumkin.

Har bir ishga tushirishda:
  1. Joriy 4 soatlik oynaning mavzusini (joyni) aniqlaydi — oyna davomida bir xil joy
     qoladi (topics.py orqali Wikipedia'ning keng qidiruvidan avtomatik topilgan
     minglab joy ichidan; places.py'dagi qo'lda tuzilgan ro'yxat zaxira/seed sifatida).
  2. Qirrani aniqlaydi — kunlik jadval rejimida `forced_facet_key` orqali BELGILAB
     beriladi (masalan "06:00 -> sunrise"), eski rejimda esa navbat bilan tasodifiy
     tanlanadi (facets.py).
  3. FAQAT Pixabay'dan (foydalanuvchi qarori — Pexels butunlay olib tashlangan) shu
     joy + qirra bo'yicha avval VIDEO, so'ng RASM qidiradi (Pixabay -> Wikimedia
     Commons zaxira sifatida). Video uchun bir nechta nomzod ketma-ket sinaladi —
     birinchisi yuklab bo'lmasa yoki sifat nazoratidan (bo'sh/qora kadr, ffmpeg qayta
     ishlash) o'tmasa, keyingisiga o'tiladi (_find_and_prepare_video()).
  4. Caption tayyorlab (FAQAT joy nomi + hashteglar — qirra caption'da UMUMAN
     ko'rinmaydi, faqat qidiruv/hashteg uchun ICHKI ishlatiladi), video/rasmga "pro"
     brendlash (joy nomi + kanal belgisi) qo'shib, kanalga joylaydi.
  5. Qirrani "ishlatildi" deb belgilaydi (eski, tasodifiy rejim uchun muhim).

MUHIM (ataylab olib tashlangan xususiyat): caption'da Wikipedia'dan olingan qisqacha
ma'lumot (izoh) YO'Q — bunday matn ba'zan (masalan joy nomi bilan bir xil nomdagi
kino/qo'shiq bo'lsa) noto'g'ri ma'lumot berish xavfini tug'dirar edi. Caption FAQAT
joy nomi va hashteglar — hech qanday qo'shimcha matn yo'q.

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

from .facets import FACETS, FACETS_BY_KEY, build_hashtags, build_query_variants
from .local_footage import find_local_video
from .media_fetcher import download_bytes, download_file
from .music_mixer import prepare_video_for_posting
from .photo_overlay import add_branding_overlay
from .content_quality import is_blank_image_bytes, is_blank_video_file
from .pexels_fetcher import PexelsFetcher
from .pixabay_fetcher import PixabayFetcher
from .places import PLACES
from .state import get_current_theme, increment_and_get_post_count, mark_facet_used, pick_next_facet
from shared.telegram_poster import TelegramPoster
from shared.hashtags import format_hashtags
from .topics import get_place_category, get_topic_pool
from .wikimedia_fetcher import WikimediaFetcher

logger = logging.getLogger(__name__)


def build_caption(theme: str, facet: dict, include_follow_reminder: bool = False) -> str:
    # Telegram parse_mode="HTML" bilan yuborilgani uchun, dinamik matndagi &, <, >
    # kabi belgilar albatta escape qilinishi shart — aks holda Telegram "can't parse
    # entities" xatosi bilan butun postni rad etadi.
    #
    # MUHIM (foydalanuvchi so'rovi bilan yakuniy soddalashtirilgan): avval sarlavhada
    # qirra nomi ham ko'rinardi ("Joy nomi — sharsharasi" kabi). Endi HECH QANDAY
    # qo'shimcha izoh/matn yo'q — FAQAT joy nomi. Qirra endi faqat (1) qidiruv so'zini
    # tanlashda va (2) hashteg ro'yxatini boyitishda ICHKI ishlatiladi, caption'da
    # umuman ko'rinmaydi. Bu ham eng sodda, ham eng xavfsiz variant (Wikipedia'dan
    # noto'g'ri ma'lumot kelish xavfi ilgari olib tashlangan edi; endi qo'shimcha
    # matn umuman yo'qligi uchun bunday xavf tag'in ham yo'q).
    theme_esc = html.escape(theme)
    header = f"🌍 <b>{theme_esc}</b>"
    footer = "\n\n" + format_hashtags(build_hashtags(theme, facet))
    # MUHIM (foydalanuvchi ikkilanishi bilan): "faqat nomi, boshqa hech narsa
    # yozilmasin" degan qat'iy ko'rsatmangizga ATAYLAB ziddiyatga kirmaslik uchun, bu
    # qo'shimcha qator STANDART HOLATDA O'CHIRILGAN (NATURE_FOLLOW_REMINDER_EVERY_N=0).
    # Faqat o'zingiz .env'da yoqsangiz (masalan =5 — har 5-postda bir marta) qo'shiladi.
    reminder = "\n\n🔔 Follow for more" if include_follow_reminder else ""
    return header + reminder + footer


def _find_and_prepare_video(sources: list[tuple[str, callable]], variants: list[str],
                             tmp_path: Path, theme: str) -> Path | None:
    """Har bir manba/so'rov birikmasi uchun BIR NECHTA nomzod (fetch_video_candidates)
    oladi, va har birini KETMA-KET: yuklab olish -> bo'sh/qora kadr tekshiruvi ->
    ffmpeg orqali Telegram uchun mos formatga o'tkazish (+ topilsa musiqa, +
    brendlash) bosqichlaridan o'tkazadi. Birinchi nomzod istalgan bosqichda muvaffaqiyatsiz bo'lsa (yuklanmadi,
    bo'sh ekan, yoki ffmpeg qayta ishlay olmadi), RO'YXATDAGI KEYINGI nomzodga o'tadi —
    faqat BITTA muammoli fayl tufayli butun post video'siz (faqat rasm bilan)
    qolib ketmasligi uchun (foydalanuvchi so'rovi).

    Muvaffaqiyatli bo'lsa, Telegram'ga joylashga tayyor YAKUNIY (qayta ishlangan)
    fayl yo'lini qaytaradi. Hech qanday nomzod (barcha manba/so'rov/nomzod
    birikmalari orasidan) sifat nazoratidan o'ta olmasa, None qaytaradi — bu holatda
    run_once() video'siz, faqat rasm bilan davom etadi (postsiz qolishdan yaxshi)."""
    attempt = 0
    for query in variants:
        for source_name, fetch_candidates_fn in sources:
            candidate_urls = fetch_candidates_fn(query)
            for video_url in candidate_urls:
                attempt += 1
                url_suffix = Path(urlparse(video_url).path).suffix
                raw_path = tmp_path / f"raw_{attempt}{url_suffix or '.mp4'}"
                if not download_file(video_url, raw_path):
                    logger.warning("'%s' manbasidan video (so'rov: '%s') yuklab olinmadi - keyingi nomzod sinaladi.", source_name, query)
                    continue
                if is_blank_video_file(raw_path):
                    logger.warning("'%s' manbasidan video (so'rov: '%s') bo'sh/qora ekan - keyingi nomzod sinaladi.", source_name, query)
                    continue
                final_path = tmp_path / f"final_{attempt}.mp4"
                if prepare_video_for_posting(raw_path, final_path, location_text=theme):
                    logger.info(
                        "Video topildi, sifat nazoratidan o'tdi va tayyorlandi — manba: %s, so'rov: '%s' (%d-nomzod).",
                        source_name, query, attempt,
                    )
                    return final_path
                logger.warning(
                    "'%s' manbasidan video (so'rov: '%s') ffmpeg orqali qayta ishlanmadi - keyingi nomzod sinaladi.",
                    source_name, query,
                )
    logger.info("Hech qanday video nomzodi sifat nazoratidan o'ta olmadi (%d ta nomzod sinaldi).", attempt)
    return None


def _find_and_prepare_photo(sources: list[tuple[str, callable]], variants: list[str],
                             theme: str, brand_label: str) -> bytes | None:
    """`_find_and_prepare_video`bilan bir xil mantiq, faqat rasm uchun: har bir manba/
    so'rov birikmasidan bir nechta nomzod olib, har birini KETMA-KET: xotiraga yuklash
    -> bo'sh/bir xil rangli tekshiruvi -> brendlash overlay chizish bosqichlaridan
    o'tkazadi. Birinchi nomzod muvaffaqiyatsiz bo'lsa, keyingisiga o'tadi. Muvaffaqiyatli
    bo'lsa, Telegram'ga joylashga tayyor (overlay bilan) rasm baytlarini qaytaradi."""
    for query in variants:
        for source_name, fetch_candidates_fn in sources:
            candidate_urls = fetch_candidates_fn(query)
            for photo_url in candidate_urls:
                photo_bytes = download_bytes(photo_url)
                if not photo_bytes:
                    logger.warning("'%s' manbasidan rasm (so'rov: '%s') yuklab olinmadi - keyingi nomzod sinaladi.", source_name, query)
                    continue
                if is_blank_image_bytes(photo_bytes):
                    logger.warning("'%s' manbasidan rasm (so'rov: '%s') bo'sh/bir xil rangdan iborat - keyingi nomzod sinaladi.", source_name, query)
                    continue
                overlaid = add_branding_overlay(photo_bytes, theme, brand_label)
                result = overlaid or photo_bytes
                logger.info("Rasm topildi va tayyorlandi — manba: %s, so'rov: '%s'.", source_name, query)
                return result
    logger.info("Hech qanday rasm nomzodi sifat nazoratidan o'ta olmadi.")
    return None


def run_once(forced_facet_key: str | None = None) -> int:
    """Bitta postni tanlaydi va joylaydi. scheduler.py ichidan chaqiriladi (standart:
    kunlik kategoriya-vaqt jadvali bo'yicha — bots/nature/schedule.py'ga qarang), yoki
    Task Scheduler/cron bilan qo'lda ham ishga tushirish mumkin.

    `forced_facet_key` berilsa (masalan "sunrise", "wildlife" — facets.py'dagi FACETS
    ro'yxatidagi "key" maydoniga mos), oddiy tasodifiy/navbat bilan qirra tanlash
    ATLAB QILINADI — kunlik jadval ("06:00 -> sunrise, 08:00 -> wildlife" kabi) shu
    orqali ishlaydi. Joy (theme) esa BARIBIR odatdagi 4 soatlik oyna mantig'i bo'yicha
    tanlanadi — faqat qirra (mavzuning "qaysi tomoni" ko'rsatilishi) qat'iy belgilanadi."""
    load_dotenv()

    bot_token = os.getenv("NATURE_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("NATURE_TELEGRAM_CHANNEL_ID")
    pixabay_key = os.getenv("PIXABAY_API_KEY")
    pexels_key = os.getenv("PEXELS_API_KEY")
    post_photo_too = os.getenv("NATURE_POST_PHOTO_TOO", "true").lower() == "true"

    missing = [
        name
        for name, val in [
            ("NATURE_TELEGRAM_BOT_TOKEN (yoki TELEGRAM_BOT_TOKEN)", bot_token),
            ("NATURE_TELEGRAM_CHANNEL_ID", channel_id),
            ("PIXABAY_API_KEY", pixabay_key),
        ]
        if not val
    ]
    if missing:
        logger.error("Quyidagi .env sozlamalari yo'q: %s. README.md'ga qarang.", ", ".join(missing))
        return 1

    seed_places = [p["query"] for p in PLACES]
    pool = get_topic_pool(seed_places=seed_places)
    theme = get_current_theme(pool)

    if forced_facet_key:
        facet = FACETS_BY_KEY.get(forced_facet_key)
        if not facet:
            logger.error("Noma'lum forced_facet_key: %r. facets.py'dagi FACETS_BY_KEY'ga qarang.", forced_facet_key)
            return 1
        facet_idx = FACETS.index(facet)
        logger.info("Kunlik jadval bo'yicha qirra belgilandi: %s", facet["label"])
    else:
        facet_idx, facet = pick_next_facet(FACETS)
    variants = build_query_variants(theme, facet, fallback_category=get_place_category(theme))
    logger.info("Joriy mavzu: %s | Qirra: %s | Qidiruv variantlari: %s", theme, facet["label"], variants)

    # MUHIM (foydalanuvchi tarixi): dastlab Pexels butunlay olib tashlangan edi
    # (Pixabay'ni qo'lda solishtirib, ko'proq yoqqani uchun). Keyinroq foydalanuvchi
    # Pexels'dagi videolar ham chiroyli chiqayotganini va Pixabay ba'zan (ayniqsa
    # noyob joy nomlari uchun) yetarli natija bermayotganini payqab, Pexels'ni
    # QO'SHIMCHA (ikkinchi, Pixabay'dan KEYIN sinaladigan) manba sifatida qaytarishni
    # so'radi. Endi tartib: Pixabay (asosiy) -> Pexels (qo'shimcha, agar kalit
    # sozlangan bo'lsa) -> Wikimedia Commons (oxirgi, kalitsiz zaxira).
    pixabay = PixabayFetcher(pixabay_key)
    pexels = PexelsFetcher(pexels_key) if pexels_key else None
    wikimedia = WikimediaFetcher()  # API kalit shart emas, doim faol qo'shimcha manba

    def _video_sources(prefer_vertical: bool):
        # MUHIM: endi `fetch_video` (bitta URL) o'rniga `fetch_video_candidates`
        # (bir nechta URL ro'yxati) ishlatiladi — pastdagi `_find_and_prepare_video()`
        # birinchi nomzod yuklab bo'lmasa yoki sifat nazoratidan o'tmasa, RO'YXATDAGI
        # KEYINGI nomzodni avtomatik sinab ko'radi (foydalanuvchi so'rovi: "topgan va
        # tekshiruvdan o'tgan videoni yuklay olmasa, boshqasini qidirsin").
        sources = [("Pixabay", lambda q, pv=prefer_vertical: pixabay.fetch_video_candidates(q, prefer_vertical=pv))]
        if pexels:
            sources.append(("Pexels", lambda q, pv=prefer_vertical: pexels.fetch_video_candidates(q, prefer_vertical=pv)))
        sources.append(("Wikimedia Commons", lambda q, pv=prefer_vertical: wikimedia.fetch_video_candidates(q, prefer_vertical=pv)))
        return sources

    def _photo_sources(prefer_vertical: bool):
        sources = [("Pixabay", lambda q, pv=prefer_vertical: pixabay.fetch_photo_candidates(q, prefer_vertical=pv))]
        if pexels:
            sources.append(("Pexels", lambda q, pv=prefer_vertical: pexels.fetch_photo_candidates(q, prefer_vertical=pv)))
        sources.append(("Wikimedia Commons", lambda q, pv=prefer_vertical: wikimedia.fetch_photo_candidates(q, prefer_vertical=pv)))
        return sources

    # Follow-eslatma — standart holatda O'CHIRILGAN (0), foydalanuvchi ongli ravishda
    # .env'da yoqishi kerak (masalan =5 — har 5-postda bir marta). Bu — "faqat joy
    # nomi, boshqa hech narsa yozilmasin" degan qat'iy ko'rsatmaga hurmat yuzasidan
    # ataylab shunday qilingan (majburan yoqilmagan).
    try:
        reminder_every_n = int(os.getenv("NATURE_FOLLOW_REMINDER_EVERY_N", "0"))
    except ValueError:
        reminder_every_n = 0
    include_reminder = False
    if reminder_every_n > 0:
        post_count = increment_and_get_post_count()
        include_reminder = (post_count % reminder_every_n == 0)

    caption = build_caption(theme, facet, include_follow_reminder=include_reminder)

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
    # Mos lokal video topilmasa, avtomatik bepul manbalarga (Pixabay/Wikimedia
    # Commons) o'tiladi: avval telefon ekraniga to'liq mos vertikal (portret, "short"
    # formatiga o'xshash) video qidiriladi — shunday videolar ko'proq topilishi/joylanishi
    # uchun. Vertikal hech narsa topilmasa, gorizontal (landscape, "uzun" format) bilan
    # qayta uriniladi — bo'sh qolgandan ko'ra shu ham yaxshi, lekin sifat baribir saralanadi.
    #
    # Ikkala holatda ham, video diskka tayyorlanadi/yuklab olinadi va ffmpeg orqali
    # Telegram uchun mos formatga keltiriladi hamda (topilsa) fon musiqasi qo'shiladi.
    video_posted = False

    local_video = find_local_video(variants, prefer_vertical=True)
    if local_video and not is_blank_video_file(local_video):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            final_path = tmp_path / "final_video.mp4"
            if prepare_video_for_posting(local_video, final_path, location_text=theme):
                video_posted = poster.post_video_file(final_path, caption)
                if not video_posted:
                    logger.error("Lokal video (%s) joylashda xatolik.", local_video.name)
            else:
                # MUHIM (foydalanuvchi tomonidan aniqlangan muammo — haqiqiy misolda
                # ko'rilgan): avval qayta ishlash (ffmpeg) muvaffaqiyatsiz bo'lsa, XOM
                # (original) fayl to'g'ridan-to'g'ri joylanardi. Bu — sifat nazoratini
                # butunlay chetlab o'tish degani: xom fayl noma'lum formatda (masalan
                # .webm) bo'lishi mumkin, Telegram mobil ilovasi buni o'ynatib
                # bo'lmaydigan oddiy FAYL (hujjat) sifatida ko'rsatib qo'yadi — bu esa
                # "pro" kanalning ko'rinishini butunlay buzadi. Endi bunday holatda
                # video UMUMAN JOYLANMAYDI (postsiz qolish, o'ynatib bo'lmaydigan xom
                # fayl joylashdan ancha yaxshi).
                logger.warning("Lokal video (%s) ffmpeg orqali qayta ishlanmadi - sifat nazoratidan o'tmagani uchun JOYLANMAYDI.", local_video.name)

    if not video_posted:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            final_path = _find_and_prepare_video(_video_sources(True), variants, tmp_path, theme)
            if not final_path:
                final_path = _find_and_prepare_video(_video_sources(False), variants, tmp_path, theme)
            if final_path:
                video_posted = poster.post_video_file(final_path, caption)
            if not video_posted:
                logger.error("'%s' (%s) uchun videoni joylashda xatolik.", theme, facet["label"])

    photo_posted = False
    if post_photo_too:
        brand_label = os.getenv("NATURE_BRAND_LABEL", "Nature Channel")
        photo_bytes = _find_and_prepare_photo(_photo_sources(True), variants, theme, brand_label)
        if not photo_bytes:
            photo_bytes = _find_and_prepare_photo(_photo_sources(False), variants, theme, brand_label)
        if photo_bytes:
            photo_posted = poster.post_photo_bytes(photo_bytes, caption)
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
