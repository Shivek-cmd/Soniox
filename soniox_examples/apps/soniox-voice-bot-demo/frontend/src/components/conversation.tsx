import { useEffect, useMemo, useRef, useState } from "react";
import useAutoScroll from "../hooks/useAutoScroll";
import {
  messageSchema,
  orderConfirmedSchema,
  updateMessages,
  type Message,
  type OrderConfirmed,
} from "../utils/messages";
import { useAudioChunkPlayer } from "../hooks/useAudioChunkPlayer";
import { useMicrophone } from "../hooks/useMicrophone";
import { ChatMessage } from "./renderer";
import { MenuPanel } from "./MenuPanel";
import { parseOrderFromBotMessages } from "../utils/menuData";

const WS_URL = import.meta.env.VITE_SONIOX_VOICE_BOT_WS_URL;

type CallStatus = "idle" | "connecting" | "listening" | "speaking" | "processing";

const LANGUAGES = [
  { code: "pa", name: "Punjabi" },
  { code: "hi", name: "Hindi"   },
  { code: "en", name: "English" },
];

// ─────────────────────────────────────────────
export function Conversation() {
  const ws = useRef<WebSocket | null>(null);

  const [lang, setLang]                     = useState("pa");
  const [messages, setMessages]             = useState<Message[]>([]);
  const [confirmedOrder, setConfirmedOrder] = useState<OrderConfirmed | null>(null);
  const [status, setStatus]                 = useState<CallStatus>("idle");
  const [error, setError]                   = useState<string | null>(null);

  const scrollRef = useAutoScroll(messages);

  const { startMicrophoneStream, cleanupMicrophoneStream } = useMicrophone({
    onData: (d) => ws.current?.send(d),
    onError: () => { setError("Microphone error — allow access and retry."); stop(); },
  });
  const { cleanupAudioPlayer, prepareAudioPlayer, addAudioChunk, interruptAudio } =
    useAudioChunkPlayer({});

  const stop = () => {
    ws.current?.close(); ws.current = null;
    cleanupMicrophoneStream(); cleanupAudioPlayer();
    setStatus("idle");
  };

  const startCall = () => {
    if (ws.current) return;
    setStatus("connecting"); setMessages([]); setConfirmedOrder(null); setError(null);
    prepareAudioPlayer();
    const url = new URL(WS_URL);
    url.searchParams.append("language", lang);
    url.searchParams.append("voice", "Nina");
    const sock = new WebSocket(url.toString());
    ws.current = sock;
    sock.onopen  = () => { setStatus("listening"); startMicrophoneStream(); };
    sock.onerror = () => { setError("Cannot connect to voice server."); stop(); };
    sock.onclose = stop;
    sock.onmessage = async (e) => {
      try {
        if (typeof e.data === "string") {
          const d = JSON.parse(e.data);
          if (d.type === "user_speech_start") { interruptAudio(); setStatus("listening"); return; }
          if (d.type === "user_speech_end")   { setStatus("processing"); return; }
          if (d.type === "session_start" || d.type === "metric") return;
          if (d.type === "order_confirmed") {
            const r = orderConfirmedSchema.safeParse(d);
            if (r.success) setConfirmedOrder(r.data);
            return;
          }
          const msg = messageSchema.parse(d);
          setMessages((p) => updateMessages(p, msg));
          if (msg.type === "transcription")  { interruptAudio(); setStatus("listening"); }
          if (msg.type === "llm_response")   setStatus("speaking");
        } else if (e.data instanceof Blob) {
          addAudioChunk(await e.data.arrayBuffer());
        }
      } catch (err) { console.error(err); }
    };
  };

  useEffect(() => () => stop(), []); // eslint-disable-line

  const isActive = status !== "idle";

  return (
    <div className="h-full flex flex-col relative" style={{ background: "var(--bg)" }}>

      {/* ── Three-column main area ──────────────────────── */}
      <div className="flex-1 flex overflow-hidden min-h-0">

        {/* ① Chat */}
        <div
          className="flex flex-col border-r"
          style={{ width: "38%", borderColor: "var(--border)", background: "var(--surface)" }}
        >
          {/* Status bar */}
          <div className="flex-none flex items-center gap-2 px-4 py-2.5 border-b" style={{ borderColor: "var(--border)" }}>
            <StatusDot status={status} />
            <span className="text-xs" style={{ color: "var(--text-muted)" }}>
              {STATUS_LABEL[status]}
            </span>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
            {messages.length === 0 && !isActive && (
              <div className="flex flex-col items-center justify-center h-full select-none gap-2">
                <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: "var(--surface-raised)" }}>
                  <MicSvg size={18} color="var(--text-dim)" />
                </div>
                <p className="text-xs" style={{ color: "var(--text-dim)" }}>Press Start call to talk to Sierra</p>
              </div>
            )}
            {messages.map((m, i) => <ChatMessage key={i} message={m} />)}
          </div>

          {error && (
            <div className="mx-4 mb-1 px-3 py-2 rounded-lg text-xs" style={{ background: "rgba(239,68,68,0.1)", color: "#f87171" }}>
              {error}
            </div>
          )}
        </div>

        {/* ② Menu */}
        <div className="flex flex-col border-r overflow-hidden" style={{ width: "34%", borderColor: "var(--border)" }}>
          <MenuPanel />
        </div>

        {/* ③ Order */}
        <div className="flex flex-col overflow-hidden" style={{ flex: 1 }}>
          <OrderColumn messages={messages} confirmedOrder={confirmedOrder} isActive={isActive} />
        </div>
      </div>

      {/* ── Bottom controls bar ─────────────────────────── */}
      <div
        className="flex-none flex items-center gap-3 px-5 py-3 border-t"
        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
      >
        <select
          disabled={isActive} value={lang} onChange={(e) => setLang(e.target.value)}
          className="text-xs rounded-lg px-3 py-2 outline-none cursor-pointer disabled:opacity-40 transition"
          style={{ background: "var(--surface-raised)", border: "1px solid var(--border)", color: "var(--text)" }}
        >
          {LANGUAGES.map(({ code, name }) => <option key={code} value={code}>{name}</option>)}
        </select>

        <div className="flex-1" />

        {isActive ? (
          <button
            onClick={stop}
            className="flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold text-white transition-all"
            style={{ background: "#dc2626", boxShadow: "0 2px 12px rgba(220,38,38,0.3)" }}
          >
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "white", display: "inline-block" }}
                  className={status === "listening" ? "animate-mic-ring" : ""} />
            {status === "listening"  ? "Listening…"       :
             status === "speaking"   ? "Sierra speaking"  :
             status === "processing" ? "Processing…"      : "End call"}
          </button>
        ) : (
          <button
            onClick={startCall}
            className="flex items-center gap-2 px-6 py-2.5 rounded-full text-sm font-semibold text-black transition-all hover:opacity-90 active:scale-95"
            style={{ background: "var(--accent)", boxShadow: "0 2px 16px rgba(245,158,11,0.3)" }}
          >
            <MicSvg size={14} /> Start call
          </button>
        )}
      </div>

      {/* ── Sierra floating circle ──────────────────────── */}
      <SierraFloat status={status} />
    </div>
  );
}

