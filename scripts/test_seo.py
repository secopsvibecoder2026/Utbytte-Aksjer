#!/usr/bin/env python3
"""Tester for scripts/seo.py (stdlib unittest, ingen nett)."""

import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import seo  # noqa: E402

SOK_EN = "Top queries,Clicks,Impressions,CTR,Position\nvår energi utbytte,26,299,8.7%,5.31\ntelenor utbytte,0,168,0%,11.8\n"
SIDER_EN = ("Top pages,Clicks,Impressions,CTR,Position\n"
            "https://exday.no/aksjer/VAR/,115,5488,2.1%,5.84\nhttps://exday.no/,111,9278,1.2%,12.98\n"
            "https://exday.no/aksjer/VAR/rapporter/,0,3,0%,5.7\n")
DAGER_EN = "Date,Clicks,Impressions,CTR,Position\n2026-08-23,12,651,1.84%,10.2\n2026-08-24,33,1217,2.71%,8.9\n"
FILTRE_EN = "Filter,Value\nSearch type,Web (text-based)\nDate,Last 3 months"
SOK_NO = "Mest brukte søk,Klikk,Visninger,CTR,Plassering\nvår energi utbytte,26,299,\"8,7 %\",\"5,31\"\n"


class TestTall(unittest.TestCase):
    def test_prosent_og_desimal_paa_begge_sprak(self):
        self.assertAlmostEqual(seo.tall("8.7%"), 0.087)
        self.assertAlmostEqual(seo.tall("8,7 %"), 0.087)
        self.assertAlmostEqual(seo.tall("12.98"), 12.98)
        self.assertAlmostEqual(seo.tall("5,31"), 5.31)
        self.assertEqual(seo.tall(""), 0.0)
        self.assertEqual(seo.tall("—"), 0.0)


class TestEksport(unittest.TestCase):
    def _zip(self, filer):
        d = tempfile.mkdtemp()
        sti = os.path.join(d, "eksport.zip")
        with zipfile.ZipFile(sti, "w") as z:
            for n, t in filer.items():
                z.writestr(n, t)
        return sti

    def test_leser_engelsk_zip(self):
        e = seo.les_eksport(self._zip({"Queries.csv": SOK_EN, "Pages.csv": SIDER_EN,
                                       "Chart.csv": DAGER_EN, "Filters.csv": FILTRE_EN}))
        self.assertEqual(len(e["sok"]), 2)
        self.assertEqual(e["sok"][0], {"nokkel": "vår energi utbytte", "klikk": 26, "visninger": 299,
                                       "ctr": 0.087, "posisjon": 5.31})
        self.assertEqual(len(e["sider"]), 3)
        self.assertEqual(seo.periode(e), "Last 3 months")
        self.assertEqual(seo.summer(e["dager"])["klikk"], 45)

    def test_leser_norske_overskrifter_og_filnavn(self):
        e = seo.les_eksport(self._zip({"Søk.csv": "﻿" + SOK_NO}))
        self.assertEqual(len(e["sok"]), 1)
        self.assertAlmostEqual(e["sok"][0]["ctr"], 0.087)
        self.assertAlmostEqual(e["sok"][0]["posisjon"], 5.31)

    def test_leser_en_mappe(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "Pages.csv"), "w", encoding="utf-8") as f:
            f.write(SIDER_EN)
        self.assertEqual(len(seo.les_eksport(d)["sider"]), 3)

    def test_periode_fra_dager_uten_filtre(self):
        e = seo.les_eksport(self._zip({"Chart.csv": DAGER_EN}))
        self.assertEqual(seo.periode(e), "2026-08-23 til 2026-08-24")


