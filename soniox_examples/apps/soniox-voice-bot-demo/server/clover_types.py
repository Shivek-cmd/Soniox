"""
Clover POS data types.

All prices are integers in cents (e.g. $11.50 → 1150).
Use .price_dollars / .total_dollars properties for display.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CloverModifier:
    id: str
    name: str
    price: int          # cents — 0 means free
    available: bool = True


@dataclass
class CloverModifierGroup:
    id: str
    name: str
    min_required: int   # 0 = optional, 1+ = customer must pick
    max_allowed: int    # max selections allowed
    modifiers: list[CloverModifier] = field(default_factory=list)


@dataclass
class CloverItem:
    id: str
    name: str
    price: int          # cents — $11.50 stored as 1150
    category_name: str
    category_id: str
    modifier_groups: list[CloverModifierGroup] = field(default_factory=list)
    # Voice-agent extras merged from menu.json — Clover has no concept of these
    terms: list[str] = field(default_factory=list)          # spoken aliases (English only)
    pronunciation: dict[str, str] = field(default_factory=dict)  # lang → phonetic guide

    @property
    def price_dollars(self) -> float:
        return self.price / 100


@dataclass
class CloverOrderType:
    id: str
    label: str
    is_hidden: bool = False
    is_default: bool = False


@dataclass
class CloverCreatedOrder:
    """Returned after successfully creating an order via the Clover atomic order API."""
    id: str                 # Clover's order ID — e.g. "F3XK2PM9QR5T6" — shown to customer
    total_cents: int        # auto-calculated by Clover
    state: str              # always "open" immediately after creation
    order_type_label: str   # e.g. "Takeout"
    created_time: int       # Unix ms
    line_item_count: int = 0

    @property
    def total_dollars(self) -> float:
        return self.total_cents / 100
