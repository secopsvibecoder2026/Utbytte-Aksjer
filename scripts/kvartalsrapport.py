#!/usr/bin/env python3
"""Oppsummeringer av kvartalsrapporter: kø, kilde og porten agenten lagrer gjennom.

    python scripts/kvartalsrapport.py --ko                      # rapporter uten oppsummering
    python scripts/kvartalsrapport.py --ko --ticker DNB EQNR
    python scripts/kvartalsrapport.py --kilde DNB               # nyeste rapport som tekst
    python scripts/kvartalsrapport.py --kilde EQNR --melding 684944 684945 --ut kilde.txt
    python scripts/kvartalsrapport.py --skriv DNB oppsummering.json kilde.txt
    python scripts/kvartalsrapport.py --sjekk [--streng]       # alle lagrede, uten nett

Rapport-agenten (`.claude/agents/rapport.md`) skriver oppsummeringene, og
de lagres i `data/rapporter/{TICKER}.json`, nyeste først. Datajobben bygger
`/aksjer/{TICKER}/rapporter/` og boksen «Siste kvartalsrapport» på aksjesiden
fra dem (`generer_rapportsider()` i fetch_stocks.py).

**Hvert tall i en oppsummering må stå i kilden.** `--kilde` henter
børsmeldingen og rapporten (PDF-vedlegget, de første sidene) og skriver dem
som én tekstfil. `--skriv` lagrer bare når hvert tall i teksten og tabellen
finnes i den fila, språket består SKRIVESTIL.md og feltene er fylt ut. En
oppsummering av et resultat er tall på en side om penger, og et feil tall der
er verre enn ingen oppsummering. Kontrollen fanger ikke alt (et riktig tall
kan stå i feil rad), men den fanger tall som er regnet ut, husket eller
diktet opp.

Ingen tredjepartspakker. `--kilde` bruker `pdftotext` (poppler-utils) når det
finnes, og tar ellers bare meldingsteksten.
"""

import argparse
import datetime
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAPPORT_DIR = os.path.join(ROT, "data", "rapporter")
TICKERS_FIL = os.path.join(ROT, "data", "tickers.json")
HENDELSER_FIL = os.path.join(ROT, "data", "hendelser.json")
NEWSWEB_MELDING_URL = "https://newsweb.oslobors.no/message/{}"

# Hvor mange sider av PDF-rapporten som tas med i kilden. Nøkkeltallene står
# på de første sidene hos alle tre vi har prøvd (DNB, Equinor, Vår Energi).
# Hele rapporten ville gjort tallkontrollen svakere: jo flere tall i kilden,
# jo lettere treffer et feil tall et annet tall et sted i den.
KILDE_SIDER = 15

# Hvor langt tilbake køen ser etter rapporter som mangler oppsummering.
KO_DAGER = 120

# Lengdegrenser i ord. Teksten skal kunne leses på en mobil uten å bla mye.
GRENSER = {
    "resultat": (25, 110),
    "utbytte": (8, 90),
    "plan": (0, 60),
    "ellers": (0, 40),       # per punkt
    "deletekst": (0, 60),
}
MAKS_ELLERS = 3
NOKKELTALL_ANTALL = (2, 6)

PERIODE_RE = re.compile(r"^(\d{4})-(Q[1-4]|H[12]|AR)$")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ── Perioder ─────────────────────────────────────────────────────────────────

def periode_tekst(periode):
    """«2026-Q3» → «3. kvartal 2026», «2026-H1» → «1. halvår 2026», «2026-AR» → «året 2026»."""
    m = PERIODE_RE.match(periode or "")
    if not m:
        return periode or ""
    aar, del_ = m.groups()
    if del_.startswith("Q"):
        return f"{del_[1]}. kvartal {aar}"
    if del_.startswith("H"):
        return f"{del_[1]}. halvår {aar}"
    return f"året {aar}"


def periode_kort(periode):
    """«2026-Q3» → «3. kv. 2026». Til tabellhoder, der plassen er knapp."""
    m = PERIODE_RE.match(periode or "")
    if not m:
        return periode or ""
    aar, del_ = m.groups()
    if del_.startswith("Q"):
        return f"{del_[1]}. kv. {aar}"
    if del_.startswith("H"):
        return f"{del_[1]}. halvår {aar}"
    return aar


def forrige_periode(periode):
    """Samme periode året før: «2026-Q3» → «2025-Q3». Det er det rapportene sammenligner med."""
    m = PERIODE_RE.match(periode or "")
    if not m:
        return ""
    return f"{int(m.group(1)) - 1}-{m.group(2)}"


def foregaaende_periode(periode):
    """Perioden rett før, av samme slag: «2026-Q3» → «2026-Q2», «2026-Q1» → «2025-Q4».

    Halvår går til forrige halvår («2026-H1» → «2025-H2») og et år til året før.
    Et kvartal og et halvår er ikke etterfølgere av hverandre, så en
    kvartalsrapport har aldri en halvårsrapport som «forrige rapport».
    Ikke det samme som `forrige_periode()`, som er samme periode i fjor.
    """
    m = PERIODE_RE.match(periode or "")
    if not m:
        return ""
    aar, del_ = int(m.group(1)), m.group(2)
    if del_ == "AR":
        return f"{aar - 1}-AR"
    n = int(del_[1])
    if del_[0] == "Q":
        return f"{aar}-Q{n - 1}" if n > 1 else f"{aar - 1}-Q4"
    return f"{aar}-H{n - 1}" if n > 1 else f"{aar - 1}-H2"


def anker(periode):
    """Id-en på siden: «2026-Q3» → «2026-q3», så en lenke kan peke rett på rapporten."""
    return (periode or "").lower()


# ── Lagring ──────────────────────────────────────────────────────────────────

def _sorter(rapporter):
    return sorted(rapporter, key=lambda r: (r.get("dato") or "", r.get("periode") or ""),
                  reverse=True)


def les_rapporter(rot=ROT):
    """{TICKER: [oppsummering, …]}, nyeste først. Tom dict uten mappe."""
    mappe = os.path.join(rot, "data", "rapporter")
    ut = {}
    try:
        navn = sorted(os.listdir(mappe))
    except OSError:
        return ut
    for fil in navn:
        if not fil.endswith(".json"):
            continue
        try:
            with open(os.path.join(mappe, fil), encoding="utf-8") as f:
                liste = json.load(f)
        except (OSError, ValueError) as e:
            print(f"  Advarsel: kunne ikke lese {fil}: {e}", file=sys.stderr)
            continue
        if isinstance(liste, list) and liste:
            ut[fil[:-5]] = _sorter([r for r in liste if isinstance(r, dict)])
    return ut


def lagre(ticker, rapport, rot=ROT):
    """Legger inn eller bytter ut oppsummeringen for perioden. Returnerer stien."""
    mappe = os.path.join(rot, "data", "rapporter")
    os.makedirs(mappe, exist_ok=True)
    sti = os.path.join(mappe, f"{ticker}.json")
    try:
        with open(sti, encoding="utf-8") as f:
            liste = json.load(f)
    except (OSError, ValueError):
        liste = []
    liste = [r for r in liste if r.get("periode") != rapport["periode"]] + [rapport]
    with open(sti, "w", encoding="utf-8") as f:
        json.dump(_sorter(liste), f, ensure_ascii=False, indent=1)
        f.write("\n")
    return sti


# ── Serier: samme nøkkeltall rapport for rapport ─────────────────────────────
#
# Rapportsiden viser forrige rapports tall ved siden av de nye, og en tabell
# over tid («Utvikling over tid»). Verdiene i `nokkeltall` er tekst skrevet av
# agenten («358,9 mill. USD»), og `navn` er fritekst. To regler holder det
# ærlig:
#
# - **Navnet må være identisk** (etter trim og casefold) for at to rader skal
#   regnes som samme tall. Ingen uklar matching: «Resultat etter skatt» og
#   «Resultat til aksjonærene» er ulike tall, og en tabell som slår dem sammen
#   er verre enn en som lar dem stå hver for seg. Portene i `--skriv` varsler
#   når navn nesten er like (`serie_varsler()`), så agenten retter det i kilden.
# - **Endringen regnes ut ved bygging og lagres aldri.** Den vises bare når
#   begge verdiene lar seg tolke til samme enhet, og grunnlaget er positivt.
#   Oppsummeringen sier selv at agenten ikke regner (se rapport.md), så
#   endringstallene er vårt, og siden sier det.

