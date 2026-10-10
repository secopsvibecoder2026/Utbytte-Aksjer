#!/usr/bin/env python3
"""
tallkontroll.py — sammenligner tallene vi viser med Yahoos rådata.

Brukes av agenten `.claude/agents/tallkontroll.md`, men kan kjøres for hånd:

    python scripts/tallkontroll.py                 # hele katalogen
    python scripts/tallkontroll.py DNB EQNR        # utvalgte tickere
    python scripts/tallkontroll.py --json          # maskinlesbart
    python scripts/tallkontroll.py --meldinger WAWI  # utbyttemeldinger fra NewsWeb
    python scripts/tallkontroll.py --sideutvalg      # ukens sider til sidelesing
    python scripts/tallkontroll.py --sidetekst DNB   # aksjesiden som ren tekst

Leser bare. Skriver aldri til data/ eller sidene.

Hvorfor et eget skript når valider_data.py finnes: valider_data sammenligner
feltene i aksjer.json med *hverandre* og kjører uten nett. Det fanger ikke et
tall som er internt konsistent og likevel feil — kursgrafen var
utbyttejustert på alle 155 sider uten at noen sjekk reagerte, fordi ingen
sjekk så på en kilde utenfor vår egen fil. Dette skriptet henter kildene.

Én begrensning skal stå tydelig: utbyttebeløpene sammenlignes med Yahoo, og
det er Yahoo vi henter fra. Et avvik der betyr at *pipelinen* har endret eller
foreldet tallet — ikke at Yahoo har rett. Fasit for utbytte er selskapets
egen melding til Oslo Børs; `--meldinger` henter den, og agenten leser den.
"""
import argparse
import datetime
import html
import json
import math
import os
import re
import statistics
import sys
import time

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)

# Toleranser. Satt slik at avrunding og en dags forsinkelse ikke gir støy,
# men en justert kurs (typisk 5–40 % lavere bakover) alltid slår ut.
KURS_TOLERANSE = 0.05          # siste kurs mot siste handelsdag
KURSGRAF_TOLERANSE = 0.03      # eldste punkt i grafen mot ujustert kurs
BELOP_TOLERANSE = 0.01         # utbyttebeløp: 1 %
FREKVENS_INTERVALL = {         # median dager mellom utbetalinger
    "Månedlig": (20, 45),
    "Kvartalsvis": (60, 125),
    "Halvårlig": (140, 230),
    "Årlig": (300, 430),
}


# ── Rene sammenligninger (testbare uten nett) ────────────────────────────────
# Rådata sendes inn som lister av (iso-dato, verdi), sortert stigende.

def _avvik(vist, kilde):
    if not kilde:
        return None
    return (vist - kilde) / kilde


def sjekk_kurs(vist_pris, raa_kurs):
    """Vist kurs mot siste ujusterte sluttkurs."""
    if not vist_pris or not raa_kurs:
        return None
    dato, siste = raa_kurs[-1]
    a = _avvik(vist_pris, siste)
    if a is not None and abs(a) > KURS_TOLERANSE:
        return {"sjekk": "kurs", "vist": vist_pris, "kilde": round(siste, 2),
                "kildedato": dato, "avvik_pst": round(a * 100, 1), "alvor": "kritisk"}
    return None


def sjekk_kursgraf(kurs_historikk, raa_kurs):
    """Er grafen utbyttejustert? Eldste punkt mot ujustert kurs samme uke.

    Grafpunktene er ukeslutt (søndag), så vi sammenligner med siste
    handelsdag på eller før den datoen.
    """
    if not kurs_historikk or not raa_kurs:
        return None
    punkt = kurs_historikk[0]
    d, k = punkt.get("d"), punkt.get("k")
    kandidater = [(dd, v) for dd, v in raa_kurs if dd <= d]
    if not kandidater or not k:
        return None
    kdato, kverdi = kandidater[-1]
    a = _avvik(k, kverdi)
    if a is not None and abs(a) > KURSGRAF_TOLERANSE:
        return {"sjekk": "kursgraf_justert", "vist": k, "vistdato": d,
                "kilde": round(kverdi, 2), "kildedato": kdato,
                "avvik_pst": round(a * 100, 1), "alvor": "kritisk"}
    return None


