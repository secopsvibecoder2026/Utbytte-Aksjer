"""
Oppdaterer beskrivelse i aksjer.json fra tickers.json og regenererer alle HTML-sider.
Brukes når tickers.json er endret men man vil unngå full Yahoo Finance-henting.

Kjør: python3 scripts/regenerer_sider.py
"""

import json, os, sys, datetime

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKERS_F = os.path.join(ROOT, "data", "tickers.json")
AKSJER_F  = os.path.join(ROOT, "data", "aksjer.json")

# Importer genererings-funksjonene fra fetch_stocks
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_stocks import generer_aksjesider, generer_sektorsider, generer_topplistesider, generer_sitemap

def main():
    with open(TICKERS_F, encoding="utf-8") as f:
        ticker_data = json.load(f)
        beskrivelser      = {t["ticker"]: t.get("beskrivelse", "") for t in ticker_data}
        beskrivelse_fakta = {t["ticker"]: t.get("beskrivelse_fakta", "") for t in ticker_data}
        ask_egnet_map     = {t["ticker"]: t.get("ask_egnet", True) for t in ticker_data}
        inkorp_map        = {t["ticker"]: t.get("inkorporeringsland", "Norge") for t in ticker_data}

    with open(AKSJER_F, encoding="utf-8") as f:
        data = json.load(f)

    oppdatert = 0
    for a in data["aksjer"]:
        ny_besk = beskrivelser.get(a["ticker"], "")
        if ny_besk and ny_besk != a.get("beskrivelse", ""):
            a["beskrivelse"] = ny_besk
            oppdatert += 1
        ny_fakta = beskrivelse_fakta.get(a["ticker"], "")
        if ny_fakta and ny_fakta != a.get("beskrivelse_fakta", ""):
            a["beskrivelse_fakta"] = ny_fakta
            oppdatert += 1
        a["ask_egnet"] = ask_egnet_map.get(a["ticker"], True)
        a["inkorporeringsland"] = inkorp_map.get(a["ticker"], "Norge")

    with open(AKSJER_F, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"aksjer.json oppdatert: {oppdatert} beskrivelser endret")

    today  = datetime.date.today().isoformat()
    aksjer = data["aksjer"]

    generer_aksjesider(aksjer, ROOT)
    print("Aksjesider regenerert")

    generer_sektorsider(aksjer, ROOT)
    print("Sektorsider regenerert")

    generer_topplistesider(aksjer, ROOT)
    print("Topplistesider regenerert")

    generer_sitemap(aksjer, ROOT, today)
    print("Sitemap oppdatert")

    print("\nFerdig!")

if __name__ == "__main__":
    main()
