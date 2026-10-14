# Deal Scout UI plan

Planning handoff · 14 October 2026. This is a design proposal, not the shipped feature list. See [technical architecture](ARCHITECTURE.md) for current behavior and the [README](../README.md) for setup. The app files now live at the repository root.

## Product direction

Make comparing a product across stores feel like one simple shopping task. The primary questions are: Where is the lowest price found? Is the item available? Which stores were checked? What changed since my last check?

Use one responsive page with three states: ready to search, checking stores, and results. Keep the existing plain HTML/CSS/JavaScript and Python server for this scope. A framework migration is unnecessary for this screen.

## Visual direction

- Retain the dark identity, but soften the current terminal-like presentation: charcoal canvas, slightly lighter surfaces, restrained emerald accents, generous spacing.
- Canvas #0B0F14; surface #141B24; border #2A3646; primary text #F3F6FA; secondary text #A6B2C3; emerald #34D399; amber #FBBF24; error #FCA5A5. Verify contrast in the implemented combinations.
- Emerald means a favorable price or a primary action. Amber means incomplete coverage or uncertain availability. Red is reserved for errors; a target hit is a success, not an amber warning.
- Use the system font stack, tabular numerals for prices, and a clear scale: 32–40px opening headline, 32px winning price, 20px section titles, 15–16px body, 13px secondary labels.
- Content width about 1120px; spacing steps 8/12/16/24/32px; 12–16px panel corners; subtle borders instead of heavy shadows or gradients.
- Use small store initials or simple text marks. Product photos are outside the existing data contract; the composition must work without them.

## Page layout and interaction

### 1. Header and search

Compact Deal Scout wordmark, a short “Powered by TinyFish” attribution, and a Recent checks anchor when history exists. Avoid a sidebar for this single-purpose tool.

Ready-state headline: “Find the best price across your stores.”
Supporting line: “Check live listings from Amazon, Flipkart, Croma and Reliance Digital.”

Search panel:
- Visible label “Product”; example placeholder “Sony WH-1000XM5”.
- Visible label “Target price (optional)”; rupee prefix, positive numeric input.
- Primary button “Compare prices”.
- Store selection as compact checkbox chips, all selected by default.
- Example-query buttons underneath; selecting one fills the input but does not start a run.
- Quiet explanation: “Checks prices when you search. Purchases stay with you.”

Keep the form compact above results. Preserve the submitted query, target, and store selection in a run snapshot so the result heading cannot accidentally describe subsequently edited inputs. Disable resubmission during a run; use inline errors for empty queries, invalid targets, or no selected stores.

### 2. Checking stores

Heading: “Checking 4 stores…” with elapsed time and a count of completed store checks. Do not invent a percentage or ETA.

Each selected store gets a compact card:
- Store name and explicit status: Queued, Browsing, Finished, or Couldn’t check.
- Latest reported activity as readable text.
- “Watch live” only when a streaming URL exists.
- Expandable “Activity” disclosure for the complete log.

Keep cards in the selected-store order so incoming events do not move them around. Use subtle motion and respect reduced-motion preferences. Do not repeatedly announce every log line to screen readers.

Current API: normalized offers arrive per store through `agent` events with `type: STORE_RESULT`, and again in the final `done` payload. The current UI renders each store as it finishes; aggregate comparison waits for `done`.

### 3. Results

Order content by decision value:
1. Query heading and coverage summary, e.g. “Prices found at 3 of 4 stores”.
2. Lowest-price summary with store, exact product title/variant, price, availability, target status, and “View deal”.
3. Comparison list containing all returned offers, grouped by store; default store order follows the cheapest eligible offer, with unavailable-only and failed stores after comparable stores.
4. Collapsed store activity.
5. Recent checks and previous prices, when present.

Label the summary “Lowest price found” rather than claiming the absolute best price on the market. If availability is unknown, say “Availability unconfirmed” next to the price. Exclude explicit out-of-stock offers from the winning offer, tie calculation, and savings calculation. If all offers are out of stock, show those offers with “No available offer found” instead of saying no products matched.

When stores tie, show both as equal-price options and give each its own View deal action. Do not arbitrarily imply that one tied store is better. Show full product titles and variants so users can judge whether listings are equivalent; omit cross-store savings when equivalence cannot be established from the returned data.

Comparison fields: Store / Product and variant / Price / MRP discount when supplied / Availability / View deal. Additional matches from a store can live behind “Show 2 more matches”. Keep all unavailable listings visibly marked and below eligible listings. Missing MRP, ratings, or URLs should leave no placeholder claims or broken actions.

Separate the two kinds of savings: “43% below listed MRP” and “₹7,501 less than Amazon’s matching offer” have different baselines. Only show a comparison if the data supports that exact wording. Do not imply taxes, delivery fees, memberships, or bank offers are included without corresponding evidence.

Target success copy: “Target met — ₹1,011 below your ₹21,000 target.” A history change can use “₹1,200 lower than your previous check” when the comparison is reliable. There is no background monitoring or notification subscription in the current backend; avoid “We’ll notify you” and “Track automatically”.

### 4. Open-deal confirmation

Preserve the existing confirmation step. Show store, full title, displayed price, and destination hostname. Buttons: “Cancel” and “Open product page”. Explanation: “Opens the store in a new tab. Checkout stays with you.” Support Escape, keyboard focus containment, and focus restoration. Validate outgoing URLs as HTTP(S) before using them.

