#!/usr/bin/env python3
"""
sjekk_sprak.py — måler det i SKRIVESTIL.md som kan telles.

    python scripts/sjekk_sprak.py artikler/hva-er-ex-dato/index.html
    python scripts/sjekk_sprak.py --plan              # siste innlegg i publiseringsplanen
    python scripts/sjekk_sprak.py --plan rekke-2026-10
    python scripts/sjekk_sprak.py --streng FIL ...    # exit 1 ved brudd

Hvorfor et skript og ikke bare en regel: artiklene hadde 18–49 tankestreker
hver da stilen ble skrevet ned (2026-10-06). Ingen hadde bedt om dem, og
ingen hadde sett dem, fordi ingen telte. Samme lærdom som sjekk_tema.py: en
regel ingen måler, holder ikke.

Bare to ting telles, fordi bare de lar seg telle uten mye støy:
tankestreker og et fast sett vendinger. Resten av stilguiden må leses.
"""
import argparse
import html
import json
import os
import re
import sys

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROT, "promo", "publiseringsplan.json")

ORD_PER_STREK = 200

# Tankestrek: — alltid; – bare med mellomrom rundt. «2021–2025» er et
# tallområde og skal ikke telles.
_STREK = re.compile(r"—|(?<=\s)–(?=\s)")

VENDINGER = [
    r"\bla oss\b",
    r"\bi denne artikkelen\b",
    r"\bher er det du trenger å vite\b",
    r"\bkort fortalt\b",
    r"\bkort sagt\b",
    r"\boppsummert\b",
    r"\bmed andre ord\b",
    r"\bdet er verdt å merke seg\b",
    r"\bdet er viktig å huske\b",
    r"\bnøkkelen er\b",
    r"\bsvaret er enkelt\b",
    r"\bikke bare\b[^.!?]{1,80}\bmen også\b",
    r"\bdet handler ikke om\b",
    r"\brobust\w*\b",
    r"\bsømløs\w*\b",
    r"\bhelhetlig\w*\b",
    r"\bkraftig(?:e)? verktøy\b",
    r"\bnaviger\w*\b",
    r"\blandskapet\b",
    r"\bgame ?changer\b",
    r"\bspillveksler\b",
    r"\bunik(?:e)? mulighet\w*\b",
    r"\benten du er nybegynner\b",
    r"\bdykke ned\b",
]
_VENDINGER = [re.compile(v, re.I) for v in VENDINGER]


def avsnitt_fra_html(kilde):
    """Synlige tekstavsnitt fra en HTML-side, uten meny, bunntekst og skript.

    Har siden et <article>, brukes bare det — da telles verken navigasjonen
    eller standardbunnteksten, som ikke er artikkelens tekst.
    """
    s = re.sub(r"<(script|style|nav|header|footer)\b[^>]*>.*?</\1>", " ", kilde,
               flags=re.S | re.I)
    m = re.search(r"<article\b.*?</article>", s, re.S | re.I)
    if m:
        s = m.group(0)
    ut = []
    for blokk in re.findall(r"<(p|li|h[1-4]|blockquote|td)\b[^>]*>(.*?)</\1>", s, re.S | re.I):
        tekst = html.unescape(re.sub(r"<[^>]+>", " ", blokk[1]))
        tekst = re.sub(r"\s+", " ", tekst).strip()
        if tekst:
            ut.append(tekst)
    return ut


def avsnitt_fra_tekst(tekst):
    return [re.sub(r"\s+", " ", a).strip() for a in re.split(r"\n\s*\n", tekst) if a.strip()]


def vurder(avsnitt):
    """Funn for en liste avsnitt: {"ord", "streker", "maks", "tette", "vendinger"}."""
    ord_ = sum(len(a.split()) for a in avsnitt)
    streker = sum(len(_STREK.findall(a)) for a in avsnitt)
    tette = [a for a in avsnitt if len(_STREK.findall(a)) > 1]
    vendinger = []
    for a in avsnitt:
        for v in _VENDINGER:
            for m in v.finditer(a):
                vendinger.append(m.group(0))
    maks = max(1, ord_ // ORD_PER_STREK)
    return {"ord": ord_, "streker": streker, "maks": maks,
            "tette": tette, "vendinger": vendinger}


def brudd(funn):
    return funn["streker"] > funn["maks"] or bool(funn["tette"]) or bool(funn["vendinger"])


def rapport(navn, funn):
    linjer = [f"{navn}: {funn['ord']} ord, {funn['streker']} tankestreker "
              f"(grense {funn['maks']})"]
    for a in funn["tette"][:5]:
        linjer.append(f"  flere streker i ett avsnitt: «{a[:110]}{'…' if len(a) > 110 else ''}»")
    if len(funn["tette"]) > 5:
        linjer.append(f"  … og {len(funn['tette']) - 5} avsnitt til")
    if funn["vendinger"]:
        linjer.append("  vendinger: " + ", ".join(f"«{v}»" for v in funn["vendinger"]))
    linjer.append("  " + ("BRUDD" if brudd(funn) else "OK"))
    return "\n".join(linjer)


def fra_plan(innlegg_id=None, sti=PLAN):
    """(navn, avsnitt) for hver kanal i ett innlegg i publiseringsplanen."""
    with open(sti, encoding="utf-8") as f:
        innlegg = json.load(f)["innlegg"]
    valgt = next((i for i in innlegg if i.get("id") == innlegg_id), None) if innlegg_id else innlegg[-1]
    if not valgt:
        raise SystemExit(f"Fant ikke innlegget {innlegg_id!r} i planen")
    ut = []
    for kanal, verdi in valgt.items():
        if isinstance(verdi, dict) and isinstance(verdi.get("tekst"), str):
            ut.append((f"{valgt.get('id')} / {kanal}", avsnitt_fra_tekst(verdi["tekst"])))
    return ut


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("filer", nargs="*")
    p.add_argument("--plan", nargs="?", const="", default=None,
                   help="sjekk et innlegg i promo/publiseringsplan.json (siste om ingen id)")
    p.add_argument("--streng", action="store_true", help="exit 1 ved brudd")
    a = p.parse_args(argv)

    mal = []
    if a.plan is not None:
        mal += fra_plan(a.plan or None)
    for fil in a.filer:
        with open(fil, encoding="utf-8") as f:
            innhold = f.read()
        avsnitt = avsnitt_fra_html(innhold) if fil.endswith(".html") else avsnitt_fra_tekst(innhold)
        mal.append((fil, avsnitt))
    if not mal:
        p.error("oppgi en fil eller --plan")

    feil = False
    for navn, avsnitt in mal:
        funn = vurder(avsnitt)
        print(rapport(navn, funn))
        feil = feil or brudd(funn)
    return 1 if (feil and a.streng) else 0


if __name__ == "__main__":
    sys.exit(main())
