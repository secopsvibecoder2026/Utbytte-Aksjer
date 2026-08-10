# CLAUDE.md — AI Assistant Guide for Utbytte-Aksjer (exday.no)

## Project Overview

This is a Progressive Web App (PWA) for tracking Norwegian dividend-paying stocks listed on Oslo Børs (Oslo Stock Exchange). It is hosted on GitHub Pages at **exday.no** and has no server-side runtime — all logic runs in the browser or in scheduled GitHub Actions.

---

## Project Color Palette

**IMPORTANT: This project uses green as its primary brand color — NOT the Arctic organization colors.**

> ### ⛔ Arctic branding is strictly off-limits in this project
>
> exday.no is a **standalone, private project** — it is NOT an Arctic deliverable and has no
> connection to the Arctic brand, templates or visual identity. The Arctic colours mentioned in
> the organization context (Navy `#132A50`, Teal `#2E7B7B`, LightBlue `#91C4D8`, DarkTeal
> `#1E5C5C`, RedAccent `#8B2020`) and any Arctic document/page templates must **NEVER** be used
> anywhere in this repository. This applies to **every surface**:
>
> - Hand-written HTML pages (`index.html`, `om/`, `faq/`, `artikler/`, `verktoy/`, …)
> - **Generated page templates in `scripts/fetch_stocks.py`** (stock/sector/overview/toppliste
>   templates) — colours placed here propagate to 180+ pages on the next regeneration
> - Promo images (`promo/`), logos, CSS (`assets/`), inline styles and SVG
>
> **Incident log:** Arctic colours leaked into the SEO templates in `fetch_stocks.py` and
> `om/index.html`; removed 2026-07-05. Before committing design changes, verify with:
>
> ```bash
> grep -rn -i "132A50\|1E5C5C\|2E7B7B\|91C4D8\|8B2020" --include="*.html" --include="*.css" --include="*.js" --include="*.py" .
> ```
>
> This must return zero hits (documentation files excepted).

| Role | Light mode | Dark mode | Tailwind class |
|------|-----------|-----------|----------------|
| Primary action / CTA | `#22c55e` (green-500) | `#22c55e` | `bg-green-500` |
| Primary hover | `#16a34a` (green-600) | `#16a34a` | `bg-green-600` |
| Dark emphasis | `#15803d` (green-700) | `#15803d` | `text-green-700` |
| Hero accent / stats | `#86efac` (green-300) | `#86efac` | `text-green-300` |
| Active tab/link | `#15803d` / `#16a34a` | `#4ade80` | `text-green-700` |
| Link text | `#16a34a` (green-600) | `#4ade80` (green-400) | `text-green-600 dark:text-green-400` |
| Background tint | `#f0fdf4` (green-50) | `rgba(20,83,45,0.2)` | `bg-green-50` |
| Border accent | `#bbf7d0` (green-200) | `#166534` (green-800) | `border-green-200` |
| Hero gradient | `linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #15803d 100%)` | — | — |
| PWA theme-color | `#16a34a` | — | — |

Gray scale (UI chrome, text, borders) uses standard Tailwind gray: `gray-50`→`gray-950`.

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
│   ├── aksjer.json            # Auto-generated daily: full stock dataset (uten kurs_historikk)
│   ├── kurs/{TICKER}.json     # Auto-generated: kurshistorikk, lastes on-demand
│   ├── tickers.json           # Manually maintained: 191 stock definitions
│   ├── priser.json            # Real-time prices, updated every 15 min
│   ├── fallback_data.json     # Fallback when API fetch fails
│   ├── hentelogg.json         # Auto-generated: per-ticker fetch diagnostics
│   ├── ticker_status.json     # Auto-generated: stale-ticker state across runs
│   └── ticker_varsler.json    # Auto-generated: current stale-ticker alerts
├── scripts/                   # Python data pipeline
│   ├── fetch_stocks.py        # Main pipeline: Yahoo Finance → aksjer.json + SEO pages
│   ├── fetch_priser.py        # Lightweight price updater → priser.json
│   ├── regenerer_sider.py     # Regenerates /aksjer/{TICKER}/index.html without full fetch
│   ├── utvid_beskrivelser.py  # Enriches stock descriptions in tickers.json
│   ├── valider_data.py        # Data quality validation script
│   ├── sjekk_utdaterte.py     # Detects delisted/renamed/duplicate tickers
│   ├── test_sjekk_utdaterte.py # Tests for sjekk_utdaterte.py (stdlib unittest)
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
python scripts/sjekk_utdaterte.py     # Detect delisted/renamed/duplicate tickers
python scripts/test_sjekk_utdaterte.py  # Tests for the stale-ticker checks
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

