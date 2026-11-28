"""Engelske aksjesider, /en/stocks/{TICKER}/ (steg 1, på grenen claude/engelsk).

Bruker de samme tallene og de samme reglene som den norske aksjesiden:
utbytte_i_tittel(), utbytte_perioder(), forrige_borsdag(), ex_forbehold_gjelder()
og hendelse_uten_mal() fra fetch_stocks.py. Bare ordene er nye. Det som er
oversatt, står i ordlistene øverst, så en sektor eller en merkelapp som
mangler gir en feil i testene, ikke norsk tekst på en engelsk side.

Sidene har noindex til eieren har godkjent dem. Selskapsteksten, FAQ og
rapportoppsummeringene er ikke med ennå (steg 2 og 3); siden lenker til den
norske siden for dem.

    python scripts/engelsk.py EQNR DNB FRO --ut KATALOG
"""

import argparse
import datetime
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_stocks as fs  # noqa: E402

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Ordliste ─────────────────────────────────────────────────────────────────

SEKTOR_EN = {
    "Energi": "Energy",
    "Energitjenester": "Energy services",
    "Finans": "Financials",
    "Industri": "Industrials",
    "Shipping": "Shipping",
    "Havbruk": "Seafood",
    "Informasjonsteknologi": "Information technology",
    "Materialer": "Materials",
    "Forbruksvarer": "Consumer goods",
    "Kommunikasjonstjenester": "Communication services",
    "Fornybar energi": "Renewable energy",
    "Eiendom": "Real estate",
    "Helsevern": "Health care",
    "Telekommunikasjon": "Telecommunications",
}

LAND_EN = {
    "Norge": "Norway",
    "Bermuda": "Bermuda",
    "Singapore": "Singapore",
    "Kypros": "Cyprus",
    "Marshalløyene": "the Marshall Islands",
    "Luxembourg": "Luxembourg",
    "Færøyene": "the Faroe Islands",
    "Storbritannia": "the United Kingdom",
    "Sverige": "Sweden",
    "Belgia": "Belgium",
    "Sveits": "Switzerland",
    "Danmark": "Denmark",
    "Nederland": "the Netherlands",
}

FREKVENS_EN = {
    "Årlig": "Annual",
    "Halvårlig": "Semi-annual",
    "Kvartalsvis": "Quarterly",
    "Månedlig": "Monthly",
    "Uregelmessig": "Irregular",
}

HENDELSE_EN = {
    "oppkjop": "Takeover offer",
    "fusjon": "Merger",
    "mulig_fusjon": "Possible merger",
    "fusjon_overtar": "Merger, the company continues",
    "avvikling": "Wind-down",
    "bytte_av_marked": "Change of marketplace",
    "bytte_av_hjemland": "Change of domicile",
    "utbytte_pause": "Distributions paused",
}

MND_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MND_LANG_EN = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

TALLORD_EN = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
              7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


# ── Tall og datoer ──────────────────────────────────────────────────────────

def nf(x, d=2):
    """1,234.56. Bare for tekst leseren ser, aldri for SVG eller CSS."""
    if x is None:
        return "—"
    return f"{float(x):,.{d}f}"


def pst(x, d=2):
    return "—" if x is None else f"{float(x):.{d}f}%"


def belop(b, valuta="NOK", d=2):
    """«NOK 15.30», «USD 0.39». Små beløp får de desimalene de har (DNO 0.375)."""
    if b is None:
        return "—"
    b = float(b)
    if b < 1 and round(b, 2) != round(b, 4):
        d = len(f"{b:.4f}".rstrip("0").split(".")[1])
    return f"{valuta} {nf(b, d)}"


def dato(iso):
    """«15 Feb 2027»."""
    if not iso:
        return ""
    d = datetime.date.fromisoformat(str(iso)[:10])
    return f"{d.day} {MND_EN[d.month - 1]} {d.year}"


def maaneder(mnd):
    """«February, May, August and November»."""
    navn = [MND_LANG_EN[m - 1] for m in sorted(mnd)]
    if len(navn) <= 1:
        return "".join(navn)
    return ", ".join(navn[:-1]) + " and " + navn[-1]


