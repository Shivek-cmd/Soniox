"""Square POS client — same interface as CloverClient for drop-in use in tools.py."""
from __future__ import annotations

import os
import re
import uuid as _uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog
from rapidfuzz import fuzz, process

log = structlog.get_logger()

SQUARE_BASE_URL     = os.environ.get("SQUARE_BASE_URL", "https://connect.squareupsandbox.com").rstrip("/")
SQUARE_ACCESS_TOKEN = os.environ.get("SQUARE_ACCESS_TOKEN", "")
SQUARE_LOCATION_ID  = os.environ.get("SQUARE_LOCATION_ID", "")
SQUARE_API_VERSION  = "2024-01-17"


def _sq_headers() -> dict[str, str]:
    return {
        "Authorization":  f"Bearer {SQUARE_ACCESS_TOKEN}",
        "Content-Type":   "application/json",
        "Square-Version": SQUARE_API_VERSION,
    }


# ── Errors ────────────────────────────────────────────────────────────────────

class SquareError(Exception):
    pass


class SquareItemNotFoundError(SquareError):
    def __init__(self, item_name: str):
        super().__init__(f"Item not found in Square catalog: {item_name}")
        self.item_name = item_name


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SquareCreatedOrder:
    id: str
    total_cents: int = 0
    state: str = "OPEN"
    order_type_label: str = ""


@dataclass
class SquareItem:
    id: str             # variation_id — used as catalog_object_id in orders
    name: str
    price: int          # cents
    category_name: str = ""
    category_id: str = ""
    modifier_groups: list = field(default_factory=list)
    terms: list[str] = field(default_factory=list)

    @property
    def price_dollars(self) -> float:
        return self.price / 100


# ── Menu cache ────────────────────────────────────────────────────────────────

class SquareMenuCache:
    """Same interface as CloverMenuCache so tools.py can use either transparently."""

    def __init__(self):
        self._items: list[SquareItem] = []
        self._by_name_lower: dict[str, SquareItem] = {}

    def replace_all(self, items: list[SquareItem]) -> None:
        self._items = list(items)
        self._by_name_lower = {i.name.lower(): i for i in items}

    def is_empty(self) -> bool:
        return not self._items

    def item_count(self) -> int:
        return len(self._items)

    def all_items(self) -> list[SquareItem]:
        return list(self._items)

    def get_category(self, category_name: str) -> list[SquareItem]:
        cat_lower = category_name.lower()
        return [i for i in self._items if i.category_name.lower() == cat_lower]

    def lookup(self, name: str) -> SquareItem | None:
        """4-level lookup: exact → tokens → fuzzy."""
        name_lower = name.strip().lower()

        # 1. Exact lowercase match
        if name_lower in self._by_name_lower:
            return self._by_name_lower[name_lower]

        # 2. All-tokens subset
        def _tokens(s: str) -> set[str]:
            return set(re.sub(r"[^a-z0-9]", " ", s.lower()).split())

        query_tokens = _tokens(name_lower)
        if query_tokens:
            best: SquareItem | None = None
            best_extra = 9999
            ambiguous = False
            for item in self._items:
                item_tokens = _tokens(item.name)
                if not query_tokens.issubset(item_tokens):
                    continue
                extra = len(item_tokens - query_tokens)
                if extra < best_extra:
                    best_extra = extra
                    best = item
                    ambiguous = False
                elif extra == best_extra:
                    ambiguous = True
            if best is not None and not ambiguous:
                return best

        # 3. Fuzzy match
        all_names = [i.name for i in self._items]
        if all_names:
            result = process.extractOne(name, all_names, scorer=fuzz.token_sort_ratio)
            if result and result[1] >= 80:
                return self._by_name_lower.get(result[0].lower())

        return None


# ── Square client ─────────────────────────────────────────────────────────────

