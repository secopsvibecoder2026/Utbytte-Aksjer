"""Tester for scripts/nettstedfiler.py og exclude-lista i _config.yml.

30.10.2026 lå CLAUDE.md, ROADMAP.md, SECURITY_ROADMAP.md, skriptene og
testene åpent på exday.no (CLAUDE.html svarte 200). Testene under bruker
repoet slik det er, så en ny intern fil i roten eller en side som faller
ut av utvalget, stopper CI.
"""

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nettstedfiler as nf

ROT = Path(__file__).resolve().parent.parent
UNNTAK = nf.les_unntak((ROT / "_config.yml").read_text(encoding="utf-8"))


class TestLesUnntak(unittest.TestCase):
    def test_leser_lista_i_config(self):
        for m in ("*.md", "scripts", "tests", "promo", "package.json"):
            self.assertIn(m, UNNTAK)

    def test_hopper_over_kommentarer_og_andre_nokler(self):
        tekst = ("# kommentar\n"
                 "title: exday\n"
                 "exclude:\n"
                 "  # om lista\n"
                 "  - \"*.md\"\n"
                 "  - scripts\n"
                 "include:\n"
                 "  - .well-known\n")
        self.assertEqual(nf.les_unntak(tekst), ["*.md", "scripts"])


class TestErUnntatt(unittest.TestCase):
    def test_interne_filer_holdes_utenfor(self):
        for sti in ("CLAUDE.md", "ROADMAP.md", "SECURITY_ROADMAP.md",
                    "promo/publiseringsprompt.md", ".claude/agents/fikser.md",
                    "scripts/fetch_stocks.py", "tests/ui.test.js",
                    "promo/publiseringsplan.json", "package.json",
                    "_config.yml", ".gitignore"):
            self.assertTrue(nf.er_unntatt(sti, UNNTAK), sti)

    def test_nettstedet_er_med(self):
        for sti in ("index.html", "CNAME", "ads.txt", "robots.txt", "sw.js",
                    "404.html", "data/aksjer.json", "data/kurs/DNB.json",
                    "aksjer/DNB/index.html", "assets/app.js",
                    "artikler/hva-er-ex-dato/index.html"):
            self.assertFalse(nf.er_unntatt(sti, UNNTAK), sti)

    def test_mappenavn_er_ikke_et_prefiks_av_andre_navn(self):
        self.assertFalse(nf.er_unntatt("scriptsamling/index.html", ["scripts"]))


class TestMotRepoet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.alle = nf.sporede_filer(ROT)
        cls.utvalg = set(nf.nettstedfiler(cls.alle, UNNTAK))

    def test_ingen_markdown_eller_interne_mapper(self):
        lekker = [f for f in self.utvalg
                  if f.endswith(".md") or f.split("/")[0] in
                  ("scripts", "tests", "promo", ".claude", ".github")]
        self.assertEqual(lekker, [])

    def test_hver_side_i_sitemap_er_med(self):
        xml = (ROT / "sitemap.xml").read_text(encoding="utf-8")
        mangler = []
        for loc in re.findall(r"<loc>https://exday\.no/([^<]*)</loc>", xml):
            sti = loc + "index.html" if loc == "" or loc.endswith("/") else loc
            if sti not in self.utvalg:
                mangler.append(sti)
        self.assertEqual(mangler, [])

    def test_service_workerens_filer_er_med(self):
        sw = (ROT / "sw.js").read_text(encoding="utf-8")
        liste = re.search(r"PRECACHE = \[(.*?)\];", sw, re.S).group(1)
        mangler = []
        for url in re.findall(r"'(/[^']*)'", liste):
            sti = url.lstrip("/")
            sti = sti + "index.html" if sti == "" or sti.endswith("/") else sti
            if sti not in self.utvalg:
                mangler.append(sti)
        self.assertEqual(mangler, [])

    def test_det_nettstedet_trenger_er_med(self):
        for sti in nf.MAA_MED:
            self.assertIn(sti, self.utvalg)


class TestKopier(unittest.TestCase):
    def test_kopierer_med_mapper_og_hopper_over_manglende(self):
        with tempfile.TemporaryDirectory() as kilde, \
                tempfile.TemporaryDirectory() as maal:
            Path(kilde, "a").mkdir()
            Path(kilde, "a", "b.html").write_text("x", encoding="utf-8")
            Path(kilde, "index.html").write_text("y", encoding="utf-8")
            antall = nf.kopier(["index.html", "a/b.html", "borte.html"],
                               kilde, maal)
            self.assertEqual(antall, 2)
            self.assertEqual(Path(maal, "a", "b.html").read_text(encoding="utf-8"), "x")
            self.assertFalse(Path(maal, "borte.html").exists())


class TestDeploySteg(unittest.TestCase):
    """Begge deploy-jobbene må laste opp utvalget, ikke hele repoet."""

    def test_deploy_laster_opp_utvalget(self):
        for navn in ("update-og-deploy.yml", "deploy-only.yml"):
            yml = (ROT / ".github" / "workflows" / navn).read_text(encoding="utf-8")
            self.assertIn("scripts/nettstedfiler.py", yml, navn)
            self.assertNotRegex(yml, r'path:\s*"\."', navn)


if __name__ == "__main__":
    unittest.main(verbosity=2)
