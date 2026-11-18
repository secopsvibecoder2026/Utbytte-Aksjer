#!/usr/bin/env python3
"""Feiler når kursene i data/priser.json ikke er oppdatert (2026-11-18).

Kursjobben (oppdater-priser.yml, startet av klokke.yml) skal skrive nye kurser
omtrent hvert kvarter i børstiden. Stopper den, ser appen og aksjesidene
gamle kurser, og ingenting i GitHub Actions blir rødt: kursjobben som ikke
kjører, feiler heller ikke. Datajobben kjører uansett fire ganger hver
børsdag, så sjekken står der, i en egen jobb som ikke stopper publiseringen.

Regelen:
- Kursene skal gjelde gjeldende børsdag. Før kl. 09 i Oslo er det forrige
  børsdag, som i kursdag() i assets/app.js.
- Ligger den nyeste kursen bak gjeldende børsdag, feiler sjekken. Eneste
  unntak er samme dag før kl. 10.30 (KURS_FORVENTET_ETTER): da har
  kursjobben ikke rukket å hente dagens kurser.

Børsens fridager kommer fra borsfridager() i fetch_stocks.py, så en kjøring
på en fridag ikke feiler.

    python scripts/sjekk_kursferskhet.py           # skriv status, avslutt 1 ved gamle kurser
"""

import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRISER = os.path.join(ROT, "data", "priser.json")
KURS_FORVENTET_ETTER = datetime.time(10, 30)


def _er_borsdag(d):
    from fetch_stocks import borsfridager
    return d.weekday() < 5 and d not in borsfridager(d.year)


def gjeldende_borsdag(naa_oslo):
    """Børsdagen kursene skal gjelde: i dag fra kl. 09, ellers forrige børsdag."""
    d = naa_oslo.date() - datetime.timedelta(days=1) if naa_oslo.hour < 9 else naa_oslo.date()
    while not _er_borsdag(d):
        d -= datetime.timedelta(days=1)
    return d


def borsdager_etter(fra, til):
    """Børsdager etter `fra`, til og med `til`."""
    n, d = 0, fra
    while d < til:
        d += datetime.timedelta(days=1)
        if _er_borsdag(d):
            n += 1
    return n


def nyeste_kursdag(priser):
    """Den nyeste handelsdagen i priser.json, eller None."""
    datoer = []
    for rad in ((priser or {}).get("aksjer") or {}).values():
        try:
            datoer.append(datetime.date.fromisoformat(str(rad.get("dato"))[:10]))
        except (TypeError, ValueError, AttributeError):
            continue
    return max(datoer) if datoer else None


def vurder(priser, naa_oslo):
    """(feil, melding). `feil` er True når kursene er for gamle."""
    nyeste = nyeste_kursdag(priser)
    if nyeste is None:
        return True, "priser.json har ingen kurser med dato."
    maal = gjeldende_borsdag(naa_oslo)
    bak = borsdager_etter(nyeste, maal)
    if bak == 0:
        return False, f"Kursene er fra {nyeste.isoformat()}, som er gjeldende børsdag."
    if bak >= 2:
        return True, (f"Nyeste kurs er fra {nyeste.isoformat()}, {bak} børsdager bak "
                      f"{maal.isoformat()}. Kursjobben har ikke kjørt.")
    if naa_oslo.date() != maal:
        return True, (f"Nyeste kurs er fra {nyeste.isoformat()}, men børsdagen "
                      f"{maal.isoformat()} er over uten nye kurser.")
    if naa_oslo.time() >= KURS_FORVENTET_ETTER:
        return True, (f"Klokka er {naa_oslo:%H:%M} og nyeste kurs er fra {nyeste.isoformat()}. "
                      "Dagens kurser skulle vært hentet.")
    return False, (f"Nyeste kurs er fra {nyeste.isoformat()}. Dagens kurser ventes "
                   f"etter kl. {KURS_FORVENTET_ETTER:%H.%M}.")


def main():
    from zoneinfo import ZoneInfo
    naa = datetime.datetime.now(ZoneInfo("Europe/Oslo"))
    try:
        with open(PRISER, encoding="utf-8") as f:
            priser = json.load(f)
    except (OSError, ValueError) as e:
        priser, feil, melding = None, True, f"Kunne ikke lese priser.json: {e}"
    else:
        feil, melding = vurder(priser, naa)

    print(melding)
    sammendrag = os.environ.get("GITHUB_STEP_SUMMARY")
    if sammendrag:
        with open(sammendrag, "a", encoding="utf-8") as f:
            f.write(f"\n### Kursferskhet\n\n{'❌' if feil else '✅'} {melding}\n")
    if feil:
        # Annotasjonen vises øverst på kjøringen i GitHub Actions.
        print(f"::error title=Kursene er ikke oppdatert::{melding}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
