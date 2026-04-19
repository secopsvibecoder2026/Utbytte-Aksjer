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
10 artikler planlagt (1 500–3 000 ord, norsk, SEO-optimalisert med JSON-LD, dark mode, samme design som FAQ):

- [ ] `/artikler/hva-er-ex-dato/` — Alt om ex-dato: T+2, kursfall, skatt, strategi
- [ ] `/artikler/beste-utbytteaksjer-2026/` — Redaksjonell gjennomgang av ledende norske utbytteaksjer
- [ ] `/artikler/utbytte-skatt-norge/` — Skatteregler: ASK vs. VPS, skjermingsfradrag, 37,84%
- [ ] `/artikler/aksjesparekonto-ask/` — Komplett guide til ASK for utbytteinvestorer
- [ ] `/artikler/bygge-utbytteportefolje/` — Steg-for-steg: diversifisering, sektorvekting, rebalansering
- [ ] `/artikler/reinvestering-utbytte/` — DRIP og rentes-rente-effekten over 20 år (med eksempler)
- [ ] `/artikler/shipping-aksjer-utbytte/` — Norske shippingaksjer: høy yield, syklisitet, risiko
- [ ] `/artikler/sparebanker-utbytte/` — Hvorfor sparebanker gir stabile utbytter år etter år
- [ ] `/artikler/payout-ratio/` — Hva payout ratio forteller deg om utbyttets bærekraft
- [ ] `/artikler/lese-utbyttekalender/` — Slik bruker du utbyttekalenderen til å planlegge kontantstrøm

Også opprett `/artikler/index.html` som oversiktsside for alle artikler.

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

**Virtuell scrolling**
- [ ] Render bare synlige kort + buffer — viktig på mobil med 160+ aksjer

**Splitt ui.js (1 600+ linjer)**
- [ ] `modal.js` for `visModal()` og `scoreForklaring()`
- [ ] `kalender.js` for `visKalender()`

**E2E-tester**
- [x] Playwright: søk aksje → åpne modal → legg i portefølje (`tests/app.e2e.js`, 8 tester)
- [ ] Kjør i GitHub Actions på PR


**Staging-miljø**
- [ ] Netlify-deploy fra `dev`-branch med preview-URL per PR

### Monetisering
- [ ] «Støtt prosjektet»-knapp (Ko-fi / Vipps) — vises etter 5 besøk

---

*Sist oppdatert: april 2026*
