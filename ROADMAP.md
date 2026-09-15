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

**To hindringer funnet 15.09.2026, begge uavhengige av de to sjekkene under.** De
krever ingen Meta-konto og kan fikses når som helst, men de flytter anslaget
«ettermiddag eller måned» og bør være kjent før noen setter av tid.

> ⛔ **Instagram tar ikke PNG.** Metas egen dokumentasjon er utvetydig: «JPEG is the
> only image format supported. Extended JPEG formats such as MPO and JPS are not
> supported.» **Alle åtte bildene i `/promo/` er PNG**, og alle fire generatorene der
> (`generate_image.py`, `facebook_mandag.py`, `generate_kalkulator_post.py`,
> `generate_sparebank_post.py`) skriver PNG. Ingen av dem ville blitt godtatt slik de
> er i dag.
>
> **Fiksen er én linje per generator**, og det er verifisert, ikke antatt: alle fire
> ender med lerretet i RGB-modus (de kaller `.convert("RGB")` etter komponeringen), så
> `img.save(..., "PNG")` kan bli `"JPEG"` uten videre. Hadde lerretet vært RGBA ville
> Pillow kastet «cannot write mode RGBA as JPEG» — JPEG har ingen alfakanal. Sjekk det
> igjen hvis en generator skrives om.
>
> Merk at kravet gjelder *Instagram*; Facebook er mer tolerant, så en flyt som virker
> på Facebook sier ingenting om den andre.

Kilde: [Metas dokumentasjon for content publishing](https://developers.facebook.com/docs/instagram-platform/content-publishing).

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
> sosiale medier, ikke innhold for lesere), og det kan komme i veien for nettopp
> denne flyten.
>
> **Oppdatert 15.09.2026 — fortsatt ikke bekreftet, men nå med et konkret symptom.**
> Flere tredjepartskilder rapporterer feilkode **479**, «social network could not
> download media from this URL», med «Restricted by robots.txt» i detaljene. Det er
> spesifikt nok til å planlegge rundt.
>
> Men det står **ikke** i Metas egen dokumentasjon, som bare krever at bildet ligger
> på «a publicly accessible server» og ikke nevner robots.txt i det hele tatt. Så
> dette er rapportert, ikke verifisert ved kilden — behandle det deretter.
>
> Filene er teknisk tilgjengelige: `promo/facebook-post.png` svarer 200 med
> `image/png`. robots.txt er en instruks, ikke en sperre, så spørsmålet er utelukkende
> om Meta velger å følge den.
>
> **To veier ut, og den andre er mest robust:** en egen `User-agent`-gruppe for Metas
> henter med `Allow: /promo/`, eller å legge de publiserte bildene i en mappe som ikke
> er sperret. Den første forutsetter at vi vet hvilket user-agent-navn henteren
> faktisk bruker — og det vet vi ikke. `robots.txt` er ikke endret; sperren ble satt
> bevisst og skal ikke røres uten at flyten faktisk skal bygges.

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

### Monetisering — donasjoner

**Utsatt, men ikke forkastet** (undersøkt 13.09.2026). Kort konklusjon: det er
teknisk enkelt, men det alternativet publikummet faktisk forventer — Vipps —
krever at prosjektet blir næringsvirksomhet. Det er en større beslutning enn
knappen ser ut som.

**Rammen vi jobber innenfor.** Siden er statisk på GitHub Pages: ingen server,
ingen webhooks, ingen hemmeligheter. Alt må være en **ren utgående lenke**. Det
er også en fordel — en lenke er ingen ny databehandler, så `/personvern/` er
uberørt. En **innebygd widget** er derimot en ny tredjepart og må inn i
tredjepartstabellen der.

| Løsning | Gebyr | Krav | Passer publikum? |
|---|---|---|---|
| GitHub Sponsors | GitHub 0 % på personlige kontoer, Stripe-payout | Ingen org.nr., Norge støttes via Stripe Connect | ❌ krever GitHub-konto |
| Ko-fi | 0 % på engangstips + Stripe ~2,9 % + $0,30 | Ingen org.nr. | ⚠️ kort, ikke Vipps |
| Buy Me a Coffee | 5 % på alt, i tillegg til Stripe | Ingen org.nr. | Strengt dårligere enn Ko-fi |
| Vipps på nett | — | **Org.nr. + bedriftskonto** | ✅ det folk forventer |

