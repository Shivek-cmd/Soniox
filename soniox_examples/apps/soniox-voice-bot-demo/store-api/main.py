"""
Parkash Sweets — Store API
Serves menu and creates orders. Supports Clover (default) and Square via ?pos= query param.

Endpoints:
    GET  /menu              → categories + items + modifiers
    GET  /discounts         → active named discounts
    POST /orders            → create an order from the cart (optional discount_code)
    POST /checkout          → create a hosted checkout session for card payment
    GET  /orders/{id}       → fetch order status
    GET  /health            → liveness probe
"""
from __future__ import annotations

import os
import uuid as _uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

log = structlog.get_logger()

# ── Clover config ─────────────────────────────────────────────────────────────

CLOVER_BASE_URL     = os.environ["CLOVER_BASE_URL"].rstrip("/")
CLOVER_MERCHANT_ID  = os.environ["CLOVER_MERCHANT_ID"]
CLOVER_ACCESS_TOKEN = os.environ["CLOVER_ACCESS_TOKEN"]
FRONTEND_URL        = os.environ.get("FRONTEND_URL", "https://voice.bizbull.ai").rstrip("/")

# Hosted Checkout needs a separate PAKMS ecom key, not the standard OAuth token.
CLOVER_ECOM_KEY: str | None = os.environ.get("CLOVER_ECOM_KEY") or None

BASE              = f"{CLOVER_BASE_URL}/v3/merchants/{CLOVER_MERCHANT_ID}"
PAKMS_URL         = f"{CLOVER_BASE_URL}/pakms/apikey"
CHECKOUT_ENDPOINT = f"{CLOVER_BASE_URL}/invoicingcheckoutservice/v1/checkouts"


def _clover_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {CLOVER_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }


def _ecom_headers() -> dict[str, str]:
    key = CLOVER_ECOM_KEY or CLOVER_ACCESS_TOKEN
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Clover-Merchant-Id": CLOVER_MERCHANT_ID,
    }


# ── Square config ─────────────────────────────────────────────────────────────

SQUARE_BASE_URL     = os.environ.get("SQUARE_BASE_URL", "https://connect.squareupsandbox.com").rstrip("/")
SQUARE_ACCESS_TOKEN = os.environ.get("SQUARE_ACCESS_TOKEN", "")
SQUARE_LOCATION_ID  = os.environ.get("SQUARE_LOCATION_ID", "")
SQUARE_API_VERSION  = "2024-01-17"


def _square_headers() -> dict[str, str]:
    return {
        "Authorization":  f"Bearer {SQUARE_ACCESS_TOKEN}",
        "Content-Type":   "application/json",
        "Square-Version": SQUARE_API_VERSION,
    }


# ── App ───────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_: FastAPI):
    global CLOVER_ECOM_KEY
    if not CLOVER_ECOM_KEY:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(PAKMS_URL, headers=_clover_headers(), timeout=10.0)
            if resp.is_success:
                CLOVER_ECOM_KEY = resp.json().get("apiAccessKey")
                log.info("ecom key fetched from PAKMS", key_prefix=(CLOVER_ECOM_KEY or "")[:8] + "...")
            else:
                log.error(
                    "PAKMS key fetch failed — Hosted Checkout will NOT work. "
                    "Get the key from Clover dashboard and set CLOVER_ECOM_KEY in .env",
                    pakms_url=PAKMS_URL, status=resp.status_code, body=resp.text[:400],
                )
        except Exception as exc:
            log.error("PAKMS request failed", pakms_url=PAKMS_URL, error=str(exc))
    log.info("store-api started", merchant_id=CLOVER_MERCHANT_ID, square_configured=bool(SQUARE_ACCESS_TOKEN))
    yield
    log.info("store-api stopped")


