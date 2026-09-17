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


class TestParseRapportDato(unittest.TestCase):
    """Bare ekte rapporthendelser får bli rapport_dato.

    Funksjonen returnerte tidligere nærmeste hendelse av *hvilken som helst*
    type når ingen matchet et rapport-nøkkelord. Da ble generalforsamlinger,
    kapitalmarkedsdager og stillefaser lagret som «neste kvartalsrapport» — og
    fordi datoen bare måtte ligge i framtiden, flyttet den seg hver gang en av
    dem passerte. Entra fikk 38 forskjellige rapportdatoer mellom april og
    september 2026, og oppdater_hendelser.py bevarte hver eneste en.
    """

    def _kalender(self, *linjer):
        return "\n".join(linjer)

    def test_rapport_velges(self):
        body = self._kalender(
            "20.10.2099 - Kapitalmarkedsdag",
            "28.10.2099 - Q3 2099 kvartalsrapport",
        )
        self.assertEqual(fs._parse_rapport_dato(body), "2099-10-28")

    def test_rapport_velges_selv_om_annet_kommer_forst(self):
        body = self._kalender(
            "05.05.2099 - Ordinær generalforsamling",
            "12.05.2099 - Stillefase starter",
            "20.05.2099 - Quarterly report Q1",
        )
        self.assertEqual(fs._parse_rapport_dato(body), "2099-05-20")

    def test_uten_rapport_gir_ingenting(self):
        # Selve feilen: dette returnerte «2099-05-05» og ble lagret som
        # neste kvartalsrapport.
        body = self._kalender(
            "05.05.2099 - Ordinær generalforsamling",
            "12.05.2099 - Kapitalmarkedsdag",
            "19.05.2099 - Ex-dato utbytte",
        )
        self.assertIsNone(fs._parse_rapport_dato(body))

    def test_passerte_datoer_teller_ikke(self):
        self.assertIsNone(fs._parse_rapport_dato("01.01.2001 - Q4 kvartalsrapport"))

    def test_tom_body(self):
        self.assertIsNone(fs._parse_rapport_dato(""))


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


class TestUtenUtbyttebevis(unittest.TestCase):
    """Grensen mellom «tomt skall» og «har sluttet å betale».

    Skillet er verdt en test fordi det er lett å ta feil av, og fordi feilen
    er stille: en for vid regel avindekserer atten sider som gjør jobben sin.
    Den som søker «Scatec utbytte» skal få vite at selskapet betalte fram til
    2023 og så stoppet — det er et svar, ikke en tom side.
    """

    def test_helt_tom_er_uten_bevis(self):
        self.assertTrue(fs.uten_utbyttebevis({"ticker": "ACR"}))

    def test_nullverdier_teller_som_tomt(self):
        self.assertTrue(fs.uten_utbyttebevis({
            "ticker": "KMAR", "historiske_utbytter": [], "ar_med_utbytte": 0,
            "utbytte_yield": 0, "utbytte_per_aksje": 0,
        }))

    def test_historikk_men_ingen_yield_beholdes(self):
        # Scatec-tilfellet: sluttet å betale, men historikken er ekte.
        self.assertFalse(fs.uten_utbyttebevis({
            "ticker": "SCATC", "utbytte_yield": 0, "utbytte_per_aksje": 0,
            "historiske_utbytter": [{"ar": 2023, "utbytte": 1.0}],
        }))

    def test_arstelling_alene_holder(self):
        self.assertFalse(fs.uten_utbyttebevis({
            "ticker": "X", "historiske_utbytter": [], "ar_med_utbytte": 4,
        }))

    def test_yield_alene_holder(self):
        self.assertFalse(fs.uten_utbyttebevis({
            "ticker": "X", "historiske_utbytter": [], "utbytte_yield": 3.2,
        }))

    def test_aktiv_utbyttebetaler_beholdes(self):
        self.assertFalse(fs.uten_utbyttebevis({
            "ticker": "ATEA", "ar_med_utbytte": 18, "utbytte_yield": 4.5,
            "utbytte_per_aksje": 7.5,
            "historiske_utbytter": [{"ar": 2025, "utbytte": 7.0}],
        }))


