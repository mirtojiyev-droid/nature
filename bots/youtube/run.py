"""
Asosiy ishga tushirish nuqtasi.

Oqim: trend videolarni aniqlash -> hali joylanmaganlarini tanlash ->
      yuklab olish -> Telegram kanalga joylash -> "joylandi" deb
      belgilash.

      Har bir ishga tushirishda standart bo'yicha 5 ta post joylanadi,
      uchta turkumga bo'lingan holda (POSTS_TRENDING / POSTS_MOST_VIEWED
      / POSTS_NEWEST, standart 1/2/2):
        - 1 tasi hozir TRENDNI EGALLAB TURGAN (eng tez o'sayotgan —
          views_per_hour eng yuqori);
        - 2 tasi ENG KO'P KO'RILGAN (xom ko'rishlar soni bo'yicha);
        - 2 tasi ENG YANGI chiqqan.
      Nomzodlar so'z bo'yicha QIDIRILMAYDI — YouTube'ning rasmiy TREND
      jadvalidan (REGION_CODE + EXTRA_REGION_CODES, har biri mumkin
      bo'lsa Music kategoriyasi bilan cheklab) olinadi. Har bir turkum
      ichida AVOID_LANGUAGES'dagi til (standart: hind) imkon qadar
      tanlanmaydi (lekin boshqa hech narsa qolmasa, baribir ishlatiladi
      — bot hech narsa joylay olmay qolmasligi uchun), PREFERRED_LANGUAGES'dagi
      til (standart: ingliz, rus, o'zbek) esa ustunlik oladi — kanal
      auditoriyasi shu tillarda so'zlashadi. Bundan tashqari,
      MIN_UZBEK_PER_RUN (standart 1) orqali kamida shuncha post
      o'zbekcha bo'lishi alohida kafolatlanadi. Til YouTube'ning o'z
      metama'lumoti (defaultAudioLanguage) yoki sarlavha/kanal
      nomidagi belgilar asosida taxmin qilinadi. Har bir caption'ga
      postni Telegram ichida qidirilganda topilishi uchun kamida 5 ta
      hashtag ham avtomatik qo'shiladi.

Avtomatik (trend qidiruvi) ishga tushirish:
    python main.py                           # standart: faqat musiqa, Shorts'siz
    python main.py --category comedy --length both   # boshqa mavzuga bir martalik almashtirish
    python main.py --category 24            # yoki to'g'ridan-to'g'ri raqamli ID bilan
    python main.py --list-categories        # mavjud kategoriyalar ro'yxati

    Standart bo'yicha bot faqat musiqa trend jadvalini qaraydi
    (VIDEO_CATEGORY_ID=10, VIDEO_LENGTH_MODE=long — Shorts umuman
    qaralmaydi va filtrdan ham butunlay chiqarib tashlanadi). Boshqa
    mavzuga (masalan kulgili) qaytmoqchi bo'lsangiz, --category ni
    o'zgartiring va kerak bo'lsa --length short yoki both bering.

Qo'lda, aniq bitta video havolasini joylash (bot o'zi tanlagan narsani
emas, siz aytgan videoni joylaydi):
    python main.py --url "https://www.youtube.com/shorts/XXXXXXXXXXX"
    python main.py --url "https://youtu.be/XXXXXXXXXXX" --force   # allaqachon joylangan bo'lsa ham majburlash

VPS'da bot_hub ichiga qo'shish uchun: shu faylni alohida chaqirmasdan,
`run()` yoki `post_manual_video()` funksiyalarini bot_hub'ning schedule
tizimiga ulash kifoya.
"""
import argparse
import logging
import os
from pathlib import Path

import requests

from . import config
from .categories import CATEGORY_ID_LABELS, format_category_list, resolve_category
from .youtube_trends import get_trending_shorts, fetch_video_details, extract_video_id, classify_language
from .downloader import download_video, DownloadError
from shared.telegram_poster import TelegramPoster
from .storage import is_posted, load_posted_ids, mark_posted
from .hashtags import format_hashtags

