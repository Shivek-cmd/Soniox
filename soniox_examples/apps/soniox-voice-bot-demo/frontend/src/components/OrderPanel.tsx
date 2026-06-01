import { useMemo } from "react";
import type { Message, OrderConfirmed, OrderItem } from "../utils/messages";
import { parseOrderFromBotMessages } from "../utils/menuData";

interface Props {
  messages: Message[];
  confirmedOrder: OrderConfirmed | null;
  isCallActive: boolean;
  embedded?: boolean; // when true: no h-full, compact layout for inline use
}

export function OrderPanel({ messages, confirmedOrder, isCallActive, embedded = false }: Props) {
  // Parse bot messages for in-progress item detection
  const detectedItems = useMemo(() => {
    if (confirmedOrder) return [];
    const botTexts = messages
      .filter((m) => m.type === "llm_response")
      .map((m) => (m as { type: "llm_response"; text: string }).text);
    return parseOrderFromBotMessages(botTexts);
  }, [messages, confirmedOrder]);

  const pad = embedded ? "px-4 py-3" : "px-5 py-5";

  // ── Confirmed state ────────────────────────────────────
  if (confirmedOrder) {
    return <ConfirmedView order={confirmedOrder} embedded={embedded} />;
  }

  // ── Active call with detected items ───────────────────
  if (isCallActive) {
    return (
      <div className={`flex flex-col ${embedded ? "" : "h-full"} ${pad}`}>
        <SectionHeader title="Your Order" />
        {detectedItems.length === 0 ? <BuildingState embedded={embedded} /> : <ItemsView items={detectedItems} />}
      </div>
    );
  }

  // ── Idle ───────────────────────────────────────────────
  return <IdleState embedded={embedded} />;
}

// ── Views ────────────────────────────────────────────────

function ConfirmedView({ order, embedded = false }: { order: OrderConfirmed; embedded?: boolean }) {
  const orderTypeLabel =
    order.order_type === "pickup"   ? "Pickup" :
    order.order_type === "dine_in"  ? "Dine-in" : "Delivery";

  const pad = embedded ? "px-4 py-3" : "px-5 py-5";
  return (
    <div className={`flex flex-col ${embedded ? "" : "h-full overflow-y-auto"} ${pad}`}>
      {/* Confirmed banner */}
      <div
        className="animate-confirm-pop rounded-xl p-4 mb-5 flex items-center gap-3"
        style={{ background: "rgba(34,197,94,0.1)", border: "1px solid rgba(34,197,94,0.25)" }}
      >
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center flex-none"
          style={{ background: "rgba(34,197,94,0.2)" }}
        >
          <CheckIcon />
        </div>
        <div>
          <p className="text-sm font-semibold" style={{ color: "#4ade80" }}>
            Order Confirmed
          </p>
          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
            {order.order_id} · {order.wait_time}
          </p>
        </div>
      </div>

      <SectionHeader title="Order Summary" />

      {/* Items */}
      <div className="flex flex-col gap-2 mb-4">
        {order.items.map((item, i) => (
          <ConfirmedItem key={i} item={item} index={i} />
        ))}
      </div>

      {/* Total */}
      <div
        className="flex items-center justify-between py-3 border-t mb-4"
        style={{ borderColor: "var(--border)" }}
      >
        <span className="text-sm font-semibold" style={{ color: "var(--text)" }}>
          Total
        </span>
        <span className="text-sm font-bold" style={{ color: "var(--accent)" }}>
          ${order.total_amount.toFixed(2)}
        </span>
      </div>

      {/* Customer info */}
      <div
        className="rounded-xl p-3 flex flex-col gap-2"
        style={{ background: "var(--surface-raised)", border: "1px solid var(--border)" }}
      >
        <InfoRow label="Name" value={order.customer_name} />
        <InfoRow label="Phone" value={order.phone_number} />
        <InfoRow label="Type" value={orderTypeLabel} accent />
        {order.special_instructions && (
          <InfoRow label="Notes" value={order.special_instructions} />
        )}
      </div>
    </div>
  );
}

