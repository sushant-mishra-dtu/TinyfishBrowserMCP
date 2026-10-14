"""Deal Scout web UI: python server.py  ->  http://localhost:8787

Streams each store's TinyFish agent progress live to the browser.
"""
from __future__ import annotations

import json
import queue
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agent import STORES, TinyFishError, best_offer, record_and_compare, results_to_json, scout, _load_history

UI = Path(__file__).with_name("ui.html")
PORT = 8787


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(u.query)
        if u.path == "/":
            return self._send(200, UI.read_bytes(), "text/html; charset=utf-8")
        if u.path == "/api/stores":
            return self._send(200, json.dumps({k: v["name"] for k, v in STORES.items()}).encode(), "application/json")
        if u.path == "/api/history":
            return self._send(200, json.dumps(_load_history()).encode(), "application/json")
        if u.path == "/api/scout":
            return self._scout(qs)
        self._send(404, b"not found", "text/plain")

    def _scout(self, qs):
        query = (qs.get("q", [""])[0]).strip()
        if not query:
            return self._send(400, b"missing q", "text/plain")
        stores = [s for s in qs.get("stores", [",".join(STORES)])[0].split(",") if s in STORES] or list(STORES)
        target = qs.get("target", [""])[0]
        target = float(target) if target else None

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        events: queue.Queue = queue.Queue()

        def emit(kind: str, data: dict):
            events.put((kind, data))

        def worker():
            try:
                results = scout(query, stores, 3, 4, lambda store, ev: emit("agent", {"store": store, **ev}))
                hist = record_and_compare(query, results, target)
                best = best_offer(results)
                emit("done", {
                    "results": results_to_json(results),
                    "best": best.__dict__ if best else None,
                    "alerts": hist["alerts"],
                    "runs": hist["runs"],
                })
            except TinyFishError as e:
                emit("fatal", {"error": str(e)})
            except Exception as e:
                emit("fatal", {"error": repr(e)})
            events.put(None)

        threading.Thread(target=worker, daemon=True).start()
        try:
            while True:
                try:
                    item = events.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                if item is None:
                    break
                kind, data = item
                self.wfile.write(f"event: {kind}\ndata: {json.dumps(data)}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    import os, sys
    if "--replay" in sys.argv:
        os.environ["DEALSCOUT_REPLAY"] = "1"
        print("REPLAY MODE: serving recorded real TinyFish runs from recordings/")
    print(f"Deal Scout running at http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
