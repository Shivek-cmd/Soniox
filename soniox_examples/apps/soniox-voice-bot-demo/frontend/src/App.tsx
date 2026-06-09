import { useEffect, useState } from "react";
import { Conversation } from "./components/conversation";
import { Store } from "./components/Store";

type Tab = "ai" | "store";
type Theme = "dark" | "light";

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
    try { return (localStorage.getItem("theme") as Theme) || "dark"; }
    catch { return "dark"; }
  });

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("theme", theme); } catch { /* */ }
  }, [theme]);

  const toggle = () => setTheme(t => t === "dark" ? "light" : "dark");
  return [theme, toggle];
}

function App() {
  const [tab, setTab] = useState<Tab>("ai");
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

        {/* Right side: theme toggle + online indicator */}
        <div className="ml-auto flex items-center gap-3">
          <button
            onClick={toggleTheme}
            className="flex items-center justify-center rounded-lg transition-all duration-200 active:scale-90"
            style={{
              width: 32,
              height: 32,
              background: "var(--surface-raised)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
            }}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            {theme === "dark" ? <SunIcon size={14} /> : <MoonIcon size={14} />}
          </button>

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
        {tab === "ai" && <Conversation />}
        {tab === "store" && <Store />}
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
