import { useState } from "react";
import { MENU_CATEGORIES } from "../utils/menuData";

export function MenuPanel() {
  const [activeCategory, setActiveCategory] = useState(MENU_CATEGORIES[0].id);

  const category = MENU_CATEGORIES.find((c) => c.id === activeCategory)!;

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
          {MENU_CATEGORIES.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className="flex-none px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 whitespace-nowrap"
              style={
                activeCategory === cat.id
                  ? { background: "var(--accent)", color: "#000" }
                  : {
                      background: "var(--surface-raised)",
                      color: "var(--text-muted)",
                      border: "1px solid var(--border)",
                    }
              }
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Items list */}
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <div className="flex flex-col gap-2 animate-tab-in">
          {category.items.map((item, i) => (
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

        {/* All prices note */}
        <p className="text-xs mt-3 pb-2 text-center" style={{ color: "var(--text-dim)" }}>
          All prices in CAD · Tax not included
        </p>
      </div>
    </div>
  );
}