## Artikler (`/artikler/`)

Artikler ligger i `artikler/{slug}/index.html`. Indekssiden er `artikler/index.html`.

### Mal og krav

- **1 500–3 000 ord** med ekte, nyttig innhold — ingen fluffy fyll
- **Norsk** — all tekst, overskrifter og kodekommentarer
- **Dark mode** via `localStorage.getItem('tema')` (ikke `theme`) — samme nøkkel som hoved-appen
- **Tailwind CSS** via `/assets/tailwind.css` + `/assets/style.css`
- **Google AdSense og Analytics** — kopier head-blokken fra `faq/index.html` nøyaktig
- **JSON-LD** — bruk `@type: "Article"` med `datePublished`, `dateModified`, `author`, `publisher`
- **Breadcrumb** — `exday.no › Artikler › Artikkeltittel`
- **Innholdsfortegnelse** — lenker til `id`-ankere for artikler over 5 seksjoner

### Standard bunntekst — bruk alltid denne eksakt

```html
<footer class="mt-8 sm:mt-12 border-t border-gray-200 dark:border-gray-800 py-6 text-center text-xs text-gray-400 dark:text-gray-600 space-y-1 px-4">
  <p>Kurs og utbyttedata hentes fra Yahoo Finance og Euronext. Oppdateres daglig på børsdager.</p>
  <p class="max-w-xl mx-auto leading-relaxed">
    exday.no er ikke et verdipapirforetak og tilbyr ikke finansiell rådgivning.
    Data kan inneholde feil eller forsinkelser — verifiser alltid mot Oslo Børs eller selskapets egne rapporter.
    Historisk utbytte er ingen garanti for fremtidig utbytte.
    Gjør alltid din egen analyse før du tar investeringsbeslutninger.
  </p>
  <p class="mt-2">
    <a href="/personvern/" class="underline hover:text-gray-400 dark:hover:text-gray-400 transition-colors">Personvern og informasjonskapsler</a>
    <span class="mx-2">·</span>
    <a href="/faq/" class="underline hover:text-gray-400 dark:hover:text-gray-400 transition-colors">Vanlige spørsmål (FAQ)</a>
  </p>
  <p class="mt-3">
    <a href="https://www.facebook.com/share/17rMp8o9yF/?mibextid=wwXIfr" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1.5 text-gray-400 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">
      <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M22 12c0-5.523-4.477-10-10-10S2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.878v-6.987h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.988C18.343 21.128 22 16.991 22 12z"/></svg>
      Følg exday.no på Facebook
    </a>
  </p>
</footer>
```

### Tabeller på mobil

Tabeller må alltid ha `display: block; overflow-x: auto; -webkit-overflow-scrolling: touch;` for å scrolle horisontalt på mobil.

### "Les også"-lenker

Bruk `flex items-center gap-2` med ikon + tekst på én linje. Ikke legg beskrivelsestekst inline etter lenken — det bryter dårlig på mobil.

### Oppdater indekssiden

Etter at en ny artikkel er ferdig: legg til et klikkbart kort under «Publisert» i `artikler/index.html` med tittel, ingress og dato. Flytt det tilhørende «Kommer snart»-kortet ut.

### Gjør artikkelen synlig i appen

Appen (`/app/`) har ingen automatisk kobling til `/artikler/` — den leser en egen
liste. Legg derfor artikkelen inn i **`ARTIKLER`-konstanten øverst i `assets/ui.js`**
(nyeste først). Det er én kilde til sannhet som driver to steder:

1. **«Lær»-undertaben** under Verktøy — viser hele listen
2. **Aksjemodalen** — viser artikkelen nederst i Oversikt-panelet for aksjer i
   sektorene du oppgir

```js
{
  slug: '/artikler/min-nye-artikkel/',
  tittel: '…', ingress: '…', meta: '9. august 2026 · 11 min',
  tags: ['Sektor', 'Guide'],
  sektorer: ['Havbruk'],   // tomt array = ingen kontekstuell lenke i modalen
}
```

