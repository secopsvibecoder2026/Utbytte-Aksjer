#!/usr/bin/env python3
"""SEO for exday.no: tall fra Search Console og sjekk av sidene på disk.

    python scripts/seo.py --eksport FIL.zip                 # en eksport fra Search Console
    python scripts/seo.py --eksport NY.zip --mot GAMMEL.zip # sammenlign to perioder
    python scripts/seo.py --sider                           # titler, meta, sitemap, lenker
    python scripts/seo.py --sider --streng                  # avslutt 1 ved feil

Search Console-tallene kommer bare fra en eksport eieren laster opp (Resultater,
Eksporter, CSV). Skriptet leser zip-filen eller mappen og skriver tabeller. Det
lagrer ingenting: repoet er offentlig, og søkeord, klikk og posisjoner skal aldri
committes.

Sidesjekken leser HTML-en som ligger i repoet og trenger ikke nett.

Begge deler er rene funksjoner som testes i test_seo.py.
"""

import csv
import io
import json
import os
import re
import statistics
import sys
import zipfile
from collections import defaultdict
from html import unescape

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMENE = "https://exday.no"

# Google klipper titler rundt 60 tegn og beskrivelser rundt 155 på mobil.
TITTEL_MAKS = 60
META_MAKS = 155
META_MIN = 70

# Mapper som ikke er en del av nettstedet (se _config.yml).
HOPP_OVER = {".git", ".claude", "node_modules", "scripts", "tests", "promo",
             "test-results", "playwright-report", "data"}


# ── Search Console-eksporten ────────────────────────────────────────────

_KOLONNER = {
    "klikk": ("clicks", "klikk"),
    "visninger": ("impressions", "visninger"),
    "ctr": ("ctr", "klikkfrekvens"),
    "posisjon": ("position", "plassering", "posisjon", "gjennomsnittlig plassering"),
}


def tall(s):
    """«1.2%», «1,2 %», «9278», «12.98» → float. Tom eller ukjent → 0."""
    s = (s or "").strip().replace(" ", "").replace(" ", "")
    pst = s.endswith("%")
    s = s.rstrip("%").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return 0.0
    return v / 100 if pst else v


def _art(forste_kolonne):
    """Hva en CSV fra eksporten inneholder, ut fra overskriften i første kolonne."""
    k = forste_kolonne.lower()
    if "quer" in k or "søk" in k or "spørring" in k:
        return "sok"
    if "page" in k or "side" in k:
        return "sider"
    if k in ("date", "dato"):
        return "dager"
    if k in ("filter",):
        return "filtre"
    return None


def les_csv(tekst):
    """Rader som dict med nøkkel, klikk, visninger, ctr og posisjon."""
    r = list(csv.reader(io.StringIO(tekst.lstrip("﻿"))))
    if not r:
        return None, []
    hode = [h.strip().lower() for h in r[0]]
    art = _art(hode[0])
    idx = {}
    for navn, alias in _KOLONNER.items():
        for i, h in enumerate(hode):
            if h in alias:
                idx[navn] = i
    rader = []
    for rad in r[1:]:
        if not rad or not rad[0].strip():
            continue
        if art == "filtre":
            rader.append({"filter": rad[0], "verdi": rad[1] if len(rad) > 1 else ""})
            continue
        d = {"nokkel": rad[0].strip()}
        for navn, i in idx.items():
            d[navn] = tall(rad[i]) if i < len(rad) else 0.0
        rader.append(d)
    return art, rader


def les_eksport(sti):
    """{'sok': [...], 'sider': [...], 'dager': [...], 'filtre': [...]} fra zip eller mappe."""
    filer = {}
    if os.path.isdir(sti):
        for n in os.listdir(sti):
            if n.lower().endswith(".csv"):
                with open(os.path.join(sti, n), encoding="utf-8-sig") as f:
                    filer[n] = f.read()
    else:
        with zipfile.ZipFile(sti) as z:
            for n in z.namelist():
                if n.lower().endswith(".csv"):
                    filer[n] = z.read(n).decode("utf-8-sig")
    ut = {"sok": [], "sider": [], "dager": [], "filtre": []}
    for tekst in filer.values():
        art, rader = les_csv(tekst)
        if art:
            ut[art] = rader
    return ut


