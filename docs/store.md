# Browse Store — E-Commerce Tab

The "Browse Store" tab is a full e-commerce storefront built into the existing React frontend at `voice.bizbull.ai`. Customers can browse the Parkash Sweets menu, add items to a cart, customise modifiers, and place an order that lands directly in the Clover POS dashboard and kitchen display.

This is **separate from the AI ordering tab** — no voice, no Sierra, no WebSocket. It's a standard React + REST API flow backed by Clover.

---

## What's Built

- Category filter pills + search bar
- Responsive item grid with price, photo (if available), and "Add" button
- Item modal: modifier groups with radio (single) or checkbox (multi), disabled "Add to Cart" until required groups are satisfied
- Cart sidebar: item list, quantity controls, subtotal + 5% GST + total
- Checkout modal: customer name, phone, order type (dine-in / takeout), optional note
- Order confirmation: success overlay with Clover order ID and ~15–25 min estimate
- Graceful fallback: if `store-api` is unreachable, the store loads from static `menu.json`

---

## What's NOT Built Yet

- **Payment** — Clover Hosted Checkout (`POST /invoicingcheckoutservice/v1/checkouts` → redirect to Clover payment page) is not implemented. Orders are created in Clover but not paid.
- **Wait:** payment will be added after purchasing Clover production access.

---

## File Locations

| File | Purpose |
|------|---------|
| `soniox_examples/apps/soniox-voice-bot-demo/store-api/main.py` | FastAPI backend — menu fetch + order creation |
| `soniox_examples/apps/soniox-voice-bot-demo/store-api/requirements.txt` | Python deps |
| `soniox_examples/apps/soniox-voice-bot-demo/store-api/Dockerfile` | Docker image (python:3.13-slim, port 8766) |
| `soniox_examples/apps/soniox-voice-bot-demo/frontend/src/components/Store.tsx` | Full store UI (~600 lines, self-contained) |
| `soniox_examples/apps/soniox-voice-bot-demo/frontend/src/App.tsx` | Tab switcher: "Order with Sierra" / "Browse Store" |
| `soniox_examples/apps/soniox-voice-bot-demo/frontend/vite.config.ts` | Dev proxy: `/store-api` → `localhost:8766` |

---

## store-api Endpoints

All endpoints are served at port 8766 internally. Caddy strips the `/store-api` prefix so the service sees requests without it.

### `GET /menu`

Fetches all items from Clover:

```
GET https://api.clover.com/v3/merchants/{mId}/items
    ?expand=categories,modifierGroups
    &limit=200
    &offset=0
```

Paginates until all items are fetched. Filters out:
- `hidden: true`
- `deleted: true`
- `price: 0` (variable-price items not supported in the store)
- `ageRestricted: true`

Returns:
```json
{
  "categories": [
    { "id": "...", "name": "Samosa" }
  ],
  "items": [
    {
      "id": "...",
      "name": "Aloo Samosa",
      "price": 250,
      "priceDisplay": "$2.50",
      "description": "...",
      "imageUrl": null,
      "categories": ["..."],
      "modifierGroups": [
        {
          "id": "...",
          "name": "Chutney",
          "minRequired": 0,
          "maxAllowed": 1,
          "modifiers": [
            { "id": "...", "name": "Tamarind", "price": 0, "priceDisplay": "" }
          ]
        }
      ]
    }
  ]
}
```

### `POST /orders`

Request body:
```json
{
  "items": [
    {
      "item_id": "...",
      "name": "Aloo Samosa",
      "quantity": 2,
      "unit_price": 250,
      "modifiers": [
        { "modifier_id": "...", "modifier_group_id": "...", "name": "Tamarind", "price": 0 }
      ]
    }
  ],
  "order_type": "takeout",
  "customer_name": "Raj Singh",
  "customer_phone": "7801234567",
  "note": "Extra spicy please"
}
```

Clover has no quantity field on line items — the API posts one line_item per unit:
```python
for _ in range(item.quantity):
    POST /v3/merchants/{mId}/orders/{orderId}/line_items
    # then per modifier:
    POST /v3/merchants/{mId}/orders/{orderId}/line_items/{lineItemId}/modifications
```

Returns:
```json
{
  "order_id": "CLOVER_ORDER_ID",
  "total_display": "$5.25"
}
```

### `GET /orders/{order_id}`

Returns current Clover order state (for polling, not used in UI yet):
```json
{
  "id": "...",
  "state": "open",
  "payment_state": "unpaid",
  "total": 525
}
```

### `GET /health`

```json
{ "ok": true, "merchant_id": "..." }
```

---

## Frontend Architecture

### Store.tsx Components

| Component | Role |
|-----------|------|
| `Store` | Root: fetches menu, owns category/search/cart/modal state |
| `Pill` | Category filter button |
| `ItemCard` | Grid card with name, price, photo, Add button |
| `CartSidebar` | Right panel: cart items, totals, Place Order button |
| `CartRow` | Single cart line with quantity +/- |
| `PriceRow` | Subtotal / GST / Total display |
| `ItemModal` | Full item detail + modifier selection |
| `CheckoutModal` | Name / phone / order type / note form |
| `SuccessOverlay` | Full-screen success with Clover order ID |
| `SkeletonGrid` | Loading placeholder cards |
| `EmptyState` | "No items found" state |
| `Overlay` | Backdrop for modals |

