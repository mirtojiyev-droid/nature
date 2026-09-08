"""
Wikipedia REST API orqali berilgan joy haqida qisqacha ma'lumot (summary) topib beradi.
API kalit kerak emas, bepul va cheklovsiz.
"""
import logging

import requests

logger = logging.getLogger(__name__)

WIKI_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"


class InfoFetcher:
    def _find_best_title(self, query: str) -> str | None:
        try:
            resp = requests.get(
                WIKI_SEARCH_URL,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 1,
                },
                timeout=20,
                headers={"User-Agent": "NatureChannelBot/1.0"},
            )
            resp.raise_for_status()
            results = resp.json().get("query", {}).get("search", [])
            if not results:
                return None
            return results[0]["title"]
        except requests.RequestException as exc:
            logger.error("Wikipedia qidiruvida xatolik (%s): %s", query, exc)
            return None

    def fetch_summary(self, query: str) -> str | None:
        """Berilgan joy nomi bo'yicha eng mos Wikipedia maqolasining qisqacha matnini qaytaradi."""
        title = self._find_best_title(query)
        if not title:
            return None
        try:
            resp = requests.get(
                WIKI_SUMMARY_URL.format(title=title.replace(" ", "_")),
                timeout=20,
                headers={"User-Agent": "NatureChannelBot/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
            extract = data.get("extract")
            if not extract:
                return None
            return extract.strip()
        except requests.RequestException as exc:
            logger.error("Wikipedia summary olishda xatolik (%s): %s", title, exc)
            return None
