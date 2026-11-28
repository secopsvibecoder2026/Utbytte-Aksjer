"""Porten for engelske oversettelser av de håndskrevne tekstene.

Bare det som er skrevet for hånd, oversettes: sektortekstene i
sektortekster.py (SEKTOR_REDAKSJONELL) og selskapstekstene (innledningen i
tickers.json). Alt med tall bygges på engelsk av engelsk.py fra dataene.

Oversettelsene ligger i data/tekster_en.json med en kontrollsum av den norske
kilden. Endres den norske teksten, regnes oversettelsen som utdatert, og
engelsk.py viser den ikke før den er oversatt på nytt.

    python scripts/oversett.py --ko 10                 # neste i køen
    python scripts/oversett.py --kilde selskap EQNR    # kilde og ordlistetreff
    python scripts/oversett.py --skriv selskap EQNR fil.txt
    python scripts/oversett.py --sjekk [--streng]
"""

import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEKSTER = os.path.join(ROT, "data", "tekster_en.json")
ORDLISTE = os.path.join(ROT, "data", "ordliste_en.json")
ARTER = ("sektor", "selskap")

# Engelsk er lengre enn norsk i ord (sammensatte ord deles), men ikke mye.
ORD_FORHOLD = (0.85, 1.6)

# Norske småord som ikke finnes på engelsk. «for» og «i» er utelatt.
NORSK_RE = re.compile(r"\b(og|ikke|det|som|av|med|også|eller|har|blir|ble|selskapet|"
                      r"utbytte\w*|aksje\w*|banken|ved|etter|mellom|når)\b", re.I)


