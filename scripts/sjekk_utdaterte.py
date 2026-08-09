#!/usr/bin/env python3
"""
sjekk_utdaterte.py — Fanger opp aksjer som er avnotert, omdøpt eller kjøpt opp.

Bakgrunn
--------
Når et selskap bytter navn, blir kjøpt opp eller avnoteres fra Oslo Børs,
fortsetter pipelinen å servere gamle data i det stille:

  * fetch_stocks.py bruker navnet fra tickers.json og sammenligner det aldri
    mot navnet Yahoo Finance faktisk returnerer  → navneendringer er usynlige.
  * Når hentingen feiler, faller den tilbake til gårsdagens data på ubestemt
    tid                                          → avnoteringer er usynlige.

Historiske hendelser dette hadde fanget opp: STRO/SNI-duplikatet, VENDA/VEND,
phantom-tickeren ODLD, COOL som ble avnotert i januar 2026, og ABL Group som
ble til Aqualis (AQUA) i juni 2026.

Slik virker den
---------------
fetch_stocks.py skriver diagnostikk per ticker til data/hentelogg.json for hver
kjøring. Dette skriptet leser den loggen, sammenligner mot tilstanden fra
tidligere kjøringer i data/ticker_status.json, og skriver varsler til
data/ticker_varsler.json.

Tilstanden måles i *dager*, ikke i antall kjøringer, slik at tersklene betyr det
samme uansett hvor ofte workflowen kjører.

Bruk
----
    python scripts/sjekk_utdaterte.py            # normal kjøring (avslutter 0)
    python scripts/sjekk_utdaterte.py --streng   # avslutt 1 ved kritiske varsler
    python scripts/sjekk_utdaterte.py --tort     # ikke skriv tilstandsfilen
"""

import argparse
import datetime
import difflib
import json
import os
import re
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TICKERS_JSON = os.path.join(DATA_DIR, "tickers.json")
AKSJER_JSON = os.path.join(DATA_DIR, "aksjer.json")
HENTELOGG_JSON = os.path.join(DATA_DIR, "hentelogg.json")
STATUS_JSON = os.path.join(DATA_DIR, "ticker_status.json")
VARSLER_JSON = os.path.join(DATA_DIR, "ticker_varsler.json")

# ── Terskler ──────────────────────────────────────────────────────────────────
# Dager uten vellykket henting før vi mistenker / konkluderer med avnotering.
DAGER_FOR_ADVARSEL = 3
DAGER_FOR_KRITISK = 7
# Dager med avvikende navn før vi konkluderer med navneendring. Én enkelt
# kjøring kan gi utslag på en forbigående Yahoo-rarhet, derfor mer enn null.
DAGER_FOR_NAVNEENDRING = 2
# Børsdager uten kursbevegelse før kursen regnes som fastfrosset.
DAGER_FOR_FASTFROSSET_KURS = 5
# Likhetsgrad under dette regnes som et nytt selskapsnavn (0.0–1.0).
NAVN_LIKHET_TERSKEL = 0.60
# Mellom denne og terskelen over: sannsynligvis bare omskriving, verdt et blikk.
NAVN_LIKHET_MILD = 0.85

ALVOR_KRITISK = "kritisk"
ALVOR_ADVARSEL = "advarsel"
ALVOR_INFO = "info"

_ALVOR_RANG = {ALVOR_KRITISK: 0, ALVOR_ADVARSEL: 1, ALVOR_INFO: 2}

# Juridiske selskapsformer og fyllord som ikke sier noe om selskapets identitet.
_SELSKAPSFORMER = {
    "asa", "as", "a/s", "ab", "ltd", "limited", "plc", "se", "nv", "n.v.",
    "oyj", "inc", "incorporated", "corp", "corporation", "co", "company",
    "group", "gruppen", "holding", "holdings", "the", "og",
}


