"""
AI video generatsiyasi uchun kompyuterda ishlaydigan boshqaruv paneli — telefon
brauzeridan (bir xil Wi-Fi tarmog'ida) boshqariladi.

MUHIM (xavfsizlik): Runway/Kling kabi "maxfiy" (secret) API kalitlari FAQAT shu
serverda (kompyuteringizda) saqlanadi va ishlatiladi — brauzerga, localStorage'ga
yoki boshqa hech qanday tashqi joyga HECH QACHON yuborilmaydi. Shuning uchun bu
funksiya (avvalgi crypto/youtube HTML asboblaridan farqli) ATAYLAB alohida,
server-based qilib qurilgan.

Ishga tushirish: `python -m bots.nature.dashboard.server`, so'ng terminaldagi
manzilni telefon brauzeringizda oching.
"""
import logging
import os
import socket
import sys
from pathlib import Path

from dotenv import load_dotenv, set_key
from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # bot_hub/ ildiziga yo'l

from bots.nature.ai_video import AIVideoError, get_provider  # noqa: E402
from bots.nature.ai_video.prompt_builder import build_ai_prompt, build_filename  # noqa: E402
from bots.nature.facets import FACETS  # noqa: E402
from bots.nature.places import PLACES  # noqa: E402
from bots.nature.music_mixer import prepare_video_for_posting  # noqa: E402
from bots.nature.video_combiner import combine_videos  # noqa: E402

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
LOCALFOOTAGE_DIR = Path(__file__).resolve().parents[1] / "localfootage"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(Path(__file__).parent / "dashboard.log", encoding="utf-8")],
)
log = logging.getLogger("ai_video_dashboard")

app = Flask(__name__)


def _ensure_env_file():
    if not ENV_PATH.exists():
        ENV_PATH.write_text("", encoding="utf-8")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/settings")
def api_get_settings():
    load_dotenv(ENV_PATH, override=True)
    return jsonify({
        "provider": os.getenv("AI_VIDEO_PROVIDER", ""),
        "runway_key_set": bool(os.getenv("RUNWAY_API_KEY")),
        "kling_key_set": bool(os.getenv("KLING_ACCESS_KEY") and os.getenv("KLING_SECRET_KEY")),
    })


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    """Kalitlarni .env fayliga yozadi — bu fayl FAQAT shu kompyuterda qoladi,
    hech qachon brauzerga qaytarilmaydi (faqat "sozlanganmi/yo'qmi" holati
    qaytariladi, hech qachon qiymatning o'zi emas)."""
    _ensure_env_file()
    data = request.get_json(force=True, silent=True) or {}

    if data.get("provider"):
        set_key(str(ENV_PATH), "AI_VIDEO_PROVIDER", data["provider"])
    if data.get("runway_key"):
        set_key(str(ENV_PATH), "RUNWAY_API_KEY", data["runway_key"])
    if data.get("kling_access_key"):
        set_key(str(ENV_PATH), "KLING_ACCESS_KEY", data["kling_access_key"])
    if data.get("kling_secret_key"):
        set_key(str(ENV_PATH), "KLING_SECRET_KEY", data["kling_secret_key"])

    return jsonify({"ok": True})


@app.route("/api/places")
def api_places():
    return jsonify({
        "places": [{"name": p["name"], "query": p["query"]} for p in PLACES],
        "facets": [{"label": f["label"], "suffix": f["suffix"]} for f in FACETS],
    })


