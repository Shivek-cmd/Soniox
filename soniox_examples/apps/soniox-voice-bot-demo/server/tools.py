import json
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
from openai.types.chat import ChatCompletionFunctionToolParam
from rapidfuzz import fuzz, process

from clover import CloverError, CloverItemNotFoundError, get_client as _get_clover_client

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
    elif language_lower == "auto":
        language_context = (
            "The opening greeting just asked the customer to choose English, Hindi, or Punjabi. "
            "Their very first message will be their language choice — it has already been handled, so go straight to helping them order. "
            "Match whatever language they are using: "
            "Punjabi → Gurmukhi script with English nouns. "
            "Hindi → Devanagari script with English nouns. "
            "English → casual warm English. "
            "If they switch language mid-call, call `select_language` immediately."
        )
    else:
        language_context = (
            "The customer has selected ENGLISH. The opening greeting has already been said — do NOT greet again or ask which language they prefer. "
            "Respond in English only. Go straight to helping them order."
        )

    return f"""You are Sierra — a voice assistant at {RESTAURANT_NAME}, a Punjabi Indian sweets and snacks restaurant in Canada. You are female. You know this food inside out, you love your job, and you genuinely enjoy helping people eat well. Warm, quick, a little playful — like a real person at the counter, not a bot reading from a screen.

Today is {datetime.now().strftime("%A, %B %d, %Y")}. Hours: 11 AM – 10 PM daily.

{language_context}

Every response is 1–2 sentences. Phone call only — no lists, no emojis. Sound like a person.
Punjabi: 60% Gurmukhi + English nouns. Hindi: Devanagari + English nouns. English: casual and warm.


## TTS SCRIPT — HARD RULE

The TTS reads your text exactly as written. Wrong script = broken audio.
Punjabi → Gurmukhi only. Hindi → Devanagari only. English → Latin only.
These words stay in English always, even mid-Punjabi or mid-Hindi:
order, confirmed, wait time, pickup, delivery, dine-in, address, phone number, name, total, dollars, minutes, menu, special instructions, allergy, mild, medium, spicy.

{_get_pronunciation_guide(language)}

Feminine forms always: Punjabi "ਕਰ ਸਕਦੀ ਹਾਂ" not "ਕਰ ਸਕਦਾ ਹਾਂ" | Hindi "कर सकती हूँ" not "कर सकता हूँ"
Respect always: "ਹਾਂਜੀ" not "ਹਾਂ" | "ਤੁਹਾਡਾ" not "ਤੇਰਾ"
Numbers/names always in English: phone numbers digit by digit, names confirmed by spelling.
Punjabi/Hindi quantities: ek/ਇੱਕ=1, do/ਦੋ=2, teen/ਤਿੰਨ=3, char/ਚਾਰ=4, paanch/ਪੰਜ=5, chhe/ਛੇ=6, saat/ਸੱਤ=7, aath/ਅੱਠ=8, nau/ਨੌਂ=9, das/ਦਸ=10.


## HOW THE CALL GOES

Greeting is done, language is set — go straight to taking the order. Ask what they are in the mood for, suggest 2–4 things. Build the order naturally. If the order includes any savory hot food (fried snacks, chaat, mains, burgers, paranthas), ask for spice level once using EXACTLY these English words — never translate them: "Mild, medium, or spicy?" Set the answer as `notes` on each savory item. Skip for desserts, drinks, and sides. Upsell once or twice max — drop it the moment they say no. Once the order is set: ask pickup, delivery, or dine-in. If delivery, get their address and confirm it back. Ask for special instructions, their name (confirm spelling), and phone number ({phone_instruction}). Give a quick recap, confirm, then call `place_order`. Close with the wait time.

Wait times: pickup 20–30 min | delivery 40–60 min | dine-in 10–15 min.
Always say "order confirmed" — never "pushti", "tasdeek", "hogi", "ho jayegi".

If customer switches language mid-call → call `select_language` immediately, then respond in their new language.
If you don't understand → ask once to repeat, then guess and confirm once. If still stuck → call `transfer_call`, say you're connecting them to a team member, and stop.
"stop", "wait", "hold on", "no", "yes", "okay" are normal replies — never count those as comprehension failures.


## SERVING SIZES

Sold per ORDER not per piece — 1 order of "Aloo Samosa (2 pcs)" = 2 samosas:
Aloo Samosa (2 pcs), Noodle Samosa (2 pcs), Rasmalai (2 pcs), Kesar Rasmalai (6 pcs), Garam Gulab Jamun (2 pcs), Rasgulla (2 pcs), Tawa Tikki (2 pcs), Aloo Besan Tikki (2 pcs), Shimla Mirch Pakora (2 pcs), Aloo Bread Pakora (2 pcs), Bread Roll (2 pcs), Butter (2 pcs).
Halwa / Gajrela / Dahi / Raita / Choley → sold by 8oz container.
In `place_order` use ORDER count: customer wants 4 samosas → {{"name": "Aloo Samosa (2 pcs)", "quantity": 2, "price": 3.00}}


## PRICES

{_get_prices_section()}


## TOOLS

`get_menu(category)` — when they want to browse a category ("what desserts do you have?")
`check_item_availability(item_name)` — when unsure an item exists
`select_language(language)` — immediately when customer switches language
`place_order(customer_name, phone_number, items, total_amount, order_type, delivery_address, special_instructions)` — after confirmation; delivery_address="" and special_instructions="" if not applicable
`transfer_call(reason)` — immediately, before responding, when: customer wants a human/manager | complaint or refund | catering 10+ people | halal/allergen questions | table reservation | 2 failed comprehension attempts. Say the handoff line once, then stop.

Pure vegetarian restaurant — no meat, chicken, beef. Off-menu requests: apologize briefly and suggest 1–2 similar items. Table reservations: not taken by phone — walk in or transfer to staff.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_prices_section() -> str:
    """Build the ## PRICES block from Clover live cache, or fall back to static."""
    _client = _get_clover_client()
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

    # Static fallback — used when Clover is unavailable at session start
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
    value_lower = value.strip().lower()
    if value_lower in MENU:
        return value_lower
    return MENU_CATEGORY_ALIASES.get(value_lower, value_lower)


