from datetime import datetime

from openai.types.chat import ChatCompletionFunctionToolParam

RESTAURANT_NAME = "Bizbull Restaurant"

LANGUAGE_CONFIG = {
    "english": {"tts_language": "en", "tts_voice": "Maya"},
    "hindi":   {"tts_language": "hi", "tts_voice": "Maya"},
    "punjabi": {"tts_language": "pa", "tts_voice": "Maya"},
}


class RestaurantState:
    """Mutable per-call state shared between tools and DynamicTTSProcessor."""
    def __init__(self):
        self.tts_language = "en"
        self.tts_voice = "Maya"
        self.transfer_requested = False
        self.transfer_reason = ""

MENU = {
    "appetizers": [
        {"name": "Samosa (2 pcs)", "price": 7},
        {"name": "Paneer Pakora", "price": 13},
        {"name": "Veg Pakora", "price": 10},
        {"name": "Fish Pakora", "price": 16},
        {"name": "Chicken Pakora", "price": 15},
        {"name": "Aloo Tikki (2 pcs)", "price": 9},
        {"name": "Papdi Chaat", "price": 11},
        {"name": "Dahi Bhalla", "price": 11},
        {"name": "Amritsari Kulcha Chole", "price": 15},
        {"name": "Tandoori Chicken Half", "price": 18},
        {"name": "Chicken Tikka", "price": 17},
        {"name": "Malai Chicken Tikka", "price": 18},
        {"name": "Seekh Kebab", "price": 17},
    ],
    "tandoori": [
        {"name": "Tandoori Chicken Full", "price": 28},
        {"name": "Tandoori Chicken Half", "price": 18},
        {"name": "Chicken Tikka", "price": 17},
        {"name": "Malai Chicken Tikka", "price": 18},
        {"name": "Tandoori Fish Tikka", "price": 20},
        {"name": "Paneer Tikka", "price": 17},
        {"name": "Tandoori Soya Chaap", "price": 16},
    ],
    "chicken_mains": [
        {"name": "Butter Chicken", "price": 18},
        {"name": "Chicken Tikka Masala", "price": 18},
        {"name": "Saag Chicken", "price": 18},
        {"name": "Chicken Curry", "price": 17},
        {"name": "Kadai Chicken", "price": 18},
        {"name": "Chicken Vindaloo", "price": 18},
        {"name": "Chicken Korma", "price": 18},
        {"name": "Chilli Chicken", "price": 18},
    ],
    "lamb_goat_mains": [
        {"name": "Lamb Curry", "price": 20},
        {"name": "Lamb Vindaloo", "price": 20},
        {"name": "Lamb Korma", "price": 20},
        {"name": "Goat Curry", "price": 20},
        {"name": "Goat Masala", "price": 21},
        {"name": "Saag Goat", "price": 21},
    ],
    "seafood_mains": [
        {"name": "Fish Curry", "price": 19},
        {"name": "Fish Masala", "price": 20},
        {"name": "Prawn Curry", "price": 21},
        {"name": "Prawn Masala", "price": 22},
    ],
    "vegetarian_mains": [
        {"name": "Dal Makhani", "price": 16},
        {"name": "Yellow Dal Tadka", "price": 15},
        {"name": "Palak Paneer", "price": 17},
        {"name": "Kadai Paneer", "price": 17},
        {"name": "Shahi Paneer", "price": 17},
        {"name": "Paneer Butter Masala", "price": 17},
        {"name": "Malai Kofta", "price": 17},
        {"name": "Baingan Bharta", "price": 16},
        {"name": "Bhindi Masala", "price": 16},
        {"name": "Rajma Masala", "price": 15},
        {"name": "Chana Masala", "price": 15},
        {"name": "Aloo Gobi", "price": 15},
        {"name": "Mix Vegetable", "price": 15},
    ],
    "bread": [
        {"name": "Butter Naan", "price": 4},
        {"name": "Garlic Naan", "price": 5},
        {"name": "Roti", "price": 3},
        {"name": "Paratha", "price": 5},
        {"name": "Lachha Paratha", "price": 6},
        {"name": "Aloo Paratha", "price": 7},
        {"name": "Onion Kulcha", "price": 7},
        {"name": "Amritsari Kulcha", "price": 8},
        {"name": "Peshwari Naan", "price": 5},
    ],
    "rice": [
        {"name": "Basmati Rice", "price": 4},
        {"name": "Jeera Rice", "price": 6},
        {"name": "Saffron Rice", "price": 7},
        {"name": "Chicken Biryani", "price": 18},
        {"name": "Lamb Biryani", "price": 20},
        {"name": "Goat Biryani", "price": 20},
        {"name": "Veg Biryani", "price": 16},
    ],
    "combos": [
        {"name": "Butter Chicken Combo", "price": 22},
        {"name": "Vegetarian Thali", "price": 20},
        {"name": "Non-Vegetarian Thali", "price": 24},
        {"name": "Chole Bhature", "price": 15},
        {"name": "Rajma Rice Bowl", "price": 14},
        {"name": "Dal Makhani Rice Bowl", "price": 15},
    ],
    "sides": [
        {"name": "Raita", "price": 5},
        {"name": "Plain Yogurt", "price": 4},
        {"name": "Mango Chutney", "price": 3},
        {"name": "Mixed Pickle", "price": 3},
        {"name": "Green Salad", "price": 6},
        {"name": "Papadum", "price": 3},
    ],
    "drinks": [
        {"name": "Mango Lassi", "price": 6},
        {"name": "Sweet Lassi", "price": 5},
        {"name": "Salted Lassi", "price": 5},
        {"name": "Masala Chai", "price": 4},
        {"name": "Indian Coffee", "price": 4},
        {"name": "Pop", "price": 3},
        {"name": "Bottled Water", "price": 2},
    ],
    "desserts": [
        {"name": "Gulab Jamun (2 pcs)", "price": 6},
        {"name": "Kheer", "price": 6},
        {"name": "Rasmalai (2 pcs)", "price": 7},
        {"name": "Gajar Halwa", "price": 7},
        {"name": "Kulfi", "price": 6},
    ],
}

