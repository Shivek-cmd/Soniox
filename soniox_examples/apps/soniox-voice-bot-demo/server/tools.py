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

MENU: dict[str, list[dict]] = {
    cat["id"]: cat["items"]
    for cat in _DATA["categories"]
}

MENU_CATEGORY_ALIASES: dict[str, str] = _DATA["category_aliases"]

_NATIVE_RE = re.compile(r"[ऀ-ॿ਀-੿]")

ITEM_ALIASES: dict[str, str] = {}
for _cat in _DATA["categories"]:
    for _item in _cat["items"]:
        for _term in _item.get("terms", []):
            if not _NATIVE_RE.search(_term):
                ITEM_ALIASES[_term.lower()] = _item["name"]

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

# ── Soniox v5 Dynamic Real-Time Mappings ──────────────────────────────────────

SONIOX_V5_TRANSLATION_TERMS = [
    {"original": "ਕੋਕ", "translation": "Coke"},
    {"original": "ਪਾਣੀ", "translation": "water"},
    {"original": "ਬਿੱਲ", "translation": "receipt"},
    {"original": "ਹਾਂਜੀ", "translation": "yes"},
    {"original": "ਪਰੌਂਠਾ", "translation": "Paratha"},
    {"original": "ਮੱਖਣ", "translation": "with butter"},
    {"original": "ਸਮੋਸਾ", "translation": "Samosa"},
    {"original": "ਚਾਹ", "translation": "Chai"}
]

LANGUAGE_CONFIG = {
    "english": {"tts_language": "en", "tts_voice": "Maya"},
    "hindi":   {"tts_language": "hi", "tts_voice": "Maya"},
    "punjabi": {"tts_language": "pa", "tts_voice": "Maya"},
}

# ── Per-call state ────────────────────────────────────────────────────────────

class RestaurantState:
    def __init__(self, caller_phone: str = ""):
        self.tts_language = "en"
        self.tts_voice = "Maya"
        self.transfer_requested = False
        self.transfer_reason = ""
        self.caller_phone = caller_phone
        self.confirmed_order: dict | None = None
        self.pos_client = None  

# ── Pronunciation guides ──────────────────────────────────────────────────────

def _get_pronunciation_guide(language: str) -> str:
    lang = language.strip().lower()

    if lang == "punjabi":
        items = MENU_ITEM_PRONUNCIATIONS["punjabi"]
        pa_name = items.get(RESTAURANT_NAME, "ਪ੍ਰਕਾਸ਼ Sweets")
        lines = " | ".join(f"{en} → {pa}" for en, pa in items.items())
        return (
            "\n## CRITICAL TTS SPEECH CONFIG (GURMUKHI)\n"
            f"Always refer to the restaurant as '{pa_name}'.\n"
            "Generate your verbal speech using Gurmukhi script for all native dishes so Soniox v5 handles inflection organically. "
            "Keep technical tool call payloads strictly in standard English text.\n"
            f"{lines}\n"
        )

    if lang == "hindi":
        items = MENU_ITEM_PRONUNCIATIONS["hindi"]
        hi_name = items.get(RESTAURANT_NAME, "प्रकाश Sweets")
        lines = " | ".join(f"{en} → {hi}" for en, hi in items.items())
        return (
            "\n## CRITICAL TTS SPEECH CONFIG (DEVANAGARI)\n"
            f"Always refer to the restaurant as '{hi_name}'.\n"
            "Generate your verbal speech using Devanagari script for all native dishes so Soniox v5 handles inflection organically. "
            "Keep technical tool call payloads strictly in standard English text.\n"
            f"{lines}\n"
        )

    items = MENU_ITEM_PRONUNCIATIONS["english"]
    en_name = items.get(RESTAURANT_NAME, "Pruh-kaash Sweets")
    lines = " | ".join(f"{name} → {ph}" for name, ph in items.items())
    return (
        "\n## ENGLISH PHONETIC INJECTIONS\n"
        f"Say the brand name as '{en_name}' naturally.\n"
        f"{lines}"
    )

# ── System Message ────────────────────────────────────────────────────────────

