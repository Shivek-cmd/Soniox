"""
Clover POS client — menu cache, token management, order creation (stub).

Public surface:
    await init_clover()      — call once at startup (from main.py)
    get_client()             — returns the singleton after init
    client.menu.lookup(name) — resolve spoken item name → CloverItem
    client.create_order(...) — Phase 4 (stub for now)
    client.verify_webhook(header) — validate X-Clover-Auth
    client.schedule_menu_reload() — called by webhook handler on inventory events
"""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import structlog
from rapidfuzz import fuzz, process

from clover_types import CloverCreatedOrder, CloverItem, CloverModifier, CloverModifierGroup

log = structlog.get_logger()

# ── Helpers ───────────────────────────────────────────────────────────────────

# Detects Gurmukhi (੦–੿) and Devanagari (ऀ–ॿ) characters.
# These are voice-agent-only display terms — not indexed for name lookup.
_NATIVE_SCRIPT_RE = re.compile(r"[ऀ-ॿ਀-੿]")


def _normalize(name: str) -> str:
    """Lowercase, collapse punctuation to spaces, strip edges."""
    s = re.sub(r"[^\w\s]", " ", name.lower())
    return re.sub(r"\s+", " ", s).strip()


# ── Exceptions ────────────────────────────────────────────────────────────────

class CloverError(Exception):
    """Base for all Clover integration errors."""


class CloverAuthError(CloverError):
    """Token missing, invalid, or refresh failed."""


class CloverRateLimitError(CloverError):
    def __init__(self, retry_after: int = 2) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited — retry after {retry_after}s")


class CloverItemNotFoundError(CloverError):
    def __init__(self, item_name: str) -> None:
        self.item_name = item_name
        super().__init__(f"Item not found in Clover or menu cache: {item_name!r}")


class CloverOrderError(CloverError):
    """Clover returned 400 — bad order data. Do not retry."""
    def __init__(self, message: str, details: str = "") -> None:
        self.clover_message = message
        self.details = details
        super().__init__(f"[{message}] {details}".rstrip())


class CloverUnavailableError(CloverError):
    """Clover is unreachable or returned repeated server errors."""


# ── Menu Cache ────────────────────────────────────────────────────────────────

@dataclass
class _Snapshot:
    """Immutable snapshot of the menu cache — swapped atomically on reload."""
    by_id: dict[str, CloverItem] = field(default_factory=dict)
    # normalized name / alias → clover item id
    by_name: dict[str, str] = field(default_factory=dict)
    # category name → list of items
    by_category: dict[str, list[CloverItem]] = field(default_factory=dict)
    # Unix ms of last successful sync with Clover
    last_sync_ts: int = 0


