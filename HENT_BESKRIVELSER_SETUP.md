# Oppsett: faktabeskrivelser fra Yahoo Finance

## Oversikt

`beskrivelse_fakta` er den faktabaserte selskapsbeskrivelsen som vises under
«Om selskapet» på hver aksjeside og i aksjemodalen i appen.

| Felt | Kilde | Oppdateres |
|------|-------|------------|
| `beskrivelse_fakta` | Yahoo Finance (oversatt til norsk) | Manuelt ved behov |

> ### ⚠️ Beskrivelsene skal være på norsk
>
> Alle 154 beskrivelser ble oversatt til norsk 26. august 2026. Fram til da sto
> 153 av dem på engelsk rett fra Yahoo — «DNB Bank ASA provides financial
> services to individuals…» på en norsk side.
>
> `hent_beskrivelser.py` henter engelsk tekst fra Yahoo på nytt. **Uten
> `ANTHROPIC_API_KEY` lagrer skriptet engelsk rett inn og reverserer
> oversettelsen.** Kjører du det, sjekk `git diff data/tickers.json` før du
> committer.

---

## Kjøring

```bash
# Med API-nøkkel (henter engelsk fra Yahoo + oversetter til norsk):
ANTHROPIC_API_KEY=sk-... python3 scripts/hent_beskrivelser.py

# Bare spesifikke aksjer:
ANTHROPIC_API_KEY=sk-... python3 scripts/hent_beskrivelser.py --tickers EQNR,DNB,TEL

# Overskriv eksisterende:
ANTHROPIC_API_KEY=sk-... python3 scripts/hent_beskrivelser.py --force
```

Etter kjøring: commit `data/tickers.json` og kjør `python3 scripts/regenerer_sider.py`.

Nøkkelen legges inn som `ANTHROPIC_API_KEY` under **Settings → Secrets and
variables → Actions** hvis den skal brukes fra GitHub Actions. Per i dag kjøres
skriptet kun manuelt.

---

## Historikk: AI-oppsummeringene

Prosjektet hadde tidligere et felt `ai_oppsummering` med en Claude-generert
vurdering per aksje, en ukentlig workflow (`ai-oppsummering.yml`) og et skript
(`ai_oppsummering.py`). Alt dette ble fjernet 26. august 2026:

- **Workflowen hadde feilet alle 20 kjøringene** siden 13. april, hver gang med
  `FEIL: ANTHROPIC_API_KEY er ikke satt` — hemmeligheten ble aldri lagt inn.
- Tekstene sto derfor frosset på 3. juli, med tall støpt inn i prosaen. 42 av
  139 hadde feil direkteavkastning, 88 feil P/E og 26 feil payout ratio.
- Innholdet gjentok i praksis «Vurdering som utbytteaksje», som allerede
  bygges fra levende tall.

Feltet er erstattet av `utbyttehistorikk_tekst`, som genereres av
`_lag_utbyttehistorikk_tekst()` i `fetch_stocks.py` ved hver kjøring og derfor
ikke kan bli utdatert. Se CLAUDE.md for detaljer.
