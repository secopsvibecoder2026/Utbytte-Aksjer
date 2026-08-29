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