class TestSidegruppe(unittest.TestCase):
    def test_grupper(self):
        g = seo.sidegruppe
        self.assertEqual(g("https://exday.no/"), "forside")
        self.assertEqual(g("https://exday.no/aksjer/EQNR/"), "aksjeside")
        self.assertEqual(g("https://exday.no/aksjer/2020/"), "aksjeside")
        self.assertEqual(g("https://exday.no/aksjer/EQNR/rapporter/#2026-q3"), "rapportside")
        self.assertEqual(g("https://exday.no/aksjer/sektor/finans/"), "sektor")
        self.assertEqual(g("https://exday.no/aksjer/hoyest-utbytte/"), "aksjelister")
        self.assertEqual(g("https://exday.no/aksjer/"), "aksjelister")
        self.assertEqual(g("https://exday.no/artikler/hva-er-ex-dato/#skatt"), "artikkel")
        self.assertEqual(g("https://exday.no/utbyttekalender/?periode=30"), "utbyttekalender")
        self.assertEqual(g("https://exday.no/faq/"), "annet")


class TestMuligheter(unittest.TestCase):
    @staticmethod
    def _r(n, k, v, pos):
        return {"nokkel": n, "klikk": k, "visninger": v, "ctr": k / v, "posisjon": pos}

    def test_lav_ctr_maales_mot_eget_baand(self):
        rader = [self._r("a", 50, 1000, 6.0), self._r("b", 40, 1000, 6.4), self._r("c", 45, 1000, 7.2),
                 self._r("d", 5, 1000, 6.8),   # 0,5 % mot median 4 %: lav
                 self._r("e", 0, 50, 6.5)]     # for få visninger
        ut = seo.lav_ctr(rader, min_visninger=100)
        self.assertEqual([r["nokkel"] for r in ut], ["d"])
        self.assertGreater(ut[0]["tapte_klikk"], 30)

    def test_trenger_minst_tre_rader_i_baandet(self):
        rader = [self._r("a", 50, 1000, 6.0), self._r("d", 1, 1000, 6.8)]
        self.assertEqual(seo.lav_ctr(rader), [])

    def test_nesten_forsteside(self):
        rader = [self._r("a", 1, 500, 9.0), self._r("b", 1, 900, 14.0), self._r("c", 1, 900, 3.0),
                 self._r("d", 1, 900, 25.0), self._r("e", 1, 50, 10.0)]
        self.assertEqual([r["nokkel"] for r in seo.nesten_forsteside(rader)], ["b", "a"])

    def test_sammenlign(self):
        gml = [self._r("x", 10, 1000, 8.0)]
        ny = [self._r("x", 20, 1000, 7.0), self._r("y", 5, 100, 3.0)]
        e = seo.sammenlign(ny, gml)
        self.assertEqual(list(e), ["x"])
        self.assertEqual(e["x"]["klikk"], (10, 20))

    def test_per_gruppe(self):
        g = seo.per_gruppe([self._r("https://exday.no/aksjer/A/", 10, 100, 5.0),
                            self._r("https://exday.no/aksjer/B/", 0, 100, 15.0)])
        self.assertEqual(g["aksjeside"]["antall"], 2)
        self.assertEqual(g["aksjeside"]["klikk"], 10)
        self.assertAlmostEqual(g["aksjeside"]["posisjon"], 10.0)


def _side(tittel="T", meta="M" * 100, kanon=None, robots="", h1=1, jsonld='{"a":1}', lenker=(), refresh=False):
    k = f'<link rel="canonical" href="{kanon}"/>' if kanon else ""
    r = f'<meta name="robots" content="{robots}"/>' if robots else ""
    f = '<meta http-equiv="refresh" content="0; url=/x/"/>' if refresh else ""
    l_ = "".join(f'<a href="{x}">x</a>' for x in lenker)
    return (f'<html><head><title>{tittel}</title><meta name="description" content="{meta}"/>{k}{r}{f}'
            f'<script type="application/ld+json">{jsonld}</script></head>'
            f'<body>{"<h1>x</h1>" * h1}{l_}</body></html>')


