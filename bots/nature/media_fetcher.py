"""
Umumiy fayl yuklab olish yordamchilari (video/rasm) — manbadan qat'i nazar (Pixabay,
Wikimedia Commons, localfootage) ishlatiladi.

MUHIM (tarix uchun eslatma): bu fayl avval Pexels API integratsiyasini ham o'z ichiga
olardi (`MediaFetcher` klassi). Foydalanuvchi qarori bilan Pexels butunlay olib
tashlangach (endi FAQAT Pixabay ishlatiladi — pixabay_fetcher.py'ga qarang), o'sha
klass ishlatilmay qoldi va shu yerdan olib tashlandi — faqat quyidagi ikkita generic
(manbadan mustaqil) yuklab olish funksiyasi qoldi.
"""
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


def download_file(url: str, dest_path: Path, timeout: int = 60) -> bool:
    """Berilgan URL'dagi faylni (video/rasm) diskka yuklab oladi — musiqa qo'shish kabi
    lokal ishlov berish kerak bo'lganda ishlatiladi. Xatolik bo'lsa False qaytaradi,
    chaqiruvchi shu holatda boshqa manba/nomzodga o'tishi kerak."""
    try:
        resp = requests.get(url, stream=True, timeout=timeout)
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                f.write(chunk)
        return True
    except (requests.RequestException, OSError) as exc:
        logger.warning("Faylni yuklab olishda xatolik (%s): %s", url, exc)
        return False


def download_bytes(url: str, timeout: int = 30) -> bytes | None:
    """`download_file`ning xotiraga (disksiz) versiyasi — rasmga brendlash overlay
    chizish kabi, faylni diskka saqlamasdan to'g'ridan-to'g'ri qayta ishlash kerak
    bo'lgan hollar uchun (masalan photo_overlay.py). Xatolik bo'lsa None qaytaradi."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as exc:
        logger.warning("Faylni xotiraga yuklab olishda xatolik (%s): %s", url, exc)
        return None
