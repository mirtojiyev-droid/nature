"""
Bir nechta bot BITTA jarayonda, BIR NECHTA ip-oqimda (thread) parallel ishlaganda
(main.py'ga qarang — tabiat boti o'zining alohida semaforida, kripto/futbol
umumiy semaforda), ular ODDIY (tarmoq so'rovi kabi) ishlarni bemalol bir vaqtda
bajarishi mumkin. LEKIN har birining o'zining OPERATIV XOTIRA JIHATIDAN OG'IR
bosqichi bor:
  - tabiat boti: ffmpeg orqali videoni qayta kodlash (music_mixer.py) — bir necha
    yuz MB'gacha operativ xotira talab qilishi mumkin, ayniqsa yuqori sifatda.
  - kripto boti: PIL orqali coin/breakout kartalarini (1080x1620, gradient +
    sham-grafik bilan) chizish (card_builder.py) — bir nechta katta rasm bir
    vaqtda xotirada saqlanishi mumkin.

MUHIM (haqiqiy voqeada aniqlangan jiddiy xato): Render'ning arzon tariflarida
(odatda 512MB) bu IKKALA og'ir bosqich AYNAN BIR VAQTDA to'g'ri kelib qolsa
(masalan hub qayta ishga tushganda — barcha botlar deyarli bir vaqtda ishga
tushadi), umumiy operativ xotira sarfi platformaning chegarasidan oshib,
"out of memory" bilan jarayon MAJBURAN o'chirilishi (OOM kill) mumkin edi.
Render buni "Instance restarted" / jarayon jimgina qaytadan ishga tushishi
sifatida ko'rsatadi — Python xatolik/traceback UMUMAN chiqmaydi (chunki
operatsion tizim jarayonni SIGKILL bilan to'xtatadi, Python "except" bloki
buni umuman ushlab qololmaydi). Natijada: hub qayta-qayta ishga tushadi, lekin
og'ir bosqichlar hech qachon TUGALLANMAYDI — tashqaridan "bot bir marta ishga
tushadi, keyin umuman ishlamay qoladi" bo'lib ko'rinadi (aslida cheksiz
qulash-qayta ishga tushish sikli).

Yechim: shu modul BUTUN JARAYON uchun UMUMIY, BITTA "og'ir operatsiya" semafori
beradi — ffmpeg (tabiat) va PIL karta chizish (kripto) hech qachon BIR VAQTDA
ishlamaydi, hatto ikkala bot boshqa bosqichlarda (tarmoq so'rovlari, Wikipedia
qidiruvi va h.k.) parallel ishlab tursa ham. Bu ikkala botning eng "qimmat"
lahzalarini vaqt bo'yicha ajratib, umumiy cho'qqi (peak) operativ xotira
sarfini sezilarli kamaytiradi — ATAYLAB shu ikki bosqich UCHUNGINA, chunki
qolgan barcha ish (tarmoq so'rovlari) CPU/RAM jihatidan arzon va parallel
ishlashi hech qanday muammo tug'dirmaydi."""
import threading
from contextlib import contextmanager

_HEAVY_OP_SEMAPHORE = threading.Semaphore(1)


@contextmanager
def heavy_operation(label: str = ""):
    """Operativ xotira jihatidan OG'IR bo'lgan (ffmpeg qayta kodlash, PIL orqali
    katta rasm chizish kabi) kod bo'lagini shu bilan o'rab qo'ying — boshqa bot
    shu payt xuddi shunday og'ir operatsiya bajarayotgan bo'lsa, bu chaqiruv
    NAVBATDA (bloklanib) kutadi, ikkalasi hech qachon bir vaqtda ishlamaydi.
    `label` faqat diagnostika/log uchun (ixtiyoriy)."""
    _HEAVY_OP_SEMAPHORE.acquire()
    try:
        yield
    finally:
        _HEAVY_OP_SEMAPHORE.release()
