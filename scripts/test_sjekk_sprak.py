#!/usr/bin/env python3
"""Tester for sjekk_sprak.py. Eksemplene er setninger fra våre egne tekster."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sjekk_sprak as ss


class TestTankestreker(unittest.TestCase):
    def test_tallomraade_teller_ikke(self):
        f = ss.vurder(["Snittet for 2021–2025 og 5-årssnittet er like."])
        self.assertEqual(f["streker"], 0)

    def test_begge_strektyper_teller(self):
        f = ss.vurder(["Prinsippet er det samme — du kjøper selv.", "Lineært – samme beløp."])
        self.assertEqual(f["streker"], 2)

    def test_to_i_samme_avsnitt_er_brudd(self):
        a = ("Det er lett å blande sammen — og det gjorde vi også, på våre egne "
             "sider, helt til nylig — før rettelsen.")
        f = ss.vurder([a] + ["ord " * 400])
        self.assertTrue(ss.brudd(f))
        self.assertEqual(len(f["tette"]), 1)

    def test_en_per_200_ord_er_lov(self):
        f = ss.vurder(["ord " * 199 + "slik — her.", "ord " * 200 + "og — her."])
        self.assertEqual((f["streker"], f["maks"]), (2, 2))
        self.assertFalse(ss.brudd(f))


class TestVendinger(unittest.TestCase):
    def test_finner_maskinvendinger(self):
        f = ss.vurder(["La oss se på tallene.", "Kort sagt: nøkkelen er tid."])
        self.assertEqual([v.lower() for v in f["vendinger"]], ["la oss", "kort sagt", "nøkkelen er"])

    def test_ikke_bare_men_ogsaa_i_samme_setning(self):
        self.assertTrue(ss.vurder(["Ikke bare for avkastning, men også for ro."])["vendinger"])
        self.assertFalse(ss.vurder(["Ikke bare det. Men også dette er greit."])["vendinger"])

    def test_vanlig_tekst_er_ok(self):
        f = ss.vurder(["Equinor betalte 3,69 kr per aksje i august. Pengene kom to uker senere."])
        self.assertFalse(ss.brudd(f))


class TestKilder(unittest.TestCase):
    def test_html_hopper_over_meny_og_bunntekst(self):
        side = ("<nav><p>Meny — lenker — her</p></nav><article><h2>Tittel</h2>"
                "<p>Første avsnitt.</p><script>var a = '—';</script></article>"
                "<footer><p>Bunntekst — med strek</p></footer>")
        self.assertEqual(ss.avsnitt_fra_html(side), ["Tittel", "Første avsnitt."])

    def test_planen_gir_hver_kanal(self):
        plan = {"innlegg": [
            {"id": "a", "facebook": {"tekst": "Gammel."}},
            {"id": "b", "facebook": {"tekst": "Ett.\n\nTo — tre."},
             "instagram": {"tekst": "Kort."}, "publiser_fra": "2026-10-10"}]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(plan, f)
        try:
            siste = ss.fra_plan(sti=f.name)
            self.assertEqual([n for n, _ in siste], ["b / facebook", "b / instagram"])
            self.assertEqual(siste[0][1], ["Ett.", "To — tre."])
            self.assertEqual(ss.fra_plan("a", sti=f.name)[0][1], ["Gammel."])
        finally:
            os.unlink(f.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
