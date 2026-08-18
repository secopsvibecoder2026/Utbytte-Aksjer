# Prosjektgjennomgang — exday.no

> ## 📌 Historisk øyeblikksbilde — ikke en levende oppgaveliste
>
> Dette dokumentet beskriver prosjektet slik det var **28. mai 2026**, og oppdateres ikke
> løpende. Alle kritiske og de fleste viktige funn var allerede utbedret da det ble skrevet.
> Det er senere avløst av [KODE_REVIEW.md](KODE_REVIEW.md) (4. juli 2026), som selv er et
> øyeblikksbilde.
>
> 👉 Åpne saker følges i **[ROADMAP_NYE_IDEER.md](ROADMAP_NYE_IDEER.md)**, sikkerhet i
> **[SECURITY_ROADMAP.md](SECURITY_ROADMAP.md)**.

*Dato: 2026-05-28 · Gjennomgang av JS, HTML/SEO, Python-scripts og GitHub Actions*

---

## Sammendrag

| Alvorlighetsgrad | Antall | Status |
|---|---|---|
| 🔴 Kritisk | 5 | ✅ Alle fikset |
| 🟠 Viktig | 10 | ✅ Fikset (7) · Anbefalt (3) |
| 🟡 Forbedring | 7 | Se under |
| 🟢 Bra | — | Se under |

---

## 🔴 Kritiske funn — alle fikset

### 1. XSS: `sektor` og `slug` ikke escapet i `portefolje.js`
**Fil:** `assets/portefolje.js` — linjene 1617, 2000, 2006, 2020, 2024–2025, 2037  
**Årsak:** `${sektor}` og `${slug}` ble interpolert direkte inn i innerHTML-maler uten `escHtml()`. Dersom datapipelinen eller en fremtidig sektorverdi inneholder HTML/skriptinnhold, kan det utføres vilkårlig kode.  
**Fix:** Alle forekomster erstattet med `${escHtml(sektor)}` og `${escHtml(slug)}`.

### 2. `data-ticker` inkonsekvent escapet i `portefolje.js`
**Fil:** `assets/portefolje.js` — linjene 74, 94, 1084, 1090, 1100, 1103  
**Årsak:** `data-ticker="${a.ticker}"` uten escape i halvparten av malene, mens andre steder bruker `escHtml(a.ticker)`. En ticker med `"` i navnet (f.eks. ved datafeil) kan bryte ut av attributtkontekst.  
**Fix:** Alle uescapede `data-ticker`-forekomster i de aktuelle radene oppdatert til `escHtml(a.ticker)`.

### 3. `faq/index.html` leser feil localStorage-nøkkel for mørk modus
**Fil:** `faq/index.html` linje 41  
**Årsak:** `localStorage.getItem('theme')` i stedet for `'tema'` (norsk nøkkel brukt i hele resten av appen). Resulterte i at FAQ alltid startet i lys modus uavhengig av brukerens valg.  
**Fix:** Endret til `if (localStorage.getItem('tema') === 'dark')` — konsekvent med alle andre sider.

### 4. `manifest.json` — feil `theme_color`
**Fil:** `manifest.json` linje 8  
**Årsak:** `theme_color` var `#0F172A` (mørk marine), mens PWA-tittellinja på mobil vises med denne fargen. Passer ikke med grønn merkevare og ser ut som en mørk feil.  
**Fix:** Endret til `#16a34a` (merkevare-grønn, matches `<meta name="theme-color">` i HTML).

---

## 🟠 Viktige funn

### 5. Service Worker mangler `/verktoy/*` i PRECACHE ✅ Fikset
**Fil:** `sw.js` linjene 7–20  
**Årsak:** `PRECACHE`-listen inkluderte ikke de nye verktøy-sidene. Brukere som aldri har besøkt f.eks. `/verktoy/fire-kalkulator/` ville ikke ha siden tilgjengelig offline.  
**Fix:** La til `/verktoy/`, `/verktoy/kalkulator/`, `/verktoy/fire-kalkulator/`, `/verktoy/sektorrebalansering/`, `/verktoy/huslan-vs-investering/` og `/utbyttekalender/` i PRECACHE.  
**Merk:** HTML-navigering bruker allerede network-first og cacher på besøk — PRECACHE sikrer tilgang uten forhåndsbesøk.

