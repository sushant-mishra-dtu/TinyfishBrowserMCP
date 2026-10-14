"""Deal Scout core: runs TinyFish web agents across Indian stores in parallel,
normalises the results, tracks price history and flags drops.

Never buys anything. The only post-search action (opening the best deal) is
gated behind an explicit user confirmation in the CLI / UI.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

# Load TINYFISH_API_KEY etc. from a local .env (kept out of git).
_env = Path(__file__).with_name(".env")
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.lstrip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

API_BASE = os.environ.get("TINYFISH_API_BASE", "https://agent.tinyfish.ai")
HISTORY_FILE = Path(__file__).with_name("price_history.json")

# Each store: how to build a search URL. The agent does the rest (popups,
# scrolling, reading prices) — no CSS selectors, so this works for any query.
STORES = {
    "amazon": {
        "name": "Amazon.in",
        "search": "https://www.amazon.in/s?k={q}",
    },
    "flipkart": {
        "name": "Flipkart",
        "search": "https://www.flipkart.com/search?q={q}",
    },
    "croma": {
        "name": "Croma",
        "search": "https://www.croma.com/searchB?q={q}%3Arelevance&text={q}",
    },
    "reliance": {
        "name": "Reliance Digital",
        "search": "https://www.reliancedigital.in/products?q={q}",
    },
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "price": {"type": "number"},
                    "mrp": {"type": "number"},
                    "rating": {"type": "string"},
                    "in_stock": {"type": "boolean"},
                    "url": {"type": "string"},
                },
                "required": ["title", "price"],
            },
        },
        "blocked_reason": {"type": "string"},
    },
    "required": ["products"],
}

GOAL = (
    'You are on the {store} search results page for "{query}". '
    "If a login, location or cookie popup appears, close or dismiss it (do NOT log in). "
    "Look at the search results and pick UP TO {n} listings that are actually "
    '"{query}" (skip sponsored accessories, cases, cables or unrelated items). '
    "If fewer than {n} match, return just the ones that do, even if it is only one. "
    "Work from the first results page only: do not change the sort order or go to page 2, and "
    "read prices from the result cards instead of opening each product page. "
    "Exception: open the product page of the single cheapest match to confirm it can be bought "
    "online (set in_stock false if it says out of stock, sold out or currently unavailable). "
    "For each, extract: title, current selling price in INR as a plain number, "
    "MRP/original price as a number if shown, rating text if shown, whether it is in stock, "
    "and the absolute product URL. "
    "Do NOT add anything to the cart, do NOT click buy, do NOT enter any personal details. "
    "Only if the page is blocked by a captcha or shows no matching results at all, return an empty "
    "products list and explain in blocked_reason."
)


@dataclass
class Offer:
    store: str
    title: str
    price: float
    mrp: Optional[float] = None
    rating: Optional[str] = None
    in_stock: Optional[bool] = None
    url: Optional[str] = None

    @property
    def discount_pct(self) -> Optional[float]:
        if self.mrp and self.mrp > self.price:
            return round(100 * (self.mrp - self.price) / self.mrp, 1)
        return None


@dataclass
class StoreResult:
    store: str
    ok: bool
    offers: list[Offer] = field(default_factory=list)
    error: Optional[str] = None
    run_id: Optional[str] = None
    streaming_url: Optional[str] = None
    seconds: float = 0.0


class TinyFishError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("TINYFISH_API_KEY")
    if not key:
        raise TinyFishError(
            "TINYFISH_API_KEY is not set. Get one at https://agent.tinyfish.ai/api-keys"
        )
    return key


def run_agent_sse(
    url: str,
    goal: str,
    output_schema: Optional[dict] = None,
    on_event: Optional[Callable[[dict], None]] = None,
    stealth: bool = True,
    timeout: int = 300,
    max_browse_seconds: int = int(os.environ.get("DEALSCOUT_MAX_SECONDS", "240")),
) -> dict:
    """Run one TinyFish agent and stream its events. Returns the COMPLETE event."""
    body = {
        "url": url,
        "goal": goal,
        "browser_profile": "stealth" if stealth else "lite",
        "api_integration": "dealscout",
    }
    if output_schema:
        body["output_schema"] = output_schema
    req = urllib.request.Request(
        f"{API_BASE}/v1/automation/run-sse",
        data=json.dumps(body).encode(),
        headers={
            "X-API-Key": _api_key(),
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise TinyFishError(f"HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise TinyFishError(f"Network error: {e.reason}") from e

    browsing_since = None
    run_id = None
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                event = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            run_id = event.get("run_id") or run_id
            if event.get("type") == "STREAMING_URL":
                browsing_since = time.time()
            if on_event:
                on_event(event)
            if event.get("type") == "COMPLETE":
                return event
            # Don't let one site hold up the whole comparison (heartbeats keep this loop ticking).
            if browsing_since and time.time() - browsing_since > max_browse_seconds:
                _cancel(run_id)
                raise TinyFishError(f"Timed out after {max_browse_seconds}s on the site; cancelled the run")
    raise TinyFishError("Stream ended without a COMPLETE event")


def _cancel(run_id: Optional[str]) -> None:
    if not run_id:
        return
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"{API_BASE}/v1/runs/{run_id}/cancel", data=b"{}", method="POST",
            headers={"X-API-Key": _api_key(), "Content-Type": "application/json"}), timeout=15).close()
    except Exception:
        pass


RECORDINGS = Path(__file__).with_name("recordings")


def _replay_run(url: str, goal: str, output_schema=None, on_event=None, **_) -> dict:
    """Offline demo mode (DEALSCOUT_REPLAY=1): replays real TinyFish runs saved in
    recordings/*.json, so the UI can be shown without spending credits."""
    recs = []
    for f in RECORDINGS.glob("*.json"):
        recs.extend(json.loads(f.read_text(encoding="utf-8")))
    rec = next((r for r in recs if r["url"] == url), None)
    if rec is None:
        raise TinyFishError("No recording for this store/query (replay mode). Unset DEALSCOUT_REPLAY to run live.")
    emit = on_event or (lambda e: None)
    emit({"type": "STARTED", "run_id": rec["run_id"]})
    for step in rec.get("steps", ["Opening search page", "Reading results"]):
        time.sleep(1.2)
        emit({"type": "PROGRESS", "purpose": f"[replay] {step}"})
    time.sleep(0.8)
    done = {"type": "COMPLETE", "run_id": rec["run_id"], "status": rec["status"], "result": rec.get("result"), "error": rec.get("error")}
    emit(done)
    return done


def _num(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    digits = re.sub(r"[^\d.]", "", str(v).split("-")[0])
    try:
        n = float(digits)
        return n if n > 0 else None
    except ValueError:
        return None


def parse_offers(store: str, result: Optional[dict], base_url: str) -> list[Offer]:
    if not result:
        return []
    # Agents sometimes wrap output; accept {"products": [...]}, {"result": {...}} or a list.
    if isinstance(result, dict) and "products" not in result:
        for v in result.values():
            if isinstance(v, dict) and "products" in v:
                result = v
                break
            if isinstance(v, list):
                result = {"products": v}
                break
    items = result.get("products", []) if isinstance(result, dict) else result
    offers = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        price = _num(it.get("price"))
        title = (it.get("title") or "").strip()
        if not price or not title:
            continue
        link = it.get("url")
        if link and not link.startswith("http"):
            link = urllib.parse.urljoin(base_url, link)
        offers.append(
            Offer(
                store=store,
                title=title,
                price=price,
                mrp=_num(it.get("mrp")),
                rating=str(it["rating"]) if it.get("rating") else None,
                in_stock=it.get("in_stock"),
                url=link,
            )
        )
    return offers


def scout_store(
    store_key: str,
    query: str,
    top_n: int = 3,
    on_event: Optional[Callable[[str, dict], None]] = None,
    retries: int = 1,
) -> StoreResult:
    store = STORES[store_key]
    url = store["search"].format(q=urllib.parse.quote_plus(query))
    goal = GOAL.format(store=store["name"], query=query, n=top_n)
    start = time.time()
    res = StoreResult(store=store["name"], ok=False)

    def relay(ev: dict):
        if ev.get("type") == "STARTED":
            res.run_id = ev.get("run_id")
        if ev.get("type") == "STREAMING_URL":
            res.streaming_url = ev.get("streaming_url")
        if on_event:
            on_event(store["name"], ev)

    runner = _replay_run if os.environ.get("DEALSCOUT_REPLAY") else run_agent_sse
    attempt = 0
    while True:
        try:
            done = runner(url, goal, OUTPUT_SCHEMA, relay)
        except TinyFishError as e:
            res.error = str(e)
            busy = "HTTP 429" in str(e) or "HTTP 503" in str(e)
            # Concurrency limit / busy: wait and retry a few times. Other 4xx (bad key) won't fix themselves.
            if busy and attempt < 4:
                if on_event:
                    on_event(store["name"], {"type": "PROGRESS", "purpose": "TinyFish busy, waiting for a free browser..."})
                time.sleep(15)
                attempt += 1
                continue
            if attempt < retries and "HTTP 4" not in str(e) and "Timed out" not in str(e):
                time.sleep(3)
                attempt += 1
                continue
            break
        attempt += 1
        if done.get("status") == "COMPLETED":
            result = done.get("result") or {}
            res.offers = parse_offers(store["name"], result, url)
            res.ok = bool(res.offers)
            if not res.ok:
                reason = result.get("blocked_reason") if isinstance(result, dict) else None
                res.error = reason or "No matching products found"
                # Empty list with no explanation is usually a flaky extraction: try once more.
                if not reason and attempt <= retries:
                    if on_event:
                        on_event(store["name"], {"type": "PROGRESS", "purpose": "Agent returned nothing without a reason, retrying once"})
                    continue
            break
        res.error = done.get("error") or done.get("help_message") or done.get("status")
        if done.get("status") != "CANCELLED" and attempt <= retries:
            if on_event:
                on_event(store["name"], {"type": "PROGRESS", "purpose": f"Retrying after: {res.error}"})
            continue
        break
    res.seconds = round(time.time() - start, 1)
    return res


def scout(
    query: str,
    stores: Optional[list[str]] = None,
    top_n: int = 3,
    max_parallel: int = 4,
    on_event: Optional[Callable[[str, dict], None]] = None,
) -> list[StoreResult]:
    stores = stores or list(STORES)
    results: list[StoreResult] = []
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futs = {pool.submit(scout_store, s, query, top_n, on_event): s for s in stores}
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as e:  # never let one store kill the whole comparison
                r = StoreResult(store=STORES[futs[f]]["name"], ok=False, error=repr(e))
            results.append(r)
            if on_event:
                on_event(r.store, {"type": "STORE_RESULT", "result": results_to_json([r])[0]})
    return results


def best_offer(results: list[StoreResult]) -> Optional[Offer]:
    offers = [o for r in results for o in r.offers if o.in_stock is not False]
    return min(offers, key=lambda o: o.price) if offers else None


# ---------- price history / drop alerts ----------

def _load_history() -> dict:
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def record_and_compare(query: str, results: list[StoreResult], target: Optional[float] = None) -> dict:
    """Saves this run's cheapest price per store and returns alerts vs the previous run."""
    hist = _load_history()
    key = query.strip().lower()
    entry = hist.setdefault(key, {"runs": []})
    prev = entry["runs"][-1]["prices"] if entry["runs"] else {}

    now_prices = {}
    for r in results:
        if r.offers:
            now_prices[r.store] = min(o.price for o in r.offers)

    alerts = []
    for store, price in now_prices.items():
        old = prev.get(store)
        if old and price < old:
            alerts.append(f"{store}: price DROPPED from Rs {old:,.0f} to Rs {price:,.0f} (-Rs {old - price:,.0f})")
        elif old and price > old:
            alerts.append(f"{store}: price went up from Rs {old:,.0f} to Rs {price:,.0f}")
    best = best_offer(results)
    if target and best and best.price <= target:
        alerts.append(f"TARGET HIT: {best.store} has it at Rs {best.price:,.0f} (your target Rs {target:,.0f})")

    entry["runs"].append({"at": datetime.now().isoformat(timespec="seconds"), "prices": now_prices})
    entry["runs"] = entry["runs"][-50:]
    HISTORY_FILE.write_text(json.dumps(hist, indent=2), encoding="utf-8")
    return {"alerts": alerts, "previous": prev, "runs": len(entry["runs"])}


def results_to_json(results: list[StoreResult]) -> list[dict]:
    out = []
    for r in results:
        d = asdict(r)
        for o, od in zip(r.offers, d["offers"]):
            od["discount_pct"] = o.discount_pct
        out.append(d)
    return out
