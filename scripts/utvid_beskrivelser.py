"""
Utvider beskrivelse-feltet i tickers.json til 160-220 ord per aksje.
Kjøres manuelt: python3 scripts/utvid_beskrivelser.py

Leser numerisk data fra aksjer.json og skriver utvidede beskrivelser
tilbake til tickers.json. Berører aksjer med beskrivelse under 150 ord.
Genererer redaksjonell, ikke-repetitiv prosa i tre avsnitt:
  1. Hva selskapet gjør (eksisterende kort beskrivelse)
  2. Utbytteprofil: frekvens, yield, historikk og bærekraft
  3. Investorperspektiv: hva som driver utbyttet og hva man bør følge med på
"""

import json, os

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TICKERS_F = os.path.join(ROOT, "data", "tickers.json")
AKSJER_F  = os.path.join(ROOT, "data", "aksjer.json")

FREQ_MAP = {
    "Kvartalsvis": "kvartalsvis — fire utbetalinger i året",
    "Halvårlig":   "halvårlig — to utbetalinger i året",
    "Månedlig":    "månedlig",
    "Årlig":       "én gang i året",
}

SEKTOR_DRIVER = {
    "Energi":            "Inntjeningen er tett koblet til olje- og gasspriser, noe som gjør utbyttet mer syklisk enn i defensive sektorer.",
    "Finans":            "Rentenivå og kredittap påvirker inntjeningen, mens regulatoriske kapitalkrav setter rammer for hva som kan deles ut.",
    "Havbruk":           "Laksepris og biologisk risiko er de viktigste variablene — gode biologiår kan gi ekstraordinære utbytter.",
    "Shipping":          "Fraktrater varierer kraftig med globalt handelsmønster og flåtekapasitet, og utbyttet svinger tilsvarende.",
    "Eiendom":           "Leieinntekter gir forutsigbar kontantstrøm, men renteendringer påvirker både refinansiering og eiendomsverdier.",
    "Telekommunikasjon": "Stabil abonnementsbase gir forutsigbar kontantstrøm, men høye infrastrukturinvesteringer begrenser utbyttepotensialet.",
    "Industri":          "Ordreinngangen varierer med konjunkturen, men langsiktige kontrakter kan gi god sikt på inntjening.",
    "Fornybar energi":   "Strømprisene og konsesjonsregimet er avgjørende — høye strømpriser gir rom for sjenerøse utbytter.",
    "Sjømat":            "Eksportpriser, biologi og markedsadgang er nøkkelvariabler som kan gi store svingninger i utbyttekapasiteten.",
    "Materialer":        "Råvarepriser og valutakurser driver marginen — selskapet er sensitivt for globale makrotrender.",
    "Helsevern":         "Regulatoriske godkjenninger og produktmiks bestemmer marginen, og utbyttet er relativt stabilt gitt lav syklikalitet.",
    "Forbruksvarer":     "Kjøpekraft og konkurranse fra netthandel påvirker volumet, men stabile merkevarer gir forutsigbar kontantstrøm.",
    "Forsyning":         "Regulerte tariffer gir svært forutsigbar inntjening, men begrenser vekspotensialet i utbyttet.",
}


_AUTO_TEGN = [
    "er notert på", "markedsverdi", "betalt utbytte", "år på rad",
    "utbetales", "direkteavkastning", "5-årssnitt", "plasserer",
    "payout ratio", "utbetalingsgrad", "noe som anses", "noe som gjør",
    "noe som reflekterer", "noe som gir selskapet",
]

def _manuell_del(beskrivelse: str) -> str:
    """Returner bare de opprinnelige (manuelle) setningene — hopp over auto-genererte."""
    import re
    if not beskrivelse:
        return ""
    setninger = re.split(r'(?<=[.!?])\s+', beskrivelse.strip())
    manuell = []
    for s in setninger:
        if any(t in s for t in _AUTO_TEGN):
            break
        manuell.append(s)
    return " ".join(manuell).strip()


