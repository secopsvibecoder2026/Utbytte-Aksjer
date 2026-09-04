#!/usr/bin/env python3
"""Tester for fetch_stocks.py.

Kjøres med: python scripts/test_fetch_stocks.py

Testene som krever pandas hoppes over hvis pakken ikke finnes, slik at
suiten fortsatt kan kjøres uten tredjepartspakker.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_stocks as fs

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


@unittest.skipIf(pd is None, "pandas er ikke installert")
class TestDatoindeksert(unittest.TestCase):
    """Regresjonstest for feilen som tok ned ni tickere i 16 dager.

    yfinance ga tilbake en ikke-tom utbytteserie med RangeIndex. Seks steder
    i fetch_stocks.py leser `dividends.index.tz` eller sammenligner indeksen
    med en dato; alle kastet «'RangeIndex' object has no attribute 'tz'».
    Unntaket boblet ut av hent_aksje(), tickeren feilet, og pipelinen serverte
    forrige kjørings tall videre uten at noe var synlig på siden.
    """

    def test_rangeindex_gir_tom_serie(self):
        serie = pd.Series([1.0, 2.0, 3.0])
        self.assertNotIsInstance(serie.index, pd.DatetimeIndex)
        self.assertTrue(fs._datoindeksert(serie).empty)

    def test_tom_serie_har_datetimeindex(self):
        """Den tomme serien må også tåle `.index.tz`.

        Første forsøk på fiksen returnerte `pd.Series(dtype="float64")`, som får
        en RangeIndex. hent_aksje() leser `dividends.index.tz` ett sted som
        ikke ligger bak en `.empty`-sjekk, så de samme sju tickerne feilet
        videre i produksjon. Testene over fanget det ikke, fordi både
        beregn_utbytte_vekst() og hent_historiske_utbytter() returnerer tidlig
        på tom serie.
        """
        for inn in (None, pd.Series([1.0, 2.0]), pd.Series(dtype="float64")):
            ut = fs._datoindeksert(inn)
            self.assertIsInstance(ut.index, pd.DatetimeIndex)
            self.assertIsNone(ut.index.tz)          # skal ikke kaste
            self.assertEqual(len(ut[ut.index >= pd.Timestamp("2020-01-01")]), 0)

    def test_datetimeindex_beholdes(self):
        serie = pd.Series([1.0, 2.0], index=pd.to_datetime(["2025-03-01", "2026-03-01"]))
        self.assertEqual(len(fs._datoindeksert(serie)), 2)

    def test_none_gir_tom_serie(self):
        self.assertTrue(fs._datoindeksert(None).empty)

    def test_beregn_utbytte_vekst_kaster_ikke(self):
        # Selve feilen: uten fiksen kaster dette AttributeError.
        self.assertEqual(fs.beregn_utbytte_vekst(fs._datoindeksert(pd.Series([1.0, 2.0]))), 0.0)

    def test_hent_historiske_utbytter_kaster_ikke(self):
        historikk, snitt = fs.hent_historiske_utbytter(
            fs._datoindeksert(pd.Series([1.0, 2.0])), pd.DataFrame(), current_price=10.0
        )
        self.assertEqual(historikk, [])


@unittest.skipIf(pd is None, "pandas er ikke installert")
class TestTomResponsFeiler(unittest.TestCase):
    """En tom Yahoo-respons skal registreres som feil, ikke som «ok».

    Da RangeIndex-krasjen ble fikset sluttet sju tickere å kaste, men Yahoo ga
    fortsatt ingenting. Resultatet ble lagret som vellykket med kurs 0, yield 0
    og tom historikk — Golden Ocean sto som «Uregelmessig utbytte» uten
    direkteavkastning. Fordi ok=True var satt, kunne verken mulig_avnotering
    eller navneendring slå ut, så ingenting varslet om det.
    """

    class _StubTicker:
        """Minimal erstatning for yf.Ticker med en tom respons."""

        def __init__(self, info):
            self.info = info
            self.dividends = pd.Series(dtype="float64", index=pd.DatetimeIndex([]))
            self.calendar = {}

        def history(self, period=None):
            return pd.DataFrame()

    def _kjor(self, info):
        stub = self._StubTicker(info)
        ekte_yf = fs.yf
        # Newsweb-oppslaget stubbes også, ellers går testen på nettet og bruker
        # fem sekunder på å time ut i CI.
        ekte_newsweb = fs.hent_newsweb_rapport_dato
        fs.yf = type("Yf", (), {"Ticker": staticmethod(lambda t: stub)})
        fs.hent_newsweb_rapport_dato = lambda t: None
        fs.HENTEDIAGNOSTIKK.pop("TEST", None)
        try:
            resultat = fs.hent_aksje({
                "ticker": "TEST", "ticker_yf": "TEST.OL",
                "navn": "Testselskap ASA", "sektor": "Finans", "bors": "Oslo Børs",
            })
        finally:
            fs.yf = ekte_yf
            fs.hent_newsweb_rapport_dato = ekte_newsweb
        return resultat, fs.HENTEDIAGNOSTIKK.get("TEST", {})

    def test_verken_navn_eller_kurs_gir_feil(self):
        resultat, diag = self._kjor({})
        self.assertIsNone(resultat)
        self.assertFalse(diag.get("ok"))
        self.assertIn("tom respons", diag.get("feilmelding", ""))

    def test_kurs_uten_navn_slipper_gjennom(self):
        # Navnet kan mangle uten at dataene er ubrukelige — kursen er nok.
        resultat, diag = self._kjor({"regularMarketPrice": 148.6})
        self.assertIsNotNone(resultat)
        self.assertTrue(diag.get("ok"))


class TestFrekvensLabel(unittest.TestCase):
    """Terskelen som gjorde SATS kvartalsvis og 2020 Bulkers kvartalsvis.

    Grensene er dokumentert her fordi de er årsaken til to reelle feil: en
    halvårlig betaler får «Kvartalsvis» så snart 12-månedersvinduet fanger en
    tredje utbetaling, og en månedlig betaler med brudd i serien faller ned i
    samme bøtte. Derfor finnes overstyringen i tickers.json.
    """

    def test_grenser(self):
        self.assertEqual(fs.frekvens_label(12), "Månedlig")
        self.assertEqual(fs.frekvens_label(10), "Månedlig")
        self.assertEqual(fs.frekvens_label(9), "Kvartalsvis")
        self.assertEqual(fs.frekvens_label(3), "Kvartalsvis")
        self.assertEqual(fs.frekvens_label(2), "Halvårlig")
        self.assertEqual(fs.frekvens_label(1), "Årlig")
        self.assertEqual(fs.frekvens_label(0), "Uregelmessig")

    def test_overstyring_leses_fra_tickers(self):
        # 2020 Bulkers og SATS er begge overstyrt manuelt.
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("2020"), "Månedlig")
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("SATS"), "Halvårlig")


if __name__ == "__main__":
    unittest.main(verbosity=2)
