"""
Akkumulerer rapport-datoer i data/hendelser.json.
Legger til nye (ticker, dato)-par — sletter aldri eksisterende.
Kjøres etter fetch_stocks.py i GitHub Actions.

Kjør: python3 scripts/oppdater_hendelser.py
"""

import json, os, datetime

ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AKSJER_F    = os.path.join(ROOT, "data", "aksjer.json")
HENDELSER_F = os.path.join(ROOT, "data", "hendelser.json")


def main():
    with open(AKSJER_F, encoding="utf-8") as f:
        aksjer = json.load(f)["aksjer"]

    # Les eksisterende hendelser
    if os.path.exists(HENDELSER_F):
        with open(HENDELSER_F, encoding="utf-8") as f:
            data = json.load(f)
        hendelser = data.get("hendelser", [])
    else:
        hendelser = []

    eksisterende = {(h["ticker"], h["dato"]) for h in hendelser}
    lagt_til = 0

    for a in aksjer:
        rd = a.get("rapport_dato")
        if not rd:
            continue
        key = (a["ticker"], rd)
        if key not in eksisterende:
            hendelser.append({"ticker": a["ticker"], "dato": rd, "type": "rapport"})
            eksisterende.add(key)
            lagt_til += 1

    hendelser.sort(key=lambda x: (x["dato"], x["ticker"]))

    with open(HENDELSER_F, "w", encoding="utf-8") as f:
        json.dump(
            {"hendelser": hendelser, "sist_oppdatert": datetime.date.today().isoformat()},
            f, ensure_ascii=False, indent=2
        )

    print(f"hendelser.json: {len(hendelser)} totalt, {lagt_til} nye lagt til")


if __name__ == "__main__":
    main()
