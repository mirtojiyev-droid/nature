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
qolib ketardi, .env'dagi o'zgartirish e'tiborga olinmasdi."""
import os

DEFAULT_MAX_VIDEO_DIMENSION = 3840


def max_video_dimension() -> int:
    try:
        return int(os.getenv("NATURE_MAX_VIDEO_QUALITY_PX", DEFAULT_MAX_VIDEO_DIMENSION))
    except (TypeError, ValueError):
        return DEFAULT_MAX_VIDEO_DIMENSION
