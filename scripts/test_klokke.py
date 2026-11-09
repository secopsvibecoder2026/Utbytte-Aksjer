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

    def test_en_dag_gaar_med_to_kjoringer(self):
        # Fra første mulige start til siste tidspunkt er det over seks timer,
        # men aldri over to ganger grensen.
        p = self.P
        self.assertLess(p[-1][0] - oslo(MANDAG_VINTER, 7, 13), 2 * k.GRENSE)

    def test_neste_i_planen_ser_forbi_midnatt_og_helg(self):
        tirsdag = MANDAG_VINTER + datetime.timedelta(days=1)
        self.assertEqual(k.neste_i_planen(oslo(MANDAG_VINTER, 17, 41)), oslo(tirsdag, 8, 41))
        fredag = MANDAG_VINTER + datetime.timedelta(days=4)
        self.assertEqual(k.neste_i_planen(oslo(fredag, 18, 0)),
                         oslo(MANDAG_VINTER + datetime.timedelta(days=7), 8, 41))

    def test_sekunder_er_faktisk_tid_over_sommertidsskiftet(self):
        # Natt til 25. oktober 2026 går klokka en time tilbake: ti timer på
        # klokka er elleve timer i virkeligheten.
        fra = oslo(datetime.date(2026, 10, 24), 23, 0)
        til = oslo(datetime.date(2026, 10, 25), 9, 0)
        self.assertEqual(til - fra, datetime.timedelta(hours=10))
        self.assertEqual(k.sekunder(fra, til), 11 * 3600)


TIRSDAG = MANDAG_VINTER + datetime.timedelta(days=1)
FREDAG = MANDAG_VINTER + datetime.timedelta(days=4)
SONDAG = MANDAG_VINTER + datetime.timedelta(days=6)


class TestNesteSteg(unittest.TestCase):
    def steg(self, start, naa=None):
        naa = naa or start
        return k.neste_steg(naa, start + k.GRENSE, k.neste_i_planen(naa))

    def test_natt_til_3_november_venter_for_den_overleverer(self):
        # Kjøringen startet 00.12 og neste tidspunkt er 08.41. Før overleverte
        # den med en gang, til en ny kjøring som gjorde det samme.
        start = oslo(TIRSDAG, 0, 12)
        self.assertEqual(self.steg(start), (k.OVERLEVER, oslo(TIRSDAG, 5, 42)))

    def test_venter_naar_neste_tidspunkt_naas_for_fristen(self):
        start = oslo(TIRSDAG, 5, 42)
        self.assertEqual(self.steg(start), (k.VENT, oslo(TIRSDAG, 8, 41)))

    def test_midt_paa_dagen_overleveres_det_ved_fristen(self):
        start = oslo(TIRSDAG, 7, 13)
        self.assertEqual(self.steg(start, oslo(TIRSDAG, 12, 37, 5)),
                         (k.OVERLEVER, oslo(TIRSDAG, 12, 43)))

    def test_hverdagskveld_holder_kjeden_til_neste_morgen(self):
        start = oslo(TIRSDAG, 16, 42)
        self.assertEqual(self.steg(start, oslo(TIRSDAG, 17, 41, 5)),
                         (k.OVERLEVER, oslo(TIRSDAG, 22, 12)))

    def test_fredag_kveld_gir_seg(self):
        self.assertEqual(self.steg(oslo(FREDAG, 17, 0), oslo(FREDAG, 17, 41, 5)),
                         (k.FERDIG, None))
        self.assertEqual(self.steg(oslo(FREDAG + datetime.timedelta(days=1), 12, 0)),
                         (k.FERDIG, None))

    def test_sondag_kveld_venter_til_mandag(self):
        start = oslo(SONDAG, 20, 0)
        self.assertEqual(self.steg(start), (k.OVERLEVER, oslo(SONDAG + datetime.timedelta(days=1), 1, 30)))

    def test_ny_kjoring_kan_ikke_overlevere(self):
        start = oslo(TIRSDAG, 0, 12)
        self.assertFalse(k.kan_overlevere(start, start + datetime.timedelta(seconds=10)))
        self.assertFalse(k.kan_overlevere(start, start + datetime.timedelta(minutes=29)))
        self.assertTrue(k.kan_overlevere(start, start + k.GRENSE))


