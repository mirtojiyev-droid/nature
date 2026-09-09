# YouTube Shorts (va uzun videolar) trendlarini Telegram kanalga avtomatik joylash

> **Diqqat — bot_hub'ga integratsiya qilingan:** bu bot endi mustaqil emas,
> `bot_hub`ning bir qismi sifatida ishlaydi (`bots/youtube/`). Quyidagi hujjatda
> tilga olingan `.env` o'zgaruvchilari (masalan `TELEGRAM_BOT_TOKEN`,
> `REGION_CODE`, `MIN_VIEWS`) endi barchasi **`YOUTUBE_` prefiksi** bilan
> (masalan `YOUTUBE_TELEGRAM_BOT_TOKEN`, `YOUTUBE_REGION_CODE`,
> `YOUTUBE_MIN_VIEWS`) — to'liq ro'yxat hub root'idagi `.env.example`'da.
> Telegram'ga yuborish endi `shared/telegram_poster.py` orqali (qayta urinish
> va hajm tekshiruvi bilan). Ishga tushirish uchun alohida `python main.py`
> shart emas — hub'ning o'zi `YOUTUBE_INTERVAL_MINUTES` (standart 120 daqiqa —
> har 2 soatda) bo'yicha avtomatik chaqiradi. Qolgan barcha mantiq (til
> aniqlash, uch turkumli tanlov, takrorlanmaslik, hashtaglar va h.k.)
> o'zgarishsiz — quyidagi hujjat shularni tushuntiradi.