def hentet_dato(hentet):
    """Oslo-datoen et UTC-tidspunkt hører til, som «27 Nov 2026», eller ""."""
    if not hentet:
        return ""
    try:
        from zoneinfo import ZoneInfo
        t = datetime.datetime.fromisoformat(str(hentet).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=datetime.timezone.utc)
        return dato(t.astimezone(ZoneInfo("Europe/Oslo")).date().isoformat())
    except (ValueError, TypeError, ImportError):
        return ""


# ── Ord som bygges av reglene ───────────────────────────────────────────────

def arsrate_merke_en(a):
    """Samme regel som arsrate_merke() i fetch_stocks.py, på engelsk."""
    kilde = a.get("arsrate_kilde")
    if kilde == "betalt_12m":
        merke = "last 12 months"
    elif kilde == "siste_utbetalinger":
        n = a.get("arsrate_antall") or 0
        merke = f"last {TALLORD_EN.get(n, n)} payments" if n > 1 else "last payment"
    elif kilde == "kunngjort":
        return "announced payment"
    elif kilde == "betalt_og_kunngjort":
        return "paid and announced"
    elif kilde == "pause":
        return "distributions paused"
    elif kilde == "kun_engangs":
        return "only one-off dividends in the last 12 months"
    else:
        return ""
    return merke + (", excluding one-off dividends" if a.get("arsrate_ekstra_trukket") else "")


def rate_merke_en(a):
    """Merket ved årsraten: regelens merke, ellers «annualised» for den som
    betaler flere ganger i året. Samme valg som _arsrate_ledd()."""
    return arsrate_merke_en(a) or (
        "annualised" if a.get("frekvens") in fs.UTBETALINGER_PR_AAR else "")


def navn_en(a):
    """Selskapsnavnet er et egennavn og oversettes ikke, bortsett fra aksjeklassen."""
    return re.sub(r"\(([AB])-aksje\)", r"(\1 shares)", a["navn"])


def kort_navn(a):
    return fs._kort_selskapsnavn(navn_en(a))


def tittel_og_h1(a, today):
    """(title, h1). Samme beløp som den norske tittelen, ingen yield i H1."""
    navn, ticker = kort_navn(a), a["ticker"]
    aar = str(today)[:4]
    t = fs.utbytte_i_tittel(a, today)
    if not t:
        h1 = f"{navn} dividend and yield"
        return f"{h1} | {ticker} | exday.no", h1
    ledd = belop(t["belop"], t["valuta"]) + " per share"
    if t["forbehold"]:
        ledd = "proposed " + ledd
    if fs._flere_i_aaret(a, t):
        ledd += " a year"
    h1 = f"{navn} dividend {aar}: {ledd}"
    tittel = h1 + (f" – ex-date {dato(t['ex'])}" if t["ex"] else "")
    return f"{tittel} | {ticker}", h1


def ingress(a, today):
    """Første avsnitt: beløpet, siste kjøpsdag og betalingsdagen."""
    navn = kort_navn(a)
    t = fs.utbytte_i_tittel(a, today)
    yield_ = a.get("utbytte_yield") or 0
    deler = []
    if t and t["art"] == "neste":
        ex = datetime.date.fromisoformat(t["ex"])
        siste = fs.forrige_borsdag(ex)
        verb = "has proposed" if t["forbehold"] else "pays"
        deler.append(f"{navn} {verb} {belop(t['belop'], t['valuta'])} per share "
                     f"with an ex-dividend date of {dato(t['ex'])}.")
        deler.append(f"To receive it you must own the shares at the close on "
                     f"{dato(siste.isoformat())}, the last trading day before.")
        if t["forbehold"]:
            deler.append("The general meeting has not yet approved it.")
        if a.get("betaling_dato") and a["betaling_dato"] >= t["ex"]:
            deler.append(f"Payment is expected on {dato(a['betaling_dato'])}.")
        if a.get("frekvens") in fs.UTBETALINGER_PR_AAR and (a.get("utbytte_per_aksje") or 0) > 0:
            deler.append(f"Over a year the dividend is {belop(a['utbytte_per_aksje'])} per share "
                         f"({rate_merke_en(a)}), a yield of {pst(yield_)} at today's price.")
    elif t:
        aaret = " a year" if fs._flere_i_aaret(a, t) else ""
        merke = rate_merke_en(a)
        deler.append(f"{navn} pays {belop(t['belop'])} per share{aaret}"
                     + (f" ({merke})" if merke else "")
                     + f", a yield of {pst(yield_)} at today's price.")
        if a.get("utbetalingsmaaneder"):
            deler.append(f"The ex-dividend date has usually been in "
                         f"{maaneder(a['utbetalingsmaaneder'])}.")
    else:
        deler.append(f"Dividend figures for {navn_en(a)} ({a['ticker']}), listed on {a.get('bors') or 'Oslo Børs'}.")
    return " ".join(deler)


