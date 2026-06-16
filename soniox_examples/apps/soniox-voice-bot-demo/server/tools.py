import json
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
from openai.types.chat import ChatCompletionFunctionToolParam
from rapidfuzz import fuzz, process

from clover import CloverError, CloverItemNotFoundError, get_client as _get_clover_client
from square_client import SquareError, SquareItemNotFoundError

# ── Load menu.json (single source of truth) ───────────────────────────────────

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

for _lang, _val in _BIZ.get("pronunciation", {}).items():
    if _lang in MENU_ITEM_PRONUNCIATIONS:
        MENU_ITEM_PRONUNCIATIONS[_lang][RESTAURANT_NAME] = _val

for _cat in _DATA["categories"]:
    for _item in _cat["items"]:
        for _lang, _val in _item.get("pronunciation", {}).items():
            if _val and _lang in MENU_ITEM_PRONUNCIATIONS:
                MENU_ITEM_PRONUNCIATIONS[_lang][_item["name"]] = _val

# ── STT terms: simplified item names for Soniox speech context ───────────────

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


# ── Per-call state with Soniox Engine Adapters ────────────────────────────────

class RestaurantState:
    """Mutable per-call state shared between tools and DynamicTTSProcessor."""
    def __init__(self, caller_phone: str = ""):
        self.tts_language = "en"
        self.tts_voice = "Maya"
        self.transfer_requested = False
        self.transfer_reason = ""
        self.caller_phone = caller_phone
        self.confirmed_order: dict | None = None
        self.pos_client = None  

    def get_soniox_v5_config(self) -> dict:
        """
        Provides the exact JSON structure required by the Soniox v5 Real-Time API.
        Your main connection pipeline should pull this dictionary when creating
        the WebSocket stream initialization context.
        """
        return {
            "model": "stt-rt-v5",
            "audio_format": "auto",
            "context": {
                "general": [
                    { "key": "domain", "value": "restaurant food ordering" },
                    { "key": "environment", "value": "telephony with real-world ambient background noise" },
                    { "key": "code_switching", "value": "enabled for English, Hindi, and Punjabi mixed terms" }
                ],
                "terms": STT_TERMS,
                "translation_terms": [
                    { "original": "ਹਾਂਜੀ", "translation": "yes" },
                    { "original": "ਹਾਂ ਜੀ", "translation": "yes" },
                    { "original": "ਬਿੱਲ", "translation": "receipt" },
                    { "original": "ਕੋਕ", "translation": "Coke" },
                    { "original": "ਪਾਣੀ", "translation": "water" },
                    { "original": "ਪਰੌਂਠਾ", "translation": "Paratha" },
                    { "original": "ਮੱਖਣ", "translation": "with butter" },
                    { "original": "ਸਮੋਸਾ", "translation": "Samosa" },
                    { "original": "ਹਾਂਜੀ", "translation": "yes" }
                ]
            }
        }


# ── Pronunciation guide injected into system prompt ───────────────────────────

def _get_pronunciation_guide(language: str) -> str:
    lang = language.strip().lower()

    if lang == "punjabi":
        items = MENU_ITEM_PRONUNCIATIONS["punjabi"]
        pa_name = items.get(RESTAURANT_NAME, "ਪ੍ਰਕਾਸ਼ Sweets")
        lines = " | ".join(f"{en} → {pa}" for en, pa in items.items())
        return (
            "\n## CRITICAL SPEECH SYNTHESIS (GURMUKHI)\n"
            f"Refer to the restaurant as '{pa_name}' always.\n"
            "Generate your verbal responses using Gurmukhi script for native dishes so Soniox v5 handles inflection correctly.\n"
            f"{lines}\n"
        )

    if lang == "hindi":
        items = MENU_ITEM_PRONUNCIATIONS["hindi"]
        hi_name = items.get(RESTAURANT_NAME, "प्रकाश Sweets")
        lines = " | ".join(f"{en} → {hi}" for en, hi in items.items())
        return (
            "\n## CRITICAL SPEECH SYNTHESIS (DEVANAGARI)\n"
            f"Refer to the restaurant as '{hi_name}' always.\n"
            "Generate your verbal responses using Devanagari script for native dishes so Soniox v5 handles inflection correctly.\n"
            f"{lines}\n"
        )

    items = MENU_ITEM_PRONUNCIATIONS["english"]
    en_name = items.get(RESTAURANT_NAME, "Pruh-kaash Sweets")
    lines = " | ".join(f"{name} → {ph}" for name, ph in items.items())
    return (
        "\n## ENGLISH PHONETIC MODIFIERS\n"
        f"Say the name as '{en_name}' naturally.\n"
        f"{lines}"
    )