app = FastAPI(title="Parkash Sweets Store API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Clover helpers ────────────────────────────────────────────────────────────

async def _clover_get(client: httpx.AsyncClient, path: str, **params: Any) -> Any:
    url = f"{BASE}/{path}"
    resp = await client.get(url, params=params, headers=_clover_headers(), timeout=15.0)
    if resp.status_code == 401:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Clover auth error — check CLOVER_ACCESS_TOKEN")
    if resp.status_code == 404:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Clover resource not found: {path}")
    resp.raise_for_status()
    return resp.json()


async def _clover_post(client: httpx.AsyncClient, path: str, body: dict) -> Any:
    url = f"{BASE}/{path}"
    resp = await client.post(url, json=body, headers=_clover_headers(), timeout=15.0)
    if resp.status_code == 401:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Clover auth error")
    resp.raise_for_status()
    return resp.json()


# ── Square helpers ────────────────────────────────────────────────────────────

async def _sq_list_catalog(types: str = "ITEM,CATEGORY,MODIFIER_LIST,DISCOUNT") -> list[dict]:
    """Fetch all catalog objects, handling cursor pagination."""
    if not SQUARE_ACCESS_TOKEN:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Square not configured — set SQUARE_ACCESS_TOKEN")

    objects: list[dict] = []
    cursor: str | None = None
    async with httpx.AsyncClient() as client:
        while True:
            params: dict[str, Any] = {"types": types}
            if cursor:
                params["cursor"] = cursor
            resp = await client.get(
                f"{SQUARE_BASE_URL}/v2/catalog/list",
                params=params,
                headers=_square_headers(),
                timeout=15.0,
            )
            if resp.status_code == 401:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Square auth error — check SQUARE_ACCESS_TOKEN")
            resp.raise_for_status()
            data = resp.json()
            objects.extend(data.get("objects", []))
            cursor = data.get("cursor")
            if not cursor:
                break
    return objects


def _sq_build_menu(objects: list[dict]) -> dict:
    categories: dict[str, str] = {}
    modifier_lists: dict[str, dict] = {}

    for obj in objects:
        if obj["type"] == "CATEGORY":
            categories[obj["id"]] = obj.get("category_data", {}).get("name", "Uncategorized")
        elif obj["type"] == "MODIFIER_LIST":
            modifier_lists[obj["id"]] = obj

    items: list[dict] = []
    for obj in objects:
        if obj["type"] != "ITEM":
            continue
        item_data = obj.get("item_data", {})
        if item_data.get("is_deleted"):
            continue

        variation_id: str | None = None
        price: int | None = None
        for var in item_data.get("variations", []):
            vd = var.get("item_variation_data", {})
            if vd.get("pricing_type", "FIXED_PRICING") != "FIXED_PRICING":
                continue
            pm = vd.get("price_money")
            if pm and pm.get("amount", 0) > 0:
                variation_id = var["id"]
                price = pm["amount"]
                break

        if price is None or variation_id is None:
            continue

        cat_id   = item_data.get("category_id", "")
        cat_name = categories.get(cat_id, "Uncategorized")

        mg_list: list[dict] = []
        for ml_info in item_data.get("modifier_list_info", []):
            if not ml_info.get("enabled", True):
                continue
            ml_id = ml_info["modifier_list_id"]
            ml    = modifier_lists.get(ml_id)
            if not ml:
                continue
            ml_data     = ml.get("modifier_list_data", {})
            sel         = ml_data.get("selection_type", "SINGLE")
            min_req     = ml_info.get("min_selected_modifiers", 0)
            max_allowed = ml_info.get("max_selected_modifiers", 1 if sel == "SINGLE" else -1)

            mods: list[dict] = []
            for mod in ml_data.get("modifiers", []):
                if mod.get("is_deleted"):
                    continue
                md = mod.get("modifier_data", {})
                mods.append({
                    "id":    mod["id"],
                    "name":  md.get("name", ""),
                    "price": md.get("price_money", {}).get("amount", 0),
                })
            if mods:
                mg_list.append({
                    "id":           ml_id,
                    "name":         ml_data.get("name", ""),
                    "min_required": max(0, min_req),
                    "max_allowed":  max_allowed if max_allowed > 0 else len(mods),
                    "modifiers":    mods,
                })

        items.append({
            "id":              variation_id,   # frontend sends this back as item_id in orders
            "name":            item_data.get("name", ""),
            "description":     item_data.get("description_html") or item_data.get("description", ""),
            "price":           price,
            "price_display":   f"${price / 100:.2f}",
            "category_id":     cat_id,
            "category_name":   cat_name,
            "image_url":       None,
            "modifier_groups": mg_list,
            "available":       True,
        })

    cat_list = [{"id": k, "name": v, "sort_order": 0} for k, v in categories.items()]
    return {"categories": cat_list, "items": items}


def _sq_build_discounts(objects: list[dict]) -> list[dict]:
    discounts: list[dict] = []
    for obj in objects:
        if obj["type"] != "DISCOUNT":
            continue
        d    = obj.get("discount_data", {})
        name = d.get("name", "").strip()
        if not name:
            continue
        entry: dict = {"id": obj["id"], "name": name}
        dtype = d.get("discount_type", "")
        if dtype == "FIXED_AMOUNT":
            entry["amount"] = d.get("amount_money", {}).get("amount", 0)
        elif dtype == "FIXED_PERCENTAGE":
            entry["percentage"] = float(d.get("percentage", "0"))
        discounts.append(entry)
    return discounts


def _sq_resolve_discount(discounts: list[dict], code: str, subtotal: int) -> tuple[int, str]:
    matched = next(
        (d for d in discounts if d["name"].upper() == code.strip().upper()),
        None,
    )
    if not matched:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Promo code '{code}' is not valid.",
        )
    amt = 0
    if matched.get("amount"):
        amt = min(int(matched["amount"]), subtotal)
    elif matched.get("percentage"):
        amt = round(subtotal * float(matched["percentage"]) / 100)
    return amt, matched["name"]


