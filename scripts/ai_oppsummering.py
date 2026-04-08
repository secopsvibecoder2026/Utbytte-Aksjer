"""
Genererer AI-oppsummeringer for norske utbytteaksjer via Claude API.
Leser nåværende tall fra aksjer.json og skriver ai_oppsummering + ai_oppsummering_dato
tilbake til aksjer.json.

Kjøres ukentlig via GitHub Actions (.github/workflows/ai-oppsummering.yml).
Kan også kjøres manuelt:
    ANTHROPIC_API_KEY=... python3 scripts/ai_oppsummering.py

Flagg:
    --force     Overskriv eksisterende oppsummeringer
    --tickers   Kommaseparert liste med spesifikke tickers (f.eks. EQNR,DNB,TEL)
    --max N     Maks antall aksjer å behandle i én kjøring (default: alle)
"""

import json
import os
import time
import datetime
import argparse
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AKSJER_F = os.path.join(ROOT, "data", "aksjer.json")

SYSTEM_PROMPT = """Du er en norsk finansanalytiker som skriver korte, faktabaserte oppsummeringer
av Oslo Børs-aksjer for norske privatinvestorer. Skriv alltid på norsk bokmål.
Svar kun med selve teksten, ingen innledning eller avslutning."""

BRUKER_PROMPT_MAL = """Skriv en AI-oppsummering (maks 80 ord) for aksjen {ticker} ({navn}).

Nåværende tall:
- Pris: {pris} kr
- P/E: {pe}
- Direkteavkastning (yield): {yield_pst}%
- Utbyttefrekvens: {frekvens}
- 5-årssnitt yield: {snitt5}%
- Payout ratio: {payout}%
- Markedsverdi: {mrd} mrd NOK
- Sektor: {sektor}
- Ex-dato (neste): {ex_dato}
- Utbytte per aksje: {dps} kr

Fokuser på:
1. Verdsettelse (er aksjen billig/dyr basert på P/E og yield?)
2. Utbyttets bærekraft (payout ratio + historikk)
3. Kort sektorvurdering

Avslutt med én setning om egnethet for utbytteinvestorer.
Ikke repeter tallene mekanisk — tolk dem."""


def _formater_tall(verdi, desimaler=1, fallback="–"):
    if verdi is None or verdi == 0:
        return fallback
    try:
        if desimaler == 0:
            return f"{verdi:.0f}"
        return f"{verdi:.{desimaler}f}"
    except (TypeError, ValueError):
        return fallback


def _lag_prompt(aksje: dict) -> str:
    return BRUKER_PROMPT_MAL.format(
        ticker=aksje.get("ticker", ""),
        navn=aksje.get("navn", ""),
        pris=_formater_tall(aksje.get("pris"), 2),
        pe=_formater_tall(aksje.get("pe")),
        yield_pst=_formater_tall(aksje.get("direkteavkastning")),
        frekvens=aksje.get("frekvens") or "–",
        snitt5=_formater_tall(aksje.get("snitt_yield_5ar")),
        payout=_formater_tall(aksje.get("payout_ratio"), 0),
        mrd=_formater_tall(aksje.get("markedsverdi_mrd"), 1),
        sektor=aksje.get("sektor") or "–",
        ex_dato=aksje.get("ex_dato") or "–",
        dps=_formater_tall(aksje.get("dps"), 2),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overskriv eksisterende")
    parser.add_argument("--tickers", default="", help="Kommaseparert liste")
    parser.add_argument("--max", type=int, default=0, help="Maks antall å behandle")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("FEIL: ANTHROPIC_API_KEY er ikke satt.", file=sys.stderr)
        sys.exit(1)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except ImportError:
        print("FEIL: pip install anthropic", file=sys.stderr)
        sys.exit(1)

    with open(AKSJER_F, encoding="utf-8") as f:
        data = json.load(f)

    aksjer = data["aksjer"] if isinstance(data, dict) else data
    filter_tickers = set(args.tickers.upper().split(",")) if args.tickers else set()
    i_dag = datetime.date.today().isoformat()

    endret = 0
    for aksje in aksjer:
        ticker = aksje.get("ticker", "")

        if filter_tickers and ticker not in filter_tickers:
            continue

        eksisterende = aksje.get("ai_oppsummering", "")
        if eksisterende and not args.force:
            print(f"[{ticker:8}] hopper over")
            continue

        if args.max and endret >= args.max:
            print(f"Nådd maks {args.max} aksjer — stopper.")
            break

        print(f"[{ticker:8}] genererer oppsummering...")

        try:
            prompt = _lag_prompt(aksje)
            svar = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            tekst = svar.content[0].text.strip()
            aksje["ai_oppsummering"] = tekst
            aksje["ai_oppsummering_dato"] = i_dag
            endret += 1
            print(f"[{ticker:8}] OK ({len(tekst)} tegn)")
        except Exception as e:
            print(f"[{ticker:8}] FEIL: {e}")

        time.sleep(0.3)   # respekter rate limits

    if isinstance(data, dict):
        data["aksjer"] = aksjer
    else:
        data = aksjer

    with open(AKSJER_F, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\nFerdig. {endret} oppsummeringer generert/oppdatert.")


if __name__ == "__main__":
    main()
