"""
Wikipedia REST API orqali berilgan mavzu (joy, futbolchi, voqea va h.k.) haqida
qisqacha ma'lumot (summary) topib beradi. API kalit kerak emas, bepul va cheklovsiz.
Bir nechta bot (tabiat, futbol) shu umumiy moduldan foydalanadi.

Wikipedia so'rov chastotasini ba'zan cheklaydi (429 Too Many Requests) — ayniqsa
bulut serverlarining IP manzillaridan (ko'p mijoz bitta IP orqali chiqadi). Shuning
uchun 429 uchun avtomatik qayta urinish (backoff bilan) qo'shilgan."""
import logging
import time

import requests

logger = logging.getLogger(__name__)

WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
_HEADERS = {"User-Agent": "BotHub/1.0 (https://github.com/; contact via repo)"}


def _get_with_retry(url: str, params: dict | None = None, max_retries: int = 3):
    """429 (Too Many Requests) javobida `Retry-After` sarlavhasini (yoki standart
    2 soniyani) kutib qayta uradi. Boshqa xatolarda darhol None qaytaradi (chaqiruvchi
    graceful tarzda davom etadi)."""
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=20, headers=_HEADERS)
        except requests.RequestException as exc:
            logger.warning("Wikipedia so'rovida tarmoq xatoligi: %s", exc)
            return None

        if resp.status_code == 429:
            if attempt >= max_retries:
                logger.warning("Wikipedia so'rov chastotasi chegarasiga (429) %d urinishdan keyin ham yechim topilmadi.", max_retries)
                return None
            wait = float(resp.headers.get("Retry-After", 2 * attempt))
            logger.info("Wikipedia so'rov chastotasi chegarasiga yetdik (429), %.0fs kutilmoqda...", wait)
            time.sleep(wait)
            continue

        try:
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Wikipedia so'rovida xatolik: %s", exc)
            return None
        return resp

    return None


class InfoFetcher:
    def _find_best_title(self, query: str) -> str | None:
        resp = _get_with_retry(
            WIKI_SEARCH_URL,
            params={"action": "query", "list": "search", "srsearch": query, "format": "json", "srlimit": 1},
        )
        if resp is None:
            return None
        results = resp.json().get("query", {}).get("search", [])
        if not results:
            return None
        return results[0]["title"]

    def fetch_summary(self, query: str) -> str | None:
        """Berilgan joy nomi bo'yicha eng mos Wikipedia maqolasining qisqacha matnini qaytaradi."""
        title = self._find_best_title(query)
        if not title:
            return None
        resp = _get_with_retry(WIKI_SUMMARY_URL.format(title=title.replace(" ", "_")))
        if resp is None:
            return None
        extract = resp.json().get("extract")
        return extract.strip() if extract else None
