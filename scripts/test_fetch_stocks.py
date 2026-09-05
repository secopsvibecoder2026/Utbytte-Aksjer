#!/usr/bin/env python3
"""Tester for fetch_stocks.py.

Kjøres med: python scripts/test_fetch_stocks.py

Testene som krever pandas hoppes over hvis pakken ikke finnes, slik at
suiten fortsatt kan kjøres uten tredjepartspakker.
"""

import datetime
import html
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_stocks as fs

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None


@unittest.skipIf(pd is None, "pandas er ikke installert")
class TestDatoindeksert(unittest.TestCase):
    """Regresjonstest for feilen som tok ned ni tickere i 16 dager.

    yfinance ga tilbake en ikke-tom utbytteserie med RangeIndex. Seks steder
    i fetch_stocks.py leser `dividends.index.tz` eller sammenligner indeksen
    med en dato; alle kastet «'RangeIndex' object has no attribute 'tz'».
    Unntaket boblet ut av hent_aksje(), tickeren feilet, og pipelinen serverte
    forrige kjørings tall videre uten at noe var synlig på siden.
    """

    def test_rangeindex_gir_tom_serie(self):
        serie = pd.Series([1.0, 2.0, 3.0])
        self.assertNotIsInstance(serie.index, pd.DatetimeIndex)
        self.assertTrue(fs._datoindeksert(serie).empty)

    def test_tom_serie_har_datetimeindex(self):
        """Den tomme serien må også tåle `.index.tz`.

        Første forsøk på fiksen returnerte `pd.Series(dtype="float64")`, som får
        en RangeIndex. hent_aksje() leser `dividends.index.tz` ett sted som
        ikke ligger bak en `.empty`-sjekk, så de samme sju tickerne feilet
        videre i produksjon. Testene over fanget det ikke, fordi både
        beregn_utbytte_vekst() og hent_historiske_utbytter() returnerer tidlig
        på tom serie.
        """
        for inn in (None, pd.Series([1.0, 2.0]), pd.Series(dtype="float64")):
            ut = fs._datoindeksert(inn)
            self.assertIsInstance(ut.index, pd.DatetimeIndex)
            self.assertIsNone(ut.index.tz)          # skal ikke kaste
            self.assertEqual(len(ut[ut.index >= pd.Timestamp("2020-01-01")]), 0)

    def test_datetimeindex_beholdes(self):
        serie = pd.Series([1.0, 2.0], index=pd.to_datetime(["2025-03-01", "2026-03-01"]))
        self.assertEqual(len(fs._datoindeksert(serie)), 2)

    def test_none_gir_tom_serie(self):
        self.assertTrue(fs._datoindeksert(None).empty)

    def test_beregn_utbytte_vekst_kaster_ikke(self):
        # Selve feilen: uten fiksen kaster dette AttributeError.
        self.assertEqual(fs.beregn_utbytte_vekst(fs._datoindeksert(pd.Series([1.0, 2.0]))), 0.0)

    def test_hent_historiske_utbytter_kaster_ikke(self):
        historikk, snitt = fs.hent_historiske_utbytter(
            fs._datoindeksert(pd.Series([1.0, 2.0])), pd.DataFrame(), current_price=10.0
        )
        self.assertEqual(historikk, [])