log = logging.getLogger(__name__)


def _bucket_sort_key(video: dict, metric, avoid_languages, preferred_languages):
    """Bitta "turkum" (trending/most-viewed/newest) ichida saralash
    kaliti. Kichikroq kalit — ustunroq. Birinchi navbatda
    AVOID_LANGUAGES'dagi til (masalan hind) ENG OXIRIGA suriladi — bu
    videoni butunlay chiqarib tashlamaydi, faqat "iloji boricha kam
    ko'rsatish" uchun eng oxirgi ustuvorlikka qo'yadi. Keyin
    PREFERRED_LANGUAGES'dagi til (ingliz/rus/o'zbek) ustunlik oladi.
    So'ngra asosiy mezon (masalan ko'rishlar soni yoki chop etilgan
    sana) bo'yicha kamayish tartibida saralanadi."""
    lang = video.get("lang_guess", "other")
    avoid_penalty = 1 if lang in avoid_languages else 0
    preferred_bonus = 0 if lang in preferred_languages else 1
    return (avoid_penalty, preferred_bonus, -metric(video))


def _select_composite(candidates: list, slot_trending: int, slot_most_viewed: int, slot_newest: int,
                       preferred_languages: list, avoid_languages: list) -> tuple:
    """Nomzodlar to'plamidan uchta turkum bo'yicha post tanlaydi:

    - TRENDING (`slot_trending` ta): hozir eng tez o'sayotgan —
      views_per_hour bo'yicha eng yuqori ("trendni egallab turgan").
    - MOST_VIEWED (`slot_most_viewed` ta): xom ko'rishlar soni bo'yicha
      eng ko'p ko'rilgan.
    - NEWEST (`slot_newest` ta): eng yaqinda chop etilgan.

    Har bir turkum ichida AVOID_LANGUAGES'dagi til (masalan hind) imkon
    qadar tanlanmaydi (lekin shu turkumda boshqa hech narsa qolmasa,
    baribir ishlatiladi — botni "hech narsa joylay olmaydigan" holga
    keltirmaslik uchun), PREFERRED_LANGUAGES'dagi til (ingliz/rus/
    o'zbek) esa ustunlik oladi. Har bir video faqat bitta turkumda
    ishlatiladi — takror yo'q.

    Qaytaradi: (tanlangan ro'yxat — trending, most_viewed, newest
    tartibida ketma-ket, ishlatilmay qolgan qolgan nomzodlar to'plami)."""
    pool = list(candidates)

    def _take(n, metric, slot_name):
        nonlocal pool
        if n <= 0 or not pool:
            return []
        ranked = sorted(pool, key=lambda v: _bucket_sort_key(v, metric, avoid_languages, preferred_languages))
        chosen = ranked[:n]
        for v in chosen:
            v["_slot"] = slot_name
        chosen_ids = {v["id"] for v in chosen}
        pool = [v for v in pool if v["id"] not in chosen_ids]
        return chosen

    trending_picks = _take(slot_trending, lambda v: v.get("views_per_hour", 0), "trend")
    most_viewed_picks = _take(slot_most_viewed, lambda v: v.get("views", 0), "eng ko'p ko'rilgan")
    newest_picks = _take(slot_newest, lambda v: v.get("published_at_ts", 0), "eng yangi")

    return trending_picks + most_viewed_picks + newest_picks, pool


