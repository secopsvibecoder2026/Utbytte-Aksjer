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
from fetch_stocks import (generer_aksjesider, generer_sektorsider, generer_topplistesider,
                          generer_sitemap, _last_kurshistorikk_fra_disk,
                          oppdater_app_noscript_liste, lag_beskrivelse)

def main():
    with open(TICKERS_F, encoding="utf-8") as f:
        ticker_data = json.load(f)
        beskrivelser      = {t["ticker"]: t.get("beskrivelse", "") for t in ticker_data}
        beskrivelse_fakta = {t["ticker"]: t.get("beskrivelse_fakta", "") for t in ticker_data}
        ask_egnet_map     = {t["ticker"]: t.get("ask_egnet", True) for t in ticker_data}
        inkorp_map        = {t["ticker"]: t.get("inkorporeringsland", "Norge") for t in ticker_data}
        navn_map          = {t["ticker"]: t.get("navn", "") for t in ticker_data}
        sektor_map        = {t["ticker"]: t.get("sektor", "") for t in ticker_data}

    with open(AKSJER_F, encoding="utf-8") as f:
        data = json.load(f)

    oppdatert = 0
    for a in data["aksjer"]:
        # Navn og sektor er manuelt vedlikeholdt i tickers.json, men ble ikke
        # synket hit. Retter man en feilregistrert ticker — AFG sto som
        # «Arendals Fossekompani ASA» i sektor Fornybar energi, men er AF
        # Gruppen ASA i Industri — slo rettelsen ikke gjennom før neste fulle
        # fetch_stocks.py-kjøring. Beskrivelsen under bygges dessuten av
        # sektoren, så den må være riktig før lag_beskrivelse() kalles.
        nytt_navn   = navn_map.get(a["ticker"])
        ny_sektor   = sektor_map.get(a["ticker"])
        if nytt_navn and nytt_navn != a.get("navn"):
            print(f"  {a['ticker']}: navn «{a.get('navn')}» → «{nytt_navn}»")
            a["navn"] = nytt_navn
            oppdatert += 1
        if ny_sektor and ny_sektor != a.get("sektor"):
            print(f"  {a['ticker']}: sektor «{a.get('sektor')}» → «{ny_sektor}»")
            a["sektor"] = ny_sektor
            oppdatert += 1

        # Teksten i tickers.json er en mal der kun innledningsavsnittet er
        # manuelt forfattet — utbytteprofil- og driver-avsnittene bygges på
        # nytt her, akkurat som i fetch_stocks.py sin hent_aksje(). Kopierer
        # vi råteksten fra tickers.json rett inn uten dette, fryser både
        # årstellingen (DNB gikk fra 21 til 20 år, Orkla 27 til 26 på 89
        # aksjer) og nøkkeltall som yield/payout/historisk høyest-lavest til
        # hva de var da tickers.json sist ble skrevet.
        ny_besk = lag_beskrivelse(
            {"ticker": a["ticker"], "navn": a["navn"], "sektor": a["sektor"],
             "bors": a["bors"], "beskrivelse": beskrivelser.get(a["ticker"], "")},
            a,
        )
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

    # Kurshistorikken ligger i data/kurs/{TICKER}.json, ikke i aksjer.json.
    # Sidegenereringen tegner kursgrafen som SVG og trenger dataene i minnet —
    # uten dette ville alle aksjesider blitt regenerert uten graf.
    # Lastes etter at aksjer.json er skrevet over, så feltet ikke havner der.
    kurs_dir = os.path.join(ROOT, "data", "kurs")
    for a in aksjer:
        a["kurs_historikk"] = _last_kurshistorikk_fra_disk(a["ticker"], kurs_dir)
    med_graf = sum(1 for a in aksjer if a["kurs_historikk"])
    print(f"Kurshistorikk lastet for {med_graf}/{len(aksjer)} aksjer")

    generer_aksjesider(aksjer, ROOT)
    print("Aksjesider regenerert")

    generer_sektorsider(aksjer, ROOT)
    print("Sektorsider regenerert")

    generer_topplistesider(aksjer, ROOT)
    print("Topplistesider regenerert")

    generer_sitemap(aksjer, ROOT, today)
    print("Sitemap oppdatert")

    oppdater_app_noscript_liste(aksjer, ROOT)

    print("\nFerdig!")

if __name__ == "__main__":
    main()
