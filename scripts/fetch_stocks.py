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
import urllib.parse
import html.parser
import yfinance as yf

_TICKER_RE = re.compile(r'^[A-Z0-9]{1,10}$')

def _valider_ticker(ticker: str) -> str:
    """Kaster ValueError hvis ticker ikke matcher forventet format."""
    if not _TICKER_RE.match(ticker):
        raise ValueError(f"Ugyldig ticker-format: {ticker!r}")
    return ticker

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
            f"{_NEWSWEB_API}/v1/newsreader/list?issuer={urllib.parse.quote(ticker, safe='')}&limit=500"
        )
        messages = resp.get("data", {}).get("messages", [])

        for msg in messages:
            title = msg.get("title", "").lower()
            if "financial calendar" in title or "finansiell kalender" in title:
                msg_id = msg.get("messageId")
                full = _newsweb_get(
                    f"{_NEWSWEB_API}/v1/newsreader/message?messageId={urllib.parse.quote(str(msg_id), safe='')}"
                )
                body = full.get("data", {}).get("message", {}).get("body", "")
                if body:
                    dato = _parse_rapport_dato(body)
                    if dato:
                        return dato
    except Exception as e:
        print(f"    Advarsel Newsweb [{ticker}]: {e}")
    return None

# ── TICKER-KONFIGURASJON ─────────────────────────────────────────────────────
# Aksjer og beskrivelser leses fra data/tickers.json — legg til nye aksjer der.
_tickers_path = os.path.join(os.path.dirname(__file__), "..", "data", "tickers.json")
with open(_tickers_path, "r", encoding="utf-8") as _f:
    _ticker_data = json.load(_f)

AKSJER = [{"ticker_yf": t["ticker_yf"], "ticker": _valider_ticker(t["ticker"]),
            "navn": t["navn"], "sektor": t["sektor"], "bors": t["bors"]}
          for t in _ticker_data]

BESKRIVELSER         = {t["ticker"]: t.get("beskrivelse", "") for t in _ticker_data}
BESKRIVELSE_FAKTA    = {t["ticker"]: t.get("beskrivelse_fakta", "") for t in _ticker_data}
DNB_NAVN             = {t["ticker"]: t.get("navn_dnb", t["navn"]) for t in _ticker_data}
TICKER_YF            = {t["ticker"]: t.get("ticker_yf", t["ticker"] + ".OL") for t in _ticker_data}

_fallback_path = os.path.join(os.path.dirname(__file__), "..", "data", "fallback_data.json")
FALLBACK_DATA = {}
if os.path.exists(_fallback_path):
    with open(_fallback_path, "r", encoding="utf-8") as _ff:
        _fb_list = json.load(_ff)
        FALLBACK_DATA = {a["ticker"]: a for a in _fb_list}

# ── DNB MARKETS INTEGRASJON ─────────────────────────────────────────────────

class _DNBParser(html.parser.HTMLParser):
    """HTML-parser for DNB Markets utbytteside (server-rendered Gatsby)."""

    def __init__(self):
        super().__init__()
        self._in_tbody = False
        self._in_tr    = False
        self._in_td    = False
        self._cells    = []
        self._current  = ""
        self.rader     = []   # list of dicts med 6 felt
        _H = ["selskap", "utbytte", "valuta", "frekvens", "eks_dato", "betaling"]
        self._headers  = _H

    def handle_starttag(self, tag, attrs):
        if tag == "tbody":
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self._in_tr  = True
            self._cells  = []
        elif tag == "td" and self._in_tr:
            self._in_td  = True
            self._current = ""

    def handle_endtag(self, tag):
        if tag == "tbody":
            self._in_tbody = False
        elif tag == "tr" and self._in_tbody:
            self._in_tr = False
            if len(self._cells) >= 6:
                self.rader.append(dict(zip(self._headers, self._cells[:6])))
        elif tag == "td" and self._in_td:
            self._in_td = False
            self._cells.append(self._current.strip())

    def handle_data(self, data):
        if self._in_td:
            self._current += data


def _parse_dnb_full_dato(s: str) -> str | None:
    """Parse '3-Feb-2026' → '2026-02-03'."""
    s = s.strip()
    if not s or s == "-":
        return None
    for fmt in ("%d-%b-%Y", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_dnb_betaling_dato(s: str, ex_dt: datetime.date) -> str | None:
    """
    Parse betalingsdato uten år ('12-Feb').
    Infererer år: hvis betaling-måned >= ex-måned → samme år, ellers neste år.
    """
    s = s.strip()
    if not s or s == "-":
        return None
    try:
        d = datetime.datetime.strptime(f"{s}-{ex_dt.year}", "%d-%b-%Y")
        if d.month < ex_dt.month:
            d = d.replace(year=ex_dt.year + 1)
        return d.strftime("%Y-%m-%d")
    except ValueError:
        return None


def _finn_dnb_tabell(obj, depth: int = 0):
    """Rekursivt søk etter utbyttetabell i Gatsby page-data.json."""
    if depth > 12:
        return None
    if isinstance(obj, list) and len(obj) > 10 and isinstance(obj[0], dict):
        keys = set(obj[0].keys())
        har_dato  = any(k for k in keys if "dato" in k.lower() or "date" in k.lower() or "eks" in k.lower())
        har_navn  = any(k for k in keys if "selskap" in k.lower() or "name" in k.lower() or "company" in k.lower())
        if har_dato and har_navn:
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = _finn_dnb_tabell(v, depth + 1)
            if r:
                return r
    if isinstance(obj, list):
        for item in obj:
            r = _finn_dnb_tabell(item, depth + 1)
            if r:
                return r
    return None


def _normaliser_dnb_navn(s: str) -> str:
    """Normaliser selskapsnavn: strip parentes, erstatt non-breaking spaces, kollaps whitespace."""
    s = re.sub(r'\s*\(.*?\)', '', s)   # fjern parentetisk suffix
    s = s.replace('\xa0', ' ')          # non-breaking space → vanlig mellomrom
    s = re.sub(r'\s+', ' ', s)          # kollaps flere mellomrom
    return s.strip()


def _processer_dnb_rader(rader: list) -> dict:
    """Konverter liste av DNB-rader til {navn: {ex_dato, betaling_dato, utbytte, valuta}}-dict."""
    today = datetime.date.today()
    result: dict = {}

    for rad in rader:
        # Normaliser navn: strip parentes, \xa0, doble mellomrom
        navn = _normaliser_dnb_navn(rad.get("selskap", ""))
        if not navn:
            continue
        ex_dato = _parse_dnb_full_dato(rad.get("eks_dato", ""))
        if not ex_dato:
            continue
        ex_dt = datetime.date.fromisoformat(ex_dato)
        if ex_dt < today:
            continue   # Kun fremtidige ex-datoer
        betaling = _parse_dnb_betaling_dato(rad.get("betaling", ""), ex_dt)
        raw_utbytte = str(rad.get("utbytte", "")).replace(",", ".").replace("\xa0", "").strip()
        utbytte_belop = safe_float(raw_utbytte) if raw_utbytte else 0.0
        # Behold tidligste fremtidige ex-dato per selskap
        if navn not in result or ex_dato < result[navn]["ex_dato"]:
            result[navn] = {
                "ex_dato": ex_dato,
                "betaling_dato": betaling,
                "utbytte": utbytte_belop,
                "valuta": str(rad.get("valuta", "")).strip(),
            }

    return result


def hent_dnb_datoer() -> dict:
    """
    Henter ex-dato og betalingsdato fra DNB Markets utbyttekalender.
    Returnerer {selskapsnavn: {"ex_dato": "YYYY-MM-DD", "betaling_dato": "YYYY-MM-DD"}}.
    Prøver Gatsby page-data.json først, faller tilbake på HTML-scraping.
    """
    import html as _html_module
    import html.parser

    PAGE_DATA = "https://www.dnb.no/web/page-data/markets/aksjer/utbytteaksjer/page-data.json"
    HTML_URL  = "https://www.dnb.no/markets/aksjer/utbytteaksjer"
    HEADERS   = {
        "User-Agent": "Mozilla/5.0 (compatible; exday.no/1.0)",
        "Accept": "*/*",
    }

    # ── Forsøk 1: page-data.json ─────────────────────────────────────────────
    try:
        req = urllib.request.Request(PAGE_DATA, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        tabell = _finn_dnb_tabell(data)
        if tabell:
            rader = []
            for item in tabell:
                # Prøv å normalisere feltnavnene
                rad = {
                    "selskap":  item.get("selskap") or item.get("company") or item.get("name", ""),
                    "utbytte":  item.get("utbytte") or item.get("dividend", ""),
                    "valuta":   item.get("valuta")  or item.get("currency", ""),
                    "frekvens": item.get("frekvens") or item.get("frequency", ""),
                    "eks_dato": item.get("eks_dato") or item.get("exDate") or item.get("ex_date", ""),
                    "betaling": item.get("betaling") or item.get("payDate") or item.get("payment_date", ""),
                }
                rader.append(rad)
            resultat = _processer_dnb_rader(rader)
            if resultat:
                print(f"  DNB: {len(resultat)} selskaper fra page-data.json")
                return resultat
    except Exception as e:
        print(f"  DNB page-data.json: {e}")

    # ── Forsøk 2: HTML-scraping ───────────────────────────────────────────────
    try:
        req = urllib.request.Request(HTML_URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            tekst = r.read().decode("utf-8", errors="replace")
        parser = _DNBParser()
        parser.feed(tekst)
        if parser.rader:
            resultat = _processer_dnb_rader(parser.rader)
            print(f"  DNB: {len(resultat)} selskaper fra HTML ({len(parser.rader)} rader funnet)")
            return resultat
    except Exception as e:
        print(f"  DNB HTML: {e}")

    print("  DNB: Kunne ikke hente datodata – hopper over")
    return {}


def hent_euronext_priser() -> dict:
    """
    Henter live-priser for alle Oslo Børs-aksjer fra Euronext CSV-nedlasting.
    Returnerer {ticker: pris} for bruk som prisfallback.
    CSV-format (semikolonseparert, 4 headerlinjer):
      Name;ISIN;Symbol;Market;Currency;"Open Price";"High Price";"low Price";"last Price";...
    Kolonneindekser: Symbol=[2], Last price=[8]
    """
    import csv, io
    # Noen tickers bruker annet symbol på Euronext enn på Oslo Børs
    _EURONEXT_MAP = {
        "ENTRA": "ENTR", "DOFG": "DOF", "OTL": "OLT", "VISTN": "VISTIN",
        "NORBT": "NORBIT", "PNOR": "PNORD", "JAREN": "JAEDR",
        # Sparebanker og andre med avvikende Euronext-ticker
        "MORG": "SBMO",    # Sparebanken Møre
        "RING": "SRHA",    # SpareBank 1 Ringerike Hadeland
        "STRO": "STRONG",  # Strongpoint (Euronext STRO → vår STRONG; YF bruker STRO.OL)
        "SNI":  "STRO",    # Stolt-Nielsen (Euronext SNI → vår STRO; YF bruker SNI.OL)
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; exday.no/1.0)",
        "Accept": "text/csv,text/plain,*/*",
    }
    priser = {}
    try:
        url = "https://live.euronext.com/pd_es/data/stocks/download?mics=XOSL%2CMERK%2CXOAS"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")

        # Hopp over 4 headerlinjer
        lines = raw.splitlines()
        skip = 0
        for i, line in enumerate(lines):
            if line.startswith("Name") or line.startswith('"Name'):
                skip = i + 1
                break
        data_lines = lines[skip:]

        reader = csv.reader(io.StringIO("\n".join(data_lines)), delimiter=";")
        for row in reader:
            if len(row) < 9:
                continue
            raw_ticker = row[2].strip().strip('"')
            if not raw_ticker:
                continue
            ticker = _EURONEXT_MAP.get(raw_ticker, raw_ticker)
            pris_str = row[8].strip().strip('"').replace('\xa0', '').replace(' ', '').replace(',', '.')
            if not pris_str or pris_str in ('-', ''):
                continue
            try:
                p = float(pris_str)
                if p > 0 and ticker not in priser:
                    priser[ticker] = p
            except (ValueError, TypeError):
                pass
    except Exception as e:
        print(f"  Euronext CSV: {e}")
    print(f"  Euronext: {len(priser)} priser hentet (CSV-nedlasting)")
    return priser


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

        # Antall år med utbytte (unike kalenderår med faktisk utbyttebetaling)
        if not dividends.empty:
            ar_med_utbytte = int(dividends.index.year.nunique())
        else:
            ar_med_utbytte = 0

        # Ex-dato og betalingsdato
        ex_dato = None
        betaling_dato = None
        if isinstance(calendar, dict):
            ex_dato = format_dato(calendar.get("exDividendDate"))
            betaling_dato = format_dato(calendar.get("dividendDate"))
        # Oslo Børs bruker T+1-oppgjør (siden okt 2024). Yahoo Finance rapporterer
        # ex-datoer korrekt for norske aksjer — ingen +1-korreksjon nødvendig.

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

        # Sanity-sjekk: hvis yield er mer enn 3× historisk snitt-yield, bruk snitt i stedet
        # (beskytter mot Yahoo Finance-feil med trailingAnnualDividendRate)
        if snitt_yield_5ar > 0 and utbytte_yield > snitt_yield_5ar * 3:
            print(f"    Advarsel [{ticker}]: yield {utbytte_yield:.1f}% >> snitt {snitt_yield_5ar:.1f}% — bruker snitt")
            utbytte_yield = snitt_yield_5ar
            utbytte_per_aksje = round(pris * snitt_yield_5ar / 100, 4) if pris > 0 else 0

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
            "beskrivelse_fakta": BESKRIVELSE_FAKTA.get(ticker, ""),
            "valuta": valuta,
            "data_kilde": "yahoo",
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
    pris = a.get("pris", 0)
    upa  = a.get("utbytte_per_aksje", 0)
    if pris > 0 and upa > 0:
        beregnet = (upa / pris) * 100
        lagret   = a.get("utbytte_yield", 0)
        if lagret > 0:
            avvik_pct = abs(beregnet - lagret) / max(beregnet, 0.01) * 100
            if avvik_pct > 25:
                advarsler.append(
                    f"[1] Yield-avvik {avvik_pct:.0f}%: "
                    f"beregnet {beregnet:.2f}% vs lagret {lagret:.2f}%"
                )

    # ── 2. Pris-validering ────────────────────────────────────────────────────
    if pris <= 0:
        advarsler.append(f"[2] Ugyldig pris: {pris}")
    elif pris > 100_000:
        advarsler.append(f"[2] Mistenkelig høy pris: {pris}")

    # ── 3. Feltplausibilitet ──────────────────────────────────────────────────
    payout = a.get("payout_ratio", 0)
    pe     = a.get("pe_ratio", 0)
    lav52  = a.get("52u_lav", 0)
    hoy52  = a.get("52u_hoy", 0)
    if payout > 300:
        advarsler.append(f"[3] Payout ratio ekstremt høy: {payout}%")
    if 0 < pe > 500:
        advarsler.append(f"[3] Mistenkelig høy P/E: {pe}")
    if a.get("utbytte_yield", 0) > 80:
        advarsler.append(f"[3] Ekstremt høy yield: {a.get('utbytte_yield')}% — sjekk manuelt")
    if a.get("utbytte_per_aksje", 0) > 0 and a.get("pris", 0) > 0 and a["utbytte_per_aksje"] > a["pris"]:
        advarsler.append(
            f"[3] Utbytte/aksje ({a['utbytte_per_aksje']}) > kurs ({a['pris']}) — umulig"
        )
    if lav52 > 0 and hoy52 > 0 and lav52 > hoy52:
        advarsler.append(
            f"[3] 52u lav ({lav52}) > 52u høy ({hoy52}) — data-feil"
        )

    # ── 4. Manglende kritiske felt ────────────────────────────────────────────
    mangler = []
    if a.get("pris", 0) == 0:               mangler.append("pris")
    if a.get("utbytte_yield", 0) == 0:      mangler.append("utbytte_yield")
    if a.get("utbytte_per_aksje", 0) == 0:  mangler.append("utbytte_per_aksje")
    if not a.get("ex_dato"):         mangler.append("ex_dato")
    if mangler:
        advarsler.append(f"[4] Manglende felt: {', '.join(mangler)}")

    return advarsler


def _generer_hist_chart(hist, valuta="NOK"):
    """Lager et inline SVG søylediagram med Y-akse og hover-tooltip for historiske utbytter."""
    if not hist or len(hist) < 2:
        return ""

    sortert = sorted(hist, key=lambda x: x["ar"])
    maks = max(h["utbytte"] for h in sortert) or 1

    W, H = 420, 180
    pad_l, pad_r, pad_t, pad_b = 52, 12, 16, 32
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n = len(sortert)
    bar_w = max(8, min(36, int(chart_w / n) - 4))
    spacing = chart_w / n

    # Y-akse ticks (4 nivåer)
    ticks = [round(maks * i / 3, 2) for i in range(4)]

    bars = []
    labels = []
    tooltips = []
    for i, h in enumerate(sortert):
        x = pad_l + spacing * i + spacing / 2
        bh = (h["utbytte"] / maks) * chart_h
        by = pad_t + chart_h - bh
        bars.append(
            f'<rect class="hbar" x="{x - bar_w/2:.1f}" y="{by:.1f}" '
            f'width="{bar_w}" height="{bh:.1f}" rx="3" fill="#16a34a" opacity="0.85"/>'
        )
        labels.append(
            f'<text x="{x:.1f}" y="{H - 6}" text-anchor="middle" '
            f'font-size="10" fill="#9ca3af">{h["ar"]}</text>'
        )
        tip = f'{h["utbytte"]} {valuta} · {h["yield"]:.1f}% yield'
        tooltips.append(
            f'<rect class="htip-bg" x="{min(x - 52, W - pad_r - 106):.1f}" y="{max(by - 28, 2):.1f}" '
            f'width="106" height="20" rx="4" fill="#111827" opacity="0" pointer-events="none"/>'
            f'<text class="htip-txt" x="{min(x, W - pad_r - 4):.1f}" y="{max(by - 13, 14):.1f}" '
            f'text-anchor="middle" font-size="10" fill="#f3f4f6" opacity="0" pointer-events="none">{tip}</text>'
            f'<rect class="htrig" x="{x - spacing/2:.1f}" y="{pad_t}" '
            f'width="{spacing:.1f}" height="{chart_h}" fill="transparent" '
            f'onmouseenter="showTip(this)" onmouseleave="hideTip(this)" data-i="{i}"/>'
        )

    y_ticks = []
    for t in ticks:
        y = pad_t + chart_h - (t / maks) * chart_h
        y_ticks.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W - pad_r}" y2="{y:.1f}" '
            f'stroke="#e5e7eb" stroke-width="1" class="ytick"/>'
            f'<text x="{pad_l - 4}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="10" fill="#9ca3af">{t}</text>'
        )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;max-width:{W}px;height:auto;display:block;margin-bottom:0.5rem;" '
        f'aria-label="Historiske utbytter per aksje i {valuta}">'
        + "".join(y_ticks)
        + "".join(bars)
        + "".join(labels)
        + "".join(tooltips)
        + f'<text x="{pad_l - 36}" y="{pad_t + chart_h/2:.1f}" text-anchor="middle" '
        f'font-size="10" fill="#9ca3af" transform="rotate(-90,{pad_l - 36},{pad_t + chart_h/2:.1f})">'
        f'{valuta} per aksje</text>'
        + "</svg>"
        + """<script>
function showTip(el){var i=el.dataset.i,s=el.closest('svg'),bg=s.querySelectorAll('.htip-bg')[i],tx=s.querySelectorAll('.htip-txt')[i];bg.setAttribute('opacity','0.92');tx.setAttribute('opacity','1');}
function hideTip(el){var i=el.dataset.i,s=el.closest('svg'),bg=s.querySelectorAll('.htip-bg')[i],tx=s.querySelectorAll('.htip-txt')[i];bg.setAttribute('opacity','0');tx.setAttribute('opacity','0');}
</script>"""
    )
    return svg


