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

from oppdater_hendelser import rydd_framtidige, velg_rapport_melding, MAKS_URL_FORSOK


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


def _m(mid, dato, tittel):
    return {"messageId": mid, "publishedTime": f"{dato}T06:00:00.000Z", "title": tittel}


class TestVelgRapportMelding(unittest.TestCase):
    """Titlene er ekte. Før 16.10.2026 traff ingen av de tre første."""

    def test_kvartalstitler_uten_q(self):
        for tittel in ["Second quarter 2026 results",
                       "BW Offshore: Second quarter and first half results 2026",
                       "TOMRA: 25% revenue growth on strong Poland roll-out in the second quarter",
                       "Höegh Autoliners ASA: Second quarter results and distribution of dividends",
                       "Delårsregnskap 1. kvartal 2026",
                       "Yara reports increased margins and strong volumes in 1Q",
                       "Borregaard ASA: EBITDA1 of NOK 428 million in the 1st quarter"]:
            self.assertEqual(velg_rapport_melding([_m(1, "2026-07-15", tittel)], "2026-07-15"), 1, tittel)

    def test_utbyttemeldingen_samme_morgen_er_ikke_rapporten(self):
        meldinger = [_m(3, "2026-07-15", "Aker BP: Key information related to cash dividend"),
                     _m(2, "2026-07-15", "Second quarter 2026 results"),
                     _m(1, "2026-07-15", "Financial calendar")]
        self.assertEqual(velg_rapport_melding(meldinger, "2026-07-15"), 2)
        self.assertIsNone(velg_rapport_melding(
            [_m(4, "2026-10-15", "WEST: Ex-dividend NOK 1.39 today (Q3 2026)")], "2026-10-15"))
        for tittel in ["Panoro Energy Announces Results of the 2026 Annual General Meeting",
                       "Reach Subsea ASA - Invitation to presentation of the first quarter results"]:
            self.assertIsNone(velg_rapport_melding([_m(5, "2026-05-21", tittel)], "2026-05-21"), tittel)

    def test_naermeste_dato_vinner_og_vinduet_er_to_dager(self):
        meldinger = [_m(2, "2026-08-21", "Q2 2026 presentation"),
                     _m(1, "2026-08-20", "Second quarter results")]
        self.assertEqual(velg_rapport_melding(meldinger, "2026-08-20"), 1)
        self.assertIsNone(velg_rapport_melding(meldinger, "2026-08-24"))

    def test_tre_forsok(self):
        self.assertEqual(MAKS_URL_FORSOK, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
