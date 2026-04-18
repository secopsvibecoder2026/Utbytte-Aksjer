# exday.no — Veikart

Norsk utbytteaksje-tracker for Oslo Børs. Fullførte funksjoner: [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md)

---

## Høy prioritet

### Datakvalitet — fjern aksjer uten utbyttedata
16 aksjer har `upa=0`, `yield=0`, `hist=0` og hører ikke hjemme på en utbytteside:
PGS, DOF, NRC, ENDUR, NKR, BWE, CADLR, KMCP, BORR, CAPT, ISLAX, AFISH, HEX, ACR, NOD, KOA
- [ ] Fjern fra `tickers.json` og regenerer alle sider

### Datakvalitet — fiks misvisende snitt_yield_5ar i fetch_stocks.py
HUNT (298%), OTEC (105%), WEST (56%) har ekstreme snitt pga. historiske spesialutbytter ved nåværende lav kurs.
- [ ] Ekskluder år med `yield > 100%` i snitt-beregningen i `hent_historiske_utbytter()`
- [ ] Vis advarsel på sider der `snitt5ar > 50%`

### SEO — OG/Twitter meta-tagger mangler på alle genererte sider
Deling på Facebook/Twitter/LinkedIn viser ingen forhåndsvisning. Bildet finnes (`/assets/og-image.png`).
- [ ] Legg til i `_aksje_side_html()`: `og:image`, `og:locale`, `og:site_name`, Twitter Card
- [ ] Legg til i `generer_sektorsider()`: samme + `og:type=website`
- [ ] Legg til i `generer_aksjesider()` (inline `/aksjer/`-template): full OG-blokk
- [ ] Legg til i `generer_topplistesider()`: `og:image`, `og:locale`, `og:site_name`, Twitter Card
- [ ] Kjør `python scripts/regenerer_sider.py` og push

### Prisvarsel via push-notifikasjon
`malPris`-feltet og push-infrastruktur finnes allerede i Service Worker.
- [ ] Legg til `malPris`-sjekk i `sjekkExDatoer()` i `sw.js`
- [ ] Send varsel: «{TICKER} har truffet målprisen din på {pris} kr»
- [ ] Lagre «varslet»-flagg per målpris for å unngå gjentatte varsler

### Import fra Nordnet/DNB CSV
Ny bruker bruker lang tid på manuell innlegging. Nordnet eksporterer CSV med Dato, Ticker, Antall, Kurs.
- [ ] Parser for Nordnet-transaksjonseksport
- [ ] Parser for DNB Aksjehandel-eksport
- [ ] Preview-modal med deduplisering

### AdSense-optimalisering
- [ ] Manuell annonseenhet mellom sammendragskort og aksjelist
- [ ] Manuell annonseenhet i bunnen av aksjemodal
- [ ] Rapporter klikk-rate og RPM i GA4

---

## Medium prioritet

### Betalingskalender — «Når får jeg utbytte?»
Kalender-fanen viser ex-datoer, men ikke forventet betalingsdato per aksje i portefølje.
- [ ] Ny visning i Kalender: «Mine utbetalinger» — gruppert per måned med beløp og sum

### Månedlig utbytteplanlegger
- [ ] Input: ønsket månedsinntekt (f.eks. 10 000 kr/mnd)
- [ ] Beregn nødvendig kapital basert på porteføljens vektede yield
- [ ] Vis fremgang: «Du er X % av veien til målet ditt»

### Skattesammendrag — årsoppsummering
Skjermingsfradrag er allerede beregnet. Mangler samlet årsvisning.
- [ ] Ny seksjon i Statistikk-fanen: «Skatteåret {år}»
- [ ] Totalt mottatt utbytte, skjermingsfradrag, skattepliktig beløp og estimert skatt (37,84%)
- [ ] Eksporter til PDF eller klippebord

### Utbyttebærekraft på aksjekortet
Bærekraft-analyse vises i modal, men ikke i kortvisning.
- [ ] Vurder subtilt ikon (skjold) i stedet for tekst-badge

### Datapipeline-validering
- [ ] Varsel i GitHub Actions ved yield > 30%, pris = 0 eller manglende felt på >50% av aksjene

### Bloggseksjon / artikler
- [ ] `/artikler/hva-er-ex-dato/`
- [ ] `/artikler/beste-utbytteaksjer-2026/`
- [ ] `/artikler/utbytte-skatt-norge/`

### Strukturerte data for aksjesider
- [ ] `Corporation`-schema med `tickerSymbol` i JSON-LD
- [ ] `FAQPage`-schema: «Hva er ex-dato for {TICKER}?»

### Ytterligere aksjer
- [ ] Merk aksjer uten live-kurs tydelig («Kurs ikke tilgjengelig»)
- [ ] Undersøk Euronext API for manglende tickers
- [ ] Vurder Oslo Børs Small Cap-aksjer med stabil utbyttehistorikk

---

## Lav prioritet

### Teknisk gjeld

**Internlenking mellom aksjesider**
- [ ] «Relaterte aksjer» (samme sektor) på bunnen av hver aksje-side

**Virtuell scrolling**
- [ ] Render bare synlige kort + buffer — viktig på mobil med 160+ aksjer

**Splitt ui.js (1 600+ linjer)**
- [ ] `modal.js` for `visModal()` og `scoreForklaring()`
- [ ] `kalender.js` for `visKalender()`

**E2E-tester**
- [ ] Playwright: søk aksje → åpne modal → legg i portefølje
- [ ] Kjør i GitHub Actions på PR

**Staging-miljø**
- [ ] Netlify-deploy fra `dev`-branch med preview-URL per PR

### Monetisering
- [ ] «Støtt prosjektet»-knapp (Ko-fi / Vipps) — vises etter 5 besøk

---

*Sist oppdatert: april 2026*
