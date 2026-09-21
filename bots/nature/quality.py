"""4K sifat standart bo'lsa-da, ba'zi hosting platformalari (masalan Render'ning arzon
tariflari, odatda 512MB RAM) 4K video bilan ishlashga (ayniqsa ffmpeg qayta kodlashda)
yetarli operativ xotiraga ega bo'lmasligi mumkin. Shu sababli maksimal video o'lchami
`.env`'dagi NATURE_MAX_VIDEO_QUALITY_PX orqali pasaytirilishi mumkin — bu HAM manba
(fetch) bosqichida qanday fayl tanlanishiga, HAM ffmpeg orqali qayta kodlashga ta'sir
qiladi (kichikroq manba = kamroq operativ xotira sarfi).

MUHIM: bu qiymat funksiya sifatida (module-level konstanta emas) ochilgan, chunki .env
fayli `run.py`'ning `run_once()` funksiyasi ICHIDA (`load_dotenv()` orqali) yuklanadi —
bu fetcher modullari esa run.py boshida IMPORT qilinadi, ya'ni .env hali yuklanmagan
paytda. Agar bu qiymat module-level konstanta bo'lganida, har doim standart (3840) bilan
qolib ketardi, .env'dagi o'zgartirish e'tiborga olinmasdi.

MUHIM (haqiqiy voqeada aniqlangan OOM sababi — ATAYLAB PAST STANDART): avval standart
qiymat 3840 (4K) edi. Bu, foydalanuvchi NATURE_MAX_VIDEO_QUALITY_PX'ni Render Environment
Variables'ga QO'LDA QO'SHMAGAN bo'lsa, fetcherlar (pixabay/pexels/wikimedia) har doim
4K MANBA faylni tanlab, yuklab olishga urinishi degani edi — bu esa (keyinchalik
ffmpeg uni pastroqqa siqsa ham) yuklab olish + dekodlash bosqichida ham katta xotira/
tarmoq sarfini talab qilib, kam xotirali (512MB) serverlarda "out of memory" (Render
avtomatik restart) uchun YETARLI bo'lib chiqdi — hatto tabiat boti YOLG'IZ O'ZI ishlagan
holatda ham. Shuning uchun endi standart pasaytirilgan — LEKIN 1920 (Full HD) qilib
belgilangan, 720 EMAS: agar bu yerdagi qiymat config.py'dagi NATURE_MIN_VIDEO_PX
standart chegarasidan (1080, "qisqa tomon") past bo'lsa, hech qanday haqiqiy video
("qisqa tomoni >=1080, LEKIN uzun tomoni <=720" — matematik jihatdan MUMKIN EMAS,
uzun tomon har doim qisqa tomondan katta) bu ikkala shartni birga qanoatlantira
olmay, bot HECH QACHON video topa olmay qoladi. 1920 — oddiy 1080p (1920x1080)
manba fayllarni o'tkazish uchun yetarli, shu bilan birga 4K'dan ancha yengil.
Haqiqiy OG'IR bosqich (ffmpeg QAYTA KODLASH/chiqish hajmi) alohida, ancha pastroq
standart bilan music_mixer.py'da cheklangan (u yerga qarang) — manba fayl
1080p bo'lsa ham, CHIQISH 720p'ga siqiladi, xotira sarfi baribir past qoladi."""
import os

DEFAULT_MAX_VIDEO_DIMENSION = 1920


def max_video_dimension() -> int:
    try:
        return int(os.getenv("NATURE_MAX_VIDEO_QUALITY_PX", DEFAULT_MAX_VIDEO_DIMENSION))
    except (TypeError, ValueError):
        return DEFAULT_MAX_VIDEO_DIMENSION
