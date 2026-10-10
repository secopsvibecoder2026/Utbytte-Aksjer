#!/usr/bin/env python3
"""
vedlikehold.py — den maskinelle delen av den daglige vedlikeholdsrunden.

Brukes av agenten `.claude/agents/vedlikehold.md`, men kan kjøres for hånd:

    python scripts/vedlikehold.py                  # siste 3 dager, som tekst
    python scripts/vedlikehold.py --dager 35       # bredere søk etter nye utbyttebetalere
    python scripts/vedlikehold.py --json           # maskinlesbart
    python scripts/vedlikehold.py --uten-nett      # bare filene i repoet
    python scripts/vedlikehold.py --melding 683894 # teksten i én børsmelding

Leser bare. Skriver aldri til data/ eller sidene.

Hvorfor: `sjekk_utdaterte.py` ser at en aksje er borte først når den *er*
borte — Euronext har strøket den, eller Yahoo har sluttet å svare. Det er en
etterpåklokskap. Selskapene melder det på forhånd: et anbefalt bud, en
fusjonsplan, «last day of trading», en søknad om å flytte til Euronext Growth.
Og ingenting i prosjektet så etter nye utbyttebetalere i det hele tatt.

Alt kommer fra kilder skriptet ikke eier, og hver del svarer `None` når
kilden ikke svarer. `None` betyr «vi vet ikke», aldri «ingenting å melde»,
samme skille som `_les_euronext_csv()` gjør.

Funnene er titler, ikke konklusjoner. En tittel som nevner et bud sier ikke
at budet går gjennom; agenten leser meldingen før noe blir et forslag.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.parse
import urllib.request

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO = "secopsvibecoder2026/Utbytte-Aksjer"
NEWSWEB_MELDING_URL = "https://newsweb.oslobors.no/message/{}"

# NewsWeb returnerer høyst rundt 600 meldinger per kall, nyeste først, uten å
# si fra at lista er kuttet. Målt 10.10.2026: 30 dager ga 601 meldinger som
# bare rakk tilbake til 30. september. En hel børsdag er 90–160 meldinger,
# så tre dager per kall holder seg godt under taket.
NEWSWEB_DAGER_PER_KALL = 3
NEWSWEB_TAK = 550

# ── Mønstre for meldingstitler ────────────────────────────────────────────────
# Kalibrert mot NewsWeb 30.09–09.10.2026. Hvert mønster har et ekte eksempel i
# testene, og det samme gjelder titlene de ikke skal treffe.

# Avgjort: aksjen forsvinner fra børsen.
UT_VEDTATT = re.compile(
    r"last day of trading|siste (dag for )?handel|\bdelist|\bde-list|strykning|avnoter"
    r"|merger (is |has been )?completed"
    r"|fusjon(en)? (er )?gjennomført|compulsory acquisition|tvangsinnløs|squeeze[- ]?out",
    re.I)

# Mulig: noe er satt i gang som kan ende med at aksjen forsvinner.
UT_MULIG = re.compile(
    r"\btender offer\b|\b(voluntary|mandatory|recommended|unconditional)\b.{0,40}\boffer\b"
    r"|\boffer (for|to acquire) all\b|\bmandatory offer\b"
    r"|\b(frivillig|pliktig|anbefalt)\w*\b.{0,20}\btilbud\b"
    r"|\bmerger plan\b|fusjonsplan|\bagreed to merge\b",
    re.I)

# Børsen endres: Oslo Børs ↔ Euronext Growth/Expand. Avgjør ASK.
MARKED = re.compile(
    r"euronext growth|euronext expand|transfer (of (the )?listing|to euronext)|\buplist"
    r"|re-?listing|overføring (av notering|til)|flytt\w* (av )?notering",
    re.I)

NAVN = re.compile(
    r"new name|change of (company )?name|name change|navneendring|nytt (selskaps)?navn"
    r"|endring av (fore)?taksnavn|new ticker|ticker change|change of ticker|endring av ticker",
    re.I)

HANDELSSTANS = re.compile(r"trading (suspension|halt)|handelsstans|suspensjon", re.I)
HANDELSSTANS_KATEGORI = 1202

# Nye aksjer på børsen.
INN = re.compile(
    r"first day of trading|første handelsdag|admission to trading|opptak til handel"
    r"|approved for listing|godkjent for notering|listing on euronext|notering på euronext"
    r"|initial public offering|\bIPO\b|application for listing of shares"
    r"|søknad om notering av aksjer",
    re.I)
# «Listing prospectus» sto i begge mønstrene til første kjøring 10.10.2026:
# HOFSETH BIOCARE ASA: APPROVAL AND PUBLICATION OF LISTING PROSPECTUS var et
# prospekt for nye aksjer i et selskap som allerede er notert.

UTBYTTE = re.compile(
    r"dividend|utbytte|cash distribution|kapitalutdeling|distribution to shareholders"
    r"|return of (paid-in )?capital",
    re.I)

# Obligasjoner og sertifikater fyller NewsWeb (149 av 601 meldinger på 30
# dager var renteregulering), men er aldri en aksje vi kan ta inn.
IKKE_AKSJE = re.compile(
    r"\bbonds?\b|obligasjon|sertifikat|certificate|\bFRN\b|\bloan\b|\blån\b"
    r"|subscription rights|tegningsrett|warrant",
    re.I)
RENTE_KATEGORI = 1105


def _kategorier(m):
    return {c.get("id") for c in (m.get("category") or [])}


def _forenklet(m):
    return {
        "utsteder": (m.get("issuerSign") or "").upper(),
        "navn": m.get("issuerName") or "",
        "dato": (m.get("publishedTime") or "")[:10],
        "tittel": (m.get("title") or "").strip(),
        "id": m.get("messageId") or m.get("id"),
        "url": NEWSWEB_MELDING_URL.format(m.get("messageId") or m.get("id")),
    }


def utsteder_til_ticker(tickere):
    """{NewsWeb-utsteder: vår ticker}, med samme oversettelse som pipelinen.

    B-aksjer melder under A-aksjens utsteder (ODFB → ODF), så én utsteder kan
    gjelde flere av våre tickere. Verdien er derfor en liste.
    """
    try:
        from fetch_stocks import _newsweb_utsteder
    except Exception:
        def _newsweb_utsteder(t):
            return t
    kart = {}
    for t in tickere:
        kart.setdefault(_newsweb_utsteder(t).upper(), []).append(t)
    return kart


def klassifiser(meldinger, katalog, euronext_symboler=None):
    """Sorterer meldinger i det agenten skal se på. Ren funksjon, ingen nett.

    katalog            {utsteder: [våre tickere]}
    euronext_symboler  utstedere Euronext lister som aksjer, eller None når
                       lista ikke kunne hentes
    """
    ut = {"ut_vedtatt": [], "ut_mulig": [], "marked": [], "navn": [],
          "handelsstans": [], "nye_noteringer": [], "utbytte_utenfor_katalogen": []}
    kandidater = {}
    for m in meldinger:
        f = _forenklet(m)
        tittel, utsteder = f["tittel"], f["utsteder"]
        kat = _kategorier(m)
        if utsteder in katalog:
            f["tickere"] = katalog[utsteder]
            if UT_VEDTATT.search(tittel):
                ut["ut_vedtatt"].append(f)
            elif UT_MULIG.search(tittel):
                ut["ut_mulig"].append(f)
            if MARKED.search(tittel) and not IKKE_AKSJE.search(tittel):
                ut["marked"].append(f)
            if NAVN.search(tittel):
                ut["navn"].append(f)
            if HANDELSSTANS_KATEGORI in kat or HANDELSSTANS.search(tittel):
                ut["handelsstans"].append(f)
            continue
        if RENTE_KATEGORI in kat or IKKE_AKSJE.search(tittel):
            continue
        if INN.search(tittel):
            ut["nye_noteringer"].append(f)
        elif UTBYTTE.search(tittel) and utsteder:
            k = kandidater.setdefault(utsteder, {
                "utsteder": utsteder, "navn": f["navn"],
                "pa_euronext": (None if euronext_symboler is None
                                else utsteder in euronext_symboler),
                "meldinger": []})
            k["meldinger"].append(f)
    for k in kandidater.values():
        k["meldinger"].sort(key=lambda x: x["dato"], reverse=True)
        k["antall"] = len(k["meldinger"])
    ut["utbytte_utenfor_katalogen"] = sorted(
        kandidater.values(), key=lambda k: (-k["antall"], k["utsteder"]))
    for nokkel in ("ut_vedtatt", "ut_mulig", "marked", "navn", "handelsstans", "nye_noteringer"):
        ut[nokkel].sort(key=lambda x: x["dato"], reverse=True)
    return ut


def perioder(fra, til, dager=NEWSWEB_DAGER_PER_KALL):
    """Deler [fra, til] i biter på høyst `dager` dager, begge ender med."""
    biter = []
    start = fra
    while start <= til:
        slutt = min(til, start + datetime.timedelta(days=dager - 1))
        biter.append((start, slutt))
        start = slutt + datetime.timedelta(days=1)
    return biter


def hent_newsweb(fra, til):
    """Alle meldinger fra hele børsen i perioden, eller None ved feil."""
    try:
        from fetch_stocks import _newsweb_api_base, _newsweb_post
        base = _newsweb_api_base()
        sett = {}
        for a, b in perioder(fra, til):
            resp = _newsweb_post(
                f"{base}/v1/newsreader/list?fromDate={a.isoformat()}"
                f"&toDate={b.isoformat()}&limit=1000", timeout=30)
            meldinger = resp.get("data", {}).get("messages", []) or []
            if len(meldinger) >= NEWSWEB_TAK:
                # Lista er trolig kuttet. Del perioden i enkeltdager.
                for d in perioder(a, b, 1):
                    r = _newsweb_post(
                        f"{base}/v1/newsreader/list?fromDate={d[0].isoformat()}"
                        f"&toDate={d[1].isoformat()}&limit=1000", timeout=30)
                    for m in r.get("data", {}).get("messages", []) or []:
                        sett[m.get("messageId") or m.get("id")] = m
                continue
            for m in meldinger:
                sett[m.get("messageId") or m.get("id")] = m
        return list(sett.values())
    except Exception as e:
        print(f"  NewsWeb: {e}", file=sys.stderr)
        return None


# ── GitHub Actions ───────────────────────────────────────────────────────────

def oppsummer_kjoringer(kjoringer):
    """Per workflow: antall, utfall og de som feilet. Ren funksjon.

    «cancelled» telles for seg og er ikke en feil: prisjobben kansellerer en
    pågående kjøring når neste starter, med vilje (se oppdater-priser.yml).
    """
    per = {}
    for k in sorted(kjoringer, key=lambda x: x.get("created_at") or ""):
        navn = k.get("name") or "?"
        p = per.setdefault(navn, {"antall": 0, "utfall": {}, "feilet": [], "siste": None})
        p["antall"] += 1
        utfall = k.get("conclusion") or k.get("status") or "ukjent"
        p["utfall"][utfall] = p["utfall"].get(utfall, 0) + 1
        rad = {"id": k.get("id"), "dato": k.get("created_at"),
               "hendelse": k.get("event"), "utfall": utfall,
               "url": k.get("html_url")}
        if utfall in ("failure", "timed_out", "startup_failure"):
            p["feilet"].append(rad)
        p["siste"] = rad
    return per


def _github_get(sti, timeout=20):
    req = urllib.request.Request(
        f"https://api.github.com/{sti}",
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": "exday-vedlikehold"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def hent_kjoringer(fra):
    """Kjøringene siden `fra`, med feilede steg for dem som feilet. None ved feil."""
    try:
        alle = []
        for side in range(1, 6):
            d = _github_get(f"repos/{REPO}/actions/runs?per_page=100&page={side}"
                            f"&created=%3E%3D{fra.isoformat()}")
            runs = d.get("workflow_runs", []) or []
            alle.extend(runs)
            if len(runs) < 100:
                break
        per = oppsummer_kjoringer(alle)
        for p in per.values():
            for rad in p["feilet"][-5:]:
                try:
                    jobber = _github_get(f"repos/{REPO}/actions/runs/{rad['id']}/jobs")
                    rad["steg"] = [
                        f"{j.get('name')}: {s.get('name')}"
                        for j in jobber.get("jobs", [])
                        for s in (j.get("steps") or [])
                        if s.get("conclusion") == "failure"]
                except Exception:
                    rad["steg"] = None
        return per
    except Exception as e:
        print(f"  GitHub Actions: {e}", file=sys.stderr)
        return None


def hent_issues():
    """Åpne issues (ikke PR-er), eldste først. None ved feil."""
    try:
        d = _github_get(f"repos/{REPO}/issues?state=open&per_page=50")
    except Exception as e:
        print(f"  GitHub issues: {e}", file=sys.stderr)
        return None
    i_dag = datetime.datetime.now(datetime.timezone.utc)
    ut = []
    for i in d:
        if "pull_request" in i:
            continue
        opprettet = _tid(i.get("created_at"))
        ut.append({
            "nummer": i.get("number"), "tittel": i.get("title"),
            "etiketter": [e.get("name") for e in i.get("labels", [])],
            "opprettet": i.get("created_at"), "oppdatert": i.get("updated_at"),
            "dager_aapen": (i_dag - opprettet).days if opprettet else None,
            "url": i.get("html_url")})
    return sorted(ut, key=lambda x: x["opprettet"] or "")


# ── Ferskhet ─────────────────────────────────────────────────────────────────

DATAJOBB_TIDER = [(7, 0), (10, 0), (13, 0), (16, 0)]            # UTC, man–fre
PRISJOBB_TIDER = [(h, m) for h in range(8, 17) for m in (0, 15, 30, 45)] + [(17, 0)]
SLAKK = datetime.timedelta(hours=3)   # GitHub forsinker planlagte jobber, ofte mye


def _tid(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def siste_planlagte(naa, tider):
    """Siste planlagte kjøring (UTC, mandag–fredag) på eller før `naa`."""
    dag = naa.date()
    for _ in range(8):
        if dag.weekday() < 5:
            for h, m in sorted(tider, reverse=True):
                t = datetime.datetime(dag.year, dag.month, dag.day, h, m,
                                      tzinfo=datetime.timezone.utc)
                if t <= naa:
                    return t
        dag -= datetime.timedelta(days=1)
    return None


def ferskhet(sist, naa, tider):
    """Hvor gammelt et tidsstempel er, og om en planlagt kjøring er uteblitt.

    Gammel betyr: den siste kjøringen som skulle vært ferdig for minst tre
    timer siden, har ikke gitt nye data. En lørdag er fredagens tall ikke
    gamle.
    """
    t = _tid(sist)
    if t is None:
        return {"tidspunkt": sist, "timer": None, "gammel": None}
    forventet = siste_planlagte(naa - SLAKK, tider)
    return {"tidspunkt": sist,
            "timer": round((naa - t).total_seconds() / 3600, 1),
            "gammel": bool(forventet and t < forventet)}


def _les_json(sti, standard):
    try:
        with open(sti, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return standard


def lokal_status(naa):
    """Det filene i repoet sier om gårsdagens kjøringer. Ingen nett."""
    aksjer = _les_json(os.path.join(ROT, "data", "aksjer.json"), {})
    priser = _les_json(os.path.join(ROT, "data", "priser.json"), {})
    varsler = _les_json(os.path.join(ROT, "data", "ticker_varsler.json"), {})
    return {
        "aksjedata": {**ferskhet(aksjer.get("sist_oppdatert"), naa, DATAJOBB_TIDER),
                      "antall_ok": aksjer.get("antall_ok"),
                      "antall_feil": aksjer.get("antall_feil")},
        "priser": ferskhet(priser.get("oppdatert"), naa, PRISJOBB_TIDER),
        "varsler": {
            "generert": varsler.get("generert"),
            "antall": varsler.get("antall"),
            "kritiske": varsler.get("antall_kritiske"),
            "liste": [{k: v.get(k) for k in ("ticker", "type", "alvorlighet", "melding")}
                      for v in varsler.get("varsler", [])],
        },
    }


# ── Nettstedet mot repoet ────────────────────────────────────────────────────

NETTSTED = "https://exday.no"
MAKS_ETTERSLEP_TIMER = 2


def etterslep(repo_tid, live_tid):
    """Timer nettstedet ligger bak repoet. None når et av tidspunktene mangler.

    Datajobben committer først og deployer etterpå, så noen minutter er
    normalt. Pages-deploy feilet fem ganger mellom 30.09 og 09.10.2026, og en
    feilet deploy viser ingenting i repoet: dataene er riktige der og gamle
    hos leseren.
    """
    r, l = _tid(repo_tid), _tid(live_tid)
    if r is None or l is None:
        return None
    return round(max(0.0, (r - l).total_seconds() / 3600), 1)


def hent_nettsted():
    """Tidsstemplene i aksjer.json og priser.json slik leseren får dem."""
    ut = {}
    for navn, sti, felt in (("aksjedata", "data/aksjer.json", "sist_oppdatert"),
                            ("priser", "data/priser.json", "oppdatert")):
        try:
            req = urllib.request.Request(f"{NETTSTED}/{sti}",
                                         headers={"User-Agent": "exday-vedlikehold",
                                                  "Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=30) as r:
                ut[navn] = json.loads(r.read()).get(felt)
        except Exception as e:
            print(f"  {NETTSTED}/{sti}: {e}", file=sys.stderr)
            ut[navn] = None
    return ut


# ── Samlet ───────────────────────────────────────────────────────────────────

def kjor(dager, uten_nett=False, naa=None):
    naa = naa or datetime.datetime.now(datetime.timezone.utc)
    til = naa.date()
    fra = til - datetime.timedelta(days=dager - 1)
    tickere = [t["ticker"] for t in _les_json(os.path.join(ROT, "data", "tickers.json"), [])]
    rapport = {"generert": naa.isoformat(timespec="seconds"),
               "periode": {"fra": fra.isoformat(), "til": til.isoformat()},
               "katalog": len(tickere),
               **lokal_status(naa)}
    if uten_nett:
        return rapport

    instrumenter = None
    try:
        from fetch_stocks import hent_euronext_instrumenter
        from sjekk_utdaterte import MIN_NOTERINGER
        instrumenter = hent_euronext_instrumenter()
        if instrumenter is not None and len(instrumenter) < MIN_NOTERINGER:
            instrumenter = None
    except Exception as e:
        print(f"  Euronext: {e}", file=sys.stderr)
    if instrumenter is not None:
        utenfor = sorted(
            (t, d["navn"], d["marked"]) for t, d in instrumenter.items() if t not in tickere)
        rapport["euronext"] = {
            "noterte": len(instrumenter),
            "utenfor_katalogen": [{"symbol": t, "navn": n, "marked": m} for t, n, m in utenfor],
            "katalog_ikke_notert": sorted(t for t in tickere if t not in instrumenter),
        }
    else:
        rapport["euronext"] = None

    meldinger = hent_newsweb(fra, til)
    if meldinger is None:
        rapport["newsweb"] = None
    else:
        euronext_symboler = None
        if instrumenter is not None:
            try:
                from fetch_stocks import EURONEXT_SYMBOL_MAP
                bakover = {v: k for k, v in EURONEXT_SYMBOL_MAP.items()}
            except Exception:
                bakover = {}
            euronext_symboler = {bakover.get(t, t).upper() for t in instrumenter}
        rapport["newsweb"] = {"meldinger": len(meldinger),
                              **klassifiser(meldinger, utsteder_til_ticker(tickere),
                                            euronext_symboler)}

    live = hent_nettsted()
    rapport["nettsted"] = {
        navn: {"live": live[navn], "repo": rapport[navn]["tidspunkt"],
               "etterslep_timer": etterslep(rapport[navn]["tidspunkt"], live[navn])}
        for navn in ("aksjedata", "priser")}
    rapport["kjoringer"] = hent_kjoringer(fra)
    rapport["issues"] = hent_issues()
    return rapport


def _linje(f):
    t = ",".join(f.get("tickere") or []) or f["utsteder"]
    return f"  {f['dato']}  {t:<8} {f['tittel']}  ({f['url']})"


def som_tekst(r):
    ut = [f"Vedlikehold {r['generert'][:16].replace('T', ' ')} UTC  "
          f"(meldinger {r['periode']['fra']} – {r['periode']['til']}, katalog {r['katalog']})"]

    ad, pr = r["aksjedata"], r["priser"]
    ut.append("\n== Data")
    ut.append(f"  aksjer.json: {ad['tidspunkt']} ({ad['timer']} t)"
              f"{'  ⚠ planlagt kjøring uteblitt' if ad['gammel'] else ''}"
              f"  ok {ad['antall_ok']} / feil {ad['antall_feil']}")
    ut.append(f"  priser.json: {pr['tidspunkt']} ({pr['timer']} t)"
              f"{'  ⚠ planlagt kjøring uteblitt' if pr['gammel'] else ''}")
    v = r["varsler"]
    ut.append(f"  ticker_varsler.json: {v['antall']} varsler, {v['kritiske']} kritiske")
    for x in v["liste"]:
        ut.append(f"    {x['alvorlighet']:<9} {x['ticker']:<7} {x['type']}")

    if "nettsted" in r:
        ut.append("\n== Nettstedet (exday.no) mot repoet")
        for navn, n in r["nettsted"].items():
            e = n["etterslep_timer"]
            flagg = ("  ⚠ nettstedet henger etter" if e is not None and e > MAKS_ETTERSLEP_TIMER
                     else "  kunne ikke sammenlignes" if e is None else "")
            ut.append(f"  {navn}: live {n['live']}, repo {n['repo']}{flagg}")

    if "kjoringer" in r:
        ut.append("\n== GitHub Actions")
        if r["kjoringer"] is None:
            ut.append("  kunne ikke hentes")
        else:
            for navn, p in sorted(r["kjoringer"].items()):
                utfall = ", ".join(f"{k} {n}" for k, n in sorted(p["utfall"].items()))
                ut.append(f"  {navn}: {p['antall']} kjøringer ({utfall})")
                for f in p["feilet"]:
                    steg = "; ".join(f.get("steg") or []) or "steg ukjent"
                    ut.append(f"    FEILET {f['dato']}  {steg}  {f['url']}")

    if "issues" in r:
        ut.append("\n== Åpne issues")
        if r["issues"] is None:
            ut.append("  kunne ikke hentes")
        elif not r["issues"]:
            ut.append("  ingen")
        for i in r["issues"] or []:
            ut.append(f"  #{i['nummer']} ({i['dager_aapen']} d, {','.join(i['etiketter'])}) {i['tittel']}")

    if "newsweb" in r:
        nw = r["newsweb"]
        ut.append("\n== NewsWeb")
        if nw is None:
            ut.append("  kunne ikke hentes — ingenting er avgjort om inn og ut")
        else:
            ut.append(f"  {nw['meldinger']} meldinger lest")
            for nokkel, overskrift in (
                    ("ut_vedtatt", "Avgjort ut (avnotering, fusjon gjennomført)"),
                    ("ut_mulig", "Mulig ut (bud, fusjonsplan)"),
                    ("marked", "Bytter markedsplass (påvirker ASK)"),
                    ("navn", "Navn eller ticker endres"),
                    ("handelsstans", "Handelsstans"),
                    ("nye_noteringer", "Nye noteringer (utenfor katalogen)")):
                ut.append(f"\n  {overskrift}: {len(nw[nokkel])}")
                ut.extend(_linje(f) for f in nw[nokkel])
            ut.append(f"\n  Utbyttemeldinger fra selskaper utenfor katalogen: "
                      f"{len(nw['utbytte_utenfor_katalogen'])}")
            for k in nw["utbytte_utenfor_katalogen"]:
                pa = {True: "på Euronext-lista", False: "IKKE på Euronext-lista",
                      None: "Euronext ukjent"}[k["pa_euronext"]]
                ut.append(f"  {k['utsteder']:<8} {k['navn']} ({k['antall']}, {pa})")
                ut.extend("  " + _linje(f) for f in k["meldinger"][:3])

    if "euronext" in r:
        eu = r["euronext"]
        ut.append("\n== Euronext")
        if eu is None:
            ut.append("  kunne ikke hentes")
        else:
            ut.append(f"  {eu['noterte']} noterte, {len(eu['utenfor_katalogen'])} utenfor katalogen")
            if eu["katalog_ikke_notert"]:
                ut.append(f"  I katalogen, men ikke notert: {', '.join(eu['katalog_ikke_notert'])}")
    return "\n".join(ut)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--dager", type=int, default=3,
                   help="hvor mange dager med børsmeldinger (standard 3)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--uten-nett", action="store_true",
                   help="bare filene i repoet: dataferskhet og varsler")
    p.add_argument("--melding", nargs="+", metavar="ID",
                   help="skriv ut teksten i NewsWeb-meldinger og avslutt")
    a = p.parse_args()
    if a.melding:
        from fetch_stocks import _newsweb_tekst
        for mid in a.melding:
            print(f"=== {NEWSWEB_MELDING_URL.format(mid)}\n{_newsweb_tekst(mid).strip()}\n")
        return
    r = kjor(max(1, a.dager), a.uten_nett)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(som_tekst(r))


if __name__ == "__main__":
    main()
