from shared.hashtags import format_hashtags, slugify_hashtag
from .analysis import signed_num
from .card_builder import format_price

# Kanalning umumiy (eng mashhur/mavzuga mos) hashteglari — har bir post turida ham bor.
CHANNEL_HASHTAGS = ["kripto", "crypto"]


def build_caption_single(coin: dict, is_up: bool, rank: int) -> str:
    emoji = "🟢" if is_up else "🔴"
    category = "O'suvchi" if is_up else "Tushuvchi"
    symbol = coin["symbol"].replace("USDT", "")
    lines = [
        f"{emoji} <b>{symbol}</b>  —  {category} #{rank}",
        f"Narx: {format_price(coin['last_price'])}  ·  24s: {signed_num(coin['price_change_pct'], 2)}%",
        coin["rsi_note"],
        "",
        "<i>Bu moliyaviy maslahat emas — faqat statistik kuzatuv.</i>",
        "",
        format_hashtags([*CHANNEL_HASHTAGS, symbol, slugify_hashtag(category), "trading"]),
    ]
    return "\n".join(lines)


def build_breakout_caption(candidate: dict, rank: int, notes: list[str]) -> str:
    symbol = candidate["symbol"].replace("USDT", "")
    lines = [
        f"🟣 <b>{symbol}</b>  —  Kuzatish ro'yxati #{rank}",
        f"24s: {signed_num(candidate['price_change_pct'], 2)}%",
        *notes,
        "",
        "<i></i>",
        "",
        format_hashtags([*CHANNEL_HASHTAGS, symbol, "breakout", "kuzatuv"]),
    ]
    return "\n".join(lines)