### 5. Recent checks

The existing `/api/history` endpoint can support a compact list of previously searched queries, last recorded time, and “Search again”. Clicking Search again should refill the form and require an explicit Compare prices action.

History stores minimum prices per store, not complete products, variants, availability, or targets. In the initial UI, label figures “Previously recorded price”; do not portray them as a verified in-stock trend. A price chart and strong price-drop claims should wait for consistent availability/variant history. Targets and store selections cannot be restored from current history data. Timestamps currently lack a timezone offset; avoid assuming they are UTC or adding Z.

## Layout sketch

```text
Deal Scout                                     Recent checks

Find the best price across your stores.
[ Product __________________ ] [ Target ₹ ____ ] [ Compare prices ]
[✓ Amazon] [✓ Flipkart] [✓ Croma] [✓ Reliance Digital]

Sony WH-1000XM5                         Prices found at 3 of 4 stores
┌ Lowest price found ──────────────────────────────────────────────┐
│ ₹19,989  ·  Flipkart / Croma                                     │
│ Full product and variant title                 [ View deal ]     │
│ Availability · Target status · Equal-price alternatives          │
└──────────────────────────────────────────────────────────────────┘
Compare offers
Store       Product / variant        Price       Status     Action
...

▸ Store activity
Recent checks
```

Illustrative prices above come from the project’s recorded example, not a fresh live check. A shipped replay mode should have a persistent “Recorded demo” badge; it should not be labeled live merely because events are streamed.

## Responsive and accessibility requirements

- Above 1000px: search on one row, four progress cards, comparison columns.
- Between 640px and 1000px: two progress columns and a wrapped search form.
- Below 640px: stacked labeled inputs, full-width submit, single-column progress and offer cards; no horizontal comparison-table scrolling required.
- Preserve price, availability, and action on mobile. Wrap product titles instead of hiding the distinguishing variant.
- Minimum 44px interactive targets, visible focus indicators, native checkboxes/buttons, semantic headings, and status text in addition to color.
- Announce run start, completion, and errors through a polite live region. Avoid auto-scrolling or moving focus as results arrive.

## State and failure coverage

| State | User-facing treatment |
| --- | --- |
| Store catalogue loading/failure | Disable submission until store choices load; provide a retry for catalogue fetch failure. |
| First visit | Clear search form and examples; no empty result panels. |
| Store queued or browsing | Latest actual activity, elapsed time, optional live link. |
| Some stores fail | Keep successful results and name the stores without prices. |
| All checks fail | “Couldn’t check prices” with useful cause and explicit retry. |
| Successful check, no matches | “No matching products found”; suggest including a model or storage size. |
| All offers out of stock | Retain listings; no winning deal. |
| Availability unknown | “Availability unconfirmed”; never infer In stock. |
| Target missed | Show the gap to target neutrally, without an alarm. |
| Stream interrupted | Explain the interruption and close the browser EventSource; retry only on user action. |
| Missing API key | Setup-oriented error, with no key value printed or requested in the shopping form. |
| Recorded demo | Persistent badge and no unsupported active live-view link. |

On interruption, closing the browser stream does not cancel the backend worker. The current EventSource uses a GET endpoint that starts work, so automatic reconnect can trigger a second run. Prevent blind reconnect in the first pass; reliable reconnect/cancel requires explicit server support.

## Implementation handoff

### First pass: UI using existing endpoints

Change `ui.html` at the repository root: layout, visual tokens, labeled form, stable progress cards, condensed activity, result hierarchy, grouped offers, inline validation, confirmation polish, responsive states, and recent-query list. Keep `/api/stores`, `/api/scout`, and `/api/history` as the integration points.

Keep a small explicit UI state object: phase, submitted query/target/stores, startedAt, per-store activity, final results, and connection error. Use textContent for external text or consistent escaping; validate links independently of HTML escaping.

Do not deduce structured failure categories by loosely parsing arbitrary provider prose. Under the current contract, use a neutral “No prices returned” plus the supplied reason when the exact category is uncertain.

### Coordinate with Claude before backend-dependent polish

1. Add structured store outcome codes for success, no matches, blocked, and error. Currently `ok: false` covers both empty results and technical failures.
2. Add explicit run metadata: mode (live/replay), recorded source timestamp, run ID, and checked-at timestamp with timezone.
3. Normalize availability policy across best offer, ties, savings, and history. Current best-offer logic accepts unknown availability, while history minimums can include out-of-stock offers.
4. Add structured alert types instead of styling by matching English alert strings.
5. Normalized per-store results now arrive through `STORE_RESULT`. Add cancellation and resumable run lookup before offering Stop or automatic reconnect.
6. Store product/variant and availability context before presenting historical comparisons as like-for-like price drops.

### Review checklist

Use recorded or synthetic fixtures; UI review does not require paid live agent runs. Check ready, browsing, tied prices, target met/missed, one failed store, all failed, no matches, all out of stock, unknown stock, and interrupted stream. Verify keyboard operation, confirmation dismissal, long product names, and layouts at 375px, 768px, and 1440px.

First-pass success: a user can identify the lowest returned eligible price, availability caveats, incomplete store coverage, and the next action without opening activity logs. No production code was changed as part of this planning handoff.
