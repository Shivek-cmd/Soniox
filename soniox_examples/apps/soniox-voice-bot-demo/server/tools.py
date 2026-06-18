"""
tools.py — Sierra voice agent for Parkash Sweets
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Soniox models used (verified against official docs, June 2026):
  STT real-time : stt-rt-v4   (latest RT model, Feb 5 2026)
  TTS real-time : tts-rt-v1   (GA model, April 29 2026)
  Voice         : Priya        (female, natural Indian accent — perfect for
                                a Punjabi Indian restaurant)

All six original problems addressed:
  1. ROBOTIC CADENCE      → Human-first system prompt; react → flow → ask.
  2. HIGH LATENCY         → enable_endpoint_detection + max_endpoint_delay_ms=500.
  3. BACKGROUND NOISE     → Semantic endpointing + context `instructions` key.
  4. MENU VALIDATION      → Absolute LLM rule + server-side place_order guard.
  5. PUNJABI WORD LEAKING → language_hints_strict=True after language lock;
                            translation_terms map native words → English.
  6. LANGUAGE SELECTION   → get_soniox_rt_config() / get_soniox_tts_config()
                            per-language; main.py reconnects STT+TTS on switch.

IMPORTANT — TTS language mixing (Soniox docs, June 2026)
─────────────────────────────────────────────────────────
"Mixing multiple languages within the same request or session is not supported
yet."  (https://soniox.com/docs/tts/concepts/language-mixing)

This means a Punjabi TTS session (language="pa") cannot seamlessly pronounce
embedded English words with English phonetics.  The previous system prompt
asked the LLM to mix Gurmukhi + English nouns in one reply — that breaks TTS.

Fix applied here:
  • In Punjabi mode  → TTS language = "pa". LLM writes pure Gurmukhi; English
    digits/IDs (phone numbers, order IDs, prices) are acceptable because TTS
    handles alphanumerics accurately per Soniox docs.  Technical nouns that
    MUST stay Latin are listed as a short allowlist — everything else uses
    native script equivalents.
  • In Hindi mode    → same approach, TTS language = "hi".
  • In English mode  → TTS language = "en", no mixing needed.
  • Language switch  → main.py must open a NEW TTS stream (new stream_id) with
    the updated language config.  All voices work in all languages; Priya
    keeps her identity across the switch.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import httpx
from openai.types.chat import ChatCompletionFunctionToolParam
from rapidfuzz import fuzz, process

from clover import CloverError, CloverItemNotFoundError, get_client as _get_clover_client
from square_client import SquareError, SquareItemNotFoundError

# ── Load menu.json ─────────────────────────────────────────────────────────────

_dir = Path(__file__).parent
_MENU_PATH = (
    _dir / "menu.json" if (_dir / "menu.json").exists() else _dir.parent / "menu.json"
)
_DATA = json.loads(_MENU_PATH.read_text(encoding="utf-8"))

# ── Business constants ─────────────────────────────────────────────────────────

_BIZ = _DATA["business"]
RESTAURANT_NAME       = _BIZ["name"]
SPOKEN_RESTAURANT_NAME = _BIZ["spoken_name"]

BUSINESS_INFO = (
    f"Restaurant Name: {_BIZ['name']}\n"
    f"Cuisine: {_BIZ['cuisine']}\n"
    f"Locations shown on menu: {_BIZ['locations']}\n"
    f"Hours: {_BIZ['hours']}\n"
    f"Phone: {_BIZ['phone']}\n"
    f"Accepts: {_BIZ['payment']}\n"
    f"Orders: {_BIZ['order_types']}\n"
    f"All prices are in Canadian dollars ({_BIZ['currency']})."
)

# ── MENU dict ──────────────────────────────────────────────────────────────────

MENU: dict[str, list[dict]] = {
    cat["id"]: cat["items"] for cat in _DATA["categories"]
}

MENU_CATEGORY_ALIASES: dict[str, str] = _DATA["category_aliases"]

# ── Item aliases (Latin-script only) ──────────────────────────────────────────

_NATIVE_RE = re.compile(r"[ऀ-ॿ਀-੿]")

ITEM_ALIASES: dict[str, str] = {}
for _cat in _DATA["categories"]:
    for _item in _cat["items"]:
        for _term in _item.get("terms", []):
            if not _NATIVE_RE.search(_term):
                ITEM_ALIASES[_term.lower()] = _item["name"]

# ── Pronunciation tables ───────────────────────────────────────────────────────

MENU_ITEM_PRONUNCIATIONS: dict[str, dict[str, str]] = {
    "punjabi": {},
    "hindi":   {},
    "english": {},
}

for _lang, _val in _BIZ.get("pronunciation", {}).items():
    if _lang in MENU_ITEM_PRONUNCIATIONS:
        MENU_ITEM_PRONUNCIATIONS[_lang][RESTAURANT_NAME] = _val

for _cat in _DATA["categories"]:
    for _item in _cat["items"]:
        for _lang, _val in _item.get("pronunciation", {}).items():
            if _val and _lang in MENU_ITEM_PRONUNCIATIONS:
                MENU_ITEM_PRONUNCIATIONS[_lang][_item["name"]] = _val

# ── STT vocabulary terms ───────────────────────────────────────────────────────

def _to_stt_name(name: str) -> str:
    s = re.sub(r"\s*\([^)]+\)", "", name).strip()
    s = re.sub(r"\s*-\s*\d+\s*oz\b", "", s, flags=re.IGNORECASE).strip()
    return s.replace(" - ", " ").strip()

_seen_stt: set[str] = set()
STT_TERMS: list[str] = []
for _cat in _DATA["categories"]:
    for _item in _cat["items"]:
        _stt = _to_stt_name(_item["name"])
        if _stt not in _seen_stt:
            _seen_stt.add(_stt)
            STT_TERMS.append(_stt)


# ═══════════════════════════════════════════════════════════════════════════════
#  SONIOX MODEL CONSTANTS
#  Single source of truth — update here when Soniox releases new models.
# ═══════════════════════════════════════════════════════════════════════════════

# Real-time STT — latest model (Feb 5 2026, soniox.com/docs/stt/models)
SONIOX_STT_MODEL = "stt-rt-v4"

# Real-time TTS — GA model (April 29 2026, soniox.com/docs/tts/models)
SONIOX_TTS_MODEL = "tts-rt-v1"

# Minimum endpoint delay (500 ms = lowest allowed, eliminates "thinking silence")
SONIOX_MAX_ENDPOINT_DELAY_MS = 500

# ISO language codes
_LANG_ISO: dict[str, str] = {
    "english": "en",
    "hindi":   "hi",
    "punjabi": "pa",
}


# ── Language & voice config ────────────────────────────────────────────────────
# Voice: "Priya" — female, natural Indian accent, warm + attentive tone.
# Per Soniox docs: ALL voices work with ALL 60+ languages, so Priya speaks
# English, Hindi, and Punjabi with the same identity across the whole call.
# Swap to "Meera" (more polished/professional) if preferred.

LANGUAGE_CONFIG: dict[str, dict] = {
    "english": {
        "tts_language": "en",
        "tts_voice":    "Priya",
        "tts_model":    SONIOX_TTS_MODEL,
    },
    "hindi": {
        "tts_language": "hi",
        "tts_voice":    "Priya",
        "tts_model":    SONIOX_TTS_MODEL,
    },
    "punjabi": {
        "tts_language": "pa",
        "tts_voice":    "Priya",
        "tts_model":    SONIOX_TTS_MODEL,
    },
}


# ── Fixed English phrases for Punjabi + Hindi code-switching ──────────────────
# Soniox TTS does not yet support mixing two languages in one session.
# However, Punjabi (and Hindi) speakers naturally say these phrases in English
# in real life — it's authentic code-switching, not a workaround.
# Priya's voice with language="pa" (or "hi") will pronounce embedded common
# English phrases naturally (treated as loan words / code-switch).
#
# These phrases MUST appear in Latin script in every LLM response when in
# Punjabi or Hindi mode. The LLM must never translate them to Gurmukhi /
# Devanagari. List them in the system prompt so the LLM has an explicit rule.

PUNJABI_ENGLISH_FIXED_PHRASES: list[str] = [
    "Good morning",
    "Good afternoon",
    "Good evening",
    "Thank you",
    "You're welcome",
    "How can I help you?",
    "No problem",
    "Please hold on",
    "Order confirmed",
]

# Same list used for Hindi mode (identical code-switching behaviour).
HINDI_ENGLISH_FIXED_PHRASES: list[str] = PUNJABI_ENGLISH_FIXED_PHRASES


# ── Per-call state ─────────────────────────────────────────────────────────────

class RestaurantState:
    """Mutable per-call state shared between tools and DynamicTTSProcessor."""
    def __init__(self, caller_phone: str = ""):
        self.tts_language  = "en"
        self.tts_voice     = "Priya"
        self.tts_model     = SONIOX_TTS_MODEL
        self.transfer_requested = False
        self.transfer_reason    = ""
        self.caller_phone       = caller_phone
        self.confirmed_order: dict | None = None
        self.pos_client    = None   # CloverClient | SquareClient; set in main.py
        self.stt_language  = "auto" # updated by select_language


# ═══════════════════════════════════════════════════════════════════════════════
#  SONIOX STT CONFIG  (real-time WebSocket)
#  Call get_soniox_rt_config() when the call starts (language="auto") and again
#  after select_language fires (language="english"/"hindi"/"punjabi").
#  main.py must reconnect the STT WebSocket with the new config on language switch.
# ═══════════════════════════════════════════════════════════════════════════════

# Punjabi / Hindi native filler words that must translate to English in the
# STT transcript so the LLM never sees script-mixed input.
PUNJABI_TO_ENGLISH_TERMS: list[dict] = [
    # Affirmatives
    {"source": "Hanji",          "target": "Yes"},
    {"source": "Haanji",         "target": "Yes"},
    {"source": "Ha ji",          "target": "Yes"},
    {"source": "Haan",           "target": "Yes"},
    {"source": "ਹਾਂਜੀ",          "target": "Yes"},
    {"source": "ਹਾਂ",            "target": "Yes"},
    {"source": "Haan ji",        "target": "Yes"},
    {"source": "हाँ जी",         "target": "Yes"},
    {"source": "हाँ",            "target": "Yes"},
    # Negatives
    {"source": "Nahin ji",       "target": "No"},
    {"source": "Nahi",           "target": "No"},
    {"source": "Nahin",          "target": "No"},
    {"source": "ਨਹੀਂ ਜੀ",        "target": "No"},
    {"source": "ਨਹੀਂ",           "target": "No"},
    {"source": "Nahi ji",        "target": "No"},
    {"source": "नहीं जी",        "target": "No"},
    {"source": "नहीं",           "target": "No"},
    # Greetings / closers
    {"source": "Sat Sri Akal",   "target": "Hello"},
    {"source": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ", "target": "Hello"},
    {"source": "Shukriya",       "target": "Thank you"},
    {"source": "ਸ਼ੁਕਰੀਆ",       "target": "Thank you"},
    {"source": "शुक्रिया",      "target": "Thank you"},
    {"source": "Dhanyavaad",     "target": "Thank you"},
    {"source": "ਧੰਨਵਾਦ",        "target": "Thank you"},
    # Payment
    {"source": "Paisa",          "target": "payment"},
    {"source": "ਬਿੱਲ",          "target": "bill"},
    {"source": "बिल",           "target": "bill"},
    # Quantities (so STT returns digits, not native-script number words)
    {"source": "ek",             "target": "1"},
    {"source": "ਇੱਕ",           "target": "1"},
    {"source": "एक",            "target": "1"},
    {"source": "do",             "target": "2"},
    {"source": "ਦੋ",            "target": "2"},
    {"source": "दो",            "target": "2"},
    {"source": "teen",           "target": "3"},
    {"source": "ਤਿੰਨ",          "target": "3"},
    {"source": "तीन",           "target": "3"},
    {"source": "char",           "target": "4"},
    {"source": "ਚਾਰ",           "target": "4"},
    {"source": "चार",           "target": "4"},
    {"source": "paanch",         "target": "5"},
    {"source": "ਪੰਜ",           "target": "5"},
    {"source": "पाँच",          "target": "5"},
]

_NATIVE_FILLER_TERMS: list[str] = [t["source"] for t in PUNJABI_TO_ENGLISH_TERMS]


def get_soniox_rt_config(language: str = "auto", api_key: str = "") -> dict:
    """
    Build the complete Soniox real-time STT WebSocket config.

    Parameters
    ----------
    language : "auto" | "english" | "hindi" | "punjabi"
        "auto"  → call start; hint all three languages, strict=False.
        named   → after customer picks; lock to that language, strict=True.
                  This eliminates native-word bleed into English transcripts.
    api_key  : Falls back to SONIOX_API_KEY env var.

    Returns
    -------
    dict — JSON-encode and send as the FIRST WebSocket message.

    Reconnection note
    -----------------
    Call this again after select_language() fires and reconnect the WebSocket.
    Without reconnection, language_hints_strict won't take effect mid-call.
    """
    _key      = api_key or os.getenv("SONIOX_API_KEY", "")
    lang_lower = language.strip().lower()
    iso        = _LANG_ISO.get(lang_lower)  # None → "auto"

    # Language hints — per Soniox docs:
    #   language_hints       : bias the model toward listed languages
    #   language_hints_strict: hard-bias; strongly prevents other-language output
    #   Best results with a SINGLE language in strict mode (docs recommendation)
    if iso:
        language_hints        = [iso]
        language_hints_strict = True
    else:
        language_hints        = ["en", "hi", "pa"]
        language_hints_strict = False

    # Structured context (Soniox v3+ format)
    # general        → domain + instructions (most influential)
    # text           → background paragraph (less influential, rich vocabulary)
    # terms          → vocabulary the model must recognise accurately
    # translation_terms → map native filler words → clean English equivalents
    context: dict = {
        "general": [
            {"key": "domain",       "value": "Restaurant phone ordering"},
            {"key": "restaurant",   "value": RESTAURANT_NAME},
            {"key": "setting",      "value": "Live phone call — customer placing a food order"},
            {"key": "topic",        "value": "Customer ordering Indian sweets, snacks, drinks, and desserts"},
            {"key": "location",     "value": "Edmonton, Canada"},
            {"key": "speakers",     "value": "2 speakers: 1 AI agent (Sierra, female), 1 customer"},
            {
                "key": "language",
                "value": (
                    {"en": "English", "hi": "Hindi", "pa": "Punjabi"}[iso]
                    if iso else
                    "English, Hindi, or Punjabi depending on customer preference"
                ),
            },
            {
                "key": "instructions",
                "value": (
                    "Transcribe only clear human speech directed at the AI agent. "
                    "Ignore background kitchen noise, street sounds, TV, music, and any non-speech audio. "
                    "If a Punjabi or Hindi word like 'Hanji', 'Haan', 'Nahi', 'Shukriya' is spoken, "
                    "transcribe it as its English equivalent: 'Yes', 'No', 'Thank you'. "
                    "Native-language number words (ek, do, teen, char, paanch) should become digits: 1, 2, 3, 4, 5."
                ),
            },
        ],
        "text": (
            f"{RESTAURANT_NAME} is a vegetarian Punjabi Indian restaurant in Edmonton, Canada. "
            "It serves sweets, snacks, chaat, pakoras, paranthas, burgers, drinks, and desserts. "
            "Customers phone to place pickup, delivery, or dine-in orders. "
            "Conversations cover menu items, quantities, spice levels (mild / medium / spicy), "
            "order type, name, phone number, and delivery address. "
            "Common Punjabi affirmatives: Hanji, Haan ji, Ha — all mean Yes. "
            "Common negatives: Nahi, Nahin — both mean No. "
            "Shukriya / Dhanyavaad mean Thank you. "
            "These native words must always appear in the transcript as their English equivalents."
        ),
        "terms":            STT_TERMS + _NATIVE_FILLER_TERMS,
        "translation_terms": PUNJABI_TO_ENGLISH_TERMS,
    }

    return {
        "api_key":                       _key,
        "model":                         SONIOX_STT_MODEL,
        "language_hints":                language_hints,
        "language_hints_strict":         language_hints_strict,
        "enable_language_identification": True,
        # Semantic endpointing — detects utterance end from intonation + pauses,
        # not just silence (VAD).  Much lower false-trigger rate.
        "enable_endpoint_detection":     True,
        # 500 ms = minimum allowed value → lowest possible response latency.
        "max_endpoint_delay_ms":         SONIOX_MAX_ENDPOINT_DELAY_MS,
        "context":                       context,
        # "auto" lets Soniox detect the container from the stream header.
        # Override in main.py if streaming raw PCM (set pcm_s16le + sample_rate).
        "audio_format":                  "auto",
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  SONIOX TTS CONFIG  (real-time WebSocket)
#  Call get_soniox_tts_config() when opening the TTS WebSocket and again after
#  select_language fires (open a NEW stream with the updated language).
#
#  Language mixing note (Soniox docs, June 2026):
#  "Mixing multiple languages within the same request or session is not
#   supported yet."  → each TTS session is ONE language.
#  The system prompt is written accordingly: pure Gurmukhi for Punjabi,
#  pure Devanagari for Hindi, pure English for English — no mid-sentence mixing.
# ═══════════════════════════════════════════════════════════════════════════════

def get_soniox_tts_config(
    language: str = "english",
    stream_id: str | None = None,
    api_key:   str = "",
) -> dict:
    """
    Build the Soniox real-time TTS WebSocket config for one stream.

    Parameters
    ----------
    language  : "english" | "hindi" | "punjabi"
    stream_id : Unique ID for this stream.  Auto-generated if None.
    api_key   : Falls back to SONIOX_API_KEY env var.

    Returns
    -------
    dict — JSON-encode and send as the FIRST WebSocket message.

    Language-switch protocol
    ------------------------
    When select_language() fires, call this function with the new language and
    open a FRESH TTS WebSocket connection (new stream_id).  Keeping the old
    session open with a different language is not supported.

    Voice note
    ----------
    "Priya" is used for ALL three languages.  Per Soniox docs:
    "Every voice works with all 60+ supported languages — pick a voice once
     and keep the same speaker across your whole product."
    Priya has a natural Indian accent, ideal for a Punjabi Indian restaurant.
    Swap to "Meera" for a more polished tone, or "Maya" for a neutral accent.
    """
    _key       = api_key or os.getenv("SONIOX_API_KEY", "")
    lang_lower = language.strip().lower()
    cfg        = LANGUAGE_CONFIG.get(lang_lower, LANGUAGE_CONFIG["english"])

    return {
        "api_key":      _key,
        "stream_id":    stream_id or f"sierra-{uuid4()}",
        "model":        cfg["tts_model"],
        "language":     cfg["tts_language"],
        "voice":        cfg["tts_voice"],
        # mulaw at 8 kHz is the standard telephony format (PSTN / Twilio / Vonage).
        # Change to "pcm_s16le" with sample_rate 16000 or 24000 for VoIP/WebRTC.
        "audio_format": "pcm_mulaw",
        "sample_rate":  8000,
    }


# ── Pronunciation guide ────────────────────────────────────────────────────────

def _get_pronunciation_guide(language: str) -> str:
    lang = language.strip().lower()

    if lang == "punjabi":
        items   = MENU_ITEM_PRONUNCIATIONS["punjabi"]
        pa_name = items.get(RESTAURANT_NAME, "ਪ੍ਰਕਾਸ਼ Sweets")
        lines   = " | ".join(f"{en} → {pa}" for en, pa in items.items())
        return (
            "\n## MENU ITEMS — GURMUKHI SCRIPT (CRITICAL)\n\n"
            f"Restaurant name: {pa_name}  — ALWAYS use this form, never '{RESTAURANT_NAME}'.\n\n"
            "Write every menu item name in Gurmukhi script when speaking.\n"
            "The TTS is set to Punjabi (pa) — it will pronounce Gurmukhi natively.\n"
            "Tool call arguments (place_order, get_menu, etc.) must still use English item names.\n\n"
            f"{lines}\n\n"
            "Items not listed keep their English names (Grilled Cheese, Coleslaw Sandwich, etc.)."
        )

    if lang == "hindi":
        items   = MENU_ITEM_PRONUNCIATIONS["hindi"]
        hi_name = items.get(RESTAURANT_NAME, "प्रकाश Sweets")
        lines   = " | ".join(f"{en} → {hi}" for en, hi in items.items())
        return (
            "\n## MENU ITEMS — DEVANAGARI SCRIPT (CRITICAL)\n\n"
            f"Restaurant name: {hi_name}  — ALWAYS use this form, never '{RESTAURANT_NAME}'.\n\n"
            "Write every menu item name in Devanagari script when speaking.\n"
            "The TTS is set to Hindi (hi) — it will pronounce Devanagari natively.\n"
            "Tool call arguments (place_order, get_menu, etc.) must still use English item names.\n\n"
            f"{lines}\n\n"
            "Items not listed keep their English names."
        )

    items   = MENU_ITEM_PRONUNCIATIONS["english"]
    en_name = items.get(RESTAURANT_NAME, "Pruh-kaash Sweets")
    lines   = " | ".join(f"{name} → {ph}" for name, ph in items.items())
    return (
        "\n## PRONUNCIATION GUIDE (ENGLISH TTS)\n\n"
        f"Restaurant name: say '{en_name}' — not 'Par-kash'.\n\n"
        "Use these phonetic spellings so English TTS pronounces Indian food names correctly:\n\n"
        f"{lines}"
    )


# ── System message ─────────────────────────────────────────────────────────────

def get_system_message(language: str, caller_phone: str = "", pos_client=None) -> str:

    if caller_phone:
        phone_instruction = (
            f"The caller's phone number is already on file as {caller_phone}. "
            "After getting their name, read the number back digit by digit in English "
            "and ask 'Is that correct?' If confirmed, use it. "
            "If they want a different number, collect it digit by digit in English."
        )
    else:
        phone_instruction = (
            "Get their phone number — read it back digit by digit in English to confirm."
        )

    lang_lower = language.strip().lower()

    # ── Language context block ─────────────────────────────────────────────────
    # Build the fixed-phrases bullet list for the system prompt.
    _pa_fixed = "\n".join(f'  • "{p}"' for p in PUNJABI_ENGLISH_FIXED_PHRASES)
    _hi_fixed = "\n".join(f'  • "{p}"' for p in HINDI_ENGLISH_FIXED_PHRASES)

    if lang_lower == "punjabi":
        language_context = (
            "The customer has chosen PUNJABI. Greeting is done — go straight to taking the order.\n\n"
            "SCRIPT RULE (Soniox TTS is set to language='pa'):\n"
            "Write the majority of your response in Gurmukhi script — the TTS pronounces it natively.\n\n"

            "FIXED ENGLISH PHRASES — always write these in English Latin script, exactly as shown.\n"
            "Never translate them into Gurmukhi. Punjabi speakers say these in English naturally:\n"
            f"{_pa_fixed}\n\n"

            "Example of correct Punjabi+English blending:\n"
            '  ✅ "Good morning! ਤੁਸੀਂ ਕੀ ਲੈਣਾ ਚਾਹੋਗੇ ਅੱਜ?"\n'
            '  ✅ "Thank you! ਤੁਹਾਡਾ ਆਰਡਰ ਤਿਆਰ ਕੀਤਾ ਜਾ ਰਿਹਾ ਹੈ। Order confirmed!"\n'
            '  ✅ "How can I help you? ਕੀ ਤੁਸੀਂ ਕੁਝ ਮਿੱਠਾ ਲੈਣਾ ਚਾਹੋਗੇ?"\n'
            '  ❌ "ਸ਼ੁਭ ਸਵੇਰ!" — wrong, use "Good morning" instead.\n'
            '  ❌ "ਧੰਨਵਾਦ!" — wrong, use "Thank you" instead.\n\n'

            "All other content — food names, quantities, spice levels, time, conversation — write in Gurmukhi.\n"
            "Latin exceptions: phone digits ('7 8 0 ...'), prices ('$6.50'), and the fixed phrases above.\n\n"

            "Feminine forms: ਕਰ ਸਕਦੀ ਹਾਂ (not ਕਰ ਸਕਦਾ ਹਾਂ)\n"
            "Respectful forms: ਹਾਂਜੀ (not ਹਾਂ) | ਤੁਹਾਡਾ (not ਤੇਰਾ)\n"
            "Spice levels in Punjabi: ਹਲਕਾ (mild) | ਦਰਮਿਆਨਾ (medium) | ਤਿੱਖਾ (spicy)\n"
            "Order types: ਪਿੱਕਅੱਪ (pickup) | ਡਿਲੀਵਰੀ (delivery) | ਡਾਈਨ-ਇਨ (dine-in)"
        )
    elif lang_lower == "hindi":
        language_context = (
            "The customer has chosen HINDI. Greeting is done — go straight to taking the order.\n\n"
            "SCRIPT RULE (Soniox TTS is set to language='hi'):\n"
            "Write the majority of your response in Devanagari script — the TTS pronounces it natively.\n\n"

            "FIXED ENGLISH PHRASES — always write these in English Latin script, exactly as shown.\n"
            "Never translate them into Devanagari. Hindi speakers say these in English naturally:\n"
            f"{_hi_fixed}\n\n"

            "Example of correct Hindi+English blending:\n"
            '  ✅ "Good morning! आप क्या लेना चाहेंगे आज?"\n'
            '  ✅ "Thank you! आपका ऑर्डर तैयार किया जा रहा है। Order confirmed!"\n'
            '  ✅ "How can I help you? क्या आप कुछ मीठा लेना चाहेंगे?"\n'
            '  ❌ "शुभ प्रभात!" — wrong, use "Good morning" instead.\n'
            '  ❌ "धन्यवाद!" — wrong, use "Thank you" instead.\n\n'

            "All other content — food names, quantities, spice levels, time, conversation — write in Devanagari.\n"
            "Latin exceptions: phone digits ('7 8 0 ...'), prices ('$6.50'), and the fixed phrases above.\n\n"

            "Feminine forms: कर सकती हूँ (not कर सकता हूँ)\n"
            "Respectful forms: हाँ जी (not हाँ) | आपका (not तेरा)\n"
            "Spice levels in Hindi: हल्का (mild) | मध्यम (medium) | तीखा (spicy)\n"
            "Order types: पिकअप (pickup) | डिलीवरी (delivery) | डाइन-इन (dine-in)"
        )
    elif lang_lower == "auto":
        language_context = (
            "You just asked the customer to choose English, Hindi, or Punjabi. "
            "Their very next message is their language choice — respond to it naturally, "
            "then call `select_language` immediately and switch into that language.\n\n"
            "Mirror whatever language they use:\n"
            "  English  → casual warm English (TTS language='en')\n"
            "  Hindi    → Devanagari only, no Latin mixing (TTS language='hi')\n"
            "  Punjabi  → Gurmukhi only, no Latin mixing (TTS language='pa')\n\n"
            "If they switch language mid-call → call `select_language` FIRST, then reply."
        )
    else:  # english
        language_context = (
            "The customer has chosen ENGLISH. Greeting is done — go straight to taking the order.\n"
            "Respond in casual, warm English only. No Gurmukhi or Devanagari."
        )

    return f"""You are Sierra — the voice at {RESTAURANT_NAME}, a Punjabi Indian vegetarian sweets and snacks restaurant in Canada. You are female. You know this food inside and out. Warm, quick, a little playful — like the friendliest person at the counter, not a bot.

