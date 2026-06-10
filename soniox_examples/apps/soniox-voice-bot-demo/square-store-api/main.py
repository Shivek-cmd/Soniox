"""
BizBull Square Store API
Standalone store service for Square POS merchants.

Endpoints:
    GET  /menu              → categories + items + modifier groups from Square Catalog
    GET  /discounts         → active named discounts from Square Catalog
    POST /orders            → create a Square order from the cart (optional discount_code)
    POST /checkout          → create a Square Payment Link for card payment
    GET  /orders/{id}       → fetch order status from Square
    GET  /health            → liveness probe
"""
from __future__ import annotations

import os
import uuid as _uuid
from contextlib import asynccontextmanager
from typing import Any

import httpx
import structlog
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

log = structlog.get_logger()

# ── Config ────────────────────────────────────────────────────────────────────

SQUARE_BASE_URL     = os.environ.get("SQUARE_BASE_URL", "https://connect.squareupsandbox.com").rstrip("/")
SQUARE_ACCESS_TOKEN = os.environ["SQUARE_ACCESS_TOKEN"]
SQUARE_LOCATION_ID  = os.environ["SQUARE_LOCATION_ID"]
SQUARE_API_VERSION  = "2024-01-17"
FRONTEND_URL        = os.environ.get("FRONTEND_URL", "https://voice.bizbull.ai").rstrip("/")


def _headers() -> dict[str, str]:
    return {
        "Authorization":  f"Bearer {SQUARE_ACCESS_TOKEN}",
        "Content-Type":   "application/json",
        "Square-Version": SQUARE_API_VERSION,
    }


# ── App ───────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("square-store-api started", base_url=SQUARE_BASE_URL, location_id=SQUARE_LOCATION_ID)
    yield
    log.info("square-store-api stopped")


app = FastAPI(title="BizBull Square Store API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Square catalog helpers ────────────────────────────────────────────────────

async def _list_catalog(types: str = "ITEM,CATEGORY,MODIFIER_LIST,DISCOUNT") -> list[dict]:
    """Fetch all catalog objects for the given types, handling cursor pagination."""
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
                headers=_headers(),
                timeout=15.0,
            )
            if resp.status_code == 401:
                raise HTTPException(
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                    "Square auth error — check SQUARE_ACCESS_TOKEN",
                )
            resp.raise_for_status()
            data = resp.json()
            objects.extend(data.get("objects", []))
            cursor = data.get("cursor")
            if not cursor:
                break

    return objects


def _build_menu(objects: list[dict]) -> dict:
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

        # Use the first fixed-price variation with a non-zero price
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
            "id":              variation_id,   # frontend sends this as item_id in order requests
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
    log.info("menu built", item_count=len(items), category_count=len(cat_list))
    return {"categories": cat_list, "items": items}


def _build_discounts(objects: list[dict]) -> list[dict]:
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


def _resolve_discount(discounts: list[dict], code: str, subtotal: int) -> tuple[int, str]:
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


def _build_line_items(items: list) -> list[dict]:
    line_items = []
    for li in items:
        entry: dict = {
            "name":             li.name,
            "quantity":         str(li.quantity),
            "base_price_money": {"amount": li.price, "currency": "CAD"},
        }
        if li.item_id:
            entry["catalog_object_id"] = li.item_id   # variation ID from /menu response
        if li.modifier_ids:
            entry["modifiers"] = [{"catalog_object_id": mid} for mid in li.modifier_ids]
        line_items.append(entry)
    return line_items


def _order_note(order_type: str, name: str, phone: str, note: str, discount_label: str | None = None, discount_amt: int = 0) -> str:
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
    price:        int
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
async def get_menu():
    objects = await _list_catalog("ITEM,CATEGORY,MODIFIER_LIST")
    return _build_menu(objects)


# ── GET /discounts ────────────────────────────────────────────────────────────

@app.get("/discounts")
async def get_discounts():
    objects = await _list_catalog("DISCOUNT")
    return {"discounts": _build_discounts(objects)}


# ── POST /orders ──────────────────────────────────────────────────────────────

@app.post("/orders", status_code=201)
async def create_order(req: PlaceOrderRequest):
    if not req.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    subtotal = sum(li.price * li.quantity for li in req.items)
    discount_amount = 0
    discount_name: str | None = None

    if req.discount_code:
        objects = await _list_catalog("DISCOUNT")
        discounts = _build_discounts(objects)
        discount_amount, discount_name = _resolve_discount(discounts, req.discount_code, subtotal)

    order_body: dict = {
        "location_id": SQUARE_LOCATION_ID,
        "line_items":  _build_line_items(req.items),
        "fulfillments": [{
            "type":  "PICKUP",
            "state": "PROPOSED",
            "pickup_details": {
                "recipient": {
                    "display_name": req.customer_name or "Guest",
                    "phone_number": req.customer_phone or "",
                },
                "schedule_type": "ASAP",
                "note": _order_note(req.order_type, req.customer_name, req.customer_phone, req.note),
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
            headers=_headers(),
            timeout=15.0,
        )
        if not resp.is_success:
            log.error("square order failed", status=resp.status_code, body=resp.text[:500])
            raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                f"Square order error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()

    order = data["order"]
    total = order.get("total_money", {}).get("amount", subtotal - discount_amount)
    log.info("order created", order_id=order["id"], customer=req.customer_name, total=total)

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


# ── POST /checkout ────────────────────────────────────────────────────────────

@app.post("/checkout", status_code=201)
async def create_checkout(req: CheckoutRequest):
    if not req.items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cart is empty")

    subtotal = sum(li.price * li.quantity for li in req.items)
    discount_amount = 0
    discount_name: str | None = None

    if req.discount_code:
        objects = await _list_catalog("DISCOUNT")
        discounts = _build_discounts(objects)
        discount_amount, discount_name = _resolve_discount(discounts, req.discount_code, subtotal)

    order_body: dict = {
        "location_id": SQUARE_LOCATION_ID,
        "line_items":  _build_line_items(req.items),
        "fulfillments": [{
            "type":  "PICKUP",
            "state": "PROPOSED",
            "pickup_details": {
                "recipient": {
                    "display_name": req.customer_name or "Guest",
                    "phone_number": req.customer_phone or "",
                },
                "schedule_type": "ASAP",
                "note": _order_note(
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
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SQUARE_BASE_URL}/v2/online-checkout/payment-links",
            json=payload,
            headers=_headers(),
            timeout=15.0,
        )
        log.info("square checkout response", status=resp.status_code, body=resp.text[:500])
        if not resp.is_success:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                f"Square checkout error {resp.status_code}: {resp.text[:300]}")
        data = resp.json()

    link = data["payment_link"]
    log.info("payment link created", link_id=link["id"], customer=req.customer_name)
    return {
        "checkout_url":    link["url"],
        "session_id":      link["id"],
        "discount_amount": discount_amount,
        "discount_name":   discount_name,
    }


# ── GET /orders/{order_id} ────────────────────────────────────────────────────

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SQUARE_BASE_URL}/v2/orders/{order_id}",
            headers=_headers(),
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


# ── GET /health ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"ok": True, "pos": "square", "location_id": SQUARE_LOCATION_ID}
