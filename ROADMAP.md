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
| Snitt yield 5 år + stolpediagram historikk | ✅ Ferdig |
| Sortering på snitt yield 5 år | ✅ Ferdig |
| Yahoo Finance robusthet (5-punkts validering) | ✅ Ferdig |

---

## Veikart

### 1. SEO — synlighet på Google 🔍
**Status: ✅ Ferdig**

- [x] `<meta name="description">` på alle sider
- [x] Open Graph-tags (tittel, beskrivelse, URL)
- [x] Twitter Card-tags
- [x] Canonical URL
- [x] JSON-LD strukturert data (WebSite-schema)
- [x] `sitemap.xml`
- [x] `robots.txt`

---

### 2. Favoritter / huskeliste 🔖
**Status: Planlagt**

Brukere kan stjernemerke sine favorittaksjer og få disse øverst i listen. Lagres i `localStorage` — ingen pålogging nødvendig.

- [ ] Stjerneikon per aksje (tabell og kort)
- [ ] Filter: "Vis kun favoritter"
- [ ] Favoritter vises øverst ved default

---

### 3. Utbytte-score (1–10) ⭐
**Status: ✅ Ferdig**

Sammensatt poengsum per aksje som rangerer utbyttekvalitet — ikke bare størrelse. Gjør det enkelt å skille "høy yield men ustabil" fra "moderat yield men svært pålitelig".

Formel:
- Yield-nivå: 0–3 poeng
- Payout ratio (bærekraft): 0–2 poeng
- Utbyttevekst 5 år: 0–2 poeng
- År med sammenhengende utbytte: 0–2 poeng
- Snitt yield 5 år vs. dagens yield: 0–1 poeng

- [x] Beregningslogikk i `app.js`
- [x] Score-badge per aksje i tabell og kort
- [x] Sorteringsalternativ: "Høyest score"
- [x] Forklaring av score i modal

---

### 4. Porteføljekalkulator 💰
**Status: ✅ Ferdig**

Brukere taster inn antall aksjer de eier → siden beregner forventet årlig utbytteinntekt, månedlig fordeling og neste utbytteutbetaling. Ingen norsk konkurrent tilbyr dette.

- [x] Input: antall aksjer per selskap (lagres i localStorage)
- [x] Beregn: forventet utbytte per år, per kvartal og totalt
- [x] Vis: kvartalsvis distribusjon som strekdiagram
- [x] Eksport til CSV (BOM for norsk Excel-kompatibilitet)
- [x] Klikk på aksjer → modal med fullstendig detaljer
- [x] Søk i beholdning
- [x] Vektet yield og total porteføljeverdi i sammendrag

---

### 4b. CSV-import av portefølje 📥
**Status: Planlagt (avvent)**

Brukere kan laste opp en CSV-fil (f.eks. eksportert fra nettbanken) for å importere beholdningen sin automatisk.

- [ ] Parser CSV-format: ticker + antall kolonner
- [ ] Valider tickers mot kjente aksjer i systemet
- [ ] Feilmelding ved ukjente tickers
- [ ] Forhåndsvisning før import bekreftes
- [ ] Støtte for eksisterende eksport-format (round-trip)

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

- [x] Yield-validering i Python: 5-punkts sanity-sjekk med strukturert rapport
- [ ] Unit-tester for `fetch_stocks.py`
- [ ] Automatisk Lighthouse-rapport i CI

### Manglende historiske utbytter for 8 aksjer

**Årsak:** Yahoo Finance returnerer tom dividend-serie eller tom kursserie for disse aksjene. Uten begge kan vi ikke beregne yield per år.

**Berørte aksjer (per mars 2026):** COOL, FLNG, GOGL, PGS, PNORD, SBVG, SRBNK, WILS

**Mulige løsninger:**
- [ ] Manuell backup-data for kjente utbytter (hardkodes i `fetch_stocks.py`)
- [ ] Alternativ datakilde for Oslo Børs (alle kjente APIer krever betalt plan)
- [ ] Vise tydelig "Historikk ikke tilgjengelig fra Yahoo Finance" i modalen i stedet for å vise ingenting

---

## Bidrag

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
