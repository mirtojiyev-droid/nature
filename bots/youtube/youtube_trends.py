"""
YouTube Shorts (va, standart bo'yicha, uzunroq videolar) trendlarini
aniqlash moduli.

MUHIM: bu modul endi so'z (matn) bo'yicha qidiruv (search.list, q=...)
ISHLATMAYDI. Avvalgi versiyada SEARCH_QUERY + relevanceLanguage bilan
qidirilar edi ("music" so'ziga mos, ko'rishlar soni bo'yicha saralab) —
lekin bu YouTube'ning butun dunyo bo'yicha eng ko'p ko'rilgan (odatda
hind/Bollywood) kontentni qaytarishga moyil edi, chunki relevanceLanguage
faqat "moslik" signali, qattiq filtr emas, va order=viewCount mintaqadan
qat'i nazar global hitlarni tepaga chiqaradi. Natijada til sozlamalari
qancha kuchaytirilmasin, natijalar baribir asosan hind tilida chiqib
qolardi.

Shuning uchun endi FAQAT YouTube'ning rasmiy TREND jadvalidan
(`videos.list`, `chart=mostPopular` — youtube.com/feed/trending bilan
bir xil manba) foydalaniladi — bu mintaqada AYNAN HOZIR trend bo'lgan
videolarni beradi, "qachondir eng ko'p ko'rilgan" emas:

  1) Avval REGION_CODE (va EXTRA_REGION_CODES'dagi har bir qo'shimcha
     mintaqa) uchun trend jadvali VIDEO_CATEGORY_ID (masalan "10" —
     Music) bilan cheklab so'raladi.
  2) Ko'p mintaqada kategoriya bilan cheklangan trend jadvali umuman
     mavjud emas (YouTube `videoChartNotFound` xatosini qaytaradi) —
     bunday holda avtomatik ravishda O'SHA mintaqaning UMUMIY trend
     jadvali (kategoriyasiz) olinadi va natijalar keyinroq
     `categoryId` bo'yicha (masalan faqat Music) filtrlanadi.
  3) Barcha mintaqalardan kelgan videolar ID bo'yicha birlashtiriladi
     (dublikatsiz).

Shundan keyin bir xil mezonlar (kategoriya, kalit so'z, davomiylik,
ko'rishlar soni, eskilik) bilan filtrlanadi. Har bir nomzod uchun tili
ham taxmin qilinadi (`lang_guess`: uz/en/ru/hi/other) — bu YERDA hech
narsa til bo'yicha chiqarib tashlanmaydi; qaysi tilga qanday ustunlik
berish (masalan hind tilini imkon qadar kam ko'rsatish) main.py'dagi
tanlov bosqichida (PREFERRED_LANGUAGES / AVOID_LANGUAGES) hal qilinadi,
shunda bitta til hammasini chiqarib tashlab, botni "hech narsa joylay
olmaydigan" holga keltirmaydi.

Kvota narxi: `videos.list` (chart bilan ham, oddiy ID bilan ham) har
doim ~1 birlik turadi (part parametridan qat'i nazar) — shuning uchun
bir nechta mintaqadan trend jadvalini olish juda arzon (odatda ~5-10
birlik/ishga tushirish, avvalgi ~600 birlikka nisbatan ancha kam).
"""
import logging
import re
import requests
from datetime import datetime, timedelta, timezone

log = logging.getLogger("trend_repost.youtube_trends")

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

_ISO8601_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)

_VIDEO_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:shorts/|watch\?(?:.*&)?v=|embed/|v/))([A-Za-z0-9_-]{11})"
)

# O'zbekcha ekanini taxmin qilish uchun (metama'lumotda til belgilanmagan
# videolar ko'p bo'lgani sabab, faqat defaultAudioLanguage'ga tayanib
# bo'lmaydi): o'zbek tiliga xos harflar (lotin apostrofli o'/g', kirill
# ў/қ/ғ/ҳ) yoki sarlavhada tez uchraydigan o'zbekcha so'zlar.
_UZBEK_CHARS_RE = re.compile(r"[ЎўҚқҒғҲҳ]|[oOgG][ʻʼ‘’`']")
_UZBEK_WORDS = {
    "qoshiq", "qo'shiq", "qo‘shiq", "qoshig'i", "ashula", "kuy", "tarona",
    "uzbek", "o'zbek", "o‘zbek", "ozbek", "milliy", "yangi", "consert",
    "konsert", "xalq", "qizlar", "yigitlar", "nomli", "olam", "yurt",
}