@app.route("/api/localfootage")
def api_localfootage():
    LOCALFOOTAGE_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for p in sorted(LOCALFOOTAGE_DIR.iterdir()):
        if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm", ".avi"):
            files.append({"name": p.name, "size_mb": round(p.stat().st_size / 1024 / 1024, 1)})
    return jsonify({"files": files})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    load_dotenv(ENV_PATH, override=True)
    data = request.get_json(force=True, silent=True) or {}

    provider_name = data.get("provider") or os.getenv("AI_VIDEO_PROVIDER", "")
    prompt_override = (data.get("custom_prompt") or "").strip()
    place_query = data.get("place_query", "")
    facet_suffix = data.get("facet_suffix", "")
    facet_label = data.get("facet_label", "clip")
    duration = int(data.get("duration", 8))
    vertical = bool(data.get("vertical", True))

    try:
        provider = get_provider(provider_name)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    prompt = prompt_override or build_ai_prompt(place_query, facet_suffix)
    log.info("Generatsiya boshlandi (%s): %s", provider_name, prompt)

    try:
        result = provider.generate(prompt, duration_sec=duration, vertical=vertical)
    except AIVideoError as exc:
        log.error("Generatsiya xatoligi: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 502

    LOCALFOOTAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = build_filename(place_query or "custom", facet_label, provider_name)
    dest_path = LOCALFOOTAGE_DIR / filename
    counter = 2
    while dest_path.exists():
        dest_path = LOCALFOOTAGE_DIR / f"{filename.removesuffix('.mp4')}_{counter}.mp4"
        counter += 1
    dest_path.write_bytes(result.video_bytes)

    log.info("Saqlandi: %s (%.1f MB)", dest_path.name, dest_path.stat().st_size / 1024 / 1024)
    return jsonify({
        "ok": True, "filename": dest_path.name,
        "size_mb": round(dest_path.stat().st_size / 1024 / 1024, 1),
        "prompt": prompt,
    })


@app.route("/api/combine", methods=["POST"])
def api_combine():
    data = request.get_json(force=True, silent=True) or {}
    filenames = data.get("filenames") or []
    output_name = (data.get("output_name") or "ai_combined_premium.mp4").strip()
    vertical = bool(data.get("vertical", True))

    if len(filenames) < 2:
        return jsonify({"ok": False, "error": "Kamida 2 ta fayl tanlang."}), 400

    clip_paths = [LOCALFOOTAGE_DIR / name for name in filenames]
    missing = [p.name for p in clip_paths if not p.exists()]
    if missing:
        return jsonify({"ok": False, "error": f"Fayl(lar) topilmadi: {', '.join(missing)}"}), 400

    import tempfile
    width, height = (1080, 1920) if vertical else (1920, 1080)
    with tempfile.TemporaryDirectory() as tmp_dir:
        combined_raw = Path(tmp_dir) / "combined_raw.mp4"
        if not combine_videos(clip_paths, combined_raw, width=width, height=height):
            return jsonify({"ok": False, "error": "Birlashtirishda xatolik (ffmpeg o'rnatilganini tekshiring)."}), 500

        if not output_name.endswith(".mp4"):
            output_name += ".mp4"
        final_path = LOCALFOOTAGE_DIR / output_name
        counter = 2
        while final_path.exists():
            final_path = LOCALFOOTAGE_DIR / f"{output_name.removesuffix('.mp4')}_{counter}.mp4"
            counter += 1

        had_music = prepare_video_for_posting(combined_raw, final_path)
        if not had_music:
            import shutil
            shutil.copyfile(combined_raw, final_path)

    log.info("Birlashtirildi: %s (%.1f MB)", final_path.name, final_path.stat().st_size / 1024 / 1024)
    return jsonify({
        "ok": True, "filename": final_path.name,
        "size_mb": round(final_path.stat().st_size / 1024 / 1024, 1),
    })


@app.route("/api/delete", methods=["POST"])
def api_delete():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("filename", "")
    path = LOCALFOOTAGE_DIR / name
    # Yo'l-almashtirish (path traversal) hujumidan himoya - fayl albatta
    # localfootage/ papkasining o'zida bo'lishi kerak.
    try:
        path.resolve().relative_to(LOCALFOOTAGE_DIR.resolve())
    except ValueError:
        return jsonify({"ok": False, "error": "Noto'g'ri fayl yo'li."}), 400
    if path.exists():
        path.unlink()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "Fayl topilmadi."}), 404


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


if __name__ == "__main__":
    load_dotenv(ENV_PATH, override=True)
    port = 5050
    ip = _local_ip()
    print("=" * 60)
    print(" AI Video boshqaruv paneli ishga tushdi")
    print("=" * 60)
    print(f" Shu kompyuterda:  http://127.0.0.1:{port}")
    print(f" Telefondan (bir xil Wi-Fi'da):  http://{ip}:{port}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, threaded=True)
