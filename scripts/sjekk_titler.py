#!/usr/bin/env python3
"""Bygger <title> for alle aksjesidene og lister dem som bør ses på.

    python scripts/sjekk_titler.py            # rapport, avslutter alltid 0
    python scripts/sjekk_titler.py --alle     # skriv ut alle titlene
    python scripts/sjekk_titler.py --streng   # avslutt 1 hvis en tittel er over taket

Tittelen leder med beløp per aksje og ex-dato (lag_aksje_tittel() i
fetch_stocks.py). Skriptet viser:

- titler over TITTEL_MAKS (60) tegn, der Google kan klippe;
- aksjer uten beløp i tittelen, med grunnen. De har dagens tittel med yield
  eller ex-dato. Det er riktig for en aksje med en hendelse (oppkjøp,
  avvikling) eller en årsrate som er et delår, men en aksje med kjent ex-dato
  og uten kunngjort beløp kan være et tegn på at beløpet ikke ble lest.

Leser data/aksjer.json og trenger ikke nett.
"""

import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_stocks as fs  # noqa: E402


def grunn_uten_belop(a, today):
    """Hvorfor aksjen ikke har beløp i tittelen, som kort tekst."""
    if fs.hendelse_uten_mal(a):
        return f"hendelse ({(a.get('hendelse') or {}).get('type', '?')})"
    ex = a.get("ex_dato") or ""
    if ex and ex >= today:
        return f"ex-dato {ex} uten kunngjort beløp"
    if fs.yield_er_delaar(a) and not fs.delaar_motbevist(a):
        return "årsraten er et delår"
    upa = a.get("utbytte_per_aksje") or 0
    if upa <= 0:
        return "ingen årsrate"
    return "beløp over kursen"


def vurder(aksjer, today):
    """(titler, lange, uten_belop): lister av (ticker, tittel[, grunn])."""
    titler, lange, uten = [], [], []
    for a in sorted(aksjer, key=lambda x: x["ticker"]):
        t = fs.lag_aksje_tittel(a, today)
        titler.append((a["ticker"], t))
        if len(t) > fs.TITTEL_MAKS:
            lange.append((a["ticker"], t))
        if not fs.utbytte_i_tittel(a, today):
            uten.append((a["ticker"], t, grunn_uten_belop(a, today)))
    return titler, lange, uten


def main():
    rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(rot, "data", "aksjer.json"), encoding="utf-8") as f:
        aksjer = json.load(f)["aksjer"]
    today = datetime.date.today().isoformat()
    titler, lange, uten = vurder(aksjer, today)

    if "--alle" in sys.argv:
        for ticker, t in titler:
            print(f"{len(t):3}  {ticker:6} {t}")
        print()

    print(f"{len(titler)} titler, {len(titler) - len(uten)} med beløp per aksje.\n")
    print(f"Over {fs.TITTEL_MAKS} tegn ({len(lange)}):")
    for ticker, t in sorted(lange, key=lambda x: len(x[1])):
        print(f"  {len(t):3}  {ticker:6} {t}")
    print(f"\nUten beløp ({len(uten)}):")
    for ticker, t, grunn in uten:
        print(f"  {ticker:6} {grunn:38} {t}")

    over_tak = [x for x in lange if len(x[1]) > fs.TITTEL_TAK]
    return 1 if ("--streng" in sys.argv and over_tak) else 0


if __name__ == "__main__":
    sys.exit(main())
