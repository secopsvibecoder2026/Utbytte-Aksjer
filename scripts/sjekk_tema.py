#!/usr/bin/env python3
"""Sjekker at mørk modus faktisk slår inn på hver side som har `dark:`-klasser.

Bakgrunn: /verktoy/ ble rapportert å «miste dark mode». Det viste seg å være
to helt ulike feil, og ingen av dem synes i en kodegjennomgang:

1. Feil nøkkel. uke/, personvern/ og bevegelser/ leste `getItem('theme')` —
   det engelske ordet — mens resten av nettstedet skriver `'tema'`. Sidene
   holdt en privat temastatus som ingenting annet skrev til, så mørk modus
   valgt et annet sted slo aldri inn. Total svikt, ikke et blink.
   utbyttekalender/ leste begge nøkler som reserve og skjulte dermed samme
   feil bak en side som virket.

2. Skript etter `</head>`. Seks sider satte klassen inne i `<body>`. Klassen
   *ble* satt, så alt så riktig ut om man bare lette etter den — men body
   hadde allerede malt seg opp i lys modus, så leseren fikk et hvitt blink.

Regelen sto allerede i CLAUDE.md og var likevel brutt fire steder. En regel
ingen måler, holder ikke. Derfor denne.

Sider uten `dark:`-klasser hoppes over — de har ingen mørk modus å miste.

Kjøres i update-og-deploy.yml ved siden av sjekk_lenker.py, og blokkerer
ikke deployen av samme grunn: et temablink skal ikke stoppe kursoppdateringer.

    python scripts/sjekk_tema.py            # rapport, avslutter alltid 0
    python scripts/sjekk_tema.py --streng   # avslutt 1 ved feil
"""

import os
import re
import sys

HOPP_OVER = {".git", "node_modules", "data", "logo", "promo", "assets"}

# Den engelske nøkkelen. Hele nettstedet bruker 'tema'.
FEIL_NOKKEL = re.compile(r"getItem\(\s*['\"]theme['\"]\s*\)")
RIKTIG_NOKKEL = re.compile(r"getItem\(\s*['\"]tema['\"]\s*\)")


def _html_filer(rot):
    for mappe, undermapper, filer in os.walk(rot):
        undermapper[:] = [d for d in undermapper if d not in HOPP_OVER]
        for f in filer:
            if f.endswith(".html"):
                yield os.path.join(mappe, f)


def _har_morkt_tema(s):
    """Bruker siden mørk modus i det hele tatt?"""
    return "dark:" in s or ".dark " in s


def sjekk_side(s):
    """Returnerer en liste med problemer for én sides HTML."""
    problemer = []
    if not _har_morkt_tema(s):
        return problemer

    if FEIL_NOKKEL.search(s):
        problemer.append("leser 'theme' — nøkkelen er 'tema'")

    i = s.lower().find("</head>")
    hode = s[:i] if i > 0 else ""
    tidlig = bool(RIKTIG_NOKKEL.search(hode)) and "classList.add" in hode
    if not tidlig:
        if RIKTIG_NOKKEL.search(s):
            problemer.append("temaskript ligger etter </head> — body rekker å male seg lys")
        else:
            problemer.append("ingen temainitialisering")

    return problemer


def finn_feil(rot="."):
    """Returnerer ({fil: [problemer]}, antall kontrollerte sider)."""
    feil, kontrollert = {}, 0
    for f in _html_filer(rot):
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                s = fh.read()
        except OSError:
            continue
        if not _har_morkt_tema(s):
            continue
        kontrollert += 1
        problemer = sjekk_side(s)
        if problemer:
            feil[os.path.relpath(f, rot)] = problemer
    return feil, kontrollert


def main():
    streng = "--streng" in sys.argv
    rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    feil, kontrollert = finn_feil(rot)

    print(f"Mørk modus: {kontrollert} sider kontrollert")
    if not feil:
        print("Alle setter .dark fra 'tema' i <head>.")
        return 0

    print(f"\n{len(feil)} SIDER MED TEMAFEIL:\n")
    for fil, problemer in sorted(feil.items()):
        print(f"  {fil}")
        for p in problemer:
            print(f"      {p}")

    sammendrag = os.environ.get("GITHUB_STEP_SUMMARY")
    if sammendrag:
        with open(sammendrag, "a", encoding="utf-8") as f:
            f.write(f"\n### Sider med temafeil ({len(feil)})\n\n")
            f.write("| Side | Problem |\n|---|---|\n")
            for fil, problemer in sorted(feil.items()):
                f.write(f"| `{fil}` | {'; '.join(problemer)} |\n")

    return 1 if streng else 0


if __name__ == "__main__":
    sys.exit(main())
