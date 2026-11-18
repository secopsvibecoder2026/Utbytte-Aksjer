#!/usr/bin/env python3
"""Tester for sjekk_kursferskhet.py: stdlib unittest, ingen nett."""

import datetime
import os
import sys
import unittest
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sjekk_kursferskhet import vurder, gjeldende_borsdag, nyeste_kursdag  # noqa: E402

OSLO = ZoneInfo("Europe/Oslo")


def kl(dato, tid):
    a, m, d = map(int, dato.split("-"))
    t, mi = map(int, tid.split(":"))
    return datetime.datetime(a, m, d, t, mi, tzinfo=OSLO)


def priser(*datoer):
    return {"aksjer": {f"T{i}": {"pris": 1, "dato": d} for i, d in enumerate(datoer)}}


class TestKursferskhet(unittest.TestCase):
    def test_gjeldende_borsdag(self):
        self.assertEqual(str(gjeldende_borsdag(kl("2026-11-18", "08:41"))), "2026-11-17")
        self.assertEqual(str(gjeldende_borsdag(kl("2026-11-18", "11:41"))), "2026-11-18")
        self.assertEqual(str(gjeldende_borsdag(kl("2026-11-23", "08:41"))), "2026-11-20")
        self.assertEqual(str(gjeldende_borsdag(kl("2026-12-28", "08:41"))), "2026-12-23")

    def test_nyeste_dato_teller(self):
        self.assertEqual(str(nyeste_kursdag(priser("2026-11-16", "2026-11-17", "x"))), "2026-11-17")
        self.assertIsNone(nyeste_kursdag({}))

    def test_morgenkjoringen_med_gaarsdagens_kurser_er_ok(self):
        self.assertFalse(vurder(priser("2026-11-17"), kl("2026-11-18", "08:41"))[0])

    def test_dagens_kurser_ventes_etter_halv_elleve(self):
        self.assertFalse(vurder(priser("2026-11-17"), kl("2026-11-18", "10:00"))[0])
        self.assertTrue(vurder(priser("2026-11-17"), kl("2026-11-18", "11:41"))[0])
        self.assertFalse(vurder(priser("2026-11-18"), kl("2026-11-18", "11:41"))[0])

    def test_en_hel_borsdag_uten_kurser_feiler(self):
        # Onsdag morgen med mandagens kurser: hele tirsdagen gikk uten oppdatering.
        self.assertTrue(vurder(priser("2026-11-16"), kl("2026-11-18", "08:41"))[0])
        self.assertTrue(vurder(priser("2026-11-17"), kl("2026-11-18", "20:00"))[0])

    def test_to_borsdager_bak_feiler_alltid(self):
        self.assertTrue(vurder(priser("2026-11-16"), kl("2026-11-18", "08:41"))[0])

    def test_helg_og_fridager_feiler_ikke(self):
        self.assertFalse(vurder(priser("2026-11-20"), kl("2026-11-23", "08:41"))[0])
        self.assertFalse(vurder(priser("2026-12-23"), kl("2026-12-28", "08:41"))[0])
        self.assertFalse(vurder(priser("2026-12-23"), kl("2026-12-25", "14:00"))[0])

    def test_tom_fil_feiler(self):
        self.assertTrue(vurder({}, kl("2026-11-18", "11:41"))[0])


if __name__ == "__main__":
    unittest.main()
