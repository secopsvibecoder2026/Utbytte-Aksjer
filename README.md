# Norske Utbytteaksjer — exday.no

Oversikt over norske utbytteaksjer notert på Oslo Børs. Data hentes automatisk fra Yahoo Finance hverdager kl 08:00.

## Funksjoner

- 44 norske utbytteaksjer med live data
- Yield, payout ratio, vekst 5 år, ex-dato, betalingsdato
- Kompakt/detaljert visning
- Mobilvennlig (tabell på desktop, korter på mobil)
- Mørk/lys modus
- Utbyttekalender
- Filtrering på sektor, frekvens og yield
- Google Analytics + AdSense Auto Ads

## Teknisk oppsett

| Del | Teknologi |
|---|---|
| Frontend | HTML + Tailwind CSS (CDN) + Vanilla JS |
| Hosting | GitHub Pages |
| Data | Yahoo Finance via `yfinance` |
| Pipeline | GitHub Actions (cron hverdager 07:00 UTC) |
| Domene | exday.no (CNAME → secopsvibecoder2026.github.io) |

## Filstruktur

```
├── index.html              # Hovedside
├── ads.txt                 # AdSense autorisasjon
├── CNAME                   # Domene: exday.no
├── assets/
│   ├── app.js              # All applikasjonslogikk
│   └── style.css           # Stilark
├── data/
│   └── aksjer.json         # Aksjedata (auto-generert)
└── scripts/
    ├── fetch_stocks.py     # Datahenting fra Yahoo Finance
    └── requirements.txt
```

## Kjøre dataskript lokalt

```bash
pip install -r scripts/requirements.txt
python scripts/fetch_stocks.py
```

## GitHub Actions

Workflowen `.github/workflows/update-og-deploy.yml` kjører automatisk:
1. Henter fersk data fra Yahoo Finance
2. Committer `data/aksjer.json` hvis endret
3. Deployer til GitHub Pages

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