def _ensure_min_language(selected: list, pool: list, lang: str, min_count: int) -> list:
    """`selected` (allaqachon tanlangan postlar) ichida kamida
    `min_count` tasi `lang_guess == lang` bo'lishini ta'minlaydi —
    yetmasa, `pool`dagi (hali tanlanmagan) shu tildagi eng ko'p
    ko'rilgan nomzod(lar) bilan, `selected` ichidagi eng past
    ustuvorlikdagi (mos kelmaydigan, ro'yxat oxiridagi) nomzod(lar)
    o'rniga almashtiriladi. Mos nomzod topilmasa, o'zgarishsiz
    qaytariladi (xato bermaydi)."""
    if min_count <= 0 or not selected:
        return selected
    have = sum(1 for v in selected if v.get("lang_guess") == lang)
    missing = min_count - have
    if missing <= 0:
        return selected

    non_matching_idx = [i for i, v in enumerate(selected) if v.get("lang_guess") != lang]
    missing = min(missing, len(non_matching_idx))
    if missing <= 0:
        return selected

    replacement = sorted(
        (v for v in pool if v.get("lang_guess") == lang),
        key=lambda v: v.get("views", 0), reverse=True,
    )[:missing]
    if not replacement:
        return selected

    to_remove = set(non_matching_idx[-len(replacement):])
    return [v for i, v in enumerate(selected) if i not in to_remove] + replacement


