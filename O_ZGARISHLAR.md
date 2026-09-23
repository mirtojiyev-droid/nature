# Tabiat boti — tuzatishlar (2026-09-23)

## Takroriy postlar nega chiqayotgan edi (aniqlangan sabablar)
1. **Arxiv konteyner ichida edi.** `HUB_DATA_DIR` bo'sh bo'lsa, `posted_media_history.json` har deploy'da (Render free tarifida esa har restartda ham) o'chib ketardi, keyin Pixabay/Pexels yana o'sha "top" natijalarni qaytarardi. **Asosiy sabab shu.**
2. **Tarix 3000 ta bilan cheklangan edi.** Eskilari "unutilib", qayta chiqardi.
3. **Fayl atomar yozilmasdi.** Yozish paytida jarayon o'chsa (OOM), JSON buzilardi va kod uni jimgina **bo'sh** deb qabul qilardi, ya'ni butun tarix yo'qolardi.
4. **Faqat ID bo'yicha tekshirilardi.** Bir xil video Pixabay'da ham, Pexels'da ham bo'lsa (ID'lari har xil) tanilmasdi.
5. **Eski URL yozuvlari yangi `Manba:ID` kalitlariga mos kelmasdi.** Format o'zgarganda migratsiya qilinmagan edi.
6. **`localfootage/` videolari arxivga umuman yozilmasdi**, shuning uchun bir xil fayl qayta-qayta chiqardi.
7. **Timeout'da qayta yuborish.** Telegram videoni qabul qilib, javobni kechiktirsa, bot uni yana 2 marta yuborardi (kanalda dublikat chiqardi) va arxivga yozmasdi.

## Nima qilindi
- **`bots/nature/archive.py`** (yangi): qisqartirilmaydigan JSONL jurnal. Yuborishdan oldin `pending` deb band qilinadi, keyin `posted` / `uncertain` / `released` bo'ladi. Buzilgan qator bo'lsa faqat o'sha qator tashlanadi. Eski tarix avtomatik ko'chiriladi. `NATURE_ARCHIVE_CHAT_ID` orqali Telegram'da zaxira saqlanadi va o'sha yerdan tiklanadi.
- **`bots/nature/fingerprint.py`** (yangi): video va rasm uchun perceptual hash + sha256.
- **`run.py`**: ID, URL va kontent bo'yicha tekshiruv; lokal videolar uchun ham dedup; har bir so'rovdan 4 emas, 15 ta nomzod ko'riladi (`NATURE_CANDIDATES_PER_QUERY`), shuning uchun yangi kontent topish osonlashdi; 50MB'dan katta video chiqsa keyingi nomzodga o'tiladi (avval butun video bosqichi to'xtardi).
- **`shared/telegram_poster.py`**: timeout'da qayta yuborilmaydi (dublikat bo'lmasin), 429 flood-limit'da kutib qayta urinadi, `message_id` saqlanadi, rasm MIME turi to'g'ri aniqlanadi.
- **`state.py`**: barcha JSON fayllar atomar yoziladi, buzilgan fayl esa o'chirilmay, `.corrupt-*` nomi bilan chetga olib qo'yiladi.
- **`local_footage.py`**: allaqachon joylangan fayllar tanlanmaydi.

## Sizdan talab qilinadigan yagona qadam
Render'da Persistent Disk bo'lmasa, yopiq kanal yarating, botni u yerga admin qiling ("Post" + "Pin" huquqlari bilan) va `.env` / Render Environment'ga quyidagini yozing:
```
NATURE_ARCHIVE_CHAT_ID=-100xxxxxxxxxx
```
Bu qilinmasa, arxiv baribir ishlaydi, lekin deploy'da o'chib ketadi (logda ogohlantirish chiqadi).

## Sinov
Soxta Pixabay/Pexels/Telegram bilan to'liq simulyatsiya o'tkazildi: 6 ta ishga tushirish, deploy (arxiv o'chirildi va Telegram'dan tiklandi), boshqa manbadagi 720p nusxa, timeout. Natijada 4 ta video va 3 ta rasm chiqdi, **birortasi ham takrorlanmadi**.
