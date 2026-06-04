# Clover POS API Reference

Everything needed to implement the integration. All details sourced directly from Clover's official documentation.

---

## Environments & Base URLs

| Environment | API Base URL |
|---|---|
| **Sandbox** | `https://apisandbox.dev.clover.com` |
| **Production — North America** | `https://api.clover.com` |
| **Production — Europe** | `https://api.eu.clover.com` |
| **Production — Latin America** | `https://api.la.clover.com` |

All REST endpoints: `/v3/merchants/{mId}/{resource}`

Ecommerce endpoints (payment tokenization + pay-for-order):

| Purpose | Sandbox | Production |
|---|---|---|
| Tokenize card | `https://token-sandbox.dev.clover.com` | `https://token.clover.com` |
| Charge / pay order | `https://scl-sandbox.dev.clover.com` | `https://scl.clover.com` |
| Get ecomm API key | `https://scl-sandbox.dev.clover.com/pakms/apikey` | `https://scl.clover.com/pakms/apikey` |

OAuth endpoints:

| Purpose | Sandbox | Production (NA) |
|---|---|---|
| Authorize | `https://sandbox.dev.clover.com/oauth/v2/authorize` | `https://www.clover.com/oauth/v2/authorize` |
| Token exchange | `https://apisandbox.dev.clover.com/oauth/v2/token` | `https://api.clover.com/oauth/v2/token` |
| Refresh | `https://apisandbox.dev.clover.com/oauth/v2/refresh` | `https://api.clover.com/oauth/v2/refresh` |

---

## Authentication

### Key Concepts

| Term | Description |
|---|---|
| **App ID** | OAuth `client_id` |
| **App Secret** | OAuth `client_secret` |
| **Merchant ID (`mId`)** | 13-char alphanumeric; required in every endpoint path |
| **Access Token** | Short-lived Bearer token (expires in ~1 hour) |
| **Refresh Token** | Single-use; exchange for new access + refresh pair |

### Request Header (all API calls)

```
Authorization: Bearer {access_token}
User-Agent: ParkashSweetsVoiceAgent/1.0
```

### OAuth 2.0 Flow (for production apps)

```
Step 1 — Redirect merchant to Clover:
GET https://sandbox.dev.clover.com/oauth/v2/authorize
  ?client_id={APP_ID}
  &response_type=code
  &redirect_uri={YOUR_REDIRECT_URL}
  &state={CSRF_TOKEN}

Step 2 — Clover redirects back with auth code:
  https://yourapp.com/callback?code=AUTH_CODE&state=xyz

Step 3 — Exchange code for tokens (server-side only):
POST https://apisandbox.dev.clover.com/oauth/v2/token
Body: {
  "client_id": "APP_ID",
  "client_secret": "APP_SECRET",
  "code": "AUTH_CODE"
}
Response: {
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600
}

Step 4 — Refresh before expiry:
POST https://apisandbox.dev.clover.com/oauth/v2/refresh
Body: { "refresh_token": "..." }
Response: new access_token + refresh_token pair
```

**Critical:** Refresh token is **single-use**. The old one is immediately invalidated on use. Store the new pair before confirming the old one is gone.

### Sandbox Quick Token (dev/testing only)

1. Log in at `https://sandbox.dev.clover.com`
2. Go to test merchant → Settings → Business Operations → API Tokens → Create New Token
3. Select permission scopes (read inventory, read/write orders, read/write payments)
4. Use as `Authorization: Bearer {token}` on sandbox endpoints **only**

---

## Inventory (Menu) API

### Categories

```
GET  /v3/merchants/{mId}/categories
GET  /v3/merchants/{mId}/categories/{categoryId}
GET  /v3/merchants/{mId}/categories/{categoryId}/items
POST /v3/merchants/{mId}/categories
POST /v3/merchants/{mId}/category_items         ← associate item to category
POST /v3/merchants/{mId}/category_items?delete=true  ← disassociate
```

