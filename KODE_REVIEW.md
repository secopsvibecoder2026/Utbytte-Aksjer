# Kodegjennomgang — exday.no (Utbytte-Aksjer)

**Dato:** 2026-07-04
**Omfang:** Frontend-JavaScript, Python-datapipeline, HTML/PWA, CI/CD, SEO, tilgjengelighet og testdekning.
**Metode:** Tre parallelle dybde-reviews (frontend, pipeline, plattform) + prosjektnivå-analyse. Alle funn er verifisert mot faktisk kildekode — de mest kritiske er dobbeltsjekket manuelt. Testsuiten (44 tester) passerer.

> Status-kolonnen oppdateres etter hvert som funn utbedres.

---

## Sammendrag

| Alvorlighet | Antall | Viktigste tema |
|---|---|---|
| 🔴 Kritisk | 5 | 2 XSS-sårbarheter, pipeline-krasj, valutamiks, deploy-gap for priser |
| 🟠 Viktig | 20 | Feil skattesats, TWR/FIFO-avvik, manglende escaping, datakvalitet |
| 🟡 Forbedring | 18 | Ytelse, vedlikehold, tilgjengelighet, repo-hygiene |
| ✅ Testdekning | 6 områder | Skatteberegning, CSV-parsere og kalkulatorer mangler tester |

**De fem viktigste tingene å fikse først:**
1. XSS i delt portefølje-lenke (K1) — én linjes fix
2. Tom `priser.json` ved Yahoo-feil (V13) — sletter alle sanntidskurser
3. Pipeline-krasj ved `pe_ratio: null` i fallback (K3) — stopper hele den daglige kjøringen
4. Prisoppdateringer når aldri live-siten (K5) — 15-min-workflowen har i praksis ingen effekt
5. Feil skattesats i FIRE-kalkulatoren (V4) — undervurderer kapitalbehov med ~20 %

---

## 🔴 Kritiske funn

### K1. XSS via delt portefølje-lenke (`?del=`)
**Fil:** `assets/ui.js:1784–1787` (inngangspunkt `assets/app.js:66–69`)
`ticker`, `vekt` og `y` fra URL-parameteren interpoleres uescapet i `innerHTML`. Payloaden er 100 % angriperstyrt (`JSON.parse(decodeURIComponent(atob(delParam)))`).
**Scenario:** Angriper deler lenke med `{"t":[["<img src=x onerror=...>",1,2]]}` i base64 → mottaker åpner → vilkårlig script kjører og kan lese/endre hele porteføljen i localStorage.
**Fix:** `escHtml()` rundt alle tre feltene (resten av funksjonen bruker allerede `textContent` korrekt).

### K2. Lagret XSS via notatfeltet
**Fil:** `assets/ui.js:3119`
`<textarea>${d.notat || ''}</textarea>` — notatet interpoleres uescapet. Et notat som `</textarea><img src=x onerror=...>` bryter ut av taggen. `bekreftJSONImport` (ui.js:2126) skriver `aksje_data` uvalidert fra importert backupfil.
**Scenario:** Bruker importerer en manipulert «backup» → åpner aksjemodal → script kjører.
**Fix:** `escHtml(d.notat)`.

### K3. Pipeline-krasj når fallback-aksjer har `pe_ratio: null`
**Fil:** `scripts/fetch_stocks.py:827` (rotårsak: `safe_float`:434 + `_sanitize`:4326)
`safe_float` slipper `Infinity` gjennom; `_sanitize` lagrer det som `null`. Dagens `aksjer.json` har `pe_ratio: null` for DOF, MAS, SWON, KOA. Når en av disse feiler mot Yahoo, brukes fallback, og `valider_aksje` kjører `if 0 < pe > 500:` med `pe=None` → `TypeError` — uhåndtert i `main()`.
**Scenario:** DOF får én 429 fra Yahoo → hele den daglige kjøringen krasjer; ingen data eller sider oppdateres.
**Fix:** None-sjekk i `valider_aksje` + gjør `safe_float` inf-sikker.

