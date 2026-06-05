# Clover POS Integration — Production Flow

Complete implementation plan for the Clover POS integration. Six phases covering startup, menu cache, webhooks, order creation, token management, and fallback. Follow build order at the bottom.

---

## Phase 1 — Startup

```
main.py boots
  │
  ├─ 1. Validate env vars
  │     CLOVER_BASE_URL, CLOVER_MERCHANT_ID, CLOVER_ACCESS_TOKEN,
  │     CLOVER_WEBHOOK_SECRET, CLOVER_MENU_POLL_INTERVAL
  │     → If any missing: log CRITICAL, raise at startup (fail fast)
  │
  ├─ 2. Initialize CloverClient
  │     → httpx.AsyncClient with:
  │          base_url = CLOVER_BASE_URL
  │          timeout  = Timeout(connect=5s, read=15s, write=10s)
  │          headers  = Authorization: Bearer {token}
  │                     User-Agent: ParkashSweetsVoiceAgent/1.0
  │
  ├─ 3. Fetch Order Types → cache as dict
  │     GET /v3/merchants/{mId}/order_types
  │     → Build: { "pickup": "ID1", "delivery": "ID2", "dine_in": "ID3" }
  │     → If fails: raise (can't take orders without knowing order types)
  │
  ├─ 4. Load Full Menu Cache
  │     GET /items?expand=categories%2CmodifierGroups&limit=1000&filter=hidden=false
  │     → Paginate if needed (follow href until no next page)
  │     → Merge with menu.json (terms, pronunciations)
  │     → Build 3 indexes (see Phase 2)
  │     → If fails: WARN + load static menu.json as emergency fallback
  │
  ├─ 5. Start Background Poll Task (asyncio.create_task)
  │     → Every CLOVER_MENU_POLL_INTERVAL seconds (default 300)
  │     → Delta sync: only items changed since last_sync_ts
  │
  └─ 6. Ready → start WebSocket server
```

---

## Phase 2 — Menu Cache

Three indexes built from Clover data:

```
MenuCache
├── by_id:       { "CLOVER_ID"     → CloverItem }   ← for order creation
├── by_name:     { "paneer pakora" → "CLOVER_ID" }   ← for name lookup
│                { "paneer"        → "CLOVER_ID" }   ← partial terms too
│                { "pakora"        → "CLOVER_ID" }
└── by_category: { "Pakora"        → [CloverItem] }  ← for get_menu(category)
```

