#!/usr/bin/env python3
"""Sjekker at interne lenker peker på noe som faktisk finnes på disk.

Bakgrunn: forsiden lenket til /aksjer/sektor/sjomat/ i lang tid. Sektoren
heter Havbruk, så lenken ga 404 — på den mest besøkte siden på nettstedet,
i et kortgalleri der den så helt normal ut. Ingenting fanget den opp:
sitemap-generatoren sjekker bare sider den selv lager, og ingen test leste
den håndskrevne HTML-en.

Kjøres i update-og-deploy.yml etter valider_data.py. Den blokkerer ikke
deployen — en brutt lenke skal ikke stoppe kursoppdateringer — men den
skriver til jobbsammendraget og kan kjøres med --streng lokalt.

    python scripts/sjekk_lenker.py            # rapport, avslutter alltid 0
    python scripts/sjekk_lenker.py --streng   # avslutt 1 ved brutte lenker
"""

import os
import re
import sys
from collections import defaultdict

# Mapper som ikke inneholder sider vi lenker til.
HOPP_OVER = {".git", "node_modules", "data", "logo", "promo", "assets"}

# Lenker som med vilje peker utenfor disken.
UNNTAK = {"/", "/sitemap.xml", "/robots.txt", "/ads.txt", "/manifest.json"}


def _html_filer(rot):
    for mappe, undermapper, filer in os.walk(rot):
        undermapper[:] = [d for d in undermapper if d not in HOPP_OVER]
        for f in filer:
            if f.endswith(".html"):
                yield os.path.join(mappe, f)


def _maalet_finnes(url, rot):
    """Finnes det en fil eller en index.html på denne stien?"""
    sti = url.lstrip("/")
    if not sti:
        return True
    full = os.path.join(rot, sti)
    return os.path.isfile(full) or os.path.isfile(os.path.join(full, "index.html"))


def finn_brutte(rot="."):
    """Returnerer {url: {filer som lenker dit}} for lenker uten mål."""
    lenker = defaultdict(set)
    for f in _html_filer(rot):
        try:
            s = open(f, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for url in re.findall(r'href="(/[^"#?]*)"', s):
            # Hopp over JS-maler som «/aksjer/${a.ticker}/» — de fylles ut
            # i nettleseren og har ingen fil bak seg her.
            if "${" in url or "{{" in url:
                continue
            if url in UNNTAK:
                continue
            lenker[url].add(os.path.relpath(f, rot))

    return {
        url: kilder
        for url, kilder in lenker.items()
        if not _maalet_finnes(url, rot)
    }, len(lenker)


def main():
    streng = "--streng" in sys.argv
    rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    brutte, totalt = finn_brutte(rot)

    print(f"Interne lenker: {totalt} unike mål kontrollert")
    if not brutte:
        print("Ingen brutte lenker.")
        return 0

    print(f"\n{len(brutte)} BRUTTE LENKER:\n")
    for url, kilder in sorted(brutte.items()):
        print(f"  {url}")
        for k in sorted(kilder)[:5]:
            print(f"      ← {k}")
        if len(kilder) > 5:
            print(f"      … og {len(kilder) - 5} til")

    # Skriv til GitHub Actions-sammendraget hvis vi kjører der.
    sammendrag = os.environ.get("GITHUB_STEP_SUMMARY")
    if sammendrag:
        with open(sammendrag, "a", encoding="utf-8") as f:
            f.write(f"\n### Brutte interne lenker ({len(brutte)})\n\n")
            f.write("| Lenke | Står på |\n|---|---|\n")
            for url, kilder in sorted(brutte.items()):
                f.write(f"| `{url}` | {', '.join(sorted(kilder)[:3])} |\n")

    return 1 if streng else 0


if __name__ == "__main__":
    sys.exit(main())
