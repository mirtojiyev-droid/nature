# Bot Hub — Tabiat + Kripto + Futbol (bitta jarayon)

Uchta Telegram botini (tabiat kanali, kripto bozor, futbol) **bitta Python
jarayonida**, bitta VPS'da, har biri o'z vaqt jadvali va o'z kanaliga ishlaydigan
qilib boshqaradi.

- **Tabiat boti** — avvalgi `nature_channel_bot` loyihasidan boshlangan, lekin shundan
  beri sezilarli darajada kuchaytirilgan (`bots/nature/`): kunlik, kategoriya-vaqtga
  bog'langan jadval, **manbalar/sifat/mavzular/format .env orqali (kod o'zgartirmasdan)
  sozlanadigan** (`bots/nature/config.py` — Pixabay + Pexels + Wikimedia, tartibi
  NATURE_SOURCE_ORDER bilan), avtomatik sifat nazorati (buzuq/bo'sh fayllarni
  aniqlash, muvaffaqiyatsiz nomzoddan keyingisiga o'tish, sifat chegarasi
  bosqichma-bosqich pasayadi — masalan 1080p topilmasa 720p), gorizontal videoni
  ham vertikalga kesib (crop) moslashtirish, "pro" brendlash (video+rasmga joy
  nomi/kanal belgisi), fon musiqasi (music/ papkasi), va ixtiyoriy AI video
  generatsiyasi — batafsil pastga qarang.
- **Kripto boti** — avvalgi `kripto_bot_mobil.html` (telefonda qo'lda ishga tushiriladigan
  versiya)ning Python porti (`bots/crypto/`). Ma'lumot manbasi **CoinGecko**
  (dastlab Binance edi, lekin Binance.com AQSh va ba'zi bulut serverlari IP'laridan
  kirishni geografik jihatdan bloklagani uchun almashtirildi — pastga qarang).
- **Futbol boti** — avvalgi `futbol_bot_mobil.html`ning to'liq Python porti (`bots/football/`).
  Natija/fixture/yangilik postlari endi TAKRORLANMAYDI (state.py orqali kuzatiladi).
  Qo'shimcha: har soatda bitta qiziqarli futbol fakti va kuniga ~2 marta futbolchi
  sharhi (ikkalasi ham Wikipedia manbali) — pastga qarang.

Uchtasi ham asosan tarmoq so'rovlari bilan band (CPU emas), shuning uchun eng arzon
VPS (1 CPU / 1GB RAM) darajasida ham bemalol ishlaydi.

> **Eslatma:** YouTube-repost boti bu loyihadan olib tashlangan — YouTube'ning
> datacenter-server IP manzillarini bloklashi tufayli bulut-serverda ishonchli
> ishlay olmadi. Endi YouTube videolarini joylash **alohida, qo'lda ishga
> tushiriladigan** vositalar orqali amalga oshiriladi (kompyuterda ishlaydigan
> Python skripti yoki telefon brauzeridagi HTML boshqaruv paneli) — bu bot_hub'dan
> mustaqil, alohida saqlanadi.

## Nima o'zgardi (HTML asboblarga nisbatan)

- **Qo'lda ishga tushirish shart emas** — `main.py` scheduler orqali har bir botni o'z
  intervalida avtomatik ishga tushiradi, 24/7.
- **CORS proxy butunlay olib tashlandi** — bu faqat brauzer cheklovi edi; server tomonida
  hamma so'rov to'g'ridan-to'g'ri, tezroq va ishonchliroq ishlaydi.
