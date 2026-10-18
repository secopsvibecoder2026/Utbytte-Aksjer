"""Tester for scripts/klokke.py. Ingen nettverk; GitHub kalles aldri."""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import klokke as k

MANDAG_VINTER = datetime.date(2026, 11, 2)
MANDAG_SOMMER = datetime.date(2026, 6, 1)


def oslo(dato, t, m, s=0):
    return datetime.datetime.combine(dato, datetime.time(t, m, s), k.OSLO)


class TestPlan(unittest.TestCase):
    def test_hverdag(self):
        p = k.plan(MANDAG_VINTER)
        self.assertEqual(sum(1 for _, wf in p if wf == k.PRISJOBB), 34)
        self.assertEqual(sum(1 for _, wf in p if wf == k.DATAJOBB), 4)
        self.assertEqual(p[0], (oslo(MANDAG_VINTER, 8, 41), k.DATAJOBB))
        self.assertEqual(p[-1], (oslo(MANDAG_VINTER, 17, 41), k.DATAJOBB))
        self.assertEqual(p, sorted(p))

    def test_helg_er_tom(self):
        self.assertEqual(k.plan(datetime.date(2026, 10, 17)), [])
        self.assertEqual(k.plan(datetime.date(2026, 10, 18)), [])

    def test_oslotid_baade_sommer_og_vinter(self):
        # Samme klokkeslett i Oslo, ulik UTC: timeplanen i UTC flyttet seg en
        # time med sommertiden, klokka gjør det ikke.
        v = k.plan(MANDAG_VINTER)[0][0]
        s = k.plan(MANDAG_SOMMER)[0][0]
        self.assertEqual((v.hour, v.minute), (s.hour, s.minute))
        self.assertEqual(v.utcoffset(), datetime.timedelta(hours=1))
        self.assertEqual(s.utcoffset(), datetime.timedelta(hours=2))


class TestSkalStartes(unittest.TestCase):
    P = k.plan(MANDAG_VINTER)

    def test_ingenting_for_forste_tidspunkt(self):
        self.assertEqual(k.skal_startes(oslo(MANDAG_VINTER, 7, 30), self.P, {}), [])

    def test_ukjent_siste_kjoring_startes(self):
        self.assertEqual(k.skal_startes(oslo(MANDAG_VINTER, 8, 42), self.P,
                                        {k.DATAJOBB: None}), [k.DATAJOBB])

    def test_startet_etter_tidspunktet_startes_ikke(self):
        # Timeplanen slo til, eller forrige klokke startet den rett før den ga seg.
        sist = {k.PRISJOBB: oslo(MANDAG_VINTER, 9, 7, 30), k.DATAJOBB: oslo(MANDAG_VINTER, 8, 45)}
        self.assertEqual(k.skal_startes(oslo(MANDAG_VINTER, 9, 10), self.P, sist), [])

    def test_startet_for_tidspunktet_startes(self):
        sist = {k.PRISJOBB: oslo(MANDAG_VINTER, 8, 0), k.DATAJOBB: oslo(MANDAG_VINTER, 8, 45)}
        self.assertEqual(k.skal_startes(oslo(MANDAG_VINTER, 9, 10), self.P, sist), [k.PRISJOBB])

    def test_flere_passerte_gir_en_start(self):
        # Klokka kom i gang klokka 13: priser og data startes én gang hver.
        sist = {k.PRISJOBB: oslo(MANDAG_VINTER - datetime.timedelta(days=3), 17, 37),
                k.DATAJOBB: oslo(MANDAG_VINTER - datetime.timedelta(days=3), 17, 41)}
        self.assertEqual(k.skal_startes(oslo(MANDAG_VINTER, 13, 0), self.P, sist),
                         sorted([k.PRISJOBB, k.DATAJOBB]))


class TestNesteOgOverlevering(unittest.TestCase):
    P = k.plan(MANDAG_VINTER)

    def test_neste_tid(self):
        self.assertEqual(k.neste_tid(oslo(MANDAG_VINTER, 9, 7), self.P), oslo(MANDAG_VINTER, 9, 22))
        self.assertIsNone(k.neste_tid(oslo(MANDAG_VINTER, 17, 41), self.P))

    def test_overlevering_for_sekstimersgrensen(self):
        start = oslo(MANDAG_VINTER, 7, 13)
        self.assertFalse(k.ma_overlevere(start, oslo(MANDAG_VINTER, 12, 37)))
        self.assertTrue(k.ma_overlevere(start, oslo(MANDAG_VINTER, 12, 52)))

    def test_en_dag_gaar_med_to_kjoringer(self):
        # Fra første mulige start til siste tidspunkt er det over seks timer,
        # men aldri over to ganger grensen.
        p = self.P
        self.assertLess(p[-1][0] - oslo(MANDAG_VINTER, 7, 13), 2 * k.GRENSE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