@unittest.skipIf(pd is None, "pandas er ikke installert")
class TestTomResponsFeiler(unittest.TestCase):
    """En tom Yahoo-respons skal registreres som feil, ikke som «ok».

    Da RangeIndex-krasjen ble fikset sluttet sju tickere å kaste, men Yahoo ga
    fortsatt ingenting. Resultatet ble lagret som vellykket med kurs 0, yield 0
    og tom historikk — Golden Ocean sto som «Uregelmessig utbytte» uten
    direkteavkastning. Fordi ok=True var satt, kunne verken mulig_avnotering
    eller navneendring slå ut, så ingenting varslet om det.
    """

    class _StubTicker:
        """Minimal erstatning for yf.Ticker med en tom respons."""

        def __init__(self, info):
            self.info = info
            self.dividends = pd.Series(dtype="float64", index=pd.DatetimeIndex([]))
            self.calendar = {}

        def history(self, period=None):
            return pd.DataFrame()

    def _kjor(self, info):
        stub = self._StubTicker(info)
        ekte_yf = fs.yf
        # Newsweb-oppslaget stubbes også, ellers går testen på nettet og bruker
        # fem sekunder på å time ut i CI.
        ekte_newsweb = fs.hent_newsweb_rapport_dato
        fs.yf = type("Yf", (), {"Ticker": staticmethod(lambda t: stub)})
        fs.hent_newsweb_rapport_dato = lambda t: None
        fs.HENTEDIAGNOSTIKK.pop("TEST", None)
        try:
            resultat = fs.hent_aksje({
                "ticker": "TEST", "ticker_yf": "TEST.OL",
                "navn": "Testselskap ASA", "sektor": "Finans", "bors": "Oslo Børs",
            })
        finally:
            fs.yf = ekte_yf
            fs.hent_newsweb_rapport_dato = ekte_newsweb
        return resultat, fs.HENTEDIAGNOSTIKK.get("TEST", {})

    def test_verken_navn_eller_kurs_gir_feil(self):
        resultat, diag = self._kjor({})
        self.assertIsNone(resultat)
        self.assertFalse(diag.get("ok"))
        self.assertIn("tom respons", diag.get("feilmelding", ""))

    def test_kurs_uten_navn_slipper_gjennom(self):
        # Navnet kan mangle uten at dataene er ubrukelige — kursen er nok.
        resultat, diag = self._kjor({"regularMarketPrice": 148.6})
        self.assertIsNotNone(resultat)
        self.assertTrue(diag.get("ok"))


class TestAntallIMarkorer(unittest.TestCase):
    """Aksjetellingene i de håndskrevne sidene fylles fra datasettet.

    Tallet sto hardkodet 28 steder og måtte rettes for hånd hver gang en
    ticker gikk ut. Det ble glemt gang på gang: sidene sa 191 da katalogen
    var 163, og 161 da den var 160 — tre runder med manuell retting på én uke.
    """

    def setUp(self):
        self.rot = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.rot, ignore_errors=True)
        self.aksjer = [
            {"ticker": "A", "sektor": "Finans", "utbytte_yield": 5.0, "ar_med_utbytte": 10, "ex_dato": "2026-04-01"},
            {"ticker": "B", "sektor": "Finans", "utbytte_yield": 0.0, "ar_med_utbytte": 3},
            {"ticker": "C", "sektor": "Shipping", "utbytte_yield": 7.5, "ar_med_utbytte": 0},
        ]

    def _skriv(self, navn, innhold):
        sti = os.path.join(self.rot, navn)
        os.makedirs(os.path.dirname(sti), exist_ok=True)
        with open(sti, "w", encoding="utf-8") as f:
            f.write(innhold)
        return sti

    def _les(self, sti):
        with open(sti, encoding="utf-8") as f:
            return f.read()

    def test_retter_utdaterte_tall(self):
        sti = self._skriv("index.html",
                          "<p>Vi følger <!--N:aksjer-->999<!--/N--> aksjer i "
                          "<!--N:sektorer-->1<!--/N--> sektorer.</p>")
        fs.oppdater_antall_i_sider(self.aksjer, self.rot)
        self.assertIn("<!--N:aksjer-->3<!--/N-->", self._les(sti))
        self.assertIn("<!--N:sektorer-->2<!--/N-->", self._les(sti))

    def test_alle_nokler(self):
        sti = self._skriv("a/index.html",
                          "<!--N:aksjer-->0<!--/N--> <!--N:utbytte-->0<!--/N--> "
                          "<!--N:historikk-->0<!--/N--> <!--N:exdato-->0<!--/N-->")
        fs.oppdater_antall_i_sider(self.aksjer, self.rot)
        t = self._les(sti)
        self.assertIn("<!--N:aksjer-->3<!--/N-->", t)        # alle
        self.assertIn("<!--N:utbytte-->2<!--/N-->", t)       # yield > 0
        self.assertIn("<!--N:historikk-->2<!--/N-->", t)     # ar_med_utbytte > 0
        self.assertIn("<!--N:exdato-->1<!--/N-->", t)        # har ex_dato

    def test_idempotent(self):
        sti = self._skriv("index.html", "<!--N:aksjer-->3<!--/N-->")
        fs.oppdater_antall_i_sider(self.aksjer, self.rot)
        forste = self._les(sti)
        fs.oppdater_antall_i_sider(self.aksjer, self.rot)
        self.assertEqual(forste, self._les(sti))

    def test_ukjent_nokkel_star_urort(self):
        # En skrivefeil i markøren skal ikke tømme teksten.
        sti = self._skriv("index.html", "<!--N:tullball-->42<!--/N-->")
        fs.oppdater_antall_i_sider(self.aksjer, self.rot)
        self.assertIn("<!--N:tullball-->42<!--/N-->", self._les(sti))

    def test_rorer_ikke_sider_uten_markor(self):
        sti = self._skriv("annen.html", "<p>160 aksjer uten markør</p>")
        fs.oppdater_antall_i_sider(self.aksjer, self.rot)
        self.assertIn("160 aksjer uten markør", self._les(sti))

    def test_frekvensnokler(self):
        # Utbyttekalenderen forklarer når på året pengene kommer, og svaret
        # er en fordeling av betalingsfrekvens. Skrives den som tekst,
        # drifter den akkurat som aksjetellingen gjorde.
        for a, f in zip(self.aksjer, ["Årlig", "Kvartalsvis", "Årlig"]):
            a["frekvens"] = f
        self.aksjer[0]["rapport_dato"] = "2026-10-30"
        sti = self._skriv("index.html",
                          "<!--N:arlig-->0<!--/N--> <!--N:kvartalsvis-->0<!--/N--> "
                          "<!--N:halvarlig-->9<!--/N--> <!--N:manedlig-->9<!--/N--> "
                          "<!--N:rapportdato-->0<!--/N-->")
        fs.oppdater_antall_i_sider(self.aksjer, self.rot)
        t = self._les(sti)
        self.assertIn("<!--N:arlig-->2<!--/N-->", t)
        self.assertIn("<!--N:kvartalsvis-->1<!--/N-->", t)
        self.assertIn("<!--N:halvarlig-->0<!--/N-->", t)
        self.assertIn("<!--N:manedlig-->0<!--/N-->", t)
        self.assertIn("<!--N:rapportdato-->1<!--/N-->", t)


