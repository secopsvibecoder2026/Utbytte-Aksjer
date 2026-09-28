#!/usr/bin/env python3
"""
finn_kandidater.py — den mekaniske delen av promo-agenten.

Svarer på to spørsmål et skript kan svare på pålitelig, så agenten
(.claude/agents/promo.md) kan bruke tiden sin på det bare den kan vurdere —
hva som er verdt å promotere, og hvordan:

  1. Hvilke artikler i ARTIKLER-konstanten (assets/ui.js) er aldri promotert?
  2. Hvor lenge er det siden forrige planlagte innlegg (publiser_fra)?

Leser bare. Bruk:

    python promo/finn_kandidater.py
    python promo/finn_kandidater.py --json
"""
import argparse
import datetime
import json
import os
import re

ROT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# Matcher ett artikkelobjekt i ARTIKLER = [ {...}, {...} ]. Ikke-grådig på
# slug/tittel/meta, som alle er enkle strenger uten ekstra klammer.
_ARTIKKEL_RE = re.compile(
    r"slug:\s*'(?P<slug>[^']*)'.*?"
    r"tittel:\s*'(?P<tittel>(?:[^'\\]|\\.)*)'.*?"
    r"meta:\s*'(?P<meta>[^']*)'",
    re.S,
)


def les_artikler(ui_js_sti):
    """Alle artikler fra ARTIKLER-konstanten i ui.js, nyeste først (som i
    filen). Returnerer [] om filen mangler eller konstanten ikke finnes —
    aldri en feil, siden dette bare skal *foreslå*, ikke blokkere."""
    try:
        with open(ui_js_sti, encoding="utf-8") as f:
            tekst = f.read()
    except OSError:
        return []
    m = re.search(r"const ARTIKLER\s*=\s*\[(.*?)\n\];", tekst, re.S)
    if not m:
        return []
    ut = []
    for obj in _ARTIKKEL_RE.finditer(m.group(1)):
        ut.append({
            "url": f"https://exday.no{obj.group('slug')}",
            "tittel": obj.group("tittel").replace("\\'", "'"),
            "meta": obj.group("meta"),
        })
    return ut


def les_plan(plan_sti):
    try:
        with open(plan_sti, encoding="utf-8") as f:
            return json.load(f).get("innlegg", [])
    except (OSError, ValueError):
        return []


def ikke_promoterte_artikler(artikler, innlegg):
    """Artikler hvis URL ikke er brukt som «artikkel» i noe planlagt innlegg.

    Sammenligning på eksakt URL, ikke fuzzy — en artikkel som er promotert én
    gang skal ikke foreslås på nytt fordi tittelen minner om noe annet.
    """
    promotert = {i.get("artikkel") for i in innlegg if i.get("artikkel")}
    return [a for a in artikler if a["url"] not in promotert]


def dager_siden_forrige(innlegg, i_dag=None):
    """Dager siden nyeste `publiser_fra` i planen, eller None uten innlegg."""
    datoer = []
    for i in innlegg:
        try:
            datoer.append(datetime.date.fromisoformat(i["publiser_fra"]))
        except (KeyError, ValueError, TypeError):
            continue
    if not datoer:
        return None
    return ((i_dag or datetime.date.today()) - max(datoer)).days


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    artikler = les_artikler(os.path.join(ROT, "assets", "ui.js"))
    innlegg = les_plan(os.path.join(ROT, "promo", "publiseringsplan.json"))
    ikke_promotert = ikke_promoterte_artikler(artikler, innlegg)
    dager = dager_siden_forrige(innlegg)

    if a.json:
        print(json.dumps({
            "dager_siden_forrige_innlegg": dager,
            "ikke_promoterte_artikler": ikke_promotert,
            "antall_artikler_totalt": len(artikler),
            "antall_planlagte_innlegg": len(innlegg),
        }, ensure_ascii=False, indent=2))
        return

    print(f"{len(innlegg)} planlagte innlegg, {len(artikler)} artikler i ARTIKLER.")
    if dager is None:
        print("Ingen tidligere innlegg funnet.")
    else:
        print(f"{dager} dager siden forrige publiser_fra.")
    print()
    if not ikke_promotert:
        print("Alle artikler i ARTIKLER er allerede promotert minst én gang.")
    else:
        print(f"Ikke promotert ({len(ikke_promotert)}):")
        for art in ikke_promotert:
            print(f"  {art['meta']:<28} {art['tittel']}\n    {art['url']}")


if __name__ == "__main__":
    main()
