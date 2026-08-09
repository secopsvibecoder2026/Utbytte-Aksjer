# exday.no — Nye ideer og forbedringer

Basert på full gjennomgang av kodebasen (april 2026).
Eksisterende veikart: [ROADMAP.md](ROADMAP.md) · Fullførte funksjoner: [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md)

---

## 🐛 Kjente bugs og rask-fikser

### B1. Utdatert antall i meta-tagger ✅
**Prioritet: Høy — påvirker SEO og troverdighet**

`index.html` har hardkodet "45 norske utbytteaksjer" i `<meta name="description">`, `og:description`, Twitter Card og JSON-LD Dataset. Vi sporer nå 80.

- [x] Oppdater alle meta-tagger til "80 norske utbytteaksjer"
- [x] Endre `fetch_stocks.py` til å skrive antall dynamisk inn i `index.html` ved hvert deploy

### B2. Modal-tekst ved ex-dato i dag ✅
**Prioritet: Lav**

Modal viser "om 0 dager" når ex-dato er i dag. Aksjekortet håndterer dette korrekt med "(i dag!)".

- [x] Bytt `om ${dagerTilEx} dager` til betinget tekst: `i dag` / `i morgen` / `om X dager`

### B3. Canonical-tag mangler på /uke/ ✅
**Prioritet: Medium — SEO**

`/uke/index.html` mangler `<link rel="canonical">`, noe som kan gi duplikat-innhold-problemer.

- [x] Legg til `<link rel="canonical" href="https://exday.no/uke/" />`

### B4. Stored XSS via JSON-backup-import ✅
**Prioritet: Kritisk — se [SECURITY_ROADMAP.md](SECURITY_ROADMAP.md)**

`parseJSONBackup()` (`ui.js:2083`) validerte kun at `versjon` var et tall 1–5. `visJSONPreview()` interpolerte deretter `backup.profil.navn` rått inn i `innerHTML` — **i selve forhåndsvisningen, før brukeren bekreftet importen.** Verifisert med `{"versjon":3,"profil":{"navn":"<img src=x onerror=alert(document.domain)>"}}` — payloaden overlevde intakt.

`bekreftJSONImport()` skrev deretter `backup.portefoljer`/`backup.watchlister` uvalidert til localStorage, og porteføljenavn og watchliste-navn rendres rått i `<option>`-tagger ved hver applast — så et ondsinnet navn ville persistert og kjørt på nytt hver gang appen åpnes.

- [x] `escHtml()` på `p.navn` i `visJSONPreview()` (ui.js:2142)
- [x] `escHtml()` på `p.id`/`p.navn` i porteføljevelgeren (portefolje.js:1938)
- [x] `escHtml()` på `w.id`/`w.navn` i watchliste-velgeren (portefolje.js:1978)
- [x] Valider typer i `parseJSONBackup()` — ny `_erGyldigBackupStruktur()` sjekker at `profil`/`portefoljer`/`watchlister`/`favoritter`/`notif_aksjer`/`rebalansering` har riktig grunnform (objekt vs. array) og at `navn`-felt er strenger, før dataene lagres

Verifisert: samme XSS-payload escapes nå til harmløs tekst; fire ulike malformerte strukturer (array der objekt forventes, feil felttype) avvises av validatoren; ekte v5-eksport, legacy v1-format og minimal `{"versjon":1}` godtas fortsatt uendret.

### B5. IRR annualiserer korte perioder til absurde tall ✅
**Prioritet: Høy — ser ut som en bug for brukeren**

`beregnIRR()` (`portefolje.js:401`) tillater annualisering ned til 30 dager. Newton-Raphson-matematikken er korrekt, men `(1+r)^365` gjør at helt normale gevinster blir meningsløse tall:

| Scenario | Vises som |
|---|---|
| +15 % etter 31 dager | +418,4 % |
| +5 % etter 31 dager | +77,6 % |
| +20 % etter 60 dager | +203,2 % |
| +10 % etter 365 dager | +10,0 % ✓ |

Verifisert ved å kjøre den faktiske Newton-Raphson-koden isolert med flere cashflow-scenarier.

- [x] Vis ikke-annualisert periodeavkastning når `periodeAr < 1` — `beregnIRR()` returnerer nå `periodeAvkastning` og `annualisert`; UI-en (`portefolje.js:1047-1069`) viser `periodeAvkastning` og bytter etikett til «Avkastning (periode)» når perioden er under ett år, «IRR (per år)» ellers. `irr_ar` beholdes uendret i returverdien. To nye tester i `tests/portefolje.test.js`.

