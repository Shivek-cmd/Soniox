import os
from datetime import datetime

import httpx
from openai.types.chat import ChatCompletionFunctionToolParam


RESTAURANT_NAME = "Parkash Sweets"
SPOKEN_RESTAURANT_NAME = "Prakaash Sweets"

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
    "samosa": [
        {"name": "Aloo Samosa (2 pcs)", "price": 3.00, "description": "Fried dough stuffed with spiced potato and peas."},
        {"name": "Noodle Samosa (2 pcs)", "price": 4.50, "description": "Fried dough stuffed with noodles and juicy veggies with soya sauce and vinegar."},
    ],
    "parkash_classic": [
        {"name": "Chole Bhatura", "price": 7.99, "description": "Chickpeas curry with two fried bhature."},
        {"name": "Choley Puri", "price": 7.99, "description": "Chickpeas curry with three puris."},
        {"name": "Aloo Puri", "price": 7.99, "description": "Tangy aloo curry with three puris."},
    ],
    "chaat": [
        {"name": "Chaat Papdi", "price": 5.99, "description": "Crispy chips with potatoes, onions, chickpeas, yogurt, mint and tamarind chutney."},
        {"name": "Dahi Bhalla", "price": 5.99, "description": "Soft lentil dumplings in chilled yogurt with tamarind chutney and spices."},
        {"name": "Samosa Choley", "price": 6.50, "description": "Two aloo samosas with spicy chickpeas, yogurt and chutney."},
        {"name": "Tawa Tikki Chaat", "price": 6.00, "description": "Crisp potato patty topped with yogurt, tamarind, mint sauce and salad."},
        {"name": "Tawa Tikki Choley", "price": 7.50, "description": "Crisp potato patty with chickpea curry, yogurt, tamarind, mint sauce and salad."},
        {"name": "Aloo Besan Tikki Chaat", "price": 5.00, "description": "Potato patty made with peas, onions, gram flour and spices with yogurt, tamarind and mint sauce."},
    ],
    "pakora": [
        {"name": "Mix Veg Pakora", "price": 8.50, "description": "Spinach fritters with gram flour, spices, cauliflower, onions, potatoes and spinach."},
        {"name": "Baingan Pakora", "price": 8.50, "description": "Thin slices of eggplant dipped in spiced gram flour batter and fried."},
        {"name": "Spring Roll", "price": 8.00, "description": "Cabbage, noodles, carrots and onions wrapped in a flaky crispy roll."},
        {"name": "Aloo Cutlet", "price": 10.50, "description": "Crispy mashed potato with spices and herbs."},
        {"name": "Parkash Platter", "price": 15.99, "description": "Assorted vegetable pakoras, paneer, gobi, aloo fingers, baingan, aloo cutlets, hara bara kababs, mushroom, bread rolls, dahi kabab and mirchi."},
        {"name": "Paneer Pakora", "price": 11.50, "description": "Indian cottage cheese pieces coated in spiced gram batter and deep fried."},
        {"name": "Mirchi Pakora", "price": 10.50, "description": "Stuffed green chili fritters with gram flour, spices and herbs."},
        {"name": "Hara Bara Kabab", "price": 10.50, "description": "Spinach, green peas and potatoes shaped into crisp pan-fried patties."},
        {"name": "Gobi Pakora", "price": 10.50, "description": "Cauliflower fritters with gram flour, spices and herbs."},
        {"name": "Dahi Kabab", "price": 9.00, "description": "Creamy yogurt patties with herbs, spices and flour, lightly pan fried."},
        {"name": "Mushroom Delux", "price": 9.00, "description": "Mushrooms dipped in spicy gram flour batter and fried crisp. Six pieces per order."},
        {"name": "Aloo Besan Tikki (2 pcs)", "price": 3.00, "description": "Crisp potato patties with peas, onions, gram flour and spices."},
        {"name": "Shimla Mirch Pakora", "price": 5.00, "description": "Capsicum rings filled with spiced potato stuffing and fried in gram flour batter. Two pieces per order."},
        {"name": "Aloo Finger", "price": 8.50, "description": "Golden brown crispy potato fingers."},
        {"name": "Tawa Tikki (2 pcs)", "price": 4.00, "description": "Golden fried potato patties, crisp outside and soft inside."},
    ],
    "bread_pakora": [
        {"name": "Aloo Bread Pakora", "price": 3.00, "description": "Spiced potato stuffing between two slices of white bread. Two pieces per order."},
        {"name": "Paneer Aloo Bread Pakora", "price": 5.00, "description": "Bread fritters with potato and paneer. Two pieces per order."},
        {"name": "Bread Roll", "price": 3.00, "description": "Crispy outside with tangy savory potato stuffing. Two pieces per order."},
    ],
    "burger_sandwich": [
        {"name": "Aloo Tikki Burger", "price": 6.50, "description": "Spiced potato patty with lettuce, sliced onions and spicy mayo."},
        {"name": "Noodle Burger", "price": 7.50, "description": "Spiced aloo patty with Asian-style noodles, cucumber, onion and signature mayo."},
        {"name": "Paneer Tikki Burger", "price": 8.50, "description": "Spicy marinated paneer tikki with lettuce, onions and signature sauce."},
        {"name": "Grilled Cheese Sandwich", "price": 5.50, "description": "Golden toasted bread with melted cheese."},
        {"name": "Super Veggie Sandwich", "price": 6.99, "description": "Red onion, capsicum, carrots, sweet corn, shredded cheese, spicy mayo, seasoning and oregano."},
        {"name": "Sweet Corn Sandwich", "price": 6.99, "description": "Sweet corn, shredded cheese, signature tangy sauce, seasoning and oregano."},
        {"name": "Paneer Mayo Sandwich", "price": 7.99, "description": "Paneer cubes, shredded cheese, sweet corn, capsicum, carrot, onion, spicy mayo, seasoning and oregano."},
        {"name": "Coleslaw Sandwich - Kids Size", "price": 5.00, "description": "White bread with eggless mayo, carrots, cabbage, black pepper and salt."},
        {"name": "Triple Layer Sandwich Add On", "price": 1.00, "description": "Add-on for sandwiches."},
    ],
    "parantha": [
        {"name": "Aloo Parantha", "price": 4.00, "description": "Flatbread stuffed with spiced mashed potatoes, served with mix pickle."},
        {"name": "Gobi Parantha", "price": 4.50, "description": "Flatbread stuffed with spiced grated cauliflower, served with mix pickle."},
        {"name": "Muli Parantha", "price": 4.50, "description": "Flatbread stuffed with spiced grated radish, served with mix pickle."},
        {"name": "Paneer Parantha", "price": 4.99, "description": "Flatbread stuffed with spiced Indian cottage cheese, served with mix pickle."},
        {"name": "Mix Parantha", "price": 4.99, "description": "Flatbread stuffed with potato, cauliflower, paneer and radish, served with mix pickle."},
    ],
    "desserts": [
        {"name": "Rasmalai (2 pcs)", "price": 4.00, "description": "Soft cheese dumplings soaked in creamy cardamom-saffron milk."},
        {"name": "Spongey Rasgulla (2 pcs)", "price": 3.00, "description": "Soft round dumplings in sugar syrup."},
        {"name": "Garam Gulab Jamun (2 pcs)", "price": 3.00, "description": "Fried dough balls with almond inside, served in warm sugar syrup."},
        {"name": "Moong Dal Halwa - 8 oz", "price": 5.50, "description": "Traditional dessert made from yellow moong dal, slow cooked with ghee, sugar and nuts."},
        {"name": "Garam Gajrela - 8 oz", "price": 4.50, "description": "Fresh carrots cooked in milk with sugar, almonds, cashews, mawa and cardamom."},
        {"name": "Kesar Rasmalai (6 pcs)", "price": 5.99, "description": "Paneer dumplings soaked in saffron milk."},
    ],
    "shake_faluda": [
        {"name": "Mango Shake", "price": 5.50},
        {"name": "Strawberry Shake", "price": 5.50},
        {"name": "Oreo Shake", "price": 5.50},
        {"name": "Chocolate Shake", "price": 5.50},
        {"name": "Vanilla Shake", "price": 5.50},
        {"name": "Mango Faluda", "price": 8.50},
        {"name": "Strawberry Faluda", "price": 8.50},
        {"name": "Vanilla Faluda", "price": 8.50},
    ],
    "beverages": [
        {"name": "Masala Chai", "price": 1.99},
        {"name": "Elachi Chai", "price": 2.99},
        {"name": "Gur Chai", "price": 2.99},
        {"name": "Dudh Patti", "price": 2.99},
        {"name": "Coffee - Indian Style", "price": 2.99},
        {"name": "Sweet Lassi", "price": 4.49},
        {"name": "Salty Lassi", "price": 4.49},
        {"name": "Mango Lassi", "price": 4.99},
        {"name": "Badam Milk", "price": 5.99},
    ],
    "sides": [
        {"name": "Butter (2 pcs)", "price": 0.99},
        {"name": "Dahi - 8 oz", "price": 2.99},
        {"name": "Raita - 8 oz", "price": 2.99},
        {"name": "Extra Bhatura", "price": 2.50},
        {"name": "Extra Puri", "price": 1.50},
        {"name": "Choley - 8 oz", "price": 2.99},
        {"name": "Mix Pickle - 2 oz", "price": 1.49},
        {"name": "Tamarind Sauce - 2 oz", "price": 1.00},
        {"name": "Mint Sauce - 2 oz", "price": 1.50},
    ],
}