class TestSider(unittest.TestCase):
    def _rot(self, sider, sitemap):
        rot = tempfile.mkdtemp()
        for rel, html in sider.items():
            os.makedirs(os.path.join(rot, os.path.dirname(rel)), exist_ok=True)
            with open(os.path.join(rot, rel), "w", encoding="utf-8") as f:
                f.write(html)
        with open(os.path.join(rot, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write("".join(f"<url><loc>{u}</loc></url>" for u in sitemap))
        os.makedirs(os.path.join(rot, "scripts", "x"), exist_ok=True)
        with open(os.path.join(rot, "scripts", "x", "index.html"), "w") as f:
            f.write("<title>skal ikke telles</title>")
        return rot

    def test_finner_feilene(self):
        D = seo.DOMENE
        rot = self._rot({
            "index.html": _side("Forside", kanon=D + "/", lenker=("/a/", "/b/")),
            "a/index.html": _side("A" * 70, kanon=D + "/a/", lenker=("/",)),
            "b/index.html": _side("Lik", kanon=D + "/x/", jsonld="{feil"),
            "c/index.html": _side("Lik", meta="kort", kanon=D + "/c/", h1=2),
            "d/index.html": _side("D", kanon=D + "/d/", robots="noindex,follow"),
            "e/index.html": _side("E", refresh=True),
        }, [D + "/", D + "/a/", D + "/b/", D + "/d/", D + "/e/", D + "/borte/"])
        funn, inn = seo.sjekk_sider(seo.finn_sider(rot), seo.les_sitemap(rot))
        self.assertEqual(funn["tittel over 60 tegn"], [D + "/a/ (70)"])
        self.assertEqual(funn["meta under 70 tegn"], [D + "/c/ (4)"])
        self.assertEqual(funn["kanonisk peker et annet sted"], [D + "/b/ → " + D + "/x/"])
        self.assertEqual(funn["JSON-LD som ikke kan leses"], [D + "/b/"])
        self.assertEqual(funn["ikke én h1"], [D + "/c/ (2)"])
        self.assertEqual(len(funn["lik tittel"]), 1)
        self.assertIn(D + "/c/", funn["indekserbar, men ikke i sitemap"])
        self.assertEqual(funn["i sitemap, men ingen side på disk"], [D + "/borte/"])
        self.assertEqual(funn["noindex, men i sitemap"], [D + "/d/"])
        self.assertEqual(funn["omdirigering i sitemap"], [D + "/e/"])
        self.assertIn(D + "/c/", funn["ingen interne lenker inn"])
        self.assertNotIn(D + "/a/", funn["ingen interne lenker inn"])
        self.assertEqual(inn[D + "/a/"], 1)
        self.assertNotIn(D + "/scripts/x/", seo.finn_sider(rot))

    def test_ren_side_gir_ingen_funn(self):
        D = seo.DOMENE
        rot = self._rot({"index.html": _side("Forside", meta="F" * 100, kanon=D + "/", lenker=("/a/",)),
                         "a/index.html": _side("A", meta="A" * 100, kanon=D + "/a/", lenker=("/",))},
                        [D + "/", D + "/a/"])
        funn, _ = seo.sjekk_sider(seo.finn_sider(rot), seo.les_sitemap(rot))
        self.assertEqual(funn, {})


class TestPersonvern(unittest.TestCase):
    def test_eksporten_lagres_ikke(self):
        """Repoet er offentlig: skriptet skriver ingen filer, og ingen eksport ligger i repoet."""
        kilde = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "seo.py"), encoding="utf-8").read()
        self.assertNotRegex(kilde, r"open\([^)]*['\"]w['\"]")
        for mappe, _, filer in os.walk(seo.ROT):
            if any(d in mappe for d in (".git", "node_modules", ".claude")):
                continue
            for f in filer:
                self.assertFalse(f.endswith("Performance-on-Search.zip") or f in ("Queries.csv", "Pages.csv"),
                                 os.path.join(mappe, f))


if __name__ == "__main__":
    unittest.main(verbosity=2)