def lag_beskrivelse(t: dict, a: dict) -> str:
    kort    = _manuell_del(t.get("beskrivelse") or "")
    navn    = t["navn"]
    ticker  = t["ticker"]
    sektor  = t.get("sektor") or ""
    bors    = t.get("bors") or "Oslo Børs"

    yield_  = a.get("utbytte_yield") or 0
    snitt5  = a.get("snitt_yield_5ar") or 0
    ar_med  = a.get("ar_med_utbytte") or 0
    frekvens = a.get("frekvens") or ""
    payout  = a.get("payout_ratio") or 0
    mrd     = a.get("markedsverdi_mrd") or 0
    vekst   = a.get("utbytte_vekst_5ar")
    valuta  = a.get("valuta") or "NOK"
    hist    = a.get("historiske_utbytter") or []

    avsnitt = []

    # ── Avsnitt 1: hva selskapet gjør + markedsposisjon ──
    if kort:
        if mrd >= 100:
            avsnitt.append(
                f"{kort} Selskapet er notert på {bors} med en markedsverdi "
                f"på rundt {mrd:.0f} milliarder kroner og er ett av de største børsnoterte "
                f"selskapene i Norge."
            )
        elif mrd >= 20:
            avsnitt.append(
                f"{kort} Aksjen er notert på {bors} med en markedsverdi "
                f"på rundt {mrd:.0f} milliarder kroner."
            )
        else:
            avsnitt.append(kort)
    elif mrd > 0:
        avsnitt.append(
            f"{navn} er notert på {bors} med en markedsverdi på rundt {mrd:.0f} milliarder kroner."
        )

    # ── Avsnitt 2: utbytteprofil ──
    deler2 = []
    freq_tekst = FREQ_MAP.get(frekvens, "")
    if freq_tekst and ar_med > 0:
        deler2.append(
            f"Utbyttet utbetales {freq_tekst}, og selskapet har "
            + (f"holdt dette gående i {ar_med} år på rad"
               if ar_med >= 5 else f"betalt utbytte de siste {ar_med} årene") + "."
        )
    elif freq_tekst:
        deler2.append(f"Utbyttet utbetales {freq_tekst}.")

    if yield_ > 0 and snitt5 > 0:
        if yield_ >= 7:
            yield_karakter = "blant de høyest-yielding"
        elif yield_ >= 4:
            yield_karakter = "blant de solid-yielding"
        else:
            yield_karakter = "i det lavere sjiktet"
        deler2.append(
            f"Direkteavkastningen er {yield_:.1f}%, og 5-årsnittet på {snitt5:.1f}% "
            f"plasserer {ticker} {yield_karakter} aksjene i sin sektor."
        )
    elif yield_ > 0:
        deler2.append(f"Direkteavkastningen er {yield_:.1f}%.")

    if payout > 0:
        if payout < 50:
            deler2.append(
                f"Utbetalingsgraden på {payout:.0f}% er lav og gir selskapet "
                f"solid buffer til å opprettholde utbyttet ved svakere kvartaler."
            )
        elif payout < 80:
            deler2.append(
                f"Utbetalingsgraden er {payout:.0f}%, noe som er balansert "
                f"for en moden utbytteaksje."
            )
        else:
            deler2.append(
                f"En utbetalingsgrad på {payout:.0f}% betyr at det meste av inntjeningen "
                f"deles ut — utbyttet er dermed sensitivt for resultatsvingninger."
            )

    if vekst is not None and abs(vekst) > 0.5:
        retning = "vokst" if vekst > 0 else "falt"
        deler2.append(
            f"Utbyttet har {retning} med i snitt {abs(vekst):.1f}% per år de siste fem årene."
        )

    if deler2:
        avsnitt.append(" ".join(deler2))

    # ── Avsnitt 3: hva driver utbyttet ──
    driver = SEKTOR_DRIVER.get(sektor, "")
    if driver:
        if len(hist) >= 3:
            sortert = sorted(hist, key=lambda x: x["ar"])
            max_h = max(sortert, key=lambda x: x["utbytte"])
            min_h = min(sortert, key=lambda x: x["utbytte"])
            if max_h["utbytte"] > min_h["utbytte"] * 1.5:
                svingning = (
                    f" Historikken viser klare svingninger: høyest utbytte var "
                    f"{max_h['utbytte']:.2f} {valuta} per aksje i {max_h['ar']}, "
                    f"lavest {min_h['utbytte']:.2f} {valuta} i {min_h['ar']}."
                )
            else:
                svingning = ""
            avsnitt.append(driver + svingning)
        else:
            avsnitt.append(driver)

    return "\n\n".join(avsnitt)


def main():
    with open(TICKERS_F, encoding="utf-8") as f:
        tickers = json.load(f)

    with open(AKSJER_F, encoding="utf-8") as f:
        raw = json.load(f)
        aksjer_data = {a["ticker"]: a for a in (raw["aksjer"] if isinstance(raw, dict) else raw)}

    endret = 0
    for t in tickers:
        eksist    = (t.get("beskrivelse") or "").strip()
        ord_count = len(eksist.split()) if eksist else 0
        a         = aksjer_data.get(t["ticker"], {})

        if ord_count < 150:
            ny = lag_beskrivelse(t, a)
            ny_ord = len(ny.split())
            t["beskrivelse"] = ny
            endret += 1
            print(f"[{t['ticker']:8}] {ord_count:3} → {ny_ord:3} ord")
        else:
            print(f"[{t['ticker']:8}] {ord_count:3} ord — uendret")

    with open(TICKERS_F, "w", encoding="utf-8") as f:
        json.dump(tickers, f, ensure_ascii=False, indent=2)

    print(f"\nFerdig. {endret} av {len(tickers)} beskrivelser oppdatert i tickers.json.")


if __name__ == "__main__":
    main()
