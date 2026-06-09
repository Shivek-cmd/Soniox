# Store — Pending Production Items

Tracked from the gap analysis against Clover's full Orders API.
Check off items as they are completed.

---

## P0 — Critical (data integrity / breaks at scale)

- [ ] **1. Switch to Atomic Order API**
  - Current `POST /orders` is multi-step (create order → loop line items → modifiers → discount). If it dies mid-way, Clover has a partial order on the POS with no cleanup.
  - Fix: replace with `POST /v3/merchants/{mId}/atomic_order/orders` — single call, all-or-nothing.
  - File: `store-api/main.py`

- [ ] **2. Menu cache with TTL**
  - Every `GET /menu` hits Clover multiple times. At 20 concurrent users, Clover's 16 req/s per-token limit will trigger 429s.
  - Fix: in-memory cache on the store-api with a 2-minute TTL. Re-fetch in background on expiry.
  - File: `store-api/main.py`

- [ ] **3. Lock CORS to production domain**
  - Currently `allow_origins=["*"]` — any website can make requests on behalf of users.
  - Fix: set `allow_origins=["https://voice.bizbull.ai"]` (or read from env var).
  - File: `store-api/main.py`

- [ ] **4. Input validation + rate limiting**
  - `customer_name`, `customer_phone`, `note` have no max length.
  - `item_id` and `modifier_id` are never verified against Clover inventory before order creation.
  - No rate limit — anyone can spam `POST /checkout` creating unlimited Clover sessions.
  - Fix: add Pydantic field length constraints; validate item IDs against menu cache; add per-IP rate limiting (e.g. `slowapi`).
  - File: `store-api/main.py`

---

## P1 — High (significant UX / business gaps)

- [ ] **5. Persist cart to localStorage**
  - Cart lives only in `useReducer` state — a page refresh wipes everything.
  - Fix: sync cart state to `localStorage` on every dispatch; rehydrate on mount.
  - File: `Store.tsx`

- [ ] **6. Per-item note input in ItemModal**
  - `OrderLineItem.note` exists in the backend model but the `ItemModal` has no note field.
  - Customers cannot say "extra spicy on this item" — only a global order note is available.
  - Fix: add a text input in `ItemModal`; pass note through to cart entry and checkout payload.
  - Files: `Store.tsx`

- [ ] **7. Fetch real tax rates from Clover**
  - GST is hardcoded at 5% in the frontend. Clover has `GET /v3/merchants/{mId}/tax_rates`.
  - Fix: expose a `GET /tax-rates` endpoint in store-api; frontend fetches it on load and uses it for display.
  - Files: `store-api/main.py`, `Store.tsx`

- [ ] **8. Poll order status after payment success**
  - After `?payment=success` redirect, we show the success overlay without confirming with Clover that the order is actually `PAID`.
  - Fix: after redirect, call `GET /orders/{session_id}` and poll until `paymentState === "PAID"` before showing success screen.
  - File: `Store.tsx`

- [ ] **9. Add delivery option with address capture**
  - "delivery" exists in `PlaceOrderRequest.order_type` but the checkout modal only shows pickup / dine-in.
  - Fix: add a "Delivery" button in the order type selector; show an address field when selected; pass address in order note.
  - Files: `Store.tsx`, `store-api/main.py`

- [ ] **10. Re-validate item availability at checkout time**
  - Menu loads once on page open. If an item sells out while the user is browsing, there's no check at checkout.
  - Fix: in `POST /checkout` and `POST /orders`, verify each `item_id` against Clover inventory (or the menu cache) before creating the order.
  - File: `store-api/main.py`

---

## P2 — Medium (missing features)

- [ ] **11. Service charge support**
  - Clover supports `POST /orders/{id}/service_charge` with `name`, `percentage`, `isAutoApplied`.
  - Common use cases: delivery fee ($3.99), packaging charge ($1.50).
  - Fix: add a `GET /service-charges` endpoint; apply configured charges to orders; show in checkout summary.
  - Files: `store-api/main.py`, `Store.tsx`

- [ ] **12. Line-item level discounts**
  - All current discounts are order-level. Clover supports `POST /orders/{id}/line_items/{lineItemId}/discounts`.
  - Needed for item-specific deals (e.g. "buy 2 samosas, get $1 off each").
  - Fix: extend discount model to include `item_id` scope; apply as line-item discount when scope is set.
  - Files: `store-api/main.py`, `Store.tsx`

- [ ] **13. Atomic checkout preview before payment**
  - `POST /v3/merchants/{mId}/atomic_order/checkouts` calculates Clover's authoritative total without creating an order.
  - Fix: call this endpoint in the checkout modal to show exact total (with real taxes + discounts) before redirecting to payment.
  - Files: `store-api/main.py`, `Store.tsx`

- [ ] **14. Order cancel / void flow**
  - No way for customers or staff to cancel an open order from the UI.
  - Clover has `DELETE /orders/{id}` and void line item endpoints.
  - Fix: add a `DELETE /orders/{id}` endpoint in store-api; add a "Cancel Order" option on the success screen or an admin panel.
  - Files: `store-api/main.py`, `Store.tsx`

- [ ] **15. DECREMENT at qty=1 should remove the item**
  - Pressing `−` at quantity 1 calls `Math.max(1, 0)` = stays at 1. Item can only be removed via `✕`.
  - Standard UX: hitting `−` at 1 should remove the cart entry.
  - Fix: in `cartReducer`, if `DECREMENT` brings quantity to 0, filter out the entry (same as `REMOVE`).
  - File: `Store.tsx`

- [ ] **16. Use item images from Clover instead of hardcoded name-match map**
  - `getItemImage()` matches names against a hardcoded Unsplash map. New Clover items with unusual names fall back to emoji.
  - Clover items support images via their API (`imageUrl` field on items).
  - Fix: include `imageUrl` from Clover in the menu response; only fall back to the name-match map when it's null.
  - File: `store-api/main.py` (already returns `image_url: None` — just populate it from Clover data)

- [ ] **17. Remove hardcoded "15–25 min" wait time**
  - Success overlay shows a fixed wait time regardless of order type or time of day.
  - Fix: remove it, or drive it from a configurable env var (`WAIT_TIME_DISPLAY`) defaulting to empty.
  - File: `Store.tsx`

---

## P3 — Nice to Have

- [ ] **18. Email / SMS confirmation after checkout**
  - No notification sent to customer after payment. n8n webhook is already wired for voice orders.
  - Fix: after successful Hosted Checkout return (or after `POST /orders`), POST to `N8N_WEBHOOK_URL` with order details.
  - File: `store-api/main.py`

- [ ] **19. Tip selector before payment**
  - Clover's payment API supports `tip_amount`. No tip UI exists.
  - Fix: add 15% / 18% / 20% / custom tip buttons in the checkout modal; factor tip into the Hosted Checkout total.
  - File: `Store.tsx`

- [ ] **20. Order history / lookup by phone**
  - Customers can't look up past orders.
  - Clover has `GET /orders?filter=createdTime>=...` that could power a phone-based lookup.
  - Fix: add `GET /orders?phone={phone}` endpoint; add a simple "Your Orders" tab or section.
  - Files: `store-api/main.py`, `Store.tsx`

---

## Done

_(move items here as they are completed)_