class TestAarstallISider(unittest.TestCase):
    """«Utbyttekalender 2026» i en <title> er den samme fellen som antallet.

    Årstallet er sidens sterkeste søketreff, men en <title> kan ikke
    inneholde en HTML-kommentar, så markørene virker ikke der. Årstallet
    synkes derfor på tekstankeret «utbyttekalender» — og bare i filer som
    melder seg på med <!--AAR-SYNK-->.
    """

    def setUp(self):
        self.rot = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.rot, ignore_errors=True)

    def _skriv(self, navn, innhold):
        sti = os.path.join(self.rot, navn)
        os.makedirs(os.path.dirname(sti) or self.rot, exist_ok=True)
        with open(sti, "w", encoding="utf-8") as f:
            f.write(innhold)
        return sti

    def _les(self, sti):
        with open(sti, encoding="utf-8") as f:
            return f.read()

    def test_oppdaterer_tittel_og_meta(self):
        sti = self._skriv("utbyttekalender/index.html",
                          "<!--AAR-SYNK-->\n"
                          "<title>Utbyttekalender 2026 – Oslo Børs</title>\n"
                          '<meta name="description" content="Utbyttekalender 2026 for Oslo Børs." />')
        fs.oppdater_aarstall_i_sider(self.rot, i_dag=datetime.date(2029, 1, 2))
        t = self._les(sti)
        self.assertIn("<title>Utbyttekalender 2029 – Oslo Børs</title>", t)
        self.assertIn("Utbyttekalender 2029 for Oslo Børs.", t)
        self.assertNotIn("2026", t)

    def test_krever_paamelding(self):
        # Uten <!--AAR-SYNK--> skal årstallet stå urørt, så funksjonen ikke
        # retter et årstall som står der med vilje.
        sti = self._skriv("artikler/beste-utbytteaksjer-2026/index.html",
                          "<title>Utbyttekalender 2026 i historisk lys</title>")
        fs.oppdater_aarstall_i_sider(self.rot, i_dag=datetime.date(2029, 1, 2))
        self.assertIn("Utbyttekalender 2026", self._les(sti))

    def test_rorer_bare_arstall_etter_ankerordet(self):
        sti = self._skriv("k/index.html",
                          "<!--AAR-SYNK-->Utbyttekalender 2026. Kurs fra 2019. "
                          "Oslo Børs 2020.")
        fs.oppdater_aarstall_i_sider(self.rot, i_dag=datetime.date(2027, 6, 1))
        t = self._les(sti)
        self.assertIn("Utbyttekalender 2027", t)
        self.assertIn("Kurs fra 2019", t)
        self.assertIn("Oslo Børs 2020", t)

    def test_idempotent(self):
        sti = self._skriv("k/index.html", "<!--AAR-SYNK-->Utbyttekalender 2026")
        fs.oppdater_aarstall_i_sider(self.rot, i_dag=datetime.date(2027, 6, 1))
        forste = self._les(sti)
        fs.oppdater_aarstall_i_sider(self.rot, i_dag=datetime.date(2027, 6, 1))
        self.assertEqual(forste, self._les(sti))