class TestKjede(unittest.TestCase):
    """Kjører klokka med liksomtid: ingen venting, GitHub kalles aldri."""

    def simuler(self, start, slutt):
        tid = [start]
        startet = []
        sist = {}

        def sov(s):
            tid[0] = tid[0] + datetime.timedelta(seconds=s)

        def start_(repo, wf):
            startet.append((tid[0], wf))
            sist[wf] = tid[0]
            return True

        orig = k.sist_opprettet, k.start
        k.sist_opprettet = lambda repo, wf: sist.get(wf)
        k.start = start_
        klokker, resultat = 0, []
        try:
            while tid[0] < slutt and klokker < 200:
                klokker += 1
                resultat.append(k.kjor("x/y", naa_fn=lambda: tid[0], sov=sov))
                if not startet or startet[-1] != (tid[0], k.KLOKKE):
                    break   # kjeden ga seg uten å starte en ny klokke
        finally:
            k.sist_opprettet, k.start = orig
        return klokker, startet, resultat, tid[0]

    def test_natt_til_3_november_gir_ingen_lokke(self):
        # 2026-11-03: rundt tusen kjøringer mellom 00.12 og 03.11.
        klokker, startet, _, _ = self.simuler(oslo(TIRSDAG, 0, 12), oslo(TIRSDAG, 3, 11))
        # Én kjøring, som venter til 05.42 og starter én ny klokke.
        self.assertEqual(klokker, 1)
        self.assertEqual(startet, [(oslo(TIRSDAG, 5, 42), k.KLOKKE)])

    def test_kjeden_gaar_uka_ut_og_starter_hvert_tidspunkt_en_gang(self):
        klokker, startet, resultat, slutt = self.simuler(
            oslo(TIRSDAG, 0, 12), oslo(FREDAG + datetime.timedelta(days=2), 0, 0))
        self.assertTrue(all(resultat))
        # Fire børsdager med 34 priskjøringer og 4 datakjøringer hver.
        self.assertEqual(sum(1 for _, wf in startet if wf == k.PRISJOBB), 4 * 34)
        self.assertEqual(sum(1 for _, wf in startet if wf == k.DATAJOBB), 4 * 4)
        # Ingen jobb startet mer enn noen sekunder etter tidspunktet i planen.
        planlagt = sorted(t for d in range(4) for t, _ in k.plan(TIRSDAG + datetime.timedelta(days=d)))
        faktisk = sorted(t for t, wf in startet if wf != k.KLOKKE)
        for p, f in zip(planlagt, faktisk):
            self.assertLessEqual((f - p).total_seconds(), 10, (p, f))
        # Én klokke per 5,5 time, og kjeden gir seg fredag etter siste tidspunkt.
        self.assertLess(klokker, 25)
        self.assertEqual(slutt.date(), FREDAG)
        self.assertGreaterEqual((slutt.hour, slutt.minute), (17, 41))
        # Ingen klokke ble startet av en kjøring som hadde levd kortere enn GRENSE.
        klokkestarter = [t for t, wf in startet if wf == k.KLOKKE]
        forrige = oslo(TIRSDAG, 0, 12)
        for t in klokkestarter:
            self.assertGreaterEqual(t - forrige, k.GRENSE)
            forrige = t

    def test_sondag_kveld_starter_mandagen(self):
        mandag = SONDAG + datetime.timedelta(days=1)
        _, startet, _, _ = self.simuler(oslo(SONDAG, 20, 0), oslo(mandag, 9, 10))
        jobber = [(t, wf) for t, wf in startet if wf != k.KLOKKE]
        self.assertEqual(jobber[0][1], k.DATAJOBB)
        self.assertEqual((jobber[0][0].hour, jobber[0][0].minute), (8, 41))

    def test_lordag_gir_seg_med_en_gang(self):
        lordag = FREDAG + datetime.timedelta(days=1)
        klokker, startet, resultat, _ = self.simuler(oslo(lordag, 10, 0), oslo(lordag, 23, 0))
        self.assertEqual((klokker, startet, resultat), (1, [], [True]))

    def test_feilet_overlevering_gir_rod_kjoring(self):
        tid = [oslo(TIRSDAG, 0, 12)]
        orig = k.sist_opprettet, k.start
        k.sist_opprettet = lambda repo, wf: None
        k.start = lambda repo, wf: False
        try:
            ok = k.kjor("x/y", naa_fn=lambda: tid[0],
                        sov=lambda s: tid.__setitem__(0, tid[0] + datetime.timedelta(seconds=s)))
        finally:
            k.sist_opprettet, k.start = orig
        self.assertFalse(ok)


class TestVekk(unittest.TestCase):
    """--vekk starter klokka bare når ingen går. GitHub kalles aldri."""

    class _Svar:
        def __init__(self, kode, ut):
            self.returncode, self.stdout, self.stderr = kode, ut, "feil"

    def _med(self, svar, fn):
        startet = []
        orig = k._gh, k.start
        k._gh = lambda *a: svar
        k.start = lambda repo, wf: startet.append(wf) or True
        try:
            return fn(), startet
        finally:
            k._gh, k.start = orig

    def test_gaar_allerede(self):
        svar = self._Svar(0, '{"workflow_runs": [{"status": "completed"}, {"status": "in_progress"}]}')
        ok, startet = self._med(svar, lambda: k.vekk("x/y"))
        self.assertTrue(ok)
        self.assertEqual(startet, [])

    def test_i_ko_teller_som_at_den_gaar(self):
        for status in ("queued", "pending", "waiting", "requested"):
            svar = self._Svar(0, '{"workflow_runs": [{"status": "%s"}]}' % status)
            self.assertTrue(self._med(svar, lambda: k.klokke_gaar("x/y"))[0], status)

    def test_ingen_gaar_starter_en(self):
        svar = self._Svar(0, '{"workflow_runs": [{"status": "completed"}]}')
        ok, startet = self._med(svar, lambda: k.vekk("x/y"))
        self.assertTrue(ok)
        self.assertEqual(startet, [k.KLOKKE])

    def test_ukjent_svar_starter_en(self):
        for svar in (self._Svar(1, ""), self._Svar(0, "ikke json")):
            self.assertIsNone(self._med(svar, lambda: k.klokke_gaar("x/y"))[0])
            self.assertEqual(self._med(svar, lambda: k.vekk("x/y"))[1], [k.KLOKKE])


if __name__ == "__main__":
    unittest.main(verbosity=2)