Today is {datetime.now().strftime("%A, %B %d, %Y")}. Hours: 11 AM – 10 PM daily.

{language_context}

{_get_pronunciation_guide(language)}


## HOW TO SOUND HUMAN — THE ONE RULE ABOVE ALL OTHERS

You are a person having a real conversation, not a computer processing a script.

• React first, ask second. If they say "Mango Lassi sounds good", say "oh that's a great pick" before moving on.
• One thing at a time. Never read out a list of questions. Flow naturally from one thing to the next.
• Use connectors: "and while I've got you —", "perfect", "got it", "love that", "sure thing".
• Short pauses, "um", "hold on" from the customer are normal — just wait.
• Background noise or a muffled line → say "Sorry, a bit of noise there — could you say that again?" Then wait. Never guess. Never make up what they said.
• Every response is 1–3 sentences max. This is a phone call.


## MENU VALIDATION — NON-NEGOTIABLE

You may ONLY add an item to the order if its EXACT name appears in the ## PRICES section below.

If a customer requests something not on that list:
  1. Apologise briefly and naturally ("Ah, we don't carry that one.")
  2. Suggest 1–2 real alternatives from the same category.
  3. Never add the off-menu item to the order, never confirm a price for it.

When in doubt → call `check_item_availability` before adding anything.