MENU_CATEGORY_ALIASES = {
    "starter": "all_snacks",
    "starters": "all_snacks",
    "snack": "all_snacks",
    "snacks": "all_snacks",
    "classic": "parkash_classic",
    "parkash classic": "parkash_classic",
    "chaat": "chaat",
    "chat": "chaat",
    "samosa": "samosa",
    "samosas": "samosa",
    "pakora": "pakora",
    "pakoras": "pakora",
    "crispy": "pakora",
    "bread pakora": "bread_pakora",
    "bread": "bread_pakora",
    "burger": "burger_sandwich",
    "burgers": "burger_sandwich",
    "sandwich": "burger_sandwich",
    "sandwiches": "burger_sandwich",
    "parantha": "parantha",
    "paratha": "parantha",
    "parathas": "parantha",
    "paranthas": "parantha",
    "drink": "beverages",
    "drinks": "beverages",
    "beverage": "beverages",
    "beverages": "beverages",
    "chai": "beverages",
    "tea": "beverages",
    "lassi": "beverages",
    "shake": "shake_faluda",
    "shakes": "shake_faluda",
    "faluda": "shake_faluda",
    "falooda": "shake_faluda",
    "sweet": "desserts",
    "sweets": "desserts",
    "dessert": "desserts",
    "desserts": "desserts",
    "side": "sides",
    "sides": "sides",
}