class TestYieldErDelaar(unittest.TestCase):
    """yield_er_delaar() — regelen som merker de ti aksjene med for lav yield.

    Den finnes i tre eksemplarer av nødvendighet: her (maler), i
    valider_data.py (Sjekk 7, som må kjøre uten yfinance) og i assets/ui.js
    (appen). Testene under dekker de samme tilfellene som ui.test.js, og
    test_samsvar_med_valider_data sammenligner mot det ekte datasettet.
    """

    def test_flagger_aarsrate_under_en_utbetaling(self):
        from fetch_stocks import yield_er_delaar
        self.assertTrue(yield_er_delaar(
            {"frekvens": "Halvårlig", "utbytte_per_aksje": 2.2, "siste_utbytte": 5.7}))
        self.assertTrue(yield_er_delaar(
            {"frekvens": "Kvartalsvis", "utbytte_per_aksje": 0.46, "siste_utbytte": 5.94}))
        self.assertTrue(yield_er_delaar(
            {"frekvens": "Månedlig", "utbytte_per_aksje": 0.47, "siste_utbytte": 128.2}))

    def test_lar_normal_betaler_i_fred(self):
        from fetch_stocks import yield_er_delaar
        self.assertFalse(yield_er_delaar(
            {"frekvens": "Kvartalsvis", "utbytte_per_aksje": 12, "siste_utbytte": 3}))

    def test_sier_ingenting_om_aarlige_betalere(self):
        # For en årlig betaler ER én utbetaling hele året. Regelen har ikke
        # grunnlag, og må ikke flagge dem.
        from fetch_stocks import yield_er_delaar
        self.assertFalse(yield_er_delaar(
            {"frekvens": "Årlig", "utbytte_per_aksje": 5, "siste_utbytte": 5}))
        self.assertFalse(yield_er_delaar(
            {"frekvens": "Uregelmessig", "utbytte_per_aksje": 1, "siste_utbytte": 9}))

    def test_takler_manglende_og_ugyldige_verdier(self):
        from fetch_stocks import yield_er_delaar
        for rar in [None, {}, [], "tull",
                    {"frekvens": "Kvartalsvis"},
                    {"frekvens": "Kvartalsvis", "utbytte_per_aksje": 0, "siste_utbytte": 5},
                    {"frekvens": "Kvartalsvis", "utbytte_per_aksje": None, "siste_utbytte": "x"}]:
            self.assertFalse(yield_er_delaar(rar), repr(rar))

    def test_samsvar_med_valider_data(self):
        """De to Python-implementasjonene må være enige om det ekte datasettet.

        valider_data.py importerer ikke herfra — den skal kunne kjøre uten
        yfinance — så kopiene kan gli fra hverandre. Denne fanger det.
        """
        import json
        from fetch_stocks import yield_er_delaar
        sti = os.path.join(os.path.dirname(__file__), "..", "data", "aksjer.json")
        if not os.path.exists(sti):
            self.skipTest("aksjer.json finnes ikke")
        with open(sti, encoding="utf-8") as f:
            aksjer = json.load(f).get("aksjer", [])

        # Sjekk 7 sin regel, skrevet ut slik den står i valider_data.py
        pr_ar = {"Månedlig": 12, "Kvartalsvis": 4, "Halvårlig": 2}
        def sjekk7(a):
            upa = a.get("utbytte_per_aksje") or 0
            if a.get("frekvens") in pr_ar and upa > 0:
                return 0 < upa < (a.get("siste_utbytte") or 0)
            return False

        mine = {a["ticker"] for a in aksjer if yield_er_delaar(a)}
        deres = {a["ticker"] for a in aksjer if sjekk7(a)}
        self.assertEqual(mine, deres,
                         f"regelen har glidd fra hverandre: {mine ^ deres}")
        self.assertTrue(mine, "ingen aksjer flagget — er datasettet tomt?")