def nokkeltall(a, today):
    t = fs.utbytte_i_tittel(a, today)
    ruter = [("Price", html.escape(belop(a.get("pris")))),
             ("Annual dividend", html.escape(belop(a.get("utbytte_per_aksje"))),
              html.escape(rate_merke_en(a))),
             ("Yield", pst(a.get("utbytte_yield")))]
    ruter.append(("Frequency", FREKVENS_EN.get(a.get("frekvens"), "—")))
    ex = a.get("ex_dato") or ""
    if ex and ex >= str(today)[:10]:
        ruter.append(("Next ex-date", dato(ex), "proposed" if t and t.get("forbehold") else ""))
    elif a.get("utbetalingsmaaneder"):
        ruter.append(("Usual ex-months", ", ".join(MND_EN[m - 1] for m in a["utbetalingsmaaneder"])))
    else:
        ruter.append(("Next ex-date", "Not known"))
    payout = a.get("payout_ratio") or 0
    # 0 betyr ukjent, ikke lav (se «payout_ratio artifacts» i CLAUDE.md).
    ruter.append(("Payout ratio", pst(payout, 0) if payout > 0 else "—"))
    return fs.tallruter_html(ruter, merkelapp="Key figures")


def betalt_tabell(a):
    """«Dividends paid»: siste 12 mnd og snitt per år, fra utbytte_perioder()."""
    rader = []
    for p in fs.utbytte_perioder(a):
        if p["periode"] == "12m":
            etikett = "Last 12 months"
        elif p["fra"] == p["til"]:
            etikett = f"{p['fra']}"
        else:
            etikett = f"Average {p['fra']}–{str(p['til'])[2:]}"
        rader.append(f'<tr><td>{etikett}</td><td class="tall">{html.escape(belop(p["belop"]))}</td>'
                     f'<td class="tall">{pst(p["yield"])}</td></tr>')
    if not rader:
        return ""
    return ('<h2 id="paid">Dividends paid</h2>'
            '<div class="tabell-ramme"><table class="en-tabell"><thead><tr><th>Period</th>'
            '<th class="tall">Per share a year</th><th class="tall">Yield today</th></tr></thead><tbody>'
            + "".join(rader) + '</tbody></table></div>'
            '<p class="note les">By ex-dividend date. Includes any special dividends. The yield is measured '
            "against today's share price, so it shows what the payments would be worth to a buyer today.</p>")


def historikk(a, today):
    """Hele år fra utbytte_per_ar, og inneværende år som «so far»."""
    per_ar = a.get("utbytte_per_ar") or {}
    if not per_ar:
        return ""
    aar = str(today)[:4]
    hittil = sum(b for d, b in (a.get("utbetalinger") or []) if str(d)[:4] == aar)
    forste = a.get("utbytte_forste_ar")
    rader = []
    if hittil > 0:
        rader.append(f'<tr><td>{aar} <span class="note">so far</span></td>'
                     f'<td class="tall">{html.escape(belop(hittil))}</td></tr>')
    for y in sorted(per_ar, reverse=True):
        if forste and int(y) < forste:
            continue
        verdi = html.escape(belop(per_ar[y])) if per_ar[y] else "No dividend"
        rader.append(f'<tr><td>{y}</td><td class="tall">{verdi}</td></tr>')
    # Rekken, ikke antallet år med utbytte («År på rad» i CLAUDE.md).
    rekke = (fs.utbytterekke(a, today) or {}).get("rad") or 0
    linje = (f'<p class="les">{kort_navn(a)} has paid a dividend {rekke} years in a row.</p>'
             if rekke >= 3 else "")
    return ('<h2 id="history">Dividend history</h2>' + linje +
            '<div class="tabell-ramme"><table class="en-tabell"><thead><tr><th>Year</th>'
            '<th class="tall">Per share</th></tr></thead><tbody>' + "".join(rader) +
            '</tbody></table></div>')