Plus from `menu.json` (voice-agent extras Clover doesn't know):
```
extras:          { "paneer pakora" → { terms[], pronunciation{} } }
```

### Full Load (startup + webhook trigger)

```
GET /items?expand=categories%2CmodifierGroups&limit=1000&filter=hidden=false
  │
  ├─ Paginate: follow href until exhausted
  ├─ For each item:
  │    hidden=true          → skip (unavailable)
  │    priceType != FIXED   → skip (can't price over phone)
  │    isAgeRestricted=true → skip (no phone sales)
  │    else                 → add to all 3 indexes
  │
  ├─ Merge with menu.json extras (by normalized name match)
  ├─ Record last_sync_ts = now()
  └─ Atomic swap: replace old cache object in one assignment
```

### Delta Sync (every 5 min background poll)

```
GET /items?filter=modifiedTime>={last_sync_ts}&expand=categories%2CmodifierGroups
  │
  ├─ For each changed item:
  │    hidden=true → REMOVE from all 3 indexes
  │    else        → UPDATE entry in all 3 indexes
  │
  └─ Update last_sync_ts = now()
```

---

## Phase 3 — Webhook

```
Clover → POST /clover-webhook (on twilio/main.py)
  │
  ├─ 1. IMMEDIATELY validate X-Clover-Auth header
  │      → constant-time compare (hmac.compare_digest)
  │      → 401 if wrong
  │
  ├─ 2. Return 200 FAST (before any processing)
  │      → Clover times out if you take too long
  │      → asyncio.create_task(process_webhook(payload))
  │
  └─ process_webhook(payload):
       Parse merchants → events
       │
       ├─ Inventory event (I, IC, IG, IM):
       │    → Cancel existing reload task if already running
       │    → Schedule full menu reload
       │    → Debounce: if multiple inventory events arrive in 2s, do ONE reload
       │
       └─ Order event (O):
            → Log order state change (optional tracking)
```

### Webhook event type prefixes

| Prefix | Resource | Action |
|---|---|---|
| `I` | Inventory item | Reload menu cache |
| `IC` | Inventory category | Reload menu cache |
| `IG` | Inventory modifier group | Reload menu cache |
| `IM` | Inventory modifier | Reload menu cache |
| `O` | Order | Log state change |
| `P` | Payment | Log (optional) |

Parse with: `obj_type = event["objectId"].split(":")[0]`

---

## Phase 4 — Order Creation

```
tools.py place_order() called by LLM
  │
  ├─ STEP 1: Resolve items
  │    For each item in the order:
  │    │
  │    ├─ Normalize name: lowercase, strip punctuation
  │    ├─ Exact lookup in by_name index
  │    ├─ If miss → fuzzy match with rapidfuzz (threshold 80)
  │    ├─ If miss → try ITEM_ALIASES from menu.json
  │    ├─ If miss → live API call: GET /items?filter=name={name} (last resort)
  │    └─ If still miss → ItemNotFoundError
  │         → LLM told: "I couldn't find {item} in our system"
  │         → Don't abort whole order, collect which items failed
  │
  ├─ STEP 2: Resolve order type
  │    "pickup"   → order_type_ids["pickup"]
  │    "delivery" → order_type_ids["delivery"]
  │    "dine_in"  → order_type_ids["dine_in"]
  │    fallback   → order_type_ids["pickup"]
  │
  ├─ STEP 3: Build request body
  │    lineItems:
  │      for each item × quantity → repeat N identical line items
  │      special_instructions    → note on first line item
  │    note: "Phone order — {name} — {phone}"
  │    orderType: { id: "..." }
  │
  ├─ STEP 4: POST to Clover (with retry logic)
  │    │
  │    ├─ Attempt 1
  │    │    Response 200  → success → return Clover order ID
  │    │    Response 400  → bad data → NO retry → surface error to LLM
  │    │    Response 401  → token expired → refresh token → retry once
  │    │    Response 429  → rate limited → wait retry-after → retry
  │    │    Response 5xx  → server error → wait 1s → retry
  │    │    Timeout       → wait 2s → retry
  │    │
  │    ├─ Attempt 2 (after 1s backoff)
  │    │
  │    ├─ Attempt 3 (after 2s backoff)
  │    │
  │    └─ All attempts exhausted:
  │         → FALLBACK: generate local order ID (PS-HHMMSS)
  │         → POST to n8n webhook as backup notification
  │         → Log ERROR with full context
  │         → Return local order ID so customer still gets confirmation
  │
  └─ STEP 5: Post-success
       → Also POST to n8n (optional secondary notification, non-blocking)
       → Log order created with Clover ID + items + total
```

### Retry strategy

| Error | Retry? | Wait | Max attempts |
|---|---|---|---|
| 400 Bad Request | No | — | 1 |
| 401 Unauthorized | Yes (refresh first) | 0s | 2 |
| 429 Rate Limited | Yes | retry-after header | 3 |
| 5xx Server Error | Yes | exponential (1s, 2s) | 3 |
| Timeout | Yes | 2s | 3 |

---

## Phase 5 — Token Management

```
Token lifecycle (access token expires ~1 hour):

  CloverClient.__init__
    → store token, record token_acquired_at = now()

  Before every API call:
    → if now() > token_acquired_at + 55min:   ← 5 min safety buffer
         refresh_token()

  refresh_token():
    → POST /oauth/v2/refresh { "refresh_token": "..." }
    → Store new access_token + refresh_token ATOMICALLY
         (write both before acknowledging old ones gone)
    → Update token_acquired_at = now()
    → If refresh fails:
         → log CRITICAL
         → set degraded_mode = True
         → continue with old token until it actually 401s
         → on 401 → retry refresh once more → if fails → fallback mode
```

**Note on sandbox dev tokens:** Sandbox tokens do not expire. Token refresh logic is wired for production correctness but won't trigger in sandbox. Set `CLOVER_REFRESH_TOKEN` to empty string in sandbox `.env` to skip.

---

## Phase 6 — Fallback

```
Clover unreachable at startup:
  → WARN "Clover unavailable — using static menu"
  → Load menu.json fully (prices + descriptions + items)
  → Set clover_available = False
  → Background task: retry Clover connection every 60s
  → When Clover comes back: hot-swap cache, set clover_available = True

Order creation fails after all retries:
  → Generate local order ID (PS-HHMMSS)
  → POST full order to n8n webhook (with all details)
  → Log ERROR so owner can manually enter into POS
  → Customer still gets confirmation

Menu item not found in Clover:
  → Try live API call as last resort
  → If still not found:
       Log WARNING with item name (for manual review)
       Return item with price from menu.json (static fallback price)
```

---

## File Structure

```
server/
  clover.py            ← CloverClient, MenuCache, order creation, exceptions
  clover_types.py      ← CloverItem, CloverOrder, CloverOrderType dataclasses

twilio/
  main.py              ← add POST /clover-webhook route
```

### `clover.py` internal structure

```
Exceptions:
  CloverError (base)
  ├── CloverAuthError
  ├── CloverRateLimitError
  ├── CloverItemNotFoundError
  └── CloverOrderError

MenuCache:
  ├── load()           ← full fetch + paginate + merge with menu.json extras
  ├── delta_sync()     ← fetch only changed items
  ├── lookup(name)     ← exact → fuzzy → alias → live API chain
  └── get_category()   ← for get_menu() tool

CloverClient:
  ├── __init__()       ← httpx client, token state
  ├── init()           ← startup: order types + menu load + poll task
  ├── _request()       ← core: retry + 401 refresh + 429 wait + backoff
  ├── refresh_token()
  ├── create_order()   ← builds body + calls _request + fallback
  └── reload_menu()    ← triggered by webhook
```

---

## Integration Points in Existing Files

| File | Change |
|---|---|
| `server/main.py` | `clover = CloverClient(); await clover.init()` before `serve()` |
| `server/tools.py` | `place_order()` → `clover.create_order()` |
| `server/tools.py` | `get_menu()` → `clover.menu.get_category()` |
| `server/tools.py` | `check_item_availability()` → `clover.menu.lookup()` |
| `twilio/main.py` | Add `POST /clover-webhook` route |
| `docker-compose.yml` | Add `CLOVER_*` env vars to both services |
| `menu.json` | Keep only: `terms[]`, `pronunciation{}`, `category_aliases`, `business` |

---

## New Environment Variables

```env
# server/.env and docker-compose.yml
CLOVER_BASE_URL=https://apisandbox.dev.clover.com   # sandbox; prod: https://api.clover.com
CLOVER_MERCHANT_ID=                                  # 13-char alphanumeric from URL bar
CLOVER_ACCESS_TOKEN=                                 # Bearer token
CLOVER_REFRESH_TOKEN=                                # leave empty for sandbox dev tokens
CLOVER_WEBHOOK_SECRET=                               # X-Clover-Auth header value
CLOVER_MENU_POLL_INTERVAL=300                        # seconds between fallback polls
```

---

## Build Order

| Step | Task | File |
|---|---|---|
| 1 | Data shapes — no dependencies | `server/clover_types.py` |
| 2 | Exception hierarchy | `server/clover.py` |
| 3 | MenuCache class | `server/clover.py` |
| 4 | CloverClient (HTTP + auth + retry) | `server/clover.py` |
| 5 | `create_order()` | `server/clover.py` |
| 6 | Init wiring | `server/main.py` |
| 7 | Tool wiring | `server/tools.py` |
| 8 | Webhook endpoint | `twilio/main.py` |
| 9 | Env vars | `docker-compose.yml` |
| 10 | Trim static data | `menu.json` |
