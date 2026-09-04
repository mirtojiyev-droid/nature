"""
Telegram Bot API orqali kanalga rasm yoki video + caption joylaydi.
Bot kanalga admin sifatida qo'shilgan bo'lishi shart (kamida "Post messages" huquqi bilan).
"""
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/{method}"

# Telegram caption uchun maksimal uzunlik (belgida)
MAX_CAPTION_LENGTH = 1024


class TelegramPoster:
    def __init__(self, bot_token: str, channel_id: str):
        self.bot_token = bot_token
        self.channel_id = channel_id

    def _url(self, method: str) -> str:
        return TELEGRAM_API_BASE.format(token=self.bot_token, method=method)

    @staticmethod
    def _trim_caption(caption: str) -> str:
        if len(caption) <= MAX_CAPTION_LENGTH:
            return caption
        return caption[: MAX_CAPTION_LENGTH - 1].rsplit(" ", 1)[0] + "…"

    def _send(self, method: str, payload: dict, files: dict | None = None) -> bool:
        """Umumiy yuborish funksiyasi. Telegram 400/403 qaytarsa ham, javob tanasidagi
        aniq sabab (masalan "can't parse entities", "chat not found") logga yoziladi —
        aks holda faqat "400 Bad Request" ko'rinib, aniq sababni topib bo'lmaydi.
        `files` berilsa (lokal fayl yuklashda), multipart so'rov yuboriladi."""
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

    def post_photo(self, photo_url: str, caption: str) -> bool:
        caption = self._trim_caption(caption)
        return self._send(
            "sendPhoto",
            {
                "chat_id": self.channel_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": "HTML",
            },
        )

    def post_video(self, video_url: str, caption: str) -> bool:
        caption = self._trim_caption(caption)
        return self._send(
            "sendVideo",
            {
                "chat_id": self.channel_id,
                "video": video_url,
                "caption": caption,
                "parse_mode": "HTML",
            },
        )

    def post_video_file(self, file_path: Path, caption: str) -> bool:
        """Lokal diskdagi video faylni (masalan musiqa qo'shilgandan keyingi natijani)
        to'g'ridan-to'g'ri (multipart) yuklab, kanalga joylaydi."""
        caption = self._trim_caption(caption)
        try:
            with open(file_path, "rb") as f:
                return self._send(
                    "sendVideo",
                    {
                        "chat_id": self.channel_id,
                        "caption": caption,
                        "parse_mode": "HTML",
                    },
                    files={"video": f},
                )
        except OSError as exc:
            logger.error("Video faylni ochib bo'lmadi (%s): %s", file_path, exc)
            return False
