"""Kripto yangiliklarini RSS orqali oladi. Brauzer versiyasida CORS proxy orqali
o'qilardi (`api.allorigins.win`); server tomonida bunday cheklov yo'q, to'g'ridan-to'g'ri
`feedparser` bilan o'qiladi — ancha ishonchli (turli xil RSS formatlarini avtomatik
tushunadi)."""
import html
import logging

import feedparser

from shared.hashtags import format_hashtags

logger = logging.getLogger(__name__)

NEWS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]


def fetch_latest_news(limit: int = 5) -> list[dict]:
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
        except Exception as exc:  # noqa: BLE001 - RSS manba muvaffaqiyatsiz bo'lsa botni to'xtatmaymiz
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
    return unique[:limit]


def build_news_caption(news_items: list[dict], header: str = "So'nggi kripto yangiliklari") -> str | None:
    if not news_items:
        return None
    lines = [f"📰 <b>{header}</b>", ""]
    for item in news_items:
        title = html.escape(item["title"])
        lines.append(f"• <a href=\"{item['link']}\">{title}</a>")
    lines.append("")
    lines.append(format_hashtags(["kripto", "crypto", "yangiliklar", "bitcoin"]))
    return "\n".join(lines)
