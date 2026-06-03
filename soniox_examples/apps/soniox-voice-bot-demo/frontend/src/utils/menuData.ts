// ── Types ────────────────────────────────────────────────────

export interface MenuItemDisplay {
  name: string;
  price: number;
  description?: string;
}

export interface MenuCategory {
  id: string;
  label: string;
  items: MenuItemDisplay[];
}

export interface DetectedOrderItem {
  name: string;
  quantity: number;
  price: number;
}

// ── Full menu for the Menu panel ─────────────────────────────

export const MENU_CATEGORIES: MenuCategory[] = [
  {
    id: "classics",
    label: "Classics",
    items: [
      { name: "Chole Bhatura",  price: 7.99, description: "Chickpea curry with two fried bhature" },
      { name: "Choley Puri",    price: 7.99, description: "Chickpea curry with three puris" },
      { name: "Aloo Puri",      price: 7.99, description: "Tangy aloo curry with three puris" },
    ],
  },
  {
    id: "samosa",
    label: "Samosa",
    items: [
      { name: "Aloo Samosa (2 pcs)",   price: 3.00, description: "Crispy fried dough with spiced potato" },
      { name: "Noodle Samosa (2 pcs)", price: 4.50, description: "Noodles, veggies, soya sauce & vinegar" },
    ],
  },
  {
    id: "chaat",
    label: "Chaat",
    items: [
      { name: "Chaat Papdi",          price: 5.99, description: "Crispy chips, potato, chickpeas, yogurt & chutneys" },
      { name: "Dahi Bhalla",          price: 5.99, description: "Soft lentil dumplings in chilled yogurt" },
      { name: "Samosa Choley",        price: 6.50, description: "Aloo samosas with spicy chickpeas & chutney" },
      { name: "Tawa Tikki Chaat",     price: 6.00, description: "Crisp potato patty with yogurt & chutneys" },
      { name: "Tawa Tikki Choley",    price: 7.50, description: "Potato patty with chickpea curry & chutney" },
      { name: "Aloo Besan Tikki Chaat", price: 5.00, description: "Gram flour potato patty with yogurt & sauces" },
    ],
  },
  {
    id: "pakora",
    label: "Pakora",
    items: [
      { name: "Mix Veg Pakora",       price: 8.50,  description: "Spinach, cauliflower, onion & potato fritters" },
      { name: "Paneer Pakora",        price: 11.50, description: "Cottage cheese in spiced gram batter, deep fried" },
      { name: "Gobi Pakora",          price: 10.50, description: "Cauliflower fritters with gram flour & spices" },
      { name: "Baingan Pakora",       price: 8.50,  description: "Thin eggplant slices in spiced gram batter" },
      { name: "Mirchi Pakora",        price: 10.50, description: "Stuffed green chili fritters" },
      { name: "Hara Bara Kabab",      price: 10.50, description: "Spinach, peas & potato pan-fried patties" },
      { name: "Dahi Kabab",           price: 9.00,  description: "Creamy yogurt patties lightly pan fried" },
      { name: "Mushroom Delux",       price: 9.00,  description: "Mushrooms in spicy gram batter, fried crisp (6 pcs)" },
      { name: "Aloo Cutlet",          price: 10.50, description: "Crispy mashed potato with spices & herbs" },
      { name: "Parkash Platter",      price: 15.99, description: "Assorted veg pakoras, paneer, kababs & more" },
      { name: "Aloo Finger",          price: 8.50,  description: "Golden crispy potato fingers" },
      { name: "Spring Roll",          price: 8.00,  description: "Cabbage, noodles & carrots in a flaky crispy roll" },
      { name: "Aloo Besan Tikki (2 pcs)", price: 3.00, description: "Crisp potato patties with peas & gram flour" },
      { name: "Shimla Mirch Pakora",  price: 5.00,  description: "Capsicum rings with spiced potato stuffing (2 pcs)" },
      { name: "Tawa Tikki (2 pcs)",   price: 4.00,  description: "Golden fried potato patties" },
    ],
  },
  {
    id: "bread",
    label: "Bread Pakora",
    items: [
      { name: "Aloo Bread Pakora",        price: 3.00, description: "Spiced potato stuffing between bread slices (2 pcs)" },
      { name: "Paneer Aloo Bread Pakora", price: 5.00, description: "Bread fritters with potato and paneer (2 pcs)" },
      { name: "Bread Roll",               price: 3.00, description: "Crispy outside, tangy potato stuffing (2 pcs)" },
    ],
  },
  {
    id: "burger",
    label: "Burgers",
    items: [
      { name: "Aloo Tikki Burger",        price: 6.50, description: "Spiced potato patty, lettuce, onion & spicy mayo" },
      { name: "Noodle Burger",            price: 7.50, description: "Aloo patty with Asian noodles & signature mayo" },
      { name: "Paneer Tikki Burger",      price: 8.50, description: "Marinated paneer tikki with lettuce & signature sauce" },
      { name: "Grilled Cheese Sandwich",  price: 5.50, description: "Golden toasted bread with melted cheese" },
      { name: "Super Veggie Sandwich",    price: 6.99, description: "Red onion, capsicum, corn, cheese & spicy mayo" },
      { name: "Sweet Corn Sandwich",      price: 6.99, description: "Sweet corn, cheese, tangy sauce & oregano" },
      { name: "Paneer Mayo Sandwich",     price: 7.99, description: "Paneer, corn, capsicum, carrot & spicy mayo" },
      { name: "Coleslaw Sandwich - Kids Size", price: 5.00, description: "White bread with eggless mayo, carrots & cabbage" },
    ],
  },
  {
    id: "parantha",
    label: "Parantha",
    items: [
      { name: "Aloo Parantha",   price: 4.00, description: "Spiced mashed potato stuffed flatbread" },
      { name: "Gobi Parantha",   price: 4.50, description: "Spiced grated cauliflower stuffed flatbread" },
      { name: "Muli Parantha",   price: 4.50, description: "Spiced grated radish stuffed flatbread" },
      { name: "Paneer Parantha", price: 4.99, description: "Spiced cottage cheese stuffed flatbread" },
      { name: "Mix Parantha",    price: 4.99, description: "Potato, cauliflower, paneer & radish stuffed flatbread" },
    ],
  },
  {
    id: "desserts",
    label: "Desserts",
    items: [
      { name: "Rasmalai (2 pcs)",         price: 4.00, description: "Soft cheese dumplings in cardamom-saffron milk" },
      { name: "Kesar Rasmalai (6 pcs)",   price: 5.99, description: "Paneer dumplings soaked in saffron milk" },
      { name: "Garam Gulab Jamun (2 pcs)",price: 3.00, description: "Fried dough balls in warm sugar syrup" },
      { name: "Spongey Rasgulla (2 pcs)", price: 3.00, description: "Soft round dumplings in sugar syrup" },
      { name: "Moong Dal Halwa - 8 oz",   price: 5.50, description: "Yellow moong dal slow-cooked with ghee & nuts" },
      { name: "Garam Gajrela - 8 oz",     price: 4.50, description: "Fresh carrots cooked in milk with almonds & mawa" },
    ],
  },
  {
    id: "beverages",
    label: "Drinks",
    items: [
      { name: "Mango Lassi",        price: 4.99 },
      { name: "Sweet Lassi",        price: 4.49 },
      { name: "Salty Lassi",        price: 4.49 },
      { name: "Masala Chai",        price: 1.99 },
      { name: "Elachi Chai",        price: 2.99 },
      { name: "Gur Chai",           price: 2.99 },
      { name: "Dudh Patti",         price: 2.99 },
      { name: "Coffee - Indian Style", price: 2.99 },
      { name: "Badam Milk",         price: 5.99 },
      { name: "Mango Shake",        price: 5.50 },
      { name: "Strawberry Shake",   price: 5.50 },
      { name: "Oreo Shake",         price: 5.50 },
      { name: "Chocolate Shake",    price: 5.50 },
      { name: "Vanilla Shake",      price: 5.50 },
      { name: "Mango Faluda",       price: 8.50 },
      { name: "Strawberry Faluda",  price: 8.50 },
      { name: "Vanilla Faluda",     price: 8.50 },
    ],
  },
  {
    id: "sides",
    label: "Sides",
    items: [
      { name: "Butter (2 pcs)",     price: 0.99 },
      { name: "Dahi - 8 oz",        price: 2.99 },
      { name: "Raita - 8 oz",       price: 2.99 },
      { name: "Extra Bhatura",      price: 2.50 },
      { name: "Extra Puri",         price: 1.50 },
      { name: "Choley - 8 oz",      price: 2.99 },
      { name: "Mix Pickle - 2 oz",  price: 1.49 },
      { name: "Tamarind Sauce - 2 oz", price: 1.00 },
      { name: "Mint Sauce - 2 oz",    price: 1.50 },
    ],
  },
];

