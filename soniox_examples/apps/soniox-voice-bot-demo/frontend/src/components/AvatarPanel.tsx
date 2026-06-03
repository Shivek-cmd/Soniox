import { useEffect, useState } from "react";

type CallStatus = "idle" | "connecting" | "listening" | "speaking" | "processing";

interface Props {
  callStatus: CallStatus;
}

// ── Built-in Sierra SVG avatar ─────────────────────────────
// South-Asian female face, mouth toggles open/closed while speaking.
// No external dependencies, no videos needed.
function SierraFace({ isSpeaking }: { isSpeaking: boolean }) {
  // Toggle mouth every 180ms while speaking to simulate talking
  const [mouthOpen, setMouthOpen] = useState(false);

  useEffect(() => {
    if (!isSpeaking) { setMouthOpen(false); return; }
    const id = setInterval(() => setMouthOpen((o) => !o), 180);
    return () => clearInterval(id);
  }, [isSpeaking]);

  // Blink every ~4 seconds
  const [blinking, setBlinking] = useState(false);
  useEffect(() => {
    const blink = () => {
      setBlinking(true);
      setTimeout(() => setBlinking(false), 120);
    };
    const id = setInterval(blink, 3800 + Math.random() * 1200);
    return () => clearInterval(id);
  }, []);

  const eyeHeight = blinking ? 1 : 7;

  return (
    <svg
      viewBox="0 0 120 130"
      width="100%"
      height="100%"
      style={{ display: "block" }}
    >
      {/* ── Hair (back layer) ──────────────────── */}
      <ellipse cx="60" cy="36" rx="38" ry="30" fill="#1C0A00" />

      {/* ── Face ──────────────────────────────── */}
      <ellipse cx="60" cy="76" rx="34" ry="38" fill="#C88B5A" />

      {/* ── Hair (front overlap, sides) ────────── */}
      <rect x="22" y="40" width="9" height="36" rx="5" fill="#1C0A00" />
      <rect x="89" y="40" width="9" height="36" rx="5" fill="#1C0A00" />

      {/* ── Neck ──────────────────────────────── */}
      <rect x="50" y="108" width="20" height="14" rx="5" fill="#C88B5A" />

      {/* ── Eyebrows ──────────────────────────── */}
      <path d="M 38 58 Q 46 53 54 57"
        stroke="#2D1000" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <path d="M 66 57 Q 74 53 82 58"
        stroke="#2D1000" strokeWidth="2.5" fill="none" strokeLinecap="round" />

      {/* ── Eyes ──────────────────────────────── */}
      <ellipse cx="46" cy="68" rx="8" ry={eyeHeight} fill="white" />
      <ellipse cx="74" cy="68" rx="8" ry={eyeHeight} fill="white" />
      {!blinking && (
        <>
          <circle cx="47" cy="69" r="4.5" fill="#2D1000" />
          <circle cx="75" cy="69" r="4.5" fill="#2D1000" />
          {/* Iris highlight */}
          <circle cx="48.5" cy="67" r="1.5" fill="white" />
          <circle cx="76.5" cy="67" r="1.5" fill="white" />
        </>
      )}

      {/* ── Nose ──────────────────────────────── */}
      <ellipse cx="60" cy="83" rx="5" ry="3" fill="#B87545" />

      {/* ── Mouth ─────────────────────────────── */}
      {mouthOpen ? (
        // Talking — open mouth
        <>
          <ellipse cx="60" cy="96" rx="10" ry="6.5" fill="#7A1A1A" />
          <rect x="52" y="91" width="16" height="5" rx="2.5" fill="#F5F0E8" />
        </>
      ) : (
        // Smiling closed mouth (also the idle state)
        <path
          d="M 50 93 Q 60 101 70 93"
          stroke="#7A1A1A"
          strokeWidth="2.5"
          fill="none"
          strokeLinecap="round"
        />
      )}

      {/* ── Gold earrings ─────────────────────── */}
      <circle cx="27" cy="79" r="3.5" fill="#F59E0B" />
      <circle cx="93" cy="79" r="3.5" fill="#F59E0B" />

      {/* ── Dupatta (scarf) hint at bottom ────── */}
      <path
        d="M 28 122 Q 60 116 92 122"
        stroke="#F59E0B"
        strokeWidth="3.5"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}


// ── Main avatar panel ──────────────────────────────────────
export function AvatarPanel({ callStatus }: Props) {
  const isSpeaking   = callStatus === "speaking";
  const isListening  = callStatus === "listening";
  const isProcessing = callStatus === "processing";
  const isActive     = callStatus !== "idle" && callStatus !== "connecting";

  return (
    <div
      className="h-full flex flex-col items-center justify-center px-4 py-8 select-none"
      style={{ background: "var(--bg)" }}
    >
      {/* ── Rings + face ─────────────────────── */}
      <div
        className="relative flex items-center justify-center mb-6"
        style={{ width: 200, height: 200 }}
      >
        {/* Outer pulse ring — speaking */}
        {isSpeaking && (
          <div
            className="absolute inset-0 rounded-full animate-avatar-pulse"
            style={{ border: "1.5px solid rgba(245,158,11,0.35)" }}
          />
        )}

        {/* Second ring */}
        <div
          className="absolute rounded-full transition-all duration-500"
          style={{
            inset: 12,
            border: `1.5px solid ${isActive ? "rgba(245,158,11,0.25)" : "var(--border)"}`,
          }}
        />

        {/* Third decorative ring */}
        <div
          className="absolute rounded-full"
          style={{
            inset: 24,
            border: `1px solid ${isActive ? "rgba(245,158,11,0.12)" : "rgba(255,255,255,0.04)"}`,
          }}
        />

        {/* Avatar circle */}
        <div
          className="relative w-32 h-32 rounded-full overflow-hidden transition-all duration-500"
          style={{
            border: `2px solid ${isActive ? "rgba(245,158,11,0.5)" : "var(--border)"}`,
            boxShadow: isActive
              ? "0 0 40px rgba(245,158,11,0.2), 0 0 80px rgba(245,158,11,0.05)"
              : "none",
            background: "linear-gradient(160deg, #2a1f3d 0%, #1a1a2e 100%)",
          }}
        >
          <SierraFace isSpeaking={isSpeaking} />
        </div>

        {/* Listening waveform bars */}
        {isListening && (
          <div
            className="absolute flex items-center gap-1"
            style={{ bottom: 22, left: "50%", transform: "translateX(-50%)" }}
          >
            {[0, 1, 2, 3, 4].map((i) => (
              <span
                key={i}
                className="rounded-full"
                style={{
                  width: 4,
                  height: 4 + i * 3,
                  background: "#f59e0b",
                  animation: `wave-bar 0.8s ${i * 0.1}s ease-in-out infinite alternate`,
                }}
              />
            ))}
          </div>
        )}

        {/* Processing spinner */}
        {isProcessing && (
          <div
            className="absolute rounded-full"
            style={{
              inset: 6,
              border: "2px solid transparent",
              borderTopColor: "rgba(245,158,11,0.6)",
              animation: "spin 1s linear infinite",
            }}
          />
        )}
      </div>

      {/* ── Name & role ─────────────────────────── */}
      <h2
        className="text-xl font-bold mb-1 tracking-tight"
        style={{ color: "var(--text)" }}
      >
        Sierra
      </h2>
      <p className="text-xs mb-5" style={{ color: "var(--text-muted)" }}>
        AI Voice Assistant · Parkash Sweets
      </p>

      {/* ── Status badge ────────────────────────── */}
      <div
        className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-300"
        style={{
          background: isActive ? "rgba(245,158,11,0.1)" : "var(--surface-raised)",
          border: `1px solid ${isActive ? "rgba(245,158,11,0.25)" : "var(--border)"}`,
          color: isActive ? "#f59e0b" : "var(--text-dim)",
        }}
      >
        <span
          className="rounded-full shrink-0"
          style={{
            width: 6,
            height: 6,
            background: isSpeaking   ? "#22c55e"
                      : isListening  ? "#f59e0b"
                      : isProcessing ? "#818cf8"
                      : "var(--text-dim)",
            display: "inline-block",
            transition: "background 0.3s",
          }}
        />
        {callStatus === "idle"       && "Ready to take your order"}
        {callStatus === "connecting" && "Connecting…"}
        {callStatus === "listening"  && "Listening…"}
        {callStatus === "speaking"   && "Sierra is speaking"}
        {callStatus === "processing" && "Thinking…"}
      </div>

      {/* ── Idle hint ───────────────────────────── */}
      {!isActive && (
        <p
          className="text-xs text-center mt-5 max-w-45 leading-relaxed"
          style={{ color: "var(--text-dim)" }}
        >
          Start a call — Sierra speaks English, Hindi, and Punjabi.
        </p>
      )}
    </div>
  );
}
