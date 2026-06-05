#!/usr/bin/env python3
"""
seed_clover_menu.py
-------------------
Reads menu.json and creates all categories + items in your Clover merchant via API.
Run once to seed the sandbox (or production) merchant.

Usage:
    cd soniox_examples/apps/soniox-voice-bot-demo/server
    uv run seed_clover_menu.py          # create everything
    uv run seed_clover_menu.py --dry-run  # preview only, no API calls

Requirements: .env must have CLOVER_BASE_URL, CLOVER_MERCHANT_ID, CLOVER_ACCESS_TOKEN
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import dotenv
import httpx

dotenv.load_dotenv()

import os

BASE_URL = os.getenv("CLOVER_BASE_URL", "https://apisandbox.dev.clover.com").rstrip("/")
MERCHANT_ID = os.getenv("CLOVER_MERCHANT_ID", "")
ACCESS_TOKEN = os.getenv("CLOVER_ACCESS_TOKEN", "")
DRY_RUN = "--dry-run" in sys.argv

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "ParkashSweetsVoiceAgent/1.0",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def ok(msg: str) -> None:       print(f"  [OK]   {msg}")
def fail(msg: str) -> None:     print(f"  [FAIL] {msg}")
def info(msg: str) -> None:     print(f"  [INFO] {msg}")
def head(msg: str) -> None:     print(f"\n[CAT]  {msg}")
def item_log(msg: str) -> None: print(f"         {msg}")

# ── API calls ─────────────────────────────────────────────────────────────────

async def create_category(client: httpx.AsyncClient, name: str, sort_order: int) -> str | None:
    """POST /categories — returns Clover category ID or None on failure."""
    resp = await client.post(
        f"/v3/merchants/{MERCHANT_ID}/categories",
        json={"name": name, "sortOrder": sort_order},
    )
    if resp.status_code == 200:
        cat_id = resp.json()["id"]
        ok(f"Category '{name}' created  (id: {cat_id})")
        return cat_id
    fail(f"Category '{name}' — HTTP {resp.status_code}: {resp.text[:200]}")
    return None


async def create_item(
    client: httpx.AsyncClient,
    name: str,
    price_dollars: float,
) -> str | None:
    """POST /items — returns Clover item ID or None on failure."""
    price_cents = int(round(price_dollars * 100))
    resp = await client.post(
        f"/v3/merchants/{MERCHANT_ID}/items",
        json={
            "name": name,
            "price": price_cents,
            "priceType": "FIXED",
            "hidden": False,
            "isRevenue": True,
            "defaultTaxRates": True,
        },
    )
    if resp.status_code == 200:
        item_id = resp.json()["id"]
        item_log(f"{name}  (${price_dollars:.2f} -> {price_cents}c)  id: {item_id}")
        return item_id
    fail(f"Item '{name}' — HTTP {resp.status_code}: {resp.text[:200]}")
    return None


async def associate_items_to_category(
    client: httpx.AsyncClient,
    cat_id: str,
    item_ids: list[str],
    cat_name: str,
) -> None:
    """POST /category_items — bulk-associate items to a category."""
    if not item_ids:
        return
    elements = [
        {"category": {"id": cat_id}, "item": {"id": iid}}
        for iid in item_ids
    ]
    resp = await client.post(
        f"/v3/merchants/{MERCHANT_ID}/category_items",
        json={"elements": elements},
    )
    if resp.status_code == 200:
        ok(f"Linked {len(item_ids)} items -> '{cat_name}'")
    else:
        fail(f"Link items → '{cat_name}' — HTTP {resp.status_code}: {resp.text[:200]}")

# ── main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    # ── Validate env ──────────────────────────────────────────────────────────
    missing = [k for k, v in {
        "CLOVER_BASE_URL":     BASE_URL,
        "CLOVER_MERCHANT_ID":  MERCHANT_ID,
        "CLOVER_ACCESS_TOKEN": ACCESS_TOKEN,
    }.items() if not v]
    if missing:
        print(f"ERROR: Missing env vars: {', '.join(missing)}")
        print("Make sure server/.env is populated and you're running from the server/ directory.")
        sys.exit(1)

    # ── Load menu.json ────────────────────────────────────────────────────────
    _dir = Path(__file__).parent
    menu_path = (
        _dir / "menu.json"
        if (_dir / "menu.json").exists()
        else _dir.parent / "menu.json"
    )
    if not menu_path.exists():
        print(f"ERROR: menu.json not found at {menu_path}")
        sys.exit(1)

    data = json.loads(menu_path.read_text(encoding="utf-8"))
    categories = data.get("categories", [])

    # ── Preview totals ────────────────────────────────────────────────────────
    total_items = sum(len(c["items"]) for c in categories)
    print(f"\n{'='*55}")
    print(f"  Clover Menu Seeder - Parkash Sweets")
    print(f"{'='*55}")
    print(f"  Merchant : {MERCHANT_ID}")
    print(f"  Base URL : {BASE_URL}")
    print(f"  Menu     : {len(categories)} categories, {total_items} items")
    if DRY_RUN:
        print(f"\n  [DRY RUN] No API calls will be made")
    print(f"{'='*55}")

    if DRY_RUN:
        for cat in categories:
            print(f"\n  [CAT] {cat['label']}  ({len(cat['items'])} items)")
            for item in cat["items"]:
                print(f"        ${item['price']:.2f}  {item['name']}")
        print(f"\n  Total: {total_items} items across {len(categories)} categories")
        print("  Run without --dry-run to create them.\n")
        return

    # ── API calls ─────────────────────────────────────────────────────────────
    created_cats  = 0
    created_items = 0
    failed_items: list[str] = []

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        headers=HEADERS,
        timeout=httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
    ) as client:

        for sort_order, category in enumerate(categories):
            cat_label = category["label"]
            head(f"{cat_label}  ({len(category['items'])} items)")

            cat_id = await create_category(client, cat_label, sort_order)
            if not cat_id:
                fail(f"Skipping all items in '{cat_label}'")
                continue
            created_cats += 1

            item_ids: list[str] = []
            for menu_item in category["items"]:
                item_id = await create_item(
                    client,
                    name=menu_item["name"],
                    price_dollars=menu_item["price"],
                )
                if item_id:
                    item_ids.append(item_id)
                    created_items += 1
                else:
                    failed_items.append(menu_item["name"])

            await associate_items_to_category(client, cat_id, item_ids, cat_label)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  Done!")
    print(f"  Categories created : {created_cats} / {len(categories)}")
    print(f"  Items created      : {created_items} / {total_items}")
    if failed_items:
        print(f"  Failed items       : {len(failed_items)}")
        for name in failed_items:
            print(f"    x {name}")
    print(f"{'='*55}\n")

    if created_items == total_items:
        print("All items seeded successfully!")
        print(f"Verify at: {BASE_URL.replace('api', 'sandbox.dev')}/home/m/{MERCHANT_ID}/inventory/items\n")
    else:
        print("Some items failed — check the errors above and re-run for missing ones.\n")


if __name__ == "__main__":
    asyncio.run(main())
