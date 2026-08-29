# Norske Utbytteaksjer — exday.no

Progressiv webapp (PWA) for norske utbytteaksjer notert på Oslo Børs. Data hentes automatisk fra Yahoo Finance på børsdager og vises på [exday.no](https://exday.no).

Ingen server-side runtime — all logikk kjører i nettleseren eller i planlagte GitHub Actions. Hostet på GitHub Pages.

## Funksjoner

### Oversikt og søk
- 162 norske utbytteaksjer med live data (yield, payout ratio, 5-årssnitt, ex-dato, betalingsdato)
- Utbyttescore 0–10 basert på yield, payout, vekst og historikk
- Sortering, sektorfilter, frekvensfilter og yield-range — valg huskes mellom besøk
- Paginering (25/50/75/100/alle)
- Sammenlign 2–3 aksjer side ved side, med delbar lenke (`?sammenlign=EQNR,DNB,ORK`)
- Topplister: høyest yield, best vekst, mest konsistente, lavest payout
- Mørk/lys modus, favoritter med prioritert visning

### Aksjemodal
- Historisk utbyttegraf og kursgraf (5 år) per aksje
- Kurshistorikk lastes on-demand fra `data/kurs/{TICKER}.json`
- Notatfelt og målpris-varsler
- Kontekstuelle artikkellenker basert på aksjens sektor
- Del-lenke (`?aksje=TICKER`)

### Kalender
- Kommende ex-datoer og betalingsdatoer, filtrerbar per måned
- ICS-eksport (kalenderabonnement)

### Portefølje
- Flere navngitte porteføljer med enkel bytting
- FIFO-kostbasis, vektet snittpris (VWAP), urealisert gevinst/tap
- Transaksjonslogg (kjøp, salg, utbytte) med validering mot beholdning
- TWR og IRR (Newton-Raphson) — med forklarende melding når perioden er for kort
- Skatteberegning med skjermingsfradrag (aksjonærmodellen, 37,84 %)
- Daglig historikk-snapshot med SVG-kurve og OSEBX-overlay
- Sparemål-fremgang og porteføljeprofil
- Del portefølje via `?del=`-URL (read-only for mottaker) + QR-kode for enhetsoverføring

### Verktøy
- **Kalkulator** — undermeny med utbyttekalkulator (yield over tid, DRIP), huslån vs. investering, og FIRE-kalkulator
- **Annonsert utbytte** — beregn utbytte for et beløp basert på annonserte satser
- **Rebalansering** — sett ønsket sektorvekting, få kjøps-/salgsanbefalinger i kroner
- **Lær** — artikkellisten fra `/artikler/`

### Watchlister og innstillinger
- Egne navngitte watchlister, adskilt fra portefølje og favoritter
- Innstillinger (`/innstillinger/`): profil, sparemål, porteføljeadministrasjon, push-varsler for ex-datoer, fullstendig JSON-backup (eksport/import)

### PWA
- Installerbar (Service Worker + manifest), offline-støtte, push-varsler

## Teknisk oppsett

| Del | Teknologi |
|---|---|
| Frontend | HTML + Tailwind CSS v4 (bygget) + Vanilla JS, ingen rammeverk |
| Hosting | GitHub Pages |
| Data | Yahoo Finance via `yfinance`, DNB Markets, Euronext, Newsweb |
| Pipeline | GitHub Actions — data 4× daglig, priser hvert 15. min |
| Domene | exday.no (CNAME → secopsvibecoder2026.github.io) |
| Tester | 63 JS-tester (`node:test`) + 52 Python-tester (`unittest`) |

## Filstruktur

```
├── index.html                  # Landingsside
├── app/index.html              # Selve appen (/app/)
├── aksjer/
│   ├── TICKER/index.html       # SEO-sider per aksje (162 stk, auto-generert)
│   └── sektor/{slug}/          # Sektorsider (16 stk, auto-generert)
├── artikler/{slug}/            # Artikler og guider (8 stk, håndskrevet)
├── verktoy/                    # SEO-sider for kalkulatorene
├── assets/
│   ├── app.js                  # Bootstrap, datalasting, escHtml()
│   ├── storage.js              # localStorage-abstraksjon
│   ├── ui.js                   # All UI-rendering + ARTIKLER-listen
│   ├── portefolje.js           # FIFO, IRR, TWR, skatt, rebalansering
│   ├── consent.js              # Samtykke + GA Consent Mode v2
│   ├── qrcode.min.js           # QR-bibliotek (vendored, ingen CDN)
│   ├── tailwind.css            # Bygget CSS
│   ├── tw-input.css            # Tailwind-config med brand-farger
│   └── style.css               # Egen CSS oppå Tailwind
├── data/
│   ├── tickers.json            # Manuelt vedlikeholdt — kilden for hvilke aksjer som finnes
│   ├── aksjer.json             # Auto-generert datasett (uten kurshistorikk)
│   ├── kurs/{TICKER}.json      # Kurshistorikk, lastes on-demand
│   ├── priser.json             # Sanntidskurser, oppdateres hvert 15. min
│   ├── hendelser.json          # Hendelseskalender
│   ├── hentelogg.json          # Per-ticker diagnostikk fra siste kjøring
│   └── ticker_varsler.json     # Aktive varsler om utdaterte tickere
├── scripts/
│   ├── fetch_stocks.py         # Hovedpipeline: Yahoo → aksjer.json + SEO-sider
│   ├── fetch_priser.py         # Lettvekts prisoppdatering → priser.json
│   ├── regenerer_sider.py      # Regenererer HTML uten full henting
│   ├── utvid_beskrivelser.py   # Bygger aksjebeskrivelsene fra levende tall
│   ├── valider_data.py         # Datakvalitetssjekk (blokkerer ved kritiske feil)
│   ├── sjekk_utdaterte.py      # Fanger avnoterte/omdøpte/dupliserte tickere
│   ├── oppdater_hendelser.py   # Hendelseskalender fra Newsweb
│   ├── hent_beskrivelser.py    # Engangsjobb: faktabeskrivelser fra Yahoo
│   ├── test_sjekk_utdaterte.py # 45 tester (stdlib unittest, uten nettverk)
│   └── test_fetch_stocks.py     # 7 tester (RangeIndex-regresjon, frekvensgrenser)
├── tests/*.test.js             # 63 JS-tester (portefølje, storage, ui)
├── promo/                      # Markedsføringsmateriell + generatorer
├── sw.js                       # Service Worker
├── manifest.json               # PWA-manifest
├── sitemap.xml                 # Auto-generert (209 URL-er)
└── CNAME                       # exday.no
```

## Utvikling

```bash
npm install              # devDependencies (Tailwind CLI, Playwright)
npm run build:css        # Bygg assets/tailwind.css
npm run watch:css        # Watch-modus under utvikling
npm test                 # 63 JS-tester

pip install -r scripts/requirements.txt
python scripts/fetch_stocks.py         # Full henting (~45 min)
python scripts/regenerer_sider.py      # Kun HTML-regenerering (raskt)
python scripts/valider_data.py         # Datakvalitetssjekk
python scripts/sjekk_utdaterte.py      # Sjekk for utdaterte tickere
python scripts/test_sjekk_utdaterte.py # 45 tester (utdaterte tickere)
python scripts/test_fetch_stocks.py     # 7 tester (fetch_stocks, krever pandas)

python -m http.server 8000             # Lokal server (SW krever localhost/HTTPS)
```

## GitHub Actions

| Workflow | Trigger | Gjør |
|---|---|---|
| `update-og-deploy.yml` | Hverdager 07/10/13/16 UTC | Henter data, validerer, sjekker utdaterte tickere, committer, deployer |
| `oppdater-priser.yml` | Hvert 15. min hverdager 08–17 UTC | Oppdaterer `priser.json`, utløser lettvekts-deploy |
| `deploy-only.yml` | `workflow_dispatch` | Deployer main til Pages uten datahenting |
| `tester.yml` | Push/PR mot `assets/`, `scripts/`, `tests/` | Kjører alle 115 tester |

Datajobben og Pages-deployen bruker atskilte concurrency-grupper, så en priscommit aldri kan kansellere en pågående datahenting.

**Merk:** Mange commits i historikken er automatiske bot-commits (`auto: oppdater kurspriser …`). Det er forventet.

## Service Worker og caching

- **Navigate (HTML):** nettverks-first med `cache:'no-cache'`
- **JSON-data** (`aksjer.json`, `priser.json`, `data/kurs/`): nettverks-first med bakgrunnscache
- **JS/CSS:** cache-first / stale-while-revalidate
- **Auto-bump:** deploy-workflowen setter `CACHE = 'exday-v{sha}'` — ikke endre denne strengen manuelt

## Dokumentasjon

| Fil | Innhold |
|---|---|
| `CLAUDE.md` | Utviklerguide: konvensjoner, arkitektur, kjente datakvalitetsproblemer |
| `ROADMAP.md` / `ROADMAP_NYE_IDEER.md` | Planlagte features og levende backlog |
| `ROADMAP_COMPLETED.md` | Logg over ferdigstilte features |
| `SECURITY_ROADMAP.md` | Sikkerhetsgjennomgang og status |
| `HENT_BESKRIVELSER_SETUP.md` | Oppsett av faktabeskrivelser fra Yahoo |
| `KODE_REVIEW.md` / `PROSJEKT_REVIEW.md` | Historiske gjennomganger (øyeblikksbilder) |

## Ansvarsfraskrivelse

exday.no er ikke et verdipapirforetak og tilbyr ikke finansiell rådgivning. Data kan inneholde feil eller forsinkelser — verifiser alltid mot Oslo Børs eller selskapets egne rapporter. Gjør alltid din egen analyse før du tar investeringsbeslutninger.