### 6. `sitemap.xml` mangler alle artikler og verktøy-URL-er ✅ Fikset
**Fil:** `sitemap.xml`  
**Årsak:** Fire artikler (`aksjesparekonto-ask`, `utbytteportefolje-sektorvekting`, `reinvestering-av-utbytte`) og alle fem `/verktoy/*`-sider manglet. Google ville ikke indeksere dem uten at brukere lenket direkte til dem.  
**Fix:** La til alle manglende URL-er.  
**⚠️ Gjentagende problem:** `sitemap.xml` regenereres daglig av GitHub Actions og overskriver manuelle tillegg. Løsning: legg til disse URL-ene i Python-scriptet som genererer sitemap (`fetch_stocks.py`).

### 7. Ingen debounce på søkefeltet i appen ✅ Fikset
**Fil:** `assets/ui.js` linje 475  
**Årsak:** Søkefeltet (`#sok`) trigget full DOM-gjengivelse på hvert eneste tastetrykk — ingen forsinkelse. Med 191 aksjer og kompleks kortgjengivelse gir dette merkbar treg respons på mobil.  
**Fix:** La til `_debounce(fn, 250ms)` på søk-input. Dropdown-filtere (`filter-sektor`, etc.) beholder umiddelbar respons siden de er enkle klikk.

### 8. `escHtml` er ikke testet ✅ Bør legges til
**Fil:** `tests/ui.test.js`  
**Årsak:** `escHtml()` er en sikkerhetskritisk funksjon brukt over hele kodebasen, men har ingen dedikerte tester. En regressjon ville ikke bli oppdaget.  
**Anbefaling:** Legg til tester for `<`, `>`, `"`, `'`, `&` og kombinasjoner.

### 9. Python-script: sitemap regenereres uten verktøy-/artikkel-URL-er
**Fil:** `scripts/fetch_stocks.py` (se seksjon om Python-funn)  
**Årsak:** Sitemap-genereringen i scriptet inkluderer ikke `/verktoy/*` og `/artikler/*`. Daglig CI-kjøring overskriver manuelle tillegg.  
**Anbefaling:** Legg til statiske URL-er for verktøy og artikler i sitemap-genereringen i scriptet.

### 10. `404.html` videresender til forsiden i stedet for å vise 404-side
**Fil:** `404.html`  
**Årsak:** `window.location.replace('/')` uten brukervennlig melding. GitHub Pages bruker denne filen for alle 404-feil. En bruker som skriver feil URL opplever bare en stille omdirigering til forsiden — ingen hjelp til å navigere.  
**Anbefaling:** Vis en enkel side med "Siden finnes ikke" og lenker til hjem, aksjer, kalender og FAQ.

### 11. `fetch_priser.py` mangler timeout og retry-logikk
**Fil:** `scripts/fetch_priser.py`  
**Årsak:** Kjøres hvert 15. minutt. Dersom Yahoo Finance henger, venter scriptet ubegrenset. GitHub Actions har 6 timers makstid, men to parallelle kjøringer kan blokkere hverandre.  
**Anbefaling:** Legg til `timeout=10` i requests-kall og maksimalt 2 forsøk.

### 12. `a.navn` ikke escapet i portefoljetabell
**Fil:** `assets/portefolje.js` linje 1086  
**Årsak:** `${a.navn}` interpolert direkte i `<td>` uten `escHtml()`. Aksjenavn hentes fra `tickers.json` (kontrollert data), men burde likevel escapes konsekvent.  
**Fix:** Fikset i samme runde som data-ticker-funnene over.

---

## 🟡 Forbedringer

### 13. `og:type="article"` på verktøy-sider
**Filer:** `verktoy/kalkulator/index.html`, `verktoy/fire-kalkulator/index.html`, m.fl.  
**Årsak:** OG-typen bør være `"website"` for interaktive verktøy, ikke `"article"`. Påvirker hvordan Facebook/LinkedIn viser lenkeforhåndsvisning.