// ── Flat list for order parsing ──────────────────────────────

interface MenuEntry {
  name: string;
  terms: string[];
  price: number;
}

const MENU: MenuEntry[] = [
  // ── Samosa ──────────────────────────────────────────────────────────────────
  { name: "Aloo Samosa (2 pcs)",   terms: ["aloo samosa", "samosa", "aloo samosay", "ਆਲੂ ਸਮੋਸਾ", "आलू समोसा"], price: 3.0  },
  { name: "Noodle Samosa (2 pcs)", terms: ["noodle samosa", "ਨੂਡਲ ਸਮੋਸਾ", "नूडल समोसा"],                price: 4.5  },

  // ── Parkash Classics ────────────────────────────────────────────────────────
  { name: "Chole Bhatura",  terms: ["chole bhatura", "chole bhature", "choley bhatura", "chhole bhatura", "ਛੋਲੇ ਭਟੂਰੇ", "छोले भटूरे"], price: 7.99 },
  { name: "Choley Puri",    terms: ["choley puri", "chole puri", "ਛੋਲੇ ਪੂਰੀ", "छोले पूरी"],           price: 7.99 },
  { name: "Aloo Puri",      terms: ["aloo puri", "ਆਲੂ ਪੂਰੀ", "आलू पूरी"],                             price: 7.99 },

  // ── Chaat ───────────────────────────────────────────────────────────────────
  { name: "Chaat Papdi",          terms: ["chaat papdi", "papdi chaat", "papri chaat", "chaat papri", "ਚਾਟ ਪਾਪੜੀ", "चाट पापड़ी"],    price: 5.99 },
  { name: "Dahi Bhalla",          terms: ["dahi bhalla", "ਦਹੀ ਭੱਲਾ", "दही भल्ला"],                   price: 5.99 },
  { name: "Samosa Choley",        terms: ["samosa choley", "samosa chole", "samosa chaat", "ਸਮੋਸਾ ਛੋਲੇ", "समोसा छोले"], price: 6.5 },
  { name: "Tawa Tikki Chaat",     terms: ["tawa tikki chaat", "tikki chaat", "ਤਵਾ ਟਿੱਕੀ ਚਾਟ", "तवा टिक्की चाट"], price: 6.0 },
  { name: "Tawa Tikki Choley",    terms: ["tawa tikki choley", "tikki choley", "ਤਵਾ ਟਿੱਕੀ ਛੋਲੇ", "तवा टिक्की छोले"], price: 7.5 },
  { name: "Aloo Besan Tikki Chaat", terms: ["aloo besan tikki chaat", "besan tikki chaat", "aloo tikki chaat", "ਆਲੂ ਬੇਸਣ ਟਿੱਕੀ ਚਾਟ", "आलू बेसन टिक्की चाट"], price: 5.0 },

  // ── Pakora ──────────────────────────────────────────────────────────────────
  { name: "Mix Veg Pakora",    terms: ["mix veg pakora", "veg pakora", "mix pakora", "mixed pakora", "ਮਿਕਸ ਵੈਜ ਪਕੌੜਾ", "मिक्स वेज पकौड़ा"], price: 8.5 },
  { name: "Paneer Pakora",     terms: ["paneer pakora", "paneer pakoda", "paner pakora", "ਪਨੀਰ ਪਕੌੜਾ", "पनीर पकौड़ा"],                     price: 11.5 },
  { name: "Gobi Pakora",       terms: ["gobi pakora", "cauliflower pakora", "ਗੋਭੀ ਪਕੌੜਾ", "गोभी पकौड़ा"],                                 price: 10.5 },
  { name: "Baingan Pakora",    terms: ["baingan pakora", "ਬੈਂਗਣ ਪਕੌੜਾ", "बैंगन पकौड़ा"],                                                 price: 8.5  },
  { name: "Mirchi Pakora",     terms: ["mirchi pakora", "ਮਿਰਚੀ ਪਕੌੜਾ", "मिर्ची पकौड़ा"],                                                 price: 10.5 },
  { name: "Hara Bara Kabab",   terms: ["hara bara kabab", "hara bhara kabab", "hara bhara", "hara bara", "ਹਰਾ ਭਰਾ ਕਬਾਬ", "हरा भरा कबाब"], price: 10.5 },
  { name: "Dahi Kabab",        terms: ["dahi kabab", "ਦਹੀ ਕਬਾਬ", "दही कबाब"],                                                            price: 9.0  },
  { name: "Mushroom Delux",    terms: ["mushroom delux", "mushroom", "mushroom pakora", "mushrooms"],  price: 9.0  },
  { name: "Aloo Cutlet",       terms: ["aloo cutlet", "cutlet"],                                       price: 10.5 },
  { name: "Parkash Platter",   terms: ["parkash platter", "platter"],                                  price: 15.99},
  { name: "Aloo Finger",       terms: ["aloo finger", "aloo fingers", "potato fingers"],               price: 8.5  },
  { name: "Spring Roll",       terms: ["spring roll"],                                                 price: 8.0  },
  { name: "Aloo Besan Tikki (2 pcs)", terms: ["aloo besan tikki", "besan tikki"],                     price: 3.0  },
  { name: "Shimla Mirch Pakora",      terms: ["shimla mirch pakora", "shimla mirch"],                  price: 5.0  },
  { name: "Tawa Tikki (2 pcs)",       terms: ["tawa tikki"],                                           price: 4.0  },

  // ── Bread Pakora ────────────────────────────────────────────────────────────
  { name: "Aloo Bread Pakora",        terms: ["aloo bread pakora", "aloo bread"],          price: 3.0  },
  { name: "Paneer Aloo Bread Pakora", terms: ["paneer aloo bread pakora", "paneer bread pakora", "paneer aloo bread", "paneer bread"], price: 5.0 },
  { name: "Bread Roll",               terms: ["bread roll"],                               price: 3.0  },

  // ── Burgers & Sandwiches ────────────────────────────────────────────────────
  { name: "Aloo Tikki Burger",         terms: ["aloo tikki burger", "aloo burger", "tikki burger"],    price: 6.5  },
  { name: "Noodle Burger",             terms: ["noodle burger"],                           price: 7.5  },
  { name: "Paneer Tikki Burger",       terms: ["paneer tikki burger", "paneer burger"],    price: 8.5  },
  { name: "Grilled Cheese Sandwich",   terms: ["grilled cheese sandwich", "grilled cheese", "cheese sandwich"], price: 5.5 },
  { name: "Super Veggie Sandwich",     terms: ["super veggie sandwich", "veggie sandwich", "veg sandwich"], price: 6.99 },
  { name: "Sweet Corn Sandwich",       terms: ["sweet corn sandwich", "corn sandwich"],    price: 6.99 },
  { name: "Paneer Mayo Sandwich",      terms: ["paneer mayo sandwich", "paneer mayo", "paneer sandwich"], price: 7.99 },
  { name: "Coleslaw Sandwich - Kids Size", terms: ["coleslaw sandwich", "kids sandwich"], price: 5.0  },

  // ── Parantha ────────────────────────────────────────────────────────────────
  { name: "Aloo Parantha",   terms: ["aloo parantha", "aloo paratha", "ਆਲੂ ਪਰਾਂਠਾ", "आलू परांठा"],  price: 4.0  },
  { name: "Gobi Parantha",   terms: ["gobi parantha", "gobi paratha", "ਗੋਭੀ ਪਰਾਂਠਾ", "गोभी परांठा"], price: 4.5  },
  { name: "Muli Parantha",   terms: ["muli parantha", "mooli parantha", "muli paratha", "mooli paratha", "ਮੂਲੀ ਪਰਾਂਠਾ", "मूली परांठा"], price: 4.5 },
  { name: "Paneer Parantha", terms: ["paneer parantha", "paneer paratha", "ਪਨੀਰ ਪਰਾਂਠਾ", "पनीर परांठा"], price: 4.99 },
  { name: "Mix Parantha",    terms: ["mix parantha", "mix paratha", "ਮਿਕਸ ਪਰਾਂਠਾ", "मिक्स परांठा"],    price: 4.99 },

  // ── Desserts ────────────────────────────────────────────────────────────────
  { name: "Rasmalai (2 pcs)",          terms: ["rasmalai", "ਰਸਮਲਾਈ", "रसमलाई"],                          price: 4.0  },
  { name: "Kesar Rasmalai (6 pcs)",    terms: ["kesar rasmalai", "saffron rasmalai", "ਕੇਸਰ ਰਸਮਲਾਈ", "केसर रसमलाई"], price: 5.99 },
  { name: "Garam Gulab Jamun (2 pcs)", terms: ["gulab jamun", "garam gulab jamun", "ਗੁਲਾਬ ਜਾਮੁਨ", "गुलाब जामुन"], price: 3.0 },
  { name: "Spongey Rasgulla (2 pcs)",  terms: ["rasgulla", "spongey rasgulla", "ਰਸਗੁੱਲਾ", "रसगुल्ला"],   price: 3.0  },
  { name: "Moong Dal Halwa - 8 oz",    terms: ["moong dal halwa", "dal halwa", "ਮੂੰਗ ਦਾਲ ਹਲਵਾ", "मूंग दाल हलवा"], price: 5.5 },
  { name: "Garam Gajrela - 8 oz",      terms: ["gajrela", "garam gajrela", "gajar halwa", "gajar ka halwa", "carrot halwa", "ਗਾਜਰੇਲਾ", "गाजरेला"], price: 4.5 },

  // ── Beverages ───────────────────────────────────────────────────────────────
  { name: "Mango Lassi",         terms: ["mango lassi", "ਮੈਂਗੋ ਲੱਸੀ", "मैंगो लस्सी"],              price: 4.99 },
  { name: "Sweet Lassi",         terms: ["sweet lassi", "ਮਿੱਠੀ ਲੱਸੀ", "मीठी लस्सी"],               price: 4.49 },
  { name: "Salty Lassi",         terms: ["salty lassi", "namkeen lassi", "salt lassi", "ਨਮਕੀਨ ਲੱਸੀ", "नमकीन लस्सी"], price: 4.49 },
  { name: "Masala Chai",         terms: ["masala chai", "chai", "tea", "ਮਸਾਲਾ ਚਾਹ", "मसाला चाय"],  price: 1.99 },
  { name: "Elachi Chai",         terms: ["elachi chai", "cardamom chai", "ਇਲਾਇਚੀ ਚਾਹ", "इलायची चाय"], price: 2.99 },
  { name: "Gur Chai",            terms: ["gur chai", "jaggery chai", "ਗੁੜ ਦੀ ਚਾਹ", "गुड़ की चाय"],  price: 2.99 },
  { name: "Dudh Patti",          terms: ["dudh patti", "doodh patti", "ਦੁੱਧ ਪੱਤੀ", "दूध पत्ती"],    price: 2.99 },
  { name: "Coffee - Indian Style", terms: ["coffee", "indian coffee"],                     price: 2.99 },
  { name: "Badam Milk",          terms: ["badam milk", "almond milk"],                     price: 5.99 },
  { name: "Mango Shake",         terms: ["mango shake"],                                   price: 5.5  },
  { name: "Strawberry Shake",    terms: ["strawberry shake"],                              price: 5.5  },
  { name: "Oreo Shake",          terms: ["oreo shake"],                                    price: 5.5  },
  { name: "Chocolate Shake",     terms: ["chocolate shake", "choco shake"],                price: 5.5  },
  { name: "Vanilla Shake",       terms: ["vanilla shake"],                                 price: 5.5  },
  { name: "Mango Faluda",        terms: ["mango faluda", "faluda", "falooda", "ਮੈਂਗੋ ਫਾਲੂਦਾ", "मैंगो फालूदा"], price: 8.5 },
  { name: "Strawberry Faluda",   terms: ["strawberry faluda", "ਸਟ੍ਰਾਬੇਰੀ ਫਾਲੂਦਾ"],          price: 8.5  },
  { name: "Vanilla Faluda",      terms: ["vanilla faluda", "ਵਨੀਲਾ ਫਾਲੂਦਾ"],                price: 8.5  },

  // ── Sides ───────────────────────────────────────────────────────────────────
  { name: "Butter (2 pcs)",    terms: ["butter"],                                          price: 0.99 },
  { name: "Dahi - 8 oz",       terms: ["dahi - 8 oz", "dahi 8oz", "extra dahi"],          price: 2.99 },
  { name: "Raita - 8 oz",      terms: ["raita"],                                           price: 2.99 },
  { name: "Extra Bhatura",     terms: ["extra bhatura"],                                   price: 2.5  },
  { name: "Extra Puri",        terms: ["extra puri"],                                      price: 1.5  },
  { name: "Choley - 8 oz",     terms: ["choley - 8 oz", "choley 8oz", "extra choley"],     price: 2.99 },
  { name: "Mix Pickle - 2 oz", terms: ["mix pickle", "pickle", "achar"],                   price: 1.49 },
  { name: "Tamarind Sauce - 2 oz", terms: ["tamarind sauce", "imli sauce", "imli chutney"], price: 1.0 },
  { name: "Mint Sauce - 2 oz", terms: ["mint sauce", "pudina sauce", "pudina chutney"],    price: 1.5  },
];

