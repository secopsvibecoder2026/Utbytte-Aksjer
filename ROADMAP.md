# exday.no — Prosjektoversikt og veikart

Norsk utbytteaksje-tracker for Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00 og siden hostes på GitHub Pages.

---

## Veikart

### 1. Favoritter / huskeliste 🔖
**Status: Ferdig ✅**

### 2. CSV-import av portefølje 📥
**Status: Ferdig ✅**

### 3. PWA + push-varsler for ex-datoer 📲
**Status: Ferdig ✅**

---

### 4. Daglig engasjement — gjør appen til en vane 🔁
**Status: Planlagt**

Tre funksjoner som i kombinasjon gjør at brukere åpner appen daglig, ikke bare av og til.

#### 4a. Inntektsteller — "Hva har jeg tjent i år?" ⭐ (høyest prioritet)
Utbytteinvestorer tenker i inntekt, ikke kursgevinst. Å se penger akkumulere gir motivasjon til å komme tilbake.
- [ ] "Hittil i år: X kr" — basert på betalingsdatoer som har passert for porteføljeaksjene
- [ ] Valgfritt **årsmål** (brukeren setter f.eks. 50 000 kr) med progress-bar
- [ ] "Du er X% av veien til målet"
- Logikk: `pf_beholdning` × `utbytte_per_aksje` for aksjer der `betaling_dato` er passert i år

#### 4b. Personlig "I dag"-dashboard
Erstatt de 4 generiske kortene øverst med personlige kort når bruker har favoritter/portefølje:
- [ ] **"Ex-dato denne uken"** — dine aksjer med ex-dato innen 7 dager (navn + dager igjen)
- [ ] **"Neste utbetaling"** — dato + beløp fra portefølje
- [ ] **"Siste sjanse"** — aksje med ex-dato ≤3 dager og høy yield
- [ ] Fallback til generiske stats hvis ingen favoritter/portefølje er satt

#### 4c. Opportunity feed — "Verdt å se på nå"
- [ ] Seksjon i Oversikt-fanen med aksjer som har ex-dato innen 10 dager OG yield ≥ 5%
- [ ] Sortert etter dager til ex-dato, med yield-badge

---

## Teknisk gjeld

- [ ] Manglende historikk for 8 aksjer (COOL, FLNG, GOGL, PGS, PNORD, SBVG, SRBNK, WILS) — Yahoo Finance har ikke data. Mulig løsning: manuell backup-data i `fetch_stocks.py`
- [ ] Unit-tester for `fetch_stocks.py`
- [ ] Automatisk Lighthouse-rapport i CI

---

## Bidrag

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
