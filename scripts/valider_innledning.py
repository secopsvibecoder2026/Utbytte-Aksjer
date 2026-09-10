#!/usr/bin/env python3
"""Sjekker de håndskrevne innledningene i tickers.json.

Innledningen er den eneste redaksjonelle teksten på en aksjeside. Den lagres
som hele `beskrivelse` i tickers.json — avsnitt 2 og 3 bygges på nytt av
lag_beskrivelse() ved hver kjøring, så ingenting annet hører hjemme i feltet.

To krav, begge lette å bryte uten at noe varsler:

  1. Ingen frase fra _AUTO_TEGN. _manuell_del() kutter teksten ved første
     treff, så en innledning som inneholder «noe som gjør» mister alt etter
     det punktet — stille. Listen inneholder helt vanlige norske
     konstruksjoner, så dette er ikke en teoretisk fare.
  2. Ingen tall som kan drifte: yield, utbetalingsgrad, markedsverdi,
     årstelling. Faste historiske årstall er greit. DNBs innledning lovet
     «ofte over 7% yield» mens setningen under viste 5,6 %.

Kjør:
    python3 scripts/valider_innledning.py            # sjekk alle
    python3 scripts/valider_innledning.py --korte    # list dem under 90 ord
    python3 scripts/valider_innledning.py --streng   # exit 1 ved funn
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from utvid_beskrivelser import _AUTO_TEGN, _manuell_del, SEKTOR_DRIVER

TICKERS_F = os.path.join(ROOT, "data", "tickers.json")

MAAL_MIN, MAAL_MAKS = 90, 180

# Tall som flytter seg. Årstall står igjen med vilje — «stiftet i 1965» og
# «tok navnet i 2017» er faste fakta og skal kunne stå i teksten.
_DRIFTENDE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|prosent|milliard|million|kroner|NOK|kr\b)"
    r"|\b\d+\s*(?:år på rad|år med utbytte|sammenhengende år)\b",
    re.IGNORECASE,
)


def valider_tekst(tekst: str, sektor: str = "") -> list:
    """Feil i en *ferdigskrevet* innledning. Tom liste betyr i orden.

    Teksten som sendes inn skal være innledningen alene. Sender du hele
    `beskrivelse`-feltet for en aksje som ennå ikke er skrevet om, vil de
    frosne genererte avsnittene naturligvis slå ut på alt her — bruk
    _manuell_del() først, slik main() gjør.
    """
    feil = []
    if not tekst.strip():
        return ["tom"]

    for tag in _AUTO_TEGN:
        if tag in tekst.lower():
            feil.append(f"inneholder _AUTO_TEGN «{tag}» — teksten ville blitt kuttet der")

    for m in _DRIFTENDE.findall(tekst):
        feil.append(f"tall som drifter: «{m.strip()}»")

    # Rundtur: overlever teksten _manuell_del() uendret? Fanger også
    # tilfeller der en frase over ikke sto i listen, men i SEKTOR_DRIVER.
    tilbake = _manuell_del(tekst, SEKTOR_DRIVER.get(sektor, ""))
    if tilbake.strip() != tekst.strip():
        tapt = len(tekst.split()) - len(tilbake.split())
        feil.append(f"_manuell_del() kutter {tapt} ord")

    return feil


def main():
    streng = "--streng" in sys.argv
    vis_korte = "--korte" in sys.argv

    with open(TICKERS_F, encoding="utf-8") as f:
        tickere = json.load(f)

    feilende, korte, urenset = {}, [], []
    for t in tickere:
        raa = t.get("beskrivelse", "") or ""
        sektor = t.get("sektor") or ""
        intro = _manuell_del(raa, SEKTOR_DRIVER.get(sektor, ""))

        feil = valider_tekst(intro, sektor)
        if feil:
            feilende[t["ticker"]] = feil

        n = len(intro.split())
        if n < MAAL_MIN:
            korte.append((n, t["ticker"], sektor))

        # Feltet skal inneholde innledningen alene. Ligger det frossen
        # generert prosa der fra en gammel kjøring av utvid_beskrivelser.py,
        # er aksjen ikke skrevet om ennå.
        if intro.strip() != raa.strip():
            urenset.append(t["ticker"])

    for tick, feil in sorted(feilende.items()):
        print(f"  FEIL {tick}:")
        for f_ in feil:
            print(f"        {f_}")

    skrevet = len(tickere) - len(korte)
    print(f"\n{len(tickere)} aksjer: {skrevet} med utskrevet innledning "
          f"(≥ {MAAL_MIN} ord), {len(korte)} igjen, {len(feilende)} med feil.")
    if urenset:
        print(f"{len(urenset)} har fortsatt frossen generert prosa i feltet "
              f"— de er ikke skrevet om ennå.")

    if vis_korte:
        print(f"\nUnder {MAAL_MIN} ord — gjenstår å skrive:")
        for n, tick, sektor in sorted(korte):
            print(f"  {n:4} ord  {tick:8} {sektor}")

    return 1 if (streng and feilende) else 0


if __name__ == "__main__":
    sys.exit(main())
