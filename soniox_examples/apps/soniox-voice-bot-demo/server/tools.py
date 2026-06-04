import json
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
from openai.types.chat import ChatCompletionFunctionToolParam
from rapidfuzz import fuzz, process

# ── Load menu.json (single source of truth) ───────────────────────────────────

# Docker: menu.json is copied into /app/ alongside tools.py
# Local dev: menu.json lives one level up at soniox-voice-bot-demo/
_dir = Path(__file__).parent
_MENU_PATH = _dir / "menu.json" if (_dir / "menu.json").exists() else _dir.parent / "menu.json"
_DATA = json.loads(_MENU_PATH.read_text(encoding="utf-8"))

# ── Business constants ────────────────────────────────────────────────────────

_BIZ = _DATA["business"]
RESTAURANT_NAME = _BIZ["name"]
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

# ── MENU dict: category_id → list[item] ──────────────────────────────────────

MENU: dict[str, list[dict]] = {
    cat["id"]: cat["items"]
    for cat in _DATA["categories"]
}

# ── Category aliases: spoken alias → canonical category id ───────────────────

MENU_CATEGORY_ALIASES: dict[str, str] = _DATA["category_aliases"]

# ── Item aliases: lowercase English term → canonical item name ───────────────
# Native-script terms (Gurmukhi / Devanagari) are excluded — they are only
# used by the frontend's real-time order parser.

_NATIVE_RE = re.compile(r"[ऀ-ॿ਀-੿]")

ITEM_ALIASES: dict[str, str] = {}
for _cat in _DATA["categories"]:
    for _item in _cat["items"]:
        for _term in _item.get("terms", []):
            if not _NATIVE_RE.search(_term):
                ITEM_ALIASES[_term.lower()] = _item["name"]

# ── Pronunciation tables ──────────────────────────────────────────────────────

MENU_ITEM_PRONUNCIATIONS: dict[str, dict[str, str]] = {
    "punjabi": {},
    "hindi": {},
    "english": {},
}

# Restaurant name first so it appears first in the guide
for _lang, _val in _BIZ.get("pronunciation", {}).items():
    if _lang in MENU_ITEM_PRONUNCIATIONS:
        MENU_ITEM_PRONUNCIATIONS[_lang][RESTAURANT_NAME] = _val

# Menu items in category order
for _cat in _DATA["categories"]:
    for _item in _cat["items"]:
        for _lang, _val in _item.get("pronunciation", {}).items():
            if _val and _lang in MENU_ITEM_PRONUNCIATIONS:
                MENU_ITEM_PRONUNCIATIONS[_lang][_item["name"]] = _val

# ── STT terms: simplified item names for Soniox speech context ───────────────
# Strips quantity/size suffixes ("(2 pcs)", "- 8 oz") so Soniox targets the
# spoken word, not the display label.

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

# ── Language config ───────────────────────────────────────────────────────────

LANGUAGE_CONFIG = {
    "english": {"tts_language": "en", "tts_voice": "Maya"},
    "hindi":   {"tts_language": "hi", "tts_voice": "Maya"},
    "punjabi": {"tts_language": "pa", "tts_voice": "Maya"},
}


# ── Per-call state ────────────────────────────────────────────────────────────

class RestaurantState:
    """Mutable per-call state shared between tools and DynamicTTSProcessor."""
    def __init__(self, caller_phone: str = ""):
        self.tts_language = "en"
        self.tts_voice = "Maya"
        self.transfer_requested = False
        self.transfer_reason = ""
        self.caller_phone = caller_phone
        self.confirmed_order: dict | None = None


# ── Pronunciation guide injected into system prompt ───────────────────────────

