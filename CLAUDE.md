# CLAUDE.md — AI Assistant Guide for Utbytte-Aksjer (exday.no)

## Project Overview

This is a Progressive Web App (PWA) for tracking Norwegian dividend-paying stocks listed on Oslo Børs (Oslo Stock Exchange). It is hosted on GitHub Pages at **exday.no** and has no server-side runtime — all logic runs in the browser or in scheduled GitHub Actions.

**Core capabilities:**
- Real-time and historical dividend data for 124+ Norwegian stocks
- Personal portfolio tracking with cost basis (FIFO), IRR, TWR, and tax calculations
- Dividend calendar, sector filters, dividend score rankings
- Offline-capable via Service Worker; installable as PWA

---

## Repository Structure

```
Utbytte-Aksjer/
├── .github/workflows/         # GitHub Actions CI/CD
│   ├── update-og-deploy.yml   # Daily data fetch + GitHub Pages deploy
│   └── oppdater-priser.yml    # Price updates every 15 min on weekdays
├── assets/                    # All frontend JS and CSS
│   ├── app.js                 # Bootstrap, data loading, cache management
│   ├── storage.js             # localStorage abstraction layer
│   ├── ui.js                  # All UI rendering and DOM manipulation
│   ├── portefolje.js          # Portfolio math (FIFO, IRR, TWR, tax)
│   ├── consent.js             # Cookie consent + Google Analytics Consent Mode v2
│   ├── style.css              # Custom CSS layered on Tailwind
│   ├── tailwind.css           # Generated/minified Tailwind v4 output
│   └── tw-input.css           # Tailwind config with brand colors
├── data/                      # JSON data files
│   ├── aksjer.json            # Auto-generated daily: full stock dataset (167 KB)
│   ├── tickers.json           # Manually maintained: 124 stock definitions
│   ├── priser.json            # Real-time prices, updated every 15 min
│   └── fallback_data.json     # Fallback when API fetch fails
├── scripts/                   # Python data pipeline
│   ├── fetch_stocks.py        # Main pipeline: Yahoo Finance → aksjer.json + SEO pages
│   ├── fetch_priser.py        # Lightweight price updater → priser.json
│   ├── regenerer_sider.py     # Regenerates /aksjer/{TICKER}/index.html pages
│   ├── utvid_beskrivelser.py  # Enriches stock descriptions
│   └── requirements.txt       # Python deps: yfinance>=0.2.36
├── tests/                     # Node.js unit tests
│   ├── portefolje.test.js     # 13 tests: FIFO, IRR, TWR
│   ├── storage.test.js        # 7 tests: favorites, watchlists
│   └── ui.test.js             # 17+ tests: formatting, scoring, classification
├── aksjer/                    # Auto-generated SEO pages (one per stock ticker)
├── sektor/                    # Sector overview pages (auto-generated)
├── bevegelser/                # Stock movement history pages
├── faq/                       # FAQ pages
├── innstillinger/             # Settings page (/innstillinger/)
├── kalkulator/                # Calculator pages
├── personvern/                # Privacy policy
├── promo/                     # Promotional assets
├── uke/                       # Weekly data pages
├── utbyttekalender/           # Dividend calendar pages
├── utbyttekalkulator/         # Dividend calculator pages
├── index.html                 # Main SPA (1,338 lines), all modal templates
├── manifest.json              # PWA manifest
├── sw.js                      # Service Worker (cache-first/network-first strategy)
├── sitemap.xml                # SEO sitemap (69+ URLs)
├── robots.txt                 # Search engine directives
├── CNAME                      # Custom domain: exday.no
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
| Data Pipeline | Python 3.12 + `yfinance` + DNB Markets scraping |
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

Runs 37 unit tests using Node.js built-in test runner. All tests must pass before committing changes to core logic files (`portefolje.js`, `storage.js`, `ui.js`).

### Building CSS

```bash
npm run build:css    # One-time build
npm run watch:css    # Watch mode during development
```

Tailwind input: `assets/tw-input.css` → output: `assets/tailwind.css`

### Python Data Scripts

```bash
pip install -r scripts/requirements.txt
python scripts/fetch_stocks.py       # Regenerates data/aksjer.json and SEO pages
python scripts/fetch_priser.py       # Updates data/priser.json
```

### Local Development

There is no local dev server configured. Open `index.html` directly in a browser, or serve with any static server:

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

All variable names, function names, UI strings, and comments are in **Norwegian**. New code must follow this convention. Examples:
- `portefølje` (portfolio), `utbytte` (dividend), `aksjer` (stocks)
- `ex_dato` (ex-date), `betaling_dato` (payment date)
- `hentPF()` (fetch portfolio), `lagrePF()` (save portfolio)

### JavaScript Style

- **`'use strict';`** at the top of every JS file — mandatory
- **camelCase** for all functions and variables: `beregnKostbasis()`, `aktivTab`, `visFeilBanner()`
- **SCREAMING_SNAKE_CASE** for constants: `CACHE_NØKKEL`, `SKJERMINGSRENTE`, `SEKTOR_FARGE`
- **No frameworks** — pure vanilla JS only
- **Global state** in `app.js`/`ui.js`: `let alleAksjer = []`, `let aktivTab = 'oversikt'`
- **Module exports for tests**: Each file exports its testable functions via `module.exports = { ... }` guarded by `if (typeof module !== 'undefined')`
- **Event delegation** pattern for dynamic DOM: `document.addEventListener('click', e => { if (e.target.matches(...)) })`

### HTML Conventions

- Semantic HTML with ARIA attributes (`role="dialog"`, `aria-sort`, `aria-label`)
- HTML element IDs use prefixes: `pf-` (portfolio), `modal-`, `tab-`
- `data-*` attributes for semantic markers: `data-tab="portfolio"`, `data-ticker="EQNR"`
- JSON-LD structured data in `<script type="application/ld+json">` for SEO

### CSS Conventions

- **Utility-first Tailwind v4** — prefer Tailwind classes over custom CSS
- **Dark mode** via class strategy: `dark:` prefix (e.g., `dark:bg-slate-800`)
- Brand green: `#16a34a` (mapped to `green-600`)
- Semantic colors: green = buy/positive, red = sell/loss, yellow = dividend
- Custom styles go in `assets/style.css` — keep minimal