class TestUtbetaltHittil(unittest.TestCase):
    """utbetalt_hittil() — det ene tallet vi faktisk vet når raten er et delår.

    Vaktene er hele poenget: uten dem ville varselet presentert 2020 Bulkers'
    132,66 NOK på en 4,06-kroners aksje som et faktum, og i januar ville det
    merket fjorårets total «hittil i år».
    """

    def _rad(self, **kw):
        base = {"ar": datetime.date.today().year, "utbytte": 8.96,
                "yield": 10.1, "maaneder": [3, 6, 9]}
        base.update(kw)
        return {"pris": 88.65, "historiske_utbytter": [base]}

    def test_henter_aarets_rad(self):
        from fetch_stocks import utbetalt_hittil
        f = utbetalt_hittil(self._rad())
        self.assertEqual(f["belop"], 8.96)
        self.assertEqual(f["antall"], 3)
        self.assertEqual(f["yield"], 10.1)
        self.assertEqual(f["ar"], datetime.date.today().year)

    def test_ingen_rad_for_i_aar_gir_none(self):
        # Januar-tilfellet: fjorårets total må ikke merkes «hittil i år».
        from fetch_stocks import utbetalt_hittil
        i_fjor = datetime.date.today().year - 1
        self.assertIsNone(utbetalt_hittil(self._rad(ar=i_fjor)))
        self.assertIsNone(utbetalt_hittil({"pris": 100, "historiske_utbytter": []}))

    def test_forkaster_belop_over_dobbel_kurs(self):
        # 2020 Bulkers etter kapitalutdelingen: 132,66 på en 4,06-kroners aksje.
        from fetch_stocks import utbetalt_hittil
        self.assertIsNone(utbetalt_hittil(
            {"pris": 4.06,
             "historiske_utbytter": [{"ar": datetime.date.today().year,
                                      "utbytte": 132.66, "yield": None,
                                      "maaneder": [1, 2, 3, 4]}]}))

    def test_krever_yield_og_kurs(self):
        from fetch_stocks import utbetalt_hittil
        self.assertIsNone(utbetalt_hittil(self._rad(**{"yield": None})))
        self.assertIsNone(utbetalt_hittil(self._rad(utbytte=0)))
        rad = self._rad()
        rad["pris"] = 0
        self.assertIsNone(utbetalt_hittil(rad))

    def test_takler_soppel(self):
        from fetch_stocks import utbetalt_hittil
        for rar in [None, {}, [], "tull", {"pris": "x"},
                    {"pris": 10, "historiske_utbytter": None},
                    {"pris": 10, "historiske_utbytter": ["tull"]}]:
            self.assertIsNone(utbetalt_hittil(rar), repr(rar))

    def test_manglende_maaneder_gir_antall_null(self):
        # `maaneder` kommer bare fra en full henting. Uten den skal beløpet
        # fortsatt vises — bare uten «fordelt på N utbetalinger».
        from fetch_stocks import utbetalt_hittil
        rad = self._rad()
        del rad["historiske_utbytter"][0]["maaneder"]
        self.assertEqual(utbetalt_hittil(rad)["antall"], 0)


class TestLagDelaarVarsel(unittest.TestCase):
    """Varselet skal ikke motsi seg selv — det er den gjentatte feilen her."""

    @staticmethod
    def _nf(v, d=2):
        return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")

    def _hafni(self):
        return {
            "frekvens": "Kvartalsvis", "utbytte_per_aksje": 3.71,
            "siste_utbytte": 4.65, "utbytte_yield": 4.18, "pris": 88.65,
            "valuta": "NOK",
            "historiske_utbytter": [{"ar": datetime.date.today().year,
                                     "utbytte": 8.96, "yield": 10.1,
                                     "maaneder": [3, 6, 9]}],
        }

    def test_viser_utbetalt_hittil(self):
        from fetch_stocks import lag_delaar_varsel
        html = lag_delaar_varsel(self._hafni(), self._nf)
        self.assertIn("8,96 NOK per aksje hittil i", html)
        self.assertIn("fordelt på 3 utbetalinger", html)
        self.assertIn("10,10 %", html)

    def test_tom_for_aksjer_som_ikke_er_berort(self):
        from fetch_stocks import lag_delaar_varsel
        a = self._hafni()
        a["utbytte_per_aksje"] = 14.0
        self.assertEqual(lag_delaar_varsel(a, self._nf), "")

    def test_utelater_tallet_naar_det_ville_motsi_setningen_over(self):
        # Teksten sier «sannsynligvis høyere enn X %». Et hittil-i-år-tall
        # under X ville lest som en feil, så da faller avsnittet tilbake.
        from fetch_stocks import lag_delaar_varsel
        a = self._hafni()
        a["historiske_utbytter"][0]["yield"] = 1.0
        html = lag_delaar_varsel(a, self._nf)
        self.assertNotIn("hittil i", html)
        self.assertIn("se utbyttehistorikken under", html)

    def test_faller_tilbake_naar_summen_er_usannsynlig(self):
        # 2020 Bulkers: varselet skal fortsatt komme, men uten tallet.
        from fetch_stocks import lag_delaar_varsel
        a = {"frekvens": "Månedlig", "utbytte_per_aksje": 0.47,
             "siste_utbytte": 128.2, "utbytte_yield": 11.58, "pris": 4.06,
             "valuta": "NOK",
             "historiske_utbytter": [{"ar": datetime.date.today().year,
                                      "utbytte": 132.66, "yield": None,
                                      "maaneder": [1, 2, 3, 4]}]}
        html = lag_delaar_varsel(a, self._nf)
        self.assertIn("Direkteavkastningen kan være for lav", html)
        self.assertNotIn("132,66", html)
        self.assertNotIn("hittil i", html)

    def test_en_enkelt_utbetaling_boyes_riktig(self):
        from fetch_stocks import lag_delaar_varsel
        a = self._hafni()
        a["historiske_utbytter"][0]["maaneder"] = [4]
        html = lag_delaar_varsel(a, self._nf)
        self.assertIn("i én utbetaling", html)
        self.assertNotIn("1 utbetalinger", html)


