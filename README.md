# Bot Hub — Tabiat + Kripto + Futbol (bitta jarayon)

Uchta Telegram botini (tabiat kanali, kripto bozor, futbol) **bitta Python jarayonida**,
bitta VPS'da, har biri o'z vaqt jadvali va o'z kanaliga ishlaydigan qilib boshqaradi.

- **Tabiat boti** — avvalgi `nature_channel_bot` loyihasi, o'zgarishsiz (`bots/nature/`).
- **Kripto boti** — avvalgi `kripto_bot_mobil.html` (telefonda qo'lda ishga tushiriladigan
  versiya)ning to'liq Python porti (`bots/crypto/`).
- **Futbol boti** — avvalgi `futbol_bot_mobil.html`ning to'liq Python porti (`bots/football/`).

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
- **Kripto boti hech narsa joylamayapti (log'da "KRIPTO BOT TO'XTATILDI: Binance bu
  server joylashgan hududdan...")** — bu Binance'ning O'ZINING geografik cheklovi
  (HTTP 451), sizning kodingiz yoki `.env`'ingizdagi xato emas. Binance ko'plab
  hudud/IP manzillardan (ayniqsa AQSh, va ko'pincha Render/Railway/AWS/GCP kabi bulut
  xizmatlari IP diapazonlaridan) kirishni butunlay taqiqlaydi. Yechimlar:
  1. Render xizmatingizni **boshqa hududga** ko'chiring (masalan Frankfurt yoki
     Singapur — AQSh hududlariga qaraganda ko'pincha bloklanmaydi). Render'da xizmat
     sozlamalaridan "Region"ni o'zgartirish mumkin (ba'zan xizmatni qayta yaratish
     kerak bo'ladi).
  2. Agar bu ham yordam bermasa (Binance ba'zi bulut provayderlarini hudud farqisiz
     bloklaydi), ma'lumot manbasini Binance'dan boshqa (masalan CoinGecko) API'ga
     almashtirish kerak bo'ladi — bu esa `bots/crypto/binance_api.py`da qo'shimcha
     ishlov talab qiladi (funding rate/OI/long-short kabi fyuchers ko'rsatkichlari
     CoinGecko'da yo'q, faqat narx/hajm bor).
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