### Data File Conventions

**`data/tickers.json`** — manually maintained, add new stocks here first:
```json
{
  "ticker_yf": "EQNR.OL",   // Yahoo Finance ticker
  "ticker": "EQNR",          // Short Oslo Børs ticker
  "name": "Equinor ASA",
  "sektor": "Energi",
  "exchange": "OSE",
  "description": "..."
}
```

**`data/aksjer.json`** — auto-generated by `fetch_stocks.py`, never edit manually:
```json
{
  "ticker": "EQNR",
  "navn": "Equinor ASA",
  "sektor": "Energi",
  "pris": 399.1,
  "utbytte_yield": 3.71,
  "payout_ratio": 76.0,
  "ex_dato": "2026-05-13",
  "betaling_dato": "2026-05-27",
  "rapport_dato": "2026-05-06",
  "historiske_utbytter": [
    { "ar": 2025, "utbytte": 19.16, "yield": 8.19 }
  ],
  "ar_med_utbytte": 25
}
```

---

## Architecture: Data Flow

```
tickers.json (manual)
       ↓
fetch_stocks.py (daily GitHub Action)
       ↓
data/aksjer.json + /aksjer/{TICKER}/index.html (auto-generated)

fetch_priser.py (every 15 min)
       ↓
data/priser.json

Browser loads index.html
       ↓
app.js: fetch aksjer.json + priser.json → merge prices
       ↓
ui.js: render tabs, filters, cards, modals
       ↓
storage.js: read/write localStorage (portfolios, favorites, watchlists, transactions)
       ↓
portefolje.js: calculate IRR, TWR, cost basis, tax
```

---

## Portfolio Math (portefolje.js)

Key financial calculations — do not change without updating tests:

