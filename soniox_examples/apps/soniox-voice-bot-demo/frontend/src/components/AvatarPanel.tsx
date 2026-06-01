type CallStatus = "idle" | "connecting" | "listening" | "speaking" | "processing";

interface Props {
  callStatus: CallStatus;
}

export function AvatarPanel({ callStatus }: Props) {
  const isSpeaking   = callStatus === "speaking";
  const isListening  = callStatus === "listening";
  const isProcessing = callStatus === "processing";
  const isActive     = callStatus !== "idle" && callStatus !== "connecting";

  return (
    <div
      className="h-full flex flex-col items-center justify-center px-6 py-8 select-none"
      style={{ background: "var(--bg)" }}
    >
      {/* Avatar ring + circle */}
      <div className="relative flex items-center justify-center mb-6" style={{ width: 200, height: 200 }}>

        {/* Outer pulse ring — speaking */}
        {isSpeaking && (
          <div
            className="absolute inset-0 rounded-full animate-avatar-pulse"
            style={{ border: "1.5px solid rgba(245,158,11,0.35)" }}
          />
        )}

        {/* Second ring — always visible, glows on active */}
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

        {/* Core avatar */}
        <div
          className="relative w-32 h-32 rounded-full flex items-center justify-center transition-all duration-500"
          style={{
            background: isActive
              ? "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)"
              : "linear-gradient(135deg, #2a2a2a 0%, #1a1a1a 100%)",
            boxShadow: isActive
              ? "0 0 40px rgba(245,158,11,0.2), 0 0 80px rgba(245,158,11,0.05)"
              : "none",
          }}
        >
          <span
            className="font-bold transition-all duration-500"
            style={{
              fontSize: 52,
              color: isActive ? "#000" : "var(--text-dim)",
              fontFamily: "Georgia, serif",
              letterSpacing: "-2px",
            }}
          >
            S
          </span>
        </div>

        {/* Listening waveform dots */}
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

      {/* Name */}
      <h2
        className="text-2xl font-bold mb-1 tracking-tight"
        style={{ color: "var(--text)" }}
      >
        Sierra
      </h2>

      {/* Role */}
      <p className="text-sm mb-5" style={{ color: "var(--text-muted)" }}>
        AI Voice Assistant · Parkash Sweets
      </p>

      {/* Status badge */}
      <div
        className="flex items-center gap-2 px-4 py-2 rounded-full text-xs font-medium transition-all duration-300"
        style={{
          background: isActive ? "rgba(245,158,11,0.1)" : "var(--surface-raised)",
          border: `1px solid ${isActive ? "rgba(245,158,11,0.25)" : "var(--border)"}`,
          color: isActive ? "#f59e0b" : "var(--text-dim)",
        }}
      >
        <span
          className="rounded-full"
          style={{
            width: 6,
            height: 6,
            background: isSpeaking ? "#22c55e" : isListening ? "#f59e0b" : isProcessing ? "#818cf8" : "var(--text-dim)",
            display: "inline-block",
            transition: "background 0.3s",
          }}
        />
        {callStatus === "idle"       && "Ready to take your order"}
        {callStatus === "connecting" && "Connecting…"}
        {callStatus === "listening"  && "Listening to you"}
        {callStatus === "speaking"   && "Sierra is speaking"}
        {callStatus === "processing" && "Thinking…"}
      </div>

      {/* Personality line */}
      {!isActive && (
        <p
          className="text-xs text-center mt-6 max-w-[200px] leading-relaxed"
          style={{ color: "var(--text-dim)" }}
        >
          Start a call and Sierra will guide you through the menu in English, Hindi, or Punjabi.
        </p>
      )}
    </div>
  );
}
