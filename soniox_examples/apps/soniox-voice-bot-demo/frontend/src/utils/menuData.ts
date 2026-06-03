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
  { name: "Aloo Samosa (2 pcs)",   terms: ["aloo samosa", "samosa", "aloo samosay"],        price: 3.0  },
  { name: "Noodle Samosa (2 pcs)", terms: ["noodle samosa"],                                price: 4.5  },

  // ── Parkash Classics ────────────────────────────────────────────────────────
  { name: "Chole Bhatura",  terms: ["chole bhatura", "chole bhature", "choley bhatura", "chhole bhatura"], price: 7.99 },
  { name: "Choley Puri",    terms: ["choley puri", "chole puri"],                           price: 7.99 },
  { name: "Aloo Puri",      terms: ["aloo puri"],                                           price: 7.99 },

  // ── Chaat ───────────────────────────────────────────────────────────────────
  { name: "Chaat Papdi",          terms: ["chaat papdi", "papdi chaat", "papri chaat", "chaat papri"],    price: 5.99 },
  { name: "Dahi Bhalla",          terms: ["dahi bhalla"],                                  price: 5.99 },
  { name: "Samosa Choley",        terms: ["samosa choley", "samosa chole", "samosa chaat"],price: 6.5  },
  { name: "Tawa Tikki Chaat",     terms: ["tawa tikki chaat", "tikki chaat"],              price: 6.0  },
  { name: "Tawa Tikki Choley",    terms: ["tawa tikki choley", "tikki choley"],            price: 7.5  },
  { name: "Aloo Besan Tikki Chaat", terms: ["aloo besan tikki chaat", "besan tikki chaat", "aloo tikki chaat"], price: 5.0 },

  // ── Pakora ──────────────────────────────────────────────────────────────────
  { name: "Mix Veg Pakora",    terms: ["mix veg pakora", "veg pakora", "mix pakora", "mixed pakora"],   price: 8.5  },
  { name: "Paneer Pakora",     terms: ["paneer pakora", "paneer pakoda", "paner pakora"],               price: 11.5 },
  { name: "Gobi Pakora",       terms: ["gobi pakora", "cauliflower pakora"],                            price: 10.5 },
  { name: "Baingan Pakora",    terms: ["baingan pakora"],                                              price: 8.5  },
  { name: "Mirchi Pakora",     terms: ["mirchi pakora"],                                               price: 10.5 },
  { name: "Hara Bara Kabab",   terms: ["hara bara kabab", "hara bhara kabab", "hara bhara", "hara bara"], price: 10.5 },
  { name: "Dahi Kabab",        terms: ["dahi kabab"],                                                  price: 9.0  },
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
  { name: "Aloo Parantha",   terms: ["aloo parantha", "aloo paratha"],                     price: 4.0  },
  { name: "Gobi Parantha",   terms: ["gobi parantha", "gobi paratha"],                     price: 4.5  },
  { name: "Muli Parantha",   terms: ["muli parantha", "mooli parantha", "muli paratha", "mooli paratha"], price: 4.5 },
  { name: "Paneer Parantha", terms: ["paneer parantha", "paneer paratha"],                 price: 4.99 },
  { name: "Mix Parantha",    terms: ["mix parantha", "mix paratha"],                       price: 4.99 },

  // ── Desserts ────────────────────────────────────────────────────────────────
  { name: "Rasmalai (2 pcs)",          terms: ["rasmalai"],                                price: 4.0  },
  { name: "Kesar Rasmalai (6 pcs)",    terms: ["kesar rasmalai", "saffron rasmalai"],       price: 5.99 },
  { name: "Garam Gulab Jamun (2 pcs)", terms: ["gulab jamun", "garam gulab jamun"],         price: 3.0  },
  { name: "Spongey Rasgulla (2 pcs)",  terms: ["rasgulla", "spongey rasgulla"],             price: 3.0  },
  { name: "Moong Dal Halwa - 8 oz",    terms: ["moong dal halwa", "dal halwa"],             price: 5.5  },
  { name: "Garam Gajrela - 8 oz",      terms: ["gajrela", "garam gajrela", "gajar halwa", "gajar ka halwa", "carrot halwa"], price: 4.5 },

  // ── Beverages ───────────────────────────────────────────────────────────────
  { name: "Mango Lassi",         terms: ["mango lassi"],                                   price: 4.99 },
  { name: "Sweet Lassi",         terms: ["sweet lassi"],                                   price: 4.49 },
  { name: "Salty Lassi",         terms: ["salty lassi", "namkeen lassi", "salt lassi"],    price: 4.49 },
  { name: "Masala Chai",         terms: ["masala chai", "chai", "tea"],                    price: 1.99 },
  { name: "Elachi Chai",         terms: ["elachi chai", "cardamom chai"],                  price: 2.99 },
  { name: "Gur Chai",            terms: ["gur chai", "jaggery chai"],                      price: 2.99 },
  { name: "Dudh Patti",          terms: ["dudh patti", "doodh patti"],                     price: 2.99 },
  { name: "Coffee - Indian Style", terms: ["coffee", "indian coffee"],                     price: 2.99 },
  { name: "Badam Milk",          terms: ["badam milk", "almond milk"],                     price: 5.99 },
  { name: "Mango Shake",         terms: ["mango shake"],                                   price: 5.5  },
  { name: "Strawberry Shake",    terms: ["strawberry shake"],                              price: 5.5  },
  { name: "Oreo Shake",          terms: ["oreo shake"],                                    price: 5.5  },
  { name: "Chocolate Shake",     terms: ["chocolate shake", "choco shake"],                price: 5.5  },
  { name: "Vanilla Shake",       terms: ["vanilla shake"],                                 price: 5.5  },
  { name: "Mango Faluda",        terms: ["mango faluda", "faluda", "falooda"],              price: 8.5  },
  { name: "Strawberry Faluda",   terms: ["strawberry faluda"],                             price: 8.5  },
  { name: "Vanilla Faluda",      terms: ["vanilla faluda"],                                price: 8.5  },

  // ── Sides ───────────────────────────────────────────────────────────────────
  { name: "Butter (2 pcs)",    terms: ["butter"],                                          price: 0.99 },
  { name: "Dahi - 8 oz",       terms: ["dahi", "yogurt"],                                  price: 2.99 },
  { name: "Raita - 8 oz",      terms: ["raita"],                                           price: 2.99 },
  { name: "Extra Bhatura",     terms: ["extra bhatura"],                                   price: 2.5  },
  { name: "Extra Puri",        terms: ["extra puri"],                                      price: 1.5  },
  { name: "Choley - 8 oz",     terms: ["choley", "chole"],                                 price: 2.99 },
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
  one: 1, two: 2, three: 3, four: 4, five: 5,
  six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
};

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

