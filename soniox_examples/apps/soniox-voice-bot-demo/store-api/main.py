"""
Parkash Sweets — Store API
Serves menu from Clover and creates orders. Used by the Browse Store tab.

Endpoints:
    GET  /menu              → categories + items + modifiers from Clover
    GET  /discounts         → active named discounts from Clover
    POST /orders            → create a Clover order from the cart (optional discount_code)
    GET  /orders/{id}       → fetch order status
    GET  /health            → liveness probe
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

log = structlog.get_logger()

# ── Clover config ─────────────────────────────────────────────────────────────

CLOVER_BASE_URL     = os.environ["CLOVER_BASE_URL"].rstrip("/")
CLOVER_MERCHANT_ID  = os.environ["CLOVER_MERCHANT_ID"]
CLOVER_ACCESS_TOKEN = os.environ["CLOVER_ACCESS_TOKEN"]
FRONTEND_URL        = os.environ.get("FRONTEND_URL", "https://voice.bizbull.ai").rstrip("/")

# Hosted Checkout needs a separate PAKMS ecom key, not the standard OAuth token.
# Can be set manually via CLOVER_ECOM_KEY; if omitted, fetched from /pakms/apikey on startup.
CLOVER_ECOM_KEY: str | None = os.environ.get("CLOVER_ECOM_KEY") or None

BASE              = f"{CLOVER_BASE_URL}/v3/merchants/{CLOVER_MERCHANT_ID}"
PAKMS_URL         = f"{CLOVER_BASE_URL}/pakms/apikey"
CHECKOUT_ENDPOINT = f"{CLOVER_BASE_URL}/invoicingcheckoutservice/v1/checkouts"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {CLOVER_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _ecom_headers() -> dict[str, str]:
    """Headers for the Hosted Checkout endpoint.
    Requires X-Clover-Merchant-Id per Clover docs — merchant is NOT in the request body.
    """
    key = CLOVER_ECOM_KEY or CLOVER_ACCESS_TOKEN
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Clover-Merchant-Id": CLOVER_MERCHANT_ID,
    }


# ── App ───────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_: FastAPI):
    global CLOVER_ECOM_KEY
    if not CLOVER_ECOM_KEY:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(PAKMS_URL, headers=_headers(), timeout=10.0)
            if resp.is_success:
                CLOVER_ECOM_KEY = resp.json().get("apiAccessKey")
                log.info("ecom key fetched from PAKMS", key_prefix=(CLOVER_ECOM_KEY or "")[:8] + "...")
            else:
                log.error(
                    "PAKMS key fetch failed — Hosted Checkout will NOT work. "
                    "Get the key from Clover dashboard and set CLOVER_ECOM_KEY in .env",
                    pakms_url=PAKMS_URL,
                    status=resp.status_code,
                    body=resp.text[:400],
                )
        except Exception as exc:
            log.error("PAKMS request failed", pakms_url=PAKMS_URL, error=str(exc))
    log.info("store-api started", merchant_id=CLOVER_MERCHANT_ID, base=CLOVER_BASE_URL)
    yield
    log.info("store-api stopped")


app = FastAPI(title="Parkash Sweets Store API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Clover helpers ────────────────────────────────────────────────────────────

async def _get(client: httpx.AsyncClient, path: str, **params: Any) -> Any:
    url = f"{BASE}/{path}"
    resp = await client.get(url, params=params, headers=_headers(), timeout=15.0)
    if resp.status_code == 401:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Clover auth error — check CLOVER_ACCESS_TOKEN")
    if resp.status_code == 404:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Clover resource not found: {path}")
    resp.raise_for_status()
    return resp.json()


async def _post(client: httpx.AsyncClient, path: str, body: dict) -> Any:
    url = f"{BASE}/{path}"
    resp = await client.post(url, json=body, headers=_headers(), timeout=15.0)
    if resp.status_code == 401:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Clover auth error")
    resp.raise_for_status()
    return resp.json()


# ── GET /menu ─────────────────────────────────────────────────────────────────

@app.get("/menu")
async def get_menu():
    """
    Returns the full menu from Clover.
    Handles pagination, filters hidden/deleted/variable-price items.
    Response: { categories: [...], items: [...] }
    """
    async with httpx.AsyncClient() as client:
        # Paginate through all items
        all_items: list[dict] = []
        offset = 0
        while True:
            data = await _get(
                client, "items",
                expand="categories,modifierGroups",
                limit=200,
                offset=offset,
            )
            elements: list[dict] = data.get("elements", [])
            all_items.extend(elements)
            if len(elements) < 200:
                break
            offset += 200

        # Fetch category list (for ordered display)
        cat_data = await _get(client, "categories", limit=200)
        raw_cats: list[dict] = cat_data.get("elements", [])

    # ── Categories ────────────────────────────────────────────────────────────
    categories = sorted(
        [
            {
                "id":         c["id"],
                "name":       c["name"],
                "sort_order": c.get("sortOrder", 0),
            }
            for c in raw_cats
        ],
        key=lambda c: c["sort_order"],
    )

    # ── Items ─────────────────────────────────────────────────────────────────
    items = []
    for raw in all_items:
        # Exclude hidden / deleted / non-fixed-price / age-restricted items
        if raw.get("hidden"):
            continue
        if raw.get("deletedTime", 0) > 0:
            continue
        if raw.get("priceType", "FIXED") != "FIXED":
            continue
        if raw.get("isAgeRestricted"):
            continue

        cats = raw.get("categories", {}).get("elements", [])
        cat  = cats[0] if cats else {}

        # Build modifier groups
        mg_list = []
        for mg in raw.get("modifierGroups", {}).get("elements", []):
            mods = [
                {
                    "id":    m["id"],
                    "name":  m["name"],
                    "price": m.get("price", 0),
                }
                for m in mg.get("modifiers", {}).get("elements", [])
                if not m.get("deleted")
            ]
            if mods:
                mg_list.append({
                    "id":           mg["id"],
                    "name":         mg["name"],
                    "min_required": mg.get("minRequired", 0),
                    "max_allowed":  mg.get("maxAllowed", 1),
                    "modifiers":    mods,
                })

        price = raw.get("price", 0)
        items.append({
            "id":              raw["id"],
            "name":            raw["name"],
            "description":     raw.get("description", ""),
            "price":           price,
            "price_display":   f"${price / 100:.2f}",
            "category_id":     cat.get("id", ""),
            "category_name":   cat.get("name", "Uncategorized"),
            "image_url":       None,
            "modifier_groups": mg_list,
            "available":       raw.get("available", True),
        })

    log.info("menu fetched", item_count=len(items), category_count=len(categories))
    return {"categories": categories, "items": items}


# ── GET /discounts ────────────────────────────────────────────────────────────

@app.get("/discounts")
async def get_discounts():
    """
    Returns active named discounts from Clover.
    Response: { discounts: [{ id, name }] }
    Only returns discounts that have a name (promo-code candidates).
    """
    async with httpx.AsyncClient() as client:
        data = await _get(client, "discounts", limit=200)

    discounts = [
        {"id": d["id"], "name": d.get("name", "").strip()}
        for d in data.get("elements", [])
        if d.get("name", "").strip()
    ]
    return {"discounts": discounts}


# ── POST /orders ──────────────────────────────────────────────────────────────

class OrderLineItem(BaseModel):
    item_id:      str
    name:         str
    price:        int                  # cents
    quantity:     int = Field(ge=1)
    modifier_ids: list[str] = []
    note:         str = ""


class PlaceOrderRequest(BaseModel):
    items:          list[OrderLineItem]
    order_type:     str = "pickup"     # pickup | dine_in | delivery
    customer_name:  str = ""
    customer_phone: str = ""
    note:           str = ""
    discount_code:  str | None = None  # promo code name (matched case-insensitively against Clover discount names)


@app.post("/orders", status_code=201)
async def create_order(req: PlaceOrderRequest):
    """
    Creates a Clover order from the cart.
    Returns { order_id, total, total_display, state }.
    """
    if not req.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    # Build order note
    parts = [f"Online Order — {req.order_type.replace('_', ' ').title()}"]
    if req.customer_name:
        parts.append(f"Name: {req.customer_name}")
    if req.customer_phone:
        parts.append(f"Phone: {req.customer_phone}")
    if req.note:
        parts.append(req.note)
    order_note = " | ".join(parts)

    subtotal_cents = sum(li.price * li.quantity for li in req.items)

    async with httpx.AsyncClient() as client:
        # 1. Validate discount code before creating order (fail fast)
        matched_discount: dict | None = None
        if req.discount_code:
            disc_data = await _get(client, "discounts", limit=200)
            matched_discount = next(
                (d for d in disc_data.get("elements", [])
                 if d.get("name", "").strip().upper() == req.discount_code.strip().upper()),
                None,
            )
            if not matched_discount:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Promo code '{req.discount_code}' is not valid.",
                )

        # 2. Create the parent order record
        order = await _post(client, "orders", {
            "state":    "open",
            "note":     order_note,
            "currency": "CAD",
        })
        order_id = order["id"]
        log.info("order created", order_id=order_id, customer=req.customer_name)

        # 3. Add one line item per unit (Clover has no quantity field on line items)
        for li in req.items:
            for _ in range(li.quantity):
                body: dict = {
                    "item":  {"id": li.item_id},
                    "price": li.price,
                }
                if li.note:
                    body["note"] = li.note

                created_li = await _post(client, f"orders/{order_id}/line_items", body)
                li_id = created_li["id"]

                # 4. Attach modifiers to each line item
                for mod_id in li.modifier_ids:
                    await _post(
                        client,
                        f"orders/{order_id}/line_items/{li_id}/modifications",
                        {"modifier": {"id": mod_id}},
                    )

        # 5. Apply discount if provided — Clover computes the exact amount server-side
        discount_amount = 0
        discount_name: str | None = None
        if matched_discount:
            await _post(
                client,
                f"orders/{order_id}/discounts",
                {"discount": {"id": matched_discount["id"]}},
            )
            # Fetch the updated order total so we return Clover's authoritative value
            updated_order = await _get(client, f"orders/{order_id}")
            clover_total = updated_order.get("total", subtotal_cents)
            discount_amount = max(0, subtotal_cents - clover_total)
            discount_name = matched_discount.get("name")
            log.info(
                "discount applied",
                order_id=order_id,
                code=discount_name,
                discount_cents=discount_amount,
            )

    final_total = subtotal_cents - discount_amount
    log.info("order complete", order_id=order_id, subtotal_cents=subtotal_cents, final_total=final_total)

    response: dict = {
        "order_id":      order_id,
        "total":         final_total,
        "total_display": f"${final_total / 100:.2f}",
        "state":         "open",
    }
    if discount_amount > 0:
        response["discount_amount"]  = discount_amount
        response["discount_display"] = f"-${discount_amount / 100:.2f}"
        response["discount_name"]    = discount_name
    return response


# ── POST /checkout ────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    items:          list[OrderLineItem]
    order_type:     str = "pickup"
    customer_name:  str = ""
    customer_phone: str = ""
    note:           str = ""
    discount_code:  str | None = None


@app.post("/checkout", status_code=201)
async def create_checkout(req: CheckoutRequest):
    """
    Creates a Clover Hosted Checkout session for card payment.
    Returns { checkout_url, session_id }.
    Frontend redirects the customer to checkout_url; Clover handles card entry.
    On success Clover redirects to FRONTEND_URL?payment=success.
    On cancel  Clover redirects to FRONTEND_URL?payment=cancelled.

    Test card (Clover sandbox): 4111 1111 1111 1111  exp: any future  cvv: any
    """
    if not req.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    # ── Discount lookup ───────────────────────────────────────────────────────
    discount_amount = 0
    discount_label: str | None = None
    if req.discount_code:
        async with httpx.AsyncClient() as client:
            disc_data = await _get(client, "discounts", limit=200)
        matched = next(
            (d for d in disc_data.get("elements", [])
             if d.get("name", "").strip().upper() == req.discount_code.strip().upper()),
            None,
        )
        if not matched:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Promo code '{req.discount_code}' is not valid.",
            )

        subtotal = sum(li.price * li.quantity for li in req.items)
        # Clover stores fixed-amount discounts as negative cents (e.g. -500 = $5 off)
        amt     = abs(matched.get("amount", 0))
        pct_raw = matched.get("percentage", 0)

        if amt > 0:
            discount_amount = min(amt, subtotal)
        elif pct_raw > 0:
            # Guard for both plain % (10) and basis-point (100000) formats
            actual_pct = pct_raw / 10000.0 if pct_raw > 100 else float(pct_raw)
            discount_amount = round(subtotal * actual_pct / 100)

        discount_label = matched.get("name")
        log.info("checkout discount resolved", code=discount_label, discount_cents=discount_amount)

    # ── Build Hosted Checkout line items ──────────────────────────────────────
    line_items: list[dict] = []
    for li in req.items:
        entry: dict = {
            "name":    li.name,
            "unitQty": li.quantity,
            "price":   li.price,   # unit price in cents
        }
        if li.note:
            entry["note"] = li.note
        line_items.append(entry)

    if discount_amount > 0:
        line_items.append({
            "name":    f"Discount: {discount_label}",
            "unitQty": 1,
            "price":   -discount_amount,
        })

    # ── Build order note ──────────────────────────────────────────────────────
    parts = [f"Online Order — {req.order_type.replace('_', ' ').title()}"]
    if req.customer_name:
        parts.append(f"Name: {req.customer_name}")
    if req.customer_phone:
        parts.append(f"Phone: {req.customer_phone}")
    if req.note:
        parts.append(req.note)

    # ── Call Clover Hosted Checkout API ───────────────────────────────────────
    # merchant is identified via X-Clover-Merchant-Id header, NOT in the body
    customer_parts = req.customer_name.split(" ", 1)
    payload = {
        "customer": {
            "firstName":   customer_parts[0] if customer_parts else "",
            "lastName":    customer_parts[1] if len(customer_parts) > 1 else "",
            "phoneNumber": req.customer_phone or "",
        },
        "shoppingCart": {
            "lineItems": line_items,
            "note":      " | ".join(parts),
        },
        "redirectUrls": {
            "success": f"{FRONTEND_URL}?payment=success",
            "failure": f"{FRONTEND_URL}?payment=cancelled",
        },
    }

    async with httpx.AsyncClient() as client:
        log.info("checkout request", endpoint=CHECKOUT_ENDPOINT, merchant=CLOVER_MERCHANT_ID,
                 ecom_key_prefix=(CLOVER_ECOM_KEY or "")[:8])
        resp = await client.post(
            CHECKOUT_ENDPOINT,
            json=payload,
            headers=_ecom_headers(),
            timeout=15.0,
        )
        log.info("checkout response", status=resp.status_code, body=resp.text[:500])
        if not resp.is_success:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                f"Clover checkout error {resp.status_code}: {resp.text[:300]}",
            )
        data = resp.json()

    session_id   = data.get("checkoutSessionId") or data.get("id", "")
    checkout_url = data.get("href", "")
    log.info("hosted checkout created", session_id=session_id, customer=req.customer_name)

    return {
        "checkout_url": checkout_url,
        "session_id":   session_id,
        "discount_amount": discount_amount,
        "discount_name":   discount_label,
    }


# ── GET /orders/{order_id} ────────────────────────────────────────────────────

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Fetch order state from Clover (for status polling)."""
    async with httpx.AsyncClient() as client:
        order = await _get(client, f"orders/{order_id}", expand="lineItems")

    return {
        "order_id":      order["id"],
        "state":         order.get("state", "open"),
        "payment_state": order.get("paymentState", "OPEN"),
        "total":         order.get("total", 0),
    }


# ── GET /health ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"ok": True, "merchant_id": CLOVER_MERCHANT_ID}
