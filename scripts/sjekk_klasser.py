#!/usr/bin/env python3
"""Sjekker at hver CSS-klasse i HTML-en faktisk er definert et sted.

Bakgrunn: «Åpne gratis app»-knappen sto med hvit tekst uten bakgrunn og var
usynlig i lys modus. Årsaken var ikke i markupen — den sa `bg-green-600
text-white` og var helt riktig — men i byggetrinnet:

Tailwind v4 velger hvilke filer den skanner ut fra mappa som CSS-inngangen
ligger i. Inngangen er `assets/tw-input.css`, så bare `assets/` ble skannet.
Hver klasse som *bare* står i en HTML-side falt dermed ut av stilarket.
`bg-green-500` overlevde fordi den tilfeldigvis også står i `assets/ui.js`;
`bg-green-600` gjorde ikke det. Målt over hele nettstedet manglet **147
klasser i 4 428 forekomster**.

Det er den verste typen feil: markupen er riktig, ingenting feiler, og
resultatet er usynlig helt til noen ser på siden i riktig tema.

`@source "../"` i `tw-input.css` er selve fiksen. Denne sjekken er
etterprøvingen, og fanger også de to andre variantene den avdekket:

- en `brand-*`-nyanse som ikke finnes i `@theme` (brand-200/300/400/800/950
  var i bruk 71 steder uten å være definert)
- en klasse fra en Tailwind-plugin vi ikke har installert (`scrollbar-hide`,
  `prose-sm`, `dark:prose-invert` …)

Klasser som bare er JS-kroker teller som definert hvis de finnes i
`assets/*.js` — de skal ikke ha CSS.

    python scripts/sjekk_klasser.py            # rapport, avslutter alltid 0
    python scripts/sjekk_klasser.py --streng   # avslutt 1 ved udefinerte
"""

import collections
import os
import re
import sys

HOPP_OVER = {".git", "node_modules", "data", "logo", "promo", "test-results"}

# Klassenavn i en CSS-selektor. Tailwind escaper : / . [ ] % med backslash,
# så `\\.` må stå først i alternasjonen — ellers spiser tegnklassen
# backslashen og stopper på kolonet i `dark\:text-gray-400`.
# Et uescapet punktum starter en ny klasse: `.val.green` er to, ikke én.
# Et escapet punktum hører til navnet: `mx-1.5` skrives `.mx-1\.5`.
_KLASSE_I_CSS = re.compile(r"\.((?:\\.|[^\s{},>+~()\[\]\"':;.\\])+)")

# Fragmenter fra JS-malstrenger inne i class="..." — ikke klasser.
_STOEY = re.compile(r"^[^A-Za-z]|[?'\"(){}$]")

# Sjekken gjelder **bare Tailwind-utilities**. Det er den feilen som faktisk
# oppsto: utilities som ikke ble generert. Egne klasser og JS-kroker
# (`faq-q`, `sb-rad`, `sun-icon`, `mnd-ja` …) styles av sidens egen
# <style>-blokk eller plukkes opp av et inline <script>, og en sjekk som
# gjetter på dem gir bare falske positive. Første utkast rapporterte 37
# klasser der ingen av dem var feil — verre enn ingen sjekk, siden det leses
# som dekning.
_VARIANT = (r"(?:sm|md|lg|xl|2xl|dark|hover|focus|focus-visible|active|disabled|group-hover"
            r"|group-open|peer-checked|first|last|odd|even|motion-safe|motion-reduce|print|rtl|ltr)")
_UTIL = re.compile(
    r"^-?(?:" + _VARIANT + r":)*"
    r"-?(?:bg|text|border|ring|divide|outline|from|via|to|fill|stroke|shadow|rounded|opacity"
    r"|p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|ml|mr|w|h|size|min-w|min-h|max-w|max-h|basis"
    r"|gap|space|flex|grid|col|row|items|justify|self|place|order|inset|top|bottom|left|right|z"
    r"|leading|tracking|font|list|underline|no-underline|line-through|truncate|whitespace|break"
    r"|overflow|object|aspect|transition|duration|ease|delay|animate|transform|translate|rotate"
    r"|scale|skew|origin|cursor|select|resize|appearance|accent|caret|scroll|snap|touch"
    r"|sr-only|not-sr-only|hidden|block|inline|inline-block|inline-flex|table|contents|backdrop"
    r"|blur|invert|prose|container|antialiased|italic|uppercase|lowercase|capitalize|align|indent"
    r"|columns|isolate|mix-blend|shrink|grow|float|clear|visible|invisible|static|fixed|absolute"
    r"|relative|sticky|pointer-events|scrollbar)"
    r"(?:-|$|\[|/)")