**Category object:**
```json
{
  "id": "ABC123",
  "name": "Appetizers",
  "colorCode": "#FF5733",
  "sortOrder": 1
}
```

**Associate item to category:**
```json
{
  "elements": [
    { "category": { "id": "CAT_ID" }, "item": { "id": "ITEM_ID" } }
  ]
}
```

---

### Items

```
GET  /v3/merchants/{mId}/items
GET  /v3/merchants/{mId}/items/{itemId}
POST /v3/merchants/{mId}/items
POST /v3/merchants/{mId}/items/{itemId}   ← update
```

**Query parameters:**

| Parameter | Example | Notes |
|---|---|---|
| `expand` | `categories%2CmodifierGroups` | Comma-separated (URL-encoded). Max 3 fields. |
| `filter` | `modifiedTime>=1700000000000` | Unix ms timestamp |
| `limit` | `1000` | Default 100, max 1000 |
| `offset` | `0` | Zero-based for pagination |

**Full menu fetch (use this for initial load):**
```
GET /v3/merchants/{mId}/items?expand=categories%2CmodifierGroups&limit=1000
```

**Delta sync (use this for polling):**
```
GET /v3/merchants/{mId}/items?filter=modifiedTime>={last_sync_unix_ms}&expand=categories%2CmodifierGroups
```

**Item object (key fields):**
```json
{
  "id": "CLOVER_ITEM_ID",
  "name": "Paneer Pakora",
  "price": 1150,
  "priceType": "FIXED",
  "hidden": false,
  "isRevenue": true,
  "isAgeRestricted": false,
  "defaultTaxRates": true,
  "modifiedTime": 1700000000000,
  "categories": {
    "elements": [
      { "id": "CAT_ID", "name": "Pakora" }
    ]
  },
  "modifierGroups": {
    "elements": [
      {
        "id": "MODGRP_ID",
        "name": "Spice Level",
        "minRequired": 0,
        "maxAllowed": 1,
        "modifiers": {
          "elements": [
            { "id": "MOD_ID", "name": "Extra Spicy", "price": 0 }
          ]
        }
      }
    ]
  }
}
```

**Important:**
- All prices are **integers in cents** (`1150` = $11.50)
- `hidden: true` → item not available; exclude from voice agent menu
- `isAgeRestricted: true` → do not offer via phone ordering
- `priceType` can be `FIXED`, `VARIABLE`, or `PER_UNIT`

---

### Modifier Groups & Modifiers

```
GET  /v3/merchants/{mId}/modifier_groups
GET  /v3/merchants/{mId}/modifier_groups/{modGroupId}
GET  /v3/merchants/{mId}/modifier_groups/{modGroupId}/modifiers
POST /v3/merchants/{mId}/modifier_groups
POST /v3/merchants/{mId}/modifier_groups/{modGroupId}/modifiers
POST /v3/merchants/{mId}/item_modifier_groups   ← associate modgrp to item
GET  /v3/merchants/{mId}/items/{itemId}?expand=modifierGroups
```

**Modifier group object:**
```json
{
  "id": "MODGRP_ID",
  "name": "Spice Level",
  "showByDefault": true,
  "minRequired": 0,
  "maxAllowed": 1
}
```

**Modifier object:**
```json
{
  "id": "MOD_ID",
  "name": "Extra Spicy",
  "price": 0,
  "modifierGroup": { "id": "MODGRP_ID" }
}
```

---

## Orders API

### Order Types

Fetch once at startup; cache the IDs mapped to fulfillment type.

```
GET  /v3/merchants/{mId}/order_types
POST /v3/merchants/{mId}/order_types
GET  /v3/merchants/{mId}/order_types/{orderTypeId}
```

**Order type object:**
```json
{
  "id": "ORDER_TYPE_ID",
  "label": "Takeout",
  "taxable": true,
  "isDefault": false,
  "filterCategories": false,
  "hoursAvailable": "ALL",
  "isHidden": false
}
```

