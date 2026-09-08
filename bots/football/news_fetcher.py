"""Futbol yangiliklarini RSS orqali oladi (feedparser bilan, proxy shart emas —
news_fetcher.py'ning kripto botidagi hamkasbi bilan bir xil mantiq)."""
import logging
from urllib.parse import quote

import feedparser

from shared.translator import translate_to_uzbek

logger = logging.getLogger(__name__)

NEWS_FEEDS = [
    "http://feeds.bbci.co.uk/sport/football/rss.xml",
    "https://news.google.com/rss/search?q=" + quote("O'zbekiston futbol") + "&hl=uz&gl=UZ&ceid=UZ:uz",
]


def fetch_latest_news(limit: int = 5, translate: bool = True) -> list[dict]:
    items = []
    for feed_url in NEWS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
            if parsed.bozo and not parsed.entries:
                raise ValueError(str(parsed.bozo_exception))
            for entry in parsed.entries[:limit]:
                title = (entry.get("title") or "").strip()
                link = (entry.get("link") or "").strip()
                pub_date = entry.get("published_parsed") or entry.get("updated_parsed")
                if title:
                    items.append({"title": title, "link": link, "pub_date": pub_date})
        except Exception as exc:  # noqa: BLE001
            logger.warning("Yangilik olinmadi (%s): %s", feed_url, exc)

    with_date = [i for i in items if i["pub_date"]]
    without_date = [i for i in items if not i["pub_date"]]
    with_date.sort(key=lambda i: i["pub_date"], reverse=True)
    ordered = with_date + without_date

    seen = set()
    unique = []
    for item in ordered:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)
    unique = unique[:limit]

    if translate:
        # BBC manbasi ingliz tilida keladi — o'zbekchaga tarjima qilinadi. Google
        # News manbasi (hl=uz) allaqachon o'zbek tilida — translate_to_uzbek endi
        # manba tilini avtomatik aniqlagani (source="auto") uchun bu holatda ham
        # xavfsiz (allaqachon o'zbekcha matnni buzib qo'ymaydi).
        for item in unique:
            item["title"] = translate_to_uzbek(item["title"])

    return unique