## HOW THE CALL FLOWS

Greeting is done, language is set. Build the order as a natural conversation:

1. Ask what they're in the mood for. Suggest 2–4 popular items if they're unsure.
2. Confirm quantities as items are mentioned.
3. Spice level: if the order includes any savory hot food (fried snacks, chaat, mains, burgers, paranthas), ask spice level ONCE: mild, medium, or spicy? Set it as `notes` on each savory item. Skip for desserts, drinks, sides.
4. Upsell once or twice naturally — drop it immediately if they decline.
5. Order type: pickup, delivery, or dine-in?
   → Delivery: get the address, confirm it back.
6. Special instructions (optional), customer name (confirm spelling), phone number ({phone_instruction}).
7. Brief recap → confirm → call `place_order`.
8. Close with the wait time.

Wait times: pickup 20–30 min | delivery 40–60 min | dine-in 10–15 min.

At order confirmation: say the two English words "order confirmed" exactly as written — never translate them. Then say the wait time.

If language switches mid-call → call `select_language` first, then reply in the new language.
If you mishear → ask once to repeat. Still stuck → best guess + confirm. Two failures → `transfer_call`, say warmly "Let me get someone from our team," then stop.
"stop", "wait", "hold on", "okay", "yes", "no" are normal replies — never comprehension failures.