`hoursAvailable`: `"ALL"`, `"BUSINESS_HOURS"`, or a custom hours object.

---

### Creating Orders — Atomic (Recommended)

Single API call. Totals calculated by Clover automatically. Use this.

```
POST /v3/merchants/{mId}/atomic_order/orders
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "orderCart": {
    "lineItems": [
      {
        "item": { "id": "CLOVER_ITEM_ID" },
        "price": 1150,
        "modifications": [
          {
            "modifier": { "id": "MOD_ID" },
            "name": "Extra Spicy",
            "amount": 0
          }
        ]
      },
      {
        "item": { "id": "CLOVER_ITEM_ID_2" },
        "price": 799,
        "quantity": 2
      }
    ],
    "discounts": [
      { "name": "Promo SAVE5", "amount": -500 }
    ],
    "orderType": { "id": "ORDER_TYPE_ID" },
    "note": "Phone order — Harpreet Singh — 9413752688"
  }
}
```

**Response (success 200):**
```json
{
  "id": "CLOVER_ORDER_ID",
  "currency": "usd",
  "total": 1449,
  "state": "open",
  "orderType": { "id": "ORDER_TYPE_ID", "label": "Takeout" },
  "lineItems": { "elements": [...] },
  "createdTime": 1700000000000
}
```

**Error responses (400):**
```json
{ "message": "item_does_not_exist", "details": "..." }
{ "message": "cart_is_empty_or_missing" }
{ "message": "invalid_modifier" }
```

**Preview before ordering (optional — calculates totals without creating):**
```
POST /v3/merchants/{mId}/atomic_order/checkouts
```
Same body format; returns total breakdown.

---

### Creating Orders — Custom (Multi-step, more flexible)

Use if you need price overrides or ad-hoc items not in inventory.

```
Step 1 — Create the order:
POST /v3/merchants/{mId}/orders
{
  "orderType": { "id": "ORDER_TYPE_ID" },
  "state": "open",
  "currency": "usd",
  "note": "Phone order — Harpreet Singh — 9413752688"
}
Response: { "id": "ORDER_ID", ... }

Step 2 — Add line items (ALWAYS use bulk — single-item endpoint has a bug):
POST /v3/merchants/{mId}/orders/{orderId}/bulk_line_items
{
  "items": [
    {
      "item": { "id": "CLOVER_ITEM_ID" },
      "name": "Paneer Pakora",
      "price": 1150
    }
  ]
}

Step 3 — Add modifier to a line item:
POST /v3/merchants/{mId}/orders/{orderId}/line_items/{lineItemId}/modifications
{
  "modifier": { "id": "MOD_ID" },
  "name": "Extra Spicy",
  "amount": 0
}

Step 4 — Add order-level discount:
POST /v3/merchants/{mId}/orders/{orderId}/discounts
{ "name": "Promo SAVE5", "amount": -500 }

Step 5 — Update total (REQUIRED in custom flow — not auto-calculated):
POST /v3/merchants/{mId}/orders/{orderId}
{ "total": 1449 }
```

---

### Order States

| State | Meaning |
|---|---|
| `null` | Draft — not visible in Orders app |
| `open` | Active — visible on POS devices. Always set this when creating via API. |
| `locked` | Being processed / payment in progress |
| `paid` | Payment completed |
| `deleted` | Soft-deleted |

**Always set `"state": "open"` when creating orders so the POS shows them.**

---

### Order Object — Key Fields