# ── Conversational System Prompt Engine ───────────────────────────────────────

def get_system_message(language: str, caller_phone: str = "", pos_client=None) -> str:
    _client = pos_client if pos_client is not None else _get_clover_client()
    has_live_pos = "TRUE" if (_client is not None and _client.available) else "FALSE"

    if caller_phone:
        phone_instruction = f"We have their phone number ending in {caller_phone[-4:]}. Casually verify it near the end, don't read it out like a machine."
    else:
        phone_instruction = "Casually secure their phone digits toward the end of the conversation."

    language_lower = language.strip().lower()
    if language_lower == "auto":
        language_context = (
            "You are doing the initial greeting. Ask the customer immediately if they want to speak in English, Hindi, or Punjabi. "
            "The moment they respond or switch dialects, call `select_language` instantly before processing anything else."
        )
    elif language_lower == "punjabi":
        language_context = "The customer chose Punjabi. Respond organically using fluent Gurmukhi text. Keep specialized industry nouns (order, confirmed, pickup, delivery, minutes) in clean standard Latin text."
    elif language_lower == "hindi":
        language_context = "The customer chose Hindi. Respond organically using fluent Devanagari text. Keep specialized industry nouns (order, confirmed, pickup, delivery, minutes) in clean standard Latin text."
    else:
        language_context = "The customer chose English. Maintain a warm, friendly, helpful tone."

    return f"""You are Sierra — a warm, quick-witted, and genuinely helpful front-desk server at {RESTAURANT_NAME} in Canada. You talk exactly like a real human clerk taking an order at a busy counter—high energy, clear voice, casual affirmations, and completely free of automated formatting or structural jargon.

Today is {datetime.now().strftime("%A, %B %d, %Y")}. We are open from 11 AM to 10 PM.

{language_context}

## CRITICAL MULTI-LINGUAL CONVERSATIONAL FLOW
- NEVER use rigid checklists, structural outlines, or bullet points in your speech. Talk in continuous, short human phrases.
- Keep every single response down to 1 or 2 quick sentences (Max 120 characters total). Shorter blocks stream across the line instantly, eliminating awkward latency.
- Interruption Handling: If a customer changes their mind or cuts you off, drop your previous line instantly and acknowledge them with natural human phrases ('Got it', 'Perfect', 'Sure thing', 'No worries').
- Noise Remediation: If the transcript contains background restaurant noise, slamming doors, or broken characters, ignore the noise artifact completely. Use a fallback line like: 'Sorry about that noise, what was that last item?'
- BANNED TRANSLATIONS: Never translate these baseline system words into native phrases: 'order', 'confirmed', 'wait time', 'pickup', 'delivery', 'dine-in', 'address', 'total', 'dollars', 'minutes'. Never use structural robotic words like 'pushti' or 'tasdeek'.

## MANDATORY POS INTEGRATION GUARDRAILS (LIVE POS CHECKS: {has_live_pos})
- You are connected live to the Clover/Square register backend. 
- HARD RULE: You are BANNED from blindly accepting menu items. If a customer names a dish, you MUST explicitly invoke `check_item_availability` or `get_menu` first to verify that the item actually exists in our inventory system and to retrieve its current live price.
- If an item is flagged as unavailable by the system tool, do not add it to the cart. Tell the customer warmly that we are out of it today, and immediately recommend an alternative that is actually on the menu list.
- For hot savory foods, ask for their spice preference exactly once ('Mild, medium, or spicy?') and map it to the item notes. Skip this for desserts and sweet drinks.

{_get_pronunciation_guide(language)}

## CHECKOUT PROCEDURES
- Establish service type: Pickup (20-30 mins), Delivery (40-60 mins), Dine-in (10-15 mins). For delivery, get the address and confirm the primary street name naturally.
- Capture their name. Cross-reference their phone profile ({phone_instruction}).
- Call `place_order` to submit the validated payload directly to the live POS. Conclude the call by saying 'order confirmed' along with their specific wait time.
"""


