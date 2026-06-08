import { useEffect, useMemo, useRef, useState } from "react";
import {
  messageSchema,
  orderConfirmedSchema,
  updateMessages,
  type Message,
  type OrderConfirmed,
} from "../utils/messages";
import { useAudioChunkPlayer } from "../hooks/useAudioChunkPlayer";
import { useMicrophone } from "../hooks/useMicrophone";
import { MenuPanel } from "./MenuPanel";
import { AvatarPanel } from "./AvatarPanel";
import { parseOrderFromBotMessages, parseConversationDetails } from "../utils/menuData";

const WS_URL = import.meta.env.VITE_SONIOX_VOICE_BOT_WS_URL;

type CallStatus = "idle" | "connecting" | "listening" | "speaking" | "processing";

const LANGUAGES = [
  { code: "pa", name: "Punjabi" },
  { code: "hi", name: "Hindi"   },
  { code: "en", name: "English" },
];

function useIsMobile(breakpoint = 640) {
  const [m, setM] = useState(() => window.innerWidth < breakpoint);
  useEffect(() => {
    const fn = () => setM(window.innerWidth < breakpoint);
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, [breakpoint]);
  return m;
}

// ─────────────────────────────────────────────
export function Conversation() {
  const ws = useRef<WebSocket | null>(null);

  const [lang, setLang]                     = useState("en");
  const [messages, setMessages]             = useState<Message[]>([]);
  const [confirmedOrder, setConfirmedOrder] = useState<OrderConfirmed | null>(null);
  const [status, setStatus]                 = useState<CallStatus>("idle");
  const [error, setError]                   = useState<string | null>(null);

  const isMobile = useIsMobile();
  const [mobilePanelTab, setMobilePanelTab] = useState<"sierra" | "order">("sierra");

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
    url.searchParams.append("voice", "Maya");
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

  // On mobile, auto-switch to Sierra panel when call becomes active
  useEffect(() => {
    if (isMobile && status !== "idle") setMobilePanelTab("sierra");
  }, [isMobile, status !== "idle"]); // eslint-disable-line

  const isActive = status !== "idle";

  return (
    <div className="h-full flex flex-col relative" style={{ background: "var(--bg)" }}>

      {/* ── Mobile panel tab bar ───────────────────────────────────────── */}
      {isMobile && (
        <div
          className="flex-none flex border-b"
          style={{ borderColor: "var(--border)", background: "var(--surface)" }}
        >
          <PanelTab
            active={mobilePanelTab === "sierra"}
            onClick={() => setMobilePanelTab("sierra")}
          >
            Sierra
          </PanelTab>
          <PanelTab
            active={mobilePanelTab === "order"}
            onClick={() => setMobilePanelTab("order")}
          >
            My Order
          </PanelTab>
        </div>
      )}

      {/* ── Content ───────────────────────────────────────────────────── */}
      {isMobile ? (
        // Mobile: single panel view
        <div className="flex-1 overflow-hidden min-h-0">
          {mobilePanelTab === "sierra" && (
            <AvatarPanel callStatus={status} />
          )}
          {mobilePanelTab === "order" && (
            <OrderColumn
              messages={messages}
              confirmedOrder={confirmedOrder}
              isActive={isActive}
            />
          )}
        </div>
      ) : (
        // Desktop: three-column layout
        <div className="flex-1 flex overflow-hidden min-h-0">

          {/* ① Sierra — avatar + status */}
          <div
            className="flex-none border-r"
            style={{ width: 260, borderColor: "var(--border)", background: "var(--bg)" }}
          >
            <AvatarPanel callStatus={status} />
          </div>

          {/* ② Menu */}
          <div
            className="flex flex-col border-r overflow-hidden"
            style={{ flex: "0 0 32%", borderColor: "var(--border)" }}
          >
            <MenuPanel />
          </div>

          {/* ③ Order */}
          <div className="flex flex-col overflow-hidden" style={{ flex: 1 }}>
            <OrderColumn
              messages={messages}
              confirmedOrder={confirmedOrder}
              isActive={isActive}
            />
          </div>
        </div>
      )}

      {/* ── Bottom controls ────────────────────────────────────────────── */}
      <div
        className="flex-none border-t"
        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
      >
        {/* Error strip */}
        {error && (
          <div
            className="flex items-center gap-2 px-4 py-2 text-xs border-b"
            style={{
              background: "rgba(239,68,68,0.08)",
              borderColor: "rgba(239,68,68,0.15)",
              color: "#f87171",
            }}
          >
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#f87171", flexShrink: 0, display: "inline-block" }} />
            {error}
          </div>
        )}

        {/* Controls row */}
        <div className="flex items-center gap-3 px-4 py-3">
          <select
            disabled={isActive}
            value={lang}
            onChange={(e) => setLang(e.target.value)}
            className="text-xs rounded-lg px-3 py-2 outline-none cursor-pointer disabled:opacity-40 transition"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border)",
              color: "var(--text)",
            }}
          >
            {LANGUAGES.map(({ code, name }) => (
              <option key={code} value={code}>{name}</option>
            ))}
          </select>

          <div className="flex-1" />

          {isActive ? (
            <button
              onClick={stop}
              className="flex items-center gap-2 px-5 py-3 rounded-full text-sm font-semibold text-white transition-all"
              style={{
                background: "#dc2626",
                boxShadow: "0 2px 12px rgba(220,38,38,0.3)",
                minHeight: 44,
              }}
            >
              <span
                style={{ width: 8, height: 8, borderRadius: "50%", background: "white", display: "inline-block" }}
                className={status === "listening" ? "animate-mic-ring" : ""}
              />
              {status === "listening"  ? "Listening…"      :
               status === "speaking"   ? "Sierra speaking" :
               status === "processing" ? "Processing…"     : "End call"}
            </button>
          ) : (
            <button
              onClick={startCall}
              className="flex items-center gap-2 px-6 py-3 rounded-full text-sm font-semibold text-black transition-all hover:opacity-90 active:scale-95"
              style={{
                background: "var(--accent)",
                boxShadow: "0 2px 16px rgba(245,158,11,0.3)",
                minHeight: 44,
              }}
            >
              <MicSvg size={14} /> Start call
            </button>
          )}
        </div>
      </div>

      {/* ── Sierra floating status bubble — desktop only ───────────────── */}
      {!isMobile && <SierraFloat status={status} />}
    </div>
  );
}

