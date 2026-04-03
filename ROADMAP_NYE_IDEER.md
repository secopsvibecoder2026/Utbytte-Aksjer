# exday.no — Nye ideer og forbedringer

Basert på full gjennomgang av kodebasen (april 2026).
Eksisterende veikart: [ROADMAP.md](ROADMAP.md) · Fullførte funksjoner: [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md)

---

## 🐛 Kjente bugs og rask-fikser

### B1. Utdatert antall i meta-tagger
**Prioritet: Høy — påvirker SEO og troverdighet**

`index.html` har hardkodet "45 norske utbytteaksjer" i `<meta name="description">`, `og:description`, Twitter Card og JSON-LD Dataset. Vi sporer nå 80.

- [ ] Oppdater alle meta-tagger til "80 norske utbytteaksjer"
- [ ] Endre `fetch_stocks.py` til å skrive antall dynamisk inn i `index.html` ved hvert deploy

### B2. Modal-tekst ved ex-dato i dag
**Prioritet: Lav**

Modal viser "om 0 dager" når ex-dato er i dag. Aksjekortet håndterer dette korrekt med "(i dag!)".

- [ ] Bytt `om ${dagerTilEx} dager` til betinget tekst: `i dag` / `i morgen` / `om X dager`

### B3. Canonical-tag mangler på /uke/
**Prioritet: Medium — SEO**

`/uke/index.html` mangler `<link rel="canonical">`, noe som kan gi duplikat-innhold-problemer.

- [ ] Legg til `<link rel="canonical" href="https://exday.no/uke/" />`

---

## 🚀 Høy prioritet

### N1. Prisvarsel via push-notifikasjon
**Prioritet: Høy — eksisterende infrastruktur, mangler bare kobling**

`malPris`-feltet finnes allerede i storage. Service workeren har push-notifikasjon-infrastruktur for ex-datoer. Mangler bare at SW sjekker om kurs har truffet målpris.

- [ ] Legg til `malPris`-sjekk i `sjekkExDatoer()` i `sw.js`
- [ ] Send varsel: «{TICKER} har truffet målprisen din på {pris} kr»
- [ ] Lagre «varslet» per målpris slik at man ikke bombarderes

### N2. Import fra Nordnet/DNB CSV
**Prioritet: Høy — stor brukerverdi, reduserer friksjon**

Nye brukere bruker lang tid på manuell innlegging. Nordnet eksporterer CSV med kolonner `Dato, Ticker, Antall, Kurs, Valuta, Transaksjonstype`.

- [ ] Parser for Nordnet-transaksjonseksport (CSV)
- [ ] Parser for DNB Aksjehandel-eksport
- [ ] Preview-modal: vis hva som importeres før det lagres
- [ ] Deduplisering: ikke legg inn transaksjoner som allerede finnes

### N3. Betalingskalender — «Når får jeg utbytte?»
**Prioritet: Høy — svarer på det mest stilte spørsmålet**

Brukere med portefølje vil vite nøyaktig hvilken måned de mottar utbytte fra sine aksjer. Kalender-fanen viser ex-datoer, men ikke betalingskalender.

- [ ] Ny visning i Kalender-fanen: «Mine utbetalinger»
- [ ] Vis kun aksjer i brukerens portefølje
- [ ] Grupper etter måned med forventet betalingsdato og beløp
- [ ] Sum per måned (forventet innbetaling)

### N4. Reinvesteringskalkulator (DRIP) ← fra ROADMAP.md #35 ✅
**Prioritet: Høy**

- [x] Inndata: startbeløp, månedlig sparing, yield, kursvekst, antall år
- [x] Beregn porteføljeverdi med og uten reinvestering (begge beregnes alltid)
- [x] SVG-graf: blå linje (med DRIP) vs. stiplet grå (uten DRIP) — renters rente-effekten over tid
- [x] DRIP-gevinst stat-kort viser differansen mellom de to scenariene
- [x] Checkbox styrer hvilken kolonne tabellen viser

---

## 📈 Medium prioritet

### N5. Sammenlign aksjer side ved side
**Prioritet: Medium**

- [ ] Velg 2–3 aksjer og vis dem i en sammenligningstabell
- [ ] Sammenlign: yield, payout, vekst, P/E, P/B, score, historikk
- [ ] Del-lenke: `?sammenlign=EQNR,DNB,ORK`

### N6. Skattesammendrag — årsoppsummering
**Prioritet: Medium**

Skjermingsfradrag er allerede beregnet. Mangler en samlet årsvisning for skattemeldingen.

- [ ] Ny seksjon i Statistikk-fanen: «Skatteåret {år}»
- [ ] Totalt mottatt utbytte dette år (fra transaksjonslogg)
- [ ] Skjermingsfradrag totalt
- [ ] Skattepliktig utbytte (etter fradrag)
- [ ] Estimert skatt å betale (37,84 %)
- [ ] Eksporter som PDF eller kopier til utklippstavle

### N7. Portefølje-rebalansering
**Prioritet: Medium**

- [ ] Bruker setter inn ønsket vekting per sektor (f.eks. 30 % Energi, 20 % Finans)
- [ ] App viser avvik fra mål og hvilke aksjer å kjøpe/selge

### N8. Månedlig utbytteplanlegger ← fra ROADMAP.md #38
**Prioritet: Medium**

