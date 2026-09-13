#!/usr/bin/env python3
"""Tester for sjekk_tema.py — stdlib unittest, ingen nett, ingen pytest.

    python scripts/test_sjekk_tema.py

Markupen i testene er hentet fra de faktiske sidene slik de var *før*
fiksen 2026-09-13. En sjekk som ikke fanger opp den virkelige feilen den
ble skrevet for, er verdiløs, så begge feilene er gjengitt ordrett.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sjekk_tema import sjekk_side  # noqa: E402


def side(hode="", kropp=""):
    return (
        "<!DOCTYPE html><html><head>"
        + hode
        + "</head><body class=\"bg-white dark:bg-gray-950\">"
        + kropp
        + "</body></html>"
    )


RIKTIG = "<script>(function(){if(localStorage.getItem('tema')==='dark')document.documentElement.classList.add('dark');})()</script>"


class TestRiktigOppsett(unittest.TestCase):
    def test_skript_i_head_er_ok(self):
        self.assertEqual(sjekk_side(side(hode=RIKTIG)), [])

    def test_flerlinjes_variant_er_ok(self):
        """personvern/ skriver samme init over flere linjer, og med
        prefers-color-scheme i tillegg. Sjekken må ikke låse formateringen."""
        hode = """<script>
    (function() {
      var t = localStorage.getItem('tema');
      if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
      }
    })();
  </script>"""
        self.assertEqual(sjekk_side(side(hode=hode)), [])

    def test_side_uten_mork_modus_hoppes_over(self):
        s = "<!DOCTYPE html><html><head></head><body>ren tekst</body></html>"
        self.assertEqual(sjekk_side(s), [])


class TestFeilNokkel(unittest.TestCase):
    """Feil 1: uke/, personvern/ og bevegelser/ leste den engelske nøkkelen."""

    def test_theme_i_head_flagges(self):
        hode = "<script>if(localStorage.getItem('theme')==='dark')document.documentElement.classList.add('dark');</script>"
        problemer = sjekk_side(side(hode=hode))
        self.assertTrue(any("theme" in p for p in problemer))

    def test_theme_flagges_selv_med_riktig_nokkel_ved_siden_av(self):
        """utbyttekalender/ leste begge nøkler som reserve. Det skjulte feilen
        bak en side som virket, så sjekken må se den likevel."""
        hode = (
            "<script>var t=localStorage.getItem('tema')||localStorage.getItem('theme');"
            "if(t==='dark')document.documentElement.classList.add('dark');</script>"
        )
        problemer = sjekk_side(side(hode=hode))
        self.assertTrue(any("theme" in p for p in problemer))

    def test_dobbelt_hermetegn_fanges_ogsa(self):
        hode = '<script>localStorage.getItem("theme");document.documentElement.classList.add("dark");</script>'
        problemer = sjekk_side(side(hode=hode))
        self.assertTrue(any("theme" in p for p in problemer))


class TestSkriptEtterHead(unittest.TestCase):
    """Feil 2: klassen ble satt, men først inne i <body>."""

    def test_skript_i_body_flagges(self):
        problemer = sjekk_side(side(kropp=RIKTIG))
        self.assertTrue(any("</head>" in p for p in problemer))

    def test_ingen_initialisering_flagges(self):
        problemer = sjekk_side(side())
        self.assertTrue(any("ingen temainitialisering" in p for p in problemer))

    def test_bare_setItem_i_head_teller_ikke(self):
        """Bryteren skriver 'tema' ved klikk. Det er ikke en initialisering —
        den må lese nøkkelen og sette klassen før body males."""
        hode = "<script>function bytt(){localStorage.setItem('tema','dark');}</script>"
        problemer = sjekk_side(side(hode=hode))
        self.assertTrue(any("ingen temainitialisering" in p for p in problemer))


class TestVirkeligeSider(unittest.TestCase):
    """Hele katalogen skal være ren etter fiksen."""

    def test_ingen_feil_i_repoet(self):
        from sjekk_tema import finn_feil

        rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        feil, kontrollert = finn_feil(rot)
        self.assertGreater(kontrollert, 100, "fant nesten ingen sider — går walk-en riktig?")
        self.assertEqual(feil, {}, f"temafeil funnet: {feil}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