| Field | Type | Notes |
|---|---|---|
| `id` | string | Clover order ID |
| `currency` | string | e.g. `"usd"` |
| `total` | int64 | Cents; auto-calculated in atomic orders |
| `state` | string | `open`, `locked`, `paid` |
| `paymentState` | string | `OPEN`, `PAID`, `PARTIALLY_PAID`, `REFUNDED` |
| `orderType` | object | `{ "id": "..." }` |
| `note` | string | Free-text note — use for customer name + phone |
| `externalReferenceId` | string | Your own reference (e.g. `PS-142305`) |
| `lineItems` | array | Expandable — `?expand=lineItems` |
| `payments` | array | Expandable — `?expand=payments` |
| `discounts` | array | Order-level discounts |
| `createdTime` | int64 | Unix ms |

**Line item limit: 3,000 per order.**

---

### Retrieve Orders

```
GET /v3/merchants/{mId}/orders/{orderId}?expand=lineItems%2Cpayments

GET /v3/merchants/{mId}/orders
  ?filter=createdTime>=1700000000000
  &expand=lineItems
  &limit=100
  &offset=0
```

---

## Payments API

### Recommended Path: Ecommerce API (for phone/web orders)

The v2 Developer Pay API is **deprecated since October 2021**. Use the Ecommerce API.

#### Get Ecommerce API Key (one-time setup per merchant)
```
GET https://scl-sandbox.dev.clover.com/pakms/apikey
Authorization: Bearer {access_token}

Response: { "apiAccessKey": "ECOMM_API_KEY" }
```

#### Tokenize Card
```
POST https://token-sandbox.dev.clover.com/v1/tokens
apikey: {ECOMM_API_KEY}
Content-Type: application/json

{
  "card": {
    "number": "4111111111111111",
    "exp_month": "12",
    "exp_year": "2030",
    "cvv": "123",
    "brand": "VISA"
  }
}

Response: { "id": "clv_1TST...", "object": "token", "card": { "first6": "411111", "last4": "1111" } }
```
All tokens begin with `clv_`.

#### Pay for an Order (primary path)
```
POST https://scl-sandbox.dev.clover.com/v1/orders/{orderId}/pay
Authorization: Bearer {access_token}
x-forwarded-for: {customer_ip_address}
Content-Type: application/json

{
  "source": "clv_1TST...",
  "tip_amount": 0
}

Response: {
  "id": "CHARGE_ID",
  "amount_paid": 1449,
  "status": "paid"
}
```
Order `paymentState` automatically updates to `PAID`.

#### Record Cash Payment (no card)
```
POST /v3/merchants/{mId}/orders/{orderId}/payments
Authorization: Bearer {access_token}

{
  "amount": 1449,
  "tender": { "label_key": "com.clover.tender.cash" },
  "order": { "id": "ORDER_ID" }
}
```

**System tender label keys:**
- `com.clover.tender.cash`
- `com.clover.tender.check`

---

### Payment Object — Key Fields

| Field | Type | Notes |
|---|---|---|
| `id` | string | Payment ID |
| `amount` | int64 | Total charged in cents |
| `tipAmount` | int | Tip in cents |
| `taxAmount` | int | Tax in cents |
| `result` | string | `SUCCESS`, `DECLINE`, `VOIDED` |
| `tender` | object | Payment method |
| `order` | object | Associated order |
| `createdTime` | int64 | Unix ms |

---

## Webhooks

### Registration (one-time in Developer Dashboard)

1. Developer Dashboard → App → App Settings → Webhooks
2. Enter HTTPS callback URL (must have valid TLS cert; no localhost)
3. Click "Send Verification Code" → Clover POSTs `{"verificationCode":"..."}` to your endpoint
4. Copy code back → click Verify
5. Select event subscriptions → Save
6. App must be installed on the test merchant

### Security Verification

Every webhook request includes:
```
X-Clover-Auth: {unique-code-set-during-registration}
```
**Always validate this header.** Reject requests without it.

### Event Types (ones we care about)