def sidegruppe(url):
    """Hvilken mal eller sidetype en URL hører til."""
    sti = re.sub(r"^https?://[^/]+", "", url).split("?")[0].split("#")[0] or "/"
    if sti == "/":
        return "forside"
    if re.match(r"^/aksjer/[^/]+/rapporter/", sti):
        return "rapportside"
    if sti.startswith("/aksjer/sektor/"):
        return "sektor"
    if re.match(r"^/aksjer/[A-Z0-9]{1,10}/$", sti):
        return "aksjeside"
    if sti.startswith("/aksjer/"):
        return "aksjelister"
    for prefiks, navn in (("/artikler/", "artikkel"), ("/utbyttekalender/", "utbyttekalender"),
                          ("/rapportkalender/", "rapportkalender"), ("/verktoy/", "verktoy"),
                          ("/app/", "app")):
        if sti.startswith(prefiks):
            return navn
    return "annet"


def summer(rader):
    """Klikk, visninger, CTR og visningsvektet snittposisjon."""
    k = sum(r.get("klikk", 0) for r in rader)
    v = sum(r.get("visninger", 0) for r in rader)
    pos = (sum(r.get("posisjon", 0) * r.get("visninger", 0) for r in rader) / v) if v else 0.0
    return {"klikk": k, "visninger": v, "ctr": (k / v) if v else 0.0, "posisjon": pos}


def per_gruppe(sider):
    g = defaultdict(list)
    for r in sider:
        g[sidegruppe(r["nokkel"])].append(r)
    return {navn: dict(summer(rader), antall=len(rader)) for navn, rader in g.items()}


def posisjonsbånd(pos):
    """Bånd for å sammenligne CTR med rader som står omtrent like høyt."""
    for grense, navn in ((1.5, "1"), (2.5, "2"), (3.5, "3"), (5.5, "4-5"), (7.5, "6-7"),
                         (10.5, "8-10"), (15.5, "11-15"), (20.5, "16-20")):
        if pos < grense:
            return navn
    return "21+"


def lav_ctr(rader, min_visninger=100, andel=0.5):
    """Rader med CTR under `andel` av medianen i sitt posisjonsbånd, i egne data.

    Medianen er målt på nettstedets egne rader med minst `min_visninger`, så
    sammenligningen er mot det samme nettstedet og ikke mot en bransjekurve.
    Sortert etter tapte klikk: visninger × (median − ctr).
    """
    med = [r for r in rader if r.get("visninger", 0) >= min_visninger]
    bånd = defaultdict(list)
    for r in med:
        bånd[posisjonsbånd(r["posisjon"])].append(r["ctr"])
    median = {b: statistics.median(v) for b, v in bånd.items() if len(v) >= 3}
    ut = []
    for r in med:
        m = median.get(posisjonsbånd(r["posisjon"]))
        if m and r["ctr"] < m * andel:
            ut.append(dict(r, median_ctr=m, tapte_klikk=r["visninger"] * (m - r["ctr"])))
    return sorted(ut, key=lambda r: -r["tapte_klikk"])


def nesten_forsteside(rader, min_visninger=100, fra=8.0, til=20.0):
    """Rader på plass 8 til 20 med mange visninger: et lite løft gir mye."""
    return sorted((r for r in rader if r.get("visninger", 0) >= min_visninger
                   and fra <= r.get("posisjon", 0) <= til), key=lambda r: -r["visninger"])


def sammenlign(ny, gammel):
    """Endring per side mellom to eksporter: {url: {klikk, visninger, ctr, posisjon} som (gammel, ny)}."""
    g = {r["nokkel"]: r for r in gammel}
    ut = {}
    for r in ny:
        a = g.get(r["nokkel"])
        if a:
            ut[r["nokkel"]] = {k: (a.get(k, 0), r.get(k, 0)) for k in ("klikk", "visninger", "ctr", "posisjon")}
    return ut


def periode(eksport):
    for r in eksport.get("filtre", []):
        if r["filter"].lower() in ("date", "dato"):
            return r["verdi"]
    d = [r["nokkel"] for r in eksport.get("dager", [])]
    return f"{min(d)} til {max(d)}" if d else "ukjent"


# ── Sidene på disk ──────────────────────────────────────────────────────

_TITTEL = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_META = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.I)
_KANON = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"', re.I)
_ROBOTS = re.compile(r'<meta\s+name="robots"\s+content="([^"]*)"', re.I)
_REFRESH = re.compile(r'<meta\s+http-equiv="refresh"', re.I)
_JSONLD = re.compile(r'<script\s+type="application/ld\+json">(.*?)</script>', re.S | re.I)
_H1 = re.compile(r"<h1[\s>]", re.I)
_LENKE = re.compile(r'href="(/[^"#?]*)')