SERIE_MAKS = 6   # kolonner i «Utvikling over tid»

_ENHETSNAVN = ((re.compile(r"\b(?:kr|kroner|nok)\b"), "nok"),
               (re.compile(r"\b(?:usd|dollar)\b"), "usd"),
               (re.compile(r"\b(?:eur|euro)\b"), "eur"),
               (re.compile(r"\bprosent\b"), "%"),
               (re.compile(r"\b(?:millioner|mill)\b\.?"), "mill."),
               (re.compile(r"\b(?:milliarder|mrd)\b\.?"), "mrd."))

# Skalaord foran enheten: «mill. USD» er en million dollar.
_SKALA = {"tusen": 3, "millioner": 6, "mill": 6, "milliarder": 9, "mrd": 9}

_MELLOM = "[ \u00a0\u202f]"
_VERDI_RE = re.compile(
    r"^(?:(?P<u1>underskudd|tap)(?:\s+på)?\s+)?"
    r"(?P<fortegn>[-\u2212\u2013+])?\s*"
    rf"(?P<tall>\d{{1,3}}(?:{_MELLOM}\d{{3}})+(?:,\d+)?|\d+(?:,\d+)?)"
    rf"(?:{_MELLOM}*(?P<skala>tusen|millioner|milliarder|mill\.?|mrd\.?)(?![\wæøå]))?"
    rf"(?:{_MELLOM}*(?P<enhet>(?!\d)[^\s].*?))?"
    r"(?:\s+(?P<u2>underskudd|tap))?\s*$", re.I)


def normaliser_navn(navn):
    """Nøkkelen to rader må dele for å være samme tall: trimmet og casefold, ingenting mer."""
    return (navn or "").strip().casefold()


def normaliser_enhet(tekst):
    """Enheten som tekst, med valutaene og skalaordene skrevet likt («kroner» → «nok»)."""
    t = " ".join((tekst or "").casefold().split())
    for monster, bytt in _ENHETSNAVN:
        t = monster.sub(bytt, t)
    return t


class Verdi:
    """Et nøkkeltall tolket: `verdi` (Decimal, med fortegn, i enhetens grunnmål),
    `enhet` (normalisert tekst uten skalaord), `desimaler` slik det sto skrevet
    og `skalert` (stod det «tusen», «mill.» eller «mrd.» foran enheten?)."""
    __slots__ = ("verdi", "enhet", "desimaler", "skalert")

    def __init__(self, verdi, enhet, desimaler, skalert=False):
        self.verdi, self.enhet, self.desimaler, self.skalert = verdi, enhet, desimaler, skalert

    def kan_sammenlignes_med(self, annen):
        """Samme enhet, og begge skrevet med skalaord eller ingen av dem. «5 kr» mot
        «5 mill. kr» er ikke samme størrelse (beløp per aksje mot et resultat),
        selv om begge er kroner."""
        return self.enhet == annen.enhet and self.skalert == annen.skalert

    @property
    def prosent(self):
        return self.enhet == "%"

    def __repr__(self):
        return f"Verdi({self.verdi}, {self.enhet!r})"


def tolk_verdi(tekst):
    """«358,9 mill. USD» → Verdi(358900000, «usd»), eller None når teksten ikke er
    ett tall med enhet.

    Godtar komma som desimaltegn, mellomrom (også hardt) som tusenskille,
    fortegn («−5,2», «-5,2», «+5,2»), skalaordene «tusen», «mill.» og «mrd.»
    foran enheten, og «underskudd» foran eller etter («underskudd på 29,5 mill.
    USD» er −29,5 millioner). Alt annet gir None: «ca. 12 mrd.», «12 til 14 %»,
    «n/a» og en tom celle har ingen verdi vi kan regne med.
    """
    m = _VERDI_RE.match(tekst or "")
    if not m:
        return None
    try:
        tall = Decimal(re.sub(rf"{_MELLOM}", "", m.group("tall")).replace(",", "."))
    except InvalidOperation:
        return None
    if re.search(r"\d", m.group("enhet") or ""):
        return None   # «12 til 14 %»: to tall, ikke ett tall med enhet
    desimaler = len(m.group("tall").split(",")[1]) if "," in m.group("tall") else 0
    skala = (m.group("skala") or "").lower().rstrip(".")
    if skala:
        tall *= Decimal(10) ** _SKALA[skala]
    if m.group("fortegn") in ("-", "\u2212", "\u2013") or m.group("u1") or m.group("u2"):
        tall = -tall   # «underskudd −5» er ett underskudd, ikke to minus
    return Verdi(tall, normaliser_enhet(m.group("enhet") or ""), desimaler, bool(skala))


def endring(ny_tekst, gammel_tekst):
    """Endringen fra `gammel` til `ny`, eller None når den ikke lar seg regne.

    - `{"type": "pp", "verdi": Decimal, "desimaler": n}` for tall i prosent:
      forskjellen i prosentpoeng, ikke en prosent av en prosent.
    - `{"type": "prosent", "verdi": Decimal, "desimaler": 1}` ellers: prosent
      endring fra grunnlaget.

    None når en av verdiene ikke lar seg tolke, enhetene er ulike (USD mot NOK,
    kroner mot en prosent, «5 mill. kr» mot «5 kr»), eller grunnlaget er null
    eller negativt. En endring
    fra underskudd er ikke en prosent, og det er heller ikke en endring til
    underskudd fra et positivt tall: tallet skifter fortegn, og «−152 %» sier
    ikke det en leser trenger å vite.

    «5,6 mrd. kr» mot «5 600 mill. kr» er samme beløp og gir 0, siden skalaordene
    regnes om. Beregningen bruker Decimal, så avrunding er den leseren venter.
    """
    ny, gammel = tolk_verdi(ny_tekst), tolk_verdi(gammel_tekst)
    if ny is None or gammel is None or not ny.kan_sammenlignes_med(gammel):
        return None
    if ny.prosent:
        des = min(2, max(ny.desimaler, gammel.desimaler))
        return {"type": "pp", "verdi": _rund(ny.verdi - gammel.verdi, des), "desimaler": des}
    if gammel.verdi <= 0 or ny.verdi < 0:
        return None
    return {"type": "prosent", "verdi": _rund((ny.verdi - gammel.verdi) / gammel.verdi * 100, 1),
            "desimaler": 1}


def _rund(verdi, desimaler):
    """Rund av, og 0,5 går opp (ikke til nærmeste partall, som `round()`)."""
    return verdi.quantize(Decimal(1).scaleb(-desimaler), rounding=ROUND_HALF_UP)


def forrige_rapport(liste, rapport):
    """Rapporten for perioden rett før `rapport` i `liste`, eller None.

    Bare den som kommer rett før (`foregaaende_periode()`): «forrige rapport»
    skal være forrige kvartal, ikke «den eldste vi har». Mangler et kvartal
    mellom to lagrede rapporter, er det ingen forrige rapport å regne endring
    mot, og siden sier ingenting om det.
    """
    onsket = foregaaende_periode((rapport or {}).get("periode"))
    if not onsket:
        return None
    return next((r for r in liste or [] if r.get("periode") == onsket), None)


def _rader_per_navn(rapport):
    """{nøkkel: rad} for nøkkeltallene med navn og verdi. Første rad vinner ved likt navn."""
    ut = {}
    for x in (rapport or {}).get("nokkeltall") or []:
        if isinstance(x, dict) and (x.get("navn") or "").strip() and (x.get("naa") or "").strip():
            ut.setdefault(normaliser_navn(x["navn"]), x)
    return ut


