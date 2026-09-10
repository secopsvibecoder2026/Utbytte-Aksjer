#!/usr/bin/env python3
"""Tester for oppdater_hendelser.py.

Kjøres med: python scripts/test_oppdater_hendelser.py

Ingen nettverk og ingen tredjepartspakker — rydd_framtidige() er ren
listebehandling, og NewsWeb-oppslagene røres ikke her.
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oppdater_hendelser import rydd_framtidige


class TestRyddFramtidige(unittest.TestCase):
    """Framtidige datoer selskapet ikke lenger står oppført med skal ut.

    hendelser.json akkumulerte (ticker, dato)-par og slettet aldri noe. Hver
    gang et selskap flyttet rapportdatoen sin ble den gamle stående som en
    framtidig hendelse, og appens kalender viste dem alle. Ved oppdagelsen
    05.09.2026 hadde 12 tickere mellom 8 og 12 «kommende» datoer hver — Entra
    sto med tolv rapporter på tre måneder — og de utgjorde 96 av 236
    framtidige hendelser, 41 %.
    """

    def setUp(self):
        self.i_dag = datetime.date(2026, 9, 7)
        self.aksjer = [
            {"ticker": "ENTR", "rapport_dato": "2026-11-19"},
            {"ticker": "DNB",  "rapport_dato": "2026-10-21"},
            {"ticker": "TOM",  "rapport_dato": None},        # henting feilet
        ]

    def test_beholder_gjeldende_dato(self):
        h = [{"ticker": "DNB", "dato": "2026-10-21", "type": "rapport"}]
        beholdt, fjernet = rydd_framtidige(h, self.aksjer, self.i_dag)
        self.assertEqual(len(beholdt), 1)
        self.assertEqual(fjernet, [])

    def test_fjerner_utdaterte_gjetninger(self):
        # Entras egne tolv «kommende» datoer, forkortet.
        h = [{"ticker": "ENTR", "dato": d, "type": "rapport"} for d in
             ("2026-09-23", "2026-09-30", "2026-10-15", "2026-10-21",
              "2026-11-05", "2026-11-19")]
        beholdt, fjernet = rydd_framtidige(h, self.aksjer, self.i_dag)
        self.assertEqual([b["dato"] for b in beholdt], ["2026-11-19"])
        self.assertEqual(len(fjernet), 5)

    def test_passerte_rores_aldri(self):
        # Historikk, og de bærer NewsWeb-URLene. Appen viser dem ikke uansett.
        h = [
            {"ticker": "ENTR", "dato": "2026-05-08", "type": "rapport"},
            {"ticker": "ENTR", "dato": "2026-08-31", "type": "rapport", "url": "x"},
            {"ticker": "ENTR", "dato": "2026-09-07", "type": "rapport"},   # i dag
        ]
        beholdt, fjernet = rydd_framtidige(h, self.aksjer, self.i_dag)
        self.assertEqual(len(beholdt), 3)
        self.assertEqual(fjernet, [])

    def test_beriket_hendelse_slettes_ikke(self):
        # En framtidig dato med URL skal aldri kastes, uansett årsak.
        h = [{"ticker": "ENTR", "dato": "2026-12-01", "type": "rapport", "url": "x"}]
        beholdt, fjernet = rydd_framtidige(h, self.aksjer, self.i_dag)
        self.assertEqual(len(beholdt), 1)

    def test_uten_rapport_dato_faller_framtidige_ut(self):
        # Feiler hentingen, er ingen dato riktigere enn en gammel gjetning.
        # Neste vellykkede kjøring legger den inn igjen.
        h = [{"ticker": "TOM", "dato": "2026-10-01", "type": "rapport"},
             {"ticker": "TOM", "dato": "2026-06-01", "type": "rapport"}]
        beholdt, fjernet = rydd_framtidige(h, self.aksjer, self.i_dag)
        self.assertEqual([b["dato"] for b in beholdt], ["2026-06-01"])
        self.assertEqual(len(fjernet), 1)

    def test_ukjent_ticker_mister_framtidige(self):
        h = [{"ticker": "BORTE", "dato": "2026-10-01", "type": "rapport"}]
        beholdt, fjernet = rydd_framtidige(h, self.aksjer, self.i_dag)
        self.assertEqual(beholdt, [])
        self.assertEqual(len(fjernet), 1)

    def test_idempotent(self):
        h = [{"ticker": "ENTR", "dato": d, "type": "rapport"} for d in
             ("2026-09-23", "2026-11-19")]
        forste, _ = rydd_framtidige(h, self.aksjer, self.i_dag)
        andre, fjernet = rydd_framtidige(forste, self.aksjer, self.i_dag)
        self.assertEqual(forste, andre)
        self.assertEqual(fjernet, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