### Cart State

Cart is managed with `useReducer` + `cartReducer`. Cart entries are keyed by:

```ts
cartKey(itemId, modifierIds) → `${itemId}__${sortedModIds.join(",")}`
```

This means the same item with different modifiers is a separate cart entry.

Actions: `ADD`, `INCREMENT`, `DECREMENT` (removes at 0), `CLEAR`.

### Pricing

All prices from Clover are in **cents** (integer). The `cad(cents)` formatter:
```ts
const cad = (cents: number) => `$${(cents / 100).toFixed(2)}`
```

GST is 5% (Canadian), computed at cart total time. Displayed as "GST (5%)".

### API Base URL

```ts
const STORE_API = import.meta.env.VITE_STORE_API_URL ?? "/store-api"
```

- **Local dev:** Vite proxies `/store-api` → `http://localhost:8766`
- **Production:** Caddy routes `/store-api/*` → `store-api:8766` (strips prefix)
- `VITE_STORE_API_URL` defaults to `/store-api` and does not need to be set in either environment

### Static Fallback

On startup, `Store` calls `GET /store-api/menu` with a 6-second timeout. On any failure, it imports from `menuData.ts` which wraps the static `server/menu.json`. The fallback is silent — no error is shown to the user.

---

## Tab Switcher (App.tsx)

```tsx
type Tab = "ai" | "store"
const [tab, setTab] = useState<Tab>("ai")
```

The header has two pill buttons with amber accent for the active tab. Switching tabs is instant (no page load — both components stay mounted in the same app).

The "Order with Sierra" tab renders `<Conversation />`. The "Browse Store" tab renders `<Store />`.

---

## Data Flow Diagram

```text
Browser → GET /store-api/menu
  → Caddy strips prefix → store-api:8766 /menu
  → store-api paginates Clover items
  → returns filtered JSON
  → React renders category grid + item cards

User adds items, opens modal, picks modifiers
User opens cart, clicks "Place Order"
User fills checkout form, clicks "Confirm Order"

Browser → POST /store-api/orders { items, order_type, name, phone }
  → Caddy → store-api:8766 /orders
  → store-api creates Clover order
  → posts line_items (one per unit) + modifications
  → returns { order_id, total_display }
  → React shows success overlay with order ID
  → Order appears in Clover POS dashboard immediately
```

---

## Clover POS Side Effects

When an order is placed via the Browse Store:
- A new order appears in the Clover merchant dashboard under "Orders"
- If a Kitchen Display System (KDS) is set up on Clover, the order appears there
- The order is in `open` + `unpaid` state (no payment taken)
- Staff can see all items and modifiers exactly as selected

---

## Routing & Infrastructure

### Caddy (`Caddyfile`)
```caddy
@store_api path /store-api /store-api/*
handle @store_api {
    uri strip_prefix /store-api
    reverse_proxy store-api:8766
}
```

The strip_prefix is critical — store-api routes are at `/menu`, `/orders`, etc., not `/store-api/menu`.

### Docker (`docker-compose.yml`)
```yaml
store-api:
  build:
    context: ./soniox_examples/apps/soniox-voice-bot-demo/store-api
  environment:
    - CLOVER_BASE_URL=${CLOVER_BASE_URL}
    - CLOVER_MERCHANT_ID=${CLOVER_MERCHANT_ID}
    - CLOVER_ACCESS_TOKEN=${CLOVER_ACCESS_TOKEN}
  restart: unless-stopped
```

`caddy` has `store-api` in its `depends_on` list.

### Vite Dev Proxy (`vite.config.ts`)
```ts
server: {
  proxy: {
    "/store-api": {
      target: "http://localhost:8766",
      rewrite: (path) => path.replace(/^\/store-api/, ""),
      changeOrigin: true,
    },
  },
},
```

---

## Pending Work

| Item | Status | Notes |
|------|--------|-------|
| Clover payment (Hosted Checkout) | Not started | Need Clover production access first |
| Switch `CLOVER_BASE_URL` to production | Not done | Will do after purchasing production access |
| Order status polling / confirmation | Not started | `GET /orders/{id}` endpoint exists but not used in UI |
| Item images | Partial | Clover items have `imageUrl` field; store-api passes it through; frontend renders if present |
| Inventory/availability check | Not started | Could check `available: false` on Clover items and grey them out |

---

## Environment Variables

Only three env vars are needed for store-api:

```env
CLOVER_BASE_URL=https://apisandbox.dev.clover.com   # switch to https://api.clover.com for production
CLOVER_MERCHANT_ID=your_merchant_id
CLOVER_ACCESS_TOKEN=your_access_token
```

These are the same credentials used by `voice-server`. Both services share the same Clover merchant account.
