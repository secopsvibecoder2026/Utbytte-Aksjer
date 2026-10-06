#!/usr/bin/env python3
"""Sjekker de håndskrevne innledningene i tickers.json.

Innledningen er den eneste redaksjonelle teksten på en aksjeside. Den lagres
som hele `beskrivelse` i tickers.json — avsnitt 2 og 3 bygges på nytt av
lag_beskrivelse() ved hver kjøring, så ingenting annet hører hjemme i feltet.

To krav, begge lette å bryte uten at noe varsler:

  1. Ingen frase fra _AUTO_TEGN. _manuell_del() kutter teksten ved første
     treff, så en innledning som inneholder «noe som gjør» mister alt etter
     det punktet — stille. Listen inneholder helt vanlige norske
     konstruksjoner, så dette er ikke en teoretisk fare.
  2. Ingen tall som kan drifte: yield, utbetalingsgrad, markedsverdi,
     årstelling. Faste historiske årstall er greit. DNBs innledning lovet
     «ofte over 7% yield» mens setningen under viste 5,6 %.

Et tredje krav kom 2026-10-06: språket. Teksten måles med sjekk_sprak.py
mot SKRIVESTIL.md (tankestreker og maskinvendinger). Da ble også lengden
hevet: innledningen er den eneste teksten på aksjesiden som er skrevet for
akkurat det selskapet, og 90–130 ord var for lite til å bære siden.

Kjør:
    python3 scripts/valider_innledning.py                 # sjekk alle
    python3 scripts/valider_innledning.py --korte         # list dem under målet
    python3 scripts/valider_innledning.py --ko [N]        # neste N å skrive om
    python3 scripts/valider_innledning.py --ticker EQNR DNB   # bare disse
    python3 scripts/valider_innledning.py --skriv EQNR tekst.txt  # lagre ny tekst
    python3 scripts/valider_innledning.py --streng        # exit 1 ved funn
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from utvid_beskrivelser import _AUTO_TEGN, _manuell_del, SEKTOR_DRIVER
import sjekk_sprak

TICKERS_F = os.path.join(ROOT, "data", "tickers.json")
AKSJER_F = os.path.join(ROOT, "data", "aksjer.json")

# Hevet fra 90–180 (2026-10-06). Selskapsteksten er den eneste prosaen på
# aksjesiden som bare finnes der, så den bærer mye av sidens egenverdi. Over
# rundt 280 ord blir den en vegg i appens modal på mobil.
MAAL_MIN, MAAL_MAKS = 180, 280

# Samme seksordsfrase i så mange tekster leses som mal, ikke som skrevet.
FRASE_ORD, FRASE_GRENSE = 6, 4

# Tall som flytter seg. Årstall står igjen med vilje — «stiftet i 1965» og
# «tok navnet i 2017» er faste fakta og skal kunne stå i teksten.
_DRIFTENDE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|prosent|milliard|million|kroner|NOK|kr\b)"
    r"|\b\d+\s*(?:år på rad|år med utbytte|sammenhengende år)\b",
    re.IGNORECASE,
)


def valider_tekst(tekst: str, sektor: str = "") -> list:
    """Feil i en *ferdigskrevet* innledning. Tom liste betyr i orden.

    Teksten som sendes inn skal være innledningen alene. Sender du hele
    `beskrivelse`-feltet for en aksje som ennå ikke er skrevet om, vil de
    frosne genererte avsnittene naturligvis slå ut på alt her — bruk
    _manuell_del() først, slik main() gjør.
    """
    feil = []
    if not tekst.strip():
        return ["tom"]

    for tag in _AUTO_TEGN:
        if tag in tekst.lower():
            feil.append(f"inneholder _AUTO_TEGN «{tag}» — teksten ville blitt kuttet der")

    for m in _DRIFTENDE.findall(tekst):
        feil.append(f"tall som drifter: «{m.strip()}»")

    # Rundtur: overlever teksten _manuell_del() uendret? Fanger også
    # tilfeller der en frase over ikke sto i listen, men i SEKTOR_DRIVER.
    tilbake = _manuell_del(tekst, SEKTOR_DRIVER.get(sektor, ""))
    if tilbake.strip() != tekst.strip():
        tapt = len(tekst.split()) - len(tilbake.split())
        feil.append(f"_manuell_del() kutter {tapt} ord")

    return feil


def sprakfeil(tekst: str) -> list:
    """Brudd på SKRIVESTIL.md, målt av sjekk_sprak.py. Tom liste betyr i orden."""
    funn = sjekk_sprak.vurder(sjekk_sprak.avsnitt_fra_tekst(tekst))
    feil = []
    if funn["streker"] > funn["maks"]:
        feil.append(f"{funn['streker']} tankestreker (grense {funn['maks']} for {funn['ord']} ord)")
    elif funn["tette"]:
        feil.append("to tankestreker i samme avsnitt")
    for v in funn["vendinger"]:
        feil.append(f"maskinvending «{v}»")
    return feil


def _ordliste(tekst: str, navn: str) -> list:
    t = tekst.lower()
    for del_ in sorted(navn.lower().split(), key=len, reverse=True):
        if len(del_) > 2:
            t = t.replace(del_, " NAVN ")
    return re.findall(r"[a-zæøåé]+|NAVN", t)


def gjentatte_fraser(tekster: dict) -> dict:
    """{ticker: [frase, …]} for seksordsfraser som går igjen i mange tekster.

    Selskapsnavnet maskeres, så «DNB er den ledende banken i» og «SpareBank 1
    Østlandet er den ledende banken i» regnes som samme frase. En frase i
    FRASE_GRENSE tekster eller flere er en malsetning, og sider som deler
    malsetninger er det AdSense avviste siden for.
    """
    forekomst = {}
    for tick, (tekst, navn) in tekster.items():
        o = _ordliste(tekst, navn)
        for f in {" ".join(o[i:i + FRASE_ORD]) for i in range(len(o) - FRASE_ORD + 1)}:
            forekomst.setdefault(f, set()).add(tick)
    ut = {}
    for f, ticks in forekomst.items():
        if len(ticks) >= FRASE_GRENSE:
            for tick in ticks:
                ut.setdefault(tick, []).append(f)
    return ut


def _markedsverdi():
    try:
        with open(AKSJER_F, encoding="utf-8") as f:
            return {a["ticker"]: a.get("markedsverdi_mrd") or 0 for a in json.load(f)["aksjer"]}
    except (OSError, ValueError, KeyError):
        return {}


def arbeidsko(tickere: list, mv: dict) -> list:
    """Aksjene som gjenstår, i rekkefølgen de bør skrives om.

    Først de som bryter skrivestilen, deretter de som er for korte. Innenfor
    hver gruppe de største selskapene først: de blir søkt på mest, så en
    bedre tekst der gir mest igjen.
    """
    ko = []
    for t in tickere:
        intro = _manuell_del(t.get("beskrivelse", "") or "", SEKTOR_DRIVER.get(t.get("sektor") or "", ""))
        n = len(intro.split())
        sprak = sprakfeil(intro)
        if not sprak and MAAL_MIN <= n <= MAAL_MAKS:
            continue
        ko.append((0 if sprak else 1, -mv.get(t["ticker"], 0), t["ticker"], n, sprak))
    ko.sort()
    return [(tick, n, sprak) for _, _, tick, n, sprak in ko]


def normaliser(tekst: str) -> str:
    """Avsnitt skilles med én blank linje; linjeskift inni et avsnitt blir mellomrom."""
    avsnitt = [re.sub(r"\s+", " ", a).strip() for a in re.split(r"\n\s*\n", tekst.strip())]
    return "\n\n".join(a for a in avsnitt if a)


def vurder_ny(ticker: str, tekst: str, tickere: list) -> list:
    """Alle krav til en ny selskapstekst. Tom liste betyr at den kan lagres."""
    rad = next((t for t in tickere if t["ticker"] == ticker), None)
    if rad is None:
        return [f"ukjent ticker {ticker}"]
    sektor = rad.get("sektor") or ""
    feil = valider_tekst(tekst, sektor) + sprakfeil(tekst)
    n = len(tekst.split())
    if not MAAL_MIN <= n <= MAAL_MAKS:
        feil.append(f"{n} ord, målet er {MAAL_MIN}–{MAAL_MAKS}")
    alle = {t["ticker"]: (_manuell_del(t.get("beskrivelse", "") or "",
                                       SEKTOR_DRIVER.get(t.get("sektor") or "", "")), t.get("navn", ""))
            for t in tickere}
    alle[ticker] = (tekst, rad.get("navn", ""))
    for fr in gjentatte_fraser(alle).get(ticker, [])[:3]:
        feil.append(f"frasen «{fr}» står i {FRASE_GRENSE} eller flere tekster")
    return feil


def skriv(ticker: str, tekst: str, sti: str = TICKERS_F) -> list:
    """Lagrer teksten som `beskrivelse` i tickers.json hvis den består alle krav.

    Returnerer feilene; da er ingenting skrevet. Formatet på filen beholdes
    (indent 2, ikke-ASCII som det er, linjeskift til slutt), så diffen bare
    viser den ene teksten.
    """
    with open(sti, encoding="utf-8") as f:
        tickere = json.load(f)
    tekst = normaliser(tekst)
    feil = vurder_ny(ticker, tekst, tickere)
    if feil:
        return feil
    for t in tickere:
        if t["ticker"] == ticker:
            t["beskrivelse"] = tekst
    with open(sti, "w", encoding="utf-8") as f:
        f.write(json.dumps(tickere, indent=2, ensure_ascii=False) + "\n")
    return []


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    streng = "--streng" in argv
    vis_korte = "--korte" in argv
    valgte = []
    if "--ticker" in argv:
        valgte = [a.upper() for a in argv[argv.index("--ticker") + 1:] if not a.startswith("--")]

    if "--skriv" in argv:
        i = argv.index("--skriv")
        ticker, fil = argv[i + 1].upper(), argv[i + 2]
        with open(fil, encoding="utf-8") as f:
            feil = skriv(ticker, f.read())
        if feil:
            print(f"IKKE LAGRET {ticker}:")
            for f_ in feil:
                print(f"        {f_}")
            return 1
        print(f"Lagret {ticker} i data/tickers.json")
        return 0

    with open(TICKERS_F, encoding="utf-8") as f:
        tickere = json.load(f)

    if "--ko" in argv:
        i = argv.index("--ko")
        antall = int(argv[i + 1]) if i + 1 < len(argv) and argv[i + 1].isdigit() else 10
        ko = arbeidsko(tickere, _markedsverdi())
        print(f"{len(ko)} selskapstekster gjenstår. De neste {min(antall, len(ko))}:")
        for tick, n, sprak in ko[:antall]:
            grunn = "; ".join(sprak) if sprak else f"{n} ord (mål {MAAL_MIN}–{MAAL_MAKS})"
            print(f"  {tick:8} {grunn}")
        return 0

    alle = {t["ticker"]: (_manuell_del(t.get("beskrivelse", "") or "",
                                       SEKTOR_DRIVER.get(t.get("sektor") or "", "")), t.get("navn", ""))
            for t in tickere}
    fraser = gjentatte_fraser(alle)
    if valgte:
        ukjente = [v for v in valgte if v not in alle]
        if ukjente:
            print(f"Ukjent ticker: {', '.join(ukjente)}")
            return 1
        tickere = [t for t in tickere if t["ticker"] in valgte]

    feilende, korte, urenset = {}, [], []
    for t in tickere:
        raa = t.get("beskrivelse", "") or ""
        sektor = t.get("sektor") or ""
        intro = alle[t["ticker"]][0]

        feil = valider_tekst(intro, sektor) + sprakfeil(intro)
        if valgte:
            # Lengde og gjentatte fraser er krav til en ny tekst, ikke til de
            # gamle — derfor bare når tickeren er valgt, slik agenten gjør.
            n_ = len(intro.split())
            if not MAAL_MIN <= n_ <= MAAL_MAKS:
                feil.append(f"{n_} ord, målet er {MAAL_MIN}–{MAAL_MAKS}")
            for fr in fraser.get(t["ticker"], [])[:3]:
                feil.append(f"frasen «{fr}» står i {FRASE_GRENSE} eller flere tekster")
        if feil:
            feilende[t["ticker"]] = feil

        n = len(intro.split())
        if n < MAAL_MIN:
            korte.append((n, t["ticker"], sektor))

        # Feltet skal inneholde innledningen alene. Ligger det frossen
        # generert prosa der fra en gammel kjøring av utvid_beskrivelser.py,
        # er aksjen ikke skrevet om ennå.
        if intro.strip() != raa.strip():
            urenset.append(t["ticker"])

    for tick, feil in sorted(feilende.items()):
        print(f"  FEIL {tick}:")
        for f_ in feil:
            print(f"        {f_}")

    if valgte:
        for t in tickere:
            if t["ticker"] not in feilende:
                print(f"  OK   {t['ticker']}: {len(alle[t['ticker']][0].split())} ord")
        return 1 if (streng and feilende) else 0

    skrevet = len(tickere) - len(korte)
    print(f"\n{len(tickere)} aksjer: {skrevet} med utskrevet innledning "
          f"(≥ {MAAL_MIN} ord), {len(korte)} igjen, {len(feilende)} med feil.")
    if urenset:
        print(f"{len(urenset)} har fortsatt frossen generert prosa i feltet "
              f"— de er ikke skrevet om ennå.")

    if vis_korte:
        print(f"\nUnder {MAAL_MIN} ord — gjenstår å skrive:")
        for n, tick, sektor in sorted(korte):
            print(f"  {n:4} ord  {tick:8} {sektor}")

    return 1 if (streng and feilende) else 0


if __name__ == "__main__":
    sys.exit(main())