def om_selskapet(a):
    """Den oversatte selskapsteksten, bare når den hører til dagens norske tekst."""
    import oversett
    norsk = (fs._redaksjonell_intro(a["ticker"], a.get("sektor", "")) or "").strip()
    tekst = oversett.gjeldende("selskap", a["ticker"], norsk)
    if not tekst:
        return ""
    avsnitt = [html.escape(re.sub(r"\s+", " ", x).strip()) for x in re.split(r"\n\s*\n", tekst) if x.strip()]
    return ('<h2 id="about">About the company</h2><div class="les">'
            + "".join(f"<p>{x}</p>" for x in avsnitt) + '</div>')


def hendelse_boks(a):
    h = a.get("hendelse") or {}
    if not h.get("type"):
        return ""
    etikett = HENDELSE_EN.get(h["type"], "Corporate event")
    tekst = (" The dividend history may say little about future dividends."
             if fs.hendelse_uten_mal(a) else "")
    lenke = ""
    if h.get("melding"):
        lenke = (f' <a href="https://newsweb.oslobors.no/message/{html.escape(str(h["melding"]))}" '
                 'rel="noopener">Read the stock exchange notice</a>.')
    naar = f" ({dato(h['dato'])})" if h.get("dato") else ""
    return f'<div class="varsel les"><p><strong>{etikett}{naar}.</strong>{tekst}{lenke}</p></div>'


# Kildeskatt, kontrollert 28.11.2026 mot Skatteetaten («Reduced withholding tax
# on dividends», med undersidene «Refunds» og «Future dividends») og PwC
# Worldwide Tax Summaries for Bermuda, Kypros og Singapore. Skatteetaten sier
# ikke «typisk 15 %», så siden nevner ingen avtalesats.
SKATTEETATEN_KILDESKATT = ("https://www.skatteetaten.no/en/person/taxes/get-the-taxes-right/"
                           "shares-and-securities/about-shares-and-securities/"
                           "reduced-withholding-tax-on-dividends/")
UTENLANDSK_KILDESKATT = {
    "Bermuda": "Bermuda does not withhold tax on dividends.",
    "Singapore": "Singapore does not withhold tax on dividends.",
    "Kypros": "Cyprus does not, as a rule, withhold tax on dividends paid to shareholders abroad.",
}


def skatt(a):
    """Kildeskatt for den som bor utenfor Norge, etter hvor selskapet hører hjemme."""
    land = a.get("inkorporeringsland") or "Norge"
    navn = kort_navn(a)
    lenke = f'<a href="{SKATTEETATEN_KILDESKATT}" rel="noopener">the Norwegian Tax Administration</a>'
    if land == "Norge":
        tekst = (f"{navn} is a Norwegian company, and Norwegian companies deduct 25% withholding tax "
                 "on dividends to shareholders resident abroad. If a tax treaty between Norway and "
                 "your country gives a lower rate, you can get it when the dividend is paid by giving "
                 "your custodian or account operator the documentation, or apply to "
                 f"{lenke} for a refund afterwards, within five years. Shareholders resident in the EEA "
                 "may instead use the risk-free return allowance where that gives less tax, and "
                 "companies resident in the EEA may be exempt. Your own country may also tax the dividend.")
    else:
        land_en = LAND_EN.get(land, land)
        tekst = (f"{navn} is registered in {land_en}. Norwegian withholding tax is deducted by "
                 "Norwegian companies, so the rules of " + land_en + " apply instead. "
                 + UTENLANDSK_KILDESKATT.get(land, "")
                 + " Your own country may also tax the dividend.").replace("  ", " ")
    if (fs.kapital_andel(a) or 0) > 0:
        tekst += (" The latest payment was a return of paid-in capital rather than a dividend. "
                  "Check how your country treats it.")
    return f'<h2 id="tax">Tax for investors outside Norway</h2><p class="les">{tekst}</p>'


