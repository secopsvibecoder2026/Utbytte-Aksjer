#!/usr/bin/env python3
"""
valider_data.py — Datakvalitetssjekk for data/aksjer.json

Kjøres automatisk etter fetch_stocks.py i GitHub Actions.
Avslutter med kode 1 hvis det finnes kritiske feil (yield-avvik > 2%).
"""

import json
import sys
import os

# Støtter kjøring fra repo-rot eller scripts/-mappen
AKSJER_JSON = os.path.join(os.path.dirname(__file__), '..', 'data', 'aksjer.json')


def valider_data(filsti=AKSJER_JSON):
    """Les aksjer.json og kjør alle datakvalitetssjekker."""
    with open(filsti, encoding='utf-8') as f:
        data = json.load(f)

    aksjer = data.get('aksjer', [])
    advarsler = []
    kritiske_feil = []

    # Feltene kan være null i tillegg til fraværende: fetch_stocks.py setter
    # bevisst snitt_yield_5ar til null når ingen yield er troverdig. dict.get()
    # med standardverdi fanger kun det fraværende tilfellet, så en eksplisitt
    # null ville krasjet sammenligningene under.
    def _tall(kilde, felt, standard=0):
        v = kilde.get(felt)
        return v if isinstance(v, (int, float)) else standard

    for a in aksjer:
        ticker = a.get('ticker', '?')
        pris = _tall(a, 'pris')
        utbytte_per_aksje = _tall(a, 'utbytte_per_aksje')
        utbytte_yield = _tall(a, 'utbytte_yield')
        snitt_yield_5ar = _tall(a, 'snitt_yield_5ar')
        payout_ratio = _tall(a, 'payout_ratio')
        historiske_utbytter = a.get('historiske_utbytter') or []

        # Sjekk 1: utbytte_yield skal stemme overens med utbytte_per_aksje / pris
        if pris > 0 and utbytte_per_aksje > 0:
            beregnet_yield = round(utbytte_per_aksje / pris * 100, 2)
            avvik = abs(beregnet_yield - utbytte_yield)
            if avvik > 2.0:
                feilmelding = (
                    f"KRITISK {ticker}: utbytte_yield={utbytte_yield}% "
                    f"men utbytte_per_aksje/pris={beregnet_yield}% "
                    f"(avvik={avvik:.2f}%)"
                )
                kritiske_feil.append(feilmelding)
            elif avvik > 0.5:
                advarsler.append(
                    f"ADVARSEL {ticker}: yield-avvik={avvik:.2f}% "
                    f"(lagret={utbytte_yield}%, beregnet={beregnet_yield}%)"
                )

        # Sjekk 2: utbytte_yield > 60% er mistenkelig
        if utbytte_yield > 60:
            advarsler.append(
                f"ADVARSEL {ticker}: utbytte_yield={utbytte_yield}% er usannsynlig høy (>60%)"
            )

        # Sjekk 3: snitt_yield_5ar > 200% er mistenkelig
        if snitt_yield_5ar > 200:
            advarsler.append(
                f"ADVARSEL {ticker}: snitt_yield_5ar={snitt_yield_5ar}% er usannsynlig høy (>200%)"
            )

        # Sjekk 4: historiske yields > 200% er mistenkelige
        # yield kan være None når fetch_stocks.py ikke fant et troverdig tall —
        # det er en bevisst markering, ikke et avvik å rapportere.
        for h in historiske_utbytter:
            hist_yield = h.get('yield')
            ar = h.get('ar', '?')
            if hist_yield is not None and hist_yield > 200:
                advarsler.append(
                    f"ADVARSEL {ticker} {ar}: historisk yield={hist_yield}% er usannsynlig høy (>200%)"
                )

        # Sjekk 5: utbytte_per_aksje > 5x siste år i historiske_utbytter (delår-unntak)
        if utbytte_per_aksje > 0 and historiske_utbytter:
            siste_ar = max(historiske_utbytter, key=lambda x: x.get('ar', 0))
            siste_historisk_utbytte = siste_ar.get('utbytte', 0)
            if siste_historisk_utbytte > 0 and utbytte_per_aksje > siste_historisk_utbytte * 5:
                advarsler.append(
                    f"ADVARSEL {ticker}: utbytte_per_aksje={utbytte_per_aksje} "
                    f"er >5x siste historiske år ({siste_ar['ar']}: {siste_historisk_utbytte}) "
                    f"— mulig delår eller feil"
                )

    # Skriv ut rapport
    print("=" * 60)
    print("DATAKVALITETSRAPPORT — aksjer.json")
    print("=" * 60)
    print(f"Antall aksjer kontrollert: {len(aksjer)}")
    print()

    if advarsler:
        print(f"Advarsler ({len(advarsler)}):")
        for a in advarsler:
            print(f"  {a}")
        print()
    else:
        print("Ingen advarsler funnet.")
        print()

    if kritiske_feil:
        print(f"KRITISKE FEIL ({len(kritiske_feil)}):")
        for f in kritiske_feil:
            print(f"  {f}")
        print()
        print("Avslutt med kode 1 — kritiske feil funnet.")
        return False
    else:
        print("Ingen kritiske feil. Datakvalitet OK.")
        return True


if __name__ == '__main__':
    ok = valider_data()
    sys.exit(0 if ok else 1)