def _sq_build_line_items(items: list) -> list[dict]:
    line_items = []
    for li in items:
        entry: dict = {
            "name":             li.name,
            "quantity":         str(li.quantity),
            "base_price_money": {"amount": li.price, "currency": "CAD"},
        }
        if li.item_id:
            entry["catalog_object_id"] = li.item_id
        if li.modifier_ids:
            entry["modifiers"] = [{"catalog_object_id": mid} for mid in li.modifier_ids]
        if li.note:
            entry["note"] = li.note
        line_items.append(entry)
    return line_items


def _sq_order_note(order_type: str, name: str, phone: str, note: str,
                   discount_label: str | None = None, discount_amt: int = 0) -> str:
    parts = [f"Online Order — {order_type.replace('_', ' ').title()}"]
    if name:  parts.append(f"Name: {name}")
    if phone: parts.append(f"Phone: {phone}")
    if note:  parts.append(note)
    if discount_label and discount_amt > 0:
        parts.append(f"Promo: {discount_label} (-${discount_amt / 100:.2f})")
    return " | ".join(parts)


# ── Pydantic models ───────────────────────────────────────────────────────────

class OrderLineItem(BaseModel):
    item_id:      str
    name:         str
    price:        int                  # cents
    quantity:     int = Field(ge=1)
    modifier_ids: list[str] = []
    note:         str = ""


class PlaceOrderRequest(BaseModel):
    items:          list[OrderLineItem]
    order_type:     str = "pickup"
    customer_name:  str = ""
    customer_phone: str = ""
    note:           str = ""
    discount_code:  str | None = None


class CheckoutRequest(BaseModel):
    items:          list[OrderLineItem]
    order_type:     str = "pickup"
    customer_name:  str = ""
    customer_phone: str = ""
    note:           str = ""
    discount_code:  str | None = None


# ── GET /menu ─────────────────────────────────────────────────────────────────

