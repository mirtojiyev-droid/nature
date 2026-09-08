"""
Berilgan matnni o'zbek tiliga tarjima qiladi (deep-translator, Google Translate backend,
API kalit talab qilmaydi). .env faylida tegishli *_TRANSLATE_TO_UZBEK=false qilib
o'chirib qo'yish mumkin.
"""
import logging

logger = logging.getLogger(__name__)


def translate_to_uzbek(text: str) -> str:
    """Matnni o'zbek tiliga tarjima qiladi. Xatolik bo'lsa asl matnni qaytaradi.

    Manba tili "auto" (avtomatik aniqlash) qilib qo'yilgan — QATTIQ "en" (ingliz)
    emas. Sabab: bu funksiya turli manbalardan kelgan matnlarga qo'llaniladi — ba'zilari
    doim ingliz tilida (masalan Wikipedia), lekin ba'zilari (masalan futbol botining
    ba'zi yangilik manbalari) allaqachon o'zbek tilida bo'lishi mumkin. Agar manba
    tili qattiq "en" qilib qo'yilganida, allaqachon o'zbekcha matnni "ingliz tili"
    deb noto'g'ri tarjima qilib, buzib qo'yishi mumkin edi."""
    try:
        from deep_translator import GoogleTranslator

        # Google Translate uzun matnlarni bo'lib yuborish talab qilishi mumkin (5000 belgi limit),
        # bizning caption'lar ancha qisqa bo'lgani uchun to'g'ridan-to'g'ri yuboramiz.
        translated = GoogleTranslator(source="auto", target="uz").translate(text)
        return translated or text
    except Exception as exc:  # noqa: BLE001 - tarjima muvaffaqiyatsiz bo'lsa botni to'xtatmaymiz
        logger.warning("Tarjima muvaffaqiyatsiz bo'ldi, asl matn ishlatiladi: %s", exc)
        return text

