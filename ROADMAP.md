# exday.no — Prosjektoversikt og veikart

Norsk utbytteaksje-tracker for Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00 og siden hostes på GitHub Pages.

---

## Ferdig ✅

- **1. Favoritter** — stjerneikon, filter og prioritert visning
- **2. Porteføljakalkulator** — forventet utbytte/år, vektet yield, tidslinje
- **3. CSV eksport og import** — round-trip med forhåndsvisning; profil-metadata inkludert
- **4. Kalender** — kommende ex-datoer og betalingsdatoer, filtrerbar per måned
- **5. Historiske data og 5-årssnitt** — utbyttegraf per aksje, snitt yield sorterbar kolonne
- **6. Utbyttescore** — automatisk score 0–10 basert på yield, payout, vekst og historikk
- **7. SEO og synlighet** — sitemap, JSON-LD Dataset-schema, semantisk markup
- **8. PWA + push-varsler** — installerbar app, Service Worker, push-varsler for ex-datoer
- **9. Branding** — logo lys/mørk, favicon, PWA-ikon
- **10. GDPR / personvernside** — dokumentasjon av lokal datalagring
- **11. Utbyttekalkulator over tid** — DRIP-reinvestering, år-for-år-tabell
- **12. Fargedesign** — dempede farger, nøytral tabellhover
- **13. Daglig engasjement** — besøksstreak, milepæl-toasts, "Hva skjer i dag?"
- **14. Porteføljesynkronisering** — QR-kode for overføring mellom enheter
- **15. Velkomstmelding** — onboarding-modal for nye brukere med profil-oppsett
- **16. Personlig profil og mål** — navn, månedlig utbyttemål, hilsen på dashboard
- **17. "Hva skjer i dag?"** — ex-dato i dag/morgen, utbetaling denne uken, siste sjanse
- **18. Notat og prisvarsler** — notatfelt og målpris per aksje i modal
- **19. Streaks og milepæler** — 🔥-streak i header, toast ved porteføljemilepæler
- **20. Lavthengende forbedringer** — sortering huskes, `?aksje=`-param, score-forklaring, søk huskes
- **21. Innstillinger-panel og onboarding** — tannhjul-meny med Profil + Varsler; utvidet profil med sparemål
- **22. Portefølje sub-tabs** — Beholdning og Statistikk som egne faner; ekstra nøkkeltall (P/E, utbetalinger/år, sparemål-fremgang, porteføljeprofil)

---

## Planlagt

### 23. Sparemål-progresjon på dashbordet 🎯
**Prioritet: Høy — lav innsats**

- [ ] Fremgangsbar på dashboard: "15 232 kr av 500 000 kr (3%)"
- [ ] Vises kun når sparemål er satt i profilen
- [ ] Oppdateres automatisk når portefølje endres

---

### 24. Del-link for enkeltaksjer 🔗
**Prioritet: Høy — lav innsats**

`?aksje=EQNR` fungerer allerede. Gjør det lett å dele.

- [ ] "Del"-knapp i aksjemodal som kopierer URL til clipboard
- [ ] Visuell bekreftelse (f.eks. "Kopiert!" i 2 sekunder)

---

### 25. Individuelle aksjesider for SEO 📄
**Prioritet: Høy — SEO-gevinst**

Utvid `fetch_stocks.py` til å generere én HTML-side per aksje.

- [ ] `aksjer/TICKER/index.html` genereres av fetch_stocks.py
- [ ] Innhold: navn, ticker, sektor, pris, yield, ex-dato, beskrivelse, historisk tabell
- [ ] SEO-metadata: `<title>`, `<meta description>`, canonical URL, JSON-LD
- [ ] Oppdater `sitemap.xml` med alle aksje-URL-er
- [ ] `/aksjer/index.html` — oversiktsside som inngangspunkt

---

### 26. Historisk porteføljeutvikling 📈
**Prioritet: Medium**

- [ ] Daglig snapshot av porteføljeverdien i localStorage
- [ ] Kurve på Statistikk-fanen: porteføljeverdi siste 30 dager

---

### 27. Full backup — JSON-eksport og -import 💾
**Prioritet: Medium**

- [ ] JSON-eksport: portefølje, favoritter, notater, målpriser, profil
- [ ] JSON-import med forhåndsvisning og bekreftelse

---

### 28. Utbyttekalender med ICS-eksport 📅
**Prioritet: Lav-medium**

- [ ] `.ics`-fil med ex-datoer og betalingsdatoer for aksjer i porteføljen
- [ ] Kompatibel med Google Kalender, Apple Kalender og Outlook

---

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
