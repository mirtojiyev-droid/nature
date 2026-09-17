"""
AI video generatsiya provayderlari uchun umumiy interfeys.

Nega abstraksiya kerak: har xil AI video xizmatlari (Runway, Kling va h.k.) turli xil
so'rov formati, autentifikatsiya usuli va narxga ega. Bu modul ularning barchasini BIR
XIL, sodda interfeys ortida yashiradi — shunda `generate_clips.py` skripti (va
kelajakda main.py) qaysi provayder ishlatilayotganidan qat'i nazar bir xil kodni
ishlatadi. Provayderni almashtirish uchun faqat `.env`dagi `AI_VIDEO_PROVIDER`
qiymatini o'zgartirish kifoya — kodni tahrirlash shart emas.

Yangi provayder qo'shish uchun: shu paketga yangi fayl (masalan `luma_provider.py`)
qo'shib, `AIVideoProvider`dan meros oling, so'ng `get_provider()` funksiyasiga bir
qator qo'shing.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


class AIVideoError(Exception):
    """AI video generatsiyasida xatolik yuz berganda ko'tariladi — chaqiruvchi
    (generate_clips.py) buni ushlab, foydalanuvchiga tushunarli xabar ko'rsatishi
    va keyingi so'rovga o'tishi kerak."""


@dataclass
class AIVideoResult:
    video_bytes: bytes
    provider_name: str
    model_name: str
    duration_sec: float
    width: int
    height: int


class AIVideoProvider(ABC):
    """Barcha AI video provayderlari shu interfeysga amal qiladi."""

    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, duration_sec: int = 8, vertical: bool = True) -> AIVideoResult:
        """Berilgan matn (prompt) asosida video yaratadi va TAYYOR bo'lguncha kutadi
        (provayderlarning aksariyati asinxron ishlaydi — bu funksiya ichida so'rov
        yuboriladi VA natija tayyor bo'lguncha so'raladi, chaqiruvchi uchun oddiy,
        sinxron ko'rinishda). Xatolik bo'lsa `AIVideoError` ko'taradi.

        `duration_sec` — so'ralgan davomiylik (provayder qo'llab-quvvatlaydigan eng
        yaqin qiymatga moslashtiriladi). `vertical` — True bo'lsa 9:16 (Shorts/Reels),
        False bo'lsa 16:9."""
        raise NotImplementedError


def get_provider(name: str) -> AIVideoProvider:
    """`.env`dagi AI_VIDEO_PROVIDER qiymatiga mos provayder obyektini qaytaradi.
    Noma'lum nom berilsa ValueError ko'taradi (aniq xato — jim ravishda noto'g'ri
    provayderga o'tib ketmasligi uchun)."""
    name = (name or "").strip().lower()
    if name == "runway":
        from .runway_provider import RunwayProvider
        return RunwayProvider()
    if name == "kling":
        from .kling_provider import KlingProvider
        return KlingProvider()
    raise ValueError(
        f"Noma'lum AI_VIDEO_PROVIDER: {name!r}. Qo'llab-quvvatlanadigan qiymatlar: "
        f"'runway', 'kling'."
    )