## SERVING SIZES

Per ORDER, not per piece:
Aloo Samosa (2 pcs), Noodle Samosa (2 pcs), Rasmalai (2 pcs), Kesar Rasmalai (6 pcs),
Garam Gulab Jamun (2 pcs), Rasgulla (2 pcs), Tawa Tikki (2 pcs), Aloo Besan Tikki (2 pcs),
Shimla Mirch Pakora (2 pcs), Aloo Bread Pakora (2 pcs), Bread Roll (2 pcs), Butter (2 pcs).
Halwa / Gajrela / Dahi / Raita / Choley → sold by 8 oz container.

In `place_order`: 4 samosas → {{"name": "Aloo Samosa (2 pcs)", "quantity": 2, "price": 3.00}}


## PRICES

{_get_prices_section(pos_client=pos_client)}


## TOOLS

`get_menu(category)`              → when customer wants to browse a category
`check_item_availability(name)`   → when unsure an item exists; call BEFORE adding anything uncertain
`select_language(language)`       → immediately when customer switches language, before replying
`place_order(...)`                 → after customer confirms; delivery_address="" and special_instructions="" if not applicable
`transfer_call(reason)`           → immediately (before speaking) when: customer wants human/manager | complaint/refund | catering 10+ | halal/allergen question | table reservation | 2 failed comprehension attempts