def _fmt_dato(iso):
    """Formaterer ISO-dato til lesbar norsk form, f.eks. 14. mars 2026."""
    if not iso:
        return "—"
    try:
        d = datetime.date.fromisoformat(iso)
        mnd = ["jan","feb","mar","apr","mai","jun","jul","aug","sep","okt","nov","des"]
        return f"{d.day}. {mnd[d.month-1]} {d.year}"
    except Exception:
        return iso


def _lag_analyse_tekst(a):
    """Bygger et analytisk avsnitt om yield, payout og veksttrender."""
    deler = []
    yield_ = a.get("utbytte_yield") or 0
    snitt5 = a.get("snitt_yield_5ar") or 0
    payout = a.get("payout_ratio") or 0
    vekst  = a.get("utbytte_vekst_5ar")

    if yield_ > 0 and snitt5 > 0:
        diff = yield_ - snitt5
        if diff > 1.5:
            deler.append(
                f"Nåværende direkteavkastning på {yield_:.1f}% er betydelig høyere enn "
                f"5-årssnittet på {snitt5:.1f}%, noe som kan indikere et midlertidig "
                "kursfall eller ekstraordinært utbytte."
            )
        elif diff < -1.5:
            deler.append(
                f"Nåværende direkteavkastning på {yield_:.1f}% er lavere enn "
                f"5-årssnittet på {snitt5:.1f}%, noe som tyder på sterk kursvekst de siste årene."
            )
        else:
            deler.append(
                f"Direkteavkastningen på {yield_:.1f}% ligger nær 5-årssnittet på {snitt5:.1f}%, "
                "som indikerer stabil kurs- og utbytteutvikling."
            )

    if payout > 0:
        if payout < 50:
            deler.append(
                f"Utbetalingsgraden på {payout:.0f}% gir godt rom for fremtidige utbytteøkninger."
            )
        elif payout < 80:
            deler.append(
                f"Utbetalingsgraden på {payout:.0f}% er bærekraftig."
            )
        else:
            deler.append(
                f"Utbetalingsgraden på {payout:.0f}% er høy — utbyttet kan være "
                "sårbart ved svakere inntjening."
            )

    if vekst is not None and abs(vekst) > 0.5:
        if vekst > 0:
            deler.append(
                f"Utbyttet har vokst med {vekst:.1f}% per år de siste 5 årene."
            )
        else:
            deler.append(
                f"Utbyttet har falt med {abs(vekst):.1f}% per år de siste 5 årene."
            )

    return " ".join(deler)


def _lag_utbytte_profil(a, sektor_snitt):
    """Investor-profil med badges og sektorsammenligning."""
    ticker = a["ticker"]
    navn   = a["navn"]
    sektor = a.get("sektor") or "Annet"
    yield_ = a.get("utbytte_yield") or 0
    snitt5 = a.get("snitt_yield_5ar") or 0
    ar_med = a.get("ar_med_utbytte") or 0
    vekst  = a.get("utbytte_vekst_5ar")
    payout = a.get("payout_ratio") or 0

    SYKLISKE  = {"Shipping", "Energi", "Havbruk", "Materialer", "Energitjenester"}
    DEFENSIVE = {"Finans", "Eiendom", "Telekommunikasjon", "Forsyning", "Helsevern"}

    badges = []
    if yield_ >= 5:
        badges.append(("Høy yield",      "badge-green"))
    if ar_med >= 10:
        badges.append(("Stabil betaler",  "badge-blue"))
    if vekst is not None and vekst > 1:
        badges.append(("Utbyttevekst",    "badge-teal"))
    if sektor in SYKLISKE:
        badges.append(("Syklisk",         "badge-orange"))
    elif sektor in DEFENSIVE:
        badges.append(("Defensiv",        "badge-gray"))

    badge_html = "".join(
        f'<span class="profil-badge {cls}">{label}</span>'
        for label, cls in badges
    )

    # Sektorsammenligning-tekst
    sn = sektor_snitt.get(sektor, 0)
    tekst_deler = []
    if yield_ > 0 and sn > 0:
        if yield_ >= sn * 1.1:
            tekst_deler.append(
                f"{ticker} gir {yield_:.1f}% direkteavkastning, "
                f"over sektorsnittet for {sektor.lower()} på {sn:.1f}%."
            )
        elif yield_ <= sn * 0.9:
            tekst_deler.append(
                f"{ticker} gir {yield_:.1f}% direkteavkastning, "
                f"noe under sektorsnittet for {sektor.lower()} på {sn:.1f}%."
            )
        else:
            tekst_deler.append(
                f"{ticker} gir {yield_:.1f}% direkteavkastning, "
                f"nær sektorsnittet for {sektor.lower()} på {sn:.1f}%."
            )
    if ar_med >= 15:
        tekst_deler.append(
            f"Med {ar_med} år på rad med utbytte er {navn} "
            f"blant de mest stabile utbyttebetalerne på Oslo Børs."
        )
    elif ar_med >= 5:
        tekst_deler.append(
            f"Selskapet har betalt utbytte {ar_med} år på rad."
        )
    if payout > 0 and payout < 50:
        tekst_deler.append("Lav utbetalingsgrad gir rom for fremtidige utbytteøkninger.")
    elif payout >= 100:
        tekst_deler.append("Utbetalingsgraden er over 100% — utbyttet finansieres delvis av kapital.")

    tekst_html = f'<p class="profil-tekst">{" ".join(tekst_deler)}</p>' if tekst_deler else ""

    return (
        f'<div class="profil-seksjon">'
        f'<h2>Utbytteprofil</h2>'
        f'<div class="profil-badges">{badge_html}</div>'
        f'{tekst_html}'
        f'</div>'
    ) if (badge_html or tekst_html) else ""


