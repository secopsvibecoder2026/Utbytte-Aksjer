# exday.no — Prosjektoversikt og veikart

Norsk utbytteaksje-tracker for Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00 og siden hostes på GitHub Pages.

---

## Ferdig ✅

### 1. Favoritter / huskeliste 🔖
Stjerneikon per aksje, filter for kun favoritter, favoritter vises øverst.

### 2. Porteføljakalkulator 📊
Legg til aksjer med antall, se forventet utbytte per år/måned, vektet yield, porteføljeverdi, neste utbetaling og tidslinje.

### 3. CSV eksport og import 📥
Eksporter portefølje til CSV og importer tilbake. Støtte for round-trip og forhåndsvisning før import bekreftes.

### 4. Kalender 📅
Oversikt over kommende ex-datoer og utbetalingsdatoer. Filtrerbar per måned.

### 5. Historiske data og 5-årssnitt 📈
Historisk utbyttegraf per aksje, snitt yield siste 5 år som sorterbar kolonne.

### 6. Utbyttescore 🏅
Automatisk score (0–10) per aksje basert på yield, payout ratio, vekst og antall år med utbytte.

### 7. SEO og synlighet 🔍
Sitemap med `<lastmod>`, JSON-LD Dataset-schema, semantiske `<h2>`/`<h3>`-overskrifter.

### 8. PWA + push-varsler for ex-datoer 📲
Installerbar app, offline-støtte via Service Worker, push-varsler for valgte aksjer.

### 9. Branding — exday.no 🎨
Ny logo (lys/mørk variant), favicon, PWA-ikon, app-ikon. Byttet ut placeholder-design.

### 10. GDPR / personvernside 🔒
Dokumentasjon av all lokal datalagring (localStorage + Cache API). Mørkemodusfix og oppdatert favicon.

### 11. Utbyttekalkulator over tid 🧮
Beregn yield over tid med startbeløp, yield %, kursvekst, månedlig sparing og DRIP-reinvestering. År-for-år-tabell.

### 12. Fargedesign — tonet ned 🖌️
Fjernet fire ulike farger på toppkortene. Dempede yield-badges, nøytral tabellhover, sorteringspiler og vekstfarger.

---

## Planlagt

### 13. Daglig engasjement — gjør appen til en vane 🔁

#### 13a. Inntektsteller — "Hva har jeg tjent i år?" ⭐
- [ ] "Hittil i år: X kr" basert på betalingsdatoer som har passert for porteføljeaksjene
- [ ] Valgfritt årsmål med progress-bar

#### 13b. Personlig "I dag"-dashboard
- [ ] Erstatt generiske toppkort med personlige når bruker har portefølje/favoritter
- [ ] "Ex-dato denne uken", "Neste utbetaling", "Siste sjanse"
- [ ] Fallback til generiske stats hvis ingen data

#### 13c. Opportunity feed
- [ ] Aksjer med ex-dato innen 10 dager OG yield ≥ 5%, sortert etter dager til ex-dato

---

### 14. Porteføljesynkronisering mellom enheter 📱↔️💻

#### 14a. QR-kode for overføring ⭐
- [ ] "Send til mobil"-knapp som genererer QR-kode med porteføljedata
- [ ] QR-koden er gyldig i 5 minutter, ingen server involvert
- [ ] Mottaker-siden oppdager `?pf=`-parameteren og viser forhåndsvisning

#### 14b. CSV som manuell backup (allerede bygget ✅)

---

## Bidrag

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
