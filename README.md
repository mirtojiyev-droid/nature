# Bot Hub — Tabiat + Kripto + Futbol (bitta jarayon)

Uchta Telegram botini (tabiat kanali, kripto bozor, futbol) **bitta Python jarayonida**,
bitta VPS'da, har biri o'z vaqt jadvali va o'z kanaliga ishlaydigan qilib boshqaradi.

- **Tabiat boti** — avvalgi `nature_channel_bot` loyihasi, o'zgarishsiz (`bots/nature/`).
- **Kripto boti** — avvalgi `kripto_bot_mobil.html` (telefonda qo'lda ishga tushiriladigan
  versiya)ning Python porti (`bots/crypto/`). Ma'lumot manbasi **CoinGecko**
  (dastlab Binance edi, lekin Binance.com AQSh va ba'zi bulut serverlari IP'laridan
  kirishni geografik jihatdan bloklagani uchun almashtirildi — pastga qarang).
- **Futbol boti** — avvalgi `futbol_bot_mobil.html`ning to'liq Python porti (`bots/football/`).
  Natija/fixture/yangilik postlari endi TAKRORLANMAYDI (state.py orqali kuzatiladi).
  Qo'shimcha: har soatda bitta qiziqarli futbol fakti va kuniga ~2 marta futbolchi
  sharhi (ikkalasi ham Wikipedia manbali) — pastga qarang.

Uchtasi ham asosan tarmoq so'rovlari bilan band (CPU emas), shuning uchun eng arzon VPS
(1 CPU / 1GB RAM) darajasida ham bemalol ishlaydi.

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
Ubuntu/Debian tizimlarida allaqachon o'rnatilgan bo'ladi). Tabiat boti uchun `ffmpeg` ham
kerak (ixtiyoriy, fon musiqasi va format moslashtirish uchun):

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
- Kripto boti uchun qo'shimcha: `PEXELS_API_KEY` shart emas (u faqat tabiat botiga kerak).
  Buning o'rniga (ixtiyoriy, lekin tavsiya etiladi) [coingecko.com/en/api/pricing](https://www.coingecko.com/en/api/pricing)'dan
  bepul "Demo" API kalit oling va `COINGECKO_API_KEY`'ga qo'ying — bo'lmasa ham
  ishlayveradi, faqat sekinroq (CoinGecko'ning bepul so'rov chastotasi cheklangan).
  **Eslatma**: kripto boti fyuchers ma'lumotlarini (funding rate, Open Interest,
  Long/Short nisbati) ko'rsatmaydi — CoinGecko bunday ma'lumotni umuman bermaydi
  (faqat narx/hajm agregatori). Faqat narx, 24soatlik o'zgarish va RSI ko'rsatiladi.
- Tabiat boti uchun: [pexels.com/api](https://www.pexels.com/api/) (shart) va
  [pixabay.com/api/docs](https://pixabay.com/api/docs/) (ixtiyoriy) kalitlari.

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

Sozlangan botlarning har biri darhol bir marta ishga tushadi (birinchi post joylanadi),
so'ng har biri o'z jadvali bo'yicha fonda ishlashda davom etadi. `hub.log` faylida barcha
uchta botning jarayoni birgalikda ko'rinadi (qaysi bot yozgani `[nature]`/`[bots.crypto.run]`
kabi logger nomidan bilinadi).

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

`.env`'dagi `NATURE_INTERVAL_MINUTES` / `CRYPTO_INTERVAL_MINUTES` /
`FOOTBALL_INTERVAL_MINUTES` orqali sozlanadi (standart: tabiat — 30 daqiqa, kripto — 60
daqiqa, futbol — 240 daqiqa/4 soat). Uch bot bir-biridan mustaqil — bittasining intervali
boshqasiga ta'sir qilmaydi, va bittasi xato bersa (masalan Binance vaqtincha ishlamay
qolsa), faqat o'sha bot safar o'tkazib yuboriladi, boshqalari davom etadi.