def mot_forrige(rapport, forrige):
    """{nøkkel: {"tekst", "endring"}} for radene i `rapport` som har en rad med
    identisk navn i `forrige`. Tom uten forrige rapport eller uten treff.

    `endring` er None når den ikke lar seg regne (se `endring()`).
    """
    if not forrige:
        return {}
    gamle = _rader_per_navn(forrige)
    ut = {}
    for nokkel, x in _rader_per_navn(rapport).items():
        g = gamle.get(nokkel)
        if g:
            ut[nokkel] = {"tekst": g["naa"], "endring": endring(x["naa"], g["naa"])}
    return ut


def serie(liste, maks=SERIE_MAKS):
    """Nøkkeltallene som står med identisk navn i minst to av de `maks` nyeste
    rapportene, eller None når ingen gjør det.

    `liste` er nyeste først. Svaret:

        {"kolonner": [{"periode": "2026-Q3"}, …],          # nyeste til venstre
         "rader": [{"navn": "Resultat etter skatt",
                    "celler": [{"tekst": "358,9 mill. USD" | None,
                                "endring": {…} | None}, …]}]}

    Radene står i rekkefølgen de har i den nyeste rapporten de finnes i. En
    celle uten tall er None. `endring` på en celle er endringen fra cellen til
    høyre, og bare når den er forrige periode og begge har et tall: et hull
    mellom to rapporter blir ikke hoppet over.
    """
    kol = [r for r in (liste or [])[:maks]]
    if len(kol) < 2:
        return None
    per_kol = [_rader_per_navn(r) for r in kol]
    rekkefolge = {}
    for rader in per_kol:
        for nokkel, x in rader.items():
            rekkefolge.setdefault(nokkel, x["navn"].strip())
    ut = []
    for nokkel, navn in rekkefolge.items():
        tekster = [(rader.get(nokkel) or {}).get("naa") for rader in per_kol]
        if sum(1 for t in tekster if t) < 2:
            continue
        celler = []
        for j, t in enumerate(tekster):
            e = None
            if (t and j + 1 < len(kol) and tekster[j + 1]
                    and foregaaende_periode(kol[j].get("periode")) == kol[j + 1].get("periode")):
                e = endring(t, tekster[j + 1])
            celler.append({"tekst": t, "endring": e})
        ut.append({"navn": navn, "celler": celler})
    if not ut:
        return None
    return {"kolonner": [{"periode": r.get("periode")} for r in kol], "rader": ut}


def _ett_ord_forskjell(a, b):
    """Navn som ligner uten å være like: ett ord skiftet ut, lagt til eller tatt bort.

    Et navn med ett ord har ingenting å dele, så to enkeltord («Inntekter» og
    «Resultat») ligner ikke. «Resultat før skatt» og «Resultat etter skatt»
    gjør det, og det er riktig at de varsles: et varsel er et spørsmål, og
    svaret kan være at de er to ulike tall.
    """
    ta, tb = a.split(), b.split()
    if len(ta) == len(tb):
        return len(ta) >= 2 and sum(x != y for x, y in zip(ta, tb)) == 1
    if abs(len(ta) - len(tb)) == 1:
        kort, lang = sorted((ta, tb), key=len)
        return any(lang[:i] + lang[i + 1:] == kort for i in range(len(lang)))
    return False


_ENHET_ETTER_TALL = re.compile(
    r"^\s*(?:(?:underskudd|tap)(?:\s+på)?\s+)?[-\u2212\u2013+]?\s*\d[\d \u00a0\u202f]*(?:,\d+)?\s*(.*?)\s*$", re.I)


def _enhet_tekst(tekst):
    """Det som står etter tallet, normalisert. Virker også for en verdi `tolk_verdi()` ikke leser."""
    m = _ENHET_ETTER_TALL.match(tekst or "")
    return normaliser_enhet(m.group(1)) if m else ""


def serie_varsler(rapport, forrige):
    """Varsler om at serien på rapportsiden ikke vil henge sammen. Stopper ikke lagringen.

    To funn, begge mot den forrige lagrede rapporten:

    - **Samme navn, annen enhet.** «Inntekter» i mill. USD forrige gang og mrd.
      USD nå, eller dollar mot kroner. Ulik valuta gir ingen endring. Ulik
      skala (mill. mot mrd.) regnes om, men to tall i samme rad med ulik skala
      leses dårlig.
    - **Nesten samme navn.** Ett ord forskjellig, uten at navnet er identisk
      med noe i forrige rapport. Radene havner da på hver sin linje i
      «Utvikling over tid», og tallet mangler i radens øvrige kolonner.
    """
    if not forrige:
        return []
    varsler = []
    ny = _rader_per_navn(rapport)
    gammel = _rader_per_navn(forrige)
    fp = periode_kort(forrige.get("periode"))
    for nokkel, x in ny.items():
        g = gammel.get(nokkel)
        if not g:
            continue
        e_ny, e_gml = _enhet_tekst(x["naa"]), _enhet_tekst(g["naa"])
        if e_ny == e_gml:
            continue
        a, b = tolk_verdi(x["naa"]), tolk_verdi(g["naa"])
        navn = x["navn"].strip()
        if a is not None and b is not None and a.kan_sammenlignes_med(b):
            varsler.append(
                f"«{navn}»: enheten er «{e_ny or 'ingen'}», og i forrige rapport ({fp}) var den «{e_gml or 'ingen'}». "
                f"Endringen regnes om, men tallene i samme rad leses best i samme enhet. Bruk samme enhet.")
        else:
            varsler.append(
                f"«{navn}»: enheten er «{e_ny or 'ingen'}», og i forrige rapport ({fp}) var den «{e_gml or 'ingen'}». "
                f"Da kan ikke endringen regnes ut, og serien henger ikke sammen på rapportsiden. Bruk samme enhet og valuta.")
    nye = {k: x for k, x in ny.items() if k not in gammel}
    gamle = {k: x for k, x in gammel.items() if k not in ny}
    for nk, x in nye.items():
        for gk, g in gamle.items():
            if _ett_ord_forskjell(nk, gk):
                varsler.append(
                    f"«{x['navn'].strip()}» ligner på «{g['navn'].strip()}» i forrige rapport ({fp}), men er ikke identisk. "
                    f"Er det samme tall, bruk nøyaktig samme navn, ellers henger ikke serien sammen på rapportsiden. "
                    f"Er det to ulike tall, er det i orden.")
                break
    return varsler


def forrige_lagrede(ticker, rapport, rot=None):
    """Den nyeste lagrede rapporten som er eldre enn `rapport`, eller None.

    En lagring av samme periode bytter ut den gamle, så den sammenlignes ikke
    med seg selv.
    """
    liste = les_rapporter(rot or ROT).get(ticker) or []
    nokkel = ((rapport.get("dato") or ""), (rapport.get("periode") or ""))
    eldre = [r for r in liste
             if r.get("periode") != rapport.get("periode")
             and ((r.get("dato") or ""), (r.get("periode") or "")) < nokkel]
    return max(eldre, key=lambda r: ((r.get("dato") or ""), (r.get("periode") or "")), default=None)


# ── Tall: hva står i oppsummeringen, og står det i kilden? ───────────────────

_MND = ("januar|februar|mars|april|mai|juni|juli|august|september|oktober|november|"
        "desember|jan|feb|mar|apr|jun|jul|aug|sept|sep|okt|nov|des")

# Det som ser ut som tall, men ikke er tall fra rapporten.
_FRITAK = [
    re.compile(rf"\b\d{{1,2}}\.\s*(?:{_MND})\b\.?(?:\s+(?:19|20)\d{{2}})?", re.I),  # datoer
    re.compile(r"\b[1-4]\.\s*(?:kvartal\w*|kv\b\.?|halvår\w*)", re.I),               # perioder
    re.compile(r"\b(?:Q[1-4]|[1-4]Q)\b", re.I),
    re.compile(r"(?<![\d,.])(?<!\d[ \u00a0])(?:19|20)\d{2}\b(?![,.]\d)(?![ \u00a0]\d{3}\b)"),  # årstall
]

