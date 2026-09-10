"""
Berilgan matnni o'zbek tiliga tarjima qiladi (deep-translator kutubxonasi orqali,
API kalit talab qilmaydi). .env faylida tegishli *_TRANSLATE_TO_UZBEK=false qilib
o'chirib qo'yish mumkin.

MUHIM (haqiqiy voqea asosida tuzatilgan xato): norasmiy/bepul Google Translate
xizmati ba'zan (masalan ko'p so'rov yuborilganda yoki xizmat vaqtincha band bo'lganda)
tarjima o'rniga Google'ning umumiy xato sahifasini ("Error 500 (Server Error) ...
That's all we know.") qaytaradi. Bu HTTP darajasida "xatolik" sifatida chiqmaydi —
deep_translator buni oddiy muvaffaqiyatli natija deb hisoblab, o'sha matnni qaytarib
yuboradi. Natijada bot bu chalkash xato-matnni "tarjima" deb kanalga joylab yuborishi
mumkin edi. Shuning uchun bu yerda ikkita himoya qatlami bor:
  1. Natija xato-sahifaga o'xshaydimi tekshiriladi (pastdagi imzolar ro'yxati) — shunday
     bo'lsa, natija RAD ETILADI (ishlatilmaydi).
  2. Birinchi xizmat (Google) muvaffaqiyatsiz/shubhali natija bersa, ikkinchi, mustaqil
     xizmat (MyMemory) avtomatik sinaladi. Ikkalasi ham muvaffaqiyatsiz bo'lsa, asl
     (tarjima qilinmagan) matn qaytariladi — bu HAR DOIM chalkash xato-matndan yaxshiroq,
     chunki hech bo'lmasa asl matn o'qish mumkin/mazmunli.

MUHIM (yana bir tuzatilgan xato): MyMemory xizmati Google'dan farqli o'laroq oddiy
"uz" kabi qisqa til kodini QABUL QILMAYDI — u "uz-UZ" kabi to'liq (mintaqa bilan
birga) kodni talab qiladi, aks holda "No support for the provided language" xatosi
bilan darhol rad etadi (hatto tarmoqqa chiqmasdan). Shuning uchun MyMemory'ga
maxsus "uz-UZ" ishlatiladi (Google uchun esa oddiy "uz" yetarli va to'g'ri).

MUHIM (uchinchi tuzatilgan xato): MyMemory manba tili sifatida "auto"ni ham QABUL
QILMAYDI — lekin bu daf'atan (kod darajasida) xato bermaydi, balki so'rovni
serverga yuborib, keyin "'AUTO' IS AN INVALID SOURCE LANGUAGE ..." degan xato
matnini xuddi TARJIMA natijasi sifatida qaytaradi! Bu — birinchi (Google xato-sahifa)
muammosi bilan bir xil turkumdagi xato, faqat boshqa xizmatda. Shuning uchun MyMemory
uchun manba tili doim ANIQ "en-GB" (ingliz) qilib beriladi — bizning deyarli barcha
tarjima manbalarimiz (Wikipedia, CoinDesk, Cointelegraph, BBC) shunday bo'lgani uchun
bu to'g'ri standart. (Futbol botining o'zbekcha Google News manbasi — kamdan-kam
holat — MyMemory FAQAT Google butunlay ishlamay qolganda, zaxira sifatida chaqirilgani
uchun, kamdan-kam holatdagi noto'g'ri manba-til taxmini qabul qilingan.)
"""
import logging

logger = logging.getLogger(__name__)

# Google'ning yoki MyMemory'ning xato-javobiga xos, tarjima natijasida UMUMAN
# uchramasligi kerak bo'lgan iboralar — shulardan biri topilsa, natija chin tarjima
# emas, xizmatning o'z xato-xabari ekani aniq.
_ERROR_SIGNATURES = (
    "error 500", "error 404", "server error", "that's an error",
    "there was an error", "please try again later", "that's all we know",
    "<html", "<!doctype", "bad gateway", "service unavailable",
    "invalid source language", "invalid target language", "is an invalid",
    "langpair", "no support for the provided language",
)


def _looks_like_error_page(text: str) -> bool:
    lowered = text.lower()
    return any(sig in lowered for sig in _ERROR_SIGNATURES)


def _try_backend(backend_name: str, make_translator, text: str) -> str | None:
    try:
        translated = make_translator().translate(text)
    except Exception as exc:  # noqa: BLE001 - keyingi zaxira xizmatga o'tish uchun
        logger.warning("%s tarjima xizmatida xatolik: %s", backend_name, exc)
        return None

    if not translated or not translated.strip():
        logger.warning("%s tarjima xizmati bo'sh natija qaytardi.", backend_name)
        return None

    if _looks_like_error_page(translated):
        logger.warning(
            "%s tarjima xizmati xato-sahifaga o'xshash natija qaytardi (chin tarjima emas), rad etildi: %r",
            backend_name, translated[:120],
        )
        return None

    return translated


def translate_to_uzbek(text: str) -> str:
    """Matnni o'zbek tiliga tarjima qiladi. Avval Google, muvaffaqiyatsiz/shubhali
    bo'lsa MyMemory sinaladi. Ikkalasi ham muvaffaqiyatsiz bo'lsa, asl matn qaytariladi
    (botni to'xtatmaslik uchun).

    Manba tili "auto" (avtomatik aniqlash) — QATTIQ "en" (ingliz) emas, chunki bu
    funksiya turli manbalardan kelgan matnlarga qo'llaniladi: ba'zilari doim ingliz
    tilida (masalan Wikipedia), lekin ba'zilari (masalan futbol botining ba'zi
    yangilik manbalari) allaqachon o'zbek tilida bo'lishi mumkin."""
    from deep_translator import GoogleTranslator, MyMemoryTranslator

    result = _try_backend("Google Translate", lambda: GoogleTranslator(source="auto", target="uz"), text)
    if result:
        return result

    result = _try_backend("MyMemory", lambda: MyMemoryTranslator(source="en-GB", target="uz-UZ"), text)
    if result:
        logger.info("Google muvaffaqiyatsiz bo'lgani uchun MyMemory (zaxira xizmat) orqali tarjima qilindi.")
        return result

    logger.warning("Barcha tarjima xizmatlari muvaffaqiyatsiz bo'ldi, asl (tarjima qilinmagan) matn ishlatiladi.")
    return text