// ─────────────────────────────────────────────
// Mobile panel tab
// ─────────────────────────────────────────────
function PanelTab({
  active, onClick, children,
}: {
  active: boolean; onClick: () => void; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="flex-1 py-2.5 text-xs font-semibold border-b-2 transition-colors"
      style={{
        borderColor: active ? "var(--accent)" : "transparent",
        color: active ? "var(--accent)" : "var(--text-dim)",
        background: "transparent",
      }}
    >
      {children}
    </button>
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

  const details = useMemo(
    () => parseConversationDetails(messages as { type: string; text?: string; final_text?: string }[]),
    [messages]
  );

  const localOrder = useMemo<OrderConfirmed | null>(() => {
    if (!details.isConfirmed || confirmedOrder || detected.length === 0) return null;
    const ts = new Date();
    const pad = (n: number) => n.toString().padStart(2, "0");
    return {
      type: "order_confirmed",
      order_id: `PS-${pad(ts.getHours())}${pad(ts.getMinutes())}${pad(ts.getSeconds())}`,
      customer_name: details.name ?? "—",
      phone_number:  details.phone ?? "—",
      order_type:    details.orderType ?? "pickup",
      items:         detected.map(i => ({ name: i.name, quantity: i.quantity, price: i.price, notes: "" })),
      total_amount:  detected.reduce((s, i) => s + i.price * i.quantity, 0),
      wait_time:     "20–30 minutes",
      special_instructions: details.instructions ?? "",
    };
  }, [details, confirmedOrder, detected]);

  const effectiveOrder = confirmedOrder ?? localOrder;

  const badgeLabel = effectiveOrder
    ? "Confirmed ✓"
    : detected.length > 0
    ? `${detected.length} item${detected.length !== 1 ? "s" : ""}`
    : null;

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div
        className="flex-none flex items-center justify-between px-4 py-3 border-b"
        style={{ borderColor: "var(--border)", background: "var(--surface)" }}
      >
        <span
          className="text-xs font-semibold uppercase tracking-widest"
          style={{ color: "var(--text-dim)" }}
        >
          Your Order
        </span>
        {badgeLabel && (
          <span
            className="text-xs px-2 py-0.5 rounded-full font-medium"
            style={{
              background: effectiveOrder ? "rgba(34,197,94,0.15)" : "rgba(245,158,11,0.15)",
              color: effectiveOrder ? "#4ade80" : "var(--accent)",
            }}
          >
            {badgeLabel}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">

        {/* Idle */}
        {!isActive && !effectiveOrder && (
          <div className="h-full flex flex-col items-center justify-center px-4 gap-3 select-none">
            <div
              className="w-12 h-12 rounded-2xl flex items-center justify-center"
              style={{ background: "var(--surface-raised)" }}
            >
              <BagSvg />
            </div>
            <p className="text-xs text-center" style={{ color: "var(--text-dim)" }}>
              Your order will appear here as you speak to Sierra
            </p>
          </div>
        )}

        {/* Active — building order */}
        {isActive && !effectiveOrder && (
          <div className="px-3 py-3 flex flex-col gap-2">
            {detected.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-6 gap-3">
                <div className="flex gap-1.5">
                  <span className="w-2 h-2 rounded-full dot-1" style={{ background: "var(--accent)" }} />
                  <span className="w-2 h-2 rounded-full dot-2" style={{ background: "var(--accent)" }} />
                  <span className="w-2 h-2 rounded-full dot-3" style={{ background: "var(--accent)" }} />
                </div>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>Taking your order…</p>
              </div>
            ) : (
              <div
                className="rounded-xl overflow-hidden"
                style={{
                  border: "1px dashed rgba(245,158,11,0.3)",
                  background: "rgba(245,158,11,0.03)",
                }}
              >
                <div
                  className="px-3 py-2 border-b"
                  style={{ borderColor: "rgba(245,158,11,0.2)" }}
                >
                  <p
                    className="text-xs font-semibold uppercase tracking-widest"
                    style={{ color: "var(--accent)" }}
                  >
                    Building Order…
                  </p>
                </div>
                <div className="px-3 py-2 flex flex-col gap-1.5">
                  {detected.map((item) => (
                    <div key={item.name} className="flex justify-between gap-2">
                      <span className="text-xs truncate flex-1" style={{ color: "var(--text-muted)" }}>
                        {item.quantity}× {item.name}
                      </span>
                      <span className="text-xs font-semibold flex-none" style={{ color: "var(--accent)" }}>
                        ${(item.price * item.quantity).toFixed(2)}
                      </span>
                    </div>
                  ))}
                  <div
                    className="flex justify-between pt-2 mt-1 border-t"
                    style={{ borderColor: "rgba(245,158,11,0.15)" }}
                  >
                    <span className="text-xs" style={{ color: "var(--text-dim)" }}>Est. subtotal</span>
                    <span className="text-xs font-bold" style={{ color: "var(--accent)" }}>
                      ${detected.reduce((s, i) => s + i.price * i.quantity, 0).toFixed(2)}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {(details.name || details.phone || details.orderType || details.instructions) && (
              <div
                className="rounded-xl px-3 py-2.5 flex flex-col gap-1.5"
                style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}
              >
                {details.name        && <DetailRow label="Name"  value={details.name} />}
                {details.phone       && <DetailRow label="Phone" value={details.phone} mono />}
                {details.orderType   && (
                  <DetailRow
                    label="Type"
                    value={details.orderType === "dine_in" ? "Dine-in" : details.orderType.charAt(0).toUpperCase() + details.orderType.slice(1)}
                    accent
                  />
                )}
                {details.instructions && <DetailRow label="Notes" value={details.instructions} />}
              </div>
            )}
          </div>
        )}

        {/* Confirmed — full receipt */}
        {effectiveOrder && <ReceiptCard order={effectiveOrder} />}
      </div>
    </div>
  );
}

function DetailRow({
  label, value, mono = false, accent = false,
}: {
  label: string; value: string; mono?: boolean; accent?: boolean;
}) {
  return (
    <div className="flex justify-between gap-2 items-start">
      <span className="text-xs flex-none" style={{ color: "var(--text-dim)" }}>{label}</span>
      <span
        className="text-xs font-medium text-right"
        style={{
          color: accent ? "var(--accent)" : "var(--text)",
          fontFamily: mono ? "monospace" : undefined,
        }}
      >
        {value}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────
// Sierra floating status bubble — desktop only
// ─────────────────────────────────────────────
function SierraFloat({ status }: { status: CallStatus }) {
  const speaking  = status === "speaking";
  const listening = status === "listening";
  const active    = status !== "idle" && status !== "connecting";

  return (
    <div style={{ position: "absolute", bottom: 68, right: 20, zIndex: 40 }}>
      {/* Tooltip */}
      {active && (
        <div style={{ position: "absolute", bottom: "calc(100% + 8px)", right: 0, pointerEvents: "none" }}>
          <span
            className="text-xs px-2.5 py-1 rounded-full whitespace-nowrap"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
            }}
          >
            {speaking  ? "Sierra is speaking…" : listening ? "Listening…" : "Thinking…"}
          </span>
        </div>
      )}

      {/* Pulse rings */}
      {speaking && (
        <>
          <div
            className="absolute inset-0 rounded-full animate-avatar-pulse"
            style={{ border: "1.5px solid rgba(245,158,11,0.5)" }}
          />
          <div
            className="absolute rounded-full animate-avatar-pulse"
            style={{ inset: -8, border: "1px solid rgba(245,158,11,0.2)", animationDelay: "0.4s" }}
          />
        </>
      )}
      {listening && (
        <div
          className="absolute rounded-full"
          style={{ inset: -4, border: "1.5px solid rgba(245,158,11,0.3)", borderRadius: "50%" }}
        />
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
        <span
          style={{
            fontSize: 24, fontWeight: 700,
            color: active ? "#000" : "var(--text-dim)",
            fontFamily: "Georgia, serif",
            transition: "color 0.3s",
          }}
        >
          S
        </span>
      </div>

      {/* Listening wave */}
      {listening && (
        <div className="flex items-center justify-center gap-0.5 mt-1.5">
          {[0, 1, 2, 3, 4].map((i) => (
            <span
              key={i}
              className="rounded-full"
              style={{
                width: 3,
                background: "#f59e0b",
                height: 4 + (i === 2 ? 8 : i === 1 || i === 3 ? 5 : 0),
                animation: `wave-bar 0.7s ${i * 0.1}s ease-in-out infinite alternate`,
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────
// Receipt card
// ─────────────────────────────────────────────
const RECEIPT_STYLE: React.CSSProperties = {
  background: "#f9f8f4",
  boxShadow: "0 8px 32px rgba(0,0,0,0.5), 0 2px 8px rgba(0,0,0,0.3)",
  borderRadius: 16,
  overflow: "hidden",
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
};

const R = {
  label:   { fontSize: 11, color: "#999" } as React.CSSProperties,
  value:   { fontSize: 11, color: "#333" } as React.CSSProperties,
  bold:    { fontSize: 11, color: "#1a1a1a", fontWeight: 600 } as React.CSSProperties,
  mono:    { fontFamily: "ui-monospace, monospace" } as React.CSSProperties,
  dash:    { borderBottom: "1.5px dashed #dedad3", margin: "0 0 0 0" } as React.CSSProperties,
  section: { padding: "12px 16px", borderBottom: "1.5px dashed #dedad3" } as React.CSSProperties,
};

function ReceiptCard({ order }: { order: OrderConfirmed }) {
  const subtotal  = order.total_amount;
  const gst       = subtotal * 0.05;
  const total     = subtotal + gst;
  const typeLabel = order.order_type === "dine_in" ? "Dine-in" : order.order_type === "pickup" ? "Pickup" : "Delivery";
  const now       = new Date();
  const dateFmt   = now.toLocaleDateString("en-CA", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
  const timeFmt   = now.toLocaleTimeString("en-CA", { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="animate-confirm-pop px-3 py-3">
      <div style={RECEIPT_STYLE}>

        {/* Restaurant header */}
        <div style={{ ...R.section, textAlign: "center", paddingTop: 18, paddingBottom: 16 }}>
          <p style={{ fontSize: 10, color: "#bbb", letterSpacing: 3, textTransform: "uppercase", marginBottom: 6 }}>
            Authentic Punjabi Cuisine
          </p>
          <h2 style={{ fontSize: 20, fontWeight: 900, color: "#1a1a1a", letterSpacing: -0.5, margin: "0 0 3px", fontFamily: "Georgia, serif" }}>
            Parkash Sweets
          </h2>
          <p style={{ fontSize: 11, color: "#777", margin: "2px 0" }}>Edmonton, AB, Canada</p>
          <p style={{ fontSize: 10, color: "#999", margin: "2px 0" }}>Open 11 AM – 10 PM · 7 Days a Week</p>
        </div>

        {/* Order status */}
        <div style={R.section}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#22c55e", display: "inline-block" }} />
            <span style={{ fontSize: 11, fontWeight: 700, color: "#16a34a", letterSpacing: 1, textTransform: "uppercase" }}>
              Order Confirmed
            </span>
          </div>
          <ReceiptRow label="Order #" value={order.order_id} mono bold />
          <ReceiptRow label="Date"    value={dateFmt} />
          <ReceiptRow label="Time"    value={timeFmt} />
        </div>

        {/* Customer */}
        <div style={R.section}>
          <p style={{ fontSize: 10, fontWeight: 700, color: "#aaa", letterSpacing: 2, textTransform: "uppercase", marginBottom: 8 }}>
            Customer
          </p>
          <ReceiptRow label="Name"     value={order.customer_name} bold />
          <ReceiptRow label="Phone"    value={order.phone_number}  mono />
          <ReceiptRow label="Type"     value={typeLabel}           color="#b45309" bold />
          <ReceiptRow label="Ready in" value={order.wait_time}     color="#16a34a" bold />
        </div>

        {/* Items */}
        <div style={R.section}>
          <p style={{ fontSize: 10, fontWeight: 700, color: "#aaa", letterSpacing: 2, textTransform: "uppercase", marginBottom: 8 }}>
            Items Ordered
          </p>
          <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid #e8e4dc", paddingBottom: 4, marginBottom: 8 }}>
            <span style={{ fontSize: 10, color: "#bbb" }}>Description</span>
            <span style={{ fontSize: 10, color: "#bbb" }}>Amount</span>
          </div>
          {order.items.map((item) => (
            <div key={item.name} style={{ marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                <span style={{ ...R.value, flex: 1 }}>{item.name}</span>
                <span style={{ ...R.bold, ...R.mono, flexShrink: 0 }}>${(item.price * item.quantity).toFixed(2)}</span>
              </div>
              <span style={{ ...R.label }}>{item.quantity} × ${item.price.toFixed(2)}</span>
              {item.notes && (
                <span style={{ fontSize: 10, color: "#b45309", fontStyle: "italic", marginTop: 1, display: "block" }}>
                  Notes: {item.notes}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Totals */}
        <div style={{ ...R.section, borderBottom: "2px dashed #dedad3" }}>
          <ReceiptRow label="Subtotal" value={`$${subtotal.toFixed(2)}`} mono />
          <ReceiptRow label="GST (5%)" value={`$${gst.toFixed(2)}`}     mono />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 10, paddingTop: 8, borderTop: "1px solid #dedad3" }}>
            <span style={{ fontSize: 15, fontWeight: 900, color: "#1a1a1a" }}>TOTAL</span>
            <span style={{ fontSize: 18, fontWeight: 900, color: "#b45309", fontFamily: "ui-monospace, monospace" }}>
              ${total.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Special instructions */}
        {order.special_instructions && (
          <div style={R.section}>
            <p style={{ fontSize: 10, fontWeight: 700, color: "#aaa", letterSpacing: 2, textTransform: "uppercase", marginBottom: 4 }}>
              Special Instructions
            </p>
            <p style={{ fontSize: 11, color: "#555" }}>{order.special_instructions}</p>
          </div>
        )}

        {/* Footer */}
        <div style={{ padding: "14px 16px 18px", textAlign: "center" }}>
          <p style={{ fontSize: 14, fontWeight: 800, color: "#1a1a1a", marginBottom: 3 }}>Thank You!</p>
          <p style={{ fontSize: 11, color: "#777" }}>Enjoy your food. See you again soon!</p>
          <p style={{ fontSize: 10, color: "#ccc", marginTop: 10, letterSpacing: 2 }}>· · · · · · · · · · · ·</p>
          <p style={{ fontSize: 10, color: "#bbb", marginTop: 4 }}>Prices in CAD · Tax not included in menu prices</p>
        </div>

      </div>
    </div>
  );
}

function ReceiptRow({
  label, value, bold = false, mono = false, color,
}: {
  label: string; value: string; bold?: boolean; mono?: boolean; color?: string;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
      <span style={R.label}>{label}</span>
      <span style={{
        ...R.value,
        ...(bold  ? { fontWeight: 600, color: color ?? "#1a1a1a" } : {}),
        ...(mono  ? R.mono : {}),
        ...(color && !bold ? { color } : {}),
      }}>
        {value}
      </span>
    </div>
  );
}

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