class TestParseUtbyttesplitt(unittest.TestCase):
    """Parseren for børsens utbyttemelding — to former, begge fra ekte tekst."""

    KOG = """Ordinary dividend
Dividend amount: 2.20 per share
Declared currency: NOK
Ex-date: 14 April 2026
Special dividend
Dividend amount: 3.50 per share
Declared currency: NOK
Ex-date: 14 April 2026"""

    HUNT = """Key information relating to the cash dividend to be paid by Hunter Group ASA:
Dividend amount: NOK 1.50 per share
Declared currency: NOK
Dividend classification: NOK 1.50 as extraordinary dividend
Ex-date: 29 September 2026"""

    ORK = """Ordinary dividend
Dividend amount: 6.00 per share
Declared currency: NOK"""

    def test_splitt_med_to_overskrifter(self):
        from fetch_stocks import _parse_utbyttesplitt
        r = _parse_utbyttesplitt(self.KOG)
        self.assertEqual(r["ordinaert"], 2.20)
        self.assertEqual(r["ekstraordinaert"], 3.50)
        self.assertEqual(r["valuta"], "NOK")

    def test_belop_hentes_i_sin_egen_seksjon(self):
        # Uten seksjonsinndeling ville den forste «Dividend amount» blitt
        # brukt for begge typene, og splitten blitt 2,20 + 2,20.
        from fetch_stocks import _parse_utbyttesplitt
        r = _parse_utbyttesplitt(self.KOG)
        self.assertNotEqual(r["ordinaert"], r["ekstraordinaert"])

    def test_klassifisering_av_hele_utbetalingen(self):
        from fetch_stocks import _parse_utbyttesplitt
        r = _parse_utbyttesplitt(self.HUNT)
        self.assertEqual(r["ordinaert"], 0.0)
        self.assertEqual(r["ekstraordinaert"], 1.50)

    def test_bare_ordinaert_gir_ingenting(self):
        # At et ordinaert utbytte er ordinaert er ikke ny informasjon.
        from fetch_stocks import _parse_utbyttesplitt
        self.assertIsNone(_parse_utbyttesplitt(self.ORK))

    def test_takler_soppel(self):
        from fetch_stocks import _parse_utbyttesplitt
        for rar in [None, "", 42, [], "Dividend amount: 5.00"]:
            self.assertIsNone(_parse_utbyttesplitt(rar), repr(rar))