function ItemsView({ items }: { items: { name: string; quantity: number; price: number }[] }) {
  const subtotal = items.reduce((s, i) => s + i.price * i.quantity, 0);
  return (
    <div className="flex flex-col flex-1">
      <div className="flex flex-col gap-2 mb-3">
        {items.map((item, i) => (
          <div
            key={item.name}
            className="animate-item-in flex items-start justify-between gap-2 rounded-lg px-3 py-2.5"
            style={{
              background: "var(--surface-raised)",
              border: "1px solid var(--border)",
              animationDelay: `${i * 60}ms`,
            }}
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate" style={{ color: "var(--text)" }}>
                {item.name}
              </p>
              <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
                × {item.quantity}
              </p>
            </div>
            <span className="text-sm font-semibold flex-none" style={{ color: "var(--accent)" }}>
              ${(item.price * item.quantity).toFixed(2)}
            </span>
          </div>
        ))}
      </div>

      {/* Running total */}
      <div
        className="flex items-center justify-between py-2.5 px-3 rounded-lg"
        style={{ background: "rgba(245,158,11,0.08)", border: "1px solid rgba(245,158,11,0.18)" }}
      >
        <span className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
          Estimated total
        </span>
        <span className="text-sm font-bold" style={{ color: "var(--accent)" }}>
          ${subtotal.toFixed(2)}
        </span>
      </div>

      <p className="text-xs mt-3" style={{ color: "var(--text-dim)" }}>
        Prices may adjust when order is confirmed.
      </p>
    </div>
  );
}

function BuildingState({ embedded = false }: { embedded?: boolean }) {
  return (
    <div className={`flex flex-col items-center justify-center ${embedded ? "py-4" : "flex-1 py-10"}`}>
      <div className="flex gap-1.5 mb-3">
        <span className="w-2 h-2 rounded-full dot-1" style={{ background: "var(--accent)" }} />
        <span className="w-2 h-2 rounded-full dot-2" style={{ background: "var(--accent)" }} />
        <span className="w-2 h-2 rounded-full dot-3" style={{ background: "var(--accent)" }} />
      </div>
      <p className="text-xs font-medium" style={{ color: "var(--text-muted)" }}>
        Taking your order…
      </p>
    </div>
  );
}

function IdleState({ embedded = false }: { embedded?: boolean }) {
  return (
    <div className={`flex items-center gap-3 select-none ${embedded ? "px-4 py-4" : "h-full flex-col justify-center px-6"}`}>
      <div
        className={`${embedded ? "w-8 h-8 rounded-xl flex-none" : "w-14 h-14 rounded-2xl mb-4"} flex items-center justify-center`}
        style={{ background: "var(--surface-raised)" }}
      >
        <BagIcon size={embedded ? 16 : 24} />
      </div>
      <div>
        <p className={`${embedded ? "text-xs" : "text-sm"} font-semibold`} style={{ color: "var(--text-muted)" }}>
          Your order will appear here
        </p>
        {!embedded && (
          <p className="text-xs text-center mt-1" style={{ color: "var(--text-dim)" }}>
            Start a call to begin ordering
          </p>
        )}
      </div>
    </div>
  );
}

// ── Small components ─────────────────────────────────────

function SectionHeader({ title }: { title: string }) {
  return (
    <h2
      className="text-xs font-semibold uppercase tracking-widest mb-3"
      style={{ color: "var(--text-dim)" }}
    >
      {title}
    </h2>
  );
}

function ConfirmedItem({ item, index }: { item: OrderItem; index: number }) {
  return (
    <div
      className="animate-item-in flex items-start justify-between gap-2 rounded-lg px-3 py-2.5"
      style={{
        background: "var(--surface-raised)",
        border: "1px solid var(--border)",
        animationDelay: `${index * 60}ms`,
      }}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate" style={{ color: "var(--text)" }}>
          {item.name}
        </p>
        <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
          × {item.quantity} · ${item.price.toFixed(2)} each
        </p>
      </div>
      <span className="text-sm font-semibold flex-none" style={{ color: "var(--accent)" }}>
        ${(item.price * item.quantity).toFixed(2)}
      </span>
    </div>
  );
}

function InfoRow({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs" style={{ color: "var(--text-dim)" }}>
        {label}
      </span>
      <span
        className="text-xs font-medium"
        style={{ color: accent ? "var(--accent)" : "var(--text-muted)" }}
      >
        {value}
      </span>
    </div>
  );
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#4ade80" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function BagIcon({ size = 24 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="var(--text-dim)" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <path d="M16 10a4 4 0 0 1-8 0" />
    </svg>
  );
}
