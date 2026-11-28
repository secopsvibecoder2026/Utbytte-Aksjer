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
            import oversett
            navn_liste = [en.navn_en(a), en.kort_navn(a), *oversett.ordliste().get("egennavn", [])]
            for navn in sorted(navn_liste, key=len, reverse=True):
                tekst = tekst.replace(navn, "")
            treff = norsk.findall(tekst)
            self.assertEqual(treff, [], f"{a['ticker']}: {treff[:5]}")

    def test_hode(self):
        a = next(x for x in _data() if x["ticker"] == "EQNR")
        side = en.aksje_side_en(a, DAG)
        self.assertIn('<html lang="en">', side)
        self.assertNotIn("noindex", side)
        self.assertIn('href="https://exday.no/en/stocks/EQNR/"', side)
        self.assertIn('hreflang="nb" href="https://exday.no/aksjer/EQNR/"', side)
        self.assertIn("localStorage.getItem('tema')!=='light'", side)

    def test_kildeskatt_etter_hjemland(self):
        a = {"navn": "Test ASA", "inkorporeringsland": "Norge"}
        self.assertIn("25%", en.skatt(a))
        a["inkorporeringsland"] = "Bermuda"
        self.assertIn("Bermuda does not withhold", en.skatt(a))
        a["inkorporeringsland"] = "Sverige"
        self.assertIn("rules of Sweden apply", en.skatt(a))
        self.assertNotIn("  ", en.skatt(a))
        # Ingen avtalesats som Skatteetaten ikke oppgir.
        self.assertNotIn("15%", en.skatt({"navn": "X ASA"}))



class TestLansering(unittest.TestCase):
    def test_tickerne_finnes_og_er_unike(self):
        katalog = {a["ticker"] for a in _data()}
        self.assertEqual(len(fs.EN_TICKERE), len(set(fs.EN_TICKERE)))
        self.assertEqual([t for t in fs.EN_TICKERE if t not in katalog], [])

    def test_bare_utbyttebetalere_som_blir_paa_bors(self):
        # Feiler når et selskap på listen slutter å betale eller får en hendelse
        # som oppkjøp eller fusjon: da skal det byttes ut med den neste.
        rader = {a["ticker"]: a for a in _data()}
        feil = [t for t in fs.EN_TICKERE
                if not (rader[t].get("utbytte_per_aksje") or 0) > 0 or not fs.i_rangering(rader[t])]
        self.assertEqual(feil, [])

    def test_generering_rydder_og_lager_oversikt(self):
        import tempfile
        rot = tempfile.mkdtemp()
        gammel = os.path.join(rot, "en", "stocks", "UTGAATT")
        os.makedirs(gammel)
        data = [a for a in _data() if a["ticker"] in ("EQNR", "DNB", "ZZZ")]
        laget = en.generer_engelske_sider(data, rot, DAG)
        self.assertEqual(laget, ["EQNR", "DNB"])
        self.assertFalse(os.path.exists(gammel))
        with open(os.path.join(rot, "en", "stocks", "index.html"), encoding="utf-8") as f:
            oversikt = f.read()
        self.assertIn('href="/en/stocks/EQNR/"', oversikt)
        self.assertIn('hreflang="nb" href="https://exday.no/aksjer/"', oversikt)
        tekst = _synlig_tekst(oversikt)
        self.assertEqual(re.findall(r"\b(utbytte|aksje\w*|og|siste)\b", tekst.replace("Oslo Børs", "")), [])

    def test_norsk_side_peker_til_engelsk(self):
        a = next(x for x in _data() if x["ticker"] == "EQNR")
        side = fs._aksje_side_html(a, DAG.isoformat())
        self.assertIn('hreflang="en" href="https://exday.no/en/stocks/EQNR/"', side)
        self.assertIn('href="/en/stocks/EQNR/" hreflang="en" lang="en">In English</a></p>', side)
        b = next(x for x in _data() if x["ticker"] not in fs.EN_TICKERE)
        self.assertNotIn("/en/stocks/", fs._aksje_side_html(b, DAG.isoformat()))


class TestOversettPort(unittest.TestCase):
    """scripts/oversett.py: porten som lagrer engelske tekster."""

    def setUp(self):
        import tempfile
        import oversett
        self.ov = oversett
        self.mappe = tempfile.mkdtemp()
        self._gammel = oversett.TEKSTER
        oversett.TEKSTER = os.path.join(self.mappe, "tekster_en.json")

    def tearDown(self):
        self.ov.TEKSTER = self._gammel

    NORSK = ("Sparebanken utsteder egenkapitalbevis, og den betalte utbytte i 2023 og 2024. "
             "Banken har vært notert siden 1994.")
    GOD = ("The savings bank issues equity certificates and paid a dividend in 2023 and 2024. "
           "The bank has been listed since 1994.")

    def test_god_tekst_slipper_gjennom(self):
        self.assertEqual(self.ov.valider("selskap", "X", self.GOD, self.NORSK), [])

    def test_feil_blir_stoppet(self):
        feil = " ".join(self.ov.valider("selskap", "X",
            "The bank — a robust lender og more — paid 7% in 2023 and 2024, listed since 1994.",
            self.NORSK))
        for ord_ in ("tall som ikke", "equity certificate", "robust", "norske ord", "tankestrek"):
            self.assertIn(ord_, feil)
        self.assertIn("årstall", " ".join(self.ov.valider("selskap", "X", self.GOD.replace("1994", "long"), self.NORSK)))

    def test_linjeskift_og_faguttrykk_med_siffer(self):
        no = "Banken har ren kjernekapital langt over kravet, og den er en sparebank."
        en_ = "The bank has CET1 capital well above the requirement, and it is a savings\nbank."
        self.assertEqual(self.ov.valider("selskap", "X", en_, no), [])

    def test_html_taggene_maa_vaere_like(self):
        no, en_ = "<p>Banken er <strong>stor</strong>.</p>", "<p>The bank is big.</p>"
        self.assertTrue(any("HTML" in f for f in self.ov.valider("sektor", "X", en_, no)))

    def test_utdatert_oversettelse_vises_ikke(self):
        self.ov.lagre("selskap", "X", self.GOD, self.NORSK)
        self.assertEqual(self.ov.gjeldende("selskap", "X", self.NORSK), self.GOD)
        self.assertEqual(self.ov.gjeldende("selskap", "X", self.NORSK + " Ny setning."), "")

    def test_ordlisten_har_gyldige_uttrykk(self):
        liste = self.ov.ordliste()
        for stamme, former in liste["termer"].items():
            re.compile(stamme)
            self.assertTrue(former, stamme)


if __name__ == "__main__":
    unittest.main()