### B6. Oversalg feiler i stillhet ✅
**Prioritet: Medium**

`beregnKostbasis()` (`portefolje.js`) tømmer FIFO-lottene og kaster resten av salgsantallet uten varsel. Registrerer brukeren et salg større enn beholdningen (skrivefeil, f.eks. 1000 i stedet for 100), ble posisjonen bare 0 — ingen feilmelding, ingen indikasjon på at noe er galt.

`beregnKostbasis()` selv er urørt — den er en robust beregningsfunksjon som bevisst håndterer historiske data (inkl. eventuell gammel skjev data) uten å kaste. Fiksen legger i stedet inn en sperre der nye transaksjoner faktisk registreres.

- [x] Valider salgsantall mot gjeldende beholdning før registrering — ny delt hjelpefunksjon `_registrerTransaksjonFraRad()` (portefolje.js), brukt av både mobil-kortvisningen og desktop-tabellvisningen (som tidligere hadde identisk, duplisert registreringslogikk)
- [x] Vis feilmelding i UI ved forsøk på oversalg — `alert()`, konsistent med eksisterende validering andre steder i kodebasen (JSON-import, QR-import)

Verifisert direkte mot `beregnKostbasis()`: forsøk på å selge 1000 av 100 blokkeres, selge 50 eller nøyaktig 100 av 100 godtas, selge noe man aldri har eid (0) blokkeres. 60/60 eksisterende tester grønne (ingen regresjon i `beregnKostbasis()` selv).

### B7. Villedende IRR-feilmelding ✅
**Prioritet: Lav**

`beregnIRR()` returnerte «trenger transaksjoner» for fire ulike årsaker under ett: ingen transaksjoner i det hele tatt, `terminalVerdi <= 0` (solgt alt / mangler prisdata), for kort periode (< 30 dager), og manglende Newton-Raphson-konvergens. Alle fire ble vist identisk, selv når brukeren hadde mange registrerte transaksjoner.

- [x] Skill meldingene — hver `return { harNokData: false }`-gren i `beregnIRR()` har nå en egen `arsak`-kode (`ingen_transaksjoner`, `ingen_beholdning`, `for_kort_periode`, `ingen_konvergens`), og UI-en (`portefolje.js`) slår opp presis tekst per årsak i stedet for det tidligere binære `forKort`-flagget

Verifisert direkte mot `beregnIRR()` for alle fire grener, inkludert et scenario for `ingen_konvergens` (99,5 %+ kurstap trigger Newton-Raphsons `rNy <= -1`-brudd pålitelig). Tre nye tester i `tests/portefolje.test.js`, 63/63 grønne.

### B8. Service worker venter ikke på cache-skriving ✅
**Prioritet: Lav — race condition, sjelden synlig**

I `sw.js` ble `caches.open(...).then(c => c.put(...))` kalt tre steder (aksjer.json, HTML-navigasjon, JS/CSS) uten å returneres/awaites inn i `event.respondWith()`-kjeden eller sendes til `event.waitUntil()`. Ble SW-prosessen drept før promisen løste (mobil bakgrunnsbegrensning, rask navigering), ble cachen aldri skrevet — offline-fallback ble upålitelig over tid.

- [x] Kjed cache-skrivingen til `event.waitUntil()` — de tre identiske forekomstene er samlet i en delt `networkFirstMedBakgrunnsCache()`-funksjon, som svarer med nettverksresponsen umiddelbart mens `waitUntil()` holder SW-en i live til cache-skrivingen fullfører i bakgrunnen

Verifisert med en simulert SW-kontekst i Node: `respondWith()` løses før cache-skrivingen er ferdig (responsen forsinkes ikke), `waitUntil()` kalles nøyaktig én gang per fetch-event, og cache-skrivingen fullfører når den promisen ventes på. Rørte ikke `CACHE`-versjonsstrengen (styres av deploy-workflowen, ikke manuelt).

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

### N3. Betalingskalender — «Når får jeg utbytte?» ✅
**Prioritet: Høy — svarer på det mest stilte spørsmålet**

Levert 2026-07-05 som **«Min utbyttelønn»** i Portefølje → Statistikk → Inntekt
(gikk lenger enn opprinnelig skisse: 12 mnd rullerende prognose i stedet for kalendervisning).

