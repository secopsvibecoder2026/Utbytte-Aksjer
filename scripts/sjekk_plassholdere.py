#!/usr/bin/env python3
"""Finner plassholdere som ikke er fylt inn, i sider som publiseres.

/om/ ble skrevet med [NAVN] og [KONTAKT-E-POST] der eieren selv fyller inn
navn og e-post (2026-11-18). En side som viser «[NAVN]» til lesere og Google
er verre enn ingen avsender, så CI er rødt så lenge en plassholder står igjen.

    python scripts/sjekk_plassholdere.py            # rapport, avslutter 0
    python scripts/sjekk_plassholdere.py --streng   # avslutt 1 ved funn
"""

import os
import re
import sys

HOPP_OVER = {".git", "node_modules", "data", "test-results", "promo", "scripts", "tests", ".claude", ".github"}

# Store bokstaver i hakeparentes, som [NAVN] eller [KONTAKT-E-POST].
PLASSHOLDER = re.compile(r"\[(?:[A-ZÆØÅ]{2,}(?:-[A-ZÆØÅ]+)*)\]")


def finn_plassholdere(rot="."):
    funn = []
    for mappe, undermapper, filer in os.walk(rot):
        undermapper[:] = [d for d in undermapper if d not in HOPP_OVER]
        for navn in filer:
            if not navn.endswith(".html"):
                continue
            sti = os.path.join(mappe, navn)
            with open(sti, encoding="utf-8", errors="ignore") as f:
                for nr, linje in enumerate(f, 1):
                    for m in PLASSHOLDER.finditer(linje):
                        funn.append((os.path.relpath(sti, rot), nr, m.group(0)))
    return funn


def main():
    rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    funn = finn_plassholdere(rot)
    if not funn:
        print("Ingen plassholdere.")
        return 0
    print(f"{len(funn)} plassholdere er ikke fylt inn:")
    for fil, nr, tekst in funn:
        print(f"  {fil}:{nr}  {tekst}")
    return 1 if "--streng" in sys.argv else 0


if __name__ == "__main__":
    sys.exit(main())
