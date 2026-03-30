# exday.no — Prosjektoversikt og veikart

Norsk utbytteaksje-tracker for Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00 og siden hostes på GitHub Pages.

---

## Veikart

### 1. Favoritter / huskeliste 🔖
**Status: Ferdig ✅**

- [x] Stjerneikon per aksje (tabell, mobilt kort og modal)
- [x] Filter: "Vis kun favoritter"
- [x] Favoritter vises øverst ved default

---

### 2. CSV-import av portefølje 📥
**Status: Planlagt (avvent)**

Brukere kan laste opp en CSV-fil (f.eks. eksportert fra nettbanken) for å importere beholdningen sin automatisk.

- [ ] Parser CSV-format: ticker + antall kolonner
- [ ] Valider tickers mot kjente aksjer i systemet
- [ ] Feilmelding ved ukjente tickers
- [ ] Forhåndsvisning før import bekreftes
- [ ] Støtte for eksisterende eksport-format (round-trip)

---

### 3. PWA + push-varsler for ex-datoer 📲
**Status: Planlagt**

Installer siden på hjemskjermen som en app. Brukere kan abonnere på varsler: *"SRBNK ex-dato er om 3 dager"*.

- [ ] `manifest.json` (navn, ikon, farger)
- [ ] Service Worker for offline-støtte
- [ ] Push-varsel-integrasjon (Web Push API)
- [ ] Innstillingsside: velg hvilke aksjer du vil ha varsler for

---

## Teknisk gjeld

- [ ] Manglende historikk for 8 aksjer (COOL, FLNG, GOGL, PGS, PNORD, SBVG, SRBNK, WILS) — Yahoo Finance har ikke data. Mulig løsning: manuell backup-data i `fetch_stocks.py`
- [ ] Unit-tester for `fetch_stocks.py`
- [ ] Automatisk Lighthouse-rapport i CI

---

## Bidrag

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