# ── Siden ───────────────────────────────────────────────────────────────────

GA_HEAD = """  <script async src="https://www.googletagmanager.com/gtag/js?id=G-X6C9PERKMB"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('consent', 'default', {
      analytics_storage: 'denied',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      wait_for_update: 500
    });
    gtag('js', new Date());
    gtag('config', 'G-X6C9PERKMB');
  </script>
  <script src="/assets/consent.js" defer></script>"""

CSS = """
    body { margin: 0; background: #f9fafb; color: #111827; }
    .dark body { background: #030712; color: #f3f4f6; }
    .en-tabell td, .norsk-boks p { color: inherit; }
    .wrap { max-width: 56rem; margin: 0 auto; padding: 1rem 1rem 2rem; }
    .sub { color: #4b5563; font-size: 0.9rem; margin: 0.25rem 0 1rem; }
    .dark .sub { color: #9ca3af; }
    .ingress { font-size: 1.02rem; line-height: 1.6; margin: 0 0 1.25rem; }
    h2 { font-size: 1.15rem; font-weight: 700; margin: 2rem 0 0.75rem; }
    p { line-height: 1.6; }
    a { color: #275f45; } .dark a { color: #6fa98a; }
    .tabell-ramme { overflow-x: auto; -webkit-overflow-scrolling: touch; }
    table.en-tabell { width: 100%; border-collapse: collapse; font-size: 0.92rem; background: #fff;
      border: 1px solid #e5e7eb; border-radius: 0.75rem; overflow: hidden; }
    .dark table.en-tabell { background: #111827; border-color: #1f2937; }
    .en-tabell th, .en-tabell td { padding: 0.55rem 0.8rem; border-bottom: 1px solid #e5e7eb; text-align: left; }
    .dark .en-tabell th, .dark .en-tabell td { border-color: #1f2937; }
    .en-tabell tr:last-child td { border-bottom: 0; }
    .en-tabell th { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; color: #6b7280; font-weight: 600; }
    .en-tabell .tall { text-align: right; white-space: nowrap; }
    .note { font-size: 0.8rem; color: #6b7280; } .dark .note { color: #9ca3af; }
    .varsel { border-left: 4px solid #b98a3a; background: #fbf8f0; padding: 0.75rem 1rem; border-radius: 0.5rem; margin: 0 0 1.25rem; }
    .dark .varsel { background: rgba(87,61,27,0.25); }
    .varsel p { margin: 0; }
    .sprak-lenke { display: inline-flex; align-items: center; min-height: 44px; }
    .norsk-boks { background: #fff; border: 1px solid #e5e7eb; border-radius: 0.75rem; padding: 0.25rem 1rem; margin-top: 2rem; }
    .dark .norsk-boks { background: #111827; border-color: #1f2937; }
"""

TEMA_SKRIPT = """<script>
  (function() {
    var btn = document.getElementById('dark-toggle');
    if (!btn) return;
    var root = document.documentElement;
    var sun = btn.querySelector('.sun-icon'), moon = btn.querySelector('.moon-icon');
    function sync() { var d = root.classList.contains('dark'); sun.style.display = d ? 'none' : ''; moon.style.display = d ? '' : 'none'; }
    sync();
    btn.addEventListener('click', function() {
      var d = root.classList.toggle('dark');
      localStorage.setItem('tema', d ? 'dark' : 'light');
      sync();
    });
  })();
</script>"""

