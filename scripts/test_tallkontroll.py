#!/usr/bin/env python3
"""Tester for tallkontroll.py — bare de rene sammenligningene, uten nett."""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tallkontroll as tk  # noqa: E402

I_DAG = datetime.date(2026, 9, 26)


class TestKursgraf(unittest.TestCase):
    # Tallene er DNB slik feilen ble funnet: grafen 141,23 mot omsatt 206,00.
    RAA = [("2021-10-07", 204.0), ("2021-10-08", 206.0), ("2026-09-25", 315.1)]

    def test_justert_graf_flagges(self):
        f = tk.sjekk_kursgraf([{"d": "2021-10-10", "k": 141.23}], self.RAA)
        self.assertEqual(f["sjekk"], "kursgraf_justert")
        self.assertEqual(f["kildedato"], "2021-10-08")  # siste handelsdag før søndag

    def test_ujustert_graf_er_ok(self):
        self.assertIsNone(tk.sjekk_kursgraf([{"d": "2021-10-10", "k": 205.5}], self.RAA))

    def test_uten_data_ingen_pastand(self):
        self.assertIsNone(tk.sjekk_kursgraf([], self.RAA))
        self.assertIsNone(tk.sjekk_kursgraf([{"d": "2020-01-05", "k": 1.0}], self.RAA))


class TestKurs(unittest.TestCase):
    def test_innenfor_toleranse(self):
        self.assertIsNone(tk.sjekk_kurs(315.1, [("2026-09-25", 312.0)]))

    def test_utenfor_toleranse(self):
        self.assertEqual(tk.sjekk_kurs(100.6, [("2026-09-25", 12.3)])["alvor"], "kritisk")


class TestBetalt(unittest.TestCase):
    UTB = [("2025-05-02", 5.0), ("2025-10-01", 3.0), ("2026-05-04", 4.0)]

    def test_sum_bruker_365_dager(self):
        self.assertEqual(tk.sum_siste_12m(self.UTB, I_DAG), (7.0, 2))

    def test_foreldet_betalt_flagges(self):
        f = tk.sjekk_betalt_12m({"utbytte_12m": 9.0}, self.UTB, I_DAG)
        self.assertEqual(f["kilde"], 7.0)

    def test_riktig_betalt_er_ok(self):
        self.assertIsNone(tk.sjekk_betalt_12m({"utbytte_12m": 7.0}, self.UTB, I_DAG))

    def test_manglende_felt_ingen_pastand(self):
        self.assertIsNone(tk.sjekk_betalt_12m({}, self.UTB, I_DAG))

    def test_yield_over_betalt_bare_oppover(self):
        # GOD-formen: vist 14 % mot betalt 3,5 %.
        self.assertIsNotNone(tk.sjekk_yield_mot_betalt({"utbytte_yield": 14.0}, 100, I_DAG, self.UTB))
        # Under betalt er ikke et varsel (engangsutbytte i vinduet).
        self.assertIsNone(tk.sjekk_yield_mot_betalt({"utbytte_yield": 3.0}, 100, I_DAG, self.UTB))


class TestFrekvens(unittest.TestCase):
    # SATS-formen: tre utbetalinger i ett 12-månedersvindu, men ~180 dager mellom.
    HALVAAR = [("2025-03-04", 1), ("2025-09-01", 1), ("2026-03-04", 1), ("2026-08-24", 1)]

    def test_intervall_avslorer_feil_etikett(self):
        f = tk.sjekk_frekvens({"frekvens": "Kvartalsvis"}, self.HALVAAR)
        self.assertEqual(f["vist"], "Kvartalsvis")

    def test_riktig_etikett(self):
        self.assertIsNone(tk.sjekk_frekvens({"frekvens": "Halvårlig"}, self.HALVAAR))

    def test_for_kort_serie(self):
        self.assertIsNone(tk.sjekk_frekvens({"frekvens": "Årlig"}, self.HALVAAR[:2]))


class TestExDato(unittest.TestCase):
    def test_new_york_dato_flagges(self):
        # EQNR: vi viste New York-datoen, Oslo Børs sier 13. november.
        f = tk.sjekk_ex_dato({"ex_dato": "2026-11-16"}, {"ex_dato": "2026-11-13"})
        self.assertEqual(f["kilde"], "2026-11-13")

    def test_uten_melding_ingen_pastand(self):
        self.assertIsNone(tk.sjekk_ex_dato({"ex_dato": "2026-11-16"}, None))


if __name__ == "__main__":
    unittest.main(verbosity=1)