- [x] 12-måneders kontantstrømprognose med daterte utbetalinger per aksje
- [x] Vis kun aksjer i brukerens portefølje
- [x] Månedssøyler + tidslinje med forventet betalingsdato og beløp
- [x] Brutto/netto (skjermingsfradrag + 37,84 %) og ≈ per måned
- [x] Skiller «annonsert» (fremtidig betalings-/ex-dato fra børsdata) fra «estimat» (rullet frem fra betalingsmønster)
- [x] Ren, testbar prognosefunksjon (`beregnUtbyttePrognose`) med 8 enhetstester

### N4. Reinvesteringskalkulator (DRIP) ← fra ROADMAP.md #35 ✅
**Prioritet: Høy**

- [x] Inndata: startbeløp, månedlig sparing, yield, kursvekst, antall år
- [x] Beregn porteføljeverdi med og uten reinvestering (begge beregnes alltid)
- [x] SVG-graf: blå linje (med DRIP) vs. stiplet grå (uten DRIP) — renters rente-effekten over tid
- [x] DRIP-gevinst stat-kort viser differansen mellom de to scenariene
- [x] Checkbox styrer hvilken kolonne tabellen viser

---

## 📈 Medium prioritet

### N5. Sammenlign aksjer side ved side ✅
**Prioritet: Medium**

- [x] Velg 2–3 aksjer og vis dem i en sammenligningstabell
- [x] Sammenlign: yield, payout, vekst, P/E, P/B, score, historikk
- [x] Del-lenke: `?sammenlign=EQNR,DNB,ORK`

### N6. Skattesammendrag — årsoppsummering
**Prioritet: Medium**

Skjermingsfradrag er allerede beregnet. Mangler en samlet årsvisning for skattemeldingen.

- [ ] Ny seksjon i Statistikk-fanen: «Skatteåret {år}»
- [ ] Totalt mottatt utbytte dette år (fra transaksjonslogg)
- [ ] Skjermingsfradrag totalt
- [ ] Skattepliktig utbytte (etter fradrag)
- [ ] Estimert skatt å betale (37,84 %)
- [ ] Eksporter som PDF eller kopier til utklippstavle

### N7. Portefølje-rebalansering ✅
**Prioritet: Medium**

- [x] Bruker setter inn ønsket vekting per sektor (f.eks. 30 % Energi, 20 % Finans)
- [x] App viser avvik fra mål og hvilke aksjer å kjøpe/selge

### N8. Månedlig utbytteplanlegger ← fra ROADMAP.md #38
**Prioritet: Medium**

- [ ] Mål-input: ønsket månedsinntekt fra utbytte (f.eks. 10 000 kr/mnd)
- [ ] Beregn nødvendig investert kapital basert på porteføljens vektede yield
- [ ] Vis fremgang: «Du er X % av veien til målet ditt»

### N9. Dynamisk meta-beskrivelse i fetch_stocks.py ✅
**Prioritet: Medium — vedlikeholdsforbedring**

I dag er antallet hardkodet i HTML. Bør genereres automatisk.

- [x] `fetch_stocks.py` oppdaterer `<meta name="description">` og JSON-LD i `index.html` med riktig antall aksjer
- [x] Tilsvarende for `og:description` og `twitter:description`

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

### T11. kurs_historikk utgjør 1,18 MB av 1,54 MB i aksjer.json
**Prioritet: Medium — unødvendig payload ved hver sidelast**

`kurs_historikk` (5 år ukentlige kurspunkter × 162 aksjer) brukes kun to steder — begge i modalen for én enkelt aksje (`ui.js:23`, `ui.js:2689`). Likevel lastes hele feltet for alle 162 aksjer ved hver sidelast, og filen ligger i service workerens `PRECACHE` (`sw.js:25`) og hentes derfor på nytt ved hvert deploy. Gzippet er `aksjer.json` 374 kB — ikke katastrofalt, men grafdata for 161 aksjer brukeren aldri åpner er ren overhead.

- [ ] Vurder å splitte `kurs_historikk` ut i egne filer per ticker (`data/kurs/{TICKER}.json`), hentet ved modalåpning
- [ ] Fjern `kurs_historikk` fra hovedresponsen i `aksjer.json` når/hvis dette gjøres

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

### N17. Swipe-navigasjon mellom faner ✅
**Prioritet: Lav**

- [x] Touch-swipe venstre/høyre bytter mellom alle faner
- [x] Scroll til toppen automatisk ved fanebyttting

### N18. «Tilbake til toppen»-knapp ✅
**Prioritet: Lav**

- [x] Vises etter scroll > 300px
- [x] Sticky, nedre høyre hjørne, lite og diskret

---

*Sist oppdatert: april 2026*
