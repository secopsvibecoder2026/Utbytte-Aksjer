#!/usr/bin/env python3
"""
fetch_priser.py — Lettvekts kursoppdatering
Henter kun nåværende kurs + forrige stenging for alle tickers.
Kjøres hvert 15. minutt i børstiden. Skriver til data/priser.json.
"""
import json
import sys
import datetime
from pathlib import Path

import yfinance as yf

ROOT       = Path(__file__).parent.parent
TICKERS_F  = ROOT / "data" / "tickers.json"
PRISER_F   = ROOT / "data" / "priser.json"


def les_tickers() -> list[dict]:
    with open(TICKERS_F, encoding="utf-8") as f:
        return json.load(f)


def hent_priser(tickers: list[dict]) -> dict:
    yf_symboler = [t["ticker_yf"] for t in tickers]
    ticker_map  = {t["ticker_yf"]: t["ticker"] for t in tickers}

    print(f"Henter kurs for {len(yf_symboler)} aksjer …")
    try:
        # Én batch-kall for alle tickers — 2 dager for å få forrige stenging
        data = yf.download(
            yf_symboler,
            period="5d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as e:
        print(f"FEIL ved nedlasting: {e}", file=sys.stderr)
        return {}

    if data.empty:
        print("Ingen data returnert.", file=sys.stderr)
        return {}

    close = data["Close"]
    resultat = {}

    for yf_sym in yf_symboler:
        ticker = ticker_map[yf_sym]
        try:
            col = close[yf_sym] if yf_sym in close.columns else close
            # Fjern NaN-rader
            serie = col.dropna()
            if len(serie) < 1:
                continue

            pris         = round(float(serie.iloc[-1]), 4)
            forrige_kurs = round(float(serie.iloc[-2]), 4) if len(serie) >= 2 else pris

            endring_krs  = round(pris - forrige_kurs, 4)
            endring_pct  = round((endring_krs / forrige_kurs) * 100, 4) if forrige_kurs else 0.0

            resultat[ticker] = {
                "pris":         pris,
                "forrige_kurs": forrige_kurs,
                "endring_krs":  endring_krs,
                "endring_pct":  endring_pct,
            }
        except Exception as e:
            print(f"  {ticker}: {e}", file=sys.stderr)

    return resultat


def main():
    tickers  = les_tickers()
    priser   = hent_priser(tickers)
    ts       = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    ok   = sum(1 for v in priser.values() if v["pris"] > 0)
    feil = len(tickers) - ok
    print(f"  {ok} OK, {feil} mangler")

    output = {"oppdatert": ts, "aksjer": priser}
    PRISER_F.parent.mkdir(exist_ok=True)
    with open(PRISER_F, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Skrevet til {PRISER_F}  ({len(priser)} tickers, {ts})")


if __name__ == "__main__":
    main()