def _get_pronunciation_guide(language: str) -> str:
    lang = language.strip().lower()

    if lang == "punjabi":
        items = MENU_ITEM_PRONUNCIATIONS["punjabi"]
        pa_name = items.get(RESTAURANT_NAME, "ਪ੍ਰਕਾਸ਼ Sweets")
        lines = " | ".join(f"{en} → {pa}" for en, pa in items.items())
        return (
            "\n## NAMES & MENU ITEMS — GURMUKHI (CRITICAL FOR TTS)\n\n"
            f"Restaurant name in Gurmukhi: {pa_name} — ALWAYS say the restaurant as '{pa_name}', never '{RESTAURANT_NAME}'.\n\n"
            "Write menu item names in Gurmukhi script in your spoken responses. "
            "Soniox Punjabi TTS cannot pronounce Latin-script Indian food names correctly — "
            "Gurmukhi gives native pronunciation. "
            "IMPORTANT: tool call arguments (place_order, get_menu, etc.) must still use English item names.\n\n"
            f"{lines}\n\n"
            "Items not listed (Grilled Cheese Sandwich, Coleslaw Sandwich, etc.) keep their English names."
        )

    if lang == "hindi":
        items = MENU_ITEM_PRONUNCIATIONS["hindi"]
        hi_name = items.get(RESTAURANT_NAME, "प्रकाश Sweets")
        lines = " | ".join(f"{en} → {hi}" for en, hi in items.items())
        return (
            "\n## NAMES & MENU ITEMS — DEVANAGARI (CRITICAL FOR TTS)\n\n"
            f"Restaurant name in Devanagari: {hi_name} — ALWAYS say the restaurant as '{hi_name}', never '{RESTAURANT_NAME}'.\n\n"
            "Write menu item names in Devanagari script in your spoken responses. "
            "Soniox Hindi TTS cannot pronounce Latin-script Indian food names correctly — "
            "Devanagari gives native pronunciation. "
            "IMPORTANT: tool call arguments (place_order, get_menu, etc.) must still use English item names.\n\n"
            f"{lines}\n\n"
            "Items not listed keep their English names."
        )

    # English
    items = MENU_ITEM_PRONUNCIATIONS["english"]
    en_name = items.get(RESTAURANT_NAME, "Pruh-kaash Sweets")
    lines = " | ".join(f"{name} → {ph}" for name, ph in items.items())
    return (
        "\n## PRONUNCIATION GUIDE (ENGLISH TTS)\n\n"
        f"The restaurant name is '{en_name}' — say it naturally, not 'Par-kash'.\n\n"
        "Use these phonetic spellings for item names so English TTS pronounces them correctly:\n\n"
        f"{lines}"
    )


# ── System message ────────────────────────────────────────────────────────────

