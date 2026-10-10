#!/usr/bin/env python3
"""Tester for tallkontroll_side.py — rapport-markdown til den faste siden."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tallkontroll_side as ts  # noqa: E402

RAPPORT = """## Systematiske feil
Ingen nye.

## Bekreftede enkeltfeil
| Aksje | Hva vises | Hva er riktig | Kilde |
|---|---|---|---|
| TEL | Ex-dato — | 15. oktober 2026 | melding 665019 |

## Uavklart
- **SOFF**: yield 0,70 % virker lav, mistenkt
  delårstilfelle.
- kjent fra før, `kursgraf_justert`
"""


class TestMarkdown(unittest.TestCase):
    def test_tabell_med_skillelinje(self):
        h = ts.markdown_til_html(RAPPORT)
        self.assertIn('<div class="tabell"><table>', h)
        self.assertIn("<th>Aksje</th>", h)
        self.assertIn("<td>TEL</td>", h)
        self.assertNotIn("<td>---</td>", h)

    def test_overskrift_blir_h2(self):
        self.assertIn("<h2>Systematiske feil</h2>", ts.markdown_til_html(RAPPORT))

    def test_liste_med_fortsettelseslinje(self):
        h = ts.markdown_til_html(RAPPORT)
        self.assertIn("mistenkt</span> delårstilfelle.</li>", h)
        self.assertIn("<code>kursgraf_justert</code>", h)

    def test_html_i_rapporten_escapes(self):
        # Innhold fra børsmeldinger skal aldri kunne bli markup på siden.
        h = ts.markdown_til_html('Melding: <script>alert(1)</script> [x](javascript:alert(1))')
        self.assertNotIn("<script>", h)
        self.assertNotIn('href="javascript', h)

    def test_bare_https_lenker(self):
        h = ts.markdown_til_html("[NewsWeb](https://newsweb.oslobors.no/message/665019)")
        self.assertIn('<a href="https://newsweb.oslobors.no/message/665019"', h)

    def test_merkelapp_blir_chip(self):
        h = ts.markdown_til_html("| a | b |\n|---|---|\n| kritisk | advarsel |")
        self.assertIn('class="chip chip-kritisk"', h)
        self.assertIn('class="chip chip-advarsel"', h)

    def test_kode_beskytter_mot_chip(self):
        self.assertIn("<code>kritisk</code>", ts.inline("`kritisk`"))


class TestSide(unittest.TestCase):
    def test_tittel_og_dato(self):
        s = ts.bygg_side(RAPPORT, dato="2026-10-05", neste="2026-10-12")
        self.assertTrue(s.startswith("<title>Tallkontroll exday.no</title>"))
        self.assertIn("Tallkontroll 5. oktober 2026", s)
        self.assertIn("Neste kontroll: 12. oktober 2026.", s)

    def test_tom_rapport_gir_tom_tilstand(self):
        self.assertIn('class="tom"', ts.bygg_side("", dato=None))

    def test_ugyldig_dato_utelates(self):
        s = ts.bygg_side("x", dato="ikke-dato")
        self.assertIn("<h1>Tallkontroll</h1>", s)

    def test_ingen_arctic_farger(self):
        s = ts.bygg_side(RAPPORT).lower()
        for farge in ("132a50", "1e5c5c", "2e7b7b", "91c4d8", "8b2020"):
            self.assertNotIn(farge, s)

    def test_vedlikehold_har_egen_tittel(self):
        s = ts.bygg_side(RAPPORT, dato="2026-10-11", neste="2026-10-12", type="vedlikehold")
        self.assertTrue(s.startswith("<title>Vedlikehold exday.no</title>"))
        self.assertIn("Vedlikehold 11. oktober 2026", s)
        self.assertIn("Neste runde: 12. oktober 2026.", s)
        self.assertIn("daglig vedlikehold", s)
        self.assertNotIn("Tallkontroll", s)

    def test_standard_er_fortsatt_tallkontroll(self):
        # Den ukentlige rutinen kaller skriptet uten --type.
        self.assertIn("ukentlig tallkontroll", ts.bygg_side(RAPPORT))


if __name__ == "__main__":
    unittest.main(verbosity=1)
