#!/usr/bin/env python3
"""Tester for slaa_sammen() i fetch_priser.py — uten nett og uten yfinance.

Tallene er HUNT fra kvelden 05.10.2026, da Yahoo hadde mistet mandagsraden og
23:02-kjøringen skrev fredagens 17,86 over mandagens 19,10.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_priser as fp


def rad(pris, forrige, dato, forrige_dato):
    krs, pct = fp._endring(pris, forrige)
    return {"pris": pris, "forrige_kurs": forrige, "endring_krs": krs,
            "endring_pct": pct, "dato": dato, "forrige_dato": forrige_dato}


class TestSlaaSammen(unittest.TestCase):
    def test_eldre_handelsdag_skriver_ikke_over(self):
        forrige = {"HUNT": rad(19.10, 17.86, "2026-10-05", "2026-10-02")}
        nye = {"HUNT": rad(17.86, 17.70, "2026-10-02", "2026-10-01")}
        ut, beholdt = fp.slaa_sammen(nye, forrige)
        self.assertEqual(ut["HUNT"]["pris"], 19.10)
        self.assertEqual(beholdt, ["HUNT"])

    def test_manglende_dag_i_serien_hentes_fra_filen(self):
        # Tirsdag: serien går fra fredag rett til tirsdag.
        forrige = {"HUNT": rad(19.10, 17.86, "2026-10-05", "2026-10-02")}
        nye = {"HUNT": rad(19.28, 17.86, "2026-10-06", "2026-10-02")}
        ut, _ = fp.slaa_sammen(nye, forrige)
        self.assertEqual(ut["HUNT"]["forrige_kurs"], 19.10)
        self.assertEqual(ut["HUNT"]["forrige_dato"], "2026-10-05")
        self.assertAlmostEqual(ut["HUNT"]["endring_pct"], (19.28 - 19.10) / 19.10 * 100, places=3)

    def test_mandagen_overlever_kvarterskjoringene(self):
        # Andre kjøring tirsdag: filen har allerede tirsdag, med mandag som
        # forrige kurs. Serien mangler fortsatt mandag.
        forrige = {"HUNT": rad(19.28, 19.10, "2026-10-06", "2026-10-05")}
        nye = {"HUNT": rad(19.40, 17.86, "2026-10-06", "2026-10-02")}
        ut, _ = fp.slaa_sammen(nye, forrige)
        self.assertEqual(ut["HUNT"]["forrige_kurs"], 19.10)

    def test_vanlig_dag_bruker_serien(self):
        # Lik dato: serien vinner, så en utbyttejustert forrige kurs på
        # ex-dagen ikke byttes mot filens ujusterte.
        forrige = {"DNB": rad(310.0, 305.0, "2026-10-06", "2026-10-05")}
        nye = {"DNB": rad(311.0, 303.0, "2026-10-06", "2026-10-05")}
        ut, beholdt = fp.slaa_sammen(nye, forrige)
        self.assertEqual(ut["DNB"]["forrige_kurs"], 303.0)
        self.assertEqual(beholdt, [])

    def test_fil_uten_dato_overstyres_som_for(self):
        forrige = {"HUNT": {"pris": 19.10, "forrige_kurs": 17.86}}
        nye = {"HUNT": rad(17.86, 17.70, "2026-10-02", "2026-10-01")}
        ut, beholdt = fp.slaa_sammen(nye, forrige)
        self.assertEqual(ut["HUNT"]["pris"], 17.86)
        self.assertEqual(beholdt, [])

    def test_ny_ticker_uten_forrige(self):
        ut, _ = fp.slaa_sammen({"X": rad(10.0, 9.0, "2026-10-06", "2026-10-05")}, {})
        self.assertEqual(ut["X"]["forrige_kurs"], 9.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
