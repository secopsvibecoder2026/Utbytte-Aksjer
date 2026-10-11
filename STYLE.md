# STYLE.md: visuell gjennomgang av exday.no

Gjennomgang av font, farger og oppbygging, med mål om et mer profesjonelt
finansuttrykk. Gjort 11.10.2026 med skjermbilder fra Playwright på 1280 px og
390 px, lyst og mørkt tema, av forsiden, `/app/` (tabell og aksjemodal),
`/aksjer/EQNR/`, `/aksjer/sektor/finans/`, `/utbyttekalender/` og en artikkel.

Dette dokumentet handler om det visuelle. Språket på sidene styres av
`SKRIVESTIL.md`, fargepaletten av «Project Color Palette» i `CLAUDE.md`.
Arctic-fargene er fortsatt utelukket overalt.

## Kort dom

Grunnmuren er god: mørk modus er gjennomført, avstandene er ryddige, og grønt
er et godt merkevarevalg. Det som trekker mot «blogg» eller «SaaS» i stedet for
«finans», er fire ting:

1. Tallene får ikke hovedrollen. Aksjesiden starter med tekst, forsiden har
   ingen tall over bretten.
2. Grønt betyr alt på en gang: merkevare, knapp, lenke, yield og kursoppgang.
3. Tallformatet varierer på samme side.
4. For mange aksentfarger uten fast betydning.

## Typografi

### Ingen egen font

Hele nettstedet bruker Tailwinds standardstabel (`ui-sans-serif, system-ui,
sans-serif`). Ingen side laster en webfont. Derfor ser siden ulik ut på Mac
(San Francisco), Windows (Segoe UI), Android (Roboto) og Linux (DejaVu Sans).

**Forslag:** Inter, med vekt 400, 500, 600 og 700, latin-utvalg, lagt på vår
egen server under `assets/fonts/` som woff2 (lisens: SIL OFL). **Ikke** via
Google Fonts: det sender besøkendes IP til Google før samtykke, og
`consent.js` styrer bare Analytics og AdSense.

### Tall med fast bredde

`tabular-nums` finnes 12 steder i `assets/ui.js`, 6 i `app/index.html`, 1 i
`scripts/fetch_stocks.py` og 0 i `index.html`. Uten det hopper kolonnene når
tall endres, og tall under hverandre står ikke på linje.

**Forslag:** `font-variant-numeric: tabular-nums` på alle tabeller, nøkkelkort,
kurs og endring. Med Inter i tillegg `font-feature-settings: "tnum", "cv11"`
for tydelig skille mellom 1 og l. Dette er det billigste enkelttiltaket for et
finansuttrykk.

### Tallformatet varierer

Samme side og samme type tall skrives ulikt:

| Hvor | Vises som | Kilde |
|---|---|---|
| EQNR, nøkkelkort | `3,48%` | `_aksje_side_html()` i `scripts/fetch_stocks.py` |
| EQNR, «Faktisk betalt utbytte» | `3,48 %` | `lag_betalt_boks()` |
| EQNR, kursgraf | `▲ +79.1%` (punktum) | grafskriptet i malen, `fetch_stocks.py` rundt linje 5065 |
| EQNR, «Utbyttedatoer» | `Yielden på 3,5%` | `fetch_stocks.py` linje 3151–3161 og 4006 |
| Kalenderen | `7.7%` (punktum) | `utbyttekalender/index.html` linje 579 |
| Kalenderen | `1.0986 NOK per aksje` | samme fil |

**Regel:** desimalkomma og hardt mellomrom før prosent, `3,48 %`. Kroner med
to desimaler (`1,10 NOK`), og bare flere desimaler når beløpet er under én krone
(`0,375`). Én formateringsfunksjon i Python (`_nf()` utvidet) og én i JS
(`fmt()`), og ingen `toFixed()` direkte i HTML.

### Tickere

Tickere står i grønn monospace (`ENH`, `ABG`). Det leses som kode. **Forslag:**
halvfet vanlig skrift i mørkegrått (gray-900 / gray-100), som hos meglerne.

## Farger

### Grønt har for mange jobber

Grønt brukes til merkevare, knapper, lenker, aktive faner, yield og kursoppgang.
I finans leses grønt som «opp». Når EQNR viser yield `3,48%` og 5-årssnitt
`5,47%` i grønt, ser det ut som kursendringer.

**Roller:**

| Rolle | Farge |
|---|---|
| Tall (kurs, yield, utbytte) | nøytral, gray-900 / gray-100 |
| Endring opp / ned | grønn / rød, og bare her |
| Advarsel | amber |
| Knapp (CTA) | green-700 `#15803d`, hover green-800 |
| Lenker | green-700 / green-400 i mørk modus |
| Overskrifter | gray-900 eller slate-900 |

Den lyse grønne knappen (green-500/600) virker mer forbruker enn finans. En
mørkere grønn gir et roligere og mer seriøst inntrykk. Paletten i `CLAUDE.md`
må oppdateres i samme endring.

### For mange aksentfarger

- Forsiden: sektorikonene har hver sin farge (oransje, blå, turkis, gul, lilla).
  Verktøyikonene likeså.
- Aksjesiden: «Utbyttehistorikken kort fortalt» i blå boks med blå tittel,
  «Utbyttedatoer» i grønn boks, merkelapper i grønt og blått, risikopunkter med
  rød kant. Fargene har ingen fast betydning.

**Forslag:** én aksentfarge pluss gråskala. Ikoner ensfarget (gray-600 på
gray-100, eller green-700 på green-50). Fargede bokser bare når de betyr noe:
amber for advarsel, grå for nøytral forklaring (slik `lag_ekstraordinaer_note()`
allerede gjør).

## Oppbygging

