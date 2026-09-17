"""
Kling (Kuaishou) — rasmiy API orqali matndan video yaratish.

Hujjat: https://app.klingai.com/global/dev/document-api | Kalitlar: Access Key + Secret
Key juftligi (oddiy Bearer token EMAS — har bir so'rov uchun qisqa muddatli JWT token
o'zingiz tomondan generatsiya qilinishi kerak, quyida `_build_jwt()`).

MUHIM: Kling'ning ikkita asosiy kalit turi bor: Access Key (AK) va Secret Key (SK) —
ikkalasi ham kerak (`KLING_ACCESS_KEY`, `KLING_SECRET_KEY`). Bu — Runway'dagi bitta
oddiy API kalitdan farqli, biroz murakkabroq autentifikatsiya usuli.

Narxlash: oldindan sotib olinadigan "resurs birligi" paketlari orqali — aniq narxni
klingai.com hisobingizdan tekshiring."""
import os
import time

import requests

from .base import AIVideoError, AIVideoProvider, AIVideoResult

# Xalqaro (global) API manzili — agar hisobingiz boshqa mintaqada bo'lsa, .env orqali
# almashtirilishi mumkin (KLING_API_BASE).
DEFAULT_API_BASE = "https://api-singapore.klingai.com"

MODEL = "kling-v2-master"
POLL_INTERVAL_SEC = 8
MAX_POLL_ATTEMPTS = 45  # ~6 daqiqagacha kutish


def _build_jwt(access_key: str, secret_key: str) -> str:
    """Kling har bir so'rov uchun qisqa muddatli (30 daqiqalik) JWT token talab qiladi —
    bu tokenni har safar o'zimiz (PyJWT bilan) generatsiya qilamiz, Kling'ning o'zidan
    so'rab olinmaydi."""
    try:
        import jwt
    except ImportError as exc:
        raise AIVideoError(
            "Kling provayderi uchun 'PyJWT' kutubxonasi kerak — "
            "requirements.txt'ga qo'shilgan, `pip install -r requirements.txt` qiling."
        ) from exc
    now = int(time.time())
    payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
    return jwt.encode(payload, secret_key, algorithm="HS256", headers={"alg": "HS256", "typ": "JWT"})


class KlingProvider(AIVideoProvider):
    name = "kling"

    def __init__(self):
        self.access_key = os.getenv("KLING_ACCESS_KEY", "")
        self.secret_key = os.getenv("KLING_SECRET_KEY", "")
        self.api_base = os.getenv("KLING_API_BASE", DEFAULT_API_BASE).rstrip("/")
        if not self.access_key or not self.secret_key:
            raise AIVideoError("KLING_ACCESS_KEY va/yoki KLING_SECRET_KEY .env faylida sozlanmagan.")

    def _headers(self) -> dict:
        token = _build_jwt(self.access_key, self.secret_key)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def generate(self, prompt: str, duration_sec: int = 8, vertical: bool = True) -> AIVideoResult:
        # Kling odatda 5 yoki 10 soniyalik variantlarni qo'llab-quvvatlaydi — eng
        # yaqinini tanlaymiz.
        duration = "10" if duration_sec >= 8 else "5"
        aspect_ratio = "9:16" if vertical else "16:9"

        try:
            submit_resp = requests.post(
                f"{self.api_base}/v1/videos/text2video",
                headers=self._headers(),
                json={
                    "model_name": MODEL,
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "duration": duration,
                },
                timeout=30,
            )
        except requests.RequestException as exc:
            raise AIVideoError(f"Kling'ga so'rov yuborishda tarmoq xatoligi: {exc}") from exc

        if submit_resp.status_code >= 400:
            raise AIVideoError(f"Kling so'rovni rad etdi (HTTP {submit_resp.status_code}): {submit_resp.text[:500]}")

        submit_data = submit_resp.json()
        task_id = (submit_data.get("data") or {}).get("task_id")
        if not task_id:
            raise AIVideoError(f"Kling javobida task_id topilmadi: {submit_resp.text[:500]}")

        for _ in range(MAX_POLL_ATTEMPTS):
            time.sleep(POLL_INTERVAL_SEC)
            try:
                status_resp = requests.get(
                    f"{self.api_base}/v1/videos/text2video/{task_id}", headers=self._headers(), timeout=20,
                )
            except requests.RequestException as exc:
                raise AIVideoError(f"Kling holatini so'rashda tarmoq xatoligi: {exc}") from exc

            if status_resp.status_code >= 400:
                raise AIVideoError(f"Kling holat so'rovi xato qaytardi (HTTP {status_resp.status_code}).")

            data = (status_resp.json() or {}).get("data") or {}
            status = data.get("task_status")

            if status == "succeed":
                videos = ((data.get("task_result") or {}).get("videos")) or []
                if not videos:
                    raise AIVideoError("Kling 'succeed' deb qaytardi, lekin video havolasi yo'q.")
                video_url = videos[0]["url"]
                # MUHIM: Kling'ning video havolasi qisqa muddat ichida eskiradi — shuning
                # uchun darhol yuklab olamiz, keyinga qoldirmaymiz.
                video_resp = requests.get(video_url, timeout=120)
                video_resp.raise_for_status()
                width, height = (720, 1280) if vertical else (1280, 720)
                return AIVideoResult(
                    video_bytes=video_resp.content, provider_name=self.name, model_name=MODEL,
                    duration_sec=float(duration), width=width, height=height,
                )

            if status == "failed":
                failure_reason = data.get("task_status_msg", "sabab noma'lum")
                raise AIVideoError(f"Kling video yaratishda muvaffaqiyatsiz bo'ldi: {failure_reason}")

            # submitted / processing — hali tayyor emas.

        raise AIVideoError(f"Kling {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SEC}s ichida yakunlamadi (task_id={task_id}).")
