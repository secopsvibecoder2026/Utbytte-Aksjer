#!/usr/bin/env python3
"""Tester for sjekk_klasser.py — stdlib unittest, ingen nett, ingen pytest.

    python scripts/test_sjekk_klasser.py

Den viktigste testen her er ikke at sjekken finner feil, men at den *ikke*
finner feil den ikke har grunnlag for. Første utkast rapporterte 37 klasser
der ingen av dem var gale — JS-kroker og egne klasser den ikke hadde noe med
å gjette på. En sjekk full av falske positive er verre enn ingen sjekk, for
den leses som dekning og blir etter hvert ignorert.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sjekk_klasser import _UTIL, klasser_i_css  # noqa: E402


class TestKlasserICss(unittest.TestCase):
    def test_enkel_selektor(self):
        self.assertIn("flex", klasser_i_css(".flex{display:flex}"))

    def test_minifisert_rekke(self):
        """I minifisert CSS følger neste selektor rett etter }."""
        k = klasser_i_css(".a{color:red}.b{color:blue}")
        self.assertEqual(k, {"a", "b"})

    def test_escapet_kolon(self):
        """dark:text-gray-400 skrives .dark\\:text-gray-400 — regexen må ta
        backslash-alternativet først, ellers stopper den på kolonet."""
        self.assertIn("dark:text-gray-400",
                      klasser_i_css(r".dark\:text-gray-400{color:#9ca3af}"))

    def test_escapet_skraastrek_og_klammer(self):
        self.assertIn("bg-brand-950/30", klasser_i_css(r".bg-brand-950\/30{}"))
        self.assertIn("min-w-[520px]", klasser_i_css(r".min-w-\[520px\]{}"))

    def test_sammensatt_selektor(self):
        k = klasser_i_css(".kcard .val.green{color:#16a34a}")
        self.assertEqual(k, {"kcard", "val", "green"})


class TestUtilityAvgrensning(unittest.TestCase):
    """Sjekken gjelder bare Tailwind-utilities."""

    def test_kjenner_igjen_utilities(self):
        for kl in ["bg-green-600", "hover:bg-green-700", "dark:text-brand-400",
                   "sm:grid-cols-2", "min-w-[520px]", "dark:bg-brand-950/30",
                   "px-4", "-mt-2", "w-11", "focus:ring-2", "prose-sm"]:
            self.assertTrue(_UTIL.match(kl), kl + " burde telle som utility")

    def test_hopper_over_egne_klasser_og_js_kroker(self):
        """Disse er alle ekte klasser fra nettstedet som styles av sidens egen
        <style> eller plukkes opp av et inline <script>."""
        for kl in ["faq-q", "ak-tab", "htip-bg", "htrig", "sun-icon", "moon-icon",
                   "mnd-ja", "konto-ikke", "sb-rad", "k-kol-netto", "pf-gi-navn-btn",
                   "aktiv-filter", "site-logo-mark", "rente-preset", "green",
                   "artikel-kort", "les-ogsa-lenke"]:
            self.assertFalse(_UTIL.match(kl), kl + " skal ikke telle som utility")


class TestVirkeligeSider(unittest.TestCase):
    def test_ingen_udefinerte_klasser_i_repoet(self):
        from sjekk_klasser import finn_udefinerte

        rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        udef, totalt = finn_udefinerte(rot)
        self.assertGreater(totalt, 300, "fant nesten ingen klasser — går walk-en riktig?")
        self.assertEqual(udef, {}, f"udefinerte klasser: {sorted(udef)}")

    def test_bg_green_600_finnes_i_bygd_css(self):
        """Regresjonstesten for selve feilen: knappen «Åpne gratis app» sto
        med hvit tekst uten bakgrunn fordi denne klassen aldri ble generert."""
        rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(rot, "assets/tailwind.css"), encoding="utf-8") as f:
            css = f.read()
        for kl in [".bg-green-600", r".hover\:bg-green-700", r".dark\:text-brand-400"]:
            self.assertIn(kl, css, kl + " mangler i assets/tailwind.css — er den bygd?")

    def test_source_direktivet_staar_i_tw_input(self):
        """Uten @source skanner Tailwind v4 bare assets/, og hele feilen
        kommer tilbake neste gang CSS-en bygges."""
        rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(rot, "assets/tw-input.css"), encoding="utf-8") as f:
            self.assertIn("@source", f.read())


if __name__ == "__main__":
    unittest.main(verbosity=2)
