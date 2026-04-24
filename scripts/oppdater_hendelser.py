"""
Akkumulerer rapport-datoer i data/hendelser.json og beriker dem med NewsWeb-URLer.

- Legger til nye (ticker, dato)-par fra aksjer.json — sletter aldri eksisterende
- For passerte/dagens hendelser uten URL: søker etter børsmelding på NewsWeb

Kjøres etter fetch_stocks.py i GitHub Actions.
Kjør manuelt: python3 scripts/oppdater_hendelser.py
"""

import json, os, datetime, time, urllib.request, urllib.parse

ROOT        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AKSJER_F    = os.path.join(ROOT, "data", "aksjer.json")
HENDELSER_F = os.path.join(ROOT, "data", "hendelser.json")

_NEWSWEB_API = None

RAPPORT_KW = [
    "kvartalsrapport", "quarterly", "interim report", "interim results",
    "q1 ", "q2 ", "q3 ", "q4 ", " q1", " q2", " q3", " q4",
    "årsrapport", "annual report", "half-year", "halvår",
    "financial results", "results for", "resultat",
]


def _api_base():
    global _NEWSWEB_API
    if _NEWSWEB_API:
        return _NEWSWEB_API
    try:
        req = urllib.request.Request(
            "https://newsweb.oslobors.no/urls.json",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            _NEWSWEB_API = data.get("api_large", "https://api3.oslo.oslobors.no")
    except Exception:
        _NEWSWEB_API = "https://api3.oslo.oslobors.no"
    return _NEWSWEB_API


def _hent_rapport_url(ticker: str, dato: str) -> str | None:
    """Finner NewsWeb-URL til kvartalsrapport publisert på gitt dato (±2 dager)."""
    try:
        api = _api_base()
        endpoint = (
            f"{api}/v1/newsreader/list"
            f"?issuer={urllib.parse.quote(ticker, safe='')}&limit=200"
        )
        req = urllib.request.Request(
            endpoint,
            data=b"",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())

        messages = resp.get("data", {}).get("messages", [])
        target = datetime.date.fromisoformat(dato)

        for msg in messages:
            title = (msg.get("title") or "").lower()
            pub   = (msg.get("publishedTime") or "")[:10]
            if not pub:
                continue
            try:
                pub_date = datetime.date.fromisoformat(pub)
            except ValueError:
                continue
            if abs((pub_date - target).days) > 2:
                continue
            if any(kw in title for kw in RAPPORT_KW):
                msg_id = msg.get("messageId")
                if msg_id:
                    return f"https://newsweb.oslobors.no/message/{msg_id}"

    except Exception as e:
        print(f"    Advarsel NewsWeb URL [{ticker}]: {e}")

    return None


def main():
    with open(AKSJER_F, encoding="utf-8") as f:
        aksjer = json.load(f)["aksjer"]

    if os.path.exists(HENDELSER_F):
        with open(HENDELSER_F, encoding="utf-8") as f:
            data = json.load(f)
        hendelser = data.get("hendelser", [])
    else:
        hendelser = []

    eksisterende = {(h["ticker"], h["dato"]) for h in hendelser}
    lagt_til = 0

    # 1. Legg til nye rapport-datoer fra aksjer.json
    for a in aksjer:
        rd = a.get("rapport_dato")
        if not rd:
            continue
        key = (a["ticker"], rd)
        if key not in eksisterende:
            hendelser.append({"ticker": a["ticker"], "dato": rd, "type": "rapport"})
            eksisterende.add(key)
            lagt_til += 1

    # 2. Berik hendelser uten URL for passerte/dagens datoer
    today = datetime.date.today().isoformat()
    url_lagt_til = 0

    for h in hendelser:
        if h.get("url"):
            continue
        if h["dato"] > today:
            continue  # rapport ikke publisert ennå

        print(f"  Søker NewsWeb URL: {h['ticker']} {h['dato']} ...", end=" ", flush=True)
        url = _hent_rapport_url(h["ticker"], h["dato"])
        if url:
            h["url"] = url
            url_lagt_til += 1
            print(f"funnet")
        else:
            print("ikke funnet")

        time.sleep(0.3)  # skånsom mot NewsWeb

    hendelser.sort(key=lambda x: (x["dato"], x["ticker"]))

    with open(HENDELSER_F, "w", encoding="utf-8") as f:
        json.dump(
            {"hendelser": hendelser, "sist_oppdatert": today},
            f, ensure_ascii=False, indent=2,
        )

    print(
        f"hendelser.json: {len(hendelser)} totalt, "
        f"{lagt_til} nye datoer, {url_lagt_til} URLer lagt til"
    )


if __name__ == "__main__":
    main()
