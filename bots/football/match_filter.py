"""Sanaga qarab so'nggi natijalar va kelgusi o'yinlarni filtrlaydi (futbol_bot_mobil.html
porti)."""
import logging
import time
from datetime import date, datetime

from . import sportsdb_api

logger = logging.getLogger(__name__)


def _days_between(date_str: str, ref: date) -> int:
    """Musbat = o'tmishda, manfiy = kelajakda."""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return (ref - d).days


def collect_recent_results(leagues: list[dict], days_back: int, on_progress=None) -> list[dict]:
    today = date.today()
    results = []
    for league in leagues:
        try:
            events = sportsdb_api.get_past_events(league["id"])
            for ev in events:
                if not ev.get("dateEvent"):
                    continue
                diff = _days_between(ev["dateEvent"], today)
                if (
                    0 <= diff <= days_back
                    and ev.get("intHomeScore") is not None
                    and ev.get("intAwayScore") is not None
                    and sportsdb_api.is_match_finished(ev)
                ):
                    results.append({**ev, "leagueName": league["name"], "leagueMeta": league})
        except Exception:  # noqa: BLE001 - bitta liga muvaffaqiyatsiz bo'lsa qolganlar bilan davom etamiz
            logger.warning("%s natijalari olinmadi.", league["name"])
        if on_progress:
            on_progress(league["name"])
        time.sleep(0.2)

    results.sort(key=lambda r: r.get("dateEvent") or "", reverse=True)

    # Har bir natija uchun gol urgan futbolchi va daqiqasini olamiz
    for match in results:
        match["goals"] = sportsdb_api.get_goal_timeline(match.get("idEvent"))
        try:
            expected_goals = int(match.get("intHomeScore") or 0) + int(match.get("intAwayScore") or 0)
        except (TypeError, ValueError):
            expected_goals = 0
        match["goalsComplete"] = expected_goals > 0 and len(match["goals"]) == expected_goals
        if on_progress:
            on_progress(f"Gollar: {match.get('strHomeTeam')} — {match.get('strAwayTeam')}")
        time.sleep(0.15)

    return results


def collect_upcoming_fixtures(leagues: list[dict], days_forward: int, on_progress=None) -> list[dict]:
    today = date.today()
    fixtures = []
    for league in leagues:
        try:
            events = sportsdb_api.get_next_events(league["id"])
            for ev in events:
                if not ev.get("dateEvent"):
                    continue
                diff = _days_between(ev["dateEvent"], today)
                if -days_forward <= diff <= 0:
                    fixtures.append({**ev, "leagueName": league["name"], "leagueMeta": league})
        except Exception:  # noqa: BLE001
            logger.warning("%s o'yinlari olinmadi.", league["name"])
        if on_progress:
            on_progress(league["name"])
        time.sleep(0.2)

    fixtures.sort(key=lambda f: f.get("dateEvent") or "")
    return fixtures