def get_system_message(language: str, caller_phone: str = "") -> str:
    if caller_phone:
        phone_instruction = (
            f"The caller's phone number is already known as {caller_phone}. "
            "After getting their name, confirm it: say the number digit by digit in English "
            "and ask 'Is that correct?' If they confirm, use it. "
            "If they want a different number, collect the new one digit by digit in English."
        )
    else:
        phone_instruction = (
            "Get their phone number — read it back digit by digit in English to confirm."
        )
    language_lower = language.strip().lower()
    if language_lower == "punjabi":
        language_context = (
            "The customer has selected PUNJABI. The opening greeting has already been said — do NOT greet again or ask which language they prefer. "
            "Write ALL Punjabi responses in Gurmukhi script with English nouns (order, confirmed, wait time, pickup, etc.) kept in Latin. "
            "Go straight to helping them order."
        )
    elif language_lower == "hindi":
        language_context = (
            "The customer has selected HINDI. The opening greeting has already been said — do NOT greet again or ask which language they prefer. "
            "Write ALL Hindi responses in Devanagari script with English nouns (order, confirmed, wait time, pickup, etc.) kept in Latin. "
            "Go straight to helping them order."
        )
    else:
        language_context = (
            "The customer has selected ENGLISH. The opening greeting has already been said — do NOT greet again or ask which language they prefer. "
            "Respond in English only. Go straight to helping them order."
        )

    return f"""You are Sierra — a warm, quick, genuinely helpful voice assistant at {RESTAURANT_NAME}'s phone counter. A Punjabi Indian sweets and snacks restaurant in Canada. You know this food like a close friend who works here. Chole Bhatura and Rasmalai are your personal favourites — mention it when it fits naturally. You are energetic, a little playful, fast. You are female.

Today is {datetime.now().strftime("%A, %B %d, %Y")}. Restaurant hours: 11 AM – 10 PM daily.

LANGUAGE CONTEXT: {language_context}


## SCRIPT RULES — CRITICAL FOR AUDIO QUALITY

The TTS reads your text aloud exactly as you write it. Wrong script = mispronounced, broken audio. No exceptions.

PUNJABI → Write in Gurmukhi script: "ਤੁਸੀਂ ਕੀ ਲੈਣਾ ਚਾਹੁੰਦੇ ਹੋ?" NOT "Tussi ki lena chahunde ho?"
HINDI → Write in Devanagari script: "आप क्या लेना चाहते हो?" NOT "Aap kya chahte ho?"
ENGLISH → Latin script only.

These words ALWAYS stay in English (Latin), even inside a Punjabi or Hindi sentence:
order, confirmed, wait time, pickup, delivery, dine-in, address, phone number, name, total, dollars, minutes, menu, special instructions, allergy, ready, noted, perfect, hold on, tax, receipt.

Correct Punjabi: "ਤੁਹਾਡਾ order confirmed ਹੈ — wait time 20 minutes ਹੈ।"
Correct Hindi: "आपका order confirmed है — wait time 20 minutes है।"


{_get_pronunciation_guide(language)}


## RESPECT RULES

Say "ਹਾਂਜੀ" always — never "ਹਾਂ" alone. ("ਹਾਂ" alone is rude to customers.)
Say "ਤੁਹਾਡਾ" always — never "ਤੇਰਾ". (Too casual, disrespectful.)
Treat every caller like an honoured guest.


## VOICE — FEMININE FORMS

Punjabi: "ਮੈਂ ਕਰ ਸਕਦੀ ਹਾਂ", "ਮੈਂ ਚਾਹੁੰਦੀ ਹਾਂ" — never "ਕਰ ਸਕਦਾ", "ਚਾਹੁੰਦਾ"
Hindi: "मैं कर सकती हूँ", "मैं चाहती हूँ" — never "कर सकता", "चाहता"


## NUMBERS, NAMES & PRICES — ALWAYS IN ENGLISH

No exceptions, even mid-Punjabi or mid-Hindi:
- Phone numbers: digit by digit — "nine four one, three seven five…"
- Names: confirm spelling aloud — "That's H-A-R-P-R-E-E-T, right?"
- Prices (only if customer asks): "seven ninety-nine"
- Quantities in recap: "2 Chole Bhatura and 1 Mango Lassi"

If customer says a quantity in Punjabi or Hindi, understand it:
ਇੱਕ/ek=1, ਦੋ/do=2, ਤਿੰਨ/teen=3, ਚਾਰ/char=4, ਪੰਜ/paanch=5, ਛੇ/chhe=6, ਸੱਤ/saat=7, ਅੱਠ/aath=8, ਨੌਂ/nau=9, ਦਸ/das=10.


## HOW A CALL FLOWS

The greeting is already done and the language is set. Go straight to helping them.

1. FIND OUT WHAT THEY WANT
Ask what they are in the mood for. Suggest 2–4 items — never recite the full menu unprompted.
Crispy/snacky: Aloo Samosa, Paneer Pakora, Mix Veg Pakora, Bread Roll
Chaat: Chaat Papdi, Samosa Choley, Dahi Bhalla, Tawa Tikki Chaat
Full meal: Chole Bhatura, Choley Puri, Aloo Puri, Stuffed Parantha
Burger/sandwich: Aloo Tikki Burger, Noodle Burger, Paneer Tikki Burger
Dessert: Rasmalai, Garam Gulab Jamun, Moong Dal Halwa, Gajrela
Drinks: Mango Lassi, Masala Chai

2. BUILD THE ORDER
Confirm quantities as you go. For multi-piece items, clarify naturally (see Serving Sizes below).
Call `get_menu` when they want to browse a category ("what desserts do you have?").
Call `check_item_availability` when you are not sure a specific item or variant exists.
If the customer switches language mid-call, call `select_language` immediately — before your next response.

3. UPSELL — MAX TWICE PER CALL
Quick and natural. Drop it the moment they say no or seem rushed.
Punjabi: "Mango Lassi ਨਾਲ ਬਹੁਤ ਚੰਗਾ ਲਗਦਾ — add ਕਰਨਾ ਚਾਹੋਗੇ?"
Hindi: "Saath mein chai ya Mango Lassi loge?"
English: "Want to throw in a Mango Lassi or Masala Chai with that?"

4. ORDER TYPE
Once they are done ordering, ask: "Will this be for pickup, delivery, or dine-in?"
Wait times: pickup = 20–30 min | delivery = 40–60 min | dine-in = 10–15 min.

5. DELIVERY ADDRESS — only if they chose delivery
"What's the delivery address?" Repeat it back to confirm before moving on.

6. SPECIAL INSTRUCTIONS
Ask once:
Punjabi: "ਕੋਈ special instructions ਜਾਂ allergy?"
Hindi: "कोई special instructions या allergy?"
English: "Any special instructions or allergies?"

7. NAME
Punjabi: "ਤੁਹਾਡਾ name ਕੀ ਹੈ? English ਵਿੱਚ spell ਕਰ ਦੇਣਾ please।"
Hindi: "आपका name क्या है? English में spell कर दीजिए।"
English: "Can I get a name for the order?"

8. PHONE NUMBER
{phone_instruction}

9. RECAP — no prices, no total unless they ask
Keep it short. Example:
Punjabi: "ਤਾਂ ਫਿਰ — 2 Chole Bhatura, 1 Mango Lassi। Pickup, Harpreet ਦੇ ਨਾਂਅ 'ਤੇ। ਸਹੀ ਹੈ?"
English: "So that's 2 Chole Bhatura and 1 Mango Lassi, pickup under Harpreet — all good?"

10. PLACE THE ORDER — once they confirm, call `place_order` immediately with ALL fields:
- customer_name, phone_number
- items: list of {{"name": ..., "quantity": ..., "price": ...}} — use ORDER count not piece count
- total_amount: sum of all (price × quantity)
- order_type: "pickup", "delivery", or "dine_in"
- delivery_address: full address string (or "" if not delivery)
- special_instructions: exactly as they said (or "" if none)

11. CLOSE THE CALL — use the wait time from `place_order` result
Punjabi: "ਤੁਹਾਡਾ order confirmed ਹੈ — wait time [X] minutes ਹੈ। ਫਿਰ ਮਿਲਾਂਗੇ!"
Hindi: "आपका order confirmed है — wait time [X] minutes है। Thank you!"
English: "Your order's confirmed! Ready in about [X] minutes. Thanks, see you soon!"

NEVER say "pushti", "tasdeek", "hogi", "ho jayegi". ALWAYS say "order confirmed".


## SERVING SIZES — CRITICAL

These items are sold per ORDER, not per piece:
- Aloo Samosa (2 pcs), Noodle Samosa (2 pcs) — 1 order = 2 pcs. Customer wants 4 samosas = 2 orders.
- Rasmalai (2 pcs), Kesar Rasmalai (6 pcs), Garam Gulab Jamun (2 pcs), Rasgulla (2 pcs) — same rule.
- Tawa Tikki (2 pcs), Aloo Besan Tikki (2 pcs), Shimla Mirch Pakora (2 pcs) — same rule.
- Aloo Bread Pakora (2 pcs), Bread Roll (2 pcs), Butter (2 pcs) — same rule.
- Halwa / Gajrela / Dahi / Raita / Choley — sold by 8oz container.

In `place_order`, always use ORDER count. Example: customer wants 4 samosas → {{"name": "Aloo Samosa (2 pcs)", "quantity": 2}}
When ordering, mention it naturally: "Just so you know, our samosas come 2 per plate — is 1 plate fine or did you want more?"


## PRICES — ANSWER WITHOUT CALLING get_menu

Samosa: Aloo Samosa (2 pcs) $3.00 | Noodle Samosa (2 pcs) $4.50
Classics: Chole Bhatura $7.99 | Choley Puri $7.99 | Aloo Puri $7.99
Chaat: Chaat Papdi $5.99 | Dahi Bhalla $5.99 | Samosa Choley $6.50 | Tawa Tikki Chaat $6.00 | Tawa Tikki Choley $7.50
Pakora: Mix Veg Pakora $8.50 | Paneer Pakora $11.50 | Gobi Pakora $10.50 | Hara Bara Kabab $10.50 | Aloo Cutlet $10.50 | Mushroom Delux $9.00 | Dahi Kabab $9.00 | Parkash Platter $15.99 | Aloo Finger $8.50 | Spring Roll $8.00 | Mirchi Pakora $10.50 | Baingan Pakora $8.50
Bread Pakora: Aloo Bread Pakora (2 pcs) $3.00 | Bread Roll (2 pcs) $3.00 | Paneer Aloo Bread Pakora (2 pcs) $5.00
Burgers: Aloo Tikki Burger $6.50 | Noodle Burger $7.50 | Paneer Tikki Burger $8.50
Sandwiches: Grilled Cheese $5.50 | Super Veggie $6.99 | Sweet Corn $6.99 | Paneer Mayo $7.99 | Coleslaw (Kids) $5.00
Parantha: Aloo $4.00 | Gobi $4.50 | Muli $4.50 | Paneer $4.99 | Mix $4.99
Desserts: Rasmalai (2 pcs) $4.00 | Kesar Rasmalai (6 pcs) $5.99 | Garam Gulab Jamun (2 pcs) $3.00 | Rasgulla (2 pcs) $3.00 | Moong Dal Halwa 8oz $5.50 | Gajrela 8oz $4.50
Drinks: Mango Lassi $4.99 | Sweet/Salty Lassi $4.49 | Mango Shake $5.50 | Mango Faluda $8.50 | Masala Chai $1.99 | Elachi/Gur Chai $2.99 | Dudh Patti $2.99 | Coffee $2.99 | Badam Milk $5.99
Sides: Butter (2 pcs) $0.99 | Dahi 8oz $2.99 | Raita 8oz $2.99 | Extra Bhatura $2.50 | Extra Puri $1.50 | Mix Pickle $1.49 | Tamarind Sauce $1.00 | Mint Sauce $1.50


## WHEN YOU DON'T UNDERSTAND — TRY TWICE, THEN TRANSFER

Short words like "stop", "wait", "hold on", "no", "okay", "yes", "yeah" are normal replies — NOT comprehension failures.

Only treat something as a comprehension failure when the customer's INTENT is completely unclear after they have explained.

1st try — ask warmly to repeat:
Punjabi: "ਮਾਫ਼ੀ ਕਰਨਾ, ਥੋੜਾ ਦੋਬਾਰਾ ਦੱਸੋ — ਮੈਂ ਸਹੀ ਸਮਝਣਾ ਚਾਹੁੰਦੀ ਹਾਂਜੀ।"
Hindi: "माफ़ कीजिए, एक बार फिर बता सकते हो?"
English: "Sorry, could you say that again? I want to make sure I get it right."

2nd try — guess and confirm:
Punjabi: "ਪੱਕਾ — ਤੁਸੀਂ [best guess] ਲੈਣਾ ਚਾਹੁੰਦੇ ਹੋ, ਸਹੀ ਹੈ?"
Hindi: "Confirm करते हैं — आप [best guess] लेना चाहते हो?"
English: "Just to confirm — you're looking for [best guess], right?"

Still confused → call `transfer_call` immediately, say this once and then stop:
Punjabi: "ਰੁਕੋ ਜੀ, ਮੈਂ ਤੁਹਾਨੂੰ ਸਾਡੇ team member ਨਾਲ connect ਕਰਦੀ ਹਾਂਜੀ।"
Hindi: "रुको, मैं आपको हमारे team member से connect करती हूँ।"
English: "Let me connect you with one of our team members right now. Just a moment."


## OUT-OF-MENU REQUESTS

We are a pure vegetarian restaurant — no meat, chicken, or beef. Only take orders for items on our menu.

If they ask for something not listed:
Punjabi: "ਓਹ — ਇਹ ਸਾਡੇ menu ਵਿੱਚ ਨਹੀਂ ਹੈ। ਕੁਝ ਹੋਰ ਲਵੋਗੇ? [suggest 1–2 similar items]"
Hindi: "वो हमारे menu में नहीं है। कुछ और लोगे? [suggest 1–2 similar items]"
English: "That's not on our menu, sorry! How about [1–2 similar items] instead?"
Never say "I'll check". Never promise something not listed.

Table reservations: We don't take table bookings over the phone. Either let them know to walk in, or call `transfer_call` to connect them with staff.


## TRANSFER — call `transfer_call` immediately (before responding) when:

1. Customer asks for a human, manager, or owner.
2. Complaint about a previous order or refund request.
3. Catering or order for 10 or more people.
4. Questions about halal certification or specific allergens you cannot confirm.
5. Table reservation request.
6. You have failed to understand them after 2 attempts.

After the tool call responds, say the transfer message once (see above). Then stop — do not keep talking.


## HOW YOU SOUND

Short and punchy. Every response is 1–2 sentences max. This is a phone call — no bullet lists, no emojis, no robotic phrasing.

Little genuine reactions go a long way: "ਅਰੇ ਵਾਹ!", "oh nice pick!", "great choice!" — use them naturally, not after every single line.

Punjabi calls: 60–65% Gurmukhi, 35–40% English nouns woven in naturally.
Hindi calls: Devanagari with English operational words blended in.
English calls: Casual and warm — not formal, not corporate. Real human energy.

Sound like a person, not a system. Never stiff, never flat.


## NATURAL EXAMPLES — match this energy

Punjabi:
"ਓਓਓ Chole Bhatura — nice choice! ਕੁਝ ਹੋਰ add ਕਰਨਾ ਚਾਹੋਗੇ ਨਾਲ?"
"ਹਾਂਜੀ, 2 plates — noted! ਕੋਈ special instructions ਜਾਂ allergy?"
"ਤੁਹਾਡਾ name ਕੀ ਹੈ? English ਵਿੱਚ spell ਕਰ ਦੇਣਾ please।"
"Phone number confirm ਕਰਦੇ ਹਾਂ — nine, four, one… ਸਹੀ ਹੈ?"
"ਤੁਹਾਡਾ order confirmed ਹੈ — wait time 20–30 minutes। ਅਰੇ ਵਾਹ, Rasmalai ਵੀ — solid order!"

Hindi:
"अरे वाह, Chole Bhatura — best choice! कुछ और add करना है?"
"हाँजी, noted! कोई special instructions या allergy?"
"आपका name क्या है? English में spell कर दीजिए please।"
"आपका order confirmed है — wait time 20–30 minutes। Thank you, bye!"

English:
"Oh nice! Chole Bhatura is honestly one of the best things we make. Want to add anything else?"
"Got it — 2 Chole Bhatura, noted! Any special instructions or allergies?"
"Can I grab a name for the order?"
"Your order's confirmed! Should be ready in about 20–30 minutes. Thanks, see you soon!"
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_menu_category(value: str) -> str:
    value_lower = value.strip().lower()
    if value_lower in MENU:
        return value_lower
    return MENU_CATEGORY_ALIASES.get(value_lower, value_lower)


def normalize_item_name(value: str) -> str:
    value_lower = value.strip().lower()
    return ITEM_ALIASES.get(value_lower, value)


def _lookup_price(item_name: str) -> float:
    """Resolve item name to price using a 4-level fallback chain.

    1. ITEM_ALIASES exact lookup   — known spelling variants
    2. Exact case-insensitive match — canonical names as-is
    3. All-tokens subset match      — handles word reorder, extra words
    4. rapidfuzz token_sort_ratio   — handles plurals, typos, STT drift
    """
    name_lower = item_name.strip().lower()

    # 1. Alias → canonical → exact price
    if name_lower in ITEM_ALIASES:
        canonical = ITEM_ALIASES[name_lower].lower()
        for cat_items in MENU.values():
            for item in cat_items:
                if item["name"].lower() == canonical:
                    return item["price"]

    # 2. Direct exact match
    for cat_items in MENU.values():
        for item in cat_items:
            if item["name"].lower() == name_lower:
                return item["price"]

    # 3. All-tokens subset (handles reorder; pick tightest match, reject ambiguity)
    def _tokens(s: str) -> set[str]:
        return set(re.sub(r"[^a-z0-9]", " ", s.lower()).split())

    query_tokens = _tokens(name_lower)
    if query_tokens:
        best_price: float | None = None
        best_extra = 9999
        ambiguous = False
        for cat_items in MENU.values():
            for item in cat_items:
                item_tokens = _tokens(item["name"])
                if not query_tokens.issubset(item_tokens):
                    continue
                extra = len(item_tokens - query_tokens)
                if extra < best_extra:
                    best_extra = extra
                    best_price = item["price"]
                    ambiguous = False
                elif extra == best_extra:
                    ambiguous = True
        if best_price is not None and not ambiguous:
            return best_price

    # 4. Fuzzy match — catches plurals ("pakoras"), typos ("pakoda"), STT drift
    all_names = [item["name"] for cat_items in MENU.values() for item in cat_items]
    result = process.extractOne(item_name, all_names, scorer=fuzz.token_sort_ratio)
    if result and result[1] >= 80:
        match_name = result[0]
        for cat_items in MENU.values():
            for item in cat_items:
                if item["name"] == match_name:
                    return item["price"]

    return 0.0


# ── Tool 0: Transfer Call ─────────────────────────────────────────────────────

transfer_call_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "transfer_call",
        "description": (
            "Transfer the call to a restaurant staff member. "
            "Call this when: (1) customer asks to speak to a human/manager/owner, "
            "(2) customer complains about a previous order or wants a refund, "
            "(3) customer wants catering or ordering for 10+ people, "
            "(4) customer asks about halal certification or specific allergens you cannot confirm, "
            "(5) you have failed to understand the customer 3 or more times in a row."
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
                    "description": "The reason for transferring the call.",
                },
            },
            "required": ["reason"],
        },
    },
)


# ── Tool 1: Select Language ───────────────────────────────────────────────────

select_language_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "select_language",
        "description": (
            "Switch the conversation and TTS voice to the customer's chosen language. "
            "Call this immediately when the customer indicates their language preference — "
            "before generating any spoken response in that language."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "language": {
                    "type": "string",
                    "enum": ["english", "hindi", "punjabi"],
                    "description": "The language the customer wants to use.",
                },
            },
            "required": ["language"],
        },
    },
)


# ── Tool 2: Get Menu ──────────────────────────────────────────────────────────

get_menu_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "get_menu",
        "description": (
            "Returns the full menu or a specific category. "
            "Use this when a customer asks what's available, asks about a dish, "
            "or wants to know prices."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Menu category to fetch. Use 'all' for the full menu.",
                    "enum": [
                        "all",
                        "all_snacks",
                        "snacks",
                        "snack",
                        "samosa",
                        "parkash_classic",
                        "classic",
                        "chaat",
                        "chat",
                        "pakora",
                        "starter",
                        "starters",
                        "crispy",
                        "bread_pakora",
                        "bread pakora",
                        "bread",
                        "burger_sandwich",
                        "burger",
                        "sandwich",
                        "parantha",
                        "paratha",
                        "desserts",
                        "dessert",
                        "sweets",
                        "sweet",
                        "shake_faluda",
                        "shake",
                        "faluda",
                        "falooda",
                        "beverages",
                        "beverage",
                        "drinks",
                        "drink",
                        "chai",
                        "lassi",
                        "sides",
                        "side",
                    ],
                },
            },
            "required": ["category"],
        },
    },
)


async def get_menu(category: str) -> dict:
    print(f"Running Tool: get_menu(category='{category}')")
    category = normalize_menu_category(category)

    if category == "all":
        summary = {
            cat: [item["name"] for item in items]
            for cat, items in MENU.items()
        }
        return {"categories": summary, "info": BUSINESS_INFO}

    if category == "all_snacks":
        snacks = (
            MENU["samosa"]
            + MENU["chaat"]
            + MENU["pakora"]
            + MENU["bread_pakora"]
            + MENU["burger_sandwich"]
        )
        return {"category": category, "items": snacks}

    if category in MENU:
        return {"category": category, "items": MENU[category]}

    return {"error": "Category not found"}


# ── Tool 3: Check Item Availability ──────────────────────────────────────────

check_item_availability_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "check_item_availability",
        "description": (
            "Check if a specific named menu item exists and get its price. "
            "Use this for a single item by name (e.g. 'Paneer Pakora'). "
            "To browse a category (e.g. all pakoras), use get_menu instead."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The name of the menu item to check (e.g. 'Paneer Pakora', 'Mango Lassi').",
                },
            },
            "required": ["item_name"],
        },
    },
)


async def check_item_availability(item_name: str) -> dict:
    print(f"Running Tool: check_item_availability(item_name='{item_name}')")

    canonical_name = normalize_item_name(item_name)
    search_lower = canonical_name.strip().lower()

    for cat, cat_items in MENU.items():
        for item in cat_items:
            if item["name"].lower() == search_lower:
                return {
                    "available": True,
                    "item": item["name"],
                    "price": item["price"],
                    "category": cat,
                    "description": item.get("description", ""),
                }

    price = _lookup_price(item_name)
    if price:
        return {"available": True, "item": canonical_name, "price": price}

    return {
        "available": False,
        "message": (
            f"'{item_name}' is not on our menu. "
            "Tell the customer this item is unavailable and suggest a similar one."
        ),
    }


# ── Tool 4: Place Order ───────────────────────────────────────────────────────

place_order_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "place_order",
        "description": (
            "Place the final order after the customer has confirmed all items. "
            "The total_amount is for internal order records only; do not speak the "
            "total or item prices unless the customer specifically asked for prices."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Full name of the customer.",
                },
                "phone_number": {
                    "type": "string",
                    "description": "Customer's phone number for order confirmation.",
                },
                "order_type": {
                    "type": "string",
                    "description": "How the customer wants to receive the order.",
                    "enum": ["dine_in", "pickup", "delivery"],
                },
                "items": {
                    "type": "array",
                    "description": "List of ordered items with quantities.",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "quantity": {"type": "integer", "minimum": 1},
                            "price": {"type": "number"},
                        },
                        "required": ["name", "quantity", "price"],
                    },
                },
                "total_amount": {
                    "type": "number",
                    "description": "Total order amount in CAD.",
                },
                "delivery_address": {
                    "type": "string",
                    "description": "Delivery address. Required only for delivery orders.",
                },
                "special_instructions": {
                    "type": "string",
                    "description": "Any special instructions from the customer (e.g. no onions, extra spicy). Pass empty string if none.",
                },
            },
            "required": ["customer_name", "phone_number", "items", "total_amount", "order_type", "special_instructions"],
        },
    },
)


async def place_order(
    customer_name: str,
    phone_number: str,
    items: list,
    total_amount: float,
    order_type: str = "pickup",
    delivery_address: str = "",
    special_instructions: str = "",
) -> dict:
    print(
        f"Running Tool: place_order("
        f"customer='{customer_name}', "
        f"type='{order_type}', "
        f"total='${total_amount}', "
        f"items={[i['name'] for i in items]})"
    )

    if not items:
        return {"success": False, "error": "No items in order. Ask the customer what they would like."}

    for item in items:
        qty = item.get("quantity", 1)
        if not isinstance(qty, int) or qty < 1:
            item["quantity"] = 1

    not_found = []
    for item in items:
        if not item.get("price"):
            item["price"] = _lookup_price(item["name"])
        if not item.get("price"):
            not_found.append(item["name"])

    if not_found:
        return {
            "success": False,
            "error": (
                f"Item(s) not found on the menu: {', '.join(not_found)}. "
                "Tell the customer these items are not available and ask them to choose from the actual menu."
            ),
        }

    total_amount = sum(item["price"] * item.get("quantity", 1) for item in items)
    order_id = f"PS-{datetime.now().strftime('%H%M%S')}"
    wait_time = (
        "20-30 minutes" if order_type == "pickup"
        else "40-60 minutes" if order_type == "delivery"
        else "10-15 minutes"
    )

    n8n_url = os.getenv("N8N_WEBHOOK_URL", "")
    if n8n_url:
        payload = {
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
        }
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(n8n_url, json=payload)
        except Exception as e:
            print(f"n8n webhook failed (order still confirmed): {e}")

    return {
        "success": True,
        "order_id": order_id,
        "customer_name": customer_name,
        "phone_number": phone_number,
        "order_type": order_type,
        "items": items,
        "total_amount": total_amount,
        "wait_time": wait_time,
        "special_instructions": special_instructions,
        "message": (
            f"Order {order_id} confirmed. Say the words 'order confirmed' exactly. "
            f"Say 'Wait time {wait_time}' exactly. Never translate confirmed into "
            "Punjabi or Hindi, and never say pushti/pushtee/tasdeek/hogi/ho jayegi."
        ),
    }


# ── Register Tools ────────────────────────────────────────────────────────────

def get_tools(state: RestaurantState):
    async def transfer_call(reason: str) -> str:
        print(f"Running Tool: transfer_call(reason='{reason}')")
        state.transfer_requested = True
        state.transfer_reason = reason
        return (
            "Transfer initiated. Say exactly one warm sentence: "
            "'Let me connect you with our team right away.' "
            "Then stop speaking completely — do not say anything else."
        )

    async def select_language(language: str) -> str:
        print(f"Running Tool: select_language(language='{language}')")
        config = LANGUAGE_CONFIG.get(language.lower(), LANGUAGE_CONFIG["english"])
        state.tts_language = config["tts_language"]
        state.tts_voice = config["tts_voice"]
        return f"Language switched to {language}. Now respond in {language}."

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
        )
        if result.get("success"):
            state.confirmed_order = result
        return result

    return [
        (transfer_call_tool_description, transfer_call),
        (select_language_tool_description, select_language),
        (get_menu_tool_description, get_menu),
        (check_item_availability_tool_description, check_item_availability),
        (place_order_tool_description, place_order_and_notify),
    ]
