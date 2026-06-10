import { useEffect, useState } from "react";
import { MENU_CATEGORIES } from "../utils/menuData";

const STORE_API: string = import.meta.env.VITE_STORE_API_URL ?? "/store-api";

type ApiItem = { name: string; description?: string; price: number; category_id?: string; category_name?: string };
type ApiCategory = { id: string; name: string };

export function MenuPanel({ pos = "clover" }: { pos?: string }) {
  const [apiCategories, setApiCategories] = useState<ApiCategory[] | null>(null);
  const [apiItems, setApiItems]           = useState<ApiItem[] | null>(null);
  const [loading, setLoading]             = useState(false);
  const [activeCategory, setActiveCategory] = useState<string>("");

  useEffect(() => {
    setLoading(true);
    setApiCategories(null);
    setApiItems(null);
    fetch(`${STORE_API}/menu?pos=${pos}`)
      .then((r) => r.json())
      .then((data) => {
        const cats: ApiCategory[] = data.categories ?? [];
        const items: ApiItem[]    = (data.items ?? []).map((i: ApiItem & { price: number }) => ({
          ...i,
          price: i.price / 100,
        }));
        setApiCategories(cats);
        setApiItems(items);
        setActiveCategory(cats[0]?.id ?? "");
      })
      .catch(() => {
        setApiCategories([]);
        setApiItems([]);
      })
      .finally(() => setLoading(false));
  }, [pos]);

  // Fallback to static data while loading or if fetch failed with no results
  const useFallback = !loading && (!apiItems || apiItems.length === 0);

  const categories = useFallback
    ? MENU_CATEGORIES.map((c) => ({ id: c.id, name: c.label }))
    : (apiCategories ?? []);

  const effectiveActive = activeCategory || categories[0]?.id || "";

  const items = useFallback
    ? (MENU_CATEGORIES.find((c) => c.id === effectiveActive)?.items ?? [])
    : (apiItems ?? []).filter((i) => i.category_id === effectiveActive);

  return (
    <div className="h-full flex flex-col overflow-hidden" style={{ background: "var(--bg)" }}>

      {/* Header */}
      <div
        className="flex-none px-4 pt-4 pb-3 border-b"
        style={{ borderColor: "var(--border)" }}
      >
        <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--text)" }}>
          Full Menu
        </h2>

        {/* Category pills — horizontally scrollable */}
        <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: "none" }}>
          {loading ? (
            <span className="text-xs px-3 py-1.5" style={{ color: "var(--text-dim)" }}>Loading…</span>
          ) : (
            categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setActiveCategory(cat.id)}
                className="flex-none px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 whitespace-nowrap"
                style={
                  effectiveActive === cat.id
                    ? { background: "var(--accent)", color: "#000" }
                    : {
                        background: "var(--surface-raised)",
                        color: "var(--text-muted)",
                        border: "1px solid var(--border)",
                      }
                }
              >
                {cat.name}
              </button>
            ))
          )}
        </div>
      </div>

      {/* Items list */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <span className="text-xs" style={{ color: "var(--text-dim)" }}>Loading menu…</span>
          </div>
        ) : (
          <div className="flex flex-col gap-2 animate-tab-in">
            {items.map((item, i) => (
              <div
                key={item.name}
                className="flex items-start justify-between gap-3 rounded-xl px-3 py-2.5"
                style={{
                  background: "var(--surface-raised)",
                  border: "1px solid var(--border)",
                  animationDelay: `${i * 30}ms`,
                }}
              >
                <div className="flex-1 min-w-0">
                  <p
                    className="text-sm font-medium leading-snug"
                    style={{ color: "var(--text)" }}
                  >
                    {item.name}
                  </p>
                  {item.description && (
                    <p
                      className="text-xs mt-0.5 leading-relaxed"
                      style={{ color: "var(--text-dim)" }}
                    >
                      {item.description}
                    </p>
                  )}
                </div>
                <span
                  className="flex-none text-sm font-semibold mt-0.5"
                  style={{ color: "var(--accent)" }}
                >
                  ${item.price.toFixed(2)}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* All prices note */}
        {!loading && (
          <p className="text-xs mt-3 pb-2 text-center" style={{ color: "var(--text-dim)" }}>
            All prices in CAD · Tax not included
          </p>
        )}
      </div>
    </div>
  );
}