- **Cost basis:** FIFO (First In, First Out) — `beregnKostbasis(transaksjoner, ticker)`
- **IRR (Internal Rate of Return):** Newton-Raphson numerical method
- **TWR (Time-Weighted Return):** Chain-links sub-period returns
- **Tax rate:** 37.84% effective rate on gains above shield allowance (`SKJERMINGSRENTE`)
- **Dividend income:** Aggregated from transaction log entries of type `"utbytte"`

---

## localStorage Schema (storage.js)

All user data lives in `localStorage`. Key names:

| Key | Content |
|-----|---------|
| `pf_data` | Array of portfolio objects with name and metadata |
| `pf_transaksjoner` | Object keyed by portfolio ID → array of transactions |
| `pf_favoritter` | Array of ticker strings marked as favorites |
| `pf_watchlist` | Array of ticker strings in watchlist |
| `pf_notater` | Object keyed by ticker → user notes string |
| `pf_innstillinger` | User settings (dark mode, sort preference, etc.) |
| `pf_notifikasjoner` | Push notification subscription data |
| `pf_streak` | Visit streak counter and last-visit date |

---

## Service Worker (sw.js)

- Cache name format: `exday-v{GIT_SHA}` — bumped automatically on each deploy
- **Network-first** for JSON data files (`aksjer.json`, `priser.json`)
- **Cache-first** for static assets (JS, CSS, images)
- Old caches are deleted on SW activation

**When modifying sw.js:** The cache version is auto-bumped by the deploy workflow — do not manually change the version string.

---

## SEO Pages (`/aksjer/` and `/sektor/`)

These 124+ HTML files are **auto-generated** by `fetch_stocks.py` / `regenerer_sider.py`. Do not edit them manually — changes will be overwritten on the next daily run.

To modify the template for these pages, edit the generation logic in `scripts/fetch_stocks.py` or `scripts/regenerer_sider.py`.

---

## Adding a New Stock

1. Add an entry to `data/tickers.json` with `ticker_yf`, `ticker`, `name`, `sektor`, `exchange`, and `description`
2. Run `python scripts/fetch_stocks.py` locally to verify data fetches correctly
3. Commit the updated `tickers.json` — the next daily GitHub Action will auto-generate the rest

---

## Testing Guidelines

- Tests use Node.js built-in `node:test` and `assert/strict` — no external test libraries
- `localStorage` is mocked with an in-memory store in each test file
- DOM elements are stubbed to `null` or empty — tests must not depend on real DOM
- Browser globals (`window`, `document`) are shimmed before importing modules
- Run `npm test` and ensure all 37 tests pass before pushing changes to logic files

---

## Common Pitfalls

1. **Do not edit auto-generated files** — `data/aksjer.json`, `/aksjer/*/index.html`, `/sektor/*/index.html` are overwritten daily
2. **CSS changes require rebuild** — run `npm run build:css` after changing `tw-input.css` or adding new Tailwind classes not already in `tailwind.css`
3. **No JS bundler** — there are no imports/exports between frontend files; they share a global scope via `<script>` tags in `index.html`
4. **Norwegian naming is mandatory** — all new variables, functions, and UI text must be in Norwegian to match the existing codebase
5. **`'use strict';` is required** — every JS file must have this at the top
6. **localStorage is the only persistence** — there is no backend database; all user data is client-side only
7. **Price data is separate from stock data** — `priser.json` is merged into `alleAksjer` at runtime in `app.js`; do not assume prices are in `aksjer.json`

---

## File Size Reference

| File | Size | Notes |
|------|------|-------|
| `assets/ui.js` | ~2,825 lines | Largest file; contains all rendering logic |
| `assets/portefolje.js` | ~1,619 lines | Portfolio math and calculations |
| `index.html` | ~1,338 lines | Main SPA with all modal templates |
| `scripts/fetch_stocks.py` | ~96 KB | Main data pipeline |
| `data/aksjer.json` | ~167 KB | Auto-generated stock dataset |
| `data/tickers.json` | ~81 KB | Manual stock definitions (124 stocks) |
