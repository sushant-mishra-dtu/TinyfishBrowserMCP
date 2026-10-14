# Setup and usage

[Project overview](../README.md) · [Technical architecture](ARCHITECTURE.md)

All commands in this guide run from the repository root, where `server.py`, `dealscout.py`, and `agent.py` live. Python 3.10 or newer is required. There are no third-party Python dependencies.

## Live setup

Create `.env` at the root with your TinyFish API key:

```dotenv
TINYFISH_API_KEY=your-key-here
```

The local loader accepts simple `NAME=value` lines and comment lines beginning with `#`. Use unquoted values: it does not implement shell expansion or strip surrounding quotes. Values already present in the environment win over `.env`.

Start the app:

```sh
python server.py
```

Open [http://localhost:8787](http://localhost:8787). Enter a product model, optionally enter a target price in INR, choose stores, and select **Scout prices**. Store cards show queued/browsing progress, live browser links when available, and offers as checks finish. The final summary appears when all selected checks finish. Product links open a confirmation dialog.

Use Ctrl+C in the server terminal to stop the local process. Closing a browser tab does not cancel its backend worker or guarantee cancellation of remote TinyFish runs.

## CLI

```sh
python dealscout.py "sony wh-1000xm5" --target 20000
python dealscout.py "iphone 16 128gb" --stores amazon flipkart --top 2 --parallel 2
python dealscout.py "sony wh-1000xm5" --target 18000 --every 360
python dealscout.py --help
```

| Argument | Default | Meaning |
| --- | --- | --- |
| `query` | Required | Product query; quote multiword queries. |
| `--target NUMBER` | None | Emit an alert when the best eligible price is at or below this INR amount. |
| `--stores KEY ...` | All four | Choose `amazon`, `flipkart`, `croma`, and/or `reliance`. |
| `--top INTEGER` | `3` | Number of matching offers requested per store in the agent goal. This is not a local result cap. |
| `--parallel INTEGER` | `4` | Maximum local scouting threads. Remote capacity can be lower. |
| `--every MINUTES` | None | Repeat checks, sleeping this long after each run completes. |
| `--yes-open` | Off | Open the best offer without the normal interactive prompt; applies only to a one-shot check. |

Use positive numbers for target, top, parallel, and interval values. The CLI does not comprehensively validate their ranges. Watch mode runs immediately, prints alerts to the terminal, and continues until stopped with Ctrl+C. It never opens offer pages, even with `--yes-open`; it does not install a background service or send notifications.

A one-shot check exits with `0` when an eligible best offer exists, `2` when none exists, or `1` for a `TinyFishError` caught at the CLI boundary. Most per-store failures are captured as store results, so missing credentials or all stores failing usually lead to `2`. Argument parsing errors also use `2`.

## Offline replay

```sh
python server.py --replay
```

Search for the exact bundled query **sony wh-1000xm5**. The replay runner matches the generated store search URL against records in `recordings/*.json`; a different query or capitalization can fail to match. It emits recorded steps with short delays and never calls the TinyFish API. No API key is needed.

For CLI replay in PowerShell:

```powershell
$env:DEALSCOUT_REPLAY = "1"
python dealscout.py "sony wh-1000xm5" --target 20000
Remove-Item Env:DEALSCOUT_REPLAY
```

For CLI replay in a POSIX shell:

```sh
DEALSCOUT_REPLAY=1 python dealscout.py "sony wh-1000xm5" --target 20000
```

Any nonempty value enables replay, including `0`. Unset the variable to return to live mode. Replay displays `[replay]` in activity messages but has no persistent demo badge, and its normal summary wording should not be read as a fresh quote. It does not emit a live streaming URL.

**Replay writes to the same `price_history.json` as live checks.** If you need to preserve a live-only history, back up and temporarily move that file before a demo, then restore it after stopping the app. Runtime file paths are resolved beside `agent.py`, not from the shell's working directory.

## Configuration

| Variable | Default | Use |
| --- | --- | --- |
| `TINYFISH_API_KEY` | Unset | Required for live API calls; sent as `X-API-Key`. |
| `TINYFISH_API_BASE` | `https://agent.tinyfish.ai` | Override the API base URL. Only point this at a trusted service because it receives the API key. |
| `DEALSCOUT_MAX_SECONDS` | `240` | Integer browsing budget after a `STREAMING_URL` event. Read when `agent.py` is imported. |
| `DEALSCOUT_REPLAY` | Unset | Any nonempty value selects saved recordings. |

The web server uses fixed port `8787` and binds to `127.0.0.1`. Its scouting defaults are three requested offers and four local workers. The CLI can override these through `--top` and `--parallel`.

## History and alerts

`price_history.json` is created automatically and ignored by Git. Queries are keyed by their trimmed, lowercase text. Each query retains at most 50 runs. Each run stores a local timestamp without a timezone offset and the minimum returned price per store.

Drops and rises are compared against the immediately preceding run for that query. A store absent from that previous run has no baseline. Targets are evaluated for the current run, not saved as subscriptions. History includes unavailable offers and does not store titles, variants, URLs, or availability, so a change is not necessarily a like-for-like price change. Avoid running multiple writers simultaneously: file updates are not locked.

## Claude Code and TinyFish MCP

The repository contains [`.claude/skills/deal-scout/SKILL.md`](../.claude/skills/deal-scout/SKILL.md). With a TinyFish connector configured in Claude Code, an example request is `scout sony wh-1000xm5 under 20000`.

The skill uses `run_web_automation_async` and `get_run` rather than the Python server. Its instructions currently use two concurrent runs and approximately 30-second polling. The Python app uses its own API credentials and SSE client; configuring one route does not configure the other. The skill references the root `agent.py` schema and root history file.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Missing API key | Add the key to root `.env` or the process environment, then restart the server. Do not put it in the search form. |
| HTTP 401/403 | Check account access and credentials. Non-busy HTTP 4xx errors are not retried. |
| Queued or HTTP 429/503 | Account capacity may be busy. The client waits 15 seconds between busy retries, up to four retries. |
| Store timed out | The client attempts remote cancellation after its browsing budget. Other stores continue; the configured budget does not cover queue time. |
| Captcha, unavailable product, or no matches | Read the store's reason and try a more specific model. Partial comparisons remain usable. |
| No recording for this store/query | Use the exact bundled query or disable replay for a live check. |
| Lost connection | The UI closes the stream to prevent automatic duplicate checks. Retrying starts new work; the earlier worker may still be running. |
| Port already in use | Stop the existing Deal Scout instance before launching another on port 8787. |
| Unexpected historical alert | Check whether a replay or different variant affected the previous run. |

## Local verification without live calls

Run `python dealscout.py --help`, then start `python server.py --replay` and search for the bundled query. Confirm that successful stores show offers, Reliance reports its recorded unavailable-product reason, and an offer click opens the confirmation dialog. A target of `20000` should trigger an alert from the saved eligible price of Rs 19,989. These are fixture expectations, not current store prices.

There is no checked-in automated test suite. Changes to paths should also be checked against `.claude/launch.json` and the connector skill.