def url_for(rel):
    """«aksjer/EQNR/index.html» → «https://exday.no/aksjer/EQNR/»."""
    rel = rel.replace(os.sep, "/")
    if rel == "index.html":
        return DOMENE + "/"
    return DOMENE + "/" + rel[: -len("index.html")]


def les_side(html):
    t = _TITTEL.search(html)
    m = _META.search(html)
    k = _KANON.search(html)
    r = _ROBOTS.search(html)
    jsonld_feil = 0
    for blokk in _JSONLD.findall(html):
        try:
            json.loads(blokk)
        except ValueError:
            jsonld_feil += 1
    return {
        "tittel": unescape(re.sub(r"\s+", " ", t.group(1)).strip()) if t else "",
        "meta": unescape(m.group(1)).strip() if m else "",
        "kanonisk": k.group(1) if k else "",
        "noindex": bool(r and "noindex" in r.group(1).lower()),
        "omdirigering": bool(_REFRESH.search(html)),
        "jsonld_feil": jsonld_feil,
        "h1": len(_H1.findall(html)),
        "lenker": set(_LENKE.findall(html)),
    }


def finn_sider(rot):
    """{url: info} for hver index.html som hører til nettstedet."""
    sider = {}
    for mappe, undermapper, filer in os.walk(rot):
        undermapper[:] = [d for d in undermapper if d not in HOPP_OVER and not d.startswith(".")]
        if "index.html" in filer:
            sti = os.path.join(mappe, "index.html")
            with open(sti, encoding="utf-8") as f:
                sider[url_for(os.path.relpath(sti, rot))] = les_side(f.read())
    return sider


def les_sitemap(rot):
    sti = os.path.join(rot, "sitemap.xml")
    if not os.path.exists(sti):
        return set()
    with open(sti, encoding="utf-8") as f:
        return set(re.findall(r"<loc>([^<]+)</loc>", f.read()))


def sjekk_sider(sider, sitemap):
    """Funn per type. Omdirigeringssider er bare med i sitemap-sjekken."""
    funn = defaultdict(list)
    ekte = {u: s for u, s in sider.items() if not s["omdirigering"]}
    indekserbare = {u: s for u, s in ekte.items() if not s["noindex"]}
    titler, metaer = defaultdict(list), defaultdict(list)
    for u, s in indekserbare.items():
        if not s["tittel"]:
            funn["uten tittel"].append(u)
        elif len(s["tittel"]) > TITTEL_MAKS:
            funn["tittel over 60 tegn"].append(f"{u} ({len(s['tittel'])})")
        if not s["meta"]:
            funn["uten metabeskrivelse"].append(u)
        elif len(s["meta"]) > META_MAKS:
            funn["meta over 155 tegn"].append(f"{u} ({len(s['meta'])})")
        elif len(s["meta"]) < META_MIN:
            funn["meta under 70 tegn"].append(f"{u} ({len(s['meta'])})")
        if s["kanonisk"] and s["kanonisk"] != u:
            funn["kanonisk peker et annet sted"].append(f"{u} → {s['kanonisk']}")
        if not s["kanonisk"]:
            funn["uten kanonisk"].append(u)
        if s["h1"] != 1:
            funn["ikke én h1"].append(f"{u} ({s['h1']})")
        if s["jsonld_feil"]:
            funn["JSON-LD som ikke kan leses"].append(u)
        if s["tittel"]:
            titler[s["tittel"]].append(u)
        if s["meta"]:
            metaer[s["meta"]].append(u)
        if u not in sitemap:
            funn["indekserbar, men ikke i sitemap"].append(u)
    for t, us in titler.items():
        if len(us) > 1:
            funn["lik tittel"].append(f"«{t}»: {', '.join(sorted(us))}")
    for m, us in metaer.items():
        if len(us) > 1:
            funn["lik metabeskrivelse"].append(", ".join(sorted(us)))
    for u in sorted(sitemap):
        if u not in sider:
            funn["i sitemap, men ingen side på disk"].append(u)
        elif sider[u]["noindex"]:
            funn["noindex, men i sitemap"].append(u)
        elif sider[u]["omdirigering"]:
            funn["omdirigering i sitemap"].append(u)
    # Innkommende interne lenker: en side ingen andre sider lenker til, er en
    # foreldreløs side, og Google finner den bare gjennom sitemapen.
    inn = defaultdict(int)
    for u, s in ekte.items():
        sti_u = u[len(DOMENE):]
        for lenke in s["lenker"]:
            if lenke != sti_u:
                inn[DOMENE + lenke] += 1
    for u in sorted(indekserbare):
        if inn[u] == 0 and u != DOMENE + "/":
            funn["ingen interne lenker inn"].append(u)
    return dict(funn), dict(inn)


