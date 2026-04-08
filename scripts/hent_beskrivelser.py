"""
Henter faktabaserte selskapsbeskrivelser fra Yahoo Finance og lagrer i tickers.json.
Oversetter automatisk til norsk via Claude API hvis ANTHROPIC_API_KEY er satt.

Kjøres manuelt (én gang, eller ved behov):
    python3 scripts/hent_beskrivelser.py

Flagg:
    --force     Overskriv eksisterende beskrivelse_fakta
    --tickers   Kommaseparert liste med spesifikke tickers (f.eks. EQNR,DNB,TEL)
"""

import json
import os
import sys
import time
import argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKERS_F = os.path.join(ROOT, "data", "tickers.json")

MAX_TEGN = 600   # maks tegn i beskrivelsen som lagres


def _hent_yf_beskrivelse(ticker_yf: str) -> str:
    """Henter longBusinessSummary fra Yahoo Finance."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker_yf).info
        tekst = (info.get("longBusinessSummary") or "").strip()
        if len(tekst) > MAX_TEGN:
            # Kutt ved siste punktum innenfor MAX_TEGN tegn
            kutt = tekst[:MAX_TEGN].rfind(".")
            tekst = tekst[: kutt + 1] if kutt > 0 else tekst[:MAX_TEGN]
        return tekst
    except Exception as e:
        print(f"  [FEIL] {ticker_yf}: {e}")
        return ""


def _oversett_til_norsk(tekst_en: str, selskapsnavn: str) -> str:
    """Oversetter engelsk tekst til norsk via Claude API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        melding = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Oversett følgende engelske selskapsbeskrivelse for {selskapsnavn} "
                        "til kortfattet norsk bokmål (maks 80 ord). "
                        "Behold faktainnholdet, men fjern unødvendig detalj. "
                        "Svar kun med den norske teksten, ingen innledning:\n\n"
                        f"{tekst_en}"
                    ),
                }
            ],
        )
        return melding.content[0].text.strip()
    except Exception as e:
        print(f"  [OVERSETTELSE FEIL]: {e}")
        return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overskriv eksisterende")
    parser.add_argument("--tickers", default="", help="Kommaseparert liste med tickers")
    args = parser.parse_args()

    har_api = bool(os.environ.get("ANTHROPIC_API_KEY"))
    print(f"Claude API: {'tilgjengelig — oversetter til norsk' if har_api else 'ikke satt — lagrer engelsk'}")
    print()

    with open(TICKERS_F, encoding="utf-8") as f:
        tickers = json.load(f)

    filter_tickers = set(args.tickers.upper().split(",")) if args.tickers else set()

    endret = 0
    for t in tickers:
        ticker = t["ticker"]
        ticker_yf = t.get("ticker_yf", ticker + ".OL")

        if filter_tickers and ticker not in filter_tickers:
            continue

        eksisterende = t.get("beskrivelse_fakta", "")
        if eksisterende and not args.force:
            print(f"[{ticker:8}] hopper over (eksisterer)")
            continue

        print(f"[{ticker:8}] henter fra Yahoo Finance ({ticker_yf})...")
        tekst_en = _hent_yf_beskrivelse(ticker_yf)

        if not tekst_en:
            print(f"[{ticker:8}] ingen beskrivelse funnet")
            continue

        if har_api:
            print(f"[{ticker:8}] oversetter til norsk...")
            tekst = _oversett_til_norsk(tekst_en, t.get("navn", ticker))
            if not tekst:
                tekst = tekst_en   # fallback til engelsk
        else:
            tekst = tekst_en

        t["beskrivelse_fakta"] = tekst
        t["beskrivelse_fakta_kilde"] = "yahoo_finance"
        t["beskrivelse_fakta_sprak"] = "no" if har_api else "en"
        endret += 1
        print(f"[{ticker:8}] lagret ({len(tekst)} tegn)")

        time.sleep(0.5)   # unngå rate limiting

    with open(TICKERS_F, "w", encoding="utf-8") as f:
        json.dump(tickers, f, ensure_ascii=False, indent=2)

    print(f"\nFerdig. {endret} aksjer oppdatert.")


if __name__ == "__main__":
    main()
