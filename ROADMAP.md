# exday.no — Prosjektoversikt og veikart

Norsk utbytteaksje-tracker for Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00 og siden hostes på GitHub Pages.

Fullførte funksjoner er dokumentert i [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md).

---

## Planlagt

### Teknisk gjeld

#### T4b. Validering av datapipeline 🧪
**Prioritet: Medium**

- [ ] Varsle i GitHub Actions hvis yield > 30%, pris = 0, eller manglende felt på mer enn halvparten av aksjene i `fetch_stocks.py` output

#### T5. Minifisering og byggesteg ⚡
**Prioritet: Lav**

- [ ] Sett opp esbuild eller Vite for å minifisere JS/CSS
- [ ] Potensielt 50–60% reduksjon i filstørrelse
- [ ] Oppdater GitHub Actions workflow til å kjøre build før deploy

---

### SEO og vekst

#### 29. Google Search Console — sitemap-innsending 🔍
**Prioritet: Høy — raskest SEO-gevinst**

- [ ] Verifiser exday.no i Google Search Console
- [ ] Send inn sitemap.xml (69 URL-er inkl. alle aksjesider)
- [ ] Sjekk indekseringsstatus for aksjer/TICKER/-sidene

#### 30. Sektorsider 📂
**Prioritet: Medium — flere SEO-landingssider**

- [ ] Generer `aksjer/sektor/energi/`, `aksjer/sektor/finans/` osv. i fetch_stocks.py
- [ ] Oversiktsside per sektor med alle aksjer i sektoren
- [ ] Legg til i sitemap.xml
- [ ] Interne lenker fra enkeltaksjesider til sektorsiden

#### 31. Interne lenker mellom app og aksjesider 🔗
**Prioritet: Medium**

- [ ] Legg til lenke fra aksjemodal i hovedappen til `exday.no/aksjer/TICKER/`
- [ ] Lenken åpner SEO-siden med full info og historikk

#### 32. Flere aksjer 📈
**Prioritet: Medium**

- [ ] Gjennomgå Oslo Børs for aksjer som mangler
- [ ] Legg til i AKSJER-listen i fetch_stocks.py

---

### Portefølje og analyse

#### 35c. TWR/IRR — tidsavhengig avkastning 💹
**Prioritet: Lav**

Faktisk avkastning (punkt 35b) er på plass. Neste steg er tidskorrigert beregning.

- [ ] Beregn TWR (Time-Weighted Return) ved å splitte perioden på transaksjonsdata
- [ ] Alternativt IRR via Newton–Raphson basert på kontantstrøm
- [ ] Sammenlign direkte mot OSEBX TWR i Historikk-kurven

---

### Monetisering

#### 33. AdSense-godkjenning og annonseenheter 💰
**Prioritet: Høy — avventer Googles gjennomgang**

- [ ] Vente på AdSense-godkjenning
- [ ] Vurdere manuelle annonseenheter i tillegg til auto-ads
- [ ] Teste annonsevisning og samtykkeflyt

---

### Brukeropplevelse

#### 34. Mobilgjennomgang 📱
**Prioritet: Medium**

- [ ] Grundig test på mobil etter alle nylige endringer
- [ ] Særlig: Statistikk-fanen, Innstillinger-modal, kalendervisning
- [ ] Vurdere forenkling av Portefølje-fanen (4 sub-tabs + valg er mye på liten skjerm)

---

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