export interface ConversationDetails {
  name: string | null;
  phone: string | null;
  orderType: string | null;   // "pickup" | "delivery" | "dine_in"
  instructions: string | null;
  isConfirmed: boolean;
}

/**
 * Real-time extraction of order details from the ongoing conversation.
 * Used to populate the order card before/instead of the server order_confirmed message.
 */
export function parseConversationDetails(messages: { type: string; text?: string; final_text?: string }[]): ConversationDetails {
  const botTexts  = messages.filter(m => m.type === "llm_response").map(m => m.text ?? "");
  const userTexts = messages.filter(m => m.type === "transcription").map(m => m.final_text ?? "");

  const botFull  = botTexts.join(" ");
  const botLower = botFull.toLowerCase();
  const userFull = userTexts.join(" ");
  const allLower = botLower + " " + userFull.toLowerCase();

  // ── Name ──────────────────────────────────────────────────────────────
  let name: string | null = null;

  // "Thank you, Shivek!" or "Thank you, Shivek."
  const m1 = botFull.match(/[Tt]hank you,?\s+([A-Z][a-z]+)[!.,\s]/);
  if (m1) name = m1[1];

  if (!name) {
    // "under the name Shivek" (in recap)
    const m2 = botFull.match(/under the name\s+([A-Z][a-z]+)/i);
    if (m2) name = m2[1];
  }

  if (!name) {
    // "for Shivek." at end of recap line
    const m3 = botFull.match(/,\s+for\s+([A-Z][a-z]+)[.,!]/);
    if (m3) name = m3[1];
  }

  // ── Phone ─────────────────────────────────────────────────────────────
  let phone: string | null = null;

  // User gave 10 consecutive digits
  const phoneDigits = userFull.match(/\b(\d{10})\b/);
  if (phoneDigits) {
    phone = phoneDigits[1];
  } else {
    // Bot read back digits: "9-4-1, 3-7-5, 2-6-8-8" → strip non-digits
    const botPhoneMatch = botFull.match(/\b(\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d)\b/);
    if (botPhoneMatch) {
      phone = botPhoneMatch[1].replace(/[^0-9]/g, "");
    }
  }

  // ── Order type ────────────────────────────────────────────────────────
  let orderType: string | null = null;
  if (allLower.includes("pickup"))                                   orderType = "pickup";
  else if (allLower.includes("delivery"))                            orderType = "delivery";
  else if (allLower.includes("dine-in") || allLower.includes("dine in")) orderType = "dine_in";

  // ── Special instructions ──────────────────────────────────────────────
  let instructions: string | null = null;

  // "Got it! Less oily for your Aloo Samosa." – capture what follows "Got it"
  const gotIt = botFull.match(/Got it[!,.]?\s+(.+?)(?:\.|What|Can I|Anything|And can|Your name)/i);
  if (gotIt) instructions = gotIt[1].trim();

  // ── Confirmed? ────────────────────────────────────────────────────────
  const isConfirmed = botLower.includes("order confirmed");

  return { name, phone, orderType, instructions, isConfirmed };
}