def _les(sti, standard):
    try:
        with open(sti, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return standard


def ordliste():
    return _les(ORDLISTE, {"termer": {}, "unngaa": []})


def tekster():
    return _les(TEKSTER, {"sektor": {}, "selskap": {}})


def kontrollsum(tekst):
    return hashlib.sha256(tekst.strip().encode("utf-8")).hexdigest()[:16]


def _aksjer():
    with open(os.path.join(ROT, "data", "aksjer.json"), encoding="utf-8") as f:
        return {a["ticker"]: a for a in json.load(f)["aksjer"]}


def kilde(art, nokkel, aksjer=None):
    """Den norske kildeteksten, eller "" når den ikke finnes."""
    if art == "sektor":
        import sektortekster
        return (sektortekster.SEKTOR_REDAKSJONELL.get(nokkel) or "").strip()
    import fetch_stocks as fs
    a = (aksjer or _aksjer()).get(nokkel)
    if not a:
        return ""
    return (fs._redaksjonell_intro(nokkel, a.get("sektor", "")) or "").strip()


def _ord(tekst):
    return re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", re.sub(r"<[^>]+>", " ", tekst))


def _tall(tekst):
    """Tall som mengde av sifferstrenger, uten tusen- og desimalskille."""
    return {re.sub(r"\D", "", t) for t in re.findall(r"\d[\d\s.,]*\d|\d", re.sub(r"<[^>]+>", " ", tekst))
            if re.sub(r"\D", "", t)}


def _tagger(tekst):
    return re.findall(r"</?([a-z0-9]+)", tekst)


def ordlistetreff(norsk, liste=None):
    """[(norsk stamme, [engelske former])] for termene som står i kilden."""
    liste = liste or ordliste()
    treff = []
    for stamme, former in liste["termer"].items():
        if re.search(r"(?<!\w)(" + stamme + ")", re.sub(r"\s+", " ", norsk), re.I):
            treff.append((stamme, former))
    return treff


def valider(art, nokkel, engelsk, norsk, navn=""):
    """Liste med feil. Tom liste betyr at teksten kan lagres."""
    feil = []
    if not engelsk.strip():
        return ["teksten er tom"]
    liste = ordliste()
    n_no, n_en = len(_ord(norsk)), len(_ord(engelsk))
    if n_no and not (ORD_FORHOLD[0] <= n_en / n_no <= ORD_FORHOLD[1]):
        feil.append(f"lengde: {n_en} ord mot {n_no} i kilden (forhold {n_en / n_no:.2f})")
    uten_unntak = engelsk
    for unntak in liste.get("tall_unntak", []):
        uten_unntak = uten_unntak.replace(unntak, " ")
    ekstra = _tall(uten_unntak) - _tall(norsk)
    if ekstra:
        feil.append(f"tall som ikke står i kilden: {sorted(ekstra)}")
    mangler = {t for t in _tall(norsk) if len(t) == 4 and t.startswith(("19", "20"))} - _tall(engelsk)
    if mangler:
        feil.append(f"årstall i kilden som mangler: {sorted(mangler)}")
    if art == "sektor" and _tagger(engelsk) != _tagger(norsk):
        feil.append("HTML-taggene er ikke de samme som i kilden, i samme rekkefølge")
    lav = re.sub(r"\s+", " ", engelsk.lower())
    for stamme, former in ordlistetreff(norsk, liste):
        if not any(f.lower() in lav for f in former):
            feil.append(f"ordliste: «{stamme}» skal bli {' / '.join(former)}")
    for ord_ in liste["unngaa"]:
        if ord_.lower() in lav:
            feil.append(f"unngå: «{ord_.strip()}»")
    renset = re.sub(r"<[^>]+>", " ", engelsk)
    for egennavn in sorted(filter(None, [navn] + liste.get("egennavn", [])), key=len, reverse=True):
        renset = renset.replace(egennavn, " ")
    norske = NORSK_RE.findall(renset)
    if norske:
        feil.append(f"norske ord: {sorted(set(norske))[:8]}")
    # Tankestrek: ingen, bortsett fra mellom tall (2021–2025).
    streker = re.findall(r"(?<!\d)[—–](?!\d)", renset)
    if streker:
        feil.append(f"{len(streker)} tankestrek(er); skriv om setningen")
    return feil


def lagre(art, nokkel, engelsk, norsk):
    # Lås, så to agenter som lagrer samtidig ikke skriver over hverandre.
    import fcntl
    with open(TEKSTER + ".las", "w") as las:
        fcntl.flock(las, fcntl.LOCK_EX)
        data = tekster()
        data.setdefault(art, {})[nokkel] = {"tekst": engelsk.strip(), "kilde": kontrollsum(norsk)}
        for a in ARTER:
            data[a] = dict(sorted(data.get(a, {}).items()))
        midl = TEKSTER + ".tmp"
        with open(midl, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(midl, TEKSTER)


def gjeldende(art, nokkel, norsk):
    """Oversettelsen når den hører til denne kilden, ellers ""."""
    rad = tekster().get(art, {}).get(nokkel) or {}
    return rad.get("tekst", "") if norsk and rad.get("kilde") == kontrollsum(norsk) else ""


def ko(antall):
    """Sektorene først, så selskapene etter markedsverdi. Utdaterte før nye."""
    import sektortekster
    data, aksjer = tekster(), _aksjer()
    i_bruk = {a.get("sektor") for a in aksjer.values()}
    # Forsyning har tekst men ingen aksjer siden ELMRA gikk ut; den har ingen side.
    kandidater = [("sektor", k, 1e9) for k in sektortekster.SEKTOR_REDAKSJONELL if k in i_bruk]
    kandidater += [("selskap", t, a.get("markedsverdi_mrd") or 0) for t, a in aksjer.items()]
    ut = []
    for art, nokkel, vekt in kandidater:
        norsk = kilde(art, nokkel, aksjer)
        if not norsk:
            continue
        rad = data.get(art, {}).get(nokkel)
        if rad and rad.get("kilde") == kontrollsum(norsk):
            continue
        ut.append((0 if rad else 1, -vekt, art, nokkel, "utdatert" if rad else "ny"))
    ut.sort()
    return [(art, n, status) for _, _, art, n, status in ut[:antall]]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ko", type=int, metavar="N")
    p.add_argument("--kilde", nargs=2, metavar=("ART", "NØKKEL"))
    p.add_argument("--skriv", nargs=3, metavar=("ART", "NØKKEL", "FIL"))
    p.add_argument("--sjekk", action="store_true")
    p.add_argument("--streng", action="store_true")
    a = p.parse_args()

    if a.ko:
        for art, n, status in ko(a.ko):
            print(f"{art}\t{n}\t{status}")
        return 0
    if a.kilde:
        art, n = a.kilde
        norsk = kilde(art, n)
        if not norsk:
            print(f"Ingen kilde for {art} {n}", file=sys.stderr)
            return 1
        print(norsk)
        print("\n--- Ordliste ---")
        for stamme, former in ordlistetreff(norsk):
            print(f"{stamme} → {' / '.join(former)}")
        return 0
    if a.skriv:
        art, n, fil = a.skriv
        if art not in ARTER:
            print(f"Ukjent art: {art}", file=sys.stderr)
            return 1
        with open(fil, encoding="utf-8") as f:
            engelsk = f.read()
        norsk = kilde(art, n)
        navn = _aksjer().get(n, {}).get("navn", "") if art == "selskap" else ""
        feil = valider(art, n, engelsk, norsk, navn) if norsk else [f"ingen kilde for {art} {n}"]
        if feil:
            print(f"IKKE LAGRET {art} {n}:")
            for f_ in feil:
                print(f"  - {f_}")
            return 1
        lagre(art, n, engelsk, norsk)
        print(f"Lagret {art} {n} ({len(_ord(engelsk))} ord)")
        return 0
    if a.sjekk:
        aksjer, antall_feil, utdatert = _aksjer(), 0, []
        for art, rader in tekster().items():
            for n, rad in rader.items():
                norsk = kilde(art, n, aksjer)
                if rad.get("kilde") != kontrollsum(norsk):
                    utdatert.append(f"{art} {n}")
                    continue
                navn = aksjer.get(n, {}).get("navn", "") if art == "selskap" else ""
                for f_ in valider(art, n, rad["tekst"], norsk, navn):
                    print(f"{art} {n}: {f_}")
                    antall_feil += 1
        for u in utdatert:
            print(f"utdatert (kilden er endret): {u}")
        print(f"{antall_feil} feil, {len(utdatert)} utdaterte")
        return 1 if a.streng and antall_feil else 0
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
