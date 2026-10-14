# Submission — Deal Scout (DTU: Personal Agents on TinyFish)

[Project overview](../README.md) · [Setup and usage](USAGE.md) · [Technical architecture](ARCHITECTURE.md)

Run commands below from the repository root. Prices in this document describe the saved example, not current quotes. Live results can differ; use `python server.py --replay` with `sony wh-1000xm5` for a reproducible recorded demo. Replay is marked in activity messages and writes to the same local history as live checks.

## Short explanation (paste into the form)

**Deal Scout** is my personal price agent. I type a product ("sony wh-1000xm5") and it sends four
TinyFish browser agents in parallel to Amazon.in, Flipkart, Croma and Reliance Digital. Each agent
works the live site — dismisses popups, reads the search results, skips accessories, and returns
structured prices via `output_schema`. Deal Scout ranks them, shows % off MRP, saves price history,
and alerts me when a price drops or hits my target.

**Who it's for:** students and anyone who compares four tabs before buying electronics, especially
around sales. It's a weekly errand that now takes one command.

**How TinyFish is used:** TinyFish Agent API (`/v1/automation/run-sse`, stealth browser,
`output_schema`) does all navigation and extraction; SSE `PROGRESS` / `STREAMING_URL` events power a
live dashboard where you can watch each agent. The same workflow also ships as a Claude Code skill that
runs through the TinyFish MCP connector.

**Purchase boundary:** agent instructions prohibit login, cart, and payment actions. Opening the best deal in the UI requires confirmation; the CLI prompts by default and offers an explicit `--yes-open` override. Failed or captcha-blocked stores are reported with the supplied reason and the comparison continues with the rest. Unknown availability can remain eligible, so the store page is the final check.

**Works across inputs:** any product query, any subset of stores, optional target price.

## 60-second demo recording script

1. `python server.py` and open http://localhost:8787 (blur nothing personal here — no login is used).
2. Type **sony wh-1000xm5**, target **21000**, click *Scout prices*. Show 4 cards going live, click one
   **▶ watch the agent live** link to show the TinyFish browser working.
3. For the saved Sony example: Rs 19,989 on Flipkart/Croma, a Rs 7,501 displayed difference against Amazon.in, and a TARGET HIT alert. Reliance reports its only match unavailable. Explain that these are recorded observations and that the comparison does not verify equivalent variants or final checkout costs. For a live run, describe the actual returned values instead.
4. Click *Open this deal…* → show the confirmation ("will not add to cart, log in, or pay") → *Not now*.
5. In live mode, run a second product (e.g. **apple airpods pro 2**) to show query-driven extraction. The bundled replay supports only its recorded Sony query.
6. Terminal: `python dealscout.py "sony wh-1000xm5" --target 18000 --every 360` (watch mode).

Screenshots are in [screenshots/](screenshots/). The architecture and API contract are documented in [ARCHITECTURE.md](ARCHITECTURE.md).

## LinkedIn post (draft)

Built a personal agent at the @TinyFish × DTU workshop: **Deal Scout** 🛒

I always open Amazon, Flipkart, Croma and Reliance Digital in four tabs before buying anything.
Now I type the product once and four TinyFish web agents do it in parallel on the live sites —
closing popups, skipping accessory listings, pulling real prices as clean JSON.

✅ Ranked comparison + % off MRP
✅ Price-history alerts ("dropped ₹1,200 since yesterday")
✅ Target-price alerts
✅ Never buys or logs in — opening the deal waits for my confirm

Built on the TinyFish Agent API (SSE streaming + output_schema) and also runs as a Claude Code
skill through the TinyFish MCP connector.

#TinyFish #AIAgents #WebAgents #DTU #BuildInPublic

## X post (draft)

Built Deal Scout at the @Tiny_Fish × DTU workshop 🐟

Type a product → 4 TinyFish web agents hit Amazon, Flipkart, Croma & Reliance Digital in parallel
→ live prices, best deal, price-drop alerts.

Never buys anything. You confirm before it even opens the page.

#AIAgents #TinyFish

> Check TinyFish's exact handle on X/LinkedIn before posting so the tag resolves.
