import { useEffect, useReducer, useState } from "react";
import { MENU_CATEGORIES } from "../utils/menuData";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface StoreModifier {
  id: string;
  name: string;
  price: number; // cents
}

interface StoreModifierGroup {
  id: string;
  name: string;
  min_required: number;
  max_allowed: number;
  modifiers: StoreModifier[];
}

interface StoreItem {
  id: string;
  name: string;
  description: string;
  price: number; // cents
  price_display: string;
  category_id: string;
  category_name: string;
  image_url: string | null;
  modifier_groups: StoreModifierGroup[];
  available?: boolean;
}

interface StoreCategory {
  id: string;
  name: string;
  sort_order: number;
}

interface CartEntry {
  key: string;
  item: StoreItem;
  quantity: number;
  selected_modifiers: StoreModifier[];
  modifier_extra: number; // cents
  note: string;
}

type CartAction =
  | { type: "ADD";       entry: CartEntry }
  | { type: "INCREMENT"; key: string }
  | { type: "DECREMENT"; key: string }
  | { type: "REMOVE";    key: string }
  | { type: "CLEAR" };

// ─────────────────────────────────────────────────────────────────────────────
// Cart reducer
// ─────────────────────────────────────────────────────────────────────────────

function cartReducer(state: CartEntry[], action: CartAction): CartEntry[] {
  switch (action.type) {
    case "ADD": {
      const idx = state.findIndex(e => e.key === action.entry.key);
      if (idx !== -1) {
        return state.map((e, i) =>
          i === idx ? { ...e, quantity: e.quantity + action.entry.quantity } : e
        );
      }
      return [...state, action.entry];
    }
    case "INCREMENT":
      return state.map(e => e.key === action.key ? { ...e, quantity: e.quantity + 1 } : e);
    case "DECREMENT":
      return state.map(e =>
        e.key === action.key ? { ...e, quantity: Math.max(1, e.quantity - 1) } : e
      );
    case "REMOVE":
      return state.filter(e => e.key !== action.key);
    case "CLEAR":
      return [];
    default:
      return state;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Hooks & helpers
// ─────────────────────────────────────────────────────────────────────────────

function useIsMobile(breakpoint = 640) {
  const [m, setM] = useState(() => window.innerWidth < breakpoint);
  useEffect(() => {
    const fn = () => setM(window.innerWidth < breakpoint);
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, [breakpoint]);
  return m;
}

const STORE_API: string = import.meta.env.VITE_STORE_API_URL ?? "/store-api";

// Category → emoji + gradient theme
const CAT_THEME: Record<string, { emoji: string; grad: string; accent: string }> = {
  samosa:          { emoji: "🥟", grad: "linear-gradient(135deg,#f59e0b1a,#92400e1a)", accent: "#f59e0b" },
  parkash_classic: { emoji: "🍛", grad: "linear-gradient(135deg,#ea580c1a,#7c2d121a)", accent: "#ea580c" },
  chaat:           { emoji: "🍲", grad: "linear-gradient(135deg,#84cc161a,#1665301a)", accent: "#84cc16" },
  pakora:          { emoji: "🧆", grad: "linear-gradient(135deg,#d977061a,#78350f1a)", accent: "#d97706" },
  bread_pakora:    { emoji: "🥪", grad: "linear-gradient(135deg,#b453091a,#7c2d121a)", accent: "#b45309" },
  burger_sandwich: { emoji: "🍔", grad: "linear-gradient(135deg,#ef44441a,#9918291a)", accent: "#ef4444" },
  parantha:        { emoji: "🫓", grad: "linear-gradient(135deg,#fbbf241a,#92400e1a)", accent: "#fbbf24" },
  desserts:        { emoji: "🍮", grad: "linear-gradient(135deg,#f43f5e1a,#8817351a)", accent: "#f43f5e" },
  shake_faluda:    { emoji: "🥛", grad: "linear-gradient(135deg,#8b5cf61a,#4c1d951a)", accent: "#8b5cf6" },
  beverages:       { emoji: "🍵", grad: "linear-gradient(135deg,#0d94801a,#0640341a)", accent: "#0d9488" },
  sides:           { emoji: "🥗", grad: "linear-gradient(135deg,#22c55e1a,#14532d1a)", accent: "#22c55e" },
  all_snacks:      { emoji: "🍱", grad: "linear-gradient(135deg,#f59e0b1a,#78350f1a)", accent: "#f59e0b" },
};

function catTheme(catId: string) {
  return (
    CAT_THEME[catId] ?? {
      emoji: "🍽️",
      grad:  "linear-gradient(135deg,#f59e0b1a,#92400e1a)",
      accent: "#f59e0b",
    }
  );
}

function cartKey(itemId: string, modIds: string[]): string {
  return `${itemId}__${[...modIds].sort().join(",")}`;
}

function cad(cents: number) {
  return `$${(cents / 100).toFixed(2)}`;
}

// ── Item image map ─────────────────────────────────────────────────────────────
// "bread pakora" listed before "pakora" so the longer key wins first.
const ITEM_IMAGES: { keys: string[]; url: string }[] = [
  { keys: ["bread pakora"],                              url: "https://images.unsplash.com/photo-1574484284002-952d92456975?auto=format&fit=crop&w=400&q=80" },
  { keys: ["samosa"],                                    url: "https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=400&q=80" },
  { keys: ["pakora", "bhajia", "bhaji"],                 url: "https://images.unsplash.com/photo-1567188040759-fb8a883dc6d8?auto=format&fit=crop&w=400&q=80" },
  { keys: ["pani puri", "bhel", "chaat", "dahi puri"],  url: "https://images.unsplash.com/photo-1567337710282-00832b415979?auto=format&fit=crop&w=400&q=80" },
  { keys: ["parantha", "paratha", "roti", "naan"],       url: "https://images.unsplash.com/photo-1600609500046-0ac3c4be1dd7?auto=format&fit=crop&w=400&q=80" },
  { keys: ["gulab jamun"],                               url: "https://images.unsplash.com/photo-1571167530149-c1105da4c2c7?auto=format&fit=crop&w=400&q=80" },
  { keys: ["jalebi"],                                    url: "https://images.unsplash.com/photo-1590123710338-8eecc2b2dd73?auto=format&fit=crop&w=400&q=80" },
  { keys: ["barfi", "burfi", "ladoo", "laddoo", "mithai"], url: "https://images.unsplash.com/photo-1609681536894-87a04a29a2e2?auto=format&fit=crop&w=400&q=80" },
  { keys: ["kheer", "halwa", "rasmalai", "ras malai"],   url: "https://images.unsplash.com/photo-1578985545062-69928b1d9587?auto=format&fit=crop&w=400&q=80" },
  { keys: ["lassi", "shake", "faluda", "falooda"],       url: "https://images.unsplash.com/photo-1544145945-f90425340c7e?auto=format&fit=crop&w=400&q=80" },
  { keys: ["chai", "tea"],                               url: "https://images.unsplash.com/photo-1579584425555-c3ce17fd4351?auto=format&fit=crop&w=400&q=80" },
  { keys: ["mango", "juice"],                            url: "https://images.unsplash.com/photo-1603833665858-e61d17a86224?auto=format&fit=crop&w=400&q=80" },
  { keys: ["burger"],                                    url: "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?auto=format&fit=crop&w=400&q=80" },
  { keys: ["sandwich"],                                  url: "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=400&q=80" },
  { keys: ["paneer", "tikka"],                           url: "https://images.unsplash.com/photo-1561564645-1539b4e09f3b?auto=format&fit=crop&w=400&q=80" },
  { keys: ["dal", "curry", "makhani"],                   url: "https://images.unsplash.com/photo-1546833999-b9f581a1996d?auto=format&fit=crop&w=400&q=80" },
];

function getItemImage(name: string, imageUrl: string | null): string | null {
  if (imageUrl) return imageUrl;
  const lower = name.toLowerCase();
  for (const entry of ITEM_IMAGES) {
    if (entry.keys.some(k => lower.includes(k))) return entry.url;
  }
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Store component
// ─────────────────────────────────────────────────────────────────────────────

export function Store() {
  const [categories, setCategories] = useState<StoreCategory[]>([]);
  const [items,      setItems]      = useState<StoreItem[]>([]);
  const [loading,    setLoading]    = useState(true);

  const [activeCategory, setActiveCategory] = useState("all");
  const [search,         setSearch]         = useState("");

  const [selectedItem,   setSelectedItem]   = useState<StoreItem | null>(null);
  const [showCheckout,   setShowCheckout]   = useState(false);
  const [confirmedOrder, setConfirmedOrder] = useState<{ order_id: string; total: number; discount_amount?: number; discount_name?: string } | null>(null);
  const [showCart,       setShowCart]       = useState(false);

  const [cart, dispatch] = useReducer(cartReducer, []);
  const isMobile = useIsMobile();

  useEffect(() => { loadMenu(); }, []);

  async function loadMenu() {
    try {
      const resp = await fetch(`${STORE_API}/menu`, {
        signal: AbortSignal.timeout(6000),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setCategories(data.categories);
      setItems(data.items);
    } catch {
      loadFallback();
    } finally {
      setLoading(false);
    }
  }

  function loadFallback() {
    const cats: StoreCategory[] = MENU_CATEGORIES.map((c, i) => ({
      id: c.id, name: c.label, sort_order: i,
    }));
    const itemList: StoreItem[] = MENU_CATEGORIES.flatMap(c =>
      c.items.map(item => ({
        id:              `local-${item.name.toLowerCase().replace(/\W+/g, "-")}`,
        name:            item.name,
        description:     item.description ?? "",
        price:           Math.round((item.price ?? 0) * 100),
        price_display:   `$${(item.price ?? 0).toFixed(2)}`,
        category_id:     c.id,
        category_name:   c.label,
        image_url:       null,
        modifier_groups: [],
        available:       true,
      }))
    );
    setCategories(cats);
    setItems(itemList);
  }

  const filtered = items.filter(item => {
    const catMatch = activeCategory === "all" || item.category_id === activeCategory;
    const q = search.trim().toLowerCase();
    const searchMatch = !q
      || item.name.toLowerCase().includes(q)
      || item.description.toLowerCase().includes(q);
    return catMatch && searchMatch;
  });

  const cartCount = cart.reduce((s, e) => s + e.quantity, 0);
  const cartTotal = cart.reduce((s, e) => s + (e.item.price + e.modifier_extra) * e.quantity, 0);

  function addDirect(item: StoreItem) {
    dispatch({
      type: "ADD",
      entry: { key: cartKey(item.id, []), item, quantity: 1, selected_modifiers: [], modifier_extra: 0, note: "" },
    });
  }

  return (
    <div className="h-full flex overflow-hidden" style={{ background: "var(--bg)" }}>

      {/* ── Menu area ─────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">

        {/* Top bar */}
        <div
          className="flex-none px-4 pt-3 pb-3 border-b"
          style={{ borderColor: "var(--border)", background: "var(--surface)" }}
        >
          {/* Search */}
          <div className="relative mb-3">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: "var(--text-dim)" }}>
              <SearchIcon />
            </span>
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search menu…"
              className="w-full pl-9 pr-9 py-2.5 rounded-xl text-sm outline-none transition-colors"
              style={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border)",
                color: "var(--text)",
              }}
            />
            {search && (
              <button
                onClick={() => setSearch("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs leading-none"
                style={{ color: "var(--text-dim)" }}
              >
                ✕
              </button>
            )}
          </div>

          {/* Category pills */}
          <div className="flex gap-2 overflow-x-auto pb-0.5" style={{ scrollbarWidth: "none" }}>
            <Pill active={activeCategory === "all"} onClick={() => setActiveCategory("all")}>
              All
            </Pill>
            {categories.map(cat => (
              <Pill
                key={cat.id}
                active={activeCategory === cat.id}
                onClick={() => setActiveCategory(cat.id)}
              >
                {cat.name}
              </Pill>
            ))}
          </div>
        </div>

        {/* Section label */}
        {!loading && (
          <div className="flex-none flex items-baseline gap-2 px-4 pt-3 pb-1">
            <span
              className="text-xs font-semibold uppercase tracking-widest"
              style={{ color: "var(--text-dim)" }}
            >
              {search
                ? `Results for "${search}"`
                : activeCategory === "all"
                ? "Full Menu"
                : categories.find(c => c.id === activeCategory)?.name ?? ""}
            </span>
            <span className="text-xs" style={{ color: "var(--text-dim)" }}>
              — {filtered.length} {filtered.length === 1 ? "item" : "items"}
            </span>
          </div>
        )}

        {/* Grid — 2 cols on mobile, auto-fill on desktop */}
        <div
          className="flex-1 overflow-y-auto px-4 pt-2 pb-6"
          style={{ paddingBottom: isMobile ? 88 : 24 }}
        >
          {loading ? (
            <SkeletonGrid isMobile={isMobile} />
          ) : filtered.length === 0 ? (
            <EmptyState query={search} />
          ) : (
            <div
              className="grid gap-3"
              style={{
                gridTemplateColumns: isMobile
                  ? "repeat(2, 1fr)"
                  : "repeat(auto-fill,minmax(200px,1fr))",
              }}
            >
              {filtered.map(item => (
                <ItemCard
                  key={item.id}
                  item={item}
                  isMobile={isMobile}
                  onOpen={() => setSelectedItem(item)}
                  onAdd={() => {
                    if (item.modifier_groups.length > 0) setSelectedItem(item);
                    else addDirect(item);
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Cart sidebar — desktop only ───────────────────────── */}
      {!isMobile && (
        <CartSidebar
          cart={cart}
          count={cartCount}
          total={cartTotal}
          dispatch={dispatch}
          onCheckout={() => setShowCheckout(true)}
        />
      )}

      {/* ── Mobile cart FAB ───────────────────────────────────── */}
      {isMobile && (
        <button
          onClick={() => setShowCart(true)}
          className="fixed flex items-center gap-2 rounded-full transition-all active:scale-95"
          style={{
            bottom: 80,
            right: 16,
            zIndex: 30,
            padding: "12px 18px",
            background: "var(--accent)",
            color: "#000",
            boxShadow: "0 4px 24px rgba(245,158,11,0.45)",
            fontWeight: 700,
            fontSize: 14,
          }}
        >
          <CartIcon color="#000" />
          <span>
            {cartCount > 0
              ? `${cartCount} item${cartCount > 1 ? "s" : ""} · ${cad(cartTotal)}`
              : "Cart"}
          </span>
        </button>
      )}

      {/* ── Mobile cart bottom sheet ──────────────────────────── */}
      {isMobile && showCart && (
        <MobileCartSheet
          cart={cart}
          count={cartCount}
          total={cartTotal}
          dispatch={dispatch}
          onClose={() => setShowCart(false)}
          onCheckout={() => { setShowCart(false); setShowCheckout(true); }}
        />
      )}

      {/* ── Modals ────────────────────────────────────────────── */}
      {selectedItem && (
        <ItemModal
          item={selectedItem}
          isMobile={isMobile}
          onClose={() => setSelectedItem(null)}
          onAdd={entry => { dispatch({ type: "ADD", entry }); setSelectedItem(null); }}
        />
      )}

      {showCheckout && !confirmedOrder && (
        <CheckoutModal
          cart={cart}
          total={cartTotal}
          isMobile={isMobile}
          onClose={() => setShowCheckout(false)}
          onConfirmed={order => {
            setConfirmedOrder(order);
            dispatch({ type: "CLEAR" });
          }}
        />
      )}

      {confirmedOrder && (
        <SuccessOverlay
          order={confirmedOrder}
          isMobile={isMobile}
          onDone={() => { setConfirmedOrder(null); setShowCheckout(false); setShowCart(false); }}
        />
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Category pill
// ─────────────────────────────────────────────────────────────────────────────

function Pill({
  active, onClick, children,
}: {
  active: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="flex-none px-3.5 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all duration-150"
      style={
        active
          ? { background: "var(--accent)", color: "#000" }
          : {
              background: "var(--surface-raised)",
              color: "var(--text-muted)",
              border: "1px solid var(--border)",
            }
      }
    >
      {children}
    </button>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Item card
// ─────────────────────────────────────────────────────────────────────────────

function ItemCard({
  item, onOpen, onAdd, isMobile,
}: {
  item: StoreItem; onOpen: () => void; onAdd: () => void; isMobile: boolean;
}) {
  const theme = catTheme(item.category_id);
  const [flash, setFlash] = useState(false);

  function handleAdd(e: React.MouseEvent) {
    e.stopPropagation();
    if (item.modifier_groups.length > 0) { onAdd(); return; }
    setFlash(true);
    onAdd();
    setTimeout(() => setFlash(false), 700);
  }

  const thumbHeight = isMobile ? 90 : 108;

  return (
    <div
      onClick={onOpen}
      className="flex flex-col rounded-2xl overflow-hidden cursor-pointer group"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        boxShadow: "0 2px 12px rgba(0,0,0,0.2)",
        transition: "transform 0.15s ease, box-shadow 0.15s ease",
        opacity: item.available === false ? 0.62 : 1,
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(-2px)";
        (e.currentTarget as HTMLElement).style.boxShadow = "0 8px 28px rgba(0,0,0,0.35)";
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
        (e.currentTarget as HTMLElement).style.boxShadow = "0 2px 12px rgba(0,0,0,0.2)";
      }}
    >
      {/* Thumbnail */}
      <div
        className="flex-none relative flex items-center justify-center overflow-hidden"
        style={{ height: thumbHeight, background: theme.grad }}
      >
        <FoodImage
          src={getItemImage(item.name, item.image_url)}
          alt={item.name}
          emoji={theme.emoji}
          emojiSize={isMobile ? 36 : 48}
        />
        {item.available === false && (
          <div
            className="absolute inset-0 flex items-center justify-center"
            style={{ background: "rgba(0,0,0,0.52)" }}
          >
            <span
              className="text-xs font-bold px-2.5 py-1 rounded-lg tracking-wide"
              style={{ background: "rgba(239,68,68,0.92)", color: "#fff" }}
            >
              SOLD OUT
            </span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col px-2.5 pt-2 pb-2.5">
        <p
          className="font-semibold leading-snug"
          style={{ color: "var(--text)", fontSize: isMobile ? 12 : 14 }}
        >
          {item.name}
        </p>

        {!isMobile && item.description && (
          <p
            className="text-xs mt-0.5 leading-relaxed"
            style={{
              color: "var(--text-dim)",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {item.description}
          </p>
        )}

        {!isMobile && item.modifier_groups.length > 0 && (
          <p className="text-xs mt-1" style={{ color: "var(--text-dim)" }}>
            Customizable ›
          </p>
        )}

        {/* Price + Add */}
        <div className="flex items-center justify-between mt-auto pt-2">
          <span
            className="font-bold"
            style={{ color: theme.accent, fontSize: isMobile ? 12 : 14 }}
          >
            {item.price_display}
          </span>
          <button
            onClick={handleAdd}
            disabled={item.available === false}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg font-bold transition-all duration-150 active:scale-95 disabled:cursor-not-allowed"
            style={{
              fontSize: isMobile ? 11 : 12,
              background: item.available === false ? "var(--surface-raised)" : flash ? "#22c55e" : "var(--accent)",
              color: item.available === false ? "var(--text-dim)" : "#000",
              minWidth: isMobile ? 44 : 52,
              justifyContent: "center",
            }}
          >
            {item.available === false ? "Out" : flash ? "✓" : "+ Add"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Cart sidebar — desktop
// ─────────────────────────────────────────────────────────────────────────────

function CartSidebar({
  cart, count, total, dispatch, onCheckout,
}: {
  cart: CartEntry[];
  count: number;
  total: number;
  dispatch: React.Dispatch<CartAction>;
  onCheckout: () => void;
}) {
  const gst   = Math.round(total * 0.05);
  const grand = total + gst;

  return (
    <div
      className="flex-none flex flex-col border-l"
      style={{ width: 304, borderColor: "var(--border)", background: "var(--surface)" }}
    >
      {/* Header */}
      <div
        className="flex-none flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <CartIcon />
          <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            Your Cart
          </span>
        </div>
        {count > 0 && (
          <span
            className="text-xs px-2 py-0.5 rounded-full font-bold"
            style={{ background: "var(--accent)", color: "#000" }}
          >
            {count}
          </span>
        )}
      </div>

      {/* Items list */}
      <div className="flex-1 overflow-y-auto">
        {cart.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center gap-3 px-4 select-none">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center"
              style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}
            >
              <span style={{ fontSize: 28 }}>🛒</span>
            </div>
            <p className="text-xs text-center leading-relaxed" style={{ color: "var(--text-dim)" }}>
              Your cart is empty.
              <br />
              Pick something delicious!
            </p>
          </div>
        ) : (
          <div className="px-3 py-2 flex flex-col gap-2">
            {cart.map(entry => (
              <CartRow key={entry.key} entry={entry} dispatch={dispatch} />
            ))}
          </div>
        )}
      </div>

      {/* Totals + CTA */}
      {cart.length > 0 && (
        <div className="flex-none border-t" style={{ borderColor: "var(--border)" }}>
          <div className="px-4 py-3 flex flex-col gap-1.5">
            <PriceRow label="Subtotal" value={total} />
            <PriceRow label="GST (5%)" value={gst} />
            <div
              className="flex items-center justify-between pt-2.5 mt-1 border-t"
              style={{ borderColor: "var(--border)" }}
            >
              <span className="text-sm font-bold" style={{ color: "var(--text)" }}>Total</span>
              <span className="text-base font-black" style={{ color: "var(--accent)" }}>
                {cad(grand)}
              </span>
            </div>
          </div>
          <div className="px-4 pb-4">
            <button
              onClick={onCheckout}
              className="w-full py-3 rounded-xl text-sm font-bold text-black transition-all hover:opacity-90 active:scale-[.98]"
              style={{
                background: "var(--accent)",
                boxShadow: "0 2px 16px rgba(245,158,11,0.3)",
              }}
            >
              Place Order →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Mobile cart bottom sheet
// ─────────────────────────────────────────────────────────────────────────────

function MobileCartSheet({
  cart, count, total, dispatch, onClose, onCheckout,
}: {
  cart: CartEntry[];
  count: number;
  total: number;
  dispatch: React.Dispatch<CartAction>;
  onClose: () => void;
  onCheckout: () => void;
}) {
  const gst   = Math.round(total * 0.05);
  const grand = total + gst;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className="absolute bottom-0 inset-x-0 flex flex-col rounded-t-2xl overflow-hidden"
        style={{
          background: "var(--surface)",
          maxHeight: "82vh",
          borderTop: "1px solid var(--border)",
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Drag handle */}
        <div className="flex-none flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full" style={{ background: "var(--border)" }} />
        </div>

        {/* Header */}
        <div
          className="flex-none flex items-center justify-between px-4 py-2.5 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <div className="flex items-center gap-2">
            <CartIcon />
            <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
              Your Cart
            </span>
          </div>
          <div className="flex items-center gap-2">
            {count > 0 && (
              <span
                className="text-xs px-2 py-0.5 rounded-full font-bold"
                style={{ background: "var(--accent)", color: "#000" }}
              >
                {count}
              </span>
            )}
            <button
              onClick={onClose}
              className="text-sm w-7 h-7 flex items-center justify-center rounded-full"
              style={{ color: "var(--text-dim)", background: "var(--surface-raised)" }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Items */}
        <div className="flex-1 overflow-y-auto">
          {cart.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3 select-none">
              <span style={{ fontSize: 48 }}>🛒</span>
              <p className="text-sm font-medium" style={{ color: "var(--text-dim)" }}>
                Your cart is empty
              </p>
              <p className="text-xs" style={{ color: "var(--text-dim)" }}>
                Go back and add some items
              </p>
            </div>
          ) : (
            <div className="px-3 py-2 flex flex-col gap-2">
              {cart.map(entry => (
                <CartRow key={entry.key} entry={entry} dispatch={dispatch} />
              ))}
            </div>
          )}
        </div>

        {/* Totals + CTA */}
        {cart.length > 0 && (
          <div className="flex-none border-t" style={{ borderColor: "var(--border)" }}>
            <div className="px-4 py-3 flex flex-col gap-1.5">
              <PriceRow label="Subtotal" value={total} />
              <PriceRow label="GST (5%)" value={gst} />
              <div
                className="flex items-center justify-between pt-2.5 mt-1 border-t"
                style={{ borderColor: "var(--border)" }}
              >
                <span className="text-sm font-bold" style={{ color: "var(--text)" }}>Total</span>
                <span className="text-base font-black" style={{ color: "var(--accent)" }}>
                  {cad(grand)}
                </span>
              </div>
            </div>
            <div className="px-4 pb-8">
              <button
                onClick={onCheckout}
                className="w-full py-4 rounded-xl text-sm font-bold text-black transition-all hover:opacity-90 active:scale-[.98]"
                style={{
                  background: "var(--accent)",
                  boxShadow: "0 2px 16px rgba(245,158,11,0.3)",
                }}
              >
                Place Order →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function CartRow({ entry, dispatch }: { entry: CartEntry; dispatch: React.Dispatch<CartAction> }) {
  const theme     = catTheme(entry.item.category_id);
  const unitPrice = entry.item.price + entry.modifier_extra;

  return (
    <div
      className="flex items-start gap-2.5 rounded-xl px-2.5 py-2"
      style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}
    >
      {/* Emoji thumb */}
      <div
        className="flex-none w-9 h-9 rounded-lg flex items-center justify-center text-xl"
        style={{ background: theme.grad }}
      >
        {theme.emoji}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold truncate" style={{ color: "var(--text)" }}>
          {entry.item.name}
        </p>
        {entry.selected_modifiers.length > 0 && (
          <p className="text-xs truncate" style={{ color: "var(--text-dim)" }}>
            {entry.selected_modifiers.map(m => m.name).join(", ")}
          </p>
        )}

        <div className="flex items-center justify-between mt-1.5">
          {/* Qty stepper */}
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => dispatch({ type: "DECREMENT", key: entry.key })}
              className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold"
              style={{ background: "var(--border)", color: "var(--text-muted)" }}
            >
              −
            </button>
            <span className="text-xs font-semibold w-4 text-center" style={{ color: "var(--text)" }}>
              {entry.quantity}
            </span>
            <button
              onClick={() => dispatch({ type: "INCREMENT", key: entry.key })}
              className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold"
              style={{ background: "var(--accent)", color: "#000" }}
            >
              +
            </button>
          </div>
          <span className="text-xs font-bold" style={{ color: theme.accent }}>
            {cad(unitPrice * entry.quantity)}
          </span>
        </div>
      </div>

      {/* Remove */}
      <button
        onClick={() => dispatch({ type: "REMOVE", key: entry.key })}
        className="flex-none mt-0.5 text-xs leading-none transition-colors hover:text-red-400"
        style={{ color: "var(--text-dim)" }}
        title="Remove item"
      >
        ✕
      </button>
    </div>
  );
}

function PriceRow({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</span>
      <span className="text-xs font-medium" style={{ color: "var(--text)" }}>{cad(value)}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Item modal
// ─────────────────────────────────────────────────────────────────────────────

function ItemModal({
  item, onClose, onAdd, isMobile,
}: {
  item: StoreItem;
  onClose: () => void;
  onAdd: (entry: CartEntry) => void;
  isMobile: boolean;
}) {
  const theme = catTheme(item.category_id);

  const [qty,          setQty]          = useState(1);
  const [selectedMods, setSelectedMods] = useState<Record<string, StoreModifier[]>>({});

  const allMods     = Object.values(selectedMods).flat();
  const modExtra    = allMods.reduce((s, m) => s + m.price, 0);
  const unitPrice   = item.price + modExtra;
  const totalPrice  = unitPrice * qty;

  const requiredMet = item.modifier_groups
    .filter(g => g.min_required > 0)
    .every(g => (selectedMods[g.id]?.length ?? 0) >= g.min_required);

  function toggleMod(group: StoreModifierGroup, mod: StoreModifier) {
    setSelectedMods(prev => {
      const cur = prev[group.id] ?? [];
      if (group.max_allowed === 1) {
        return { ...prev, [group.id]: cur.some(m => m.id === mod.id) ? [] : [mod] };
      }
      const has = cur.some(m => m.id === mod.id);
      const next = has
        ? cur.filter(m => m.id !== mod.id)
        : cur.length < group.max_allowed ? [...cur, mod] : cur;
      return { ...prev, [group.id]: next };
    });
  }

  function handleAdd() {
    const modIds = allMods.map(m => m.id);
    onAdd({
      key:                cartKey(item.id, modIds),
      item,
      quantity:           qty,
      selected_modifiers: allMods,
      modifier_extra:     modExtra,
      note:               "",
    });
  }

  const panelStyle: React.CSSProperties = isMobile
    ? {
        width: "100%",
        height: "100%",
        borderRadius: 0,
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }
    : {
        width: 440,
        maxWidth: "100%",
        maxHeight: "86vh",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 16,
        boxShadow: "0 24px 80px rgba(0,0,0,0.75)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      };

  return (
    <Overlay onClose={onClose} isMobile={isMobile}>
      <div style={panelStyle} onClick={e => e.stopPropagation()}>
        {/* Hero */}
        <div
          className="flex-none relative flex items-center justify-center overflow-hidden"
          style={{ height: isMobile ? 160 : 140, background: theme.grad }}
        >
          <FoodImage
            src={getItemImage(item.name, item.image_url)}
            alt={item.name}
            emoji={theme.emoji}
            emojiSize={isMobile ? 80 : 72}
          />
          <button
            onClick={onClose}
            className="absolute top-3 right-3 w-8 h-8 rounded-full flex items-center justify-center text-xs"
            style={{ background: "rgba(0,0,0,0.45)", color: "#fff" }}
          >
            ✕
          </button>
          {/* Category badge */}
          <span
            className="absolute bottom-3 left-4 text-xs px-2.5 py-1 rounded-full font-medium"
            style={{ background: "rgba(0,0,0,0.45)", color: "#fff", backdropFilter: "blur(4px)" }}
          >
            {item.category_name}
          </span>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="flex items-start justify-between gap-2 mb-1">
            <h2 className="text-lg font-bold leading-tight" style={{ color: "var(--text)" }}>
              {item.name}
            </h2>
            <span className="text-base font-black flex-none" style={{ color: theme.accent }}>
              {item.price_display}
            </span>
          </div>

          {item.description && (
            <p className="text-sm leading-relaxed mb-5" style={{ color: "var(--text-muted)" }}>
              {item.description}
            </p>
          )}

          {/* Modifier groups */}
          {item.modifier_groups.map(group => {
            const sel = selectedMods[group.id] ?? [];
            return (
              <div key={group.id} className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span
                    className="text-xs font-semibold uppercase tracking-wide"
                    style={{ color: "var(--text-dim)" }}
                  >
                    {group.name}
                  </span>
                  <span
                    className="text-xs px-2 py-0.5 rounded-full"
                    style={
                      group.min_required > 0
                        ? { background: "rgba(245,158,11,0.15)", color: "var(--accent)" }
                        : { background: "var(--surface-raised)", color: "var(--text-dim)" }
                    }
                  >
                    {group.min_required > 0 ? "Required" : "Optional"}
                  </span>
                </div>

                <div className="flex flex-col gap-1.5">
                  {group.modifiers.map(mod => {
                    const isSel = sel.some(m => m.id === mod.id);
                    const isRadio = group.max_allowed === 1;
                    return (
                      <button
                        key={mod.id}
                        onClick={() => toggleMod(group, mod)}
                        className="flex items-center justify-between px-3 py-3 rounded-xl text-sm transition-all"
                        style={{
                          background: isSel ? `${theme.accent}18` : "var(--surface-raised)",
                          border: `1px solid ${isSel ? theme.accent : "var(--border)"}`,
                        }}
                      >
                        <div className="flex items-center gap-2.5">
                          <span
                            className="w-4 h-4 flex-none flex items-center justify-center"
                            style={{
                              background: isSel ? theme.accent : "transparent",
                              border: `1.5px solid ${isSel ? theme.accent : "var(--border)"}`,
                              borderRadius: isRadio ? "50%" : 4,
                            }}
                          >
                            {isSel && (
                              <span style={{ fontSize: 9, fontWeight: 900, color: "#000" }}>✓</span>
                            )}
                          </span>
                          <span className="text-sm" style={{ color: "var(--text)" }}>{mod.name}</span>
                        </div>
                        {mod.price > 0 && (
                          <span className="text-xs" style={{ color: "var(--text-dim)" }}>
                            +{cad(mod.price)}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div
          className="flex-none flex items-center gap-3 px-5 py-4 border-t"
          style={{ borderColor: "var(--border)", background: "var(--surface)" }}
        >
          {/* Quantity */}
          <div
            className="flex items-center gap-3 rounded-xl px-3 py-2"
            style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}
          >
            <button
              onClick={() => setQty(q => Math.max(1, q - 1))}
              className="w-7 h-7 rounded-lg flex items-center justify-center font-bold text-sm"
              style={{ background: "var(--border)", color: "var(--text-muted)" }}
            >
              −
            </button>
            <span className="text-sm font-bold w-5 text-center" style={{ color: "var(--text)" }}>
              {qty}
            </span>
            <button
              onClick={() => setQty(q => q + 1)}
              className="w-7 h-7 rounded-lg flex items-center justify-center font-bold text-sm"
              style={{ background: "var(--accent)", color: "#000" }}
            >
              +
            </button>
          </div>

          {/* Add to cart */}
          <button
            onClick={handleAdd}
            disabled={!requiredMet || item.available === false}
            className="flex-1 py-3 rounded-xl text-sm font-bold transition-all active:scale-[.98] disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: (requiredMet && item.available !== false) ? "var(--accent)" : "var(--surface-raised)",
              color: (requiredMet && item.available !== false) ? "#000" : "var(--text-dim)",
              boxShadow: (requiredMet && item.available !== false) ? "0 2px 12px rgba(245,158,11,0.3)" : "none",
            }}
          >
            {item.available === false ? "Currently Unavailable" : `Add to Cart — ${cad(totalPrice)}`}
          </button>
        </div>
      </div>
    </Overlay>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Checkout modal
// ─────────────────────────────────────────────────────────────────────────────

interface DiscountOption { id: string; name: string; }

function CheckoutModal({
  cart, total, onClose, onConfirmed, isMobile,
}: {
  cart: CartEntry[];
  total: number;
  onClose: () => void;
  onConfirmed: (order: { order_id: string; total: number; discount_amount?: number; discount_name?: string }) => void;
  isMobile: boolean;
}) {
  const [name,      setName]      = useState("");
  const [phone,     setPhone]     = useState("");
  const [orderType, setOrderType] = useState<"pickup" | "dine_in">("pickup");
  const [note,      setNote]      = useState("");
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState<string | null>(null);

  // ── Promo code state ───────────────────────────────────────────────────────
  const [promoInput,     setPromoInput]     = useState("");
  const [appliedDiscount, setAppliedDiscount] = useState<DiscountOption | null>(null);
  const [promoError,     setPromoError]     = useState<string | null>(null);
  const [discountList,   setDiscountList]   = useState<DiscountOption[]>([]);

  // Fetch available discounts once when modal opens
  useEffect(() => {
    fetch(`${STORE_API}/discounts`)
      .then(r => r.ok ? r.json() : { discounts: [] })
      .then(d => setDiscountList(d.discounts ?? []))
      .catch(() => {});
  }, []);

  function applyPromo() {
    const code = promoInput.trim().toUpperCase();
    if (!code) return;
    const match = discountList.find(d => d.name.toUpperCase() === code);
    if (match) {
      setAppliedDiscount(match);
      setPromoError(null);
    } else {
      setAppliedDiscount(null);
      setPromoError("Invalid promo code.");
    }
  }

  function removePromo() {
    setAppliedDiscount(null);
    setPromoInput("");
    setPromoError(null);
  }

  // ── Pricing ────────────────────────────────────────────────────────────────
  // We don't know the exact discount amount until the server applies it in Clover,
  // so we show the subtotal line with a "Discount applied" notice. The confirmed
  // success overlay shows the actual savings returned by the API.
  const gst   = Math.round(total * 0.05);
  const grand = total + gst;

  // ── Submit ─────────────────────────────────────────────────────────────────
  async function confirm() {
    if (!name.trim()) { setError("Please enter your name."); return; }
    setLoading(true); setError(null);
    try {
      const body: Record<string, unknown> = {
        items: cart.map(e => ({
          item_id:      e.item.id,
          name:         e.item.name,
          price:        e.item.price,
          quantity:     e.quantity,
          modifier_ids: e.selected_modifiers.map(m => m.id),
          note:         e.note,
        })),
        order_type:     orderType,
        customer_name:  name.trim(),
        customer_phone: phone.trim(),
        note:           note.trim(),
      };
      if (appliedDiscount) body.discount_code = appliedDiscount.name;

      const resp = await fetch(`${STORE_API}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const payload = await resp.json().catch(() => ({}));
        throw new Error((payload as any).detail ?? `Server error (${resp.status})`);
      }
      const data = await resp.json();
      onConfirmed({
        order_id:        data.order_id,
        total:           data.total ?? grand,
        discount_amount: data.discount_amount,
        discount_name:   data.discount_name,
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to place order. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const panelStyle: React.CSSProperties = isMobile
    ? {
        width: "100%",
        height: "100%",
        borderRadius: 0,
        background: "var(--surface)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }
    : {
        width: 480,
        maxWidth: "100%",
        maxHeight: "90vh",
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 16,
        boxShadow: "0 24px 80px rgba(0,0,0,0.75)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      };

  return (
    <Overlay onClose={onClose} isMobile={isMobile}>
      <div style={panelStyle} onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div
          className="flex-none flex items-center justify-between px-5 py-4 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <div>
            <h2 className="text-base font-bold" style={{ color: "var(--text)" }}>Confirm Order</h2>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
              Parkash Sweets · Edmonton, AB
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-full flex items-center justify-center text-sm"
            style={{ color: "var(--text-dim)", background: "var(--surface-raised)" }}
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">

          {/* Order type */}
          <div>
            <Label>Order Type</Label>
            <div className="flex gap-2 mt-2">
              {(["pickup", "dine_in"] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setOrderType(t)}
                  className="flex-1 py-3 rounded-xl text-sm font-medium transition-all"
                  style={
                    orderType === t
                      ? { background: "var(--accent)", color: "#000" }
                      : {
                          background: "var(--surface-raised)",
                          color: "var(--text-muted)",
                          border: "1px solid var(--border)",
                        }
                  }
                >
                  {t === "pickup" ? "🥡  Pickup" : "🍽️  Dine-in"}
                </button>
              ))}
            </div>
          </div>

          {/* Name */}
          <div>
            <Label>Your Name *</Label>
            <input
              type="text"
              placeholder="e.g. Harpreet Singh"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full mt-2 px-4 py-3 rounded-xl text-sm outline-none transition-colors"
              style={{
                background: "var(--surface-raised)",
                border: `1px solid ${name.trim() ? "var(--accent)" : "var(--border)"}`,
                color: "var(--text)",
              }}
            />
          </div>

          {/* Phone */}
          <div>
            <Label>Phone (optional)</Label>
            <input
              type="tel"
              placeholder="780-555-0100"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              className="w-full mt-2 px-4 py-3 rounded-xl text-sm outline-none"
              style={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border)",
                color: "var(--text)",
              }}
            />
          </div>

          {/* Promo code */}
          <div>
            <Label>Promo Code</Label>
            {appliedDiscount ? (
              <div
                className="flex items-center justify-between mt-2 px-4 py-3 rounded-xl"
                style={{
                  background: "rgba(34,197,94,0.08)",
                  border: "1px solid rgba(34,197,94,0.25)",
                }}
              >
                <div className="flex items-center gap-2">
                  <span style={{ color: "#22c55e", fontSize: 14 }}>✓</span>
                  <span className="text-sm font-semibold" style={{ color: "#22c55e" }}>
                    {appliedDiscount.name}
                  </span>
                  <span className="text-xs" style={{ color: "var(--text-dim)" }}>applied</span>
                </div>
                <button
                  onClick={removePromo}
                  className="text-xs"
                  style={{ color: "var(--text-dim)" }}
                >
                  Remove
                </button>
              </div>
            ) : (
              <div className="flex gap-2 mt-2">
                <input
                  type="text"
                  placeholder="Enter code"
                  value={promoInput}
                  onChange={e => { setPromoInput(e.target.value.toUpperCase()); setPromoError(null); }}
                  onKeyDown={e => { if (e.key === "Enter") applyPromo(); }}
                  className="flex-1 px-4 py-3 rounded-xl text-sm outline-none font-mono tracking-wide"
                  style={{
                    background: "var(--surface-raised)",
                    border: `1px solid ${promoError ? "rgba(239,68,68,0.5)" : "var(--border)"}`,
                    color: "var(--text)",
                  }}
                />
                <button
                  onClick={applyPromo}
                  disabled={!promoInput.trim()}
                  className="px-4 py-3 rounded-xl text-sm font-semibold transition-all active:scale-95 disabled:opacity-40"
                  style={{ background: "var(--surface-raised)", color: "var(--text)", border: "1px solid var(--border)" }}
                >
                  Apply
                </button>
              </div>
            )}
            {promoError && (
              <p className="text-xs mt-1.5" style={{ color: "#f87171" }}>{promoError}</p>
            )}
          </div>

          {/* Special Instructions */}
          <div>
            <Label>Special Instructions</Label>
            <textarea
              placeholder="Any special requests…"
              value={note}
              onChange={e => setNote(e.target.value)}
              rows={2}
              className="w-full mt-2 px-4 py-3 rounded-xl text-sm outline-none resize-none"
              style={{
                background: "var(--surface-raised)",
                border: "1px solid var(--border)",
                color: "var(--text)",
              }}
            />
          </div>

          {/* Order summary */}
          <div
            className="rounded-xl overflow-hidden"
            style={{ border: "1px solid var(--border)", background: "var(--surface-raised)" }}
          >
            <div className="px-4 py-2 border-b" style={{ borderColor: "var(--border)" }}>
              <span
                className="text-xs font-semibold uppercase tracking-wide"
                style={{ color: "var(--text-dim)" }}
              >
                Order Summary
              </span>
            </div>
            <div className="px-4 py-3 flex flex-col gap-1.5">
              {cart.map(e => (
                <div key={e.key} className="flex justify-between gap-2 text-xs">
                  <span style={{ color: "var(--text-muted)" }}>
                    {e.quantity}× {e.item.name}
                    {e.selected_modifiers.length > 0 && (
                      <span style={{ color: "var(--text-dim)" }}>
                        {" "}({e.selected_modifiers.map(m => m.name).join(", ")})
                      </span>
                    )}
                  </span>
                  <span className="font-medium flex-none" style={{ color: "var(--text)" }}>
                    {cad((e.item.price + e.modifier_extra) * e.quantity)}
                  </span>
                </div>
              ))}

              <div className="flex flex-col gap-1 border-t pt-2 mt-1" style={{ borderColor: "var(--border)" }}>
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-muted)" }}>Subtotal</span>
                  <span style={{ color: "var(--text)" }}>{cad(total)}</span>
                </div>
                {appliedDiscount && (
                  <div className="flex justify-between text-xs">
                    <span style={{ color: "#22c55e" }}>Promo: {appliedDiscount.name}</span>
                    <span className="font-semibold" style={{ color: "#22c55e" }}>Applied ✓</span>
                  </div>
                )}
                <div className="flex justify-between text-xs">
                  <span style={{ color: "var(--text-muted)" }}>GST (5%)</span>
                  <span style={{ color: "var(--text)" }}>{cad(gst)}</span>
                </div>
                <div
                  className="flex justify-between text-sm font-bold border-t pt-2 mt-0.5"
                  style={{ borderColor: "var(--border)" }}
                >
                  <span style={{ color: "var(--text)" }}>Total</span>
                  <span style={{ color: "var(--accent)" }}>
                    {cad(grand)}
                    {appliedDiscount && (
                      <span className="text-xs font-normal ml-1" style={{ color: "var(--text-dim)" }}>
                        (before discount)
                      </span>
                    )}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div
              className="px-3 py-2 rounded-xl text-xs"
              style={{
                background: "rgba(239,68,68,0.1)",
                border: "1px solid rgba(239,68,68,0.2)",
                color: "#f87171",
              }}
            >
              {error}
            </div>
          )}
        </div>

        {/* CTA */}
        <div
          className="flex-none px-5 py-4 border-t"
          style={{ borderColor: "var(--border)", background: "var(--surface)" }}
        >
          <button
            onClick={confirm}
            disabled={loading || !name.trim()}
            className="w-full py-3.5 rounded-xl text-sm font-bold text-black transition-all active:scale-[.98] disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: "var(--accent)",
              boxShadow: "0 2px 16px rgba(245,158,11,0.3)",
            }}
          >
            {loading ? "Placing Order…" : `Confirm Order — ${cad(grand)}`}
          </button>
        </div>
      </div>
    </Overlay>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Order success overlay
// ─────────────────────────────────────────────────────────────────────────────

function SuccessOverlay({
  order, onDone, isMobile,
}: {
  order: { order_id: string; total: number; discount_amount?: number; discount_name?: string };
  onDone: () => void;
  isMobile: boolean;
}) {
  const hasSavings = (order.discount_amount ?? 0) > 0;

  return (
    <Overlay onClose={onDone} isMobile={isMobile}>
      <div
        className="flex flex-col items-center text-center rounded-2xl px-8 py-10"
        style={{
          width: isMobile ? "100%" : 380,
          maxWidth: "100%",
          background: "var(--surface)",
          border: isMobile ? "none" : "1px solid var(--border)",
          borderRadius: isMobile ? 0 : 16,
          boxShadow: isMobile ? "none" : "0 24px 80px rgba(0,0,0,0.75)",
          height: isMobile ? "100%" : "auto",
          justifyContent: isMobile ? "center" : undefined,
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Check circle */}
        <div
          className="w-24 h-24 rounded-full flex items-center justify-center mb-5"
          style={{
            background: "rgba(34,197,94,0.12)",
            border: "2px solid rgba(34,197,94,0.3)",
          }}
        >
          <span style={{ fontSize: 48 }}>✅</span>
        </div>

        <h2 className="text-2xl font-black mb-1" style={{ color: "var(--text)" }}>
          Order Placed!
        </h2>
        <p className="text-sm mb-6" style={{ color: "var(--text-muted)" }}>
          Your order is confirmed at Parkash Sweets.
        </p>

        {/* Savings banner */}
        {hasSavings && (
          <div
            className="w-full flex items-center justify-center gap-2 rounded-xl px-4 py-3 mb-4"
            style={{
              background: "rgba(34,197,94,0.1)",
              border: "1px solid rgba(34,197,94,0.25)",
            }}
          >
            <span style={{ fontSize: 18 }}>🎉</span>
            <span className="text-sm font-semibold" style={{ color: "#22c55e" }}>
              You saved {cad(order.discount_amount!)} with {order.discount_name}
            </span>
          </div>
        )}

        {/* Order details card */}
        <div
          className="w-full rounded-xl px-5 py-4 mb-6 text-left"
          style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}
        >
          <div className="flex justify-between mb-2">
            <span className="text-xs" style={{ color: "var(--text-dim)" }}>Order ID</span>
            <span
              className="text-xs font-bold"
              style={{ color: "var(--accent)", fontFamily: "monospace" }}
            >
              {order.order_id}
            </span>
          </div>
          <div className="flex justify-between mb-2">
            <span className="text-xs" style={{ color: "var(--text-dim)" }}>
              Total {hasSavings ? "(after discount + GST)" : "(incl. GST)"}
            </span>
            <span className="text-xs font-bold" style={{ color: "var(--text)" }}>
              {cad(order.total)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-xs" style={{ color: "var(--text-dim)" }}>Est. wait</span>
            <span className="text-xs font-bold" style={{ color: "#22c55e" }}>15 – 25 min</span>
          </div>
        </div>

        <button
          onClick={onDone}
          className="w-full py-4 rounded-xl text-sm font-bold text-black transition-all hover:opacity-90 active:scale-[.98]"
          style={{ background: "var(--accent)" }}
        >
          Back to Menu
        </button>
      </div>
    </Overlay>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Shared overlay wrapper — fixed inset-0 for reliable full-viewport coverage
// ─────────────────────────────────────────────────────────────────────────────

function Overlay({
  children, onClose, isMobile,
}: {
  children: React.ReactNode;
  onClose: () => void;
  isMobile: boolean;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className={`fixed inset-0 z-50 flex ${isMobile ? "items-stretch p-0" : "items-center justify-center p-4"}`}
      style={{ background: "rgba(0,0,0,0.72)", backdropFilter: "blur(6px)" }}
      onClick={onClose}
    >
      {children}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Utility components
// ─────────────────────────────────────────────────────────────────────────────

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="text-xs font-semibold uppercase tracking-wide"
      style={{ color: "var(--text-dim)" }}
    >
      {children}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// FoodImage — shows real photo when available; falls back to emoji on error
// ─────────────────────────────────────────────────────────────────────────────

function FoodImage({
  src, alt, emoji, emojiSize,
}: {
  src: string | null; alt: string; emoji: string; emojiSize: number;
}) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <span
        style={{
          fontSize: emojiSize,
          lineHeight: 1,
          filter: "drop-shadow(0 2px 8px rgba(0,0,0,0.25))",
          transition: "transform 0.2s ease",
        }}
        className="group-hover:scale-110"
      >
        {emoji}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className="absolute inset-0 w-full h-full object-cover"
      onError={() => setFailed(true)}
    />
  );
}

function SkeletonGrid({ isMobile }: { isMobile: boolean }) {
  return (
    <div
      className="grid gap-3"
      style={{
        gridTemplateColumns: isMobile
          ? "repeat(2, 1fr)"
          : "repeat(auto-fill,minmax(200px,1fr))",
      }}
    >
      {Array.from({ length: 12 }).map((_, i) => (
        <div
          key={i}
          className="rounded-2xl overflow-hidden animate-pulse"
          style={{
            height: isMobile ? 160 : 196,
            background: "var(--surface)",
            border: "1px solid var(--border)",
          }}
        />
      ))}
    </div>
  );
}

function EmptyState({ query }: { query: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 gap-3 select-none">
      <span style={{ fontSize: 40 }}>🔍</span>
      <p className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>
        {query ? `No results for "${query}"` : "No items in this category"}
      </p>
      <p className="text-xs" style={{ color: "var(--text-dim)" }}>
        Try a different search or category
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Icons
// ─────────────────────────────────────────────────────────────────────────────

function SearchIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function CartIcon({ color = "var(--text-muted)" }: { color?: string }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="21" r="1" /><circle cx="20" cy="21" r="1" />
      <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
    </svg>
  );
}
