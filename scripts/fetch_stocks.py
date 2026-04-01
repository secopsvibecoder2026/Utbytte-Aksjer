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

# ── TICKER-KONFIGURASJON ─────────────────────────────────────────────────────
# Aksjer og beskrivelser leses fra data/tickers.json — legg til nye aksjer der.
_tickers_path = os.path.join(os.path.dirname(__file__), "..", "data", "tickers.json")
with open(_tickers_path, "r", encoding="utf-8") as _f:
    _ticker_data = json.load(_f)

AKSJER = [{"ticker_yf": t["ticker_yf"], "ticker": t["ticker"],
            "navn": t["navn"], "sektor": t["sektor"], "bors": t["bors"]}
          for t in _ticker_data]

BESKRIVELSER = {t["ticker"]: t.get("beskrivelse", "") for t in _ticker_data}

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
