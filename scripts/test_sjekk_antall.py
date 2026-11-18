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

from sjekk_antall import _TELLING, _FORBEHOLD, _SEKTORER, _synlig_tekst, MIN_ANTALL, MAKS_ANTALL  # noqa: E402


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

    def test_sektorantall_paa_forsiden(self):
        """Forsiden sto med «16 sektorer totalt» mens katalogen hadde 15."""
        self.assertTrue(_SEKTORER.search("Alle sektorer 16 sektorer totalt"))
        self.assertTrue(_SEKTORER.search(_synlig_tekst(
            "<div>Alle sektorer</div><div>16 sektorer totalt</div>")))
        self.assertIsNone(_SEKTORER.search(_synlig_tekst(
            "<div><!--N:sektorer-->15<!--/N--> sektorer totalt</div>")))
        # Et råd med spenn er ikke en telling.
        self.assertIsNone(_SEKTORER.search("er 4–7 sektorer et godt utgangspunkt"))


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


class TestMetaOgMaler(unittest.TestCase):
    """Meta-taggene og malene i Python (2026-11-18).

    /aksjer/ hadde 162 i meta-beskrivelsen mens forsiden sa 155. Sjekken så
    bare synlig tekst, og Google viser meta-beskrivelsen i søkeresultatet.
    """

    def test_bart_tall_i_meta_fanges(self):
        from sjekk_antall import _attributt_tekst, _treff
        html = '<meta name="description" content="Oversikt over 162 norske utbytteaksjer.">'
        # «Oversikt over 162» har «over» foran og regnes som rundet; et bart tall gjør ikke det.
        self.assertEqual(_treff(_attributt_tekst(html)), [])
        html = '<meta property="og:description" content="Se 162 norske utbytteaksjer.">'
        self.assertEqual(len(_treff(_attributt_tekst(html))), 1)

    def test_json_ld_fanges(self):
        from sjekk_antall import _attributt_tekst, _treff
        html = '<script type="application/ld+json">{"description": "Alle 155 aksjer"}</script>'
        self.assertEqual(len(_treff(_attributt_tekst(html))), 1)

    def test_tall_i_f_streng_fanges_men_ikke_docstring(self):
        import tempfile
        from sjekk_antall import _mal_strenger, _treff
        kode = (
            'def mal(aksjer):\n'
            '    """Bygger 155 aksjer."""\n'
            '    print("155 aksjer OK")\n'
            '    return f"<h2>Alle 155 aksjer</h2><p>{len(aksjer)} aksjer</p>"\n'
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(kode)
        try:
            treff = [t for _, s in _mal_strenger(f.name) for t in _treff(s)]
        finally:
            os.unlink(f.name)
        self.assertEqual([t[0] for t in treff], ["155 aksjer"])


class TestRundetAntall(unittest.TestCase):
    def test_rundet_er_sant(self):
        from fetch_stocks import rundet_antall
        self.assertEqual(rundet_antall(155), 150)
        self.assertEqual(rundet_antall(150), 140)
        self.assertEqual(rundet_antall(151), 150)

    def test_synk_er_idempotent_og_hopper_over_artikler(self):
        import tempfile
        from fetch_stocks import oppdater_rundet_antall_i_sider
        with tempfile.TemporaryDirectory() as rot:
            os.makedirs(os.path.join(rot, "artikler", "a"))
            side = os.path.join(rot, "index.html")
            artikkel = os.path.join(rot, "artikler", "a", "index.html")
            with open(side, "w") as f:
                f.write('<meta content="for over 160 aksjer"><p>mer enn 160 norske utbytteaksjer</p><p>over 5 aksjer</p>')
            with open(artikkel, "w") as f:
                f.write('<p>over 120 aksjer har betalt</p>')
            aksjer = [{}] * 147
            self.assertEqual(oppdater_rundet_antall_i_sider(aksjer, rot), ["index.html"])
            self.assertEqual(oppdater_rundet_antall_i_sider(aksjer, rot), [])
            t = open(side).read()
            self.assertIn("for over 140 aksjer", t)
            self.assertIn("mer enn 140 norske utbytteaksjer", t)
            self.assertIn("over 5 aksjer", t)
            self.assertIn("over 120 aksjer", open(artikkel).read())


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