# Norsk skrivemåte: mellomrom (eller hardt mellomrom) som tusenskille, komma
# som desimaltegn. «3Q26» og «CET1» er ikke tall i teksten (bokstav inntil).
_TALL_NORSK = re.compile(
    r"(?<![\w.,])\d{1,3}(?:[  ]\d{3})+(?:,\d+)?(?![\w])"
    r"|(?<![\w.,])\d+(?:,\d+)?(?![\w])")

# Engelsk skrivemåte i norsk tekst («9.8» eller «1,849»). Kilden bruker den,
# teksten skal ikke: et punktum som desimaltegn leses ellers som to tall.
_TALL_MED_PUNKTUM = re.compile(r"(?<![\w.,])\d+\.\d+(?![\w])")

_TALL_KILDE = re.compile(r"\d[\d.,]*\d|\d")
_TALL_KILDE_MELLOMROM = re.compile(r"\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?")
_PROSENT_ORD = re.compile(r"%|per ?cent|percent|prosent|\bpst\b", re.I)

# Hvor langt fra hverandre (i tegn) to tall på linjer rett under hverandre kan
# starte og likevel regnes som samme kolonne. I Vår Energis nøkkeltallsruter
# står forrige periode i parentes på linjen under: «369» over «(376)».
KOLONNE_SLINGRING = 4

def _enhet(tekst, slutt):
    """Enheten rett etter et tall: «%», «mrd», «mill» eller None."""
    etter = tekst[slutt:slutt + 14].lower()
    if re.match(r"\s*(?:%|prosent)", etter):
        return "%"
    if re.match(r"\s*(?:mrd|milliard)", etter):
        return "mrd"
    if re.match(r"\s*mill", etter):
        return "mill"
    return None


def tall_i_tekst(tekst, fritak_navn=()):
    """[(slik det står, verdi, desimaler, enhet)] for tallene i en norsk tekst.

    Årstall, datoer og periodenavn («3. kvartal») telles ikke, og heller ikke
    tall i selskapsnavnet («SpareBank 1», «Subsea 7»).
    """
    t = tekst or ""
    for n in sorted((n for n in fritak_navn if n), key=len, reverse=True):
        t = t.replace(n, " " * len(n))
    for r in _FRITAK:
        t = r.sub(lambda m: " " * len(m.group(0)), t)
    ut = []
    for m in _TALL_NORSK.finditer(t):
        s = m.group(0)
        ren = s.replace(" ", "").replace(" ", "")
        des = len(ren.split(",")[1]) if "," in ren else 0
        try:
            ut.append((s, float(ren.replace(",", ".")), des, _enhet(t, m.end())))
        except ValueError:
            continue
    return ut


def _verdier(token, per_aksje=False):
    """Mulige verdier for et tall slik det står i kilden.

    Kildene blander engelsk («9,844» er ni tusen åtte hundre og førtifire) og
    norsk («12,35 milliarder»), og samme tegn betyr ulike ting. Tre sifre etter
    skilletegnet leses som tusenskille («9,844», «1.125 millioner»): ellers
    blir hvert tusental i en engelsk tabell også et lite desimaltall, og
    «10,7» uten enhet fant «10,684» (testen fanget det). Unntak: et tall som
    begynner med 0 («0.375»), og tall på en linje om beløp per aksje, der tre
    desimaler forekommer («NOK 1.125 per share»).
    """
    s = token.replace("\u00a0", "").replace(" ", "")
    ut = set()
    tusen = (lambda sep: re.fullmatch(rf"[1-9]\d{{0,2}}(?:\{sep}\d{{3}})+", s))
    try:
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):
                ut.add(float(s.replace(".", "").replace(",", ".")))
            else:
                ut.add(float(s.replace(",", "")))
        elif "," in s:
            if tusen(","):
                ut.add(float(s.replace(",", "")))
            if s.count(",") == 1 and (not tusen(",") or per_aksje):
                ut.add(float(s.replace(",", ".")))
        elif "." in s:
            if tusen("."):
                ut.add(float(s.replace(".", "")))
            if s.count(".") == 1 and (not tusen(".") or per_aksje):
                ut.add(float(s))
        else:
            ut.add(float(s))
    except ValueError:
        pass
    return ut


_PER_AKSJE = re.compile(r"per (?:share|aksje)|pr\.? aksje|dividend|utbytte", re.I)


def _tall_i_linje(linje):
    """[(kolonne, {verdier})] for tallene på en linje i kilden."""
    ut = []
    per_aksje = bool(_PER_AKSJE.search(linje))
    for r in (_TALL_KILDE, _TALL_KILDE_MELLOMROM):
        for m in r.finditer(linje):
            v = _verdier(m.group(0), per_aksje)
            if v:
                ut.append((m.start(), v))
    return ut


class Kilde:
    """Tallene i kildeteksten, linje for linje.

    `alle` er alle verdier, `prosent` bare dem på linjer som handler om
    prosent («7.9 per cent», «Return on equity (per cent) 14.5 15.8»).
    """

    def __init__(self, tekst):
        linjer = (tekst or "").splitlines()
        self.linjer = [_tall_i_linje(l) for l in linjer]
        self.alle, self.prosent = set(), set()
        for linje, tall in zip(linjer, self.linjer):
            v = set().union(*(t[1] for t in tall)) if tall else set()
            self.alle |= v
            if _PROSENT_ORD.search(linje):
                self.prosent |= v


def finnes_i(verdi, desimaler, enhet, verdier):
    """Står verdien blant `verdier`, eventuelt avrundet til færre desimaler?

    Med «mrd.» etter tallet godtas også millioner i kilden (9 844 → 9,8), med
    «mill.» også milliarder (1.5 → 1 500). Ingen annen omregning: et tall som
    er regnet ut av to andre, står ikke i kilden.
    """
    halv = 0.5 * 10 ** -desimaler + 1e-9
    for k in verdier:
        k = abs(k)
        if abs(k - verdi) <= halv:
            return True
        if enhet == "mrd" and abs(k / 1000 - verdi) <= halv:
            return True
        if enhet == "mill" and abs(k * 1000 - verdi) <= halv:
            return True
    return False


def finnes_i_kilde(verdi, desimaler, kilde, enhet=None):
    """Står tallet i kilden? Et prosenttall må stå på en linje om prosent."""
    if isinstance(kilde, Kilde):
        return finnes_i(verdi, desimaler, enhet, kilde.prosent if enhet == "%" else kilde.alle)
    return finnes_i(verdi, desimaler, enhet, kilde)


def tall_i_kilde(tekst):
    """Alle tallverdier i kilden."""
    return Kilde(tekst).alle


def _tekstfelt(rapport):
    """[(feltnavn, tekst)] for alt i oppsummeringen som vises eller deles."""
    felt = [(n, rapport.get(n) or "") for n in ("resultat", "utbytte", "plan", "deletekst")]
    for i, p in enumerate(rapport.get("ellers") or []):
        felt.append((f"ellers[{i}]", p or ""))
    for i, rad in enumerate(rapport.get("nokkeltall") or []):
        if isinstance(rad, dict):
            for n in ("navn", "naa", "forrige"):
                felt.append((f"nokkeltall[{i}].{n}", rad.get(n) or ""))
    return felt


def tall_uten_kilde(rapport, kildetekst, fritak_navn=()):
    """[(felt, tall)] for hvert tall i oppsummeringen som ikke står i kilden."""
    kilde = kildetekst if isinstance(kildetekst, Kilde) else Kilde(kildetekst)
    mangler = []
    for felt, tekst in _tekstfelt(rapport):
        for s, verdi, des, enhet in tall_i_tekst(tekst, fritak_navn):
            if not finnes_i_kilde(verdi, des, kilde, enhet):
                mangler.append((felt, s))
    return mangler


