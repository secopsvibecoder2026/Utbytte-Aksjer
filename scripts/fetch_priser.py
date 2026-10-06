#!/usr/bin/env python3
"""
fetch_priser.py — Lettvekts kursoppdatering
Henter kun nåværende kurs + forrige stenging for alle tickers.
Kjøres hvert 15. minutt i børstiden. Skriver til data/priser.json.

**En kjøring skal aldri skrive en eldre kurs over en nyere.** Yahoo mister av
og til den siste dagsraden om kvelden. Mandag 28.09 og mandag 05.10.2026 kom
17:00-kjøringen (forsinket av GitHub til 22–23) tilbake med fredagens
sluttkurser for 140 av 155 aksjer, og appen viste fredagens kurs og
fredagens endring resten av kvelden og natten — HUNT 17,86 i stedet for
19,10, VEND 208,40 i stedet for 202,20. Hver oppføring bærer derfor datoen
for handelsdagen den gjelder (`dato`), og slaa_sammen() beholder den forrige
når Yahoo gir en eldre dag.

Den samme hullet gir neste dag feil «forrige kurs»: serien går rett fra
fredag til tirsdag, så tirsdagens endring ble regnet mot fredag. Har forrige
fil en kurs fra en dag mellom de to, brukes den.
"""
import json
import sys
import datetime
from pathlib import Path

ROOT       = Path(__file__).parent.parent
TICKERS_F  = ROOT / "data" / "tickers.json"
PRISER_F   = ROOT / "data" / "priser.json"


def les_tickers() -> list[dict]:
    with open(TICKERS_F, encoding="utf-8") as f:
        return json.load(f)


def les_forrige(sti=PRISER_F) -> dict:
    """Oppføringene fra forrige kjøring, eller {} om filen mangler."""
    try:
        with open(sti, encoding="utf-8") as f:
            return json.load(f).get("aksjer", {}) or {}
    except (OSError, ValueError):
        return {}


def _endring(pris, forrige_kurs):
    endring_krs = round(pris - forrige_kurs, 4)
    endring_pct = round((endring_krs / forrige_kurs) * 100, 4) if forrige_kurs else 0.0
    return endring_krs, endring_pct


def hent_priser(tickers: list[dict]) -> dict:
    # Importert her, ikke øverst: testene av slaa_sammen() skal kunne kjøre
    # uten yfinance installert, som i CI.
    import yfinance as yf

    yf_symboler = [t["ticker_yf"] for t in tickers]
    ticker_map  = {t["ticker_yf"]: t["ticker"] for t in tickers}

    print(f"Henter kurs for {len(yf_symboler)} aksjer …")
    try:
        # Én batch-kall for alle tickers — 2 dager for å få forrige stenging
        data = yf.download(
            yf_symboler,
            period="5d",
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as e:
        print(f"FEIL ved nedlasting: {e}", file=sys.stderr)
        return {}

    if data.empty:
        print("Ingen data returnert.", file=sys.stderr)
        return {}

    close = data["Close"]
    resultat = {}

    for yf_sym in yf_symboler:
        ticker = ticker_map[yf_sym]
        try:
            col = close[yf_sym] if yf_sym in close.columns else close
            # Fjern NaN-rader
            serie = col.dropna()
            if len(serie) < 1:
                continue

            pris         = round(float(serie.iloc[-1]), 4)
            forrige_kurs = round(float(serie.iloc[-2]), 4) if len(serie) >= 2 else pris
            endring_krs, endring_pct = _endring(pris, forrige_kurs)

            resultat[ticker] = {
                "pris":         pris,
                "forrige_kurs": forrige_kurs,
                "endring_krs":  endring_krs,
                "endring_pct":  endring_pct,
                "dato":         serie.index[-1].date().isoformat(),
                "forrige_dato": serie.index[-2].date().isoformat() if len(serie) >= 2 else None,
            }
        except Exception as e:
            print(f"  {ticker}: {e}", file=sys.stderr)

    return resultat


def slaa_sammen(nye: dict, forrige: dict) -> tuple[dict, list[str]]:
    """Nye oppføringer, rettet mot forrige kjørings fil.

    * Er Yahoos siste dag *eldre* enn den vi allerede har, beholdes den vi har.
    * «Forrige kurs» er den nyeste kjente sluttkursen før dagen vi viser —
      fra Yahoos serie, fra forrige fils kurs, eller fra forrige fils egen
      «forrige kurs». Mangler serien en dag, har filen den. Den siste kilden
      trengs fordi filen skrives hvert kvarter: etter første kjøring på
      tirsdag er mandagen bare å finne som tirsdagsoppføringens forrige kurs.

    Oppføringer uten `dato` (filer skrevet før feltet fantes) kan ikke
    sammenlignes og overstyres som før. Returnerer (resultat, beholdte).
    """
    ut, beholdt = {}, []
    for ticker, ny in nye.items():
        gml = forrige.get(ticker) or {}
        gml_dato, ny_dato = gml.get("dato"), ny.get("dato")
        if gml_dato and ny_dato and ny_dato < gml_dato:
            ut[ticker] = gml
            beholdt.append(ticker)
            continue
        if ny_dato:
            # (dato, prioritet, kurs). Ved lik dato vinner serien: den er
            # justert på samme måte som dagens kurs.
            kandidater = []
            if ny.get("forrige_dato"):
                kandidater.append((ny["forrige_dato"], 1, ny["forrige_kurs"]))
            if gml_dato and gml.get("pris") and gml_dato < ny_dato:
                kandidater.append((gml_dato, 0, gml["pris"]))
            if gml_dato == ny_dato and gml.get("forrige_dato") and gml.get("forrige_kurs"):
                kandidater.append((gml["forrige_dato"], 0, gml["forrige_kurs"]))
            kandidater = [k for k in kandidater if k[0] < ny_dato]
            if kandidater:
                dato, _, kurs = max(kandidater)
                ny["forrige_dato"], ny["forrige_kurs"] = dato, kurs
                ny["endring_krs"], ny["endring_pct"] = _endring(ny["pris"], kurs)
        ut[ticker] = ny
    return ut, beholdt


def main():
    tickers  = les_tickers()
    priser, beholdt = slaa_sammen(hent_priser(tickers), les_forrige())
    ts       = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    if beholdt:
        print(f"  Yahoo ga en eldre handelsdag for {len(beholdt)} aksjer — "
              f"beholdt forrige kurs: {', '.join(sorted(beholdt)[:10])}"
              + (" …" if len(beholdt) > 10 else ""))

    ok   = sum(1 for v in priser.values() if v["pris"] > 0)
    feil = len(tickers) - ok
    print(f"  {ok} OK, {feil} mangler")

    output = {"oppdatert": ts, "aksjer": priser}
    PRISER_F.parent.mkdir(exist_ok=True)
    with open(PRISER_F, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    print(f"Skrevet til {PRISER_F}  ({len(priser)} tickers, {ts})")


if __name__ == "__main__":
    main()