### K4. DNB-berikelsen blander valutaer for USD-betalere
**Fil:** `scripts/fetch_stocks.py:4222–4239`
(a) `siste_utbytte = dnb_belop` settes **ubetinget** før valutasjekken — et USD-beløp lagres og vises som NOK. (b) Valutasjekken sammenligner mot Yahoos *rapporteringsvaluta* (USD for GOGL/FLNG), ikke NOK som prisen er i.
**Scenario:** GOGL deklarerer 0,30 USD → «match» mot rapporteringsvaluta → `utbytte_per_aksje` = 1,2 mot NOK-pris → yield 1,2 % i stedet for ~11 %.
**Fix:** Konverter DNB-beløp til NOK eksplisitt (valutakurs), og flytt tilordningen bak sjekken.

### K5. Prisoppdateringer hvert 15. minutt når aldri ut på nettsiden
**Fil:** `.github/workflows/oppdater-priser.yml:39–50` + `update-og-deploy.yml:4–8`
Siten deployes kun via `actions/deploy-pages` (artefakt). `oppdater-priser.yml` committer bare `data/priser.json`: push med `GITHUB_TOKEN` trigger aldri `on: push`-workflows, og `paths-ignore` ekskluderer uansett datafilene.
**Konsekvens:** Live `/data/priser.json` oppdateres bare ved de 4 daglige deployene — 15-min-workflowen brenner CI-minutter uten brukersynlig effekt. Samme gjelder AI-oppsummeringer committet av `ai-oppsummering.yml`.
**Fix:** Legg et deploy-steg i priser-workflowen, bytt til branch-deploy, eller la priser-workflowen kalle `workflow_dispatch` på deploy-jobben.

---

## 🟠 Viktige funn

### Frontend (JavaScript)

| # | Funn | Fil:linje | Konsekvens / scenario |
|---|---|---|---|
| V1 | Feltnavn-typo `utbytte_pr_aksje` (skal være `utbytte_per_aksje`) | `ui.js:1739` | Delte porteføljer viser alltid «0 kr utbytte/år, 0,0 % yield» |
| V2 | TWR ignorerer kontantstrømmer mellom snapshots | `portefolje.js:317–340` | Innskudd 50 000 kr mellom to snapshots telles som *avkastning*; flows samme dag og på siste dato håndteres heller ikke |
| V3 | «FIFO» er i realiteten snittkost-metode | `portefolje.js:16–23` | Kjøp 100@100 + 100@300, selg 100: FIFO gir kost 30 000, koden gir 20 000 — avviker fra sktl. § 10-36; påvirker gevinst og skjermingsfradrag |
| V4 | Feil skattesats i FIRE-kalkulator for «Vanlig konto» (22 % i stedet for 37,84 %) | `ui.js:364` + `app/index.html:1269` | Kapitalbehov undervurderes med ~20 % (utbytte beskattes 37,84 %, ikke 22 %) |
| V5 | Akkumulerende `addEventListener` inne i render-funksjoner | `portefolje.js:1345`, `ui.js:3851`, `ui.js:4196` | Etter 30 renders utløser én endring 30 handler-kall → 30 nye fulle re-renders |
| V6 | `JSON.parse` uten try/catch i migrasjonskode som kjører ved lasting | `storage.js:19–21` | Korrupt localStorage-verdi → uncaught exception → hele appen dør ved oppstart |
| V7 | Systematiske brudd på escHtml-konvensjonen i innerHTML (10+ steder) | `ui.js:1037–1082, 1137–1230, 1370–1375, 1519–1520, 3596, 3830`; `portefolje.js:1109, 1743, 1783` | Lav utnyttbarhet i dag (egen pipeline), men ett råttent felt i aksjer.json rammer 10+ render-steder; inkonsistent med steder som escaper |
| V8 | SW: `resp.clone()` etter asynkron `caches.open()` | `sw.js:68, 82, 96` | «Response body is already used» på trege enheter → cache-oppdatering feiler stille → offline serverer gammel versjon |
| V9 | Hele aksjer.json (flere MB) caches i localStorage; porteføljeskriving mangler kvotehåndtering | `app.js:223`, `storage.js:72–105` | Full kvote → ny transaksjon forsvinner stille uten feilmelding |

