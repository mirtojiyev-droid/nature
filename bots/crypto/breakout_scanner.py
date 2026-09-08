"""Top gainers/losers'ga kirmagan, lekin hajm portlashi yoki OI to'planishi kabi
"erta signal" ko'rsatayotgan coinlarni topadi — kripto_bot_mobil.html'dagi
breakout_scanner mantiqining porti."""
import time

from .analysis import calculate_rsi, rsi_explanation, signed_num
from .binance_api import get_klines_full, get_open_interest_change


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
    oi_accum_threshold: float,
    price_quiet_threshold: float,
    top_n: int,
    delay: float = 0.15,
) -> list[dict]:
    results = []
    for pair in candidate_pairs:
        symbol = pair["symbol"]
        klines = get_klines_full(symbol, "1h", 25)
        closes = klines["closes"] if klines else None
        volumes = klines["volumes"] if klines else None
        time.sleep(delay)

        oi_change_pct = get_open_interest_change(symbol)
        time.sleep(delay)

        volume_ratio = compute_volume_ratio(volumes) if volumes else None
        has_volume_spike = volume_ratio is not None and volume_ratio >= volume_multiplier
        has_oi_accum = (
            oi_change_pct is not None
            and oi_change_pct >= oi_accum_threshold
            and abs(pair["price_change_pct"]) <= price_quiet_threshold
        )

        score = int(has_volume_spike) + int(has_oi_accum)
        if score == 0:
            continue

        rsi = calculate_rsi(closes) if closes else None
        results.append({
            **pair, "rsi": rsi, "rsi_note": rsi_explanation(rsi),
            "volume_ratio": volume_ratio, "has_volume_spike": has_volume_spike,
            "oi_change_pct": oi_change_pct, "has_oi_accum": has_oi_accum, "score": score,
        })

    results.sort(key=lambda c: (c["score"], c.get("volume_ratio") or 0), reverse=True)
    return results[:top_n]


def breakout_notes(candidate: dict) -> list[str]:
    notes = [candidate["rsi_note"]]
    if candidate["has_volume_spike"]:
        notes.append(f"Hajm portlashi — o'rtachadan {candidate['volume_ratio']:.1f}x ko'p savdo")
    if candidate["has_oi_accum"]:
        notes.append(
            f"OI to'planmoqda: {signed_num(candidate['oi_change_pct'], 1)}%, "
            f"narx {signed_num(candidate['price_change_pct'], 1)}% (sokin)"
        )
    return notes