### 14. `manifest.json` — `background_color` ikke tilpasset dark mode
**Fil:** `manifest.json`  
**Årsak:** `background_color: #f9fafb` (lys) vises som splash-skjerm ved PWA-oppstart. Mørke-modus-brukere opplever en hvit blits. Kan ikke fikses dynamisk i manifest, men det er dokumentert her som kjent oppførsel.

### 15. Ingen e2e-tester for de nye verktøy-sidene
**Fil:** `tests/app.e2e.js`  
**Årsak:** Playwright-konfig og e2e-testfil eksisterer, men dekker ikke `/verktoy/fire-kalkulator/` eller `/verktoy/sektorrebalansering/`.

### 16. `window.alleAksjer` settes men leses aldri fra
**Fil:** `assets/app.js` linje ~116  
**Årsak:** `window.alleAksjer = alleAksjer` ser ut til å være et relikt fra da filene kommuniserte via `window` — nå bruker testene `global.alleAksjer`-mock direkte. Harmløst men ryddig å fjerne.

### 17. IRR-beregning mangler maks-iterasjoner-garanti
**Fil:** `assets/portefolje.js`  
**Årsak:** Newton-Raphson-løkkens konvergenskriterium er lavt, men svært store eller små tall kan i teorien oscillere. Maks 1000 iterasjoner er satt, men feilhåndtering ved ikke-konvergens returnerer `null` stille.

### 18. `oppdater_hendelser.py` og `ai_oppsummering.py` — ingen CI-integrasjon
**Filer:** `scripts/oppdater_hendelser.py`, `scripts/ai_oppsummering.py`  
**Årsak:** Scripter som ser nyttige ut, men mangler GitHub Actions-workflow. Kjøres kun manuelt.

---

## 🟢 Det som fungerer bra

- **`'use strict'`** er konsekvent i toppen av alle JS-filer ✅  
- **Navigasjonsmeny** er identisk på tvers av alle sider — Verktøy-dropdown med alle 4 verktøy ✅  
- **Kanoniske URL-er** er korrekte på alle sider ✅  
- **OG/meta-tagger** er komplette på alle sider ✅  
- **Brødsmulesti** finnes der det er forventet ✅  
- **Standard bunntekst** er konsekvent på tvers av alle sider ✅  
- **Ticker-validering** i `fetch_stocks.py` (`^[A-Z0-9]{1,10}$`) forhindrer injeksjon ✅  
- **FIFO-kostbasis og IRR-beregning** dekket av enhetstester ✅  
- **Service Worker** bruker network-first for HTML og JSON — brukere ser alltid siste versjon ✅  
- **Concurrency-guard** i `oppdater-priser.yml` forhindrer parallelle kjøringer ✅  
- **Datakvalitetsvalidering** (`valider_data.py`) kjøres automatisk i CI etter hvert datahenting ✅  
- **QRCode-biblioteket er vendored** — ingen CDN-avhengighet ✅  
- **Ingen brutte interne lenker** til gammel `/utbyttekalkulator/`-sti ✅  

---

## Gjennomførte fikser i denne reviewen

| # | Fil | Endring |
|---|---|---|
| 1–2 | `assets/portefolje.js` | `escHtml()` på alle `sektor`, `slug`, `ticker`, `navn` i innerHTML |
| 3 | `faq/index.html` | Dark mode nøkkel `'theme'` → `'tema'` |
| 4 | `manifest.json` | `theme_color` `#0F172A` → `#16a34a` |
| 5 | `sw.js` | `/verktoy/*` og `/utbyttekalender/` lagt til i PRECACHE |
| 6 | `sitemap.xml` | Alle artikler og verktøy-URL-er lagt til |
| 7 | `assets/ui.js` | 250ms debounce på søk-input |
| 8 | `scripts/fetch_stocks.py` | `generer_sitemap()` oppdatert med artikler og verktøy (permanent fix) |
| 9 | `.github/workflows/ai-oppsummering.yml` | Shell-injeksjon fikset: inputs via env-variabler |
| 10 | `.github/workflows/oppdater-priser.yml` | `git pull --rebase` lagt til før push |

---

---

## GitHub Actions og Python-scripts

