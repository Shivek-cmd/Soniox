import { useEffect, useRef, useState } from "react";
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
import { OrderPanel } from "./OrderPanel";
import { MenuPanel } from "./MenuPanel";

const backendWebsocketUrl = import.meta.env.VITE_SONIOX_VOICE_BOT_WS_URL;

export type CallStatus = "idle" | "connecting" | "listening" | "speaking" | "processing";

const LANGUAGES = [
  { code: "pa", name: "Punjabi" },
  { code: "hi", name: "Hindi"   },
  { code: "en", name: "English" },
];

export function Conversation() {
  const websocket = useRef<WebSocket | null>(null);

  const [language, setLanguage]             = useState("pa");
  const [messages, setMessages]             = useState<Message[]>([]);
  const [confirmedOrder, setConfirmedOrder] = useState<OrderConfirmed | null>(null);
  const [callStatus, setCallStatus]         = useState<CallStatus>("idle");
  const [error, setError]                   = useState<string | null>(null);

  const autoScrollRef = useAutoScroll(messages);

  const { startMicrophoneStream, cleanupMicrophoneStream } = useMicrophone({
    onData: (data) => websocket.current?.send(data),
    onError: () => { setError("Microphone error. Please allow access and try again."); cleanup(); },
  });

  const { cleanupAudioPlayer, prepareAudioPlayer, addAudioChunk, interruptAudio } =
    useAudioChunkPlayer({});

  const cleanup = () => {
    websocket.current?.close();
    websocket.current = null;
    cleanupMicrophoneStream();
    cleanupAudioPlayer();
    setCallStatus("idle");
  };

  const startCall = () => {
    if (websocket.current) return;
    setCallStatus("connecting");
    setMessages([]);
    setConfirmedOrder(null);
    setError(null);
    prepareAudioPlayer();

    const url = new URL(backendWebsocketUrl);
    url.searchParams.append("language", language);
    url.searchParams.append("voice", "Nina");
    const ws = new WebSocket(url.toString());
    websocket.current = ws;

    ws.onopen  = () => { setCallStatus("listening"); startMicrophoneStream(); };
    ws.onerror = () => { setError("Could not connect to voice server."); cleanup(); };
    ws.onclose = () => cleanup();

    ws.onmessage = async (e) => {
      try {
        if (typeof e.data === "string") {
          const data = JSON.parse(e.data);
          if (data.type === "user_speech_start") { interruptAudio(); setCallStatus("listening"); return; }
          if (data.type === "user_speech_end")   { setCallStatus("processing"); return; }
          if (data.type === "session_start" || data.type === "metric") return;
          if (data.type === "order_confirmed") {
            const p = orderConfirmedSchema.safeParse(data);
            if (p.success) setConfirmedOrder(p.data);
            return;
          }
          const message = messageSchema.parse(data);
          setMessages((prev) => updateMessages(prev, message));
          if (message.type === "transcription") { interruptAudio(); setCallStatus("listening"); }
          else if (message.type === "llm_response") setCallStatus("speaking");
        } else if (e.data instanceof Blob) {
          addAudioChunk(await e.data.arrayBuffer());
        }
      } catch (err) { console.error(err); }
    };
  };

  useEffect(() => { return () => { cleanup(); }; }, []); // eslint-disable-line

  const isActive = callStatus !== "idle";

  return (
    <div className="h-full flex overflow-hidden">

      {/* ════════════════════════════════════════
          LEFT — Chat (always visible)
      ════════════════════════════════════════ */}
      <div
        className="flex flex-col"
        style={{ width: "50%", borderRight: "1px solid var(--border)", background: "var(--surface)" }}
      >
        {/* Status */}
        <div className="flex-none flex items-center gap-2 px-4 py-2.5 border-b" style={{ borderColor: "var(--border)" }}>
          <StatusDot status={callStatus} />
          <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
            <StatusLabel status={callStatus} />
          </span>
        </div>

        {/* Messages */}
        <div ref={autoScrollRef} className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
          {messages.length === 0 && !isActive && <ChatEmptyState />}
          {messages.map((msg, i) => <ChatMessage key={i} message={msg} />)}
        </div>

        {error && (
          <div className="flex-none mx-4 mb-2 px-3 py-2 rounded-lg text-xs" style={{ background: "rgba(239,68,68,0.1)", color: "#f87171" }}>
            {error}
          </div>
        )}

        {/* Controls */}
        <div className="flex-none flex items-center gap-3 px-4 py-3 border-t" style={{ borderColor: "var(--border)" }}>
          <select
            disabled={isActive} value={language} onChange={(e) => setLanguage(e.target.value)}
            className="text-xs rounded-lg px-2 py-1.5 outline-none cursor-pointer disabled:opacity-40"
            style={{ background: "var(--surface-raised)", border: "1px solid var(--border)", color: "var(--text)" }}
          >
            {LANGUAGES.map(({ code, name }) => <option key={code} value={code}>{name}</option>)}
          </select>
          <div className="flex-1" />
          {isActive ? (
            <button onClick={cleanup} className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-semibold text-white" style={{ background: "#dc2626" }}>
              <span className={callStatus === "listening" ? "animate-mic-ring" : ""} style={{ width: 7, height: 7, borderRadius: "50%", display: "inline-block", background: "white" }} />
              {callStatus === "listening" ? "Listening…" : callStatus === "speaking" ? "Sierra speaking" : callStatus === "processing" ? "Processing…" : "On call"}
            </button>
          ) : (
            <button onClick={startCall} className="flex items-center gap-2 px-5 py-2 rounded-full text-xs font-semibold text-black hover:opacity-90 transition-opacity" style={{ background: "var(--accent)" }}>
              <MicIcon size={13} /> Start call
            </button>
          )}
        </div>
      </div>

      {/* ════════════════════════════════════════
          RIGHT — 3 stacked sections
      ════════════════════════════════════════ */}
      <div className="flex-1 flex flex-col overflow-hidden" style={{ background: "var(--bg)" }}>

        {/* ── 1. Sierra avatar strip ── */}
        <SierraStrip callStatus={callStatus} />

        {/* ── 2. Order section (auto height, max 220px) ── */}
        <div
          className="flex-none overflow-y-auto border-y"
          style={{ maxHeight: 220, borderColor: "var(--border)" }}
        >
          <OrderPanel messages={messages} confirmedOrder={confirmedOrder} isCallActive={isActive} embedded />
        </div>

        {/* ── 3. Menu section (takes remaining space) ── */}
        <div className="flex-1 overflow-hidden">
          <MenuPanel />
        </div>

      </div>
    </div>
  );
}