const WORD_QTY: Record<string, number> = {
  // English
  one: 1, two: 2, three: 3, four: 4, five: 5,
  six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  // Punjabi (Gurmukhi)
  'ਇੱਕ': 1, 'ਦੋ': 2, 'ਤਿੰਨ': 3, 'ਚਾਰ': 4, 'ਪੰਜ': 5,
  'ਛੇ': 6, 'ਸੱਤ': 7, 'ਅੱਠ': 8, 'ਨੌਂ': 9, 'ਦਸ': 10,
  // Hindi (Devanagari)
  'एक': 1, 'दो': 2, 'तीन': 3, 'चार': 4, 'पाँच': 5,
  'पांच': 5, 'छह': 6, 'सात': 7, 'आठ': 8, 'नौ': 9, 'दस': 10,
};

// Returns true if a string contains Gurmukhi or Devanagari characters
const hasNativeScript = (s: string): boolean =>
  /[ऀ-ॿ਀-੿]/.test(s);

// Sierra is recapping the full current order → clear and rebuild from this message
const isRecapMessage = (text: string): boolean =>
  // English
  /\bjust to confirm\b/i.test(text) ||
  /\byour order is\b/i.test(text) ||
  /\bso we have\b/i.test(text) ||
  /\bto recap\b/i.test(text) ||
  /\blet me confirm\b/i.test(text) ||
  /\bso you'?re (?:getting|ordering|having)\b/i.test(text) ||
  /\bso that'?s\s+[1-9one|two|three]/i.test(text) ||
  // Punjabi (Gurmukhi) recap triggers
  /ਤੁਹਾਡਾ order/.test(text) ||
  /order ਵਿੱਚ/.test(text) ||
  /ਦੱਸ ਦਿੰਦੀ ਹਾਂ/.test(text) ||
  /confirm ਕਰਦੇ ਹਾਂ/.test(text) ||
  /ਤਾਂ ਤੁਸੀਂ/.test(text) ||
  // Hindi (Devanagari) recap triggers
  /आपका order/.test(text) ||
  /order में/.test(text) ||
  /confirm करते हैं/.test(text) ||
  /तो आपने/.test(text);