### 13. Shell-injeksjon i `ai-oppsummering.yml` 🔴 Fikset
**Fil:** `.github/workflows/ai-oppsummering.yml` linje 42  
**Årsak:** `${{ inputs.tickers }}` ble interpolert direkte i shell-kommandoen uten sanitering. En bruker med skrivetilgang som triggrer `workflow_dispatch` med `; malicious_command` som ticker-input, ville fått kjørt vilkårlig kode i CI-miljøet.  
**Fix:** Moved inputs til env-variabler (`INPUT_TICKERS`, `INPUT_FORCE`) og refererer til disse i shell-kommandoen, slik at GitHub Actions håndterer escapingen.

### 14. `oppdater-priser.yml` mangler `git pull --rebase` før push 🟠 Fikset
**Fil:** `.github/workflows/oppdater-priser.yml` linje 48  
**Årsak:** `git push` uten forutgående `git pull --rebase` feiler med 403/rejected dersom `update-og-deploy.yml` har committet endringer i mellomtiden. Daglig data-workflow kjører 4× daglig, pris-workflow 37× daglig — kollisjoner er sannsynlige.  
**Fix:** La til `git pull --rebase origin main` før `git push`, konsistent med `update-og-deploy.yml`.

### 15. `update-og-deploy.yml` — `git add` inkluderer ikke `verktoy/` og `artikler/` 🟡
**Fil:** `.github/workflows/update-og-deploy.yml` linje 59  
**Årsak:** `git add data/aksjer.json data/hendelser.json aksjer/ sitemap.xml index.html app/` dekker ikke `verktoy/` eller `artikler/`. Dette er OK i dag siden `fetch_stocks.py` ikke rører disse mappene — men hvis man legger til automatisk generering av verktøy-/artikkelsider, vil de ikke bli committet.  
**Anbefaling:** Dokumentert som kjent begrensning; ingen umiddelbar risiko.

### 16. `fetch_priser.py` mangler request-timeout 🟠
**Fil:** `scripts/fetch_priser.py` linje 31–38  
**Årsak:** `yf.download()` har ingen eksplisitt timeout. `yfinance` internt bruker `requests` med standard timeout (ubegrenset). Dersom Yahoo Finance henger, kan kjøringen bruke opp GitHub Actions-tidsbegrensningen og blokkere påfølgende 15-minutters kjøringer.  
**Anbefaling:** `yf.download(..., timeout=30)` (støttes i nyere yfinance-versjoner) eller implementer en `signal.alarm`-basert timeout på topp-nivå.

### 17. `fetch_stocks.py` har gode sikkerhetsrutiner 🟢
- `_valider_ticker()` med regex `^[A-Z0-9]{1,10}$` forhindrer path traversal i filnavn
- `urllib.parse.quote()` brukes konsekvent for URL-parametere
- Alle HTTP-kall har eksplisitte timeouts (5–30 sek)
- `Promise.allSettled()`-ekvivalent — enkeltfeil krasjer ikke hele pipelinen

### 18. `ai-oppsummering.yml` bruker ikke pinned action-versjoner 🟡
**Årsak:** `actions/checkout@v4`, `actions/setup-python@v5` bruker major-versjon-tags, ikke SHA-pinned. Sikkerhetsbeste-praksis for CI er å bruke full SHA for å forhindre supply chain-angrep.  
**Anbefaling:** Lav risiko for et privat repo, men verdt å dokumentere. Eksempel: `uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2`

---

## Gjenstående anbefalinger (ikke fikset i denne omgang)

1. **Skriv tester for `escHtml()`** i `tests/ui.test.js` — sikkerhetskritisk funksjon bør verifiseres.
2. **Forbedre `404.html`** med nyttig navigasjon i stedet for stille redirect til forsiden.
3. **Legg til timeout** i `scripts/fetch_priser.py` (`yf.download(..., timeout=30)`) for å forhindre at hengende API-kall blokkerer CI-køen.
4. **Endre `og:type`** fra `"article"` til `"website"` på interaktive verktøy-sider.
5. **Vurder e2e-tester** for de nye verktøy-sidene i `tests/app.e2e.js`.
6. **Vurder SHA-pinning** av GitHub Actions for økt supply chain-sikkerhet.