def _avesc(s):
    return re.sub(r"\\(.)", r"\1", s)


def klasser_i_css(tekst):
    return {_avesc(m.group(1)) for m in _KLASSE_I_CSS.finditer(tekst)}


def _filer(rot, endelse):
    for mappe, undermapper, filer in os.walk(rot):
        undermapper[:] = [d for d in undermapper if d not in HOPP_OVER]
        for f in filer:
            if f.endswith(endelse):
                yield os.path.join(mappe, f)


def finn_udefinerte(rot="."):
    """Returnerer ({klasse: (antall, filer)}, antall kontrollerte klasser)."""
    definert = set()
    for navn in ("assets/tailwind.css", "assets/style.css"):
        sti = os.path.join(rot, navn)
        if os.path.isfile(sti):
            with open(sti, encoding="utf-8", errors="ignore") as f:
                definert |= klasser_i_css(f.read())

    # En klasse som bare er en JS-krok trenger ingen CSS.
    js = ""
    for f in _filer(os.path.join(rot, "assets"), ".js"):
        with open(f, encoding="utf-8", errors="ignore") as fh:
            js += fh.read()

    bruk = collections.Counter()
    hvor = collections.defaultdict(set)
    per_fil_definert = {}

    for f in _filer(rot, ".html"):
        with open(f, encoding="utf-8", errors="ignore") as fh:
            s = fh.read()
        rel = os.path.relpath(f, rot)
        # Sider har egne <style>-blokker; de gjelder bare den sida.
        egne = set()
        for blokk in re.findall(r"<style[^>]*>(.*?)</style>", s, re.S):
            egne |= klasser_i_css(blokk)
        per_fil_definert[rel] = egne
        for attr in re.findall(r'class="([^"]*)"', s):
            if "${" in attr or "{{" in attr:
                continue
            for kl in attr.split():
                if _STOEY.search(kl) or not _UTIL.match(kl):
                    continue
                bruk[kl] += 1
                hvor[kl].add(rel)

    udef = {}
    for kl, n in bruk.items():
        if kl in definert or ("." + kl) in js or ("'" + kl) in js or ('"' + kl) in js:
            continue
        # Definert i hver enkelt sides egen <style>? Da er den grei.
        mangler_i = {f for f in hvor[kl] if kl not in per_fil_definert.get(f, set())}
        if mangler_i:
            udef[kl] = (sum(1 for _ in range(n)), sorted(mangler_i))
    return udef, len(bruk)


def main():
    streng = "--streng" in sys.argv
    rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    udef, totalt = finn_udefinerte(rot)

    print(f"CSS-klasser i HTML: {totalt} unike kontrollert")
    if not udef:
        print("Alle er definert.")
        return 0

    print(f"\n{len(udef)} UDEFINERTE KLASSER:\n")
    for kl, (n, filer) in sorted(udef.items(), key=lambda x: -x[1][0]):
        vis = filer[0] if len(filer) == 1 else f"{len(filer)} filer"
        print(f"  {n:5}  {kl:<34} {vis}")

    sammendrag = os.environ.get("GITHUB_STEP_SUMMARY")
    if sammendrag:
        with open(sammendrag, "a", encoding="utf-8") as f:
            f.write(f"\n### Udefinerte CSS-klasser ({len(udef)})\n\n")
            f.write("| Klasse | Bruk | Står på |\n|---|---|---|\n")
            for kl, (n, filer) in sorted(udef.items(), key=lambda x: -x[1][0]):
                f.write(f"| `{kl}` | {n} | {', '.join(filer[:3])} |\n")

    return 1 if streng else 0


if __name__ == "__main__":
    sys.exit(main())
