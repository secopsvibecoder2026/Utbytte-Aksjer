# exday.no — Veikart

Norsk utbytteaksje-tracker for Oslo Børs. Fullførte funksjoner: [ROADMAP_COMPLETED.md](ROADMAP_COMPLETED.md)

---

## Høy prioritet

### Datakvalitet — aksjer uten utbyttedata ✅ (løst annerledes enn planlagt, 12.09.2026)
Punktet listet 15 aksjer med `upa=0`, `yield=0`, `hist=0` og foreslo å fjerne dem fra
`tickers.json`. **Det viste seg å være for bredt, og ble ikke gjennomført slik.**

Da listen ble kontrollert falt de i to grupper:

- **Sju er tomme skall** — ACR, AFISH, BWE, CADLR, DOF, ISLAX, KMAR. De har verken
  yield, historikk eller år med utbytte, og har fått `noindex,follow` og er ute av
  sitemap. Ikke slettet: sidene brukes av appen og ved direktebesøk.
- **Resten har ekte utbyttehistorikk** og har bare sluttet å betale — NKR, NOD, KOA,
  BORR, HEX og flere. Å fjerne dem ville tatt bort sider som gjør jobben sin: den som
  søker «Scatec utbytte» er godt tjent med å få vite at selskapet betalte fram til
  2023 og så stoppet.

- [x] `uten_utbyttebevis()` i `fetch_stocks.py` styrer både malen og sitemap, så de to
      ikke kan komme i utakt. Tester: `TestUtenUtbyttebevis`, som dekker nettopp
      grensen mellom de to gruppene.
- [x] KMCP er ikke lenger på listen — den er omdøpt til **BINT** (Bevest ASA), ikke
      uten data. Se `/avnoteringer/`.
- [x] PGS fjernet 04.09.2026 — avnotert 2. juli 2024 etter fusjonen inn i TGS.

### Datakvalitet — fiks misvisende snitt_yield_5ar i fetch_stocks.py ✅
Historisk yield beregnes mot *dagens* kurs (bevisst designvalg for konsistent visning). For aksjer der kursen har kollapset ga det meningsløse tall: 2020 Bulkers viste 5-årssnitt på **1104 %** med et enkeltår på 3623 %.

- [x] `hent_historiske_utbytter()` faller nå tilbake til **årets faktiske sluttkurs** når dagens-kurs-basisen gir over 100 % — altså yielden en investor det året faktisk fikk. Året markeres med `yield_basis: "arsslutt"` så avviket er synlig i dataene.
- [x] Er tallet urimelig mot *begge* basiser, står ikke utbyttet i forhold til kursen i det hele tatt (typisk manglende splittjustering hos Yahoo). Da settes `yield` til `null` og året utelates fra snittet — «—» er ærligere enn «3623 %». Utbyttebeløpet beholdes; det er riktig og driver søylediagrammet.
- [x] `snitt_yield_5ar` settes til `null` (ikke `0.0`) når ingen yield er troverdig — `0.0` leste som «betaler ingenting».

Rettet i eksisterende data samtidig: 2020 (1104 → 17,06 %), HUNT (203 → 14,71 %), OTEC (121 % → null), WEST (51,15 → 37,16 %), GSF (37,66 → 10,35 %). `valider_data.py` gir nå null advarsler, mot tidligere HUNT på 308 % og 475 %.

- [ ] ~~Vis advarsel på sider der `snitt5ar > 50%`~~ — mindre relevant nå; WEST på 37 % er høyeste gjenværende

### Prisvarsel via push-notifikasjon
`malPris`-feltet og push-infrastruktur finnes allerede i Service Worker.
- [ ] Legg til `malPris`-sjekk i `sjekkExDatoer()` i `sw.js`
- [ ] Send varsel: «{TICKER} har truffet målprisen din på {pris} kr»
- [ ] Lagre «varslet»-flagg per målpris for å unngå gjentatte varsler

### Import fra Nordnet/DNB CSV
Ny bruker bruker lang tid på manuell innlegging. Nordnet eksporterer CSV med Dato, Ticker, Antall, Kurs.
- [ ] Parser for Nordnet-transaksjonseksport
- [ ] Parser for DNB Aksjehandel-eksport
- [ ] Preview-modal med deduplisering