def _lag_historikk_prosa(a):
    """Narrativ tekst basert på historiske utbyttedata."""
    navn  = a["navn"]
    hist  = a.get("historiske_utbytter") or []
    valuta = a.get("valuta") or "NOK"
    yield_ = a.get("utbytte_yield") or 0
    upa    = a.get("utbytte_per_aksje") or 0

    if len(hist) < 2:
        return ""

    sortert  = sorted(hist, key=lambda x: x["ar"])
    antall_ar = len(sortert)
    min_h    = min(sortert, key=lambda x: x["utbytte"])
    max_h    = max(sortert, key=lambda x: x["utbytte"])
    siste    = sortert[-1]

    deler = []
    deler.append(
        f"{navn} har de siste {antall_ar} årene betalt mellom "
        f"{min_h['utbytte']:.2f} og {max_h['utbytte']:.2f} {valuta} per aksje i utbytte."
    )
    if max_h["ar"] != siste["ar"]:
        deler.append(
            f"Det høyeste utbyttet ble registrert i {max_h['ar']} "
            f"med {max_h['utbytte']:.2f} {valuta} per aksje "
            f"({max_h.get('yield', 0):.1f}% yield)."
        )
    if upa > 0 and yield_ > 0:
        deler.append(
            f"I {siste['ar']} er utbyttet {siste['utbytte']:.2f} {valuta} per aksje, "
            f"tilsvarende {yield_:.1f}% direkteavkastning."
        )

    return (
        f'<div class="historikk-prosa">'
        f'<h2>Utbyttehistorikk</h2>'
        f'<p>{" ".join(deler)}</p>'
        f'</div>'
    )


SEKTOR_RISIKOER = {
    "Energi": [
        "Olje- og gasspris påvirker inntjeningen direkte og kan svinge kraftig",
        "Energiomstilling og ESG-krav kan presse markedsverdi over tid",
        "Statlig eierstyring kan påvirke utbyttepolitikk",
    ],
    "Energitjenester": [
        "Aktivitetsnivå i olje- og gassektoren styrer etterspørselen",
        "Prispress fra internasjonale konkurrenter",
        "Syklisk inntjening gjør utbyttet konjunkturavhengig",
    ],
    "Shipping": [
        "Fraktrater er svært volatile og kan halves på kort tid",
        "Bunkerspriser (drivstoff) påvirker driftsmarginene direkte",
        "Overkapasitet i markedet kan presse ratene ned i lengre perioder",
    ],
    "Havbruk": [
        "Laksepris varierer med globalt tilbud og etterspørsel",
        "Biologisk risiko (lakselus, sykdom) kan redusere produksjonsvolum",
        "Eksportrestriksjoner og politisk risiko i nøkkelmarkeder",
    ],
    "Finans": [
        "Rentenivå påvirker netto renteinntekter og utlånsmargin",
        "Økte kredittap i nedgangstider kan presse resultater",
        "Regulatoriske kapitalkrav begrenser utbyttekapasitet",
    ],
    "Eiendom": [
        "Renteøkninger øker finansieringskostnader og presser verdivurderinger",
        "Ledighetsgrad og leiepriser varierer med konjunktur",
        "Refinansiering av gjeld kan være utfordrende i et stramt marked",
    ],
    "Fornybar energi": [
        "Strømpris er volatil og avgjørende for inntjening",
        "Regulatorisk risiko knyttet til støtteordninger og konsesjoner",
        "Høye investeringsbehov kan begrense utbyttekapasitet",
    ],
    "Materialer": [
        "Råvareprisene er sykliske og konjunkturfølsomme",
        "Valutaeksponering ved internasjonal omsetning kan påvirke marginer",
        "Miljøregulering kan øke driftskostnader",
    ],
    "Industri": [
        "Konjunkturfølsomhet påvirker ordrevolum og marginer",
        "Råvare- og energikostnader kan variere betydelig",
        "Valuta- og eksportrisiko for internasjonale selskaper",
    ],
    "Telekommunikasjon": [
        "Prispress fra konkurranse kan redusere marginer",
        "Høye investeringer i infrastruktur binder kapital",
        "Regulatorisk usikkerhet rundt frekvenstillatelser",
    ],
    "Forbruksvarer": [
        "Konjunkturnedgang reduserer forbrukernes kjøpekraft",
        "Priskonkurranse fra netthandel og lavprisaktører",
        "Råvarekostnader (emballasje, ingredienser) varierer",
    ],
    "Helsevern": [
        "Regulatorisk godkjenning og patent-utløp kan endre inntjeningsbildet",
        "Prispress fra offentlige innkjøpere",
        "Høye FoU-kostnader kan begrense utbyttekapasitet",
    ],
    "Forsyning": [
        "Regulerte tariffer begrenser vekstpotensialet",
        "Høye kapitalinvesteringer i nett og infrastruktur",
        "Politisk risiko knyttet til prissetting og konsesjoner",
    ],
    "Informasjonsteknologi": [
        "Rask teknologiutvikling kan gjøre produkter utdaterte",
        "Høy konkurranse fra internasjonale aktører presser marginer",
        "Høye investeringsbehov i utvikling og salg",
    ],
    "Kommunikasjonstjenester": [
        "Prispress og høy konkurranse i digitale medier",
        "Regulatoriske krav knyttet til personvern og innhold",
        "Annonseinntekter er konjunkturfølsomme",
    ],
}
STANDARD_RISIKOER = [
    "Makroøkonomisk nedgang kan påvirke inntjening og utbyttekapasitet",
    "Valuta- og renteeksponering kan påvirke resultater",
    "Regulatoriske endringer kan påvirke driftsbetingelser",
]


def _lag_risikofaktorer(a):
    """Sektor-spesifikke risikofaktorer for utbyttet."""
    sektor = a.get("sektor") or ""
    risikoer = SEKTOR_RISIKOER.get(sektor, STANDARD_RISIKOER)
    punkter = "\n".join(f"<li>{r}</li>" for r in risikoer)
    return (
        f'<div class="risiko-seksjon">'
        f'<h2>Risiko for utbyttet</h2>'
        f'<ul class="risiko-liste">{punkter}</ul>'
        f'</div>'
    )


