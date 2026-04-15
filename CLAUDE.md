# CLAUDE.md — AI Assistant Guide for Utbytte-Aksjer (exday.no)

## Project Overview

This is a Progressive Web App (PWA) for tracking Norwegian dividend-paying stocks listed on Oslo Børs (Oslo Stock Exchange). It is hosted on GitHub Pages at **exday.no** and has no server-side runtime — all logic runs in the browser or in scheduled GitHub Actions.

**Core capabilities:**
- Real-time and historical dividend data for 191 Norwegian stocks
- Personal portfolio tracking with cost basis (FIFO), IRR, TWR, and tax calculations
- Dividend calendar, sector filters, dividend score rankings, sector rebalancing tool
- Offline-capable via Service Worker; installable as PWA

---

## Repository Structure

```
Utbytte-Aksjer/
├── .github/workflows/         # GitHub Actions CI/CD
│   ├── update-og-deploy.yml   # Daily data fetch + GitHub Pages deploy
│   └── oppdater-priser.yml    # Price updates every 15 min on weekdays
├── assets/                    # All frontend JS and CSS
│   ├── app.js                 # Bootstrap, data loading, cache management, escHtml()
│   ├── storage.js             # localStorage abstraction layer
│   ├── ui.js                  # All UI rendering and DOM manipulation
│   ├── portefolje.js          # Portfolio math (FIFO, IRR, TWR, tax) + rebalancing
│   ├── consent.js             # Cookie consent + Google Analytics Consent Mode v2
│   ├── qrcode.min.js          # QR code library (vendored, no CDN dependency)
│   ├── style.css              # Custom CSS layered on Tailwind
│   ├── tailwind.css           # Generated/minified Tailwind v4 output
│   └── tw-input.css           # Tailwind config with brand colors
├── data/                      # JSON data files
│   ├── aksjer.json            # Auto-generated daily: full stock dataset
│   ├── tickers.json           # Manually maintained: 191 stock definitions
│   ├── priser.json            # Real-time prices, updated every 15 min
│   └── fallback_data.json     # Fallback when API fetch fails
├── scripts/                   # Python data pipeline
│   ├── fetch_stocks.py        # Main pipeline: Yahoo Finance → aksjer.json + SEO pages
│   ├── fetch_priser.py        # Lightweight price updater → priser.json
│   ├── regenerer_sider.py     # Regenerates /aksjer/{TICKER}/index.html without full fetch
│   ├── utvid_beskrivelser.py  # Enriches stock descriptions in tickers.json
│   ├── valider_data.py        # Data quality validation script
│   └── requirements.txt       # Python deps: yfinance>=0.2.36
├── tests/                     # Node.js unit tests
│   ├── portefolje.test.js     # Tests: FIFO, IRR, TWR
│   ├── storage.test.js        # Tests: favorites, watchlists
│   └── ui.test.js             # Tests: formatting, scoring, classification
├── aksjer/                    # Auto-generated SEO pages (one per stock ticker, 184 pages)
├── aksjer/sektor/             # Sector overview pages (16 sectors, auto-generated)
├── bevegelser/                # Stock movement history pages
├── faq/                       # FAQ pages
├── innstillinger/             # Settings page (/innstillinger/)
├── kalkulator/                # Calculator pages
├── personvern/                # Privacy policy (v3)
├── promo/                     # Promotional assets
├── uke/                       # Weekly data pages
├── utbyttekalender/           # Dividend calendar pages
├── utbyttekalkulator/         # Dividend calculator pages
├── index.html                 # Main SPA, all modal templates
├── manifest.json              # PWA manifest
├── sw.js                      # Service Worker (cache-first/network-first strategy)
├── sitemap.xml                # SEO sitemap (212 URLs)
├── robots.txt                 # Search engine directives
├── CNAME                      # Custom domain: exday.no
├── SECURITY_ROADMAP.md        # Security review findings and fix status
├── package.json               # npm scripts: test, build:css, watch:css
├── README.md                  # Project overview and setup instructions
├── ROADMAP.md                 # Planned features
├── ROADMAP_COMPLETED.md       # Completed features log
└── ROADMAP_NYE_IDEER.md       # Backlog of new ideas
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML5 + Vanilla JavaScript (no frameworks) + Tailwind CSS v4 |
| PWA | Service Worker + Web App Manifest |
| Analytics | Google Analytics with Consent Mode v2 |
| Monetization | Google AdSense |
| Data Pipeline | Python 3.12 + `yfinance` + DNB Markets scraping + Euronext CSV |
| CI/CD | GitHub Actions |
| Hosting | GitHub Pages |
| Testing | Node.js built-in `node:test` module |

**No build step for JavaScript** — files are served as-is. CSS is built with Tailwind CLI.

---

## Development Workflow

### Running Tests

```bash
npm test
```

### Building CSS

```bash
npm run build:css    # One-time build
npm run watch:css    # Watch mode during development
```

Tailwind input: `assets/tw-input.css` → output: `assets/tailwind.css`

### Python Data Scripts

```bash
pip install -r scripts/requirements.txt
python scripts/fetch_stocks.py        # Full fetch: aksjer.json + all SEO pages (~45 min)
python scripts/regenerer_sider.py     # Regenerate HTML pages only (fast, no Yahoo Finance)
python scripts/utvid_beskrivelser.py  # Expand descriptions in tickers.json
python scripts/fetch_priser.py        # Update priser.json
python scripts/valider_data.py        # Run data quality checks on aksjer.json
```

### Local Development

```bash
python -m http.server 8000
```

Note: The Service Worker requires HTTPS or `localhost` to function.

---

## Automated CI/CD (GitHub Actions)

### Daily Data Pipeline (`update-og-deploy.yml`)

- **Trigger:** Weekdays 07:00 UTC (08:00 CET) + manual `workflow_dispatch`
- **Steps:**
  1. `oppdater-data`: Runs `fetch_stocks.py`, commits updated `data/aksjer.json` and stock SEO pages to `main`
  2. `deploy-pages`: Bumps Service Worker cache version (`CACHE = 'exday-v{SHA}'`), deploys to GitHub Pages

### Real-Time Price Updates (`oppdater-priser.yml`)

- **Trigger:** Every 15 min, Mon–Fri 08:00–16:45 UTC + extra run at 17:00 UTC
- **Job:** Runs `fetch_priser.py`, commits `data/priser.json` if prices changed
- **Concurrency:** Cancels previous in-progress run to avoid queue buildup

**Important:** Many commits in git history are automated bot commits (`auto: oppdater kurspriser ...`). This is expected and normal.

---

## Key Coding Conventions

### Language

All variable names, function names, UI strings, and comments are in **Norwegian**. New code must follow this convention.

### JavaScript Style

- **`'use strict';`** at the top of every JS file — mandatory
- **camelCase** for all functions and variables
- **SCREAMING_SNAKE_CASE** for constants
- **No frameworks** — pure vanilla JS only
- **`escHtml(s)`** — always use this helper (defined in `app.js`) when interpolating string data into `innerHTML` template literals. Never interpolate untrusted strings directly.
- **Event delegation** — never use inline `onclick="..."` with interpolated data. Use `data-*` attributes and delegated listeners.
- **Module exports for tests**: guarded by `if (typeof module !== 'undefined')`

### HTML Conventions

- Semantic HTML with ARIA attributes
- HTML element IDs use prefixes: `pf-` (portfolio), `modal-`, `tab-`
- `data-*` attributes for semantic markers: `data-tab`, `data-ticker`
- JSON-LD structured data for SEO

### Data File Conventions

**`data/tickers.json`** — manually maintained, add new stocks here first:
```json
{
  "ticker_yf": "EQNR.OL",
  "ticker": "EQNR",
  "navn": "Equinor ASA",
  "sektor": "Energi",
  "bors": "Oslo Børs",
  "beskrivelse": "..."
}
```

**`data/aksjer.json`** — auto-generated by `fetch_stocks.py`, never edit manually.

---

## Architecture: Data Flow

```
tickers.json (manual, 191 stocks)
       ↓