def _idag() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def _som_dato(verdi):
    """Tolker 'YYYY-MM-DD' til date. Returnerer None ved ugyldig/manglende verdi."""
    if not verdi:
        return None
    if isinstance(verdi, datetime.date):
        return verdi
    try:
        return datetime.datetime.strptime(str(verdi)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def normaliser_navn(navn: str) -> str:
    """
    Reduserer et selskapsnavn til identitetsbærende ord.

    'ABL Group ASA' → 'abl', 'Equinor ASA' → 'equinor'. Aksjeklasse-markører
    bevares, slik at 'Wilh. Wilhelmsen Holding B' ikke kollapser til samme
    streng som A-aksjen.
    """
    if not navn:
        return ""
    s = navn.lower()
    s = re.sub(r"[.,&()\-/]", " ", s)
    ord_liste = [o for o in s.split() if o and o not in _SELSKAPSFORMER]
    return " ".join(ord_liste)


def navn_likhet(vart_navn: str, yahoo_navn: str) -> float:
    """
    Returnerer likhetsgrad 0.0–1.0 mellom to selskapsnavn etter normalisering.

    Når det ene navnet er et rent prefiks av det andre ('equinor' vs
    'equinor energy'), regnes det som fullt treff — Yahoo er ofte mer eller
    mindre ordrik enn vår egen katalog uten at selskapet har endret seg.
    """
    a = normaliser_navn(vart_navn)
    b = normaliser_navn(yahoo_navn)
    if not a or not b:
        return 1.0  # Mangler grunnlag — ikke rop ulv
    if a == b:
        return 1.0
    if a.startswith(b) or b.startswith(a):
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def _varsel(ticker, type_, alvor, melding, forslag):
    return {
        "ticker": ticker,
        "type": type_,
        "alvorlighet": alvor,
        "melding": melding,
        "forslag": forslag,
    }


# ── Deteksjon ─────────────────────────────────────────────────────────────────

def finn_duplikat_ticker_yf(tickere: list) -> list:
    """
    Samme ticker_yf på to oppføringer gir identiske data fra Yahoo for begge.

    Dette er STRO/SNI- og VENDA/VEND-tilfellet, og fanges umiddelbart — det
    trengs ingen historikk for å slå fast at katalogen er inkonsistent.
    """
    varsler = []
    sett = {}
    for t in tickere:
        yf_ticker = (t.get("ticker_yf") or "").strip().upper()
        if not yf_ticker:
            continue
        sett.setdefault(yf_ticker, []).append(t.get("ticker", "?"))

    for yf_ticker, eiere in sorted(sett.items()):
        if len(eiere) > 1:
            varsler.append(_varsel(
                ", ".join(sorted(eiere)),
                "duplikat_ticker_yf",
                ALVOR_KRITISK,
                f"{len(eiere)} oppføringer deler ticker_yf «{yf_ticker}»: "
                f"{', '.join(sorted(eiere))}. Begge får identiske data fra Yahoo Finance.",
                "Fjern den utdaterte oppføringen fra data/tickers.json, eller rett "
                "ticker_yf på den som er feil.",
            ))
    return varsler


def finn_duplikat_navn(tickere: list) -> list:
    """
    To oppføringer med samme selskapsnavn er nesten alltid en gammel og en ny
    ticker for samme selskap.

    Dette er WALWIL/WAWI-tilfellet: begge heter «Wallenius Wilhelmsen ASA», men
    bare WAWI gir data. Ticker_yf er forskjellig, så duplikatsjekken på ticker_yf
    fanger det ikke, og WALWIL har ingen data å sammenligne mot.
    """
    varsler = []
    sett = {}
    for t in tickere:
        navn = normaliser_navn(t.get("navn") or "")
        if not navn:
            continue
        sett.setdefault(navn, []).append(t.get("ticker", "?"))

    for navn, eiere in sorted(sett.items()):
        if len(eiere) > 1:
            varsler.append(_varsel(
                ", ".join(sorted(eiere)),
                "duplikat_navn",
                ALVOR_KRITISK,
                f"{len(eiere)} oppføringer har samme selskapsnavn: "
                f"{', '.join(sorted(eiere))}. Sannsynligvis en gammel og en ny ticker "
                f"for samme selskap.",
                "Kontroller mot Euronext hvilken ticker som er gjeldende, og fjern den "
                "utdaterte fra data/tickers.json.",
            ))
    return varsler


def finn_manglende_data(tickere: list, aksjer: list, hentelogg: dict = None) -> list:
    """
    Tickere som står i katalogen, men som ikke har en eneste rad i aksjer.json.

    At en ticker mangler helt betyr at hentingen feilet og at det heller ikke
    fantes fallback-data — altså at den aldri har levert. Typisk et selskap som
    er avnotert, fusjonert eller omdøpt for lenge siden, eller en ticker som
    aldri har eksistert.

    En nylig lagt til ticker mangler også data, men er ikke et problem: den er
    bare ikke hentet ennå. De skilles på hentelogget — har hentingen kjørt uten
    å nevne tickeren i det hele tatt, ble den lagt til etter forrige kjøring.

    Sjekken krever ingen historikk og virker derfor fra første kjøring.
    """
    if not aksjer:
        # Uten aksjer.json vet vi ingenting — ikke rapporter alt som manglende.
        return []
    har_data = {a.get("ticker") for a in aksjer}
    logg_tickere = set((hentelogg or {}).get("tickere", {}))

    varsler = []
    for t in sorted(tickere, key=lambda x: x.get("ticker") or ""):
        ticker = t.get("ticker")
        if not ticker or ticker in har_data:
            continue
        navn = t.get("navn", "?")
        yf_ticker = t.get("ticker_yf", "?")

        if logg_tickere and ticker not in logg_tickere:
            varsler.append(_varsel(
                ticker, "ny_ticker", ALVOR_INFO,
                f"«{navn}» ({yf_ticker}) er lagt til i tickers.json etter forrige "
                f"datahenting og har derfor ingen data ennå.",
                "Ingen handling nødvendig — data kommer ved neste kjøring av "
                "fetch_stocks.py.",
            ))
        else:
            varsler.append(_varsel(
                ticker, "ingen_data", ALVOR_KRITISK,
                f"«{navn}» ({yf_ticker}) står i tickers.json, men har ingen rad i "
                f"aksjer.json. Hentingen leverer ingenting.",
                "Kontroller om selskapet er avnotert, fusjonert eller omdøpt. "
                "Fjern oppføringen fra data/tickers.json, eller rett ticker_yf.",
            ))
    return varsler


def finn_duplikat_data(aksjer: list) -> list:
    """
    To ulike tickere med identisk kurs, utbytte og 52-ukers intervall er nesten
    sikkert samme underliggende instrument — selv når ticker_yf er forskjellig.

    Fanger tilfellet der en avnotert ticker og etterfølgeren peker på samme
    papir hos Yahoo uten at ticker_yf avslører det.
    """
    varsler = []
    fingeravtrykk = {}
    for a in aksjer:
        pris = a.get("pris") or 0
        upa = a.get("utbytte_per_aksje") or 0
        hoy = a.get("52u_hoy") or 0
        lav = a.get("52u_lav") or 0
        # Krev at alle feltene er satt — nullrader ville ellers matchet hverandre.
        if not (pris and upa and hoy and lav):
            continue
        nokkel = (round(pris, 4), round(upa, 4), round(hoy, 4), round(lav, 4))
        fingeravtrykk.setdefault(nokkel, []).append(a.get("ticker", "?"))

    for nokkel, eiere in fingeravtrykk.items():
        if len(eiere) > 1:
            varsler.append(_varsel(
                ", ".join(sorted(eiere)),
                "identiske_data",
                ALVOR_KRITISK,
                f"{', '.join(sorted(eiere))} har identisk kurs ({nokkel[0]}), "
                f"utbytte ({nokkel[1]}) og 52-ukers intervall. Sannsynligvis samme selskap "
                f"registrert to ganger.",
                "Kontroller mot Euronext hvilken ticker som er gjeldende, og fjern den andre "
                "fra data/tickers.json.",
            ))
    return varsler


def vurder_ticker(ticker, logg, forrige, idag):
    """
    Vurderer én ticker mot forrige kjente tilstand.

    Returnerer (varsler, ny_tilstand). Rendyrket funksjon uten I/O, slik at den
    kan testes med syntetiske data.
    """
    varsler = []
    tilstand = dict(forrige) if forrige else {}

    ok = bool(logg.get("ok"))
    yahoo_navn = logg.get("yahoo_navn") or ""
    vart_navn = logg.get("vart_navn") or ""

    # ── Hentestatus: hvor lenge er det siden vi sist fikk data? ───────────────
    if ok:
        tilstand["sist_ok"] = idag.isoformat()
        tilstand.pop("feil_siden", None)
    else:
        tilstand.setdefault("feil_siden", idag.isoformat())

    sist_ok = _som_dato(tilstand.get("sist_ok"))
    if not ok and sist_ok:
        dager = (idag - sist_ok).days
        if dager >= DAGER_FOR_KRITISK:
            varsler.append(_varsel(
                ticker, "mulig_avnotering", ALVOR_KRITISK,
                f"Ingen data fra Yahoo Finance på {dager} dager (sist OK {sist_ok.isoformat()}). "
                f"Siden vises fortsatt med data fra den datoen.",
                "Sjekk om selskapet er avnotert, fusjonert eller har byttet ticker. "
                "Fjern eller rett oppføringen i data/tickers.json.",
            ))
        elif dager >= DAGER_FOR_ADVARSEL:
            varsler.append(_varsel(
                ticker, "hentefeil", ALVOR_ADVARSEL,
                f"Henting har feilet i {dager} dager (sist OK {sist_ok.isoformat()}).",
                "Følg med. Vedvarer det til "
                f"{DAGER_FOR_KRITISK} dager, kontroller om tickeren fortsatt finnes.",
            ))
    elif not ok and not sist_ok:
        # Aldri sett vellykket henting for denne tickeren.
        varsler.append(_varsel(
            ticker, "aldri_hentet", ALVOR_ADVARSEL,
            "Ingen vellykket henting registrert for denne tickeren.",
            "Kontroller at ticker_yf er riktig i data/tickers.json.",
        ))

    # ── Navneendring ──────────────────────────────────────────────────────────
    if ok and yahoo_navn and vart_navn:
        likhet = navn_likhet(vart_navn, yahoo_navn)
        tilstand["sist_navn_yahoo"] = yahoo_navn

        if likhet < NAVN_LIKHET_TERSKEL:
            tilstand.setdefault("navn_avvik_siden", idag.isoformat())
            avvik_siden = _som_dato(tilstand["navn_avvik_siden"])
            dager = (idag - avvik_siden).days if avvik_siden else 0
            if dager >= DAGER_FOR_NAVNEENDRING:
                varsler.append(_varsel(
                    ticker, "navneendring", ALVOR_KRITISK,
                    f"Yahoo Finance kaller selskapet «{yahoo_navn}», vi har «{vart_navn}» "
                    f"(likhet {likhet:.0%}, avvik i {dager} dager).",
                    f"Sannsynlig navneendring eller oppkjøp. Oppdater navn — og trolig "
                    f"ticker_yf — i data/tickers.json.",
                ))
            else:
                varsler.append(_varsel(
                    ticker, "navneendring", ALVOR_ADVARSEL,
                    f"Nytt navnavvik: Yahoo sier «{yahoo_navn}», vi har «{vart_navn}» "
                    f"(likhet {likhet:.0%}).",
                    f"Bekreftes som navneendring hvis avviket vedvarer i "
                    f"{DAGER_FOR_NAVNEENDRING} dager.",
                ))
        elif likhet < NAVN_LIKHET_MILD:
            tilstand.pop("navn_avvik_siden", None)
            varsler.append(_varsel(
                ticker, "navnavvik", ALVOR_INFO,
                f"Navnet avviker litt fra Yahoo: «{yahoo_navn}» vs «{vart_navn}» "
                f"(likhet {likhet:.0%}).",
                "Sannsynligvis bare ulik skrivemåte. Juster gjerne navnet i "
                "data/tickers.json for konsistens.",
            ))
        else:
            tilstand.pop("navn_avvik_siden", None)

    # ── Fastfrosset kurs ──────────────────────────────────────────────────────
    # En avnotert aksje kan fortsatt returnere data fra Yahoo, men kursen slutter
    # å bevege seg. Siste handelsdato er derfor et selvstendig signal.
    siste_handel = _som_dato(logg.get("siste_handelsdato"))
    if ok and siste_handel:
        dager = _borsdager_mellom(siste_handel, idag)
        if dager >= DAGER_FOR_FASTFROSSET_KURS:
            varsler.append(_varsel(
                ticker, "fastfrosset_kurs", ALVOR_ADVARSEL,
                f"Siste registrerte handel var {siste_handel.isoformat()} "
                f"({dager} børsdager siden). Kursen står stille.",
                "Kan bety at handelen er suspendert eller at papiret er avnotert.",
            ))

    # ── Markedsverdi forsvunnet ───────────────────────────────────────────────
    mkt = logg.get("markedsverdi")
    forrige_mkt = forrige.get("sist_markedsverdi") if forrige else None
    if ok and mkt:
        tilstand["sist_markedsverdi"] = mkt
    elif ok and not mkt and forrige_mkt:
        varsler.append(_varsel(
            ticker, "markedsverdi_borte", ALVOR_ADVARSEL,
            f"Markedsverdien er borte fra Yahoo (var {forrige_mkt:,.0f} sist). "
            f"Kan indikere strukturendring i selskapet.",
            "Kontroller om selskapet er under oppkjøp eller strykning.",
        ))

    return varsler, tilstand


def _borsdager_mellom(fra: datetime.date, til: datetime.date) -> int:
    """Grovtelling av virkedager mellom to datoer. Ignorerer helligdager."""
    if til <= fra:
        return 0
    dager = 0
    peker = fra
    while peker < til:
        peker += datetime.timedelta(days=1)
        if peker.weekday() < 5:  # mandag–fredag
            dager += 1
    return dager


# ── Kjøring ───────────────────────────────────────────────────────────────────

def _les_json(sti, standard):
    if not os.path.exists(sti):
        return standard
    try:
        with open(sti, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  Advarsel: kunne ikke lese {os.path.basename(sti)}: {e}")
        return standard


def analyser(tickere, aksjer, hentelogg, status, idag):
    """
    Kjører alle sjekkene og returnerer (varsler, ny_status).

    Rendyrket funksjon uten filsystem-tilgang — hele testdekningen går via denne.
    """
    varsler = []
    varsler.extend(finn_duplikat_ticker_yf(tickere))
    varsler.extend(finn_duplikat_navn(tickere))
    varsler.extend(finn_manglende_data(tickere, aksjer, hentelogg))
    varsler.extend(finn_duplikat_data(aksjer))

    forrige_tickere = status.get("tickere", {})
    ny_tickere = {}

    logg_per_ticker = hentelogg.get("tickere", {})
    for t in tickere:
        ticker = t.get("ticker")
        if not ticker:
            continue
        logg = logg_per_ticker.get(ticker)
        if logg is None:
            # Ingen hentelogg for denne tickeren i denne kjøringen. Behold
            # tilstanden urørt i stedet for å nullstille historikken.
            if ticker in forrige_tickere:
                ny_tickere[ticker] = forrige_tickere[ticker]
            continue
        t_varsler, tilstand = vurder_ticker(
            ticker, logg, forrige_tickere.get(ticker), idag
        )
        varsler.extend(t_varsler)
        ny_tickere[ticker] = tilstand

    # «ingen_data» og «aldri_hentet» beskriver samme situasjon fra hver sin
    # kilde. Behold den kritiske katalogsjekken og drop dubletten.
    uten_data = {v["ticker"] for v in varsler if v["type"] == "ingen_data"}
    varsler = [
        v for v in varsler
        if not (v["type"] == "aldri_hentet" and v["ticker"] in uten_data)
    ]

    # Tickere som er fjernet fra tickers.json faller naturlig ut av ny_tickere.
    varsler.sort(key=lambda v: (_ALVOR_RANG.get(v["alvorlighet"], 9), v["ticker"]))

    ny_status = {
        "sist_oppdatert": datetime.datetime.now(datetime.timezone.utc)
                                  .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tickere": ny_tickere,
    }
    return varsler, ny_status


def _skriv_rapport(varsler, antall_tickere):
    linje = "=" * 60
    print(linje)
    print("  UTDATERTE AKSJER — kontrollrapport")
    print(linje)
    print(f"Tickere kontrollert: {antall_tickere}")
    print()

    if not varsler:
        print("Ingen varsler. Alle tickere ser gjeldende ut.")
        print(linje)
        return

    for alvor, etikett in (
        (ALVOR_KRITISK, "KRITISK"),
        (ALVOR_ADVARSEL, "ADVARSEL"),
        (ALVOR_INFO, "INFO"),
    ):
        gruppe = [v for v in varsler if v["alvorlighet"] == alvor]
        if not gruppe:
            continue
        print(f"{etikett} ({len(gruppe)}):")
        for v in gruppe:
            print(f"  [{v['type']}] {v['ticker']}")
            print(f"      {v['melding']}")
            print(f"      → {v['forslag']}")
        print()
    print(linje)


def _skriv_github_sammendrag(varsler):
    """Skriver en markdown-tabell til GitHub Actions-sammendraget hvis vi kjører der."""
    sti = os.environ.get("GITHUB_STEP_SUMMARY")
    if not sti:
        return
    kritiske = [v for v in varsler if v["alvorlighet"] == ALVOR_KRITISK]
    advarsler = [v for v in varsler if v["alvorlighet"] == ALVOR_ADVARSEL]

    rader = ["## Kontroll av utdaterte aksjer", ""]
    if not varsler:
        rader.append("Ingen varsler — alle tickere ser gjeldende ut.")
    else:
        rader.append(
            f"**{len(kritiske)} kritiske**, {len(advarsler)} advarsler, "
            f"{len(varsler) - len(kritiske) - len(advarsler)} info."
        )
        rader += ["", "| Alvor | Ticker | Type | Melding |", "|---|---|---|---|"]
        for v in varsler:
            melding = v["melding"].replace("|", "\\|")
            rader.append(
                f"| {v['alvorlighet']} | `{v['ticker']}` | {v['type']} | {melding} |"
            )
    try:
        with open(sti, "a", encoding="utf-8") as f:
            f.write("\n".join(rader) + "\n")
    except OSError as e:
        print(f"  Advarsel: kunne ikke skrive GitHub-sammendrag: {e}")


def lag_issue_tekst(varsler, generert):
    """Bygger markdown-teksten som brukes i GitHub-issuet."""
    kritiske = [v for v in varsler if v["alvorlighet"] == ALVOR_KRITISK]
    advarsler = [v for v in varsler if v["alvorlighet"] == ALVOR_ADVARSEL]

    rader = [
        "Automatisk kontroll har funnet tickere som ser utdaterte ut — "
        "avnotert, omdøpt, fusjonert eller duplisert.",
        "",
        f"**{len(kritiske)} kritiske**, {len(advarsler)} advarsler. "
        f"Sist kontrollert: {generert}.",
        "",
    ]

    for alvor, tittel in ((ALVOR_KRITISK, "Kritisk"), (ALVOR_ADVARSEL, "Advarsler")):
        gruppe = [v for v in varsler if v["alvorlighet"] == alvor]
        if not gruppe:
            continue
        rader.append(f"### {tittel}")
        rader.append("")
        for v in gruppe:
            rader.append(f"- **`{v['ticker']}`** — {v['melding']}")
            rader.append(f"  - {v['forslag']}")
        rader.append("")

    rader += [
        "---",
        "",
        "Issuet oppdateres automatisk ved hver datakjøring, og lukkes når "
        "alle kritiske varsler er borte.",
        "Kontrollen kjøres av `scripts/sjekk_utdaterte.py`.",
    ]
    return "\n".join(rader)


def main(argv=None):
    p = argparse.ArgumentParser(description="Fanger opp avnoterte og omdøpte aksjer.")
    p.add_argument("--streng", action="store_true",
                   help="Avslutt med kode 1 hvis det finnes kritiske varsler.")
    p.add_argument("--tort", action="store_true",
                   help="Kjør uten å skrive tilstands- og varselfiler.")
    p.add_argument("--issue-tekst", action="store_true",
                   help="Skriv markdown for GitHub-issue til stdout, basert på "
                        "eksisterende data/ticker_varsler.json. Kjører ingen ny analyse.")
    args = p.parse_args(argv)

    if args.issue_tekst:
        lagret = _les_json(VARSLER_JSON, {})
        print(lag_issue_tekst(lagret.get("varsler", []), lagret.get("generert", "ukjent")))
        return 0

    tickere = _les_json(TICKERS_JSON, [])
    aksjer_data = _les_json(AKSJER_JSON, {})
    aksjer = aksjer_data.get("aksjer", []) if isinstance(aksjer_data, dict) else aksjer_data
    hentelogg = _les_json(HENTELOGG_JSON, {})
    status = _les_json(STATUS_JSON, {})

    if not hentelogg.get("tickere"):
        print("Ingen hentelogg funnet (data/hentelogg.json).")
        print("Kjør scripts/fetch_stocks.py først — den skriver loggen dette skriptet leser.")
        print("Kontrollerer katalogen for duplikater i mellomtiden.\n")

    varsler, ny_status = analyser(tickere, aksjer, hentelogg, status, _idag())

    _skriv_rapport(varsler, len(tickere))
    _skriv_github_sammendrag(varsler)

    if not args.tort:
        with open(STATUS_JSON, "w", encoding="utf-8") as f:
            json.dump(ny_status, f, ensure_ascii=False, indent=2)
        utdata = {
            "generert": ny_status["sist_oppdatert"],
            "antall": len(varsler),
            "antall_kritiske": sum(1 for v in varsler if v["alvorlighet"] == ALVOR_KRITISK),
            "varsler": varsler,
        }
        with open(VARSLER_JSON, "w", encoding="utf-8") as f:
            json.dump(utdata, f, ensure_ascii=False, indent=2)
        print(f"Skrev {os.path.relpath(VARSLER_JSON)} og {os.path.relpath(STATUS_JSON)}")

    kritiske = sum(1 for v in varsler if v["alvorlighet"] == ALVOR_KRITISK)
    if args.streng and kritiske:
        print(f"\nAvslutter med kode 1 — {kritiske} kritiske varsler.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
