# Clover POS Integration — Architecture

## What We're Building

The voice agent currently holds menu data in a static `menu.json` file and sends confirmed orders to n8n via a webhook. The POS integration replaces both of these:

- `menu.json` → **Clover Inventory API** (live menu, always in sync with POS)
- n8n webhook → **Clover Orders API** (orders land directly in the POS, visible on kitchen display and merchant devices in real-time)
- Payments can optionally be captured through Clover's Ecommerce API (card-not-present phone orders)

---

## Updated Architecture

```
PHONE PATH (existing — unchanged):
Customer Phone → Twilio → twilio-bridge → voice-server

BROWSER PATH (existing — unchanged):
Browser → React frontend → voice-server

VOICE SERVER (changes):
voice-server
  ├── STT (Soniox)
  ├── LLM (OpenAI)  ← system prompt now built from live Clover menu
  ├── TTS (Soniox)
  └── tools.py      ← place_order() now creates Clover order instead of n8n POST

NEW: clover.py (POS client module)
  ├── Menu cache    ← loaded from Clover at startup, refreshed via webhooks
  ├── Order client  ← creates atomic orders in Clover
  └── Webhook receiver (new FastAPI endpoint or added to twilio-bridge)

NEW: Clover Webhook → voice-server
  ├── Inventory events (I, IC, IG, IM) → invalidate menu cache → reload
  └── Order events (O) → optional: track order state
```

---

## Integration Points in Existing Code

### 1. `menu.json` → Clover Inventory

**Current:** Menu items, prices, descriptions, terms, pronunciations all live in `menu.json`. `tools.py` loads it at startup.

**After integration:**
- `menu.json` **keeps** only: `terms[]` (spelling variants), `pronunciation{}`, `category_aliases`, and `business` metadata — things Clover doesn't know about
- Prices, descriptions, item names, categories → pulled live from Clover
- A new `clover.py` module handles the API calls and caches the result
- `tools.py` merges Clover data with local `menu.json` extras (terms + pronunciations)

**Why keep menu.json at all?**
Clover has no field for "how a customer says this item over the phone in Punjabi" or "what Gurmukhi script to use for TTS". Those are voice-agent-specific and stay local.

### 2. `tools.py` — `place_order()` → Clover Orders API

**Current:** `place_order()` POSTs to `N8N_WEBHOOK_URL` and returns a local order ID.

**After integration:**
- `place_order()` calls `clover.py` → `POST /v3/merchants/{mId}/atomic_order/orders`
- Returns Clover's native order ID (e.g. `ABC123DEF456`) as the order ID shown to customer
- Order immediately appears on POS terminal and kitchen display
- n8n webhook call stays as an optional secondary notification (keep the env var)

### 3. `main.py` — Menu loading at startup

**Current:** `tools.py` loads `menu.json` synchronously at import time.

**After integration:**
- `main.py` calls `await clover.load_menu()` once at startup (before `serve()`)
- Menu is stored in a module-level cache in `clover.py`
- Webhook endpoint invalidates cache and triggers a background reload

### 4. `twilio-bridge` or new webhook service

A new HTTPS endpoint is needed to receive Clover webhook events. Two options:

**Option A (simpler):** Add `/clover-webhook` to the existing `twilio/main.py` FastAPI app.

**Option B (cleaner):** Add a new `webhook` service in `docker-compose.yml`.

**Recommendation: Option A** — the twilio-bridge is already a FastAPI app exposed via Caddy with a valid TLS cert. Adding one more route is trivial.

The webhook handler:
1. Validates `X-Clover-Auth` header
2. For `I`, `IC`, `IG`, `IM` events → calls `clover.invalidate_menu_cache()`
3. For `O` events → optional order state tracking

---

## Menu Sync Flow

```
Startup:
  1. clover.load_menu()
     └── GET /v3/merchants/{mId}/items?expand=categories%2CmodifierGroups&limit=1000
     └── Build in-memory dict: { clover_item_id → item data }
     └── Merge with menu.json: attach terms[], pronunciation{} by item name

Runtime (cache hit):
  Voice agent uses in-memory menu → zero latency

Refresh trigger (webhook event I/IC/IG/IM arrives):
  1. Receive webhook → validate X-Clover-Auth
  2. Background task: re-fetch full menu from Clover
  3. Merge with menu.json extras
  4. Atomic swap of in-memory cache

Fallback (no webhook / webhook missed):
  Scheduled poll every 5 min: GET items?filter=modifiedTime>={last_sync_ts}
  → only fetches changed items, updates cache entries
```

---

## Order Creation Flow

```
Customer confirms order over phone
  ↓
tools.py place_order() called with:
  - customer_name, phone_number
  - items: [{ name, quantity, price }]
  - order_type: "pickup" | "delivery" | "dine_in"
  - special_instructions

  ↓
clover.py create_order():
  1. Map item names → Clover item IDs (from cache)
  2. Map order_type → Clover order_type ID (fetched once at startup)
  3. POST /v3/merchants/{mId}/atomic_order/orders
     {
       "orderCart": {
         "lineItems": [
           {
             "item": { "id": "CLOVER_ITEM_ID" },
             "price": 1499,   ← in cents
             "note": "special instructions on first item"
           },
           ...
         ],
         "orderType": { "id": "CLOVER_ORDER_TYPE_ID" },
         "note": "Phone order — {customer_name} — {phone_number}"
       }
     }
  4. Response: { "id": "CLOVER_ORDER_ID", "total": 2997, ... }

  ↓
tools.py returns success with Clover order ID
  ↓
DynamicTTSProcessor fires OrderConfirmedMessage → frontend receipt card
```

