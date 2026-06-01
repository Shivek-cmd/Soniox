import { Conversation } from "./components/conversation";

function App() {
  return (
    <div className="h-screen flex flex-col overflow-hidden" style={{ background: "var(--bg)" }}>
      {/* Header */}
      <header
        className="flex-none flex items-center gap-3 px-5 py-3 border-b"
        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
      >
        {/* Logo */}
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center font-bold text-sm text-black flex-none"
          style={{ background: "var(--accent)" }}
        >
          P
        </div>

        <div className="flex flex-col leading-none">
          <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
            Parkash Sweets
          </span>
          <span className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            AI Voice Ordering
          </span>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Online
          </span>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 overflow-hidden">
        <Conversation />
      </main>
    </div>
  );
}

export default App;
