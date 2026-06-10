import { useEffect, useState } from "react";
import { Conversation } from "./components/conversation";
import { Store } from "./components/Store";

type Tab = "ai" | "store";
type Theme = "dark" | "light";
type POS = "clover" | "square";

function useIsMobile(breakpoint = 640) {
  const [m, setM] = useState(() => window.innerWidth < breakpoint);
  useEffect(() => {
    const fn = () => setM(window.innerWidth < breakpoint);
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, [breakpoint]);
  return m;
}

function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try { return (localStorage.getItem("theme") as Theme) || "light"; }
    catch { return "light"; }
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch { /* */ }
  }, [theme]);

  const toggle = () => setTheme(t => t === "dark" ? "light" : "dark");
  return [theme, toggle];
}

function App() {
  const [tab, setTab] = useState<Tab>(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("payment")) return "store";
    try { return (localStorage.getItem("lastTab") as Tab) || "ai"; }
    catch { return "ai"; }
  });

  useEffect(() => {
    try { localStorage.setItem("lastTab", tab); } catch { /* */ }
  }, [tab]);
  const [pos, setPos] = useState<POS>(() => {
    try { return (localStorage.getItem("pos") as POS) || "clover"; }
    catch { return "clover"; }
  });

  useEffect(() => {
    try { localStorage.setItem("pos", pos); } catch { /* */ }
  }, [pos]);

  const isMobile = useIsMobile();
  const [theme, toggleTheme] = useTheme();

  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: "var(--bg)" }}>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <header
        className="flex-none flex items-center gap-3 px-4 py-3 border-b"
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
        <div className="flex flex-col leading-none">
          <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            Parkash Sweets
          </span>
          <span className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            Edmonton, AB
          </span>
        </div>

        {/* Tab switcher — desktop only */}
        {!isMobile && (
          <div
            className="flex items-center gap-1 rounded-xl p-1 ml-4"
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
        )}

        {/* Right side: POS selector + theme toggle + online indicator */}
        <div className="ml-auto flex items-center gap-3">
          <select
            value={pos}
            onChange={e => setPos(e.target.value as POS)}
            className="text-xs rounded-lg px-2 py-1.5 outline-none cursor-pointer"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border)",
              color: "var(--text)",
            }}
            title="POS System"
          >
            <option value="clover">Clover</option>
            <option value="square">Square</option>
          </select>

          <ThemeToggle theme={theme} onToggle={toggleTheme} />

          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
            {!isMobile && (
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>Online</span>
            )}
          </div>
        </div>
      </header>

      {/* ── Main ────────────────────────────────────────────────────── */}
      <main
        className="flex-1 overflow-hidden"
        style={{ paddingBottom: isMobile ? 64 : 0 }}
      >
        {tab === "ai" && <Conversation pos={pos} />}
        {tab === "store" && <Store pos={pos} />}
      </main>

      {/* ── Mobile bottom nav ───────────────────────────────────────── */}
      {isMobile && (
        <nav
          className="fixed bottom-0 inset-x-0 flex border-t z-40"
          style={{
            background: "var(--surface)",
            borderColor: "var(--border)",
            height: 64,
          }}
        >
          <MobileNavBtn
            active={tab === "ai"}
            onClick={() => setTab("ai")}
            icon={<MicIcon size={22} />}
            label="Order"
          />
          <MobileNavBtn
            active={tab === "store"}
            onClick={() => setTab("store")}
            icon={<StoreIcon size={22} />}
            label="Browse"
          />
        </nav>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Desktop tab button
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
// Mobile bottom nav button
// ─────────────────────────────────────────────
function MobileNavBtn({
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
      className="flex-1 flex flex-col items-center justify-center gap-1 transition-all duration-150 active:scale-95"
      style={{ color: active ? "var(--accent)" : "var(--text-dim)" }}
    >
      {icon}
      <span className="text-xs font-semibold">{label}</span>
    </button>
  );
}

// ─────────────────────────────────────────────
// Theme toggle slider
// ─────────────────────────────────────────────
function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const isLight = theme === "light";
  return (
    <button
      onClick={onToggle}
      aria-label={isLight ? "Switch to dark mode" : "Switch to light mode"}
      style={{
        position: "relative",
        width: 52,
        height: 26,
        borderRadius: 13,
        border: "none",
        background: isLight
          ? "linear-gradient(135deg, #fcd34d 0%, #f59e0b 100%)"
          : "linear-gradient(135deg, #1e1e2e 0%, #0f0f1a 100%)",
        cursor: "pointer",
        padding: 0,
        flexShrink: 0,
        outline: "none",
        boxShadow: isLight
          ? "0 0 0 1.5px rgba(245,158,11,0.35), 0 2px 8px rgba(245,158,11,0.15)"
          : "0 0 0 1.5px rgba(255,255,255,0.07), 0 2px 8px rgba(0,0,0,0.4)",
        transition: "background 0.35s ease, box-shadow 0.35s ease",
      }}
    >
      {/* sliding thumb */}
      <span
        style={{
          position: "absolute",
          top: 3,
          left: isLight ? 3 : 29,
          width: 20,
          height: 20,
          borderRadius: "50%",
          background: "#ffffff",
          boxShadow: "0 1px 5px rgba(0,0,0,0.28)",
          transition: "left 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: isLight ? "#f59e0b" : "#818cf8",
        }}
      >
        {isLight ? <SunIcon size={11} /> : <MoonIcon size={11} />}
      </span>
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

function SunIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1"  x2="12" y2="3"  />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22"  x2="5.64" y2="5.64"  />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1"  y1="12" x2="3"  y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64"  x2="19.78" y2="4.22"  />
    </svg>
  );
}

function MoonIcon({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

export default App;
