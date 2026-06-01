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
const LANGUAGES = [
  { code: "pa", name: "Punjabi" },
  { code: "hi", name: "Hindi"   },
  { code: "en", name: "English" },
];
import { ChatMessage } from "./renderer";
import { OrderPanel } from "./OrderPanel";

const backendWebsocketUrl = import.meta.env.VITE_SONIOX_VOICE_BOT_WS_URL;

type CallStatus = "idle" | "connecting" | "listening" | "speaking" | "processing";

export function Conversation() {
  const websocket = useRef<WebSocket | null>(null);

  const [language, setLanguage] = useState("pa");
  const [messages, setMessages] = useState<Message[]>([]);
  const [confirmedOrder, setConfirmedOrder] = useState<OrderConfirmed | null>(null);
  const [callStatus, setCallStatus] = useState<CallStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const autoScrollRef = useAutoScroll(messages);

  const { startMicrophoneStream, cleanupMicrophoneStream } = useMicrophone({
    onData: (data) => websocket.current?.send(data),
    onError: (err) => {
      console.error("Microphone error:", err);
      setError("Microphone error. Please allow access and try again.");
      cleanup();
    },
  });

  const { cleanupAudioPlayer, prepareAudioPlayer, addAudioChunk, interruptAudio } =
    useAudioChunkPlayer({});

  const cleanup = () => {
    if (websocket.current) {
      websocket.current.close();
      websocket.current = null;
    }
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

    ws.onopen = () => {
      setCallStatus("listening");
      startMicrophoneStream();
    };

    ws.onerror = () => {
      setError("Could not connect to voice server.");
      cleanup();
    };

    ws.onclose = () => cleanup();

    ws.onmessage = async (e) => {
      try {
        if (typeof e.data === "string") {
          const data = JSON.parse(e.data);

          if (data.type === "user_speech_start") {
            interruptAudio();
            setCallStatus("listening");
            return;
          }
          if (data.type === "user_speech_end") {
            setCallStatus("processing");
            return;
          }
          if (data.type === "session_start" || data.type === "metric") {
            return;
          }

          // Order confirmed — populate the right panel
          if (data.type === "order_confirmed") {
            const parsed = orderConfirmedSchema.safeParse(data);
            if (parsed.success) setConfirmedOrder(parsed.data);
            return;
          }

          const message = messageSchema.parse(data);
          setMessages((prev) => updateMessages(prev, message));

          if (message.type === "transcription") {
            interruptAudio();
            setCallStatus("listening");
          } else if (message.type === "llm_response") {
            setCallStatus("speaking");
          }
        } else if (e.data instanceof Blob) {
          addAudioChunk(await e.data.arrayBuffer());
        }
      } catch (err) {
        console.error(err);
      }
    };
  };

  const endCall = () => cleanup();

  useEffect(() => {
    return () => { cleanup(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isActive = callStatus !== "idle";

  return (
    <div className="h-full flex overflow-hidden">

      {/* ── LEFT: Chat panel ─────────────────────────────── */}
      <div
        className="flex flex-col"
        style={{
          width: "58%",
          borderRight: "1px solid var(--border)",
          background: "var(--surface)",
        }}
      >
        {/* Status bar */}
        <div
          className="flex-none flex items-center gap-2 px-4 py-2.5 border-b"
          style={{ borderColor: "var(--border)" }}
        >
          <StatusDot status={callStatus} />
          <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
            <StatusLabel status={callStatus} />
          </span>
        </div>

        {/* Messages */}
        <div
          ref={autoScrollRef}
          className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3"
        >
          {messages.length === 0 && !isActive && (
            <EmptyState />
          )}
          {messages.map((msg, i) => (
            <ChatMessage key={i} message={msg} />
          ))}
        </div>

        {error && (
          <div
            className="flex-none mx-4 mb-2 px-3 py-2 rounded-lg text-xs"
            style={{ background: "rgba(239,68,68,0.1)", color: "#f87171" }}
          >
            {error}
          </div>
        )}

        {/* Controls */}
        <div
          className="flex-none flex items-center gap-3 px-4 py-3 border-t"
          style={{ borderColor: "var(--border)" }}
        >
          {/* Language selector */}
          <select
            disabled={isActive}
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="text-xs rounded-lg px-2 py-1.5 outline-none cursor-pointer disabled:opacity-40"
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

          {/* Call button */}
          {isActive ? (
            <button
              onClick={endCall}
              className="flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold text-white"
              style={{ background: "#dc2626" }}
            >
              <span
                className={callStatus === "listening" ? "animate-mic-ring" : ""}
                style={{
                  width: 8, height: 8, borderRadius: "50%",
                  background: callStatus === "listening" ? "white" : "rgba(255,255,255,0.6)",
                  display: "inline-block",
                }}
              />
              {callStatus === "listening" ? "Listening…" :
               callStatus === "speaking"   ? "Sierra speaking" :
               callStatus === "processing" ? "Processing…" : "On call"}
            </button>
          ) : (
            <button
              onClick={startCall}
              className="flex items-center gap-2 px-5 py-2 rounded-full text-sm font-semibold text-black transition-opacity hover:opacity-90"
              style={{ background: "var(--accent)" }}
            >
              <MicIcon />
              Start call
            </button>
          )}
        </div>
      </div>

      {/* ── RIGHT: Order panel ───────────────────────────── */}
      <div className="flex-1 overflow-hidden" style={{ background: "var(--bg)" }}>
        <OrderPanel
          messages={messages}
          confirmedOrder={confirmedOrder}
          isCallActive={isActive}
        />
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────

function StatusDot({ status }: { status: CallStatus }) {
  const color =
    status === "idle"       ? "#3a3a3a" :
    status === "listening"  ? "#f59e0b" :
    status === "speaking"   ? "#22c55e" :
    status === "processing" ? "#818cf8" : "#888";

  return (
    <span
      style={{
        width: 7, height: 7, borderRadius: "50%",
        background: color, display: "inline-block",
        transition: "background 0.3s",
      }}
    />
  );
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

function EmptyState() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-16 select-none">
      <div
        className="w-12 h-12 rounded-full flex items-center justify-center mb-3"
        style={{ background: "var(--surface-raised)" }}
      >
        <MicIcon size={20} color="var(--text-dim)" />
      </div>
      <p className="text-sm" style={{ color: "var(--text-dim)" }}>
        Press Start call to talk to Sierra
      </p>
    </div>
  );
}

function MicIcon({ size = 14, color = "currentColor" }: { size?: number; color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  );
}
