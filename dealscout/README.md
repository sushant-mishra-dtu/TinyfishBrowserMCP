# Deal Scout — a personal price agent on TinyFish

**What it does:** you type what you want to buy ("sony wh-1000xm5", "boat airdopes 141",
"iphone 16 128gb"). Deal Scout launches one TinyFish web agent per store — Amazon.in, Flipkart,
Croma, Reliance Digital — **in parallel**, on the live sites. Each agent dismisses popups, reads the
real search results, skips accessories and junk listings, and returns structured prices. You get a
ranked comparison, the best deal, % off MRP, and an alert when the price drops below your last
check or hits your target price.

**Who it's for:** anyone (students especially) who opens four tabs and compares prices before every
purchase — headphones, phones, laptops, festival-sale shopping. Run it again tomorrow and it tells you
whether the price moved.

**It never buys.** No login, no add-to-cart, no checkout. The only action after a search is opening
the product page, and that waits for you to confirm.

## How TinyFish is used

| Piece | TinyFish feature |
|---|---|
| One browser agent per store, live web, multi-step (open search, dismiss popups, read listings, filter out accessories, extract) | **Agent API** `POST /v1/automation/run-sse` with `browser_profile: "stealth"` |
| Clean JSON back, no scraping code or CSS selectors | `output_schema` on every run |
| Live progress in the UI + "watch the agent" link | SSE `PROGRESS` and `STREAMING_URL` events |
| Same workflow inside Claude Code | TinyFish **MCP connector** (`run_web_automation_async` + `get_run`) via the `deal-scout` skill |

Because the goal is natural language, it works for **any product query**, not a hardcoded page.

## Real results from live runs (14 Oct 2026, "sony wh-1000xm5")

| Store | Cheapest found | Note |
|---|---|---|
| Flipkart | Rs 19,989 (MRP 34,990, 43% off) | |
| Croma | Rs 19,989 | in stock, 3 colours |
| Amazon.in | Rs 27,490 | **Rs 7,501 more** |
| Reliance Digital | — | agent opened the only matching listing (Rs 17,990) and found it *"Currently unavailable online"*, so it was excluded instead of shown as the best deal |

Bugs the live runs caught (and fixes):

- The first prompt asked for "the top 3" matches; when a store had only one real match the agent
  returned nothing. The goal now says "up to 3 … even if it is only one".
- On Amazon, one agent kept re-sorting and paging for 8+ minutes. The goal now says "first results
  page only, read prices from the cards", and any store still browsing after 240s
  (`DEALSCOUT_MAX_SECONDS`) has its TinyFish run cancelled and is reported as timed out.
- After a server restart, the browser's EventSource auto-reconnected and silently started a second
  scout (more credits spent). The UI now never auto-reconnects, and cancelled runs are never retried.

## Failure handling

- A store that errors or times out is retried once (system errors only), then reported as
  "couldn't check X" — the comparison continues with the stores that worked.
- Captcha / no matching results: the agent returns an empty list with a `blocked_reason`;
  Deal Scout shows that reason instead of inventing a price.
- Out-of-stock listings are shown but never picked as "best deal".
- Missing API key or network errors are reported clearly.
- TinyFish concurrency limit: extra runs queue on TinyFish's side. The UI says "waiting for a
  TinyFish browser" until a browser is free, and HTTP 429/503 responses are retried with backoff.
- Each store's card fills in as soon as that store finishes, so one slow site doesn't hide the others.

## Run it

Put your key in `dealscout/.env` (gitignored) as `TINYFISH_API_KEY=sk-tinyfish-...`, or export it.

```bash
python server.py                          # web UI at http://localhost:8787
python dealscout.py "sony wh-1000xm5" --target 20000
python dealscout.py "boat airdopes 141" --stores amazon flipkart
```

No dependencies beyond the Python 3.10+ standard library.

`DEALSCOUT_REPLAY=1 python server.py` replays real recorded TinyFish runs from `recordings/`
(for offline demos — clearly marked `[replay]` in the UI log).

### In Claude Code (TinyFish MCP connector)

With the TinyFish connector enabled, open this folder in Claude Code and say
"scout sony wh-1000xm5 under 20000". The `.claude/skills/deal-scout` skill runs the same
workflow through the connector.

## Files

- `agent.py` — TinyFish SSE client, store configs, parallel scouting, parsing, price history
- `server.py` + `ui.html` — live web UI
- `dealscout.py` — CLI
- `price_history.json` — created on first run; powers price-drop alerts