| Key | Resource | Use |
|---|---|---|
| `I` | Inventory items | Item created/updated/deleted → invalidate menu cache |
| `IC` | Inventory categories | Category changed → invalidate menu cache |
| `IG` | Inventory modifier groups | Modifier group changed → invalidate menu cache |
| `IM` | Inventory modifiers | Modifier changed → invalidate menu cache |
| `O` | Orders | Order state changes → track order lifecycle |
| `P` | Payments | Payment created/updated → confirm payment |

### Payload Structure

```json
{
  "appId": "YOUR_APP_ID",
  "merchants": {
    "MERCHANT_ID": [
      {
        "objectId": "O:CLOVER_ORDER_ID",
        "type": "CREATE",
        "ts": 1537970958000
      },
      {
        "objectId": "I:CLOVER_ITEM_ID",
        "type": "UPDATE",
        "ts": 1537970959000
      }
    ]
  }
}
```

- `objectId` format: `{event_key}:{resource_id}` — e.g., `I:ABC123` for an item update
- `type`: `CREATE`, `UPDATE`, or `DELETE`
- `ts`: Unix ms timestamp
- One payload can contain multiple events for multiple merchants

### Webhook Handler Pattern

```python
@app.post("/clover-webhook")
async def clover_webhook(request: Request):
    # 1. Validate auth header immediately
    auth = request.headers.get("X-Clover-Auth", "")
    if auth != CLOVER_WEBHOOK_SECRET:
        raise HTTPException(status_code=401)

    # 2. Return 200 FAST — process async to avoid Clover timeout
    payload = await request.json()
    asyncio.create_task(handle_webhook_async(payload))
    return {"status": "ok"}

async def handle_webhook_async(payload: dict):
    inventory_events = {"I", "IC", "IG", "IM"}
    for merchant_id, events in payload.get("merchants", {}).items():
        for event in events:
            obj_type = event["objectId"].split(":")[0]
            if obj_type in inventory_events:
                await clover.reload_menu_cache()
                break   # one reload covers all inventory events in the batch
```

---

## Pagination & Filtering

### Parameters

| Parameter | Default | Max | Notes |
|---|---|---|---|
| `limit` | 100 | 1000 | Items per page |
| `offset` | 0 | — | Zero-based |

**Nested field pagination cap:** Even with `expand=lineItems`, nested arrays are capped at **100 items** regardless of `limit`. Cannot paginate nested fields — query them separately if needed.

### Filter Operators

`=`, `>`, `>=`, `<`, `<=`, `!=`

```
filter=modifiedTime>=1700000000000
filter=total>1000
filter=createdTime>=1700000000000&filter=createdTime<=1702679999000
```

**90-day window:** Time-based filters return at most 90 days of data per request.

### Expand

```
?expand=categories
?expand=lineItems.modifications
?expand=categories%2CmodifierGroups        ← multiple: URL-encode commas
```

Maximum **3 expand fields** per call.

---

## Rate Limits

| Limit | Threshold | Error |
|---|---|---|
| Per-token per-second | 16 req/s | HTTP 429 |
| Per-app per-second | 50 req/s | HTTP 429 |
| Per-token concurrent | 5 simultaneous | HTTP 429 |
| Per-app concurrent | 10 simultaneous | HTTP 429 |

**Response headers on 429:**

| Violation | Header |
|---|---|
| Per-app rate | `X-RateLimit-crossTokenLimit` |
| Per-token rate | `X-RateLimit-tokenLimit` |
| Per-app concurrent | `X-RateLimit-crossTokenConcurrentLimit` |
| Per-token concurrent | `X-RateLimit-tokenConcurrentLimit` |

Concurrent 429s include `retry-after: {seconds}`.

**Strategy for voice agent:** Cache menu in-memory; use atomic orders (1 call per order instead of 5+); poll on webhook miss only. Normal operation should stay well under 1 req/s.

---

## Sandbox Setup

