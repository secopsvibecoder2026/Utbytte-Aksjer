"""
Genererer AI-oppsummeringer for alle aksjer basert på talldata.
Brukes for første kjøring uten Claude API-nøkkel.
Erstatt med ekte Claude-kall via ai_oppsummering.py når API-nøkkel er tilgjengelig.
"""

import json
import datetime
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AKSJER_F = os.path.join(ROOT, "data", "aksjer.json")


def _prosent(v, des=1):
    if v is None or v == 0:
        return None
    return round(v, des)


def _tall(v, des=1):
    if v is None:
        return None
    return round(v, des)


def _pe_vurdering(pe):
    if pe is None or pe <= 0:
        return None
    if pe < 8:
        return "svært lavt"
    if pe < 12:
        return "lavt"
    if pe < 18:
        return "moderat"
    if pe < 25:
        return "noe høyt"
    return "høyt"


def _yield_vurdering(y):
    if y is None or y <= 0:
        return None
    if y >= 10:
        return "svært høy"
    if y >= 7:
        return "høy"
    if y >= 4:
        return "solid"
    if y >= 2:
        return "moderat"
    return "lav"


def _payout_vurdering(p):
    if p is None or p <= 0:
        return None
    if p < 40:
        return ("lav utbetalingsgrad", "gir godt rom for fremtidige utbytteøkninger")
    if p < 65:
        return ("moderat utbetalingsgrad", "fremstår bærekraftig")
    if p < 85:
        return ("høy utbetalingsgrad", "er akseptabelt men gir lite buffer")
    return ("svært høy utbetalingsgrad", "er sårbar ved svakere inntjening")


def _historikk_setning(ar_med, vekst_5ar):
    if ar_med and ar_med >= 20:
        return f"Med {ar_med} år sammenhengende utbytte viser selskapet solid kapitaldisiplin over lang tid."
    if ar_med and ar_med >= 10:
        return f"Selskapet har betalt utbytte i {ar_med} år på rad, noe som gir god forutsigbarhet."
    if ar_med and ar_med >= 5:
        return f"Fem eller flere år med sammenhengende utbytte gir et visst historisk grunnlag."
    if ar_med and ar_med >= 1:
        return f"Utbyttehistorikken er kortere ({ar_med} år), noe som krever tettere oppfølging."
    return ""


def _vekst_setning(vekst_5ar):
    if vekst_5ar is None:
        return ""
    if vekst_5ar >= 10:
        return f"Utbyttet har vokst med {vekst_5ar:.1f}% i snitt siste fem år — sterk vekstprofil."
    if vekst_5ar >= 3:
        return f"Moderat utbyttevekst på {vekst_5ar:.1f}% per år styrker realverdien av utbetalingene."
    if vekst_5ar >= 0:
        return ""
    if vekst_5ar < -5:
        return f"Utbyttet har falt med {abs(vekst_5ar):.1f}% per år siste fem år — følg inntjeningsutviklingen nøye."
    return ""


def _52u_setning(pris, hoy, lav):
    if not pris or not hoy or not lav or hoy == lav:
        return ""
    pos = (pris - lav) / (hoy - lav)
    if pos >= 0.85:
        return "Aksjen handles nær 52-ukers topp."
    if pos <= 0.15:
        return "Aksjen handles nær 52-ukers bunn — mulig inngang, men undersøk årsaken."
    return ""


def _frekvens_tekst(f):
    if f == "Kvartalsvis":
        return "kvartalsvis"
    if f == "Halvårlig":
        return "halvårlig"
    if f == "Månedlig":
        return "månedlig"
    return "årlig"