class TestUtbyttesplittStemmer(unittest.TestCase):
    """Sumvakten — den avgjor om meldingen beskriver DEN utbetalingen."""

    def _a(self, **kw):
        a = {"siste_utbytte": 5.70, "valuta": "NOK",
             "utbyttesplitt": {"ordinaert": 2.20, "ekstraordinaert": 3.50,
                               "valuta": "NOK"}}
        a.update(kw)
        return a

    def test_godtar_naar_summen_stemmer(self):
        from fetch_stocks import utbyttesplitt_stemmer
        r = utbyttesplitt_stemmer(self._a())
        self.assertEqual(r["ordinaert"], 2.20)

    def test_forkaster_melding_om_en_annen_utbetaling(self):
        # HUNT annonserte 1,50 med ex-dato fram i tid mens siste_utbytte var
        # 1,25. A feste den meldingen til den utbetalingen ville vaert galt.
        from fetch_stocks import utbyttesplitt_stemmer
        self.assertIsNone(utbyttesplitt_stemmer(self._a(siste_utbytte=1.25)))

    def test_godtar_hele_utbetalingen_som_ekstraordinaer(self):
        from fetch_stocks import utbyttesplitt_stemmer
        a = self._a(siste_utbytte=1.25,
                    utbyttesplitt={"ordinaert": 0.0, "ekstraordinaert": 1.25,
                                   "valuta": "NOK"})
        self.assertEqual(utbyttesplitt_stemmer(a)["ekstraordinaert"], 1.25)

    def test_krever_en_ekstraordinaer_del(self):
        from fetch_stocks import utbyttesplitt_stemmer
        a = self._a(siste_utbytte=2.20,
                    utbyttesplitt={"ordinaert": 2.20, "ekstraordinaert": 0.0,
                                   "valuta": "NOK"})
        self.assertIsNone(utbyttesplitt_stemmer(a))

    def test_takler_soppel(self):
        from fetch_stocks import utbyttesplitt_stemmer
        for rar in [None, {}, [], "tull", {"utbyttesplitt": "nei"},
                    {"siste_utbytte": 0, "utbyttesplitt": {"ordinaert": 1, "ekstraordinaert": 1}},
                    {"siste_utbytte": 5, "utbyttesplitt": {"ordinaert": "x", "ekstraordinaert": None}}]:
            self.assertIsNone(utbyttesplitt_stemmer(rar), repr(rar))

    def test_samsvar_med_datasettet(self):
        """Hver lagret splitt i aksjer.json ma passere vakten.

        En splitt som ligger lagret men blir forkastet ved rendring er dod
        vekt — og et tegn pa at hentingen festet feil melding til aksjen.
        """
        import json
        from fetch_stocks import utbyttesplitt_stemmer
        sti = os.path.join(os.path.dirname(__file__), "..", "data", "aksjer.json")
        if not os.path.exists(sti):
            self.skipTest("aksjer.json finnes ikke")
        with open(sti, encoding="utf-8") as f:
            aksjer = json.load(f).get("aksjer", [])
        med = [a for a in aksjer if a.get("utbyttesplitt")]
        for a in med:
            self.assertIsNotNone(utbyttesplitt_stemmer(a),
                                 f"{a['ticker']} har lagret splitt som vakten forkaster")


class TestDelaarMotbevist(unittest.TestCase):
    """Når børsmeldingen motbeviser premisset, må advarselen vike.

    yield_er_delaar() slutter fra «årsraten er mindre enn én utbetaling» at
    raten dekker et delår. Den slutningen forutsetter at utbetalingen var
    ordinær — og begge aksjene vi har splitt for bryter forutsetningen.
    """

    KOG = {"frekvens": "Halvårlig", "utbytte_per_aksje": 4.40,
           "siste_utbytte": 5.70, "utbytte_yield": 1.44, "valuta": "NOK",
           "utbyttesplitt": {"ordinaert": 2.20, "ekstraordinaert": 3.50,
                             "valuta": "NOK"}}
    HUNT = {"frekvens": "Kvartalsvis", "utbytte_per_aksje": 0.30,
            "siste_utbytte": 1.25, "utbytte_yield": 1.73, "valuta": "NOK",
            "utbyttesplitt": {"ordinaert": 0.0, "ekstraordinaert": 1.25,
                              "valuta": "NOK"}}

    @staticmethod
    def _nf(v, d=2):
        return f"{v:.{d}f}".replace(".", ",")

    def test_aarsraten_dekker_den_ordinaere_delen(self):
        # 4,40 er større enn den ordinære delen på 2,20 — yielden er ikke for lav.
        from fetch_stocks import delaar_motbevist
        self.assertTrue(delaar_motbevist(self.KOG))

    def test_hele_utbetalingen_ekstraordinaer_motbeviser_alltid(self):
        from fetch_stocks import delaar_motbevist
        self.assertTrue(delaar_motbevist(self.HUNT))

    def test_uten_splitt_motbevises_ingenting(self):
        from fetch_stocks import delaar_motbevist
        a = dict(self.KOG)
        a.pop("utbyttesplitt")
        self.assertFalse(delaar_motbevist(a))

    def test_aarsrate_under_den_ordinaere_delen_staar_ved_lag(self):
        # Forklarer splitten bare en del av gapet, er premisset intakt.
        from fetch_stocks import delaar_motbevist
        self.assertFalse(delaar_motbevist(dict(self.KOG, utbytte_per_aksje=1.00)))

    def test_boksen_blir_noytral_ikke_advarende(self):
        from fetch_stocks import lag_delaar_varsel
        h = lag_delaar_varsel(self.KOG, self._nf)
        self.assertIn("delaar-noytral", h)
        self.assertIn("Siste utbetaling var større enn årsraten", h)
        self.assertNotIn("kan være for lav", h)
        self.assertIn("3,50 NOK av den var ekstraordinært", h)
        self.assertNotIn("bygger på den ordinære raten", h)

    def test_hele_belopet_formuleres_riktig(self):
        # «0,00 NOK ordinært» ville vært tullete — den grenen må ha egen tekst.
        from fetch_stocks import lag_delaar_varsel
        h = lag_delaar_varsel(self.HUNT, self._nf)
        self.assertIn("hele beløpet", h)
        self.assertNotIn("0,00", h)

    def test_advarselen_staar_naar_ingenting_motbeviser_den(self):
        from fetch_stocks import lag_delaar_varsel
        a = dict(self.KOG)
        a.pop("utbyttesplitt")
        h = lag_delaar_varsel(a, self._nf)
        self.assertIn("kan være for lav", h)
        self.assertNotIn("delaar-noytral", h)

    def test_kortetiketten_droppes_naar_premisset_er_motbevist(self):
        # «usikker» på kortet ved siden av en boks som sier at tallet er greit
        # ville vært den samme selvmotsigelsen, bare delt over to elementer.
        from fetch_stocks import yield_er_delaar, delaar_motbevist
        self.assertTrue(yield_er_delaar(self.KOG))
        self.assertFalse(yield_er_delaar(self.KOG) and not delaar_motbevist(self.KOG))

