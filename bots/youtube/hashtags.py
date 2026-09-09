"""
Caption uchun hashtag yasovchi modul.

Telegram'da odamlar ko'pincha kanal ichida (yoki hashtag havolasi orqali,
masalan t.me/kanal?q=%23teg) hashtag bo'yicha qidiradi — shuning uchun
har bir postga video sarlavhasi, kanal nomi, kategoriyasi va tilidan
kelib chiqib avtomatik hashtaglar qo'shiladi.
"""
import re

# Hashtag sifatida foyda bermaydigan, juda umumiy so'zlar (ingliz/o'zbek/
# rus va boshqa tillarda tez-tez uchraydigan "shovqin" so'zlar).
_STOPWORDS = {
    "the", "and", "for", "with", "official", "video", "music", "audio",
    "lyric", "lyrics", "new", "song", "ft", "feat", "featuring", "full",
    "hd", "4k", "8k", "mv", "of", "in", "on", "to", "a", "an", "prod",
    "by", "vs", "part", "official video", "музыка", "клип",
}

# Faqat harflar (lotin, kengaytirilgan lotin — o'zbekcha ' bilan, kirill),
# raqamlar va pastki chiziq hashtagda qoladi.
_INVALID_HASHTAG_CHARS_RE = re.compile(r"[^0-9A-Za-z_À-ɏЀ-ӿ]+")
_WORD_RE = re.compile(r"[0-9A-Za-z_À-ɏЀ-ӿ']+")

_LANGUAGE_HASHTAGS = {
    "uz": ["#Uzbek", "#UzbekMusic"],
    "ru": ["#Russian"],
    "en": ["#English"],
    "tr": ["#Turkish"],
    "hi": ["#Hindi"],
}

_GENERIC_HASHTAGS = ["#Trending", "#Viral", "#YouTube", "#MustWatch", "#New"]


def _clean(word: str) -> str:
    return _INVALID_HASHTAG_CHARS_RE.sub("", word).strip("_")


def _title_hashtags(title: str, limit: int = 4) -> list:
    """Sarlavhadagi ma'noli so'zlardan (umumiy so'zlarsiz, qisqa
    so'zlarsiz) hashtaglar yasaydi."""
    tags = []
    seen = set()
    for raw_word in _WORD_RE.findall(title):
        cleaned = _clean(raw_word)
        if len(cleaned) < 3:
            continue
        key = cleaned.lower()
        if key in _STOPWORDS or key in seen:
            continue
        seen.add(key)
        tags.append("#" + cleaned[0].upper() + cleaned[1:])
        if len(tags) >= limit:
            break
    return tags


def build_hashtags(title: str, channel: str = "", category_label: str = None,
                    language: str = None, min_count: int = 5, max_count: int = 8) -> list:
    """Caption uchun hashtag ro'yxatini quradi — kamida `min_count` ta
    (standart 5), postni Telegram ichida qidirilganda topilishi osonroq
    bo'lishi uchun (masalan #Uzbek, #Music, qo'shiq nomiga oid hashtaglar
    va h.k.). Manba: video sarlavhasi, kanal nomi, YouTube kategoriyasi
    (bor bo'lsa) va til (relevance_language yoki aniqlangan bo'lsa)."""
    tags = []
    seen = set()

    def _add(tag):
        if not tag:
            return
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            tags.append(tag)

    if category_label:
        _add("#" + _clean(category_label.replace("&", "")))
    if language:
        for t in _LANGUAGE_HASHTAGS.get(language.lower(), ["#" + _clean(language.upper())]):
            _add(t)
    if channel:
        channel_tag = "#" + _clean(channel)
        if len(channel_tag) > 1:
            _add(channel_tag)
    for t in _title_hashtags(title, limit=4):
        _add(t)
    for t in _GENERIC_HASHTAGS:
        if len(tags) >= min_count:
            break
        _add(t)

    return tags[:max_count]


def format_hashtags(title: str, channel: str = "", category_label: str = None,
                     language: str = None, min_count: int = 5, max_count: int = 8) -> str:
    """build_hashtags natijasini caption'ga qo'shish uchun bitta qatorga
    (probel bilan ajratilgan) birlashtiradi."""
    return " ".join(build_hashtags(title, channel, category_label, language, min_count, max_count))
