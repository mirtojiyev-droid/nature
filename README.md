# Tabiat kanali uchun avtomatik post bot

Har kuni bitta "kunlik mavzu" (tabiiy joy) tanlab, kun davomida bir necha marta o'sha
joyning turli go'zal qirralari haqida (sharsharasi, sohili, tog' manzarasi, quyosh
botishi, havodan ko'rinishi va h.k.) video va rasm + qisqacha ma'lumot bilan Telegram
kanalingizga avtomatik post qiladigan Python skript. Topilgan videoga, agar ffmpeg va
`music/` papkasida musiqa fayli bo'lsa, avtomatik fon musiqasi ham qo'shiladi —
tomoshabinga yoqimliroq bo'lishi uchun.

## Qanday ishlaydi

1. **Kunlik mavzu**: har kuni bitta joy (masalan "Angel Falls") tanlanadi va kun davomida
   shu bilan qoladi. Joylar `topics.py` orqali [Wikipedia](https://www.wikipedia.org/)'ning
   keng qidiruvidan avtomatik topiladi — bu qo'lda tuzilgan kichik ro'yxat emas, balki
   sharshara, orol, milliy bog', tog', ko'l va h.k. bo'yicha yuzlab-minglab real joyni o'z
   ichiga olgan doimiy yangilanadigan havza (1 haftaga keshlanadi). `places.py`'dagi 69 ta
   qo'lda tuzilgan joy esa zaxira (seed) sifatida shu havzaga qo'shiladi.
2. **Qirralar**: har safar ishga tushganda, bugungi mavzu uchun hali ishlatilmagan bitta
   "qirra" tanlanadi (`facets.py`) — masalan "sharsharasi", "sohili", "quyosh botishi".
   Kun davomida shu joyning turli tomonlari ketma-ket ochib boriladi.
3. Video qidirishda avval `local_footage/` papkasi tekshiriladi — agar u yerda joriy
   mavzu/qirraga fayl nomi bo'yicha mos keladigan qo'lda joylangan premium video bo'lsa
   (masalan Shutterstock/Envato Elements/Storyblocks kabi pullik kutubxonadan siz
   o'zingiz yuklab olgan), u eng ustuvor sifatida ishlatiladi (pastdagi "Premium/pullik
   kutubxonalar" bo'limiga qarang). Mos lokal video topilmasa (odatiy holat — bu papka
   ixtiyoriy), uchta bepul manbadan qidiradi — [Pexels](https://www.pexels.com/api/),
   (ixtiyoriy) [Pixabay](https://pixabay.com/api/docs/) va **Wikimedia Commons** (kalit
   talab qilmaydi, doim faol — dunyodagi eng katta ochiq litsenziyali media arxivi,
   ko'pincha Pexels/Pixabay'da topilmagan noyob joylarni ham topib beradi). Video
   kutubxonalari nisbatan kichik bo'lgani uchun, bot avval eng aniq so'rovni (masalan
   "Angel Falls waterfall") sinaydi, natija topilmasa asta-sekin soddaroq variantlarga
   (joy nomining o'zi, keyin faqat qirra so'zi, oxirida umumiy "beautiful nature
   landscape") o'tadi — va har bir variantni **uchala bepul manbada ham** tekshiradi. Uch
   manba + to'rtta qidiruv varianti birlashganda, video topilish ehtimoli sezilarli
   oshadi.
   - **Format**: har safar avval telefon ekraniga to'liq mos **vertikal (portret)**
     video/rasm qidiriladi — bu Telegram'da "Short"ga o'xshab, to'liq ekranda ochilib
     qulay ko'rinadi. Vertikal variant umuman topilmasa, bot **gorizontal (landscape)**
     format bilan qayta izlaydi — shunda ham post o'tkazib yuborilmaydi.
   - **Sifat**: har uchala manbada ham, topilgan barcha natijalar orasidan eng yuqori
     o'lchamli (sifatli) variant tanlanadi (tasodifiy emas) — videoning o'zi ham,
     undagi fayl darajasi (masalan HD/Full HD) ham. Juda katta (4K/UHD) fayllar esa
     ataylab tanlanmaydi — ular Telegram'ga yuklashda muammo (hajm chegarasi) tug'dirishi
     mumkin, shuning uchun ~1920px chegarasidagi eng sifatli variant tanlanadi.
4. Topilgan video diskka yuklab olinadi va ffmpeg orqali Telegram uchun eng mos formatga
   keltiriladi: Pexels/Pixabay'dan kelgan video odatda allaqachon to'g'ri formatda bo'lgani
   uchun tezda nusxalanadi, Wikimedia Commons'dan kelgan video esa ko'pincha boshqa
   formatda (VP9/webm) bo'lgani uchun avtomatik qayta kodlanadi — bu qadam har doim
   ishlaydi, ffmpeg talab qiladi. Shu bilan bir qatorda, agar `music/` papkasida kamida
   bitta musiqa fayli bo'lsa, ustiga tasodifiy tanlangan fon musiqasi ham qo'shiladi
   (video uzunligiga moslab kesiladi, oxirida asta pasaytiriladi). ffmpeg umuman
   o'rnatilmagan bo'lsa, video shunchaki asl holida (qayta ishlanmagan, musiqasiz)
   joylanadi — xatolik bermaydi, faqat Wikimedia Commons'dan kelgan videolar ba'zi
   qurilmalarda to'g'ri ko'rinmasligi mumkin (shuning uchun ffmpeg o'rnatish tavsiya
   etiladi — 1-qadamga qarang).
5. Wikipedia'dan joy haqida umumiy ma'lumot oladi (kun davomida bir marta so'raladi,
   keshlanadi) va kerak bo'lsa o'zbek tiliga tarjima qiladi.
6. Telegram Bot API orqali videoni va rasmni (ikkalasini ham, topilsa) shu ma'lumot bilan
   birga, alohida post qilib kanalga joylaydi.
7. Standart sozlamada **har 30 daqiqada** bittadan post chiqadi (`scheduler.py` orqali) —
   bu `.env`'da o'zgartiriladi.

## O'rnatish

### 1. Talab qilinadigan dasturlar

Python 3.10+ kerak (Windows'da [python.org](https://www.python.org/downloads/) dan yuklab oling,
o'rnatishda "Add Python to PATH" belgisini bosishni unutmang).

**ffmpeg (ixtiyoriy, lekin fon musiqasi uchun shart)** — video topilgandan keyin unga
musiqa qo'shish uchun ishlatiladi. O'rnatilmagan bo'lsa ham bot ishlayveradi, faqat
videolar musiqasiz joylanadi.

- **Windows**: [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) dan "release
  essentials" zip'ni yuklab oling, biror joyga (masalan `C:\ffmpeg`) chiqaring, so'ng
  `C:\ffmpeg\bin` papkasini Windows PATH'ga qo'shing (Windows qidiruvidan "Edit the
  system environment variables" → "Environment Variables" → "Path" → "New"). Tekshirish
  uchun yangi CMD oynasida `ffmpeg -version` yozing.
- **Ubuntu/Debian (VPS)**:
  ```
  sudo apt update && sudo apt install -y ffmpeg
  ```
- **macOS**: `brew install ffmpeg`

### 2. Loyihani tayyorlash

Buyruq qatorida (CMD yoki PowerShell) loyiha papkasiga kiring va kutubxonalarni o'rnating:

```
cd nature_channel_bot
pip install -r requirements.txt
```

### 3. Telegram bot yaratish

1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing, `/newbot` buyrug'ini yuboring va
   ko'rsatmalarga amal qiling.
2. BotFather bergan tokenni saqlab qo'ying — bu `TELEGRAM_BOT_TOKEN`.
3. Botingizni kanalingizga **administrator** sifatida qo'shing va unga kamida
   "Post Messages" (xabar joylash) huquqini bering.
4. Kanal username'ini eslab qoling (masalan `@mening_kanalim`) — bu `TELEGRAM_CHANNEL_ID`.
   Agar kanal yopiq (private) bo'lsa, o'rniga kanal ID'sini ishlating (odatda `-100` bilan boshlanadi;
   buni topish uchun [@userinfobot](https://t.me/userinfobot) yoki shunga o'xshash botlardan foydalanish mumkin).

### 4. Pexels API kalit olish

1. [pexels.com/api](https://www.pexels.com/api/) saytiga kiring, ro'yxatdan bepul o'ting.
2. Sizga darhol API kalit beriladi — bu `PEXELS_API_KEY`. Bepul limit juda yuqori (oyiga 20,000+ so'rov),
   kunlik bitta post uchun batamom yetarli.

### 5. Pixabay API kalit olish (ixtiyoriy, lekin tavsiya etiladi)

Pexels'ning video kutubxonasi nisbatan kichik bo'lgani uchun, ikkinchi manba sifatida
Pixabay qo'shish video topilish ehtimolini sezilarli oshiradi:

1. [pixabay.com/api/docs](https://pixabay.com/api/docs/) sahifasiga kiring, ro'yxatdan
   bepul o'ting (yoki mavjud hisobingiz bilan kiring).
2. Sahifa yuqorisida ko'rsatilgan API kalitni nusxalang — bu `PIXABAY_API_KEY`.
3. Bu qadamni o'tkazib yubormoqchi bo'lsangiz, `.env`'da shu qatorni bo'sh qoldiring —
   bot faqat Pexels bilan ishlashda davom etadi, xato bermaydi.

### 6. Premium/pullik kutubxonalardan video qo'shish (ixtiyoriy)

Shutterstock, Envato Elements, iStock/Getty Images, Storyblocks, Motion Array kabi
kutubxonalar juda yuqori sifatli (4K, sinematik, "dark moody"/"dramatic" uslubdagi)
tabiat videolariga ega, lekin ular pullik obuna talab qiladi va — Pexels/Pixabay'dan
farqli o'laroq — ochiq, bepul, o'z-o'zidan ro'yxatdan o'tiladigan qidiruv+yuklab olish
API'siga ega emas. Bundan ham muhimi, ularning litsenziya shartlari kontentni FAQAT
inson tomonidan qo'lda tanlab yuklab olishga ruxsat beradi — shuning uchun bot ularni
avtomatik qidira olmaydi va bu qonuniy emas ham bo'lardi.

Buning o'rniga, agar sizda shu platformalardan biriga obuna bo'lsa:

1. Saytda o'zingiz qo'lda ko'rib, yoqqan sinematik/tabiat videongizni yuklab oling (bu —
   litsenziya talab qiladigan "inson tomonidan tanlash" qadami).
2. Faylni loyihadagi `local_footage/` papkasiga, tavsiflovchi nom bilan joylang — masalan
   `waterfall_night_storm_dramatic.mp4` yoki `aerial_mountain_sunset_cinematic.mp4`
   (batafsil: `local_footage/README.txt`).
3. Bot fayl nomini kunlik mavzu/qirra so'roviga solishtiradi — mos kelsa, shu videoni
   Pexels/Pixabay/Wikimedia Commons'dan OLDIN, eng ustuvor sifatida ishlatadi. Mos fayl
   topilmasa (yoki papka bo'sh bo'lsa — bu ixtiyoriy qadam), bot odatdagidek bepul
   manbalardan avtomatik qidirishda davom etadi.

### 7. Fon musiqasi qo'shish (ixtiyoriy)

1. [pixabay.com/music](https://pixabay.com/music/) sahifasiga kiring, "nature", "ambient",
   "relaxing", "calm" kabi so'zlar bilan qidiring (bu yerdagi musiqalar ham bepul va
   litsenziyasiz).
2. Yoqqan 5-10 ta trekni yuklab oling va loyihadagi `music/` papkasiga joylang.
3. Shu bilan tamom — bot har safar tasodifiy birini tanlab, video uzunligiga moslab
   avtomatik qo'shadi. Papka bo'sh qolsa, videolar shunchaki musiqasiz joylanadi.

### 8. .env faylini sozlash

`.env.example` faylini nusxalab `.env` deb nomlang, so'ng yuqoridagi qadamlarda olgan qiymatlaringizni yozing:

```
copy .env.example .env
```

Keyin `.env` faylni Notepad bilan ochib, tegishli joylarga token/kalitlaringizni yozing.

### 9. Sinab ko'rish

```
python main.py
```

Agar hammasi to'g'ri sozlangan bo'lsa, kanalingizga darhol bitta post joylanadi va
`bot.log` faylida jarayon haqida yozuvlar paydo bo'ladi.

**Diqqat — birinchi ishga tushirish biroz sekinroq bo'lishi mumkin**: bot birinchi marta
ishlaganda Wikipedia'dan minglab joy nomini yig'ib, `topic_pool_cache.json` fayliga
keshlaydi (bu bir necha o'n soniya vaqt olishi mumkin). Keyingi ishga tushirishlarda esa
kesh 1 hafta davomida qayta ishlatilgani uchun juda tez ishlaydi.

## Ikki xil ishga tushirish rejimi

- **`main.py`** — bitta ishga tushganda bitta post joylaydi, so'ng tugaydi. Qo'lda sinash
  yoki cron/Task Scheduler bilan chaqirish uchun.
- **`scheduler.py`** — dasturning o'zi doimiy ishlab turadi (to'xtamaydi) va har
  `POST_INTERVAL_MINUTES` (standart 30) daqiqada o'zi `main.py`'dagi mantiqni chaqiradi.
  Bu **VPS'ga (24/7 bulutli server) joylash uchun mo'ljallangan** — shunda laptop o'chirilgan
  yoki uxlab qolgan bo'lsa ham, kanal ishlashda davom etadi. Har 30 daqiqada post
  chiqishi kerak bo'lgani uchun, bu rejim uchun **VPS deyarli shart** (Windows'da ham
  ishga tushirsa bo'ladi, lekin faqat terminal/kompyuter doimiy ochiq turgan taqdirda).

## Bot doim yoqilib turishi uchun VPS'ga joylash (tavsiya etiladi)

Laptop orqali Task Scheduler faqat kompyuter yoqiq va uyg'oq bo'lgandagina ishlaydi. Kanal
haqiqatan ham 24/7 avtomatik postlab turishi uchun botni arzon bulutli serverga (VPS) qo'yish
kerak — bu doimiy ishlaydigan, sizga tegishli kichik "kompyuter", oyiga taxminan $4-6 turadi
(Hetzner CX22, DigitalOcean Droplet yoki shunga o'xshash — Ubuntu 22.04 tanlang).

1. **VPS sotib oling va unga ulaning** (SSH orqali, provayder ko'rsatmasiga qarang).

2. **Python va ffmpeg o'rnating** (Ubuntu'da odatda Python allaqachon bor; ffmpeg fon
   musiqasi uchun kerak, o'rnatilmasa ham bot ishlayveradi):
   ```
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip unzip ffmpeg
   ```

3. **Loyihani serverga yuklang** — `nature_channel_bot.zip`'ni serverga (masalan `scp` orqali
   o'z kompyuteringizdan) yuboring, so'ng:
   ```
   unzip nature_channel_bot.zip
   cd nature_channel_bot
   ```

4. **Virtual muhit yaratib, kutubxonalarni o'rnating:**
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **`.env` faylini sozlang** (yuqoridagi "O'rnatish" bo'limidagi kabi):
   ```
   cp .env.example .env
   nano .env
   ```

6. **Sinab ko'ring:**
   ```
   python main.py
   ```

7. **Doimiy ishlashi uchun systemd xizmati qilib qo'ying** — loyihada tayyor
   `nature-bot.service` fayli bor:
   ```
   nano nature-bot.service   # User, WorkingDirectory, ExecStart'dagi YOUR_USERNAME'ni almashtiring
   sudo cp nature-bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable nature-bot
   sudo systemctl start nature-bot
   ```

8. **Holatini tekshirish:**
   ```
   sudo systemctl status nature-bot
   journalctl -u nature-bot -f      # jonli loglarni ko'rish
   ```

Shu bilan bot server qayta yoqilganda ham (`enable` tufayli), yoki qulab tushsa ham
(`Restart=on-failure` tufayli) avtomatik o'zini tiklab, doimiy ishlab turadi.

## Windows Task Scheduler bilan (VPS'siz, kamroq tavsiya etiladi)

30 daqiqalik yuqori chastota tufayli bu variant unchalik qulay emas (kompyuter doimo
yoqiq va uyg'oq turishi kerak), lekin texnik jihatdan mumkin:

1. Windows qidiruvidan **"Task Scheduler"** (Vazifalar rejalashtiruvchisi) ni oching.
2. O'ng tomondan **"Create Task..."** ni bosing (oddiy "Create Basic Task" emas — takrorlanish
   sozlamasi kerak).
3. **General** tabida nom bering (masalan "Tabiat kanali boti").
4. **Triggers** tabida **"New..."** → "Daily" → boshlanish vaqtini belgilang → pastda
   **"Repeat task every"** qutisiga `30 minutes`, **"for a duration of"** qutisiga
   `1 day` deb qo'ying.
5. **Actions** tabida **"New..."** → Program/script maydoniga Python'ning to'liq yo'lini
   yozing (aniq yo'lni bilish uchun CMD'da `where python`), **Add arguments**ga `main.py`,
   **Start in**ga loyiha papkasining to'liq yo'lini yozing (masalan
   `C:\Users\SizningIsm\Documents\nature_channel_bot`) — bu **muhim**, aks holda skript
   `.env` faylini topa olmaydi.
6. **OK** bosib saqlang.

Sinash uchun Task Scheduler ro'yxatida yaratilgan vazifani tanlab, o'ng tugma → **Run** ni bosing.

## Sozlash imkoniyatlari

- **Post chastotasini o'zgartirish**: `.env`'da `POST_INTERVAL_MINUTES` (standart 30).
- **Tarjimani o'chirish**: `.env`'da `TRANSLATE_TO_UZBEK=false`.
- **Rasmni o'chirish**: har bir postda video (asosiy) dan tashqari rasm ham avtomatik
  joylanadi. Faqat video bilan cheklanmoqchi bo'lsangiz, `.env`'da `POST_PHOTO_TOO=false`
  qiling.
- **Qirralar ro'yxatini o'zgartirish**: `facets.py` faylidagi `FACETS` ro'yxatiga yangi
  `{"label": "...", "suffix": "..."}` qo'shing yoki mavjudlarini tahrirlang.
- **Joylar havzasini kengaytirish**: `topics.py` faylidagi `SEARCH_TERMS` ro'yxatiga yangi
  qidiruv so'zlari qo'shing (masalan "hot air balloon", "cherry blossom") — bot keyingi
  safar (yoki kesh muddati tugaganda) shu bo'yicha ham qidiradi.
- **Joylar havzasini darhol yangilash**: `topic_pool_cache.json` faylini o'chirib
  tashlang — bot keyingi ishga tushganda Wikipedia'dan qaytadan yig'ib oladi.

## Muammolarni bartaraf etish

- **"Quyidagi .env sozlamalari yo'q" xatosi** — `.env` fayl yaratilmagan yoki noto'g'ri joyda. Fayl `main.py` bilan bir papkada bo'lishi kerak.
- **Telegram "chat not found" xatosi** — bot kanalga admin sifatida qo'shilmagan, yoki `TELEGRAM_CHANNEL_ID` noto'g'ri.
- **Tarjima ishlamayapti** — `deep-translator` internet orqali Google Translate'ga murojaat qiladi; internet yo'q bo'lsa yoki vaqtincha bloklansa, bot asl (inglizcha) matnni ishlatadi va davom etadi (to'xtamaydi).
- **"Joylar havzasi bo'sh" xatosi** — bu juda kamdan-kam uchraydi (Wikipedia ham, kesh ham,
  `places.py` ham bir vaqtda ishlamasa). Internetni tekshiring va qayta urinib ko'ring.
- **Bir xil qirra tez-tez takrorlanyapti** — bu normal holat: `facets.py`'da atigi 12 ta
  qirra bor, 30 daqiqalik chastotada kun davomida hammasi tugab, qaytadan aylanishi
  mumkin. Pexels har safar tasodifiy natija qaytargani uchun rasm/video baribir farq
  qiladi. Xohlasangiz, `facets.py`'ga yangi qirralar qo'shib, xilma-xillikni oshirsangiz bo'ladi.
- **Video kam topilyapti** — Wikimedia Commons kalitsiz doim faol, lekin `PIXABAY_API_KEY`'ni
  `.env`'ga qo'shsangiz (5-qadam) yana bitta manba qo'shiladi va natija yanada yaxshilanadi.
  `bot.log`'da har bir urinishda qaysi so'rov/manba birikmasida natija topilgani (yoki
  topilmagani) — jumladan Wikimedia Commons uchun ham — ko'rinadi.
- **Videolarda musiqa yo'q** — ikki sababi bo'lishi mumkin: (1) ffmpeg o'rnatilmagan —
  `ffmpeg -version` bilan tekshiring; (2) `music/` papkasi bo'sh — unga mp3/m4a/wav/ogg
  fayllar qo'shing (7-qadamga qarang). Ikkalasi ham bo'lmasa, bot xato bermay, shunchaki
  musiqasiz joylashda davom etadi — bu normal, ataylab shunday qilingan.
- **`local_footage/` papkasiga video qo'ydim, lekin ishlatilmayapti** — fayl nomi joriy
  mavzu/qirra so'roviga mos kelmasligi mumkin (`bot.log`'da har bir postda qaysi so'rov
  sinalgani ko'rinadi). Fayl nomini tavsiflovchi so'zlar bilan (joy nomi, qirra turi,
  kayfiyat) qayta ataysiz — masalan "sunset" so'zi bo'lishi kerak bo'lgan joyda faylni
  faqat "video1.mp4" deb atasangiz, hech qachon mos kelmaydi.
- **Wikimedia Commons'dan kelgan video ba'zi qurilmalarda ochilmayapti** — bu ffmpeg
  o'rnatilmaganda yuz berishi mumkin (Commons videolari ko'pincha VP9/webm formatida
  bo'ladi, ffmpeg esa uni Telegram uchun H.264'ga avtomatik o'giradi). ffmpeg o'rnating —
  muammo hal bo'ladi.
- Har doim `bot.log` faylini tekshiring — barcha xatoliklar shu yerda batafsil yoziladi.