# ── Utskrift ────────────────────────────────────────────────────────────

def _nf(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def _pst(x):
    return _nf(x * 100) + " %"


def _rad(r):
    return (f"{r['nokkel'][:70]:70}  {int(r['klikk']):>5}  {int(r['visninger']):>7}  "
            f"{_pst(r['ctr']):>7}  {_nf(r['posisjon']):>5}")


def skriv_eksport(eksport, gammel=None, min_visninger=100, antall=20):
    print(f"Periode: {periode(eksport)}")
    tot = summer(eksport["dager"] or eksport["sider"])
    print(f"Totalt: {int(tot['klikk'])} klikk, {int(tot['visninger'])} visninger, "
          f"CTR {_pst(tot['ctr'])}, snittposisjon {_nf(tot['posisjon'])}")
    print("\nPer sidetype (fra Pages):")
    for navn, s in sorted(per_gruppe(eksport["sider"]).items(), key=lambda x: -x[1]["klikk"]):
        print(f"  {navn:16} {s['antall']:>4} sider  {int(s['klikk']):>5} klikk  "
              f"{int(s['visninger']):>7} visn.  CTR {_pst(s['ctr']):>7}  pos {_nf(s['posisjon'])}")
    for tittel, rader in (("Søk med lav CTR for plasseringen", lav_ctr(eksport["sok"], min_visninger)),
                          ("Sider med lav CTR for plasseringen", lav_ctr(eksport["sider"], min_visninger)),
                          ("Søk på plass 8 til 20", nesten_forsteside(eksport["sok"], min_visninger)),
                          ("Sider på plass 8 til 20", nesten_forsteside(eksport["sider"], min_visninger))):
        print(f"\n{tittel} (minst {min_visninger} visninger):")
        for r in rader[:antall]:
            print("  " + _rad(r))
        if not rader:
            print("  ingen")
    if gammel:
        print(f"\nMot forrige eksport ({periode(gammel)}):")
        endr = sammenlign(eksport["sider"], gammel["sider"])
        a, b = summer(gammel["sider"]), summer(eksport["sider"])
        print(f"  alle sider: klikk {int(a['klikk'])} → {int(b['klikk'])}, "
              f"CTR {_pst(a['ctr'])} → {_pst(b['ctr'])}")
        topp = sorted(endr.items(), key=lambda x: -abs(x[1]["klikk"][1] - x[1]["klikk"][0]))[:antall]
        for u, e in topp:
            print(f"  {u[:70]:70}  klikk {int(e['klikk'][0])} → {int(e['klikk'][1])}  "
                  f"pos {_nf(e['posisjon'][0])} → {_nf(e['posisjon'][1])}")


def skriv_sider(funn, inn, antall=15):
    if not funn:
        print("Ingen funn.")
    for navn, liste in sorted(funn.items(), key=lambda x: -len(x[1])):
        print(f"\n{navn}: {len(liste)}")
        for u in liste[:antall]:
            print(f"  {u}")
        if len(liste) > antall:
            print(f"  … og {len(liste) - antall} til")
    rapport = sorted((n, u) for u, n in inn.items() if "/rapporter/" in u)
    if rapport:
        null = sum(1 for n, _ in rapport if n == 0)
        print(f"\nRapportsider: {len(rapport)} med lenker inn, {null} med ingen")


def main(argv):
    if "--eksport" in argv:
        sti = argv[argv.index("--eksport") + 1]
        gammel = les_eksport(argv[argv.index("--mot") + 1]) if "--mot" in argv else None
        mv = int(argv[argv.index("--min-visninger") + 1]) if "--min-visninger" in argv else 100
        skriv_eksport(les_eksport(sti), gammel, mv)
        return 0
    if "--sider" in argv:
        funn, inn = sjekk_sider(finn_sider(ROT), les_sitemap(ROT))
        skriv_sider(funn, inn)
        alvorlige = ("uten tittel", "i sitemap, men ingen side på disk", "noindex, men i sitemap",
                     "JSON-LD som ikke kan leses", "kanonisk peker et annet sted")
        return 1 if "--streng" in argv and any(funn.get(n) for n in alvorlige) else 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