class TestSidetittelOgMeta(unittest.TestCase):
    """Tittel og meta er bygget for hvordan folk faktisk søker.

    Search Console viste 29 900 visninger mot 601 klikk — 2,0 % CTR. Sidene
    rangerte, men treffet ble ikke kjent igjen: tittelen ledet med tickeren
    («EQNR – Equinor ASA»), og folk søker «Equinor utbytte». Meta-teksten var
    median 162 tegn og ble klippet av Google rundt 155.
    """

    I_DAG = "2026-09-05"

    def test_navnet_kommer_forst(self):
        t = fs._lag_sidetittel("Equinor ASA", "EQNR", 3.71, None, self.I_DAG)
        self.assertTrue(t.startswith("Equinor utbytte 2026"), t)
        self.assertIn("EQNR", t)

    def test_selskapsform_fjernes(self):
        for navn, vent in [("Equinor ASA", "Equinor"),
                           ("Frontline PLC", "Frontline"),
                           ("Bakkafrost P/F", "Bakkafrost"),
                           ("Hafnia Limited", "Hafnia"),
                           ("Golden Ocean Group", "Golden Ocean")]:
            self.assertEqual(fs._kort_selskapsnavn(navn), vent)

    def test_aksjeklasse_bevares(self):
        # A- og B-aksjen er to papirer og må ikke få samme tittel.
        a = fs._kort_selskapsnavn("Wilh. Wilhelmsen Holding (A-aksje)")
        b = fs._kort_selskapsnavn("Wilh. Wilhelmsen Holding (B-aksje)")
        self.assertNotEqual(a, b)

    def test_ex_dato_i_tittel_nar_den_naermer_seg(self):
        # Trafikken bygger seg opp i forkant — FRO steg 229 % tre uker før.
        nær = fs._lag_sidetittel("Frontline PLC", "FRO", 2.0, "2026-09-29", self.I_DAG)
        self.assertIn("ex-dato", nær)
        fjern = fs._lag_sidetittel("Equinor ASA", "EQNR", 3.7, "2027-05-20", self.I_DAG)
        self.assertNotIn("ex-dato", fjern)
        self.assertIn("yield", fjern)

    def test_passert_ex_dato_gir_ikke_tittel(self):
        t = fs._lag_sidetittel("Vår Energi ASA", "VAR", 10.8, "2026-08-21", self.I_DAG)
        self.assertNotIn("ex-dato", t)

    def test_tittel_holder_seg_under_60_tegn(self):
        for navn in ["Klaveness Combination Carriers ASA", "SpareBank 1 Ringerike Hadeland",
                     "Wilh. Wilhelmsen Holding (B-aksje)", "SED Energy Holdings PLC"]:
            t = fs._lag_sidetittel(navn, "XXXXX", 12.34, "2026-09-20", self.I_DAG)
            self.assertLessEqual(len(t), 60, t)

    def test_meta_under_155_tegn(self):
        for y, ex, upa, s5 in [(3.71, "2026-11-25", 14.59, 5.77), (10.82, None, 3.6, 12.1),
                               (0.0, None, 0.0, 0.0), (5.32, "2026-09-10", 12.0, 6.1)]:
            m = fs._lag_meta_beskrivelse("SpareBank 1 Ringerike Hadeland ASA", "SRHA",
                                         y, ex, upa, s5, "NOK", self.I_DAG)
            self.assertLessEqual(len(m), 155, m)

    def test_meta_beholder_valuta_i_versaler(self):
        # .capitalize() ville gjort «NOK» til «nok».
        m = fs._lag_meta_beskrivelse("Vår Energi ASA", "VAR", 10.8, None, 3.6, 12.1,
                                     "NOK", self.I_DAG)
        self.assertIn("NOK", m)

    def test_uten_utbytte_gir_meningsfull_tekst(self):
        t = fs._lag_sidetittel("KMC Properties ASA", "KMCP", 0.0, None, self.I_DAG)
        m = fs._lag_meta_beskrivelse("KMC Properties ASA", "KMCP", 0.0, None, 0.0, 0.0,
                                     "NOK", self.I_DAG)
        self.assertIn("KMC Properties", t)
        self.assertIn("KMC Properties", m)
        self.assertNotIn("0,0 %", m)