`sektorer` må matche `sektor`-verdien i `data/aksjer.json` eksakt (f.eks. `Finans`,
`Shipping`, `Skipsfart`, `Havbruk`). Feil verdi feiler stille — artikkelen dukker
bare aldri opp i modalen.

### Sitemap: legg URL-en i generatoren, ikke i filen

Artikkel-URL-ene er **hardkodet i `generer_sitemap()` i `scripts/fetch_stocks.py`**.
`sitemap.xml` er autogenerert, så redigerer du bare filen, forsvinner artikkelen
neste gang `fetch_stocks.py` eller `regenerer_sider.py` kjører. Legg URL-en inn i
listen i generatoren.

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

## Detecting Outdated Tickers (delisted / renamed / acquired)

`scripts/sjekk_utdaterte.py` catches tickers that have gone stale because the company was
delisted, renamed, acquired or merged. Without it these failures are **silent**:

- `fetch_stocks.py` uses the name from `tickers.json` and never compares it against the name
  Yahoo Finance actually returns → renames are invisible.
- When a fetch fails, the pipeline falls back to the previous run's data indefinitely →
  delistings are invisible.

Historic incidents this covers: STRO/SNI and VENDA/VEND duplicates, the phantom ODLD ticker,
COOL's delisting in Jan 2026, and ABL Group → Aqualis (AQUA) in Jun 2026.

### How it works