// Sierra is removing an item
const REMOVAL_RE = /\b(?:remov(?:e|ed|ing)|without|no more|cancel(?:l?ed)?|tak(?:en?|ing) (?:off|out)|drop(?:p(?:ed|ing))?|no longer)\b/i;

// Latin word-quantity keys for the regex (excludes Gurmukhi/Devanagari entries)
const LATIN_WORD_QTY_KEYS = Object.keys(WORD_QTY)
  .filter(k => !hasNativeScript(k))
  .join("|");

export function parseOrderFromBotMessages(botTexts: string[]): DetectedOrderItem[] {
  const order = new Map<string, DetectedOrderItem>();

  for (const text of botTexts) {
    const lower = text.toLowerCase();
    const isCurrentRecap = isRecapMessage(text);

    // On a full recap clear everything and rebuild from this message only
    if (isCurrentRecap) order.clear();

    // Pre-compute "instead of X" removals
    const insteadOfRemoved = new Set<string>();
    const insteadMatch = lower.match(/\binstead of\s+([\w\s]+?)(?:,|\.|(?:\s+(?:how about|we|would|i'll|let)))/i);
    if (insteadMatch) {
      const phrase = insteadMatch[1].trim();
      for (const item of MENU) {
        if (item.terms.some(t => phrase.includes(t))) {
          insteadOfRemoved.add(item.name);
        }
      }
    }

    const isRemoval = REMOVAL_RE.test(text);

    for (const item of MENU) {
      for (const term of item.terms) {
        const native = hasNativeScript(term);
        const esc = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

        // ── Removal ────────────────────────────────────────────────────────────
        if (isRemoval) {
          const remPat = native
            ? new RegExp(`(?:remov(?:e|ed|ing)|without|no more|cancel(?:l?ed)?)\\s+(?:the\\s+)?${esc}`, "i")
            : new RegExp(`\\b(?:remov(?:e|ed|ing)|without|no more|cancel(?:l?ed)?|tak(?:en?|ing) (?:off|out)|drop(?:p(?:ed|ing))?)\\s+(?:the\\s+)?${esc}\\b`, "i");
          if (remPat.test(native ? text : lower)) {
            order.delete(item.name);
            break;
          }
        }

        if (native) {
          // ── Native script (Gurmukhi / Devanagari) ─────────────────────────
          // Numbers in Sierra's text are always Latin digits even in Punjabi/Hindi,
          // so "2 ਛੋਲੇ ਭਟੂਰੇ" and "1 पनीर पकौड़ा" are real patterns.

          // 1. Digit before native term: "2 ਛੋਲੇ ਭਟੂਰੇ"
          const nDigit = text.match(new RegExp(`([1-9]\\d*)\\s+${esc}`));
          if (nDigit) {
            order.set(item.name, { name: item.name, quantity: parseInt(nDigit[1]), price: item.price });
            break;
          }

          // 2. Native word quantity before term: "ਦੋ ਛੋਲੇ ਭਟੂਰੇ", "दो पनीर पकौड़ा"
          let wqty: number | null = null;
          for (const [word, qty] of Object.entries(WORD_QTY)) {
            if (hasNativeScript(word) && text.includes(`${word} ${term}`)) {
              wqty = qty;
              break;
            }
          }
          if (wqty !== null) {
            order.set(item.name, { name: item.name, quantity: wqty, price: item.price });
            break;
          }

          // 3. On recap messages, a bare mention = confirmed qty 1
          //    (Sierra uses native names in recaps like "ਤੁਹਾਡਾ order ਵਿੱਚ ਛੋਲੇ ਭਟੂਰੇ")
          if (isCurrentRecap && text.includes(term)) {
            if (!order.has(item.name)) {
              order.set(item.name, { name: item.name, quantity: 1, price: item.price });
            }
            break;
          }

        } else {
          // ── Latin script ───────────────────────────────────────────────────

          // 1. Digit quantity: "2 Chole Bhatura"
          const digitMatch = lower.match(new RegExp(`\\b([1-9]\\d*)\\s+${esc}\\b`));
          if (digitMatch) {
            order.set(item.name, { name: item.name, quantity: parseInt(digitMatch[1]), price: item.price });
            break;
          }

          // 2. Word quantity: "one Chole Bhatura", "two Mango Lassi"
          const wordMatch = lower.match(new RegExp(`\\b(${LATIN_WORD_QTY_KEYS})\\s+${esc}\\b`));
          if (wordMatch) {
            order.set(item.name, { name: item.name, quantity: WORD_QTY[wordMatch[1]] ?? 1, price: item.price });
            break;
          }
        }
      }

      // "instead of X" removal overrides any quantity match above
      if (insteadOfRemoved.has(item.name)) {
        order.delete(item.name);
      }
    }
  }

  return Array.from(order.values());
}
