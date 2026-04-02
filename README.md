# Norske Utbytteaksjer — exday.no

Komplett verktøy for norske utbytteaksjer notert på Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00 og vises på [exday.no](https://exday.no).

## Funksjoner

### Oversikt og søk
- 67+ norske utbytteaksjer med live data (yield, payout ratio, 5-årssnitt, ex-dato, betalingsdato)
- Utbyttescore 0–10 basert på yield, payout, vekst og historikk
- Sortering på alle kolonner (huskes mellom besøk)
- Filtrering på sektor, frekvens og yield-range
- Søk med debounce (huskes mellom besøk)
- Kompakt/detaljert visning — tabell på desktop, korter på mobil
- Mørk/lys modus
- Favoritter med prioritert visning

### Aksjemodal
- Historisk utbyttegraf (5 år) per aksje
- Notatfelt og målpris-varsler
- Del-link (`?aksje=TICKER`) kopierer til clipboard

### Kalender
- Kommende ex-datoer og betalingsdatoer
- Filtrerbar per måned
- ICS-eksport (kalenderabonnement)

### Portefølje
- Flere navngitte porteføljer med enkel bytting
- Legg til aksjer med kjøpskurs og dato
- **Inline kostbasis og transaksjoner per rad** — chevron utvider en sub-rad med:
  - Vektet snittpris (VWAP), kostpris, urealisert gevinst/tap
  - Mottatt utbytte og total avkastning
  - Transaksjonsskjema (kjøp, salg, utbytte mottatt) og logg med sletting
- Beholdning og Statistikk som egne faner
- Daglig historikk-snapshot med SVG-kurve (siste 30 dager)
- OSEBX-overlay i grafen + «Slår du indeksen?»-indikator
- TWR/IRR — tidskorrigert avkastning (Newton-Raphson)
- Skatteberegning med skjermingsfradrag (aksjonærmodellen 37,84%)
- Sparemål-fremgang og porteføljeprofil
- Del portefølje via `?del=`-URL (base64, read-only modal for mottaker)
- QR-kode for overføring mellom enheter

### Watchlister
- Egne navngitte watchlister, adskilt fra portefølje og favoritter

### Innstillinger (`/innstillinger/`)
- Profil (navn, månedlig utbyttemål, sparemål)
- Porteføljeadministrasjon (opprett, gi nytt navn, slett)
- Push-varsler for ex-datoer
- Fullstendig JSON-backup (eksport og import av all brukerdata)

### Engasjement og tilgjengelighet
- Besøksstreak med 🔥-teller i header
- Milepæl-toasts ved porteføljemilepæler
- «Hva skjer i dag?» — ex-dato i dag/morgen, utbetaling denne uken
- Onboarding-modal for nye brukere; inline 3-stegs guide i tom portefølje
- Personlig hilsen og profil på dashbordet
- `aria-label` på alle ikonknapper, `role="dialog"` på modaler, `aria-sort` på kolonner

### PWA
- Installerbar som app (Service Worker + manifest)
- Push-varsler for ex-datoer
- Offline-støtte med cache-fallback

## Teknisk oppsett

| Del | Teknologi |
|---|---|
| Frontend | HTML + Tailwind CSS v4 (statisk, bygget) + Vanilla JS |
| Hosting | GitHub Pages |
| Data | Yahoo Finance via `yfinance` |
| Pipeline | GitHub Actions (cron hverdager 07:00 UTC) |
| Domene | exday.no (CNAME → secopsvibecoder2026.github.io) |
| Tester | Node.js `node:test` — 37 enhetstester |

## Filstruktur

```
├── index.html                  # Hovedside
├── innstillinger/
│   └── index.html              # Innstillinger-side (/innstillinger/)
├── aksjer/
│   └── TICKER/index.html       # Individuelle SEO-sider (67 stk, auto-generert)
├── personvern/
│   └── index.html              # GDPR / personvernside
├── assets/
│   ├── app.js                  # Bootstrap og datalasting
│   ├── storage.js              # localStorage-funksjoner (23 funksjoner)
│   ├── ui.js                   # All UI-logikk
│   ├── portefolje.js           # Porteføljelogikk
│   ├── tailwind.css            # Bygget CSS (~44 KB, minifisert)
│   ├── tw-input.css            # Tailwind v4 input med brand-farger
│   ├── style.css               # Ekstra stilark
│   └── icon.svg                # App-ikon
├── data/
│   └── aksjer.json             # Aksjedata (auto-generert av pipeline)
├── scripts/
│   ├── fetch_stocks.py         # Datahenting fra Yahoo Finance
│   └── requirements.txt
├── tests/
│   └── *.test.js               # 37 enhetstester
├── sw.js                       # Service Worker
├── manifest.json               # PWA-manifest
├── sitemap.xml                 # Sitemap (69 URL-er)
├── ads.txt                     # AdSense autorisasjon
└── CNAME                       # Domene: exday.no
```

## Utvikling

### Forutsetninger

```bash
npm install          # Installer devDependencies (@tailwindcss/cli)
```

### CSS

```bash
npm run build:css    # Bygg assets/tailwind.css én gang
npm run watch:css    # Watch-modus under utvikling
```

### Tester

```bash
npm test             # Kjør 37 enhetstester
```

### Data lokalt

```bash
pip install -r scripts/requirements.txt
python scripts/fetch_stocks.py
```

## GitHub Actions

Workflowen `.github/workflows/update-og-deploy.yml` kjører automatisk hverdager:
1. Henter fersk data fra Yahoo Finance
2. Committer `data/aksjer.json` og aksje-SEO-sider hvis endret
3. Bumper Service Worker cache-navn til `exday-v{git-sha}` for automatisk cache-invalidering
4. Deployer til GitHub Pages

## Service Worker og caching

- **Navigate (HTML):** nettverks-first med `cache:'no-cache'` — brukere ser alltid nyeste versjon
- **JS/CSS:** stale-while-revalidate — rask lasting, oppdateres i bakgrunnen
- **aksjer.json:** nettverks-first med cache-fallback
- **Install:** resilient med `Promise.allSettled` — én feilende URL avbryter ikke installasjonen
- **Auto-bump:** GitHub Actions setter `CACHE = 'exday-v{sha}'` på hvert deploy, eldre cacher ryddes automatisk

## JSON-backup

Backup v4 dekker all brukerdata:

| localStorage-nøkkel | Innhold |
|---|---|
| `pf_portefoljer` | Alle porteføljer med beholdning og transaksjoner |
| `pf_aktiv` | Aktiv portefølje |
| `pf_watchlister` | Watchlister |
| `pf_historikk` | Daglig verdihistorikk |
| `fav_aksjer` | Favoritter |
| `aksje_data` | Notater og målpriser per aksje |
| `notif_aksjer` | Varselspreferanser |
| `profil_navn` / `profil_mal_mnd` / `profil_sparemaal` | Profil og mål |
| `tema` | Lys/mørk modus |
| `sortering` | Sorteringsvalg |
| `streak_teller` / `streak_sist_besok` | Streak |
| `milepeler_oppnaad` | Oppnådde milepæler |

## DNS-oppsett (exday.no)

| Type | Navn | Verdi |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| CNAME | www | secopsvibecoder2026.github.io |

## Ansvarsfraskrivelse

Ikke finansiell rådgivning. Gjør alltid din egen analyse før investering.