### AdSense-optimalisering
- [ ] Manuell annonseenhet mellom sammendragskort og aksjelist
- [ ] Manuell annonseenhet i bunnen av aksjemodal
- [ ] Rapporter klikk-rate og RPM i GA4

### Automatisk publisering til Facebook og Instagram
**Utsatt til AdSense er godkjent** (måldato 06.10.2026 — se «AdSense: timeline» i
CLAUDE.md). Ikke fordi det er teknisk avhengig, men fordi oppmerksomheten bør ligge
på søknaden først.

Mye av grunnlaget finnes allerede: Actions kjører 4× daglig, `/promo/` har ferdige
SVG/PNG-maler, og siden ligger statisk på GitHub Pages — som er nyttig i seg selv,
fordi **Instagram krever en offentlig bilde-URL** og henter bildet selv. Jobben er i
praksis ett workflow-steg, ikke ny infrastruktur.

**Kjør disse to før noe bygges — de kan gjøres i dag og avgjør omfanget:**

- [ ] **Test om et innlegg fra en app i utviklingsmodus er offentlig synlig.**
      Dette er det eneste som avgjør om prosjektet er en ettermiddag eller en måned.
      Kildene spriker: én sier innlegg i utviklermodus bare ses av sideadministratorer,
      en annen at «Standard Access» på egen side holder. Er svaret det første, kreves
      app review — 2–4 uker. Test med ett innlegg fra en tom testapp.
- [ ] **Konverter Instagram til Business- eller Creator-konto.** Personlige kontoer
      har ikke API-tilgang. Gratis og reversibelt, men det er en endring på kontoen.
      For posting til *egen* konto trengs ingen app review — utviklingsmodus pluss
      Instagram Tester-rolle holder.

**Selve byggingen:**

- [ ] Workflow som bygger bildet, committer det til en offentlig sti, og kaller
      Graph API. Instagram publiserer i to steg: `POST /{ig-user-id}/media` lager en
      container, `POST /{ig-user-id}/media_publish` publiserer den.
- [ ] Langlevd Page Access Token i Actions secrets — ikke i repoet.
- [ ] **`valider_data.py` må gate posten, ikke bare deployen.** Dette repoet har en
      dokumentert historikk med feil tall som når ut på sider — SNTIA med 14 % mot
      faktiske 6,9 %, `ai_oppsummering` frosset i to måneder. En nettside kan rettes
      stille; et Facebook-innlegg med feil yield kan ikke det.

> ⚠️ **`/promo/` er blokkert i robots.txt** siden 12.09.2026 (mappen er grafikk til
> sosiale medier, ikke innhold for lesere). Om Metas bildehenter respekterer
> robots.txt er uavklart — det kan altså komme i veien for nettopp denne flyten.
> Test det, og løs eventuelt med en egen mappe eller en `Allow:`-regel.

### Statisk forside — SEO-vennlig frontdoor for exday.no

**Bakgrunn:** Google ser i dag en JavaScript-tung SPA på `exday.no/` og flagget siden for tynt innhold. Løsningen er ikke å flytte appen (stor migrasjonsrisiko, ingen server-side routing på GitHub Pages), men å erstatte `index.html` med en statisk landing page som laster appen ved klikk. Google indekserer statisk HTML — brukere som vil ha appen klikker én knapp.

**Arkitektur etter endringen:**
```
exday.no/              → statisk landing page (ny index.html)
exday.no/#app          → SPA lastes når bruker klikker «Åpne appen»
exday.no/utforsk/      → navigasjonshub (eksisterer)
exday.no/aksjer/       → SEO-sider (eksisterer)
exday.no/artikler/     → innhold (eksisterer)
```

**Hva landing page-en skal inneholde (alt statisk HTML):**
- [ ] Hero: tittel, ingress og «Åpne appen»-knapp (laster SPA inline eller navigerer til `/#app`)
- [ ] 3–4 fremhevede nøkkeltall: antall aksjer, snittavkastning Oslo Børs, neste ex-dato
- [ ] Sektorkort (samme som `/utforsk/`) — gir Google intern lenkestruktur fra roten
- [ ] Siste 3 artikler fra `/artikler/`
- [ ] Lenker til kalender, kalkulator og FAQ
- [ ] Full standard footer med Facebook-lenke