> ⚠️ **Vipps-fella.** Vipps for bedrift krever norsk organisasjonsnummer.
> Organisasjonsnummer er gratis i Enhetsregisteret, men registreringsplikten
> gjelder foretak som *driver næringsvirksomhet* — man kan altså ikke registrere
> et ENK for en hobby og beholde hobbystatusen. Å skaffe Vipps er i praksis å
> erklære at dette er næring.
>
> Alternativet, å oppgi eget mobilnummer for privat-Vipps, betyr å publisere
> telefonnummeret sitt på en side med 155 aksjesider. Frarådes.

**Skatt: det finnes ingen kronegrense.** Skatteetaten opererer ikke med et beløp
der hobby blir næring. Vurderingen er fire vilkår — aktiviteten må ha en viss
**varighet**, et visst **omfang**, være **egnet til å gå med overskudd** over
tid, og drives for **egen regning og risiko** — og den er *objektiv*, ikke basert
på hva man selv mener hensikten er.

Det som gjør exday.no sårbart er kostnadsbildet, ikke donasjonene: GitHub Pages
er gratis og domenet koster småpenger, så nesten enhver inntekt blir overskudd.
Kombinasjonen donasjoner **+** AdSense på en side som oppdateres 4× daglig er
nettopp det som ser «egnet til å gå med overskudd» ut. Merk også at etiketten
«donasjon» ikke avgjør skattespørsmålet — en støtteknapp på en tjeneste man
leverer er ikke åpenbart en gave. Blir det reelle beløp, er dette et spørsmål
for regnskapsfører.

**AdSense er ikke i veien.** Donasjonsknapper er tillatt ved siden av annonser.
Den ene reelle fellen er ordlyd som leder oppmerksomhet mot annonsene — «klikk
en annonse hvis du ikke vil donere» er brudd. En ren «støtt prosjektet»-knapp
er det ikke.

**Rekkefølge — og hvorfor vi venter:**

- [ ] **Nå, om ønskelig:** GitHub Sponsors-lenke i bunnteksten. Kontoen finnes,
      koster ingenting, ingen personvernendring, null risiko. Fanger få, men
      koster heller ingenting. *Ikke gjort — venter bevisst.*
- [ ] **Etter AdSense-godkjenning + reell trafikk:** vurder Ko-fi.
- [ ] **Sist, hvis beløpene forsvarer det:** Vipps og ENK vurdert samlet, med
      regnskapsfører.

Grunnen til å vente er ikke AdSense, men regnestykket: med dagens trafikk i
Search Console gir donasjoner tilnærmet null i året. Å registrere ENK for å få
Vipps ville koste regnskapsplikt og næringsstatus for en inntekt nær null.

### Betalt datakilde for kurser og utbytte

**Vurdert på nytt 14.09.2026. Konklusjon: ikke kjøp — og avslaget handler om
passform, ikke om pris.**

En tidligere vurdering ble aldri skrevet ned noe sted, så denne er gjort fra
grunnen av. Skriv den ned denne gangen.

#### Spør først hva som faktisk er ødelagt

Kursene er ikke problemet. De hentes fra Yahoo, kryssjekkes mot Euronext-CSV-en
og oppdateres hvert 15. minutt, og ingen av de dokumenterte hendelsene i
CLAUDE.md handler om feil kurs. Det som er ødelagt er **utbyttedata**, og
nærmere bestemt to ting:

1. **Ordinært kontra ekstraordinært utbytte.** Hele «Why the yield is not
   auto-corrected»-avsnittet finnes fordi vi ikke kan skille dem. Tre
   erstatningsregler ble simulert og alle tre ga et åpenbart galt tall et sted.
2. **Frekvens.** `frekvens` hentes ikke, den *utledes* ved å telle utbetalinger
   i et 12-måneders vindu — og en forstyrret serie endrer etiketten stille.
   SATS og 2020 Bulkers er dokumenterte tilfeller.

En betalt kurskilde løser ingen av dem. Det er den egentlige testen, og de
fleste leverandørene stryker på den før prisen i det hele tatt er relevant.

