"""Deal Scout CLI.

  python dealscout.py "sony wh-1000xm5"
  python dealscout.py "iphone 16 128gb" --target 65000 --stores amazon flipkart
  python dealscout.py "sony wh-1000xm5" --target 18000 --every 360   # watch every 6h
"""
from __future__ import annotations

import argparse
import sys
import webbrowser

from agent import STORES, TinyFishError, best_offer, record_and_compare, scout

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Compare a product's price across Indian stores with TinyFish web agents.")
    p.add_argument("query", help='product to look for, e.g. "boat airdopes 141"')
    p.add_argument("--target", type=float, help="alert me if the best price is at or below this (INR)")
    p.add_argument("--stores", nargs="+", choices=list(STORES), default=list(STORES))
    p.add_argument("--top", type=int, default=3, help="listings per store")
    p.add_argument("--parallel", type=int, default=4)
    p.add_argument("--yes-open", action="store_true", help="skip the confirmation before opening the best deal")
    p.add_argument("--every", type=float, metavar="MINUTES", help="keep watching: re-check every N minutes and report drops")
    a = p.parse_args()

    if a.every:
        import time
        print(f"Watching '{a.query}' every {a.every:g} min. Ctrl+C to stop. (Watch mode never opens or buys anything.)")
        while True:
            check(a, interactive=False)
            time.sleep(a.every * 60)
    return check(a, interactive=True)


def check(a, interactive: bool) -> int:

    print(f"\nDeal Scout: '{a.query}' across {', '.join(STORES[s]['name'] for s in a.stores)}\n")

    def on_event(store: str, ev: dict):
        t = ev.get("type")
        if t == "STARTED":
            print(f"  [{store}] agent started (run {ev.get('run_id')})")
        elif t == "STREAMING_URL":
            print(f"  [{store}] watch live: {ev.get('streaming_url')}")
        elif t == "PROGRESS":
            print(f"  [{store}] {ev.get('purpose')}")
        elif t == "COMPLETE":
            print(f"  [{store}] finished: {ev.get('status')}")

    try:
        results = scout(a.query, a.stores, a.top, a.parallel, on_event)
    except TinyFishError as e:
        print(f"\nError: {e}")
        return 1

    print("\n" + "=" * 78)
    for r in sorted(results, key=lambda r: min((o.price for o in r.offers), default=1e12)):
        if not r.ok:
            print(f"\n{r.store}: could not get prices ({r.error}) [{r.seconds}s]")
            continue
        print(f"\n{r.store}  [{r.seconds}s]")
        for o in sorted(r.offers, key=lambda o: o.price):
            disc = f"  ({o.discount_pct}% off MRP Rs {o.mrp:,.0f})" if o.discount_pct else ""
            stock = "  OUT OF STOCK" if o.in_stock is False else ""
            print(f"  Rs {o.price:>9,.0f}  {o.title[:60]}{disc}{stock}")

    best = best_offer(results)
    hist = record_and_compare(a.query, results, a.target)
    print("\n" + "=" * 78)
    if hist["alerts"]:
        print("\nAlerts:")
        for al in hist["alerts"]:
            print(f"  * {al}")
    elif hist["runs"] > 1:
        print("\nNo price change since your last check.")

    failed = [r.store for r in results if not r.ok]
    if failed:
        print(f"\nNote: {', '.join(failed)} could not be checked this time; comparison uses the remaining stores.")

    if not best:
        print("\nNo offers found. Try a more specific product name.")
        return 2

    print(f"\nBEST DEAL: Rs {best.price:,.0f} on {best.store}\n  {best.title}\n  {best.url}")
    print("\nDeal Scout never buys, adds to cart or logs in for you.")
    if best.url and interactive:
        ok = a.yes_open or input("Open this product page in your browser so you can decide? [y/N] ").strip().lower() == "y"
        if ok:
            webbrowser.open(best.url)
            print("Opened. Checkout is up to you.")
        else:
            print("Okay, not opening anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