**Tekniske hensyn:**
- [ ] Eksisterende `index.html` (SPA) flyttes til `app.html` eller lastes dynamisk
- [ ] Service Worker må oppdateres: cache `app.html` i stedet for `index.html` for SPA-skallet
- [ ] `sw.js`-deploy-scriptet i `update-og-deploy.yml` må oppdateres tilsvarende
- [ ] Alle interne lenker til `/?tab=kalender` etc. må sjekkes — de fleste går direkte til undersider og er upåvirket
- [ ] `manifest.json` `start_url` bør peke på `app.html` eller `/` med hash

**Risiko:** Middels. SPA-logikken røres ikke — kun shell-filen flyttes. Største risiko er Service Worker-cache og PWA-installasjon for eksisterende brukere.

---

## Medium prioritet


### Skattesammendrag — årsoppsummering
Skjermingsfradrag er allerede beregnet. Mangler samlet årsvisning.
- [ ] Ny seksjon i Statistikk-fanen: «Skatteåret {år}»
- [ ] Totalt mottatt utbytte, skjermingsfradrag, skattepliktig beløp og estimert skatt (37,84%)
- [ ] Eksporter til PDF eller klippebord

### Utbyttebærekraft på aksjekortet
Bærekraft-analyse vises i modal, men ikke i kortvisning.
- [ ] Vurder subtilt ikon (skjold) i stedet for tekst-badge

### Datapipeline-validering
- [ ] Varsel i GitHub Actions ved yield > 30%, pris = 0 eller manglende felt på >50% av aksjene

### Bloggseksjon / artikler
10 artikler planlagt — alle publisert per 30. august 2026 (1 500–3 000 ord, norsk, SEO-optimalisert med JSON-LD, dark mode, samme design som FAQ):

- [x] `/artikler/hva-er-ex-dato/` — Alt om ex-dato: T+2, kursfall, skatt, strategi
- [x] `/artikler/beste-utbytteaksjer-2026/` — Redaksjonell gjennomgang av ledende norske utbytteaksjer
- [x] `/artikler/utbytte-og-skatt/` — Skatteregler: ASK vs. VPS, skjermingsfradrag, 37,84%
- [x] `/artikler/aksjesparekonto-ask/` — Komplett guide til ASK for utbytteinvestorer
- [x] `/artikler/utbytteportefolje-sektorvekting/` — Steg-for-steg: diversifisering, sektorvekting, rebalansering
- [x] `/artikler/reinvestering-av-utbytte/` — DRIP og rentes-rente-effekten over 20 år (med eksempler)
- [x] `/artikler/norske-shippingaksjer/` — Norske shippingaksjer: høy yield, syklisitet, risiko
- [x] `/artikler/sparebanker-oslo-bors/` — Hvorfor sparebanker gir stabile utbytter år etter år
- [x] `/artikler/hva-er-payout-ratio/` — Hva payout ratio forteller deg om utbyttets bærekraft
- [x] `/artikler/slik-leser-du-utbyttekalenderen/` — Slik bruker du utbyttekalenderen til å planlegge kontantstrøm

Også opprett `/artikler/index.html` som oversiktsside for alle artikler.

### Strukturerte data for aksjesider
- [ ] `Corporation`-schema med `tickerSymbol` i JSON-LD
- [ ] `FAQPage`-schema: «Hva er ex-dato for {TICKER}?»

### Ytterligere aksjer
- [ ] Merk aksjer uten live-kurs tydelig («Kurs ikke tilgjengelig»)
- [ ] Undersøk Euronext API for manglende tickers
- [ ] Vurder Oslo Børs Small Cap-aksjer med stabil utbyttehistorikk

---

## Lav prioritet

### Teknisk gjeld

**Virtuell scrolling**
- [ ] Render bare synlige kort + buffer — viktig på mobil med 160+ aksjer

**Splitt ui.js (1 600+ linjer)**
- [ ] `modal.js` for `visModal()` og `scoreForklaring()`
- [ ] `kalender.js` for `visKalender()`

**E2E-tester**
- [x] Playwright: søk aksje → åpne modal → legg i portefølje (`tests/app.e2e.js`, 8 tester)
- [ ] Kjør i GitHub Actions på PR


**Staging-miljø**
- [ ] Netlify-deploy fra `dev`-branch med preview-URL per PR

### Monetisering
- [ ] «Støtt prosjektet»-knapp (Ko-fi / Vipps) — vises etter 5 besøk

---

*Sist oppdatert: april 2026*