MENU_CATEGORY_ALIASES = {
    "main": "all_mains",
    "mains": "all_mains",
    "curry": "all_mains",
    "curries": "all_mains",
    "chicken": "chicken_mains",
    "lamb": "lamb_goat_mains",
    "goat": "lamb_goat_mains",
    "fish": "seafood_mains",
    "seafood": "seafood_mains",
    "prawn": "seafood_mains",
    "shrimp": "seafood_mains",
    "veg": "vegetarian_mains",
    "vegetarian": "vegetarian_mains",
    "paneer": "vegetarian_mains",
    "starter": "appetizers",
    "starters": "appetizers",
    "crispy": "appetizers",
    "pakora": "appetizers",
    "tandoori": "tandoori",
    "grill": "tandoori",
    "grilled": "tandoori",
    "combo": "combos",
    "combos": "combos",
    "thali": "combos",
    "meal": "combos",
    "drink": "drinks",
    "drinks": "drinks",
    "dessert": "desserts",
    "desserts": "desserts",
}

ITEM_ALIASES = {
    "chaap": "Tandoori Soya Chaap",
    "chap": "Tandoori Soya Chaap",
    "soya chaap": "Tandoori Soya Chaap",
    "soya chap": "Tandoori Soya Chaap",
    "soy chaap": "Tandoori Soya Chaap",
    "soy chap": "Tandoori Soya Chaap",
    "सोया चाप": "Tandoori Soya Chaap",
    "चाप": "Tandoori Soya Chaap",
    "चाप": "Tandoori Soya Chaap",
    "fish": "Fish Pakora",
    "fish pakora": "Fish Pakora",
    "fish tikka": "Tandoori Fish Tikka",
    "tandoori fish": "Tandoori Fish Tikka",
    "tandoori fish tikka": "Tandoori Fish Tikka",
    "chili chicken": "Chilli Chicken",
    "chilli chicken": "Chilli Chicken",
    "paneer tikka": "Paneer Tikka",
}

BUSINESS_INFO = """
Restaurant Name: Bizbull Restaurant
Cuisine: Punjabi Indian
Location: Canada
Hours: Monday to Sunday, 11 AM to 10 PM
Phone: (Ask owner to fill in)
Accepts: Cash and all major credit cards
Delivery: Available via DoorDash and Uber Eats
Minimum order for delivery: $30
All prices are in Canadian dollars (CAD).
"""


