# Oppsett: AI-oppsummering og faktabeskrivelser

## Oversikt

To nye felt legges til hver aksje:

| Felt | Kilde | Oppdateres |
|------|-------|------------|
| `beskrivelse_fakta` | Yahoo Finance (oversatt med Claude) | Manuelt ved behov |
| `ai_oppsummering` | Claude Haiku (analyse av nåværende tall) | Ukentlig automatisk |

---

## 1. Legg til API-nøkkel i GitHub

1. Gå til **Settings → Secrets and variables → Actions** i GitHub-repositoriet
2. Klikk **New repository secret**
3. Navn: `ANTHROPIC_API_KEY`
4. Verdi: din nøkkel fra [console.anthropic.com](https://console.anthropic.com)
5. Klikk **Add secret**

---

## 2. Hent faktabeskrivelser (én gang)

Kjøres manuelt for å fylle `beskrivelse_fakta` i `tickers.json`:

```bash
# Med API-nøkkel (henter engelsk fra Yahoo + oversetter til norsk):
ANTHROPIC_API_KEY=sk-... python3 scripts/hent_beskrivelser.py

# Uten API-nøkkel (lagrer engelsk fra Yahoo Finance):
python3 scripts/hent_beskrivelser.py

# Bare spesifikke aksjer:
ANTHROPIC_API_KEY=sk-... python3 scripts/hent_beskrivelser.py --tickers EQNR,DNB,TEL

# Overskriv eksisterende:
ANTHROPIC_API_KEY=sk-... python3 scripts/hent_beskrivelser.py --force
```

Etter kjøring: commit `data/tickers.json` og kjør `python3 scripts/regenerer_sider.py`.

---

## 3. Generer AI-oppsummeringer

### Manuell kjøring lokalt

```bash
ANTHROPIC_API_KEY=sk-... python3 scripts/ai_oppsummering.py

# Bare spesifikke aksjer:
ANTHROPIC_API_KEY=sk-... python3 scripts/ai_oppsummering.py --tickers EQNR,DNB

# Overskriv alle:
ANTHROPIC_API_KEY=sk-... python3 scripts/ai_oppsummering.py --force
```

### Automatisk via GitHub Actions

GitHub Action (`.github/workflows/ai-oppsummering.yml`) kjøres automatisk **hver mandag kl. 07:00 CET**.

Manuell trigger via GitHub → Actions → "AI-oppsummering (ukentlig)" → "Run workflow".

---

## 4. Kostnad

| Operasjon | Modell | Estimert kostnad |
|-----------|--------|-----------------|
| Faktabeskrivelse (oversettelse) | claude-haiku-4-5 | ~$0.001 per aksje |
| AI-oppsummering | claude-haiku-4-5 | ~$0.001 per aksje |
| Ukentlig full kjøring (172 aksjer) | claude-haiku-4-5 | ~$0.17 |
| Månedlig total | — | ~$0.70 |

---

## 5. Feilsøking

- **`ANTHROPIC_API_KEY er ikke satt`**: Sjekk at GitHub Secret er riktig konfigurert
- **Rate limit-feil**: Scriptet har innebygd 300ms delay mellom kall; prøv igjen
- **Tom beskrivelse**: Noen aksjer mangler data i Yahoo Finance — disse hoppes over
