"""
Umumiy Telegram Bot API orqali post joylash moduli — tabiat, kripto va futbol
botlarining barchasi shu moduldan foydalanadi (avval har biri o'zining alohida
nusxasiga ega edi; endi bitta joyda, kod takrorlanmaydi).

Qo'llab-quvvatlaydi:
- Tashqi URL orqali rasm/video joylash (masalan Pexels/Pixabay linki) — Telegram
  o'zi URL'dan yuklab oladi.
- Xotiradagi bayt (bytes) — masalan Pillow bilan chizilgan karta rasmi — to'g'ridan-to'g'ri
  multipart orqali yuklab joylash (diskka vaqtincha yozmasdan).
- Diskdagi video faylni multipart orqali yuklash (ffmpeg bilan tayyorlangandan keyin).
- Oddiy matnli xabar (masalan yangiliklar ro'yxati).
"""
import logging
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"

# Telegram caption/matn uchun maksimal uzunlik (belgida)
MAX_CAPTION_LENGTH = 1024
MAX_TEXT_LENGTH = 4096

_TAG_RE = re.compile(r"</?(\w+)[^>]*>")


def _close_unclosed_tags(text: str) -> str:
    """Qisqartirilgan matnda ochilgan-u lekin yopilmagan HTML teg (masalan matn oxirida
    kesilib qolgan "<b>" yoki "<a href=...>") qolmasligi uchun, ochiq qolgan teglarni
    охиrida avtomatik yopadi. Bunday teg qolib ketsa, Telegram butun postni "can't find
    end tag" xatosi bilan rad etadi — caption 1024 belgidan uzun bo'lgan (kamdan-kam)
    holatlarda buni oldini olish uchun kerak."""
    stack = []
    for m in _TAG_RE.finditer(text):
        tag = m.group(1).lower()
        if m.group(0).startswith("</"):
            if tag in stack:
                # Odatda oxirgisi (to'g'ri ichma-ich holat), lekin xavfsizlik uchun
                # ro'yxatda qayerda bo'lsa ham olib tashlaymiz.
                for i in range(len(stack) - 1, -1, -1):
                    if stack[i] == tag:
                        del stack[i]
                        break
        else:
            stack.append(tag)
    for tag in reversed(stack):
        text += f"</{tag}>"
    return text