# ── Dynamic Price Validation Systems ──────────────────────────────────────────

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
        "Chaat: Chaat Papdi $5.99 | Dahi Bhalla $5.99 | Samosa Choley $6.50\n"
        "Pakora: Mix Veg Pakora $8.50 | Paneer Pakora $11.50 | Gobi Pakora $10.50\n"
        "Desserts: Rasmalai (2 pcs) $4.00 | Garam Gulab Jamun (2 pcs) $3.00\n"
        "Drinks: Mango Lassi $4.99 | Masala Chai $1.99 | Coffee $2.99"
    )


def normalize_menu_category(value: str) -> str:
    value_lower = value.strip().lower()
    if value_lower in MENU:
        return value_lower
    return MENU_CATEGORY_ALIASES.get(value_lower, value_lower)


def normalize_item_name(value: str) -> str:
    value_lower = value.strip().lower()
    return ITEM_ALIASES.get(value_lower, value)


def _lookup_price(item_name: str, pos_client=None) -> float:
    _client = pos_client if pos_client is not None else _get_clover_client()
    if _client is not None and _client.available and _client.menu is not None:
        clover_item = _client.menu.lookup(item_name)
        if clover_item is not None:
            return clover_item.price_dollars

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

    all_names = [item["name"] for cat_items in MENU.values() for item in cat_items]
    result = process.extractOne(item_name, all_names, scorer=fuzz.token_sort_ratio)
    if result and result[1] >= 80:
        match_name = result[0]
        for cat_items in MENU.values():
            for item in cat_items:
                if item["name"] == match_name:
                    return item["price"]

    return 0.0


# ── Function Tools Schema ─────────────────────────────────────────────────────

transfer_call_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "transfer_call",
        "description": "Transfer call to live restaurant team for escalations, complaints, or complex inquiries.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "enum": ["customer_requested", "complaint", "catering", "allergy_or_certification", "comprehension_issue"],
                }
            },
            "required": ["reason"],
        },
    },
)

select_language_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "select_language",
        "description": "Switches conversation and speech synthesis language profiles dynamically.",
        "parameters": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "enum": ["english", "hindi", "punjabi"]}
            },
            "required": ["language"],
        },
    },
)

get_menu_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "get_menu",
        "description": "Queries menu category lists from live POS systems.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["all", "all_snacks", "snacks", "samosa", "classic", "chaat", "pakora", "desserts", "beverages", "drinks", "sides"],
                }
            },
            "required": ["category"],
        },
    },
)


async def get_menu(category: str, pos_client=None) -> dict:
    category_norm = normalize_menu_category(category)
    _client = pos_client if pos_client is not None else _get_clover_client()
    
    if _client is not None and _client.available and _client.menu is not None:
        if category_norm == "all":
            all_items = _client.menu.all_items()
            by_cat: dict[str, list] = {}
            for item in all_items:
                cat = item.category_name or "Other"
                by_cat.setdefault(cat, []).append({"name": item.name, "price": item.price_dollars})
            return {"categories": by_cat, "info": BUSINESS_INFO}

        clover_items = _client.menu.get_category(category_norm.replace("_", " "))
        if clover_items:
            return {
                "category": category_norm,
                "items": [{"name": i.name, "price": i.price_dollars} for i in clover_items],
            }

    if category_norm == "all":
        summary = {cat: [item["name"] for item in items] for cat, items in MENU.items()}
        return {"categories": summary, "info": BUSINESS_INFO}

    if category_norm in MENU:
        return {"category": category_norm, "items": MENU[category_norm]}

    return {"error": "Category not found"}


