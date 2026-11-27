"""Tester for de engelske aksjesidene (scripts/engelsk.py). Ingen nettverk."""
import datetime
import html
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engelsk as en  # noqa: E402
import fetch_stocks as fs  # noqa: E402

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAG = datetime.date(2026, 11, 27)


def _data():
    with open(os.path.join(ROT, "data", "aksjer.json"), encoding="utf-8") as f:
        return json.load(f)["aksjer"]


def _synlig_tekst(side):
    kropp = side.split("<body>", 1)[1]
    kropp = re.sub(r"<script.*?</script>|<style.*?</style>", " ", kropp, flags=re.S)
    # Lenker merket lang="nb" er norske med vilje («Norsk»).
    kropp = re.sub(r'<a [^>]*lang="nb"[^>]*>.*?</a>', " ", kropp, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", " ", kropp))


class TestOrdliste(unittest.TestCase):
    def test_alle_verdier_i_katalogen_er_oversatt(self):
        for a in _data():
            if a.get("sektor"):
                self.assertIn(a["sektor"], en.SEKTOR_EN, a["ticker"])
            if a.get("frekvens"):
                self.assertIn(a["frekvens"], en.FREKVENS_EN, a["ticker"])
            if a.get("inkorporeringsland"):
                self.assertIn(a["inkorporeringsland"], en.LAND_EN, a["ticker"])
            if (a.get("hendelse") or {}).get("type"):
                self.assertIn(a["hendelse"]["type"], en.HENDELSE_EN, a["ticker"])

    def test_arsratemerket_finnes_der_det_norske_finnes(self):
        for kilde in ["betalt_12m", "siste_utbetalinger", "kunngjort", "betalt_og_kunngjort",
                      "pause", "kun_engangs", None, "annet"]:
            for ekstra in (False, True):
                a = {"arsrate_kilde": kilde, "arsrate_antall": 4, "arsrate_ekstra_trukket": ekstra}
                self.assertEqual(bool(fs.arsrate_merke(a)), bool(en.arsrate_merke_en(a)), kilde)


class TestFormat(unittest.TestCase):
    def test_tall_og_datoer(self):
        self.assertEqual(en.nf(1234.5), "1,234.50")
        self.assertEqual(en.pst(4.031), "4.03%")
        self.assertEqual(en.dato("2027-02-15"), "15 Feb 2027")
        self.assertEqual(en.belop(15.3), "NOK 15.30")
        self.assertEqual(en.belop(0.375), "NOK 0.375")
        self.assertEqual(en.maaneder([11, 2, 5]), "February, May and November")


class TestSide(unittest.TestCase):
    def test_hele_katalogen_uten_norsk_tekst(self):
        norsk = re.compile(r"\b(utbytte\w*|aksje\w*|og|siste|årlig|kvartalsvis|halvårlig|"
                           r"betalt|kr|hittil|selskapet|ingen|mnd)\b", re.I)
        for a in _data():
            side = en.aksje_side_en(a, DAG)
            tekst = _synlig_tekst(side).replace("Oslo Børs", "")
            # Selskapsnavn er egennavn («Høland og Setskog Sparebank»).
            for navn in (en.navn_en(a), en.kort_navn(a)):
                tekst = tekst.replace(navn, "")
            treff = norsk.findall(tekst)
            self.assertEqual(treff, [], f"{a['ticker']}: {treff[:5]}")

    def test_hode(self):
        a = next(x for x in _data() if x["ticker"] == "EQNR")
        side = en.aksje_side_en(a, DAG)
        self.assertIn('<html lang="en">', side)
        self.assertIn('content="noindex,follow"', side)
        self.assertIn('href="https://exday.no/en/stocks/EQNR/"', side)
        self.assertIn('hreflang="nb" href="https://exday.no/aksjer/EQNR/"', side)
        self.assertIn("localStorage.getItem('tema')!=='light'", side)

    def test_kildeskatt_etter_hjemland(self):
        a = {"navn": "Test ASA", "inkorporeringsland": "Norge"}
        self.assertIn("25%", en.skatt(a))
        a["inkorporeringsland"] = "Bermuda"
        self.assertIn("does not withhold", en.skatt(a))
        a["inkorporeringsland"] = "Sverige"
        self.assertIn("rules of Sweden apply", en.skatt(a))


if __name__ == "__main__":
    unittest.main()