ITEM_ALIASES = {
    "aloo samosa": "Aloo Samosa (2 pcs)",
    "regular samosa": "Aloo Samosa (2 pcs)",
    "noodle samosa": "Noodle Samosa (2 pcs)",
    "chole bhature": "Chole Bhatura",
    "chole bhatura": "Chole Bhatura",
    "choley bhatura": "Chole Bhatura",
    "chole puri": "Choley Puri",
    "choley puri": "Choley Puri",
    "papdi chaat": "Chaat Papdi",
    "papri chaat": "Chaat Papdi",
    "samosa chaat": "Samosa Choley",
    "samosa chole": "Samosa Choley",
    "samosa choley": "Samosa Choley",
    "tikki chaat": "Tawa Tikki Chaat",
    "tikki choley": "Tawa Tikki Choley",
    "tikki chole": "Tawa Tikki Choley",
    "veggie sandwich": "Super Veggie Sandwich",
    "mooli parantha": "Muli Parantha",
    "muli paratha": "Muli Parantha",
    "paneer paratha": "Paneer Parantha",
    "aloo paratha": "Aloo Parantha",
    "gobi paratha": "Gobi Parantha",
    "mix paratha": "Mix Parantha",
    "gulab jamun": "Garam Gulab Jamun (2 pcs)",
    "gajrela": "Garam Gajrela - 8 oz",
    "gajar halwa": "Garam Gajrela - 8 oz",
    "rasgulla": "Spongey Rasgulla (2 pcs)",
    "falooda": "Mango Faluda",
}