def looks_uzbek(title: str, channel: str = "") -> bool:
    """Sarlavha/kanal nomida o'zbek tiliga xos belgi yoki so'z bor-yo'qligini
    tekshiradi — bu qattiq isbot emas, faqat taxmin (heuristika)."""
    text = f"{title} {channel}"
    if _UZBEK_CHARS_RE.search(text):
        return True
    words = re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
    return any(w in _UZBEK_WORDS for w in words)


# Hindcha (devanagari yozuvi) ekanini aniqlash uchun — YouTube'da hind
# musiqasi ko'p videoning sarlavhasi shu yozuvda bo'ladi (kanal nomi
# lotincha bo'lsa ham).
_HINDI_SCRIPT_RE = re.compile(r"[ऀ-ॿ]")
# Kirill harflari — rus yoki (agar o'zbekchaga xos harflar/so'zlar
# bo'lmasa) umumiy taxmin sifatida rus tili deb hisoblanadi.
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def classify_language(lang_tag: str, title: str, channel: str = "") -> str:
    """Videoning tilini "uz", "en", "ru", "hi" yoki "other" (aniqlab
    bo'lmadi) sifatida taxmin qiladi.

    Avval YouTube'ning o'zi bergan lang_tag'ga (defaultAudioLanguage/
    defaultLanguage) ishoniladi, agar u shu to'rttadan biriga mos kelsa.
    Aks holda (yoki lang_tag bo'sh bo'lsa) sarlavha/kanal nomidagi
    belgilar asosida taxmin qilinadi: avval hind yozuvi (devanagari),
    keyin o'zbekchaga xos belgi/so'zlar (kirill bo'lsa ham — shuning
    uchun bu tekshiruv umumiy kirill tekshiruvidan OLDIN keladi), so'ng
    umumiy kirill (rus deb taxmin qilinadi), aks holda lotin harflari
    ustunlik qilsa ingliz deb taxmin qilinadi. Bu qattiq isbot emas,
    faqat taxmin — noaniq holatlarda "other" qaytariladi."""
    lang_tag = (lang_tag or "").lower()
    for code in ("uz", "en", "ru", "hi"):
        if lang_tag.startswith(code):
            return code

    text = f"{title} {channel}"
    if _HINDI_SCRIPT_RE.search(text):
        return "hi"
    if looks_uzbek(title, channel):
        return "uz"
    if _CYRILLIC_RE.search(text):
        return "ru"
    letters = re.findall(r"[^\W\d_]", text, flags=re.UNICODE)
    if letters and sum(1 for ch in letters if ch.isascii()) / len(letters) > 0.8:
        return "en"
    return "other"


def extract_video_id(url: str) -> str:
    """YouTube havolasidan (shorts/watch/youtu.be shakllari) video ID'ni
    ajratib oladi. Agar to'g'ridan-to'g'ri 11 xonali ID berilgan bo'lsa,
    o'shani qaytaradi. Tanib bo'lmasa ValueError ko'taradi."""
    url = url.strip()
    match = _VIDEO_ID_RE.search(url)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", url):
        return url
    raise ValueError(f"YouTube video ID'sini havoladan ajratib bo'lmadi: {url}")


def parse_iso8601_duration(duration: str) -> int:
    """'PT1M30S' kabi ISO8601 davomiylikni soniyaga aylantiradi."""
    match = _ISO8601_DURATION_RE.match(duration or "")
    if not match:
        return 0
    parts = match.groupdict()
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def _chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _get_json(url: str, params: dict, timeout: int = 20) -> dict:
    """requests.get + xato bo'lsa, Google/YouTube API qaytargan aniq sabab
    (masalan videoChartNotFound) bilan birga tushunarli xato ko'taradi —
    tozа "400 Client Error: Bad Request" o'rniga nima uchun xato
    ekanini ham ko'rsatadi."""
    resp = requests.get(url, params=params, timeout=timeout)
    if not resp.ok:
        reason = None
        message = None
        try:
            err = resp.json().get("error", {})
            message = err.get("message")
            errors_list = err.get("errors") or []
            if errors_list:
                reason = errors_list[0].get("reason")
        except ValueError:
            pass
        detail = message or resp.text[:200]
        if reason:
            detail = f"{detail} (reason: {reason})"
        raise requests.exceptions.HTTPError(
            f"{resp.status_code} xato ({url.rsplit('/', 1)[-1]}): {detail}", response=resp
        )
    return resp.json()