### Aksjesiden (`_aksje_side_html()`)

- **Tre avsnitt tekst før første tall.** «Om selskapet» står øverst, nøkkeltallene
  kommer etter. Finanssider starter med et kurshode: kurs, dagens endring, yield
  og neste ex-dato på én linje, så grafen, så detaljene. Selskapsteksten kan
  flyttes ned; Google leser den like godt der.
- **Nøkkelkortene:** ni kort i et rutenett, ett tomt («Kvartalsrapport —») og
  P/E alene på tredje rad. **Forslag:** kurshode med fire tall, deretter en
  kompakt tabell med to kolonner for resten, og tomme felt skjules.
- **«Faktisk betalt utbytte»:** tabellen fyller halve boksen på desktop.
- **Merkelappene** «Lav risiko» står både i raden over boksen og i boksen.

### Forsiden (`index.html`)

Ingen data over bretten, bare tekst. Resten er navigasjonskort og artikler.
**Forslag:** en datamodul øverst med «Neste ex-datoer» (5 rader) og «Høyest
betalt yield siste 12 mnd», generert som ekte HTML av `fetch_stocks.py` /
`regenerer_sider.py` (mellom markører, som `oppdater_antall_i_sider()`), så
søkemotorer ser tallene. Bruk betalt yield, ikke estimatet (se «What was
actually paid» i `CLAUDE.md`).

### Appen (`/app/`)

- **To lag over dataene ved første besøk:** velkomstvinduet («Hva skal vi kalle
  deg?», `assets/ui.js` rundt linje 3558) og cookie-banneret. Profesjonelle
  apper viser dataene først. **Forslag:** dropp velkomstvinduet ved første
  besøk; spør om navn i Innstillinger eller i Portefølje-fanen.
- **Tabellen:**
  - Overskriftene brytes over to og tre linjer («TICKER ⇅», «SNITT YIELD 5Å»),
    med sorteringspilen på egen linje.
  - Radene er rundt 160 px høye på desktop.
  - Nesten hvert tall ligger i en farget pille (yield, score, snitt).

  **Forslag:** én linje per overskrift (pilen ved siden av), radhøyde rundt
  40 px, høyrejusterte tall med fast bredde, tynne skillelinjer, piller bare i
  én kolonne (score).
- **Stjernen** for favoritter er tegnet ☆, ikke SVG som resten av ikonene (se
  «Icons» i `CLAUDE.md`).

### Kalenderen (`utbyttekalender/`)

Under hovedmenyen ligger en ekstra linje («← exday.no / Utbyttekalender») med
sin egen tema-knapp, så siden har to. Fjern den ekstra linjen og bruk
brødsmulesti som på aksjesidene.

## Grafer

- **Aksene har skjeve verdier:** kursgrafen 232 / 326 / 419, søylene 11,88 /
  23,76 / 35,64. Runde verdier (250 / 300 / 350 / 400) ser profesjonelle ut.
- **Inneværende år** i søylediagrammet ser ut som et helt år. Vis det lysere
  eller skravert, merket «hittil i år», slik tabellen under gjør.
- Linjen kan være tynnere og fyllet svakere; grafen er i dag det sterkeste
  fargeinntrykket på siden.

## Rekkefølge

| # | Tiltak | Virker på | Omfang |
|---|---|---|---|
| 1 | Inter, tall med fast bredde, ett tallformat | Hele nettstedet | ca. en halv dag |
| 2 | Fargeroller: nøytrale tall, grønt og rødt bare for retning, ensfargede ikoner, mørkere knapp | Hele nettstedet | ca. en halv dag |
| 3 | Kurshode og kompakt nøkkeltabell på aksjesiden | 154 aksjesider + appens modal | ca. en dag |
| 4 | Appen: uten velkomstvindu, strammere tabell | Appen | ca. en halv dag |
| 5 | Datamodul på forsiden | Forsiden | ca. en halv dag |
| 6 | Grafer: runde akser, «hittil i år» | Aksjesider og app | et par timer |

Ingen av tiltakene endrer tekstinnholdet Google vurderer, så de påvirker ikke
AdSense-søknaden. Etter hvert tiltak: `npm run build:css`, så
`scripts/sjekk_klasser.py --streng` og `scripts/sjekk_tema.py --streng`, og se
på resultatet i nettleser på 390 px og 1280 px i begge temaer før commit.

## Funnet underveis (innhold, ikke stil)

- **Forsiden sier feil om når du må kjøpe.** `index.html` sier fire steder
  (linje 101, 125, 362–363, 621 og 657–659, også i FAQ-ens JSON-LD) at du må
  kjøpe «senest to børsdager før ex-dato». Riktig er senest dagen før ex-dato:
  med T+2 er registreringsdatoen dagen etter ex-dato. Aksjesidene
  (`fetch_stocks.py` linje 4460) og `/uke/` sier det riktig.
- **EQNR lover dobling av utbyttet.** «Med +40,1 % per år dobles utbyttet på
  ca. 2 år» (`fetch_stocks.py` linje 4244, `assets/ui.js` linje 1036). Tallet er
  regnet fra 2021 (4,97 kr), et bunnår, til 2025 (19,16 kr). Utbyttet har falt
  fra 35,64 kr i 2023, og samme side nevner to kutt. Doblingsteksten bør ikke
  vises når siste hele år ligger under toppen i perioden.
- **Interne dokumenter blir publisert.** Så lenge Pages også publiserer fra
  branchen, gjør Jekyll `.md`-filene i roten til HTML-sider. Denne fila blir da
  `/STYLE.html`, som `/CLAUDE.html` og `/ROADMAP.html`. Rettes når Pages-kilden
  byttes til «GitHub Actions» (se vedlikeholdsrapporten).