// ─────────────────────────────────────────────
// Order column
// ─────────────────────────────────────────────
function OrderColumn({
  messages,
  confirmedOrder,
  isActive,
}: {
  messages: Message[];
  confirmedOrder: OrderConfirmed | null;
  isActive: boolean;
}) {
  const detected = useMemo(() => {
    if (confirmedOrder) return [];
    return parseOrderFromBotMessages(
      messages.filter((m) => m.type === "llm_response").map((m) => (m as { text: string }).text)
    );
  }, [messages, confirmedOrder]);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div
        className="flex-none flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
      >
        <span className="text-xs font-semibold uppercase tracking-widest" style={{ color: "var(--text-dim)" }}>
          Your Order
        </span>
        {(detected.length > 0 || confirmedOrder) && (
          <span
            className="text-xs px-2 py-0.5 rounded-full font-medium"
            style={{ background: confirmedOrder ? "rgba(34,197,94,0.15)" : "rgba(245,158,11,0.15)", color: confirmedOrder ? "#4ade80" : "var(--accent)" }}
          >
            {confirmedOrder ? "Confirmed" : `${detected.length} item${detected.length !== 1 ? "s" : ""}`}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">

        {/* Idle */}
        {!isActive && !confirmedOrder && (
          <div className="h-full flex flex-col items-center justify-center px-4 gap-3 select-none">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: "var(--surface-raised)" }}>
              <BagSvg />
            </div>
            <p className="text-xs text-center" style={{ color: "var(--text-dim)" }}>
              Your order will appear here as you speak to Sierra
            </p>
          </div>
        )}

        {/* Active, no items yet */}
        {isActive && !confirmedOrder && detected.length === 0 && (
          <div className="h-full flex flex-col items-center justify-center gap-3">
            <div className="flex gap-1.5">
              <span className="w-2 h-2 rounded-full dot-1" style={{ background: "var(--accent)" }} />
              <span className="w-2 h-2 rounded-full dot-2" style={{ background: "var(--accent)" }} />
              <span className="w-2 h-2 rounded-full dot-3" style={{ background: "var(--accent)" }} />
            </div>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>Taking your order…</p>
          </div>
        )}

        {/* Items detected */}
        {!confirmedOrder && detected.length > 0 && (
          <div className="px-3 py-3 flex flex-col gap-2">
            {detected.map((item, i) => (
              <OrderItemRow key={item.name} name={item.name} qty={item.quantity} price={item.price} index={i} pending />
            ))}
            <div className="mt-2 pt-2 border-t flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
              <span className="text-xs" style={{ color: "var(--text-dim)" }}>Estimated</span>
              <span className="text-sm font-bold" style={{ color: "var(--accent)" }}>
                ${detected.reduce((s, i) => s + i.price * i.quantity, 0).toFixed(2)}
              </span>
            </div>
            <p className="text-xs" style={{ color: "var(--text-dim)" }}>Prices confirmed on order placement</p>
          </div>
        )}

        {/* Confirmed */}
        {confirmedOrder && (
          <div className="px-3 py-3 flex flex-col gap-2">
            {/* Banner */}
            <div
              className="animate-confirm-pop rounded-xl px-3 py-2.5 flex items-center gap-2.5 mb-1"
              style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.2)" }}
            >
              <span className="flex-none w-6 h-6 rounded-full flex items-center justify-center" style={{ background: "rgba(34,197,94,0.2)" }}>
                <CheckSvg />
              </span>
              <div>
                <p className="text-xs font-semibold" style={{ color: "#4ade80" }}>Order Confirmed</p>
                <p className="text-xs" style={{ color: "var(--text-dim)" }}>{confirmedOrder.order_id} · {confirmedOrder.wait_time}</p>
              </div>
            </div>

            {confirmedOrder.items.map((item, i) => (
              <OrderItemRow key={item.name} name={item.name} qty={item.quantity} price={item.price} index={i} />
            ))}

            <div className="mt-1 pt-2 border-t flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
              <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>Total</span>
              <span className="text-sm font-bold" style={{ color: "var(--accent)" }}>
                ${confirmedOrder.total_amount.toFixed(2)}
              </span>
            </div>

            {/* Customer info */}
            <div className="mt-1 rounded-xl px-3 py-2.5 flex flex-col gap-1.5" style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}>
              <InfoRow label="Name"  value={confirmedOrder.customer_name} />
              <InfoRow label="Phone" value={confirmedOrder.phone_number} />
              <InfoRow label="Type"  value={confirmedOrder.order_type === "dine_in" ? "Dine-in" : confirmedOrder.order_type === "pickup" ? "Pickup" : "Delivery"} accent />
              {confirmedOrder.special_instructions && (
                <InfoRow label="Notes" value={confirmedOrder.special_instructions} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// Sierra floating circle
// ─────────────────────────────────────────────
function SierraFloat({ status }: { status: CallStatus }) {
  const speaking  = status === "speaking";
  const listening = status === "listening";
  const active    = status !== "idle" && status !== "connecting";

  return (
    <div style={{ position: "absolute", bottom: 68, right: 20, zIndex: 40 }}>
      {/* Tooltip label */}
      {active && (
        <div style={{ position: "absolute", bottom: "calc(100% + 8px)", right: 0, pointerEvents: "none" }}>
          <span
            className="text-xs px-2.5 py-1 rounded-full whitespace-nowrap"
            style={{ background: "var(--surface-raised)", border: "1px solid var(--border)", color: "var(--text-muted)", boxShadow: "0 2px 8px rgba(0,0,0,0.4)" }}
          >
            {speaking  ? "Sierra is speaking…"  :
             listening ? "Listening…"             : "Thinking…"}
          </span>
        </div>
      )}

      {/* Pulse rings */}
      {speaking && (
        <>
          <div className="absolute inset-0 rounded-full animate-avatar-pulse"
               style={{ border: "1.5px solid rgba(245,158,11,0.5)" }} />
          <div className="absolute rounded-full animate-avatar-pulse"
               style={{ inset: -8, border: "1px solid rgba(245,158,11,0.2)", animationDelay: "0.4s" }} />
        </>
      )}
      {listening && (
        <div className="absolute rounded-full"
             style={{ inset: -4, border: "1.5px solid rgba(245,158,11,0.3)", borderRadius: "50%" }} />
      )}

      {/* Main circle */}
      <div
        style={{
          width: 56, height: 56, borderRadius: "50%",
          background: active
            ? "linear-gradient(135deg, #f59e0b 0%, #b45309 100%)"
            : "var(--surface-raised)",
          border: `2px solid ${active ? "rgba(245,158,11,0.5)" : "var(--border)"}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: active ? "0 4px 24px rgba(245,158,11,0.35)" : "0 2px 12px rgba(0,0,0,0.5)",
          transition: "all 0.35s ease",
          cursor: "default",
        }}
      >
        <span style={{ fontSize: 24, fontWeight: 700, color: active ? "#000" : "var(--text-dim)", fontFamily: "Georgia, serif", transition: "color 0.3s" }}>
          S
        </span>
      </div>

      {/* Listening wave under circle */}
      {listening && (
        <div className="flex items-center justify-center gap-0.5 mt-1.5">
          {[0, 1, 2, 3, 4].map((i) => (
            <span key={i} className="rounded-full" style={{
              width: 3, background: "#f59e0b",
              height: 4 + (i === 2 ? 8 : i === 1 || i === 3 ? 5 : 0),
              animation: `wave-bar 0.7s ${i * 0.1}s ease-in-out infinite alternate`,
            }} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Small shared components
// ─────────────────────────────────────────────
function OrderItemRow({ name, qty, price, index, pending = false }: { name: string; qty: number; price: number; index: number; pending?: boolean }) {
  return (
    <div
      className="animate-item-in flex items-start justify-between gap-2 rounded-lg px-3 py-2.5"
      style={{
        background: "var(--surface-raised)",
        border: `1px solid ${pending ? "rgba(245,158,11,0.15)" : "var(--border)"}`,
        animationDelay: `${index * 50}ms`,
      }}
    >
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium leading-snug truncate" style={{ color: "var(--text)" }}>{name}</p>
        <p className="text-xs mt-0.5" style={{ color: "var(--text-dim)" }}>× {qty}</p>
      </div>
      <span className="text-xs font-semibold flex-none" style={{ color: "var(--accent)" }}>
        ${(price * qty).toFixed(2)}
      </span>
    </div>
  );
}

function InfoRow({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs" style={{ color: "var(--text-dim)" }}>{label}</span>
      <span className="text-xs font-medium" style={{ color: accent ? "var(--accent)" : "var(--text-muted)" }}>{value}</span>
    </div>
  );
}

function StatusDot({ status }: { status: CallStatus }) {
  const bg = status === "listening" ? "#f59e0b" : status === "speaking" ? "#22c55e" : status === "processing" ? "#818cf8" : "#3a3a3a";
  return <span style={{ width: 7, height: 7, borderRadius: "50%", background: bg, display: "inline-block", transition: "background 0.3s" }} />;
}

const STATUS_LABEL: Record<CallStatus, string> = {
  idle:       "Ready — click Start call",
  connecting: "Connecting…",
  listening:  "Listening",
  speaking:   "Sierra is speaking",
  processing: "Processing",
};

// ─────────────────────────────────────────────
// SVG Icons
// ─────────────────────────────────────────────
function MicSvg({ size = 14, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8"  y1="23" x2="16" y2="23" />
    </svg>
  );
}

function BagSvg() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--text-dim)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <path d="M16 10a4 4 0 0 1-8 0" />
    </svg>
  );
}

function CheckSvg() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