@app.get("/menu")
async def get_menu(pos: str = Query("clover")):
    if pos == "square":
        objects = await _sq_list_catalog("ITEM,CATEGORY,MODIFIER_LIST")
        return _sq_build_menu(objects)

    async with httpx.AsyncClient() as client:
        all_items: list[dict] = []
        offset = 0
        while True:
            data = await _clover_get(
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

        cat_data  = await _clover_get(client, "categories", limit=200)
        raw_cats: list[dict] = cat_data.get("elements", [])

    categories = sorted(
        [{"id": c["id"], "name": c["name"], "sort_order": c.get("sortOrder", 0)} for c in raw_cats],
        key=lambda c: c["sort_order"],
    )

    items = []
    for raw in all_items:
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

        mg_list = []
        for mg in raw.get("modifierGroups", {}).get("elements", []):
            mods = [
                {"id": m["id"], "name": m["name"], "price": m.get("price", 0)}
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

    log.info("menu fetched", pos="clover", item_count=len(items))
    return {"categories": categories, "items": items}


# ── GET /discounts ────────────────────────────────────────────────────────────

@app.get("/discounts")
async def get_discounts(pos: str = Query("clover")):
    if pos == "square":
        objects = await _sq_list_catalog("DISCOUNT")
        return {"discounts": _sq_build_discounts(objects)}

    async with httpx.AsyncClient() as client:
        data = await _clover_get(client, "discounts", limit=200)

    discounts = []
    for d in data.get("elements", []):
        name = d.get("name", "").strip()
        if not name:
            continue
        entry: dict = {"id": d["id"], "name": name}
        if d.get("amount"):
            entry["amount"] = abs(d["amount"])
        if d.get("percentage"):
            entry["percentage"] = d["percentage"]
        discounts.append(entry)
    return {"discounts": discounts}


# ── POST /orders ──────────────────────────────────────────────────────────────

@app.post("/orders", status_code=201)
async def create_order(req: PlaceOrderRequest, pos: str = Query("clover")):
    if not req.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    if pos == "square":
        subtotal = sum(li.price * li.quantity for li in req.items)
        discount_amount = 0
        discount_name: str | None = None

        if req.discount_code:
            objects = await _sq_list_catalog("DISCOUNT")
            discounts = _sq_build_discounts(objects)
            discount_amount, discount_name = _sq_resolve_discount(discounts, req.discount_code, subtotal)

        order_body: dict = {
            "location_id": SQUARE_LOCATION_ID,
            "line_items":  _sq_build_line_items(req.items),
            "fulfillments": [{
                "type":  "PICKUP",
                "state": "PROPOSED",
                "pickup_details": {
                    "recipient": {
                        "display_name": req.customer_name or "Guest",
                        "phone_number": req.customer_phone or "",
                    },
                    "schedule_type": "ASAP",
                    "note": _sq_order_note(req.order_type, req.customer_name, req.customer_phone, req.note),
                },
            }],
        }

        if discount_amount > 0:
            order_body["discounts"] = [{
                "uid":          "promo-1",
                "name":         discount_name,
                "amount_money": {"amount": discount_amount, "currency": "CAD"},
                "scope":        "ORDER",
            }]

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SQUARE_BASE_URL}/v2/orders",
                json={"idempotency_key": str(_uuid.uuid4()), "order": order_body},
                headers=_square_headers(),
                timeout=15.0,
            )
            if not resp.is_success:
                log.error("square order failed", status=resp.status_code, body=resp.text[:500])
                raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                    f"Square order error {resp.status_code}: {resp.text[:300]}")
            data = resp.json()

        order = data["order"]
        total = order.get("total_money", {}).get("amount", subtotal - discount_amount)
        log.info("order created", pos="square", order_id=order["id"], customer=req.customer_name)

        response: dict = {
            "order_id":      order["id"],
            "total":         total,
            "total_display": f"${total / 100:.2f}",
            "state":         order.get("state", "OPEN"),
        }
        if discount_amount > 0:
            response["discount_amount"]  = discount_amount
            response["discount_display"] = f"-${discount_amount / 100:.2f}"
            response["discount_name"]    = discount_name
        return response

    # ── Clover path ───────────────────────────────────────────────────────────
    parts = [f"Online Order — {req.order_type.replace('_', ' ').title()}"]
    if req.customer_name:  parts.append(f"Name: {req.customer_name}")
    if req.customer_phone: parts.append(f"Phone: {req.customer_phone}")
    if req.note:           parts.append(req.note)
    order_note = " | ".join(parts)

    subtotal_cents = sum(li.price * li.quantity for li in req.items)

    async with httpx.AsyncClient() as client:
        matched_discount: dict | None = None
        if req.discount_code:
            disc_data = await _clover_get(client, "discounts", limit=200)
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

        order = await _clover_post(client, "orders", {
            "state": "open", "note": order_note, "currency": "CAD",
        })
        order_id = order["id"]
        log.info("order created", pos="clover", order_id=order_id, customer=req.customer_name)

        for li in req.items:
            for _ in range(li.quantity):
                body: dict = {"item": {"id": li.item_id}, "price": li.price}
                if li.note:
                    body["note"] = li.note
                created_li = await _clover_post(client, f"orders/{order_id}/line_items", body)
                li_id = created_li["id"]
                for mod_id in li.modifier_ids:
                    await _clover_post(
                        client,
                        f"orders/{order_id}/line_items/{li_id}/modifications",
                        {"modifier": {"id": mod_id}},
                    )

        discount_amount = 0
        discount_name_c: str | None = None
        if matched_discount:
            await _clover_post(
                client,
                f"orders/{order_id}/discounts",
                {"discount": {"id": matched_discount["id"]}},
            )
            updated_order = await _clover_get(client, f"orders/{order_id}")
            clover_total = updated_order.get("total", subtotal_cents)
            discount_amount = max(0, subtotal_cents - clover_total)
            discount_name_c = matched_discount.get("name")

    final_total = subtotal_cents - discount_amount
    response2: dict = {
        "order_id":      order_id,
        "total":         final_total,
        "total_display": f"${final_total / 100:.2f}",
        "state":         "open",
    }
    if discount_amount > 0:
        response2["discount_amount"]  = discount_amount
        response2["discount_display"] = f"-${discount_amount / 100:.2f}"
        response2["discount_name"]    = discount_name_c
    return response2