- **Karta rasmlari** (coin kartasi, o'yin tabloi) endi brauzer Canvas o'rniga **Pillow**
  (Python rasm kutubxonasi) bilan chiziladi — natija deyarli bir xil ko'rinadi.
- Har bir bot o'zining bot tokeni/kanaliga ega, lekin xohlasangiz bitta umumiy tokendan
  ham foydalanish mumkin (pastga qarang).

## O'rnatish

### 1. Talablar

```
sudo apt update && sudo apt install -y python3 python3-venv python3-pip fonts-dejavu-core
```

`fonts-dejavu-core` — kripto/futbol kartalaridagi matnni chizish uchun kerak (ko'p
Ubuntu/Debian tizimlarida allaqachon o'rnatilgan bo'ladi). `ffmpeg` tabiat boti uchun
kerak (fon musiqasi va format moslashtirish, ixtiyoriy):

```
sudo apt install -y ffmpeg
```

### 2. Loyihani joylash

```
cd bot_hub
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. `.env` faylini sozlash

```
cp .env.example .env
nano .env
```

Har bir bot uchun:
- **Telegram bot tokeni** — [@BotFather](https://t.me/BotFather)'dan `/newbot` orqali oling.
- **Kanal ID** — botni kanalga administrator (kamida "Post Messages" huquqi bilan) qilib
  qo'shing, kanal username'ini yozing (masalan `@mening_kanalim`).
- Kripto boti uchun qo'shimcha: `PIXABAY_API_KEY` shart emas (u faqat tabiat botiga kerak).
  Buning o'rniga (ixtiyoriy, lekin tavsiya etiladi) [coingecko.com/en/api/pricing](https://www.coingecko.com/en/api/pricing)'dan
  bepul "Demo" API kalit oling va `COINGECKO_API_KEY`'ga qo'ying — bo'lmasa ham
  ishlayveradi, faqat sekinroq (CoinGecko'ning bepul so'rov chastotasi cheklangan).
  **Eslatma**: kripto boti fyuchers ma'lumotlarini (funding rate, Open Interest,
  Long/Short nisbati) ko'rsatmaydi — CoinGecko bunday ma'lumotni umuman bermaydi
  (faqat narx/hajm agregatori). Faqat narx, 24soatlik o'zgarish va RSI ko'rsatiladi.
- Tabiat boti uchun: [pixabay.com/api/docs](https://pixabay.com/api/docs/) (shart)
  kaliti. Ixtiyoriy qo'shimcha: [pexels.com/api](https://www.pexels.com/api/) —
  batafsil pastga qarang.

**Bitta bot, uchta kanal**: agar 3 ta alohida bot yaratishni istamasangiz, faqat umumiy
`TELEGRAM_BOT_TOKEN`ni to'ldiring va har bir botning o'z `*_TELEGRAM_BOT_TOKEN` qatorini
bo'sh qoldiring — o'sha holda bitta bot uchala kanalga ham admin qilib qo'yilishi kerak.

**Faqat ba'zi botlarni ishlatish**: bironta botni hozircha ishlatmoqchi bo'lmasangiz,
uning `*_TELEGRAM_CHANNEL_ID` qatorini bo'sh qoldiring — hub uni avtomatik o'tkazib
yuboradi (xato bermaydi).

### 4. Sinab ko'rish

```
python main.py
```

Kripto va futbol botlari darhol bir marta ishga tushadi (birinchi post joylanadi), so'ng
o'z intervalida davom etadi. Tabiat boti esa (standart — kunlik jadval rejimida) darhol
ISHGA TUSHMAYDI, balki eng yaqin jadval vaqtini (masalan 06:00, 08:00...) kutadi —
BUNDAN TASHQARI, agar aynan shu ishga tushirish paytida bugungi biror jadval vaqti
allaqachon o'tib ketgan bo'lsa-yu, hali ishlamagan bo'lsa (masalan qayta ishga
tushirilgan), o'sha ham darhol bajariladi. Har uchala botning jarayoni `hub.log`
faylida birgalikda ko'rinadi — qaysi bot yozgani `[bot-tabiat]`/`[bot-kripto]`/
`[bot-futbol]` ip-oqim nomidan bilinadi.

To'xtatish: `Ctrl+C`.

## VPS'da doimiy (24/7) ishlatish — systemd

```
nano bot-hub.service   # User, WorkingDirectory, ExecStart'dagi YOUR_USERNAME'ni almashtiring
sudo cp bot-hub.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bot-hub
sudo systemctl start bot-hub
```

Holatini tekshirish:
```
sudo systemctl status bot-hub
journalctl -u bot-hub -f      # jonli loglar
```

Server qayta yoqilganda (`enable`) yoki jarayon qulab tushsa (`Restart=on-failure`),
avtomatik o'zini tiklab, davom etadi.

## Har bir botning jadvali

**Kripto va futbol**: `.env`'dagi `CRYPTO_INTERVAL_MINUTES` / `FOOTBALL_INTERVAL_MINUTES`
orqali sozlanadi (standart: ikkalasi ham 60 daqiqa). **Tabiat**: standart bo'yicha
`NATURE_INTERVAL_MINUTES` UMUMAN ishlatilmaydi — buning o'rniga kunlik,
kategoriya-vaqtga bog'langan jadval ishlaydi (kuniga 12 marta, aniq vaqt + aniq
mavzu turi — pastga qarang). `NATURE_INTERVAL_MINUTES` faqat `.env`da
`NATURE_USE_DAILY_SCHEDULE=false` qilib, ESKI (tasodifiy interval) rejimga
qaytilganda ishlatiladi. Har bir bot bir-biridan mustaqil — bittasining jadvali
boshqasiga ta'sir qilmaydi, va bittasi xato bersa (masalan CoinGecko vaqtincha
rate-limit qilsa), faqat o'sha bot safar o'tkazib yuboriladi, boshqalari davom etadi.

**Operativ xotira va bir vaqtda ishlash (`HUB_MAX_CONCURRENT_JOBS`)**: har bir bot o'z
ALOHIDA ip-oqimida (thread) ishlaydi. **Kripto va futbol** bir-birlari bilan umumiy
"ruxsat" (semaphore)ni bo'lishadi — `.env`'dagi `HUB_MAX_CONCURRENT_JOBS` orqali
ikkalasi BIR VAQTDA nechtasi ishlashi mumkinligi cheklanadi:
- **Standart qiymat: 1** — kripto/futbol hech qachon bir vaqtda ishlamaydi, navbat
  bilan birin-ketin ishlaydi. Bu Render/Railway kabi platformalarning arzon, kam
  xotirali (512MB-1GB) tariflari uchun **XAVFSIZ va TAVSIYA ETILADI**.
- Serveringizda operativ xotira yetarli bo'lsa (2GB+), buni 2'ga oshirib,
  ikkalasining bir-birini kutmasdan parallel ishlashiga ruxsat berishingiz mumkin.

**MUHIM (haqiqiy voqeada aniqlangan va tuzatilgan xato): tabiat boti bu umumiy
cheklovga KIRMAYDI** — u o'zining ALOHIDA ruxsatiga ega, hech qachon kripto/futbolni
kutmaydi (va ular ham uni kutmaydi). Sabab: tabiat botining kunlik jadvali ANIQ
VAQTGA bog'liq (masalan "06:00 — quyosh chiqishi"), kripto esa CoinGecko rate-limit
tufayli 20-30+ daqiqa davom etishi mumkin — agar umumiy cheklovga kirganida, tabiat
boti shu vaqt ichida jim kutib, jadvaldagi vaqtini o'tkazib yuborishi mumkin edi.

**Qo'shimcha**: operativ xotira muammosini ikkinchi tomondan ham kamaytirish mumkin —
tabiat botining video sifatini `NATURE_MAX_VIDEO_QUALITY_PX` orqali pasaytirish
(masalan 4K/3840 o'rniga 1920 yoki 1280) xotira sarfini sezilarli kamaytiradi.

**Tabiat boti — kunlik jadval (standart)**: kuniga 12 marta, har biri aniq vaqtda va
aniq mavzu turida (masalan 06:00 — quyosh chiqishi, 18:00 — quyosh botishi, 20:00 —
yomg'ir/tinchlantiruvchi kontent). Jadval `bots/nature/schedule_config.py`da MAHALLIY
vaqtda yozilgan — `.env`dagi `NATURE_TZ_OFFSET_HOURS` (standart: 5, O'zbekiston UTC+5)
orqali serverning (odatda UTC) soatiga avtomatik moslashtiriladi. Vaqt yoki
kategoriyani o'zgartirish uchun shu faylni to'g'ridan-to'g'ri tahrirlang.

**Qo'shimcha — 4 soatlik "joy" oynasi**: kunlik jadvaldagi HAR BIR post, ichkarida,
joriy 4 soatlik oynaning MAVZUSINI (joyni) ishlatadi — bu oyna alohida, jadvaldan
mustaqil ravishda topics.py orqali yangilanadi (Wikipedia'dan). Bu oraliqni
o'zgartirish uchun `bots/nature/state.py`'dagi `WINDOW_HOURS` qiymatini tahrirlang.

**Tabiat boti — AI video generatsiyasi (ixtiyoriy, qo'lda ishga tushiriladi)**: agar
Pixabay/Wikimedia'dan topilgan kontent sifati (ayniqsa kamdan-kam so'raladigan
joylar uchun) yetarli bo'lmasa, `python -m bots.nature.generate_clips --count 10`
buyrug'i orqali Runway yoki Kling AI provayderi bilan premium sifatli video yarating —
bular avtomatik ravishda `bots/nature/localfootage/`ga joylanadi va bot ULARNI ENG
BIRINCHI navbatda ishlatadi. **MUHIM**: bu — pullik xizmat (~$0.05-0.15/soniya) va
ATAYLAB avtomatik botga ulanmagan (aks holda har post uchun pul sarflanardi) — siz
o'zingiz, xohlagan vaqtda, xohlagan miqdorda ishga tushirasiz. `--combine` bayrog'i
bir nechta klipni bitta uzunroq videoga birlashtirib, fon musiqasi ham qo'shadi.
Sozlash: `.env`dagi `AI_VIDEO_PROVIDER` (`runway` yoki `kling`) va tegishli API
kalit(lar). Batafsil: `bots/nature/generate_clips.py`ning boshidagi izoh.

**Tabiat boti — sifat nazorati va "keyingi nomzodni sinash"**: har bir video/rasm
postlashdan oldin bir nechta bosqichdan o'tkaziladi — yuklab olinadi, deyarli bir xil
rangdan iborat (qora ekran, buzuq/placeholder fayl) emasligi tekshiriladi, va video
uchun qo'shimcha ravishda ffmpeg orqali Telegram'ga mos formatga o'girilishi kerak
(muvaffaqiyatsiz bo'lsa — masalan noodatiy kodek tufayli — bu ham rad etiladi, xom
fayl HECH QACHON to'g'ridan-to'g'ri joylanmaydi). MUHIM: bitta nomzod istalgan
bosqichda muvaffaqiyatsiz bo'lsa, bot TASLIM BO'LMAYDI — bir nechta nomzod (odatda
4 tagacha, har bir manba/so'rov birikmasidan) ketma-ket sinaladi, toki biri barcha
tekshiruvlardan o'tguncha yoki hammasi tugaguncha. Bundan tashqari, Pixabay'dan
kelgan natijalar so'rov so'ziga mutlaqo aloqasi bo'lmasa (masalan "ocean"
so'ralganda "forest" natija), qabul qilinmaydi.

**Tabiat boti — follow-eslatma (ixtiyoriy, standart o'chirilgan)**: `.env`dagi
`NATURE_FOLLOW_REMINDER_EVERY_N` orqali (masalan =5) har N-postda "🔔 Follow for
more" qatorini qo'shish mumkin. Standart holatda 0 (o'chirilgan) — chunki bu "faqat
joy nomi ko'rinsin, boshqa hech narsa yozilmasin" tamoyiliga ozgina zid, shuning
uchun ongli ravishda o'zingiz yoqishingiz kerak.

**Tabiat boti — "pro" brendlash (video va rasm)**: har bir post (video ham, rasm ham)
pastki qismida yarim shaffof fon ustida joy nomi + kanal belgisi ko'rsatiladi —
professional sayohat-kanal uslubidagi "lower-third" brendlash. Kanal nomini
`.env`dagi `NATURE_BRAND_LABEL` orqali o'zgartiring. **Eslatma**: video uchun bu
matn bitta ffmpeg bosqichida (musiqa bilan birga) "kuydiriladi" — qo'shimcha
qayta kodlash bosqichi kerak emas.

**Video/rasm manba tartibi — .env orqali to'liq sozlanadigan (`bots/nature/config.py`)**:
manbalar va ularning TARTIBI endi `NATURE_SOURCE_ORDER` orqali boshqariladi (standart:
`pixabay,pexels,wikimedia`). `PIXABAY_API_KEY` **shart**, `PEXELS_API_KEY` **ixtiyoriy**
(sozlanmasa, `NATURE_SOURCE_ORDER`da ko'rsatilgan bo'lsa ham avtomatik chetlab
o'tiladi), Wikimedia Commons kalitsiz doim mavjud. Yangi manba (masalan Unsplash)
qo'shish uchun kelajakda `bots/nature/run.py`dagi `_SOURCE_ADAPTERS` ro'yxatiga bitta
yozuv qo'shish kifoya — tartib/yoqish-o'chirish esa kod o'zgartirmasdan, `.env`
orqali boshqariladi. Har bir manba/so'rov birikmasi uchun bir nechta nomzod
ketma-ket sinaladi (sifat nazoratidan o'tmasa, keyingisiga o'tiladi — pastga qarang).

**Sifat chegarasi bosqichma-bosqich pasayadi (`NATURE_MIN_VIDEO_PX`/`NATURE_MIN_PHOTO_PX`,
standart 1080p/1600px)**: eng yuqori darajada hech narsa topilmasa (masalan noyob
joy nomi uchun), bot butunlay rad etish o'rniga avtomatik pastroq darajaga (720p,
1080px) tushib qayta qidiradi. To'liq zaxira ro'yxatini o'zingiz ham
(`NATURE_MIN_VIDEO_PX=1080,720,480` kabi) belgilashingiz mumkin.

**Gorizontal video ham ishlatiladi (`NATURE_ALLOW_ORIENTATION_FALLBACK`, standart
yoqilgan)**: Pixabay/Pexels'dagi tabiat videolarining aksariyati kino/dron uslubida
GORIZONTAL tushirilgan — avval bot FAQAT tabiiy vertikal (9:16) videoni qabul
qilardi, bu esa ko'p hollarda "vertikal video topilmadi" bilan tugab, faqat rasm
bilan qolishga olib kelardi. Endi mos gorizontal video ham nomzod sifatida qabul
qilinadi va ffmpeg orqali markazdan kesib (crop, qora chiziqlarsiz) vertikal
formatga keltiriladi.

**Muhim texnik cheklov**: Pixabay'ning video API'si — platformaning o'zining qat'iy
chegarasi sifatida — **faqat 1920x1080 (Full HD)gacha** beradi, 4K (3840x2160)
umuman taklif qilmaydi (bu hech qanday sozlama bilan o'zgartirilmaydi). **Pexels
esa haqiqiy 4K video beradi** — shuning uchun eng yuqori sifat kerak bo'lgan
hollarda Pexels foydali qo'shimcha manba. Rasm uchun Pixabay'ning yuqori sifatli
havolasi (`fullHDURL`, 1920px+) faqat "to'liq API kirish" tasdiqlangan
hisoblarda mavjud, aks holda `largeImageURL` (1280px) ishlatiladi.

**Format (video/rasm) va mavzu tanlovi (`NATURE_MEDIA_MODE`, `NATURE_TOPICS`)**:
`NATURE_MEDIA_MODE=video_first` (standart, avval video + alohida rasm),
`video_only` (faqat video) yoki `photo_only` (faqat rasm, eng tez/eng kam
xotira sarflaydigan rejim) qilib belgilash mumkin. `NATURE_TOPICS` bo'sh
qoldirilsa, standart bo'yicha Wikipedia orqali topilgan KENG (24 xil
kategoriyali) ro'yxat ishlaydi; to'ldirilsa (masalan
`NATURE_TOPICS=ocean,forest,mountain,wildlife`), bot FAQAT shu mavzular bo'yicha
qidiradi — bu ham natijani cheklaydi, ham havzani (Wikipedia so'rovlari kamayishi
tufayli) sezilarli tezroq yig'adi.

**Telefon orqali boshqarish (CLI o'rniga)**: agar buyruq qatori (terminal) o'rniga
telefon brauzeridan qulay boshqarmoqchi bo'lsangiz, `python -m
bots.nature.dashboard.server` orqali kompyuteringizda kichik boshqaruv paneli
ishga tushiring — u orqali sozlamalarni kiritish, video yaratish va birlashtirish
telefon brauzeridan (bir xil Wi-Fi'da) amalga oshiriladi. **Xavfsizlik**: bu
holatda ham API kalitlaringiz faqat kompyuteringizda qoladi, brauzerga hech qachon
yuborilmaydi. Batafsil: `bots/nature/dashboard/README.md`.

**Futbol boti — takrorlanmaslik + qo'shimcha kontent turlari**:
- **Takrorlanishning oldini olish**: har bir natija, kelgusi o'yin va yangilik
  `bots/football/posted_state.json`'da (idEvent/link bo'yicha) kuzatiladi — bir marta
  joylangan o'yin/yangilik boshqa HECH QACHON qayta joylanmaydi, hatto bot tez-tez
  (har soatda) ishga tushsa ham. Yozuvlar 10 kundan keyin avtomatik tozalanadi
  (`bots/football/state.py`'dagi `DEDUP_KEEP_DAYS`).
- **Qiziqarli fakt ("Bilasizmi?")** — har ishga tushganda (standart: har soatda)
  bitta. Mavzular oldindan qo'lda tanlangan (`bots/football/trivia_topics.py` —
  jahon chempionatlari, mashhur klublar, taktika tarixi, rekordlar va h.k.), LEKIN
  matn har safar Wikipedia'dan JONLI olinadi — statik/qotib qolgan ro'yxat emas,
  har doim eng so'nggi tahrirlangan, manbali ma'lumot. So'nggi 40 ta mavzu
  takrorlanmaydi.
- **Futbolchi sharhi** — kuniga taxminan 2 marta (`FOOTBALL_SPOTLIGHT_MIN_HOURS`
  oralig'ida). Futbolchi nomi oldindan tanlangan ro'yxatdan (`bots/football/players.py`),
  lekin HOZIRGI klubi va tarjimai holi har doim Wikipedia'dan jonli olinadi — shuning
  uchun transfer bo'lganda ham bot avtomatik eng yangi ma'lumotni ko'rsatadi, ro'yxatni
  qo'lda yangilab turish shart emas. **Halollik haqida eslatma**: bot futbolchining
  "texnik imkoniyatlari" haqida o'zi hech narsa TO'QIB CHIQARMAYDI — faqat Wikipedia
  maqolasining boshlang'ich qismini (odatda pozitsiya, o'ynash uslubi va klub tilga
  olinadi) tarjima qilib beradi, bu ancha ishonchli va tekshirib bo'ladigan yondashuv.

## Papka tuzilishi

```
bot_hub/
├── main.py                 # Scheduler — barcha botlarni boshqaradi
├── requirements.txt
├── .env / .env.example
├── bot-hub.service          # systemd unit fayli
├── hub.log                  # ishga tushgach avtomatik yaratiladi
├── shared/
│   ├── telegram_poster.py   # Umumiy Telegram yuborish funksiyalari (qayta urinish bilan)
│   ├── wikipedia.py          # Umumiy Wikipedia ma'lumot olish (tabiat, futbol)
│   ├── translator.py         # Umumiy o'zbek tiliga tarjima (zaxira xizmat bilan)
│   ├── canvas.py               # Umumiy chizish vositalari (gradient, soya, gauge)
│   ├── hashtags.py            # Umumiy hashteg yasovchi
│   ├── timezone_utils.py       # UTC -> mahalliy vaqt o'tkazuvchi (futbol boti)
│   └── fonts.py                # Karta rasmlari uchun umumiy shrift yuklovchi
└── bots/
    ├── nature/               # Tabiat kanali boti — Pixabay/Wikimedia, kunlik jadval,
    │                         # sifat nazorati, AI video (ai_video/), telefon paneli
    │                         # (dashboard/) — batafsil yuqoridagi tegishli bo'limlarda
    ├── crypto/                # Kripto bozor boti (CoinGecko)
    └── football/               # Futbol boti
```

## Muammolarni bartaraf etish

- **"NATURE_TELEGRAM_BOT_TOKEN ... kerak" / shunga o'xshash xato** — `.env` fayl
  yaratilmagan yoki tegishli qator bo'sh. `.env` fayl `main.py` bilan bir papkada
  (hub root) bo'lishi kerak.
- **Telegram "chat not found" xatosi** — bot kanalga admin sifatida qo'shilmagan, yoki
  `*_TELEGRAM_CHANNEL_ID` noto'g'ri.
- **Kripto boti sekin ishlayapti / ba'zi coinlarni o'tkazib yuboryapti** — bu normal.
  Kripto boti CoinGecko API'sidan foydalanadi (Binance emas — pastga qarang), va
  CoinGecko'ning bepul tarifi so'rov chastotasini qattiq cheklaydi (kalitsiz
  5-15/daqiqa). Shuning uchun bitta ishga tushirish bir necha daqiqa davom etishi va
  vaqti-vaqti bilan "rate-limit sababli qayta urinilmoqda" log yozuvlari chiqishi
  mumkin — bu xato emas, avtomatik qayta urinish ishlab turibdi. Tezlashtirish uchun
  `.env`'da `COINGECKO_API_KEY` qiling (bepul "Demo" kalit — pastga qarang).
  **Diqqat**: agar logda `"CoinGecko API kalitingiz rad etildi (401)"` degan xabar
  ko'rsangiz, bu VAQTINCHALIK emas — kunlik/oylik so'rov limitingiz tugagan degani,
  keyingi kun/oygacha davom etadi.
- **"exceeded its memory limit" / "out of memory" (Render, Railway va h.k.)** —
  eng ehtimolli sabab: hub qayta ishga tushganda (masalan avvalgi OOM-restart
  tufayli) tabiat (ffmpeg video qayta kodlash) va kripto (PIL karta chizish) bir
  vaqtda ishlab, xotira cho'qqisi qo'shilib ketishi — bu esa YANA restartga, va
  natijada CHEKSIZ QULASH SIKLIGA olib kelishi mumkin ("bot bir marta ishlab, keyin
  umuman ishlamay qoladi" bo'lib ko'rinadi). Hozirgi kodda bunga qarshi 3 ta himoya
  bor: (1) `shared/resource_guard.py` — ffmpeg va PIL karta chizish hech qachon BIR
  VAQTDA ishlamaydi (mutual exclusion); (2) `HUB_STARTUP_STAGGER_SECONDS` (standart
  60s) — hub qayta ishga tushganda kripto/futbol tabiat botidan keyin, kechikib
  ishga tushadi; (3) `NATURE_MAX_VIDEO_QUALITY_PX` standart qiymati pasaytirilgan
  (1280). Agar bularga qaramay restart davom etsa, quyidagilarni sinab ko'ring:
  video sifatini yanada pasaytiring (`NATURE_MAX_VIDEO_QUALITY_PX=960`), kripto
  botida tahlil qilinadigan koinlar sonini kamaytiring, yoki (eng ishonchli yechim)
  serveringizning operativ xotirasini oshiring (masalan Render'da 512MB'dan 1GB+
  tarifga o'ting) — 3 ta media bilan ishlaydigan botni bitta 512MB konteynerda
  ishlatish har doim chegaraga juda yaqin bo'ladi.
- **Deploy qilingandan keyin tabiat boti yana sekin/429 xato bilan boshlaydi** —
  Render (va shunga o'xshash platformalar) har yangi deploy'da konteynerni
  yangidan yaratadi, shuning uchun `topic_pool_cache.json` kabi kesh fayllari
  o'chib ketadi va bot Wikipedia'dan minglab joyni qaytadan so'rashga majbur
  bo'ladi (429 xavfi oshadi). Buni oldini olish uchun Render'da xizmatingizga
  kichik Persistent Disk ulang (Dashboard → xizmatingiz → Disks → Add Disk, masalan
  1GB, Mount Path masalan `/var/data`) va `.env`'da `HUB_DATA_DIR=/var/data`
  qiling — shundan keyin kesh/holat fayllari o'sha diskka yoziladi va DEPLOY
  QILINGANDA HAM saqlanib qoladi (batafsil izoh `.env.example`'da).
- **Tabiat boti "ishlamayapti" (lekin xato ham yo'q)** — kunlik jadval rejimida
  (standart) bu ko'pincha xato emas: bot shunchaki eng yaqin jadval vaqtini (masalan
  06:00, 08:00...) kutayotgan bo'lishi mumkin — darhol ishlamaydi. `hub.log`'da
  "Tabiat boti KUNLIK jadval bo'yicha ishlaydi..." qatorini qidiring — u yerda
  qaysi vaqtlar rejalashtirilgani ko'rinadi. Agar vaqtlar sizning kutganingizdan
  boshqacha ko'rinsa, `NATURE_TZ_OFFSET_HOURS`ni tekshiring.
- **Kripto/futbol kartalarida matn juda kichik/standart ko'rinishda chiqyapti** —
  `fonts-dejavu-core` o'rnatilmagan. `sudo apt install fonts-dejavu-core` qiling.
- **Bitta bot doim xato beryapti, boshqalari ishlayapti** — bu normal, hub dizayni
  aynan shunday: bitta bot muammosi boshqalarini to'xtatmaydi. `hub.log`'dan aniq
  xatoni toping.

---

## Tabiat boti: postlar arxivi (takroriy postlardan himoya)

Bir marta joylangan har bir video/rasm `posted_archive.jsonl` jurnaliga yoziladi va **hech qachon qayta chiqmaydi**:

- **ID/URL bo'yicha:** `Pixabay:123`, `Pexels:456` kabi kalit va asl URL tekshiriladi.
- **Kontent bo'yicha:** perceptual hash (video — 3 ta kadr, rasm — dHash). Bir xil video boshqa saytda, boshqa ID bilan yoki boshqa sifatda qayta topilsa ham tanib olinadi.
- **Jurnal qisqartirilmaydi** (avval faqat so'nggi 3000 ta saqlanardi), yozuvlar atomar va fsync bilan yoziladi.
- **Telegram zaxirasi:** `.env`dagi `NATURE_ARCHIVE_CHAT_ID` ga yopiq kanal ID'sini yozing (bot u yerda admin bo'lishi va pin qila olishi kerak). Bot arxivni o'sha kanalga pin qiladi va ishga tushganda o'sha yerdan tiklaydi. Render/Railway'da Persistent Disk bo'lmasa, **shuni albatta yoqing**.

Arxiv holatini ko'rish (hub papkasidan): `python -m bots.nature.archive`
