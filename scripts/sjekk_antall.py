#!/usr/bin/env python3
"""Finner hardkodede aksjetellinger som skulle vært en markør.

Bakgrunn: `/om/` viste **191 «Aksjer fulgt»** mens katalogen var 155. Tallet
er ikke en tilfeldig skrivefeil — 191 er nøyaktig det tallet
`oppdater_antall_i_sider()` ble skrevet for å bli kvitt, og docstringen der
nevner det ved navn. Resten av `/om/` fikk markører; hovedtallet øverst på
sida, det største og mest synlige, fikk det ikke. `promo/facebook-post.html`
sto med 124 på samme vis, og det tallet havner på et bilde som publiseres.

Markørmekanismen virker. Feilen er at noen skriver et bart tall i stedet, og
da har generatoren ingenting å fylle ut. Det ser riktig ut den dagen det
skrives og drifter stille etterpå — katalogen har vært 191 → 163 → 161 → 160
→ 155 mens sidene sto stille.

Sjekken er med vilje **smal**, ellers drukner den i tall som skal stå i fred:
kronebeløp, regneeksempler, årstall og rådtekst som «diversifiser på 15–20
selskaper». Den ser bare etter et heltall i et realistisk katalogintervall
som står rett foran ordet «aksjer» eller «selskaper» i synlig tekst.

Disse hoppes over:

- `aksjer/**` og `/rapportkalender/` — genereres fra tallene i samme kjøring
- `artikler/**` — CLAUDE.md tillater et eksakt, datostemplet tall i
  brødteksten. «alle 137 utbyttebetalende selskaper» står under «data
  oppdatert 30. august 2026», og det er meningen.
- Tall med et forbehold foran («over 150», «mer enn 150») — den rundede
  formen som brukes i `<meta>` og JSON-LD, der en HTML-kommentar ikke kan stå

    python scripts/sjekk_antall.py            # rapport, avslutter alltid 0
    python scripts/sjekk_antall.py --streng   # avslutt 1 ved funn
"""

import os
import re
import sys

HOPP_OVER = {".git", "node_modules", "data", "logo", "test-results",
             "aksjer", "artikler", "rapportkalender"}

# Et antall som er lavere enn dette er neppe katalogstørrelsen, og et som er
# høyere er neppe et selskapsantall på Oslo Børs.
MIN_ANTALL, MAKS_ANTALL = 100, 400

# «over 150 norske utbytteaksjer» er den godkjente rundede formen.
_FORBEHOLD = re.compile(r"(over|mer enn|rundt|nesten|minst|under|ca\.?|opptil)\s*$", re.I)

_TELLING = re.compile(
    r"(?<![\d.,])(\d{2,3})(?![\d.,])\s+(?:norske\s+)?(aksjer|selskaper|utbytteaksjer)\b",
    re.I,
)


def _synlig_tekst(html):
    """HTML strippet til det leseren ser, med markørinnhold nøytralisert."""
    t = re.sub(r"<!--N:\w+-->.*?<!--/N-->", " MARKOER ", html, flags=re.S)
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    # Attributter bort før tagger: klassenavn som «gray-200» ser ellers ut
    # som tall i teksten.
    t = re.sub(r"<(\w+)[^>]*>", r" <\1> ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(t.replace("\xa0", " ").split())


def finn_hardkodede(rot="."):
    """Returnerer [(fil, tall, kontekst)] for tellinger uten markør."""
    funn = []
    for mappe, undermapper, filer in os.walk(rot):
        undermapper[:] = [d for d in undermapper if d not in HOPP_OVER]
        for navn in filer:
            if not navn.endswith(".html"):
                continue
            sti = os.path.join(mappe, navn)
            with open(sti, encoding="utf-8", errors="ignore") as f:
                tekst = _synlig_tekst(f.read())
            for m in _TELLING.finditer(tekst):
                n = int(m.group(1))
                if not (MIN_ANTALL <= n <= MAKS_ANTALL):
                    continue
                if _FORBEHOLD.search(tekst[max(0, m.start() - 20):m.start()]):
                    continue
                kontekst = tekst[max(0, m.start() - 55):m.end() + 25]
                funn.append((os.path.relpath(sti, rot), m.group(0), kontekst))
    return funn


def main():
    streng = "--streng" in sys.argv
    rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    funn = finn_hardkodede(rot)

    if not funn:
        print("Ingen hardkodede aksjetellinger.")
        return 0

    print(f"{len(funn)} HARDKODEDE TELLINGER — skulle vært <!--N:aksjer-->:\n")
    for fil, treff, kontekst in funn:
        print(f"  {fil}   «{treff}»")
        print(f"      …{kontekst}…")

    sammendrag = os.environ.get("GITHUB_STEP_SUMMARY")
    if sammendrag:
        with open(sammendrag, "a", encoding="utf-8") as f:
            f.write(f"\n### Hardkodede aksjetellinger ({len(funn)})\n\n")
            f.write("| Side | Tall |\n|---|---|\n")
            for fil, treff, _ in funn:
                f.write(f"| `{fil}` | {treff} |\n")

    return 1 if streng else 0


if __name__ == "__main__":
    sys.exit(main())