1. Create developer account: `https://sandbox.dev.clover.com/developer-home/create-account`
2. Create a test merchant (prompted on signup) — **choose currency carefully, cannot change later**
3. Create app in Developer Dashboard → set redirect URI
4. Install app on test merchant via App Market
5. Generate test API token: merchant dashboard → Settings → API Tokens → Create New Token
6. Get Merchant ID from URL bar: `.../merchant/{mId}/...`
7. Load sample inventory via Inventory app in test merchant dashboard

**Test API call:**
```bash
curl https://apisandbox.dev.clover.com/v3/merchants/{mId}/items \
  -H "Authorization: Bearer {test_api_token}"
```

---

## Critical Gotchas

1. **Single line item POST bug** — `POST .../line_items` with multiple items only adds the last one. Always use `bulk_line_items`.

2. **Atomic order modifier silence** — if `modId` is missing, modifier fields are silently ignored (no error). Always verify modifier IDs exist in the cache before submitting.

3. **Total not auto-calculated in custom orders** — must manually POST the `total` field. Atomic orders handle this automatically.

4. **Always set `state: open`** — orders created with `null` state are invisible in the Orders app on POS devices.

5. **Tax rates must pre-exist** — cannot create them per-order. Reference existing IDs from the merchant's account.

6. **Clover Dining app incompatibility** — orders created via REST API never appear in the Clover Dining app. They show in the Orders app and Merchant Dashboard.

7. **Refresh token single-use** — consuming a refresh token immediately invalidates the old one. Persist the new pair before acknowledging.

8. **Nested expand 100-item cap** — even with `expand=lineItems`, you get at most 100. For large orders, fetch line items separately.

9. **90-day filter window** — time-filtered queries cap at 90 days. Page in chunks for history.

10. **`modifiedTime` not in category default response** — add `?expand=items` to get `modifiedTime` on categories.

11. **`hidden: true` items excluded from default list** — items the merchant has disabled won't appear in standard GET. Add `filter=hidden=false` or handle in your merge logic.

12. **Multi-location = multiple mIds** — each merchant location is a separate `mId`. No cross-location inventory sync endpoint exists.

---

## Endpoints Quick Reference

```
# Auth
POST {oauth_base}/oauth/v2/token
POST {oauth_base}/oauth/v2/refresh

# Inventory
GET  /v3/merchants/{mId}/categories
GET  /v3/merchants/{mId}/items?expand=categories%2CmodifierGroups&limit=1000
GET  /v3/merchants/{mId}/items?filter=modifiedTime>={ts}&expand=categories%2CmodifierGroups
GET  /v3/merchants/{mId}/modifier_groups
GET  /v3/merchants/{mId}/modifier_groups/{mgId}/modifiers

# Order types
GET  /v3/merchants/{mId}/order_types

# Orders — atomic (use this)
POST /v3/merchants/{mId}/atomic_order/orders
POST /v3/merchants/{mId}/atomic_order/checkouts

# Orders — custom (when needed)
POST /v3/merchants/{mId}/orders
POST /v3/merchants/{mId}/orders/{oId}/bulk_line_items
POST /v3/merchants/{mId}/orders/{oId}/line_items/{liId}/modifications
POST /v3/merchants/{mId}/orders/{oId}/discounts
POST /v3/merchants/{mId}/orders/{oId}               ← update state/total/note

# Retrieve orders
GET  /v3/merchants/{mId}/orders/{oId}?expand=lineItems%2Cpayments
GET  /v3/merchants/{mId}/orders?filter=createdTime>={ts}&expand=lineItems

# Payments — ecommerce flow
GET  {scl_base}/pakms/apikey
POST {token_base}/v1/tokens
POST {scl_base}/v1/orders/{oId}/pay

# Payments — record cash/alternate tender
POST /v3/merchants/{mId}/orders/{oId}/payments
GET  /v3/merchants/{mId}/orders/{oId}/payments

# Tax rates
GET  /v3/merchants/{mId}/tax_rates

# Customers
POST /v3/merchants/{mId}/customers
```