fetch_stocks.py (daily GitHub Action)
       ↓
data/aksjer.json + /aksjer/{TICKER}/index.html (auto-generated, 184 pages)

fetch_priser.py (every 15 min)
       ↓
data/priser.json

Browser loads index.html
       ↓
app.js: fetch aksjer.json + priser.json → merge prices → window.alleAksjer
       ↓
ui.js: render tabs, filters, cards, modals, pagination (25/50/75/100/Alle)
       ↓
storage.js: read/write localStorage
       ↓
portefolje.js: FIFO, IRR, TWR, tax, sector rebalancing
```

---

## Portfolio Math (portefolje.js)

- **Cost basis:** FIFO — `beregnKostbasis()`
- **IRR:** Newton-Raphson numerical method
- **TWR:** Chain-links sub-period returns
- **Tax rate:** 37.84% effective rate above shield allowance (`SKJERMINGSRENTE`)
- **Sector rebalancing:** `visRebalansering()` — compares actual vs. target sector weights, shows kr-amount to buy/sell

---

## Security Notes (see SECURITY_ROADMAP.md)

- **`escHtml(s)`** is defined globally in `app.js` — use it for all string data in `innerHTML`
- **No inline `onclick` with interpolated data** — use `data-ticker` + event delegation
- **`urllib.parse.quote()`** used for all URL parameters in Python scripts
- **Ticker validation** — `_valider_ticker()` in `fetch_stocks.py` enforces `^[A-Z0-9]{1,10}$`
- **QRCode library is vendored** in `assets/qrcode.min.js` — no CDN dependency
- **CSP** is not yet implemented (GitHub Pages limitation — use `<meta>` tag when ready)

---

## localStorage Schema

| Key | Content |
|-----|---------|
| `fav_aksjer` | Starred tickers |
| `pf_portefoljer` | Portfolio names and holdings |
| `pf_transaksjoner` | Buy/sell transaction history |
| `pf_historikk` | Portfolio value time series |
| `pf_watchlister` | Custom watchlists |
| `pf_rebalansering` | Sector target weights (%) |
| `profil_navn` / `profil_sparemaal` / `profil_mal_mnd` | User profile / goals |
| `notif_aksjer` | Tickers with ex-date push notifications enabled |
| `sortering` | Sort preference |
| `paginering-per-side` | Stocks per page (25/50/75/100/0=all) |
| `tema` | Dark/light theme |
| `cookie_consent` | Cookie consent choice |

---

## Service Worker (sw.js)

- Cache name: `exday-v{GIT_SHA}` — auto-bumped on each deploy
- **Network-first** for JSON data (`aksjer.json`, `priser.json`)
- **Cache-first** for static assets

**Do not manually change the cache version string** — the deploy workflow updates it.

---

## SEO Pages

`/aksjer/{TICKER}/index.html`, `/aksjer/sektor/{slug}/index.html`, and `/aksjer/index.html` are **auto-generated**. Do not edit manually — changes are overwritten on the next daily run.

To modify the template, edit `scripts/fetch_stocks.py` or run `python scripts/regenerer_sider.py` after updating `tickers.json`.

### SEO Page Templates (in `scripts/fetch_stocks.py`)

There are **3 HTML templates** in `fetch_stocks.py`:

| Template | Function | Output | Dark mode |
|----------|----------|--------|-----------|
| Stock page | `_aksje_side_html()` | `/aksjer/{TICKER}/index.html` (184 pages) | ✓ Tailwind `dark:` classes |
| Sector page | `generer_sektorsider()` | `/aksjer/sektor/{slug}/index.html` (16 pages) | ✓ Tailwind `dark:` classes |
| Overview page | inline in `generer_aksjesider()` | `/aksjer/index.html` | ✓ Inline CSS `.dark` selectors |

**Key conventions for all 3 templates:**
- Dark mode init script reads `localStorage.getItem('tema')` (Norwegian key — matches main app)
- Dark mode toggle saves `localStorage.setItem('tema', 'dark'|'light')`
- Favicon block: `/favicon.png` (512), `/logo/apple_touch_icon_180.png`, SVG icon
- Footer: `STANDARD_FOOTER` constant (defined after `generer_aksjesider()`) — uses inline styles with `.dark .std-footer` override
- After changing any template: run `python scripts/regenerer_sider.py` to rebuild all pages

---

## Data Quality Checks

`scripts/valider_data.py` is a reusable validation script that reads `data/aksjer.json` and verifies data integrity after each data fetch.

### What it checks

- **Yield consistency:** `utbytte_yield` must equal `utbytte_per_aksje / pris * 100` within 0.5% tolerance (flags); avvik > 2% is a **critical error** (exits with code 1)
- **Implausibly high yields:** `utbytte_yield` > 60% is flagged as suspicious
- **5-year average yield:** `snitt_yield_5ar` > 200% is flagged as suspicious
- **Historical yields:** any entry in `historiske_utbytter` with yield > 200% is flagged
- **Forward vs. trailing mismatch:** `utbytte_per_aksje` > 5x the most recent year in `historiske_utbytter` is flagged (may indicate Yahoo is returning a forward estimate)

### Running manually

```bash
python scripts/valider_data.py
```

Exit code 0 = OK, exit code 1 = critical errors found.

### Automatic execution

The script runs automatically in the daily GitHub Actions workflow (`update-og-deploy.yml`) after `fetch_stocks.py` completes, before committing updated data. See the `Valider datakvalitet` step in the workflow.

---

## Known Yahoo Finance Data Quality Issues

This section documents recurring patterns where Yahoo Finance returns incorrect or misleading dividend data. These root causes are important to understand when investigating yield discrepancies (e.g. "our app shows 16% but Nordnet shows 10%").

### 1. Mixed-period payment stacking (WAWI-type)

**Symptom:** `utbytte_per_aksje` is inflated — roughly equal to the sum of the most recent two payment events from different periods.

**Root cause:** Yahoo's `dividendRate` sums recent payment events across calendar year boundaries. For stocks that pay semi-annually (one NOK payment in autumn + one USD payment in spring), Yahoo sums e.g. H2-2025 (NOK) + Q1-2026 (USD→NOK) and presents this as the "annual rate". Since `trailing_annual` (our cross-validation reference) computes the same sum, the 50%-deviation check doesn't catch it.

**How to detect:** `utbytte_per_aksje` ≈ `siste_utbytte` + previous period's `historiske_utbytter` entry. Nordnet shows a significantly lower current yield.

**Script mitigation:** Cross-validation now uses the last complete calendar year total as primary reference (not trailing 12 months). Also: `utbytte_per_aksje` is rounded to 2 decimal places on storage.

**Affected stocks:** WAWI (canonical example), potentially other mixed NOK/USD payers.

### 2. Stale USD/NOK exchange rate in dividend history

**Symptom:** Historical dividends stored in NOK show inflated/deflated amounts compared to what investors actually received in real-time.

**Root cause:** Yahoo Finance stores dividends for Oslo Børs stocks (`.OL` tickers) in NOK, converting USD-denominated dividends at the exchange rate at the time of payment. When the exchange rate changes significantly (e.g. USD weakens from 10.5 to 12.5 NOK/USD), the stored NOK values become stale. A dividend of 1.01 USD paid when USDNOK=9.45 is stored as 9.54 NOK, but at current USDNOK=12.5 it should be 12.63 NOK.

**How to detect:** `valuta` field may show "USD" even for `.OL` tickers (Yahoo uses corporate reporting currency). The discrepancy is visible by comparing displayed yield vs. Nordnet.

**Affected stocks:** WAWI, GOGL (USD), FLNG (USD), COOL (USD) — all companies that declare dividends in USD but trade on Oslo Børs in NOK.

**Note:** `valuta=USD` in our data for `.OL` stocks means the company reports in USD, not that prices or dividends are displayed in USD. Prices are always in NOK for `.OL` tickers.

### 3. Annualization inflation of single payment

**Symptom:** `utbytte_per_aksje` = `siste_utbytte` × payment_frequency_multiplier (2 for halvårlig, 4 for kvartalsvis), and this annualized value is much higher than the previous full year's total.

**Root cause:** Yahoo annualizes the most recent individual payment by multiplying by the assumed payment frequency. If a company recently raised its dividend significantly (e.g. KOG from ~1.1 NOK/quarter to 5.7 NOK/quarter), the annualized Yahoo figure (22.8) will be much higher than the previous year's total (4.4). This can be correct (genuine raise) or inflated (one-time special payment).

**How to detect:** `frekvens == "Kvartalsvis"` or `"Halvårlig"` and `utbytte_per_aksje` ≈ `siste_utbytte × freq_multiplier`. Compare against `historiske_utbytter` last full year.

**Affected stocks:** OET (quarterly tanker dividends), KOG (quarterly defense growth), SUBC (semi-annual offshore), others.

**Script mitigation:** Cross-validation now compares against last complete calendar year (not just trailing 12m), which will flag cases where the annualized rate is >50% higher than the prior full year.

### 4. Missing historical data (snitt_yield_5ar = None)

**Symptom:** `snitt_yield_5ar = None` or 0, and `historiske_utbytter = []`.

**Root cause:** `hent_historiske_utbytter()` requires both `dividends` and `hist_prices` to be non-empty. If `hist_prices` fails to fetch (network error, API limit), the function returns `[], 0.0`. Without `snitt_yield_5ar`, the sanity check (yield > 3× snitt) is bypassed, allowing inflated yields to pass through.

**Script mitigation:** The sanity check now falls back to `trailing_annual / pris × 100` as effective snitt when `snitt_yield_5ar = 0`.

**Affected stocks:** GOGL, FLNG, COOL (USD-reporting companies with potential hist_prices fetch issues).

### 5. payout_ratio artifacts

**Symptom:** `payout_ratio` shows values like 1197%, 1333%, 687%.

**Root cause:** When EPS is near zero or negative, Yahoo's payout_ratio = dividend/EPS produces huge values. These are mathematically correct but meaningless for users.

**Fix:** Values > 500% are zeroed out in the data pipeline.

### Historical yields design decision

**`historiske_utbytter.yield` is computed at the CURRENT stock price**, not the historical year-end price. This is a deliberate design choice for display consistency: a user comparing "2023 yield" to "current yield" is comparing at the same price base. This means:
- Historical yields will look different from what a 2023 investor actually earned
- For stocks with large price changes (HUNT: collapsed, KOG: tripled), historical yields may appear extreme
- `snitt_yield_5ar` is the average of these current-price-adjusted historical yields

### Duplicate tickers in tickers.json

**Each `ticker_yf` must be unique** — if two entries share the same `ticker_yf`, both will receive identical data from Yahoo Finance. Known incidents:
- **STRO** (removed 2026-04-15): duplicate of SNI (Stolt-Nielsen)
- **VENDA** (removed 2026-04-15): duplicate of VEND (Vend Marketplaces)
- **ODLD**: currently uses `ODLD.OL` — different company from ODL (Odfjell Drilling vs Odfjell SE), but may be delisted; needs verification on next data fetch

When adding new tickers, always verify `ticker_yf` is unique in `tickers.json`.

---

## Adding a New Stock

1. Add entry to `data/tickers.json`
2. Run `python scripts/utvid_beskrivelser.py` to generate description
3. Run `python scripts/regenerer_sider.py` to generate HTML pages
4. Commit — the next daily GitHub Action fetches fresh financial data

---

## Common Pitfalls

1. **Do not edit auto-generated files** — `data/aksjer.json`, `/aksjer/*/index.html` are overwritten daily
2. **CSS changes require rebuild** — run `npm run build:css` after changing `tw-input.css`
3. **No JS bundler** — frontend files share global scope via `<script>` tags
4. **Norwegian naming is mandatory** — all variables, functions, and UI text must be in Norwegian
5. **`'use strict';` is required** — every JS file must have this at the top
6. **Use `escHtml()` in innerHTML** — never interpolate raw stock data strings into HTML
7. **Price data is separate** — `priser.json` is merged into `alleAksjer` at runtime; prices are not in `aksjer.json`
8. **`window.alleAksjer`** is set in `lastInnData()` in `app.js` for cross-file access