def get_system_message(language: str, caller_phone: str = "", pos_client=None) -> str:
    if caller_phone:
        phone_instruction = (
            f"The caller's phone number is noted as {caller_phone}. "
            "When confirming details, casually drop it into conversation naturally (e.g., 'And we still have your number ending in [last 4 digits], right?'). "
            "Do not read it back like a monotonous computer program unless they specifically request a modification."
        )
    else:
        phone_instruction = "Snag their phone number casually toward the end of the interaction to tie it to the order profile."

    language_lower = language.strip().lower()
    if language_lower == "punjabi":
        language_context = (
            "The caller is using Punjabi. Skip greetings and dive straight into organizing their order. "
            "Respond organically using fluent Gurmukhi combined with conversational English industry nouns (order, confirmed, pickup, delivery)."
        )
    elif language_lower == "hindi":
        language_context = (
            "The caller is using Hindi. Skip repetitive greetings and dive straight into organizing their order. "
            "Respond organically using fluent Devanagari combined with conversational English industry nouns (order, confirmed, pickup, delivery)."
        )
    elif language_lower == "auto":
        language_context = (
            "The initial language selection handshake has passed. Analyze incoming tokens fluidly. "
            "Match the user's selected language flow instantly: Punjabi (Gurmukhi + English nouns), Hindi (Devanagari + English nouns), English (Warm, casual). "
            "If they execute a clear dialect pivot mid-sentence, fire `select_language` instantly."
        )
    else:
        language_context = "The caller is using English. Keep things smooth, conversational, and warm."

    return f"""You are Sierra — a real, warm, and fast front-desk assistant at {RESTAURANT_NAME} in Canada. You're quick, enthusiastic, and talk exactly like a helpful human server at the physical counter. You don't repeat yourself, you don't list off menus like a robot, and you never use structured text templates or emojis.

Today is {datetime.now().strftime("%A, %B %d, %Y")}. We're open from 11 AM to 10 PM.

{language_context}

## REAL HUMAN CONVERSATION PRINCIPLES (LATENCY & NOISE REMEDIATION)
1. Keep responses ultra-short (1-2 brief sentences max, under 120 characters total). Shorter lines guarantee faster real-time streaming over WebSockets.
2. Interruption Friendly: Use natural transitional markers ('Got it', 'Perfect', 'Sure thing', 'No worries') to acknowledge changes immediately when a customer cuts you off.
3. Noise Mitigation: If an incoming transcription contains random gibberish, broken characters, or ambient restaurant clanking noise, disregard the noise artifact seamlessly. Smoothly guide the customer back with a quick, human prompt ('Sorry about that, what was that last item?').
4. Avoid Text Lists: Never read choices out in an index format. Say things like, 'We've got some great samosas, chaat papdi, or chole bhatura—what sounds good?'

## TTS SCRIPTING GATEWAYS
- Punjabi -> Gurmukhi only. Hindi -> Devanagari only. English -> Latin characters only.
- Never translate these conversational anchor words: order, confirmed, wait time, pickup, delivery, dine-in, address, total, dollars, minutes.
- Always implement natural feminine honorific forms (Punjabi: "ਕਰ ਸਕਦੀ ਹਾਂ" | Hindi: "कर सकती हूँ") and respectful pronouns ("ਹਾਂਜੀ", "ਤੁਹਾਡਾ").
- Keep numbers conversational. When confirming quantities, use clear, native tokens (e.g., 'Two garlic naan' or 'ਦੋ ਪਰੌਂਠੇ').

{_get_pronunciation_guide(language)}

## ORDER ORCHESTRATION PIPELINE
- Skip redundant greetings. Ask what they're craving, throw out 1 or 2 quick mouthwatering recommendations, and log things.
- For hot savory foods (chaat, paranthas, mains), ask for spice preference exactly once per item: 'Mild, medium, or spicy?' and bind it to the item notes. Skip this for desserts and sweet drinks.
- Keep upselling to a minimum—suggest one item that pairs well (like a Mango Lassi with a spicy dish), and drop it instantly if they decline.
- Gather receipt paths: Pickup (20-30 min), Delivery (40-60 min), Dine-in (10-15 min). For delivery, get the address and repeat the key street name back quickly to confirm.
- Wrap up by getting their name, cross-referencing their phone profile ({phone_instruction}), and trigger `place_order`.
- Final Handoff Sign-off: Always say 'order confirmed' along with their wait time. Never use overly formal localized translations like 'pushti', 'tasdeek', or 'ho jayegi'.

## SYSTEM STABILITY INDICES
- If you encounter a critical customer service anomaly (complaints, catering requirements for 10+ people, table reservations, complex allergen matrices, or if you both get completely stuck after 2 attempts), fire `transfer_call` instantly and pass the line to the physical restaurant staff with a single short handoff sentence.

## INTEGRATED POS LIVE CACHE
{_get_prices_section(pos_client=pos_client)}
"""

# ── Helper Data Accessors ─────────────────────────────────────────────────────

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
        "Pakora: Mix Veg Pakora $8.50 | Paneer Pakora $11.50 | Gobi Pakora $10.50\n"
        "Desserts: Rasmalai (2 pcs) $4.00 | Kesar Rasmalai (6 pcs) $5.99 | Garam Gulab Jamun (2 pcs) $3.00\n"
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

# ── Tool Definitions ──────────────────────────────────────────────────────────

transfer_call_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "transfer_call",
        "description": "Transfer call to live restaurant team for escalations, reservations, or complex inquiries.",
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
        "description": "Switches tracking context and voice synthesis to English, Hindi, or Punjabi dynamically.",
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
        "description": "Queries menu structural breakdowns or specific category arrays.",
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
        "description": "Validates existence and tracks live pricing variables for an isolated menu entity.",
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

    canonical_name = normalize_item_name(item_name)
    search_lower = canonical_name.strip().lower()

    for cat, cat_items in MENU.items():
        for item in cat_items:
            if item["name"].lower() == search_lower:
                return {"available": True, "item": item["name"], "price": item["price"], "category": cat}

    price = _lookup_price(item_name, pos_client=pos_client)
    if price:
        return {"available": True, "item": canonical_name, "price": price}

    return {"available": False, "message": "Item unavailable. Suggest a localized substitute gracefully."}

place_order_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "place_order",
        "description": "Commits confirmed item array directly to live POS infrastructure data tunnels.",
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

    for item in items:
        if not item.get("price"):
            item["price"] = _lookup_price(item["name"], pos_client=pos_client)

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
            return {"success": False, "error": f"Item '{exc.item_name}' mismatch inside POS catalog logic."}
        except (CloverError, SquareError) as exc:
            print(f"Primary POS pipeline write failure, failing over to backup n8n stream: {exc}")

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
        except Exception as e:
            print(f"Data infrastructure warning - Backup webhook unreachable: {e}")

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
        "message": f"Order {order_id} confirmed. Explicitly voice 'order confirmed' along with the wait time '{wait_time}' directly.",
    }

# ── Dynamic Pipeline Binding Execution Matrices ───────────────────────────────

def get_tools(state: RestaurantState):
    async def transfer_call(reason: str) -> str:
        state.transfer_requested = True
        state.transfer_reason = reason
        return "Transfer active. Say: 'Let me grab someone on our team to help you with that right away.' and yield audio pipeline."

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