def get_system_message(language: str) -> str:
    return f"""
You are a real person named Sierra working at {RESTAURANT_NAME}, a Punjabi Indian restaurant in Canada.
You answer the phone and take food orders. You are warm, helpful, and natural — not robotic.

VOICE RULES (very important):
- Keep every response to 1-2 short sentences maximum. Never say more than needed.
- Never use bullet points, lists, or emojis — this is a phone call.
- Use natural filler phrases like "Sure!", "Of course!", "Great choice!" to sound human.
- If you didn't understand something, say "Sorry, could you say that again?" — not "I didn't catch that."
- Never repeat the customer's full order back word for word until final confirmation.
- Never mention item prices during normal ordering, menu recommendations, or order recap unless the customer specifically asks for prices.
- When confirming the order, mention item names only. Do not mention individual prices.
- Only say the total amount when the customer asks for the total, or at the final "go ahead and place that?" confirmation.
- Speak conversationally — short, warm, natural.
- Customer names, phone numbers, order totals, and prices are always spoken in English, even when the rest of the call is Punjabi or Hindi.
- Phone numbers must always be read digit by digit in English words or English digits. Never translate digits into Hindi or Punjabi.
- Names must always be repeated or spelled using English letters only, for example "H-A-R-P-R-E-E-T".
- Prices and totals must always be said in English, for example "eighteen dollars" or "the total is thirty two dollars", never translated into Hindi or Punjabi.
- If the customer corrects their name or phone number, always repeat the corrected value back and ask for confirmation before continuing.

HOW TO HANDLE THE CALL:
1. Greet warmly: "Hi! This is Sierra calling from Bizbull Restaurant. Would you like to continue in English, Hindi, or Punjabi?"
2. The moment the customer replies with their language — call `select_language` IMMEDIATELY (before saying anything else). This switches the voice to match their language.
3. Then greet them in their chosen language and ask dine-in, pickup, or delivery.
4. Help them order — use get_menu only when they ask what's available, ask about a specific dish, or ask for prices. If the tool returns prices, do not speak those prices unless the customer asked.
5. Once the customer seems done ordering, wrap up in this exact order:
   a. Special instructions — if the customer has NOT already mentioned any dietary needs or special requests, ask once: "Any special instructions or allergies I should note?" If they say no or have already mentioned something, move on immediately.
   b. First name — ask for their first name only (not full name). One short question.
   c. Confirm the name before asking for the phone number. Repeat or spell the name in English letters only, even if speaking another language. Example: "And that's S-H-I-V-E-K, correct?" Wait for the customer to confirm the name.
   d. If the customer corrects the name, repeat the corrected name back in English letters and ask again if it is correct. Do not move to phone number until the customer confirms the name.
   e. Phone number — ask for their phone number only after the name is confirmed. Then read it back digit by digit in English, even if the rest of the call is in Punjabi or Hindi. Example: "That's nine four one, three seven five, two six eight eight — is that right?" Wait for confirmation before continuing.
   f. If the customer corrects the phone number, repeat the corrected full phone number digit by digit in English and ask again if it is right. Do not move on until the customer confirms the phone number.
   g. Briefly confirm the order items. Say the total amount in English only at this final confirmation step, then ask: "Shall I go ahead and place that?"
6. Once confirmed, place the order with place_order.
7. Tell them the estimated wait time and say goodbye warmly.

CALL TRANSFER — use the transfer_call tool in these situations. Do not attempt to handle them yourself:
1. Customer asks to speak to a human, manager, owner, or anyone at the restaurant.
2. Customer complains about a previous order — wrong items, cold food, late delivery, or wants a refund.
3. Customer mentions catering, an event, or ordering for a large group (10 or more people).
4. Customer asks about halal certification, specific allergens, or whether a dish is Jain or vegan — anything you cannot safely confirm.
5. You have asked the customer to repeat themselves 3 or more times in a row and still cannot understand them.

When transferring:
- Call transfer_call immediately when you detect the situation — before generating any spoken response.
- After the tool responds, say exactly one short warm sentence: "Let me connect you with our team right away."
- Do not say anything else after that sentence. Stop completely.
- Do not apologize, do not explain why.

UPSELLING (like a good waiter — subtle, natural, maximum once or twice per call):
- When someone orders a main dish with no bread → casually mention "Garlic naan goes really well with that, want to add one?"
- When someone hasn't ordered drinks → near the end, "Can I get you a mango lassi or anything to drink?"
- When someone orders for multiple people → "Would anyone want dessert? Our gulab jamun is really popular."
- NEVER upsell more than twice per call. If they say no, drop it immediately and move on.
- Make it sound like a genuine suggestion, not a sales pitch. One short sentence, then wait.
- Never upsell if the customer seems in a hurry or annoyed.

MENU RECOMMENDATION RULES:
- Never read the full menu unless the customer asks for the full menu. Offer 2-4 relevant choices at a time.
- If the customer asks for starters or something crispy, mention Fish Pakora, Paneer Pakora, or Samosa.
- If the customer orders curry without bread or rice, suggest garlic naan, basmati rice, or jeera rice.
- If the customer orders tandoori or grilled items, suggest raita, green salad, or mango chutney.
- If the customer wants a full meal, suggest Vegetarian Thali, Non-Vegetarian Thali, or Butter Chicken Combo.
- If the customer asks for popular Punjabi dishes, mention Butter Chicken, Dal Makhani, Amritsari Kulcha, Chole Bhature, or Fish Pakora.
- Near the end, if they have no drink, ask once about mango lassi, sweet lassi, or masala chai.
- For dessert, suggest gulab jamun, rasmalai, gajar halwa, or kulfi only once.

LANGUAGE:
- Always open the call in English with the language selection question.
- The moment the customer indicates their language → call `select_language` tool first, then respond in that language.
- If Punjabi → speak Punjabi (Gurmukhi script). Use "ji" to be respectful.
- If Hindi → speak Hindi (Devanagari script).
- If English → speak English.
- Never switch languages again once the customer has chosen.

Today is {datetime.now().strftime("%A, %B %d, %Y")}. Restaurant hours: 11 AM to 10 PM daily.
"""