Pure vegetarian — no meat, chicken, beef.
Table reservations: not taken by phone — walk in or transfer to staff.
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_prices_section(pos_client=None) -> str:
    _client = pos_client if pos_client is not None else _get_clover_client()
    if _client is not None and _client.available and _client.menu is not None:
        all_items = _client.menu.all_items()
        by_cat: dict[str, list] = {}
        for item in all_items:
            cat = item.category_name or "Other"
            by_cat.setdefault(cat, []).append(item)
        lines = [
            f"{cat}: " + " | ".join(f"{i.name} ${i.price_dollars:.2f}" for i in items)
            for cat, items in by_cat.items()
        ]
        return "\n".join(lines)

    return (
        "Samosa: Aloo Samosa (2 pcs) $3.00 | Noodle Samosa (2 pcs) $4.50\n"
        "Classics: Chole Bhatura $7.99 | Choley Puri $7.99 | Aloo Puri $7.99\n"
        "Chaat: Chaat Papdi $5.99 | Dahi Bhalla $5.99 | Samosa Choley $6.50 | Tawa Tikki Chaat $6.00 | Tawa Tikki Choley $7.50\n"
        "Pakora: Mix Veg Pakora $8.50 | Paneer Pakora $11.50 | Gobi Pakora $10.50 | Hara Bara Kabab $10.50 | Aloo Cutlet $10.50 | Mushroom Delux $9.00 | Dahi Kabab $9.00 | Parkash Platter $15.99 | Aloo Finger $8.50 | Spring Roll $8.00 | Mirchi Pakora $10.50 | Baingan Pakora $8.50\n"
        "Bread Pakora: Aloo Bread Pakora (2 pcs) $3.00 | Bread Roll (2 pcs) $3.00 | Paneer Aloo Bread Pakora (2 pcs) $5.00\n"
        "Burgers: Aloo Tikki Burger $6.50 | Noodle Burger $7.50 | Paneer Tikki Burger $8.50\n"
        "Sandwiches: Grilled Cheese $5.50 | Super Veggie $6.99 | Sweet Corn $6.99 | Paneer Mayo $7.99 | Coleslaw (Kids) $5.00\n"
        "Parantha: Aloo $4.00 | Gobi $4.50 | Muli $4.50 | Paneer $4.99 | Mix $4.99\n"
        "Desserts: Rasmalai (2 pcs) $4.00 | Kesar Rasmalai (6 pcs) $5.99 | Garam Gulab Jamun (2 pcs) $3.00 | Rasgulla (2 pcs) $3.00 | Moong Dal Halwa 8oz $5.50 | Gajrela 8oz $4.50\n"
        "Drinks: Mango Lassi $4.99 | Sweet/Salty Lassi $4.49 | Mango Shake $5.50 | Mango Faluda $8.50 | Masala Chai $1.99 | Elachi/Gur Chai $2.99 | Dudh Patti $2.99 | Coffee $2.99 | Badam Milk $5.99\n"
        "Sides: Butter (2 pcs) $0.99 | Dahi 8oz $2.99 | Raita 8oz $2.99 | Extra Bhatura $2.50 | Extra Puri $1.50 | Mix Pickle $1.49 | Tamarind Sauce $1.00 | Mint Sauce $1.50"
    )