def sum_siste_12m(utbytter, i_dag):
    grense = (i_dag - datetime.timedelta(days=365)).isoformat()
    rader = [(d, v) for d, v in utbytter if grense < d <= i_dag.isoformat()]
    return round(sum(v for _, v in rader), 4), len(rader)


def sjekk_betalt_12m(rad, utbytter, i_dag):
    """utbytte_12m i aksjer.json mot summen av rådata siste 365 dager."""
    if "utbytte_12m" not in rad:
        return None
    kilde, antall = sum_siste_12m(utbytter, i_dag)
    vist = float(rad.get("utbytte_12m") or 0)
    if kilde == 0 and vist == 0:
        return None
    if kilde == 0 or abs(vist - kilde) / kilde > BELOP_TOLERANSE:
        return {"sjekk": "betalt_12m", "vist": vist, "kilde": kilde,
                "kilde_antall": antall, "alvor": "advarsel",
                "merknad": "pipelinen avviker fra rådata — foreldet eller omregnet"}
    return None


def sjekk_siste_utbytte(rad, utbytter):
    if not utbytter or not rad.get("siste_utbytte"):
        return None
    dato, kilde = utbytter[-1]
    vist = float(rad["siste_utbytte"])
    if abs(vist - kilde) / kilde > BELOP_TOLERANSE:
        return {"sjekk": "siste_utbytte", "vist": vist, "kilde": round(kilde, 4),
                "kildedato": dato, "alvor": "advarsel"}
    return None


def sjekk_yield_mot_betalt(rad, pris, i_dag, utbytter):
    """Vist direkteavkastning mot det som faktisk ble betalt siste 12 mnd.

    Begge retninger rapporteres, men bare *over* betalt er et varsel: under
    betalt skyldes som regel et engangsutbytte i vinduet, og det er riktig å
    ikke vise det som årlig.
    """
    vist = float(rad.get("utbytte_yield") or 0)
    if not pris:
        return None
    betalt, antall = sum_siste_12m(utbytter, i_dag)
    betalt_yield = betalt / pris * 100
    if vist >= betalt_yield + 1.0 and vist >= betalt_yield * 1.3:
        return {"sjekk": "yield_over_betalt", "vist": round(vist, 2),
                "kilde": round(betalt_yield, 2), "kilde_antall": antall,
                "alvor": "advarsel"}
    return None


def median_intervall(utbytter, antall=6):
    datoer = [datetime.date.fromisoformat(d) for d, _ in utbytter[-antall:]]
    if len(datoer) < 3:
        return None
    return statistics.median((b - a).days for a, b in zip(datoer, datoer[1:]))


def sjekk_frekvens(rad, utbytter):
    """Vist frekvens mot median intervall — intervaller, ikke telling (SATS)."""
    frekvens = rad.get("frekvens")
    if frekvens not in FREKVENS_INTERVALL:
        return None
    m = median_intervall(utbytter)
    if m is None:
        return None
    lav, hoy = FREKVENS_INTERVALL[frekvens]
    if not lav <= m <= hoy:
        return {"sjekk": "frekvens", "vist": frekvens, "kilde": f"median {m} dager",
                "alvor": "advarsel"}
    return None


def sjekk_ex_dato(rad, newsweb):
    """Vist ex-dato mot Oslo Børs' egen melding (om vi har en)."""
    if not newsweb or not newsweb.get("ex_dato"):
        return None
    if rad.get("ex_dato") != newsweb["ex_dato"]:
        return {"sjekk": "ex_dato", "vist": rad.get("ex_dato"),
                "kilde": newsweb["ex_dato"], "alvor": "kritisk",
                "merknad": "fasit er meldingen til Oslo Børs"}
    return None