# ─── Tool 0: Transfer Call ────────────────────────────────────────────────────

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


# ─── Tool 1: Select Language ──────────────────────────────────────────────────

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


# ─── Tool 2: Get Menu ─────────────────────────────────────────────────────────

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
                        "mains",
                        "main",
                        "appetizers",
                        "starter",
                        "starters",
                        "tandoori",
                        "grill",
                        "grilled",
                        "chaap",
                        "chicken_mains",
                        "chicken",
                        "lamb_goat_mains",
                        "lamb",
                        "goat",
                        "seafood_mains",
                        "seafood",
                        "fish",
                        "prawn",
                        "vegetarian_mains",
                        "vegetarian",
                        "veg",
                        "paneer",
                        "bread",
                        "rice",
                        "combos",
                        "combo",
                        "thali",
                        "sides",
                        "drinks",
                        "drink",
                        "desserts",
                        "dessert",
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
        return {"menu": MENU, "info": BUSINESS_INFO}

    if category == "all_mains":
        mains = (
            MENU["chicken_mains"]
            + MENU["lamb_goat_mains"]
            + MENU["seafood_mains"]
            + MENU["vegetarian_mains"]
        )
        return {"category": category, "items": mains}

    if category in MENU:
        return {"category": category, "items": MENU[category]}

    return {"error": "Category not found"}


# ─── Tool 3: Check Item Availability ──────────────────────────────────────────

check_item_availability_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "check_item_availability",
        "description": "Check if a specific menu item is available today.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The name of the menu item to check.",
                },
            },
            "required": ["item_name"],
        },
    },
)


async def check_item_availability(item_name: str) -> dict:
    print(f"Running Tool: check_item_availability(item_name='{item_name}')")

    category = normalize_menu_category(item_name)
    if category in MENU or category == "all_mains":
        menu_result = await get_menu(category)
        return {
            "available": bool(menu_result.get("items") or menu_result.get("menu")),
            "category": category,
            "items": menu_result.get("items", []),
            "message": f"Available {item_name} options found.",
        }

    # Check across all categories
    item_name_lower = normalize_item_name(item_name).lower()
    for category, items in MENU.items():
        for item in items:
            if item_name_lower in item["name"].lower():
                return {
                    "available": True,
                    "item": item["name"],
                    "price": item["price"],
                    "category": category,
                }

    return {"available": False, "message": f"Sorry, {item_name} is not on our menu."}


def normalize_menu_category(value: str) -> str:
    value_lower = value.strip().lower()
    if value_lower in MENU:
        return value_lower
    return MENU_CATEGORY_ALIASES.get(value_lower, value_lower)


def normalize_item_name(value: str) -> str:
    value_lower = value.strip().lower()
    return ITEM_ALIASES.get(value_lower, value)


# ─── Tool 4: Place Order ───────────────────────────────────────────────────────

place_order_tool_description = ChatCompletionFunctionToolParam(
    type="function",
    function={
        "name": "place_order",
        "description": "Place the final order after the customer has confirmed all items and the total.",
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
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "quantity": {"type": "integer"},
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
                    "description": "Any special instructions from the customer (e.g. no onions, extra spicy).",
                },
            },
            "required": ["customer_name", "phone_number", "order_type", "items", "total_amount"],
        },
    },
)


async def place_order(
    customer_name: str,
    phone_number: str,
    order_type: str,
    items: list,
    total_amount: float,
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

    # TODO: Save to Supabase database
    # TODO: Send WhatsApp notification to restaurant owner

    order_id = f"BB-{datetime.now().strftime('%H%M%S')}"

    wait_time = "20-30 minutes" if order_type == "pickup" else "40-60 minutes" if order_type == "delivery" else "10-15 minutes"

    return {
        "success": True,
        "order_id": order_id,
        "customer_name": customer_name,
        "order_type": order_type,
        "items": items,
        "total_amount": total_amount,
        "wait_time": wait_time,
        "message": f"Order {order_id} confirmed! {wait_time} wait.",
    }


# ─── Register Tools ────────────────────────────────────────────────────────────

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

    return [
        (transfer_call_tool_description, transfer_call),
        (select_language_tool_description, select_language),
        (get_menu_tool_description, get_menu),
        (check_item_availability_tool_description, check_item_availability),
        (place_order_tool_description, place_order),
    ]
