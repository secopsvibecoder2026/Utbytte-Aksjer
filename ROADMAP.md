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
**Status: Ferdig ✅**

### 14. Porteføljesynkronisering mellom enheter 📱↔️💻
**Status: Ferdig ✅**

---

### 15. Velkomstmelding for nye brukere 👋
**Status: Ferdig ✅**

Pop-up som vises kun ved første besøk. Informerer om prosjektets natur (hobbyprosjekt, hyppige endringer), personvernmodellen (alt lagres lokalt) og datakvalitet (Yahoo Finance, kan inneholde feil). Lagres i localStorage så den ikke vises igjen.

---

## Planlagt

### 16. Personlig profil og mål 🎯
**Status: Ferdig ✅**

Brukeren setter et personlig navn og månedlig utbyttemål. Vises øverst på dashbordet.

- [x] Profil-knapp øverst i hjørnet → enkel modal: navn + månedlig mål i NOK
- [x] "God morgen, Kristian" på dashbordet basert på klokkeslett
- [x] Fremgangsbar mot månedlig mål (estimert utbytte vs. mål)
- [x] Profil lagres i localStorage

---

### 17. Daglig oppdatering — "Hva skjer i dag?" 📰
**Status: Ferdig ✅**

- [x] "Ex-dato i dag / i morgen" — fremhevet for aksjer i portefølje/favoritter
- [x] "Utbetaling denne uken" — hvilke utbetalinger er nær (med estimert beløp)
- [x] "Siste sjanse" — høy-yield aksjer med ex-dato i dag/morgen som brukeren ikke eier
- [x] Oppdateres automatisk ved innlasting uten ekstra kall
- [ ] Kursendring siden forrige dag — krever historisk kurslager, utsatt

---

### 18. Notat og prisvarsler per aksje 📝
**Mål: gjøre appen til et personlig arbeidsverktøy**

- [ ] Notatfelt per aksje i detaljmodalen (lagret i localStorage)
- [ ] "Målpris"-felt: sett ønsket kjøpspris — vises som badge i tabellen når pris er under mål
- [ ] Prisvarsler vises som en samlet liste i et eget panel ("Aksjer nær din målpris")

---

### 19. Streaks og milepæler 🏆
**Mål: belønne daglig bruk og bygge vane**

- [ ] Besøksstreak-teller ("5 dager på rad") — vist diskret i hjørnet
- [ ] Utbyttemilestones: badge når portefølje passerer 1 000 / 10 000 / 100 000 kr estimert/år
- [ ] "Hittil i år"-fremgang — visuell oppdatering når ny utbetaling er registrert i perioden
- [ ] Animasjon / konfetti ved ny milepæl (kan slås av)

---

### 20. Lavthengende forbedringer 🍒

#### 20a. Sortering huskes mellom besøk
Lagre valgt sorteringskolonne og retning i localStorage.

#### 20b. Dele enkeltaksje via URL
`?aksje=EQNR` åpner modalen direkte — gjør det mulig å sende lenker.

#### 20c. Score-forklaring
Tooltip eller infoboks som forklarer hva Score (0–10) faktisk beregnes fra.

#### 20d. Søk huskes ved tabbytte
Søkefeltet tømmes i dag ved tabbytte — vurder å beholde søket.

---

### 21. Individuelle aksjesider for SEO 📄
**Mål: organisk trafikk fra Google på ticker-spesifikke søk**

Utvid `fetch_stocks.py` til å generere én HTML-side per aksje i tillegg til JSON og sitemap. Ingen ny teknologi — samme Python-script, samme GitHub Actions.

- [ ] HTML-template i `fetch_stocks.py` som genererer `aksjer/TICKER/index.html`
- [ ] Innhold per side: navn, ticker, sektor, pris, yield, ex-dato, beskrivelse, historisk tabell
- [ ] SEO-metadata: `<title>`, `<meta description>`, canonical URL
- [ ] JSON-LD schema per side (`WebPage` + nøkkeltall)
- [ ] Oppdater `sitemap.xml` til å inkludere alle aksje-URL-er
- [ ] Intern lenking: "Åpne full oversikt" → tilbake til hovedappen
- [ ] `/aksjer/index.html` — oversiktsside med alle aksjer som inngangspunkt

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