def lag_oppsummering(a: dict) -> str:
    ticker = a.get("ticker", "")
    yield_pst = a.get("utbytte_yield") or a.get("direkteavkastning")
    snitt5 = a.get("snitt_yield_5ar")
    pe = a.get("pe_ratio")
    pb = a.get("pb_ratio")
    payout = a.get("payout_ratio")
    ar_med = a.get("ar_med_utbytte")
    vekst = a.get("utbytte_vekst_5ar")
    frekvens = a.get("frekvens", "Årlig")
    pris = a.get("pris")
    hoy = a.get("52u_hoy")
    lav = a.get("52u_lav")
    dps = a.get("utbytte_per_aksje") or a.get("siste_utbytte")

    deler = []

    # Verdsettelse
    pe_vurd = _pe_vurdering(pe)
    yield_vurd = _yield_vurdering(yield_pst or snitt5)

    if pe_vurd and yield_vurd and yield_pst:
        deler.append(
            f"P/E på {pe:.1f} er {pe_vurd}, og {_prosent(yield_pst)}% direkteavkastning "
            f"klassifiseres som {yield_vurd} i norsk børssammenheng."
        )
    elif yield_pst and yield_vurd:
        deler.append(
            f"Direkteavkastning på {_prosent(yield_pst)}% er {yield_vurd} "
            f"og utbetales {_frekvens_tekst(frekvens)}."
        )
    elif pe_vurd:
        deler.append(f"P/E på {pe:.1f} er {pe_vurd} relativt til Oslo Børs-gjennomsnittet.")

    if pb and 0 < pb < 1.5 and pe_vurd in ("lavt", "svært lavt"):
        deler.append(f"P/B på {pb:.1f} underbygger et attraktivt verdsettelsesnivå.")
    elif pb and pb > 3:
        deler.append(f"P/B på {pb:.1f} reflekterer markedets vekstforventninger.")

    # Payout og bærekraft
    p_vurd = _payout_vurdering(payout)
    if p_vurd:
        label, vurdering = p_vurd
        deler.append(f"{label.capitalize()} på {payout:.0f}% {vurdering}.")

    # Historikk og vekst
    hist = _historikk_setning(ar_med, vekst)
    if hist:
        deler.append(hist)

    vekst_s = _vekst_setning(vekst)
    if vekst_s:
        deler.append(vekst_s)

    # 52-ukers kurs
    kurs_s = _52u_setning(pris, hoy, lav)
    if kurs_s:
        deler.append(kurs_s)

    # Egnethet
    if yield_pst and yield_pst >= 5 and ar_med and ar_med >= 5 and payout and payout < 80:
        deler.append(
            f"{ticker} fremstår som et solid valg for utbytteinvestorer som søker "
            "kombinasjonen av inntekt og historisk stabilitet."
        )
    elif yield_pst and yield_pst >= 3 and payout and payout < 70:
        deler.append(
            f"{ticker} kan passe for utbytteinvestorer med moderat risikotoleranse."
        )
    elif payout and payout > 90:
        deler.append(
            f"Utbyttet bør følges nøye — høy payout ratio gir liten sikkerhetsmargin."
        )
    elif not yield_pst or yield_pst < 2:
        deler.append(
            f"Lav eller fraværende direkteavkastning gjør {ticker} mindre relevant for "
            "rendyrkede utbyttestrategier."
        )

    return " ".join(deler) if deler else (
        f"{ticker} mangler tilstrekkelig tallgrunnlag for en fullstendig vurdering. "
        "Følg med på neste kvartalsrapport."
    )


def main():
    with open(AKSJER_F, encoding="utf-8") as f:
        data = json.load(f)

    aksjer = data["aksjer"] if isinstance(data, dict) else data
    i_dag = datetime.date.today().isoformat()

    for a in aksjer:
        tekst = lag_oppsummering(a)
        a["ai_oppsummering"] = tekst
        a["ai_oppsummering_dato"] = i_dag

    if isinstance(data, dict):
        data["aksjer"] = aksjer

    with open(AKSJER_F, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Ferdig. {len(aksjer)} AI-oppsummeringer generert.")


if __name__ == "__main__":
    main()