def kontroller(rad, pris, kurs_historikk, raa_kurs, utbytter, i_dag, newsweb=None):
    """Alle sjekker for én aksje. Returnerer liste med avvik."""
    funn = [
        sjekk_kurs(pris, raa_kurs),
        sjekk_kursgraf(kurs_historikk, raa_kurs),
        sjekk_betalt_12m(rad, utbytter, i_dag),
        sjekk_siste_utbytte(rad, utbytter),
        sjekk_yield_mot_betalt(rad, pris, i_dag, utbytter),
        sjekk_frekvens(rad, utbytter),
        sjekk_ex_dato(rad, newsweb),
    ]
    return [f for f in funn if f]


# ── Henting (nett) ───────────────────────────────────────────────────────────

def _les_json(sti, standard):
    try:
        with open(sti, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return standard


def hent_raadata(ticker_yf):
    """Ujustert kurs og utbytter fra Yahoo, som (iso-dato, verdi)-lister."""
    import yfinance as yf
    t = yf.Ticker(ticker_yf)
    hist = t.history(period="5y", auto_adjust=False, actions=True)
    if hist is None or hist.empty:
        return [], []
    kurs = [(str(i.date()), float(v)) for i, v in hist["Close"].dropna().items()]
    utb = []
    if "Dividends" in hist.columns:
        utb = [(str(i.date()), float(v)) for i, v in hist["Dividends"].items() if v and v > 0]
    return kurs, utb


_UTBYTTEORD = ("dividend", "distribution", "utbytte", "utdeling")


def utbyttemeldinger(ticker, maks=8):
    """Tekst fra de nyeste «Key information … dividend»-meldingene på NewsWeb.

    Taket var 3. Equinor melder på norsk og engelsk, og et utbytte har ofte
    både en kunngjøring og en «Key information»-melding, så tre meldinger
    rakk bare én utbytterunde. Tallkontrollen 05.10.2026 fikk derfor EQNRs
    ex-dato 13. november som «uavklart», enda melding 678527 sa det rett ut.
    """
    import fetch_stocks as fs
    if fs._NEWSWEB_API is None:
        fs._NEWSWEB_API = fs._newsweb_api_base()
    ut = []
    for msg in fs._newsweb_meldinger(ticker):
        tittel = (msg.get("title") or "")
        # «distribution» (ENH) og norske titler (SB68, SOAG) ble oversett da
        # filteret bare så etter «dividend» — funnet av agenten selv.
        if not any(o in tittel.lower() for o in _UTBYTTEORD):
            continue
        full = fs._newsweb_get(
            f"{fs._NEWSWEB_API}/v1/newsreader/message?messageId={msg.get('messageId')}")
        body = full.get("data", {}).get("message", {}).get("body", "")
        tekst = html.unescape(re.sub(r"<[^>]+>", "\n", body))
        tekst = re.sub(r"\n\s*\n+", "\n", tekst).strip()
        ut.append({"tittel": tittel, "publisert": (msg.get("publishedTime") or "")[:10],
                   "id": msg.get("messageId"), "tekst": tekst[:3000]})
        if len(ut) >= maks:
            break
    return ut


# ── Sidelesing (2026-10-09) ──────────────────────────────────────────────────
# Tallsjekkene over sammenligner felt mot kilder. De ser ikke at en side sier
# to ting som ikke kan være sanne samtidig: 2020 Bulkers fikk «8 år på rad …
# konsistent kapitalavkastningspolitikk» og «god buffer» om et selskap som
# hadde solgt hele virksomheten, og alle 14 Growth-aksjene sto som «kan holdes
# i ASK». Det ble funnet ved å lese sidene. Agenten leser derfor noen hele
# sider hver uke, i fast rekkefølge, så hele katalogen er lest på ~16 uker.

SIDER_PER_UKE = 10


def ukens_sider(tickere, i_dag, antall=SIDER_PER_UKE):
    """Aksjesidene som leses i sin helhet denne ISO-uken.

    Alfabetisk rekkefølge, og samme uke gir samme utvalg uansett når på dagen
    eller hvor mange ganger det kjøres.
    """
    tickere = sorted(set(tickere))
    if not tickere:
        return []
    runder = math.ceil(len(tickere) / antall)
    aar, uke, _ = i_dag.isocalendar()
    n = (aar * 53 + uke) % runder
    return tickere[n * antall:(n + 1) * antall]


def sidetekst(kilde):
    """Teksten leseren ser på en generert side, med overskrifter merket ##.

    Tittel og metabeskrivelse først, for de har egne tall som kan motsi
    siden. Skript, stil, SVG og navigasjon tas bort; tabellrader blir én linje
    med | mellom cellene.
    """
    from html.parser import HTMLParser

    class Leser(HTMLParser):
        HOPP = {"script", "style", "svg", "noscript", "nav", "header", "footer"}
        BLOKK = {"p", "div", "li", "tr", "section", "article", "details", "summary",
                 "br", "table", "ul", "ol", "dt", "dd"}

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.deler, self.dybde, self.tittel, self.meta = [], 0, "", ""
            self._i_tittel = False

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "meta" and a.get("name") == "description":
                self.meta = a.get("content") or ""
            if tag == "title":
                self._i_tittel = True
            if tag in self.HOPP:
                self.dybde += 1
            elif not self.dybde:
                if tag in ("h1", "h2", "h3", "h4"):
                    self.deler.append("\n\n## ")
                elif tag in ("td", "th"):
                    self.deler.append(" | ")
                elif tag in self.BLOKK:
                    self.deler.append("\n")

        def handle_endtag(self, tag):
            if tag == "title":
                self._i_tittel = False
            if tag in self.HOPP and self.dybde:
                self.dybde -= 1
            elif not self.dybde and tag in ("h1", "h2", "h3", "h4"):
                self.deler.append("\n")

        def handle_data(self, data):
            if self._i_tittel:
                self.tittel += data
            elif not self.dybde:
                self.deler.append(data)

    leser = Leser()
    leser.feed(kilde)
    tekst = "".join(leser.deler)
    linjer = [re.sub(r"[ \t]+", " ", l).strip(" |") for l in tekst.splitlines()]
    tekst = re.sub(r"\n{3,}", "\n\n", "\n".join(linjer)).strip()
    return (f"TITTEL: {' '.join(leser.tittel.split())}\n"
            f"META: {' '.join(leser.meta.split())}\n\n{tekst}")


def markdown_rapport(i_dag, antall, resultat, feilet):
    """Sammendrag for GitHub Actions: én linje per sjekk, eksempler under.

    Er samme sjekk utløst på mange aksjer, er det nesten alltid én feil i
    koden og ikke mange i dataene — derfor telles det per sjekk først.
    """
    per_sjekk = {}
    for t, funn in resultat.items():
        for f in funn:
            per_sjekk.setdefault(f["sjekk"], []).append((t, f))
    ut = [f"## Tallkontroll {i_dag.isoformat()}", "",
          f"{antall} aksjer kontrollert mot Yahoos ujusterte rådata og Oslo Børs — "
          f"**{len(resultat)} med avvik**, {len(feilet)} ikke kontrollert.", ""]
    if not per_sjekk:
        ut.append("Ingen avvik.")
    else:
        ut += ["| Sjekk | Alvor | Antall | Eksempler (vist → kilde) |", "|---|---|---|---|"]
        for sjekk, liste in sorted(per_sjekk.items(), key=lambda x: -len(x[1])):
            eks = "; ".join(f"{t} {f.get('vist')} → {f.get('kilde')}" for t, f in liste[:3])
            ut.append(f"| `{sjekk}` | {liste[0][1]['alvor']} | {len(liste)} | {eks} |")
    if feilet:
        ut += ["", "Ikke kontrollert: " + ", ".join(f"{t} ({g})" for t, g in feilet[:10])]
    ut += ["", "_Maskinell sammenligning. Etterprøving mot børsmeldingene gjøres av "
           "tallkontroll-agenten (`.claude/agents/tallkontroll.md`)._"]
    return "\n".join(ut)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("tickere", nargs="*")
    p.add_argument("--json", action="store_true")
    p.add_argument("--markdown", action="store_true",
                   help="tabell for jobbsammendraget i GitHub Actions")
    p.add_argument("--uten-newsweb", action="store_true",
                   help="hopp over ex-dato mot Oslo Børs (raskere)")
    p.add_argument("--meldinger", metavar="TICKER",
                   help="skriv ut utbyttemeldingene fra NewsWeb og avslutt")
    p.add_argument("--sideutvalg", action="store_true",
                   help="skriv ut ukens aksjesider til sidelesing og avslutt")
    p.add_argument("--sidetekst", nargs="+", metavar="TICKER",
                   help="skriv ut aksjesidene som ren tekst og avslutt")
    a = p.parse_args()

    if a.sideutvalg:
        alle = [t["ticker"] for t in _les_json(os.path.join(ROT, "data", "tickers.json"), [])]
        print(" ".join(ukens_sider(alle, datetime.date.today())))
        return

    if a.sidetekst:
        for t in a.sidetekst:
            sti = os.path.join(ROT, "aksjer", t.upper(), "index.html")
            if not os.path.exists(sti):
                print(f"=== {t.upper()}: finnes ikke ({sti})\n")
                continue
            with open(sti, encoding="utf-8") as f:
                print(f"=== {t.upper()}\n{sidetekst(f.read())}\n")
        return

    if a.meldinger:
        for m in utbyttemeldinger(a.meldinger.upper()):
            print(f"=== {m['publisert']}  {m['tittel']}  (id {m['id']})\n{m['tekst']}\n")
        return

    data = _les_json(os.path.join(ROT, "data", "aksjer.json"), {})
    rader = {r["ticker"]: r for r in (data.get("aksjer", data) if isinstance(data, dict) else data)}
    priser = _les_json(os.path.join(ROT, "data", "priser.json"), {}).get("aksjer", {})
    tickere_yf = {t["ticker"]: t["ticker_yf"]
                  for t in _les_json(os.path.join(ROT, "data", "tickers.json"), [])}
    valgt = [t.upper() for t in a.tickere] or sorted(rader)
    i_dag = datetime.date.today()

    if not a.uten_newsweb:
        import fetch_stocks as fs

    resultat, feilet = {}, []
    for n, t in enumerate(valgt):
        rad = rader.get(t)
        if not rad or t not in tickere_yf:
            feilet.append((t, "finnes ikke i aksjer.json/tickers.json"))
            continue
        try:
            kurs, utb = hent_raadata(tickere_yf[t])
        except Exception as e:  # nettverk / 429 — rapporteres, ikke gjettes
            feilet.append((t, f"Yahoo: {e}"))
            time.sleep(5)
            continue
        if not kurs:
            feilet.append((t, "Yahoo returnerte ingen kurs"))
            continue
        pris = (priser.get(t) or {}).get("pris") or rad.get("pris")
        kh = _les_json(os.path.join(ROT, "data", "kurs", f"{t}.json"), [])
        nw = None if a.uten_newsweb else fs.hent_newsweb_ex_dato(t, i_dag)
        funn = kontroller(rad, pris, kh, kurs, utb, i_dag, nw)
        if funn:
            resultat[t] = funn
        if not (a.json or a.markdown):
            print(f"[{n + 1}/{len(valgt)}] {t}: {len(funn)} avvik", file=sys.stderr)
        time.sleep(0.4)

    if a.json:
        print(json.dumps({"dato": i_dag.isoformat(), "kontrollert": len(valgt),
                          "avvik": resultat, "feilet": feilet},
                         ensure_ascii=False, indent=2))
        return

    if a.markdown:
        print(markdown_rapport(i_dag, len(valgt), resultat, feilet))
        return

    print(f"\nTallkontroll {i_dag.isoformat()} — {len(valgt)} aksjer, "
          f"{len(resultat)} med avvik, {len(feilet)} ikke kontrollert\n")
    per_sjekk = {}
    for t, funn in resultat.items():
        for f in funn:
            per_sjekk.setdefault(f["sjekk"], []).append((t, f))
    for sjekk, liste in sorted(per_sjekk.items()):
        print(f"## {sjekk} ({len(liste)})")
        for t, f in liste:
            detalj = ", ".join(f"{k}={v}" for k, v in f.items() if k not in ("sjekk", "alvor"))
            print(f"  {f['alvor']:8} {t:7} {detalj}")
        print()
    for t, grunn in feilet:
        print(f"  ikke kontrollert: {t} — {grunn}")


if __name__ == "__main__":
    main()