class TelegramPoster:
    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token
        self.channel_id = channel_id

    def _url(self, method: str) -> str:
        return TELEGRAM_API_BASE.format(token=self.bot_token, method=method)

    @staticmethod
    def _trim(text: str, max_len: int) -> str:
        """Matnni max_len'gacha qisqartiradi. `parse_mode="HTML"` bilan yuborilgani
        uchun, oddiy uzunlik bo'yicha kesish xavfli — agar kesish nuqtasi aynan bir
        HTML tegi (masalan "<b>" yoki "&amp;") ICHIDA to'g'ri kelib qolsa, Telegram
        "can't parse entities" xatosi bilan BUTUN postni rad etadi. Shuning uchun
        kesilgan matnda ochiq (yopilmagan) teg yoki chala entity qolmasligini
        tekshiramiz — topilsa, o'sha yergacha (tegning boshigacha) qisqartiramiz."""
        if len(text) <= max_len:
            return text
        trimmed = text[: max_len - 1].rsplit(" ", 1)[0]

        # Kesilgan qism ichida yopilmagan "<...": oxirgi "<" oxirgi ">"dan keyin bo'lsa,
        # teg o'rtasida kesilgan demakdir — o'sha "<"gacha qaytaramiz.
        last_open = trimmed.rfind("<")
        last_close = trimmed.rfind(">")
        if last_open > last_close:
            trimmed = trimmed[:last_open].rstrip()

        # Xuddi shu mantiq chala HTML entity ("&amp" kabi, ";" siz qolgan) uchun ham.
        last_amp = trimmed.rfind("&")
        if last_amp != -1 and ";" not in trimmed[last_amp:]:
            trimmed = trimmed[:last_amp].rstrip()

        # Va nihoyat: agar kesish nuqtasi "<b>...</b>" kabi juftlikning O'RTASIGA tushib,
        # ochuvchi teg butun qolib, lekin uning yopuvchisi kesib tashlangan bo'lsa — shuni
        # ham yopib qo'yamiz (aks holda Telegram "end tag topilmadi" deb butun postni rad etadi).
        return _close_unclosed_tags(trimmed) + "…"

    def _send(self, method: str, payload: dict, files: dict | None = None) -> bool:
        """Umumiy yuborish funksiyasi. Telegram 400/403 qaytarsa ham, javob tanasidagi
        aniq sabab (masalan "can't parse entities", "chat not found") logga yoziladi —
        aks holda faqat "400 Bad Request" ko'rinib, aniq sababni topib bo'lmaydi."""
        try:
            timeout = 180 if files else 60
            resp = requests.post(self._url(method), data=payload, files=files, timeout=timeout)
        except requests.RequestException as exc:
            logger.error("Telegram %s so'rovida tarmoq xatoligi: %s", method, exc)
            return False

        try:
            result = resp.json()
        except ValueError:
            logger.error("Telegram %s: javobni o'qib bo'lmadi (status %s): %s", method, resp.status_code, resp.text[:500])
            return False

        if not result.get("ok"):
            logger.error(
                "Telegram %s rad etdi (status %s): %s",
                method,
                resp.status_code,
                result.get("description", result),
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Rasm
    # ------------------------------------------------------------------
    def post_photo(self, photo_url: str, caption: str) -> bool:
        """Tashqi URL'dagi rasmni joylaydi (Telegram o'zi URL'dan yuklab oladi) —
        Pexels/Pixabay/Wikimedia Commons kabi manbalardan kelgan rasm uchun."""
        caption = self._trim(caption, MAX_CAPTION_LENGTH)
        return self._send(
            "sendPhoto",
            {"chat_id": self.channel_id, "photo": photo_url, "caption": caption, "parse_mode": "HTML"},
        )

    def post_photo_bytes(self, photo_bytes: bytes, caption: str, filename: str = "card.png") -> bool:
        """Xotiradagi rasm baytlarini (masalan Pillow bilan chizilgan karta) to'g'ridan-to'g'ri
        multipart orqali yuklab joylaydi — diskka vaqtincha yozish shart emas."""
        caption = self._trim(caption, MAX_CAPTION_LENGTH)
        return self._send(
            "sendPhoto",
            {"chat_id": self.channel_id, "caption": caption, "parse_mode": "HTML"},
            files={"photo": (filename, photo_bytes, "image/png")},
        )

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------
    def post_video(self, video_url: str, caption: str) -> bool:
        caption = self._trim(caption, MAX_CAPTION_LENGTH)
        return self._send(
            "sendVideo",
            {"chat_id": self.channel_id, "video": video_url, "caption": caption, "parse_mode": "HTML"},
        )

    def post_video_file(self, file_path: Path, caption: str) -> bool:
        """Lokal diskdagi video faylni (masalan musiqa qo'shilgandan keyingi natijani)
        to'g'ridan-to'g'ri (multipart) yuklab, kanalga joylaydi."""
        caption = self._trim(caption, MAX_CAPTION_LENGTH)
        try:
            with open(file_path, "rb") as f:
                return self._send(
                    "sendVideo",
                    {"chat_id": self.channel_id, "caption": caption, "parse_mode": "HTML"},
                    files={"video": f},
                )
        except OSError as exc:
            logger.error("Video faylni ochib bo'lmadi (%s): %s", file_path, exc)
            return False

    # ------------------------------------------------------------------
    # Matn
    # ------------------------------------------------------------------
    def post_text(self, text: str, disable_preview: bool = True) -> bool:
        """Oddiy matnli xabar (masalan yangiliklar ro'yxati) — rasm/video yo'q."""
        text = self._trim(text, MAX_TEXT_LENGTH)
        return self._send(
            "sendMessage",
            {
                "chat_id": self.channel_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true" if disable_preview else "false",
            },
        )
