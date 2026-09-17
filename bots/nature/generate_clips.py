"""
AI orqali bir nechta tabiat videosi yaratib, `localfootage/` papkasiga joylaydigan
QO'LDA ishga tushiriladigan vosita — main.py/run.py'ning avtomatik oqimidan MUSTAQIL.

NEGA ALOHIDA (avtomatik botga bevosita ulanmagan): AI video generatsiyasi soniyasiga
pul turadi (~$0.05-0.15/soniya, provayderga qarab). Agar avtomatik bot HAR safar post
qilganda (masalan har 30 daqiqada, kuniga ~48 marta) jonli AI video yarata boshlasa, bu
oyiga yuzlab-minglab dollar xarajat degani bo'lardi. Buning o'rniga: siz bu skriptni
o'zingiz, xohlagan vaqtingizda (masalan haftasiga bir marta) ishga tushirasiz — u bir
nechta (siz belgilagan sondagi) sifatli klip yaratib, to'g'ridan-to'g'ri
`localfootage/`ga qo'yadi. Shundan keyin ASOSIY BOT bu tayyor fayllarni ENG BIRINCHI
navbatda (bepul, tezkor) ishlatadi — avtomatik ishlashda hech qanday qo'shimcha AI
xarajati YO'Q.

ISHLATILISHI:
    python -m bots.nature.generate_clips --count 5
    python -m bots.nature.generate_clips --count 10 --provider kling --duration 10
    python -m bots.nature.generate_clips --place "Ha Long Bay Vietnam" --facet waterfall

.env'da sozlanishi kerak:
    AI_VIDEO_PROVIDER=runway          # yoki "kling"
    RUNWAY_API_KEY=...                # Runway tanlangan bo'lsa
    KLING_ACCESS_KEY=... / KLING_SECRET_KEY=...   # Kling tanlangan bo'lsa
"""
import argparse
import logging
import os
import random
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # bot_hub/ ildiziga yo'l

from bots.nature.ai_video import AIVideoError, get_provider  # noqa: E402
from bots.nature.ai_video.prompt_builder import build_ai_prompt, build_filename  # noqa: E402
from bots.nature.facets import FACETS  # noqa: E402
from bots.nature.places import PLACES  # noqa: E402
from bots.nature.video_combiner import combine_videos  # noqa: E402
from bots.nature.music_mixer import prepare_video_for_posting  # noqa: E402

LOCALFOOTAGE_DIR = Path(__file__).parent / "localfootage"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("generate_clips")


