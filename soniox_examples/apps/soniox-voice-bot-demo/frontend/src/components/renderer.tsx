import type { Message } from "../utils/messages";

export function ChatMessage({ message }: { message: Message }) {
  if (message.type === "transcription") {
    return (
      <div className="animate-msg-in flex justify-end">
        <div
          className="max-w-xs rounded-2xl rounded-br-sm px-3.5 py-2.5 text-sm"
          style={{ background: "var(--accent)", color: "#000" }}
        >
          <span className="font-medium">{message.final_text}</span>
          {message.non_final_text && (
            <span style={{ opacity: 0.6 }}>{message.non_final_text}</span>
          )}
        </div>
      </div>
    );
  }

  if (message.type === "llm_response") {
    return (
      <div className="animate-msg-in flex items-start gap-2.5">
        {/* Sierra avatar */}
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center flex-none text-xs font-bold mt-0.5"
          style={{ background: "rgba(245,158,11,0.15)", color: "var(--accent)" }}
        >
          S
        </div>
        <div
          className="max-w-xs rounded-2xl rounded-bl-sm px-3.5 py-2.5 text-sm leading-relaxed"
          style={{
            background: "var(--surface-raised)",
            border: "1px solid var(--border)",
            color: "var(--text)",
          }}
        >
          {message.text}
        </div>
      </div>
    );
  }

  return null;
}

// Legacy export kept for any existing imports
export function Renderer({ messages }: { messages: Message[] }) {
  return (
    <div className="flex flex-col gap-3">
      {messages.map((msg, i) => (
        <ChatMessage key={i} message={msg} />
      ))}
    </div>
  );
}