`fetch_stocks.py` writes per-ticker diagnostics to `data/hentelogg.json` on every run
(Yahoo's own company name, market cap, last trade date, success/failure). `sjekk_utdaterte.py`
reads that log, compares it against state from earlier runs in `data/ticker_status.json`, and
writes alerts to `data/ticker_varsler.json`.

**State is measured in days, not runs**, so thresholds mean the same thing regardless of how
often the workflow fires.

### Checks

| Check | Trigger | Severity | Needs history |
|---|---|---|---|
| `duplikat_ticker_yf` | Two entries share a `ticker_yf` | kritisk | No |
| `duplikat_navn` | Two entries share a company name | kritisk | No |
| `ingen_data` | In `tickers.json` but no row in `aksjer.json` | kritisk | No |
| `identiske_data` | Two tickers with identical price/dividend/52w | kritisk | No |
| `navneendring` | Yahoo's name differs from ours (<60 % similar) | advarsel → kritisk after 2 days | Yes |
| `mulig_avnotering` | No successful fetch for 7 days | kritisk | Yes |
| `hentefeil` | No successful fetch for 3 days | advarsel | Yes |
| `fastfrosset_kurs` | Last trade ≥ 5 trading days ago | advarsel | No |
| `markedsverdi_borte` | Market cap disappeared since last run | advarsel | Yes |

The four checks that need no history work from the existing data files, so the script is useful
on the very first run — before any `hentelogg.json` exists.

### Name comparison

`normaliser_navn()` strips legal forms (ASA, Ltd, PLC, Holding …) before comparing, so
"Equinor ASA" vs "Equinor" is a match. Share-class markers are **preserved** — "Wilh. Wilhelmsen
Holding" and "… Holding B" must not collapse to the same string. A prefix match counts as
identical, since Yahoo is often more or less verbose than our catalog.

### Running manually

```bash
python scripts/sjekk_utdaterte.py            # normal run, always exits 0
python scripts/sjekk_utdaterte.py --streng   # exit 1 on critical alerts
python scripts/sjekk_utdaterte.py --tort     # analyse without writing state files
python scripts/sjekk_utdaterte.py --issue-tekst  # markdown body for the GitHub issue
```

### Automatic execution and alerting

Runs in `update-og-deploy.yml` after `valider_data.py`. It **deliberately does not block the
deploy** — a renamed company must not stop price updates. Instead:

1. Alerts go to the GitHub Actions job summary as a markdown table.
2. The `Varsle om utdaterte aksjer` step keeps a single issue (label `utdaterte-aksjer`)
   up to date, and **closes it automatically** once all critical alerts are gone.

Tests live in `scripts/test_sjekk_utdaterte.py` (stdlib `unittest`, no network, no pytest):

```bash
python scripts/test_sjekk_utdaterte.py
```

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
- **ODLD** (removed 2026-07-03): phantom `ODLD.OL` entry — Odfjell Drilling's real Oslo Børs ticker is **ODL**. The old **ODL** entry was mislabelled as "Odfjell SE"; corrected to **Odfjell Drilling Ltd** (sektor Energitjenester). Odfjell SE remains as **ODF** (A-aksje) + **ODFB** (B-aksje, added 2026-07-03).

### Ticker corrections / delistings (2026-07-03)

- **COOL** (removed): Cool Company delisted from Oslo Børs 20 Jan 2026 (merged into EPS Ventures, cash $9.65/share).
- **ABL → AQUA**: ABL Group ASA renamed to **Aqualis ASA** (new ticker `AQUA`, effective 17 Jun 2026). `ticker_yf` updated to `AQUA.OL`.

### Ticker corrections / delistings (2026-08-09)

Found by the first run of `scripts/sjekk_utdaterte.py` — all six had been failing
silently, some for over three years, while the fallback logic kept serving old data.

- **JAEDR → JAREN** (corrected, not removed): Jæren Sparebank is still listed and trading.
  The ticker was simply wrong — Oslo Børs uses `JAREN` (ISIN NO0010359433), and `JAEDR.OL`
  resolves to nothing. This *restores* a stock that had been missing from the site.
- **FKRAFT** (removed): Fjordkraft Holding ASA renamed to **Elmera Group ASA** on
  26 Apr 2022. `ELMRA` was already in the catalog, so this was a stale duplicate.
- **HDLG** (removed): Höegh LNG Holdings delisted from Oslo Børs in May 2021, taken
  private by Larus Holding (Leif Höegh & Co / Morgan Stanley Infrastructure Partners).
  Not to be confused with **HAUTO** (Höegh Autoliners), which is a separate live company.
- **NOFI** (removed): Norway Royal Salmon merged into SalMar, delisted 8 Nov 2022.
  `SALM` covers it.
- **TOTG** (removed): phantom entry — listed as "Tidewater Inc.", a NYSE company (`TDW`).
  `TOTG.OL` has never existed on Oslo Børs. Same class of error as the old ODLD entry.
- **WALWIL** (removed): duplicate of **WAWI** (Wallenius Wilhelmsen ASA) with an identical
  company name but a dead `ticker_yf`.

All six were also listed in `sitemap.xml` while having no page on disk, so the live sitemap
advertised six 404s. `generer_sitemap()` now requires the page to exist on disk before
including a ticker — a transient fetch failure still keeps yesterday's page in the sitemap,
but a permanently dead ticker drops out.

When adding new tickers, always verify `ticker_yf` is unique in `tickers.json`, and confirm the ticker/name matches the current Oslo Børs / Euronext listing (companies get renamed, merged and delisted).

---

## Adding a New Stock

1. Add entry to `data/tickers.json`
2. Run `python scripts/utvid_beskrivelser.py` to generate description
3. Run `python scripts/regenerer_sider.py` to generate HTML pages
4. Commit — the next daily GitHub Action fetches fresh financial data

---

## Common Pitfalls

1. **Do not edit auto-generated files** — `data/aksjer.json`, `/aksjer/*/index.html`, `sitemap.xml` and the aksjeliste inside the `<noscript>` block in `app/index.html` (between the `AKSJELISTE:START`/`AKSJELISTE:SLUTT` markers) are all overwritten by `fetch_stocks.py` / `regenerer_sider.py`
2. **CSS changes require rebuild** — run `npm run build:css` after changing `tw-input.css`
3. **No JS bundler** — frontend files share global scope via `<script>` tags
4. **Norwegian naming is mandatory** — all variables, functions, and UI text must be in Norwegian
5. **`'use strict';` is required** — every JS file must have this at the top
6. **Use `escHtml()` in innerHTML** — never interpolate raw stock data strings into HTML
7. **Price data is separate** — `priser.json` is merged into `alleAksjer` at runtime; prices are not in `aksjer.json`
8. **Kurshistorikk er separat** — ligger i `data/kurs/{TICKER}.json`, ikke i `aksjer.json`. Frontend henter den on-demand via `hentKursHistorikk()` når en aksjemodal åpnes. Python-kode som genererer sider må laste den tilbake med `_last_kurshistorikk_fra_disk()` — ellers regenereres alle SEO-sider uten kursgraf
8. **`window.alleAksjer`** is set in `lastInnData()` in `app.js` for cross-file access
