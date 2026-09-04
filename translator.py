"""
Ingliz tilidagi matnni o'zbek tiliga tarjima qiladi (deep-translator, Google Translate backend,
API kalit talab qilmaydi). .env faylida TRANSLATE_TO_UZBEK=false qilib o'chirib qo'yish mumkin.
"""
import logging

logger = logging.getLogger(__name__)


def translate_to_uzbek(text: str) -> str:
    """Matnni o'zbek tiliga tarjima qiladi. Xatolik bo'lsa asl matnni qaytaradi."""
    try:
        from deep_translator import GoogleTranslator

        # Google Translate uzun matnlarni bo'lib yuborish talab qilishi mumkin (5000 belgi limit),
        # bizning caption'lar ancha qisqa bo'lgani uchun to'g'ridan-to'g'ri yuboramiz.
        translated = GoogleTranslator(source="en", target="uz").translate(text)
        return translated or text
    except Exception as exc:  # noqa: BLE001 - tarjima muvaffaqiyatsiz bo'lsa botni to'xtatmaymiz
        logger.warning("Tarjima muvaffaqiyatsiz bo'ldi, asl matn ishlatiladi: %s", exc)
        return text