def _treff(verdi, des, enhet, tall):
    """Kolonnene der verdien står på en linje."""
    return [kol for kol, v in tall if finnes_i(verdi, des, enhet, v)]


def par_uten_kilde(rapport, kildetekst, fritak_navn=()):
    """[(rad, naa, forrige)] for nøkkeltallsrader der de to tallene ikke står
    i samme tabellrad i kilden.

    Hvert tall kan stå i kilden hver for seg og likevel komme fra to ulike
    rader i tabellen. Står de i samme rad, står de på samme linje (DNB,
    Equinor), eller rett under hverandre i samme kolonne (Vår Energis
    nøkkeltallsruter, med forrige periode i parentes under).
    """
    kilde = kildetekst if isinstance(kildetekst, Kilde) else Kilde(kildetekst)
    ut = []
    for i, rad in enumerate(rapport.get("nokkeltall") or []):
        if not isinstance(rad, dict):
            continue
        a = tall_i_tekst(rad.get("naa") or "", fritak_navn)
        b = tall_i_tekst(rad.get("forrige") or "", fritak_navn)
        if not a or not b:
            continue
        (_, va, da, ea), (_, vb, db, eb) = a[0], b[0]
        funnet = False
        for j, tall in enumerate(kilde.linjer):
            ka = _treff(va, da, ea, tall)
            if not ka:
                continue
            kb = _treff(vb, db, eb, tall)
            if kb and (len(set(ka) | set(kb)) > 1 or va == vb):
                funnet = True
                break
            under = kilde.linjer[j + 1] if j + 1 < len(kilde.linjer) else []
            kb = _treff(vb, db, eb, under)
            if any(abs(x - y) <= KOLONNE_SLINGRING for x in ka for y in kb):
                funnet = True
                break
        if not funnet:
            ut.append((i, rad.get("naa"), rad.get("forrige")))
    return ut


# ── Felt og språk ────────────────────────────────────────────────────────────

_RAD = re.compile(r"\banbefal\w*|\bkursmål\w*|\bbør (?:du )?(?:kjøpe|selge)\b", re.I)

# Vurderinger leseren bør se hvem som står bak. Ikke forbudt, men et varsel:
# står ordet uten «ifølge selskapet» eller et sitat, er det vår vurdering.
_VURDERING = re.compile(
    r"\b(?:sterk\w*|solid\w*|svak\w*|imponer\w*|skuff\w*|rekord\w*|knallsterk\w*|"
    r"eksepsjonell\w*|fantastisk\w*|glimrende|dramatisk\w*)\b", re.I)


def _ord(tekst):
    return len((tekst or "").split())


def sjekk_felt(rapport, i_dag=None):
    """(feil, varsler). Feil stopper lagringen, varsler gjør det ikke."""
    feil, varsler = [], []
    i_dag = i_dag or datetime.date.today().isoformat()
    for n in ("periode", "dato", "melding", "tittel", "resultat", "nokkeltall",
              "utbytte", "skrevet"):
        if not rapport.get(n):
            feil.append(f"«{n}» mangler")
    p = rapport.get("periode") or ""
    if p and not PERIODE_RE.match(p):
        feil.append(f"«periode» må være ÅÅÅÅ-Q1…Q4, ÅÅÅÅ-H1/H2 eller ÅÅÅÅ-AR, ikke «{p}»")
    fp = rapport.get("forrige_periode")
    if fp and not PERIODE_RE.match(fp):
        feil.append(f"«forrige_periode» har feil form: «{fp}»")
    for n in ("dato", "skrevet"):
        v = rapport.get(n) or ""
        if v and not _ISO_RE.match(v):
            feil.append(f"«{n}» må være ÅÅÅÅ-MM-DD, ikke «{v}»")
    dato, skrevet = rapport.get("dato") or "", rapport.get("skrevet") or ""
    if _ISO_RE.match(dato) and dato > i_dag:
        feil.append(f"rapporten er datert fram i tid ({dato})")
    if _ISO_RE.match(dato) and _ISO_RE.match(skrevet) and skrevet < dato:
        feil.append("«skrevet» er før rapporten ble lagt fram")
    m = PERIODE_RE.match(p)
    if m and _ISO_RE.match(dato) and not (0 <= int(dato[:4]) - int(m.group(1)) <= 1):
        feil.append(f"perioden {p} passer ikke med datoen {dato}")
    if rapport.get("melding") and not re.fullmatch(r"\d+", str(rapport["melding"])):
        feil.append("«melding» skal være id-en til børsmeldingen på NewsWeb")

    for n, (lav, hoy) in GRENSER.items():
        if n == "ellers":
            continue
        v = rapport.get(n) or ""
        if not isinstance(v, str):
            feil.append(f"«{n}» skal være tekst")
            continue
        o = _ord(v)
        if v and (o < lav or o > hoy):
            feil.append(f"«{n}» har {o} ord, skal ha {lav}–{hoy}")
    ellers = rapport.get("ellers") or []
    if not isinstance(ellers, list):
        feil.append("«ellers» skal være en liste")
        ellers = []
    if len(ellers) > MAKS_ELLERS:
        feil.append(f"«ellers» har {len(ellers)} punkter, høyst {MAKS_ELLERS}")
    for i, pkt in enumerate(ellers):
        if _ord(pkt) > GRENSER["ellers"][1]:
            feil.append(f"«ellers[{i}]» har {_ord(pkt)} ord, høyst {GRENSER['ellers'][1]}")

    rader = rapport.get("nokkeltall") or []
    if not isinstance(rader, list):
        feil.append("«nokkeltall» skal være en liste")
        rader = []
    lav, hoy = NOKKELTALL_ANTALL
    if rader and not (lav <= len(rader) <= hoy):
        feil.append(f"«nokkeltall» har {len(rader)} rader, skal ha {lav}–{hoy}")
    for i, rad in enumerate(rader):
        if not isinstance(rad, dict) or not rad.get("navn") or not rad.get("naa"):
            feil.append(f"«nokkeltall[{i}]» trenger «navn» og «naa»")

    for felt, tekst in _tekstfelt(rapport):
        if _TALL_MED_PUNKTUM.search(tekst):
            feil.append(f"«{felt}»: bruk komma som desimaltegn («{_TALL_MED_PUNKTUM.search(tekst).group(0)}»)")
        if _RAD.search(tekst):
            feil.append(f"«{felt}»: «{_RAD.search(tekst).group(0)}» er et råd. Beskriv, ikke anbefal")
        for v in _VURDERING.findall(tekst):
            varsler.append(f"«{felt}»: «{v}». Er det selskapets ord? Skriv «ifølge selskapet» eller sitér")
    return feil, varsler