def _aksje_side_html(a, today, relaterte=None, sektor_snitt=None):
    ticker  = a["ticker"]
    navn    = a["navn"]
    sektor  = a.get("sektor") or "—"
    pris    = a.get("pris") or 0
    yield_  = a.get("utbytte_yield") or 0
    ex      = a.get("ex_dato") or ""
    bet     = a.get("betaling_dato") or ""
    frekvens = a.get("frekvens") or "—"
    upa     = a.get("utbytte_per_aksje") or 0
    pe      = a.get("pe_ratio") or 0
    ar_med  = a.get("ar_med_utbytte") or 0
    besk         = a.get("beskrivelse_fakta") or a.get("beskrivelse") or ""
    ai_opp       = a.get("ai_oppsummering") or ""
    ai_opp_dato  = a.get("ai_oppsummering_dato") or ""
    hist         = a.get("historiske_utbytter") or []
    snitt5  = a.get("snitt_yield_5ar") or 0
    valuta  = a.get("valuta") or "NOK"
    payout  = a.get("payout_ratio") or 0
    vekst   = a.get("utbytte_vekst_5ar")
    mrd     = a.get("markedsverdi_mrd") or 0
    hoy52   = a.get("52u_hoy") or 0
    lav52   = a.get("52u_lav") or 0

    meta_desc = (
        f"{navn} ({ticker}) betaler {yield_:.2f}% utbytte ({sektor}). "
        f"Ex-dato: {_fmt_dato(ex)}. "
        f"5-årssnitt yield: {snitt5:.2f}%. "
        f"Siste utbytte: {upa} {valuta} per aksje. "
        f"Oppdatert daglig på exday.no."
    )

    hist_rader = ""
    for h in sorted(hist, key=lambda x: x["ar"], reverse=True):
        hist_rader += f"""
        <tr>
          <td>{h["ar"]}</td>
          <td>{h["utbytte"]} {valuta}</td>
          <td>{h["yield"]:.2f}%</td>
        </tr>"""

    pe_rad = f"<tr><td>P/E</td><td>{pe:.1f}</td></tr>" if pe and pe > 0 else ""

    pe_card = (
        f'<div class="kcard"><div class="label">P/E</div>'
        f'<div class="val">{pe:.1f}</div></div>'
    ) if pe and pe > 0 else ""

    payout_rad = f"<tr><td>Payout ratio</td><td>{payout:.0f}%</td></tr>" if payout > 0 else ""
    vekst_rad  = (
        f"<tr><td>Utbyttevekst 5 år</td><td>{'+' if vekst >= 0 else ''}{vekst:.1f}% p.a.</td></tr>"
        if vekst is not None else ""
    )
    mrd_rad    = f"<tr><td>Markedsverdi</td><td>{mrd:.1f} mrd NOK</td></tr>" if mrd > 0 else ""
    kurs52_rad = (
        f"<tr><td>52-ukers kurs</td><td>{lav52} – {hoy52} {valuta}</td></tr>"
        if hoy52 > 0 and lav52 > 0 else ""
    )

    om_seksjon = f'<div class="desc"><h2>Om selskapet</h2><p>{besk}</p></div>' if besk else ""

    ai_dato_tekst = f' <span class="ai-dato">Oppdatert {ai_opp_dato}</span>' if ai_opp_dato else ""
    ai_oppsummering_seksjon = (
        f'<div class="ai-oppsummering">'
        f'<h2>AI-oppsummering{ai_dato_tekst}</h2>'
        f'<p>{ai_opp}</p>'
        f'</div>'
    ) if ai_opp else ""

    analyse_tekst   = _lag_analyse_tekst(a)
    analyse_seksjon = (
        f'<div class="analyse"><h2>Utbytteanalyse</h2><p>{analyse_tekst}</p></div>'
        if analyse_tekst else ""
    )

    nokkeltal_seksjon = (
        "<h2>Nøkkeltall</h2>"
        "<table>"
        "<thead><tr><th>Nøkkeltall</th><th>Verdi</th></tr></thead>"
        "<tbody>"
        f"<tr><td>Sektor</td><td>{sektor}</td></tr>"
        f"<tr><td>Frekvens</td><td>{frekvens}</td></tr>"
        f"<tr><td>Utbytte per aksje</td><td>{upa} {valuta}</td></tr>"
        f"<tr><td>Direkteavkastning</td><td>{f'{yield_:.2f}%' if yield_ else '—'}</td></tr>"
        f"<tr><td>5-årssnitt yield</td><td>{snitt5:.2f}%</td></tr>"
        f"<tr><td>År med utbytte</td><td>{ar_med}</td></tr>"
        f"{pe_rad}"
        f"{payout_rad}"
        f"{vekst_rad}"
        f"{mrd_rad}"
        f"{kurs52_rad}"
        "</tbody></table>"
    )

    hist_chart = _generer_hist_chart(hist, valuta)
    hist_seksjon = (
        "<h2>Historiske utbytter</h2>"
        + hist_chart
        + "<table>"
        "<thead><tr><th>År</th><th>Utbytte</th><th>Yield</th></tr></thead>"
        f"<tbody>{hist_rader}</tbody>"
        "</table>"
    ) if hist_rader else ""

    # Nye innholdsseksjoner
    profil_html    = _lag_utbytte_profil(a, sektor_snitt or {})
    hist_prosa_html = _lag_historikk_prosa(a)
    risiko_html    = _lag_risikofaktorer(a)

    # Relaterte aksjer
    relaterte_html = ""
    if relaterte:
        kort = "\n".join(
            f'<a href="/aksjer/{r["ticker"]}/" class="rel-kort">'
            f'<span class="rel-ticker">{r["ticker"]}</span>'
            f'<span class="rel-navn">{r["navn"]}</span>'
            f'<span class="rel-yield">{r.get("utbytte_yield", 0):.1f}%</span>'
            f'</a>'
            for r in relaterte
        )
        relaterte_html = (
            f'<div class="relaterte"><h2>Andre {sektor.lower()}-aksjer med utbytte</h2>'
            f'<div class="rel-grid">{kort}</div></div>'
        )

    ld_graph = [
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Hjem",   "item": "https://exday.no/"},
                {"@type": "ListItem", "position": 2, "name": "Aksjer", "item": "https://exday.no/aksjer/"},
                {"@type": "ListItem", "position": 3, "name": ticker,   "item": f"https://exday.no/aksjer/{ticker}/"},
            ]
        },
        {
            "@type": "FinancialProduct",
            "name": f"{navn} ({ticker})",
            "description": (besk or meta_desc)[:500],
            "url": f"https://exday.no/aksjer/{ticker}/",
            "provider": {"@type": "Organization", "name": "exday.no", "url": "https://exday.no/"},
        },
    ]
    json_ld = json.dumps({"@context": "https://schema.org", "@graph": ld_graph}, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="nb">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <!-- Google Analytics med Consent Mode v2 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-X6C9PERKMB"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('consent', 'default', {{
      analytics_storage: 'denied',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      wait_for_update: 500
    }});
    gtag('js', new Date());
    gtag('config', 'G-X6C9PERKMB');
  </script>
  <script src="/assets/consent.js" defer></script>
  <title>{ticker} – {navn} | Utbytte og ex-dato | exday.no</title>
  <meta name="description" content="{meta_desc}"/>
  <link rel="canonical" href="https://exday.no/aksjer/{ticker}/"/>
  <meta name="theme-color" content="#16a34a"/>
  <link rel="icon" type="image/png" sizes="512x512" href="/favicon.png"/>
  <link rel="icon" type="image/png" sizes="180x180" href="/logo/apple_touch_icon_180.png"/>
  <link rel="icon" type="image/svg+xml" href="/logo/exday_icon_primary.svg"/>
  <link rel="shortcut icon" href="/favicon.png"/>
  <link rel="apple-touch-icon" href="/logo/apple_touch_icon_180.png"/>
  <meta property="og:title" content="{ticker} – {navn} | exday.no"/>
  <meta property="og:description" content="{meta_desc}"/>
  <meta property="og:url" content="https://exday.no/aksjer/{ticker}/"/>
  <meta property="og:type" content="website"/>
  <script type="application/ld+json">{json_ld}</script>
  <link rel="stylesheet" href="/assets/tailwind.css"/>
  <link rel="stylesheet" href="/assets/style.css"/>
  <script>
    (function(){{
      var t = localStorage.getItem('tema');
      if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {{
        document.documentElement.classList.add('dark');
      }}
    }})();
  </script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; }}
    a {{ color: #16a34a; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 760px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
    .breadcrumb {{ font-size: 0.85rem; color: #6b7280; margin-bottom: 1.5rem; }}
    .breadcrumb a {{ color: #6b7280; }}
    .breadcrumb span {{ margin: 0 0.35rem; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }}
    .sub {{ font-size: 0.95rem; margin-bottom: 1.5rem; }}
    .badge {{ display: inline-block; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem;
              border-radius: 9999px; margin-bottom: 1.25rem; }}
    .kgrid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
    .kcard {{ border-radius: 0.75rem; padding: 1rem; border: 1px solid; }}
    .kcard .label {{ font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.2rem; }}
    .kcard .val {{ font-size: 1.25rem; font-weight: 700; }}
    .kcard .val.green {{ color: #16a34a; }}
    .desc {{ border-radius: 0.75rem; padding: 1rem 1.25rem; margin-bottom: 1.5rem; border: 1px solid; }}
    .desc h2 {{ margin-bottom: 0.5rem; }}
    .analyse {{ border-radius: 0.75rem; padding: 1rem 1.25rem; margin: 1rem 0 1.5rem; border: 1px solid; line-height: 1.75; }}
    .analyse h2 {{ margin-bottom: 0.4rem; }}
    .ai-oppsummering {{ border-radius: 0.75rem; padding: 1rem 1.25rem; margin: 1rem 0 1.5rem; border: 1px solid; line-height: 1.75; }}
    .ai-oppsummering h2 {{ margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }}
    .ai-dato {{ font-size: 0.7rem; font-weight: 400; padding: 0.15rem 0.5rem; border-radius: 9999px; }}
    h2 {{ font-size: 1rem; font-weight: 700; margin-bottom: 0.75rem; }}
    table {{ width: 100%; border-collapse: collapse; border-radius: 0.75rem; overflow: hidden; margin-bottom: 1.5rem; font-size: 0.9rem; border: 1px solid; }}
    th {{ padding: 0.6rem 1rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }}
    td {{ padding: 0.6rem 1rem; border-top: 1px solid; }}
    .cta {{ text-align: center; margin-top: 2rem; padding: 1.5rem; border-radius: 0.75rem; border: 1px solid; }}
    .cta a {{ display: inline-block; background: #16a34a; color: #fff !important; font-weight: 600; padding: 0.65rem 1.5rem; border-radius: 0.5rem; text-decoration: none; }}
    .cta a:hover {{ background: #15803d; }}
    .updated {{ font-size: 0.78rem; text-align: right; margin-top: 1rem; }}
    .mini-nav {{ display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 1.5rem; font-size: 0.85rem; }}
    .mini-nav a {{ color: #16a34a; }}
    .profil-seksjon {{ margin: 1.5rem 0; }}
    .profil-badges {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 0.75rem; }}
    .profil-badge {{ font-size: 0.75rem; font-weight: 600; padding: 0.25rem 0.75rem; border-radius: 9999px; }}
    .badge-green {{ background: #dcfce7; color: #15803d; }}
    .badge-blue {{ background: #dbeafe; color: #1d4ed8; }}
    .badge-teal {{ background: #ccfbf1; color: #0f766e; }}
    .badge-orange {{ background: #ffedd5; color: #c2410c; }}
    .badge-gray {{ background: #f3f4f6; color: #374151; }}
    .profil-tekst {{ font-size: 0.9rem; line-height: 1.65; }}
    .historikk-prosa {{ margin: 1.5rem 0; }}
    .historikk-prosa p {{ font-size: 0.9rem; line-height: 1.7; }}
    .risiko-seksjon {{ margin: 1.5rem 0; }}
    .risiko-liste {{ list-style: none; padding: 0; margin: 0; }}
    .risiko-liste li {{ font-size: 0.875rem; padding: 0.5rem 0.75rem; border-left: 3px solid #fca5a5; margin-bottom: 0.5rem; line-height: 1.5; }}
    .relaterte {{ margin: 1.5rem 0; }}
    .relaterte h2 {{ margin-bottom: 0.75rem; }}
    .rel-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 0.75rem; }}
    .rel-kort {{ border-radius: 0.75rem; padding: 0.75rem 1rem; border: 1px solid; display: flex; flex-direction: column; gap: 0.2rem; text-decoration: none; transition: border-color 0.15s; }}
    .rel-kort:hover {{ border-color: #16a34a; text-decoration: none; }}
    .rel-ticker {{ font-weight: 700; font-size: 1rem; color: #16a34a; }}
    .rel-navn {{ font-size: 0.75rem; }}
    .rel-yield {{ font-size: 0.8rem; font-weight: 600; color: #16a34a; }}
    @media (max-width: 480px) {{ h1 {{ font-size: 1.4rem; }} }}

    /* Light mode */
    body {{ background: #f9fafb; color: #111827; }}
    .kcard {{ background: #fff; border-color: #e5e7eb; }}
    .kcard .label {{ color: #9ca3af; }}
    .kcard .val {{ color: #111827; }}
    .desc {{ background: #fff; border-color: #e5e7eb; color: #374151; }}
    .analyse {{ background: #f0fdf4; border-color: #bbf7d0; color: #374151; }}
    .analyse h2 {{ color: #15803d; }}
    .ai-oppsummering {{ background: #eff6ff; border-color: #bfdbfe; color: #374151; }}
    .ai-oppsummering h2 {{ color: #1d4ed8; }}
    .ai-dato {{ background: #dbeafe; color: #1e40af; }}
    h2 {{ color: #374151; }}
    table {{ background: #fff; border-color: #e5e7eb; }}
    th {{ background: #f3f4f6; color: #6b7280; }}
    td {{ border-color: #f3f4f6; }}
    tr:hover td {{ background: #f9fafb; }}
    .cta {{ background: #f0fdf4; border-color: #bbf7d0; }}
    .cta p {{ color: #374151; }}
    .updated {{ color: #9ca3af; }}
    .breadcrumb {{ color: #6b7280; }}
    .sub {{ color: #6b7280; }}
    .faq-item {{ background: #fff; border-color: #e5e7eb; }}
    .faq-q {{ color: #111827; }}
    .faq-a {{ color: #374151; }}
    .rel-kort {{ background: #fff; border-color: #e5e7eb; }}
    .rel-navn {{ color: #6b7280; }}
    .badge {{ background: #dcfce7; color: #15803d; }}

    /* Dark mode */
    .dark body {{ background: #030712; color: #f3f4f6; }}
    .dark .kcard {{ background: #111827; border-color: #1f2937; }}
    .dark .kcard .label {{ color: #6b7280; }}
    .dark .kcard .val {{ color: #f3f4f6; }}
    .dark .desc {{ background: #111827; border-color: #1f2937; color: #d1d5db; }}
    .dark .analyse {{ background: #052e16; border-color: #166534; color: #d1d5db; }}
    .dark .analyse h2 {{ color: #4ade80; }}
    .dark .ai-oppsummering {{ background: #0f1729; border-color: #1e3a5f; color: #d1d5db; }}
    .dark .ai-oppsummering h2 {{ color: #93c5fd; }}
    .dark .ai-dato {{ background: #1e3a5f; color: #93c5fd; }}
    .dark h2 {{ color: #d1d5db; }}
    .dark table {{ background: #111827; border-color: #1f2937; }}
    .dark th {{ background: #1f2937; color: #9ca3af; }}
    .dark td {{ border-color: #1f2937; }}
    .dark tr:hover td {{ background: #1f2937; }}
    .dark .cta {{ background: #052e16; border-color: #166534; }}
    .dark .cta p {{ color: #d1d5db; }}
    .dark .updated {{ color: #6b7280; }}
    .dark .breadcrumb {{ color: #9ca3af; }}
    .dark .breadcrumb a {{ color: #9ca3af; }}
    .dark .sub {{ color: #9ca3af; }}
    .dark .badge {{ background: #14532d; color: #86efac; }}
    .dark a {{ color: #4ade80; }}
    .dark .cta a {{ background: #16a34a; color: #fff !important; }}
    .dark .kcard .val.green {{ color: #4ade80; }}
    .dark .ytick {{ stroke: #1f2937; }}
    .dark .hbar {{ fill: #22c55e; }}
    .dark .badge-green {{ background: #14532d; color: #86efac; }}
    .dark .badge-blue {{ background: #1e3a5f; color: #93c5fd; }}
    .dark .badge-teal {{ background: #134e4a; color: #5eead4; }}
    .dark .badge-orange {{ background: #431407; color: #fdba74; }}
    .dark .badge-gray {{ background: #1f2937; color: #d1d5db; }}
    .dark .profil-tekst {{ color: #9ca3af; }}
    .dark .historikk-prosa p {{ color: #9ca3af; }}
    .dark .risiko-liste li {{ border-left-color: #7f1d1d; color: #9ca3af; }}
    .dark .rel-kort {{ background: #111827; border-color: #1f2937; }}
    .dark .rel-navn {{ color: #9ca3af; }}
  </style>
</head>
<body>

  <!-- HEADER -->
  <header class="ak-header">
    <div class="ak-inner" style="max-width:760px;">
      <div class="ak-left">
        <a href="/" class="ak-back">
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
          exday.no
        </a>
        <span class="ak-sep">/</span>
        <a href="/aksjer/" class="ak-back">{navn[:18]}{'…' if len(navn) > 18 else ''}</a>
      </div>
      <button id="dark-toggle" class="ak-toggle" aria-label="Bytt fargemodus">
        <svg class="sun-icon" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
        <svg class="moon-icon" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display:none;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
      </button>
    </div>
  </header>

<div class="wrap">

  <div class="breadcrumb">
    <a href="https://exday.no/">exday.no</a>
    <span>/</span>
    <a href="https://exday.no/aksjer/">Aksjer</a>
    <span>›</span>
    <a href="https://exday.no/aksjer/sektor/{_sektor_slug(sektor)}/">{_sektor_ikon(sektor)} {sektor}</a>
    <span>›</span>
    {ticker}
  </div>

  <h1>{ticker} – {navn}</h1>
  <p class="sub">{_sektor_ikon(sektor)} {sektor} · {frekvens} utbytte · Oslo Børs</p>
  <span class="badge">{f'{yield_:.2f}% direkteavkastning' if yield_ else 'Kurs ikke tilgjengelig'}</span>

  <div class="kgrid">
    <div class="kcard">
      <div class="label">Kurs</div>
      <div class="val">{f'{pris:,.0f} {valuta}' if pris else '—'}</div>
    </div>
    <div class="kcard">
      <div class="label">Yield</div>
      <div class="val green">{f'{yield_:.2f}%' if yield_ else '—'}</div>
    </div>
    <div class="kcard">
      <div class="label">Utbytte/aksje</div>
      <div class="val">{upa} {valuta}</div>
    </div>
    <div class="kcard">
      <div class="label">Ex-dato</div>
      <div class="val" style="font-size:1rem">{_fmt_dato(ex)}</div>
    </div>
    <div class="kcard">
      <div class="label">Utbetalingsdato</div>
      <div class="val" style="font-size:1rem">{_fmt_dato(bet)}</div>
    </div>
    <div class="kcard">
      <div class="label">5-årssnitt yield</div>
      <div class="val green">{snitt5:.2f}%</div>
    </div>
    <div class="kcard">
      <div class="label">År med utbytte</div>
      <div class="val">{ar_med}</div>
    </div>
    {pe_card}
  </div>

  {om_seksjon}

  {ai_oppsummering_seksjon}

  {analyse_seksjon}

  {nokkeltal_seksjon}

  {hist_seksjon}

  {profil_html}

  {hist_prosa_html}

  {risiko_html}

  {relaterte_html}

  <div class="mini-nav">
    <a href="/aksjer/sektor/{_sektor_slug(sektor)}/">← Alle {sektor}-aksjer</a>
    <span style="color:#9ca3af;">·</span>
    <a href="/utbyttekalender/">Utbyttekalender</a>
    <span style="color:#9ca3af;">·</span>
    <a href="/utbyttekalkulator/">Kalkulator</a>
    <span style="color:#9ca3af;">·</span>
    <a href="/aksjer/hoyest-utbytte/">Høyest yield</a>
  </div>

  <div class="cta">
    <p style="margin-bottom:0.75rem;">Se alle norske utbytteaksjer, bygg portefølje og spor ex-datoer</p>
    <a href="https://exday.no/?aksje={ticker}">Åpne {ticker} i exday.no →</a>
  </div>

  <p class="updated">Sist oppdatert: {today}</p>
{STANDARD_FOOTER}
</div>

<script>
  (function() {{
    var btn = document.getElementById('dark-toggle');
    var root = document.documentElement;
    var sun = btn.querySelector('.sun-icon');
    var moon = btn.querySelector('.moon-icon');
    function syncIcons() {{
      var dark = root.classList.contains('dark');
      sun.style.display = dark ? 'none' : '';
      moon.style.display = dark ? '' : 'none';
    }}
    syncIcons();
    btn.addEventListener('click', function() {{
      var isDark = root.classList.toggle('dark');
      localStorage.setItem('tema', isDark ? 'dark' : 'light');
      syncIcons();
    }});
  }})();
</script>

</body>
</html>"""


def generer_aksjesider(aksjer, root_dir):
    """Genererer én HTML-side per aksje under aksjer/TICKER/index.html."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    aksjer_dir = os.path.join(root_dir, "aksjer")
    os.makedirs(aksjer_dir, exist_ok=True)

    # Bygg sektor-indeks for relaterte aksjer og sektorsnitt
    sektor_map  = {}
    sektor_data = {}
    for a in aksjer:
        s = a.get("sektor") or "Annet"
        sektor_map.setdefault(s, []).append(a)
        y = a.get("utbytte_yield") or 0
        if y > 0:
            sektor_data.setdefault(s, []).append(y)
    sektor_snitt = {s: sum(v) / len(v) for s, v in sektor_data.items() if v}

    for a in aksjer:
        ticker = a["ticker"]
        ticker_dir = os.path.join(aksjer_dir, ticker)
        os.makedirs(ticker_dir, exist_ok=True)
        # Finn inntil 4 relaterte aksjer fra samme sektor (ekskl. seg selv), sortert på yield
        sektor = a.get("sektor") or "Annet"
        relaterte = [
            r for r in sorted(sektor_map.get(sektor, []),
                               key=lambda x: x.get("utbytte_yield", 0), reverse=True)
            if r["ticker"] != ticker and (r.get("utbytte_yield") or 0) > 0
        ][:4]
        html = _aksje_side_html(a, today, relaterte=relaterte, sektor_snitt=sektor_snitt)
        with open(os.path.join(ticker_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    # Oversiktsside
    rader = ""
    for a in sorted(aksjer, key=lambda x: x.get("utbytte_yield", 0), reverse=True):
        t   = a["ticker"]
        ex  = _fmt_dato(a.get("ex_dato"))
        rader += f"""
        <tr>
          <td><a href="/aksjer/{t}/">{t}</a></td>
          <td>{a["navn"]}</td>
          <td>{a.get("sektor") or "—"}</td>
          <td>{a.get("pris") or "—"} {a.get("valuta","NOK")}</td>
          <td>{a.get("utbytte_yield", 0):.2f}%</td>
          <td>{ex}</td>
        </tr>"""

    oversikt_html = f"""<!DOCTYPE html>
<html lang="nb">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <!-- Mørk modus init (før rendering for å unngå flimring) -->
  <script>(function(){{var t=localStorage.getItem('tema');if(t==='dark'||(!t&&window.matchMedia('(prefers-color-scheme: dark)').matches)){{document.documentElement.classList.add('dark');}}}})();</script>
  <!-- Favicon -->
  <link rel="icon" type="image/png" sizes="512x512" href="/favicon.png">
  <link rel="icon" type="image/png" sizes="180x180" href="/logo/apple_touch_icon_180.png">
  <link rel="icon" type="image/svg+xml" href="/logo/exday_icon_primary.svg">
  <link rel="shortcut icon" href="/favicon.png">
  <!-- Google Analytics med Consent Mode v2 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-X6C9PERKMB"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('consent', 'default', {{
      analytics_storage: 'denied',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      wait_for_update: 500
    }});
    gtag('js', new Date());
    gtag('config', 'G-X6C9PERKMB');
  </script>
  <script src="/assets/consent.js" defer></script>
  <title>Norske utbytteaksjer – oversikt | exday.no</title>
  <meta name="description" content="Oversikt over {len(aksjer)} norske utbytteaksjer på Oslo Børs med yield, ex-dato og utbyttehistorikk. Oppdateres daglig."/>
  <link rel="canonical" href="https://exday.no/aksjer/"/>
  <script type="application/ld+json">{json.dumps({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Hjem","item":"https://exday.no/"},{"@type":"ListItem","position":2,"name":"Aksjer","item":"https://exday.no/aksjer/"}]}, ensure_ascii=False)}</script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #f9fafb; color: #111827; line-height: 1.6; }}
    a {{ color: #16a34a; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem; }}
    .page-nav {{ display:flex; align-items:center; justify-content:space-between; font-size: 0.85rem; color: #6b7280; margin-bottom: 1.5rem; }}
    .page-nav-links {{ display:flex; align-items:center; gap:0.4rem; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.5rem; }}
    .sub {{ color: #6b7280; margin-bottom: 1.5rem; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; border-radius: 0.75rem; overflow: hidden; font-size: 0.9rem; }}
    th {{ background: #f3f4f6; padding: 0.6rem 1rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: #6b7280; }}
    td {{ padding: 0.65rem 1rem; border-top: 1px solid #f3f4f6; }}
    tr:hover td {{ background: #f9fafb; }}
    .yield {{ color: #16a34a; font-weight: 600; }}
    .cta {{ margin-top: 1.5rem; text-align: center; }}
    .cta a {{ display: inline-block; background: #16a34a; color: #fff; font-weight: 600; padding: 0.65rem 1.5rem; border-radius: 0.5rem; }}
    .updated {{ font-size: 0.78rem; color: #9ca3af; text-align: right; margin-top: 1rem; }}
    .dk-btn {{ background:transparent; border:none; cursor:pointer; padding:0.3rem; color:#6b7280; border-radius:0.375rem; }}
    .dk-btn:hover {{ background:#e5e7eb; }}
    /* Mørk modus */
    .dark body {{ background: #111827; color: #f9fafb; }}
    .dark a {{ color: #4ade80; }}
    .dark table {{ background: #1f2937; border-color: #374151; }}
    .dark th {{ background: #111827; color: #9ca3af; }}
    .dark td {{ border-color: #374151; }}
    .dark tr:hover td {{ background: #1e2d3d; }}
    .dark .sub {{ color: #9ca3af; }}
    .dark .updated {{ color: #6b7280; }}
    .dark .dk-btn {{ color: #9ca3af; }}
    .dark .dk-btn:hover {{ background: #374151; }}
    .dark .cta a {{ background: #16a34a; }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="page-nav">
    <div class="page-nav-links"><a href="https://exday.no/">exday.no</a> <span>›</span> <span>Aksjer</span></div>
    <button class="dk-btn" id="dark-toggle" aria-label="Bytt fargemodus" title="Bytt fargemodus">
      <svg id="ov-moon" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
      <svg id="ov-sun" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="display:none"><path stroke-linecap="round" stroke-linejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
    </button>
  </div>
  <h1>Norske utbytteaksjer</h1>
  <p class="sub">Oversikt over {len(aksjer)} utbytteaksjer på Oslo Børs, sortert etter direkteavkastning. Oppdateres daglig.</p>
  <table>
    <thead><tr><th>Ticker</th><th>Navn</th><th>Sektor</th><th>Kurs</th><th>Yield</th><th>Ex-dato</th></tr></thead>
    <tbody>{rader}</tbody>
  </table>
  <div class="cta"><a href="https://exday.no/">Åpne full app med porteføljekalkulator →</a></div>
  <p class="updated">Sist oppdatert: {today}</p>
{STANDARD_FOOTER}
</div>
<script>
  (function(){{
    var root = document.documentElement;
    var btn  = document.getElementById('dark-toggle');
    var moon = document.getElementById('ov-moon');
    var sun  = document.getElementById('ov-sun');
    function sync(){{ var d=root.classList.contains('dark'); moon.style.display=d?'none':''; sun.style.display=d?'':'none'; }}
    sync();
    btn.addEventListener('click', function(){{
      var isDark = root.classList.toggle('dark');
      localStorage.setItem('tema', isDark ? 'dark' : 'light');
      sync();
    }});
  }})();
</script>
</body>
</html>"""

    with open(os.path.join(aksjer_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(oversikt_html)

    print(f"Genererte {len(aksjer)} aksjesider + oversiktsside under aksjer/")


STANDARD_FOOTER = """  <footer style="margin-top:2rem;padding-top:1.5rem;border-top:1px solid #e5e7eb;font-size:0.78rem;text-align:center;color:#9ca3af;line-height:1.6;" class="std-footer">
    <p>Kurs og utbyttedata hentes fra Yahoo Finance og Euronext. Oppdateres daglig på børsdager.</p>
    <p style="max-width:36rem;margin:0.4rem auto;">
      exday.no er ikke et verdipapirforetak og tilbyr ikke finansiell rådgivning.
      Data kan inneholde feil eller forsinkelser &#8212; verifiser alltid mot Oslo B&#248;rs eller selskapets egne rapporter.
      Historisk utbytte er ingen garanti for fremtidig utbytte.
      Gj&#248;r alltid din egen analyse f&#248;r du tar investeringsbeslutninger.
    </p>
    <p style="margin-top:0.5rem;">
      <a href="/personvern/" style="color:#9ca3af;text-decoration:underline;">Personvern og informasjonskapsler</a>
      <span style="margin:0 0.4rem;">&#183;</span>
      <a href="/faq/" style="color:#9ca3af;text-decoration:underline;">Vanlige sp&#248;rsm&#229;l (FAQ)</a>
    </p>
    <p style="margin-top:0.75rem;">
      <a href="https://www.facebook.com/share/17rMp8o9yF/?mibextid=wwXIfr" target="_blank" rel="noopener noreferrer" style="display:inline-flex;align-items:center;gap:0.375rem;color:#9ca3af;">
        <svg width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><path d="M22 12c0-5.523-4.477-10-10-10S2 6.477 2 12c0 4.991 3.657 9.128 8.438 9.878v-6.987h-2.54V12h2.54V9.797c0-2.506 1.492-3.89 3.777-3.89 1.094 0 2.238.195 2.238.195v2.46h-1.26c-1.243 0-1.63.771-1.63 1.562V12h2.773l-.443 2.89h-2.33v6.988C18.343 21.128 22 16.991 22 12z"/></svg>
        F&#248;lg exday.no p&#229; Facebook
      </a>
    </p>
  </footer>
  <style>.dark .std-footer {{ color:#6b7280 !important; border-color:#1f2937 !important; }} .dark .std-footer a {{ color:#6b7280 !important; }}</style>"""

SEKTOR_IKONER = {
    "Energi":          "⚡",
    "Finans":          "🏦",
    "Shipping":        "🚢",
    "Sjømat":          "🐟",
    "Havbruk":         "🐟",
    "Teknologi":       "💻",
    "Industri":        "🏗️",
    "Eiendom":         "🏢",
    "Forbruksvarer":   "🛒",
    "Helsevern":       "🏥",
    "Kommunikasjon":   "📡",
    "Materialer":      "⛏️",
    "Offshore":        "🛢️",
    "Kraftproduksjon": "💧",
    "Forsikring":      "🛡️",
}


def _sektor_ikon(sektor):
    for k, v in SEKTOR_IKONER.items():
        if k.lower() in sektor.lower():
            return v
    return "📊"


def _sektor_slug(sektor):
    return (sektor.lower()
            .replace('æ', 'ae').replace('ø', 'o').replace('å', 'a')
            .replace(' ', '-'))


def generer_sektorsider(aksjer, root_dir):
    """Genererer én HTML-oversiktsside per sektor under aksjer/sektor/{slug}/index.html."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    sektor_dir = os.path.join(root_dir, "aksjer", "sektor")
    os.makedirs(sektor_dir, exist_ok=True)

    from collections import defaultdict
    sektorer = defaultdict(list)
    for a in aksjer:
        if a.get("sektor"):
            sektorer[a["sektor"]].append(a)

    generert = []
    for sektor, aksjer_i_sektor in sorted(sektorer.items()):
        slug = _sektor_slug(sektor)
        aksjer_sortert = sorted(aksjer_i_sektor, key=lambda x: x.get("utbytte_yield", 0), reverse=True)
        snitt_yield = sum(a.get("utbytte_yield", 0) for a in aksjer_sortert) / len(aksjer_sortert)

        rader = ""
        for a in aksjer_sortert:
            t  = a["ticker"]
            ex = _fmt_dato(a.get("ex_dato"))
            rader += f"""
        <tr>
          <td><a href="/aksjer/{t}/">{t}</a></td>
          <td>{a["navn"]}</td>
          <td>{a.get("pris") or "—"} {a.get("valuta","NOK")}</td>
          <td class="yield">{a.get("utbytte_yield", 0):.2f}%</td>
          <td>{ex}</td>
        </tr>"""

        meta_desc = (f"{len(aksjer_sortert)} norske {sektor.lower()}-aksjer på Oslo Børs med "
                     f"gjennomsnittlig utbytteyield på {snitt_yield:.1f}%. "
                     f"Se yield, ex-dato og historikk på exday.no.")

        json_ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Hjem",   "item": "https://exday.no/"},
                {"@type": "ListItem", "position": 2, "name": "Aksjer", "item": "https://exday.no/aksjer/"},
                {"@type": "ListItem", "position": 3, "name": sektor,   "item": f"https://exday.no/aksjer/sektor/{slug}/"},
            ]
        }, ensure_ascii=False)

        html = f"""<!DOCTYPE html>
<html lang="nb">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <!-- Google Analytics med Consent Mode v2 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-X6C9PERKMB"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('consent', 'default', {{
      analytics_storage: 'denied',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      wait_for_update: 500
    }});
    gtag('js', new Date());
    gtag('config', 'G-X6C9PERKMB');
  </script>
  <script src="/assets/consent.js" defer></script>
  <title>{sektor}-aksjer med utbytte | Oslo Børs | exday.no</title>
  <meta name="description" content="{meta_desc}"/>
  <link rel="canonical" href="https://exday.no/aksjer/sektor/{slug}/"/>
  <meta name="theme-color" content="#16a34a"/>
  <link rel="icon" type="image/png" sizes="512x512" href="/favicon.png"/>
  <link rel="icon" type="image/png" sizes="180x180" href="/logo/apple_touch_icon_180.png"/>
  <link rel="icon" type="image/svg+xml" href="/logo/exday_icon_primary.svg"/>
  <link rel="shortcut icon" href="/favicon.png"/>
  <link rel="apple-touch-icon" href="/logo/apple_touch_icon_180.png"/>
  <meta property="og:title" content="{sektor}-aksjer med utbytte – exday.no"/>
  <meta property="og:description" content="{meta_desc}"/>
  <meta property="og:url" content="https://exday.no/aksjer/sektor/{slug}/"/>
  <script type="application/ld+json">{json_ld}</script>
  <link rel="stylesheet" href="/assets/tailwind.css"/>
  <link rel="stylesheet" href="/assets/style.css"/>
  <script>
    (function(){{
      var t = localStorage.getItem('tema');
      if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {{
        document.documentElement.classList.add('dark');
      }}
    }})();
  </script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; }}
    a {{ color: #16a34a; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
    .breadcrumb {{ font-size: 0.85rem; color: #6b7280; margin-bottom: 1.5rem; }}
    .breadcrumb a {{ color: #6b7280; }}
    .breadcrumb span {{ margin: 0 0.35rem; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.5rem; }}
    .sub {{ margin-bottom: 1.5rem; font-size: 0.95rem; }}
    .stats {{ display: flex; gap: 1.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
    .stat {{ border-radius: 0.5rem; padding: 0.75rem 1.25rem; border: 1px solid; }}
    .stat-val {{ font-size: 1.4rem; font-weight: 700; color: #16a34a; }}
    .stat-lbl {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }}
    table {{ width: 100%; border-collapse: collapse; border-radius: 0.75rem; overflow: hidden; font-size: 0.9rem; border: 1px solid; }}
    th {{ padding: 0.6rem 1rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }}
    td {{ padding: 0.65rem 1rem; border-top: 1px solid; }}
    .yield {{ font-weight: 600; color: #16a34a; }}
    .cta {{ margin-top: 1.5rem; text-align: center; }}
    .cta a {{ display: inline-block; background: #16a34a; color: #fff !important; font-weight: 600; padding: 0.65rem 1.5rem; border-radius: 0.5rem; text-decoration: none; }}
    .cta a:hover {{ background: #15803d; }}
    .updated {{ font-size: 0.78rem; text-align: right; margin-top: 1rem; }}

    body {{ background: #f9fafb; color: #111827; }}
    .stat {{ background: #fff; border-color: #e5e7eb; }}
    .stat-lbl {{ color: #6b7280; }}
    table {{ background: #fff; border-color: #e5e7eb; }}
    th {{ background: #f3f4f6; color: #6b7280; }}
    td {{ border-color: #f3f4f6; }}
    tr:hover td {{ background: #f9fafb; }}
    .sub {{ color: #6b7280; }}
    .updated {{ color: #9ca3af; }}

    .dark body {{ background: #030712; color: #f3f4f6; }}
    .dark .stat {{ background: #111827; border-color: #1f2937; }}
    .dark .stat-lbl {{ color: #9ca3af; }}
    .dark table {{ background: #111827; border-color: #1f2937; }}
    .dark th {{ background: #1f2937; color: #9ca3af; }}
    .dark td {{ border-color: #1f2937; }}
    .dark tr:hover td {{ background: #1f2937; }}
    .dark .sub {{ color: #9ca3af; }}
    .dark .updated {{ color: #6b7280; }}
    .dark a {{ color: #4ade80; }}
    .dark .breadcrumb {{ color: #9ca3af; }}
    .dark .breadcrumb a {{ color: #9ca3af; }}
    .dark .stat-val {{ color: #4ade80; }}
    .dark .yield {{ color: #4ade80; }}
    .dark .cta a {{ background: #16a34a; color: #fff !important; }}
  </style>
</head>
<body>
  <header class="ak-header">
    <div class="ak-inner">
      <div class="ak-left">
        <a href="/" class="ak-back">
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
          exday.no
        </a>
        <span class="ak-sep">/</span>
        <span class="ak-title">{sektor}</span>
      </div>
      <button id="dark-toggle" aria-label="Bytt fargemodus" class="ak-toggle">
        <svg class="sun-icon" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
        <svg class="moon-icon" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display:none;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
      </button>
    </div>
  </header>
<div class="wrap">
  <div class="breadcrumb">
    <a href="https://exday.no/">exday.no</a>
    <span>/</span>
    <a href="/aksjer/">Aksjer</a>
    <span>/</span>
    {sektor}
  </div>
  <h1>{_sektor_ikon(sektor)} {sektor}-aksjer med utbytte</h1>
  <p class="sub">{len(aksjer_sortert)} norske {sektor.lower()}-aksjer på Oslo Børs. Sortert etter direkteavkastning.</p>
  <div class="stats">
    <div class="stat"><div class="stat-val">{len(aksjer_sortert)}</div><div class="stat-lbl">Aksjer</div></div>
    <div class="stat"><div class="stat-val">{snitt_yield:.1f}%</div><div class="stat-lbl">Snitt yield</div></div>
    <div class="stat"><div class="stat-val">{max(a.get("utbytte_yield",0) for a in aksjer_sortert):.1f}%</div><div class="stat-lbl">Høyeste yield</div></div>
  </div>
  <table>
    <thead><tr><th>Ticker</th><th>Navn</th><th>Kurs</th><th>Yield</th><th>Ex-dato</th></tr></thead>
    <tbody>{rader}</tbody>
  </table>
  <div class="cta"><a href="https://exday.no/">Åpne full app med filtrering og porteføljekalkulator →</a></div>
  <p class="updated">Sist oppdatert: {today}</p>
{STANDARD_FOOTER}
</div>
<script>
  (function() {{
    var btn = document.getElementById('dark-toggle');
    var root = document.documentElement;
    var sun = btn.querySelector('.sun-icon');
    var moon = btn.querySelector('.moon-icon');
    function syncIcons() {{
      var dark = root.classList.contains('dark');
      sun.style.display = dark ? 'none' : '';
      moon.style.display = dark ? '' : 'none';
    }}
    syncIcons();
    btn.addEventListener('click', function() {{
      var isDark = root.classList.toggle('dark');
      localStorage.setItem('tema', isDark ? 'dark' : 'light');
      syncIcons();
    }});
  }})();
</script>
</body>
</html>"""

        slug_dir = os.path.join(sektor_dir, slug)
        os.makedirs(slug_dir, exist_ok=True)
        with open(os.path.join(slug_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        generert.append((slug, sektor, len(aksjer_sortert)))

    # Oversiktsside for alle sektorer
    sektorkort = ""
    for slug, sektor, antall in generert:
        aksjer_i = sektorer[sektor]
        snitt = sum(a.get("utbytte_yield", 0) for a in aksjer_i) / len(aksjer_i)
        sektorkort += f"""
    <a href="/aksjer/sektor/{slug}/" class="sektor-kort">
      <div class="sk-navn">{sektor}</div>
      <div class="sk-antall">{antall} aksjer · snitt {snitt:.1f}%</div>
    </a>"""

    sektor_oversikt = f"""<!DOCTYPE html>
<html lang="nb">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <!-- Google Analytics med Consent Mode v2 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-X6C9PERKMB"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('consent', 'default', {{
      analytics_storage: 'denied',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      wait_for_update: 500
    }});
    gtag('js', new Date());
    gtag('config', 'G-X6C9PERKMB');
  </script>
  <script src="/assets/consent.js" defer></script>
  <title>Norske utbytteaksjer etter sektor | exday.no</title>
  <meta name="description" content="Finn norske utbytteaksjer på Oslo Børs sortert etter sektor — energi, finans, shipping, havbruk og mer."/>
  <link rel="canonical" href="https://exday.no/aksjer/sektor/"/>
  <meta name="theme-color" content="#16a34a"/>
  <link rel="icon" type="image/png" sizes="512x512" href="/favicon.png"/>
  <link rel="icon" type="image/png" sizes="180x180" href="/logo/apple_touch_icon_180.png"/>
  <link rel="icon" type="image/svg+xml" href="/logo/exday_icon_primary.svg"/>
  <link rel="shortcut icon" href="/favicon.png"/>
  <link rel="apple-touch-icon" href="/logo/apple_touch_icon_180.png"/>
  <link rel="stylesheet" href="/assets/tailwind.css"/>
  <link rel="stylesheet" href="/assets/style.css"/>
  <script>
    (function(){{
      var t = localStorage.getItem('tema');
      if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {{
        document.documentElement.classList.add('dark');
      }}
    }})();
  </script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; }}
    a {{ color: #16a34a; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }}
    .breadcrumb {{ font-size: 0.85rem; color: #6b7280; margin-bottom: 1.5rem; }}
    .breadcrumb a {{ color: #6b7280; }}
    .breadcrumb span {{ margin: 0 0.35rem; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }}
    .sub {{ font-size: 0.95rem; margin-bottom: 1.5rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }}
    .sektor-kort {{ display: block; border-radius: 0.75rem; padding: 1rem 1.25rem; border: 1px solid; transition: border-color 0.15s; text-decoration: none; }}
    .sektor-kort:hover {{ border-color: #16a34a; text-decoration: none; }}
    .sk-navn {{ font-weight: 600; font-size: 1rem; }}
    .sk-antall {{ font-size: 0.8rem; margin-top: 0.25rem; }}

    /* Light mode */
    body {{ background: #f9fafb; color: #111827; }}
    .breadcrumb {{ color: #6b7280; }}
    .sub {{ color: #6b7280; }}
    .sektor-kort {{ background: #fff; border-color: #e5e7eb; }}
    .sk-navn {{ color: #111827; }}
    .sk-antall {{ color: #6b7280; }}

    /* Dark mode */
    .dark body {{ background: #030712; color: #f3f4f6; }}
    .dark .breadcrumb {{ color: #9ca3af; }}
    .dark .breadcrumb a {{ color: #9ca3af; }}
    .dark .sub {{ color: #9ca3af; }}
    .dark .sektor-kort {{ background: #111827; border-color: #1f2937; }}
    .dark .sektor-kort:hover {{ border-color: #16a34a; }}
    .dark .sk-navn {{ color: #f3f4f6; }}
    .dark .sk-antall {{ color: #6b7280; }}
    .dark a {{ color: #4ade80; }}
  </style>
</head>
<body>

  <!-- HEADER -->
  <header class="ak-header">
    <div class="ak-inner" style="max-width:900px;">
      <div class="ak-left">
        <a href="/" class="ak-back">
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
          exday.no
        </a>
        <span class="ak-sep">/</span>
        <a href="/aksjer/" class="ak-back">Aksjer</a>
        <span class="ak-sep">/</span>
        <span style="font-size:0.85rem;color:#6b7280;">Sektorer</span>
      </div>
      <button id="dark-toggle" class="ak-toggle" aria-label="Bytt fargemodus">
        <svg class="sun-icon" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
        <svg class="moon-icon" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display:none;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
      </button>
    </div>
  </header>

<div class="wrap">
  <div class="breadcrumb">
    <a href="https://exday.no/">exday.no</a>
    <span>›</span>
    <a href="/aksjer/">Aksjer</a>
    <span>›</span>
    Sektorer
  </div>
  <h1>Utbytteaksjer etter sektor</h1>
  <p class="sub">Velg en sektor for å se alle aksjer med utbytte innen den kategorien.</p>
  <div class="grid">{sektorkort}
  </div>
{STANDARD_FOOTER}
</div>

<script>
  (function() {{
    var btn = document.getElementById('dark-toggle');
    var root = document.documentElement;
    var sun = btn.querySelector('.sun-icon');
    var moon = btn.querySelector('.moon-icon');
    function syncIcons() {{
      var dark = root.classList.contains('dark');
      sun.style.display = dark ? 'none' : '';
      moon.style.display = dark ? '' : 'none';
    }}
    syncIcons();
    btn.addEventListener('click', function() {{
      var isDark = root.classList.toggle('dark');
      localStorage.setItem('tema', isDark ? 'dark' : 'light');
      syncIcons();
    }});
  }})();
</script>
</body>
</html>"""

    with open(os.path.join(sektor_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(sektor_oversikt)

    print(f"Genererte {len(generert)} sektorsider under aksjer/sektor/")


def generer_topplistesider(aksjer, root_dir):
    """Genererer 4 statiske SEO-sider for kuraterte topplistor."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")

    LISTER = [
        {
            "slug":     "hoyest-utbytte",
            "tittel":   "Aksjer med høyest utbytte på Oslo Børs",
            "h1":       "Aksjer med høyest utbytte",
            "desc_tpl": "De {n} norske aksjene med høyest utbytteyield på Oslo Børs akkurat nå. Oppdatert daglig.",
            "sub":      "Sortert etter direkteavkastning (utbytteyield) — høyest først.",
            "filter":   lambda a: a.get("utbytte_yield", 0) > 0,
            "sort_key": lambda a: a.get("utbytte_yield", 0),
            "reverse":  True,
            "kolonner": [
                ("Yield",        lambda a: f'<td class="metric">{a["utbytte_yield"]:.2f}%</td>'),
                ("Pris",         lambda a: f'<td>{a.get("pris") or "—"} {a.get("valuta","NOK")}</td>'),
                ("Payout",       lambda a: f'<td>{a["payout_ratio"]:.0f}% </td>' if a.get("payout_ratio") else '<td>—</td>'),
                ("Ex-dato",      lambda a: f'<td>{_fmt_dato(a.get("ex_dato"))}</td>'),
            ],
            "stat_lbl": "Snitt yield",
            "stat_fn":  lambda topp: f'{sum(a["utbytte_yield"] for a in topp)/len(topp):.1f}%',
            "stat2_lbl":"Høyeste yield",
            "stat2_fn": lambda topp: f'{topp[0]["utbytte_yield"]:.2f}%',
        },
        {
            "slug":     "utbyttevekst",
            "tittel":   "Norske aksjer med best utbyttevekst siste 5 år",
            "h1":       "Aksjer med best utbyttevekst",
            "desc_tpl": "De {n} norske aksjene med sterkest utbyttevekst siste 5 år på Oslo Børs. CAGR beregnet fra historiske utbyttedata.",
            "sub":      "Sortert etter gjennomsnittlig årlig utbyttevekst siste 5 år (CAGR).",
            "filter":   lambda a: a.get("utbytte_vekst_5ar", 0) > 0,
            "sort_key": lambda a: a.get("utbytte_vekst_5ar", 0),
            "reverse":  True,
            "kolonner": [
                ("Vekst 5år",    lambda a: f'<td class="metric">+{a["utbytte_vekst_5ar"]:.1f}%/år</td>'),
                ("Yield nå",     lambda a: f'<td>{a.get("utbytte_yield",0):.2f}%</td>'),
                ("Pris",         lambda a: f'<td>{a.get("pris") or "—"} {a.get("valuta","NOK")}</td>'),
                ("Ex-dato",      lambda a: f'<td>{_fmt_dato(a.get("ex_dato"))}</td>'),
            ],
            "stat_lbl": "Snitt vekst",
            "stat_fn":  lambda topp: f'+{sum(a["utbytte_vekst_5ar"] for a in topp)/len(topp):.1f}%/år',
            "stat2_lbl":"Høyeste vekst",
            "stat2_fn": lambda topp: f'+{topp[0]["utbytte_vekst_5ar"]:.1f}%/år',
        },
        {
            "slug":     "konsistente-utbytteaksjer",
            "tittel":   "Mest konsistente utbytteaksjer på Oslo Børs",
            "h1":       "Mest konsistente utbytteaksjer",
            "desc_tpl": "De {n} norske aksjene som har betalt utbytte flest år på rad. Konsistens er et sentralt kriterium for utbytteinvestorer.",
            "sub":      "Sortert etter antall kalenderår med utbyttebetaling — flest år først.",
            "filter":   lambda a: a.get("ar_med_utbytte", 0) > 0,
            "sort_key": lambda a: a.get("ar_med_utbytte", 0),
            "reverse":  True,
            "kolonner": [
                ("År m/utbytte", lambda a: f'<td class="metric">{a["ar_med_utbytte"]} år</td>'),
                ("Yield",        lambda a: f'<td>{a.get("utbytte_yield",0):.2f}%</td>'),
                ("Pris",         lambda a: f'<td>{a.get("pris") or "—"} {a.get("valuta","NOK")}</td>'),
                ("Ex-dato",      lambda a: f'<td>{_fmt_dato(a.get("ex_dato"))}</td>'),
            ],
            "stat_lbl": "Snitt år",
            "stat_fn":  lambda topp: f'{sum(a["ar_med_utbytte"] for a in topp)/len(topp):.0f} år',
            "stat2_lbl":"Flest år",
            "stat2_fn": lambda topp: f'{topp[0]["ar_med_utbytte"]} år',
        },
        {
            "slug":     "lavest-payout",
            "tittel":   "Aksjer med lavest payout ratio – bærekraftig utbytte",
            "h1":       "Aksjer med lavest payout ratio",
            "desc_tpl": "De {n} norske aksjene med lavest payout ratio på Oslo Børs. Lav payout betyr at selskapet beholder mer av overskuddet og utbyttet er mer bærekraftig.",
            "sub":      "Sortert etter payout ratio (andel av overskudd utbetalt som utbytte) — lavest først.",
            "filter":   lambda a: 0 < a.get("payout_ratio", 0) < 100,
            "sort_key": lambda a: a.get("payout_ratio", 0),
            "reverse":  False,
            "kolonner": [
                ("Payout ratio", lambda a: f'<td class="metric">{a["payout_ratio"]:.0f}%</td>'),
                ("Yield",        lambda a: f'<td>{a.get("utbytte_yield",0):.2f}%</td>'),
                ("Pris",         lambda a: f'<td>{a.get("pris") or "—"} {a.get("valuta","NOK")}</td>'),
                ("Ex-dato",      lambda a: f'<td>{_fmt_dato(a.get("ex_dato"))}</td>'),
            ],
            "stat_lbl": "Snitt payout",
            "stat_fn":  lambda topp: f'{sum(a["payout_ratio"] for a in topp)/len(topp):.0f}%',
            "stat2_lbl":"Laveste payout",
            "stat2_fn": lambda topp: f'{topp[0]["payout_ratio"]:.0f}%',
        },
    ]

    CSS = """
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, -apple-system, sans-serif; line-height: 1.6; }
    a { color: #16a34a; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .wrap { max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
    .breadcrumb { font-size: 0.85rem; margin-bottom: 1.5rem; }
    .breadcrumb a { text-decoration: none; }
    .breadcrumb span { margin: 0 0.35rem; }
    h1 { font-size: 1.75rem; font-weight: 700; margin-bottom: 0.5rem; }
    .sub { margin-bottom: 1.5rem; font-size: 0.95rem; }
    .stats { display: flex; gap: 1.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
    .stat { border-radius: 0.5rem; padding: 0.75rem 1.25rem; border: 1px solid; }
    .stat-val { font-size: 1.4rem; font-weight: 700; color: #16a34a; }
    .stat-lbl { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }
    table { width: 100%; border-collapse: collapse; border-radius: 0.75rem; overflow: hidden; font-size: 0.9rem; border: 1px solid; }
    th { padding: 0.6rem 1rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
    td { padding: 0.65rem 1rem; border-top: 1px solid; }
    .rang { font-size: 0.8rem; font-weight: 700; width: 2rem; }
    .ticker a { color: #16a34a; font-family: monospace; font-weight: 700; font-size: 0.95rem; }
    .metric { color: #16a34a; font-weight: 700; }
    .cta { margin-top: 2rem; border-radius: 0.75rem; padding: 1.25rem; text-align: center; border: 1px solid; }
    .cta a { display: inline-block; background: #16a34a; color: #fff !important; font-weight: 600; padding: 0.65rem 1.5rem; border-radius: 0.5rem; margin-top: 0.5rem; text-decoration: none; }
    .cta a:hover { background: #15803d; }
    .relatert { margin-top: 2rem; }
    .relatert h2 { font-size: 1rem; font-weight: 600; margin-bottom: 0.75rem; }
    .relatert ul { list-style: none; display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .relatert li a { display: block; border-radius: 0.5rem; padding: 0.4rem 0.85rem; font-size: 0.85rem; border: 1px solid; text-decoration: none; }
    .updated { font-size: 0.78rem; text-align: right; margin-top: 1rem; }

    body { background: #f9fafb; color: #111827; }
    .stat { background: #fff; border-color: #e5e7eb; }
    .stat-lbl { color: #6b7280; }
    .sub { color: #6b7280; }
    .breadcrumb { color: #6b7280; }
    .breadcrumb a { color: #6b7280; }
    .rang { color: #9ca3af; }
    table { background: #fff; border-color: #e5e7eb; }
    th { background: #f3f4f6; color: #6b7280; }
    td { border-color: #f3f4f6; }
    tr:hover td { background: #f9fafb; }
    .cta { background: #f0fdf4; border-color: #bbf7d0; }
    .relatert h2 { color: #374151; }
    .relatert li a { background: #fff; border-color: #e5e7eb; color: #374151; }
    .relatert li a:hover { border-color: #16a34a; color: #15803d; }
    .updated { color: #9ca3af; }

    .dark body { background: #030712; color: #f3f4f6; }
    .dark .stat { background: #111827; border-color: #1f2937; }
    .dark .stat-lbl { color: #9ca3af; }
    .dark .stat-val { color: #4ade80; }
    .dark .sub { color: #9ca3af; }
    .dark .breadcrumb { color: #9ca3af; }
    .dark .breadcrumb a { color: #9ca3af; }
    .dark .rang { color: #6b7280; }
    .dark a { color: #4ade80; }
    .dark .ticker a { color: #4ade80; }
    .dark .metric { color: #4ade80; }
    .dark table { background: #111827; border-color: #1f2937; }
    .dark th { background: #1f2937; color: #9ca3af; }
    .dark td { border-color: #1f2937; }
    .dark tr:hover td { background: #1f2937; }
    .dark .cta { background: #052e16; border-color: #166534; }
    .dark .cta a { background: #16a34a; }
    .dark .relatert h2 { color: #d1d5db; }
    .dark .relatert li a { background: #111827; border-color: #1f2937; color: #d1d5db; }
    .dark .relatert li a:hover { border-color: #4ade80; color: #4ade80; }
    .dark .updated { color: #6b7280; }
"""

    alle_slugs = [(l["slug"], l["h1"]) for l in LISTER]

    for cfg in LISTER:
        topp = sorted(
            [a for a in aksjer if cfg["filter"](a)],
            key=cfg["sort_key"],
            reverse=cfg["reverse"]
        )[:20]

        if not topp:
            continue

        n = len(topp)
        desc = cfg["desc_tpl"].format(n=n)
        col_headers = "".join(f"<th>{lbl}</th>" for lbl, _ in cfg["kolonner"])
        rader = ""
        for i, a in enumerate(topp, 1):
            kols = "".join(fn(a) for _, fn in cfg["kolonner"])
            rader += f"""
        <tr>
          <td class="rang">{i}</td>
          <td class="ticker"><a href="/aksjer/{a['ticker']}/">{a['ticker']}</a></td>
          <td>{a['navn']}</td>
          {kols}
        </tr>"""

        relatert_lenker = "".join(
            f'<li><a href="/aksjer/{s}/">{h}</a></li>'
            for s, h in alle_slugs if s != cfg["slug"]
        )

        json_ld = json.dumps({
            "@context": "https://schema.org",
            "@type": "ItemList",
            "name": cfg["tittel"],
            "description": desc,
            "url": f"https://exday.no/aksjer/{cfg['slug']}/",
            "numberOfItems": n,
        }, ensure_ascii=False)

        html = f"""<!DOCTYPE html>
<html lang="nb">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <!-- Google Analytics med Consent Mode v2 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-X6C9PERKMB"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('consent', 'default', {{
      analytics_storage: 'denied',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      wait_for_update: 500
    }});
    gtag('js', new Date());
    gtag('config', 'G-X6C9PERKMB');
  </script>
  <script src="/assets/consent.js" defer></script>
  <title>{cfg['tittel']} | exday.no</title>
  <meta name="description" content="{desc}"/>
  <link rel="canonical" href="https://exday.no/aksjer/{cfg['slug']}/"/>
  <meta name="theme-color" content="#16a34a"/>
  <link rel="icon" type="image/png" sizes="512x512" href="/favicon.png"/>
  <link rel="icon" type="image/png" sizes="180x180" href="/logo/apple_touch_icon_180.png"/>
  <link rel="icon" type="image/svg+xml" href="/logo/exday_icon_primary.svg"/>
  <link rel="shortcut icon" href="/favicon.png"/>
  <link rel="apple-touch-icon" href="/logo/apple_touch_icon_180.png"/>
  <meta property="og:title" content="{cfg['tittel']} | exday.no"/>
  <meta property="og:description" content="{desc}"/>
  <meta property="og:url" content="https://exday.no/aksjer/{cfg['slug']}/"/>
  <meta property="og:type" content="website"/>
  <script type="application/ld+json">{json_ld}</script>
  <link rel="stylesheet" href="/assets/tailwind.css"/>
  <link rel="stylesheet" href="/assets/style.css"/>
  <script>
    (function(){{
      var t = localStorage.getItem('tema');
      if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {{
        document.documentElement.classList.add('dark');
      }}
    }})();
  </script>
  <style>{CSS}</style>
</head>
<body>
  <header class="ak-header">
    <div class="ak-inner">
      <div class="ak-left">
        <a href="/" class="ak-back">
          <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
          exday.no
        </a>
        <span class="ak-sep">/</span>
        <span class="ak-cur">{cfg['h1'][:30]}{'…' if len(cfg['h1']) > 30 else ''}</span>
      </div>
      <button id="dark-toggle" class="ak-toggle" aria-label="Bytt fargemodus">
        <svg class="sun-icon" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
        <svg class="moon-icon" width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display:none;"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
      </button>
    </div>
  </header>
<div class="wrap">
  <div class="breadcrumb">
    <a href="https://exday.no/">exday.no</a>
    <span>/</span>
    <a href="/aksjer/">Aksjer</a>
    <span>/</span>
    {cfg['h1']}
  </div>
  <h1>{cfg['h1']}</h1>
  <p class="sub">{cfg['sub']}</p>
  <div class="stats">
    <div class="stat"><div class="stat-val">{n}</div><div class="stat-lbl">Aksjer</div></div>
    <div class="stat"><div class="stat-val">{cfg['stat_fn'](topp)}</div><div class="stat-lbl">{cfg['stat_lbl']}</div></div>
    <div class="stat"><div class="stat-val">{cfg['stat2_fn'](topp)}</div><div class="stat-lbl">{cfg['stat2_lbl']}</div></div>
  </div>
  <table>
    <thead><tr><th>#</th><th>Ticker</th><th>Selskap</th>{col_headers}</tr></thead>
    <tbody>{rader}
    </tbody>
  </table>
  <div class="cta">
    <p>Se yield, ex-dato, score og porteføljekalkulator for alle aksjer</p>
    <a href="https://exday.no/">Åpne exday.no →</a>
  </div>
  <div class="relatert">
    <h2>Andre topplistor</h2>
    <ul>{relatert_lenker}</ul>
  </div>
  <p class="updated">Sist oppdatert: {today}</p>
{STANDARD_FOOTER}
</div>
<script>
  (function() {{
    var btn = document.getElementById('dark-toggle');
    var root = document.documentElement;
    var sun = btn.querySelector('.sun-icon');
    var moon = btn.querySelector('.moon-icon');
    function syncIcons() {{
      var dark = root.classList.contains('dark');
      sun.style.display = dark ? 'none' : '';
      moon.style.display = dark ? '' : 'none';
    }}
    syncIcons();
    btn.addEventListener('click', function() {{
      var isDark = root.classList.toggle('dark');
      localStorage.setItem('tema', isDark ? 'dark' : 'light');
      syncIcons();
    }});
  }})();
</script>
</body>
</html>"""

        slug_dir = os.path.join(root_dir, "aksjer", cfg["slug"])
        os.makedirs(slug_dir, exist_ok=True)
        with open(os.path.join(slug_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)

    print(f"Genererte {len(LISTER)} topplistesider under aksjer/{{slug}}/")


def generer_sitemap(aksjer, root_dir, today):
    """Genererer sitemap.xml med alle sider inkludert individuelle aksjesider og sektorsider."""
    from collections import defaultdict
    sektorer = defaultdict(list)
    for a in aksjer:
        if a.get("sektor"):
            sektorer[a["sektor"]].append(a)

    urls = [
        f"""  <url>
    <loc>https://exday.no/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>1.0</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/uke/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/aksjer/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/aksjer/sektor/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/utbyttekalender/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.9</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/utbyttekalkulator/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/bevegelser/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/aksjer/hoyest-utbytte/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.8</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/aksjer/utbyttevekst/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/aksjer/konsistente-utbytteaksjer/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/aksjer/lavest-payout/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""",
        f"""  <url>
    <loc>https://exday.no/personvern/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.3</priority>
  </url>""",
    ]
    for sektor in sorted(sektorer.keys()):
        slug = _sektor_slug(sektor)
        urls.append(f"""  <url>
    <loc>https://exday.no/aksjer/sektor/{slug}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.75</priority>
  </url>""")
    for a in aksjer:
        urls.append(f"""  <url>
    <loc>https://exday.no/aksjer/{a["ticker"]}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>daily</changefreq>
    <priority>0.7</priority>
  </url>""")

    sitemap_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_content += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sitemap_content += "\n".join(urls)
    sitemap_content += "\n</urlset>"

    sitemap_path = os.path.join(root_dir, "sitemap.xml")
    with open(sitemap_path, "w", encoding="utf-8") as f:
        f.write(sitemap_content)
    total = len(urls)
    print(f"Sitemap oppdatert med {total} URL-er: {sitemap_path}")


def hent_osebx_historikk():
    """Henter OSEBX (^OSEAX) 30-dagers historikk fra Yahoo Finance."""
    try:
        ticker = yf.Ticker("^OSEAX")
        hist = ticker.history(period="30d")
        if hist.empty:
            print("  OSEBX: Ingen data returnert")
            return {}
        result = {}
        for d, v in hist["Close"].items():
            dato = str(d.date()) if hasattr(d, "date") else str(d)[:10]
            result[dato] = round(float(v), 2)
        print(f"  OSEBX: {len(result)} datapunkter hentet")
        return result
    except Exception as e:
        print(f"  Kunne ikke hente OSEBX: {e}")
        return {}


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

    print("\nForhenter Euronext-priser...")
    euronext_priser = hent_euronext_priser()

    for meta in AKSJER:
        aksje = hent_aksje(meta)
        if aksje:
            # Berik med Euronext-pris hvis Yahoo-pris mangler
            if aksje.get("pris", 0) == 0 and meta["ticker"] in euronext_priser:
                aksje["pris"] = euronext_priser[meta["ticker"]]
                aksje["data_kilde"] = "euronext"
            # Bevar ai_oppsummering fra forrige kjøring
            if meta["ticker"] in fallback:
                prev = fallback[meta["ticker"]]
                if prev.get("ai_oppsummering"):
                    aksje["ai_oppsummering"] = prev["ai_oppsummering"]
                if prev.get("ai_oppsummering_dato"):
                    aksje["ai_oppsummering_dato"] = prev["ai_oppsummering_dato"]
            resultater.append(aksje)
        elif meta["ticker"] in fallback:
            fb = dict(fallback[meta["ticker"]])
            # Sett data_kilde — behold "yahoo" hvis kjent, sett "euronext" hvis vi oppdaterer pris
            if not fb.get("data_kilde"):
                fb["data_kilde"] = "yahoo"
            if fb.get("pris", 0) == 0 and meta["ticker"] in euronext_priser:
                fb["pris"] = euronext_priser[meta["ticker"]]
                fb["data_kilde"] = "euronext"
            print(f"    Bruker fallback-data for {meta['ticker']}")
            resultater.append(fb)
            feil.append(meta["ticker"])
        elif meta["ticker"] in FALLBACK_DATA:
            fb = dict(FALLBACK_DATA[meta["ticker"]])
            # Berik statisk data med Euronext-pris
            if meta["ticker"] in euronext_priser:
                fb["pris"] = euronext_priser[meta["ticker"]]
                fb["data_kilde"] = "euronext"
            print(f"    Bruker statisk fallback for {meta['ticker']}")
            resultater.append(fb)
            ingen_data.append(meta["ticker"])
        else:
            print(f"    KRITISK: Ingen data for {meta['ticker']} og ingen fallback.")
            ingen_data.append(meta["ticker"])

    # ── DNB-datoer: berik ex_dato og betaling_dato ───────────────────────────
    print("\nHenter utbyttedatoer fra DNB Markets...")
    dnb_datoer = hent_dnb_datoer()
    if dnb_datoer:
        dnb_treff = 0
        for aksje in resultater:
            t = aksje["ticker"]
            navn_dnb = DNB_NAVN.get(t)
            if not navn_dnb:
                continue
            # Normaliser navn for oppslag (samme logikk som _processer_dnb_rader)
            oppslag = _normaliser_dnb_navn(navn_dnb)
            if oppslag in dnb_datoer:
                dnb = dnb_datoer[oppslag]
                if dnb.get("ex_dato"):
                    dnb_ex = dnb["ex_dato"]
                    # DNB Markets publiserer offisielle ex-datoer fra Oslo Børs — ingen +1-korreksjon.
                    if not aksje.get("ex_dato"):
                        # Yahoo manglet ex_dato — bruk DNB-dato direkte
                        aksje["ex_dato"] = dnb_ex
                        dnb_treff += 1
                    elif dnb_ex > aksje.get("ex_dato", ""):
                        # DNB har en nyere dato enn Yahoo — bruk DNB
                        aksje["ex_dato"] = dnb_ex
                        dnb_treff += 1
                if dnb.get("betaling_dato") and not aksje.get("betaling_dato"):
                    aksje["betaling_dato"] = dnb["betaling_dato"]
                # Bruk DNBs annonserte utbyttebeløp som primærkilde
                dnb_belop = dnb.get("utbytte", 0)
                if dnb_belop and dnb_belop > 0:
                    aksje["siste_utbytte"] = dnb_belop
                    dnb_valuta = dnb.get("valuta", "")
                    aksje_valuta = aksje.get("valuta", "NOK")
                    if dnb_valuta == aksje_valuta or dnb_valuta == "":
                        frekvens_map = {
                            "Månedlig": 12, "Kvartalsvis": 4,
                            "Halvårlig": 2, "Årlig": 1, "Uregelmessig": 1,
                        }
                        per_ar = frekvens_map.get(aksje.get("frekvens", ""), 1)
                        dnb_annual = round(dnb_belop * per_ar, 4)
                        if dnb_annual > 0:
                            aksje["utbytte_per_aksje"] = dnb_annual
                            if aksje.get("pris", 0) > 0:
                                aksje["utbytte_yield"] = round(
                                    (dnb_annual / aksje["pris"]) * 100, 2
                                )
        print(f"  DNB oppdaterte ex_dato for {dnb_treff} aksjer")

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

    # ── T4b: Datakvalitets-terskel — stopp deploy hvis dataene er ubrukelige ──
    antall_null_pris   = sum(1 for a in resultater if a.get("pris", 0) <= 0)
    antall_hoy_yield   = sum(1 for a in resultater if a.get("utbytte_yield", 0) > 30)
    antall_mangler_felt = sum(
        1 for a in resultater
        if not a.get("navn") or not a.get("ticker") or a.get("pris") is None
    )

    kritiske_feil = []
    if antall_null_pris > len(resultater) // 2:
        kritiske_feil.append(f"{antall_null_pris}/{len(resultater)} aksjer har pris = 0")
    if antall_hoy_yield > len(resultater) // 2:
        kritiske_feil.append(f"{antall_hoy_yield}/{len(resultater)} aksjer har yield > 30 %")
    if antall_mangler_felt > len(resultater) // 2:
        kritiske_feil.append(f"{antall_mangler_felt}/{len(resultater)} aksjer mangler kritiske felt")

    if kritiske_feil:
        print("\n" + "!" * 54)
        print("  KRITISK DATAKVALITETSFEIL — deploy avbrutt")
        for f_melding in kritiske_feil:
            print(f"  ✗ {f_melding}")
        print("!" * 54)
        sys.exit(2)

    # Hent OSEBX-historikk
    print("\nHenter OSEBX-historikk...")
    osebx_data = hent_osebx_historikk()

    # Lagre til JSON
    output = {
        "sist_oppdatert": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kilde": "Yahoo Finance (yfinance)",
        "aksjer": resultater,
        "osebx_historikk": osebx_data,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    # Erstatt Infinity/NaN med null — ugyldig JSON som brekker nettlesere
    import math
    def _sanitize(obj):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(_sanitize(output), f, ensure_ascii=False, indent=2)

    print(f"\nFerdig! {len(resultater)} aksjer lagret til {output_path}")
    print(f"Sist oppdatert: {output['sist_oppdatert']}")

    # Generer individuelle aksjesider, sektorsider og sitemap
    root_dir = os.path.join(os.path.dirname(__file__), "..")
    generer_aksjesider(resultater, root_dir)
    generer_sektorsider(resultater, root_dir)
    generer_topplistesider(resultater, root_dir)
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    generer_sitemap(resultater, root_dir, today)
    oppdater_index_html_meta(len(resultater), root_dir)


def oppdater_index_html_meta(antall_aksjer: int, root_dir: str):
    """Oppdaterer hardkodet antall aksjer i meta-tagger og JSON-LD i index.html."""
    path = os.path.join(root_dir, "index.html")
    if not os.path.exists(path):
        print("  Advarsel: index.html ikke funnet, hopper over meta-oppdatering")
        return
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    oppdatert = re.sub(
        r'((?:Oversikt|Daglig oppdatert oversikt) over )\d+( norske utbytteaksjer)',
        rf'\g<1>{antall_aksjer}\g<2>',
        html
    )
    if oppdatert == html:
        print(f"  index.html: ingen endring (allerede {antall_aksjer} aksjer)")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(oppdatert)
    print(f"  index.html meta-beskrivelse oppdatert → {antall_aksjer} aksjer")


if __name__ == "__main__":
    main()
