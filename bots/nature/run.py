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
  3. `.env`'da (config.py orqali) sozlanadigan MANBALAR TARTIBI bo'yicha (standart:
     Pixabay -> Pexels (kalit bo'lsa) -> Wikimedia Commons — NATURE_SOURCE_ORDER
     bilan o'zgartiriladi) shu joy + qirra bo'yicha VIDEO va/yoki RASM qidiradi
     (NATURE_MEDIA_MODE: "video_first" (standart), "video_only" yoki "photo_only").
     Video uchun bir nechta nomzod ketma-ket sinaladi — birinchisi yuklab bo'lmasa
     yoki sifat nazoratidan (bo'sh/qora kadr, ffmpeg qayta ishlash) o'tmasa,
     keyingisiga o'tiladi (_find_and_prepare_video()). Sifat chegarasi ham
     bosqichma-bosqich pasayadi (NATURE_MIN_VIDEO_PX/NATURE_MIN_PHOTO_PX — standart
     1080p->720p va 1600px->1080px): eng yuqori darajada hech narsa topilmasa,
     butunlay rad etish o'rniga pastroq darajada qayta qidiriladi. Vertikal video
     topilmasa (NATURE_ALLOW_ORIENTATION_FALLBACK yoqilgan bo'lsa, standart), mos
     gorizontal video ham qabul qilinib, ffmpeg orqali markazdan kesib (crop)
     vertikal formatga keltiriladi.
  4. Caption tayyorlab (FAQAT joy nomi + hashteglar — qirra caption'da UMUMAN
     ko'rinmaydi, faqat qidiruv/hashteg uchun ICHKI ishlatiladi), video/rasmga "pro"
     brendlash (joy nomi + kanal belgisi) qo'shib, kanalga joylaydi.
  5. Qirrani "ishlatildi" deb belgilaydi (eski, tasodifiy rejim uchun muhim).

MUHIM (universal sozlash — bots/nature/config.py): mavzular ham NATURE_TOPICS orqali
cheklanishi mumkin (masalan "ocean,forest,mountain" — bo'sh bo'lsa, standart keng
Wikipedia-asosli ro'yxat ishlaydi). Bularning barchasi KOD O'ZGARTIRMASDAN, faqat
.env orqali boshqariladi — config.py'dagi har bir funksiyaning docstring'iga qarang.

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

from . import config
from .facets import FACETS, FACETS_BY_KEY, build_hashtags, build_query_variants
from .local_footage import find_local_video
from .media_fetcher import download_bytes, download_file
from .music_mixer import prepare_video_for_posting
from .photo_overlay import add_branding_overlay
from .content_quality import is_blank_image_bytes, is_blank_video_file
from .pexels_fetcher import PexelsFetcher
from .pixabay_fetcher import PixabayFetcher
from .places import PLACES
from . import archive
from .fingerprint import photo_fingerprint, sha256_file, video_fingerprint
from .state import (
    get_current_theme,
    increment_and_get_post_count,
    mark_facet_used,
    pick_next_facet,
)
from shared.telegram_poster import TelegramPoster
from shared.hashtags import format_hashtags
from .topics import get_place_category, get_topic_pool
from .wikimedia_fetcher import WikimediaFetcher

logger = logging.getLogger(__name__)


def build_caption(theme: str, facet: dict, brand_label: str, include_follow_reminder: bool = False) -> str:
    # Telegram parse_mode="HTML" bilan yuborilgani uchun, dinamik matndagi &, <, >
    # kabi belgilar albatta escape qilinishi shart — aks holda Telegram "can't parse
    # entities" xatosi bilan butun postni rad etadi.
    #
    # MUHIM (foydalanuvchi qarori — yakuniy o'zgartirish): avval sarlavhada Wikipedia'dan
    # topilgan ANIQ joy nomi ko'rinardi (masalan "Yosemite National Park"). Lekin
    # foydalanuvchi aniqladi: bitta xuddi shu rasm/video ba'zan 2 yoki undan ortiq
    # TURLI joy nomi bilan chiqib qolayotgan edi (chunki qidiruv so'zi umumiy bo'lsa,
    # Pixabay/Pexels bir xil natijani turli so'rovlar uchun ham qaytarishi mumkin —
    # bu esa "botga ishonchsizlik" tuyg'usini uyg'otadi). Foydalanuvchining o'z qarori:
    # ANIQ joy nomi HOZIRCHA muhim emas — caption'da FAQAT kanal nomi/belgisi
    # (NATURE_BRAND_LABEL) chiqsin. `theme` parametri hali ham funksiyaga uzatiladi
    # (kelajakda kerak bo'lib qolishi mumkin), lekin caption matnida ENDI ishlatilmaydi.
    brand_esc = html.escape(brand_label)
    header = f"🌿 <b>{brand_esc}</b>"
    footer = "\n\n" + format_hashtags(build_hashtags(theme, facet))
    # MUHIM (foydalanuvchi ikkilanishi bilan): "faqat nomi, boshqa hech narsa
    # yozilmasin" degan qat'iy ko'rsatmangizga ATAYLAB ziddiyatga kirmaslik uchun, bu
    # qo'shimcha qator STANDART HOLATDA O'CHIRILGAN (NATURE_FOLLOW_REMINDER_EVERY_N=0).
    # Faqat o'zingiz .env'da yoqsangiz (masalan =5 — har 5-postda bir marta) qo'shiladi.
    reminder = "\n\n🔔 Follow for more" if include_follow_reminder else ""
    return header + reminder + footer


def _local_key(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return f"local:{path.name}:{size}"


def _posted_local_videos() -> set[str]:
    """localfootage/ dagi allaqachon joylangan fayllar nomlari (qayta tanlanmasligi uchun)."""
    from .local_footage import _list_local_videos
    return {p.name for p in _list_local_videos() if archive.is_posted("video", _local_key(p))}


def _post_with_archive(poster: TelegramPoster, kind: str, meta: dict, theme: str, facet: dict, send_fn) -> bool:
    """Media'ni ARXIV nazorati ostida yuboradi:
      1) yuborishdan OLDIN "pending" deb band qilinadi (jarayon o'rtada o'chsa ham qayta chiqmaydi);
      2) muvaffaqiyat -> "posted" (+ Telegram message_id);
      3) Telegram ANIQ rad etdi yoki so'rov yetib bormadi -> "released" (keyin qayta sinash mumkin);
      4) natija NOANIQ (timeout) -> "uncertain" — joylangan deb hisoblanadi, qayta chiqmaydi."""
    key = meta["key"]
    archive.reserve(
        kind, key, url=meta.get("url"), source=meta.get("source"), query=meta.get("query"),
        theme=theme, facet=facet.get("key"), sha256=meta.get("sha256"), phash=meta.get("phash"),
    )
    ok = send_fn()
    if ok:
        archive.confirm(kind, key, message_id=poster.last_message_id)
        return True
    if poster.last_error_kind == "uncertain":
        logger.warning("%s (%s) yuborish natijasi noaniq — takror chiqmasligi uchun arxivda 'joylangan' deb qoldirildi.", kind, key)
        archive.confirm(kind, key, uncertain=True)
    else:
        archive.release(kind, key)
    return False


def _find_and_prepare_video(sources: list[tuple[str, callable]], variants: list[str],
                             tmp_path: Path, theme: str, prefer_vertical: bool = True) -> tuple[Path, dict] | None:
    """Har bir manba/so'rov birikmasi uchun BIR NECHTA nomzod (fetch_video_candidates —
    endi har biri {"url", "is_vertical", ...} ko'rinishidagi dict) oladi, va har birini
    KETMA-KET: yuklab olish -> bo'sh/qora kadr tekshiruvi -> ffmpeg orqali Telegram
    uchun mos formatga o'tkazish (+ topilsa musiqa, + brendlash, + kerak bo'lsa
    orientatsiya moslashtirish) bosqichlaridan o'tkazadi. Birinchi nomzod istalgan
    bosqichda muvaffaqiyatsiz bo'lsa (yuklanmadi, bo'sh ekan, yoki ffmpeg qayta ishlay
    olmadi), RO'YXATDAGI KEYINGI nomzodga o'tadi — faqat BITTA muammoli fayl tufayli
    butun post video'siz (faqat rasm bilan) qolib ketmasligi uchun (foydalanuvchi
    so'rovi).

    MUHIM (universal manba-orientatsiya qo'llab-quvvatlash): fetcherlar endi bitta
    so'rovning o'zida ham afzal (masalan vertikal), ham — NATURE_ALLOW_ORIENTATION_
    FALLBACK yoqilgan bo'lsa — qarshi (gorizontal) orientatsiyadagi nomzodlarni birga
    qaytaradi. Nomzod GORIZONTAL bo'lsa-yu, `prefer_vertical=True` bo'lsa, ffmpeg orqali
    markazdan kesib (crop) 9:16 formatga keltiriladi — shu tarzda ko'pchilik stok-video
    kutubxonalarida ustunlik qiladigan gorizontal kliplar ham ishlatilishi mumkin bo'ladi
    (avval bular butunlay chetlab tashlanardi, natijada ko'p postlar video topilmagani
    uchun faqat rasm bilan qolardi).

    Muvaffaqiyatli bo'lsa, Telegram'ga joylashga tayyor YAKUNIY (qayta ishlangan)
    fayl yo'lini qaytaradi. Hech qanday nomzod (barcha manba/so'rov/nomzod
    birikmalari orasidan) sifat nazoratidan o'ta olmasa, None qaytaradi — bu holatda
    run_once() video'siz, faqat rasm bilan davom etadi (postsiz qolishdan yaxshi)."""
    attempt = 0
    for query in variants:
        for source_name, fetch_candidates_fn in sources:
            candidates = fetch_candidates_fn(query)
            for candidate in candidates:
                video_url = candidate["url"]
                # MUHIM (haqiqiy voqeada aniqlangan muammo — birinchi tuzatishdan
                # KEYIN ham davom etgan): bitta video bir nechta sifat darajasida
                # (masalan large/medium) TURLI URL'ga ega, shuning uchun faqat URL
                # bo'yicha solishtirish yetarli emas edi. Endi manbaning DOIMIY
                # ID'si (mavjud bo'lsa) bilan tekshiramiz - shu tufayli sifat
                # darajasi o'zgarsa ham bir xil video tanib olinadi. Manba nomi
                # bilan birga ("Pixabay:12345") saqlanadi, chunki turli manbalarning
                # ID raqamlari mos kelib qolishi mumkin (tasodifiy to'qnashuv).
                dedup_key = f"{source_name}:{candidate.get('id') or video_url}"
                # URL ham tekshiriladi — eski (migratsiyadan oldingi) yozuvlar xom URL edi.
                if archive.is_posted("video", dedup_key, video_url):
                    # Bir xil so'rov ko'pincha bir xil natijani qaytaradi - bu video
                    # ILGARI (boshqa joy nomi bilan bo'lsa ham) allaqachon joylangan,
                    # qayta joylanmasin, ro'yxatdagi keyingi nomzodga o'tamiz.
                    logger.info("'%s' manbasidan video (so'rov: '%s') ALLAQACHON joylangan edi - keyingi nomzod sinaladi.", source_name, query)
                    continue
                is_vertical = candidate.get("is_vertical", prefer_vertical)
                crop_to_vertical = prefer_vertical and not is_vertical
                attempt += 1
                url_suffix = Path(urlparse(video_url).path).suffix
                raw_path = tmp_path / f"raw_{attempt}{url_suffix or '.mp4'}"
                if not download_file(video_url, raw_path):
                    logger.warning("'%s' manbasidan video (so'rov: '%s') yuklab olinmadi - keyingi nomzod sinaladi.", source_name, query)
                    continue
                if is_blank_video_file(raw_path):
                    logger.warning("'%s' manbasidan video (so'rov: '%s') bo'sh/qora ekan - keyingi nomzod sinaladi.", source_name, query)
                    continue
                # KONTENT bo'yicha tekshiruv: bir xil video boshqa manbada/boshqa ID
                # bilan/boshqa sifatda qayta topilgan bo'lsa ham tanib olinadi.
                fp = video_fingerprint(raw_path)
                dup = archive.find_duplicate_content("video", fp)
                if dup:
                    logger.info(
                        "'%s' manbasidan video (so'rov: '%s') KONTENT bo'yicha avval joylangan videoga o'xshaydi "
                        "(%s) - keyingi nomzod sinaladi.", source_name, query, dup.get("key"),
                    )
                    continue
                final_path = tmp_path / f"final_{attempt}.mp4"
                # MUHIM (foydalanuvchi qarori): standart bo'yicha video ustiga hech qanday
                # matn (joy nomi/kanal belgisi) chizilmaydi - manzaraning asosiy qismini
                # yopib qo'yardi. config.media_overlay_enabled() bilan (.env orqali)
                # yoqish mumkin - shunda location_text=theme uzatiladi, aks holda None
                # (prepare_video_for_posting overlay'ni UMUMAN qo'shmaydi).
                overlay_location = theme if config.media_overlay_enabled() else None
                if prepare_video_for_posting(raw_path, final_path, location_text=overlay_location, crop_to_vertical=crop_to_vertical):
                    # Telegram Bot API 50MB'dan katta videoni qabul qilmaydi — avval bunday
                    # holatda butun video bosqichi to'xtab, post videosiz qolardi. Endi
                    # shunchaki keyingi nomzodga o'tamiz.
                    size_mb = final_path.stat().st_size / (1024 * 1024)
                    if size_mb > 49:
                        logger.warning("'%s' manbasidan video (so'rov: '%s') tayyorlangandan keyin %.1f MB — Telegram limiti (50MB) oshadi, keyingi nomzod sinaladi.", source_name, query, size_mb)
                        continue
                    logger.info(
                        "Video topildi, sifat nazoratidan o'tdi va tayyorlandi — manba: %s, so'rov: '%s' (%d-nomzod%s).",
                        source_name, query, attempt, ", gorizontaldan vertikalga kesildi" if crop_to_vertical else "",
                    )
                    return final_path, {"key": dedup_key, "url": video_url, "source": source_name, "query": query, **fp}
                logger.warning(
                    "'%s' manbasidan video (so'rov: '%s') ffmpeg orqali qayta ishlanmadi - keyingi nomzod sinaladi.",
                    source_name, query,
                )
    logger.info("Hech qanday video nomzodi sifat nazoratidan o'ta olmadi (%d ta nomzod sinaldi).", attempt)
    return None


def _find_and_prepare_photo(sources: list[tuple[str, callable]], variants: list[str],
                             theme: str, brand_label: str) -> tuple[bytes, dict] | None:
    """`_find_and_prepare_video`bilan bir xil mantiq, faqat rasm uchun: har bir manba/
    so'rov birikmasidan bir nechta nomzod olib, har birini KETMA-KET: xotiraga yuklash
    -> bo'sh/bir xil rangli tekshiruvi -> brendlash overlay chizish bosqichlaridan
    o'tkazadi. Birinchi nomzod muvaffaqiyatsiz bo'lsa, keyingisiga o'tadi. Muvaffaqiyatli
    bo'lsa, Telegram'ga joylashga tayyor (overlay bilan) rasm baytlarini qaytaradi."""
    for query in variants:
        for source_name, fetch_candidates_fn in sources:
            candidates = fetch_candidates_fn(query)
            for candidate in candidates:
                photo_url = candidate["url"]
                # video'dagi bir xil sabab (yuqoridagi _find_and_prepare_video'ga
                # qarang): rasmning ham sifat darajasiga qarab boshqa URL bo'lishi
                # mumkin, shuning uchun manbaning doimiy ID'si bilan tekshiramiz.
                dedup_key = f"{source_name}:{candidate.get('id') or photo_url}"
                if archive.is_posted("photo", dedup_key, photo_url):
                    # Video bilan bir xil sabab: bir xil so'rov ko'pincha bir xil rasmni
                    # qaytaradi - bu rasm ILGARI allaqachon joylangan, keyingi nomzod
                    # sinaladi.
                    logger.info("'%s' manbasidan rasm (so'rov: '%s') ALLAQACHON joylangan edi - keyingi nomzod sinaladi.", source_name, query)
                    continue
                photo_bytes = download_bytes(photo_url)
                if not photo_bytes:
                    logger.warning("'%s' manbasidan rasm (so'rov: '%s') yuklab olinmadi - keyingi nomzod sinaladi.", source_name, query)
                    continue
                if is_blank_image_bytes(photo_bytes):
                    logger.warning("'%s' manbasidan rasm (so'rov: '%s') bo'sh/bir xil rangdan iborat - keyingi nomzod sinaladi.", source_name, query)
                    continue
                fp = photo_fingerprint(photo_bytes)
                dup = archive.find_duplicate_content("photo", fp)
                if dup:
                    logger.info(
                        "'%s' manbasidan rasm (so'rov: '%s') KONTENT bo'yicha avval joylangan rasmga o'xshaydi "
                        "(%s) - keyingi nomzod sinaladi.", source_name, query, dup.get("key"),
                    )
                    continue
                # MUHIM (foydalanuvchi qarori): standart bo'yicha rasm ustiga hech qanday
                # matn (joy nomi/kanal belgisi) chizilmaydi - manzaraning asosiy qismini
                # yopib qo'yardi. config.media_overlay_enabled() bilan (.env orqali)
                # yoqish mumkin.
                if config.media_overlay_enabled():
                    overlaid = add_branding_overlay(photo_bytes, theme, brand_label)
                    result = overlaid or photo_bytes
                else:
                    result = photo_bytes
                logger.info("Rasm topildi va tayyorlandi — manba: %s, so'rov: '%s'.", source_name, query)
                return result, {"key": dedup_key, "url": photo_url, "source": source_name, "query": query, **fp}
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

    archive.ensure_loaded()

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
    # QO'SHIMCHA manba sifatida qaytarishni so'radi. Bundan tashqari, foydalanuvchi
    # kelajakda yana boshqa manba (masalan Unsplash) qo'shilishini yoki manbalar
    # tartibi/yoqilishi .env orqali (kodni o'zgartirmasdan) boshqarilishini so'radi.
    #
    # Shuning uchun endi: har bir manba ADAPTER sifatida ro'yxatga olinadi
    # (`_SOURCE_ADAPTERS`), va NATURE_SOURCE_ORDER (.env, config.py) shu ro'yxatdan
    # QAYSILARI va QANDAY TARTIBDA ishlatilishini belgilaydi. Yangi manba qo'shish
    # uchun kelajakda shu ro'yxatga bitta yozuv qo'shish kifoya (README.md'ga qarang).
    pixabay = PixabayFetcher(pixabay_key)
    pexels = PexelsFetcher(pexels_key) if pexels_key else None
    wikimedia = WikimediaFetcher()  # API kalit shart emas, doim faol qo'shimcha manba

    _SOURCE_ADAPTERS = {
        "pixabay": ("Pixabay", pixabay),
        "pexels": ("Pexels", pexels),  # None bo'lsa (kalit sozlanmagan), pastda avtomatik chetlab o'tiladi
        "wikimedia": ("Wikimedia Commons", wikimedia),
    }

    def _ordered_adapters():
        order = config.source_order()
        chosen = [_SOURCE_ADAPTERS[key] for key in order if key in _SOURCE_ADAPTERS and _SOURCE_ADAPTERS[key][1]]
        # Agar .env'da noto'g'ri/bo'sh tartib berilgan bo'lsa yoki barcha ko'rsatilgan
        # manbalar o'chirilgan bo'lsa, botning umuman ishlamay qolishining oldini olish
        # uchun standart tartibga qaytiladi.
        if not chosen:
            chosen = [(label, adapter) for label, adapter in _SOURCE_ADAPTERS.values() if adapter]
        return chosen

    def _video_sources(prefer_vertical: bool, min_dimension: int):
        # MUHIM: endi `fetch_video` (bitta URL) o'rniga `fetch_video_candidates`
        # (bir nechta {"url", "is_vertical", ...} dict ro'yxati) ishlatiladi —
        # pastdagi `_find_and_prepare_video()` birinchi nomzod yuklab bo'lmasa yoki
        # sifat nazoratidan o'tmasa, RO'YXATDAGI KEYINGI nomzodni avtomatik sinab
        # ko'radi (foydalanuvchi so'rovi: "topgan va tekshiruvdan o'tgan videoni
        # yuklay olmasa, boshqasini qidirsin").
        return [
            (label, lambda q, a=adapter, pv=prefer_vertical, md=min_dimension:
             a.fetch_video_candidates(q, prefer_vertical=pv, min_dimension=md, max_results=config.candidates_per_query()))
            for label, adapter in _ordered_adapters()
        ]

    def _photo_sources(prefer_vertical: bool, min_dimension: int):
        return [
            (label, lambda q, a=adapter, pv=prefer_vertical, md=min_dimension:
             a.fetch_photo_candidates(q, prefer_vertical=pv, min_dimension=md, max_results=config.candidates_per_query()))
            for label, adapter in _ordered_adapters()
        ]

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

    brand_label = os.getenv("NATURE_BRAND_LABEL", "Nature Channel")
    caption = build_caption(theme, facet, brand_label, include_follow_reminder=include_reminder)

    poster = TelegramPoster(bot_token, channel_id)

    # Video asosiy kontent hisoblanadi (foydalanuvchi so'ragani kabi), shuning uchun avval
    # videoni sinaymiz — FAQAT agar NATURE_MEDIA_MODE="photo_only" qilib qo'yilmagan bo'lsa.
    #
    # 0-ustuvorlik: localfootage/ papkasida foydalanuvchi o'zi (masalan Shutterstock,
    # Envato Elements, iStock, Storyblocks, Motion Array kabi pullik kutubxonadan qonuniy
    # yuklab olib) joylagan, joriy so'rovga fayl nomi bo'yicha mos keladigan premium video
    # bo'lsa, u eng birinchi ishlatiladi (README.md'ga qarang — bu manba avtomatik
    # ulanmagan, chunki bunday kutubxonalar bepul API taklif qilmaydi va litsenziyasi
    # faqat qo'lda yuklab olishga ruxsat beradi).
    #
    # Mos lokal video topilmasa, avtomatik bepul manbalarga (NATURE_SOURCE_ORDER orqali
    # sozlanadigan tartibda) o'tiladi. Har bir sifat darajasi (config.py'dagi
    # min_video_dimension_tiers() — standart [1080, 720]) uchun avval telefon ekraniga
    # to'liq mos vertikal (portret, "short" formatiga o'xshash) video qidiriladi;
    # NATURE_ALLOW_ORIENTATION_FALLBACK yoqilgan bo'lsa (standart), gorizontal video ham
    # nomzod sifatida qabul qilinib, ffmpeg orqali kesib (crop) vertikal qilinadi. Eng
    # yuqori sifat darajasida hech narsa topilmasa, pastroq darajaga (masalan 720p) tushib
    # qayta uriniladi — butunlay rad etish o'rniga.
    media_mode = config.media_mode()
    video_posted = False

    if media_mode != "photo_only":
        local_video = find_local_video(variants, prefer_vertical=True, exclude=_posted_local_videos())
        if local_video and not is_blank_video_file(local_video):
            local_meta = {"key": _local_key(local_video), "source": "local", "sha256": sha256_file(local_video)}
            if archive.find_duplicate_content("video", {"sha256": local_meta["sha256"]}):
                logger.info("Lokal video (%s) avval joylangan — o'tkazib yuboriladi.", local_video.name)
            else:
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_path = Path(tmp_dir)
                    final_path = tmp_path / "final_video.mp4"
                    overlay_location = theme if config.media_overlay_enabled() else None
                    if prepare_video_for_posting(local_video, final_path, location_text=overlay_location):
                        video_posted = _post_with_archive(
                            poster, "video", local_meta, theme, facet,
                            lambda: poster.post_video_file(final_path, caption),
                        )
                        if not video_posted:
                            logger.error("Lokal video (%s) joylashda xatolik.", local_video.name)
                    else:
                        # ffmpeg muvaffaqiyatsiz bo'lsa xom fayl JOYLANMAYDI (Telegram uni
                        # o'ynatib bo'lmaydigan hujjat sifatida ko'rsatardi).
                        logger.warning("Lokal video (%s) ffmpeg orqali qayta ishlanmadi - sifat nazoratidan o'tmagani uchun JOYLANMAYDI.", local_video.name)

        if not video_posted:
            for min_dimension in config.min_video_dimension_tiers():
                with tempfile.TemporaryDirectory() as tmp_dir:
                    tmp_path = Path(tmp_dir)
                    found = _find_and_prepare_video(
                        _video_sources(True, min_dimension), variants, tmp_path, theme, prefer_vertical=True,
                    )
                    if found:
                        final_path, video_meta = found
                        video_posted = _post_with_archive(
                            poster, "video", video_meta, theme, facet,
                            lambda: poster.post_video_file(final_path, caption),
                        )
                if video_posted:
                    break
            if not video_posted:
                logger.error("'%s' (%s) uchun videoni joylashda xatolik.", theme, facet["label"])

    photo_posted = False
    if post_photo_too and media_mode != "video_only":
        # brand_label yuqorida (caption uchun) allaqachon hisoblangan - qayta
        # o'qishga hojat yo'q, xuddi shu qiymat overlay uchun ham ishlatiladi.
        found_photo = None
        for min_dimension in config.min_photo_dimension_tiers():
            found_photo = _find_and_prepare_photo(_photo_sources(True, min_dimension), variants, theme, brand_label)
            if found_photo:
                break
        if found_photo:
            photo_bytes, photo_meta = found_photo
            photo_posted = _post_with_archive(
                poster, "photo", photo_meta, theme, facet,
                lambda: poster.post_photo_bytes(photo_bytes, caption, filename="photo.jpg"),
            )
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
