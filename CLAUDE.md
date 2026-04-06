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

`/aksjer/{TICKER}/index.html` and `/aksjer/sektor/{slug}/index.html` are **auto-generated**. Do not edit manually — changes are overwritten on the next daily run.

To modify the template, edit `scripts/fetch_stocks.py` or run `python scripts/regenerer_sider.py` after updating `tickers.json`.

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
