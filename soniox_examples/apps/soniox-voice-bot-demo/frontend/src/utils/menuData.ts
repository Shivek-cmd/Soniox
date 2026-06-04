import MENU_DATA from "../../../menu.json";

// ── Types ─────────────────────────────────────────────────────────────────────

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

export interface ConversationDetails {
  name: string | null;
  phone: string | null;
  orderType: string | null; // "pickup" | "delivery" | "dine_in"
  instructions: string | null;
  isConfirmed: boolean;
}

// ── Derived from menu.json (single source of truth) ───────────────────────────

export const MENU_CATEGORIES: MenuCategory[] = MENU_DATA.categories.map((cat) => ({
  id: cat.id,
  label: cat.label,
  items: cat.items.map((item) => ({
    name: item.name,
    price: item.price,
    description: item.description || undefined,
  })),
}));

// Flat list used for real-time order parsing
interface MenuEntry {
  name: string;
  terms: string[];
  price: number;
}

const MENU: MenuEntry[] = MENU_DATA.categories.flatMap((cat) =>
  cat.items.map((item) => ({
    name: item.name,
    terms: item.terms,
    price: item.price,
  }))
);

// ── Conversation detail extraction ────────────────────────────────────────────

export function parseConversationDetails(
  messages: { type: string; text?: string; final_text?: string }[]
): ConversationDetails {
  const botTexts = messages.filter((m) => m.type === "llm_response").map((m) => m.text ?? "");
  const userTexts = messages.filter((m) => m.type === "transcription").map((m) => m.final_text ?? "");

  const botFull = botTexts.join(" ");
  const botLower = botFull.toLowerCase();
  const userFull = userTexts.join(" ");
  const allLower = botLower + " " + userFull.toLowerCase();

  // ── Name ──────────────────────────────────────────────────────────────────
  let name: string | null = null;
  const m1 = botFull.match(/[Tt]hank you,?\s+([A-Z][a-z]+)[!.,\s]/);
  if (m1) name = m1[1];
  if (!name) {
    const m2 = botFull.match(/under the name\s+([A-Z][a-z]+)/i);
    if (m2) name = m2[1];
  }
  if (!name) {
    const m3 = botFull.match(/,\s+for\s+([A-Z][a-z]+)[.,!]/);
    if (m3) name = m3[1];
  }

  // ── Phone ─────────────────────────────────────────────────────────────────
  let phone: string | null = null;
  const phoneDigits = userFull.match(/\b(\d{10})\b/);
  if (phoneDigits) {
    phone = phoneDigits[1];
  } else {
    const botPhoneMatch = botFull.match(
      /\b(\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d[-–\s,]+\d)\b/
    );
    if (botPhoneMatch) phone = botPhoneMatch[1].replace(/[^0-9]/g, "");
  }

  // ── Order type ────────────────────────────────────────────────────────────
  let orderType: string | null = null;
  if (allLower.includes("pickup")) orderType = "pickup";
  else if (allLower.includes("delivery")) orderType = "delivery";
  else if (allLower.includes("dine-in") || allLower.includes("dine in")) orderType = "dine_in";

  // ── Special instructions ──────────────────────────────────────────────────
  let instructions: string | null = null;
  const gotIt = botFull.match(
    /Got it[!,.]?\s+(.+?)(?:\.|What|Can I|Anything|And can|Your name)/i
  );
  if (gotIt) instructions = gotIt[1].trim();

  // ── Confirmed? ────────────────────────────────────────────────────────────
  const isConfirmed = botLower.includes("order confirmed");

  return { name, phone, orderType, instructions, isConfirmed };
}

// ── Real-time order parsing from bot messages ─────────────────────────────────

const WORD_QTY: Record<string, number> = {
  // English
  one: 1, two: 2, three: 3, four: 4, five: 5,
  six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
  // Punjabi (Gurmukhi)
  "ਇੱਕ": 1, "ਦੋ": 2, "ਤਿੰਨ": 3, "ਚਾਰ": 4, "ਪੰਜ": 5,
  "ਛੇ": 6, "ਸੱਤ": 7, "ਅੱਠ": 8, "ਨੌਂ": 9, "ਦਸ": 10,
  // Hindi (Devanagari)
  "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पाँच": 5,
  "पांच": 5, "छह": 6, "सात": 7, "आठ": 8, "नौ": 9, "दस": 10,
};

const hasNativeScript = (s: string): boolean => /[ऀ-ॿ਀-੿]/.test(s);