class TestUtbetalingsmaaneder(unittest.TestCase):
    """Månedsmønsteret som gjør en utbyttekalender mulig.

    Bare 11 av 160 aksjer har en annonsert ex-dato på et gitt tidspunkt, så en
    kalender bygget på annonseringer er tom det meste av året. Historikken
    lagret år og beløp, men ikke måned — datoene lå i Yahoo-serien og ble
    kastet. Nå utledes mønsteret av dem.
    """

    def test_maaneder_som_gjentar_seg(self):
        h = [{"ar": 2022, "maaneder": [5, 11]}, {"ar": 2023, "maaneder": [5, 11]},
             {"ar": 2024, "maaneder": [5, 11]}, {"ar": 2025, "maaneder": [5, 11]}]
        self.assertEqual(fs._typiske_utbetalingsmaaneder(h), [5, 11])

    def test_engangsmaaned_faller_ut(self):
        # Et ekstraordinært utbytte i august gjør ikke august til en
        # utbetalingsmåned.
        h = [{"ar": 2022, "maaneder": [5]}, {"ar": 2023, "maaneder": [5]},
             {"ar": 2024, "maaneder": [5, 8]}, {"ar": 2025, "maaneder": [5]}]
        self.assertEqual(fs._typiske_utbetalingsmaaneder(h), [5])

    def test_inneverende_ar_holdes_utenfor(self):
        # 2026 har bare rukket mai. Uten unntaket ville november falt ut fordi
        # året ikke er ferdig.
        h = [{"ar": 2024, "maaneder": [5, 11]}, {"ar": 2025, "maaneder": [5, 11]},
             {"ar": 2026, "maaneder": [5]}]
        self.assertEqual(fs._typiske_utbetalingsmaaneder(h), [5, 11])

    def test_ett_ar_gir_likevel_svar(self):
        # En fersk betaler har bare ett år. Da er det året det beste vi har.
        self.assertEqual(fs._typiske_utbetalingsmaaneder([{"ar": 2025, "maaneder": [4]}]), [4])

    def test_uten_data(self):
        self.assertEqual(fs._typiske_utbetalingsmaaneder([]), [])
        self.assertEqual(fs._typiske_utbetalingsmaaneder([{"ar": 2025, "utbytte": 5}]), [])

    def test_maanedstekst(self):
        self.assertEqual(fs._maaneder_tekst([5]), "mai")
        self.assertEqual(fs._maaneder_tekst([5, 11]), "mai og november")
        self.assertEqual(fs._maaneder_tekst([2, 5, 8]), "februar, mai og august")
        self.assertEqual(fs._maaneder_tekst([]), "")
        self.assertEqual(fs._maaneder_tekst([0, 13]), "")   # ugyldige måneder


class TestFrekvensLabel(unittest.TestCase):
    """Terskelen som gjorde SATS kvartalsvis og 2020 Bulkers kvartalsvis.

    Grensene er dokumentert her fordi de er årsaken til to reelle feil: en
    halvårlig betaler får «Kvartalsvis» så snart 12-månedersvinduet fanger en
    tredje utbetaling, og en månedlig betaler med brudd i serien faller ned i
    samme bøtte. Derfor finnes overstyringen i tickers.json.
    """

    def test_grenser(self):
        self.assertEqual(fs.frekvens_label(12), "Månedlig")
        self.assertEqual(fs.frekvens_label(10), "Månedlig")
        self.assertEqual(fs.frekvens_label(9), "Kvartalsvis")
        self.assertEqual(fs.frekvens_label(3), "Kvartalsvis")
        self.assertEqual(fs.frekvens_label(2), "Halvårlig")
        self.assertEqual(fs.frekvens_label(1), "Årlig")
        self.assertEqual(fs.frekvens_label(0), "Uregelmessig")

    def test_overstyring_leses_fra_tickers(self):
        # 2020 Bulkers og SATS er begge overstyrt manuelt.
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("2020"), "Månedlig")
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("SATS"), "Halvårlig")