Bu modul YouTube'dagi eng ko'p ko'rilayotgan Shorts'larni (standart
bo'yicha uzunroq videolarni ham) aniqlaydi, oldindan qo'yilgan
filtrlardan (ko'rishlar soni, yosh, davomiylik) o'tkazadi, yuklab oladi
va Telegram kanalingizga joylaydi. Bir marta joylangan video qayta
joylanmasligi uchun `posted.json` faylida yozib boriladi.

**Muhim: bot so'z (matn) bo'yicha qidiruv qilmaydi.** Avvalgi
versiyada `search.list` orqali `SEARCH_QUERY`ga (masalan "music") mos,
ko'rishlar soni bo'yicha saralangan videolar qidirilar edi — lekin bu
yondashuv mintaqadan qat'i nazar butun dunyo bo'yicha eng ko'p
ko'rilgan (odatda hind/Bollywood) kontentni qaytarishga moyil edi, til
sozlamalari qancha kuchaytirilmasin. Shuning uchun endi FAQAT
YouTube'ning rasmiy TREND jadvalidan (`videos.list?chart=mostPopular`
— youtube.com/feed/trending bilan bir xil manba) foydalaniladi — bu
mintaqada AYNAN HOZIR trend bo'lgan videolarni beradi:

1. Avval `REGION_CODE` (masalan `UZ`) va har bir `EXTRA_REGION_CODES`
   mintaqasi uchun trend jadvali `VIDEO_CATEGORY_ID` (masalan `10` —
   Music) bilan cheklab so'raladi.
2. Ko'p mintaqada kategoriya bilan cheklangan trend jadvali umuman
   mavjud emas — bunday holda avtomatik ravishda o'sha mintaqaning
   UMUMIY trend jadvali olinadi va natijalar keyinroq `categoryId`
   bo'yicha (masalan faqat Music) qo'lda filtrlanadi.
3. Barcha mintaqalardan kelgan videolar ID bo'yicha birlashtiriladi.

Ro'yxat oxirida videolar **xom ko'rishlar soni bo'yicha kamayish
tartibida** (eng ko'p ko'rilgani birinchi) saralanadi — soat boshiga
tezlik emas (tezlik/trend bo'yicha saralash alohida "turkum" sifatida
pastda tushuntirilgan).

Barcha mintaqadan kelgan videolar birlashtirilib, `MIN_VIEWS`,
`MAX_AGE_HOURS` va davomiylik (`MAX_DURATION_SEC` / `MAX_LONG_DURATION_SEC`
/ `VIDEO_LENGTH_MODE`) mezonlari bilan filtrlanadi (haddan tashqari
uzun videolarni behuda yuklab olmaslik uchun — Telegram'ning 50MB
limiti ham bor). Agar natija hech narsa qaytarmasa, terminaldagi loglarda aynan qaysi
bosqichda (kategoriya/kalit so'z, davomiylik, ko'rishlar, eskilik)
videolar chiqib ketayotgani ko'rsatiladi — shu mezonlardan birini
bo'shashtirib ko'ring.

### Faqat musiqa, Shorts'siz, o'yin/Roblox videolarisiz

Standart sozlamalar shunga moslangan:

- `VIDEO_CATEGORY_ID=10` (Music) — trend jadvali shu kategoriya bilan cheklanadi (yoki umumiy jadvaldan shu kategoriya bo'yicha filtrlanadi).
- `VIDEO_LENGTH_MODE=long` — Shorts umuman qaralmaydi va filtrdan ham butunlay chiqarib tashlanadi, faqat uzun (musiqa klipi/audio) videolar qoladi.
- `EXCLUDE_CATEGORY_IDS=20` (Gaming) — bu kategoriyadagi videolar avtomatik chiqarib tashlanadi.
- `EXCLUDE_KEYWORDS=roblox,gameplay,minecraft,fortnite,gta,pubg,free fire` — sarlavhasida shu so'zlardan biri bo'lgan video (kategoriyasidan qat'i nazar) chiqarib tashlanadi.

Bu ikki qatlamli himoya: kategoriya bo'yicha (YouTube o'zi belgilagan) va
kalit so'z bo'yicha (sarlavhada). Agar boshqa turdagi kontentni ham
chetlab o'tmoqchi bo'lsangiz, `EXCLUDE_KEYWORDS`ga vergul bilan
qo'shimcha so'zlar qo'shsangiz bo'ladi. Boshqa mavzuga qaytmoqchi
bo'lsangiz, `.env`dagi `VIDEO_CATEGORY_ID`/`VIDEO_LENGTH_MODE`ni
o'zgartiring (yoki `--category`/`--length` bilan bir martalik
almashtiring).

**Diqqat:** bu bosqichda faqat YouTube -> Telegram yo'nalishi ishlaydi.
TikTok tarafi (trend aniqlash va avtomatik joylash) alohida bosqich —
TikTok'da rasmiy ochiq trend API yo'q va avtomatik joylash uchun TikTok
Developer portalida alohida ilova tasdiqlatish kerak bo'ladi, shu sabab
keyingi qadam sifatida qoldirildi.

## 1. YouTube API kalitini olish

1. https://console.cloud.google.com ga kiring, yangi loyiha yarating.
2. "APIs & Services -> Library" bo'limidan **YouTube Data API v3** ni toping va yoqing.
3. "APIs & Services -> Credentials" bo'limidan yangi **API key** yarating.
4. Kalitni `.env` fayliga `YOUTUBE_API_KEY` sifatida qo'ying.

Bepul kvota kuniga 10,000 birlik. Har bir ishga tushirish ~100-150 birlik
sarflaydi, shuning uchun kuniga 4-6 marta ishga tushirish xavfsiz.

## 2. Telegram botini yaratish

1. Telegram'da @BotFather bilan suhbatlashib, `/newbot` orqali bot yarating.
2. Bergan tokenni `.env` fayliga `TELEGRAM_BOT_TOKEN` sifatida qo'ying.
3. Botni o'z kanalingizga **admin** sifatida qo'shing (video joylash huquqi bilan).
4. Kanal username'ini (masalan `@mening_kanalim`) yoki raqamli chat_id'sini
   `.env` fayliga `TELEGRAM_CHANNEL_ID` sifatida qo'ying.

## 3. O'rnatish

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# .env faylini ochib, yuqoridagi qiymatlarni to'ldiring
```

**Muhim: `ffmpeg` kerak.** `yt-dlp` video va audio oqimlarini birlashtirib
mp4 qilish uchun `ffmpeg`dan foydalanadi. Windows'da
[ffmpeg.org](https://ffmpeg.org/download.html)dan yuklab, PATH'ga
qo'shing (yoki `choco install ffmpeg` / `winget install ffmpeg`); Linux
VPS'da `apt install ffmpeg` kifoya. `ffmpeg` bo'lmasa, yuklab olish
audiosiz chiqishi yoki umuman xato berishi mumkin.

## 4. Ishga tushirish

```bash
python main.py
```

### Kategoriyani ishga tushirishda almashtirish

Bot doim `.env`dagi `VIDEO_CATEGORY_ID` bo'yicha qidiradi, lekin har safar
`.env`ni tahrirlamasdan, shu ishga tushirish uchun boshqa kategoriya
berish mumkin:

```bash
python main.py --category comedy      # nom bilan
python main.py --category 24          # yoki to'g'ridan-to'g'ri ID bilan
python main.py --list-categories      # mavjud barcha kategoriyalar ro'yxati
```

Standart bo'yicha bot faqat musiqa trend jadvalini qaraydi
(`VIDEO_CATEGORY_ID=10`, `VIDEO_LENGTH_MODE=long` — Shorts umuman
qaralmaydi). Masalan kulgili (comedy) kontentga qaytmoqchi bo'lsangiz,
`--length`ni ham kerak bo'lsa birga bering:

```bash
python main.py --category comedy --length both
```

Doimiy o'zgartirish uchun `.env` faylida ikkalasini ham yangilang:

```
VIDEO_CATEGORY_ID=23
VIDEO_LENGTH_MODE=both
```

### Bitta ishga tushirishda nechta video joylanadi

Standart bo'yicha bot har safar ishga tushganida **5 ta** post
joylaydi, va bu 5 ta uchta turkumga bo'linadi (har bir video faqat
bitta turkumda ishlatiladi, takrorlanmaydi):

| Turkum | .env o'zgaruvchisi | Standart | Saralash mezoni |
| --- | --- | --- | --- |
| Trend (hozir eng tez o'sayotgan) | `POSTS_TRENDING` | `1` | `views / video yoshi (soat)` — eng yuqori |
| Eng ko'p ko'rilgan | `POSTS_MOST_VIEWED` | `2` | xom ko'rishlar soni — eng yuqori |
| Eng yangi | `POSTS_NEWEST` | `2` | chop etilgan vaqti — eng yaqin |

`MAX_POSTS_PER_RUN` standart bo'yicha shu uchtaning yig'indisi (`5`),
lekin xohlasangiz `.env`da alohida ham belgilashingiz mumkin (bunda
tarkibiy qismlar bilan mos kelishiga e'tibor bering). Har bir turkum
ichida, avval `AVOID_LANGUAGES`dagi tildagi nomzodlar orqaga
suriladi va `PREFERRED_LANGUAGES`dagi tildagi nomzodlar oldinga
suriladi (pastdagi bo'limga qarang), so'ng shu turkumning o'z mezoni
bo'yicha saralanadi. Allaqachon joylangan (`posted.json`da bor)
nomzodlar boshidanoq chiqarib tashlanadi. Kamroq yoki ko'proq video
joylashni xohlasangiz, `.env`da mos o'zgaruvchilarni o'zgartiring.

### Har bir ishga tushirishda kamida bitta o'zbekcha post

Tanlangan 5 ta post orasida o'zbekcha (yoki o'zbekcha deb taxmin
qilingan) kontent umuman bo'lmay qolmasligi uchun,
`MIN_UZBEK_PER_RUN` (standart `1`) yuqoridagi uchta turkum bo'yicha
tanlovdan KEYIN, alohida qo'shimcha qatlam sifatida ishlaydi: agar
tanlangan postlar orasida yetarlicha o'zbekcha video bo'lmasa,
qolgan (tanlanmagan) nomzodlar orasidan eng ko'p ko'rilgan o'zbekcha
nomzod(lar) bilan, tanlangan postlar ichidagi eng past ustuvorlikdagi
o'zbekcha bo'lmagan nomzod(lar) almashtiriladi. Agar umuman o'zbekcha
nomzod topilmasa, bu talab xatosiz e'tiborsiz qoldiriladi. "O'zbekcha"
deb taxmin qilish (`classify_language`, `youtube_trends.py`) uchun
bir nechta signal ishlatiladi: avval YouTube'ning
`defaultAudioLanguage`/`defaultLanguage` maydoni (agar `uz`/`en`/
`ru`/`hi` bilan boshlansa, shunga ishoniladi), bo'lmasa devanagari
yozuvi (hind tili), so'ng sarlavha/kanal nomidagi o'zbek tiliga xos
harflar (kirill ў/қ/ғ/ҳ, lotin apostrofli o'/g') yoki tez uchraydigan
o'zbekcha so'zlar (qo'shiq, ashula, konsert va h.k.), so'ng kirill
harflari (rus), so'ng lotin/ASCII harflarining ustunligi (ingliz);
hech biriga to'g'ri kelmasa "boshqa" deb belgilanadi. `0` qilib
qo'ysangiz, bu talab butunlay o'chadi.

### Barcha topilgan nomzod allaqachon joylangan bo'lsa

Trend jadvali (bitta kategoriya + bir nechta mintaqa bilan cheklangan)
tez-tez o'zgarmaydi, shuning uchun bot ketma-ket bir necha marta ishga
tushirilsa, avvalgi ishga tushirishda joylangan videolarning barchasi
qayta chiqishi mumkin. Bu holatda bot avtomatik ravishda eskilik
(`MAX_AGE_HOURS`) va davomiylik (`MAX_LONG_DURATION_SEC`) chegaralarini
vaqtincha kengaytirib, xuddi shu trend jadvalidan BOSHQA (hali
joylanmagan) nomzod bormi qayta tekshiradi — shunda "bu allaqachon
joylangan" videoning o'rniga avtomatik boshqasi topiladi. Faqat shu
kengaytirilgan qidiruv ham hech narsa topa olmasa (haqiqatan hozircha
yangi material yo'q bo'lsa), botning o'zi boshqa hech narsa qila
olmaydi — trend jadvali yangilanishini kutish yoki `EXTRA_REGION_CODES`ga
qo'shimcha mintaqa qo'shish kerak bo'ladi.

### Yuklab bo'lmagan videolar (mintaqaviy cheklov, "Video unavailable")

Ikki qatlamli himoya bor:

1. **Oldindan filtrlash:** YouTube API har bir video uchun mintaqaviy
   cheklov ma'lumotini (`contentDetails.regionRestriction`) qaytaradi.
   Agar video `REGION_CODE` uchun yopiq bo'lsa (masalan boshqa
   mamlakat uchun litsenziyalangan musiqa klipi), u nomzodlar
   ro'yxatiga UMUMAN qo'shilmaydi — chunki baribir yuklab bo'lmaydi
   ("Video unavailable" xatosi bilan tugaydi).
2. **Zaxira navbat:** shunga qaramay, boshqa sabablarga ko'ra
   (video o'chirilgan, tarmoq xatosi va h.k.) ba'zi nomzodlar
   yuklanmasligi mumkin. Shuning uchun bot faqat dastlab tanlangan
   (masalan 5 ta) nomzod bilan cheklanib qolmaydi — ulardan biri
   yuklab yoki Telegram'ga joylab bo'lmasa, qolgan nomzodlar
   to'plamidan navbatdagi eng mos keladigani avtomatik sinab
   ko'riladi, toki `MAX_POSTS_PER_RUN` ta muvaffaqiyatli joylanguncha
   yoki butun to'plam tugaguncha. Agar shunga qaramay ba'zi postlar
   kam bo'lsa, logda ochiq ogohlantirish chiqadi va odatda sabab
   `yt-dlp` eskirib qolgani (`pip install -U yt-dlp` bilan tuzatiladi
   — pastdagi "Muntazam ishga tushirish" bo'limiga qarang).

### Hashtaglar (Telegram ichida qidirilganda topilishi uchun)

Har bir postning caption'iga avtomatik ravishda kamida **5 ta
hashtag** qo'shiladi (`hashtags.py`), shunda masalan qo'shiq
postlari Telegram ichida qidirilganda topilishi osonlashadi.
Hashtaglar quyidagilardan yasaladi: YouTube kategoriyasi (masalan
`#Music`), til (video `uz`, `en`, `ru` yoki `hi` deb taxmin
qilingan bo'lsa, mos `#Uzbek #UzbekMusic` / `#English` / `#Russian`
/ `#Hindi` kabi hashtaglar — "boshqa" deb belgilangan videolarga til
hashtag'i qo'shilmaydi, noto'g'ri hashtag qo'yib izlovchilarni
chalg'itmaslik uchun), kanal nomi, sarlavhadagi ma'noli so'zlar
(umumiy so'zlar — "official", "video" va h.k. — chiqarib tashlanadi)
va, agar yetarli bo'lmasa, umumiy hashtaglar (`#Trending`, `#Viral`
va h.k.).

### Til ustuvorligi va hind tilini kamaytirish

`REGION_CODE=UZ` faqat "shu mintaqada trend" degani — O'zbekistonda
xalqaro (ayniqsa hind/Bollywood) musiqa ham juda mashhur bo'lgani
uchun, faqat mintaqa bo'yicha qarash ba'zan kanal auditoriyasiga
(ingliz, rus, o'zbek tilida so'zlashuvchilarga) mos kelmaydigan
natijalar beradi. Buning oldini olish uchun bir nechta mexanizm
birgalikda ishlaydi — **bularning hech biri so'z (matn) bo'yicha
qidiruv emas**, faqat allaqachon YouTube'ning o'z trend jadvalidan
olingan nomzodlarni mintaqa/saralash orqali xilma-xillashtirish va
kamroq/ko'proq ko'rsatish:

1. **`PREFERRED_LANGUAGES`** (standart `en,ru,uz`) — har bir turkum
   (trend/eng ko'p ko'rilgan/eng yangi) ichida shu tillardagi
   nomzodlar ustunroq tanlanadi. Qattiq filtr emas: agar shu
   tillardagi nomzod yetarli bo'lmasa, boshqa (`AVOID_LANGUAGES`dan
   tashqari) tildagi nomzod ham ishlatiladi.