const isRecapMessage = (text: string): boolean =>
  /\bjust to confirm\b/i.test(text) ||
  /\byour order is\b/i.test(text) ||
  /\bso we have\b/i.test(text) ||
  /\bto recap\b/i.test(text) ||
  /\blet me confirm\b/i.test(text) ||
  /\bso you'?re (?:getting|ordering|having)\b/i.test(text) ||
  /\bso that'?s\s+[1-9one|two|three]/i.test(text) ||
  /ਤੁਹਾਡਾ order/.test(text) ||
  /order ਵਿੱਚ/.test(text) ||
  /ਦੱਸ ਦਿੰਦੀ ਹਾਂ/.test(text) ||
  /confirm ਕਰਦੇ ਹਾਂ/.test(text) ||
  /ਤਾਂ ਤੁਸੀਂ/.test(text) ||
  /आपका order/.test(text) ||
  /order में/.test(text) ||
  /confirm करते हैं/.test(text) ||
  /तो आपने/.test(text);

const REMOVAL_RE =
  /\b(?:remov(?:e|ed|ing)|without|no more|cancel(?:l?ed)?|tak(?:en?|ing) (?:off|out)|drop(?:p(?:ed|ing))?|no longer)\b/i;

const LATIN_WORD_QTY_KEYS = Object.keys(WORD_QTY)
  .filter((k) => !hasNativeScript(k))
  .join("|");

export function parseOrderFromBotMessages(botTexts: string[]): DetectedOrderItem[] {
  const order = new Map<string, DetectedOrderItem>();

  for (const text of botTexts) {
    const lower = text.toLowerCase();
    const isCurrentRecap = isRecapMessage(text);

    if (isCurrentRecap) order.clear();

    // Pre-compute "instead of X" removals
    const insteadOfRemoved = new Set<string>();
    const insteadMatch = lower.match(
      /\binstead of\s+([\w\s]+?)(?:,|\.|(?:\s+(?:how about|we|would|i'll|let)))/i
    );
    if (insteadMatch) {
      const phrase = insteadMatch[1].trim();
      for (const item of MENU) {
        if (item.terms.some((t) => phrase.includes(t))) {
          insteadOfRemoved.add(item.name);
        }
      }
    }

    const isRemoval = REMOVAL_RE.test(text);

    for (const item of MENU) {
      for (const term of item.terms) {
        const native = hasNativeScript(term);
        const esc = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

        // ── Removal ──────────────────────────────────────────────────────────
        if (isRemoval) {
          const remPat = native
            ? new RegExp(
                `(?:remov(?:e|ed|ing)|without|no more|cancel(?:l?ed)?)\\s+(?:the\\s+)?${esc}`,
                "i"
              )
            : new RegExp(
                `\\b(?:remov(?:e|ed|ing)|without|no more|cancel(?:l?ed)?|tak(?:en?|ing) (?:off|out)|drop(?:p(?:ed|ing))?)\\s+(?:the\\s+)?${esc}\\b`,
                "i"
              );
          if (remPat.test(native ? text : lower)) {
            order.delete(item.name);
            break;
          }
        }

        if (native) {
          // ── Native script (Gurmukhi / Devanagari) ────────────────────────
          // Numbers in Sierra's text are always Latin digits even in Punjabi/Hindi.

          const nDigit = text.match(new RegExp(`([1-9]\\d*)\\s+${esc}`));
          if (nDigit) {
            order.set(item.name, { name: item.name, quantity: parseInt(nDigit[1]), price: item.price });
            break;
          }

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

          if (isCurrentRecap && text.includes(term)) {
            if (!order.has(item.name)) {
              order.set(item.name, { name: item.name, quantity: 1, price: item.price });
            }
            break;
          }
        } else {
          // ── Latin script ──────────────────────────────────────────────────

          const digitMatch = lower.match(new RegExp(`\\b([1-9]\\d*)\\s+${esc}\\b`));
          if (digitMatch) {
            order.set(item.name, { name: item.name, quantity: parseInt(digitMatch[1]), price: item.price });
            break;
          }

          const wordMatch = lower.match(new RegExp(`\\b(${LATIN_WORD_QTY_KEYS})\\s+${esc}\\b`));
          if (wordMatch) {
            order.set(item.name, { name: item.name, quantity: WORD_QTY[wordMatch[1]] ?? 1, price: item.price });
            break;
          }
        }
      }

      if (insteadOfRemoved.has(item.name)) {
        order.delete(item.name);
      }
    }
  }

  return Array.from(order.values());
}