#### Det som ble undersøkt

| Kilde | Pris | Hva som stopper den |
|---|---|---|
| **Börsdata** (best nordisk dekning) | Pro+-medlemskap | **Vilkårene forbyr det eksplisitt** — se sitat under |
| **EODHD** | 19,99 $/mnd personlig, **kommersielt fra 399 $/mnd** | Utbytte-API-et skiller **ikke** ordinært fra ekstraordinært, og oppgir ikke frekvens. Utvidede felter (erklærings-, record- og betalingsdato) er dokumentert kun for «major U.S. tickers» og «major European companies» |
| **Euronext direkte** | Ikke offentlig prisliste; egen avtale | Rett kilde for kurs, men selger ikke utbytteklassifisering. Krever markedsdataavtale |
| Finnhub / Twelve Data / FMP | 0–100 $/mnd | Fant ingen dokumentasjon på utbyttetype for Oslo Børs. Fravær av treff er ikke bevis — men det er heller ikke noe å bygge på |

> ⚠️ **Börsdata er den beste passformen og samtidig umulig.** Den dekker
> Norden inkludert Oslo Børs med utbyttekalender, og API-vilkårene sier:
> «It is not permitted to use the Börsdata API for commercial purposes»,
> «It is not permitted to distribute API data both commercially and
> non-commercially», og «It is not allowed to build external systems/home
> pages/widgets that display API data». Alle tre beskriver nøyaktig det
> exday.no er. Ikke et forhandlingsrom — et nei.

#### Videredistribusjon er et spørsmål vi allerede har

Euronext gjør 15-minutters forsinkede data gratis tilgjengelig, men **gratis
for internt bruk**; videredistribusjon krever markedsdataavtale. exday.no
publiserer kurser på et offentlig nettsted, altså videredistribusjon.

Det er verdt å merke seg at dette gjelder **uavhengig av om vi betaler noen**.
Spørsmålet gjelder dagens oppsett, ikke bare et framtidig kjøp — og det er ikke
et argument for å kjøpe, siden et retail-abonnement ikke gir
videredistribusjonsrett det heller. Jeg er ikke jurist, og dette er ikke
avklart. Det bør avklares på egen kjøl, med AdSense-godkjenning som naturlig
anledning, siden annonser gjør siden utvetydig kommersiell.

#### Hva gratisveien faktisk rekker — målt, ikke gjettet

Oslo Børs' egen melding «Key information relating to the cash dividend» er
primærkilden en betalt leverandør uansett ville lest. Skannet over et
tilfeldig utvalg på 35 tickere (frø 42, opptil fire meldinger hver):

| | Andel |
|---|---|
| Har meldingen | **25/35 (71 %)** |
| Beløp uttrekkbart | 24/35 (69 %) |
| **Merker utbyttetypen** | **4/35 (11 %)** |

Taket på klassifisering er altså rundt **11 %** — lavt, men det er 11 % mer enn
noen leverandør tilbyr oss i dag, og det koster ingenting. To av de fire var
KOG og HUNT, og de alene motbeviste varselet på to aksjesider (#45). En tredje
er **WAWI** — selve skoleeksempelet på periodestabling i CLAUDE.md.

#### Beslutning

**Ikke kjøp nå.** Ingen undersøkt leverandør selger det vi mangler, den ene som
passer forbyr bruken, og de 399 $/mnd som kreves for kommersiell EODHD-lisens
er ~4 800 $ i året for en side som ennå ikke har annonseinntekt.

**Gjør i stedet:** les flere meldingstyper fra NewsWeb-lista vi allerede henter
per ticker. «Ex-dividend NOK 5.70/share today» ligger i samme respons som
rapportdatoen. Null nye kilder, null nye vilkår, null kroner.

**Hva som ville snudd dette:**

- En leverandør som dokumenterer utbyttetype *og* frekvens for Oslo Børs — da
  er samtalen om pris, ikke om passform.
- Reell annonseinntekt som gjør 399 $/mnd til en andel av noe, ikke en ren
  utgift.
- En avklaring som sier at videredistribusjon krever lisens uansett — da endres
  regnestykket, fordi vi da betaler for noe vi må ha.

---

*Sist oppdatert: 15. september 2026*
