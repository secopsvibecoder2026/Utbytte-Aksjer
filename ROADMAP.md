# exday.no — Prosjektoversikt og veikart

Norsk utbytteaksje-tracker for Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00 og siden hostes på GitHub Pages.

Fullførte funksjoner er dokumentert i [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md).

---

## Planlagt

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

#### 35. Transaksjonslogg og faktisk avkastning 💹
**Prioritet: Høy — største gap mot konkurrenter**

Lar brukeren registrere kjøp/salg med kurs og dato, og beregner faktisk avkastning i stedet for kun forventet yield.

- [ ] Transaksjonslogg per aksje: dato, antall, kurs, type (kjøp/salg)
- [ ] Beregn kostpris (VWAP) og urealisert gevinst/tap
- [ ] Vis faktisk avkastning inkl. mottatt utbytte (TWR/IRR)
- [ ] Lagres i localStorage under `pf_transaksjoner`

#### 36. Flere porteføljer og watchlister 📋
**Prioritet: Høy**

- [ ] Støtte for flere navngitte porteføljer (f.eks. "Langsiktig", "Pensjon")
- [ ] Watchliste-funksjon separat fra portefølje og favoritter
- [ ] Bytte mellom porteføljer i Portefølje-fanen
- [ ] Lagres som `pf_portefoljer` — objekt med navn og beholdning per portefølje

#### 37. OSEBX-sammenligning 📊
**Prioritet: Medium**

- [ ] Hent OSEBX-historikk (eller bruk indeksverdi fra Yahoo Finance)
- [ ] Vis porteføljens utvikling mot OSEBX på Historikk-kurven
- [ ] "Slår du indeksen?"-indikator på Statistikk-fanen

#### 38. Skatteberegning — skjermingsfradrag 🧾
**Prioritet: Lav**

- [ ] Beregn skjermingsrente på kostpris per posisjon
- [ ] Vis estimert skatt på utbytte (31,68% over skjermingsfradrag)
- [ ] Netto utbytte etter skatt i Statistikk-fanen

---

### Community og deling

#### 39. Offentlige porteføljer / deling 🌐
**Prioritet: Lav**

- [ ] Generer en delbar lenke med porteføljesammendraget (read-only)
- [ ] Viser yield, fordeling og nøkkeltall — ingen persondata
- [ ] Alternativt: lenke til Facebook-gruppe for utbytteinvestorer

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

---

Dette er et privat prosjekt. Kontakt via GitHub Issues for spørsmål eller feilrapporter.
