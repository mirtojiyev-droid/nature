"""
YouTube video kategoriyalari — `main.py --category` argumenti uchun
qulay nomlar. Raqamli ID'ni to'g'ridan-to'g'ri ham berish mumkin
(masalan --category 23), yoki quyidagi nomlardan birini (masalan
--category comedy).
"""

CATEGORY_ID_LABELS = {
    "1": "Film & Animation",
    "2": "Autos & Vehicles",
    "10": "Music",
    "15": "Pets & Animals",
    "17": "Sports",
    "19": "Travel & Events",
    "20": "Gaming",
    "22": "People & Blogs",
    "23": "Comedy",
    "24": "Entertainment",
    "25": "News & Politics",
    "26": "Howto & Style",
    "27": "Education",
    "28": "Science & Technology",
    "29": "Nonprofits & Activism",
}

CATEGORY_NAME_MAP = {
    "film": "1",
    "animation": "1",
    "autos": "2",
    "vehicles": "2",
    "music": "10",
    "pets": "15",
    "animals": "15",
    "sports": "17",
    "travel": "19",
    "events": "19",
    "gaming": "20",
    "games": "20",
    "people": "22",
    "blogs": "22",
    "comedy": "23",
    "kulgi": "23",
    "entertainment": "24",
    "kongilochar": "24",
    "news": "25",
    "politics": "25",
    "howto": "26",
    "style": "26",
    "education": "27",
    "talim": "27",
    "science": "28",
    "technology": "28",
    "tech": "28",
    "nonprofits": "29",
    "activism": "29",
}


def resolve_category(value: str) -> str:
    """'23' yoki 'comedy' kabi qiymatni YouTube kategoriya ID'siga aylantiradi.

    Noma'lum nom berilsa ValueError ko'taradi (xabarida mavjud
    kategoriyalar ro'yxati ko'rsatiladi)."""
    value = value.strip()
    if value.isdigit():
        return value
    key = value.lower()
    if key in CATEGORY_NAME_MAP:
        return CATEGORY_NAME_MAP[key]
    available = ", ".join(f"{cid}={label}" for cid, label in CATEGORY_ID_LABELS.items())
    raise ValueError(
        f"Noma'lum kategoriya: {value!r}. Raqam (masalan 23) yoki nom bering. "
        f"Mavjud kategoriyalar: {available}"
    )


def format_category_list() -> str:
    """--list-categories uchun o'qilishi qulay ro'yxat."""
    lines = ["Mavjud kategoriyalar (--category uchun ID yoki nom ishlatiladi):", ""]
    for cid, label in CATEGORY_ID_LABELS.items():
        names = sorted(name for name, mapped_id in CATEGORY_NAME_MAP.items() if mapped_id == cid)
        lines.append(f"  {cid:>3}  {label:<22} ({', '.join(names)})")
    return "\n".join(lines)