**Operativ xotira va bir vaqtda ishlash (`HUB_MAX_CONCURRENT_JOBS`)**: har bir bot o'z
ALOHIDA ip-oqimida (thread) ishlaydi, lekin bir vaqtning o'zida NECHTASI haqiqatan
ISHLASHI (fn() bajarilishi) mumkinligi `.env`'dagi `HUB_MAX_CONCURRENT_JOBS` bilan
cheklanadi:
- **Standart qiymat: 1** — botlar hech qachon bir vaqtda ishlamaydi, navbat bilan
  birin-ketin ishlaydi. Bu Render/Railway kabi platformalarning arzon, kam xotirali
  (512MB-1GB) tariflari uchun **XAVFSIZ va TAVSIYA ETILADI** — ayniqsa tabiat boti 4K
  video qayta kodlayotgan (ffmpeg orqali, bir necha yuz MB operativ xotira talab
  qilishi mumkin) paytda boshqa bot ham ishga tushib qolsa, xotira "out of memory"
  xatosiga olib kelishi mumkin edi.
- Serveringizda operativ xotira yetarli bo'lsa (2GB+), buni 2 yoki 3'ga oshirib,
  botlarning bir-birini kutmasdan tezroq (parallel) ishlashiga ruxsat berishingiz mumkin.

**Muhim**: bu operativ xotira muammosini ikkinchi tomondan ham kamaytiring — tabiat
botining video sifatini `NATURE_MAX_VIDEO_QUALITY_PX` orqali pasaytirish (masalan
4K/3840 o'rniga 1920 yoki 1280) ham xotira sarfini sezilarli kamaytiradi (quyida
alohida bo'limda tushuntirilgan).

**Tabiat boti — 4 soatlik mavzu rejimi**: har 30 daqiqada post qiladi, lekin MAVZUNI
(joyni) har 4 soatda bir marta yangilaydi — shu 4 soatlik oyna ichida bir xil joyning 8
xil qirrasini (sharshara, sohil, tog', quyosh botishi va h.k. — takrorlanmasdan) ko'rsatib
chiqadi, so'ng yangi joyga o'tadi. Bu oraliqni o'zgartirish uchun
`bots/nature/state.py`'dagi `WINDOW_HOURS` qiymatini tahrirlang.

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
├── main.py                 # Scheduler — uchala botni boshqaradi
├── requirements.txt
├── .env / .env.example
├── bot-hub.service          # systemd unit fayli
├── hub.log                  # ishga tushgach avtomatik yaratiladi
├── shared/
│   ├── telegram_poster.py   # Umumiy Telegram yuborish funksiyalari
│   └── fonts.py             # Karta rasmlari uchun umumiy shrift yuklovchi
└── bots/
    ├── nature/               # Tabiat kanali boti (avvalgi nature_channel_bot)
    ├── crypto/                # Kripto bozor boti
    └── football/              # Futbol boti
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
- **"exceeded its memory limit" / "out of memory" (Render, Railway va h.k.)** —
  eng ehtimolli sabab: tabiat botining 4K video qayta kodlashi (ffmpeg) ko'p operativ
  xotira talab qiladi. Ikkita narsani sinab ko'ring (ikkalasi ham birga ishlatilishi
  mumkin): (1) `.env`'da `NATURE_MAX_VIDEO_QUALITY_PX=1280` qiling (video sifatini
  pasaytiradi, xotira sarfini kamaytiradi); (2) `HUB_MAX_CONCURRENT_JOBS=1` ekanini
  tekshiring (standart shunday — botlar bir vaqtda ishlamasin). Ikkalasi ham yordam
  bermasa, serveringizning operativ xotirasini oshiring (masalan Render'da Standard
  tarifga o'ting).
- **Kripto/futbol kartalarida matn juda kichik/standart ko'rinishda chiqyapti** —
  `fonts-dejavu-core` o'rnatilmagan. `sudo apt install fonts-dejavu-core` qiling.
- **Bitta bot doim xato beryapti, boshqalari ishlayapti** — bu normal, hub dizayni
  aynan shunday: bitta bot muammosi boshqalarini to'xtatmaydi. `hub.log`'dan aniq
  xatoni toping.
- Tabiat botiga xos muammolar (video/rasm sifati, ffmpeg va h.k.) uchun
  `bots/nature/` ichidagi eski `README.md`'dagi "Muammolarni bartaraf etish"
  bo'limi ham amal qiladi (fayl nomlari bir xil qolgan, faqat joylashuvi o'zgargan).