class SquareClient:
    """Connects to Square and manages a live menu cache."""

    def __init__(self):
        self.available: bool = False
        self.menu: SquareMenuCache = SquareMenuCache()

    async def init(self) -> None:
        if not SQUARE_ACCESS_TOKEN:
            raise SquareError("SQUARE_ACCESS_TOKEN is not set")
        await self._refresh_menu()
        self.available = True
        log.info("square.init.ok", item_count=self.menu.item_count(), location=SQUARE_LOCATION_ID)

    async def close(self) -> None:
        self.available = False

    async def _refresh_menu(self) -> None:
        objects = await self._list_catalog("ITEM,CATEGORY")
        items = self._parse_items(objects)
        self.menu.replace_all(items)
        log.info("square.menu.refreshed", item_count=len(items))

    async def _list_catalog(self, types: str) -> list[dict]:
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
                    headers=_sq_headers(),
                    timeout=15.0,
                )
                if resp.status_code == 401:
                    raise SquareError("Square auth error — check SQUARE_ACCESS_TOKEN")
                if not resp.is_success:
                    raise SquareError(f"Square catalog list failed: {resp.status_code} {resp.text[:200]}")
                data = resp.json()
                objects.extend(data.get("objects", []))
                cursor = data.get("cursor")
                if not cursor:
                    break
        return objects

    @staticmethod
    def _parse_items(objects: list[dict]) -> list[SquareItem]:
        categories: dict[str, str] = {}
        for obj in objects:
            if obj["type"] == "CATEGORY":
                categories[obj["id"]] = obj.get("category_data", {}).get("name", "Uncategorized")

        items: list[SquareItem] = []
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

            # category_id (legacy field) or first entry in categories array (newer API)
            cat_id = item_data.get("category_id", "")
            if not cat_id:
                cats_arr = item_data.get("categories", [])
                if cats_arr:
                    cat_id = cats_arr[0].get("id", "")
            cat_name = categories.get(cat_id, "Uncategorized")
            items.append(SquareItem(
                id=variation_id,
                name=item_data.get("name", ""),
                price=price,
                category_name=cat_name,
                category_id=cat_id,
            ))
        return items

    async def create_order(
        self,
        order_type: str,
        items: list[dict],
        customer_name: str,
        phone_number: str,
        special_instructions: str = "",
        delivery_address: str = "",
    ) -> SquareCreatedOrder:
        if not SQUARE_LOCATION_ID:
            raise SquareError("SQUARE_LOCATION_ID is not set")

        line_items: list[dict] = []
        for item in items:
            sq_item = self.menu.lookup(item["name"])
            if sq_item is None:
                raise SquareItemNotFoundError(item["name"])

            # LLM sends price as dollars (e.g. 4.50); Square needs cents
            price_cents = round(float(item.get("price", sq_item.price_dollars)) * 100)

            for _ in range(item.get("quantity", 1)):
                entry: dict = {
                    "catalog_object_id": sq_item.id,
                    "quantity":          "1",
                    "base_price_money":  {"amount": price_cents, "currency": "CAD"},
                }
                if item.get("notes"):
                    entry["note"] = item["notes"]
                line_items.append(entry)

        note_parts = [f"Voice Order — {order_type.replace('_', ' ').title()}"]
        if customer_name:         note_parts.append(f"Name: {customer_name}")
        if phone_number:          note_parts.append(f"Phone: {phone_number}")
        if delivery_address:      note_parts.append(f"Address: {delivery_address}")
        if special_instructions:  note_parts.append(special_instructions)
        order_note = " | ".join(note_parts)

        fulfillment_type = "DELIVERY" if order_type == "delivery" else "PICKUP"
        order_body: dict = {
            "location_id": SQUARE_LOCATION_ID,
            "line_items":  line_items,
            "fulfillments": [{
                "type":  fulfillment_type,
                "state": "PROPOSED",
                "pickup_details": {
                    "recipient": {
                        "display_name": customer_name or "Guest",
                        "phone_number": phone_number or "",
                    },
                    "schedule_type": "ASAP",
                    "note": order_note,
                },
            }],
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{SQUARE_BASE_URL}/v2/orders",
                json={"idempotency_key": str(_uuid.uuid4()), "order": order_body},
                headers=_sq_headers(),
                timeout=15.0,
            )
            if not resp.is_success:
                raise SquareError(
                    f"Square order creation failed: {resp.status_code} {resp.text[:200]}"
                )
            data = resp.json()

        order = data["order"]
        total = order.get("total_money", {}).get("amount", 0)
        log.info("square.order.created", order_id=order["id"], total_cents=total, customer=customer_name)
        return SquareCreatedOrder(
            id=order["id"],
            total_cents=total,
            state=order.get("state", "OPEN"),
            order_type_label=order_type,
        )
