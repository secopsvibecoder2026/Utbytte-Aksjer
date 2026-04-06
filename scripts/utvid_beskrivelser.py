"""
Utvider beskrivelse-feltet i tickers.json fra ~15 til ~80-120 ord per aksje.
Kjøres én gang: python3 scripts/utvid_beskrivelser.py

Leser numerisk data fra aksjer.json (payout_ratio, snitt_yield_5ar osv.)
og skriver utvidede beskrivelser tilbake til tickers.json.
Berører kun aksjer med beskrivelse under 80 ord.
"""

import json, os

ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKERS_F   = os.path.join(ROOT, "data", "tickers.json")
AKSJER_F    = os.path.join(ROOT, "data", "aksjer.json")

FREQ_MAP = {
    "Kvartalsvis": "kvartalsvis — fire ganger i året",
    "Halvårlig":   "halvårlig — to ganger i året",
    "Årlig":       "én gang i året",
    "Månedlig":    "månedlig",
}

SEKTOR_KONTEKST = {
    "Energi":           "energisektoren",
    "Finans":           "finanssektoren",
    "Havbruk":          "havbrukssektoren",
    "Shipping":         "shippingsektoren",
    "Telekommunikasjon":"telekommunikasjonssektoren",
    "Industri":         "industrisektoren",
    "Forbruksvarer":    "forbruksvarer-sektoren",
    "Eiendom":          "eiendomssektoren",
    "Teknologi":        "teknologisektoren",
    "Helse":            "helsesektoren",
    "Materialer":       "materialersektoren",
    "Sjømat":           "sjømatsektoren",
}


def lag_beskrivelse(t: dict, a: dict) -> str:
    """
    t = rad fra tickers.json  (ticker, navn, sektor, bors, beskrivelse)
    a = rad fra aksjer.json   (numerisk data)
    """
    deler = []

    # 1. Eksisterende kort beskrivelse
    kort = (t.get("beskrivelse") or "").strip()
    if kort:
        deler.append(kort)

    # 2. Markedsposisjon
    mrd  = a.get("markedsverdi_mrd") or 0
    bors = t.get("bors") or "Oslo Børs"
    navn = t["navn"]
    if mrd >= 100:
        deler.append(
            f"{navn} er notert på {bors} med en markedsverdi på rundt "
            f"{mrd:.0f} milliarder NOK, noe som gjør selskapet til ett av "
            "de større børsnoterte selskapene i Norge."
        )
    elif mrd >= 10:
        deler.append(
            f"{navn} er notert på {bors} med en markedsverdi på "
            f"rundt {mrd:.0f} milliarder NOK."
        )
    elif mrd > 0:
        deler.append(f"{navn} er notert på {bors}.")

    # 3. Utbyttehistorikk
    ar_med = a.get("ar_med_utbytte") or 0
    if ar_med >= 15:
        deler.append(
            f"Aksjen har betalt utbytte {ar_med} år på rad, "
            "noe som reflekterer langvarig stabil inntjening og kapitalavkastning til aksjonærene."
        )
    elif ar_med >= 5:
        deler.append(
            f"Selskapet har hatt sammenhengende utbyttebetalinger i {ar_med} år."
        )
    elif ar_med >= 1:
        deler.append(f"Selskapet har betalt utbytte de siste {ar_med} årene.")

    # 4. Utbyttefrekvens
    frekvens   = a.get("frekvens") or ""
    freq_tekst = FREQ_MAP.get(frekvens)
    if freq_tekst:
        deler.append(f"Utbyttet utbetales {freq_tekst}.")

    # 5. Yield-karakteristikk
    snitt5 = a.get("snitt_yield_5ar") or 0
    sektor = t.get("sektor") or ""
    sekt_k = SEKTOR_KONTEKST.get(sektor, f"{sektor.lower()}-sektoren" if sektor else "sektoren")
    ticker = t["ticker"]
    if snitt5 >= 7:
        karakter = "de høyest-yielding"
    elif snitt5 >= 4:
        karakter = "de solid-yielding"
    else:
        karakter = "de mer moderate"
    if snitt5 > 0:
        deler.append(
            f"5-årssnittlig direkteavkastning er {snitt5:.1f}%, "
            f"noe som plasserer {ticker} blant {karakter} aksjene i {sekt_k}."
        )

    # 6. Payout ratio
    payout = a.get("payout_ratio") or 0
    if payout > 0:
        if payout < 50:
            vurd = "noe som gir selskapet godt rom for å øke utbyttet fremover"
        elif payout < 80:
            vurd = "noe som anses som bærekraftig for de fleste markedsforhold"
        else:
            vurd = "noe som kan gjøre utbyttet sårbart ved svakere inntjening"
        deler.append(f"Utbetalingsgraden (payout ratio) er {payout:.0f}%, {vurd}.")

    # Fjern dupliserte setninger før sammenslåing
    sett = set()
    unike = []
    for d in deler:
        if d not in sett:
            sett.add(d)
            unike.append(d)
    return " ".join(unike)


def main():
    with open(TICKERS_F, encoding="utf-8") as f:
        tickers = json.load(f)

    with open(AKSJER_F, encoding="utf-8") as f:
        aksjer_data = {a["ticker"]: a for a in json.load(f)["aksjer"]}

    endret = 0
    for t in tickers:
        eksist    = (t.get("beskrivelse") or "").strip()
        ord_count = len(eksist.split()) if eksist else 0
        a         = aksjer_data.get(t["ticker"], {})

        if ord_count < 80:
            ny = lag_beskrivelse(t, a)
            t["beskrivelse"] = ny
            endret += 1
            print(f"[{t['ticker']:8}] {ord_count} → {len(ny.split())} ord")
        else:
            print(f"[{t['ticker']:8}] {ord_count} ord — uendret")

    with open(TICKERS_F, "w", encoding="utf-8") as f:
        json.dump(tickers, f, ensure_ascii=False, indent=2)

    print(f"\nFerdig. {endret} av {len(tickers)} beskrivelser utvidet i tickers.json.")


if __name__ == "__main__":
    main()
