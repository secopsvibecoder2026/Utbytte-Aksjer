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
import html.parser
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

# ── TICKER-KONFIGURASJON ─────────────────────────────────────────────────────
# Aksjer og beskrivelser leses fra data/tickers.json — legg til nye aksjer der.
_tickers_path = os.path.join(os.path.dirname(__file__), "..", "data", "tickers.json")
with open(_tickers_path, "r", encoding="utf-8") as _f:
    _ticker_data = json.load(_f)

AKSJER = [{"ticker_yf": t["ticker_yf"], "ticker": t["ticker"],
            "navn": t["navn"], "sektor": t["sektor"], "bors": t["bors"]}
          for t in _ticker_data]

BESKRIVELSER = {t["ticker"]: t.get("beskrivelse", "") for t in _ticker_data}
DNB_NAVN = {t["ticker"]: t.get("navn_dnb", t["navn"]) for t in _ticker_data}

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


def _aksje_side_html(a, today):
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
    besk    = a.get("beskrivelse") or ""
    hist    = a.get("historiske_utbytter") or []
    snitt5  = a.get("snitt_yield_5ar") or 0
    valuta  = a.get("valuta") or "NOK"

    meta_desc = (
        f"{navn} ({ticker}) betaler {yield_:.2f}% utbytte. "
        f"Ex-dato: {_fmt_dato(ex)}. "
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
        f'<div class="card"><div class="label">P/E</div>'
        f'<div class="val">{pe:.1f}</div></div>'
    ) if pe and pe > 0 else ""

    besk_seksjon = f'<div class="desc"><p>{besk}</p></div>' if besk else ""

    nokkeltal_seksjon = (
        "<h2>Nøkkeltall</h2>"
        "<table>"
        "<thead><tr><th>Nøkkeltall</th><th>Verdi</th></tr></thead>"
        "<tbody>"
        f"<tr><td>Sektor</td><td>{sektor}</td></tr>"
        f"<tr><td>Frekvens</td><td>{frekvens}</td></tr>"
        f"<tr><td>Utbytte per aksje</td><td>{upa} {valuta}</td></tr>"
        f"<tr><td>Direkteavkastning</td><td>{yield_:.2f}%</td></tr>"
        f"<tr><td>5-årssnitt yield</td><td>{snitt5:.2f}%</td></tr>"
        f"<tr><td>År med utbytte</td><td>{ar_med}</td></tr>"
        f"{pe_rad}"
        "</tbody></table>"
    )

    hist_seksjon = (
        "<h2>Historiske utbytter</h2>"
        "<table>"
        "<thead><tr><th>År</th><th>Utbytte</th><th>Yield</th></tr></thead>"
        f"<tbody>{hist_rader}</tbody>"
        "</table>"
    ) if hist_rader else ""

    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@graph": [
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
                "description": besk or meta_desc,
                "url": f"https://exday.no/aksjer/{ticker}/",
                "provider": {"@type": "Organization", "name": "exday.no", "url": "https://exday.no/"},
            }
        ]
    }, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="nb">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{ticker} – {navn} | Utbytte og ex-dato | exday.no</title>
  <meta name="description" content="{meta_desc}"/>
  <link rel="canonical" href="https://exday.no/aksjer/{ticker}/"/>
  <meta property="og:title" content="{ticker} – {navn} | exday.no"/>
  <meta property="og:description" content="{meta_desc}"/>
  <meta property="og:url" content="https://exday.no/aksjer/{ticker}/"/>
  <meta property="og:type" content="website"/>
  <script type="application/ld+json">{json_ld}</script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #f9fafb; color: #111827; line-height: 1.6; }}
    a {{ color: #16a34a; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 760px; margin: 0 auto; padding: 1.5rem 1rem; }}
    nav {{ font-size: 0.85rem; color: #6b7280; margin-bottom: 1.5rem; }}
    nav a {{ color: #6b7280; }}
    nav span {{ margin: 0 0.35rem; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }}
    .sub {{ color: #6b7280; font-size: 0.95rem; margin-bottom: 1.5rem; }}
    .badge {{ display: inline-block; font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem;
              border-radius: 9999px; background: #dcfce7; color: #15803d; margin-bottom: 1.25rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
    .card {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 0.75rem; padding: 1rem; }}
    .card .label {{ font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #9ca3af; margin-bottom: 0.2rem; }}
    .card .val {{ font-size: 1.25rem; font-weight: 700; color: #111827; }}
    .card .val.green {{ color: #16a34a; }}
    .desc {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 0.75rem; padding: 1rem 1.25rem; margin-bottom: 1.5rem; color: #374151; }}
    h2 {{ font-size: 1rem; font-weight: 700; margin-bottom: 0.75rem; color: #374151; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; border-radius: 0.75rem; overflow: hidden; margin-bottom: 1.5rem; font-size: 0.9rem; }}
    th {{ background: #f3f4f6; padding: 0.6rem 1rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: #6b7280; }}
    td {{ padding: 0.6rem 1rem; border-top: 1px solid #f3f4f6; }}
    tr:hover td {{ background: #f9fafb; }}
    .cta {{ text-align: center; margin-top: 2rem; padding: 1.5rem; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 0.75rem; }}
    .cta a {{ display: inline-block; background: #16a34a; color: #fff; font-weight: 600; padding: 0.65rem 1.5rem; border-radius: 0.5rem; }}
    .cta a:hover {{ background: #15803d; text-decoration: none; }}
    .updated {{ font-size: 0.78rem; color: #9ca3af; text-align: right; margin-top: 1rem; }}
    @media (max-width: 480px) {{ h1 {{ font-size: 1.4rem; }} }}
  </style>
</head>
<body>
<div class="wrap">

  <nav>
    <a href="https://exday.no/">exday.no</a>
    <span>›</span>
    <a href="https://exday.no/aksjer/">Aksjer</a>
    <span>›</span>
    <a href="https://exday.no/aksjer/sektor/{_sektor_slug(sektor)}/">{sektor}</a>
    <span>›</span>
    {ticker}
  </nav>

  <h1>{ticker} – {navn}</h1>
  <p class="sub">{sektor} · {frekvens} utbytte · Oslo Børs</p>
  <span class="badge">{yield_:.2f}% direkteavkastning</span>

  <div class="grid">
    <div class="card">
      <div class="label">Kurs</div>
      <div class="val">{pris:,.0f} {valuta}</div>
    </div>
    <div class="card">
      <div class="label">Yield</div>
      <div class="val green">{yield_:.2f}%</div>
    </div>
    <div class="card">
      <div class="label">Utbytte/aksje</div>
      <div class="val">{upa} {valuta}</div>
    </div>
    <div class="card">
      <div class="label">Ex-dato</div>
      <div class="val" style="font-size:1rem">{_fmt_dato(ex)}</div>
    </div>
    <div class="card">
      <div class="label">Utbetalingsdato</div>
      <div class="val" style="font-size:1rem">{_fmt_dato(bet)}</div>
    </div>
    <div class="card">
      <div class="label">5-årssnitt yield</div>
      <div class="val green">{snitt5:.2f}%</div>
    </div>
    <div class="card">
      <div class="label">År med utbytte</div>
      <div class="val">{ar_med}</div>
    </div>
    {pe_card}
  </div>

  {besk_seksjon}

  {nokkeltal_seksjon}

  {hist_seksjon}

  <div style="margin-top:1.5rem;">
    <a href="/aksjer/sektor/{_sektor_slug(sektor)}/" style="font-size:0.9rem;color:#2563eb;">← Se alle {sektor}-aksjer med utbytte</a>
  </div>

  <div class="cta">
    <p style="margin-bottom:0.75rem;color:#374151;">Se alle norske utbytteaksjer, bygg portefølje og spor ex-datoer</p>
    <a href="https://exday.no/?aksje={ticker}">Åpne {ticker} i exday.no →</a>
  </div>

  <p class="updated">Sist oppdatert: {today}</p>

</div>
</body>
</html>"""


def generer_aksjesider(aksjer, root_dir):
    """Genererer én HTML-side per aksje under aksjer/TICKER/index.html."""
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    aksjer_dir = os.path.join(root_dir, "aksjer")
    os.makedirs(aksjer_dir, exist_ok=True)

    for a in aksjer:
        ticker = a["ticker"]
        ticker_dir = os.path.join(aksjer_dir, ticker)
        os.makedirs(ticker_dir, exist_ok=True)
        html = _aksje_side_html(a, today)
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
    nav {{ font-size: 0.85rem; color: #6b7280; margin-bottom: 1.5rem; }}
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
  </style>
</head>
<body>
<div class="wrap">
  <nav><a href="https://exday.no/">exday.no</a> › Aksjer</nav>
  <h1>Norske utbytteaksjer</h1>
  <p class="sub">Oversikt over {len(aksjer)} utbytteaksjer på Oslo Børs, sortert etter direkteavkastning. Oppdateres daglig.</p>
  <table>
    <thead><tr><th>Ticker</th><th>Navn</th><th>Sektor</th><th>Kurs</th><th>Yield</th><th>Ex-dato</th></tr></thead>
    <tbody>{rader}</tbody>
  </table>
  <div class="cta"><a href="https://exday.no/">Åpne full app med porteføljekalkulator →</a></div>
  <p class="updated">Sist oppdatert: {today}</p>
</div>
</body>
</html>"""

    with open(os.path.join(aksjer_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(oversikt_html)

    print(f"Genererte {len(aksjer)} aksjesider + oversiktsside under aksjer/")


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
  <title>{sektor}-aksjer med utbytte | Oslo Børs | exday.no</title>
  <meta name="description" content="{meta_desc}"/>
  <link rel="canonical" href="https://exday.no/aksjer/sektor/{slug}/"/>
  <meta property="og:title" content="{sektor}-aksjer med utbytte – exday.no"/>
  <meta property="og:description" content="{meta_desc}"/>
  <meta property="og:url" content="https://exday.no/aksjer/sektor/{slug}/"/>
  <script type="application/ld+json">{json_ld}</script>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #f9fafb; color: #111827; line-height: 1.6; }}
    a {{ color: #2563eb; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem; }}
    nav {{ font-size: 0.85rem; color: #6b7280; margin-bottom: 1.5rem; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.5rem; }}
    .sub {{ color: #6b7280; margin-bottom: 1.5rem; font-size: 0.95rem; }}
    .stats {{ display: flex; gap: 1.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; }}
    .stat {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 0.5rem; padding: 0.75rem 1.25rem; }}
    .stat-val {{ font-size: 1.4rem; font-weight: 700; color: #2563eb; }}
    .stat-lbl {{ font-size: 0.75rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.04em; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e5e7eb; border-radius: 0.75rem; overflow: hidden; font-size: 0.9rem; }}
    th {{ background: #f3f4f6; padding: 0.6rem 1rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: #6b7280; }}
    td {{ padding: 0.65rem 1rem; border-top: 1px solid #f3f4f6; }}
    tr:hover td {{ background: #f9fafb; }}
    .yield {{ color: #0891b2; font-weight: 600; }}
    .cta {{ margin-top: 1.5rem; text-align: center; }}
    .cta a {{ display: inline-block; background: #2563eb; color: #fff; font-weight: 600; padding: 0.65rem 1.5rem; border-radius: 0.5rem; }}
    .updated {{ font-size: 0.78rem; color: #9ca3af; text-align: right; margin-top: 1rem; }}
  </style>
</head>
<body>
<div class="wrap">
  <nav><a href="https://exday.no/">exday.no</a> › <a href="/aksjer/">Aksjer</a> › {sektor}</nav>
  <h1>{sektor}-aksjer med utbytte</h1>
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
</div>
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
  <title>Norske utbytteaksjer etter sektor | exday.no</title>
  <meta name="description" content="Finn norske utbytteaksjer på Oslo Børs sortert etter sektor — energi, finans, shipping, havbruk og mer."/>
  <link rel="canonical" href="https://exday.no/aksjer/sektor/"/>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #f9fafb; color: #111827; line-height: 1.6; }}
    a {{ color: #2563eb; text-decoration: none; }}
    .wrap {{ max-width: 900px; margin: 0 auto; padding: 1.5rem 1rem; }}
    nav {{ font-size: 0.85rem; color: #6b7280; margin-bottom: 1.5rem; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.5rem; }}
    .sub {{ color: #6b7280; margin-bottom: 1.5rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 1rem; }}
    .sektor-kort {{ display: block; background: #fff; border: 1px solid #e5e7eb; border-radius: 0.75rem; padding: 1rem 1.25rem; transition: border-color 0.15s; }}
    .sektor-kort:hover {{ border-color: #2563eb; }}
    .sk-navn {{ font-weight: 600; font-size: 1rem; color: #111827; }}
    .sk-antall {{ font-size: 0.8rem; color: #6b7280; margin-top: 0.25rem; }}
  </style>
</head>
<body>
<div class="wrap">
  <nav><a href="https://exday.no/">exday.no</a> › <a href="/aksjer/">Aksjer</a> › Sektorer</nav>
  <h1>Utbytteaksjer etter sektor</h1>
  <p class="sub">Velg en sektor for å se alle aksjer med utbytte innen den kategorien.</p>
  <div class="grid">{sektorkort}
  </div>
</div>
</body>
</html>"""

    with open(os.path.join(sektor_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(sektor_oversikt)

    print(f"Genererte {len(generert)} sektorsider under aksjer/sektor/")


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
                    if not aksje.get("ex_dato") or dnb["ex_dato"] > (aksje.get("ex_dato") or ""):
                        aksje["ex_dato"] = dnb["ex_dato"]
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
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nFerdig! {len(resultater)} aksjer lagret til {output_path}")
    print(f"Sist oppdatert: {output['sist_oppdatert']}")

    # Generer individuelle aksjesider, sektorsider og sitemap
    root_dir = os.path.join(os.path.dirname(__file__), "..")
    generer_aksjesider(resultater, root_dir)
    generer_sektorsider(resultater, root_dir)
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
