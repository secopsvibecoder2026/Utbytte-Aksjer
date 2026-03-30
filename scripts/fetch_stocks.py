#!/usr/bin/env python3
"""
Henter utbyttedata for norske aksjer fra Yahoo Finance og lagrer til data/aksjer.json.
Kjøres daglig via GitHub Actions.
"""

import json
import os
import re
import sys
import datetime
import urllib.request
import yfinance as yf

# ── NEWSWEB (Oslo Børs) INTEGRASJON ───────────────────────────────────────────

def _newsweb_api_base():
    """Henter Newsweb API-baseurl dynamisk fra urls.json."""
    try:
        req = urllib.request.Request(
            "https://newsweb.oslobors.no/urls.json",
            headers={"Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            return data.get("api_large", "https://api3.oslo.oslobors.no")
    except Exception:
        return "https://api3.oslo.oslobors.no"


def _newsweb_post(url, data=None, timeout=10):
    """Hjelpefunksjon for POST til Newsweb API."""
    body = json.dumps(data).encode() if data else b""
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _newsweb_get(url, timeout=10):
    """Hjelpefunksjon for GET til Newsweb API."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _parse_rapport_dato(body: str) -> str | None:
    """
    Parser kvartalsrapport-dato fra finansiell kalender body-tekst.
    Foretrekker kvartal/halvår/årsrapporter fremfor andre hendelser.
    """
    today = datetime.date.today()
    dato_pattern = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\s*[-–]\s*(.+)")
    kommende = []
    for m in dato_pattern.finditer(body):
        dag, mnd, ar, event = m.group(1), m.group(2), m.group(3), m.group(4).strip()
        try:
            d = datetime.date(int(ar), int(mnd), int(dag))
        except ValueError:
            continue
        if d > today:
            kommende.append((d, event))

    if not kommende:
        return None
    kommende.sort(key=lambda x: x[0])

    # Prioriter rapport-hendelser over f.eks. kapitalmarkedsdag / generalforsamling
    rapport_kw = ["quarterly", "kvartals", "annual report", "årsrapport",
                  "half-yearly", "halvår", "q1", "q2", "q3", "q4"]
    for d, event in kommende:
        if any(kw in event.lower() for kw in rapport_kw):
            return d.strftime("%Y-%m-%d")

    return kommende[0][0].strftime("%Y-%m-%d")


_NEWSWEB_API = None   # Lazy-init én gang per kjøring

def hent_newsweb_rapport_dato(ticker: str) -> str | None:
    """
    Henter neste kvartalsrapport-dato for en aksje fra Newsweb Oslo Børs.
    Søker etter 'Financial calendar' / 'Finansiell kalender' meldinger.
    """
    global _NEWSWEB_API
    if _NEWSWEB_API is None:
        _NEWSWEB_API = _newsweb_api_base()
        print(f"  Newsweb API: {_NEWSWEB_API}")

    try:
        resp = _newsweb_post(
            f"{_NEWSWEB_API}/v1/newsreader/list?issuer={ticker}&limit=500"
        )
        messages = resp.get("data", {}).get("messages", [])

        for msg in messages:
            title = msg.get("title", "").lower()
            if "financial calendar" in title or "finansiell kalender" in title:
                msg_id = msg.get("messageId")
                full = _newsweb_get(
                    f"{_NEWSWEB_API}/v1/newsreader/message?messageId={msg_id}"
                )
                body = full.get("data", {}).get("message", {}).get("body", "")
                if body:
                    dato = _parse_rapport_dato(body)
                    if dato:
                        return dato
    except Exception as e:
        print(f"    Advarsel Newsweb [{ticker}]: {e}")
    return None

# Norske aksjer med Yahoo Finance ticker-symbol (.OL = Oslo Børs, .OAX = Euronext Expand)
AKSJER = [
    {"ticker_yf": "EQNR.OL",  "ticker": "EQNR",  "navn": "Equinor ASA",              "sektor": "Energi",             "bors": "Oslo Børs"},
    {"ticker_yf": "DNB.OL",   "ticker": "DNB",   "navn": "DNB Bank ASA",              "sektor": "Finans",             "bors": "Oslo Børs"},
    {"ticker_yf": "TEL.OL",   "ticker": "TEL",   "navn": "Telenor ASA",               "sektor": "Telekommunikasjon",  "bors": "Oslo Børs"},
    {"ticker_yf": "ORK.OL",   "ticker": "ORK",   "navn": "Orkla ASA",                 "sektor": "Forbruksvarer",      "bors": "Oslo Børs"},
    {"ticker_yf": "MOWI.OL",  "ticker": "MOWI",  "navn": "Mowi ASA",                  "sektor": "Havbruk",            "bors": "Oslo Børs"},
    {"ticker_yf": "AKRBP.OL", "ticker": "AKRBP", "navn": "Aker BP ASA",               "sektor": "Energi",             "bors": "Oslo Børs"},
    {"ticker_yf": "NHY.OL",   "ticker": "NHY",   "navn": "Norsk Hydro ASA",           "sektor": "Materialer",         "bors": "Oslo Børs"},
    {"ticker_yf": "YAR.OL",   "ticker": "YAR",   "navn": "Yara International ASA",    "sektor": "Materialer",         "bors": "Oslo Børs"},
    {"ticker_yf": "SALM.OL",  "ticker": "SALM",  "navn": "SalMar ASA",                "sektor": "Havbruk",            "bors": "Oslo Børs"},
    {"ticker_yf": "SRBNK.OL", "ticker": "SRBNK", "navn": "SpareBank 1 SR-Bank",       "sektor": "Finans",             "bors": "Oslo Børs"},
    {"ticker_yf": "GOGL.OL",  "ticker": "GOGL",  "navn": "Golden Ocean Group",        "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "MPCC.OL",  "ticker": "MPCC",  "navn": "MPC Container Ships",       "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "BWLPG.OL", "ticker": "BWLPG", "navn": "BW LPG Limited",            "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "KOG.OL",   "ticker": "KOG",   "navn": "Kongsberg Gruppen ASA",     "sektor": "Industri",           "bors": "Oslo Børs"},
    {"ticker_yf": "FRO.OL",   "ticker": "FRO",   "navn": "Frontline PLC",             "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "NONG.OL",  "ticker": "NONG",  "navn": "SpareBank 1 Nord-Norge",    "sektor": "Finans",             "bors": "Oslo Børs"},
    {"ticker_yf": "SUBC.OL",  "ticker": "SUBC",  "navn": "Subsea 7 SA",               "sektor": "Energitjenester",    "bors": "Oslo Børs"},
    {"ticker_yf": "WWI.OL",   "ticker": "WWI",   "navn": "Wilh. Wilhelmsen Holding",  "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "PNORD.OL", "ticker": "PNORD", "navn": "Protector Forsikring ASA",  "sektor": "Finans",             "bors": "Oslo Børs"},
    {"ticker_yf": "SCATC.OL", "ticker": "SCATC", "navn": "Scatec ASA",                "sektor": "Fornybar energi",    "bors": "Oslo Børs"},
    {"ticker_yf": "AUSS.OL",  "ticker": "AUSS",  "navn": "Austevoll Seafood ASA",     "sektor": "Havbruk",            "bors": "Oslo Børs"},
    {"ticker_yf": "LSG.OL",   "ticker": "LSG",   "navn": "Lerøy Seafood Group ASA",   "sektor": "Havbruk",            "bors": "Oslo Børs"},
    {"ticker_yf": "BAKKA.OL", "ticker": "BAKKA", "navn": "Bakkafrost P/F",            "sektor": "Havbruk",            "bors": "Oslo Børs"},
    {"ticker_yf": "HAFNI.OL", "ticker": "HAFNI", "navn": "Hafnia Limited",            "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "FLNG.OL",  "ticker": "FLNG",  "navn": "Flex LNG Ltd",              "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "MING.OL",  "ticker": "MING",  "navn": "SpareBank 1 SMN",           "sektor": "Finans",             "bors": "Oslo Børs"},
    {"ticker_yf": "SPOL.OL",  "ticker": "SPOL",  "navn": "SpareBank 1 Østlandet",     "sektor": "Finans",             "bors": "Oslo Børs"},
    {"ticker_yf": "AFG.OL",   "ticker": "AFG",   "navn": "Arendals Fossekompani ASA", "sektor": "Fornybar energi",    "bors": "Oslo Børs"},
    {"ticker_yf": "ODL.OL",   "ticker": "ODL",   "navn": "Odfjell SE",                "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "PGS.OL",   "ticker": "PGS",   "navn": "PGS ASA",                   "sektor": "Energitjenester",    "bors": "Oslo Børs"},
    {"ticker_yf": "VEI.OL",   "ticker": "VEI",   "navn": "Veidekke ASA",              "sektor": "Industri",           "bors": "Oslo Børs"},
    {"ticker_yf": "AKER.OL",  "ticker": "AKER",  "navn": "Aker ASA",                  "sektor": "Industri",           "bors": "Oslo Børs"},
    {"ticker_yf": "BWO.OL",   "ticker": "BWO",   "navn": "BW Offshore Limited",       "sektor": "Energitjenester",    "bors": "Oslo Børs"},
    {"ticker_yf": "SBVG.OL",  "ticker": "SBVG",  "navn": "SpareBank 1 BV",            "sektor": "Finans",             "bors": "Oslo Børs"},
    {"ticker_yf": "GJF.OL",   "ticker": "GJF",   "navn": "Gjensidige Forsikring ASA", "sektor": "Finans",             "bors": "Oslo Børs"},
    {"ticker_yf": "STB.OL",   "ticker": "STB",   "navn": "Storebrand ASA",             "sektor": "Finans",             "bors": "Oslo Børs"},
    {"ticker_yf": "AKSO.OL",  "ticker": "AKSO",  "navn": "Aker Solutions ASA",         "sektor": "Energitjenester",    "bors": "Oslo Børs"},
    {"ticker_yf": "COOL.OL",  "ticker": "COOL",  "navn": "Cool Company Ltd",           "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "OKEA.OL",  "ticker": "OKEA",  "navn": "OKEA ASA",                   "sektor": "Energi",             "bors": "Oslo Børs"},
    {"ticker_yf": "BEWI.OL",  "ticker": "BEWI",  "navn": "BEWI ASA",                   "sektor": "Industri",           "bors": "Oslo Børs"},
    {"ticker_yf": "WILS.OL",  "ticker": "WILS",  "navn": "Wilson ASA",                 "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "BONHR.OL", "ticker": "BONHR", "navn": "Bonheur ASA",                "sektor": "Fornybar energi",    "bors": "Oslo Børs"},
    {"ticker_yf": "WAWI.OL",  "ticker": "WAWI",  "navn": "Wallenius Wilhelmsen ASA",  "sektor": "Shipping",           "bors": "Oslo Børs"},
    {"ticker_yf": "NORCO.OL", "ticker": "NORCO", "navn": "Norconsult AS",              "sektor": "Industri",           "bors": "Oslo Børs"},
    {"ticker_yf": "B2I.OL",   "ticker": "B2I",   "navn": "B2 Impact ASA",              "sektor": "Finans",             "bors": "Oslo Børs"},
]

# Statiske beskrivelser (ikke tilgjengelig fra Yahoo Finance)
BESKRIVELSER = {
    "EQNR":  "Norges største energiselskap. Kvartalsutbytte pluss ekstraordinære utbytter ved høye oljepriser.",
    "DNB":   "Norges største bank. Kjent for høyt og stabilt utbytte, ofte over 7% yield.",
    "TEL":   "Norges ledende telekomselskap med stabil kontantstrøm og høy utbyttegrad. Sterkt fotavtrykk i Asia.",
    "ORK":   "Nordisk merkevareselskap med diversifisert portefølje. Konsistent og voksende utbytte i over 30 år.",
    "MOWI":  "Verdens største lakseoppdrettsselskap. Kvartalsutbytte koblet til laksepris og inntjening.",
    "AKRBP": "Norsk E&P-selskap med høy utbyttepolitikk. Betaler kvartalsvis utbytte basert på fri kontantstrøm.",
    "NHY":   "Globalt aluminiumselskap og ledende innen fornybar energi. Syklisk utbytte påvirket av aluminiumspriser.",
    "YAR":   "Verdens ledende gjødselprodusent. Utbytte varierer med gjødselpris og global matetterspørsel.",
    "SALM":  "En av Norges mest effektive lakseoppdrettere. Høy margin og voksende utbytte over tid.",
    "SRBNK": "Ledende regional sparebank på Sør-Vestlandet. Kjent for høyt og stabilt utbytte med god vekst.",
    "GOGL":  "Verdens største tørrbulkrederi. Volatilt men potensielt svært høyt utbytte koblet til shippingratene.",
    "MPCC":  "Containerrederi med svært høy utbyttegrad. Syklisk og volatilt – utbytte varierer sterkt med containerrater.",
    "BWLPG": "Verdens største LPG-tankrederi. Høy kontantstrøm og liberal utbyttepolitikk. Volatilt med shippingmarkedet.",
    "KOG":   "Teknologi- og forsvarskonsern. Lav yield men sterk utbyttevekst. Defensivt som følge av økt NATO-satsing.",
    "FRO":   "Ledende råoljetankrederi. Svært høy utbyttegrad fra sterk kontantstrøm. Syklisk og rateeksponert.",
    "NONG":  "Regional sparebank i Nord-Norge. Stabilt og voksende utbytte, godt kapitaldekkede.",
    "SUBC":  "Ledende leverandør av undersøiske engineering-tjenester til olje og gass. Solid balanse.",
    "WWI":   "Internasjonal shipping- og logistikkkonsern. Ro-ro transport og havnevirksomhet. Lav verdsettelse.",
    "PNORD": "Raskt voksende skadeforsikringsselskap i Norden og UK. Sterk utbyttevekst over mange år.",
    "SCATC": "Norsk leverandør av fornybar energi globalt. Solenergi- og vindkraftprosjekter i fremvoksende markeder.",
    "AUSS":  "Holdingselskap med majoritetseierandel i Lerøy Seafood og Pelagia. Bred eksponering mot sjømat og fiskeri.",
    "LSG":   "En av Norges største lakseoppdrettere med virksomhet innen oppdrett, villfangst og bearbeiding.",
    "BAKKA": "Færøysk-skotsk lakseoppdrettsselskap notert på Oslo Børs. Integrert verdikjede fra rogn til ferdig produkt.",
    "HAFNI": "Verdens største produkttankrederi. Frakter raffinerte petroleumsprodukter. Svært høy utbyttegrad fra sterk kontantstrøm.",
    "FLNG":  "LNG-tankselskap med moderne flåte på langsiktige TC-kontrakter. Stabil og forutsigbar kontantstrøm.",
    "MING":  "Ledende sparebank i Midt-Norge. Konsistent og voksende utbytte med solid kapitalisering.",
    "SPOL":  "Stor sparebank på Østlandet og Innlandet. Stabil inntjening og høy utbyttegrad.",
    "AFG":   "Industrielt investeringsselskap med fokus på grønn teknologi og fornybar energi. Lang utbyttehistorikk.",
    "ODL":   "Ledende kjemikalietankrederi. Frakter spesialkjemikalier globalt. Nytter av høy etterspørsel etter spesialprodukter.",
    "PGS":   "Ledende seismikkselskap som henter inn geofysiske data for olje- og gassindustrien. Gjenopptok utbytte etter restrukturering.",
    "VEI":   "Ledende skandinavisk bygg- og anleggsselskap. Lang og stabil utbyttehistorikk med ansatteeierskap som særpreg.",
    "AKER":  "Kjell Inge Røkkes industrielle investeringsselskap. Eierandeler i bl.a. Aker BP, Aker Solutions og Cognite.",
    "BWO":   "FPSO-operatør (flytende produksjon og lagring av olje). Langvarige kontrakter gir stabil kontantstrøm.",
    "SBVG":  "Sparebank i Telemark og Vestfold. Stabil lokal bank med god utbyttehistorikk og solid kapitaldekning.",
    "GJF":   "Norges største skadeforsikringsselskap. Betaler ordinært utbytte pluss ekstraordinært. Svært høy og stabil utbyttegrad.",
    "STB":   "Ledende nordisk livsforsikrings- og pensjonskonsern. Voksende utbytte drevet av sterk vekst i forvaltningskapital.",
    "AKSO":  "Leverandør av engineering og teknologi til olje-, gass- og havvindprosjekter. Gjenopptok utbytte etter restrukturering i 2020.",
    "COOL":  "LNG-tankselskap spinnet ut fra Golar LNG. Liberal utbyttepolitikk. Syklisk eksponering mot LNG-fraktrater.",
    "OKEA":  "Norsk E&P-selskap med fokus på norsk sokkel. Høy utbytteyield drevet av sterk produksjon fra Draugen og Brage.",
    "BEWI":  "Produsent av EPS-emballasje og isolasjonsmaterialer. Eksponert mot bygg, fisk og mat. Voksende i Europa.",
    "WILS":  "Europas ledende kysttransportselskap. Frakter tørrbulk og prosjektlast langs europakysten. Stabil inntjening.",
    "BONHR": "Fred. Olsen-kontrollert konglomerat med offshore vind (Fred. Olsen Renewables), cruiseskip og shippingvirksomhet.",
    "WAWI":  "Verdensledende innen bil- og høy-og-tung transport til sjøs (ro-ro). Betjener globale bilprodusenter med en moderne flåte.",
    "NORCO": "Nordens ledende ingeniør- og rådgivningsselskap. Ansatteeid med over 7 000 medarbeidere. Stabil kontantstrøm fra konsulentoppdrag.",
    "B2I":   "Europeisk kreditthåndteringsselskap. Kjøper og inndriver misligholdte fordringer. Voksende utbytte drevet av ekspansjon i Norden og Baltikum.",
}


def safe_float(value, default=0.0):
    try:
        v = float(value)
        return round(v, 2) if v == v else default  # NaN check
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        v = int(value)
        return v
    except (TypeError, ValueError):
        return default


def format_dato(ts):
    """Konverter Unix timestamp til YYYY-MM-DD streng."""
    if not ts:
        return None
    try:
        return datetime.datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return None


def frekvens_label(dividends_per_year):
    """Estimer utbyttefrekvens basert på antall utbetalinger siste år."""
    if dividends_per_year >= 10:
        return "Månedlig"
    elif dividends_per_year >= 3:
        return "Kvartalsvis"
    elif dividends_per_year >= 2:
        return "Halvårlig"
    elif dividends_per_year >= 1:
        return "Årlig"
    return "Uregelmessig"


def hent_historiske_utbytter(dividends, hist_prices, years=5):
    """Hent totalt utbytte og yield per kalenderår for siste N år."""
    if dividends.empty or hist_prices.empty:
        return [], 0.0

    current_year = datetime.datetime.today().year
    cutoff_year = current_year - years

    # Summer utbytter per kalenderår
    div_per_year = dividends.groupby(dividends.index.year).sum()
    div_per_year = div_per_year[
        (div_per_year.index > cutoff_year) & (div_per_year.index <= current_year)
    ]

    historiske = []
    yields = []

    for year, total_div in div_per_year.items():
        total_div = float(total_div)
        if total_div <= 0:
            continue
        year_hist = hist_prices[hist_prices.index.year == year]
        if year_hist.empty:
            continue
        year_end_price = float(year_hist["Close"].iloc[-1])
        if year_end_price <= 0:
            continue
        year_yield = round((total_div / year_end_price) * 100, 2)
        historiske.append({"ar": int(year), "utbytte": round(total_div, 2), "yield": year_yield})
        yields.append(year_yield)

    historiske.sort(key=lambda x: x["ar"])
    snitt_yield = round(sum(yields) / len(yields), 2) if yields else 0.0
    return historiske, snitt_yield


def beregn_utbytte_vekst(dividends, years=5):
    """Beregn CAGR for utbytte over angitte år."""
    if dividends.empty:
        return 0.0
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=years * 365)
    # Håndter både timezone-aware og naive DatetimeIndex
    if dividends.index.tz is None:
        cutoff = cutoff.replace(tzinfo=None)
    recent = dividends[dividends.index >= cutoff]
    if recent.empty or len(recent) < 2:
        return 0.0
    # Summer utbytter per år
    annual = recent.resample("YE").sum()
    if len(annual) < 2:
        return 0.0
    start_val = annual.iloc[0]
    end_val = annual.iloc[-1]
    if start_val <= 0:
        return 0.0
    n = len(annual) - 1
    cagr = (end_val / start_val) ** (1 / n) - 1
    return round(cagr * 100, 1)


def hent_aksje(meta):
    ticker_yf = meta["ticker_yf"]
    ticker = meta["ticker"]
    print(f"  Henter {ticker} ({ticker_yf})...")

    try:
        stk = yf.Ticker(ticker_yf)
        info = stk.info
        dividends = stk.dividends
        calendar = stk.calendar
        try:
            hist_prices = stk.history(period="5y")
        except Exception as hist_err:
            print(f"    Advarsel: kunne ikke hente historiske kurser for {ticker}: {hist_err}")
            import pandas as pd
            hist_prices = pd.DataFrame()

        pris = safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        if pris == 0.0:
            history = stk.history(period="1d")
            if not history.empty:
                pris = round(float(history["Close"].iloc[-1]), 2)

        raw_div_rate = safe_float(info.get("dividendRate") or info.get("trailingAnnualDividendRate"))

        # Yahoo Finance returnerer av og til dividendRate som yield-prosent
        # (f.eks. 13.93) i stedet for absolutt beløp per aksje (f.eks. 7.10 NOK).
        # Deteksjon: hvis raw_div_rate / pris * 100 > 100 er det sannsynligvis
        # allerede en prosentsats → omregn til absolutt beløp.
        if pris > 0 and raw_div_rate > 0:
            tentativ_yield = (raw_div_rate / pris) * 100
            if tentativ_yield > 100:
                # dividendRate er sannsynligvis yield i prosent, ikke absolutt beløp
                utbytte_per_aksje = round(raw_div_rate * pris / 100, 4)
            else:
                utbytte_per_aksje = raw_div_rate
        else:
            utbytte_per_aksje = raw_div_rate

        # Beregn yield fra pris og utbytte per aksje
        if pris > 0 and utbytte_per_aksje > 0:
            utbytte_yield = round((utbytte_per_aksje / pris) * 100, 2)
        else:
            raw = safe_float(info.get("dividendYield", 0))
            # dividendYield: desimal (0.069) → ×100, eller allerede prosent (6.9) → bruk direkte
            utbytte_yield = round(raw if raw > 1 else raw * 100, 2)

        # Siste faktiske utbytte
        siste_utbytte = safe_float(dividends.iloc[-1]) if not dividends.empty else 0.0

        # Antall utbytter siste 12 mnd
        one_year_ago = datetime.datetime.today() - datetime.timedelta(days=365)
        if dividends.index.tz:
            one_year_ago = one_year_ago.astimezone(dividends.index.tz)
        recent_divs = dividends[dividends.index >= one_year_ago]
        div_count = len(recent_divs)
        frekvens = frekvens_label(div_count)

        # Utbyttevekst 5 år CAGR
        utbytte_vekst_5ar = beregn_utbytte_vekst(dividends, years=5)

        # Historiske utbytter per år + snitt yield
        historiske_utbytter, snitt_yield_5ar = hent_historiske_utbytter(dividends, hist_prices)

        # Antall år med utbytte
        if not dividends.empty:
            first_year = dividends.index[0].year
            ar_med_utbytte = datetime.datetime.today().year - first_year
        else:
            ar_med_utbytte = 0

        # Ex-dato og betalingsdato
        ex_dato = None
        betaling_dato = None
        if isinstance(calendar, dict):
            ex_dato = format_dato(calendar.get("exDividendDate"))
            betaling_dato = format_dato(calendar.get("dividendDate"))

        # Neste kvartalsrapport ─ Kilde 1: Newsweb Oslo Børs (offisiell, primær)
        rapport_dato = hent_newsweb_rapport_dato(ticker)
        if rapport_dato:
            print(f"    Newsweb rapport_dato: {rapport_dato}")

        # Kilde 2: yfinance earnings_dates (fallback)
        if not rapport_dato:
            try:
                idag = datetime.datetime.today().date()
                ed = stk.earnings_dates
                if ed is not None and not ed.empty:
                    fremtidige = [
                        d.date() for d in ed.index
                        if hasattr(d, 'date') and d.date() > idag
                    ]
                    if fremtidige:
                        rapport_dato = min(fremtidige).strftime("%Y-%m-%d")
            except Exception:
                pass

        # Kilde 3: calendar["Earnings Date"] fra Yahoo Finance (siste fallback)
        if not rapport_dato and isinstance(calendar, dict):
            earnings = calendar.get("Earnings Date") or calendar.get("earningsDate")
            if isinstance(earnings, list) and earnings:
                rapport_dato = format_dato(earnings[0])
            elif earnings:
                rapport_dato = format_dato(earnings)

        # 52-ukers kurs
        hoy_52u = safe_float(info.get("fiftyTwoWeekHigh"))
        lav_52u = safe_float(info.get("fiftyTwoWeekLow"))

        # Markedsverdi i milliarder NOK
        mkt_cap = safe_float(info.get("marketCap"))
        markedsverdi_mrd = round(mkt_cap / 1e9, 1)

        # Nøkkeltall
        pe_ratio = safe_float(info.get("trailingPE") or info.get("forwardPE"))
        pb_ratio = safe_float(info.get("priceToBook"))
        payout_ratio = safe_float(info.get("payoutRatio", 0)) * 100
        payout_ratio = round(payout_ratio, 1)

        valuta = info.get("currency", "NOK")

        resultat = {
            "ticker": ticker,
            "navn": meta["navn"],
            "sektor": meta["sektor"],
            "bors": meta["bors"],
            "pris": pris,
            "52u_hoy": hoy_52u,
            "52u_lav": lav_52u,
            "markedsverdi_mrd": markedsverdi_mrd,
            "utbytte_per_aksje": utbytte_per_aksje,
            "utbytte_yield": utbytte_yield,
            "utbytte_vekst_5ar": utbytte_vekst_5ar,
            "payout_ratio": payout_ratio,
            "pe_ratio": pe_ratio,
            "pb_ratio": pb_ratio,
            "ex_dato": ex_dato,
            "betaling_dato": betaling_dato,
            "rapport_dato": rapport_dato,
            "frekvens": frekvens,
            "ar_med_utbytte": ar_med_utbytte,
            "siste_utbytte": siste_utbytte,
            "historiske_utbytter": historiske_utbytter,
            "snitt_yield_5ar": snitt_yield_5ar,
            "beskrivelse": BESKRIVELSER.get(ticker, ""),
            "valuta": valuta,
        }
        return resultat

    except Exception as e:
        print(f"    FEIL for {ticker}: {e}")
        return None


# ── VALIDERING ────────────────────────────────────────────────────────────────

def valider_aksje(a):
    """
    Kjør 5 valideringskontroller på en ferdig hentet aksje.
    Returnerer liste med advarselstrenger (tom = OK).

    Punkt 1: Yield-kryssvalidering
    Punkt 2: Pris-validering
    Punkt 3: Feltplausibilitet
    Punkt 4: Manglende kritiske felt
    (Punkt 5 er den strukturerte rapporten i main())
    """
    advarsler = []
    ticker = a.get("ticker", "?")

    # ── 1. Yield-kryssvalidering ──────────────────────────────────────────────
    if a["pris"] > 0 and a["utbytte_per_aksje"] > 0:
        beregnet = (a["utbytte_per_aksje"] / a["pris"]) * 100
        lagret   = a["utbytte_yield"]
        if lagret > 0:
            avvik_pct = abs(beregnet - lagret) / max(beregnet, 0.01) * 100
            if avvik_pct > 25:
                advarsler.append(
                    f"[1] Yield-avvik {avvik_pct:.0f}%: "
                    f"beregnet {beregnet:.2f}% vs lagret {lagret:.2f}%"
                )

    # ── 2. Pris-validering ────────────────────────────────────────────────────
    if a["pris"] <= 0:
        advarsler.append(f"[2] Ugyldig pris: {a['pris']}")
    elif a["pris"] > 100_000:
        advarsler.append(f"[2] Mistenkelig høy pris: {a['pris']}")

    # ── 3. Feltplausibilitet ──────────────────────────────────────────────────
    if a["payout_ratio"] > 300:
        advarsler.append(f"[3] Payout ratio ekstremt høy: {a['payout_ratio']}%")
    if 0 < a["pe_ratio"] > 500:
        advarsler.append(f"[3] Mistenkelig høy P/E: {a['pe_ratio']}")
    if a["utbytte_yield"] > 80:
        advarsler.append(f"[3] Ekstremt høy yield: {a['utbytte_yield']}% — sjekk manuelt")
    if a["utbytte_per_aksje"] > 0 and a["pris"] > 0 and a["utbytte_per_aksje"] > a["pris"]:
        advarsler.append(
            f"[3] Utbytte/aksje ({a['utbytte_per_aksje']}) > kurs ({a['pris']}) — umulig"
        )
    if a["52u_lav"] > 0 and a["52u_hoy"] > 0 and a["52u_lav"] > a["52u_hoy"]:
        advarsler.append(
            f"[3] 52u lav ({a['52u_lav']}) > 52u høy ({a['52u_hoy']}) — data-feil"
        )

    # ── 4. Manglende kritiske felt ────────────────────────────────────────────
    mangler = []
    if a["pris"] == 0:               mangler.append("pris")
    if a["utbytte_yield"] == 0:      mangler.append("utbytte_yield")
    if a["utbytte_per_aksje"] == 0:  mangler.append("utbytte_per_aksje")
    if not a.get("ex_dato"):         mangler.append("ex_dato")
    if mangler:
        advarsler.append(f"[4] Manglende felt: {', '.join(mangler)}")

    return advarsler


def main():
    print("Starter henting av aksjedata fra Yahoo Finance...")
    output_path = os.path.join(os.path.dirname(__file__), "..", "data", "aksjer.json")

    # Last eksisterende data som fallback
    fallback = {}
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
            existing_aksjer = existing if isinstance(existing, list) else existing.get("aksjer", [])
            fallback = {a["ticker"]: a for a in existing_aksjer}

    resultater = []
    feil = []          # Henting feilet, brukte fallback
    ingen_data = []    # Henting feilet, ingen fallback

    for meta in AKSJER:
        aksje = hent_aksje(meta)
        if aksje:
            resultater.append(aksje)
        elif meta["ticker"] in fallback:
            print(f"    Bruker fallback-data for {meta['ticker']}")
            resultater.append(fallback[meta["ticker"]])
            feil.append(meta["ticker"])
        else:
            print(f"    KRITISK: Ingen data for {meta['ticker']} og ingen fallback.")
            ingen_data.append(meta["ticker"])

    # ── 5. Strukturert datakvalitetsrapport ───────────────────────────────────
    linje = "=" * 54
    print(f"\n{linje}")
    print("  DATAKVALITETSRAPPORT")
    print(linje)

    advarsel_map = {}   # ticker -> [advarsler]
    for a in resultater:
        advarsler = valider_aksje(a)
        if advarsler:
            advarsel_map[a["ticker"]] = advarsler

    antall_ok       = len(resultater) - len(advarsel_map)
    antall_advarsel = len(advarsel_map)
    antall_fallback = len(feil)
    antall_tapt     = len(ingen_data)

    print(f"  ✅ {antall_ok} aksjer OK")

    if advarsel_map:
        print(f"  ⚠️  {antall_advarsel} aksjer med advarsler:")
        for ticker, advarsler in advarsel_map.items():
            for advarsel in advarsler:
                print(f"     {ticker:6s} – {advarsel}")

    if feil:
        print(f"  🔄 {antall_fallback} aksjer brukte fallback-data:")
        print(f"     {', '.join(feil)}")

    if ingen_data:
        print(f"  ❌ {antall_tapt} aksjer uten data og uten fallback:")
        print(f"     {', '.join(ingen_data)}")

    print(linje)
    print(f"  Totalt: {len(AKSJER)} aksjer | {antall_ok} OK | "
          f"{antall_advarsel} advarsler | {antall_fallback} fallback | {antall_tapt} tapt")
    print(linje)

    if not resultater:
        print("\nKRITISK FEIL: Ingen aksjedata hentet og ingen fallback tilgjengelig.")
        sys.exit(1)

    if len(feil) + len(ingen_data) > len(AKSJER) // 2:
        print("\nADVARSEL: Over halvparten av aksjene feilet. Sjekk Yahoo Finance-tilkoblingen.")

    # Lagre til JSON
    output = {
        "sist_oppdatert": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kilde": "Yahoo Finance (yfinance)",
        "aksjer": resultater,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nFerdig! {len(resultater)} aksjer lagret til {output_path}")
    print(f"Sist oppdatert: {output['sist_oppdatert']}")

    # Generer sitemap.xml med oppdatert lastmod
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    sitemap_path = os.path.join(os.path.dirname(__file__), "..", "sitemap.xml")
    sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://exday.no/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://exday.no/personvern/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.3</priority>
  </url>
</urlset>"""
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write(sitemap_content)
    print(f"Sitemap oppdatert: {sitemap_path}")


if __name__ == "__main__":
    main()
