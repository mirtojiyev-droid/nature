"""
Runway (RunwayML) — rasmiy Developer API orqali matndan video yaratish.

Hujjat: https://docs.dev.runwayml.com/ | API kalit: https://dev.runwayml.com/
Narxlash: kredit asosida, ~$0.01/kredit, gen4.5 modeli sekundiga ~12 kredit
(~$0.12/soniya) — aniq narxni dev.runwayml.com'dagi hisobingizdan tekshiring.

MUHIM: bu yerdagi endpoint/parametr nomlari 2026-yil sentyabr holatiga ko'ra rasmiy
hujjatlardan olingan. Runway API tez-tez yangilanadi — agar xato chiqsa, avval
docs.dev.runwayml.com'dagi eng so'nggi holatni tekshiring."""
import os
import time

import requests

from .base import AIVideoError, AIVideoProvider, AIVideoResult

API_BASE = "https://api.dev.runwayml.com/v1"
API_VERSION = "2024-11-06"  # Runway'ning talab qiladigan versiya sanasi header'i

# gen4.5 — matndan video (text-to-video) qo'llab-quvvatlaydigan Runway modeli
# (gen4_turbo FAQAT image-to-video uchun, matndan video uchun ishlamaydi).
MODEL = "gen4.5"

# gen4.5 qo'llab-quvvatlaydigan nisbatlar (kenglik:balandlik piksel shaklida yozilishi
# shart — oddiy "16:9" emas). Vertikal (Shorts/Reels) va gorizontal uchun eng yaqin mos
# keladiganini tanlaymiz.
RATIO_VERTICAL = "720:1280"
RATIO_HORIZONTAL = "1280:720"

POLL_INTERVAL_SEC = 5  # Runway "5 soniyada bir martadan ko'p so'ramang" deb tavsiya qiladi
MAX_POLL_ATTEMPTS = 60  # 5 daqiqagacha kutish (odatda 1-2 daqiqada tayyor bo'ladi)


class RunwayProvider(AIVideoProvider):
    name = "runway"

    def __init__(self):
        self.api_key = os.getenv("RUNWAY_API_KEY", "")
        if not self.api_key:
            raise AIVideoError("RUNWAY_API_KEY .env faylida sozlanmagan.")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": API_VERSION,
            "Content-Type": "application/json",
        }

    def generate(self, prompt: str, duration_sec: int = 8, vertical: bool = True) -> AIVideoResult:
        # gen4.5 davomiyligi 2-10 soniya oralig'ida bo'lishi kerak — shu oraliqqa cheklaymiz.
        duration_sec = max(2, min(10, duration_sec))
        ratio = RATIO_VERTICAL if vertical else RATIO_HORIZONTAL

        try:
            submit_resp = requests.post(
                f"{API_BASE}/text_to_video",
                headers=self._headers(),
                json={
                    "model": MODEL,
                    "promptText": prompt,
                    "ratio": ratio,
                    "duration": duration_sec,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            raise AIVideoError(f"Runway'ga so'rov yuborishda tarmoq xatoligi: {exc}") from exc

        if submit_resp.status_code >= 400:
            raise AIVideoError(
                f"Runway so'rovni rad etdi (HTTP {submit_resp.status_code}): {submit_resp.text[:500]}"
            )

        task_id = submit_resp.json().get("id")
        if not task_id:
            raise AIVideoError(f"Runway javobida task ID topilmadi: {submit_resp.text[:500]}")

        # Asinxron: tayyor bo'lguncha davriy so'rab turamiz.
        for _ in range(MAX_POLL_ATTEMPTS):
            time.sleep(POLL_INTERVAL_SEC)
            try:
                status_resp = requests.get(f"{API_BASE}/tasks/{task_id}", headers=self._headers(), timeout=20)
            except requests.RequestException as exc:
                raise AIVideoError(f"Runway holatini so'rashda tarmoq xatoligi: {exc}") from exc

            if status_resp.status_code >= 400:
                raise AIVideoError(f"Runway holat so'rovi xato qaytardi (HTTP {status_resp.status_code}).")

            data = status_resp.json()
            status = data.get("status")

            if status == "SUCCEEDED":
                output_urls = data.get("output") or []
                if not output_urls:
                    raise AIVideoError("Runway 'SUCCEEDED' deb qaytardi, lekin video havolasi yo'q.")
                video_url = output_urls[0]
                video_resp = requests.get(video_url, timeout=120)
                video_resp.raise_for_status()
                width, height = (1280, 720) if not vertical else (720, 1280)
                return AIVideoResult(
                    video_bytes=video_resp.content, provider_name=self.name, model_name=MODEL,
                    duration_sec=duration_sec, width=width, height=height,
                )

            if status == "FAILED":
                failure_reason = data.get("failure", "sabab noma'lum")
                raise AIVideoError(f"Runway video yaratishda muvaffaqiyatsiz bo'ldi: {failure_reason}")

            # PENDING / THROTTLED / RUNNING — hali tayyor emas, kutishda davom etamiz.

        raise AIVideoError(f"Runway {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SEC}s ichida yakunlamadi (task_id={task_id}).")