2. **`AVOID_LANGUAGES`** (standart `hi` — hind tili) — bu tildagi
   nomzodlar har doim ro'yxatning oxiriga suriladi, ya'ni boshqa
   yetarli nomzod bo'lsa, deyarli hech qachon tanlanmaydi. Qattiq
   taqiq emas: agar biror turkumda FAQAT shu tildagi nomzod qolgan
   bo'lsa, baribir ishlatiladi (aks holda bot hech narsa joylay
   olmay qolishi mumkin edi).
3. **`EXTRA_REGION_CODES`** (standart `US,RU`) — `REGION_CODE`dan
   tashqari, shu qo'shimcha mintaqalarning trend jadvali ham olinadi.
   Bitta mintaqaning (masalan faqat UZ) trend jadvaliga tayanish
   natijalarni o'sha mintaqada trend bo'lgan (ba'zan hind) kontentga
   qarab siljitib yuboradi — qo'shimcha mintaqalar natijalarni
   xilma-xillashtirib, ingliz/rus tilidagi kontentni ham faolroq
   topishga yordam beradi.
4. **`MIN_UZBEK_PER_RUN` kafolati** (yuqoriga qarang) — tanlangan
   postlar orasidan kamida shuncha tasi o'zbekcha bo'lishini
   ta'minlaydi. O'zbekcha kontent trend jadvalida kam bo'lgan
   holatlarda (masalan barcha nomzodlar boshqa tilda bo'lsa), bu talab
   xatosiz e'tiborsiz qoldiriladi.

Bularning barchasi FAQAT allaqachon olingan trend nomzodlarni
saralash/almashtirish uchun ishlatiladi — hech biri qo'shimcha qidiruv
so'rovi yubormaydi, shuning uchun kvota narxiga ta'sir qilmaydi.

### Bot o'zi tanlagan narsani emas, aynan siz ko'rsatgan videoni joylash

Bot avtomatik rejimda YouTube trendlaridan o'zi tanlaydi — ba'zan siz
kutmagan video chiqishi mumkin. Agar aynan bitta ma'lum videoni qo'lda
tanlab, o'sha yuklanib Telegram'ga joylanishini xohlasangiz, `--url`
bering — bu holda avtomatik qidiruv butunlay o'tkazib yuboriladi:

```bash
python main.py --url "https://www.youtube.com/shorts/XXXXXXXXXXX"
python main.py --url "https://youtu.be/XXXXXXXXXXX"
# Video avvalroq joylangan bo'lsa ham baribir joylash uchun:
python main.py --url "https://youtu.be/XXXXXXXXXXX" --force
```

## 5. Muntazam ishga tushirish (VPS)

Eng oddiy yo'l — cron:

```bash
# Har 4 soatda bir marta ishga tushirish
0 */4 * * * cd /path/to/youtube_telegram_repost && /path/to/venv/bin/python main.py >> run.log 2>&1
```

**Tavsiya:** YouTube tez-tez o'zgargani uchun `yt-dlp` ba'zan eskirib,
"403 Forbidden" xatosi bera boshlaydi (pastdagi "Bilishingiz kerak
bo'lgan cheklovlar" bo'limiga qarang). Uzoq muddat kuzatuvsiz ishlashi
uchun, `yt-dlp`ni har safar avtomatik yangilab turgan ma'qul:

```bash
# Har 4 soatda: avval yt-dlp yangilanadi, keyin bot ishga tushadi
0 */4 * * * cd /path/to/youtube_telegram_repost && /path/to/venv/bin/pip install -U yt-dlp -q && /path/to/venv/bin/python main.py >> run.log 2>&1
```

Agar mavjud `bot_hub` (nature/crypto/football botlari birlashtirilgan
jarayon) ichiga qo'shmoqchi bo'lsangiz, `main.run()` funksiyasini import
qilib, o'sha jarayonning schedule tizimiga (masalan har 4 soatda) ulash
kifoya — alohida process ochish shart emas.

## Sozlamalarni moslashtirish (`.env`)

| O'zgaruvchi | Ma'nosi | Standart |
|---|---|---|
| `REGION_CODE` | Qaysi mamlakatning trend jadvali asosiy manba | `UZ` |
| `EXTRA_REGION_CODES` | `REGION_CODE`dan tashqari trend jadvali ham olinadigan qo'shimcha mintaqalar | `US,RU` |
| `VIDEO_CATEGORY_ID` | Trend jadvali shu kategoriya bilan cheklanadi (10 = Music) | `10` |
| `MIN_VIEWS` | Minimal ko'rishlar soni | `100000` |
| `MAX_AGE_HOURS` | Video necha soat ichida chop etilgan bo'lishi kerak | `168` |
| `MAX_DURATION_SEC` | Shorts hisoblanadigan davomiylik chegarasi (soniya) — 60-180 oralig'i | `180` |
| `VIDEO_LENGTH_MODE` | `short` — faqat Shorts, `long` — faqat uzun videolar (Shorts'siz), `both` — ikkalasi | `long` |
| `MAX_LONG_DURATION_SEC` | `long`/`both` rejimida ruxsat etilgan eng katta davomiylik (soniya) | `900` |
| `POSTS_TRENDING` | Trend turkumidan nechta post (eng tez o'sayotgan) | `1` |
| `POSTS_MOST_VIEWED` | Eng ko'p ko'rilgan turkumidan nechta post | `2` |
| `POSTS_NEWEST` | Eng yangi turkumidan nechta post | `2` |
| `MAX_POSTS_PER_RUN` | Bitta ishga tushirishda nechta video joylansin (standart uchtaning yig'indisi) | `5` |
| `MIN_UZBEK_PER_RUN` | Shundan kamida shunchasi o'zbekcha (taxmin) bo'lishi kafolatlanadi | `1` |
| `PREFERRED_LANGUAGES` | Har bir turkum ichida ustunlik beriladigan tillar (ISO 639-1, vergul bilan) | `en,ru,uz` |
| `AVOID_LANGUAGES` | Imkon qadar kam ko'rsatiladigan tillar (qattiq taqiq emas) | `hi` |

## Bilishingiz kerak bo'lgan cheklovlar

- **Mualliflik huquqi:** boshqa muallif joylagan videoni qayta joylash
  mualliflik huquqi bilan bog'liq xavf tug'diradi (video olib tashlanishi,
  kanal cheklanishi mumkin). Xavfni kamaytirish uchun caption'da manba
  havolasi avtomatik qo'shiladi (`main.py` ichida), lekin bu to'liq
  himoya bermaydi.
- **Telegram'ga yuklashda tarmoq xatosi (timeout/ConnectionError):**
  katta video sekin internetda bir necha daqiqa yuklanishi mumkin —
  `telegram_bot.py` endi bunday tarmoq xatolarini avtomatik 2 martagacha
  qayta uringandan keyin, muvaffaqiyatsiz bo'lsa ham (avvalgidek xom
  traceback bilan emas) toza xato sifatida qaytaradi, shunda faqat shu
  bitta video o'tkazib yuboriladi va navbatdagi videoga o'tiladi.
- **Sekinlik va "osilib qolish" bo'yicha:** bir nechta narsa aniqlanib,
  tuzatildi: (1) yuklab olish jarayonida `quiet=True` yt-dlp'ning o'z
  progress-barini yashirgani uchun sekin (lekin ishlayotgan) yuklashlar
  "muzlab qolgan"dek ko'rinardi — endi har 5 sekundda "Yuklanmoqda: X%
  (tezlik, ETA)" tarzida log chiqadi; (2) tarmoq ulanishi haqiqatan
  javob bermay qolganda eng yomon holatda juda uzoq (yuklab olishda
  ~150 soniyagacha, Telegram'ga yuborishda ~10 daqiqagacha) kutish bor
  edi — bu qisqartirildi (`downloader.py`: socket_timeout 15 sek + 3
  marta qayta urinish; `telegram_bot.py`: timeout 120 sek), shunda
  haqiqatan uzilib qolgan ulanish tezroq aniqlanib, keyingi videoga
  o'tiladi; (3) `posted.json`ni har bir nomzod uchun alohida-alohida
  qayta o'qib tekshirish o'rniga (`storage.py`), endi bir ishga
  tushirish uchun ID'lar to'plami bir marta yuklab olinadi — bu fayl
  vaqt o'tishi bilan kattalashgani sayin sezilarli tezlik farqi beradi.
- **Telegram fayl hajmi:** oddiy Bot API orqali 50MB dan katta video
  yuborib bo'lmaydi (Shorts uchun odatda muammo emas, uzun videolar
  uchun `downloader.py` avtomatik ~45MB'dan kichikroq — yoki topilmasa
  480p'gacha cheklangan — formatni tanlaydi, shu limitdan chiqmaslik
  uchun).
- **`yt-dlp` "HTTP Error 403: Forbidden" xatosi (ayniqsa yuklab olish
  jarayonining o'rtasida to'xtab qolishi):** bu YouTube'ning
  yt-dlp'ga qarshi tez-tez o'zgarib turadigan cheklovlari (masalan
  "SABR streaming" yoki `android_vr` klient bilan bog'liq muammolar)
  sabab bo'ladi — bu yt-dlp loyihasida doimiy kuzatilib, tuzatilib
  turadigan holat, sizning sozlamalaringizdagi xato emas. Birinchi
  navbatda `yt-dlp`ni yangilang:
  ```bash
  pip install -U yt-dlp
  ```
  Agar shundan keyin ham xato chiqsa: (1) `YTDLP_COOKIES_FILE` orqali
  cookie fayl bering (yuqoriga qarang) — ayniqsa VPS'da bu ko'pincha
  yordam beradi; (2) `yt-dlp`ning imzo (signature) chiqarish uchun
  JavaScript runtime (Deno yoki Node.js) talab qilishi mumkin —
  o'rnatilganini tekshiring; (3) muammo davom etsa, bu odatda YouTube
  tarafida vaqtinchalik — bir necha kundan keyin `yt-dlp`ning yangi
  versiyasi chiqadi.

  Bot uzoq muddat kuzatuvsiz (masalan VPS'da cron orqali) ishlashi
  kerak bo'lgani uchun, har safar ishga tushishdan oldin `yt-dlp`ni
  avtomatik yangilab turish tavsiya etiladi:
  ```bash
  # Har 4 soatda: avval yt-dlp yangilanadi, keyin bot ishga tushadi
  0 */4 * * * cd /path/to/youtube_telegram_repost && /path/to/venv/bin/pip install -U yt-dlp -q && /path/to/venv/bin/python main.py >> run.log 2>&1
  ```
- **YouTube "Shorts" filtri heuristika:** YouTube API'da rasmiy "Shorts"
  belgisi yo'q, shuning uchun davomiylik (`MAX_DURATION_SEC`) orqali
  taxminiy filtrlanadi.
- **"Sign in to confirm you're not a bot" xatosi:** YouTube ba'zan
  `yt-dlp`ning yuklab olishini bloklaydi, ayniqsa VPS kabi brauzer
  cookie'lari yo'q joylarda. Shunday xato ko'p chiqsa, brauzeringizdan
  (YouTube'ga kirgan holda) cookie faylini eksport qilib (masalan "Get
  cookies.txt" kengaytmasi bilan), yo'lini `.env`dagi
  `YTDLP_COOKIES_FILE`ga yozing — `downloader.py` uni avtomatik ishlatadi.