class TestNewswebUtsteder(unittest.TestCase):
    """NewsWeb arkiverer under børsens navn, ikke vårt.

    Åtte av 155 tickere fikk null NewsWeb-data fram til 17.09.2026 fordi vi
    spurte under vår egen ticker. Målt: vår ticker ga 0 meldinger, børsens
    symbol ga 17–144. Samme rotårsak som DOF-feilen mot Yahoo.
    """

    def test_bruker_euronext_symbolet(self):
        from fetch_stocks import _newsweb_utsteder
        for vår, forventet in [("DOF", "DOFG"), ("ENTR", "ENTRA"), ("SBMO", "MORG"),
                               ("SRHA", "RING"), ("VISTIN", "VISTN"), ("STRONG", "STRO")]:
            self.assertEqual(_newsweb_utsteder(vår), forventet, vår)

    def test_b_aksjer_melder_under_selskapet(self):
        from fetch_stocks import _newsweb_utsteder
        self.assertEqual(_newsweb_utsteder("ODFB"), "ODF")
        self.assertEqual(_newsweb_utsteder("WWIB"), "WWI")

    def test_vanlige_tickere_er_urørt(self):
        from fetch_stocks import _newsweb_utsteder
        for t in ["EQNR", "DNB", "MOWI", "2020", "", "UKJENT"]:
            self.assertEqual(_newsweb_utsteder(t), t, t)

    def test_avledet_av_symbolkartet_ikke_duplisert(self):
        """Kartet skal være eneste kilde — retter noen der, følger dette etter.

        En hardkodet kopi ville råtnet i stillhet, slik EURONEXT_SYMBOL_MAP selv
        gjorde med fem stale oppføringer.
        """
        from fetch_stocks import _newsweb_utsteder, EURONEXT_SYMBOL_MAP, _NEWSWEB_UTSTEDER_EKSTRA
        for eu_symbol, vår_ticker in EURONEXT_SYMBOL_MAP.items():
            self.assertEqual(_newsweb_utsteder(vår_ticker), eu_symbol)
        # De eksplisitte må ikke overlappe med kartet — da ville kartet vunnet
        # og oppføringen vært død vekt.
        self.assertFalse(set(_NEWSWEB_UTSTEDER_EKSTRA) & set(EURONEXT_SYMBOL_MAP.values()))


