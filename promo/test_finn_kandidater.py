#!/usr/bin/env python3
"""Tester for finn_kandidater.py — mot skrevne fixture-filer, ikke repoets
egne data, så testene ikke endrer seg når noen legger til en artikkel."""
import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import finn_kandidater as fk  # noqa: E402

UI_JS = """'use strict';
const ARTIKLER = [
  {
    slug: '/artikler/ny-artikkel/',
    tittel: 'En ny artikkel',
    ingress: 'Ingress her.',
    meta: '1. oktober 2026 · 9 min',
    tags: ['Guide'],
    sektorer: [],
  },
  {
    slug: '/artikler/gammel-artikkel/',
    tittel: 'En gammel, allerede promotert artikkel',
    ingress: 'Ingress her.',
    meta: '1. januar 2026 · 5 min',
    tags: ['Guide'],
    sektorer: [],
  },
];
function noeAnnet() {}
"""


class TestLesArtikler(unittest.TestCase):
    def test_parser_begge_artiklene(self):
        with tempfile.TemporaryDirectory() as tmp:
            sti = os.path.join(tmp, "ui.js")
            open(sti, "w", encoding="utf-8").write(UI_JS)
            artikler = fk.les_artikler(sti)
        self.assertEqual(len(artikler), 2)
        self.assertEqual(artikler[0]["url"], "https://exday.no/artikler/ny-artikkel/")
        self.assertEqual(artikler[0]["tittel"], "En ny artikkel")

    def test_manglende_fil_gir_tom_liste(self):
        self.assertEqual(fk.les_artikler("/finnes/ikke.js"), [])

    def test_fil_uten_artikler_konstant_gir_tom_liste(self):
        with tempfile.TemporaryDirectory() as tmp:
            sti = os.path.join(tmp, "ui.js")
            open(sti, "w", encoding="utf-8").write("'use strict';\nfunction x(){}\n")
            self.assertEqual(fk.les_artikler(sti), [])


class TestIkkePromoterteArtikler(unittest.TestCase):
    def test_filtrerer_bort_promoterte(self):
        artikler = [
            {"url": "https://exday.no/artikler/a/", "tittel": "A", "meta": ""},
            {"url": "https://exday.no/artikler/b/", "tittel": "B", "meta": ""},
        ]
        innlegg = [{"artikkel": "https://exday.no/artikler/a/"}]
        ut = fk.ikke_promoterte_artikler(artikler, innlegg)
        self.assertEqual([a["url"] for a in ut], ["https://exday.no/artikler/b/"])

    def test_innlegg_uten_artikkel_teller_ikke(self):
        # «betalt-2026-09»-formen: artikkel peker på /aksjer/, ikke en artikkel.
        artikler = [{"url": "https://exday.no/artikler/a/", "tittel": "A", "meta": ""}]
        innlegg = [{"artikkel": "https://exday.no/aksjer/"}]
        self.assertEqual(len(fk.ikke_promoterte_artikler(artikler, innlegg)), 1)


class TestDagerSidenForrige(unittest.TestCase):
    def test_finner_nyeste_dato(self):
        innlegg = [{"publiser_fra": "2026-09-01"}, {"publiser_fra": "2026-09-20"}]
        i_dag = datetime.date(2026, 9, 28)
        self.assertEqual(fk.dager_siden_forrige(innlegg, i_dag), 8)

    def test_ingen_innlegg_gir_none(self):
        self.assertIsNone(fk.dager_siden_forrige([]))

    def test_ugyldig_dato_hoppes_over(self):
        innlegg = [{"publiser_fra": "ikke-en-dato"}, {"publiser_fra": "2026-09-10"}]
        i_dag = datetime.date(2026, 9, 15)
        self.assertEqual(fk.dager_siden_forrige(innlegg, i_dag), 5)

    def test_fremtidig_dato_gir_negativt_tall(self):
        # Et innlegg som ennå ikke er publisert skal ikke se ut som en pause.
        innlegg = [{"publiser_fra": "2026-10-05"}]
        i_dag = datetime.date(2026, 9, 28)
        self.assertEqual(fk.dager_siden_forrige(innlegg, i_dag), -7)


if __name__ == "__main__":
    unittest.main(verbosity=1)
