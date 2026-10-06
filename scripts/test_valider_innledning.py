#!/usr/bin/env python3
"""Tester for valider_innledning.py — porten selskapstekst-agenten skriver gjennom."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import valider_innledning as vi

# En tekst innenfor lengdemålet, uten tall og uten maskinvendinger.
GOD = ("Selskapet bygger ferger og hurtigbåter ved to verft på Vestlandet. "
       "Kundene er fylkeskommuner og rederier som kjører kontrakter for det offentlige. " * 9
       ).strip() + "\n\nDet andre avsnittet handler om hvordan ordrene kommer i bølger."


def _fil(tickere):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    f.write(json.dumps(tickere, indent=2, ensure_ascii=False) + "\n")
    f.close()
    return f.name


class TestSprak(unittest.TestCase):
    def test_tankestreker_over_grensen(self):
        feil = vi.sprakfeil("Banken — som er stor — låner ut penger.")
        self.assertTrue(any("tankestreker" in f for f in feil))

    def test_maskinvending(self):
        self.assertEqual(vi.sprakfeil("Det er verdt å merke seg at banken er stor."),
                         ["maskinvending «Det er verdt å merke seg»"])

    def test_vanlig_tekst(self):
        self.assertEqual(vi.sprakfeil("Banken låner ut penger til boligkjøpere i Trøndelag."), [])


class TestGjentatteFraser(unittest.TestCase):
    def test_navnet_maskeres(self):
        tekster = {f"T{i}": (f"Selskap{i} Bank er den ledende banken i sitt fylke.", f"Selskap{i} Bank")
                   for i in range(vi.FRASE_GRENSE)}
        self.assertEqual(set(vi.gjentatte_fraser(tekster)), set(tekster))

    def test_under_grensen_er_greit(self):
        tekster = {f"T{i}": ("Den ledende banken i sitt eget fylke.", f"S{i}")
                   for i in range(vi.FRASE_GRENSE - 1)}
        self.assertEqual(vi.gjentatte_fraser(tekster), {})


class TestSkriv(unittest.TestCase):
    def setUp(self):
        self.sti = _fil([{"ticker": "AAA", "navn": "Aaa ASA", "sektor": "Industri",
                          "beskrivelse": "Gammel tekst."},
                         {"ticker": "BBB", "navn": "Bbb ASA", "sektor": "Industri",
                          "beskrivelse": "Urørt — æøå."}])

    def tearDown(self):
        os.unlink(self.sti)

    def _les(self):
        with open(self.sti, encoding="utf-8") as f:
            return f.read()

    def test_godkjent_tekst_lagres_og_bare_den_endres(self):
        foer = self._les()
        self.assertEqual(vi.skriv("AAA", GOD, self.sti), [])
        etter = self._les()
        self.assertIn("Urørt — æøå.", etter)
        self.assertTrue(etter.endswith("]\n"))
        self.assertEqual(json.loads(etter)[0]["beskrivelse"], vi.normaliser(GOD))
        self.assertEqual(len(foer.splitlines()), len(etter.splitlines()))

    def test_avvist_tekst_skrives_ikke(self):
        foer = self._les()
        feil = vi.skriv("AAA", GOD.replace("ferger", "ferger — og båter — ", 1)
                        + " Det gir 7 % yield.", self.sti)
        self.assertTrue(any("tall som drifter" in f for f in feil))
        self.assertTrue(any("tankestrek" in f for f in feil))
        self.assertEqual(self._les(), foer)

    def test_for_kort(self):
        self.assertTrue(any("ord, målet er" in f for f in vi.skriv("AAA", "Kort.", self.sti)))

    def test_auto_tegn_ville_kuttet_teksten(self):
        feil = vi.skriv("AAA", GOD + " Utbyttet utbetales hvert år.", self.sti)
        self.assertTrue(any("_AUTO_TEGN" in f for f in feil))

    def test_avsnitt_normaliseres(self):
        self.assertEqual(vi.normaliser("En\nlinje.\n\n\n  To.  "), "En linje.\n\nTo.")


class TestArbeidsko(unittest.TestCase):
    def test_sprakbrudd_forst_deretter_storst(self):
        tickere = [
            {"ticker": "LITEN", "sektor": "", "beskrivelse": "Kort tekst."},
            {"ticker": "STOR", "sektor": "", "beskrivelse": "Kort tekst."},
            {"ticker": "STREK", "sektor": "", "beskrivelse": "Kort — og — strek."},
            {"ticker": "FERDIG", "sektor": "", "beskrivelse": vi.normaliser(GOD)},
        ]
        ko = vi.arbeidsko(tickere, {"STOR": 500, "LITEN": 5, "STREK": 1})
        self.assertEqual([t for t, _, _ in ko], ["STREK", "STOR", "LITEN"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
