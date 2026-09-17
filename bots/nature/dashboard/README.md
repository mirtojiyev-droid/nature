# AI Video boshqaruv paneli

Kompyuteringizda ishlaydi, telefon brauzeringizdan (bir xil Wi-Fi tarmog'ida)
boshqariladi. Runway/Kling kabi "maxfiy" API kalitlaringiz **faqat shu
kompyuterda** qoladi — brauzerga hech qachon yuborilmaydi (bu boshqa
HTML-asboblarimizdan (crypto, youtube) ATAYLAB farqli — chunki bu yerdagi
kalitlar pullik va o'g'irlansa moliyaviy zarar keltirishi mumkin).

## Ishga tushirish

Asosiy `bot_hub` o'rnatilgan bo'lishi kerak (`pip install -r requirements.txt`
allaqachon `flask`ni ham o'rnatadi). Keyin:

```
cd bot_hub
python -m bots.nature.dashboard.server
```

Terminalda ko'rsatilgan manzilni (masalan `http://192.168.1.5:5050`) telefon
brauzeringizda oching (kompyuter bilan bir xil Wi-Fi tarmog'ida bo'lishi kerak).

## Bo'limlar

1. **Sozlamalar** — qaysi provayder (Runway/Kling) ishlatilishini tanlaysiz va
   API kalit(lar)ingizni kiritasiz. Kalitlar `.env` fayliga yoziladi (shu
   kompyuterda qoladi).
2. **Yaratish** — joy/qirra tanlab (yoki o'zingiz erkin prompt yozib), bitta
   AI video yaratasiz. Har bosish — pullik so'rov (~$0.05-0.15/soniya,
   provayderga qarab) — narxni oldindan hisobingizdan tekshiring.
3. **Birlashtirish** — `localfootage/`dagi (shu jumladan avval yaratilgan)
   kliplardan bir nechtasini belgilab, bitta uzunroq videoga birlashtirasiz —
   fon musiqasi ham avtomatik qo'shiladi (agar `bots/nature/music/` papkasida
   trek bo'lsa).

Yaratilgan/birlashtirilgan barcha videolar to'g'ridan-to'g'ri
`bots/nature/localfootage/`ga tushadi — asosiy bot ularni keyingi postlarda
avtomatik, **eng birinchi navbatda** ishlatadi.

## Muammolarni bartaraf etish

- **Telefon ulanolmayapti** — kompyuter va telefon bir xil Wi-Fi'da ekanini
  tekshiring.
- **"RUNWAY_API_KEY ... sozlanmagan" xatosi** — Sozlamalar bo'limida kalitni
  kiritib, "Saqlash"ni bosganingizni tekshiring.
- **Generatsiya juda uzoq davom etyapti** — bu normal, odatda 1-2 daqiqa
  vaqt oladi (AI serverida video render qilinadi).
- **Musiqa qo'shilmayapti** — `bots/nature/music/` papkasida `.mp3`/`.m4a`
  fayl borligini tekshiring.