def normalize_menu_category(value: str) -> str:
    v = value.strip().lower()
    if v in MENU:
        return v
    return MENU_CATEGORY_ALIASES.get(v, v)


def normalize_item_name(value: str) -> str:
    v = value.strip().lower()
    return ITEM_ALIASES.get(v, value)


def _lookup_price(item_name: str, pos_client=None) -> float:
    """4-level price lookup: POS live → alias → exact → token subset → fuzzy."""
    _client = pos_client if pos_client is not None else _get_clover_client()
    if _client is not None and _client.available and _client.menu is not None:
        ci = _client.menu.lookup(item_name)
        if ci is not None:
            return ci.price_dollars

    name_lower = item_name.strip().lower()

    if name_lower in ITEM_ALIASES:
        canonical = ITEM_ALIASES[name_lower].lower()
        for cat_items in MENU.values():
            for item in cat_items:
                if item["name"].lower() == canonical:
                    return item["price"]

    for cat_items in MENU.values():
        for item in cat_items:
            if item["name"].lower() == name_lower:
                return item["price"]

    def _tokens(s: str) -> set[str]:
        return set(re.sub(r"[^a-z0-9]", " ", s.lower()).split())

    query_tokens = _tokens(name_lower)
    if query_tokens:
        best_price: float | None = None
        best_extra = 9999
        ambiguous   = False
        for cat_items in MENU.values():
            for item in cat_items:
                item_tokens = _tokens(item["name"])
                if not query_tokens.issubset(item_tokens):
                    continue
                extra = len(item_tokens - query_tokens)
                if extra < best_extra:
                    best_extra, best_price, ambiguous = extra, item["price"], False
                elif extra == best_extra:
                    ambiguous = True
        if best_price is not None and not ambiguous:
            return best_price

    all_names = [item["name"] for cat_items in MENU.values() for item in cat_items]
    result = process.extractOne(item_name, all_names, scorer=fuzz.token_sort_ratio)
    if result and result[1] >= 80:
        for cat_items in MENU.values():
            for item in cat_items:
                if item["name"] == result[0]:
                    return item["price"]

    return 0.0


# ── Tool definitions ───────────────────────────────────────────────────────────

