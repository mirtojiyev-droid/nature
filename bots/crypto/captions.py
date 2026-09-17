"""Coin/breakout postlarining matn qismi (caption).

MUHIM (foydalanuvchi tahlili asosida qayta ishlangan): avval bu yerda kartada
allaqachon ko'rsatilgan narx/foiz/RSI ma'lumotlari yana MATN sifatida
takrorlanardi — foydalanuvchi bir xil narsani ikki marta o'qishga majbur
bo'lardi. Endi caption FAQAT qisqa, emojili xulosa va hashteglardan iborat —
barcha raqamlar FAQAT kartaning o'zida (rasmda)."""
import random

from shared.hashtags import format_hashtags, slugify_hashtag
from .analysis import signed_num

CHANNEL_HASHTAGS = ["kripto", "crypto"]

# Har biri qisqa, emojili, raqamsiz xulosa — bir xil coin ketma-ket ko'p marta
# joylansa ham matn zerikarli/bir xil bo'lib qolmasligi uchun bir nechtadan tanlanadi.
_UP_PHRASES = [
    "\U0001F680 Kuchli ko'tarilish davom etyapti!",
    "\U0001F4C8 Bugungi eng yaxshi ko'rsatkichlardan biri.",
    "\U0001F525 Xaridorlar bosimi sezilarli.",
    "\u26A1 Diqqatga molik harakat.",
]
_DOWN_PHRASES = [
    "\U0001F4C9 Sotuvchilar bosim o'tkazmoqda.",
    "\U0001F9CA Sovish davom etyapti.",
    "\u26A0\uFE0F Ehtiyot bo'lish tavsiya etiladi.",
    "\U0001F4C9 Bugungi eng zaif ko'rsatkichlardan biri.",
]
_BREAKOUT_PHRASES = [
    "\U0001F440 Radar ostida — erta signal.",
    "\U0001F4CA Hajm sezilarli oshdi, kuzatishga arziydi.",
    "\U0001F9E9 Naqsh shakllanmoqda.",
]


def build_caption_single(coin: dict, is_up: bool, rank: int) -> str:
    symbol = coin["symbol"].replace("USDT", "")
    phrase = random.choice(_UP_PHRASES if is_up else _DOWN_PHRASES)
    category_tag = slugify_hashtag("Osuvchi" if is_up else "Tushuvchi")
    lines = [
        phrase,
        "",
        "<i>Bu moliyaviy maslahat emas \u2014 faqat statistik kuzatuv.</i>",
        "",
        format_hashtags([*CHANNEL_HASHTAGS, symbol, category_tag, "trading"]),
    ]
    return "\n".join(lines)


def build_breakout_caption(candidate: dict, rank: int, notes: list[str]) -> str:
    symbol = candidate["symbol"].replace("USDT", "")
    phrase = random.choice(_BREAKOUT_PHRASES)
    lines = [
        phrase,
        "",
        "<i>Bu statistik naqsh \u2014 kafolat emas. Moliyaviy maslahat emas.</i>",
        "",
        format_hashtags([*CHANNEL_HASHTAGS, symbol, "breakout", "kuzatuv"]),
    ]
    return "\n".join(lines)


def build_poll_question(symbol: str) -> tuple[str, list[str]]:
    """Har bir coin posti bilan birga yuboriladigan (ixtiyoriy) Telegram so'rovnoma
    savoli va variantlari — foydalanuvchi faolligini oshirish uchun (haqiqiy Telegram
    poll, shunchaki matn emas)."""
    clean_symbol = symbol.replace("USDT", "")
    question = f"{clean_symbol} keyingi 24 soatda qanday harakat qiladi, deb o'ylaysiz?"
    options = ["\U0001F4C8 Ko'tariladi", "\U0001F4C9 Tushadi", "\u27A1\uFE0F O'zgarishsiz qoladi"]
    return question, options