FOOTER = """  <footer class="std-footer" style="margin-top:2rem;padding-top:1.5rem;border-top:1px solid #e5e7eb;font-size:0.78rem;text-align:center;color:#6b7280;line-height:1.6;">
    <p>Prices and dividend data come from Yahoo Finance, Euronext and the companies' notices to Oslo B&#248;rs. Updated on trading days.</p>
    <p style="max-width:36rem;margin:0.4rem auto;">
      exday.no is not an investment firm and does not give financial advice.
      The data may contain errors or delays, so check against Oslo B&#248;rs or the company's own reports.
      Past dividends are no guarantee of future dividends.
    </p>
    <p style="margin-top:0.5rem;">
      <a href="/om/" lang="nb" style="color:#6b7280;text-decoration:underline;">About exday.no (Norwegian)</a>
      <span style="margin:0 0.4rem;">&#183;</span>
      <a href="/metode/" lang="nb" style="color:#6b7280;text-decoration:underline;">Method and data sources (Norwegian)</a>
      <span style="margin:0 0.4rem;">&#183;</span>
      <a href="/personvern/" lang="nb" style="color:#6b7280;text-decoration:underline;">Privacy (Norwegian)</a>
    </p>
  </footer>
  <style>.dark .std-footer { color:#9ca3af !important; border-color:#1f2937 !important; } .dark .std-footer a { color:#9ca3af !important; }</style>"""

SOL = ('<svg class="sun-icon" width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">'
       '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>')
MAANE = ('<svg class="moon-icon" width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="display:none;" aria-hidden="true">'
         '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>')


def url_en(ticker):
    return f"/en/stocks/{ticker}/"


def url_nb(ticker):
    return f"/aksjer/{ticker}/"


def meta_beskrivelse(a, today):
    t = fs.utbytte_i_tittel(a, today)
    navn = kort_navn(a)
    if t and t["art"] == "neste":
        siste = fs.forrige_borsdag(datetime.date.fromisoformat(t["ex"]))
        tekst = (f"{navn} pays {belop(t['belop'], t['valuta'])} per share, ex-dividend "
                 f"{dato(t['ex'])}. Last day to buy: {dato(siste.isoformat())}. Yield, history and tax.")
    else:
        tekst = f"{navn} ({a['ticker']}) dividend per share, yield, ex-dividend months and payment history."
    return tekst[:155]


def aksje_side_en(a, today):
    """Hele den engelske aksjesiden som HTML."""
    today = datetime.date.fromisoformat(str(today)[:10])
    ticker = a["ticker"]
    tittel, h1 = tittel_og_h1(a, today)
    beskr = meta_beskrivelse(a, today)
    kanonisk = f"https://exday.no{url_en(ticker)}"
    sub = " · ".join(x for x in [
        f"{html.escape(navn_en(a))} ({ticker})",
        SEKTOR_EN.get(a.get("sektor"), ""),
        (FREKVENS_EN[a["frekvens"]] + (" dividends" if a["frekvens"] == "Uregelmessig" else " dividend"))
        if a.get("frekvens") in FREKVENS_EN else "",
        html.escape(a.get("bors") or "Oslo Børs"),
    ] if x)
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebPage", "@id": kanonisk, "url": kanonisk, "name": tittel,
         "description": beskr, "inLanguage": "en"},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": fs.BRODSMULE_ROT, "item": "https://exday.no/"},
            {"@type": "ListItem", "position": 2, "name": ticker, "item": kanonisk}]},
    ]}
    skille = f' <span class="brodsmule-skille" aria-hidden="true">{fs.BRODSMULE_SKILLETEGN}</span> '
    smule = (f'<nav class="brodsmule" aria-label="Breadcrumb"><a href="/">{fs.BRODSMULE_ROT}</a>'
             f'{skille}<span aria-current="page">{ticker}</span></nav>')
    hentet = hentet_dato(a.get("hentet"))
    hentet_linje = f'<p class="note">Figures fetched {hentet}.</p>' if hentet else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <script>(function(){{if(localStorage.getItem('tema')!=='light')document.documentElement.classList.add('dark');}})()</script>
{fs.ADSENSE_HEAD}
{GA_HEAD}
  <title>{html.escape(tittel)}</title>
  <meta name="description" content="{html.escape(beskr)}"/>
  <meta name="robots" content="noindex,follow"/>
  <link rel="canonical" href="{kanonisk}"/>
  <link rel="alternate" hreflang="nb" href="https://exday.no{url_nb(ticker)}"/>
  <link rel="alternate" hreflang="en" href="{kanonisk}"/>
  <link rel="alternate" hreflang="x-default" href="https://exday.no{url_nb(ticker)}"/>
  <meta name="theme-color" content="#2f7352"/>
  <link rel="icon" type="image/png" sizes="512x512" href="/favicon.png"/>
  <link rel="icon" type="image/svg+xml" href="/logo/exday_icon_primary.svg"/>
  <link rel="apple-touch-icon" href="/logo/apple_touch_icon_180.png"/>
  <meta property="og:title" content="{html.escape(tittel)}"/>
  <meta property="og:description" content="{html.escape(beskr)}"/>
  <meta property="og:url" content="{kanonisk}"/>
  <meta property="og:type" content="website"/>
  <meta property="og:locale" content="en_GB"/>
  <meta property="og:locale:alternate" content="nb_NO"/>
  <meta property="og:site_name" content="exday.no"/>
  <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
  <link rel="stylesheet" href="/assets/tailwind.css"/>
  <link rel="stylesheet" href="/assets/style.css"/>
  <style>{CSS}  </style>