export function parseOrderFromBotMessages(botTexts: string[]): DetectedOrderItem[] {
  const order = new Map<string, DetectedOrderItem>();

  for (const text of botTexts) {
    const lower = text.toLowerCase();

    // On a full recap, clear everything and rebuild from scratch from this message only
    if (isRecapMessage(text)) order.clear();

    // Pre-compute "instead of X" removals before quantity matching
    // e.g. "Instead of 1 Masala Chai, how about a Mango Lassi?" → delete Masala Chai
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
        const esc = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

        // 1. Explicit removal: "remove the Mix Veg Pakora", "without Mix Veg Pakora"
        if (isRemoval && new RegExp(
          `\\b(?:remov(?:e|ed|ing)|without|no more|cancel(?:l?ed)?|tak(?:en?|ing) (?:off|out)|drop(?:p(?:ed|ing))?)\\s+(?:the\\s+)?${esc}\\b`, "i"
        ).test(lower)) {
          order.delete(item.name);
          break;
        }

        // 2. Digit quantity: "2 Mix Veg Pakora", "1 Noodle Burger"
        const digitMatch = lower.match(new RegExp(`\\b([1-9]\\d*)\\s+${esc}\\b`));
        if (digitMatch) {
          order.set(item.name, { name: item.name, quantity: parseInt(digitMatch[1]), price: item.price });
          break;
        }

        // 3. Word quantity: "one Mix Veg Pakora", "two Chole Bhatura"
        const wordMatch = lower.match(new RegExp(`\\b(one|two|three|four|five|six|seven|eight|nine|ten)\\s+${esc}\\b`));
        if (wordMatch) {
          order.set(item.name, { name: item.name, quantity: WORD_QTY[wordMatch[1]] ?? 1, price: item.price });
          break;
        }
      }

      // Apply "instead of X" removal — overrides any quantity match above
      if (insteadOfRemoved.has(item.name)) {
        order.delete(item.name);
      }
    }
  }

  return Array.from(order.values());
}