def run_once(video_category_id: str = None, video_length_mode: str = None) -> int:
    """Avtomatik rejim: YouTube'ning rasmiy trend jadvalidan (REGION_CODE
    + EXTRA_REGION_CODES) nomzod topib, mos kelganlarini navbat bilan
    joylaydi. So'z bo'yicha qidiruv ishlatilmaydi (youtube_trends.py
    docstring'ida sababi tushuntirilgan).

    video_category_id berilsa, .env'dagi VIDEO_CATEGORY_ID o'rniga shu
    ishga tushirish uchun o'sha kategoriya ishlatiladi (masalan
    --category orqali). video_length_mode berilsa, .env'dagi
    VIDEO_LENGTH_MODE o'rniga ishlatiladi (--length orqali) — "short",
    "long" yoki "both"."""
    try:
        config.validate()
    except RuntimeError as exc:
        log.error(str(exc))
        return 1

    poster = TelegramPoster(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHANNEL_ID)
    category_id = video_category_id or config.VIDEO_CATEGORY_ID
    length_mode = video_length_mode or config.VIDEO_LENGTH_MODE

    log.info(
        "YouTube trend jadvalidan qidirilmoqda... (kategoriya=%s, davomiylik rejimi=%s, mintaqalar=%s)",
        category_id, length_mode, [config.REGION_CODE] + config.EXTRA_REGION_CODES,
    )
    try:
        trending = get_trending_shorts(
            api_key=config.YOUTUBE_API_KEY,
            region_code=config.REGION_CODE,
            min_views=config.MIN_VIEWS,
            max_age_hours=config.MAX_AGE_HOURS,
            max_duration_sec=config.MAX_DURATION_SEC,
            video_category_id=category_id,
            exclude_category_ids=config.EXCLUDE_CATEGORY_IDS,
            exclude_keywords=config.EXCLUDE_KEYWORDS,
            max_results=config.MAX_RESULTS,
            video_length_mode=length_mode,
            max_long_duration_sec=config.MAX_LONG_DURATION_SEC,
            extra_region_codes=config.EXTRA_REGION_CODES,
        )
    except requests.exceptions.RequestException as exc:
        # Masalan YouTube kvotasi tugagan yoki tarmoq xatosi — butun
        # skriptni xom traceback bilan yiqitish o'rniga toza log qilib
        # shu ishga tushirishni to'xtatamiz (keyingi ishga tushirishda qayta urinadi).
        log.error("YouTube API'ga murojaat qilib bo'lmadi: %s", exc)
        return 1
    log.info("Topildi: %d ta nomzod video.", len(trending))

    # posted.json'ni har bir nomzod uchun alohida-alohida qayta o'qib
    # tekshirish o'rniga (bu ro'yxat kattalashgani sayin sekinlashadigan
    # I/O bo'ladi), shu ishga tushirish uchun bir marta ID'lar to'plamini
    # yuklab olamiz va shu to'plam ichida tekshiramiz.
    posted_ids = load_posted_ids(config.POSTED_LOG_FILE)
    candidates = [v for v in trending if v["id"] not in posted_ids]

    if trending and not candidates:
        # Topilgan barcha nomzod allaqachon joylangan (posted.json'da bor).
        # Bu XATO emas — trend jadvali tez-tez o'zgarmaydi. Lekin darhol
        # taslim bo'lish o'rniga, birinchi navbatda ESKILIK/DAVOMIYLIK
        # chegaralarini kengaytirib (tarmoq bo'yicha bir necha qo'shimcha
        # so'rov bilan, lekin arzon — chart chaqiruvi ~1 birlik), xuddi
        # shu allaqachon topilgan trend ro'yxatidan (yoshi kattaroq yoki
        # davomiylik chegarasidan tashqarida qolgan) BOSHQA, hali
        # joylanmagan nomzod bormi tekshiramiz — foydalanuvchi aynan
        # shuni so'ragan: "bu joylangan bo'lsa, boshqasini joylasin".
        log.info(
            "Topilgan %d ta nomzodning barchasi allaqachon joylangan — eskilik/davomiylik "
            "chegaralari kengaytirilib, boshqa (hali joylanmagan) nomzod uchun qayta "
            "urinilmoqda...",
            len(trending),
        )
        try:
            wider_trending = get_trending_shorts(
                api_key=config.YOUTUBE_API_KEY,
                region_code=config.REGION_CODE,
                min_views=config.MIN_VIEWS,
                max_age_hours=max(config.MAX_AGE_HOURS * 3, config.MAX_AGE_HOURS + 168),
                max_duration_sec=config.MAX_DURATION_SEC,
                video_category_id=category_id,
                exclude_category_ids=config.EXCLUDE_CATEGORY_IDS,
                exclude_keywords=config.EXCLUDE_KEYWORDS,
                max_results=config.MAX_RESULTS,
                video_length_mode=length_mode,
                max_long_duration_sec=int(config.MAX_LONG_DURATION_SEC * 1.5),
                extra_region_codes=config.EXTRA_REGION_CODES,
            )
        except requests.exceptions.RequestException as exc:
            log.warning("Kengaytirilgan qidiruvda YouTube API'ga murojaat qilib bo'lmadi: %s", exc)
            wider_trending = []

        wider_candidates = [v for v in wider_trending if v["id"] not in posted_ids]
        if wider_candidates:
            log.info(
                "Kengaytirilgan qidiruv orqali %d ta yangi (hali joylanmagan) nomzod topildi.",
                len(wider_candidates),
            )
            trending = wider_trending
            candidates = wider_candidates
        else:
            # Kengaytirilgan qidiruv ham yordam bermadi — haqiqatan
            # hozircha yangi post uchun material yo'q. Botning o'zi
            # bunda boshqa hech narsa qila olmaydi.
            log.info(
                "Kengaytirilgan qidiruvdan keyin ham yangi nomzod topilmadi — bu xato emas, "
                "hozircha hammasi allaqachon joylangan. Ko'proq nomzod uchun "
                "EXTRA_REGION_CODES'ga qo'shimcha mintaqa qo'shing yoki keyinroq qayta urining."
            )
            return 0

    selected, remaining_pool = _select_composite(
        candidates, config.POSTS_TRENDING, config.POSTS_MOST_VIEWED, config.POSTS_NEWEST,
        config.PREFERRED_LANGUAGES, config.AVOID_LANGUAGES,
    )
    selected = _ensure_min_language(selected, remaining_pool, "uz", config.MIN_UZBEK_PER_RUN)

    # Tanlangan (masalan 5 ta) nomzoddan ba'zilari yuklab bo'lmasligi
    # mumkin (video o'chirilgan, mintaqaviy cheklangan, tarmoq xatosi
    # va h.k.). Shuning uchun faqat aynan shu tanlangan ro'yxat bilan
    # cheklanib qolmaymiz — muvaffaqiyatsiz bo'lganlarning o'rniga
    # qolgan nomzodlar to'plamidan (remaining_pool) navbatdagi eng mos
    # keladiganini olib, MAX_POSTS_PER_RUN ta muvaffaqiyatli joylanguncha
    # yoki butun to'plam tugaguncha davom etamiz — shunda bitta-ikkita
    # "Video unavailable" xatosi butun ishga tushirishni "0 ta
    # joylandi" holiga olib kelmaydi.
    selected_ids = {v["id"] for v in selected}
    reserve = [v for v in remaining_pool if v["id"] not in selected_ids]
    reserve.sort(key=lambda v: _bucket_sort_key(
        v, lambda vv: vv.get("views", 0), config.AVOID_LANGUAGES, config.PREFERRED_LANGUAGES,
    ))
    attempt_queue = selected + reserve

    posted_count = 0
    attempted_count = 0
    for video in attempt_queue:
        if posted_count >= config.MAX_POSTS_PER_RUN:
            break
        attempted_count += 1

        kind = "Shorts" if video.get("is_short", True) else "uzun video"
        slot = video.get("_slot", "zaxira")
        log.info(
            "Nomzod (%s, %s): %s | %s ko'rish | %s/soat | til taxmini: %s | %s",
            kind, slot, video["id"], video["views"], video["views_per_hour"],
            video.get("lang_guess", "?"), video["title"],
        )

        try:
            filepath = download_video(
                video["url"], config.DOWNLOAD_DIR, cookies_file=config.YTDLP_COOKIES_FILE
            )
        except DownloadError as exc:
            log.warning(
                "Yuklab bo'lmadi, navbatdagi zaxira nomzodga o'tilmoqda: %s", exc
            )
            continue

        category_label = CATEGORY_ID_LABELS.get(str(video.get("category_id") or category_id))
        # Video uchun taxmin qilingan til (lang_guess) ANIQ shu videoga
        # tegishli — shuning uchun hashtag ham shundan olinadi (masalan
        # #Uzbek, #Russian, #English). "other" (aniqlab bo'lmagan)
        # bo'lsa, noto'g'ri hashtag qo'yib yubormaslik uchun til
        # hashtag'i qo'shilmaydi.
        lang_guess = video.get("lang_guess")
        hashtag_lang = lang_guess if lang_guess in ("uz", "en", "ru", "hi") else None
        hashtags = format_hashtags(
            video["title"], video.get("channel", ""), category_label, hashtag_lang,
        )
        caption = f"{video['title']}\n\nManba: {video['url']}"
        if hashtags:
            caption = f"{caption}\n\n{hashtags}"
        ok = poster.post_video_file(Path(filepath), caption)
        if os.path.exists(filepath):
            # Diskni tejash uchun yuklangan faylni o'chiramiz (muvaffaqiyatli bo'lsa ham,
            # bo'lmasa ham — natijadan qat'i nazar).
            # Agar fayllarni saqlab qolishni xohlasangiz, shu qatorni olib tashlang.
            os.remove(filepath)
        if not ok:
            log.warning("Telegram'ga joylab bo'lmadi, navbatdagi zaxira nomzodga o'tilmoqda.")
            continue

        mark_posted(config.POSTED_LOG_FILE, video["id"], {
            "title": video["title"],
            "url": video["url"],
            "views": video["views"],
        })
        posted_count += 1
        log.info("Joylandi: %s", video["url"])

    if posted_count < config.MAX_POSTS_PER_RUN:
        log.warning(
            "Tugadi. Jami joylangan: %d/%d (%d ta nomzod sinab ko'rildi, jami %d ta nomzod bor edi — "
            "qolganlari yuklab yoki Telegram'ga joylab bo'lmadi, yoki nomzodlar tugadi). "
            "Agar bu tez-tez takrorlansa, yt-dlp'ni yangilang: pip install -U yt-dlp",
            posted_count, config.MAX_POSTS_PER_RUN, attempted_count, len(attempt_queue),
        )
    else:
        log.info("Tugadi. Jami joylangan: %d", posted_count)
    return 0


