export interface DetectedOrderItem {
  name: string;
  quantity: number;
  price: number;
}

interface MenuEntry {
  name: string;
  terms: string[];
  price: number;
}

// All menu items with search terms for parsing bot messages
const MENU: MenuEntry[] = [
  { name: "Aloo Samosa", terms: ["aloo samosa", "samosa"], price: 3.0 },
  { name: "Noodle Samosa", terms: ["noodle samosa"], price: 4.5 },
  { name: "Chole Bhatura", terms: ["chole bhatura", "chole bhature", "choley bhatura"], price: 7.99 },
  { name: "Choley Puri", terms: ["choley puri", "chole puri"], price: 7.99 },
  { name: "Aloo Puri", terms: ["aloo puri"], price: 7.99 },
  { name: "Chaat Papdi", terms: ["chaat papdi", "papdi chaat", "papri chaat"], price: 5.99 },
  { name: "Dahi Bhalla", terms: ["dahi bhalla"], price: 5.99 },
  { name: "Samosa Choley", terms: ["samosa choley", "samosa chole", "samosa chaat"], price: 6.5 },
  { name: "Tawa Tikki Chaat", terms: ["tawa tikki chaat", "tikki chaat"], price: 6.0 },
  { name: "Tawa Tikki Choley", terms: ["tawa tikki choley", "tikki choley"], price: 7.5 },
  { name: "Mix Veg Pakora", terms: ["mix veg pakora", "veg pakora"], price: 8.5 },
  { name: "Paneer Pakora", terms: ["paneer pakora"], price: 11.5 },
  { name: "Gobi Pakora", terms: ["gobi pakora"], price: 10.5 },
  { name: "Baingan Pakora", terms: ["baingan pakora"], price: 8.5 },
  { name: "Mirchi Pakora", terms: ["mirchi pakora"], price: 10.5 },
  { name: "Hara Bara Kabab", terms: ["hara bara kabab", "hara bhara"], price: 10.5 },
  { name: "Dahi Kabab", terms: ["dahi kabab"], price: 9.0 },
  { name: "Mushroom Delux", terms: ["mushroom delux", "mushroom"], price: 9.0 },
  { name: "Aloo Cutlet", terms: ["aloo cutlet"], price: 10.5 },
  { name: "Parkash Platter", terms: ["parkash platter", "platter"], price: 15.99 },
  { name: "Aloo Finger", terms: ["aloo finger"], price: 8.5 },
  { name: "Spring Roll", terms: ["spring roll"], price: 8.0 },
  { name: "Bread Roll", terms: ["bread roll"], price: 3.0 },
  { name: "Aloo Bread Pakora", terms: ["aloo bread pakora"], price: 3.0 },
  { name: "Paneer Aloo Bread Pakora", terms: ["paneer aloo bread pakora"], price: 5.0 },
  { name: "Aloo Tikki Burger", terms: ["aloo tikki burger"], price: 6.5 },
  { name: "Noodle Burger", terms: ["noodle burger"], price: 7.5 },
  { name: "Paneer Tikki Burger", terms: ["paneer tikki burger"], price: 8.5 },
  { name: "Grilled Cheese Sandwich", terms: ["grilled cheese sandwich", "grilled cheese"], price: 5.5 },
  { name: "Super Veggie Sandwich", terms: ["super veggie sandwich", "veggie sandwich"], price: 6.99 },
  { name: "Sweet Corn Sandwich", terms: ["sweet corn sandwich"], price: 6.99 },
  { name: "Paneer Mayo Sandwich", terms: ["paneer mayo sandwich"], price: 7.99 },
  { name: "Aloo Parantha", terms: ["aloo parantha", "aloo paratha"], price: 4.0 },
  { name: "Gobi Parantha", terms: ["gobi parantha", "gobi paratha"], price: 4.5 },
  { name: "Muli Parantha", terms: ["muli parantha", "mooli parantha", "muli paratha"], price: 4.5 },
  { name: "Paneer Parantha", terms: ["paneer parantha", "paneer paratha"], price: 4.99 },
  { name: "Mix Parantha", terms: ["mix parantha", "mix paratha"], price: 4.99 },
  { name: "Rasmalai", terms: ["rasmalai", "kesar rasmalai"], price: 4.0 },
  { name: "Gulab Jamun", terms: ["gulab jamun"], price: 3.0 },
  { name: "Rasgulla", terms: ["rasgulla"], price: 3.0 },
  { name: "Moong Dal Halwa", terms: ["moong dal halwa"], price: 5.5 },
  { name: "Gajrela", terms: ["gajrela", "gajar halwa"], price: 4.5 },
  { name: "Mango Lassi", terms: ["mango lassi"], price: 4.99 },
  { name: "Sweet Lassi", terms: ["sweet lassi"], price: 4.49 },
  { name: "Salty Lassi", terms: ["salty lassi"], price: 4.49 },
  { name: "Masala Chai", terms: ["masala chai"], price: 1.99 },
  { name: "Elachi Chai", terms: ["elachi chai"], price: 2.99 },
  { name: "Chai", terms: ["chai"], price: 1.99 },
  { name: "Badam Milk", terms: ["badam milk"], price: 5.99 },
  { name: "Mango Shake", terms: ["mango shake"], price: 5.5 },
  { name: "Mango Faluda", terms: ["mango faluda", "faluda", "falooda"], price: 8.5 },
];

export function parseOrderFromBotMessages(botTexts: string[]): DetectedOrderItem[] {
  const allText = botTexts.join(" ").toLowerCase();
  const detected = new Map<string, DetectedOrderItem>();

  for (const item of MENU) {
    for (const term of item.terms) {
      const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      // Only add item if a number (1-99) explicitly precedes it.
      // This prevents adding items Sierra merely *mentions* or *suggests*.
      const match = allText.match(new RegExp(`\\b([1-9]\\d?)\\s+${escaped}`));
      if (!match) continue;

      const quantity = parseInt(match[1]);
      const existing = detected.get(item.name);
      if (!existing || existing.quantity < quantity) {
        detected.set(item.name, { name: item.name, quantity, price: item.price });
      }
      break;
    }
  }

  return Array.from(detected.values());
}