def sjekk_sprak(rapport):
    """Feil etter SKRIVESTIL.md. Ingen tankestreker i det hele tatt: tekstene er korte."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sjekk_sprak import vurder
    avsnitt = [t for _, t in _tekstfelt(rapport) if t]
    funn = vurder(avsnitt)
    feil = []
    if funn["streker"]:
        feil.append(f"{funn['streker']} tankestrek(er). Del setningen, eller bruk komma eller kolon")
    if funn["vendinger"]:
        feil.append("vendinger fra SKRIVESTIL.md: " + ", ".join(f"«{v}»" for v in funn["vendinger"]))
    return feil


def _navn(ticker):
    try:
        with open(TICKERS_FIL, encoding="utf-8") as f:
            for t in json.load(f):
                if t["ticker"] == ticker:
                    return t
    except (OSError, ValueError):
        pass
    return None


def _kortnavn(navn):
    """Selskapsnavnet uten selskapsform, som fetch_stocks._kort_selskapsnavn()."""
    return re.sub(r"\s+(ASA|AS|ASA\.|Ltd\.?|Limited|PLC|plc|SE|AB|N\.V\.|NV|Inc\.?|Corp\.?|"
                  r"Corporation|AG|SA|P/F|Holding|Group)\b.*$", "", navn or "").strip()


def vurder_oppsummering(ticker, rapport, kildetekst=None, meldinger_i_kilde=None, i_dag=None,
                        forrige=None):
    """(feil, varsler) for én oppsummering. Ren funksjon, ingen nett.

    Uten `kildetekst` sjekkes bare form og språk; det er det CI kan gjøre.
    Med `forrige` (selskapets forrige lagrede rapport) varsles det også om en
    rad som ikke lar seg lese som en serie sammen med den forrige
    (`serie_varsler()`). Varslene stopper ikke lagringen.
    """
    feil, varsler = sjekk_felt(rapport, i_dag)
    varsler += serie_varsler(rapport, forrige)
    feil += sjekk_sprak(rapport)
    t = _navn(ticker)
    if t is None:
        feil.append(f"{ticker} finnes ikke i data/tickers.json")
    if kildetekst is not None:
        if meldinger_i_kilde is not None and str(rapport.get("melding")) not in meldinger_i_kilde:
            feil.append(f"kilden er hentet for melding {', '.join(meldinger_i_kilde) or '?'}, "
                        f"oppsummeringen sier {rapport.get('melding')}")
        fritak = [t["navn"], _kortnavn(t["navn"])] if t else []
        kilde = Kilde(kildetekst)
        for felt, s in tall_uten_kilde(rapport, kilde, fritak):
            feil.append(f"«{felt}»: tallet «{s}» står ikke i kilden")
        for i, naa, forrige in par_uten_kilde(rapport, kilde, fritak):
            feil.append(f"«nokkeltall[{i}]»: «{naa}» og «{forrige}» står ikke i samme "
                        f"tabellrad i kilden. Er de hentet fra to ulike rader?")
    return feil, varsler


# ── Hvilke meldinger er kvartalsrapporter? ───────────────────────────────────

_PERIODE_ORD = re.compile(
    r"quarter|kvartal|\bq[1-4]\b|\b[1-4]q\b|half[- ]?year|halvår|interim|delårs|"
    r"first half|second half|full[- ]year|annual|årsrapport|årsresultat|helår", re.I)
_RESULTAT_ORD = re.compile(
    r"result|report|rapport|resultat|regnskap|earnings|financial statements|figures", re.I)
_IKKE_RAPPORT = re.compile(
    r"trading update|invitation|invitasjon|reminder|påminnelse|presentation of|"
    r"presentasjon av|webcast|conference call|key information|nøkkelinformasjon|"
    r"ex[ .-]?dividend|ex[ .-]?utbytte|financial calendar|finansiell kalender|"
    r"general meeting|generalforsamling|mandatory notification|meldepliktig|"
    r"share buy|tilbakekjøp|correction|korrigering|"
    # Varsler om en rapport som kommer, ikke rapporten selv (CMB.TECH, Cadeler,
    # BW LPG i november 2026), og et annet selskaps rapport i et
    # tilbudsdokument (Telenor om Bahnhof).
    r"publication date|release date|notice of|upcoming|will (?:be )?(?:publish|release|present)|"
    r"presentation on|earnings presentation|supplement|tilbudsdokument|offer document|"
    # «… ANNOUNCES Q3 2026 RESULTS ON 26/11/2026» (CMB.TECH) og «resultatpresentasjon
    # tredje kvartal 2026 – fredag 30. oktober» (Sparebanken Norge) varsler rapporten.
    r"results? on \d|resultatpresentasjon|to (?:publish|release|present)\b", re.I)

# Gjelder også meldinger som kommer inn via rapportdatoen i hendelser.json. Den
# lenken peker iblant på en melding samme dag som ikke er rapporten: Mowis og
# TGS' «Quarterly dividend», Sparebanken Norges invitasjon, en påminnelse.
_ALDRI_RAPPORT = re.compile(
    r"reminder|påminnelse|trading update|invitation|invitasjon|key information|"
    r"nøkkelinformasjon|ex[ .-]?dividend|ex[ .-]?utbytte|results? on \d|resultatpresentasjon|"
    r"publication date|notice of|upcoming|(?:to|will(?: be)?) (?:publish|release|present)\b",
    re.I)
_UTBYTTE_ORD = re.compile(r"dividend|utbytte|distribution", re.I)
# Prefikset før «:» eller « - » når det er et selskapsnavn, ikke «Q3 2026» eller
# «PRESS RELEASE».
_GENERISK_PREFIKS = re.compile(r"\d|press release|pressemelding|børsmelding|"
                               r"quarter|kvartal|result|report|rapport|"
                               r"correction|korreksjon|korrigering|rettelse", re.I)


def er_rapporttittel(tittel):
    t = tittel or ""
    return bool(_PERIODE_ORD.search(t) and _RESULTAT_ORD.search(t) and not _IKKE_RAPPORT.search(t))


def aldri_rapport(tittel):
    """Tittelen kan ikke være rapporten, uansett hvor id-en kommer fra.

    En ren utbyttemelding («Quarterly dividend») har ikke et eneste resultatord.
    """
    t = tittel or ""
    return bool(_ALDRI_RAPPORT.search(t)
                or (_UTBYTTE_ORD.search(t) and not _RESULTAT_ORD.search(t)))


def annet_selskaps_rapport(tittel, ticker, navn):
    """«Grameenphone - results for the third quarter 2026» under Telenor.

    Bare et prefiks som ser ut som et selskapsnavn sammenlignes, så «Q3 2026:
    KONGSBERG …» og «PRESS RELEASE: …» aldri teller som et annet selskap.
    """
    # «Fremtind Holding-konsernets resultater …» under MING og NONG: Fremtind er
    # et forsikringsselskap bankene eier sammen, ikke banken selv.
    m = (re.match(r"\s*([^:]{2,80}?)\s*(?::|\s[-–]\s)", tittel or "")
         or re.match(r"\s*([^:\d]{2,80}?)-konsern", tittel or "", re.I))
    if not m or _GENERISK_PREFIKS.search(m.group(1)) or not navn:
        return False
    # «ABGSC - Q3 2026 Interim Report»: en forkortelse som begynner med tickeren.
    forkortelse = m.group(1).strip().upper()
    if ticker and (forkortelse.startswith(ticker.upper()) or ticker.upper().startswith(forkortelse)):
        return False
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fetch_stocks as fs
    prefiks = m.group(1).split("(")[0].strip()
    if fs._kort_selskapsnavn(prefiks).strip().lower() == (ticker or "").lower():
        return False
    return fs.melding_gjelder_annet_selskap(prefiks + ":", "", ticker, navn)


def hendelse_ider(hendelser, ticker):
    """Id-ene til rapportmeldingene oppdater_hendelser.py har koblet til tickeren.

    DNB kaller rapporten «Solid results across operations in the Nordics», og
    Vår Energi «… reports strong financial results …». Ingen av titlene sier
    hvilket kvartal, så tittelen alene finner dem ikke. Rapportdatoen gjør det.
    """
    ut = set()
    for h in hendelser or []:
        if h.get("ticker") == ticker and h.get("type") == "rapport" and h.get("url"):
            m = re.search(r"/message/(\d+)", h["url"])
            if m:
                ut.add(m.group(1))
    return ut


def rapportmeldinger(meldinger, ider=(), ticker="", navn=""):
    """[{dato, ider, titler}] for rapportene i meldingslista, nyeste først.

    En rapport kommer ofte i to meldinger samme dag (norsk og engelsk, som
    Equinor), så de grupperes per dato.
    """
    per_dato = {}
    for m in meldinger or []:
        mid = str(m.get("messageId") or m.get("id") or "")
        tittel = (m.get("title") or "").strip()
        if not mid or not (er_rapporttittel(tittel) or mid in ider):
            continue
        if aldri_rapport(tittel) or annet_selskaps_rapport(tittel, ticker, navn):
            continue
        dato = (m.get("publishedTime") or "")[:10]
        g = per_dato.setdefault(dato, {"dato": dato, "ider": [], "titler": []})
        g["ider"].append(mid)
        g["titler"].append(tittel)
    return sorted(per_dato.values(), key=lambda g: g["dato"], reverse=True)


def venter(lagret, rapporter, i_dag=None, dager=KO_DAGER):
    """Nyeste rapport uten oppsummering, eller None. Ren funksjon.

    `lagret` er oppsummeringene for tickeren, `rapporter` fra rapportmeldinger().
    En rapport er dekket når en oppsummering bygger på en av meldingene, eller
    er skrevet for en rapport lagt fram samme dag eller senere.
    """
    if not rapporter:
        return None
    nyeste = rapporter[0]
    i_dag = i_dag or datetime.date.today()
    try:
        alder = (i_dag - datetime.date.fromisoformat(nyeste["dato"])).days
    except ValueError:
        return None
    if alder > dager:
        return None
    for r in lagret or []:
        if str(r.get("melding")) in nyeste["ider"] or (r.get("dato") or "") >= nyeste["dato"]:
            return None
    return nyeste


def _b_aksjer():
    """{B-aksje: A-aksje}. B-aksjene melder under A-aksjen og får ingen egen side."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from fetch_stocks import _NEWSWEB_UTSTEDER_EKSTRA
        return dict(_NEWSWEB_UTSTEDER_EKSTRA)
    except Exception:
        return {"ODFB": "ODF", "WWIB": "WWI"}