# ── POST /checkout ────────────────────────────────────────────────────────────

@app.post("/checkout", status_code=201)
async def create_checkout(req: CheckoutRequest, pos: str = Query("clover")):
    if not req.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    if pos == "square":
        subtotal = sum(li.price * li.quantity for li in req.items)
        discount_amount = 0
        discount_name: str | None = None

        if req.discount_code:
            objects = await _sq_list_catalog("DISCOUNT")
            discounts = _sq_build_discounts(objects)
            discount_amount, discount_name = _sq_resolve_discount(discounts, req.discount_code, subtotal)

        order_body: dict = {
            "location_id": SQUARE_LOCATION_ID,
            "line_items":  _sq_build_line_items(req.items),
            "fulfillments": [{
                "type":  "PICKUP",
                "state": "PROPOSED",
                "pickup_details": {
                    "recipient": {
                        "display_name": req.customer_name or "Guest",
                        "phone_number": req.customer_phone or "",
                    },
                    "schedule_type": "ASAP",
                    "note": _sq_order_note(
                        req.order_type, req.customer_name, req.customer_phone,
                        req.note, discount_name, discount_amount,
                    ),
                },
            }],
        }

        if discount_amount > 0:
            order_body["discounts"] = [{
                "uid":          "promo-1",
                "name":         discount_name,
                "amount_money": {"amount": discount_amount, "currency": "CAD"},
                "scope":        "ORDER",
            }]

        payload = {
            "idempotency_key": str(_uuid.uuid4()),
            "order":           order_body,
            "checkout_options": {
                "redirect_url":             f"{FRONTEND_URL}?payment=success",
                "ask_for_shipping_address": False,
            },
            "pre_populated_data": {
                "buyer_phone_number": req.customer_phone or "",
            },
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SQUARE_BASE_URL}/v2/online-checkout/payment-links",
                json=payload,
                headers=_square_headers(),
                timeout=15.0,
            )
            log.info("square checkout response", status=resp.status_code, body=resp.text[:400])
            if not resp.is_success:
                raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                    f"Square checkout error {resp.status_code}: {resp.text[:300]}")
            data = resp.json()

        link = data["payment_link"]
        log.info("square payment link created", link_id=link["id"], customer=req.customer_name)
        return {
            "checkout_url":    link["url"],
            "session_id":      link["id"],
            "discount_amount": discount_amount,
            "discount_name":   discount_name,
        }

    # ── Clover Hosted Checkout path ───────────────────────────────────────────
    discount_amount = 0
    discount_label: str | None = None
    subtotal = sum(li.price * li.quantity for li in req.items)

    if req.discount_code:
        async with httpx.AsyncClient() as client:
            disc_data = await _clover_get(client, "discounts", limit=200)
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

        amt     = abs(matched.get("amount", 0))
        pct_raw = matched.get("percentage", 0)
        if amt > 0:
            discount_amount = min(amt, subtotal)
        elif pct_raw > 0:
            actual_pct = pct_raw / 10000.0 if pct_raw > 100 else float(pct_raw)
            discount_amount = round(subtotal * actual_pct / 100)

        discount_label = matched.get("name")
        log.info("checkout discount resolved", code=discount_label, discount_cents=discount_amount)

    line_items: list[dict] = []
    for li in req.items:
        entry: dict = {"name": li.name, "unitQty": li.quantity, "price": li.price}
        if li.note:
            entry["note"] = li.note
        line_items.append(entry)

    if discount_amount > 0 and subtotal > 0:
        scale = (subtotal - discount_amount) / subtotal
        for entry in line_items:
            entry["price"] = max(1, round(entry["price"] * scale))

    parts = [f"Online Order — {req.order_type.replace('_', ' ').title()}"]
    if req.customer_name:  parts.append(f"Name: {req.customer_name}")
    if req.customer_phone: parts.append(f"Phone: {req.customer_phone}")
    if req.note:           parts.append(req.note)
    if discount_amount > 0:
        parts.append(f"Promo: {discount_label} (-${discount_amount / 100:.2f})")

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
        "checkout_url":    checkout_url,
        "session_id":      session_id,
        "discount_amount": discount_amount,
        "discount_name":   discount_label,
    }


# ── GET /orders/{order_id} ────────────────────────────────────────────────────

@app.get("/orders/{order_id}")
async def get_order(order_id: str, pos: str = Query("clover")):
    if pos == "square":
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SQUARE_BASE_URL}/v2/orders/{order_id}",
                headers=_square_headers(),
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
        order       = data["order"]
        fulfillment = order.get("fulfillments", [{}])[0]
        return {
            "order_id":      order["id"],
            "state":         order.get("state", "OPEN"),
            "payment_state": fulfillment.get("state", "PROPOSED"),
            "total":         order.get("total_money", {}).get("amount", 0),
        }

    async with httpx.AsyncClient() as client:
        order = await _clover_get(client, f"orders/{order_id}", expand="lineItems")
    return {
        "order_id":      order["id"],
        "state":         order.get("state", "open"),
        "payment_state": order.get("paymentState", "OPEN"),
        "total":         order.get("total", 0),
    }


# ── GET /health ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "ok":           True,
        "clover":       bool(CLOVER_ACCESS_TOKEN),
        "square":       bool(SQUARE_ACCESS_TOKEN),
        "merchant_id":  CLOVER_MERCHANT_ID,
        "location_id":  SQUARE_LOCATION_ID or None,
    }