check_item_availability_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "check_item_availability",
        "description": "Mandatory live inventory availability lookups. Execute whenever a customer requests any item.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string"}
            },
            "required": ["item_name"],
        },
    },
)


async def check_item_availability(item_name: str, pos_client=None) -> dict:
    _client = pos_client if pos_client is not None else _get_clover_client()
    if _client is not None and _client.available and _client.menu is not None:
        clover_item = _client.menu.lookup(item_name)
        if clover_item is not None:
            return {"available": True, "item": clover_item.name, "price": clover_item.price_dollars, "category": clover_item.category_name}
        return {"available": False, "message": f"'{item_name}' is not in the live register system."}

    canonical_name = normalize_item_name(item_name)
    search_lower = canonical_name.strip().lower()

    for cat, cat_items in MENU.items():
        for item in cat_items:
            if item["name"].lower() == search_lower:
                return {"available": True, "item": item["name"], "price": item["price"], "category": cat}

    price = _lookup_price(item_name, pos_client=pos_client)
    if price:
        return {"available": True, "item": canonical_name, "price": price}

    return {"available": False, "message": f"'{item_name}' is not in our system inventory records."}


place_order_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "place_order",
        "description": "Submits validated, confirmed items directly to the POS network system.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {"type": "string"},
                "phone_number": {"type": "string"},
                "order_type": {"type": "string", "enum": ["dine_in", "pickup", "delivery"]},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "price": {"type": "number"},
                            "notes": {"type": "string"},
                        },
                        "required": ["name", "quantity", "price"],
                    },
                },
                "total_amount": {"type": "number"},
                "delivery_address": {"type": "string"},
                "special_instructions": {"type": "string"},
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
    pos_client=None,
) -> dict:
    if not items:
        return {"success": False, "error": "Order payload empty."}

    not_found = []
    for item in items:
        if not item.get("price"):
            item["price"] = _lookup_price(item["name"], pos_client=pos_client)
        if not item.get("price"):
            not_found.append(item["name"])

    if not_found:
        return {"success": False, "error": f"Item(s) missing from active records: {', '.join(not_found)}."}

    total_amount = sum(item["price"] * item.get("quantity", 1) for item in items)
    wait_time = "20-30 minutes" if order_type == "pickup" else "40-60 minutes" if order_type == "delivery" else "10-15 minutes"

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
        except (CloverItemNotFoundError, SquareItemNotFoundError) as exc:
            return {"success": False, "error": f"Item '{exc.item_name}' could not be resolved inside active POS maps."}
        except (CloverError, SquareError) as exc:
            print(f"POS connection fallback triggered: {exc}")

    order_id = pos_order_id or f"PS-{datetime.now().strftime('%H%M%S')}"

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
        except Exception:
            pass

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
        "message": f"Order {order_id} confirmed. Explicitly state the exact tokens 'order confirmed' and wait time '{wait_time}'. Do not use native switch translations.",
    }


# ── Orchestration Pipeline Registration ───────────────────────────────────────

def get_tools(state: RestaurantState):
    async def transfer_call(reason: str) -> str:
        state.transfer_requested = True
        state.transfer_reason = reason
        return "Transfer active. Say: 'Let me connect you with our team right away.' and drop connection hooks."

    async def select_language(language: str) -> str:
        config = LANGUAGE_CONFIG.get(language.lower(), LANGUAGE_CONFIG["english"])
        state.tts_language = config["tts_language"]
        state.tts_voice = config["tts_voice"]
        return f"Context updated. Continue speaking fluidly in {language}."

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
        (transfer_call_tool_description, transfer_call),
        (select_language_tool_description, select_language),
        (get_menu_tool_description, get_menu_for_pos),
        (check_item_availability_tool_description, check_availability_for_pos),
        (place_order_tool_description, place_order_and_notify),
    ]