def _pick_random_place_facet_pairs(count: int) -> list[tuple[dict, dict]]:
    """Takrorlanishni kamaytirish uchun, iloji boricha turli joy+qirra juftliklarini
    tasodifiy tanlaydi (agar `count` PLACES x FACETS ko'paytmasidan katta bo'lsa,
    takrorlanish muqarrar bo'ladi)."""
    all_pairs = [(p, f) for p in PLACES for f in FACETS]
    random.shuffle(all_pairs)
    if count <= len(all_pairs):
        return all_pairs[:count]
    # Yetarli noyob juftlik yo'q - qolganini tasodifiy takrorlab to'ldiramiz.
    extra = [random.choice(all_pairs) for _ in range(count - len(all_pairs))]
    return all_pairs + extra


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="AI orqali tabiat videolarini yaratib, localfootage/ga joylaydi.")
    parser.add_argument("--count", type=int, default=5, help="Nechta klip yaratish (standart: 5)")
    parser.add_argument("--provider", type=str, default=None, help="runway | kling (standart: .env'dagi AI_VIDEO_PROVIDER)")
    parser.add_argument("--duration", type=int, default=8, help="Har bir klip davomiyligi, soniya (standart: 8)")
    parser.add_argument("--vertical", action="store_true", default=True, help="Vertikal (9:16) format (standart)")
    parser.add_argument("--horizontal", dest="vertical", action="store_false", help="Gorizontal (16:9) format")
    parser.add_argument("--place", type=str, default=None, help="Aniq joy nomi (inglizcha, masalan 'Ha Long Bay Vietnam') - berilmasa tasodifiy tanlanadi")
    parser.add_argument("--facet", type=str, default=None, help="Aniq qirra so'zi (masalan 'waterfall', 'sunset') - berilmasa tasodifiy tanlanadi")
    parser.add_argument("--combine", action="store_true", help="Yaratilgan barcha kliplarni BITTA uzunroq videoga birlashtirib, musiqa qo'shib saqlaydi (alohida-alohida saqlash o'rniga)")
    parser.add_argument("--combine-name", type=str, default="ai_combined_premium.mp4", help="--combine ishlatilganda chiqish fayli nomi (localfootage/ ichida)")
    args = parser.parse_args()

    provider_name = args.provider or os.getenv("AI_VIDEO_PROVIDER", "")
    if not provider_name:
        logger.error("Provayder ko'rsatilmagan — --provider bilan yoki .env'dagi AI_VIDEO_PROVIDER orqali belgilang.")
        return 1

    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        logger.error(str(exc))
        return 1
    except AIVideoError as exc:
        logger.error("Provayderni ishga tushirishda xatolik: %s", exc)
        return 1

    LOCALFOOTAGE_DIR.mkdir(parents=True, exist_ok=True)

    if args.place:
        pairs = [({"query": args.place, "name": args.place}, next((f for f in FACETS if f["suffix"] == args.facet), FACETS[0]))] * args.count
    else:
        pairs = _pick_random_place_facet_pairs(args.count)

    logger.info(
        "=" * 60 + "\n"
        " %d ta klip yaratiladi (%s, %ds har biri, %s format)\n"
        " MUHIM: bu pullik xizmat — narxni oldindan providerning\n"
        " narxlash sahifasidan tekshiring (taxminan $0.05-0.15/soniya).\n" + "=" * 60,
        args.count, provider_name, args.duration, "vertikal" if args.vertical else "gorizontal",
    )

    succeeded, failed = 0, 0
    generated_paths = []  # --combine rejimida vaqtinchalik fayllar shu yerga yig'iladi
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        for i, (place, facet) in enumerate(pairs, 1):
            prompt = build_ai_prompt(place["query"], facet["suffix"])
            filename = build_filename(place["query"], facet["label"], provider_name)

            logger.info("[%d/%d] Yaratilmoqda: %s", i, args.count, prompt)
            try:
                result = provider.generate(prompt, duration_sec=args.duration, vertical=args.vertical)
            except AIVideoError as exc:
                logger.error("  Xatolik: %s", exc)
                failed += 1
                continue

            if args.combine:
                clip_path = tmp_path / f"clip_{i:02d}.mp4"
                clip_path.write_bytes(result.video_bytes)
                generated_paths.append(clip_path)
                logger.info("  OK -> vaqtinchalik saqlandi (%.1f MB)", len(result.video_bytes) / 1024 / 1024)
            else:
                dest_path = LOCALFOOTAGE_DIR / filename
                # Bir xil nomdagi fayl allaqachon bo'lsa, ustidan yozib yubormaslik
                # uchun raqam qo'shamiz (masalan ikkinchi marta ishga tushirilganda).
                counter = 2
                while dest_path.exists():
                    dest_path = LOCALFOOTAGE_DIR / f"{filename.removesuffix('.mp4')}_{counter}.mp4"
                    counter += 1
                dest_path.write_bytes(result.video_bytes)
                logger.info("  OK -> %s (%.1f MB)", dest_path.name, len(result.video_bytes) / 1024 / 1024)
            succeeded += 1

        if args.combine and generated_paths:
            logger.info("Barcha %d ta klip birlashtirilmoqda...", len(generated_paths))
            combined_path = tmp_path / "combined_raw.mp4"
            combine_w, combine_h = (1080, 1920) if args.vertical else (1920, 1080)
            if not combine_videos(generated_paths, combined_path, width=combine_w, height=combine_h):
                logger.error("Videolarni birlashtirishda xatolik yuz berdi (ffmpeg o'rnatilganini tekshiring).")
                return 1

            final_name = args.combine_name if args.combine_name.endswith(".mp4") else f"{args.combine_name}.mp4"
            final_path = LOCALFOOTAGE_DIR / final_name
            counter = 2
            while final_path.exists():
                final_path = LOCALFOOTAGE_DIR / f"{final_name.removesuffix('.mp4')}_{counter}.mp4"
                counter += 1

            logger.info("Fon musiqasi qo'shilmoqda va Telegram uchun tayyorlanmoqda...")
            if prepare_video_for_posting(combined_path, final_path):
                logger.info("Tayyor -> %s (%.1f MB)", final_path.name, final_path.stat().st_size / 1024 / 1024)
            else:
                # Musiqa/qayta kodlash muvaffaqiyatsiz bo'lsa ham, birlashtirilgan
                # (musiqasiz) video baribir foydali - uni yo'qotmasdan saqlaymiz.
                shutil.copyfile(combined_path, final_path)
                logger.warning("Musiqa qo'shishda muammo bo'ldi, musiqasiz saqlandi -> %s", final_path.name)

    logger.info("=" * 60 + "\n Tayyor: %d ta muvaffaqiyatli, %d ta xato.\n" + "=" * 60, succeeded, failed)
    return 0 if succeeded > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
