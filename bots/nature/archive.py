"""
JOYLANGAN POSTLAR ARXIVI — bir marta chiqqan video/rasm HECH QACHON qayta chiqmasligi uchun.

ESKI TIZIMNING KAMCHILIKLARI (aynan shular "vaqt o'tib qayta chiqish"ga sabab bo'lgan):
  1. posted_media_history.json konteyner ichida saqlanardi — HUB_DATA_DIR bo'sh bo'lsa,
     har DEPLOY'da (va Render free'da har restart/uyquda) BUTUNLAY o'chib ketardi.
     Arxiv bo'sh -> Pixabay/Pexels yana o'sha "top" natijalarni qaytaradi -> qayta post.
  2. Har turdan faqat so'nggi 3000 ta saqlanardi — eskilari "unutilib", qayta chiqardi.
  3. JSON fayl atomar yozilmagan: yozish paytida jarayon o'chsa, fayl buziladi va
     _load_json JIMGINA bo'sh ro'yxat qaytarardi — butun tarix yo'qolardi.
  4. Tekshiruv faqat "Manba:ID" bo'yicha — bir xil video Pixabay'da ham, Pexels'da ham
     bo'lsa (yoki Wikimedia'da boshqa nom bilan) — tanilmasdi.
  5. Eski yozuvlar xom URL ko'rinishida edi, keyin "Manba:ID" formatiga o'tildi —
     eski URL yozuvlari yangi kalitlar bilan solishtirilmasdi (migratsiya yo'q edi).
  6. localfootage/ videolari umuman arxivga yozilmasdi — bir xil fayl qayta-qayta chiqardi.
  7. Telegram'ga yuborish timeout bo'lsa (aslida post chiqqan bo'lsa ham), media
     "joylanmadi" deb belgilanmasdi — keyingi safar yana chiqardi.

YANGI TIZIM:
  - posted_archive.jsonl — faqat QO'SHILADIGAN (append-only) jurnal, HECH QACHON
    qisqartirilmaydi. Har bir qator: vaqt, tur, kalit, URL, manba, joy, qirra,
    sha256, perceptual hash, Telegram message_id.
  - Har yozuvdan keyin fsync; buzilgan qator bo'lsa faqat o'sha qator tashlanadi.
  - Kontent barmoq izi (fingerprint.py) — manba/URL/sifatdan qat'i nazar dublikat topadi.
  - "pending" -> "posted" / "released" oqimi: yuborishdan OLDIN band qilinadi; natija
    noaniq bo'lsa (timeout) — "joylangan" deb qoladi (takrordan ko'ra o'tkazib yuborish yaxshi).
  - TELEGRAM ZAXIRA: .env'da NATURE_ARCHIVE_CHAT_ID berilsa, arxiv fayli o'sha chatga
    (masalan shaxsiy yopiq kanal) hujjat sifatida yuklanib, PIN qilinadi va har postdan
    keyin yangilanadi. Konteyner o'chib ketsa ham, ishga tushganda pin'dagi arxiv
    yuklab olinib tiklanadi — Persistent Disk shart emas.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

import requests

from shared.data_dir import get_data_dir

from .fingerprint import is_similar

logger = logging.getLogger(__name__)

_DATA_DIR = get_data_dir("nature", Path(__file__).parent)
ARCHIVE_FILE = _DATA_DIR / "posted_archive.jsonl"
LEGACY_FILE = _DATA_DIR / "posted_media_history.json"
REMOTE_FILE_NAME = "nature_posted_archive.jsonl"

ACTIVE = ("pending", "posted", "uncertain")

_lock = threading.RLock()
_loaded = False
_entries: dict[str, dict] = {}   # "kind|key" -> oxirgi holat yozuvi
_urls: dict[str, set] = {"video": set(), "photo": set()}
_remote_msg_id: int | None = None


def _k(kind: str, key: str) -> str:
    return f"{kind}|{key}"


# --------------------------------------------------------------------------------
# Lokal fayl
# --------------------------------------------------------------------------------
def _apply(rec: dict) -> None:
    kind, key = rec.get("kind"), rec.get("key")
    if kind not in _urls or not key:
        return
    k = _k(kind, key)
    if rec.get("event") == "released":
        old = _entries.pop(k, None)
        if old and old.get("url"):
            _urls[kind].discard(old["url"])
        return
    prev = _entries.get(k, {})
    merged = {**prev, **{f: v for f, v in rec.items() if v not in (None, "", [])}}
    _entries[k] = merged
    if merged.get("url"):
        _urls[kind].add(merged["url"])


def _parse_lines(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if isinstance(rec, dict):
                out.append(rec)
        except json.JSONDecodeError:
            logger.warning("Arxivda buzilgan qator tashlab ketildi: %s", line[:120])
    return out


def _append_lines(recs: list[dict]) -> None:
    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ARCHIVE_FILE, "a", encoding="utf-8") as f:
        for rec in recs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _migrate_legacy() -> list[dict]:
    """Eski posted_media_history.json'dagi yozuvlarni arxivga ko'chiradi (bir marta)."""
    if not LEGACY_FILE.exists():
        return []
    try:
        data = json.loads(LEGACY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    recs = []
    for kind in ("video", "photo"):
        for item in data.get(kind, []) or []:
            if not isinstance(item, str) or not item:
                continue
            is_url = item.startswith("http")
            recs.append({
                "ts": 0, "event": "posted", "kind": kind, "key": item,
                "url": item if is_url else None, "source": "legacy",
            })
    try:
        LEGACY_FILE.rename(LEGACY_FILE.with_suffix(".json.migrated"))
    except OSError:
        pass
    if recs:
        logger.info("Eski media tarixidan %d ta yozuv yangi arxivga ko'chirildi.", len(recs))
    return recs


# --------------------------------------------------------------------------------
# Telegram zaxira (ixtiyoriy, lekin Render/Railway uchun TAVSIYA ETILADI)
# --------------------------------------------------------------------------------
def _remote_cfg() -> tuple[str, str] | None:
    token = os.getenv("NATURE_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("NATURE_ARCHIVE_CHAT_ID", "").strip()
    return (token, chat) if token and chat else None


def _api(token: str, method: str, **kw):
    resp = requests.post(f"https://api.telegram.org/bot{token}/{method}", timeout=60, **kw)
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", str(data)))
    return data["result"]


def _download_remote() -> str | None:
    global _remote_msg_id
    cfg = _remote_cfg()
    if not cfg:
        return None
    token, chat = cfg
    try:
        chat_info = _api(token, "getChat", data={"chat_id": chat})
        pinned = chat_info.get("pinned_message") or {}
        doc = pinned.get("document") or {}
        if doc.get("file_name") != REMOTE_FILE_NAME:
            return None
        _remote_msg_id = pinned.get("message_id")
        file_info = _api(token, "getFile", data={"file_id": doc["file_id"]})
        r = requests.get(f"https://api.telegram.org/file/bot{token}/{file_info['file_path']}", timeout=60)
        r.raise_for_status()
        return r.content.decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram'dagi arxiv zaxirasini o'qib bo'lmadi: %s", exc)
        return None


def backup_remote() -> None:
    """Arxiv faylini NATURE_ARCHIVE_CHAT_ID chatiga yuklaydi (pin'dagi xabarni tahrirlaydi,
    bo'lmasa yangisini yuborib pin qiladi). Xatolik botni to'xtatmaydi."""
    global _remote_msg_id
    cfg = _remote_cfg()
    if not cfg or not ARCHIVE_FILE.exists():
        return
    token, chat = cfg
    caption = f"🗄 Tabiat boti arxivi — {len(_entries)} ta yozuv. O'CHIRMANG va pinni olib tashlamang."
    with _lock:
        payload = ARCHIVE_FILE.read_bytes()
    try:
        if _remote_msg_id:
            try:
                _api(token, "editMessageMedia", data={
                    "chat_id": chat, "message_id": _remote_msg_id,
                    "media": json.dumps({"type": "document", "media": "attach://f", "caption": caption}),
                }, files={"f": (REMOTE_FILE_NAME, payload)})
                return
            except Exception as exc:  # noqa: BLE001
                logger.info("Pin'dagi arxivni tahrirlab bo'lmadi (%s) — yangisi yuboriladi.", exc)
        msg = _api(token, "sendDocument", data={
            "chat_id": chat, "caption": caption, "disable_notification": "true",
        }, files={"document": (REMOTE_FILE_NAME, payload)})
        _remote_msg_id = msg["message_id"]
        _api(token, "pinChatMessage", data={
            "chat_id": chat, "message_id": _remote_msg_id, "disable_notification": "true",
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning("Arxivni Telegram'ga zaxiralab bo'lmadi: %s", exc)


# --------------------------------------------------------------------------------
# Ommaviy API
# --------------------------------------------------------------------------------
def ensure_loaded() -> None:
    global _loaded
    with _lock:
        if _loaded:
            return
        local_recs = _parse_lines(ARCHIVE_FILE.read_text(encoding="utf-8")) if ARCHIVE_FILE.exists() else []
        new_recs = _migrate_legacy()

        remote_text = _download_remote()
        if remote_text:
            seen = {json.dumps(r, sort_keys=True) for r in local_recs}
            remote_only = [r for r in _parse_lines(remote_text) if json.dumps(r, sort_keys=True) not in seen]
            if remote_only:
                logger.info("Telegram zaxirasidan %d ta arxiv yozuvi tiklandi.", len(remote_only))
                new_recs = remote_only + new_recs

        if new_recs:
            try:
                _append_lines(new_recs)
            except OSError as exc:
                logger.warning("Arxivga yozib bo'lmadi: %s", exc)
        for rec in local_recs + new_recs:
            _apply(rec)
        _loaded = True
        logger.info("Arxiv yuklandi: %d ta joylangan media (fayl: %s).", len(_entries), ARCHIVE_FILE)

        if not os.getenv("HUB_DATA_DIR", "").strip() and not _remote_cfg():
            logger.warning(
                "DIQQAT: HUB_DATA_DIR ham, NATURE_ARCHIVE_CHAT_ID ham sozlanmagan — arxiv faqat "
                "konteyner ichida. Render/Railway'da deploy qilinganda arxiv O'CHADI va eski "
                "postlar qayta chiqishi mumkin. .env.example'ga qarang."
            )
        if new_recs and _remote_cfg() and not remote_text:
            backup_remote()


def _record(event: str, kind: str, key: str, **meta) -> None:
    rec = {"ts": int(time.time()), "event": event, "kind": kind, "key": key, **meta}
    with _lock:
        _apply(rec)
        try:
            _append_lines([rec])
        except OSError as exc:
            logger.error("Arxivga yozib bo'lmadi (post baribir xotirada belgilandi): %s", exc)


def is_posted(kind: str, key: str | None = None, url: str | None = None) -> bool:
    ensure_loaded()
    with _lock:
        if key:
            e = _entries.get(_k(kind, key))
            if e and e.get("event") in ACTIVE:
                return True
        return bool(url and url in _urls.get(kind, set()))


def find_duplicate_content(kind: str, fp: dict | None) -> dict | None:
    """Barmoq izi bo'yicha allaqachon joylangan o'xshash kontentni qaytaradi (yoki None)."""
    if not fp:
        return None
    ensure_loaded()
    sha, ph = fp.get("sha256"), fp.get("phash")
    with _lock:
        for e in _entries.values():
            if e.get("kind") != kind or e.get("event") not in ACTIVE:
                continue
            if sha and e.get("sha256") == sha:
                return e
            if ph and e.get("phash") and is_similar(kind, ph, e["phash"]):
                return e
    return None


def reserve(kind: str, key: str, **meta) -> None:
    """Yuborishdan OLDIN chaqiriladi — jarayon yuborish o'rtasida o'chsa ham qayta chiqmaydi."""
    _record("pending", kind, key, **meta)


def confirm(kind: str, key: str, message_id: int | None = None, uncertain: bool = False) -> None:
    _record("uncertain" if uncertain else "posted", kind, key, message_id=message_id)
    backup_remote()


def release(kind: str, key: str) -> None:
    """Telegram postni ANIQ rad etgan bo'lsa — media keyinroq qayta sinalishi mumkin."""
    _record("released", kind, key)


def stats() -> dict:
    ensure_loaded()
    with _lock:
        by_kind: dict[str, int] = {}
        for e in _entries.values():
            if e.get("event") in ACTIVE:
                by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
        return {"total": sum(by_kind.values()), **by_kind, "file": str(ARCHIVE_FILE)}


if __name__ == "__main__":
    # hub papkasidan: python -m bots.nature.archive
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(stats(), ensure_ascii=False, indent=2))