def post_manual_video(url: str, force: bool = False) -> None:
    """Qo'lda rejim: bot avtomatik qidiruvni o'tkazib yuborib, faqat
    berilgan `url` videoni yuklab, Telegram'ga joylaydi. Bot "o'zi
    hohlagandek" tanlagan narsani emas, aynan siz ko'rsatgan videoni
    joylash kerak bo'lganda shu funksiyadan foydalaning."""
    config.validate()

    try:
        video_id = extract_video_id(url)
    except ValueError as exc:
        log.error(str(exc))
        return

    if is_posted(config.POSTED_LOG_FILE, video_id) and not force:
        log.warning(
            "Bu video allaqachon joylangan (id=%s). Baribir joylash uchun --force bering.",
            video_id,
        )
        return

    watch_url = f"https://www.youtube.com/watch?v={video_id}"

    title = watch_url
    channel = ""
    category_label = None
    try:
        details = fetch_video_details(config.YOUTUBE_API_KEY, [video_id])
        if details:
            snippet = details[0].get("snippet", {})
            title = snippet.get("title", watch_url)
            channel = snippet.get("channelTitle", "")
            category_label = CATEGORY_ID_LABELS.get(str(snippet.get("categoryId")))
        else:
            log.warning("YouTube API bu video haqida ma'lumot qaytarmadi (id=%s), baribir yuklab ko'ramiz.", video_id)
    except requests.exceptions.RequestException as exc:
        log.warning("Video sarlavhasini YouTube API'dan olib bo'lmadi, havola caption sifatida ishlatiladi: %s", exc)

    try:
        filepath = download_video(watch_url, config.DOWNLOAD_DIR, cookies_file=config.YTDLP_COOKIES_FILE)
    except DownloadError as exc:
        log.error("Yuklab bo'lmadi: %s", exc)
        return

    lang_guess = classify_language("", title, channel)
    hashtag_lang = lang_guess if lang_guess in ("uz", "en", "ru", "hi") else None
    hashtags = format_hashtags(title, channel, category_label, hashtag_lang)
    caption = f"{title}\n\nManba: {watch_url}"
    if hashtags:
        caption = f"{caption}\n\n{hashtags}"
    poster = TelegramPoster(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHANNEL_ID)
    ok = poster.post_video_file(Path(filepath), caption)
    if os.path.exists(filepath):
        os.remove(filepath)
    if not ok:
        log.error("Telegram'ga joylab bo'lmadi.")
        return

    mark_posted(config.POSTED_LOG_FILE, video_id, {
        "title": title,
        "url": watch_url,
        "views": None,
        "manual": True,
    })
    log.info("Qo'lda joylandi: %s", watch_url)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="YouTube Shorts'larni avtomatik yoki qo'lda Telegram kanalga joylash."
    )
    parser.add_argument(
        "--url",
        help="Ma'lum bir YouTube video havolasi. Berilsa, avtomatik qidiruv "
             "o'tkazib yuborilib, faqat shu video yuklanib Telegram'ga joylanadi.",
    )
    parser.add_argument(
        "--category",
        help="Shu ishga tushirish uchun .env'dagi VIDEO_CATEGORY_ID o'rniga "
             "ishlatiladigan kategoriya — raqam (masalan 24) yoki nom "
             "(masalan comedy). To'liq ro'yxat: --list-categories",
    )
    parser.add_argument(
        "--length",
        choices=["short", "long", "both"],
        help="Shu ishga tushirish uchun .env'dagi VIDEO_LENGTH_MODE "
             "o'rniga ishlatiladi: short — faqat Shorts, long — faqat "
             "uzun videolar (Shorts'siz), both — ikkalasi ham (standart).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="--url bilan birga: video avvalroq joylangan bo'lsa ham qayta joylashni majburlaydi.",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="Mavjud YouTube kategoriyalari ro'yxatini chiqarib, chiqib ketadi.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.list_categories:
        print(format_category_list())
    elif args.url:
        post_manual_video(args.url, force=args.force)
    else:
        category_id = None
        if args.category:
            try:
                category_id = resolve_category(args.category)
            except ValueError as exc:
                raise SystemExit(str(exc))
        run_once(video_category_id=category_id, video_length_mode=args.length)