class MenuCache:
    """
    Async-safe in-memory cache of Clover menu items.

    Three indexes for fast lookups during a voice call:
        by_id       — look up by Clover item ID (used when building order payload)
        by_name     — look up by normalized name or alias (used during item resolution)
        by_category — list all items in a category (used by get_menu tool)

    Thread-safety: writes use asyncio.Lock; reads grab a reference snapshot
    (Python assignment is atomic under the GIL — no lock needed for reads).
    """

    def __init__(self, extras: dict[str, dict]) -> None:
        # extras: { normalized_item_name → { "terms": [...], "pronunciation": {...} } }
        # Loaded from menu.json at startup — Clover has no concept of these fields.
        self._extras = extras
        self._snap = _Snapshot()
        self._lock = asyncio.Lock()

    # ── Item coercion ─────────────────────────────────────────────────────────

    def _coerce_item(self, raw: dict) -> CloverItem | None:
        """
        Convert a raw Clover API item dict to a CloverItem.
        Returns None for items that should be excluded from the voice menu.
        """
        # Exclude unavailable / non-phone-orderable items
        if raw.get("hidden"):
            return None
        if raw.get("priceType", "FIXED") != "FIXED":
            # VARIABLE and PER_UNIT cannot be priced over the phone
            return None
        if raw.get("isAgeRestricted"):
            # Never offer age-restricted items via phone
            return None
        if raw.get("deletedTime", 0) > 0:
            return None

        categories = raw.get("categories", {}).get("elements", [])
        cat = categories[0] if categories else {}

        modifier_groups: list[CloverModifierGroup] = []
        for mg_raw in raw.get("modifierGroups", {}).get("elements", []):
            modifiers = [
                CloverModifier(
                    id=m["id"],
                    name=m["name"],
                    price=m.get("price", 0),
                    available=m.get("available", True),
                )
                for m in mg_raw.get("modifiers", {}).get("elements", [])
                if not m.get("deleted")
            ]
            modifier_groups.append(
                CloverModifierGroup(
                    id=mg_raw["id"],
                    name=mg_raw["name"],
                    min_required=mg_raw.get("minRequired", 0),
                    max_allowed=mg_raw.get("maxAllowed", 1),
                    modifiers=modifiers,
                )
            )

        norm_name = _normalize(raw["name"])
        extras = self._extras.get(norm_name, {})

        return CloverItem(
            id=raw["id"],
            name=raw["name"],
            price=raw.get("price", 0),
            category_name=cat.get("name", ""),
            category_id=cat.get("id", ""),
            modifier_groups=modifier_groups,
            terms=extras.get("terms", []),
            pronunciation=extras.get("pronunciation", {}),
        )

    # ── Index helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _index_item(snap: _Snapshot, item: CloverItem) -> None:
        snap.by_id[item.id] = item

        # Primary name index
        norm = _normalize(item.name)
        snap.by_name[norm] = item.id

        # Also index Latin-script terms from menu.json extras (spoken aliases)
        for term in item.terms:
            if _NATIVE_SCRIPT_RE.search(term):
                continue  # skip Gurmukhi / Devanagari — not spoken by LLM
            norm_term = _normalize(term)
            if norm_term and norm_term not in snap.by_name:
                snap.by_name[norm_term] = item.id

        # Category index
        cat = item.category_name or "Other"
        snap.by_category.setdefault(cat, [])
        if not any(i.id == item.id for i in snap.by_category[cat]):
            snap.by_category[cat].append(item)

    @staticmethod
    def _remove_from_index(snap: _Snapshot, item_id: str) -> None:
        item = snap.by_id.pop(item_id, None)
        if not item:
            return
        snap.by_name.pop(_normalize(item.name), None)
        for term in item.terms:
            snap.by_name.pop(_normalize(term), None)
        cat_list = snap.by_category.get(item.category_name, [])
        snap.by_category[item.category_name] = [i for i in cat_list if i.id != item_id]

    # ── Public mutators (async — acquire lock before writing) ────────────────

    async def replace_all(self, raw_items: list[dict]) -> None:
        """
        Full atomic swap of the cache from a fresh Clover item list.
        Used at startup and on webhook-triggered full reloads.
        """
        snap = _Snapshot(last_sync_ts=int(time.time() * 1000))
        for raw in raw_items:
            item = self._coerce_item(raw)
            if item:
                self._index_item(snap, item)

        async with self._lock:
            self._snap = snap

        log.info(
            "menu_cache.replaced",
            item_count=len(snap.by_id),
            category_count=len(snap.by_category),
        )

    async def apply_delta(self, raw_items: list[dict]) -> None:
        """
        Apply a list of changed items in-place (from delta poll or incremental update).
        Items with hidden=true or deletedTime>0 are removed from all indexes.
        """
        if not raw_items:
            return

        removed, updated = 0, 0
        async with self._lock:
            snap = self._snap
            for raw in raw_items:
                item_id = raw.get("id")
                if not item_id:
                    continue

                is_gone = raw.get("hidden") or raw.get("deletedTime", 0) > 0
                if is_gone:
                    self._remove_from_index(snap, item_id)
                    removed += 1
                else:
                    item = self._coerce_item(raw)
                    if item:
                        self._remove_from_index(snap, item_id)  # clean stale entries first
                        self._index_item(snap, item)
                        updated += 1

            snap.last_sync_ts = int(time.time() * 1000)

        log.info("menu_cache.delta_applied", removed=removed, updated=updated)

    # ── Public readers (no lock — snapshot reference read is atomic) ──────────

    def lookup(self, name: str) -> CloverItem | None:
        """
        Resolve a spoken item name to a CloverItem.
        Resolution chain: exact match → fuzzy match (≥80 score) → None.
        """
        snap = self._snap  # single reference read — atomic under Python GIL

        norm = _normalize(name)

        # 1. Exact match (also catches alias matches from terms[])
        if cid := snap.by_name.get(norm):
            return snap.by_id.get(cid)

        # 2. Fuzzy match — catches typos and paraphrases from STT
        if snap.by_name:
            result = process.extractOne(
                norm,
                list(snap.by_name.keys()),
                scorer=fuzz.ratio,
                score_cutoff=80,
            )
            if result:
                return snap.by_id.get(snap.by_name[result[0]])

        return None

    def get_category(self, category: str | None = None) -> list[CloverItem]:
        """
        Return items in a category. Fuzzy-matches the category name (≥70 score).
        Passing None or empty string returns all items.
        """
        snap = self._snap

        if not category:
            return list(snap.by_id.values())

        norm_cat = category.lower().strip()
        cat_keys = list(snap.by_category.keys())

        # Exact (case-insensitive)
        for k in cat_keys:
            if k.lower() == norm_cat:
                return list(snap.by_category[k])

        # Fuzzy
        lower_keys = [k.lower() for k in cat_keys]
        result = process.extractOne(norm_cat, lower_keys, scorer=fuzz.ratio, score_cutoff=70)
        if result:
            matched = cat_keys[lower_keys.index(result[0])]
            return list(snap.by_category[matched])

        return []

    def get_by_id(self, clover_id: str) -> CloverItem | None:
        return self._snap.by_id.get(clover_id)

    def is_empty(self) -> bool:
        return len(self._snap.by_id) == 0

    def item_count(self) -> int:
        return len(self._snap.by_id)

    def last_sync_ts(self) -> int:
        return self._snap.last_sync_ts

    def all_items(self) -> list[CloverItem]:
        return list(self._snap.by_id.values())