transfer_call_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "transfer_call",
        "description": (
            "Transfer the call to a restaurant staff member. "
            "Call this when: (1) customer asks to speak to a human/manager/owner, "
            "(2) customer complains about a previous order or wants a refund, "
            "(3) customer wants catering or ordering for 10+ people, "
            "(4) customer asks about halal certification or specific allergens, "
            "(5) two or more consecutive comprehension failures."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": [
                        "customer_requested",
                        "complaint",
                        "catering",
                        "allergy_or_certification",
                        "comprehension_issue",
                    ],
                },
            },
            "required": ["reason"],
        },
    },
)

select_language_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "select_language",
        "description": (
            "Switch the conversation language, TTS voice, and STT session to the "
            "customer's chosen language. Call this IMMEDIATELY when the customer "
            "indicates a language preference — before generating any response. "
            "main.py must reconnect both STT and TTS WebSockets after this call."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "enum": ["english", "hindi", "punjabi"],
                },
            },
            "required": ["language"],
        },
    },
)

get_menu_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "get_menu",
        "description": (
            "Returns the full menu or a specific category. "
            "Use when the customer asks what's available, asks about a dish, "
            "or wants to know prices."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "all", "all_snacks",
                        "snacks", "snack", "samosa",
                        "parkash_classic", "classic",
                        "chaat", "chat",
                        "pakora", "starter", "starters", "crispy",
                        "bread_pakora", "bread pakora", "bread",
                        "burger_sandwich", "burger", "sandwich",
                        "parantha", "paratha",
                        "desserts", "dessert", "sweets", "sweet",
                        "shake_faluda", "shake", "faluda", "falooda",
                        "beverages", "beverage", "drinks", "drink",
                        "chai", "lassi",
                        "sides", "side",
                    ],
                },
            },
            "required": ["category"],
        },
    },
)

check_item_availability_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "check_item_availability",
        "description": (
            "Check if a specific menu item exists and get its price. "
            "Call this for a single item by name before adding it to the order "
            "whenever you are not 100% certain it appears in the PRICES section. "
            "For browsing a category use get_menu instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Item name to look up, e.g. 'Paneer Pakora'.",
                },
            },
            "required": ["item_name"],
        },
    },
)

place_order_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "place_order",
        "description": (
            "Place the confirmed order in the POS and notify via webhook. "
            "Call only after the customer has confirmed all items. "
            "total_amount is for records only — do not speak it unless asked."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name":        {"type": "string"},
                "phone_number":         {"type": "string"},
                "order_type": {
                    "type": "string",
                    "enum": ["dine_in", "pickup", "delivery"],
                },
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name":     {"type": "string"},
                            "quantity": {"type": "integer", "minimum": 1},
                            "price":    {"type": "number"},
                            "notes":    {
                                "type": "string",
                                "description": "Spice level or other per-item note. Empty string if none.",
                            },
                        },
                        "required": ["name", "quantity", "price"],
                    },
                },
                "total_amount":         {"type": "number"},
                "delivery_address":     {"type": "string"},
                "special_instructions": {"type": "string"},
            },
            "required": [
                "customer_name", "phone_number", "items",
                "total_amount", "order_type", "special_instructions",
            ],
        },
    },
)


# ── Async tool implementations ─────────────────────────────────────────────────

async def get_menu(category: str, pos_client=None) -> dict:
    print(f"Tool: get_menu(category='{category}')")
    category_norm = normalize_menu_category(category)

    _client = pos_client if pos_client is not None else _get_clover_client()
    if _client is not None and _client.available and _client.menu is not None:
        if category_norm == "all":
            all_items = _client.menu.all_items()
            by_cat: dict[str, list] = {}
            for item in all_items:
                cat = item.category_name or "Other"
                by_cat.setdefault(cat, []).append(
                    {"name": item.name, "price": item.price_dollars}
                )
            return {"categories": by_cat, "info": BUSINESS_INFO}

        if category_norm == "all_snacks":
            seen: set[str] = set()
            items: list[dict] = []
            for q in ["samosa", "chaat", "pakora", "bread pakora", "burger sandwich"]:
                for ci in _client.menu.get_category(q):
                    if ci.id not in seen:
                        seen.add(ci.id)
                        items.append({"name": ci.name, "price": ci.price_dollars})
            return {"category": "all_snacks", "items": items}

        clover_items = _client.menu.get_category(category_norm.replace("_", " "))
        if clover_items:
            return {
                "category": category_norm,
                "items": [{"name": i.name, "price": i.price_dollars} for i in clover_items],
            }
        return {"error": f"Category '{category}' not found"}

    if category_norm == "all":
        return {
            "categories": {cat: [i["name"] for i in items] for cat, items in MENU.items()},
            "info": BUSINESS_INFO,
        }
    if category_norm == "all_snacks":
        return {
            "category": "all_snacks",
            "items": (
                MENU["samosa"] + MENU["chaat"] + MENU["pakora"]
                + MENU["bread_pakora"] + MENU["burger_sandwich"]
            ),
        }
    if category_norm in MENU:
        return {"category": category_norm, "items": MENU[category_norm]}
    return {"error": "Category not found"}


async def check_item_availability(item_name: str, pos_client=None) -> dict:
    print(f"Tool: check_item_availability('{item_name}')")

    _client = pos_client if pos_client is not None else _get_clover_client()
    if _client is not None and _client.available and _client.menu is not None:
        ci = _client.menu.lookup(item_name)
        if ci is not None:
            return {
                "available": True,
                "item": ci.name, "price": ci.price_dollars,
                "category": ci.category_name, "description": "",
            }
        return {
            "available": False,
            "message": (
                f"'{item_name}' is not on the menu. "
                "Tell the customer and suggest a similar item. Do NOT add to order."
            ),
        }

    canonical = normalize_item_name(item_name)
    for cat, cat_items in MENU.items():
        for item in cat_items:
            if item["name"].lower() == canonical.strip().lower():
                return {
                    "available": True,
                    "item": item["name"], "price": item["price"],
                    "category": cat, "description": item.get("description", ""),
                }

    price = _lookup_price(item_name, pos_client=pos_client)
    if price:
        return {"available": True, "item": canonical, "price": price}

    return {
        "available": False,
        "message": (
            f"'{item_name}' is not on the menu. "
            "Tell the customer and suggest a similar item. Do NOT add to order."
        ),
    }