class TestUtbetalingsmaanederVindu(unittest.TestCase):
    """Bare de tre nyeste årene teller — ellers vinner gamle år over nye.

    WAWI gikk ex i april/november i 2022–2023, men i mars/august i både 2025 og
    2026. Uten vindu sto vi med april/november, fordi de gamle årene hadde to
    treff hver mens de nye hadde ett hver så lenge inneværende år var utelatt.
    """

    def test_omlagt_plan_slaar_gjennom(self):
        from fetch_stocks import _typiske_utbetalingsmaaneder
        wawi = [{"ar": 2022, "maaneder": [4, 11]}, {"ar": 2023, "maaneder": [4, 11]},
                {"ar": 2024, "maaneder": [5, 9]}, {"ar": 2025, "maaneder": [3, 8]},
                {"ar": 2026, "maaneder": [3, 8]}]
        self.assertEqual(_typiske_utbetalingsmaaneder(wawi), [3, 8])

    def test_stabil_betaler_er_urort(self):
        from fetch_stocks import _typiske_utbetalingsmaaneder
        stabil = [{"ar": a, "maaneder": [2, 5, 8, 11]} for a in range(2021, 2027)]
        self.assertEqual(_typiske_utbetalingsmaaneder(stabil), [2, 5, 8, 11])

    def test_enkelt_ekstrautbytte_blir_ikke_typisk(self):
        # Én august gjør ikke august til en utbetalingsmåned.
        from fetch_stocks import _typiske_utbetalingsmaaneder
        h = [{"ar": 2024, "maaneder": [5]}, {"ar": 2025, "maaneder": [5, 8]},
             {"ar": 2026, "maaneder": [5]}]
        self.assertEqual(_typiske_utbetalingsmaaneder(h), [5])

    def test_faller_tilbake_paa_nyeste_aar(self):
        # Ulike måneder hvert år: det siste vi vet slår ingenting.
        from fetch_stocks import _typiske_utbetalingsmaaneder
        h = [{"ar": 2024, "maaneder": [5]}, {"ar": 2025, "maaneder": [8]},
             {"ar": 2026, "maaneder": [4]}]
        self.assertEqual(_typiske_utbetalingsmaaneder(h), [4])

    def test_aar_uten_maanedsdata_filtreres_bort(self):
        from fetch_stocks import _typiske_utbetalingsmaaneder
        h = [{"ar": 2024, "maaneder": [5]}, {"ar": 2025, "maaneder": [5]},
             {"ar": 2026, "maaneder": []}]
        self.assertEqual(_typiske_utbetalingsmaaneder(h), [5])
        self.assertEqual(_typiske_utbetalingsmaaneder([]), [])


