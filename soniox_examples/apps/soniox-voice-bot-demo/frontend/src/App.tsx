import { useState } from "react";
import { Conversation } from "./components/conversation";
import { Store } from "./components/Store";

type Tab = "ai" | "store";

function App() {
  const [tab, setTab] = useState<Tab>("ai");

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: "var(--bg)" }}>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <header
        className="flex-none flex items-center gap-3 px-5 py-3 border-b"
        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
      >
        {/* Logo mark */}
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm text-black flex-none"
          style={{ background: "var(--accent)" }}
        >
          P
        </div>

        {/* Brand */}
        <div className="flex flex-col leading-none mr-4">
          <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            Parkash Sweets
          </span>
          <span className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            Edmonton, AB
          </span>
        </div>

        {/* Tab switcher */}
        <div
          className="flex items-center gap-1 rounded-xl p-1"
          style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}
        >
          <TabButton
            active={tab === "ai"}
            onClick={() => setTab("ai")}
            icon={<MicIcon />}
            label="Order with Sierra"
          />
          <TabButton
            active={tab === "store"}
            onClick={() => setTab("store")}
            icon={<StoreIcon />}
            label="Browse Store"
          />
        </div>

        {/* Online indicator */}
        <div className="ml-auto flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>Online</span>
        </div>
      </header>

      {/* ── Main ────────────────────────────────────────────────────── */}
      <main className="flex-1 overflow-hidden">
        {tab === "ai" && <Conversation />}
        {tab === "store" && <Store />}
      </main>
    </div>
  );
}

// ─────────────────────────────────────────────
// Tab button
// ─────────────────────────────────────────────
function TabButton({
  active, onClick, icon, label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200"
      style={
        active
          ? {
              background: "var(--accent)",
              color: "#000",
              boxShadow: "0 1px 6px rgba(245,158,11,0.3)",
            }
          : {
              background: "transparent",
              color: "var(--text-muted)",
            }
      }
    >
      {icon}
      {label}
    </button>
  );
}

// ─────────────────────────────────────────────
// SVG Icons
// ─────────────────────────────────────────────
function MicIcon({ size = 13, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8"  y1="23" x2="16" y2="23" />
    </svg>
  );
}

function StoreIcon({ size = 13, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <path d="M16 10a4 4 0 0 1-8 0" />
    </svg>
  );
}

export default App;