### Python-pipeline

| # | Funn | Fil:linje | Konsekvens / scenario |
|---|---|---|---|
| V10 | DNB-annualisering (`beløp × frekvens`) kjøres *etter* alle sanity-sjekker | `fetch_stocks.py:4228–4239` | Engangsutbytte 8 kr × 4 = 32 kr/år publiseres uten re-validering — gjeninnfører kjent Yahoo-problem #3 |
| V11 | AI-oppsummeringer genereres med feil feltnavn (`pe`, `direkteavkastning`, `dps` finnes ikke — heter `pe_ratio`, `utbytte_yield`, `utbytte_per_aksje`) | `ai_oppsummering.py:69–77` | Claude bes vurdere P/E og yield med «–» som input → gjettede tall publiseres på 184 SEO-sider |
| V12 | Ingen HTML-escaping i noen av de tre HTML-templatene — inkl. rå AI-output i `<p>` | `fetch_stocks.py:2007, 2001, 1967, 2187, 2196` | AI-generert tekst med `<script>`/`</p>` → lagret XSS/ødelagt DOM, deployet automatisk uten review |
| V13 | `fetch_priser.py` skriver tom `priser.json` når Yahoo feiler | `fetch_priser.py:79–89` | Ett Yahoo-utfall → alle 191 sanntidskurser slettes fra produksjon og committes |
| V14 | Ingen throttling/retry mot Yahoo (~1000 kall i sekvens); feilede aksjer faller stille tilbake på gamle data med ferskt tidsstempel | `fetch_stocks.py:4155, 549–564, 4317` | 60 aksjer rate-limites → dagers gamle kurser under «oppdatert i dag»-stempel, ingen alarm |
| V15 | `valider_data.py` dekker ikke de kjente Yahoo-problemene den skal beskytte mot | `valider_data.py:36–82` | Blokkerende sjekk kan per konstruksjon nesten aldri feile (yield beregnes av pipelinen selv); issue #1/#3/#4-deteksjon mangler; ikke None-sikker |

### HTML / PWA / CI