// ── Sierra mini avatar strip ──────────────────────────────────

function SierraStrip({ callStatus }: { callStatus: CallStatus }) {
  const isSpeaking  = callStatus === "speaking";
  const isListening = callStatus === "listening";
  const isActive    = callStatus !== "idle" && callStatus !== "connecting";

  const statusColor =
    isSpeaking  ? "#22c55e" :
    isListening ? "#f59e0b" :
    callStatus === "processing" ? "#818cf8" : "var(--text-dim)";

  const statusLabel =
    callStatus === "idle"       ? "Ready" :
    callStatus === "connecting" ? "Connecting…" :
    callStatus === "listening"  ? "Listening" :
    callStatus === "speaking"   ? "Speaking" : "Thinking…";

  return (
    <div
      className="flex-none flex items-center gap-3 px-4 py-3 border-b"
      style={{ background: "var(--surface)", borderColor: "var(--border)" }}
    >
      {/* Animated circle avatar */}
      <div className="relative flex-none" style={{ width: 44, height: 44 }}>
        {isSpeaking && (
          <div className="absolute inset-0 rounded-full animate-avatar-pulse"
               style={{ border: "1.5px solid rgba(245,158,11,0.4)" }} />
        )}
        {isListening && (
          <div className="absolute rounded-full"
               style={{ inset: -3, border: "1.5px solid rgba(245,158,11,0.25)", borderRadius: "50%" }} />
        )}
        <div
          className="w-11 h-11 rounded-full flex items-center justify-center font-bold text-lg transition-all duration-400"
          style={{
            background: isActive
              ? "linear-gradient(135deg, #f59e0b, #d97706)"
              : "var(--surface-raised)",
            color: isActive ? "#000" : "var(--text-dim)",
            boxShadow: isActive ? "0 0 20px rgba(245,158,11,0.2)" : "none",
          }}
        >
          S
        </div>
      </div>

      {/* Name + role */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold leading-none mb-0.5" style={{ color: "var(--text)" }}>Sierra</p>
        <p className="text-xs" style={{ color: "var(--text-dim)" }}>AI Voice Assistant</p>
      </div>

      {/* Status pill */}
      <div
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs flex-none transition-all duration-300"
        style={{
          background: isActive ? "rgba(245,158,11,0.08)" : "var(--surface-raised)",
          border: `1px solid ${isActive ? "rgba(245,158,11,0.2)" : "var(--border)"}`,
        }}
      >
        <span className="rounded-full transition-all duration-300"
              style={{ width: 6, height: 6, background: statusColor, display: "inline-block" }} />
        <span style={{ color: isActive ? "var(--accent)" : "var(--text-dim)" }}>{statusLabel}</span>
      </div>

      {/* Listening wave bars */}
      {isListening && (
        <div className="flex items-center gap-0.5 flex-none">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} className="rounded-full" style={{
              width: 3,
              background: "#f59e0b",
              height: 8 + (i % 2 === 0 ? 6 : 0),
              animation: `wave-bar 0.7s ${i * 0.12}s ease-in-out infinite alternate`,
            }} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────

function StatusDot({ status }: { status: CallStatus }) {
  const bg = status === "listening" ? "#f59e0b" : status === "speaking" ? "#22c55e" : status === "processing" ? "#818cf8" : "#3a3a3a";
  return <span style={{ width: 7, height: 7, borderRadius: "50%", background: bg, display: "inline-block", transition: "background 0.3s" }} />;
}

function StatusLabel({ status }: { status: CallStatus }) {
  return (
    <>
      {status === "idle"       && "Ready — click Start call"}
      {status === "connecting" && "Connecting…"}
      {status === "listening"  && "Listening"}
      {status === "speaking"   && "Sierra is speaking"}
      {status === "processing" && "Processing"}
    </>
  );
}

function ChatEmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-16 select-none">
      <div className="w-10 h-10 rounded-full flex items-center justify-center mb-3" style={{ background: "var(--surface-raised)" }}>
        <MicIcon size={18} color="var(--text-dim)" />
      </div>
      <p className="text-xs" style={{ color: "var(--text-dim)" }}>Press Start call to talk to Sierra</p>
    </div>
  );
}

function MicIcon({ size = 14, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8"  y1="23" x2="16" y2="23" />
    </svg>
  );
}