class TestRapportkalender(unittest.TestCase):
    """Rapportkalenderen leser rapport_dato fra aksjer.json — ikke hendelser.json.

    hendelser.json akkumulerer (ticker, dato)-par og sletter aldri noe, så
    hver gang et selskap flytter rapportdatoen sin blir den gamle stående som
    en framtidig hendelse. Ved oppdagelsen hadde 12 tickere mellom 8 og 12
    «kommende» datoer hver — Entra sto med tolv rapporter på tre måneder — og
    de sto for 96 av 236 hendelser, 41 %. Siden må vise ett selskap én gang.
    """

    def setUp(self):
        self.rot = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.rot, ignore_errors=True)
        self.i_dag = datetime.date(2026, 9, 5)
        self.aksjer = [
            {"ticker": "AAA", "navn": "Alfa ASA", "sektor": "Finans",
             "utbytte_yield": 5.5, "rapport_dato": "2026-10-15", "ex_dato": "2026-04-01"},
            {"ticker": "BBB", "navn": "Beta ASA", "sektor": "Finans",
             "utbytte_yield": 0.0, "rapport_dato": "2026-11-03"},
            {"ticker": "CCC", "navn": "Gamma ASA", "sektor": "Shipping",
             "utbytte_yield": 7.0, "rapport_dato": "2026-08-01"},   # passert
            {"ticker": "DDD", "navn": "Delta ASA", "sektor": "Shipping",
             "utbytte_yield": 3.0},                                  # ingen dato
        ]

    def _generer(self):
        fs.generer_rapportkalender(self.aksjer, self.rot, i_dag=self.i_dag)
        sti = os.path.join(self.rot, "rapportkalender", "index.html")
        with open(sti, encoding="utf-8") as f:
            return f.read()

    def test_bare_kommende_datoer(self):
        h = self._generer()
        self.assertIn("Alfa ASA", h)        # 15. okt, framover
        self.assertIn("Beta ASA", h)        # 3. nov, framover
        self.assertNotIn("Gamma ASA", h)    # passert
        self.assertNotIn("Delta ASA", h)    # ingen rapport_dato

    def test_ett_selskap_en_rad(self):
        # Selv om hendelser.json skulle inneholde et titalls datoer for samme
        # ticker, bygger siden på aksjer.json og kan ikke duplisere.
        os.makedirs(os.path.join(self.rot, "data"), exist_ok=True)
        with open(os.path.join(self.rot, "data", "hendelser.json"), "w", encoding="utf-8") as f:
            json.dump({"hendelser": [
                {"ticker": "AAA", "dato": d, "type": "rapport"}
                for d in ("2026-09-23", "2026-09-30", "2026-10-15", "2026-10-21")
            ]}, f)
        h = self._generer()
        self.assertEqual(h.count('<a href="/aksjer/AAA/"'), 1)

    def test_ingen_kommende_gir_ingen_side(self):
        for a in self.aksjer:
            a.pop("rapport_dato", None)
        fs.generer_rapportkalender(self.aksjer, self.rot, i_dag=self.i_dag)
        self.assertFalse(os.path.exists(os.path.join(self.rot, "rapportkalender", "index.html")))

    def test_faq_star_ordrett_i_json_ld(self):
        h = self._generer()
        blokker = re.findall(r'<script type="application/ld\+json">(.*?)</script>', h, re.S)
        faq = next(json.loads(b) for b in blokker if json.loads(b)["@type"] == "FAQPage")
        for e in faq["mainEntity"]:
            self.assertIn(html.escape(e["name"]), h)
            self.assertIn(html.escape(e["acceptedAnswer"]["text"]), h)

    def test_tittel_holder_seg_under_60_tegn(self):
        # Med « | exday.no» bak klipper Google alt over ca. 60.
        h = self._generer()
        tittel = re.search(r"<title>(.*?)</title>", h).group(1)
        self.assertLessEqual(len(tittel), 60, tittel)
        self.assertIn(str(self.i_dag.year), tittel)

    def test_maaneder_nevnes_i_kalenderrekkefolge(self):
        # «november og oktober» leses som en feil selv når tallene stemmer.
        for i in range(5):
            self.aksjer.append({"ticker": f"N{i}", "navn": f"Nov {i} ASA",
                                "sektor": "Finans", "utbytte_yield": 1.0,
                                "rapport_dato": "2026-11-10"})
        h = self._generer()
        self.assertIn("oktober og november", h)
        self.assertNotIn("november og oktober", h)


if __name__ == "__main__":
    unittest.main(verbosity=2)
