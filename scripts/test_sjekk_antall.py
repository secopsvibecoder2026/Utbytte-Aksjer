#!/usr/bin/env python3
"""Tester for sjekk_antall.py — stdlib unittest, ingen nett, ingen pytest.

    python scripts/test_sjekk_antall.py

Halvparten av testene her handler om hva sjekken skal la være i fred.
Utkastet før avgrensningen traff «675 aksjer» i et regneeksempel og
«15–20 selskaper» i et råd — tre falske for hver ekte. En sjekk med den
treffsikkerheten blir slått av, ikke fulgt.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sjekk_antall import _TELLING, _FORBEHOLD, _synlig_tekst, MIN_ANTALL, MAKS_ANTALL  # noqa: E402


def treffer(tekst):
    """Ville sjekken flagget denne synlige teksten?"""
    for m in _TELLING.finditer(tekst):
        n = int(m.group(1))
        if not (MIN_ANTALL <= n <= MAKS_ANTALL):
            continue
        if _FORBEHOLD.search(tekst[max(0, m.start() - 20):m.start()]):
            continue
        return True
    return False


class TestFangerEkteFeil(unittest.TestCase):
    def test_om_sidas_hovedtall(self):
        """Den faktiske feilen: 191 «Aksjer fulgt» mens katalogen var 155."""
        self.assertTrue(treffer("utbytteinvestorer 191 Aksjer fulgt Daglig"))

    def test_promobildet(self):
        self.assertTrue(treffer("exday.no 124 Aksjer 8.2% Høyeste"))

    def test_selskaper_teller_ogsa(self):
        self.assertTrue(treffer("Vi følger 155 selskaper på Oslo Børs"))


class TestLarStaIFred(unittest.TestCase):
    """Alt her er ekte tekst fra nettstedet som ikke skal flagges."""

    def test_rundet_form_med_forbehold(self):
        """«over 150» er den godkjente formen i meta og JSON-LD, der en
        HTML-kommentar ikke kan stå."""
        for s in ["Oversikt over mer enn 150 norske utbytteaksjer på Oslo Børs",
                  "Over 150 norske utbytteaksjer sortert etter sektor",
                  "rundt 155 aksjer", "minst 150 selskaper"]:
            self.assertFalse(treffer(s), s)

    def test_regneeksempel(self):
        """675 er antall aksjer man kjøper for 100 000 kr, ikke katalogen."""
        self.assertFalse(treffer("en aksje som koster 148 kr gir 675 aksjer"))

    def test_raad_med_lavt_tall(self):
        self.assertFalse(treffer("diversifiser på minst 15–20 selskaper i ulike sektorer"))

    def test_markor_er_ikke_et_bart_tall(self):
        html = '<div class="stat-num"><!--N:aksjer-->155<!--/N--></div><div>Aksjer fulgt</div>'
        self.assertFalse(treffer(_synlig_tekst(html)))


class TestSynligTekst(unittest.TestCase):
    def test_klassenavn_teller_ikke_som_tall(self):
        """«dark:text-gray-200» inneholder 200 og må ikke lekke inn i teksten."""
        html = '<p class="text-gray-200 dark:bg-gray-800">Vi følger aksjer</p>'
        self.assertNotIn("200", _synlig_tekst(html))

    def test_skript_og_stil_fjernes(self):
        html = "<style>.a{width:155px}</style><script>var n=155;</script><p>hei</p>"
        self.assertEqual(_synlig_tekst(html), "hei")


class TestVirkeligeSider(unittest.TestCase):
    def test_ingen_hardkodede_tellinger_i_repoet(self):
        from sjekk_antall import finn_hardkodede

        rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        funn = finn_hardkodede(rot)
        self.assertEqual(funn, [], f"hardkodede tellinger: {funn}")

    def test_om_sida_bruker_markor(self):
        rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(rot, "om/index.html"), encoding="utf-8") as f:
            innhold = f.read()
        self.assertIn("<!--N:aksjer-->", innhold)
        self.assertNotIn(">191<", innhold)


if __name__ == "__main__":
    unittest.main(verbosity=2)