def ko(tickere=None, dager=KO_DAGER):
    """[(ticker, rapport)] som venter på oppsummering. Henter fra NewsWeb."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fetch_stocks as fs
    try:
        with open(HENDELSER_FIL, encoding="utf-8") as f:
            hendelser = json.load(f).get("hendelser", [])
    except (OSError, ValueError):
        hendelser = []
    lagret = les_rapporter()
    b = _b_aksjer()
    try:
        with open(TICKERS_FIL, encoding="utf-8") as f:
            navn = {t["ticker"]: t.get("navn", "") for t in json.load(f)}
    except (OSError, ValueError):
        navn = {}
    if not tickere:
        # Største selskaper først: de får flest søk.
        try:
            with open(os.path.join(ROT, "data", "aksjer.json"), encoding="utf-8") as f:
                rader = json.load(f)["aksjer"]
            tickere = [a["ticker"] for a in sorted(
                rader, key=lambda a: -(a.get("markedsverdi_mrd") or 0))]
        except (OSError, ValueError, KeyError):
            with open(TICKERS_FIL, encoding="utf-8") as f:
                tickere = [t["ticker"] for t in json.load(f)]
    ut, feilet = [], []
    for t in tickere:
        if t in b:
            continue
        try:
            meldinger = fs._newsweb_meldinger(t)
        except Exception as e:
            feilet.append((t, str(e)))
            continue
        r = venter(lagret.get(t), rapportmeldinger(meldinger, hendelse_ider(hendelser, t),
                                                   t, navn.get(t, "")),
                   dager=dager)
        if r:
            ut.append((t, r))
    return ut, feilet


# ── Kilden: meldingen og rapporten som tekst ─────────────────────────────────

def _html_til_tekst(body):
    t = re.sub(r"<(br|/p|/li|/tr|/h\d)\b[^>]*>", "\n", body or "", flags=re.I)
    t = re.sub(r"<li\b[^>]*>", "\n* ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t ]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()


_IKKE_HOVEDVEDLEGG = re.compile(r"presentation|presentasjon|factbook|fact book|webcast|"
                                r"transcript|slides", re.I)
_HOVEDVEDLEGG = re.compile(r"report|rapport|statements|review|interim|quarter|kvartal|"
                           r"results|resultat|regnskap", re.I)


def hovedvedlegg(vedlegg):
    """Rapporten blant vedleggene, eller None: ikke presentasjonen, ikke faktaboka."""
    pdf = [v for v in vedlegg or [] if (v.get("name") or "").lower().endswith(".pdf")]
    kandidater = [v for v in pdf if not _IKKE_HOVEDVEDLEGG.search(v.get("name") or "")]
    for v in kandidater:
        if _HOVEDVEDLEGG.search(v.get("name") or ""):
            return v
    return kandidater[0] if kandidater else None


def _hent_pdf_tekst(api, melding_id, vedlegg_id, sider):
    if not shutil.which("pdftotext"):
        return None, "pdftotext finnes ikke (apt-get install poppler-utils)"
    url = (f"{api}/v1/newsreader/attachment?messageId={urllib.parse.quote(str(melding_id))}"
           f"&attachmentId={urllib.parse.quote(str(vedlegg_id))}")
    with tempfile.TemporaryDirectory() as d:
        sti = os.path.join(d, "rapport.pdf")
        req = urllib.request.Request(url, headers={"Accept": "application/pdf"})
        with urllib.request.urlopen(req, timeout=60) as r, open(sti, "wb") as f:
            shutil.copyfileobj(r, f)
        res = subprocess.run(["pdftotext", "-layout", "-f", "1", "-l", str(sider), sti, "-"],
                             capture_output=True, text=True, timeout=120)
        if res.returncode != 0:
            return None, res.stderr.strip()[:200]
        return res.stdout, None


_UTBYTTEMELDING = re.compile(
    r"(?:key information|nøkkelinformasjon).{0,60}(?:dividend|utbytte|distribution|utdeling)"
    # Mowi kaller utbyttemeldingen «Quarterly dividend» (680022, 685530).
    r"|(?:quarterly|interim|kvartalsvis)\s+(?:dividend|utbytte)\s*$"
    # NorAm Drilling: «Monthly rig update and key information for November 2026»
    # (686141) bærer månedens utdeling uten at tittelen sier det.
    r"|monthly\s+rig\s+update\s+and\s+key\s+information", re.I)
_NORSK_TITTEL = re.compile(r"nøkkelinformasjon|utbytte", re.I)
# Et engangsutbytte er ikke noe å sammenligne det ordinære med. Frontlines
# melding før Q3-rapporten gjaldt særutbyttet etter salget av to VLCC-er
# (682181), og den ordinære for andre kvartal lå bak den (681123).
_ENGANGS_TITTEL = re.compile(r"special|one[- ]time|extraordinary|additional|"
                             r"ekstraordinær|særutbytte|tilleggsutbytte", re.I)


def utbyttemeldinger(meldinger, dato, dager_etter=3):
    """Id-ene til utbyttemeldingene («Key information …») som hører til rapporten.

    Rapporten oppgir ofte bare totalbeløpet. Vår Energi skrev «USD 400
    million» for tredje kvartal 2026, og agenten skrev «øker utbyttet til 400
    millioner dollar». Per aksje var det 1,368 kroner mot 1,355 i andre
    kvartal: totalen steg fordi utbyttet også skulle deles på aksjene til
    BlueNords eiere. Beløpet per aksje står i utbyttemeldingen samme dag.

    Gir én melding per dag fra dagen før rapporten til `dager_etter` etter,
    pluss den nyeste før det, så beløpet kan sammenlignes med forrige utbytte.
    """
    try:
        d0 = datetime.date.fromisoformat(dato[:10])
    except (TypeError, ValueError):
        return []
    fra, til = (d0 - datetime.timedelta(days=1)).isoformat(), (d0 + datetime.timedelta(days=dager_etter)).isoformat()
    treff = [m for m in meldinger or [] if _UTBYTTEMELDING.search(m.get("title") or "")]
    # Én dag kan ha flere utbytter (Gjensidige: ordinært og særutbytte), men
    # også samme melding på norsk og engelsk (Equinor). Den norske tas bare
    # med når dagen ikke har en engelsk.
    engelsk_dager = {(m.get("publishedTime") or "")[:10] for m in treff
                     if not _NORSK_TITTEL.search(m.get("title") or "")}
    i_vinduet, forrige, forrige_engangs = [], [], False
    for m in treff:   # NewsWeb gir nyeste først
        tittel = m.get("title") or ""
        dag = (m.get("publishedTime") or "")[:10]
        mid = str(m.get("messageId") or m.get("id") or "")
        if dag in engelsk_dager and _NORSK_TITTEL.search(tittel):
            continue
        if fra <= dag <= til:
            i_vinduet.append(mid)
        elif dag < fra and (not forrige or (len(forrige) == 1 and forrige_engangs)):
            forrige.append(mid)
            forrige_engangs = bool(_ENGANGS_TITTEL.search(tittel))
    return i_vinduet + forrige


def hent_kilde(ticker, melding_ider=None, sider=KILDE_SIDER, med_utbytte=True):
    """(tekst, ider). Meldingene og hovedvedlegget til den første, som én tekst.

    Utbyttemeldingene som hører til rapporten tas med (utbyttemeldinger()),
    med mindre `med_utbytte` er False.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fetch_stocks as fs
    api = fs._newsweb_api_base()
    if not melding_ider:
        try:
            with open(HENDELSER_FIL, encoding="utf-8") as f:
                hendelser = json.load(f).get("hendelser", [])
        except (OSError, ValueError):
            hendelser = []
        rapporter = rapportmeldinger(fs._newsweb_meldinger(ticker), hendelse_ider(hendelser, ticker))
        if not rapporter:
            raise SystemExit(f"Fant ingen rapportmelding for {ticker}. Oppgi --melding ID.")
        melding_ider = rapporter[0]["ider"]
    melding_ider = [str(m) for m in melding_ider]
    if med_utbytte:
        try:
            liste = fs._newsweb_meldinger(ticker)
            dato = next(((m.get("publishedTime") or "")[:10] for m in liste
                         if str(m.get("messageId")) == melding_ider[0]), "")
            melding_ider += [m for m in utbyttemeldinger(liste, dato) if m not in melding_ider]
        except Exception as e:
            print(f"  Utbyttemeldingene kunne ikke hentes: {e}", file=sys.stderr)
    deler, ider, pdf_tatt, publisert = [], [], False, ""
    hode = [f"# exday kilde", f"# ticker: {ticker}"]
    for mid in melding_ider:
        full = fs._newsweb_get(f"{api}/v1/newsreader/message?messageId={urllib.parse.quote(str(mid))}")
        m = full.get("data", {}).get("message", {}) or {}
        if (m.get("issuerSign") or "").upper() not in {ticker.upper(), fs._newsweb_utsteder(ticker).upper()}:
            raise SystemExit(f"Melding {mid} er fra {m.get('issuerSign')}, ikke {ticker}.")
        ider.append(str(mid))
        dato = (m.get("publishedTime") or "")[:10]
        publisert = publisert or dato
        deler.append(f"=== MELDING {mid}: {m.get('title', '').strip()} ({dato}) ===\n\n"
                     f"{_html_til_tekst(m.get('body'))}")
        v = hovedvedlegg(m.get("attachments"))
        if v and not pdf_tatt:
            tekst, feil = _hent_pdf_tekst(api, mid, v.get("id"), sider)
            if tekst:
                pdf_tatt = True
                hode.append(f"# vedlegg: {v.get('id')} {v.get('name')} (side 1–{sider})")
                deler.append(f"=== VEDLEGG {v.get('id')}: {v.get('name')} (side 1–{sider}) ===\n\n{tekst}")
            else:
                hode.append(f"# vedlegg: {v.get('name')} kunne ikke leses: {feil}")
    hode.insert(2, f"# meldinger: {' '.join(ider)}")
    if publisert:
        hode.insert(3, f"# publisert: {publisert}")
    hode.append(f"# hentet: {datetime.date.today().isoformat()}")
    return "\n".join(hode) + "\n\n" + "\n\n".join(deler) + "\n", ider


