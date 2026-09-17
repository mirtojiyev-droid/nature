"""Top gainers/losers'ga kirmagan, lekin hajm portlashi ko'rsatayotgan (odatiy
hajmdan bir necha barobar ko'proq savdo qilinayotgan) coinlarni topadi —
kripto_bot_mobil.html'dagi breakout_scanner mantiqining porti.

Eslatma: avvalgi (Binance) versiyada bu yerda OI (Open Interest) to'planishi ham
qo'shimcha signal sifatida hisobga olinardi. CoinGecko'ga o'tilgach (Binance
geografik cheklovi tufayli) OI ma'lumoti manbada mavjud emas, shuning uchun endi
faqat hajm portlashi signali ishlatiladi."""
import time

from .analysis import calculate_rsi, rsi_explanation
from .coingecko_api import get_market_chart, request_delay_seconds


def compute_volume_ratio(volumes: list[float]) -> float | None:
    if not volumes or len(volumes) < 6:
        return None
    current = volumes[-1]
    history = volumes[:-1]
    avg = sum(history) / len(history)
    if avg <= 0:
        return None
    return round((current / avg) * 100) / 100


def scan_breakout_candidates(
    candidate_pairs: list[dict],
    volume_multiplier: float,
    top_n: int,
    delay: float | None = None,
) -> list[dict]:
    """`candidate_pairs` — har birida `cg_id` bo'lgan coin dict'lari ro'yxati
    (coingecko_api.get_market_data() natijasi). `delay` berilmasa, CoinGecko'ning
    so'rov chastotasi chegarasiga mos standart qiymat ishlatiladi."""
    if delay is None:
        delay = request_delay_seconds()

    results = []
    for pair in candidate_pairs:
        chart = get_market_chart(pair["cg_id"], days=2)
        time.sleep(delay)
        if not chart:
            continue

        volume_ratio = compute_volume_ratio(chart["volumes"])
        has_volume_spike = volume_ratio is not None and volume_ratio >= volume_multiplier
        if not has_volume_spike:
            continue

        rsi = calculate_rsi(chart["closes"])
        results.append({
            **pair, "rsi": rsi, "rsi_note": rsi_explanation(rsi),
            "volume_ratio": volume_ratio, "has_volume_spike": has_volume_spike,
        })

    results.sort(key=lambda c: c.get("volume_ratio") or 0, reverse=True)
    return results[:top_n]


def breakout_notes(candidate: dict) -> list[str]:
    notes = [candidate["rsi_note"]]
    if candidate["has_volume_spike"]:
        notes.append(f"Hajm portlashi — o'rtachadan {candidate['volume_ratio']:.1f}x ko'p savdo")
    return notes