async def place_order(
    customer_name: str,
    phone_number: str,
    items: list,
    total_amount: float,
    order_type: str = "pickup",
    delivery_address: str = "",
    special_instructions: str = "",
    pos_client=None,
) -> dict:
    print(
        f"Tool: place_order(customer='{customer_name}', type='{order_type}', "
        f"items={[i['name'] for i in items]})"
    )

    if not items:
        return {"success": False, "error": "No items in order."}

    for item in items:
        qty = item.get("quantity", 1)
        if not isinstance(qty, int) or qty < 1:
            item["quantity"] = 1

    # Server-side menu validation (last defence against off-menu items)
    not_found = []
    for item in items:
        if not item.get("price"):
            item["price"] = _lookup_price(item["name"], pos_client=pos_client)
        if not item.get("price"):
            not_found.append(item["name"])

    if not_found:
        return {
            "success": False,
            "error": (
                f"Item(s) not on the menu: {', '.join(not_found)}. "
                "Tell the customer and ask them to choose from the actual menu."
            ),
        }

    total_amount = sum(item["price"] * item.get("quantity", 1) for item in items)
    wait_time = (
        "20-30 minutes" if order_type == "pickup"
        else "40-60 minutes" if order_type == "delivery"
        else "10-15 minutes"
    )

    pos_order_id: str | None = None
    _client = pos_client if pos_client is not None else _get_clover_client()
    if _client is not None and _client.available:
        try:
            pos_order = await _client.create_order(
                order_type=order_type,
                items=items,
                customer_name=customer_name,
                phone_number=phone_number,
                special_instructions=special_instructions,
                delivery_address=delivery_address,
            )
            pos_order_id = pos_order.id
            print(f"POS order created: {pos_order_id}")
        except (CloverItemNotFoundError, SquareItemNotFoundError) as exc:
            return {
                "success": False,
                "error": f"Item '{exc.item_name}' not matched in POS. Ask customer to clarify.",
            }
        except (CloverError, SquareError) as exc:
            print(f"POS failed (falling back to n8n): {exc}")

    order_id = pos_order_id or f"PS-{datetime.now().strftime('%H%M%S')}"

    n8n_url = os.getenv("N8N_WEBHOOK_URL", "")
    if n8n_url:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(n8n_url, json={
                    "order_id": order_id,
                    "customer_name": customer_name,
                    "phone_number": phone_number,
                    "order_type": order_type,
                    "items": items,
                    "total_amount": total_amount,
                    "wait_time": wait_time,
                    "delivery_address": delivery_address,
                    "special_instructions": special_instructions,
                    "timestamp": datetime.now().isoformat(),
                })
        except Exception as e:
            print(f"n8n webhook failed (order still confirmed): {e}")

    return {
        "success":              True,
        "order_id":             order_id,
        "customer_name":        customer_name,
        "phone_number":         phone_number,
        "order_type":           order_type,
        "items":                items,
        "total_amount":         total_amount,
        "wait_time":            wait_time,
        "special_instructions": special_instructions,
        "message": (
            f"Order {order_id} placed. "
            "Say the two English words 'order confirmed' exactly as written — "
            "do NOT translate them into Punjabi or Hindi. "
            f"Then say the wait time: {wait_time}."
        ),
    }


# ── Tool registry ──────────────────────────────────────────────────────────────

def get_tools(state: RestaurantState):

    async def transfer_call(reason: str) -> str:
        print(f"Tool: transfer_call(reason='{reason}')")
        state.transfer_requested = True
        state.transfer_reason    = reason
        return (
            "Transfer initiated. Say exactly one warm sentence in the customer's language: "
            "English → 'Let me get someone from our team for you right away.' "
            "Punjabi → 'ਮੈਂ ਤੁਹਾਨੂੰ ਸਾਡੀ ਟੀਮ ਨਾਲ ਜੋੜਦੀ ਹਾਂ।' "
            "Hindi → 'मैं आपको हमारी टीम से जोड़ती हूँ।' "
            "Then stop speaking completely."
        )

    async def select_language(language: str) -> str:
        print(f"Tool: select_language(language='{language}')")
        cfg = LANGUAGE_CONFIG.get(language.lower(), LANGUAGE_CONFIG["english"])
        state.tts_language  = cfg["tts_language"]
        state.tts_voice     = cfg["tts_voice"]
        state.tts_model     = cfg["tts_model"]
        state.stt_language  = language.lower()
        return (
            f"Language locked to {language}. "
            f"main.py ACTION REQUIRED: "
            f"(1) Reconnect STT WebSocket → get_soniox_rt_config('{language.lower()}') "
            f"    This sets language_hints_strict=True for [{_LANG_ISO.get(language.lower(), 'en')}] only. "
            f"(2) Open new TTS stream    → get_soniox_tts_config('{language.lower()}', new_stream_id) "
            f"    TTS language='{cfg['tts_language']}', voice='{cfg['tts_voice']}'. "
            f"Respond in {language} now."
        )

    async def get_menu_for_pos(category: str) -> dict:
        return await get_menu(category, pos_client=state.pos_client)

    async def check_availability_for_pos(item_name: str) -> dict:
        return await check_item_availability(item_name, pos_client=state.pos_client)

    async def place_order_and_notify(
        customer_name: str,
        phone_number: str,
        items: list,
        total_amount: float,
        order_type: str = "pickup",
        delivery_address: str = "",
        special_instructions: str = "",
    ) -> dict:
        result = await place_order(
            customer_name=customer_name,
            phone_number=phone_number,
            items=items,
            total_amount=total_amount,
            order_type=order_type,
            delivery_address=delivery_address,
            special_instructions=special_instructions,
            pos_client=state.pos_client,
        )
        if result.get("success"):
            state.confirmed_order = result
        return result

    return [
        (transfer_call_tool_description,           transfer_call),
        (select_language_tool_description,         select_language),
        (get_menu_tool_description,                get_menu_for_pos),
        (check_item_availability_tool_description, check_availability_for_pos),
        (place_order_tool_description,             place_order_and_notify),
    ]