</head>
<body>
  <nav class="site-nav" aria-label="Main menu">
    <div class="site-nav-inner">
      <a href="/" class="site-logo" aria-label="exday.no home">
        <img src="/logo/exday_icon_primary.svg" class="site-logo-icon site-logo-icon-light" alt="" width="28" height="28"><img src="/logo/exday_icon_inverse.svg" class="site-logo-icon site-logo-icon-dark" alt="" width="28" height="28">
        <span>e<span class="site-logo-x">x</span>day<span class="site-logo-dot">.no</span></span>
      </a>
      <div class="site-nav-actions">
        <a href="{url_nb(ticker)}" class="site-app-btn" hreflang="nb" lang="nb">Norsk</a>
        <button id="dark-toggle" class="site-dark-btn" aria-label="Switch colour mode">{SOL}{MAANE}</button>
      </div>
    </div>
  </nav>
<div class="wrap">
  {smule}
  <h1 class="side-h1">{html.escape(h1)}</h1>
  <p class="sub">{sub}</p>
  {hendelse_boks(a)}
  <p class="ingress les">{html.escape(ingress(a, today))}</p>
  {nokkeltall(a, today)}
  {hentet_linje}
  {om_selskapet(a)}
  {betalt_tabell(a)}
  {historikk(a, today)}
  {skatt(a)}
  <div class="norsk-boks les">
    <p>{"Frequently asked questions" if om_selskapet(a) else "The company description, frequently asked questions"}, quarterly report summaries and the price chart
    are on the <a href="{url_nb(ticker)}" hreflang="nb">Norwegian page for {ticker}</a>.</p>
  </div>
{FOOTER}
</div>
{TEMA_SKRIPT}
</body>
</html>
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tickere", nargs="+")
    p.add_argument("--ut", required=True, help="Rotkatalogen sidene skrives under (en/stocks/…)")
    p.add_argument("--dato", default=None, help="Dagens dato, ÅÅÅÅ-MM-DD (for tester)")
    args = p.parse_args()
    with open(os.path.join(ROT, "data", "aksjer.json"), encoding="utf-8") as f:
        data = json.load(f)
    rader = {a["ticker"]: a for a in data["aksjer"]}
    today = args.dato or datetime.date.today().isoformat()
    for t in args.tickere:
        a = rader.get(t)
        if not a:
            print(f"Ukjent ticker: {t}", file=sys.stderr)
            continue
        mappe = os.path.join(args.ut, "en", "stocks", t)
        os.makedirs(mappe, exist_ok=True)
        with open(os.path.join(mappe, "index.html"), "w", encoding="utf-8") as f:
            f.write(aksje_side_en(a, today))
        print(f"Skrev {mappe}/index.html")


if __name__ == "__main__":
    main()