- [ ] Mål-input: ønsket månedsinntekt fra utbytte (f.eks. 10 000 kr/mnd)
- [ ] Beregn nødvendig investert kapital basert på porteføljens vektede yield
- [ ] Vis fremgang: «Du er X % av veien til målet ditt»

### N9. Dynamisk meta-beskrivelse i fetch_stocks.py
**Prioritet: Medium — vedlikeholdsforbedring**

I dag er antallet hardkodet i HTML. Bør genereres automatisk.

- [ ] `fetch_stocks.py` oppdaterer `<meta name="description">` og JSON-LD i `index.html` med riktig antall aksjer
- [ ] Tilsvarende for `og:description` og `twitter:description`

### N10. Ytterligere aksjer og datakvalitet
**Prioritet: Medium**

20 tickers mangler data fra Yahoo Finance. Noen alternativer:

- [ ] Prøv Oslo Børs API direkte for priser (særlig mindre aksjer)
- [ ] Merk aksjer uten live-kurs tydelig i appen («Kurs ikke tilgjengelig»)
- [ ] Undersøk `pyfinviz` eller `euronext` API for manglende tickers
- [ ] Legg til Oslo Børs Small Cap-aksjer med utbyttehistorikk (f.eks. BWLPG, MPCC, HAVI)

### N11. Utbyttebærekraft-score på kortene ← fra ROADMAP.md #36 (delvis gjort)
**Prioritet: Medium**

Bærekraft-analysen er implementert i modalen, men vi fjernet badget fra kortene. Vurder en mer subtil fremstilling.

- [ ] Vurder å vise bare et lite ikon (f.eks. et skjold) i stedet for tekst-badge
- [ ] Alternativt: legg til i kompaktvisning som en ekstra kolonne i tabellen

---

## 🔍 SEO og vekst

### N12. Bloggseksjon / artikler
**Prioritet: Medium — langsiktig SEO**

Statiske innholdssider rangerer godt og bygger domeneautoritet.

- [ ] `/artikler/hva-er-ex-dato/` — forklarer ex-dato for nybegynnere
- [ ] `/artikler/beste-utbytteaksjer-2026/` — oppdateres hvert år
- [ ] `/artikler/utbytte-skatt-norge/` — skatteregler for privatpersoner
- [ ] Generer fra markdown via `fetch_stocks.py` eller manuelt

### N13. Strukturerte data for aksjesider
**Prioritet: Medium — Google-indeksering**

Enkeltaksjesider (`/aksjer/TICKER/`) mangler `StockTicker`-schema.

- [ ] Legg til `{"@type": "Corporation", "tickerSymbol": "EQNR", ...}` i JSON-LD
- [ ] Legg til `FAQPage`-schema med "Hva er ex-dato for EQNR?"

### N14. Internlenking mellom aksjesider
**Prioritet: Lav**

- [ ] «Relaterte aksjer» seksjon på hver aksje側 (samme sektor)
- [ ] Legg til `<link rel="next">`/`<link rel="prev">` for sektorsider

---

## 🛠️ Teknisk gjeld

### T7. Virtuell scrolling for stor aksjelist
**Prioritet: Medium**

Med 80 aksjer (snart flere) rendres alle DOM-noder på en gang.

- [ ] Implementer windowing: render bare synlige kort + ~5 buffer
- [ ] Særlig viktig på mobil med lav RAM

### T8. ui.js er over 1 600 linjer
**Prioritet: Lav**

- [ ] Splitt ut `visModal()` + `scoreForklaring()` i en egen `modal.js`
- [ ] Splitt ut `visKalender()` i `kalender.js`

### T9. E2E-tester for kritiske brukerflyter
**Prioritet: Lav**

Eksisterende enhetstester dekker beregningslogikk. Brukerflyter testes ikke.

- [ ] Playwright-tester: last side → søk aksje → åpne modal → lukk
- [ ] Test: legg til aksje i portefølje → sjekk at statistikk oppdateres
- [ ] Kjør i GitHub Actions på PR

### T10. Staging-miljø ← fra ROADMAP.md T6
**Prioritet: Lav**

- [ ] Netlify-deploy fra `dev`-branch
- [ ] Preview-URL per PR

---

## 💰 Monetisering

### N15. AdSense-optimalisering
**Prioritet: Høy etter godkjenning**

- [ ] Manuell annonseenhet mellom sammendragskort og aksjelist
- [ ] Manuell annonseenhet i bunnen av aksjemodal (etter scoreforklaring)
- [ ] Test annonseformat: display vs. in-feed
- [ ] Rapporter klikk-rate og RPM i GA4

### N16. «Støtt prosjektet»-knapp
**Prioritet: Lav**

- [ ] Ko-fi eller Vipps QR-kode i innstillinger/footer
- [ ] Vises etter 5 besøk (ikke umiddelbart)

---

## 📱 Mobilopplevelse

### N17. Swipe-navigasjon mellom faner
**Prioritet: Lav**

- [ ] Touch-swipe venstre/høyre bytter mellom Oversikt / Kalender / Portefølje
- [ ] Visuell indikator som følger fingeren

### N18. «Tilbake til toppen»-knapp
**Prioritet: Lav**

- [ ] Vises etter scroll > 300px
- [ ] Sticky, lavere høyre hjørne, lite og diskret

---

*Sist oppdatert: april 2026*