def normalize_item_name(value: str) -> str:
    value_lower = value.strip().lower()
    return ITEM_ALIASES.get(value_lower, value)


def _lookup_price(item_name: str) -> float:
    """Resolve item name to price using Clover cache first, then 4-level static fallback.

    0. Clover live cache            — always up to date if client is running
    1. ITEM_ALIASES exact lookup    — known spelling variants
    2. Exact case-insensitive match — canonical names as-is
    3. All-tokens subset match      — handles word reorder, extra words
    4. rapidfuzz token_sort_ratio   — handles plurals, typos, STT drift
    """
    # 0. Clover live cache (authoritative price source)
    _client = _get_clover_client()
    if _client is not None and _client.available and _client.menu is not None:
        clover_item = _client.menu.lookup(item_name)
        if clover_item is not None:
            return clover_item.price_dollars

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
    category_norm = normalize_menu_category(category)

    # ── Clover live cache (source of truth when available) ────────────────────
    _client = _get_clover_client()
    if _client is not None and _client.available and _client.menu is not None:
        if category_norm == "all":
            all_items = _client.menu.all_items()
            by_cat: dict[str, list] = {}
            for item in all_items:
                cat = item.category_name or "Other"
                by_cat.setdefault(cat, []).append({"name": item.name, "price": item.price_dollars})
            return {"categories": by_cat, "info": BUSINESS_INFO}

        if category_norm == "all_snacks":
            snack_queries = ["samosa", "chaat", "pakora", "bread pakora", "burger sandwich"]
            seen: set[str] = set()
            items: list[dict] = []
            for q in snack_queries:
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

    # ── Fallback: static menu.json ────────────────────────────────────────────
    if category_norm == "all":
        summary = {cat: [item["name"] for item in items] for cat, items in MENU.items()}
        return {"categories": summary, "info": BUSINESS_INFO}

    if category_norm == "all_snacks":
        snacks = (
            MENU["samosa"] + MENU["chaat"] + MENU["pakora"]
            + MENU["bread_pakora"] + MENU["burger_sandwich"]
        )
        return {"category": category_norm, "items": snacks}

    if category_norm in MENU:
        return {"category": category_norm, "items": MENU[category_norm]}

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

    # Clover live cache — authoritative when available
    _client = _get_clover_client()
    if _client is not None and _client.available and _client.menu is not None:
        clover_item = _client.menu.lookup(item_name)
        if clover_item is not None:
            return {
                "available": True,
                "item": clover_item.name,
                "price": clover_item.price_dollars,
                "category": clover_item.category_name,
                "description": "",
            }
        return {
            "available": False,
            "message": (
                f"'{item_name}' is not on our menu. "
                "Tell the customer this item is unavailable and suggest a similar one."
            ),
        }

    # Clover unavailable — fall back to static menu.json
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
                            "notes": {"type": "string", "description": "Per-item note, e.g. spice level: 'mild', 'medium', 'spicy'. Empty string if none."},
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
    wait_time = (
        "20-30 minutes" if order_type == "pickup"
        else "40-60 minutes" if order_type == "delivery"
        else "10-15 minutes"
    )

    # ── Create order in Clover POS ────────────────────────────────────────────
    clover_order_id: str | None = None
    _client = _get_clover_client()
    if _client is not None and _client.available:
        try:
            clover_order = await _client.create_order(
                order_type=order_type,
                items=items,
                customer_name=customer_name,
                phone_number=phone_number,
                special_instructions=special_instructions,
                delivery_address=delivery_address,
            )
            clover_order_id = clover_order.id
            print(f"Clover order created: {clover_order_id}")
        except CloverItemNotFoundError as exc:
            return {
                "success": False,
                "error": (
                    f"Item '{exc.item_name}' could not be matched in the POS. "
                    "Ask the customer to clarify the item name."
                ),
            }
        except CloverError as exc:
            # Network/API failure — fall through to n8n-only path so order still confirms
            print(f"Clover order creation failed (falling back to n8n): {exc}")

    order_id = clover_order_id or f"PS-{datetime.now().strftime('%H%M%S')}"

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