class TestProsasplittOgAndel(unittest.TestCase):
    """WAWI-formen: «ordinary dividend of USD 0.37 … extraordinary portion of USD 0.24».

    Parseren kjente bare KOGs seksjonsform og HUNTs klassifiseringsfelt, så
    landets tydeligste utbyttesplitt ga ingenting — «portion» er ikke
    «dividend», og beløpet står rett etter frasen, ikke i et eget felt.
    """

    WAWI_TEKST = ("The dividend is split in an ordinary dividend of USD 0.37 based on "
                  "50% of net profit and an extraordinary portion of USD 0.24, "
                  "totalling USD 0.61 per share.\nDeclared currency: USD")

    def test_prosaformen_parses(self):
        from fetch_stocks import _parse_utbyttesplitt
        r = _parse_utbyttesplitt(self.WAWI_TEKST)
        self.assertEqual(r["ordinaert"], 0.37)
        self.assertEqual(r["ekstraordinaert"], 0.24)
        self.assertEqual(r["valuta"], "USD")

    def test_de_gamle_formene_er_urort(self):
        from fetch_stocks import _parse_utbyttesplitt
        kog = ("Ordinary dividend\nDividend amount: 2.20 per share\n"
               "Declared currency: NOK\nSpecial dividend\nDividend amount: 3.50 per share")
        self.assertEqual(_parse_utbyttesplitt(kog)["ekstraordinaert"], 3.50)
        hunt = "Dividend amount: NOK 1.50\nDividend classification: NOK 1.50 as extraordinary dividend"
        self.assertEqual(_parse_utbyttesplitt(hunt)["ordinaert"], 0.0)

    def test_millionbelop_er_ikke_per_aksje(self):
        """«an extraordinary dividend of USD 100m» er hundre millioner totalt.

        WAWIs melding nevner både totalbeløpet og beløpet per aksje. Første
        forsøk plukket 100 og ville rendret «om lag 100 % var ekstraordinært».
        """
        from fetch_stocks import _parse_utbyttesplitt
        self.assertIsNone(_parse_utbyttesplitt(
            "an ordinary dividend of USD 0.37 and an extraordinary dividend of USD 100m"))

    def test_tallet_trunkeres_ikke_av_vakten(self):
        """Regexen backtracket «100m» til «10», og da så vakten «0m», ikke «m».

        Uten `(?![0-9])` slapp millionbeløpet gjennom som 10.
        """
        from fetch_stocks import _SPLITT_PROSA
        funnet = [m.group(3) for m in _SPLITT_PROSA.finditer(
            "an extraordinary dividend of USD 100m")]
        self.assertEqual(funnet, [])

    def test_desimalkomma_forveksles_ikke_med_skilletegn(self):
        """«USD 0.24,» — kommaet etter er skilletegn, ikke del av tallet.

        Første vakt avviste alle kommaer og mistet dermed 0,24 helt.
        """
        from fetch_stocks import _parse_utbyttesplitt
        r = _parse_utbyttesplitt(
            "an ordinary dividend of USD 0.37 and an extraordinary portion of "
            "USD 0.24, totalling USD 0.61 per share")
        self.assertEqual(r["ekstraordinaert"], 0.24)

    def test_delene_maa_summere_til_oppgitt_total(self):
        from fetch_stocks import _parse_utbyttesplitt
        self.assertIsNone(_parse_utbyttesplitt(
            "an ordinary dividend of USD 0.37 and an extraordinary portion of "
            "USD 5.00, totalling USD 0.61 per share"))

    def test_bare_ordinaert_gir_fortsatt_ingenting(self):
        from fetch_stocks import _parse_utbyttesplitt
        self.assertIsNone(_parse_utbyttesplitt("an ordinary dividend of NOK 6.00 per share"))

    def _wawi(self, **kw):
        a = {"utbytte_yield": 13.46, "siste_utbytte": 5.75, "valuta": "NOK",
             "frekvens": "Halvårlig", "utbytte_per_aksje": 24.26,
             "historiske_utbytter": [{"ar": 2026, "maaneder": [3, 8]}],
             "utbyttesplitt": {"ordinaert": 0.37, "ekstraordinaert": 0.24,
                               "valuta": "USD", "melding_dato": "2026-08-11"}}
        a.update(kw)
        return a

    def test_annen_valuta_godtas_som_forholdstall(self):
        from fetch_stocks import utbyttesplitt_stemmer
        r = utbyttesplitt_stemmer(self._wawi())
        self.assertTrue(r["kun_andel"])
        self.assertEqual(r["ekstraordinaert"], 0.24)

    def test_melding_fra_feil_maaned_avvises(self):
        # Uten sumvakten er månedskoblingen alt som binder meldingen til
        # utbetalingen. Ryker den, skal vi ikke vise noe.
        from fetch_stocks import utbyttesplitt_stemmer
        a = self._wawi()
        a["utbyttesplitt"] = dict(a["utbyttesplitt"], melding_dato="2026-06-02")
        self.assertIsNone(utbyttesplitt_stemmer(a))

    def test_uten_maanedsdata_avvises(self):
        from fetch_stocks import utbyttesplitt_stemmer
        self.assertIsNone(utbyttesplitt_stemmer(self._wawi(historiske_utbytter=[])))

    def test_eksakt_sum_bruker_fortsatt_belop(self):
        from fetch_stocks import utbyttesplitt_stemmer
        kog = {"siste_utbytte": 5.70, "valuta": "NOK",
               "utbyttesplitt": {"ordinaert": 2.20, "ekstraordinaert": 3.50, "valuta": "NOK"}}
        r = utbyttesplitt_stemmer(kog)
        self.assertFalse(r["kun_andel"])

    def test_forholdstall_kan_ikke_motbevise_delaar(self):
        # delaar_motbevist() trekker den ekstraordinære delen fra siste_utbytte.
        # Med beløp i ulike valutaer er den subtraksjonen meningsløs.
        from fetch_stocks import delaar_motbevist
        self.assertFalse(delaar_motbevist(self._wawi()))

    def test_noten_rendres_for_hoy_yield(self):
        from fetch_stocks import lag_ekstraordinaer_note
        nf = lambda v, d=2: f"{v:.{d}f}".replace(".", ",")
        h = lag_ekstraordinaer_note(self._wawi(), nf)
        self.assertIn("39 % av siste utbetaling", h)
        self.assertIn("13,46 %", h)

    def test_ingen_note_naar_delaarsvarselet_gjelder(self):
        from fetch_stocks import lag_ekstraordinaer_note
        nf = lambda v, d=2: f"{v:.{d}f}"
        a = self._wawi(utbytte_per_aksje=1.0, siste_utbytte=5.0)
        self.assertEqual(lag_ekstraordinaer_note(a, nf), "")

    def test_gaten_dekker_hoy_yield(self):
        from fetch_stocks import bor_hente_utbyttesplitt
        self.assertTrue(bor_hente_utbyttesplitt({"utbytte_yield": 13.46}))
        self.assertFalse(bor_hente_utbyttesplitt({"utbytte_yield": 4.0}))
        self.assertFalse(bor_hente_utbyttesplitt({"utbytte_yield": "tull"}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
