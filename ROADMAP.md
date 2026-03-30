# exday.no — Prosjektoversikt og veikart

Norsk utbytteaksje-tracker for Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00 og siden hostes på GitHub Pages.

---

## Status

| Område | Status |
|---|---|
| 44 aksjer med live data | ✅ Ferdig |
| Tabell + kortsvisning (desktop/mobil) | ✅ Ferdig |
| Kompakt/detaljert visning | ✅ Ferdig |
| Mørk/lys modus | ✅ Ferdig |
| Historiske utbytter (5 år) + stolpediagram | ✅ Ferdig |
| 52-ukers kursrange med fargekoding | ✅ Ferdig |
| Utbyttekalender | ✅ Ferdig |
| Filtrering og sortering | ✅ Ferdig |
| Google Analytics + AdSense Auto Ads | ✅ Ferdig |
| GDPR cookie-samtykke + personvernside | ✅ Ferdig |
| Skeleton loader | ✅ Ferdig |
| Custom domene (exday.no) | ✅ Ferdig |

---

## Veikart

### 1. SEO — synlighet på Google 🔍
**Status: Pågår**

Siden mangler i dag meta-beskrivelse, Open Graph-tags og strukturert data. Noen som søker "norske utbytteaksjer" eller "DNB utbytte 2026" vil ikke finne siden organisk.

- [ ] `<meta name="description">` på alle sider
- [ ] Open Graph-tags (tittel, beskrivelse, URL, bilde)
- [ ] Twitter Card-tags
- [ ] Canonical URL
- [ ] JSON-LD strukturert data (WebSite + tabell-data)
- [ ] `sitemap.xml`
- [ ] `robots.txt`

---

### 2. Favoritter / huskeliste 🔖
**Status: Planlagt**

Brukere kan stjernemerke sine favorittaksjer og få disse øverst i listen. Lagres i `localStorage` — ingen pålogging nødvendig.

- [ ] Stjerneikon per aksje (tabell og kort)
- [ ] Filter: "Vis kun favoritter"
- [ ] Favoritter vises øverst ved default

---

### 3. Utbytte-score (1–10) ⭐
**Status: Planlagt**

Sammensatt poengsum per aksje som rangerer utbyttekvalitet — ikke bare størrelse. Gjør det enkelt å skille "høy yield men ustabil" fra "moderat yield men svært pålitelig".

Formel (forslag):
- Yield-nivå: 0–3 poeng
- Payout ratio (bærekraft): 0–2 poeng
- Utbyttevekst 5 år: 0–2 poeng
- År med sammenhengende utbytte: 0–2 poeng
- Snitt yield 5 år vs. dagens yield: 0–1 poeng

- [ ] Beregningslogikk i `app.js`
- [ ] Score-badge per aksje i tabell og kort
- [ ] Sorteringsalternativ: "Høyest score"
- [ ] Forklaring av score i modal

---

### 4. Porteføljekalkulator 💰
**Status: Planlagt**

Brukere taster inn antall aksjer de eier → siden beregner forventet årlig utbytteinntekt, månedlig fordeling og neste utbytteutbetaling. Ingen norsk konkurrent tilbyr dette.

- [ ] Input: antall aksjer per selskap (lagres i localStorage)
- [ ] Beregn: forventet utbytte per år, per kvartal og totalt
- [ ] Vis: tidslinje over når utbetalingene kommer
- [ ] Eksport til CSV

---

### 5. PWA + push-varsler for ex-datoer 📲
**Status: Planlagt**

Installer siden på hjemskjermen som en app. Brukere kan abonnere på varsler: *"SRBNK ex-dato er om 3 dager"*.

- [ ] `manifest.json` (navn, ikon, farger)
- [ ] Service Worker for offline-støtte
- [ ] Push-varsel-integrasjon (Web Push API)
- [ ] Innstillingsside: velg hvilke aksjer du vil ha varsler for

---

## Teknisk gjeld

- [ ] Yield-validering i Python: sanity-sjekk beregnet yield mot Yahoo-felt, varsle ved avvik > 20%
- [ ] Unit-tester for `fetch_stocks.py`
- [ ] Automatisk Lighthouse-rapport i CI

---

## Bidrag

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