| # | Funn | Fil:linje | Konsekvens / scenario |
|---|---|---|---|
| V16 | Feil localStorage-nøkkel `'theme'` på fire sider (konvensjon: `'tema'`) | `uke/index.html:206,209`, `bevegelser/index.html:214,220`, `personvern/index.html:33,298`, `faq/index.html:500` | Mørk modus valgt i appen ignoreres; to toggles på samme side skriver til ulike nøkler |
| V17 | Arctic-fargene (#132A50 m.fl.) i genererte oversiktssider — brudd på grønn brand-palett | `aksjer/index.html:44–110`, `aksjer/sektor/index.html:44–110` (kilde: `fetch_stocks.py:2789–2898, 3468–3511`) | Må fikses i malene og regenereres, ellers overskrives fiksen daglig |
| V18 | `manifest.json` mangler `scope` | `manifest.json:5` | `start_url: "/app/"` gir default scope `/app/` → navigasjon til /aksjer/, /artikler/ osv. åpner med browser-UI i installert PWA; `sw.js:123` åpner `/` (utenfor scope) ved varselklikk |
| V19 | `ai-oppsummering.yml` pusher uten rebase og uten concurrency-gruppe | `ai-oppsummering.yml:47–57` | Priser-workflow committer hvert 15. min → høy sannsynlighet for avvist push → tapte AI-oppsummeringer |
| V20 | Hele repoet publiseres til exday.no (`path: "."`) | `update-og-deploy.yml:98` | `SECURITY_ROADMAP.md` (dokumenterte sikkerhetsfunn!), `CLAUDE.md`, `PROSJEKT_REVIEW.md`, `scripts/`, `tests/` er offentlig tilgjengelig på domenet |

---

## 🟡 Forbedringsforslag

### Korrekthet / robusthet
1. **«Lavest: ∞ kr» i månedschart** — `portefolje.js:1497`: `Math.min(...tomArray)` gir `Infinity` når alle månedsverdier er 0.
2. **Kryssvalideringen klipper reelle utbytteøkninger stille** — `fetch_stocks.py:599–604`: avvik > 50 % *erstatter* verdien med fjorårets i stedet for å flagge; en reell KOG-type økning underrapporteres et helt år.
3. **`format_dato` bruker lokal tidssone på UTC-timestamps** — `fetch_stocks.py:450–457`: lokal kjøring vest for UTC gir ex-dato én dag for tidlig. Bruk `tz=timezone.utc`. (`datetime.utcnow()` er dessuten deprecated i 3.12.)
4. **Ikke-atomiske JSON-skrivinger** — `ai_oppsummering.py:148`, `fetch_stocks.py:4334`, `fetch_priser.py:88`, `regenerer_sider.py:42`: krasj midt i dump etterlater trunkert fil. Bruk temp-fil + `os.replace`. (`ai_oppsummering.py` skriver dessuten kompakt JSON mens resten bruker `indent=2` → 190 000-linjers diff-churn.)
5. **Push-race uten retry i update-og-deploy** — `update-og-deploy.yml:63–65`: lander en priser-commit mellom rebase og push, går hele den ~45 min lange datakjøringen tapt.

### Skattekonstanter og vedlikehold
6. **Utdaterte/dupliserte skattekonstanter** — `storage.js:38`: `SKJERMINGSRENTE = 0.031 // (2024)` uten oppdateringsmekanisme; satsen `0.3784`/`0.6216`/`0.22` duplisert som magiske tall på 9+ steder (`ui.js:364, 2765, 2791, 3265, 3277, 3282, 3283, 3298, 4127`). Samle i én konfig.
7. **`fetch_stocks.py` er 4 372 linjer med tre duplerte HTML-templater** — `_aksje_side_html` (~690 linjer), `generer_sektorsider` (~410), `generer_topplistesider` (~310). Head/favicon/dark-mode-init/nav er duplisert på tvers; Newsweb-API-koden duplisert mot `oppdater_hendelser.py`. Splitt i moduler (henting / prosa / templating / sitemap) og del templatefragmenter (som `STANDARD_FOOTER` allerede gjør).
8. **To foreldreløse AI-scripts** — `scripts/generer_ai_oppsummeringer.py` (503 linjer) og `scripts/_generer_ai_oppsummering_manuelt.py` (221 linjer) refereres ingen steder og dupliserer `ai_oppsummering.py`. Slett eller konsolider.
9. **Hardkodet artikkel-liste i sitemap-generatoren** — `fetch_stocks.py:4011+`: ny artikkel som glemmes her faller ut av sitemap ved neste daglige kjøring. Generer ved å liste `artikler/*/index.html`.
10. **Inline `onmouseenter` i generert SVG** — `fetch_stocks.py:982`: bryter prosjektets egen konvensjon om delegerte lyttere.

### Ytelse
11. **Polling og dobbeltlyttere** — `ui.js:240–243`: scroll-lytter på både `window` og `document` **pluss** `setInterval(…, 1000)` for alltid, for én «til toppen»-knapp.
12. **Unødige fulle re-renders** — favoritt-toggle re-rendrer hele oversikten inkl. paginering (`ui.js:1105`); `visDagensBevegelser()` kjøres ved hvert søketastetrykk (`ui.js:953`); filter-selectene rendrer på hvert `input`-event uten debounce (`ui.js:485–487`).
13. **Repo-vekst** — `data/aksjer.json` (~3 MB) committes opptil 4× daglig → git-historikken vokser med ~250+ MB/år. Vurder å flytte data ut av git (Pages-artefakt, egen data-branch med jevnlig squash, eller ekstern lagring).

### PWA / SEO / tilgjengelighet
14. **FOUC på /uke/ og /bevegelser/** — dark-klassen settes nederst i `<body>`, ikke i `<head>` → hvit blink for mørk modus-brukere.
15. **`/app/` har canonical til forsiden** tross vesentlig ulikt innhold (`app/index.html:38`); metadata spriker («162 aksjer» vs. «191»). Vurder egen canonical eller `noindex`.
16. **Faneknapper uten tab-semantikk** — `app/index.html:206–210`: mangler `role="tablist"/"tab"`, `aria-selected`, `aria-controls`.
17. **Filterkontroller uten label** — `app/index.html:236–262`: søkefelt og fire selects annonseres bare som «combo box» i skjermlesere.
18. **`theme-color` mangler** på `faq/` og `personvern/`.

### CI-sikkerhet
19. **Actions pinnet til tag, ikke commit-SHA** — alle workflows; SHA-pinning anbefales særlig med `contents: write` + `id-token: write`.
20. **For brede permissions på workflow-nivå** — `update-og-deploy.yml:17–20`: flytt til jobb-nivå (`oppdater-data` trenger ikke pages/id-token; `deploy-pages` trenger ikke contents: write).

---

## ✅ Testdekning — hull i kritisk regnelogikk

Dagens 44 tester dekker kostbasis, IRR, TWR (happy path), favoritter og formatterere. **Mangler helt:**

| Område | Hvorfor det haster |
|---|---|
| Skatteberegning (skjermingsfradrag × 37,84 %) | Ligger inline i `visPortefolje` med DOM-avhengigheter — bør trekkes ut som ren funksjon `beregnUtbytteskatt()` og testes |
| TWR med transaksjon *mellom* snapshots | Ville avdekket V2 |
| `parseCSV` / `parseNordnetCSV` (`ui.js:1823–1924`) | Parser upålitelig brukerinput (UTF-16, GAV-komma) uten én test |
| `beregnFire` / kalkulatorer | Ville avdekket V4 (feil skattesats) |
| `sorterAksjer` + paginering | `null`→`Infinity` mot strengkolonner gir NaN-sammenlikning |
| `escHtml` | Sikkerhetskritisk hjelper uten test |

---

## 👍 Det som er bra (verifisert)

- God feilhåndtering i `lastData` med cache-fallback og feilbanner
- SW-strategien er riktig vei (network-first for HTML/JS/CSS/aksjer.json); `Promise.allSettled` i precache gjør at én 404 ikke velter installasjonen
- Alle 204 sitemap-URL-er eksisterer på disk; robots.txt korrekt
- Standard-footer med ansvarsfraskrivelse på alle sjekkede sider
- Ingen shell-injeksjon i workflows (inputs går via env-variabler)
- Tickervalidering, `urllib.parse.quote`, timeouts på alle nettverkskall, ingen secrets i logger
- Søk er debouncet; klikk-delegering uten inline onclick; `'use strict'` overalt
- QR-import validerer tickers mot `alleAksjer`
- consent.js er ren og korrekt (Consent Mode v2)

---

## Anbefalt rekkefølge

**Runde 1 — små fikser, stor nedside (én økt):**
K1, K2 (escHtml ×2) · V13 (exit ≠ 0 ved tom priser) · K3 (None-sjekk) · V1 (feltnavn-typo) · V11 (feltnavn i AI-prompt) · V16 (tema-nøkkel ×4) · V6 (try/catch) · V8 (clone før retur)

**Runde 2 — regnefeil som påvirker brukere:**
V4 (FIRE-skattesats) · V3 (FIFO vs. snittkost — minimum rett dokumentasjonen) · V2 (TWR-flows) · forbedring 1 og 6

**Runde 3 — plattform:**
K5 (deploy-gap) · V19 (rebase i AI-workflow) · V20 (publiser `_site/` i stedet for hele repoet) · V18 (manifest scope) · V17 (Arctic-farger i maler + regenerering)

**Runde 4 — datakvalitet og arkitektur:**
K4 + V10 (DNB-valuta/annualisering) · V14 (throttling/retry) · V15 (utvid valider_data) · forbedring 4, 7, 8, 13 · testdekning

---

*Generert av Claude Code. Alle funn er verifisert mot kildekoden på commit-tidspunktet; linjenumre kan forskyves ved senere endringer.*
