import re

# ── TTS Word Substitution Table ───────────────────────────────────────────────
#
# Canadian Punjabi/Hindi speakers naturally code-switch into English for
# certain words — especially in a business/phone context. This table enforces
# that at the audio layer: the LLM can write whatever it wants, the chat
# transcript is untouched, but Soniox TTS speaks the natural English word.
#
# Rules:
#   Non-Latin (Gurmukhi / Devanagari): exact string replace — no word
#     boundaries needed; these scripts have natural spacing.
#   Latin (romanized fallbacks): whole-word, case-insensitive regex so
#     "madad" matches but "amada" or "madads" does not.
#
# To add a word: append a (original, replacement) tuple. That's it.

TTS_WORD_SUBSTITUTIONS: list[tuple[str, str]] = [

    # ── Gurmukhi (Punjabi) ────────────────────────────────────────────────────
    # "madad" — nobody at a Canadian Punjabi counter says this, always "help"
    ("ਮਦਦ",              "help"),
    # "pushti / tasdeek" — the system prompt bans these; this is the hard layer
    ("ਪੁਸ਼ਟੀ",            "confirmed"),
    ("ਤਸਦੀਕ",             "confirmed"),
    # "samsiya" — always "problem" in casual speech
    ("ਸਮੱਸਿਆ",            "problem"),
    # "maafi" — always "sorry" ("mafi karo" sounds stiff/old)
    ("ਮਾਫ਼ੀ",              "sorry"),
    ("ਮਾਫੀ",              "sorry"),
    # "koi gal nahi" — always "no problem"
    ("ਕੋਈ ਗੱਲ ਨਹੀਂ",      "no problem"),
    ("ਕੋਈ ਗੱਲ ਨਹੀ",       "no problem"),
    # "keemat" — always "price" in ordering context
    ("ਕੀਮਤ",              "price"),
    # "rakam" — always "amount" or "total"
    ("ਰਕਮ",               "amount"),
    # "intazaar" — "wait" is universally used
    ("ਇੰਤਜ਼ਾਰ",            "wait"),
    ("ਇੰਤਜਾਰ",             "wait"),

    # ── Devanagari (Hindi) ────────────────────────────────────────────────────
    ("मदद",               "help"),
    ("पुष्टि",             "confirmed"),
    ("तस्दीक",             "confirmed"),
    ("समस्या",             "problem"),
    ("माफ़ी",               "sorry"),
    ("माफी",               "sorry"),
    ("कोई बात नहीं",       "no problem"),
    ("कोई बात नही",        "no problem"),
    ("कीमत",              "price"),
    ("रकम",               "amount"),
    ("इंतज़ार",             "wait"),
    ("इंतजार",             "wait"),

    # ── Romanized fallbacks ───────────────────────────────────────────────────
    # Guards against the LLM slipping out of native script
    ("madad",             "help"),
    ("pushti",            "confirmed"),
    ("tasdeek",           "confirmed"),
    ("maafi",             "sorry"),
    ("mafi",              "sorry"),
    ("koi gal nahi",      "no problem"),
    ("koi baat nahi",     "no problem"),
    ("keemat",            "price"),
    ("rakam",             "amount"),
    ("intazaar",          "wait"),
]

# ── Regex helpers ─────────────────────────────────────────────────────────────

_LATIN_RE = re.compile(r"[a-zA-Z]")

# Pre-compile all Latin patterns once at import time
_LATIN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"(?<!\w)" + re.escape(orig) + r"(?!\w)", re.IGNORECASE),
        repl,
    )
    for orig, repl in TTS_WORD_SUBSTITUTIONS
    if _LATIN_RE.search(orig)
]

_NON_LATIN_PAIRS: list[tuple[str, str]] = [
    (orig, repl)
    for orig, repl in TTS_WORD_SUBSTITUTIONS
    if not _LATIN_RE.search(orig)
]


def apply_tts_substitutions(text: str) -> str:
    """Swap unnatural Punjabi/Hindi words for their English equivalents.

    Applied to TTS-bound text only — chat transcript and LLM context
    are never touched. Cost is negligible (pure string ops, no LLM call).
    """
    # Non-Latin first (longer phrases, no boundary ambiguity)
    for original, replacement in _NON_LATIN_PAIRS:
        if original in text:
            text = text.replace(original, replacement)

    # Latin whole-word (pre-compiled, case-insensitive)
    for pattern, replacement in _LATIN_PATTERNS:
        text = pattern.sub(replacement, text)

    return text