---

## Payment Flow (Optional — Card-Not-Present)

For phone orders, payment can be:

**Option A — Pay in store (no API payment needed)**
Order is created in Clover, customer pays at pickup. No payment API calls required. This is the simplest path and what most restaurants do for phone orders.

**Option B — Take card over phone**
```
1. Collect 16-digit card number, expiry, CVV over phone (PCI risk — requires compliance)
2. POST https://token-sandbox.dev.clover.com/v1/tokens → clv_... token
3. POST https://scl-sandbox.dev.clover.com/v1/orders/{orderId}/pay
   { "source": "clv_...", "tip_amount": 0 }
4. Order paymentState → PAID automatically
```

**Recommendation: Option A** for the initial integration. Keep the order flow simple; payment at pickup. Add online payment later if needed.

---

## New Environment Variables

Add to `.env` and `docker-compose.yml`:

```env
# Clover POS
CLOVER_BASE_URL=https://apisandbox.dev.clover.com   # sandbox; production: https://api.clover.com
CLOVER_MERCHANT_ID=XXXXXXXXXXXXXXXXX                 # 13-char alphanumeric
CLOVER_ACCESS_TOKEN=                                 # Bearer token (from OAuth or sandbox test token)
CLOVER_WEBHOOK_SECRET=                               # X-Clover-Auth header value for verification
CLOVER_MENU_POLL_INTERVAL=300                        # seconds between fallback polls (default 5 min)
```

---

## New Files to Create

```
server/
  clover.py           ← Clover API client: menu cache, order creation, token management
  clover_types.py     ← Typed dataclasses for Clover item, order, line item

twilio/ (or new webhook service)
  main.py             ← add POST /clover-webhook handler
```

---

## Changes to Existing Files

| File | Change |
|---|---|
| `server/tools.py` | `place_order()` calls `clover.create_order()` instead of POSTing to n8n directly |
| `server/tools.py` | `get_menu()` reads from Clover cache instead of local MENU dict |
| `server/tools.py` | `check_item_availability()` looks up Clover item IDs |
| `server/main.py` | Call `await clover.init()` at startup before `serve()` |
| `server/main.py` | Export Clover client instance for tools to use |
| `menu.json` | Keep only: `terms[]`, `pronunciation{}`, `category_aliases`, `business` — remove prices/descriptions (Clover owns those) |
| `docker-compose.yml` | Add `CLOVER_*` env vars to voice-server and twilio-bridge services |
| `twilio/main.py` | Add `POST /clover-webhook` route |

---

## Data Model Mapping

### Clover Item → Voice Agent Menu Entry

```
Clover Item                    Voice Agent (merged)
───────────────────────────────────────────────────────
id (string)              →     clover_id  (used for order creation)
name (string)            →     name       (display + LLM)
price (int, cents)       →     price      ($/100 for display)
hidden (bool)            →     filtered out if true
categories[].name        →     category
modifierGroups[].name    →     modifier group labels
modifiers[].name + price →     modifier options
─── from menu.json (by name match) ───
terms[]                  →     used by frontend order parser + STT context
pronunciation{}          →     used by system prompt TTS guide
```

### Voice Agent Order Item → Clover Line Item

```
Voice Agent                    Clover Atomic Order lineItem
────────────────────────────────────────────────────────────
item name (string)       →     item: { id: clover_item_id }  (lookup by name)
quantity (int)           →     repeated N times in lineItems (Clover counts by line)
price (float, dollars)   →     price: int (cents = price * 100)
special_instructions     →     note on first line item
order_type string        →     orderType: { id: clover_order_type_id }
```

---

## Failure Modes and Fallbacks

| Failure | Fallback |
|---|---|
| Clover API unreachable at startup | Log error; fall back to loading `menu.json` fully (emergency static menu) |
| Order creation fails (Clover 5xx) | Return success to caller; POST to n8n webhook as backup notification |
| Item not found in Clover cache | Try `check_item_availability` live API call; log for manual review |
| Webhook delivery fails | Scheduled 5-min poll catches changes |
| Access token expired | Token refresh; retry once; fall back to static menu |

---

## Implementation Order

1. **`clover.py`** — write the client module (menu load, order create, token refresh)
2. **Update `tools.py`** — wire `place_order()` and menu tools to `clover.py`
3. **Update `main.py`** — init Clover client at startup
4. **Webhook endpoint** — add to twilio-bridge
5. **Update `docker-compose.yml`** — add env vars
6. **Trim `menu.json`** — remove prices/descriptions once Clover is source of truth
7. **Test end-to-end** on sandbox merchant before going live