BUSINESS_INFO = """
Restaurant Name: Parkash Sweets
Cuisine: Punjabi Indian vegetarian sweets, snacks, chaat, pakora, paranthas, burgers, sandwiches, desserts and beverages
Locations shown on menu: Kapurthala and Edmonton
Hours: Monday to Sunday, 11 AM to 10 PM
Phone: (Ask owner to fill in)
Accepts: Cash and all major credit cards
Orders: dine-in, pickup, and delivery if available for the caller's location
All prices are in Canadian dollars (CAD).
"""


def get_system_message(language: str) -> str:
    return f"""
You are Sierra, and you work the phone counter at {RESTAURANT_NAME}, a Punjabi Indian sweets and snacks restaurant in Canada. You grew up around this kind of food — you know the menu inside out, you have your own favourites (the Chole Bhatura and Rasmalai are honestly hard to beat), and you genuinely love helping people find something delicious. You're warm, a little chatty, always in a good mood, and you make every caller feel like they're talking to a friend who happens to know all the best things to order.

You are female. Always use feminine first-person in Hindi/Punjabi: "main kar sakti hoon", "main chahti hoon", "ਮੈਂ ਕਰ ਸਕਦੀ ਹਾਂ". Never use masculine forms.

---

TONE & ENERGY

Speak the way a cheerful, warm counter person does — excited about the food, patient with questions, never rushed or robotic. Keep every response short (1–2 sentences). You're on a phone call, so no bullet points, no lists, no emojis — just natural, flowing conversation. Be the highlight of their day.

---

LANGUAGE

Open every call in English and ask which language they'd like. The moment they reply — call `select_language`, then match their language for the rest of the call. Whichever language they pick at the start, stay in that language. Don't switch unless they switch first.

Mix English words naturally into Punjabi and Hindi — the way people actually speak. Everyday words like order, ready, pickup, delivery, dine-in, wait time, total, name, phone number, special instructions, allergy, and "order confirmed" always stay in English, even mid-Punjabi or mid-Hindi sentence. This isn't a rule — it's just how people talk.

Speak Punjabi and Hindi the way a young Canadian Punjabi person would — relaxed, warm, peppered with English. Avoid overly formal or old-fashioned words.

Numbers and digits are always spoken in English — phone numbers digit by digit ("nine, four, one…"), quantities in English numerals ("2 Chole Bhatura, 4 Mango Lassi"). Never use Punjabi or Hindi digit words like nau, chaar, teen when saying numbers out loud. But do understand them when a customer uses them: ek=1, do=2, teen=3, char=4, paanch=5, chhe=6, saat=7, aath=8, nau=9, das=10.

Customer names are always spelled back in English letters: "That's H-A-R-P-R-E-E-T, right?" Prices, if asked, are always in English: "eighteen dollars."

If a customer corrects their name or number, warmly repeat the corrected version back before moving on.

---

MENU KNOWLEDGE

You know this menu like the back of your hand. When someone's figuring out what they want, offer 2–4 options that fit their mood — don't recite the whole menu unless they ask for it.

Snacks / crispy: Aloo Samosa, Paneer Pakora, Mix Veg Pakora, Bread Roll
Chaat: Chaat Papdi, Samosa Choley, Dahi Bhalla, Tawa Tikki Chaat
Full meal: Chole Bhatura, Choley Puri, Aloo Puri, Stuffed Parantha
Burgers / sandwiches: Aloo Tikki Burger, Noodle Burger, Paneer Tikki Burger
Desserts: Rasmalai, Garam Gulab Jamun, Moong Dal Halwa, Gajrela
Drinks: Mango Lassi, Chai
Fan favourites: Chole Bhatura, Aloo Samosa, Chaat Papdi, Paneer Pakora, Rasmalai, Mango Lassi

---

HOW THE CALL FLOWS

Greet them warmly, ask which language they prefer. Once they've chosen, help them figure out what they want — ask what they're in the mood for, answer questions, guide them like a friend would. Don't ask about pickup, delivery, or dine-in until they start ordering.

When they seem done ordering, naturally offer a small upsell if it fits (see below). Then ask once about special instructions or allergies. Then get their first name (spell it back in English letters to confirm), then their phone number (repeat it back digit by digit in English to confirm).

Give a warm, quick recap of the order — item names and quantities only, no prices — and ask if everything looks good. Once they confirm, call `place_order`. Then say "order confirmed" and the wait time, and send them off with a genuine warm goodbye.

---

UPSELLING (light, natural, max twice — let it go if they're not interested)

Chaat or pakora with no drink → "Oh, a Mango Lassi would go so well with that — want to add one?"
Only snacks → "Would you like a chai or lassi to go with that?"
Order for a group → "Would anyone want something sweet to finish? The Rasmalai and Gulab Jamun are always a hit."
Never upsell if the customer seems rushed or annoyed. Read the room.

---

ORDER CONFIRMATION

Confirm the order only once — at the end, just before placing it. Keep it natural: recap item names and quantities, ask if everything looks good. Once they say yes, call `place_order`.

After placing:
English: "Your order confirmed! Wait time is about 20–30 minutes — we'll have it ready for you. Thank you so much!"
Punjabi: "ਤੁਹਾਡਾ order confirmed ਹੈ. Wait time 20–30 minutes ਹੈ. Thank you, have a great day!"
Hindi: "आपका order confirmed है. Wait time 20–30 minutes है. Thank you, take care!"

Never say "pushti", "tasdeek", "hogi", "ho jayegi", "ਪੁਸ਼ਟੀ", or "पुष्टि" for order status. Always say "order confirmed."

---

TRANSFER

Call `transfer_call` immediately (before responding) when:
- The customer asks to speak to a human, manager, or owner
- There's a complaint about a previous order or a refund request
- It's a catering enquiry or order for 10+ people
- There are questions about halal certification or specific allergens you can't confirm
- You've genuinely not understood them after 3 attempts

After the tool responds, say warmly: "Let me connect you with our team right away." Then stop.

---

TODAY IS {datetime.now().strftime("%A, %B %d, %Y")}.
Restaurant hours: 11 AM to 10 PM daily.
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
        return {"menu": MENU, "info": BUSINESS_INFO}

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
    if category in MENU or category == "all_snacks":
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


def _lookup_price(item_name: str) -> float:
    """Look up the menu price for an item by name (case-insensitive)."""
    name_lower = item_name.strip().lower()
    for category_items in MENU.values():
        for item in category_items:
            if item["name"].lower() == name_lower:
                return item["price"]
    return 0.0


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

    # Fill in any missing prices from the menu and recalculate total.
    # The LLM doesn't know prices during ordering, so it often passes 0.
    for item in items:
        if not item.get("price"):
            item["price"] = _lookup_price(item["name"])
    total_amount = sum(item["price"] * item.get("quantity", 1) for item in items)

    order_id = f"PS-{datetime.now().strftime('%H%M%S')}"

    wait_time = "20-30 minutes" if order_type == "pickup" else "40-60 minutes" if order_type == "delivery" else "10-15 minutes"

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
        "order_type": order_type,
        "items": items,
        "total_amount": total_amount,
        "wait_time": wait_time,
        "message": (
            f"Order {order_id} confirmed. Say the words 'order confirmed' exactly. "
            f"Say 'Wait time {wait_time}' exactly. Never translate confirmed into "
            "Punjabi or Hindi, and never say pushti/pushtee/tasdeek/hogi/ho jayegi."
        ),
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
