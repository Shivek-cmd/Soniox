# Browse Store — E-Commerce Tab

The "Browse Store" tab is a full e-commerce storefront built into the existing React frontend at `voice.bizbull.ai`. Customers can browse the Parkash Sweets menu, add items to a cart, customise modifiers, and place an order that lands directly in the Clover POS dashboard and kitchen display.

This is **separate from the AI ordering tab** — no voice, no Sierra, no WebSocket. It's a standard React + REST API flow backed by Clover.

---

## What's Built

- Category filter pills + search bar
- Responsive item grid: food photos (Unsplash fallback per category), sold-out items greyed out with "Sold Out" badge
- Item modal: modifier groups with radio (single) or checkbox (multi), disabled "Add to Cart" until required groups are satisfied
- **Desktop:** cart sidebar (right panel). **Mobile:** floating amber cart FAB (fixed bottom-right) + slide-up bottom sheet
- Checkout modal: customer name, phone, order type (dine-in / takeout), optional note, **promo code input** (matched against Clover named discounts)
- **Payment via Clover Hosted Checkout** — clicking "Pay Now" redirects to Clover's payment page; on return `?payment=success`, cart is cleared and success overlay shown
- Success overlay with total paid + green savings banner if a promo code was applied
- Graceful fallback: if `store-api` is unreachable on startup, store loads from static `menu.json`
- Fully mobile-responsive: `useIsMobile(640)` drives layout; mobile gets bottom nav, full-screen modals, cart bottom sheet

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

### `GET /discounts`

Returns named discounts configured in Clover (used to populate the promo code input):

```json
{ "discounts": [{ "id": "ABC123", "name": "SUMMER10" }] }
```

### `POST /checkout`

**This is the primary checkout path for the Browse Store tab.**

Request body (same shape as `POST /orders` plus optional `discount_code`):
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
  "note": "Extra spicy please",
  "discount_code": "SUMMER10"
}
```

What happens server-side:
1. If `discount_code` provided: validates it against `GET /v3/merchants/{mId}/discounts`
2. Builds `line_items` list for Clover's Hosted Checkout payload
3. If discount valid: appends a negative line item for the discount amount; computes `discount_amount` from Clover's percentage field (guards for both integer `%` and basis-point format)
4. Calls `POST /invoicingcheckoutservice/v1/checkouts` with merchant, shoppingCart, customer, redirectUrls
5. Returns redirect URL and session info

Returns:
```json
{
  "checkout_url": "https://checkout.clover.com/...",
  "session_id": "SESSION_ID",
  "discount_amount": 75,
  "discount_name": "SUMMER10"
}
```

Frontend:
- Saves `{ session_id, total, discount_amount, discount_name }` to `sessionStorage` as `pendingOrder`
- Redirects: `window.location.href = checkout_url`
- On return with `?payment=success`: reads sessionStorage, clears cart, shows `SuccessOverlay`
- On return with `?payment=cancelled`: silently resumes browsing with cart intact

**Test card:** `4111 1111 1111 1111`, any future expiry, any CVV (sandbox mode).

### `POST /orders`

Legacy endpoint — creates a Clover order without taking payment. Still used internally (e.g. voice-server AI tab path). Supports optional `discount_code`; returns `{ order_id, total_display, discount_amount?, discount_name? }`.

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
| `Store` | Root: fetches menu + discounts, owns category/search/cart/modal state; handles `?payment=` redirect on mount |
| `Pill` | Category filter button |
| `ItemCard` | Grid card with food photo, sold-out badge/greyout, price, Add button |
| `CartSidebar` | Desktop right panel: cart items, totals, Place Order button |
| `MobileCartSheet` | Mobile slide-up bottom sheet for cart (`fixed inset-0` backdrop + `rounded-t-2xl` panel) |
| `CartRow` | Single cart line with quantity +/- |
| `PriceRow` | Subtotal / GST / Promo / Total display |
| `ItemModal` | Full item detail + modifier selection; full-screen on mobile |
| `CheckoutModal` | Name / phone / order type / note / promo code → redirects to Clover Hosted Checkout |
| `SuccessOverlay` | Full-screen success: total paid + optional savings banner |
| `SkeletonGrid` | Loading placeholder cards |
| `EmptyState` | "No items found" state |
| `Overlay` | `fixed inset-0` backdrop for modals |

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
User opens cart (sidebar on desktop; FAB → bottom sheet on mobile)
User clicks "Place Order" → fills name/phone/type/note
User optionally enters promo code → validated against /discounts list
User clicks "Pay Now"

Browser → POST /store-api/checkout { items, order_type, name, phone, discount_code? }
  → Caddy → store-api:8766 /checkout
  → store-api validates discount (if any), builds Hosted Checkout payload
  → POST https://api.clover.com/invoicingcheckoutservice/v1/checkouts
  → returns { checkout_url, session_id, discount_amount, discount_name }

Frontend saves pendingOrder to sessionStorage
window.location.href = checkout_url  (navigates away to Clover payment page)

Customer fills card details on Clover-hosted page → payment processed

Clover redirects → voice.bizbull.ai?payment=success

Frontend on mount:
  → reads ?payment=success query param
  → reads pendingOrder from sessionStorage
  → dispatches CLEAR to cart
  → shows SuccessOverlay: total paid + savings banner
  → Order appears in Clover POS dashboard / KDS immediately
```

---

## Clover POS Side Effects

When an order is placed via the Browse Store:
- Payment is processed by Clover's Hosted Checkout before the order lands in the dashboard
- A new order appears in the Clover merchant dashboard under "Orders" in `paid` state
- If a Kitchen Display System (KDS) is set up on Clover, the order appears there
- Staff can see all items and modifiers exactly as selected
- If a discount was applied, Clover records it against the order

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
    - FRONTEND_URL=${FRONTEND_URL:-https://voice.bizbull.ai}
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
| Switch `CLOVER_BASE_URL` to production | Not done | Change env var + redeploy store-api; see deployment section |
| Order status polling in UI | Not started | `GET /orders/{id}` endpoint exists but not used in UI |
| `book_table` tool for Sierra (AI tab) | Not started | Table reservation intent in voice agent |

---

## Environment Variables

```env
CLOVER_BASE_URL=https://apisandbox.dev.clover.com   # switch to https://api.clover.com for production
CLOVER_MERCHANT_ID=your_merchant_id
CLOVER_ACCESS_TOKEN=your_access_token
FRONTEND_URL=https://voice.bizbull.ai               # Hosted Checkout redirect base URL
```

`CLOVER_BASE_URL` and `CLOVER_ACCESS_TOKEN` are shared with `voice-server` (same Clover merchant account). `FRONTEND_URL` is store-api-specific — used to build the `?payment=success` / `?payment=cancelled` redirect URLs sent to Clover Hosted Checkout.