def search_short_video_ids(api_key: str, region_code: str, query: str,
                            max_age_hours: int, max_results: int = 50,
                            video_category_id: str = None,
                            video_duration: str = "short",
                            relevance_language: str = None) -> list:
    """So'rov so'ziga mos, ko'rishlar bo'yicha saralangan video ID'larni
    qaytaradi.

    video_duration: YouTube'ning `videoDuration` parametri — "short"
        (standart, < 4 daqiqa, ya'ni Shorts), "medium" (4-20 daqiqa),
        "long" (> 20 daqiqa) yoki "any" (cheklovsiz, uzun videolarni ham
        qidirish uchun).
    video_category_id berilsa (masalan "23" — Comedy), qidiruv shu
    kategoriya bilan cheklanadi — bu Roblox/o'yin kontentini boshidanoq
    katta qismini chetlab o'tishga yordam beradi.
    relevance_language berilsa (masalan "uz" — o'zbekcha), YouTube'ga shu
    tildagi natijalarni ustunroq ko'rsatish haqida ko'rsatma beriladi
    (`relevanceLanguage` parametri). Diqqat: bu qattiq filtr emas — faqat
    "moslik" signali, YouTube o'zi mos deb hisoblagan boshqa tildagi
    (masalan mintaqada mashhur hind-tilidagi) videolarni ham qaytarishi
    mumkin."""
    published_after = (
        datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    base_params = {
        "part": "id",
        "q": query,
        "type": "video",
        "order": "viewCount",
        "publishedAfter": published_after,
        "regionCode": region_code,
        "key": api_key,
    }
    if video_duration and video_duration != "any":
        base_params["videoDuration"] = video_duration
    if video_category_id:
        base_params["videoCategoryId"] = video_category_id
    if relevance_language:
        base_params["relevanceLanguage"] = relevance_language

    ids = []
    page_token = None
    while len(ids) < max_results:
        params = dict(base_params)
        params["maxResults"] = min(max_results - len(ids), 50)
        if page_token:
            params["pageToken"] = page_token
        data = _get_json(SEARCH_URL, params)
        page_ids = [item["id"]["videoId"] for item in data.get("items", []) if "videoId" in item.get("id", {})]
        ids.extend(page_ids)
        if not page_ids and "error" in data:
            log.warning("search.list API xatosi qaytardi: %s", data["error"])
        page_token = data.get("nextPageToken")
        if not page_token or not page_ids:
            break

    log.info(
        "search.list: q=%r, regionCode=%s, videoDuration=%s, publishedAfter=%s -> %d ta natija.",
        query, region_code, video_duration, published_after, len(ids),
    )
    return ids


def fetch_trending_chart_items(api_key: str, region_code: str, max_results: int = 50,
                                video_category_id: str = None) -> list:
    """YouTube'ning rasmiy trend jadvalidan (mostPopular) videolarni,
    to'liq statistikasi bilan birga oladi — zaxira manba sifatida.
    video_category_id berilsa, shu kategoriyadagi trend (masalan Comedy)
    olinadi.

    Diqqat: ko'p mintaqa+kategoriya kombinatsiyalari uchun YouTube'da
    "mostPopular" jadvali umuman mavjud emas — bunday holda API
    `videoChartNotFound` (400) xatosini qaytaradi. Bu chaqiruvchi kodda
    (get_trending_shorts) kutilgan holat sifatida ushlab olinadi, chunki
    bu faqat zaxira manba — asosiy manbalar (search.list) baribir
    ishlayveradi."""
    base_params = {
        "part": "snippet,contentDetails,statistics",
        "chart": "mostPopular",
        "regionCode": region_code,
        "key": api_key,
    }
    if video_category_id:
        base_params["videoCategoryId"] = video_category_id

    items = []
    page_token = None
    while len(items) < max_results:
        params = dict(base_params)
        params["maxResults"] = min(max_results - len(items), 50)
        if page_token:
            params["pageToken"] = page_token
        data = _get_json(VIDEOS_URL, params)
        page_items = data.get("items", [])
        items.extend(page_items)
        page_token = data.get("nextPageToken")
        if not page_token or not page_items:
            break

    log.info("videos.list(chart=mostPopular): regionCode=%s -> %d ta video.", region_code, len(items))
    return items


def fetch_video_details(api_key: str, video_ids: list) -> list:
    """Berilgan video ID'lar uchun statistika va davomiylikni oladi."""
    results = []
    for batch in _chunked(video_ids, 50):
        params = {
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(batch),
            "key": api_key,
        }
        data = _get_json(VIDEOS_URL, params)
        results.extend(data.get("items", []))
    return results


def get_trending_shorts(api_key: str, region_code: str = "UZ", min_views: int = 100_000,
                         max_age_hours: int = 168, max_duration_sec: int = 180,
                         max_results: int = 100,
                         video_category_id: str = "10",
                         exclude_category_ids: set = frozenset({"20"}),
                         exclude_keywords: list = None,
                         video_length_mode: str = "long",
                         max_long_duration_sec: int = 900,
                         extra_region_codes: list = None) -> list:
    """YouTube'ning rasmiy TREND jadvalidan (`chart=mostPopular`) —
    REGION_CODE va har bir EXTRA_REGION_CODES mintaqasidan — nomzodlarni
    yig'ib, birlashtirib, filtrlab qaytaradi. So'z (matn) bo'yicha
    qidiruv ISHLATILMAYDI — sababi modul docstring'ida tushuntirilgan.

    video_category_id: trend jadvalini shu kategoriya bilan cheklashga
        harakat qiladi (masalan "10" — Music). Agar YouTube shu
        mintaqa+kategoriya kombinatsiyasi uchun trend jadvalini
        bermasa (`videoChartNotFound`), avtomatik ravishda o'sha
        mintaqaning UMUMIY trend jadvali olinadi va natijalar keyinroq
        `categoryId` bo'yicha qo'lda filtrlanadi — shu bilan qaysi
        mintaqada bo'lmasin natija baribir topiladi.
    exclude_category_ids: shu kategoriyadagi videolar chiqarib
        tashlanadi (standart {"20"} — Gaming). exclude_keywords:
        sarlavhada shu so'zlar (kichik harfda) uchrasa video chiqarib
        tashlanadi (masalan ["roblox", "minecraft", "gameplay"]).
    video_length_mode:
        "short" — faqat Shorts (<= max_duration_sec) qoldiriladi.
        "long"  — faqat uzun videolar qoldiriladi (max_duration_sec
            dan max_long_duration_sec gacha), Shorts'siz.
        "both"  — ikkalasi ham (standart) — Shorts va uzun videolar
            birga nomzod bo'ladi.
    max_long_duration_sec: "long" yoki "both" rejimida ruxsat etilgan
        eng katta davomiylik (soniya, standart 900 = 15 daqiqa). Judayam
        uzun videolarni behuda yuklab olmaslik uchun.
    extra_region_codes: region_code'dan tashqari, trend jadvali ham
        olinadigan qo'shimcha mintaqalar ro'yxati (masalan ["US", "RU"])
        — faqat bitta mintaqaning trend jadvaliga tayanib qolmaslik
        uchun, natijalarni xilma-xillashtiradi.

    Har bir element: {id, title, channel, url, views, duration_sec,
                       published_at, published_at_ts, views_per_hour,
                       lang_guess, is_uzbek_guess, is_short, category_id}
    """
    if video_length_mode not in ("short", "long", "both"):
        video_length_mode = "both"
    if exclude_keywords is None:
        exclude_keywords = ["roblox", "gameplay", "minecraft", "fortnite", "gta", "pubg", "free fire"]
    exclude_keywords = [kw.lower() for kw in exclude_keywords if kw.strip()]

    def _fetch_chart_with_reason(source_name, region, category):
        """`fetch_trending_chart_items`ni chaqiradi, lekin xato bo'lsa
        (masalan `videoChartNotFound` yoki `invalidRegionCode`) butun
        ishga tushirishni yiqitmasdan, natija sifatida (bo'sh ro'yxat,
        xato sababi) qaytaradi — chaqiruvchi kod sabab bo'yicha turlicha
        (masalan qayta urinish yoki butunlay o'tkazib yuborish) qaror
        qabul qila oladi."""
        try:
            return fetch_trending_chart_items(api_key, region, max_results, category), None
        except requests.exceptions.RequestException as exc:
            reason_match = re.search(r"reason:\s*(\w+)", str(exc))
            reason = reason_match.group(1) if reason_match else None
            log.warning("%s manbasidan xato (o'tkazib yuborilmoqda): %s", source_name, exc)
            return [], reason

    def _fetch_region_trend(region: str) -> list:
        """Bitta mintaqa uchun trend jadvalini oladi — avval
        video_category_id bilan cheklab, agar shu kombinatsiya uchun
        YouTube'da trend jadvali mavjud bo'lmasa (`videoChartNotFound`),
        UMUMIY trend jadvaliga qaytadi va keyinroq categoryId bo'yicha
        qo'lda filtrlanadi (filtr bosqichida amalga oshadi). Agar esa
        MINTAQANING O'ZI trend jadvali (`chart=mostPopular`) uchun
        umuman qo'llab-quvvatlanmasa (`invalidRegionCode` — bu ba'zi
        kichikroq mintaqalar uchun YouTube'ning o'z cheklovi, .env
        xatosi emas), ikkinchi (umumiy) urinish ham baribir bir xil
        xato bilan tugashi aniq bo'lgani uchun, behuda API so'rovi
        yubormasdan darhol bo'sh ro'yxat bilan qaytiladi."""
        items, reason = _fetch_chart_with_reason(
            f"videos.list(chart=mostPopular, {region}, cat={video_category_id})",
            region, video_category_id,
        )
        if reason == "invalidRegionCode":
            log.warning(
                "%s mintaqasi uchun YouTube trend jadvali (chart=mostPopular) UMUMAN "
                "qo'llab-quvvatlanmaydi — bu YouTube'ning o'zi cheklovi (ba'zi kichikroq "
                "mintaqalarda bu API ishlamaydi), .env sozlamangizda xato emas. Shu "
                "mintaqa bu ishga tushirish uchun butunlay o'tkazib yuboriladi — "
                "EXTRA_REGION_CODES'dagi boshqa mintaqalardan baribir nomzod topiladi.",
                region,
            )
            return []
        if not items and video_category_id:
            log.info(
                "%s mintaqasida %s kategoriyasi uchun alohida trend jadvali topilmadi — "
                "umumiy trend jadvali olinib, keyin kategoriya bo'yicha filtrlanadi.",
                region, video_category_id,
            )
            items, _ = _fetch_chart_with_reason(
                f"videos.list(chart=mostPopular, {region}, umumiy)", region, None,
            )
        return items

    # Barcha mintaqalar (asosiy + qo'shimcha) uchun trend jadvalini olib,
    # ID bo'yicha birlashtiramiz (dublikatsiz — bir video bir nechta
    # mintaqada trend bo'lishi mumkin).
    regions = [region_code] + [
        r for r in (extra_region_codes or []) if r and r.upper() != region_code.upper()
    ]
    all_items_by_id = {}
    per_region_counts = {}
    for region in regions:
        region_items = _fetch_region_trend(region)
        per_region_counts[region] = len(region_items)
        for item in region_items:
            all_items_by_id[item["id"]] = item

    all_items = list(all_items_by_id.values())
    log.info(
        "Jami nomzodlar: %d (mintaqalar bo'yicha: %s)",
        len(all_items),
        ", ".join(f"{r}={c}" for r, c in per_region_counts.items()),
    )

    if not all_items:
        return []

    now = datetime.now(timezone.utc)
    min_published_at = now - timedelta(hours=max_age_hours)

    def _apply_filters():
        """Bitta filtrlash bosqichi (kategoriya, davomiylik, ko'rishlar,
        eskilik, mintaqaviy cheklov) — til bo'yicha hech narsa chiqarib
        tashlanmaydi, faqat `lang_guess` hisoblab qo'yiladi (yumshoq
        ustunlashtirish main.py'da bo'ladi)."""
        counts = {"category": 0, "duration": 0, "views": 0, "age": 0, "region_restricted": 0}
        result = []
        for item in all_items:
            stats = item.get("statistics", {})
            content = item.get("contentDetails", {})
            snippet = item.get("snippet", {})

            duration_sec = parse_iso8601_duration(content.get("duration", "PT0S"))
            views = int(stats.get("viewCount", 0))
            title_lower = snippet.get("title", "").lower()
            category_id = snippet.get("categoryId")

            # video_category_id berilgan bo'lsa (masalan "10" — Music),
            # boshqa kategoriyadagi videolar chiqarib tashlanadi — bu
            # ayniqsa UMUMIY trend jadvaliga qaytilgan mintaqalar uchun
            # muhim (u yerda barcha kategoriyalar aralash keladi).
            if video_category_id and category_id and category_id != video_category_id:
                counts["category"] += 1
                continue
            if category_id in exclude_category_ids or any(kw in title_lower for kw in exclude_keywords):
                counts["category"] += 1
                continue

            # Boshqa mintaqa(lar)ning trend jadvalidan (EXTRA_REGION_CODES)
            # olingan videolar ba'zan REGION_CODE (botning o'zi ishlaydi
            # deb hisoblangan mintaqa) uchun mualliflik-huquqi/litsenziya
            # sababli yopiq bo'lishi mumkin — bunday video yt-dlp orqali
            # yuklab bo'lmaydi ("Video unavailable"), shuning uchun uni
            # boshidanoq nomzodlar ro'yxatidan chiqarib tashlaymiz (aks
            # holda u bir "slot"ni band qilib, keyin yuklab bo'lmay,
            # o'sha slot uchun bekorga urinish sarflanardi).
            region_restriction = content.get("regionRestriction") or {}
            blocked = {c.upper() for c in (region_restriction.get("blocked") or [])}
            allowed = {c.upper() for c in (region_restriction.get("allowed") or [])}
            if region_code and (region_code.upper() in blocked or (allowed and region_code.upper() not in allowed)):
                counts["region_restricted"] += 1
                continue

            lang_tag = (snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage") or "").lower()
            if video_length_mode == "short":
                duration_ok = duration_sec <= max_duration_sec
            elif video_length_mode == "long":
                # Shorts uzunlikdagilar butunlay chiqarib tashlanadi —
                # faqat "uzun" hisoblanadigan videolar qoladi.
                duration_ok = max_duration_sec < duration_sec <= max_long_duration_sec
            else:  # "both"
                duration_ok = duration_sec <= max_long_duration_sec
            if not duration_ok:
                counts["duration"] += 1
                continue
            if views < min_views:
                counts["views"] += 1
                continue

            published_at_raw = snippet.get("publishedAt")
            try:
                published_at = datetime.strptime(published_at_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                published_at = now

            if published_at < min_published_at:
                counts["age"] += 1
                continue

            age_hours = max((now - published_at).total_seconds() / 3600, 0.5)

            # Shorts uchun /shorts/ havolasi, uzunroq videolar uchun
            # oddiy /watch?v= havolasi — ikkalasi ham YouTube'da to'g'ri
            # ochiladi va yt-dlp bilan ishonchli yuklanadi.
            video_url = (
                f"https://www.youtube.com/shorts/{item['id']}"
                if duration_sec <= max_duration_sec
                else f"https://www.youtube.com/watch?v={item['id']}"
            )

            lang_guess = classify_language(lang_tag, snippet.get("title", ""), snippet.get("channelTitle", ""))

            result.append({
                "id": item["id"],
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "url": video_url,
                "is_short": duration_sec <= max_duration_sec,
                "lang_guess": lang_guess,
                "is_uzbek_guess": lang_guess == "uz",
                "category_id": category_id,
                "views": views,
                "duration_sec": duration_sec,
                "published_at": published_at_raw,
                "published_at_ts": published_at.timestamp(),
                "views_per_hour": round(views / age_hours, 1),
            })
        return result, counts

    trending, counts = _apply_filters()

    # "Eng ko'p ko'rilgan" — soat boshiga tezlik emas, xom ko'rishlar soni
    # bo'yicha kamayish tartibida saralaymiz (views_per_hour faqat
    # ma'lumot sifatida saqlanadi).
    trending.sort(key=lambda v: v["views"], reverse=True)
    log.info(
        "Filtrdan o'tdi: %d ta. (kategoriya/kalit so'z bo'yicha chiqdi: %d, "
        "davomiylik bo'yicha chiqdi: %d, ko'rishlar bo'yicha chiqdi: %d, eskiligi bo'yicha chiqdi: %d, "
        "mintaqaviy cheklov bo'yicha chiqdi: %d)",
        len(trending), counts["category"], counts["duration"], counts["views"], counts["age"],
        counts["region_restricted"],
    )
    return trending