def meldinger_i_kilde(kildetekst):
    m = re.search(r"^# meldinger: ([\d ]+)$", kildetekst or "", re.M)
    return m.group(1).split() if m else []


# ── Kommandolinje ────────────────────────────────────────────────────────────

def _skriv(ticker, json_sti, kilde_sti):
    with open(json_sti, encoding="utf-8") as f:
        rapport = json.load(f)
    with open(kilde_sti, encoding="utf-8") as f:
        kilde = f.read()
    rapport.setdefault("skrevet", datetime.date.today().isoformat())
    rapport["melding"] = str(rapport.get("melding") or "")
    feil, varsler = vurder_oppsummering(ticker, rapport, kilde, meldinger_i_kilde(kilde),
                                        forrige=forrige_lagrede(ticker, rapport))
    for v in varsler:
        print(f"  varsel: {v}")
    if feil:
        print(f"IKKE LAGRET {ticker} {rapport.get('periode')}:")
        for f_ in feil:
            print(f"  - {f_}")
        return 1
    sti = lagre(ticker, rapport)
    print(f"LAGRET {ticker} {periode_tekst(rapport['periode'])} → {os.path.relpath(sti, ROT)}")
    return 0


def _sjekk_alle(streng):
    alle = les_rapporter()
    antall_feil = 0
    for ticker, liste in sorted(alle.items()):
        for r in liste:
            feil, varsler = vurder_oppsummering(ticker, r)
            if feil:
                antall_feil += 1
                print(f"{ticker} {r.get('periode')}:")
                for f_ in feil:
                    print(f"  - {f_}")
    n = sum(len(v) for v in alle.values())
    print(f"{n} oppsummeringer for {len(alle)} selskaper, {antall_feil} med feil.")
    return 1 if (streng and antall_feil) else 0


def main(argv=None):
    p = argparse.ArgumentParser(description="Oppsummeringer av kvartalsrapporter.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ko", action="store_true", help="rapporter som venter på oppsummering")
    g.add_argument("--kilde", metavar="TICKER", help="hent meldingen og rapporten som tekst")
    g.add_argument("--skriv", nargs=3, metavar=("TICKER", "JSON", "KILDE"),
                   help="lagre en oppsummering hvis den består kontrollen")
    g.add_argument("--sjekk", action="store_true", help="sjekk alle lagrede, uten nett")
    p.add_argument("--ticker", nargs="+", help="bare disse (med --ko)")
    p.add_argument("--dager", type=int, default=KO_DAGER, help="hvor langt tilbake --ko ser")
    p.add_argument("--melding", nargs="+", metavar="ID", help="meldings-id-er (med --kilde)")
    p.add_argument("--sider", type=int, default=KILDE_SIDER, help="sider av PDF-rapporten")
    p.add_argument("--ut", help="fil kilden skrives til (med --kilde)")
    p.add_argument("--uten-utbytte", action="store_true",
                   help="ikke ta med utbyttemeldingene (med --kilde)")
    p.add_argument("--streng", action="store_true", help="exit 1 ved feil (med --sjekk)")
    a = p.parse_args(argv)

    if a.sjekk:
        return _sjekk_alle(a.streng)
    if a.skriv:
        return _skriv(a.skriv[0].upper(), a.skriv[1], a.skriv[2])
    if a.kilde:
        tekst, ider = hent_kilde(a.kilde.upper(), a.melding, a.sider, not a.uten_utbytte)
        ut = a.ut or os.path.join(tempfile.gettempdir(), f"kilde_{a.kilde.upper()}_{ider[0]}.txt")
        with open(ut, "w", encoding="utf-8") as f:
            f.write(tekst)
        print(f"Kilde for {a.kilde.upper()} (meldinger {' '.join(ider)}): {ut}")
        print(f"{len(tekst.split())} ord, {len(tall_i_kilde(tekst))} ulike tallverdier")
        return 0
    if a.ko:
        venter_, feilet = ko([t.upper() for t in a.ticker] if a.ticker else None, a.dager)
        for t, r in sorted(venter_, key=lambda x: x[1]["dato"], reverse=True):
            print(f"{r['dato']}  {t:<7} {' '.join(r['ider'])}  {r['titler'][0][:80]}")
        print(f"\n{len(venter_)} rapporter venter på oppsummering.")
        if feilet:
            print(f"NewsWeb svarte ikke for {len(feilet)}: {', '.join(t for t, _ in feilet)}")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
