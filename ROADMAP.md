# exday.no — Prosjektoversikt og veikart

Norsk utbytteaksje-tracker for Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00 og siden hostes på GitHub Pages.

Fullførte funksjoner er dokumentert i [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md).

---

## Planlagt

### 25. Individuelle aksjesider for SEO 📄
**Prioritet: Høy — SEO-gevinst**

Utvid `fetch_stocks.py` til å generere én HTML-side per aksje.

- [ ] `aksjer/TICKER/index.html` genereres av fetch_stocks.py
- [ ] Innhold: navn, ticker, sektor, pris, yield, ex-dato, beskrivelse, historisk tabell
- [ ] SEO-metadata: `<title>`, `<meta description>`, canonical URL, JSON-LD
- [ ] Oppdater `sitemap.xml` med alle aksje-URL-er
- [ ] `/aksjer/index.html` — oversiktsside som inngangspunkt

---

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