# ── Clover Client ─────────────────────────────────────────────────────────────

class CloverClient:
    """
    Async Clover POS client. One instance per server process.

    Lifecycle:
        client = CloverClient()
        await client.init()       # once at startup — blocks until ready
        ...use client...
        await client.close()      # on shutdown
    """

    def __init__(self) -> None:
        # Read from env at construction time — fail-fast validation happens in init()
        self._base_url: str = os.getenv("CLOVER_BASE_URL", "").rstrip("/")
        self._merchant_id: str = os.getenv("CLOVER_MERCHANT_ID", "")
        self._access_token: str = os.getenv("CLOVER_ACCESS_TOKEN", "")
        self._refresh_token_val: str = os.getenv("CLOVER_REFRESH_TOKEN", "")
        self._webhook_secret: str = os.getenv("CLOVER_WEBHOOK_SECRET", "")
        self._poll_interval: int = int(os.getenv("CLOVER_MENU_POLL_INTERVAL", "300"))

        self._token_acquired_at: float = time.monotonic()
        self._http: httpx.AsyncClient | None = None

        # Menu cache — initialized in init()
        self.menu: MenuCache | None = None

        # Maps "pickup" | "delivery" | "dine_in" → Clover order type ID
        self._order_type_ids: dict[str, str] = {}

        # True once Clover is reachable and menu is loaded from API
        self.available: bool = False

        self._refresh_lock = asyncio.Lock()
        self._poll_task: asyncio.Task[None] | None = None
        self._reload_task: asyncio.Task[None] | None = None
        self._reload_debounce_handle: asyncio.TimerHandle | None = None

    # ── Startup ───────────────────────────────────────────────────────────────

    def _validate_env(self) -> None:
        """Raise CloverError immediately if any required env var is missing."""
        required = {
            "CLOVER_BASE_URL": self._base_url,
            "CLOVER_MERCHANT_ID": self._merchant_id,
            "CLOVER_ACCESS_TOKEN": self._access_token,
            "CLOVER_WEBHOOK_SECRET": self._webhook_secret,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise CloverError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Add them to server/.env and restart."
            )

    def _load_menu_extras(self) -> dict[str, dict]:
        """
        Load voice-agent-only extras from menu.json (terms + pronunciation).

        These fields don't exist in Clover — they are merged into CloverItem
        objects so the voice agent can resolve spoken aliases and guide TTS.
        """
        _dir = Path(__file__).parent
        path = (
            _dir / "menu.json"
            if (_dir / "menu.json").exists()
            else _dir.parent / "menu.json"
        )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("clover.extras.load_failed", error=str(exc))
            return {}

        extras: dict[str, dict] = {}
        for cat in data.get("categories", []):
            for item in cat.get("items", []):
                name = item.get("name", "")
                if not name:
                    continue
                norm = _normalize(name)
                extras[norm] = {
                    "terms": item.get("terms", []),
                    "pronunciation": item.get("pronunciation", {}),
                }

        log.debug("clover.extras.loaded", count=len(extras))
        return extras

    async def init(self) -> None:
        """
        Initialize the Clover client. Must be called once before the WebSocket
        server starts accepting connections.

        Raises:
            CloverError      — missing env vars
            CloverAuthError  — bad token on first request
            CloverError      — cannot fetch order types (hard requirement)

        Menu load failure is non-fatal — tools.py continues with its static
        menu.json until Clover becomes reachable.
        """
        self._validate_env()

        extras = self._load_menu_extras()
        self.menu = MenuCache(extras)

        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "User-Agent": "ParkashSweetsVoiceAgent/1.0",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0),
        )

        # Order types are a hard requirement — cannot create orders without them
        await self._fetch_order_types()

        # Menu load is best-effort — fall back to static if Clover is down
        try:
            raw_items = await self._load_all_items()
            await self.menu.replace_all(raw_items)
            self.available = True
            log.info("clover.ready", item_count=self.menu.item_count())
        except CloverError as exc:
            log.warning(
                "clover.menu.load_failed_using_static_fallback",
                error=str(exc),
                note="Voice agent will use menu.json until Clover is reachable",
            )
            self._start_reconnect_loop()

        # Background delta-sync to catch changes the webhook may have missed
        self._poll_task = asyncio.create_task(
            self._poll_loop(), name="clover-delta-poll"
        )

    # ── HTTP core ─────────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | list[tuple[str, str]] | None = None,
        _attempt: int = 1,
        _retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """
        Core HTTP call with full retry + token-refresh logic.

        Retry policy:
            401  → refresh token, retry once (if refresh_token configured)
            429  → wait retry-after header value, retry (max 3 total)
            5xx  → exponential backoff (1s, 2s), retry (max 3 total)
            timeout / network → 2s * attempt, retry (max 3 total)
            400  → raise CloverOrderError immediately (bad data, not transient)
        """
        MAX_ATTEMPTS = 3

        if self._http is None:
            raise CloverUnavailableError("CloverClient.init() has not been called")

        await self._maybe_refresh_token()

        try:
            response = await self._http.request(
                method, path, json=json_body, params=params
            )
        except httpx.TimeoutException as exc:
            if _attempt < MAX_ATTEMPTS:
                wait = 2.0 * _attempt
                log.warning("clover.request.timeout", path=path, attempt=_attempt, retrying_in=wait)
                await asyncio.sleep(wait)
                return await self._request(
                    method, path, json_body=json_body, params=params,
                    _attempt=_attempt + 1, _retry_on_401=_retry_on_401,
                )
            raise CloverUnavailableError(
                f"Request timed out after {MAX_ATTEMPTS} attempts: {path}"
            ) from exc
        except httpx.NetworkError as exc:
            if _attempt < MAX_ATTEMPTS:
                wait = 1.0 * _attempt
                log.warning("clover.request.network_error", path=path, attempt=_attempt, retrying_in=wait)
                await asyncio.sleep(wait)
                return await self._request(
                    method, path, json_body=json_body, params=params,
                    _attempt=_attempt + 1, _retry_on_401=_retry_on_401,
                )
            raise CloverUnavailableError(
                f"Network error after {MAX_ATTEMPTS} attempts: {path}"
            ) from exc

        status = response.status_code

        if status == 200:
            return response.json()

        if status == 400:
            try:
                err = response.json()
            except Exception:
                err = {}
            raise CloverOrderError(
                message=err.get("message", "bad_request"),
                details=err.get("details", response.text[:300]),
            )

        if status == 401:
            if _retry_on_401 and self._refresh_token_val:
                log.warning("clover.request.401_refreshing_token", path=path)
                try:
                    await self.refresh_token()
                except CloverAuthError as exc:
                    raise CloverAuthError(
                        f"401 on {path} and token refresh also failed: {exc}"
                    ) from exc
                return await self._request(
                    method, path, json_body=json_body, params=params,
                    _attempt=_attempt, _retry_on_401=False,
                )
            raise CloverAuthError(
                f"Unauthorized on {path}. "
                f"Check CLOVER_ACCESS_TOKEN (sandbox tokens don't expire; "
                f"production tokens need CLOVER_REFRESH_TOKEN)."
            )

        if status == 429:
            retry_after = int(response.headers.get("retry-after", "2"))
            if _attempt < MAX_ATTEMPTS:
                log.warning(
                    "clover.request.rate_limited",
                    path=path, retry_after=retry_after, attempt=_attempt,
                )
                await asyncio.sleep(float(retry_after))
                return await self._request(
                    method, path, json_body=json_body, params=params,
                    _attempt=_attempt + 1, _retry_on_401=_retry_on_401,
                )
            raise CloverRateLimitError(retry_after)

        if status >= 500:
            backoff = 1.0 * _attempt
            if _attempt < MAX_ATTEMPTS:
                log.warning(
                    "clover.request.server_error",
                    status=status, path=path, attempt=_attempt, backoff=backoff,
                )
                await asyncio.sleep(backoff)
                return await self._request(
                    method, path, json_body=json_body, params=params,
                    _attempt=_attempt + 1, _retry_on_401=_retry_on_401,
                )
            raise CloverUnavailableError(
                f"Clover server error {status} after {MAX_ATTEMPTS} attempts: {path}"
            )

        raise CloverError(
            f"Unexpected HTTP {status} from {path}: {response.text[:200]}"
        )

    # ── Token management ──────────────────────────────────────────────────────

    async def _maybe_refresh_token(self) -> None:
        """Refresh access token if it's within 5 minutes of expiry."""
        if not self._refresh_token_val:
            return  # sandbox dev token — no TTL, no refresh needed
        elapsed = time.monotonic() - self._token_acquired_at
        if elapsed < 3300:  # 55 min — refresh 5 min before 1h expiry
            return
        await self.refresh_token()

    async def refresh_token(self) -> None:
        """
        Exchange the current refresh token for a new access + refresh token pair.

        Uses a lock so concurrent callers don't trigger multiple simultaneous
        refreshes. The second caller re-checks elapsed time inside the lock and
        returns immediately if the first caller already refreshed.

        Important: Clover refresh tokens are single-use. We store the new pair
        atomically before the old one becomes invalid.
        """
        async with self._refresh_lock:
            # Double-check inside lock — another coroutine may have just refreshed
            elapsed = time.monotonic() - self._token_acquired_at
            if elapsed < 3300:
                return

            log.info("clover.token.refreshing")
            refresh_url = f"{self._base_url}/oauth/v2/refresh"

            try:
                # Use a separate short-lived client to avoid state entanglement
                async with httpx.AsyncClient(timeout=10.0) as tmp:
                    resp = await tmp.post(
                        refresh_url,
                        json={"refresh_token": self._refresh_token_val},
                    )

                if resp.status_code != 200:
                    raise CloverAuthError(
                        f"Token refresh returned HTTP {resp.status_code}: {resp.text[:200]}"
                    )

                data = resp.json()
                new_access = data.get("access_token", "")
                new_refresh = data.get("refresh_token", "")

                if not new_access:
                    raise CloverAuthError("Token refresh response contained no access_token")

                # Atomic store — write new pair before anything reads them
                self._access_token = new_access
                if new_refresh:
                    # Clover issues a new refresh token each time — old one is now invalid
                    self._refresh_token_val = new_refresh
                self._token_acquired_at = time.monotonic()

                # Propagate to the live httpx session
                if self._http:
                    self._http.headers["Authorization"] = f"Bearer {self._access_token}"

                log.info("clover.token.refreshed")

            except CloverAuthError:
                raise
            except Exception as exc:
                raise CloverAuthError(f"Unexpected error during token refresh: {exc}") from exc

    # ── Menu loading ──────────────────────────────────────────────────────────

    async def _load_all_items(self) -> list[dict]:
        """
        Paginated full fetch of all non-hidden items with categories + modifiers.
        For a typical restaurant menu, limit=1000 returns everything in one call.
        Pagination guard is here for correctness on very large menus.
        """
        all_items: list[dict] = []
        offset = 0
        limit = 1000
        path = f"/v3/merchants/{self._merchant_id}/items"

        while True:
            data = await self._request(
                "GET", path,
                params={
                    "expand": "categories,modifierGroups",
                    "limit": str(limit),
                    "offset": str(offset),
                    "filter": "hidden=false",
                },
            )
            elements: list[dict] = data.get("elements", [])
            all_items.extend(elements)

            # Fewer results than requested → we're on the last page
            if len(elements) < limit:
                break
            offset += limit

        return all_items

    async def _load_delta_items(self, since_ts: int) -> list[dict]:
        """
        Fetch only items modified since `since_ts` (Unix ms).
        Falls back to full load if since_ts is 0 (cache was never populated).
        """
        if not since_ts:
            return await self._load_all_items()

        all_items: list[dict] = []
        offset = 0
        limit = 1000
        path = f"/v3/merchants/{self._merchant_id}/items"

        while True:
            # Use list-of-tuples so we can pass the filter with >= operator.
            # httpx URL-encodes it to %3E%3D which Clover's server decodes correctly.
            data = await self._request(
                "GET", path,
                params=[
                    ("expand", "categories,modifierGroups"),
                    ("limit", str(limit)),
                    ("offset", str(offset)),
                    ("filter", f"modifiedTime>={since_ts}"),
                ],
            )
            elements: list[dict] = data.get("elements", [])
            all_items.extend(elements)
            if len(elements) < limit:
                break
            offset += limit

        return all_items

    # ── Order types ───────────────────────────────────────────────────────────

    async def _fetch_order_types(self) -> None:
        """
        Fetch merchant's Clover order types and map them to our canonical keys:
        "pickup", "delivery", "dine_in".

        Matching is label-based (case-insensitive, common variants).
        If no labels match, logs a warning with all found labels so the developer
        can extend the label_map below or rename labels in Clover.

        Falls back to the first available order type as "pickup" so order creation
        always has at least one usable type.
        """
        data = await self._request(
            "GET", f"/v3/merchants/{self._merchant_id}/order_types"
        )
        all_types: list[dict] = data.get("elements", [])
        available = [ot for ot in all_types if not ot.get("isHidden")]

        if not available:
            raise CloverError(
                "No non-hidden order types found in Clover. "
                "Create at least one order type in the Clover dashboard."
            )

        # Common label variants → our canonical key
        label_map: dict[str, str] = {
            "takeout": "pickup",      "take out": "pickup",    "take-out": "pickup",
            "pickup": "pickup",       "pick up": "pickup",     "pick-up": "pickup",
            "to go": "pickup",        "to-go": "pickup",       "togo": "pickup",
            "delivery": "delivery",   "deliver": "delivery",
            "online delivery": "delivery",                      "door delivery": "delivery",
            "dine in": "dine_in",     "dine-in": "dine_in",   "dinein": "dine_in",
            "eat in": "dine_in",      "in store": "dine_in",  "in-store": "dine_in",
            "table service": "dine_in",                         "here": "dine_in",
        }

        for ot in available:
            label_lower = ot.get("label", "").lower().strip()
            key = label_map.get(label_lower)
            if key and key not in self._order_type_ids:
                self._order_type_ids[key] = ot["id"]

        if not self._order_type_ids:
            # No label matched at all — use the first available as pickup so we
            # can still create orders. Developer must fix labels or extend label_map.
            self._order_type_ids["pickup"] = available[0]["id"]
            log.warning(
                "clover.order_types.no_label_match",
                found_labels=[ot.get("label") for ot in available],
                fallback_label=available[0].get("label"),
                fix="Rename your Clover order types to match expected labels, "
                    "or extend label_map in clover.py._fetch_order_types()",
            )

        # "pickup" must always exist — it's the fallback for any unrecognized order type
        if "pickup" not in self._order_type_ids:
            default_ot = next(
                (ot for ot in available if ot.get("isDefault")), available[0]
            )
            self._order_type_ids["pickup"] = default_ot["id"]
            log.warning(
                "clover.order_types.pickup_fallback",
                using_label=default_ot.get("label"),
            )

        log.info(
            "clover.order_types.ready",
            mapped=self._order_type_ids,
            all_labels=[ot.get("label") for ot in available],
        )

    def resolve_order_type_id(self, order_type: str) -> str:
        """
        Map a voice-agent order type string to a Clover order type ID.
        Falls back to "pickup" if the type isn't mapped.
        """
        key = order_type.lower().replace("-", "_").replace(" ", "_")
        if key not in self._order_type_ids:
            log.warning(
                "clover.order_type.unknown_falling_back_to_pickup",
                received=order_type,
            )
            key = "pickup"
        return self._order_type_ids[key]

    # ── Webhook + background sync ─────────────────────────────────────────────

    def verify_webhook(self, auth_header: str) -> bool:
        """
        Constant-time comparison of the X-Clover-Auth header value.
        Always returns False if CLOVER_WEBHOOK_SECRET is not configured.
        """
        if not self._webhook_secret:
            return False
        return hmac.compare_digest(auth_header, self._webhook_secret)

    def schedule_menu_reload(self) -> None:
        """
        Debounced full menu reload. Call this from the webhook handler on any
        inventory event (I, IC, IG, IM).

        Waits 2 seconds before reloading so that a burst of webhook events from
        a single batch update only triggers one network round-trip.
        """
        if self._reload_debounce_handle:
            self._reload_debounce_handle.cancel()

        loop = asyncio.get_event_loop()
        self._reload_debounce_handle = loop.call_later(2.0, self._trigger_reload)
        log.debug("clover.webhook.menu_reload_scheduled")

    def _trigger_reload(self) -> None:
        """Fire the reload task. Skip if a reload is already in flight."""
        if self._reload_task and not self._reload_task.done():
            log.debug("clover.webhook.reload_already_running_skipping")
            return
        self._reload_task = asyncio.create_task(
            self._reload_menu_safe(), name="clover-webhook-reload"
        )

    async def _reload_menu_safe(self) -> None:
        log.info("clover.menu.reload.started")
        try:
            raw_items = await self._load_all_items()
            await self.menu.replace_all(raw_items)
            self.available = True
            log.info("clover.menu.reload.done", item_count=self.menu.item_count())
        except CloverError as exc:
            log.warning("clover.menu.reload.failed", error=str(exc))

    async def _poll_loop(self) -> None:
        """
        Background delta-sync task.
        Runs every CLOVER_MENU_POLL_INTERVAL seconds (default 300 = 5 min).
        Fetches only items changed since the last successful sync — this is the
        safety net for webhook delivery failures.
        """
        log.info("clover.poll.started", interval_seconds=self._poll_interval)
        while True:
            try:
                await asyncio.sleep(self._poll_interval)

                if self.menu is None:
                    continue

                since = self.menu.last_sync_ts()
                raw_items = await self._load_delta_items(since)

                if raw_items:
                    await self.menu.apply_delta(raw_items)
                    log.info("clover.poll.delta_applied", changed_items=len(raw_items))
                else:
                    log.debug("clover.poll.no_changes")

                if not self.available and not self.menu.is_empty():
                    self.available = True
                    log.info("clover.poll.became_available")

            except asyncio.CancelledError:
                log.info("clover.poll.cancelled")
                return
            except CloverError as exc:
                log.warning("clover.poll.error", error=str(exc))

    def _start_reconnect_loop(self) -> None:
        """
        Start a background task that retries the full menu load every 60 seconds
        until Clover becomes reachable. Used when the initial menu load fails.
        """
        async def _reconnect() -> None:
            while not self.available:
                await asyncio.sleep(60)
                try:
                    if self.menu is None:
                        return
                    raw_items = await self._load_all_items()
                    await self.menu.replace_all(raw_items)
                    self.available = True
                    log.info("clover.reconnected", item_count=self.menu.item_count())
                except CloverError as exc:
                    log.warning("clover.reconnect.failed", error=str(exc))

        asyncio.create_task(_reconnect(), name="clover-reconnect")

    # ── Order creation ────────────────────────────────────────────────────────

    async def create_order(
        self,
        order_type: str,
        items: list[dict],
        customer_name: str = "",
        phone_number: str = "",
        special_instructions: str = "",
        delivery_address: str = "",
    ) -> CloverCreatedOrder:
        """Create a Clover POS order atomically.

        items: [{"name": str, "quantity": int, "price": float, "notes": str}]
        order_type: "pickup" | "delivery" | "dine_in"

        Raises CloverItemNotFoundError if any item cannot be resolved to a
        Clover catalog entry. Raises CloverOrderError / CloverError on API failures.
        """
        order_type_id = self.resolve_order_type_id(order_type)

        # Build human-readable order note for POS display
        note_parts: list[str] = []
        if phone_number:
            note_parts.append(f"Phone: {phone_number}")
        if delivery_address:
            note_parts.append(f"Deliver to: {delivery_address}")
        if special_instructions:
            note_parts.append(f"Note: {special_instructions}")
        spice_parts = [
            f"{item['name']} x{item.get('quantity', 1)}: {item.get('notes', '')}"
            for item in items
            if item.get("notes")
        ]
        if spice_parts:
            note_parts.append("Spice — " + " | ".join(spice_parts))

        order_body: dict = {"orderType": {"id": order_type_id}}
        if customer_name:
            order_body["title"] = customer_name[:64]
        if note_parts:
            order_body["note"] = "\n".join(note_parts)

        # Step 1: Create the order shell
        order_data = await self._request(
            "POST",
            f"/v3/merchants/{self._merchant_id}/orders",
            json_body=order_body,
        )
        order_id = order_data["id"]

        # Step 2: Add line items — Clover has no quantity field; one request per unit
        line_item_count = 0
        for item in items:
            if self.menu is None:
                raise CloverUnavailableError("Menu cache not ready")
            clover_item = self.menu.lookup(item["name"])
            if clover_item is None:
                raise CloverItemNotFoundError(item["name"])

            qty = max(1, int(item.get("quantity", 1)))
            for _ in range(qty):
                await self._request(
                    "POST",
                    f"/v3/merchants/{self._merchant_id}/orders/{order_id}/line_items",
                    json_body={"item": {"id": clover_item.id}},
                )
                line_item_count += 1

        # Step 3: Fetch final order to get server-computed total
        final = await self._request(
            "GET",
            f"/v3/merchants/{self._merchant_id}/orders/{order_id}",
        )

        log.info(
            "clover.order.created",
            order_id=order_id,
            order_type=order_type,
            customer=customer_name,
            line_items=line_item_count,
            total_cents=final.get("total", 0),
        )

        return CloverCreatedOrder(
            id=order_id,
            total_cents=final.get("total", 0),
            state=final.get("state", "open"),
            order_type_label=order_type,
            created_time=final.get("createdTime", 0),
            line_item_count=line_item_count,
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Cancel background tasks and close the HTTP client."""
        for task in (self._poll_task, self._reload_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if self._reload_debounce_handle:
            self._reload_debounce_handle.cancel()

        if self._http:
            await self._http.aclose()

        log.info("clover.closed")


# ── Module-level singleton ────────────────────────────────────────────────────
# main.py calls set_client() after init(). Everything else calls get_client().

_client: CloverClient | None = None


def set_client(client: CloverClient) -> None:
    global _client
    _client = client


def get_client() -> CloverClient:
    if _client is None:
        raise RuntimeError(
            "Clover client not initialized. "
            "Call set_client() in main.py after CloverClient.init()."
        )
    return _client
