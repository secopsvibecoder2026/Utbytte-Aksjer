#!/usr/bin/env python3
"""Tester for fetch_stocks.py.

Kjøres med: python scripts/test_fetch_stocks.py

Testene som krever pandas hoppes over hvis pakken ikke finnes, slik at
suiten fortsatt kan kjøres uten tredjepartspakker.
"""

import datetime
import html
from html.parser import HTMLParser
import inspect
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

    # Neste år fra desember (2026-11-16, var november fra 2026-10-19).
    def test_kalenderaar_tekst(self):
        D = datetime.date
        self.assertEqual(fs.kalenderaar_tekst(D(2026, 11, 15)), "2026")
        self.assertEqual(fs.kalenderaar_tekst(D(2026, 11, 30)), "2026")
        self.assertEqual(fs.kalenderaar_tekst(D(2026, 12, 1)), "2026 og 2027")
        self.assertEqual(fs.kalenderaar_tekst(D(2026, 12, 5)), "2026 og 2027")
        self.assertEqual(fs.kalenderaar_tekst(D(2027, 1, 2)), "2027")

    def test_begge_ar_i_desember_og_tilbake_i_januar(self):
        sti = self._skriv("utbyttekalender/index.html",
                          "<!--AAR-SYNK--><title>Utbyttekalender 2026 – Oslo Børs</title>"
                          '<h1>Utbyttekalender <span id="aar">2026</span></h1>')
        fs.oppdater_aarstall_i_sider(self.rot, i_dag=datetime.date(2026, 11, 15))
        self.assertIn("<title>Utbyttekalender 2026 – Oslo Børs</title>", self._les(sti))
        fs.oppdater_aarstall_i_sider(self.rot, i_dag=datetime.date(2026, 12, 5))
        t = self._les(sti)
        self.assertIn("<title>Utbyttekalender 2026 og 2027 – Oslo Børs</title>", t)
        self.assertIn('<span id="aar">2026 og 2027</span>', t)
        fs.oppdater_aarstall_i_sider(self.rot, i_dag=datetime.date(2026, 12, 6))
        self.assertEqual(t, self._les(sti))
        fs.oppdater_aarstall_i_sider(self.rot, i_dag=datetime.date(2027, 1, 2))
        t = self._les(sti)
        self.assertIn("<title>Utbyttekalender 2027 – Oslo Børs</title>", t)
        self.assertIn('<span id="aar">2027</span>', t)
        self.assertNotIn(" og ", t)


class TestUtbyttekalenderTabell(unittest.TestCase):
    """Hele kalendertabellen som ferdig HTML (2026-11-16)."""

    I_DAG = datetime.date(2026, 11, 16)

    def _aksjer(self):
        return [
            {"ticker": "DOF", "navn": "DOF Group ASA", "sektor": "Energitjenester",
             "frekvens": "Kvartalsvis", "utbytte_yield": 10.9, "markedsverdi_mrd": 30,
             "utbetalinger": [["2025-11-19", 3.5], ["2026-02-25", 3.3], ["2026-08-27", 3.5]],
             "ex_dato": "2026-11-20", "betaling_dato": "2026-11-30",
             "annonsert_utland": {"belop": 0.4, "valuta": "USD", "ex": "2026-11-20"}},
            {"ticker": "GOD", "navn": "Goodtech ASA", "sektor": "Industri", "frekvens": "Årlig",
             "utbytte_yield": 3.3, "markedsverdi_mrd": 1, "utbetalinger": [["2026-11-10", 0.5]],
             "ex_dato": "2026-12-03", "annonsert_utbytte": 2.0, "annonsert_ex": "2026-12-03",
             "ex_forbehold": "2026-12-02"},
            {"ticker": "x<y", "navn": "Ugyldig", "utbetalinger": [["2026-05-01", 1.0]]},
        ]

    def test_rader_rekkefolge_og_status(self):
        rader = fs.kalender_rader(self._aksjer(), self.I_DAG)
        self.assertEqual([(r["ticker"], r["ex"].isoformat()) for r in rader], [
            ("DOF", "2026-11-20"), ("GOD", "2026-12-03"),          # kommende, tidligste først
            ("GOD", "2026-11-10"), ("DOF", "2026-08-27"), ("DOF", "2026-02-25")])  # passerte, nyeste først
        status = {(r["ticker"], r["ex"].isoformat()): r["status"] for r in rader}
        self.assertEqual(status[("GOD", "2026-12-03")], "foreslatt")
        self.assertEqual(status[("DOF", "2026-11-20")], "vedtatt")
        self.assertEqual(status[("DOF", "2026-08-27")], "betalt")
        self.assertEqual(status[("GOD", "2026-11-10")], "vedtatt")   # under 31 dager, ingen betalingsdato
        dof = rader[0]
        self.assertEqual((dof["belop"], dof["valuta"], dof["kjop"].isoformat()), (0.4, "USD", "2026-11-19"))

    def test_fjoraret_er_ikke_med(self):
        rader = fs.kalender_rader(self._aksjer(), self.I_DAG)
        self.assertNotIn("2025-11-19", [r["ex"].isoformat() for r in rader])

    def test_alle_rader_i_html_og_valuta_vises(self):
        rader = fs.kalender_rader(self._aksjer(), self.I_DAG)
        html = fs.lag_kalender_kropp(rader, self.I_DAG)
        self.assertEqual(html.count("<tr data-ticker="), len(rader))
        self.assertIn("0,40\u00a0USD", html)
        self.assertIn('<h1 class="side-h1">Utbyttekalender 2026</h1>', html)
        self.assertIn("kjøp senest tor. 19. nov", html)
        self.assertIn("Foreslått", html)

    def test_tittel_og_meta(self):
        self.assertEqual(fs.kalender_tittel(self.I_DAG),
                         "Utbyttekalender 2026: ex-datoer, beløp og siste kjøpsdag")
        self.assertLessEqual(len(fs.kalender_tittel(datetime.date(2026, 12, 5))), 70)
        meta = fs.kalender_meta(self.I_DAG)
        self.assertTrue(meta.startswith("Alle ex-datoer på Oslo Børs i 2026 med beløp per aksje"), meta)
        self.assertLessEqual(len(meta), 155)

    def test_meta_har_ingen_tall_som_flytter_seg(self):
        """24.11.2026: Google viste «9 ex-datoer de neste 30 dagene – neste:
        Höegh Autoliners 23. nov.» dagen etter at datoen var passert. En
        beskrivelse leses dager etter at den ble skrevet, så den bærer bare
        årstallet."""
        self.assertEqual(fs.kalender_meta(datetime.date(2026, 11, 20)),
                         fs.kalender_meta(datetime.date(2026, 11, 25)))
        self.assertEqual(re.findall(r"\d+", fs.kalender_meta(self.I_DAG)), ["2026"])
        desember = fs.kalender_meta(datetime.date(2026, 12, 5))
        self.assertEqual(re.findall(r"\d+", desember), ["2026", "2027"])
        self.assertLessEqual(len(desember), 155)

    def test_smaa_belop_mister_ikke_sifre(self):
        self.assertEqual(fs._kal_belop(0.0342, "USD"), "0,0342\u00a0USD")
        self.assertEqual(fs._kal_belop(4.5, "NOK"), "4,50\u00a0NOK")
        self.assertEqual(fs._kal_belop(None, None), "—")

    def test_markorene_fylles(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as rot:
            os.makedirs(os.path.join(rot, "utbyttekalender"))
            sti = os.path.join(rot, "utbyttekalender", "index.html")
            with open(sti, "w", encoding="utf-8") as f:
                f.write("<head><!--KAL-HODE:START--><!--KAL-HODE:SLUTT--></head>"
                        "<main><!--KAL:START--><!--KAL:SLUTT--></main>")
            self.assertTrue(fs.oppdater_utbyttekalender(self._aksjer(), rot, i_dag=self.I_DAG, hentet=""))
            t = open(sti, encoding="utf-8").read()
            self.assertIn("<title>Utbyttekalender 2026", t)
            self.assertIn('"BreadcrumbList"', t)
            self.assertEqual(t.count("<tr data-ticker="), 5)
            self.assertFalse(fs.oppdater_utbyttekalender(self._aksjer(), rot, i_dag=self.I_DAG, hentet=""))
            ics = open(os.path.join(rot, "utbyttekalender", "exday.ics"), encoding="utf-8", newline="").read()
            self.assertEqual(ics.count("BEGIN:VEVENT"), 5)

    def test_ics(self):
        rader = fs.kalender_rader(self._aksjer(), self.I_DAG)
        ics = fs.lag_kalender_ics(rader, self.I_DAG)
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n"))
        self.assertEqual(ics.count("BEGIN:VEVENT"), len(rader))
        self.assertIn("UID:DOF-20261120@exday.no", ics)
        self.assertIn("DTSTART;VALUE=DATE:20261120\r\nDTEND;VALUE=DATE:20261121", ics)
        self.assertIn("TRIGGER:-PT39H", ics)        # kl. 09 dagen før siste kjøpsdag 19.11
        self.assertIn("0\\,40 USD", ics)            # aldri omregnet til kroner
        self.assertIn("foreslått\\, ikke vedtatt", ics.replace("\r\n ", ""))
        for linje in ics.split("\r\n"):
            self.assertLessEqual(len(linje.encode("utf-8")), 75, linje)
        lang = fs._ics_brett("DESCRIPTION:" + "æ" * 100)
        self.assertEqual(lang.replace("\r\n ", ""), "DESCRIPTION:" + "æ" * 100)


class TestKalenderMaaneder(unittest.TestCase):
    """Månedsoversikten i /utbyttekalender/ (2026-10-19)."""

    def _a(self, ticker, mnd, **felt):
        return dict({"ticker": ticker, "navn": f"{ticker} ASA", "utbytte_yield": 4.0,
                     "markedsverdi_mrd": 10, "utbetalingsmaaneder": mnd}, **felt)

    def test_hvem_som_er_med(self):
        aksjer = [self._a("STOR", [3, 3], markedsverdi_mrd=500),
                  self._a("LITEN", [3], markedsverdi_mrd=1),
                  self._a("STOPPET", [3], utbytte_yield=0),
                  self._a("KJOPT", [3], hendelse={"type": "oppkjop", "tekst": "Bud."}),
                  self._a("MULIG", [3], hendelse={"type": "mulig_fusjon", "tekst": "Intensjon."}),
                  self._a("x<y", [3])]
        mars = [a["ticker"] for a in fs.ex_maaneder(aksjer)[3]]
        self.assertEqual(mars, ["STOR", "MULIG", "LITEN"])

    def test_travleste_i_kalenderrekkefolge(self):
        per = {m: [] for m in range(1, 13)}
        per[5] = [1] * 49
        per[3] = [1] * 38
        per[4] = [1] * 29
        per[2] = [1] * 16
        self.assertEqual(fs._travleste_maaneder(per), "mars (38), april (29) og mai (49)")

    def test_blokk_overskrift_folger_datoen(self):
        D = datetime.date
        aksjer = [self._a("AAA", [5])]
        self.assertIn("ex-utbytte i 2027?", fs.lag_exmnd_blokk(aksjer, D(2026, 11, 2)))
        self.assertIn("har ikke annonsert ex-datoene for 2027", fs.lag_exmnd_blokk(aksjer, D(2026, 11, 2)))
        self.assertIn("ex-utbytte i 2027?", fs.lag_exmnd_blokk(aksjer, D(2027, 3, 1)))
        self.assertIn("Når i året går aksjene ex-utbytte?", fs.lag_exmnd_blokk(aksjer, D(2027, 8, 1)))

    def test_vis_alle_og_escaping(self):
        aksjer = [self._a(f"A{i}", [4], markedsverdi_mrd=100 - i) for i in range(11)]
        aksjer.append(self._a("ESC", [6], navn="A & <B> ASA"))
        blokk = fs.lag_exmnd_blokk(aksjer, datetime.date(2026, 11, 2))
        self.assertIn("Vis alle 11", blokk)
        self.assertIn("· 11 aksjer", blokk)
        self.assertIn("· 1 aksje<", blokk)
        self.assertIn("A &amp; &lt;B&gt;", blokk)
        self.assertNotIn("<B>", blokk)
        self.assertIn("Ingen aksjer har pleid å gå ex i denne måneden.", blokk)

    def test_oppdater_er_idempotent(self):
        with tempfile.TemporaryDirectory() as rot:
            os.makedirs(os.path.join(rot, "utbyttekalender"))
            sti = os.path.join(rot, "utbyttekalender", "index.html")
            with open(sti, "w", encoding="utf-8") as f:
                f.write("<main>\n    <!--EXMND:START-->\n    <!--EXMND:SLUTT-->\n</main>\n")
            aksjer = [self._a("AAA", [5])]
            dag = datetime.date(2026, 11, 2)
            self.assertTrue(fs.oppdater_kalender_maaneder(aksjer, rot, dag))
            self.assertFalse(fs.oppdater_kalender_maaneder(aksjer, rot, dag))
            with open(sti, encoding="utf-8") as f:
                self.assertIn('href="/aksjer/AAA/"', f.read())
            with open(sti, "w", encoding="utf-8") as f:
                f.write("<main></main>")
            self.assertFalse(fs.oppdater_kalender_maaneder(aksjer, rot, dag))

    def test_kalendersiden_har_markorene(self):
        rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(rot, "utbyttekalender", "index.html"), encoding="utf-8") as f:
            t = f.read()
        self.assertRegex(t, r"(?s)<!--EXMND:START-->.*<!--EXMND:SLUTT-->")
        # Tittel og årstall skrives nå av oppdater_utbyttekalender(), ikke AAR-SYNK.
        self.assertRegex(t, r"(?s)<!--KAL-HODE:START-->.*<!--KAL-HODE:SLUTT-->")
        self.assertRegex(t, r"(?s)<!--KAL:START-->.*<!--KAL:SLUTT-->")


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
                           ("Golden Ocean Group", "Golden Ocean"),
                           # «SoftwareOne AG» er et navn selskapet ikke har (2026-10-19).
                           ("SoftwareOne Holding AG", "SoftwareOne"),
                           ("Subsea 7 SA", "Subsea 7")]:
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

    def test_meta_kaller_ikke_arsraten_siste_utbytte(self):
        m = fs._lag_meta_beskrivelse("Okeanis Eco Tankers Corp.", "OET", 10.2, None, 91.22,
                                     4.4, "NOK", self.I_DAG)
        self.assertNotIn("siste utbytte", m.lower())
        self.assertIn("årlig utbytte er 91,22 NOK", m.lower().replace("nok", "NOK"))

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


class TestBelopITittel(unittest.TestCase):
    """Beløp per aksje og ex-dato i tittel, meta, H1 og ingress (2026-11-18).

    Søk med et konkret beløp hadde 10–12 % klikkrate i Search Console, mens
    «frontline utbytte» hadde 1,1 % mot en tittel med bare yield.
    """

    I_DAG = "2026-11-18"

    def rad(self, **kw):
        a = {"ticker": "OKEA", "navn": "OKEA ASA", "pris": 45.85, "utbytte_yield": 4.36,
             "utbytte_per_aksje": 2.0, "frekvens": "Årlig", "ex_dato": None}
        a.update(kw)
        return a

    def test_kunngjort_belop_med_ex_dato(self):
        a = self.rad(ex_dato="2026-12-02", annonsert_ex="2026-12-02", annonsert_utbytte=2.0)
        t = fs.lag_aksje_tittel(a, self.I_DAG)
        self.assertEqual(t, "OKEA utbytte 2026: 2,00 kr per aksje – ex-dato 2. des")
        m = fs.lag_aksje_meta(a, self.I_DAG)
        self.assertTrue(m.startswith("OKEA betaler 2,00 kr per aksje med ex-dato 2. des 2026."), m)
        self.assertIn("børsslutt 1. des", m)
        self.assertLessEqual(len(m), 155)
        self.assertEqual(fs.lag_aksje_h1(a, self.I_DAG), "OKEA utbytte 2026: 2,00 kr per aksje")

    def test_utenlandsk_valuta_vises_som_kunngjort(self):
        a = self.rad(ticker="DOF", navn="DOF Group ASA", frekvens="Kvartalsvis",
                     utbytte_per_aksje=13.86, ex_dato="2026-11-20",
                     annonsert_utland={"belop": 0.4, "valuta": "USD", "ex": "2026-11-20"})
        self.assertIn("0,40 USD per aksje – ex-dato 20. nov", fs.lag_aksje_tittel(a, self.I_DAG))
        ing = fs.lag_aksje_ingress(a, self.I_DAG)
        self.assertIn("kunngjort i USD", ing)
        # Kvartalsvis: årsraten står ved siden av, så kurshodets «13,86» ikke
        # ser ut til å motsi 0,40 USD.
        self.assertIn("Årlig utbytte er 13,86 kr", ing)

    def test_uten_ex_dato_brukes_arsraten_som_yielden_bygger_paa(self):
        a = self.rad(ticker="DNB", navn="DNB Bank ASA", pris=325.7, utbytte_yield=5.53,
                     utbytte_per_aksje=18.0, siste_utbytte=99.0)
        t = fs.lag_aksje_tittel(a, self.I_DAG)
        self.assertIn("18,00 kr per aksje", t)
        self.assertNotIn("99", t)
        self.assertNotIn("i året", t)  # årlig betaler: per utbetaling og per år er det samme
        k = self.rad(ticker="VAR", navn="Vår Energi ASA", frekvens="Kvartalsvis",
                     utbytte_per_aksje=5.47, pris=47.68)
        self.assertIn("5,47 kr per aksje i året", fs.lag_aksje_tittel(k, self.I_DAG))
        self.assertTrue(fs.lag_aksje_h1(k, self.I_DAG).endswith("i året"))
        self.assertIn("i året", fs.lag_aksje_meta(a, self.I_DAG))

    def test_ex_dato_uten_belop_gir_dagens_tittel(self):
        a = self.rad(ex_dato="2026-11-20", annonsert_ex=None, annonsert_utbytte=None)
        t = fs.lag_aksje_tittel(a, self.I_DAG)
        self.assertNotIn("per aksje", t)
        self.assertIn("ex-dato", t)
        self.assertIn("beløpet er ikke kunngjort", fs.lag_aksje_ingress(a, self.I_DAG))

    def test_passert_ex_dato_brukes_ikke(self):
        a = self.rad(ex_dato="2026-11-17", annonsert_ex="2026-11-17", annonsert_utbytte=1.37)
        t = fs.lag_aksje_tittel(a, self.I_DAG)
        self.assertNotIn("ex-dato", t)
        self.assertIn("2,00 kr per aksje", t)

    def test_hendelse_gir_ingen_belop(self):
        a = self.rad(hendelse={"type": "avvikling", "dato": "2026-08-05", "melding": "679057",
                               "tekst": "Styret har vedtatt å selge flåten."})
        self.assertIsNone(fs.utbytte_i_tittel(a, self.I_DAG))
        self.assertNotIn("per aksje", fs.lag_aksje_tittel(a, self.I_DAG))
        self.assertEqual(fs.lag_aksje_ingress(a, self.I_DAG), "")

    def test_foreslatt_utbytte_sier_det(self):
        a = self.rad(ex_dato="2026-12-02", annonsert_ex="2026-12-02", annonsert_utbytte=1.15,
                     ex_forbehold="2026-11-25")
        self.assertIn("foreslått 1,15 kr", fs.lag_aksje_tittel(a, self.I_DAG))
        self.assertIn("har foreslått", fs.lag_aksje_meta(a, self.I_DAG))
        self.assertIn("ikke vedtatt", fs.lag_aksje_ingress(a, self.I_DAG))

    def test_smaa_belop_mister_ikke_sifre(self):
        self.assertEqual(fs._belop_tekst(0.0342, "USD"), "0,0342 USD")
        self.assertEqual(fs._belop_tekst(0.375), "0,375 kr")
        self.assertEqual(fs._belop_tekst(3.7889), "3,79 kr")

    def test_kjopsdag_er_forrige_borsdag(self):
        # Ex-dato mandag 23. nov: siste dag med rett er fredag 20. nov.
        a = self.rad(ex_dato="2026-11-23", annonsert_ex="2026-11-23", annonsert_utbytte=2.0)
        self.assertIn("børsslutt 20. nov", fs.lag_aksje_meta(a, self.I_DAG))

    def test_yield_ryker_foran_lengden_men_ex_dato_blir(self):
        lang = "Paratus Energy Services Ltd"
        y = fs.lag_aksje_tittel(self.rad(ticker="PLSV", navn=lang), self.I_DAG)
        self.assertNotIn("yield", y)
        self.assertLessEqual(len(y), fs.TITTEL_MAKS + 5)
        e = fs.lag_aksje_tittel(self.rad(ticker="EQNR", navn="Equinor ASA", ex_dato="2027-02-15",
                                         annonsert_utland={"belop": 0.39, "valuta": "USD",
                                                           "ex": "2027-02-15"}), self.I_DAG)
        self.assertIn("ex-dato 15. feb 2027 | EQNR", e)
        self.assertLessEqual(len(e), fs.TITTEL_TAK)

    def test_hele_katalogen(self):
        """Ingen tittel over taket, ingen meta over 155, og beløpet i titlen
        er det samme som i H1."""
        rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(rot, "data", "aksjer.json"), encoding="utf-8") as f:
            aksjer = json.load(f)["aksjer"]
        for a in aksjer:
            t = fs.lag_aksje_tittel(a, self.I_DAG)
            self.assertLessEqual(len(fs.lag_aksje_meta(a, self.I_DAG)), 155, a["ticker"])
            if fs.utbytte_i_tittel(a, self.I_DAG):
                h1 = fs.lag_aksje_h1(a, self.I_DAG)
                self.assertIn(h1.split(": ", 1)[1], t, a["ticker"])


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
        # 2020 Bulkers og SATS er begge overstyrt manuelt. 2020 betalte
        # månedlig til skipene var solgt i april 2026; den nye virksomheten
        # har ikke betalt noe ennå (se TestLopendeUtbytteFra).
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("2020"), "Uregelmessig")
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
        self.assertIn("10,10\u00a0%", html)

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
        self.assertIn("39\u00a0% av siste utbetaling", h)
        self.assertIn("13,46\u00a0%", h)

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


class TestUtbetalingsaar(unittest.TestCase):
    """«Utbyttet gjennom året» må ikke motsi frekvensen på samme side."""

    @staticmethod
    def _aksje(frekvens, maaneder):
        return {
            "navn": "Testselskap ASA",
            "ticker": "TEST",
            "frekvens": frekvens,
            "utbetalingsmaaneder": maaneder,
            "utbytte_per_aksje": 12.0,
        }

    def test_antall_og_belop_naar_listen_stemmer(self):
        from fetch_stocks import _lag_utbetalingsaar
        h = _lag_utbetalingsaar(self._aksje("Halvårlig", [3, 8]))
        self.assertIn("betaler ut to ganger i året", h)
        self.assertIn("6,00 kroner per aksje hver gang", h)

    def test_ingen_antallspaastand_naar_listen_er_kortere(self):
        # DOF: kvartalsvis, men bare to måneder går igjen. «2 ganger i året»
        # ville motsagt nøkkeltalltabellen, og 12/2 er dobbelt så mye som
        # selskapet faktisk betaler per gang.
        from fetch_stocks import _lag_utbetalingsaar
        h = _lag_utbetalingsaar(self._aksje("Kvartalsvis", [5, 8]))
        self.assertIn("Ex-datoene til Testselskap ASA har de siste årene", h)
        self.assertIn("mai og august", h)
        self.assertNotIn("ganger i året", h)
        self.assertNotIn("hver gang", h)

    def test_ukjent_frekvens_gir_ingen_antallspaastand(self):
        from fetch_stocks import _lag_utbetalingsaar
        h = _lag_utbetalingsaar(self._aksje("Uregelmessig", [5, 8]))
        self.assertNotIn("ganger i året", h)

    def test_seksjonen_uteblir_for_en_enkelt_maaned(self):
        from fetch_stocks import _lag_utbetalingsaar
        self.assertEqual(_lag_utbetalingsaar(self._aksje("Årlig", [5])), "")



class TestNoramMaanedsmelding(unittest.TestCase):
    """NorAm kunngjør utdelingen i «Monthly rig update and key information for …».

    Tittelen har verken «dividend» eller «distribution», så månedsmeldingen ble
    aldri lest, og siden hadde ingen kunngjort ex-dato for NorAm før ex-dagen
    (24.11.2026). Meldingen under er 686141.
    """

    TITTEL = "NorAm Drilling AS - Monthly rig update and key information for November 2026"
    TEKST = ("Oslo, Norway, November 10, 2026\n\nCommercial update:\n\n"
             "In October 2026, the Company had 11 out of 11 rigs employed.\n\n"
             "Cash distribution:\n\nThe Board of Directors today approved a monthly cash distribution "
             "of approximately USD 2.0 million based on free cash flow for October 2026. The distribution "
             "will be made from the Company's Contributed Surplus account which consists of previously "
             "paid in share premium.\n\nKey information:\n\nDistribution amount: USD 0.045 per share\n\n"
             "Declared currency: USD. Payment to shares registered with Euronext VPS will be distributed in NOK\n\n"
             "Date of approval: November 10, 2026\n\nLast day including right: November 17, 2026\n\n"
             "Ex-date: November 18, 2026\n\nRecord date: November 19, 2026\n\n"
             "Payment date: On or about November 27, 2026\n")

    def test_tittelen_treffer_filteret(self):
        from fetch_stocks import _UTBYTTE_TITTEL_RE
        for t in (self.TITTEL, self.TITTEL.replace(" - ", " – ").replace("November", "September")):
            self.assertTrue(_UTBYTTE_TITTEL_RE.search(t), t)

    def test_filteret_tar_ikke_med_andre_manedsmeldinger(self):
        from fetch_stocks import _UTBYTTE_TITTEL_RE
        for t in ("NorAm Drilling AS - Monthly rig update for November 2026",
                  "Monthly update on production",
                  "Key information relating to the share capital increase"):
            self.assertFalse(_UTBYTTE_TITTEL_RE.search(t), t)

    def test_meldingen_gir_ex_dato_betaling_og_dollarbelop(self):
        from fetch_stocks import _parse_utbetalinger
        ut = _parse_utbetalinger(self.TEKST)
        self.assertEqual(len(ut), 1)
        self.assertEqual((ut[0]["ex_dato"], ut[0]["betaling_dato"]), ("2026-11-18", "2026-11-27"))
        self.assertEqual((ut[0]["belop"], ut[0]["valuta"]), (0.045, "USD"))

    def test_rapportkoen_kjenner_tittelen(self):
        import kvartalsrapport as kr
        self.assertTrue(kr._UTBYTTEMELDING.search(self.TITTEL))
        self.assertFalse(kr._UTBYTTEMELDING.search("NorAm Drilling AS - Monthly rig update for November 2026"))


class TestAkvaHendelse(unittest.TestCase):
    """AKVA-teksten sto på 92 % og «akseptperioden løper til 20. november» etter at
    perioden var over. Meldingen 687133 (23.11.2026) sier 98,82 %, godkjenning fra
    Konkurransetilsynet 13. november, og at bare godkjenning i Storbritannia mangler."""

    def test_teksten_folger_meldingen(self):
        h = fs.HENDELSE["AKVA"]
        self.assertEqual((h["type"], h["melding"]), ("oppkjop", "687133"))
        for ledd in ("98,82 prosent", "Akseptperioden gikk ut 20. november 2026",
                     "Konkurransetilsynet godkjente 13. november", "britiske myndigheter"):
            self.assertIn(ledd, h["tekst"])
        for gammelt in ("92 prosent", "løper til"):
            self.assertNotIn(gammelt, h["tekst"])
        self.assertTrue(fs.gyldig_hendelse(h))


class TestToSifferAar(unittest.TestCase):
    """MPC Container Ships skriver «Ex-date: 21.09.26», året med to sifre.

    Parseren leste bare fire sifre, så ex-dato, siste kjøpsdag, betalingsdato og
    beløp manglet fra børsmeldingen for MPCC (funnet 24.11.2026, dagen før
    kvartalsrapporten). Meldingen under er meldingen 680785 fra 26.08.2026.
    """

    MPCC = ("Oslo, Norway, 26 August 2026 - Reference is made to the declaration of\n"
            "dividends in the quarterly results for Q2 2026 published by MPC Container\n"
            "Ships ASA at 07:00 CET on 26 August 2026.\n\n"
            "Dividend amount: USD 0.04 per share.\n\n"
            "Declared currency: USD. The distribution will be made in NOK.\n\n"
            "Last day including right: 18.09.26\n"
            "Ex-date: 21.09.26\n"
            "Record date: 22.09.26\n"
            "Payment date: 28.09.26 (on or about)\n"
            "Date of board resolution: 25.08.26\n")

    def test_mpcc_melding_gir_ex_dato_og_betaling(self):
        from fetch_stocks import _parse_ex_dato
        self.assertEqual(_parse_ex_dato(self.MPCC), ("2026-09-21", "2026-09-28"))

    def test_mpcc_melding_gir_utbetaling_med_belop(self):
        from fetch_stocks import _parse_utbetalinger
        ut = _parse_utbetalinger(self.MPCC)
        self.assertEqual(len(ut), 1)
        self.assertEqual(ut[0]["ex_dato"], "2026-09-21")
        self.assertEqual(ut[0]["betaling_dato"], "2026-09-28")
        self.assertEqual((ut[0]["belop"], ut[0]["valuta"]), (0.04, "USD"))

    def test_godkjenningsdato_med_to_sifre(self):
        from fetch_stocks import _parse_utbetalinger
        tekst = ("Dividend amount: NOK 2.00\nDate of approval: 05.12.26\n"
                 "Ex-date: 15.12.26\nPayment date: 22.12.26\n")
        ut = _parse_utbetalinger(tekst)
        self.assertEqual(ut[0]["godkjenning_dato"], "2026-12-05")
        self.assertEqual(ut[0]["ex_dato"], "2026-12-15")

    def test_fire_siffer_er_uendret(self):
        from fetch_stocks import _parse_ex_dato
        self.assertEqual(_parse_ex_dato("Ex-date: 23.06.2026\nPayment date: 30.06.2026"),
                         ("2026-06-23", "2026-06-30"))
        self.assertEqual(_parse_ex_dato("Ex-date: 23/06/2026\nPayment date: 30/06/2026"),
                         ("2026-06-23", "2026-06-30"))

    def test_tre_siffer_leses_ikke_som_to(self):
        from fetch_stocks import _parse_ex_dato
        self.assertEqual(_parse_ex_dato("Ex-date: 21.09.202\n"), (None, None))

    def test_ugyldig_dato_med_to_siffer_gir_ingenting(self):
        from fetch_stocks import _parse_ex_dato
        self.assertEqual(_parse_ex_dato("Ex-date: 31.02.26\n"), (None, None))


class TestParseExDato(unittest.TestCase):
    """Ex-dato for Oslo Børs fra «Key information relating to the cash dividend».

    Hver variant her er hentet fra en ekte melding. EQNR-tilfellet er grunnen
    til at funksjonen finnes: vi viste New York-datoen, tre dager for sent.
    """

    def _p(self, tekst):
        from fetch_stocks import _parse_ex_dato
        return _parse_ex_dato(tekst)

    def test_kog_enkel_form(self):
        self.assertEqual(self._p("Ex-date: 14 April 2026\nPayment date: 22 April 2026"),
                         ("2026-04-14", "2026-04-22"))

    def test_eqnr_oslo_foran_new_york(self):
        t = ("Ex-date Oslo Børs: 13 November 2026\n"
             "Ex-date New York Stock Exchange: 16 November 2026\n"
             "Payment date: 25 November 2026")
        self.assertEqual(self._p(t), ("2026-11-13", "2026-11-25"))

    def test_eqnr_rekkefolgen_avgjor_ikke(self):
        t = ("Ex-date New York Stock Exchange: 16 November 2026\n"
             "Ex-date Oslo Børs: 13 November 2026")
        self.assertEqual(self._p(t)[0], "2026-11-13")

    def test_bare_utenlandsk_borsdato_gir_ingenting(self):
        self.assertEqual(self._p("Ex-date NYSE: 16 November 2026"), (None, None))

    def test_wawi_amerikansk_format_og_oa(self):
        t = "Ex-date: August 26, 2026\nPayment date: o/a September 16, 2026"
        self.assertEqual(self._p(t), ("2026-08-26", "2026-09-16"))

    def test_dnb_from_foran_betalingsdato(self):
        t = "Ex-date: 22 April 2026\nPayment date: from 30 April 2026"
        self.assertEqual(self._p(t), ("2026-04-22", "2026-04-30"))

    def test_mellomrom_i_stedet_for_bindestrek(self):
        self.assertEqual(self._p("Ex date: 3 May 2026")[0], "2026-05-03")

    def test_forkortede_maaneder(self):
        self.assertEqual(self._p("Ex-date: 7 Apr 2026")[0], "2026-04-07")
        self.assertEqual(self._p("Ex-date: 7 Sept. 2026")[0], "2026-09-07")

    def test_ord_som_bare_begynner_som_en_maaned(self):
        self.assertEqual(self._p("Ex-date: 14 Aprilis 2026"), (None, None))

    def test_umulig_dato(self):
        self.assertEqual(self._p("Ex-date: 31 February 2026"), (None, None))

    def test_salmar_numerisk_dato(self):
        t = ("Ex-date: 23.06.2026\nRecord date: 24.06.2026\n"
             "Payment date: On or about 06.07.2026")
        self.assertEqual(self._p(t), ("2026-06-23", "2026-07-06"))

    def test_stst_on_or_about(self):
        t = "Ex-date: 7 August 2026\nPayment date: on or about 1 September 2026"
        self.assertEqual(self._p(t), ("2026-08-07", "2026-09-01"))

    def test_cmbto_felles_dato_for_to_borser(self):
        t = "Ex-date on Euronext Belgium and Euronext Oslo Børs: expected on 14 April 2026"
        self.assertEqual(self._p(t)[0], "2026-04-14")

    def test_oslo_og_nyse_i_samme_merkelapp_beholdes(self):
        self.assertEqual(self._p("Ex-date Oslo Børs and NYSE: 3 May 2026")[0], "2026-05-03")

    def test_uten_arstall_gjettes_ikke(self):
        # AFK skriver «Ex-date: 13 May». Å gjette året er verre enn ingenting.
        self.assertEqual(self._p("Ex-date: 13 May"), (None, None))

    def test_numerisk_umulig_dato(self):
        self.assertEqual(self._p("Ex-date: 31.02.2026"), (None, None))
        self.assertEqual(self._p("Ex-date: 12.13.2026"), (None, None))

    def test_betalingsdato_for_ex_dato_forkastes(self):
        t = "Ex-date: 14 April 2026\nPayment date: 2 April 2026"
        self.assertEqual(self._p(t), ("2026-04-14", None))


class TestHentNewswebExDato(unittest.TestCase):
    """Utvalget av meldinger — uten nett, med en falsk NewsWeb."""

    def _kjor(self, meldinger, i_dag="2026-09-24"):
        import fetch_stocks as fs
        bodies = {m["messageId"]: m.pop("body") for m in meldinger}
        hentet = []

        def falsk_get(url, timeout=10):
            mid = int(url.rsplit("=", 1)[1])
            hentet.append(mid)
            return {"data": {"message": {"body": bodies[mid]}}}

        gml = (fs._newsweb_get, dict(fs._NEWSWEB_LISTE), fs._NEWSWEB_API)
        fs._newsweb_get = falsk_get
        fs._NEWSWEB_API = "http://x"
        fs._NEWSWEB_LISTE[fs._newsweb_utsteder("TEST")] = meldinger
        try:
            r = fs.hent_newsweb_ex_dato("TEST", datetime.date.fromisoformat(i_dag))
        finally:
            fs._newsweb_get = gml[0]
            fs._NEWSWEB_LISTE.clear(); fs._NEWSWEB_LISTE.update(gml[1])
            fs._NEWSWEB_API = gml[2]
        return r, hentet

    @staticmethod
    def _m(mid, publ, body, tittel="Key information relating to the cash dividend"):
        return {"messageId": mid, "publishedTime": publ + "T07:00:00Z", "title": tittel, "body": body}

    def test_kommende_ex_dato_returneres(self):
        r, _ = self._kjor([self._m(1, "2026-07-22", "Ex-date Oslo Børs: 13 November 2026")])
        self.assertEqual(r["ex_dato"], "2026-11-13")

    def test_dividend_information_leses_som_utbyttemelding(self):
        # BW Offshore kaller meldingen «Dividend information» (687343, 25.11.2026).
        # Uten «key information» i tittelen ble den aldri lest.
        body = ("Cash dividend amount: USD 0.0625 per share\nDeclared currency: USD\n"
                "Date of approval: 24 November 2026\nLast day inclusive: 27 November 2026\n"
                "Ex-date: 30 November 2026\nRecord date: 1 December 2026\n"
                "Dividend payment date: On or about 9 December 2026\n")
        r, _ = self._kjor([self._m(687343, "2026-11-25", body, tittel="BW Offshore: Dividend information")],
                          i_dag="2026-11-25")
        self.assertEqual((r["ex_dato"], r["betaling_dato"]), ("2026-11-30", "2026-12-09"))
        self.assertEqual((r["belop"], r["valuta"]), (0.0625, "USD"))

    def test_andre_dividend_titler_leses_fortsatt_ikke(self):
        r, hentet = self._kjor([self._m(5, "2026-11-25", "Ex-date: 30 November 2026",
                                        tittel="Ex dividend today")], i_dag="2026-11-25")
        self.assertIsNone(r)
        self.assertEqual(hentet, [])

    def test_passert_ex_dato_gir_ingenting_og_stopper(self):
        r, hentet = self._kjor([
            self._m(2, "2026-08-11", "Ex-date: August 26, 2026"),
            self._m(1, "2026-02-01", "Ex-date: 13 November 2026"),
        ])
        self.assertIsNone(r)
        self.assertEqual(hentet, [2], "eldre meldinger gjelder eldre utbytter og skal ikke hentes")

    def test_for_gammel_melding_hentes_ikke(self):
        r, hentet = self._kjor([self._m(1, "2025-10-01", "Ex-date: 13 November 2026")])
        self.assertIsNone(r)
        self.assertEqual(hentet, [])

    def test_andre_meldinger_ignoreres(self):
        r, hentet = self._kjor([
            self._m(3, "2026-09-01", "Ex-date: 1 December 2026", tittel="Q2 2026 results"),
            self._m(1, "2026-07-22", "Ex-date: 13 November 2026"),
        ])
        self.assertEqual(r["ex_dato"], "2026-11-13")
        self.assertEqual(hentet, [1])

    def test_naermeste_kommende_vinner_over_nyeste_melding(self):
        # Equinor 30.10.2026: tredje kvartal (ex 15.02.2027) meldt 28.10,
        # andre kvartal (ex 13.11.2026) meldt 22.07. Siden viste februar.
        r, hentet = self._kjor([
            self._m(33, "2026-10-28", "Ex-date Oslo Børs: 15 February 2027\nPayment date: 26 February 2027"),
            self._m(32, "2026-07-22", "Ex-date Oslo Børs: 13 November 2026\nPayment date: 25 November 2026"),
            self._m(31, "2026-04-29", "Ex-date Oslo Børs: 13 August 2026"),
        ], i_dag="2026-10-30")
        self.assertEqual(r["ex_dato"], "2026-11-13")
        self.assertEqual(r["betaling_dato"], "2026-11-25")
        self.assertEqual(hentet, [33, 32, 31], "stopper ved første melding der alt er passert")

    def test_nettverksfeil_gir_none(self):
        import fetch_stocks as fs
        gml = fs._newsweb_meldinger
        fs._newsweb_meldinger = lambda t: (_ for _ in ()).throw(OSError("nede"))
        try:
            self.assertIsNone(fs.hent_newsweb_ex_dato("TEST"))
        finally:
            fs._newsweb_meldinger = gml



class TestBetaltSomArsrate(unittest.TestCase):
    """Betalt siste 12 mnd som årsrate (2026-10-07). Tallene er fra datasettet."""

    I_DAG = datetime.date(2026, 10, 7)

    def _yara(self, **k):
        a = {"ticker": "YAR", "pris": 410.30, "frekvens": "Årlig", "utbytte_per_aksje": 5.0,
             "utbytte_yield": 1.22, "utbytte_12m": 22.0, "utbytte_12m_antall": 1,
             "utbytte_per_ar": {"2021": 40.0, "2022": 40.0, "2023": 55.0, "2024": 5.0, "2025": 5.0}}
        a.update(k)
        return a

    def test_yara_er_kandidat(self):
        self.assertTrue(fs.betalt_kan_bli_arsrate(self._yara(), self.I_DAG))

    def test_antall_maa_stemme_med_frekvensen(self):
        # HUNT: fem utbetalinger i et kvartalsvis vindu er en ekstra utbetaling.
        a = self._yara(frekvens="Kvartalsvis", utbytte_12m_antall=5)
        self.assertFalse(fs.betalt_kan_bli_arsrate(a, self.I_DAG))
        # Og færre er et halvt år.
        self.assertFalse(fs.betalt_kan_bli_arsrate(self._yara(utbytte_12m_antall=0), self.I_DAG))

    def test_uregelmessig_bruker_det_betalte(self):
        # WEST: to utbetalinger etter to år uten, ingen rytme å telle mot.
        # Yahoo ga 1,39 (én utbetaling); betalt siste 12 mnd er 2,60.
        a = self._yara(ticker="WEST", pris=24.0, frekvens="Uregelmessig", utbytte_per_aksje=1.39,
                       utbytte_12m=2.60, utbytte_12m_antall=2,
                       utbytte_per_ar={"2021": 0.0, "2022": 28.32, "2023": 3.0, "2024": 0.0, "2025": 0.0})
        self.assertTrue(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_uregelmessig_uten_utbetaling_gir_ingen_regel(self):
        a = self._yara(frekvens="Uregelmessig", utbytte_12m=0.0, utbytte_12m_antall=0)
        self.assertFalse(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_engangsutbytte_som_skjuler_kutt(self):
        # KOG etter 23.11.2026: én utbetaling på 5,70 (2,20 ordinært + 3,50
        # særutbytte, 665028) mot vist 4,40. Summen avviker 29,5 %, så den
        # gamle porten spurte aldri NewsWeb.
        kog = self._yara(ticker="KOG", pris=326.7, utbytte_per_aksje=4.4, utbytte_yield=1.35,
                         utbytte_12m=5.7, utbytte_12m_antall=1,
                         utbytte_12m_liste=[{"ex_dato": "2026-04-14", "belop": 5.7}],
                         utbytte_per_ar={"2023": 2.4, "2024": 2.8, "2025": 4.4})
        i_dag = datetime.date(2026, 11, 24)
        self.assertFalse(fs.betalt_kan_bli_arsrate(kog, i_dag))
        self.assertTrue(fs.betalt_kan_bli_arsrate(kog, i_dag, min_avvik=0))
        self.assertTrue(fs.stor_enkeltutbetaling(kog))
        # Uten særutbyttet slår regelen inn.
        uten = dict(kog, utbytte_12m=2.2)
        self.assertTrue(fs.betalt_kan_bli_arsrate(uten, i_dag))

    def test_jevne_utbetalinger_er_ikke_store(self):
        # Fire like kvartaler, og en årlig betaler som betalte omtrent raten.
        kv = {"frekvens": "Kvartalsvis", "utbytte_per_aksje": 4.0,
              "utbytte_12m_liste": [{"belop": 1.0}] * 3 + [{"belop": 1.2}]}
        self.assertFalse(fs.stor_enkeltutbetaling(kv))
        self.assertFalse(fs.stor_enkeltutbetaling(
            {"frekvens": "Årlig", "utbytte_per_aksje": 5.0, "utbytte_12m_liste": [{"belop": 6.0}]}))
        self.assertFalse(fs.stor_enkeltutbetaling({"frekvens": "Årlig", "utbytte_per_aksje": 0}))

    def test_lite_avvik_beholder_tallet(self):
        self.assertFalse(fs.betalt_kan_bli_arsrate(self._yara(utbytte_per_aksje=20.0), self.I_DAG))

    def test_virker_begge_veier(self):
        # BOR: viste 1,00, betalte 0,50.
        a = self._yara(pris=17.2, utbytte_per_aksje=1.0, utbytte_12m=0.5,
                       utbytte_per_ar={"2025": 0.8})
        self.assertTrue(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_stst_maales_mot_betalt(self):
        # 7,15 vist mot 5,17 betalt er 38 % over det betalte. Delt på det
        # viste ble det 27,7 %, og STST sto på 17,40 % (18.10.2026).
        a = self._yara(ticker="STST", pris=41.10, frekvens="Kvartalsvis", utbytte_per_aksje=7.15,
                       utbytte_12m=5.1705, utbytte_12m_antall=4,
                       utbytte_per_ar={"2024": 10.9835, "2025": 12.7422})
        self.assertTrue(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_avviket_er_likt_begge_veier(self):
        for vist, betalt, ventet in ((1.25, 1.0, False), (1.0, 1.25, False),
                                     (1.31, 1.0, True), (1.0, 1.31, True)):
            a = self._yara(utbytte_per_aksje=vist, utbytte_12m=betalt, utbytte_per_ar={})
            self.assertEqual(fs.betalt_kan_bli_arsrate(a, self.I_DAG), ventet, (vist, betalt))

    def test_gsf_engangsutdeling_stoppes_av_historikken(self):
        a = self._yara(ticker="GSF", pris=23.40, utbytte_per_aksje=8.34, utbytte_12m=35.64 / 2,
                       utbytte_per_ar={"2022": 3.0, "2023": 4.5, "2024": 1.75, "2025": 0.0})
        self.assertFalse(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_mer_enn_hele_kursen_stoppes(self):
        a = self._yara(pris=23.40, utbytte_12m=35.64, utbytte_per_ar={})
        self.assertFalse(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_heving_over_mange_utbetalinger_er_ingen_engangsutdeling(self):
        # HSHP: tolv månedlige utbetalinger på til sammen 17,15 kr mot 5,37
        # i 2025. Den største er 15 % av summen, så det er en heving, og
        # vakten holdt siden på 3,53 % (20.10.2026).
        liste = [{"ex_dato": f"2026-{m:02d}-15", "belop": b} for m, b in
                 enumerate([0.66, 0.94, 1.23, 0.57, 0.57, 0.57,
                            1.41, 2.07, 2.07, 2.07, 2.36, 2.64], start=1)]
        a = self._yara(ticker="HSHP", pris=152.0, frekvens="Månedlig", utbytte_12m_antall=12,
                       utbytte_per_aksje=5.37, utbytte_12m=17.15, utbytte_12m_liste=liste,
                       utbytte_per_ar={"2024": 4.52, "2025": 5.37})
        self.assertTrue(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_en_dominerende_utbetaling_stoppes_fortsatt(self):
        # 2020 Bulkers: salgsprovenyet er 94 % av det betalte.
        liste = [{"ex_dato": "2026-04-29", "belop": 130.05}] + \
                [{"ex_dato": f"2026-0{m}-20", "belop": 1.66} for m in (1, 2, 3, 5, 6)]
        a = self._yara(ticker="2020", pris=8.68, frekvens="Uregelmessig", utbytte_12m_antall=6,
                       utbytte_per_aksje=0.0, utbytte_12m=138.34, utbytte_12m_liste=liste,
                       utbytte_per_ar={"2024": 33.74, "2025": 13.76})
        self.assertFalse(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_ny_betaler_maales_ikke_mot_sitt_forste_aar(self):
        # BNOR begynte i 2025; 180 kr mot 54 kr i det første, halve året.
        a = self._yara(ticker="BNOR", pris=570.0, frekvens="Kvartalsvis", utbytte_12m_antall=4,
                       utbytte_per_aksje=66.82, utbytte_12m=180.58,
                       utbytte_per_ar={"2021": 0.0, "2025": 54.24})
        self.assertTrue(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_kunngjort_kommende_utbytte_vinner(self):
        a = self._yara(annonsert_utbytte=24.0, annonsert_ex="2026-11-01")
        self.assertFalse(fs.betalt_kan_bli_arsrate(a, self.I_DAG))
        # Et forslag som ikke er vedtatt, er ingen grunn til å vente.
        a["ex_forbehold"] = "2026-10-20"
        self.assertTrue(fs.betalt_kan_bli_arsrate(a, self.I_DAG))

    def test_bruk_setter_begge_tallene_og_kilden(self):
        a = self._yara()
        fs.bruk_betalt_som_arsrate(a)
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"], a["arsrate_kilde"]),
                         (22.0, 5.36, "betalt_12m"))


class TestEkstraordinaerIVindu(unittest.TestCase):
    """Teksten i selskapets melding skiller Yara fra KOG og HUNT."""

    def test_formuleringer_som_teller(self):
        for t in ["Special dividend\nDividend amount: 3.50",            # KOG
                  "NOK 1.50 as extraordinary dividend",                 # HUNT
                  "an additional dividend of NOK 2.00",
                  "foreslår et ekstraordinært utbytte på 5 kroner",
                  "styret har vedtatt tilleggsutbytte"]:
            self.assertTrue(fs._har_ekstraordinaer(t), t)

    def test_generalforsamling_og_nektelse_teller_ikke(self):
        for t in ["subject to approval by the extraordinary general meeting",
                  "Notice of Extraordinary General Meeting",
                  "The Board does not propose any extraordinary dividend",
                  "Dividend amount: NOK 22.00\nThe dividend is an ordinary dividend"]:
            self.assertFalse(fs._har_ekstraordinaer(t), t)

    def _kjor(self, meldinger, tekster, i_dag=datetime.date(2026, 10, 7)):
        gml = fs._newsweb_meldinger, fs._newsweb_tekst
        fs._newsweb_meldinger = meldinger
        fs._newsweb_tekst = lambda mid: tekster.get(mid, "")
        try:
            return fs.ekstraordinaer_i_vindu("X", i_dag)
        finally:
            fs._newsweb_meldinger, fs._newsweb_tekst = gml

    def test_ordinaer_melding_gir_false(self):
        m = lambda t: [{"publishedTime": "2026-02-11T07:00", "title": "Key information relating to the cash dividend", "messageId": 1}]
        self.assertIs(self._kjor(m, {1: "Dividend amount: NOK 22.00"}), False)

    def test_spesialutbytte_gir_true(self):
        m = lambda t: [{"publishedTime": "2026-02-11T07:00", "title": "Key information relating to the cash dividend", "messageId": 1}]
        self.assertIs(self._kjor(m, {1: "Ordinary dividend 2.20. Special dividend 3.50."}), True)

    def test_bare_gamle_meldinger_er_ukjent(self):
        # Ingen utbyttemelding i perioden: vi vet ikke, og skal ikke gjette.
        m = lambda t: [{"publishedTime": "2024-01-01T07:00", "title": "Key information relating to the cash dividend", "messageId": 1}]
        self.assertIs(self._kjor(m, {}), fs.UKJENT)

    def test_nettverksfeil_er_ukjent(self):
        def feil(t):
            raise OSError("nede")
        self.assertIs(self._kjor(feil, {}), fs.UKJENT)


class TestVelgArsrate(unittest.TestCase):
    """Vakten var blind for kutt. Tallene er ekte serier fra 24.09.2026."""

    def _v(self, *a):
        from fetch_stocks import velg_arsrate
        return velg_arsrate(*a)

    # ── Kutt: trailing 12 mnd skal vinne ─────────────────────────────────
    def test_salmar_arlig_kutt(self):
        # NOK 22 i 2025, NOK 10 i 2026 — bekreftet mot SalMars melding.
        self.assertEqual(self._v(22.0, 10.0, 1, "Årlig"), 10.0)

    def test_stst_kvartalsvis_kutt(self):
        self.assertAlmostEqual(self._v(12.757, 5.168, 4, "Kvartalsvis"), 5.168)

    def test_wawi_halvarlig_kutt(self):
        self.assertAlmostEqual(self._v(24.26, 15.377, 2, "Halvårlig"), 15.377)

    # ── Enveis: kan aldri heve ───────────────────────────────────────────
    def test_ekstraordinaer_i_vinduet_heves_ikke(self):
        # GSF-type: trailing inneholder salgsprovenyet og er høyere enn
        # fjoråret. Å bruke den ville gitt 116 % yield.
        self.assertEqual(self._v(4.0, 39.0, 3, "Kvartalsvis"), 4.0)

    def test_like_tall_endrer_ingenting(self):
        self.assertEqual(self._v(8.0, 8.0, 4, "Kvartalsvis"), 8.0)

    # ── Vinduet må være fullt ────────────────────────────────────────────
    def test_halvfullt_vindu_brukes_ikke(self):
        # Halvårlig betaler, septemberutbetalingen falt rett utenfor vinduet.
        # Trailing er da en halv årsrate — ikke et kutt.
        self.assertEqual(self._v(10.0, 5.0, 1, "Halvårlig"), 10.0)

    def test_kvartalsvis_med_tre_i_vinduet_brukes_ikke(self):
        self.assertEqual(self._v(8.0, 6.0, 3, "Kvartalsvis"), 8.0)

    def test_ukjent_frekvens_brukes_ikke(self):
        self.assertEqual(self._v(8.0, 2.0, 1, "Uregelmessig"), 8.0)
        self.assertEqual(self._v(8.0, 2.0, 1, None), 8.0)

    # ── Uten fjorår: som før ─────────────────────────────────────────────
    def test_uten_fjorar_brukes_trailing(self):
        # SWON etter byttet til .OL: bare ett utbytte, i 2026.
        self.assertEqual(self._v(0.0, 1.72, 1, "Årlig"), 1.72)

    def test_tom_trailing_gir_fjorar(self):
        self.assertEqual(self._v(6.0, 0.0, 0, "Årlig"), 6.0)



# Felles tilfeller — de samme står i tests/ui.test.js, så malen og appen
# ikke kan drive fra hverandre.
KID_BETALT = {"pris": 119.4, "utbytte_yield": 8.38, "utbytte_12m": 5.0, "utbytte_12m_antall": 2,
              "utbytte_per_ar": {"2021": 4.0, "2022": 6.5, "2023": 5.75, "2024": 6.5, "2025": 7.5},
              "utbytte_forste_ar": 2010}
NY_BETALER = {"pris": 50.0, "utbytte_yield": 4.0, "utbytte_12m": 2.0, "utbytte_12m_antall": 2,
              "utbytte_per_ar": {"2021": 0.0, "2022": 0.0, "2023": 0.0, "2024": 1.0, "2025": 2.0},
              "utbytte_forste_ar": 2024}
STST_BETALT = {"pris": 41.1, "utbytte_yield": 17.4, "utbytte_12m": 5.1705, "utbytte_12m_antall": 4,
               "utbytte_per_ar": {"2021": 0.0, "2022": 0.0, "2023": 0.0, "2024": 10.9835, "2025": 12.7422},
               "utbytte_forste_ar": 2024}


class TestUtbetalingerMedDato(unittest.TestCase):
    """Utbetalingene appen regner mottatt utbytte fra (2026-11-10)."""

    def _s(self, par):
        import pandas as pd
        return pd.Series([v for _, v in par], index=pd.to_datetime([d for d, _ in par]))

    def test_seks_aar_eldste_forst_og_bare_gyldige_belop(self):
        s = self._s([("2026-11-06", 2.7683), ("2020-05-10", 1.0), ("2020-12-01", 0.5),
                     ("2026-05-20", 0.9169), ("2025-11-25", float("nan")), ("2025-08-01", 0.0)])
        self.assertEqual(fs.utbetalinger_med_dato(s, datetime.date(2026, 11, 10)),
                         [["2020-12-01", 0.5], ["2026-05-20", 0.9169], ["2026-11-06", 2.7683]])

    def test_framtidig_dato_og_tom_serie(self):
        s = self._s([("2026-12-02", 2.0)])
        self.assertEqual(fs.utbetalinger_med_dato(s, datetime.date(2026, 11, 10)), [])
        self.assertEqual(fs.utbetalinger_med_dato(None, datetime.date(2026, 11, 10)), [])

    def test_hent_aksje_skriver_feltet(self):
        import inspect
        kilde = inspect.getsource(fs.hent_aksje)
        self.assertIn('"utbetalinger": utbetalinger', kilde)


class TestBetaltFraSerie(unittest.TestCase):
    def _s(self, par):
        import pandas as pd
        return pd.Series([v for _, v in par], index=pd.to_datetime([d for d, _ in par]))

    def test_kid(self):
        from fetch_stocks import betalt_fra_serie
        s = self._s([("2023-05-12", 3.0), ("2023-11-16", 2.75), ("2024-05-21", 3.5), ("2024-11-19", 3.0),
                     ("2025-05-13", 5.0), ("2025-11-18", 2.5), ("2026-05-12", 2.5)])
        tot, n, per_ar, forste = betalt_fra_serie(s, datetime.date(2026, 9, 24))
        self.assertEqual((tot, n, forste), (5.0, 2, 2023))
        self.assertEqual(per_ar, {"2021": 0.0, "2022": 0.0, "2023": 5.75, "2024": 6.5, "2025": 7.5})

    def test_stoppet_utbytte_gir_null(self):
        # REACH: siste utbetaling mai 2025.
        from fetch_stocks import betalt_fra_serie
        tot, n, _, _ = betalt_fra_serie(self._s([("2025-05-30", 0.42)]), datetime.date(2026, 9, 24))
        self.assertEqual((tot, n), (0.0, 0))

    def test_tom_serie(self):
        import pandas as pd
        from fetch_stocks import betalt_fra_serie
        self.assertEqual(betalt_fra_serie(pd.Series(dtype=float), datetime.date(2026, 9, 24)), (0.0, 0, {}, None))


class TestUtbyttePerioder(unittest.TestCase):
    def test_kid_alle_perioder(self):
        from fetch_stocks import utbytte_perioder
        r = {x["periode"]: x for x in utbytte_perioder(KID_BETALT)}
        self.assertEqual(r["12m"]["belop"], 5.0)
        self.assertEqual(r["12m"]["yield"], 4.19)
        self.assertEqual((r["1"]["belop"], r["1"]["fra"], r["1"]["til"]), (7.5, 2025, 2025))
        self.assertEqual(r["3"]["belop"], 6.58)
        self.assertEqual((r["5"]["belop"], r["5"]["ar_brukt"]), (6.05, 5))   # 30,25 / 5

    def test_ny_betaler_teller_ikke_ar_for_forste_utbytte_som_null(self):
        from fetch_stocks import utbytte_perioder
        r = {x["periode"]: x for x in utbytte_perioder(NY_BETALER)}
        self.assertEqual(r["5"]["belop"], 1.5, "snitt av 2024–2025, ikke av fem år med tre nuller")
        self.assertEqual((r["5"]["ar_brukt"], r["5"]["ar_onsket"], r["5"]["fra"]), (2, 5, 2024))

    def test_over_to_ganger_kursen_gir_ingen_yield(self):
        from fetch_stocks import utbytte_perioder
        a = dict(KID_BETALT, pris=2.0)   # 2020 Bulkers-form
        self.assertIsNone(utbytte_perioder(a)[0]["yield"])

    def test_mangler_feltene(self):
        from fetch_stocks import utbytte_perioder
        self.assertEqual(utbytte_perioder({"pris": 10}), [])


class TestVistOverBetalt(unittest.TestCase):
    def test_kid_flagges(self):
        from fetch_stocks import vist_over_betalt
        self.assertEqual(vist_over_betalt(KID_BETALT), (8.38, 4.19))

    def test_stoppet_utbytte_flagges(self):
        from fetch_stocks import vist_over_betalt
        a = dict(KID_BETALT, utbytte_12m=0.0)
        self.assertEqual(vist_over_betalt(a), (8.38, 0.0))

    def test_under_betalt_flagges_ikke(self):
        # Engangsutdeling i vinduet: vist er lavere enn betalt, og det er riktig.
        from fetch_stocks import vist_over_betalt
        self.assertIsNone(vist_over_betalt(dict(KID_BETALT, utbytte_yield=2.0)))

    def test_lite_avvik_flagges_ikke(self):
        from fetch_stocks import vist_over_betalt
        self.assertIsNone(vist_over_betalt(dict(KID_BETALT, utbytte_yield=4.9)))   # 0,71 pp

    def test_tretti_prosent_over_det_betalte(self):
        # STST: 17,40 vist, 12,58 betalt. 38 % over det betalte, men bare
        # 27,7 % av det viste, og Sjekk 10 tidde til 18.10.2026.
        from fetch_stocks import vist_over_betalt
        self.assertEqual(vist_over_betalt(STST_BETALT), (17.4, 12.58))
        # 25 % over det betalte er under grensen.
        self.assertIsNone(vist_over_betalt(dict(STST_BETALT, utbytte_yield=15.73)))

    def test_samsvar_med_valider_data(self):
        import fetch_stocks, valider_data
        tilfeller = [KID_BETALT, NY_BETALER, STST_BETALT, dict(KID_BETALT, utbytte_12m=0.0),
                     dict(KID_BETALT, utbytte_yield=4.9), {"pris": 10}]
        sti = os.path.join(os.path.dirname(__file__), "..", "data", "aksjer.json")
        tilfeller += json.load(open(sti, encoding="utf-8"))["aksjer"]
        for a in tilfeller:
            self.assertEqual(fetch_stocks.vist_over_betalt(a), valider_data.vist_over_betalt(a), a.get("ticker"))



class TestUtbytterekke(unittest.TestCase):
    """«År på rad» fra rekken, ikke fra antall år med utbytte (2026-09-26).

    Tallkontrollen fant påstanden feil på 76 av 155 sider. Tilfellene under
    er de virkelige: DNB uten utbytte i 2009 og 2020, Scatec som sluttet i 2023.
    """
    I_DAG = datetime.date(2026, 9, 26)
    # DNB slik Yahoo har den: 2003–2008, 2010–2019, 2021–2026.
    DNB = {"ar_med_utbytte": 22,
           "utbytteaar": list(range(2003, 2009)) + list(range(2010, 2020)) + list(range(2021, 2027))}

    def test_dnb_rekke_starter_etter_pandemien(self):
        from fetch_stocks import utbytterekke
        r = utbytterekke(self.DNB, self.I_DAG)
        self.assertEqual((r["rad"], r["fra"], r["totalt"], r["brutt"]), (6, 2021, 22, True))

    def test_arlig_betaler_teller_fra_i_fjor(self):
        # Betaler i november: i september er årets utbytte ikke kommet ennå.
        from fetch_stocks import utbytterekke
        r = utbytterekke({"utbytteaar": [2022, 2023, 2024, 2025]}, self.I_DAG)
        self.assertEqual(r["rad"], 4)

    def test_stoppet_utbytte_gir_null(self):
        from fetch_stocks import utbytterekke
        r = utbytterekke({"utbytteaar": list(range(2015, 2024))}, self.I_DAG)
        self.assertEqual((r["rad"], r["siste"], r["brutt"]), (0, 2023, True))

    def test_uten_felt_ingen_rekke(self):
        from fetch_stocks import utbytterekke
        self.assertIsNone(utbytterekke({"ar_med_utbytte": 21}))

    def test_ingen_pastand_uten_felt(self):
        # Før første fulle henting finnes ikke utbytteaar. Da skal antallet
        # aldri skrives som en rekke.
        from fetch_stocks import _lag_utbytterekken, _driver_selskapsledd
        a = {"ticker": "DNB", "navn": "DNB Bank ASA", "ar_med_utbytte": 21}
        self.assertEqual(_lag_utbytterekken(a), "")
        self.assertNotIn("på rad", _driver_selskapsledd(a, "Finans") or "")

    def test_dnb_far_ikke_krisesetningen(self):
        from fetch_stocks import _lag_utbytterekken, _driver_selskapsledd
        a = dict(self.DNB, ticker="DNB", navn="DNB Bank ASA")
        tekst = _driver_selskapsledd(a, "Finans") or ""
        self.assertNotIn("finanskrisen", tekst)
        self.assertNotIn("21 år på rad", tekst)
        self.assertEqual(_lag_utbytterekken(a), "")  # 6 år er under terskelen

    def test_lang_rekke_far_krisesetningen(self):
        from fetch_stocks import _lag_utbytterekken
        a = {"ticker": "X", "navn": "X ASA", "utbytteaar": list(range(2000, 2027))}
        tekst = _lag_utbytterekken(a)
        self.assertIn("27 år på rad", tekst)
        self.assertIn("finanskrisen", tekst)

    def test_stoppet_utbytte_sies_rett_ut(self):
        from fetch_stocks import _driver_selskapsledd
        a = {"ticker": "SCATC", "navn": "Scatec ASA", "ar_med_utbytte": 9,
             "utbytteaar": list(range(2015, 2024))}
        tekst = _driver_selskapsledd(a, "Fornybar energi") or ""
        self.assertIn("ikke siden 2023", tekst)
        self.assertNotIn("på rad", tekst)

    def test_beskrivelsen_bruker_rekken(self):
        from utvid_beskrivelser import lag_beskrivelse
        t = {"ticker": "DNB", "navn": "DNB Bank ASA", "sektor": "Finans",
             "bors": "Oslo Børs", "beskrivelse": ""}
        tekst = lag_beskrivelse(t, dict(self.DNB, frekvens="Årlig", utbytte_yield=5.0))
        self.assertNotIn("22 år på rad", tekst)
        uten = lag_beskrivelse(t, {"ar_med_utbytte": 22, "frekvens": "Årlig", "utbytte_yield": 5.0})
        self.assertNotIn("på rad", uten)

    def test_samsvar_med_datasettet(self):
        # Når feltet finnes, må antallet stemme med listen det bygger på.
        sti = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aksjer.json")
        with open(sti, encoding="utf-8") as f:
            data = json.load(f)
        rader = data["aksjer"] if isinstance(data, dict) else data
        med = [a for a in rader if isinstance(a.get("utbytteaar"), list)]
        if not med:
            self.skipTest("utbytteaar finnes ikke før første fulle henting")
        for a in med:
            self.assertEqual(len(a["utbytteaar"]), a.get("ar_med_utbytte"), a["ticker"])


class TestNfKurs(unittest.TestCase):
    def test_norsk_tusenskille(self):
        from fetch_stocks import _nf_kurs
        self.assertEqual(_nf_kurs(1434), "1\u00a0434,00")   # Aker: ikke «1,434»
        self.assertEqual(_nf_kurs(3.37), "3,37")             # ALNG: ikke «3»
        self.assertEqual(_nf_kurs(None), "—")


class TestNewswebBelopOverDnb(unittest.TestCase):
    """DNB merket DOFs USD 0,40 som kroner, og børsmeldingen rettet det ikke (2026-11-15)."""

    def _dof(self):
        # Slik raden så ut etter DNB-steget: 0,40 × 4 = 1,60 kr, 1,26 %.
        return {"ticker": "DOF", "pris": 127.1, "utbytte_per_aksje": 1.6, "utbytte_yield": 1.26,
                "annonsert_utbytte": 0.4, "annonsert_ex": "2026-11-20",
                "_for_dnb": {"utbytte_per_aksje": 13.86, "utbytte_yield": 10.9}}

    def test_usd_i_meldingen_fjerner_dnb_belopet(self):
        from fetch_stocks import bruk_newsweb_belop
        a = self._dof()
        nw = {"ex_dato": "2026-11-20", "belop": 0.4, "valuta": "USD"}
        self.assertTrue(bruk_newsweb_belop(a, nw))
        self.assertNotIn("annonsert_utbytte", a)
        self.assertNotIn("annonsert_ex", a)
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"]), (13.86, 10.9))
        self.assertNotIn("_for_dnb", a)

    def test_melding_uten_belop_bekrefter_ikke_dnb(self):
        # ENH: «USD 25.0 million (USD 0.0342 / NOK 0.32 per share)» gir ikke noe beløp.
        from fetch_stocks import bruk_newsweb_belop
        a = self._dof()
        self.assertTrue(bruk_newsweb_belop(a, {"ex_dato": "2026-11-20", "belop": None, "valuta": None}))
        self.assertNotIn("annonsert_utbytte", a)

    def test_kroner_i_meldingen_brukes(self):
        from fetch_stocks import bruk_newsweb_belop
        a = {"annonsert_utbytte": 1.37, "annonsert_ex": "2026-11-17"}
        self.assertFalse(bruk_newsweb_belop(a, {"ex_dato": "2026-11-17", "belop": 1.368, "valuta": "NOK"}))
        self.assertEqual(a["annonsert_utbytte"], 1.368)

    def test_annen_ex_dato_lar_dnb_vaere(self):
        # Meldingen gjelder en senere utbetaling; DNB-beløpet hører til en annen dato.
        from fetch_stocks import bruk_newsweb_belop
        a = self._dof()
        self.assertFalse(bruk_newsweb_belop(a, {"ex_dato": "2027-02-20", "belop": 0.4, "valuta": "USD"}))
        self.assertEqual(a["annonsert_utbytte"], 0.4)

    def test_vistin_per_share_i_parentes(self):
        from fetch_stocks import neste_utbetaling
        tekst = ("Dividend amount (per share): NOK 0.50\nDeclared currency: NOK\n"
                 "Ex-date: 24 November 2026\nRecord date: 25 November 2026\n"
                 "Payment date: 3 December 2026\n")
        u = neste_utbetaling(tekst, datetime.date(2026, 11, 15))
        self.assertEqual((u["belop"], u["valuta"]), (0.5, "NOK"))


class TestUtbetalingerIMelding(unittest.TestCase):
    """Flere utbetalinger i én melding, og forbehold om godkjenning (2026-09-26).

    Tekstene er forkortet fra de virkelige meldingene på NewsWeb.
    """
    I_DAG = datetime.date(2026, 9, 26)
    TEL = ("Dividend amount: NOK 5.00 per share\nEx-date: 20 May 2026\n"
           "Record date: 21 May 2026\nPayment date: 2 June 2026\nDate of approval: 19 May 2026\n"
           "Dividend amount: NOK 4.70 per share\nEx-date: 15 October 2026\n"
           "Record date: 16 October 2026\nPayment date: 27 October 2026\nDate of approval:19 May 2026\n"
           "Key information relating to the proposed cash dividend")
    PUBLI = ("Tranche 1: \nDividend amount: SEK 0.25 per share.\nDate of approval: 26 June 2026.\n"
             "Ex-date: 29 June 2026. \nPayment date: On or about 3 July 2026 for shares\n"
             "Tranche 2: \nDividend amount: SEK 0.25 per share. \nDate of approval: 26 June 2026.\n"
             "Ex-date: 29 September 2026. \nPayment date: On or about 5 October 2026 for shares\n"
             "Tranche 3: \nDividend amount: SEK 0.25 per share. \nEx-date: 29 December 2026\n")
    HUNT = ("Dividend amount: NOK 1.50 per share\nEx-date: 29 September 2026\n"
            "Record date: 30 September 2026\nPayment date: Expected on or about 7 October 2026\n"
            "Date of approval: Expected on 28 September 2026\n"
            "Other: Please note that the cash dividend is subject to approval by the EGM")
    GOD = ("The Board of Directors will propose to the Extraordinary General Meeting a "
           "supplemental dividend of NOK 2.00 per share.\nSubject to approval by the "
           "Extraordinary General Meeting\nDividend amount: 2.00\nEx date: 16 October 2026\n"
           "Payment date: 28 October 2026\nDate of approval: 15 October 2026")

    def test_telenor_andre_del(self):
        from fetch_stocks import neste_utbetaling
        u = neste_utbetaling(self.TEL, self.I_DAG)
        self.assertEqual((u["ex_dato"], u["betaling_dato"]), ("2026-10-15", "2026-10-27"))
        # «proposed» i teksten, men godkjent 19. mai: vedtatt.
        self.assertIsNone(u["ex_forbehold"])

    def test_publi_neste_kvartal(self):
        from fetch_stocks import neste_utbetaling
        u = neste_utbetaling(self.PUBLI, self.I_DAG)
        self.assertEqual((u["ex_dato"], u["betaling_dato"]), ("2026-09-29", "2026-10-05"))

    def test_hunt_forventet_betalingsdato_og_forbehold(self):
        from fetch_stocks import neste_utbetaling
        u = neste_utbetaling(self.HUNT, self.I_DAG)
        self.assertEqual(u["betaling_dato"], "2026-10-07")   # «Expected on or about»
        self.assertEqual(u["ex_forbehold"], "2026-09-28")

    def test_god_ikke_vedtatt(self):
        from fetch_stocks import neste_utbetaling
        self.assertEqual(neste_utbetaling(self.GOD, self.I_DAG)["ex_forbehold"], "2026-10-15")

    def test_alt_passert_gir_none(self):
        from fetch_stocks import neste_utbetaling
        self.assertIsNone(neste_utbetaling(self.TEL, datetime.date(2026, 11, 1)))

    def test_forbeholdet_utloper_ved_bygging(self):
        from fetch_stocks import ex_forbehold_gjelder
        a = {"ex_dato": "2026-10-16", "ex_forbehold": "2026-10-15"}
        self.assertEqual(ex_forbehold_gjelder(a, datetime.date(2026, 9, 26)), "2026-10-15")
        self.assertIsNone(ex_forbehold_gjelder(a, datetime.date(2026, 10, 16)))
        self.assertIsNone(ex_forbehold_gjelder({"ex_dato": "2026-10-16"}, datetime.date(2026, 9, 26)))

    def test_enkel_melding_uendret(self):
        # Meldinger med én utbetaling skal gi det samme som før.
        from fetch_stocks import _parse_utbetalinger, _parse_ex_dato
        tekst = "Ex-date Oslo Børs: 13 November 2026\nPayment date: 25 November 2026"
        u = _parse_utbetalinger(tekst)
        self.assertEqual(len(u), 1)
        self.assertEqual((u[0]["ex_dato"], u[0]["betaling_dato"]), _parse_ex_dato(tekst))


class TestKapitalTilbake(unittest.TestCase):
    """Tilbakebetaling av innbetalt kapital — utdrag fra ekte børsmeldinger."""

    STST = ("Ex-date: 7 August 2026 Record date: 10 August 2026 Payment date: on or about "
            "1 September 2026 Date of approval: 4 August 2026 Other information: The "
            "distribution will constitute a repayment of the Company's paid-in capital.")
    HUNT_DELT = ("Dividend amount: NOK 0.58 per share Declared currency: NOK Dividend "
                 "classification: NOK 0.50 as repayment of paid-in capital and NOK 0.08 as "
                 "ordinary dividend Last day including right: 25 March 2026 Ex-date: 26 March 2026")
    HUNT_HEL = ("Dividend amount: NOK 0.40 per share Declared currency: NOK Dividend "
                "classification: Repayment of paid-in capital Ex-date: 2 March 2026")
    BOR = ("For Norwegian tax purposes, the distribution shall be in the form of repayment of "
           "paid-in equity. Dividend amount: NOK 0.50 per share")
    PEN = "Distributions will be paid in NOK The cash distribution will be paid as a return of paid in capital"
    ENH = ("The approved cash distribution of USD 25.0 million will be distributed as a "
           "repayment of paid in capital.")
    SATS = ("For Norwegian tax-purposes, the dividend is considered repayment of paid-in "
            "capital. Dividend amount: NOK 0.72 per share")
    ORDINAER = ("Dividend amount: NOK 5.00 per share Declared currency: NOK Ex-date: "
                "13 November 2026 Payment date: 25 November 2026")

    def test_hele_utbetalingen(self):
        for tekst in (self.STST, self.HUNT_HEL, self.BOR, self.PEN, self.ENH, self.SATS):
            self.assertEqual(fs._parse_kapitaltilbake(tekst), 1.0, tekst[:40])

    def test_delt_utbetaling_gir_andel(self):
        self.assertAlmostEqual(fs._parse_kapitaltilbake(self.HUNT_DELT), 0.5 / 0.58, places=3)

    def test_delt_uten_total_gir_intet_svar(self):
        # En delt utbetaling er ikke det samme som en hel — uten totalen gjetter vi ikke.
        tekst = "NOK 0.50 as repayment of paid-in capital and NOK 0.08 as ordinary dividend"
        self.assertIsNone(fs._parse_kapitaltilbake(tekst))

    def test_ordinaert_utbytte_gir_none(self):
        self.assertIsNone(fs._parse_kapitaltilbake(self.ORDINAER))
        self.assertIsNone(fs._parse_kapitaltilbake(""))

    def test_nektende_formulering_teller_ikke(self):
        tekst = "The dividend will not constitute a repayment of paid-in capital."
        self.assertIsNone(fs._parse_kapitaltilbake(tekst))

    def _med_meldinger(self, meldinger, tekster, feil=False):
        gml_liste, gml_tekst = fs._newsweb_meldinger, fs._newsweb_tekst

        def liste(_t):
            if feil:
                raise OSError("nett nede")
            return meldinger
        fs._newsweb_meldinger = liste
        fs._newsweb_tekst = lambda mid: tekster[mid]
        try:
            return fs.hent_kapitaltilbake("X", i_dag=datetime.date(2026, 10, 3))
        finally:
            fs._newsweb_meldinger, fs._newsweb_tekst = gml_liste, gml_tekst

    def test_nyeste_melding_avgjor(self):
        # BOR: tilbakebetaling i 2026 etter ordinært utbytte i 2025.
        m = [{"title": "Key information relating to the cash dividend", "messageId": 2,
              "publishedTime": "2026-02-26T08:00"},
             {"title": "Key information relating to the cash dividend", "messageId": 1,
              "publishedTime": "2025-05-28T08:00"}]
        kt = self._med_meldinger(m, {2: self.BOR, 1: self.ORDINAER})
        self.assertEqual(kt, {"andel": 1.0, "melding_dato": "2026-02-26", "melding_id": 2})
        # Og motsatt: en nyere ordinær melding opphever et gammelt merke.
        kt = self._med_meldinger(m, {2: self.ORDINAER, 1: self.BOR})
        self.assertIsNone(kt)

    def test_andre_meldinger_hoppes_over(self):
        m = [{"title": "Mandatory notification of trade", "messageId": 3,
              "publishedTime": "2026-09-01T08:00"},
             {"title": "Key information on cash distribution", "messageId": 2,
              "publishedTime": "2026-08-20T08:00"}]
        kt = self._med_meldinger(m, {2: self.PEN})
        self.assertEqual(kt["melding_id"], 2)

    def test_for_gammel_melding_gir_none(self):
        m = [{"title": "Key information relating to the cash dividend", "messageId": 1,
              "publishedTime": "2025-06-01T08:00"}]
        self.assertIsNone(self._med_meldinger(m, {1: self.STST}))

    def test_nettverksfeil_er_ukjent_ikke_none(self):
        # En feilet henting er ikke bevis for at utbetalingen er vanlig utbytte.
        self.assertIs(self._med_meldinger([], {}, feil=True), fs.UKJENT)

    def test_kapital_andel_vakter(self):
        self.assertEqual(fs.kapital_andel({}), 0.0)
        self.assertEqual(fs.kapital_andel({"kapital_tilbake": {"andel": 1.5}}), 0.0)
        self.assertEqual(fs.kapital_andel({"kapital_tilbake": {"andel": "x"}}), 0.0)
        self.assertEqual(fs.kapital_andel({"kapital_tilbake": {"andel": 0.86}}), 0.86)

    def test_note_bare_der_feltet_finnes(self):
        self.assertEqual(fs.lag_kapital_note({"ticker": "EQNR"}, fs._nf), "")
        a = {"kapital_tilbake": {"andel": 1.0, "melding_dato": "2026-08-25"}}
        h = fs.lag_kapital_note(a, fs._nf)
        self.assertIn("tilbakebetaling av innbetalt", h)
        self.assertIn("25. aug 2026", h)
        delt = fs.lag_kapital_note({"kapital_tilbake": {"andel": 0.862}}, fs._nf)
        self.assertIn("om lag 86\u00a0%", delt)

    def test_faq_sier_ikke_37_prosent_om_tilbakebetaling(self):
        a = {"ticker": "STST", "navn": "Stainless Tankers ASA", "utbytte_yield": 12.9,
             "pris": 10.0, "utbytte_per_aksje": 1.29, "kapital_tilbake": {"andel": 1.0}}
        tekst = json.dumps(fs._lag_faq_seksjon(a, datetime.date(2026, 10, 3)), ensure_ascii=False)
        self.assertIn("ikke skattepliktig når den utbetales", tekst)
        self.assertNotIn("beskattes med 37,84 %", tekst)
        # Overskytende kapital er ikke utbytte (sktl. § 10-35, Skatte-ABC A-6-7.1).
        self.assertNotIn("overskytende", tekst)
        self.assertIn("negativ", tekst)

    def test_faq_nevner_skjerming_og_kildeskatt(self):
        def faq(land):
            a = {"ticker": "X", "navn": "X", "utbytte_yield": 5.0, "pris": 100.0,
                 "utbytte_per_aksje": 5.0, "inkorporeringsland": land, "bors": "Oslo Børs"}
            return json.dumps(fs._lag_faq_seksjon(a, datetime.date(2026, 10, 10)), ensure_ascii=False)
        self.assertIn("overstiger skjermingsfradraget", faq("Norge"))
        self.assertNotIn("kildeskatt", faq("Norge"))
        self.assertIn("registrert i Belgia, som kan trekke kildeskatt", faq("Belgia"))
        self.assertNotIn("kildeskatt", faq("Bermuda"))

    def test_kapitalnoten_sier_ikke_at_overskytende_er_utbytte(self):
        h = fs.lag_kapital_note({"kapital_tilbake": {"andel": 1.0}}, fs._nf)
        self.assertNotIn("overskytende", h)
        self.assertIn("negativ", h)


class TestUtbyttevekst(unittest.TestCase):
    """Vekst mellom hele kalenderår (2026-10-06). Seriene er de virkelige fra Yahoo."""
    I_DAG = datetime.date(2026, 10, 6)
    TEL = [("2021-05-28", 5.0), ("2021-10-07", 4.0), ("2022-05-12", 5.0), ("2022-10-06", 4.3),
           ("2023-05-11", 5.0), ("2023-10-19", 4.4), ("2024-05-08", 5.0), ("2024-10-17", 4.5),
           ("2025-05-22", 5.0), ("2025-10-16", 4.6), ("2026-05-20", 5.0)]
    DNB = [("2021-02-24", 8.4), ("2021-10-28", 9.0), ("2022-04-27", 9.75), ("2023-04-26", 12.5),
           ("2024-04-30", 16.0), ("2025-04-30", 16.75), ("2026-04-22", 18.0)]

    def serie(self, punkter):
        try:
            import pandas as pd
        except ImportError:
            self.skipTest("pandas mangler")
        return pd.Series([v for _, v in punkter],
                         index=pd.DatetimeIndex([d for d, _ in punkter], tz="Europe/Oslo"))

    def test_telenor_er_ikke_minus_14(self):
        # Den gamle målte et fullt 2022 mot et 2026 med bare maiutbetalingen.
        self.assertEqual(fs.beregn_utbytte_vekst(self.serie(self.TEL), i_dag=self.I_DAG), 1.6)

    def test_dnb_etterslep_2021_flytter_startaaret(self):
        # To års utbytte i 2021 ga ellers −0,9 % for et utbytte som har steget hvert år.
        self.assertEqual(fs.beregn_utbytte_vekst(self.serie(self.DNB), i_dag=self.I_DAG), 19.8)

    def test_ny_betaler_uten_startaar_gir_null(self):
        # CMB.TECH toppet listen med +1 600 % fra én betaling i 2025.
        cmbto = [("2025-10-01", 0.48), ("2026-01-10", 2.0), ("2026-04-10", 3.0), ("2026-06-10", 3.1)]
        self.assertEqual(fs.beregn_utbytte_vekst(self.serie(cmbto), i_dag=self.I_DAG), 0.0)

    def test_inneverende_aar_telles_ikke(self):
        med = self.TEL + [("2026-10-01", 50.0)]
        self.assertEqual(fs.beregn_utbytte_vekst(self.serie(med), i_dag=self.I_DAG), 1.6)


class TestVekstFraTopp(unittest.TestCase):
    """Femårsvekst fra et bunnår er ikke vekst når utbyttet har falt siden (2026-10-11).

    Seriene er de lagrede `utbytte_per_ar` fra aksjer.json. Samme tilfeller
    står i tests/ui.test.js, så malen og appen ikke kan gli fra hverandre.
    """
    EQNR = {"ticker": "EQNR", "navn": "Equinor ASA", "sektor": "Energi",
            "utbytte_vekst_5ar": 40.1, "ar_med_utbytte": 25, "utbytte_yield": 3.48,
            "payout_ratio": 40, "frekvens": "Kvartalsvis",
            "utbytte_per_ar": {"2021": 4.9699, "2022": 16.5531, "2023": 35.6415,
                               "2024": 32.1646, "2025": 19.1553}}
    # 2021 er utsatt bankutbytte; beregn_utbytte_vekst() starter i 2022.
    DNB = {"ticker": "DNB", "navn": "DNB Bank ASA", "sektor": "Finans",
           "utbytte_vekst_5ar": 19.8, "ar_med_utbytte": 22, "utbytte_yield": 6.0,
           "payout_ratio": 60, "frekvens": "Årlig",
           "utbytte_per_ar": {"2021": 17.4, "2022": 9.75, "2023": 12.5,
                              "2024": 16.0, "2025": 16.75}}
    MOWI = {"utbytte_vekst_5ar": 10.6,
            "utbytte_per_ar": {"2021": 4.45, "2022": 7.35, "2023": 7.2,
                               "2024": 6.6, "2025": 6.65}}

    def test_eqnr_har_falt_fra_toppen(self):
        topp_ar, topp, siste_ar, siste = fs.vekst_fra_topp(self.EQNR)
        self.assertEqual((topp_ar, siste_ar), (2023, 2025))
        self.assertAlmostEqual(topp, 35.6415)
        self.assertAlmostEqual(siste, 19.1553)

    def test_forste_aar_er_startpunkt_ikke_topp(self):
        self.assertIsNone(fs.vekst_fra_topp(self.DNB))

    def test_liten_dupp_er_fortsatt_vekst(self):
        # 6,65 er 90,5 % av 7,35.
        self.assertIsNone(fs.vekst_fra_topp(self.MOWI))

    def test_mangler_serie(self):
        self.assertIsNone(fs.vekst_fra_topp({"utbytte_vekst_5ar": 40.1}))
        self.assertIsNone(fs.vekst_fra_topp({"utbytte_per_ar": {"2024": 1.0, "2025": 0.5}}))

    def test_eqnr_faar_ikke_vekstmaal_eller_dobling(self):
        self.assertNotIn("vekst", fs._beregn_mal_py(self.EQNR))
        self.assertNotIn("dobles", fs._lag_investor_badges(self.EQNR))
        self.assertNotIn("Utbyttevekst", fs._lag_utbytte_profil(self.EQNR, {}))

    def test_eqnr_vurdering_nevner_toppen(self):
        tekst = fs._lag_investor_vurdering(self.EQNR, {})
        self.assertIn("toppen var 35,64 NOK i 2023, og 2025 endte på 19,16 NOK", tekst)
        self.assertNotIn("attraktivt for langsiktige", tekst)
        self.assertIn("det høyeste året i perioden var 2023", tekst)

    def test_dobling_er_en_betingelse(self):
        self.assertIn("vekst", fs._beregn_mal_py(self.DNB))
        tekst = fs._lag_investor_badges(self.DNB)
        self.assertIn("Holder veksten på +19,8\u00a0% per år seg, dobles utbyttet på ca. 4 år.", tekst)


class TestKurshode(unittest.TestCase):
    """Kurshodet og den kompakte nøkkeltabellen på aksjesiden (STYLE.md, 2026-10-11)."""
    EQNR = {"ticker": "EQNR", "pris": 417.9, "utbytte_yield": 3.48, "utbytte_per_aksje": 14.55,
            "ex_dato": "2026-11-13", "52u_hoy": 426.0, "52u_lav": 226.4,
            "betaling_dato": "2026-11-25", "snitt_yield_5ar": 5.47, "ar_med_utbytte": 25,
            "pe_ratio": 11.6, "payout_ratio": 40.0, "markedsverdi_mrd": 990.1}

    def test_prosent_med_komma_og_hardt_mellomrom(self):
        self.assertEqual(fs._pst(3.48), "3,48 %")
        self.assertIn("3,48 %", fs._lag_kurshode(self.EQNR, "NOK"))

    def test_spenn_med_punktum_i_css(self):
        html = fs._lag_kurshode(self.EQNR, "NOK")
        self.assertIn("left:95.9%", html)          # (417,9 − 226,4) / (426 − 226,4)
        self.assertIn("226,40", html)

    def test_spenn_utelates_naar_toppen_er_over_3x_kursen(self):
        # 2020 Bulkers etter kapitalutdelingen: 52-ukers høy 152,00 på 4,35 kr.
        a = dict(self.EQNR, pris=4.35, **{"52u_hoy": 152.0, "52u_lav": 2.56})
        self.assertNotIn("kh-spenn", fs._lag_kurshode(a, "NOK"))
        a = dict(self.EQNR, pris=430.0)            # over 52-ukers høy: spennet er gammelt
        self.assertNotIn("kh-spenn", fs._lag_kurshode(a, "NOK"))

    def test_ukjent_ex_dato_sies(self):
        a = dict(self.EQNR, ex_dato="")
        self.assertIn("Ikke kjent", fs._lag_kurshode(a, "NOK"))

    def test_tomme_felt_utelates(self):
        a = dict(self.EQNR, betaling_dato="", pe_ratio=0, payout_ratio=0)
        html = fs._lag_korttall(a, "NOK")
        self.assertNotIn("Utbetalingsdato", html)
        self.assertNotIn("P/E", html)
        self.assertNotIn("Payout", html)       # 0 er ukjent, ikke lav
        self.assertIn("5-årssnitt yield", html)
        self.assertEqual(fs._lag_korttall({}, "NOK"), "")


class TestIngenDobleParenteser(unittest.TestCase):
    """{{ }} hører bare hjemme i f-strenger. Settes en vanlig streng med {{ inn i
    en mal, står parentesene doble i HTML-en og CSS-regelen forkastes. Slik var
    mørk modus i bunnteksten død på 176 sider (2026-10-11)."""

    def test_bunnteksten(self):
        self.assertNotIn("{{", fs.STANDARD_FOOTER)
        self.assertIn(".dark .std-footer {", fs.STANDARD_FOOTER)

    def test_aksjesiden(self):
        sti = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aksjer.json")
        if not os.path.exists(sti):
            self.skipTest("aksjer.json finnes ikke")
        with open(sti, encoding="utf-8") as f:
            a = json.load(f)["aksjer"][0]
        html_ = fs._aksje_side_html(dict(a, kurs_historikk=[]), "2026-10-11")
        # Bare {{: }} forekommer lovlig når JSON-LD avslutter nestede objekter.
        self.assertNotIn("{{", html_)


class TestTallkontroll1210(unittest.TestCase):
    """Tekstfeilene tallkontrollen fant 2026-10-12, med radene slik de så ut."""
    I_DAG = datetime.date(2026, 10, 12)

    def rad(self, **felt):
        a = {"ticker": "TST", "navn": "Test ASA", "sektor": "Finans", "frekvens": "Årlig",
             "pris": 100.0, "utbytte_yield": 6.0, "utbytte_per_aksje": 6.0,
             "payout_ratio": 60, "ar_med_utbytte": 10, "valuta": "NOK",
             "utbytte_12m": 6.0, "utbytte_forste_ar": 2010,
             "utbytte_per_ar": {"2021": 4.0, "2022": 4.0, "2023": 5.0, "2024": 5.0, "2025": 6.0},
             "utbytteaar": list(range(2010, 2027)), "historiske_utbytter": []}
        a.update(felt)
        return a

    # 2) Snittet: hele år, nullår teller, år før første utbytte teller ikke
    def test_snitt_fra_hele_ar(self):
        a = self.rad()
        fs.sett_snitt_felter(a)
        self.assertEqual((a["snitt_yield_5ar"], a["snitt_yield_ar"]), (4.8, 5))

    def test_snitt_under_tre_ar_er_ukjent(self):
        # SNTIA viste «5-årssnitt 6,88 %» fra 2026 alene.
        a = self.rad(utbytte_forste_ar=2025, snitt_yield_5ar=6.88)
        fs.sett_snitt_felter(a)
        self.assertEqual(a["snitt_yield_5ar"], 0)
        self.assertEqual(fs.snitt_navn(a), "5-årssnitt")

    def test_nullar_teller_og_navnet_folger_arene(self):
        a = self.rad(utbytte_forste_ar=2022,
                     utbytte_per_ar={"2021": 0, "2022": 3.0, "2023": 0, "2024": 3.0, "2025": 3.0})
        fs.sett_snitt_felter(a)
        self.assertEqual((a["snitt_yield_5ar"], a["snitt_yield_ar"]), (2.25, 4))
        self.assertEqual(fs.snitt_navn(a), "4-årssnitt")
        self.assertTrue(fs.snitt_har_nullar(a))

    def test_uten_serie_beholdes_lagret_snitt(self):
        a = self.rad(utbytte_per_ar=None, snitt_yield_5ar=5.5)
        fs.sett_snitt_felter(a)
        self.assertEqual(a["snitt_yield_5ar"], 5.5)

    # 1) Payout-grensen
    def test_payout_over_80_ikke_egen_verdi(self):
        html_ = " ".join(fs._lag_faq_seksjon(self.rad(payout_ratio=110), "2026-10-12"))
        self.assertIn("payout ratio over 80\u00a0%", html_)
        self.assertNotIn("over 110 %", html_)

    # 3) «På linje med» er relativt, og kursen er aldri forklaringen
    def test_paa_linje_relativt(self):
        a = self.rad(utbytte_yield=0.70, snitt_yield_5ar=1.99, snitt_yield_ar=5)
        html_ = " ".join(fs._lag_faq_seksjon(a, "2026-10-12"))
        self.assertNotIn("på linje med", html_)
        self.assertIn("under 5-årssnittet", html_)
        self.assertNotIn("inngangskurs", html_)

    # 5 og 7) Hull er ikke «uten kutt», og «kursen har falt» kan ikke stemme
    def test_hull_er_ikke_uten_kutt(self):
        a = self.rad(historiske_utbytter=[{"ar": 2022, "utbytte": 11.0}, {"ar": 2024, "utbytte": 20.0},
                                          {"ar": 2025, "utbytte": 32.52}],
                     utbytte_yield=9.0, snitt_yield_5ar=3.9, snitt_yield_ar=5)
        tekst = fs._lag_utbyttehistorikk_tekst(a, 2026)
        self.assertNotIn("uten et eneste kutt", tekst)
        self.assertIn("for 2023 har vi ikke registrert noe utbytte", tekst)

    def test_aldri_kursen_som_forklaring(self):
        a = self.rad(historiske_utbytter=[{"ar": 2022, "utbytte": 6.1}, {"ar": 2023, "utbytte": 53.4},
                                          {"ar": 2024, "utbytte": 32.6}, {"ar": 2025, "utbytte": 20.3}],
                     utbytte_yield=9.7, snitt_yield_5ar=2.6, snitt_yield_ar=5)
        self.assertNotIn("kursen har falt", fs._lag_utbyttehistorikk_tekst(a, 2026))
        for p in fs._lag_risikofaktorer(a):
            self.assertNotIn("kursen har falt", p)

    # 4) Rekken, ikke antallet, og et brudd nevnes alltid
    def test_brudd_med_lang_rekke(self):
        # SOGN: 17 år med utbytte, 8 på rad siden 2019.
        a = self.rad(ar_med_utbytte=17, utbytteaar=list(range(2002, 2009)) + list(range(2010, 2018))
                     + list(range(2019, 2027)))
        html_ = fs._lag_investor_badges(a)
        self.assertIn("med brudd — sammenhengende siden 2019", html_)
        self.assertNotIn("Lang utbyttehistorikk (17 år)", html_)
        self.assertNotIn("vist evne til stabil utbetaling", html_)

    # 4 og 6) Ingen påstander dataene ikke bærer
    def test_ingen_konsistent_eller_kompenserer(self):
        a = self.rad(utbytte_yield=2.0, utbytteaar=list(range(2019, 2027)))
        vurd = fs._lag_investor_vurdering(a, {"Finans": 6.0})
        faq = " ".join(fs._lag_faq_seksjon(a, "2026-10-12"))
        for tekst in (vurd, faq):
            self.assertNotIn("konsistent", tekst)
            self.assertNotIn("kompenserer", tekst)
            self.assertNotIn("konjunktursyklus", tekst)


class TestBelopIUtbyttemelding(unittest.TestCase):
    """Beløpet for neste utbetaling, fra børsmeldingen (2026-10-06)."""
    I_DAG = datetime.date(2026, 10, 6)

    def test_telenor_oktober_er_470(self):
        u = fs.neste_utbetaling(TestUtbetalingerIMelding.TEL, self.I_DAG)
        self.assertEqual((u["ex_dato"], u["belop"], u["valuta"]), ("2026-10-15", 4.70, "NOK"))

    def test_millioner_er_ikke_per_aksje(self):
        enh = "Distribution amount: USD 25.0 million\nEx-date: 9 November 2026"
        self.assertIsNone(fs.neste_utbetaling(enh, self.I_DAG)["belop"])

    def test_uten_valuta_ingen_belop(self):
        # GOD oppgir ikke valuta i beløpsfeltet; da vet vi ikke hva tallet er i.
        u = fs.neste_utbetaling(TestUtbetalingerIMelding.GOD, self.I_DAG)
        self.assertIsNone(u["belop"])

    def test_valuta_fra_meldingen(self):
        atea = ("Declared currency: NOK\nDividend amount:     3.75\nEx-date: 18 November 2026\n"
                "Payment date: 23 November 2026")
        u = fs.neste_utbetaling(atea, self.I_DAG)
        self.assertEqual((u["belop"], u["valuta"]), (3.75, "NOK"))


class TestOmSelskapet(unittest.TestCase):
    """Innledningen skal stå én gang også uten faktasammendrag (2026-10-06)."""

    def test_intro_ikke_doblet_uten_fakta(self):
        sti = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aksjer.json")
        if not os.path.exists(sti):
            self.skipTest("aksjer.json finnes ikke")
        with open(sti, encoding="utf-8") as f:
            rader = json.load(f)["aksjer"]
        uten = [a for a in rader if a.get("beskrivelse_intro") and not a.get("beskrivelse_fakta")]
        if not uten:
            self.skipTest("ingen aksje uten faktasammendrag")
        for a in uten:
            html_ = fs._aksje_side_html(dict(a, kurs_historikk=[]), "2026-10-06")
            # Bare den synlige seksjonen — JSON-LD-beskrivelsen bærer den også.
            om = re.search(r'<div class="desc"><h2>Om selskapet</h2>(.*?)</div>', html_, re.S)
            self.assertIsNotNone(om, a["ticker"])
            self.assertEqual(om.group(1).count(a["beskrivelse_intro"][:80]), 1, a["ticker"])

    def test_flere_avsnitt_gir_flere_p(self):
        sti = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aksjer.json")
        if not os.path.exists(sti):
            self.skipTest("aksjer.json finnes ikke")
        with open(sti, encoding="utf-8") as f:
            a = json.load(f)["aksjer"][0]
        a = dict(a, kurs_historikk=[], beskrivelse_intro="Første avsnitt.\n\nAndre avsnitt.",
                 beskrivelse_fakta="Fakta.")
        html_ = fs._aksje_side_html(a, "2026-10-06")
        om = re.search(r'<div class="desc"><h2>Om selskapet</h2>(.*?)</div>', html_, re.S)
        self.assertIn("<p>Første avsnitt.</p><p>Andre avsnitt.</p>", om.group(1))
        # Yahoos avsnitt vises ikke når selskapet har en egen tekst (2026-10-07).
        self.assertNotIn("Fakta.", om.group(1))

    def test_yahoo_avsnittet_brukes_uten_egen_tekst(self):
        sti = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aksjer.json")
        if not os.path.exists(sti):
            self.skipTest("aksjer.json finnes ikke")
        with open(sti, encoding="utf-8") as f:
            a = json.load(f)["aksjer"][0]
        a = dict(a, kurs_historikk=[], beskrivelse_intro="", beskrivelse_fakta="Bare fakta.")
        html_ = fs._aksje_side_html(a, "2026-10-07")
        om = re.search(r'<div class="desc"><h2>Om selskapet</h2>(.*?)</div>', html_, re.S)
        self.assertIn('<p class="desc-fakta">Bare fakta.</p>', om.group(1))

    def test_jsonld_beskrivelse_er_var_egen_tekst(self):
        sti = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aksjer.json")
        if not os.path.exists(sti):
            self.skipTest("aksjer.json finnes ikke")
        with open(sti, encoding="utf-8") as f:
            a = json.load(f)["aksjer"][0]
        a = dict(a, kurs_historikk=[], beskrivelse_intro="Vår tekst.\n\nMer tekst.",
                 beskrivelse_fakta="Yahoo-tekst.")
        html_ = fs._aksje_side_html(a, "2026-10-07")
        self.assertIn('"description": "Vår tekst. Mer tekst."', html_)
        self.assertNotIn("Yahoo-tekst.", html_)


class TestManuellDelAvsnitt(unittest.TestCase):
    """Selskapsteksten kan ha flere avsnitt — skillene må overleve _manuell_del()."""

    def test_avsnitt_beholdes(self):
        from utvid_beskrivelser import _manuell_del
        self.assertEqual(_manuell_del("Én. To.\n\nTre."), "Én. To.\n\nTre.")

    def test_stopper_ved_generert_setning_i_senere_avsnitt(self):
        from utvid_beskrivelser import _manuell_del
        t = "Én.\n\nTo. Utbyttet utbetales kvartalsvis. Tre.\n\nFire."
        self.assertEqual(_manuell_del(t), "Én.\n\nTo.")

    def test_generert_avsnitt_alene_forsvinner(self):
        from utvid_beskrivelser import _manuell_del
        t = "Én.\n\nUtbyttet utbetales kvartalsvis."
        self.assertEqual(_manuell_del(t), "Én.")


class TestAskStatus(unittest.TestCase):
    """ASK krever EØS-hjemsted *og* et regulert marked.

    Alle 14 aksjene på Euronext Growth sto som «kan holdes i ASK», og FAQ-en
    lovet utsatt skatt på ASK også for Bermuda-selskapene (2026-10-09).
    """

    FOR = datetime.date(2026, 10, 9)
    ETTER = datetime.date(2027, 1, 2)

    def test_status(self):
        self.assertEqual(fs.ask_status(True, "Oslo Børs", self.FOR), "ja")
        self.assertEqual(fs.ask_status(True, "Euronext Growth Oslo", self.FOR), "growth")
        self.assertEqual(fs.ask_status(False, "Oslo Børs", self.FOR), "utenfor_eos")
        # Hjemstedet er grunnen som ikke går bort i 2027.
        self.assertEqual(fs.ask_status(False, "Euronext Growth Oslo", self.FOR), "utenfor_eos")
        self.assertEqual(fs.ask_status(None, "Oslo Børs", self.FOR), "uavklart")
        self.assertEqual(fs.ask_status(None, "Euronext Growth Oslo", self.FOR), "growth")

    def test_growth_aapnes_forst_naar_datoen_er_satt(self):
        self.assertEqual(fs.ask_status(True, "Euronext Growth Oslo", self.ETTER), "growth")
        gml = fs.ASK_MHF_FRA
        try:
            fs.ASK_MHF_FRA = "2027-01-01"
            self.assertEqual(fs.ask_status(True, "Euronext Growth Oslo", self.FOR), "growth")
            self.assertEqual(fs.ask_status(True, "Euronext Growth Oslo", self.ETTER), "ja")
        finally:
            fs.ASK_MHF_FRA = gml

    def test_forslaget_nevnes_bare_for_2027(self):
        a = {"ask_egnet": True, "bors": "Euronext Growth Oslo"}
        self.assertIn("statsbudsjettet for 2027", fs.ask_tekst(a, self.FOR)[1])
        self.assertNotIn("statsbudsjettet", fs.ask_tekst(a, self.ETTER)[1])

    def test_paa_og_i(self):
        bm = fs.ask_tekst({"ask_egnet": False, "inkorporeringsland": "Bermuda"}, self.FOR)[1]
        self.assertIn("registrert på Bermuda, utenfor EØS", bm)
        se = fs.ask_tekst({"ask_egnet": True, "inkorporeringsland": "Sverige",
                           "bors": "Oslo Børs"}, self.FOR)[1]
        self.assertIn("registrert i Sverige", se)
        oet = fs.ask_tekst({"ask_egnet": None, "inkorporeringsland": "Marshalløyene",
                            "bors": "Oslo Børs"}, self.FOR)
        self.assertEqual(oet[0], "uavklart")
        self.assertIn("ikke fått bekreftet", oet[1])

    def test_kontoraden(self):
        h = fs._lag_kontoer_seksjon({"ask_egnet": True, "bors": "Euronext Growth Oslo"})
        self.assertIn("konto-ikke", h)
        self.assertIn("Euronext Growth", h)
        h = fs._lag_kontoer_seksjon({"ask_egnet": None, "inkorporeringsland": "Marshalløyene"})
        self.assertIn("konto-uavklart", h)

    def test_faq_lover_ikke_ask_der_det_ikke_gjelder(self):
        for rad, skal in ((dict(ask_egnet=True, bors="Oslo Børs"), True),
                          (dict(ask_egnet=True, bors="Euronext Growth Oslo"), False),
                          (dict(ask_egnet=False, inkorporeringsland="Bermuda"), False)):
            a = {"ticker": "X", "navn": "X ASA", "utbytte_yield": 5.0, "pris": 100.0,
                 "utbytte_per_aksje": 5.0, **rad}
            tekst = json.dumps(fs._lag_faq_seksjon(a, self.FOR), ensure_ascii=False)
            self.assertEqual("utsettes skatten" in tekst, skal, rad)

    def test_uavklart_teller_ikke_som_utenfor_eos_i_risikoen(self):
        base = {"sektor": "Shipping", "payout_ratio": 0, "markedsverdi": 5e9, "utbytte_yield": 5}
        self.assertEqual(fs._beregn_risiko_py(dict(base, ask_egnet=True)),
                         fs._beregn_risiko_py(dict(base, ask_egnet=None)))

    def test_katalogen(self):
        """Ingen Growth-aksje får «ja», og land helt utenfor EØS står som false."""
        with open(os.path.join(os.path.dirname(__file__), "..", "data", "tickers.json"),
                  encoding="utf-8") as f:
            tickere = json.load(f)
        for t in tickere:
            st = fs.ask_status(t.get("ask_egnet", True), t["bors"], self.FOR)
            if "Growth" in t["bors"]:
                self.assertNotEqual(st, "ja", t["ticker"])
            if t.get("inkorporeringsland", "Norge") in ("Bermuda", "Singapore", "Sveits", "Færøyene"):
                self.assertIs(t.get("ask_egnet"), False, t["ticker"])


class TestEngangsutbytteTrukketFra(unittest.TestCase):
    """Frontline: 0,80 dollar engangsutbytte i en egen melding (11.09.2026).

    «special one-time dividend» slapp gjennom regexen, så 12-månederssummen
    med engangsutbyttet ble årsraten. Å bare rette regexen ville sendt
    Frontline tilbake til fjorårets 8,90 kr (1,6 %). Beløpet trekkes derfor
    ut når meldingene oppgir det.
    """

    FRO_Q2 = ("Dividend amount: $2.61 per share\nDeclared currency: USD.\n"
              "Ex-date: 17 September, 2026\nPayment date: On or about 28 September, 2026.")
    FRO_SPESIAL = ("Dividend amount: $0.80 per share\nDeclared currency: USD.\n"
                   "Ex-date: 17 September, 2026\nPayment date: On or about 28 September, 2026.")
    FRO_PRESSE = ("the Board of Directors has declared a special one-time dividend of $0.80 "
                  "per share ... in addition to the previously declared dividend of $2.61")

    def _kjor(self, meldinger, tekster, i_dag=datetime.date(2026, 10, 9)):
        gml = fs._newsweb_meldinger, fs._newsweb_tekst
        fs._newsweb_meldinger = lambda t: meldinger
        fs._newsweb_tekst = lambda mid: tekster.get(mid, "")
        try:
            return fs.ekstraordinaere_i_vindu("FRO", i_dag)
        finally:
            fs._newsweb_meldinger, fs._newsweb_tekst = gml

    def _fro(self):
        m = [{"publishedTime": "2026-09-11T22:00", "messageId": 3,
              "title": "Key information relating to the special one-time dividend after sale of two VLLCs"},
             {"publishedTime": "2026-09-11T22:00", "messageId": 2,
              "title": "FRO - Declares special one-time dividend after sale of two VLLCs"},
             {"publishedTime": "2026-08-28T07:00", "messageId": 1,
              "title": "Key information relating to the dividend to be paid by Frontline plc for the second quarter, 2026"}]
        return self._kjor(m, {1: self.FRO_Q2, 2: self.FRO_PRESSE, 3: self.FRO_SPESIAL})

    def test_formuleringene(self):
        for t in ["Key information relating to the special one-time dividend",
                  "declares a one-time dividend", "an extraordinary portion of USD 0.47"]:
            self.assertTrue(fs._har_ekstraordinaer(t), t)
        self.assertFalse(fs._har_ekstraordinaer("excluding one-time items"))

    def test_dollartegn_er_usd(self):
        u = fs._parse_utbetalinger(self.FRO_SPESIAL)
        self.assertEqual((u[0]["belop"], u[0]["valuta"]), (0.8, "USD"))

    def test_frontline_tallfestes(self):
        funn = self._fro()
        # Pressemeldingen samme dag lar seg ikke tallfeste, men er samme utbetaling.
        self.assertEqual(len(funn), 1)
        self.assertEqual((funn[0]["ex_dato"], funn[0]["ekstra"], funn[0]["total"]),
                         ("2026-09-17", 0.8, 3.41))
        a = {"utbytte_12m_liste": [{"ex_dato": "2026-06-11", "belop": 14.8028},
                                   {"ex_dato": "2026-09-17", "belop": 32.5661}]}
        self.assertAlmostEqual(fs.ekstra_i_kroner(a, funn), 32.5661 * 0.8 / 3.41, places=3)

    def test_uten_belop_holdes_regelen_unna(self):
        a = {"utbytte_12m_liste": [{"ex_dato": "2026-09-17", "belop": 32.5661}]}
        self.assertIsNone(fs.ekstra_i_kroner(a, [{"ex_dato": None, "ekstra": None, "total": None}]))
        # Ingen utbetaling med den ex-datoen i serien.
        self.assertIsNone(fs.ekstra_i_kroner(
            a, [{"ex_dato": "2026-03-11", "ekstra": 0.8, "total": 3.41}]))
        # Før første fulle henting finnes ikke listen.
        self.assertIsNone(fs.ekstra_i_kroner({}, [{"ex_dato": "2026-09-17", "ekstra": 0.8, "total": 3.41}]))

    def test_bruk_med_fradrag(self):
        a = {"utbytte_12m": 59.15, "pris": 543.6}
        fs.bruk_betalt_som_arsrate(a, 7.64)
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"], a["arsrate_ekstra_trukket"]),
                         (51.51, 9.48, 7.64))
        fs.bruk_betalt_som_arsrate(a)
        self.assertNotIn("arsrate_ekstra_trukket", a)

    def test_noten_motsier_ikke_fradraget(self):
        a = {"utbytte_yield": 5.05, "utbytte_per_aksje": 8.73, "siste_utbytte": 5.8256,
             "valuta": "NOK", "frekvens": "Halvårlig", "arsrate_kilde": "betalt_12m",
             "arsrate_ekstra_trukket": 6.78,
             "utbyttesplitt": {"ordinaert": 0.37, "ekstraordinaert": 0.24, "valuta": "USD",
                               "melding_dato": "2026-08-11"},
             "historiske_utbytter": [{"ar": 2026, "utbytte": 15.47, "maaneder": [3, 8]}]}
        h = fs.lag_ekstraordinaer_note(a, fs._nf)
        self.assertIn("holdt utenfor", h)
        self.assertNotIn("inneholder den", h)
        a.pop("arsrate_ekstra_trukket")
        self.assertIn("inneholder den", fs.lag_ekstraordinaer_note(a, fs._nf))


class TestKapitalTittel(unittest.TestCase):
    """Pexip meldte utbyttet uten «Key information» i tittelen (665466)."""

    def test_titler(self):
        ja = ["Key information relating to the cash dividend to be paid by X ASA",
              "Key information relating to cash distribution",
              "Information relating to the proposed dividend for 2025"]
        nei = ["Ex. dividend NOK 4.0 today", "Share capital increase registered",
               "Key information relating to share capital increase"]
        for t in ja:
            self.assertTrue(fs._KAPITAL_TITTEL.search(t), t)
        for t in nei:
            self.assertFalse(fs._KAPITAL_TITTEL.search(t), t)


class TestTilleggErOrdinaert(unittest.TestCase):
    """WWI viste 12,00 kr mot 28,50 betalt, AFG 6,50 mot 11,00 (2026-11-21).

    Politikken deler årsutbyttet i to, og den andre delen heter «additional»
    eller «tilleggsutbytte». Det ordet skal ikke stoppe betalt-12m-regelen.
    """

    def test_tillegget_teller_ikke_for_merkede_selskaper(self):
        tekst = "the Board resolved an additional dividend of NOK 8.50 per share"
        self.assertTrue(fs._har_ekstraordinaer(tekst))
        self.assertIn("WWI", fs.TILLEGG_ER_ORDINAERT)
        self.assertFalse(fs._har_ekstraordinaer(fs._uten_tillegg(tekst, "WWI")))
        norsk = "styret har besluttet at selskapet utbetaler et tilleggsutbytte på NOK 4,50"
        self.assertFalse(fs._har_ekstraordinaer(fs._uten_tillegg(norsk, "AFG")))

    def test_ekte_engangsutbytte_finnes_fortsatt(self):
        tekst = "an additional dividend of NOK 8.50 and a special dividend of NOK 10.00"
        self.assertTrue(fs._har_ekstraordinaer(fs._uten_tillegg(tekst, "WWI")))

    def test_andre_selskaper_er_uendret(self):
        tekst = "an additional dividend of NOK 2.00"
        self.assertNotIn("GOD", fs.TILLEGG_ER_ORDINAERT)
        self.assertEqual(fs._uten_tillegg(tekst, "GOD"), tekst)

    def test_haandregistrerte_utbetalinger_har_kilde(self):
        for t, liste in fs.UTBETALINGER_FRA_MELDING.items():
            for f in liste:
                datetime.date.fromisoformat(f["ex_dato"])
                self.assertGreater(f["belop"], 0, t)
                self.assertTrue(str(f["melding_id"]).isdigit(), t)

    def test_forrige_supplert_kommer_med(self):
        """Det som er lagt til før, følger med inn i neste kjørings funn."""
        kilde = inspect.getsource(fs.hent_aksje)
        self.assertIn("FORRIGE_SUPPLERT.get(ticker", kilde)
        self.assertIn("FORRIGE_SUPPLERT.update", inspect.getsource(fs.main))


class TestGoodtechTillegg(unittest.TestCase):
    """Goodtech: 0,50 ordinært og 2,00 som tillegg. Siden viste 26,32 % (16.10.2026).

    DNB-steget ganget tillegget med «Halvårlig», og regelen om betalt siste
    12 mnd ga opp fordi rapporten og pressemeldingen om det samme tillegget
    ikke oppgir beløpet per aksje i et format vi leser.
    """

    ORDINAER = "Dividend amount: NOK 0.50 per share\nEx-date: 4 May 2026\n"
    TILLEGG = "Dividend amount: NOK 2.00 per share\nEx-date: 16 October 2026\n"

    def _meldinger(self, ekstra=()):
        m = [{"publishedTime": "2026-09-18T06:00", "messageId": 4,
              "title": "Key information relating to the proposed supplemental cash dividend "
                       "for the Financial Year 2025"},
             {"publishedTime": "2026-09-17T16:00", "messageId": 3,
              "title": "Goodtech ASA: The Board resolves to distribute a supplemental dividend "
                       "of NOK 2.00 per share"},
             {"publishedTime": "2026-07-17T06:00", "messageId": 2,
              "title": "Goodtech ASA Q2 2026 and first half 2026 Strong financial position "
                       "supports planned NOK 60 million capital distribution"},
             {"publishedTime": "2026-03-20T06:00", "messageId": 1,
              "title": "Key information relating to the proposed cash dividend for the "
                       "Financial Year 2025"}]
        return list(ekstra) + m

    def _kjor(self, meldinger, tekster):
        gml = fs._newsweb_meldinger, fs._newsweb_tekst
        fs._newsweb_meldinger = lambda t: meldinger
        fs._newsweb_tekst = lambda mid: tekster.get(mid, "")
        try:
            return fs.ekstraordinaere_i_vindu("GOD", datetime.date(2026, 10, 16))
        finally:
            fs._newsweb_meldinger, fs._newsweb_tekst = gml

    TEKSTER = {1: ORDINAER, 2: "The board intends to propose supplemental dividends.",
               3: "The Board has resolved to distribute a supplemental dividend.",
               4: TILLEGG}

    def test_rapport_og_pressemelding_er_samme_sak(self):
        funn = self._kjor(self._meldinger(), self.TEKSTER)
        self.assertEqual([(f["ex_dato"], f["ekstra"], f["total"]) for f in funn],
                         [("2026-10-16", 2.0, 2.0)])

    def test_en_annen_ex_dato_stopper_fortsatt_regelen(self):
        annen = {"publishedTime": "2026-09-30T06:00", "messageId": 5,
                 "title": "Key information relating to the extraordinary dividend"}
        tekster = {**self.TEKSTER, 5: "Ex-date: 1 December 2026\nextraordinary dividend"}
        funn = self._kjor(self._meldinger([annen]), tekster)
        self.assertIn(("2026-12-01", None), [(f["ex_dato"], f["ekstra"]) for f in funn])

    def test_hel_engangsutbetaling_tas_ut_av_antallet(self):
        self.assertEqual(fs.hele_engangsutbetalinger(
            [{"ex_dato": "2026-10-16", "ekstra": 2.0, "total": 2.0}]), 1)
        # Frontlines 0,80 lå i samme utbetaling som kvartalsutbyttet.
        self.assertEqual(fs.hele_engangsutbetalinger(
            [{"ex_dato": "2026-09-17", "ekstra": 0.8, "total": 3.41}]), 0)

    def test_paa_ex_dagen_er_utbyttet_ikke_lenger_kommende(self):
        a = {"pris": 15.2, "frekvens": "Årlig", "utbytte_12m": 0.5, "utbytte_12m_antall": 1,
             "utbytte_per_aksje": 2.5, "annonsert_utbytte": 2.0, "annonsert_ex": "2026-10-16",
             "utbytte_12m_liste": [{"ex_dato": "2026-05-04", "belop": 0.5},
                                   {"ex_dato": "2026-10-16", "belop": 2.0}]}
        self.assertTrue(fs.betalt_kan_bli_arsrate(a, datetime.date(2026, 10, 16)))
        # Før Yahoo har utbetalingen, er det kunngjorte utbyttet ferskere.
        b = dict(a, utbytte_12m_liste=a["utbytte_12m_liste"][:1])
        self.assertFalse(fs.betalt_kan_bli_arsrate(b, datetime.date(2026, 10, 14)))

    def test_dnb_beloepet_gangs_ikke_opp_naar_det_er_engangs(self):
        gml = fs.ekstraordinaere_i_vindu
        fs.ekstraordinaere_i_vindu = lambda t, i_dag=None: [
            {"ex_dato": "2026-10-16", "ekstra": 2.0, "total": 2.0}]
        try:
            self.assertTrue(fs.annonsert_er_ekstraordinaer("GOD", "2026-10-16"))
            self.assertFalse(fs.annonsert_er_ekstraordinaer("GOD", "2026-05-04"))
            self.assertFalse(fs.annonsert_er_ekstraordinaer("GOD", None))
            fs.ekstraordinaere_i_vindu = lambda t, i_dag=None: fs.UKJENT
            self.assertFalse(fs.annonsert_er_ekstraordinaer("GOD", "2026-10-16"))
        finally:
            fs.ekstraordinaere_i_vindu = gml

    def test_katalogen_er_aarlig(self):
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("GOD"), "Årlig")


class TestUtbytteStoppet(unittest.TestCase):
    """REACH 6,99 % og MGN 3,6 % i oktober 2026, siste utbetaling i 2025."""

    I_DAG = datetime.date(2026, 10, 16)

    def rad(self, **kw):
        a = {"utbytte_per_aksje": 0.42, "utbytte_yield": 6.99, "utbytte_12m": 0,
             "siste_utbytte_dato": "2025-05-20", "ex_dato": None}
        a.update(kw)
        return a

    def test_reach(self):
        self.assertTrue(fs.utbytte_stoppet(self.rad(), self.I_DAG))

    def test_aarlig_betaler_noen_uker_sent_er_ikke_stoppet(self):
        # 13 måneder siden: årlig betaler som går ex litt senere i år.
        self.assertFalse(fs.utbytte_stoppet(self.rad(siste_utbytte_dato="2025-09-10"), self.I_DAG))

    def test_kunngjort_ex_dato_holder_raten(self):
        self.assertFalse(fs.utbytte_stoppet(self.rad(ex_dato="2026-11-02"), self.I_DAG))
        # En passert ex-dato teller ikke.
        self.assertTrue(fs.utbytte_stoppet(self.rad(ex_dato="2025-05-20"), self.I_DAG))

    def test_uten_dato_sier_regelen_ingenting(self):
        self.assertFalse(fs.utbytte_stoppet(self.rad(siste_utbytte_dato=None), self.I_DAG))
        self.assertFalse(fs.utbytte_stoppet(self.rad(siste_utbytte_dato="tull"), self.I_DAG))

    def test_rate_null_fra_for_er_ikke_et_funn(self):
        self.assertFalse(fs.utbytte_stoppet(self.rad(utbytte_per_aksje=0.0), self.I_DAG))


class TestMarkedsverdiFastInfo(unittest.TestCase):
    """Yahoos info manglet marketCap for FRO, GJF, HEX, JIN og SNI (oktober 2026)."""

    class _Aksje:
        def __init__(self, fast_info):
            self._fi = fast_info

        @property
        def fast_info(self):
            if isinstance(self._fi, Exception):
                raise self._fi
            return self._fi

    def test_bruker_fast_info(self):
        stk = self._Aksje({"marketCap": 111088821611.0, "shares": 222622889})
        self.assertEqual(fs.markedsverdi_fra_fast_info(stk), 111088821611.0)

    def test_mangler_eller_feiler_gir_null(self):
        self.assertEqual(fs.markedsverdi_fra_fast_info(self._Aksje({})), 0.0)
        self.assertEqual(fs.markedsverdi_fra_fast_info(self._Aksje({"marketCap": None})), 0.0)
        self.assertEqual(fs.markedsverdi_fra_fast_info(self._Aksje(KeyError("x"))), 0.0)
        self.assertEqual(fs.markedsverdi_fra_fast_info(self._Aksje({"marketCap": float("nan")})), 0.0)


class TestCmbTechMelding(unittest.TestCase):
    """CMB.TECH: valutaen etter beløpet og tre betalingsdatoer (08.10.2026)."""

    TEKST = ("Distribution amount: 0.64 USD per share\nAnnounced currency: USD.\n"
             "Ex-date on Euronext Belgium and Euronext Oslo Børs: expected on 15 October 2026\n"
             "Ex-date on NYSE: expected on 16 October 2026\n"
             "Payment date on Euronext Belgium and NYSE: expected on 22 October 2026.\n"
             "Payment date on Euronext Oslo Børs: Expected on or about 27 October 2026.")

    def test_oslo_vinner_for_betalingsdatoen_ogsaa(self):
        self.assertEqual(fs._parse_ex_dato(self.TEKST), ("2026-10-15", "2026-10-27"))

    def test_belop_med_valuta_fra_announced_currency(self):
        u = fs._parse_utbetalinger(self.TEKST)
        self.assertEqual((u[0]["belop"], u[0]["valuta"]), (0.64, "USD"))


class TestLopendeUtbytteFra(unittest.TestCase):
    """2020 Bulkers: ny virksomhet, gammel historikk, 11,62 % yield (2026-10-09)."""

    def test_nulles_til_ny_utbetaling(self):
        a = {"utbytte_per_aksje": 0.73, "utbytte_yield": 11.62, "pris": 6.3,
             "utbytte_12m_liste": [{"ex_dato": "2026-04-29", "belop": 129.45}]}
        self.assertTrue(fs.bruk_lopende_utbytte_fra(a, "2026-05-01"))
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"], a["arsrate_kilde"]),
                         (0.0, 0.0, "ingen_lopende"))

    def test_slutter_av_seg_selv(self):
        a = {"utbytte_per_aksje": 0.5, "utbytte_yield": 8.0,
             "utbytte_12m_liste": [{"ex_dato": "2026-04-29", "belop": 129.45},
                                   {"ex_dato": "2026-11-20", "belop": 0.5}]}
        self.assertFalse(fs.bruk_lopende_utbytte_fra(a, "2026-05-01"))
        self.assertEqual(a["utbytte_yield"], 8.0)

    def test_katalogen(self):
        self.assertEqual(fs.LOPENDE_UTBYTTE_FRA.get("2020"), "2026-05-01")
        # Grieg Seafood: 35,64 kr i april 2026 var salgssummen fra Cermaq, på en
        # aksje til 23 kr. Siden og appens toppkort viste 35,64 % yield.
        self.assertEqual(fs.LOPENDE_UTBYTTE_FRA.get("GSF"), "2026-04-21")

    def test_grieg_faar_ingen_lopende_rate(self):
        a = {"utbytte_per_aksje": 8.29, "utbytte_yield": 35.64, "pris": 23.26,
             "utbytte_12m_liste": [{"ex_dato": "2026-04-20", "belop": 35.6371}]}
        self.assertTrue(fs.bruk_lopende_utbytte_fra(a, "2026-04-21"))
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"], a["arsrate_kilde"]),
                         (0.0, 0.0, "ingen_lopende"))

    def test_faq_lover_ikke_rekke_eller_buffer(self):
        a = {"ticker": "2020", "navn": "2020 Bulkers Ltd", "frekvens": "Uregelmessig",
             "ar_med_utbytte": 8, "utbytteaar": list(range(2019, 2027)), "payout_ratio": 18,
             "utbytte_yield": 0.0, "utbytte_per_aksje": 0.0, "pris": 6.3,
             "arsrate_kilde": "ingen_lopende"}
        tekst = json.dumps(fs._lag_faq_seksjon(a, datetime.date(2026, 10, 9)), ensure_ascii=False)
        self.assertIn("ikke betalt utbytte etter 1. mai 2026", tekst)
        self.assertIn("hele eller deler av virksomheten", tekst)
        self.assertNotIn("på rad", tekst)
        self.assertNotIn("buffer", tekst)


class TestNewswebUtsteder(unittest.TestCase):
    """En ukjent utsteder gir hele børsens nyeste meldinger, ikke en tom liste."""

    def test_fremmede_meldinger_filtreres_bort(self):
        gml = fs._newsweb_post, fs._NEWSWEB_API
        fs._NEWSWEB_API = "https://x"
        fs._newsweb_post = lambda url, data=None, timeout=10: {"data": {"messages": [
            {"issuerSign": "OTEC", "title": "Otello"},
            {"issuerSign": "AQUA", "title": "Aqualis"}]}}
        fs._NEWSWEB_LISTE.pop("XYZFOO", None)
        try:
            self.assertEqual(fs._newsweb_meldinger("XYZFOO"), [])
        finally:
            fs._newsweb_post, fs._NEWSWEB_API = gml
            fs._NEWSWEB_LISTE.pop("XYZFOO", None)

    def test_egne_meldinger_beholdes(self):
        gml = fs._newsweb_post, fs._NEWSWEB_API
        fs._NEWSWEB_API = "https://x"
        fs._newsweb_post = lambda url, data=None, timeout=10: {"data": {"messages": [
            {"issuerSign": "EQNR", "title": "Equinor"}, {"title": "uten utsteder"}]}}
        fs._NEWSWEB_LISTE.pop("EQNR", None)
        try:
            self.assertEqual(len(fs._newsweb_meldinger("EQNR")), 2)
        finally:
            fs._newsweb_post, fs._NEWSWEB_API = gml
            fs._NEWSWEB_LISTE.pop("EQNR", None)


class TestParseExMelding(unittest.TestCase):
    """Meldingen om at aksjen går ex i dag: ex-dato og beløp i kroner."""

    # Meldingene er forkortet; kontaktlinjene er tatt ut.
    SOFF = ("Issuer: Solstad Offshore ASA\n\nEx. Date: 10 March 2026\n\n"
            "Dividend amount: USD 0.05 per share\n\n"
            "Dividend amount in NOK: 0.48320 per share\n\n"
            "Announced currency: USD (please note that the dividend will be paid out in NOK)\n")
    WWI = ("The shares in Wilh. Wilhelmsen Holding ASA (ticker: WWI and WWIB) will be "
           "traded ex dividend NOK 8.00 as from today, 12 November 2025.\n\n"
           "The expected dividend payment date is 20 November 2025.")

    def test_soff_belop_i_kroner_fra_egen_linje(self):
        r = fs._parse_ex_melding("SOLSTAD OFFSHORE ASA: EX DIVIDEND USD 0.05 PER SHARE TODAY",
                                 self.SOFF, "2026-03-10T07:00:12.000Z")
        self.assertEqual(r, {"ex_dato": "2026-03-10", "belop": 0.4832})

    def test_wwi_publiseringsdagen_er_ex_dato(self):
        r = fs._parse_ex_melding("Wilh. Wilhelmsen Holding ASA: Ex dividend NOK 8.00 today",
                                 self.WWI, "2025-11-12T06:30:00.000Z")
        self.assertEqual(r, {"ex_dato": "2025-11-12", "belop": 8.0})

    def test_kronebelop_ved_siden_av_dollar(self):
        tekst = ("The shares in Odfjell SE will trade ex-dividend of USD 0.52/ NOK 4.87 "
                 "per share as from today August 26, 2026.")
        r = fs._parse_ex_melding("Odfjell SE: Shares trade ex-dividend USD 0.52 today",
                                 tekst, "2026-08-26T06:00:00Z")
        self.assertEqual(r["belop"], 4.87)

    def test_norsk_melding_med_desimalkomma(self):
        tekst = ("Egenkapitalbevisene i Grong Sparebank noteres ex utbytte NOK 10,5 "
                 "fra og med i dag, 09.04.2026.")
        r = fs._parse_ex_melding("Ex utbytte", tekst, "2026-04-09T06:00:00Z")
        self.assertEqual(r, {"ex_dato": "2026-04-09", "belop": 10.5})

    def test_bare_dollar_gir_ingenting(self):
        tekst = "The shares in Frontline plc will be traded ex dividend USD 1.55 as from today."
        self.assertIsNone(fs._parse_ex_melding("FRO - Ex dividend USD 1.55 today",
                                               tekst, "2026-06-11T06:00:00Z"))

    def test_to_ulike_kronebelop_er_tvetydig(self):
        tekst = "Ex dividend NOK 2.50 today. Last year the dividend was NOK 2.00."
        self.assertIsNone(fs._parse_ex_melding("Ex dividend today", tekst, "2026-05-04T06:00:00Z"))

    def test_storrelse_er_ikke_belop_per_aksje(self):
        tekst = "Ex dividend NOK 5.00 per share today, in total NOK 10.2 billion."
        r = fs._parse_ex_melding("Ex dividend today", tekst, "2026-05-04T06:00:00Z")
        self.assertEqual(r["belop"], 5.0)

    def test_ex_dato_langt_fra_publisering_avvises(self):
        tekst = "Ex. Date: 20 March 2026\nDividend amount in NOK: 1.00"
        self.assertIsNone(fs._parse_ex_melding("Ex dividend", tekst, "2026-03-05T06:00:00Z"))

    def test_annen_tittel_avvises(self):
        self.assertIsNone(fs._parse_ex_melding(
            "Key information relating to the cash dividend",
            "Ex-date: 10 March 2026\nDividend amount: NOK 1.00", "2026-02-16T06:00:00Z"))
        self.assertIsNone(fs._parse_ex_melding(
            "Extraordinary dividend NOK 1.00", "today", "2026-02-16T06:00:00Z"))

    def test_oslo_dato_fra_utc(self):
        # 23:30 UTC 9. mars er 00:30 10. mars i Oslo.
        self.assertEqual(fs._oslo_dato("2026-03-09T23:30:00.000Z"), datetime.date(2026, 3, 10))


@unittest.skipIf(pd is None, "pandas er ikke installert")
class TestSupplerUtbytteserie(unittest.TestCase):
    """SOFF manglet ex-datoen 10. mars 2026 hos Yahoo, som NewsWeb bekreftet."""

    I_DAG = datetime.date(2026, 10, 13)

    def serie(self, punkter):
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _ in punkter]).tz_localize("Europe/Oslo")
        return pd.Series([v for _, v in punkter], index=idx, dtype="float64")

    def soff(self):
        return self.serie([("2015-05-01", 1.0), ("2025-11-25", 0.5119),
                           ("2026-05-20", 0.9169), ("2026-07-17", 1.4592)])

    def test_soff_hullet_fylles(self):
        funn = [{"ex_dato": "2026-03-10", "belop": 0.4832, "melding_id": "667879"}]
        ny, lagt = fs.suppler_utbytteserie(self.soff(), funn, 72.0, self.I_DAG)
        self.assertEqual(lagt, funn)
        self.assertEqual(len(ny), 5)
        self.assertTrue(ny.index.is_monotonic_increasing)
        self.assertEqual(str(ny.index.tz), "Europe/Oslo")
        sum12, antall, _, _ = fs.betalt_fra_serie(ny, self.I_DAG)
        self.assertEqual((sum12, antall), (3.3712, 4))

    def test_kjent_utbetaling_legges_ikke_til_igjen(self):
        funn = [{"ex_dato": "2026-05-22", "belop": 0.92}]
        ny, lagt = fs.suppler_utbytteserie(self.soff(), funn, 72.0, self.I_DAG)
        self.assertEqual((len(ny), lagt), (4, []))

    def test_samme_utbetaling_to_meldinger_gir_en(self):
        # Equinor sender både «Ex. dividend» og «Ex. utbytte».
        funn = [{"ex_dato": "2026-03-10", "belop": 0.4832},
                {"ex_dato": "2026-03-10", "belop": 0.4832}]
        _, lagt = fs.suppler_utbytteserie(self.soff(), funn, 72.0, self.I_DAG)
        self.assertEqual(len(lagt), 1)

    def test_en_tom_serie_skapes_ikke(self):
        tom = pd.Series(dtype="float64", index=pd.DatetimeIndex([]))
        funn = [{"ex_dato": "2026-03-10", "belop": 0.4832}]
        ny, lagt = fs.suppler_utbytteserie(tom, funn, 72.0, self.I_DAG)
        self.assertEqual((len(ny), lagt), (0, []))

    def test_ingen_utbetaling_siste_ar_gir_ingen_tillegg(self):
        gammel = self.serie([("2024-05-01", 1.0), ("2024-09-01", 1.0)])
        funn = [{"ex_dato": "2026-03-10", "belop": 1.0}]
        self.assertEqual(fs.suppler_utbytteserie(gammel, funn, 72.0, self.I_DAG)[1], [])

    def test_belop_langt_fra_medianen_avvises(self):
        # Dellia: 4,60 i meldingen, 0,575 hos Yahoo etter splitten 1:8.
        s = self.serie([("2025-11-01", 0.5), ("2026-06-01", 0.575)])
        funn = [{"ex_dato": "2026-03-16", "belop": 4.6}]
        self.assertEqual(fs.suppler_utbytteserie(s, funn, 19.6, self.I_DAG)[1], [])

    def test_utbetaling_for_en_splitt_avvises(self):
        s = self.serie([("2025-11-01", 0.5), ("2026-06-01", 0.6)])
        funn = [{"ex_dato": "2026-03-16", "belop": 0.55}]
        _, lagt = fs.suppler_utbytteserie(s, funn, 19.6, self.I_DAG,
                                          splitter=[datetime.date(2026, 4, 1)])
        self.assertEqual(lagt, [])
        _, lagt = fs.suppler_utbytteserie(s, funn, 19.6, self.I_DAG,
                                          splitter=[datetime.date(2026, 3, 1)])
        self.assertEqual(len(lagt), 1)

    def test_framtidig_ex_dato_avvises(self):
        funn = [{"ex_dato": "2026-10-20", "belop": 1.0}]
        self.assertEqual(fs.suppler_utbytteserie(self.soff(), funn, 72.0, self.I_DAG)[1], [])


class TestSupplertFotnote(unittest.TestCase):
    """Fotnoten i «Faktisk betalt» står bare der en utbetaling er lagt til."""

    def test_ingen_tillegg_ingen_fotnote(self):
        self.assertEqual(fs.supplert_fotnote({}), "")
        self.assertEqual(fs.supplert_fotnote({"utbytte_supplert": []}), "")

    def test_en_og_flere(self):
        en = fs.supplert_fotnote({"utbytte_supplert": [{"ex_dato": "2026-03-10", "belop": 0.4832}]})
        self.assertTrue(en.startswith("Utbetalingen med ex-dato 10. mar 2026 mangler"))
        to = fs.supplert_fotnote({"utbytte_supplert": [
            {"ex_dato": "2026-03-10", "belop": 0.48}, {"ex_dato": "2025-11-12", "belop": 8.0}]})
        self.assertIn("Utbetalingene med ex-dato 12. nov 2025 og 10. mar 2026", to)

    def test_star_i_betalt_boksen(self):
        a = {"pris": 72.3, "utbytte_12m": 3.3712, "utbytte_forste_ar": 2000,
             "utbytte_per_ar": {"2021": 0.0, "2022": 0.0, "2023": 0.0, "2024": 0.0, "2025": 0.5119}}
        self.assertNotIn("Yahoos utbytteserie", fs.lag_betalt_boks(a, fs._nf))
        a["utbytte_supplert"] = [{"ex_dato": "2026-03-10", "belop": 0.4832}]
        self.assertIn("hentet fra selskapets melding til Oslo Børs", fs.lag_betalt_boks(a, fs._nf))


class TestNewswebExMeldinger(unittest.TestCase):
    """Bare meldinger uten en Yahoo-utbetaling i nærheten åpnes."""

    def kjor(self, meldinger, tekster, kjente):
        gml = fs._newsweb_meldinger, fs._newsweb_tekst
        apnet = []

        def tekst(mid):
            apnet.append(mid)
            return tekster.get(mid, "")
        fs._newsweb_meldinger = lambda t: meldinger
        fs._newsweb_tekst = tekst
        try:
            funn = fs.newsweb_ex_meldinger("SOFF", datetime.date(2026, 10, 13), kjente)
        finally:
            fs._newsweb_meldinger, fs._newsweb_tekst = gml
        return funn, apnet

    def test_apner_bare_hullet(self):
        meldinger = [
            {"messageId": 3, "publishedTime": "2026-07-17T06:00:00Z",
             "title": "SOLSTAD OFFSHORE ASA: EX DIVIDEND USD 0.15 PER SHARE TODAY"},
            {"messageId": 2, "publishedTime": "2026-03-10T06:00:00Z",
             "title": "SOLSTAD OFFSHORE ASA: EX DIVIDEND USD 0.05 PER SHARE TODAY"},
            {"messageId": 1, "publishedTime": "2026-02-16T06:00:00Z",
             "title": "Solstad Offshore ASA - Key information relating to Q4 2025 dividend"},
        ]
        funn, apnet = self.kjor(meldinger, {2: TestParseExMelding.SOFF},
                                [datetime.date(2026, 7, 17)])
        self.assertEqual(apnet, [2])
        self.assertEqual(funn, [{"ex_dato": "2026-03-10", "belop": 0.4832, "melding_id": "2"}])

    def test_rettet_melding_brukes_ikke(self):
        # Grong: 10,50 i meldingen 9. april, 11 i rettelsen dagen etter.
        meldinger = [
            {"messageId": 2, "publishedTime": "2026-04-10T06:00:00Z", "title": "Ex utbytte, korrigert"},
            {"messageId": 1, "publishedTime": "2026-04-09T06:00:00Z", "title": "Ex utbytte"},
        ]
        tekster = {1: "noteres ex utbytte NOK 10,5 fra og med i dag, 09.04.2026."}
        funn, _ = self.kjor(meldinger, tekster, [datetime.date(2025, 4, 9)])
        self.assertEqual(funn, [])

    def test_nettverksfeil_gir_tom_liste(self):
        gml = fs._newsweb_meldinger

        def feil(t):
            raise OSError("tidsavbrudd")
        fs._newsweb_meldinger = feil
        try:
            self.assertEqual(fs.newsweb_ex_meldinger("SOFF", datetime.date(2026, 10, 13), []), [])
        finally:
            fs._newsweb_meldinger = gml


class TestSidemeny(unittest.TestCase):
    """Menyen står kopiert inn i hver håndskrevne side og i malen.

    17.10.2026: /avnoteringer/ fantes ikke i menyen, undermenyene var skjult
    på mobil, «Åpne app» gikk til forsiden på 203 sider, og /avnoteringer/
    manglet skriptet som åpner menyen. Ingenting målte at kopiene var like.
    """

    ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @staticmethod
    def _lenker(tekst):
        m = re.search(r'<ul class="site-nav-menu">(.*?)</ul>\s*<div class="site-nav-actions">',
                      tekst, re.S)
        return re.findall(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', m.group(1)) if m else None

    def _haandskrevne(self):
        for mappe, undermapper, filer in os.walk(self.ROT):
            rel = os.path.relpath(mappe, self.ROT).replace(os.sep, "/")
            undermapper[:] = [d for d in undermapper
                              if not d.startswith(".") and d != "node_modules"
                              and not (rel == "." and d in ("aksjer", "rapportkalender"))]
            for f in filer:
                if f.endswith(".html"):
                    sti = os.path.join(mappe, f)
                    with open(sti, encoding="utf-8") as fh:
                        tekst = fh.read()
                    if 'class="site-nav"' in tekst:
                        yield os.path.relpath(sti, self.ROT), tekst

    def test_malen_har_avnoteringer_og_appen(self):
        mal = fs._site_nav_html()
        self.assertIn(("/avnoteringer/", "Avnoterte aksjer"), self._lenker(mal))
        self.assertIn('href="/app/" class="site-app-btn"', mal)

    def test_haandskrevne_sider_har_samme_meny_som_malen(self):
        mal = self._lenker(fs._site_nav_html())
        sider = list(self._haandskrevne())
        self.assertGreater(len(sider), 20)
        for sti, tekst in sider:
            with self.subTest(side=sti):
                self.assertEqual(self._lenker(tekst), mal)
                self.assertIn('href="/app/" class="site-app-btn"', tekst)
                self.assertIn("toggle('open')", tekst, "menyknappen gjør ingenting uten skriptet")
                knapp = re.search(r'<button id="([^"]+)" class="site-dark-btn"', tekst)
                self.assertTrue(knapp, "ingen temaknapp")
                self.assertRegex(tekst, r"getElementById\(['\"]%s['\"]\)" % re.escape(knapp.group(1)),
                                 "ingen skript leser temaknappens id")


class TestTallkontroll1910(unittest.TestCase):
    """Malfunnene fra tallkontrollen 19.10.2026, hvert med sin motsigelse."""

    IAAR = datetime.date.today().year

    def _hist(self, belop, iaar_belop=None):
        """Hele år bakover fra i fjor, pluss en delvis rad for i år."""
        start = self.IAAR - len(belop)
        rader = [{"ar": start + i, "utbytte": b} for i, b in enumerate(belop)]
        if iaar_belop is not None:
            rader.append({"ar": self.IAAR, "utbytte": iaar_belop})
        return rader

    def _rad(self, **felt):
        a = {"ticker": "TEST", "navn": "Test ASA", "sektor": "Finans", "payout_ratio": 85,
             "utbytte_yield": 4.0, "markedsverdi": 5e9}
        a.update(felt)
        return a

    # S1: delårsraden er ikke et kutt (TGS).
    def test_delaar_er_ikke_kutt(self):
        a = self._rad(historiske_utbytter=self._hist([5.47, 5.91, 6.03, 6.46], 4.40))
        self.assertEqual(fs.utbyttekutt(a), [])
        tekst = fs._lag_nedtur_test(a)
        self.assertNotIn("satt ned utbyttet før", tekst)
        self.assertIn("ikke kuttet", tekst)

    def test_kutt_mellom_hele_ar_teller(self):
        a = self._rad(historiske_utbytter=self._hist([5.0, 3.25, 3.75, 4.25], 4.75))
        self.assertEqual(len(fs.utbyttekutt(a)), 1)
        self.assertIn("satt ned utbyttet før", fs._lag_nedtur_test(a))

    # S2: tre år er «Moderat» i merket, og da ikke «Kort» i risikolista (STST).
    def test_tre_ar_er_ikke_kort(self):
        a = self._rad(ar_med_utbytte=3, utbytteaar=[self.IAAR - 2, self.IAAR - 1, self.IAAR])
        self.assertIn("Moderat utbyttehistorikk (3 år)", fs._lag_investor_badges(a))
        self.assertFalse(any("Kort utbyttehistorikk" in r for r in fs._selskapsrisikoer(a)))
        self.assertNotIn("begrenset", fs._lag_investor_vurdering(a, {}))

    # S3: en lang historikk med brudd er ikke «begrenset» (STB, SPOG).
    def test_brutt_lang_historikk(self):
        aar = list(range(self.IAAR - 20, self.IAAR - 6)) + list(range(self.IAAR - 4, self.IAAR + 1))
        a = self._rad(ar_med_utbytte=len(aar), utbytteaar=aar)
        tekst = fs._lag_investor_vurdering(a, {})
        self.assertNotIn("begrenset", tekst)
        self.assertIn(f"i {len(aar)} av årene", tekst)

    # S4: kutt gir verken «Stabil inntekt» eller «Lav risiko» (SRHA).
    def test_kutt_gir_ikke_stabil_eller_lav(self):
        aar = list(range(self.IAAR - 10, self.IAAR + 1))
        a = self._rad(payout_ratio=40, markedsverdi=20e9, utbytteaar=aar, ar_med_utbytte=len(aar),
                      historiske_utbytter=self._hist([16.2, 13.1, 14.0, 15.0], 9.0))
        self.assertNotIn("stabil", fs._beregn_mal_py(a))
        self.assertNotEqual(fs._beregn_risiko_py(a), "lav")
        a["historiske_utbytter"] = self._hist([12.0, 13.1, 14.0, 15.0], 9.0)
        self.assertIn("stabil", fs._beregn_mal_py(a))
        self.assertEqual(fs._beregn_risiko_py(a), "lav")

    # S5: 40 % over snittet er ikke «nær» (STB 2,9 mot 2,0).
    def test_relativt_band_mot_eget_snitt(self):
        a = self._rad(utbytte_yield=2.9, snitt_yield_5ar=2.0, snitt_yield_ar=5,
                      historiske_utbytter=self._hist([1, 1, 1, 1]))
        tekst = fs._lag_utbyttehistorikk_tekst(a)
        self.assertIn("ligger over aksjens eget", tekst)
        self.assertNotIn("nær", tekst)

    # S6: payout over 100 % er ikke «nesten hele» (SPOG 130 %).
    def test_payout_over_hundre(self):
        risiko = " ".join(fs._selskapsrisikoer(self._rad(payout_ratio=130)))
        self.assertIn("mer enn det tjener", risiko)
        self.assertNotIn("nesten hele", risiko)
        self.assertIn("nesten hele", " ".join(fs._selskapsrisikoer(self._rad(payout_ratio=95))))

    # SUBC: ingen doblingstid fra +59,7 % per år.
    def test_ingen_doblingstid_over_taket(self):
        a = self._rad(utbytte_vekst_5ar=59.7, utbytte_yield=3.0)
        tekst = fs._lag_investor_badges(a)
        self.assertNotIn("dobles utbyttet", tekst)
        self.assertIn("regner den ikke fram", tekst)
        a["utbytte_vekst_5ar"] = 10.0
        self.assertIn("dobles utbyttet på ca. 7 år", fs._lag_investor_badges(a))


class TestBransje(unittest.TestCase):
    """Forsikring fikk banktekst og seismikk riggtekst (tallkontrollen 2026-10-19)."""

    def test_hver_bransje_har_tekst_og_risiko(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "data", "tickers.json"),
                  encoding="utf-8") as f:
            bransjer = {t["bransje"] for t in json.load(f) if t.get("bransje")}
        self.assertTrue(bransjer)
        for b in bransjer:
            with self.subTest(bransje=b):
                self.assertIn(b, fs._BRANSJE_DRIVER_UTDYPET)
                self.assertIn(b, fs.BRANSJE_RISIKOER)

    def test_storebrand_far_forsikringstekst(self):
        self.assertEqual(fs.BRANSJE.get("STB"), "forsikring")
        a = {"ticker": "STB", "navn": "Storebrand ASA", "sektor": "Finans", "utbytte_yield": 3.0}
        side = fs._lag_investor_vurdering(a, {})
        self.assertIn("Solvenskravene", side)
        self.assertNotIn("Netto renteinntekter", side)
        self.assertIn("Store skadeår", fs._lag_risikofaktorer(a))


class TestHendelse(unittest.TestCase):
    """Oppkjøp, fusjon og avvikling på aksjesiden (tallkontrollen 2026-10-19)."""

    H = {"type": "avvikling", "dato": "2026-08-05", "melding": "679057",
         "tekst": "Styret vil selge flåten <innen> 18 måneder."}

    def test_boks_med_kilde_og_escaping(self):
        boks = fs.lag_hendelse_boks({"hendelse": self.H})
        self.assertIn("Virksomheten skal avvikles", boks)
        self.assertIn("&lt;innen&gt;", boks)
        self.assertIn("https://newsweb.oslobors.no/message/679057", boks)
        self.assertIn("5. aug", boks)

    def test_ugyldig_gir_ingenting(self):
        self.assertEqual(fs.lag_hendelse_boks({"hendelse": {"type": "noe", "tekst": "x"}}), "")
        self.assertEqual(fs.lag_hendelse_boks({}), "")
        boks = fs.lag_hendelse_boks({"hendelse": dict(self.H, melding="x\"><script>")})
        self.assertNotIn("newsweb", boks)

    def test_mal_faller_bort_bare_ved_avgjorte_hendelser(self):
        a = {"sektor": "Finans", "utbytte_yield": 7.0, "frekvens": "Kvartalsvis"}
        self.assertTrue(fs._beregn_mal_py(a))
        self.assertEqual(fs._beregn_mal_py(dict(a, hendelse=self.H)), [])
        mulig = dict(self.H, type="mulig_fusjon")
        self.assertTrue(fs._beregn_mal_py(dict(a, hendelse=mulig)))

    def test_sett_hendelse(self):
        a = {"hendelse": {"type": "gammel"}}
        fs.sett_hendelse(a, None)
        self.assertNotIn("hendelse", a)
        fs.sett_hendelse(a, self.H)
        self.assertEqual(a["hendelse"]["melding"], "679057")

    def test_undertittelen_viser_markedsplassen(self):
        # Alle 155 sider sa «Oslo Børs», også de 14 på Euronext Growth.
        sti = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aksjer.json")
        if not os.path.exists(sti):
            self.skipTest("aksjer.json finnes ikke")
        with open(sti, encoding="utf-8") as f:
            a = json.load(f)["aksjer"][0]
        for bors in ("Euronext Growth Oslo", "Oslo Børs"):
            with self.subTest(bors=bors):
                side = fs._aksje_side_html(dict(a, kurs_historikk=[], bors=bors), "2026-10-26")
                sub = re.search(r'<p class="sub">(.*?)</p>', side).group(1)
                self.assertTrue(sub.endswith("· " + bors), sub)

    def test_appen_kjenner_de_samme_typene(self):
        # Cadeler fikk en ny type (2026-10-26). Mangler den i ui.js, viser
        # appen ingen boks og intet merke, uten feilmelding.
        with open(os.path.join(os.path.dirname(__file__), "..", "assets", "ui.js"),
                  encoding="utf-8") as f:
            js = f.read()
        for konst in ("HENDELSE_TITTEL", "HENDELSE_KORT"):
            with self.subTest(konst=konst):
                blokk = re.search(r"const " + konst + r" = \{(.*?)\n\};", js, re.S).group(1)
                self.assertEqual(set(re.findall(r"^\s+(\w+):", blokk, re.M)),
                                 set(fs.HENDELSE_TITTEL))

    def test_bytte_av_hjemland_beholder_maal(self):
        a = {"sektor": "Energitjenester", "utbytte_yield": 7.0, "frekvens": "Kvartalsvis"}
        h = dict(self.H, type="bytte_av_hjemland")
        self.assertIn("flytter til et annet land", fs.lag_hendelse_boks({"hendelse": h}))
        self.assertEqual(fs._beregn_mal_py(dict(a, hendelse=h)), fs._beregn_mal_py(a))

    def test_hendelsene_i_tickers_er_gyldige(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "data", "tickers.json"),
                  encoding="utf-8") as f:
            hendelser = {t["ticker"]: t["hendelse"] for t in json.load(f) if t.get("hendelse")}
        self.assertTrue(hendelser)
        for ticker, h in hendelser.items():
            with self.subTest(ticker=ticker):
                self.assertTrue(fs.gyldig_hendelse(h))
                self.assertRegex(h.get("melding", ""), r"^\d+$")
                datetime.date.fromisoformat(h["dato"])
                self.assertNotIn("—", h["tekst"])


class TestHullaar(unittest.TestCase):
    """Hele år uten utbetaling mellom to betalte år slås opp i NewsWeb-arkivet."""

    I_DAG = datetime.date(2026, 10, 19)
    D = datetime.date

    def test_spog_2023(self):
        kjente = [self.D(y, 3, 24) for y in (2020, 2021, 2022, 2024, 2025, 2026)]
        self.assertEqual(fs.hullaar(kjente, self.I_DAG), [2023])

    def test_ar_for_forste_utbetaling_er_ikke_hull(self):
        kjente = [self.D(y, 5, 1) for y in (2024, 2025, 2026)]
        self.assertEqual(fs.hullaar(kjente, self.I_DAG), [])

    def test_bare_innenfor_vinduet(self):
        kjente = [self.D(2010, 5, 1), self.D(2025, 5, 1)]
        self.assertEqual(fs.hullaar(kjente, self.I_DAG), [2021, 2022, 2023, 2024])
        self.assertEqual(fs.hullaar([], self.I_DAG), [])

    def test_norske_ex_titler(self):
        f = fs._parse_ex_melding("Skue Sparebank - eks utbytte NOK 12,50 i dag", "",
                                 "2023-03-24T06:00:00Z")
        self.assertEqual(f, {"ex_dato": "2023-03-24", "belop": 12.5})
        f = fs._parse_ex_melding("Eks. utbytte kr 10,50 frå i dag",
                                 "Kr 10,50 i utbytte vart vedteke på generalforsamlinga.",
                                 "2023-04-27T06:00:00Z")
        self.assertEqual(f, {"ex_dato": "2023-04-27", "belop": 10.5})
        # Et beløp i millioner er ikke per aksje.
        self.assertIsNone(fs._parse_ex_melding("Eks. utbytte i dag",
                                               "Samlet utbytte kr 120 millioner.",
                                               "2023-04-27T06:00:00Z"))


class TestNokOmregning(unittest.TestCase):
    """Kronebeløpet selskapet selv fastsetter, der Yahoo har et foreløpig beløp.

    Equinor 2023: Yahoo hadde 8,42 kr for tre utbetalinger, selskapet meldte
    9,02, 9,58 og 9,41 kr (NewsWeb 580174, 591103, 597337). Tekstene under er
    forkortet fra meldingenes form, uten kontaktpersoner.
    """

    NY = ("The NOK cash dividend per share is based on average USDNOK fixing rate from "
          "Norges Bank in the period plus/minus three business days from record date. "
          "Total cash dividend for first quarter 2026 is consequently NOK 3.6882 per share.")
    GAMMEL = ("The NOK dividend per share is based on average USDNOK fixing rate from Norges "
              "Bank. Second quarter 2021 dividend per share is consequently NOK 1.5572.")
    NORSK = ("Utbytte per aksje i NOK er basert på gjennomsnittlig USDNOK valutakurs fra "
             "Norges Bank. Utbyttet er følgelig NOK 9,0159 per aksje.")

    def serie(self, verdier):
        import pandas as pd
        idx = pd.DatetimeIndex([pd.Timestamp(d) for d in verdier]).tz_localize("Europe/Oslo")
        return pd.Series(list(verdier.values()), index=idx, dtype="float64")

    def test_parser_ny_gammel_og_norsk_form(self):
        self.assertEqual(fs.parse_nok_omregning(self.NY), 3.6882)
        self.assertEqual(fs.parse_nok_omregning(self.GAMMEL), 1.5572)
        self.assertEqual(fs.parse_nok_omregning(self.NORSK), 9.0159)

    def test_krever_valutakurs_og_ett_belop(self):
        # Et selskap som vedtar i kroner, nevner ingen valutakurs.
        self.assertIsNone(fs.parse_nok_omregning(
            "The board resolved a dividend that will be NOK 3.00 per share."))
        self.assertIsNone(fs.parse_nok_omregning(
            self.NY + " The second installment is accordingly NOK 0.5000 per share."))
        self.assertIsNone(fs.parse_nok_omregning("fixing rate. Proceeds will be NOK 2.5 billion."))
        self.assertIsNone(fs.parse_nok_omregning(""))

    def test_retter_forelopige_belop_for_equinor_2023(self):
        s = self.serie({"2023-01-09": 8.4217, "2023-05-11": 8.4217,
                        "2023-08-14": 8.4217, "2023-11-14": 9.8519})
        meld = [{"publisert": "2023-01-16", "belop": 9.0159, "melding_id": "580174"},
                {"publisert": "2023-05-22", "belop": 9.5753, "melding_id": "591103"},
                {"publisert": "2023-08-21", "belop": 9.4091, "melding_id": "597337"},
                {"publisert": "2023-11-21", "belop": 9.8519, "melding_id": "604509"}]
        ny, rettet = fs.korriger_med_nok_omregning(s, meld)
        self.assertAlmostEqual(float(ny.sum()), 37.8522, places=4)
        self.assertEqual([r["ex_dato"] for r in rettet], ["2023-01-09", "2023-05-11", "2023-08-14"])
        self.assertEqual(rettet[0]["yahoo"], 8.4217)
        self.assertAlmostEqual(float(s.sum()), 35.1170, places=4)   # originalen er urørt

    def test_uklart_eller_for_stort_avvik_endrer_ingenting(self):
        # To utbetalinger i vinduet: uklart hvilken meldingen gjelder.
        s = self.serie({"2025-10-10": 0.50, "2025-10-15": 0.60})
        meld = [{"publisert": "2025-10-23", "belop": 0.55}]
        self.assertEqual(fs.korriger_med_nok_omregning(s, meld)[1], [])
        # Over 25 % avvik er heller en annen utbetaling enn et foreløpig beløp.
        s = self.serie({"2025-10-15": 0.50})
        self.assertEqual(fs.korriger_med_nok_omregning(s, [{"publisert": "2025-10-23", "belop": 1.00}])[1], [])
        # Meldingen kom for lenge etter ex-datoen.
        self.assertEqual(fs.korriger_med_nok_omregning(s, [{"publisert": "2025-12-23", "belop": 0.52}])[1], [])
        # Under en halv prosent er avrunding, ikke et foreløpig beløp.
        self.assertEqual(fs.korriger_med_nok_omregning(s, [{"publisert": "2025-10-23", "belop": 0.501}])[1], [])

    def test_fotnote_nevner_rettede_utbetalinger(self):
        a = {"utbytte_korrigert": [{"ex_dato": "2023-01-09", "yahoo": 8.42, "belop": 9.02}]}
        tekst = fs.supplert_fotnote(a)
        self.assertIn("kronebeløpet selskapet meldte til Oslo Børs", tekst)
        self.assertIn("foreløpig beløp", tekst)
        self.assertNotIn("mangler i Yahoos", tekst)


class TestFaqHistorikk(unittest.TestCase):
    """FAQ-svaret om historikken bruker hele år, ikke det som er betalt hittil i år.

    Equinor 22.10.2026: «Høyest enkeltutbytte var 37,85 NOK i 2023, lavest
    10,82 NOK i 2026», der 2026 bare var betalt hittil.
    """

    RAD = {"ticker": "EQNR", "navn": "Equinor ASA", "valuta": "NOK", "utbytte_yield": 3.37,
           "utbytte_per_aksje": 14.55, "pris": 431.8, "utbytte_forste_ar": 2001,
           "utbytte_per_ar": {"2021": 4.8078, "2022": 16.4282, "2023": 37.8522,
                              "2024": 32.1646, "2025": 19.1553},
           "historiske_utbytter": [{"ar": 2026, "utbytte": 10.82}, {"ar": 2025, "utbytte": 19.16},
                                   {"ar": 2024, "utbytte": 32.16}]}

    def svar(self, a, i_dag="2026-10-22"):
        html_, _ = fs._lag_faq_seksjon(a, i_dag)
        return html_

    def test_inneverende_aar_er_ikke_lavest(self):
        t = self.svar(self.RAD)
        self.assertNotIn("lavest 10,82", t)
        self.assertNotIn("enkeltutbytte", t)
        self.assertIn("I de hele årene 2021–2025 betalte Equinor ASA til sammen 110,41 kroner", t)
        self.assertIn("Høyest var 2023 med 37,85 kroner, lavest 2021 med 4,81 kroner.", t)
        self.assertIn("Hittil i 2026 er det betalt 10,82 kroner per aksje.", t)

    def test_aar_uten_utbytte_og_aar_for_forste(self):
        a = dict(self.RAD, utbytte_forste_ar=2022,
                 utbytte_per_ar={"2021": 0, "2022": 2.0, "2023": 0, "2024": 3.0, "2025": 3.5})
        t = self.svar(a)
        self.assertIn("2022–2025", t)                 # 2021 er før første utbytte
        self.assertIn("I 2023 har vi ikke registrert noe utbytte.", t)

    def test_kjop_senest_borsdagen_for(self):
        a = dict(self.RAD, ex_dato="2026-11-13")
        t = self.svar(a)
        self.assertIn("må du kjøpe aksjen senest 12. november, børsdagen før ex-datoen", t)


class TestTallformat(unittest.TestCase):
    def test_tusenskille_og_prosent(self):
        self.assertEqual(fs._nf_tusen(1022.7, 1), "1\u00a0022,7")
        self.assertEqual(fs._pst(3.37), "3,37\u00a0%")
        self.assertEqual(fs._ganger(2), "to ganger")
        self.assertEqual(fs._ganger(12), "12 ganger")


class TestAnnetSelskap(unittest.TestCase):
    """En ex-melding om et annet selskap er ikke vår utbetaling (20.10.2026).

    SOFF publiserte «Solstad Maritime Holding AS: Ex dividend today» om
    datterselskapets utbytte. Hullårsoppslaget la det inn i SOFFs serie, og
    yielden falt fra 4,66 til 0,71 %. Tekstene her er syntetiske.
    """

    SOFF = ("SOFF", "Solstad Offshore ASA")

    def test_datterselskap_i_tittelen(self):
        self.assertTrue(fs.melding_gjelder_annet_selskap(
            "Solstad Maritime Holding AS: Ex dividend today", "", *self.SOFF))

    def test_annen_utsteder_i_teksten(self):
        tekst = "Issuer: Solstad Maritime Holding AS Ex-date: 15 November 2024"
        self.assertTrue(fs.melding_gjelder_annet_selskap("Ex dividend today", tekst, *self.SOFF))

    def test_eget_selskap_gir_false(self):
        tekst = "Issuer: Solstad Offshore ASA Ex-date: 10 March 2026 Dividend amount in NOK: 0.48"
        for tittel in ("Solstad Offshore ASA: Ex dividend today", "Ex dividend today",
                       "SOFF: Ex dividend today", "SOFF - Ex dividend today"):
            self.assertFalse(fs.melding_gjelder_annet_selskap(tittel, tekst, *self.SOFF), tittel)

    def test_prefiks_teller_som_samme_selskap(self):
        # WWI og WWIB er A- og B-aksjen i samme selskap.
        self.assertFalse(fs.melding_gjelder_annet_selskap(
            "Wilh. Wilhelmsen Holding ASA: Ex dividend NOK 8.00 today", "",
            "WWIB", "Wilh. Wilhelmsen Holding ASA B"))
        self.assertFalse(fs.melding_gjelder_annet_selskap(
            "Sparebanken Øst - eks utbytte i dag", "", "SPOG", "Sparebanken Øst"))

    def test_ex_funn_hopper_over_annet_selskap(self):
        meldinger = [
            {"publishedTime": "2024-11-15T06:00:00Z", "messageId": 1,
             "title": "Solstad Maritime Holding AS: Ex dividend today"},
            {"publishedTime": "2026-03-10T06:00:00Z", "messageId": 2,
             "title": "Solstad Offshore ASA: Ex dividend today"},
        ]
        tekster = {1: "Dividend amount in NOK: 0.50",
                   2: "Dividend amount in NOK: 0.48320"}
        gml = fs._newsweb_tekst
        fs._newsweb_tekst = lambda mid: tekster.get(mid, "")
        try:
            funn = fs._ex_funn_i(meldinger, datetime.date(2026, 10, 20),
                                 datetime.date(2024, 1, 1), [], *self.SOFF)
        finally:
            fs._newsweb_tekst = gml
        self.assertEqual([f["ex_dato"] for f in funn], ["2026-03-10"])


class TestBorsdager(unittest.TestCase):
    """«Kjøp senest» er forrige børsdag, ikke dagen før (19.10.2026).

    En ex-dato på mandag ga søndag. IWS' egen melding sier «Last day including
    right: 4 September 2026» om ex-datoen mandag 7. september.
    """

    D = datetime.date

    def test_fridager_2026_som_euronext(self):
        forventet = {self.D(2026, 1, 1), self.D(2026, 4, 2), self.D(2026, 4, 3),
                     self.D(2026, 4, 6), self.D(2026, 5, 1), self.D(2026, 5, 14),
                     self.D(2026, 5, 25), self.D(2026, 12, 24), self.D(2026, 12, 25),
                     self.D(2026, 12, 31)}
        hverdager = {d for d in fs.borsfridager(2026) if d.weekday() < 5}
        self.assertEqual(hverdager, forventet)

    def test_paaske(self):
        self.assertEqual(fs._paaskedag(2026), self.D(2026, 4, 5))
        self.assertEqual(fs._paaskedag(2027), self.D(2027, 3, 28))
        self.assertEqual(fs._paaskedag(2025), self.D(2025, 4, 20))

    def test_mandag_gir_fredag(self):
        self.assertEqual(fs.forrige_borsdag(self.D(2026, 9, 7)), self.D(2026, 9, 4))

    def test_vanlig_ukedag_gir_dagen_for(self):
        self.assertEqual(fs.forrige_borsdag(self.D(2026, 11, 13)), self.D(2026, 11, 12))

    def test_etter_paaske_hopper_over_fridagene(self):
        # Tirsdag etter påske: 2. påskedag, langfredag og skjærtorsdag er stengt.
        self.assertEqual(fs.forrige_borsdag(self.D(2026, 4, 7)), self.D(2026, 4, 1))

    def test_ingen_borsdag_i_helg(self):
        self.assertFalse(fs.er_borsdag(self.D(2026, 10, 17)))
        self.assertTrue(fs.er_borsdag(self.D(2026, 10, 19)))

    def test_faq_sier_fredag_for_mandag(self):
        a = {"ticker": "IWS", "navn": "Integrated Wind Solutions ASA", "ex_dato": "2026-09-07"}
        faq = fs._lag_faq_seksjon(a, "2026-09-01")[0]
        self.assertIn("senest 4. september", faq)
        self.assertNotIn("6. september", faq)


class TestUkaBlokk(unittest.TestCase):
    """«Denne uka på Oslo Børs» på forsiden."""

    I_DAG = datetime.date(2026, 11, 9)  # mandag

    def _aksje(self, ticker, **felt):
        return dict({"ticker": ticker, "navn": f"{ticker} ASA", "markedsverdi_mrd": 10}, **felt)

    def test_ex_i_dag_er_for_sent(self):
        h = fs.uka_hendelser([self._aksje("AAA", ex_dato="2026-11-09")], self.I_DAG)
        self.assertEqual(h["ex"], [])

    def test_ex_innen_sju_dager_og_neste_etter(self):
        aksjer = [self._aksje("AAA", ex_dato="2026-11-16"),
                  self._aksje("BBB", ex_dato="2026-11-17"),
                  self._aksje("CCC", ex_dato="2026-12-01")]
        h = fs.uka_hendelser(aksjer, self.I_DAG)
        self.assertEqual([r["ticker"] for r in h["ex"]], ["AAA"])
        self.assertEqual(h["ex"][0]["kjop_senest"], datetime.date(2026, 11, 13))
        self.assertEqual(h["neste"]["ex"]["ticker"], "BBB")

    def test_sortert_paa_dato_saa_storst(self):
        aksjer = [self._aksje("LITEN", rapport_dato="2026-11-10", markedsverdi_mrd=1),
                  self._aksje("STOR", rapport_dato="2026-11-10", markedsverdi_mrd=500),
                  self._aksje("TIDLIG", rapport_dato="2026-11-09", markedsverdi_mrd=0)]
        h = fs.uka_hendelser(aksjer, self.I_DAG)
        self.assertEqual([r["ticker"] for r in h["rapport"]], ["TIDLIG", "STOR", "LITEN"])

    def test_belop_bare_for_samme_ex_dato(self):
        aksjer = [self._aksje("AAA", ex_dato="2026-11-12", annonsert_utbytte=2.5,
                              annonsert_ex="2026-11-12"),
                  self._aksje("BBB", ex_dato="2026-11-12", annonsert_utbytte=2.5,
                              annonsert_ex="2026-05-12")]
        rader = {r["ticker"]: r for r in fs.uka_hendelser(aksjer, self.I_DAG)["ex"]}
        self.assertEqual(rader["AAA"]["belop"], 2.5)
        self.assertIsNone(rader["BBB"]["belop"])
        html_ut = fs.lag_uka_blokk(fs.uka_hendelser(aksjer, self.I_DAG), self.I_DAG)
        self.assertIn("2,50 kr", html_ut)

    def test_ugyldig_ticker_hoppes_over_og_navn_escapes(self):
        aksjer = [self._aksje("x<y", ex_dato="2026-11-12"),
                  self._aksje("AAA", navn="A & <B>", ex_dato="2026-11-12")]
        h = fs.uka_hendelser(aksjer, self.I_DAG)
        self.assertEqual([r["ticker"] for r in h["ex"]], ["AAA"])
        html_ut = fs.lag_uka_blokk(h, self.I_DAG)
        self.assertIn("A &amp; &lt;B&gt;", html_ut)
        self.assertNotIn("<B>", html_ut)

    def test_tom_liste_sier_naar_neste_kommer(self):
        h = fs.uka_hendelser([self._aksje("ENH", navn="Energi PLC", ex_dato="2026-11-30")], self.I_DAG)
        html_ut = fs.lag_uka_blokk(h, self.I_DAG)
        self.assertIn("Ingen ex-datoer de neste sju dagene. Neste ex-dato er man. 30. nov", html_ut)
        self.assertIn('href="/aksjer/ENH/"', html_ut)

    def test_maks_seks_rader_og_se_alle(self):
        aksjer = [self._aksje(f"R{i}", rapport_dato="2026-11-10") for i in range(9)]
        html_ut = fs.lag_uka_blokk(fs.uka_hendelser(aksjer, self.I_DAG), self.I_DAG)
        self.assertEqual(html_ut.count("<li>"), 6)
        self.assertIn("Se alle 9", html_ut)

    def test_forslag_merkes(self):
        a = self._aksje("GOD", ex_dato="2026-11-12", ex_forbehold="2026-11-11")
        html_ut = fs.lag_uka_blokk(fs.uka_hendelser([a], self.I_DAG), self.I_DAG)
        self.assertIn("foreslått, ikke vedtatt", html_ut)

    def test_hentet_i_oslotid(self):
        html_ut = fs.lag_uka_blokk(fs.uka_hendelser([], self.I_DAG), self.I_DAG,
                                   hentet="2026-11-09T06:41:00Z")
        self.assertIn("Tallene er hentet man. 9. nov kl. 07.41.", html_ut)

    def test_oppdater_forside_er_idempotent(self):
        with tempfile.TemporaryDirectory() as mappe:
            sti = os.path.join(mappe, "index.html")
            with open(sti, "w", encoding="utf-8") as f:
                f.write("<main>\n  <!--UKA:START-->\n  <!--UKA:SLUTT-->\n</main>\n")
            aksjer = [self._aksje("AAA", ex_dato="2026-11-12")]
            self.assertTrue(fs.oppdater_forside_uka(aksjer, mappe, self.I_DAG, hentet=""))
            self.assertFalse(fs.oppdater_forside_uka(aksjer, mappe, self.I_DAG, hentet=""))
            with open(sti, encoding="utf-8") as f:
                tekst = f.read()
            self.assertIn("Ex tor. 12. nov · kjøp senest ons. 11. nov", tekst)
            self.assertTrue(tekst.startswith("<main>") and tekst.endswith("</main>\n"))

    def test_uten_markor_endres_ingenting(self):
        with tempfile.TemporaryDirectory() as mappe:
            sti = os.path.join(mappe, "index.html")
            with open(sti, "w", encoding="utf-8") as f:
                f.write("<main></main>\n")
            self.assertFalse(fs.oppdater_forside_uka([], mappe, self.I_DAG, hentet=""))

    def test_forsiden_har_markorene(self):
        rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(rot, "index.html"), encoding="utf-8") as f:
            self.assertRegex(f.read(), r"(?s)<!--UKA:START-->.*<!--UKA:SLUTT-->")


class TestForsideArtikler(unittest.TestCase):
    """«Siste artikler» på forsiden fylles fra ARTIKLER i ui.js (20.10.2026).

    De fire håndskrevne kortene var fra april og mai mens seks nyere artikler
    var publisert.
    """

    ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    JS = """'use strict';
const ARTIKLER = [
  {
    slug: '/artikler/ny/',
    tittel: 'Ny artikkel om <utbytte>',
    ingress: 'Selskapets \\'ordinære\\' utbytte.',
    meta: '12. september 2026 · 12 min',
    tags: ['Guide', 'Skatt'],
    sektorer: [],
  },
  {
    slug: '/artikler/eldre/',
    tittel: 'Eldre artikkel',
    ingress: 'Ingress.',
    meta: '8. mai 2026 · 11 min',
    tags: ['Strategi'],
    sektorer: ['Finans'],
  },
  {
    slug: 'javascript:alert(1)',
    tittel: 'Ugyldig', ingress: 'x', meta: 'y', tags: [],
  },
];
"""

    def test_leser_i_rekkefolge_og_hopper_over_ugyldige(self):
        a = fs.les_artikler(self.JS)
        self.assertEqual([x["slug"] for x in a], ["/artikler/ny/", "/artikler/eldre/"])
        self.assertEqual(a[0]["ingress"], "Selskapets 'ordinære' utbytte.")
        self.assertEqual(a[0]["tags"], ["Guide", "Skatt"])

    def test_kortet_escaper_teksten(self):
        kort = fs.lag_artikkel_kort(fs.les_artikler(self.JS)[:1])
        self.assertIn("Ny artikkel om &lt;utbytte&gt;", kort)
        self.assertIn('href="/artikler/ny/"', kort)
        self.assertIn(">Guide</span>", kort)

    def test_ekte_ui_js_gir_alle_artiklene(self):
        with open(os.path.join(self.ROT, "assets", "ui.js"), encoding="utf-8") as f:
            js = f.read()
        blokk = re.search(r"const ARTIKLER\s*=\s*\[(.*?)\n\];", js, re.S).group(1)
        self.assertEqual(len(fs.les_artikler(js)), blokk.count("slug:"))

    def test_oppdaterer_bare_med_side_paa_disk(self):
        with tempfile.TemporaryDirectory() as mappe:
            os.makedirs(os.path.join(mappe, "assets"))
            os.makedirs(os.path.join(mappe, "artikler", "eldre"))
            open(os.path.join(mappe, "artikler", "eldre", "index.html"), "w").close()
            with open(os.path.join(mappe, "assets", "ui.js"), "w", encoding="utf-8") as f:
                f.write(self.JS)
            sti = os.path.join(mappe, "index.html")
            with open(sti, "w", encoding="utf-8") as f:
                f.write("<div>\n      <!--ARTIKLER:START-->\n      <!--ARTIKLER:SLUTT-->\n</div>\n")
            self.assertTrue(fs.oppdater_forside_artikler(mappe))
            self.assertFalse(fs.oppdater_forside_artikler(mappe))
            with open(sti, encoding="utf-8") as f:
                tekst = f.read()
            self.assertIn('href="/artikler/eldre/"', tekst)
            self.assertNotIn("/artikler/ny/", tekst)

    def test_forsiden_viser_de_nyeste(self):
        with open(os.path.join(self.ROT, "assets", "ui.js"), encoding="utf-8") as f:
            nyeste = fs.les_artikler(f.read())[:fs.FORSIDE_ARTIKLER]
        with open(os.path.join(self.ROT, "index.html"), encoding="utf-8") as f:
            blokk = re.search(r"(?s)<!--ARTIKLER:START-->(.*)<!--ARTIKLER:SLUTT-->", f.read()).group(1)
        self.assertEqual(re.findall(r'href="(/artikler/[^"]+)"', blokk), [a["slug"] for a in nyeste])


class TestSitemapLastmod(unittest.TestCase):
    """lastmod er datoen siden sist ble endret, ikke byggedatoen (vedlikehold 2026-10-23)."""

    def setUp(self):
        self.rot = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.rot, "faq"))
        os.makedirs(os.path.join(self.rot, "data"))
        self._skriv("faq/index.html", "<p>FAQ</p>")
        self._skriv("index.html", "<p>Forside</p>")

    def tearDown(self):
        shutil.rmtree(self.rot)

    def _skriv(self, sti, tekst):
        with open(os.path.join(self.rot, sti), "w", encoding="utf-8") as f:
            f.write(tekst)

    LOCS = ["https://exday.no/", "https://exday.no/faq/"]

    def test_uendret_side_beholder_datoen(self):
        forste = fs.sitemap_lastmod(self.LOCS, self.rot, "2026-10-01", {})
        andre = fs.sitemap_lastmod(self.LOCS, self.rot, "2026-10-26", forste)
        self.assertEqual(andre["https://exday.no/faq/"]["dato"], "2026-10-01")
        self.assertEqual(andre["https://exday.no/"]["dato"], "2026-10-01")

    def test_endret_side_far_dagens_dato(self):
        forste = fs.sitemap_lastmod(self.LOCS, self.rot, "2026-10-01", {})
        self._skriv("faq/index.html", "<p>FAQ, rettet</p>")
        andre = fs.sitemap_lastmod(self.LOCS, self.rot, "2026-10-26", forste)
        self.assertEqual(andre["https://exday.no/faq/"]["dato"], "2026-10-26")
        self.assertEqual(andre["https://exday.no/"]["dato"], "2026-10-01")

    def test_manglende_side_og_tom_lagring_gir_dagens_dato(self):
        ut = fs.sitemap_lastmod(["https://exday.no/finnes-ikke/"], self.rot, "2026-10-26", None)
        self.assertEqual(ut["https://exday.no/finnes-ikke/"]["dato"], "2026-10-26")

    def test_sett_lastmod_bytter_bare_kjente_urler(self):
        tekst = ("  <url>\n    <loc>https://exday.no/faq/</loc>\n    <lastmod>2026-10-26</lastmod>\n  </url>\n"
                 "  <url>\n    <loc>https://exday.no/om/</loc>\n    <lastmod>2026-10-26</lastmod>\n  </url>")
        ut = fs._sett_lastmod(tekst, {"https://exday.no/faq/": {"dato": "2026-09-14"}})
        self.assertIn("<loc>https://exday.no/faq/</loc>\n    <lastmod>2026-09-14</lastmod>", ut)
        self.assertIn("<loc>https://exday.no/om/</loc>\n    <lastmod>2026-10-26</lastmod>", ut)

    def test_sitemap_skrives_med_lagrede_datoer(self):
        lagret = fs.sitemap_lastmod(["https://exday.no/faq/"], self.rot, "2026-09-14", {})
        with open(os.path.join(self.rot, fs.SITEMAP_LASTMOD_FIL), "w", encoding="utf-8") as f:
            json.dump(lagret, f)
        fs.generer_sitemap([], self.rot, "2026-10-26")
        with open(os.path.join(self.rot, "sitemap.xml"), encoding="utf-8") as f:
            xml = f.read()
        self.assertIn("<loc>https://exday.no/faq/</loc>\n    <lastmod>2026-09-14</lastmod>", xml)
        self.assertIn("<loc>https://exday.no/om/</loc>\n    <lastmod>2026-10-26</lastmod>", xml)


class TestTallkontroll0211(unittest.TestCase):
    """Funnene fra tallkontrollen 2026-11-02 (S1–S4) og vedlikeholdsrapporten 08.11."""

    def wwi(self, **kw):
        i = datetime.date.today().year
        a = {
            "ticker": "WWI", "navn": "Wilh. Wilhelmsen Holding", "sektor": "Industri",
            "frekvens": "Halvårlig", "bors": "Oslo Børs", "pris": 860.0,
            "utbytte_per_aksje": 28.0, "utbytte_yield": 3.24, "utbytte_12m": 28.0,
            "snitt_yield_5ar": 1.18, "snitt_yield_ar": 5, "payout_ratio": 22,
            "utbytte_vekst_5ar": 60.7, "ar_med_utbytte": 30,
            "historiske_utbytter": [{"ar": i - 5 + k, "utbytte": v} for k, v in
                                    enumerate([4.0, 6.0, 8.0, 12.0, 20.0, 28.0])],
            "utbytte_per_ar": {str(i - 5 + k): v for k, v in enumerate([4.0, 6.0, 8.0, 12.0, 20.0])},
            "kurs_historikk": [],
        }
        a.update(kw)
        return a

    def yar(self, **kw):
        i = datetime.date.today().year
        a = {
            "ticker": "YAR", "navn": "Yara International ASA", "sektor": "Materialer",
            "frekvens": "Årlig", "bors": "Oslo Børs", "pris": 400.0,
            "utbytte_per_aksje": 22.0, "utbytte_yield": 5.5, "utbytte_12m": 22.0,
            "payout_ratio": 60, "utbytte_vekst_5ar": -50.0, "ar_med_utbytte": 30,
            "historiske_utbytter": [{"ar": i - 4, "utbytte": 40.0}, {"ar": i - 3, "utbytte": 15.0},
                                    {"ar": i - 2, "utbytte": 10.0}, {"ar": i - 1, "utbytte": 5.0},
                                    {"ar": i, "utbytte": 22.0}],
            "utbytte_per_ar": {str(i - 4): 40.0, str(i - 3): 15.0, str(i - 2): 10.0, str(i - 1): 5.0},
            "kurs_historikk": [],
        }
        a.update(kw)
        return a

    def test_s1_hoy_vekst_kalles_ikke_attraktiv(self):
        side = fs._aksje_side_html(self.wwi(), datetime.date.today().isoformat())
        self.assertNotIn("attraktivt for langsiktige reinvesteringsstrategier", side)
        self.assertIn("regnet fra et lavt utgangspunkt", side)
        moderat = fs._aksje_side_html(self.wwi(utbytte_vekst_5ar=12.0), datetime.date.today().isoformat())
        self.assertIn("attraktivt for langsiktige reinvesteringsstrategier", moderat)

    def test_s2_hevet_og_betalt_er_ikke_usikkert(self):
        a = self.wwi()
        self.assertTrue(fs.utbytte_hevet_og_betalt(a))
        self.assertNotIn("ikke sikkert", " ".join(fs._selskapsrisikoer(a)))
        # Høy payout, eller en rate som ikke er betalt, beholder advarselen.
        for b in (self.wwi(payout_ratio=94), self.wwi(utbytte_12m=10.0)):
            self.assertFalse(fs.utbytte_hevet_og_betalt(b))
            self.assertIn("ikke sikkert", " ".join(fs._selskapsrisikoer(b)))

    def test_s3_holdingselskaper_har_egen_bransje(self):
        for t in ("WWI", "WWIB", "AKER"):
            self.assertEqual(fs.BRANSJE.get(t), "holding")
        self.assertIn("holding", fs._BRANSJE_DRIVER_UTDYPET)
        self.assertIn("holding", fs.BRANSJE_RISIKOER)
        side = fs._aksje_side_html(self.wwi(), datetime.date.today().isoformat())
        self.assertIn("utbyttene det selv mottar", side)
        self.assertNotIn("book-to-bill", side)

    def test_s4_aarets_hoyere_utbytte_nevnes(self):
        a = self.yar()
        i = datetime.date.today().year
        self.assertEqual(fs.aarets_oppgang(a), (i, 22.0, i - 1, 5.0))
        tekst = fs._lag_utbyttehistorikk_tekst(a)
        self.assertNotIn("lavere nå", tekst)
        self.assertIn(f"For {i} er det betalt 22,00 kroner per aksje, mot 5,00 kroner for {i - 1}.", tekst)
        side = fs._aksje_side_html(a, datetime.date.today().isoformat())
        self.assertNotIn("setter seg inn i hva som har drevet nedgangen", side)
        self.assertIn(f"men for {i} er det betalt 22,00 NOK, mot 5,00 NOK for {i - 1}", side)

    def test_snitt_yield_paa_aksjer_teller_ikke_aksjer_paa_vei_ut(self):
        self.assertIn("sektor_snitt_yield(aksjer)", inspect.getsource(fs.generer_aksjesider))

    def test_ingen_med_andre_ord(self):
        self.assertNotIn("Med andre ord", inspect.getsource(fs))


class TestTallkontroll2610(unittest.TestCase):
    """Funnene fra tallkontrollen 2026-10-26."""

    D = datetime.date(2026, 10, 26)

    def tinde(self, **kw):
        a = {
            "ticker": "TINDE", "navn": "Tinde Sparebank", "frekvens": "Årlig",
            "sektor": "Finans", "payout_ratio": 75, "utbytte_yield": 4.0,
            "historiske_utbytter": [
                {"ar": 2022, "utbytte": 7.74}, {"ar": 2023, "utbytte": 8.37},
                {"ar": 2024, "utbytte": 7.63}, {"ar": 2025, "utbytte": 9.00},
                {"ar": 2026, "utbytte": 4.90, "maaneder": [3]},
            ],
            "utbytte_per_ar": {"2021": 7.0, "2022": 7.74, "2023": 8.37, "2024": 7.63, "2025": 9.0},
            "utbytte_vekst_5ar": 29.0,
        }
        a.update(kw)
        return a

    def test_aarets_utbytte_for_aarlig_betaler(self):
        self.assertEqual(fs.aarets_arsutbytte(self.tinde(), self.D), (2026, 4.9))
        self.assertIsNone(fs.aarets_arsutbytte(self.tinde(frekvens="Kvartalsvis"), self.D))
        # En meldt ex-dato senere i år: mer kan komme.
        self.assertIsNone(fs.aarets_arsutbytte(self.tinde(ex_dato="2026-11-20"), self.D))
        self.assertEqual(fs.aarets_nedgang(self.tinde(), self.D), (2026, 4.9, 2025, 9.0))

    def test_tinde_mister_vekstmerket(self):
        topp = fs.vekst_fra_topp(self.tinde(), self.D)
        self.assertEqual(topp, (2025, 9.0, 2026, 4.9))

    def test_nedtur_sier_ikke_ikke_kuttet(self):
        # Relativt til i år: _lag_nedtur_test() bruker dagens dato.
        i = datetime.date.today().year
        a = self.tinde(
            historiske_utbytter=[{"ar": i - 4, "utbytte": 7.74}, {"ar": i - 3, "utbytte": 8.37},
                                 {"ar": i - 2, "utbytte": 8.37}, {"ar": i - 1, "utbytte": 9.00},
                                 {"ar": i, "utbytte": 4.90}],
            utbytte_per_ar={str(i - 1): 9.0})
        side = fs._lag_nedtur_test(a)
        self.assertNotIn("ikke kuttet", side)
        self.assertIn(f"For {i} er det betalt 4,90 kroner per aksje, mot 9,00 kroner for {i - 1}", side)

    def test_liten_nedgang_er_ikke_ikke_kuttet(self):
        # 2023 → 2024 er −8,9 %: historikkteksten sier «satt ned én gang».
        a = self.tinde(historiske_utbytter=self.tinde()["historiske_utbytter"][:-1])
        self.assertIn("satt ned én gang", fs._lag_utbyttehistorikk_tekst(a))
        side = fs._lag_nedtur_test(a)
        self.assertNotIn("ikke kuttet", side)
        self.assertIn("aldri med mer enn 15\u00a0%", side)

    def test_aar_uten_utbytte_er_ikke_ikke_kuttet(self):
        a = self.tinde(historiske_utbytter=[{"ar": 2021, "utbytte": 5.0}, {"ar": 2023, "utbytte": 5.0},
                                            {"ar": 2024, "utbytte": 5.0}, {"ar": 2025, "utbytte": 5.0}])
        side = fs._lag_nedtur_test(a)
        self.assertNotIn("ikke kuttet", side)
        self.assertIn("For 2022 har vi ikke registrert noe utbytte", side)

    def test_historikkteksten_nevner_aarets_utbytte(self):
        tekst = fs._lag_utbyttehistorikk_tekst(self.tinde(), 2026)
        self.assertIn("For 2026 er det betalt 4,90 kroner per aksje, mot 9,00 kroner for 2025.", tekst)

    def vend(self):
        return {
            "ticker": "VEND", "frekvens": "Årlig", "pris": 240.0, "utbytte_12m": 2.5,
            "utbytte_forste_ar": 2015, "utbytte_vekst_5ar": 22.3,
            "saerutbytte": [{"ex_dato": "2024-05-30", "belop": 77.10, "melding": "620125"},
                            {"ex_dato": "2024-09-03", "belop": 8.56, "melding": "626907"},
                            {"ex_dato": "2025-06-16", "belop": 2.22, "melding": "648900"}],
            "utbytte_per_ar": {"2021": 2.0, "2022": 2.0, "2023": 2.0, "2024": 87.66, "2025": 4.47},
            "historiske_utbytter": [{"ar": y, "utbytte": v} for y, v in
                                    ((2021, 2.0), (2022, 2.0), (2023, 2.0), (2024, 87.66), (2025, 4.47))],
        }

    def test_saerutbytte_er_ikke_kutt(self):
        a = self.vend()
        self.assertEqual(fs.ordinaer_per_ar(a)["2024"], 2.0)
        self.assertEqual(fs.ordinaer_per_ar(a)["2025"], 2.25)
        self.assertEqual(fs.utbyttekutt(a, 2026), [])
        self.assertNotIn("lite forutsigbar", fs._lag_utbyttehistorikk_tekst(a, 2026))
        self.assertIn("Tallene er uten særutbytte, som var 85,66 kroner i 2024 og 2,22 kroner i 2025.",
                      fs._lag_utbyttehistorikk_tekst(a, 2026))

    def test_snitt_og_vekst_uten_saerutbytte(self):
        a = self.vend()
        fs.sett_snitt_felter(a)
        self.assertAlmostEqual(a["snitt_yield_5ar"], round(2.05 / 240 * 100, 2))
        fs.sett_saerutbytte(a, a["saerutbytte"], self.D)
        self.assertEqual(a["utbytte_vekst_5ar"], 3.0)
        self.assertIn("85,66 kr i 2024", fs.saerutbytte_fotnote(a, 2026))

    def test_saerutbyttene_i_tickers_er_kontrollert(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "data", "tickers.json"),
                  encoding="utf-8") as f:
            alle = [t for t in json.load(f) if t.get("saerutbytte")]
        self.assertTrue(alle)
        for t in alle:
            for s_ in t["saerutbytte"]:
                with self.subTest(ticker=t["ticker"], ex=s_.get("ex_dato")):
                    datetime.date.fromisoformat(s_["ex_dato"])
                    self.assertGreater(s_["belop"], 0)
                    self.assertRegex(s_["melding"], r"^\d+$")

    def test_aarets_maaneder_naar_aaret_er_komplett(self):
        var = {"frekvens": "Kvartalsvis", "ex_dato": "2026-11-17",
               "historiske_utbytter": [{"ar": 2024, "maaneder": [2, 4, 7, 10]},
                                       {"ar": 2025, "maaneder": [2, 4, 8, 11]},
                                       {"ar": 2026, "maaneder": [2, 6, 8]}]}
        self.assertEqual(fs.aarets_maaneder(var, self.D), [2, 6, 8, 11])
        fs.sett_utbetalingsmaaneder(var, self.D)
        self.assertEqual(var["utbetalingsmaaneder"], [2, 6, 8, 11])
        # Uten den meldte novemberdatoen er året ikke komplett.
        var.pop("ex_dato")
        self.assertIsNone(fs.aarets_maaneder(var, self.D))
        fs.sett_utbetalingsmaaneder(var, self.D)
        self.assertEqual(var["utbetalingsmaaneder"], [2, 4, 8])
        vistin = {"frekvens": "Årlig", "historiske_utbytter": [
            {"ar": 2024, "maaneder": [6]}, {"ar": 2025, "maaneder": [6]}, {"ar": 2026, "maaneder": [5]}]}
        self.assertEqual(fs.aarets_maaneder(vistin, self.D), [5])

    def test_maanedsteksten_sier_hvor_maanedene_kommer_fra(self):
        var = {"navn": "Vår Energi ASA", "frekvens": "Kvartalsvis", "ex_dato": "2026-11-17",
               "utbetalingsmaaneder": [2, 6, 8, 11],
               "historiske_utbytter": [{"ar": 2025, "maaneder": [2, 4, 8, 11]},
                                       {"ar": 2026, "maaneder": [2, 6, 8]}]}
        self.assertEqual(fs.maaneder_kilde(var, [2, 6, 8, 11], self.D), ("aar", 2026, 11))
        west = {"frekvens": "Uregelmessig",
                "historiske_utbytter": [{"ar": 2022, "maaneder": [3, 6, 9, 12]},
                                        {"ar": 2023, "maaneder": [2]},
                                        {"ar": 2026, "maaneder": [2, 10]}]}
        self.assertEqual(fs.maaneder_kilde(west, [2, 10], self.D), ("aar", 2026, None))
        stabil = {"frekvens": "Halvårlig",
                  "historiske_utbytter": [{"ar": y, "maaneder": [5, 11]} for y in (2023, 2024, 2025)]}
        self.assertEqual(fs.maaneder_kilde(stabil, [5, 11], self.D)[0], "monster")

    def test_faq_nevner_alle_nullaar(self):
        a = {"ticker": "WEST", "navn": "Western Bulk", "frekvens": "Uregelmessig",
             "utbytte_forste_ar": 2021,
             "utbytte_per_ar": {"2021": 1.0, "2022": 28.32, "2023": 3.0, "2024": 0.0, "2025": 0.0},
             "historiske_utbytter": []}
        _, ld = fs._lag_faq_seksjon(a, "2026-10-26")
        self.assertIn("I 2024 og 2025 har vi ikke registrert noe utbytte", ld)

    def test_kuttpunktet_nevner_aar_uten_utbytte_etterpaa(self):
        a = {"utbytte_per_ar": {"2022": 28.32, "2023": 3.0, "2024": 0.0, "2025": 0.0}}
        self.assertEqual(fs._pauser_etter_tekst(a, 2023),
                         ", og for 2024 og 2025 har vi ikke registrert noe utbytte")
        self.assertEqual(fs._pauser_etter_tekst(a, 2025), "")



class TestFrekvensartikkel(unittest.TestCase):
    """Tallene i «Slik leser du utbyttekalenderen» fylles fra dataene (30.10.2026).

    Tabellen summerte til 160 aksjer i en katalog på 155, teksten under sa 32
    kvartalsvise mot tabellens 31, HSHP sto med 3,5 % mot 10,9 %, og «år på
    rad» var regnet fra antall år med utbytte. Setninger som trekker en
    slutning fra tallene, skal bare skrives når tallene bærer den.
    """

    I_DAG = datetime.date(2026, 10, 30)

    @staticmethod
    def _aksje(ticker, frekvens, sektor, yld, aar, navn=None):
        return {"ticker": ticker, "navn": navn or f"{ticker} ASA", "frekvens": frekvens,
                "sektor": sektor, "utbytte_yield": yld, "utbytteaar": aar,
                "ar_med_utbytte": len(aar)}

    def _katalog(self):
        a = self._aksje
        aar = lambda n: list(range(2026 - n + 1, 2027))
        return [
            a("HSHP", "Månedlig", "Shipping", 11.0, aar(3), "Himalaya Shipping Ltd."),
            a("K1", "Kvartalsvis", "Shipping", 8.0, aar(3)),
            a("K2", "Kvartalsvis", "Shipping", 9.0, aar(4)),
            a("K3", "Kvartalsvis", "Energi", 7.0, aar(5)),
            a("K4", "Kvartalsvis", "Industri", 4.0, aar(2)),
            a("H1", "Halvårlig", "Industri", 4.0, aar(15)),
            a("H2", "Halvårlig", "Shipping", 5.0, aar(13)),
            a("A1", "Årlig", "Finans", 6.0, aar(9), "Alfa Sparebank"),
            a("A2", "Årlig", "Finans", 5.0, aar(8), "SpareBank 1 Beta"),
            a("A3", "Årlig", "Finans", 4.0, aar(10), "Gamma Forsikring ASA"),
            a("A4", "Årlig", "Industri", 3.0, aar(7)),
            a("U1", "Uregelmessig", "Industri", 0, [2019, 2022]),
            a("U2", "Uregelmessig", "Energi", 0, []),
            a("U3", "Uregelmessig", "Industri", 6.0, [2024, 2026]),
        ]

    def _blokker(self, katalog=None, dato="30. oktober 2026"):
        g = fs.frekvensfordeling(katalog or self._katalog(), self.I_DAG)
        return fs.lag_frekvens_blokker(g, dato)

    def test_fordeling(self):
        g = fs.frekvensfordeling(self._katalog(), self.I_DAG)
        self.assertEqual(list(g), list(fs.FREKVENS_REKKEFOLGE))
        self.assertEqual(sum(x["antall"] for x in g.values()), 14)
        self.assertEqual(g["Kvartalsvis"]["sykliske"], 3)
        self.assertEqual(g["Kvartalsvis"]["rekke"], 3.5)       # rekken, ikke antall år
        self.assertEqual(g["Uregelmessig"]["rekke"], 0)        # U1 og U2 har ingen rekke nå
        self.assertEqual(g["Uregelmessig"]["yield"], 0)        # median over alle
        self.assertEqual(g["Uregelmessig"]["betaler"], 1)
        self.assertEqual(g["Årlig"]["sparebanker"], 2)

    def test_tabell_summerer_til_katalogen(self):
        tabell = self._blokker()["tabell"]
        antall = [int(x) for x in re.findall(r"</strong></td><td>(\d+)</td>", tabell)]
        self.assertEqual(sum(antall), 14)
        self.assertIn("<td>3,5</td>", tabell)
        self.assertIn("Tallene er fra 30. oktober 2026.", tabell)
        self.assertNotIn("Tallene er fra", self._blokker(dato="")["tabell"])

    def test_analyse_folger_tallene(self):
        b = self._blokker()
        self.assertIn("75\u00a0% av de kvartalsvise", b["analyse"])
        self.assertIn("mot 0\u00a0% av de årlige", b["analyse"])
        self.assertIn("Av de 4 kvartalsvise er 2 shipping, 1 energi og 1 industri.", b["analyse"])
        self.assertIn("3 av de 4 årlige betalerne finansselskaper, de fleste av dem sparebanker.",
                      b["analyse"])
        # Én av tre sparebanker: ingen påstand om «de fleste».
        kat = self._katalog()
        kat[8]["navn"] = "Beta Finans ASA"
        self.assertNotIn("sparebanker", self._blokker(kat)["analyse"])

    def test_slutningen_om_kort_historikk_krever_at_den_holder(self):
        b = self._blokker()
        self.assertIn("kortest historikk", b["rekke"])
        kat = self._katalog()
        for a in kat:
            if a["frekvens"] == "Kvartalsvis":
                a["utbytteaar"] = list(range(2000, 2027))
        b = self._blokker(kat)
        self.assertNotIn("kortest historikk", b["rekke"])
        self.assertNotIn("samme historien", b["rekke"])

    def test_uregelmessig(self):
        b = self._blokker()["uregelmessig"]
        self.assertIn("De 3 aksjene", b)
        self.assertIn("Bare én av dem", b)
        self.assertIn("ikke betalt i det hele tatt", b)        # U2 har aldri betalt
        kat = [a for a in self._katalog() if a["ticker"] != "U3"]
        self.assertIn("Ingen av dem", self._blokker(kat)["uregelmessig"])

    def test_manedlig_navngir_det_som_finnes(self):
        b = self._blokker()["manedlig"]
        self.assertIn("bare én som betaler månedlig", b)
        self.assertIn('<a href="/aksjer/HSHP/"', b)
        self.assertIn("Himalaya Shipping (HSHP)", b)
        self.assertIn("11,00 %", b)
        kat = [a for a in self._katalog() if a["frekvens"] != "Månedlig"]
        self.assertIn("ingen som betaler månedlig", self._blokker(kat)["manedlig"])
        kat = self._katalog() + [self._aksje("M2", "Månedlig", "Eiendom", 6.0, [2025, 2026])]
        self.assertIn("bare to som betaler månedlig", self._blokker(kat)["manedlig"])

    def test_halvarlig(self):
        b = self._blokker()["halvarlig"]
        self.assertIn("interessant mellomsjikt", b)             # 50 % mot 75 %
        self.assertIn("den lengste historikken", b)             # median 14
        kat = self._katalog()
        kat[5]["sektor"] = "Shipping"                            # 100 % sykliske
        self.assertNotIn("mellomsjikt", self._blokker(kat)["halvarlig"])

    def test_oppdaterer_markorene_og_er_idempotent(self):
        rot = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, rot, ignore_errors=True)
        sti = os.path.join(rot, fs.FREKVENS_ARTIKKEL)
        os.makedirs(os.path.dirname(sti))
        with open(sti, "w", encoding="utf-8") as f:
            f.write("<p><!--FREKV:analyse-->gammelt 32<!--/FREKV--></p>\n"
                    "<p><!--FREKV:ukjent-->står<!--/FREKV--></p>\n")
        self.assertTrue(fs.oppdater_frekvensartikkel(self._katalog(), rot, self.I_DAG))
        self.assertFalse(fs.oppdater_frekvensartikkel(self._katalog(), rot, self.I_DAG))
        with open(sti, encoding="utf-8") as f:
            h = f.read()
        self.assertNotIn("gammelt", h)
        self.assertIn("<!--FREKV:ukjent-->står<!--/FREKV-->", h)

    def test_artikkelen_har_bare_blokker_generatoren_fyller(self):
        sti = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           fs.FREKVENS_ARTIKKEL)
        with open(sti, encoding="utf-8") as f:
            navn = re.findall(r"<!--FREKV:(\w+)-->", f.read())
        self.assertEqual(sorted(navn), sorted(self._blokker()))


class TestMarkedsplassOgRapportmeta(unittest.TestCase):
    """14 av 155 aksjer står på Euronext Growth (30.10.2026)."""

    def test_markedsplass_tekst(self):
        self.assertEqual(fs.markedsplass_tekst([{"bors": "Oslo Børs"}]), "Oslo Børs")
        self.assertEqual(fs.markedsplass_tekst([{"bors": "Oslo Børs"},
                                                {"bors": "Euronext Growth Oslo"}]),
                         "Oslo Børs og Euronext Growth")
        self.assertEqual(fs.markedsplass_tekst([]), "Oslo Børs")

    def test_rapportkalender_meta_har_ikke_dagens_antall(self):
        # «over 130» fulgte antallet rapportdatoer, som faller mot null før
        # hver rapportsesong og gjorde beskrivelsen feil mot slutten av året.
        rot = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, rot, ignore_errors=True)
        aksjer = [{"ticker": f"T{i}", "navn": f"T{i} ASA", "sektor": "Finans",
                   "bors": "Euronext Growth Oslo" if i == 0 else "Oslo Børs",
                   "utbytte_yield": 5.0, "rapport_dato": "2026-11-05"} for i in range(25)]
        fs.generer_rapportkalender(aksjer, rot, i_dag=datetime.date(2026, 10, 30))
        with open(os.path.join(rot, "rapportkalender", "index.html"), encoding="utf-8") as f:
            h = f.read()
        desc = re.search(r'<meta name="description" content="([^"]*)"', h).group(1)
        self.assertNotRegex(desc, r"\d")
        self.assertIn("selskaper på Oslo Børs og Euronext Growth.", h)



class TestTallUtdatert(unittest.TestCase):
    """Gamle tall for én aksje (31.10.2026).

    Datajobben gjenbruker forrige kjørings rad når Yahoo ikke svarer, og sida
    så da like fersk ut som de andre. `hentet` følger raden, og regelen er den
    samme som tallUtdatert() i assets/app.js.
    """

    DATA = "2026-11-02T10:41:00Z"   # mandag 2.11 kl. 11:41 i Oslo

    def test_to_borsdager_bak_gir_datoen(self):
        a = {"hentet": "2026-10-29T15:41:00Z"}   # torsdag 16:41
        self.assertEqual(fs.tall_utdatert(a, self.DATA), datetime.date(2026, 10, 29))

    def test_helg_og_morgenkjoring_er_ikke_gamle_tall(self):
        fredag = {"hentet": "2026-10-30T16:41:00Z"}
        self.assertIsNone(fs.tall_utdatert(fredag, "2026-11-02T07:41:00Z"))
        self.assertIsNone(fs.tall_utdatert(fredag, self.DATA))
        self.assertIsNone(fs.tall_utdatert({"hentet": self.DATA}, self.DATA))

    def test_uten_hentet_sier_den_ingenting(self):
        self.assertIsNone(fs.tall_utdatert({}, self.DATA))
        self.assertIsNone(fs.tall_utdatert({"hentet": "tull"}, self.DATA))
        self.assertIsNone(fs.tall_utdatert({"hentet": "2026-10-01T10:00:00Z"}, ""))
        self.assertIsNone(fs.tall_utdatert(None, self.DATA))

    def test_boks_og_datolinje_paa_aksjesiden(self):
        gammel = {"ticker": "TST", "navn": "Test & Co ASA", "hentet": "2026-10-29T15:41:00Z"}
        fersk = {"ticker": "NY", "navn": "Ny ASA", "hentet": self.DATA}
        lagret = fs.DATA_SIST_OPPDATERT
        fs.DATA_SIST_OPPDATERT = self.DATA
        try:
            boks = fs.lag_utdatert_boks(gammel)
            self.assertIn("Tallene for denne aksjen er ikke oppdatert", boks)
            self.assertIn("Test &amp; Co ASA siden 29. oktober 2026", boks)
            self.assertEqual(fs.lag_utdatert_boks(fersk), "")
            self.assertIn("Tallene for denne aksjen er hentet 29. oktober 2026",
                          fs.sist_oppdatert_html(gammel))
            self.assertIn("Tallene er hentet 2. november 2026", fs.sist_oppdatert_html(fersk))
            self.assertIn("Tallene er hentet 2. november 2026", fs.sist_oppdatert_html())
        finally:
            fs.DATA_SIST_OPPDATERT = lagret

    def test_hentet_fra_status(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            sti = os.path.join(d, "ticker_status.json")
            with open(sti, "w", encoding="utf-8") as f:
                json.dump({"tickere": {"TST": {"sist_ok": "2026-10-29"}, "FEIL": {"sist_ok": "x"}}}, f)
            self.assertEqual(fs.hentet_fra_status("TST", sti), "2026-10-29T12:00:00Z")
            self.assertIsNone(fs.hentet_fra_status("FEIL", sti))
            self.assertIsNone(fs.hentet_fra_status("MANGLER", sti))
            self.assertIsNone(fs.hentet_fra_status("TST", os.path.join(d, "finnes_ikke.json")))
        # Kursdagen for kl. 12 UTC er samme dag, så datoen blir riktig i regelen.
        self.assertEqual(fs.tall_utdatert({"hentet": "2026-10-29T12:00:00Z"}, self.DATA),
                         datetime.date(2026, 10, 29))


class TestSektorSnitt(unittest.TestCase):
    """Én definisjon av sektorsnittet (01.11.2026).

    Energi sto med 6,8 % på sin egen side og 9,8 % i sektoroversikten, og
    oversikten viste BlueNord og Stainless Tankers som «Topp» etter at de var
    tatt ut av rangeringene.
    """

    BNOR = {"ticker": "BNOR", "utbytte_yield": 28.53,
            "hendelse": {"type": "fusjon", "dato": "2026-10-20", "tekst": "Fusjon."}}
    VAR = {"ticker": "VAR", "utbytte_yield": 9.26}
    AKRBP = {"ticker": "AKRBP", "utbytte_yield": 6.27}
    NULL = {"ticker": "NULL", "utbytte_yield": 0}

    def test_snitt_bare_betalende_og_uten_aksjer_paa_vei_ut(self):
        self.assertAlmostEqual(fs.sektor_snitt_yield([self.BNOR, self.VAR, self.AKRBP, self.NULL]),
                               (9.26 + 6.27) / 2)
        self.assertEqual(fs.sektor_snitt_yield([self.BNOR, self.NULL]), 0.0)
        self.assertEqual(fs.sektor_snitt_yield([]), 0.0)

    def test_topp_hopper_over_aksjer_paa_vei_ut(self):
        self.assertEqual([a["ticker"] for a in fs.sektor_topp([self.BNOR, self.AKRBP, self.VAR, self.NULL])],
                         ["VAR", "AKRBP"])

    def test_sektorsider_og_oversikt_viser_samme_snitt(self):
        import tempfile
        aksjer = [dict(a, sektor="Energi", navn=a["ticker"], pris=100.0)
                  for a in (self.BNOR, self.VAR, self.AKRBP, self.NULL)]
        aksjer.append({"ticker": "TEL", "navn": "Telenor ASA", "sektor": "Telekommunikasjon",
                       "utbytte_yield": 7.37, "pris": 131.7})
        with tempfile.TemporaryDirectory() as d:
            fs.generer_sektorsider(aksjer, d)
            with open(os.path.join(d, "aksjer", "sektor", "energi", "index.html"), encoding="utf-8") as f:
                side = f.read()
            with open(os.path.join(d, "aksjer", "sektor", "index.html"), encoding="utf-8") as f:
                oversikt = f.read()
        snitt = fs._pst((9.26 + 6.27) / 2, 1)
        self.assertIn(f'<dt>Snitt yield</dt><dd>{snitt}</dd>', side)
        self.assertIn(f"4 aksjer · snitt {snitt}", oversikt)
        self.assertIn("Topp: VAR, AKRBP", oversikt)
        self.assertNotIn("Topp: BNOR", oversikt)
        self.assertIn("1 aksje · snitt", oversikt)
        self.assertNotIn("1 aksjer", oversikt)
        self.assertNotIn("app-en", oversikt)

    def test_aksjesidene_bruker_samme_snitt(self):
        # EQNR sto med «under snittet for Energi-sektoren (10,4 %)» mens
        # sektorsiden viste 6,6 %: aksjesidene tok med BlueNord (08.11.2026).
        kart = {"Energi": [self.BNOR, self.VAR, self.AKRBP, self.NULL],
                "Tom": [self.BNOR, self.NULL]}
        snitt = fs.sektorsnitt_per_sektor(kart)
        self.assertAlmostEqual(snitt["Energi"], fs.sektor_snitt_yield(kart["Energi"]))
        self.assertAlmostEqual(snitt["Energi"], (9.26 + 6.27) / 2)
        self.assertNotIn("Tom", snitt)
        kilde = inspect.getsource(fs.generer_aksjesider)
        self.assertIn("sektorsnitt_per_sektor(", kilde)


class TestRangering(unittest.TestCase):
    """Topplistene tar ikke med aksjer under oppkjøp, fusjon eller avvikling (30.10.2026).

    BlueNord toppet «Høyest utbytte» med 28,53 % etter å ha sagt at det ikke
    vedtar flere utbytter før fusjonen, og Stainless Tankers sto der under
    avvikling.
    """

    @staticmethod
    def _h(type_):
        return {"type": type_, "dato": "2026-08-24", "melding": "1", "tekst": "Meldt."}

    def _aksjer(self):
        return [
            {"ticker": "BNOR", "navn": "BlueNord ASA", "sektor": "Energi", "utbytte_yield": 28.53,
             "pris": 633.0, "frekvens": "Kvartalsvis", "ar_med_utbytte": 3, "utbytte_vekst_5ar": 40,
             "payout_ratio": 60, "hendelse": self._h("fusjon")},
            {"ticker": "STST", "navn": "Stainless Tankers ASA", "sektor": "Shipping", "utbytte_yield": 12.25,
             "pris": 41.0, "frekvens": "Kvartalsvis", "ar_med_utbytte": 3, "utbytte_vekst_5ar": 5,
             "payout_ratio": 30, "hendelse": self._h("avvikling")},
            {"ticker": "TRSB", "navn": "Trøndelag Sparebank", "sektor": "Finans", "utbytte_yield": 9.0,
             "pris": 150.0, "frekvens": "Årlig", "ar_med_utbytte": 10, "utbytte_vekst_5ar": 8,
             "payout_ratio": 50, "hendelse": self._h("fusjon_overtar")},
            {"ticker": "PARB", "navn": "Pareto Bank ASA", "sektor": "Finans", "utbytte_yield": 17.06,
             "pris": 46.9, "frekvens": "Årlig", "ar_med_utbytte": 10, "utbytte_vekst_5ar": 12,
             "payout_ratio": 89},
        ]

    def test_i_rangering(self):
        a = {t["ticker"]: t for t in self._aksjer()}
        self.assertFalse(fs.i_rangering(a["BNOR"]))
        self.assertFalse(fs.i_rangering(a["STST"]))
        self.assertTrue(fs.i_rangering(a["TRSB"]))     # den som overtar, fortsetter
        self.assertTrue(fs.i_rangering(a["PARB"]))

    def test_topplistene(self):
        rot = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, rot, ignore_errors=True)
        fs.generer_topplistesider(self._aksjer(), rot)
        for slug in ("hoyest-utbytte", "utbyttevekst", "konsistente-utbytteaksjer", "lavest-payout"):
            sti = os.path.join(rot, "aksjer", slug, "index.html")
            if not os.path.exists(sti):
                continue
            with open(sti, encoding="utf-8") as f:
                h = f.read()
            self.assertNotIn("/aksjer/BNOR/", h, slug)
            self.assertNotIn("/aksjer/STST/", h, slug)
        with open(os.path.join(rot, "aksjer", "hoyest-utbytte", "index.html"), encoding="utf-8") as f:
            h = f.read()
        self.assertLess(h.index("/aksjer/PARB/"), h.index("/aksjer/TRSB/"))


class TestProsentformat(unittest.TestCase):
    """Prosent med hardt mellomrom i malene (30.–31.10.2026).

    «3,48 %» med vanlig mellomrom kan brytes slik at «%» står alene på neste
    linje. Første runde så bare etter «{_nf(x)} %», og 24 steder slapp unna:
    funksjoner som får formatereren inn som parameteren `nf`, og fast tekst
    som «beskattes med 37,84 %». Testen leser derfor alle strenger i koden,
    ikke én skrivemåte. Docstrings og print() er utelatt.
    """

    @staticmethod
    def _funn(sti):
        import ast
        with open(sti, encoding="utf-8") as f:
            tre = ast.parse(f.read())
        hopp = set()
        for n in ast.walk(tre):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.body:
                d = n.body[0]
                if isinstance(d, ast.Expr) and isinstance(d.value, ast.Constant):
                    hopp.add(id(d.value))
            if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "print":
                for barn in ast.walk(n):
                    hopp.add(id(barn))
        funn = []
        for n in ast.walk(tre):
            if id(n) in hopp:
                continue
            if isinstance(n, ast.JoinedStr):
                for a, b in zip(n.values, n.values[1:]):
                    if (isinstance(a, ast.FormattedValue) and isinstance(b, ast.Constant)
                            and isinstance(b.value, str) and b.value.startswith(" %")):
                        funn.append(n.lineno)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.search(r"\d %", n.value):
                funn.append(n.lineno)
        return sorted(set(funn))

    def test_ingen_prosent_med_vanlig_mellomrom(self):
        mappe = os.path.dirname(os.path.abspath(__file__))
        for navn in ("fetch_stocks.py", "utvid_beskrivelser.py", "sektortekster.py"):
            self.assertEqual(self._funn(os.path.join(mappe, navn)), [], navn)

    def test_fanger_parameter_og_fast_tekst(self):
        import tempfile
        kode = (
            'def f(nf, y):\n'
            '    """Docstring med 5 % er lov."""\n'
            '    print(f"{y} % i loggen er lov")\n'
            '    a = f"{nf(y, 2)} %"\n'
            '    b = "beskattes med 37,84 % av"\n'
            '    return a + b\n'
        )
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(kode)
        try:
            self.assertEqual(self._funn(f.name), [4, 5])
        finally:
            os.unlink(f.name)


class TestUtbetalingsrunde(unittest.TestCase):
    """Vinduet på 365 dager teller feil rundt årsdagen for en utbetaling.

    9. november 2026 ga det tre feil samme dag: SOFF 0,75 % mot 8,3 %, STST
    30,33 % mot 12,3 %, og Bouvet som «Kvartalsvis». Seriene er de ekte.
    """

    I_DAG = datetime.date(2026, 11, 9)
    D = datetime.date
    SOFF = [(D(2025, 11, 25), 0.5119), (D(2026, 3, 10), 0.4832), (D(2026, 5, 20), 0.9169),
            (D(2026, 7, 17), 1.4592), (D(2026, 11, 6), 2.7683)]
    STST = [(D(2025, 5, 9), 3.3), (D(2025, 8, 8), 3.2), (D(2025, 11, 7), 1.3858),
            (D(2026, 2, 6), 1.2843), (D(2026, 5, 8), 1.2461), (D(2026, 8, 7), 1.2544)]
    BOUV = [(D(2024, 11, 14), 0.7), (D(2025, 5, 16), 3.0), (D(2025, 11, 13), 0.7),
            (D(2026, 5, 15), 3.0), (D(2026, 11, 6), 0.7)]
    HUNT = [(D(2025, 12, 1), 0.3), (D(2026, 3, 2), 0.4), (D(2026, 3, 26), 0.58),
            (D(2026, 6, 30), 1.25), (D(2026, 9, 29), 1.5)]

    def _strengt(self, serie, i_dag=None):
        grense = (i_dag or self.I_DAG) - datetime.timedelta(days=365)
        return [b for b in serie if b[0] > grense]

    def test_soff_for_tidlig_i_aar_gir_fire(self):
        self.assertEqual(len(self._strengt(self.SOFF)), 5)
        runde = fs.utbetalingsrunde(self.SOFF, self.I_DAG)
        self.assertEqual([d for d, _ in runde], [d for d, _ in self.SOFF[1:]])
        self.assertAlmostEqual(sum(v for _, v in runde), 5.6276, places=4)

    def test_stst_for_sent_i_aar_gir_fire(self):
        self.assertEqual(len(self._strengt(self.STST)), 3)
        runde = fs.utbetalingsrunde(self.STST, self.I_DAG)
        self.assertEqual(len(runde), 4)
        self.assertEqual(runde[0][0], datetime.date(2025, 11, 7))
        self.assertAlmostEqual(sum(v for _, v in runde), 5.1706, places=4)

    def test_uteblitt_utbetaling_er_ikke_sen_for_alltid(self):
        # Kommer ingen etterfølger før slingringen er brukt opp, mangler den.
        runde = fs.utbetalingsrunde(self.STST, datetime.date(2026, 12, 20))
        self.assertEqual(len(runde), 3)

    def test_etterfolgeren_tar_plassen(self):
        # Årets utbetaling er kommet: fjorårets blir ikke med i tillegg.
        serie = self.STST + [(datetime.date(2026, 11, 13), 1.25)]
        runde = fs.utbetalingsrunde(serie, datetime.date(2026, 11, 14))
        self.assertEqual([d for d, _ in runde], [d for d, _ in serie[-4:]])

    def test_bouvet_er_halvaarlig(self):
        self.assertEqual(fs.frekvens_label(len(self._strengt(self.BOUV))), "Kvartalsvis")
        runde = fs.utbetalingsrunde(self.BOUV, self.I_DAG)
        self.assertEqual(len(runde), 2)
        self.assertEqual(fs.frekvens_label(len(runde)), "Halvårlig")

    def test_hunt_har_en_ekstra_utbetaling_ikke_en_tidlig(self):
        # Eldste og nyeste ligger 302 dager fra hverandre: ikke samme
        # utbetaling to år på rad.
        self.assertEqual(len(fs.utbetalingsrunde(self.HUNT, self.I_DAG)), 5)

    def test_vanlig_kvartalsbetaler_er_uendret(self):
        serie = [(datetime.date(2025, 8, 20), 1.0), (datetime.date(2025, 11, 20), 1.0),
                 (datetime.date(2026, 2, 20), 1.0), (datetime.date(2026, 5, 20), 1.0),
                 (datetime.date(2026, 8, 20), 1.0)]
        runde = fs.utbetalingsrunde(serie, self.I_DAG)
        self.assertEqual(runde, self._strengt(serie))
        self.assertEqual(len(runde), 4)

    def test_aarlig_betaler_som_er_ti_dager_sen(self):
        serie = [(datetime.date(2024, 5, 8), 4.0), (datetime.date(2025, 5, 10), 5.0)]
        self.assertEqual(self._strengt(serie, datetime.date(2026, 5, 20)), [])
        self.assertEqual(fs.utbetalingsrunde(serie, datetime.date(2026, 5, 20)), [serie[-1]])
        # Etter 45 dager er den ikke sen lenger.
        self.assertEqual(fs.utbetalingsrunde(serie, datetime.date(2026, 6, 30)), [])

    def test_maanedlig_betaler_faar_ikke_45_dager(self):
        # Tretten utbetalinger i vinduet blir tolv, og en som mangler, blir
        # ikke dekket av den som gikk ut for en måned siden.
        start = datetime.date(2025, 10, 20)
        serie = [(start + datetime.timedelta(days=30 * i), 1.0) for i in range(14)]
        i_dag = serie[-1][0] + datetime.timedelta(days=2)
        strengt = self._strengt(serie, i_dag)
        self.assertEqual(len(strengt), 13)
        self.assertEqual(len(fs.utbetalingsrunde(serie, i_dag)), 12)
        # Sen: de to siste månedene mangler. En utbetaling som gikk ut for 20
        # dager siden, dekker ikke hullet; slingringen er 12 dager her.
        sen = serie[:-2]
        i_dag = sen[1][0] + datetime.timedelta(days=365 + 20)
        self.assertEqual(len(self._strengt(sen, i_dag)), 10)
        self.assertEqual(len(fs.utbetalingsrunde(sen, i_dag)), 10)
        # Gikk den ut for fem dager siden, er den bare sen.
        i_dag = sen[1][0] + datetime.timedelta(days=365 + 5)
        self.assertEqual(len(fs.utbetalingsrunde(sen, i_dag)), 11)

    def test_tom_serie(self):
        self.assertEqual(fs.utbetalingsrunde([], self.I_DAG), [])

    # ── Regelen for betalt årsrate ser runden ────────────────────────────
    def _soff_rad(self):
        strengt = [{"ex_dato": d.isoformat(), "belop": v} for d, v in self.SOFF]
        return {"ticker": "SOFF", "pris": 67.7, "frekvens": "Kvartalsvis",
                "utbytte_per_aksje": 0.51, "utbytte_yield": 0.75,
                "utbytte_12m": 6.1395, "utbytte_12m_antall": 5, "utbytte_12m_liste": strengt,
                "utbytte_runde": strengt[1:],
                "utbytte_per_ar": {"2021": 0.0, "2022": 0.0, "2023": 0.0, "2024": 0.0, "2025": 0.5119}}

    def test_soff_er_kandidat_med_runden(self):
        a = self._soff_rad()
        self.assertFalse(fs.betalt_kan_bli_arsrate(a, self.I_DAG))
        self.assertTrue(fs.betalt_kan_bli_arsrate(fs.med_runde(a), self.I_DAG))

    def test_soff_faar_de_fire_siste_og_riktig_merkelapp(self):
        a = self._soff_rad()
        fs.bruk_betalt_som_arsrate(a)
        self.assertEqual(a["utbytte_per_aksje"], 5.63)
        self.assertEqual(a["utbytte_yield"], 8.31)
        self.assertEqual((a["arsrate_kilde"], a["arsrate_antall"]), ("siste_utbetalinger", 4))
        self.assertEqual(fs.arsrate_merke(a), "siste fire utbetalinger")
        self.assertIn("fra de fire siste utbetalingene", fs._faq_arsrate_ledd(a))
        # Det strenge vinduet er urørt: det er det som vises som betalt.
        self.assertEqual((a["utbytte_12m"], a["utbytte_12m_antall"]), (6.1395, 5))

    def test_uten_runde_er_alt_som_for(self):
        a = self._soff_rad()
        del a["utbytte_runde"]
        a.update(utbytte_12m_antall=4)
        self.assertIs(fs.med_runde(a), a)
        fs.bruk_betalt_som_arsrate(a)
        self.assertEqual(a["arsrate_kilde"], "betalt_12m")
        self.assertNotIn("arsrate_antall", a)
        self.assertEqual(fs.arsrate_merke(a), "siste 12 mnd")
        a["arsrate_ekstra_trukket"] = 0.8
        self.assertEqual(fs.arsrate_merke(a), "siste 12 mnd, uten engangsutbytte")
        self.assertEqual(fs.arsrate_merke({"arsrate_kilde": "stoppet"}), "")

    def test_rate_lik_runden_faar_merkelappen_uten_at_tallet_endres(self):
        # STST: vakten har alt valgt de fire siste (5,17). Avviket er null,
        # så regelen for betalt årsrate slår ikke inn, men merkelappen skal
        # ikke si «annualisert» ved siden av 3,78 kr betalt siste 12 måneder.
        runde = [{"ex_dato": d.isoformat(), "belop": v} for d, v in self.STST[-4:]]
        a = {"ticker": "STST", "pris": 42.0, "frekvens": "Kvartalsvis", "utbytte_per_aksje": 5.17,
             "utbytte_yield": 12.31, "utbytte_12m": 3.7848, "utbytte_12m_antall": 3,
             "utbytte_12m_liste": runde[1:], "utbytte_runde": runde}
        self.assertFalse(fs.betalt_kan_bli_arsrate(fs.med_runde(a), self.I_DAG))
        self.assertTrue(fs.merk_rate_lik_runden(a))
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"]), (5.17, 12.31))
        self.assertEqual(fs.arsrate_merke(a), "siste fire utbetalinger")
        # Avviker raten fra runden, eller er runden lik vinduet, røres ingenting.
        b = dict(a, utbytte_per_aksje=7.15)
        b.pop("arsrate_kilde"), b.pop("arsrate_antall")
        self.assertFalse(fs.merk_rate_lik_runden(b))
        self.assertNotIn("arsrate_kilde", b)
        c = {"pris": 10.0, "frekvens": "Kvartalsvis", "utbytte_per_aksje": 1.5,
             "utbytte_12m": 1.5, "utbytte_12m_antall": 4}
        self.assertFalse(fs.merk_rate_lik_runden(c))
        self.assertNotIn("arsrate_kilde", c)

    def test_boksen_forklarer_avviket(self):
        # STST: raten er de fire siste, den eldste ligger utenfor vinduet.
        a = {"ticker": "STST", "pris": 42.0, "utbytte_yield": 12.31, "utbytte_per_aksje": 5.17,
             "utbytte_12m": 3.7847, "utbytte_12m_antall": 3, "frekvens": "Kvartalsvis",
             "arsrate_kilde": "siste_utbetalinger", "arsrate_antall": 4,
             "utbytte_per_ar": {"2021": 0.0, "2022": 0.0, "2023": 0.0, "2024": 10.9835, "2025": 12.7382},
             "utbytte_forste_ar": 2024}
        html = fs.lag_betalt_boks(a, fs._nf)
        self.assertIn("bygger på de fire siste utbetalingene", html)
        self.assertIn("rett før tolvmånedersvinduet", html)
        a["arsrate_kilde"] = "betalt_12m"
        self.assertNotIn("bygger på", fs.lag_betalt_boks(a, fs._nf))


class TestKuttMedEnManglende(unittest.TestCase):
    """velg_arsrate() når én utbetaling mangler og det ikke er vinduskanten."""

    def test_stst_etter_slingringen(self):
        # Tre av fire i runden, 3,78 kr mot 12,74 i fjor. Regnet opp for den
        # som mangler er det 5,05: et kutt, ikke et halvt år.
        self.assertAlmostEqual(fs.velg_arsrate(12.7382, 3.7847, 3, "Kvartalsvis"), 3.7847)

    def test_stabil_betaler_er_ikke_et_kutt(self):
        self.assertEqual(fs.velg_arsrate(8.0, 6.0, 3, "Kvartalsvis"), 8.0)
        self.assertEqual(fs.velg_arsrate(10.0, 5.0, 1, "Halvårlig"), 10.0)
        # Litt lavere er heller ikke nok: 6,5 regnet opp er 8,67 av 9,0.
        self.assertEqual(fs.velg_arsrate(9.0, 6.5, 3, "Kvartalsvis"), 9.0)

    def test_aarlig_og_to_manglende_roeres_ikke(self):
        self.assertEqual(fs.velg_arsrate(6.0, 0.0, 0, "Årlig"), 6.0)
        self.assertEqual(fs.velg_arsrate(12.0, 2.0, 2, "Kvartalsvis"), 12.0)

    def test_kan_aldri_heve(self):
        self.assertEqual(fs.velg_arsrate(4.0, 30.0, 3, "Kvartalsvis"), 4.0)



_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BUNNLENKER = ("/om/", "/metode/", "/personvern/", "/vilkaar/")


def _haandskrevne_sider():
    """Håndskrevne sider med bunntekst: alt utenom aksjer/** og videresendinger."""
    import re as _re
    for mappe, under, filer in os.walk(_REPO):
        under[:] = [d for d in under if d not in (".git", ".claude", "node_modules", "test-results", "promo", "aksjer")]
        for navn in filer:
            if navn.endswith(".html"):
                sti = os.path.join(mappe, navn)
                tekst = open(sti, encoding="utf-8").read()
                fot = _re.search(r"<footer.*?</footer>", tekst, _re.S)
                # std-footer er STANDARD_FOOTER fra en generert side (rapportkalenderen),
                # som test_standard_bunntekst dekker og datajobben skriver på nytt.
                if fot and "std-footer" not in fot.group(0):
                    yield os.path.relpath(sti, _REPO), tekst, fot.group(0)


class TestBunntekst(unittest.TestCase):
    """Om, metode, personvern og vilkår fra alle sider (2026-11-18).

    17 sider manglet /om/ og /vilkaar/ i bunnteksten, og ingen hadde en
    metodeside å lenke til. Google ser etter avsender og metode på
    finanssider, og leseren skal finne dem fra hvor som helst.
    """

    def test_haandskrevne_sider(self):
        sider = list(_haandskrevne_sider())
        self.assertGreater(len(sider), 30)
        for rel, _, fot in sider:
            for lenke in _BUNNLENKER:
                self.assertIn(f'href="{lenke}"', fot, f"{rel} mangler {lenke} i bunnteksten")

    def test_standard_bunntekst(self):
        for lenke in _BUNNLENKER:
            self.assertIn(f'href="{lenke}"', fs.STANDARD_FOOTER)

    def test_lesbar_farge(self):
        """Kilden og ansvarsfraskrivelsen hadde 2,49:1 i lyst og 2,66:1 i mørkt
        tema (gray-400 på gray-50, gray-600 på gray-950). Kravet er 4,5:1.
        Designrunden 22.11.2026 ga gray-500 / gray-400."""
        for rel, _, fot in _haandskrevne_sider():
            self.assertNotIn("text-gray-400 dark:text-gray-600", fot, rel)
            self.assertIn("text-gray-500 dark:text-gray-400", fot, rel)
        f = fs.STANDARD_FOOTER
        self.assertNotIn("color:#9ca3af;line-height", f)
        self.assertIn("color:#6b7280;line-height", f)
        self.assertIn(".dark .std-footer { color:#9ca3af", f)

    def test_metodesiden_er_i_sitemap_og_finnes(self):
        self.assertTrue(os.path.exists(os.path.join(_REPO, "metode", "index.html")))
        import inspect
        self.assertIn("https://exday.no/metode/", inspect.getsource(fs.generer_sitemap))


class TestArtikkelKontrollert(unittest.TestCase):
    """«Sist kontrollert» på artiklene må være samme dato som dateModified."""

    def test_synlig_dato_er_date_modified(self):
        import re as _re
        mappe = os.path.join(_REPO, "artikler")
        sjekket = 0
        for slug in sorted(os.listdir(mappe)):
            sti = os.path.join(mappe, slug, "index.html")
            if not os.path.isfile(sti):
                continue
            t = open(sti, encoding="utf-8").read()
            dm = _re.search(r'"dateModified":\s*"(\d{4}-\d\d-\d\d)"', t)
            self.assertIsNotNone(dm, f"{slug} mangler dateModified")
            linje = _re.search(r'class="sist-kontrollert[^"]*">.*?<time datetime="([\d-]+)"', t, _re.S)
            self.assertIsNotNone(linje, f"{slug} mangler «sist kontrollert»-linja")
            self.assertEqual(linje.group(1), dm.group(1), f"{slug}: synlig dato og dateModified er ulike")
            sjekket += 1
        self.assertGreater(sjekket, 10)


class TestKursvarsel(unittest.TestCase):
    """Skjult varsel på aksjesiden som assets/kursferskhet.js viser."""

    def test_kursdag_fra_raden(self):
        gml = fs.DATA_SIST_OPPDATERT
        try:
            fs.DATA_SIST_OPPDATERT = "2026-11-18T16:45:00Z"
            html = fs.lag_kursvarsel({"hentet": "2026-11-16T07:10:00Z"})
            # 08.10 i Oslo mandag gjelder fredagens kurs.
            self.assertIn('data-kursdag="2026-11-13"', html)
            self.assertIn("hidden", html)
            self.assertIn("/assets/kursferskhet.js", html)
            self.assertIn('data-kursdag="2026-11-18"', fs.lag_kursvarsel({}))
            self.assertIn("2026-12-24", fs.lag_kursvarsel({}))
        finally:
            fs.DATA_SIST_OPPDATERT = gml

    def test_uten_dato_ingen_varsel(self):
        gml = fs.DATA_SIST_OPPDATERT
        try:
            fs.DATA_SIST_OPPDATERT = ""
            self.assertEqual(fs.lag_kursvarsel({}), "")
        finally:
            fs.DATA_SIST_OPPDATERT = gml

    def test_ett_antall(self):
        self.assertEqual(fs.antall_i_katalog([{}] * 155), 155)
        self.assertEqual(fs.antall_i_katalog(None), 0)

class TestRapportbunken2211(unittest.TestCase):
    """Seks funn fra rapportagentene i bunken for 3. kvartal (22.11.2026)."""

    # ── MEDI: kvartalsvis fra 27.10.2026 (684699) ──────────────────────────
    MEDI = {"ticker": "MEDI", "frekvens": "Kvartalsvis", "pris": 319.0,
            "utbytte_per_aksje": 6.0, "utbytte_yield": 1.88,
            "utbytte_12m": 10.5, "utbytte_12m_antall": 2,
            "utbytte_12m_liste": [{"ex_dato": "2026-05-07", "belop": 8.0},
                                  {"ex_dato": "2026-10-27", "belop": 2.5}]}

    def test_medi_kvartalsvis_annualiserer_det_nye(self):
        a = dict(self.MEDI, arsrate_kilde="betalt_12m")
        self.assertTrue(fs.bruk_frekvens_fra(a, "2026-10-27"))
        self.assertEqual(a["utbytte_per_aksje"], 10.0)
        self.assertEqual(a["utbytte_yield"], 3.13)
        self.assertNotIn("arsrate_kilde", a)   # kortet sier «annualisert»

    def test_frekvens_fra_slutter_av_seg_selv(self):
        # Ingen ny utbetaling ennå: ingenting gjøres.
        a = dict(self.MEDI, utbytte_12m_liste=self.MEDI["utbytte_12m_liste"][:1])
        self.assertFalse(fs.bruk_frekvens_fra(a, "2026-10-27"))
        # Bare nye utbetalinger i vinduet: de vanlige reglene gjelder.
        a = dict(self.MEDI, utbytte_12m_liste=self.MEDI["utbytte_12m_liste"][1:])
        self.assertFalse(fs.bruk_frekvens_fra(a, "2026-10-27"))

    def test_medi_i_tickers(self):
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("MEDI"), "Kvartalsvis")
        self.assertEqual(fs.FREKVENS_FRA["MEDI"], {"dato": "2026-10-27", "melding": "684699"})
        for t, ff in fs.FREKVENS_FRA.items():
            datetime.date.fromisoformat(ff["dato"])
            self.assertTrue(str(ff["melding"]).isdigit(), t)

    # ── OKEA: kvartalsvis igjen, 2,00 kr ex 2.12.2026 (685403) ────────────
    OKEA = {"ticker": "OKEA", "frekvens": "Kvartalsvis", "pris": 46.05,
            "utbytte_per_aksje": 2.0, "utbytte_yield": 4.34, "utbytte_12m": 0,
            "utbytte_12m_antall": 0, "utbytte_12m_liste": [],
            "annonsert_utbytte": 2.0, "annonsert_ex": "2026-12-02"}

    def test_okea_kunngjort_ikke_annualisert(self):
        a = dict(self.OKEA)
        self.assertTrue(fs.merk_kunngjort_rate(a, datetime.date(2026, 11, 22)))
        self.assertEqual(fs.arsrate_merke(a), "kunngjort utbetaling")
        self.assertEqual(fs._arsrate_ledd(a), " (kunngjort utbetaling)")
        self.assertEqual(a["utbytte_per_aksje"], 2.0)
        # Etter ex-datoen er det ikke kunngjort lenger.
        self.assertFalse(fs.merk_kunngjort_rate(dict(self.OKEA), datetime.date(2026, 12, 3)))

    def test_okea_etter_ex_dato_er_siste_12_mnd(self):
        a = dict(self.OKEA, utbytte_12m=2.0, utbytte_12m_antall=1,
                 utbytte_12m_liste=[{"ex_dato": "2026-12-02", "belop": 2.0}])
        self.assertTrue(fs.merk_rate_lik_betalt(a))
        self.assertEqual(fs.arsrate_merke(a), "siste 12 mnd")
        # Et helt vindu, eller en rate som er ganget opp, merkes ikke.
        self.assertFalse(fs.merk_rate_lik_betalt(dict(a, utbytte_per_aksje=8.0)))
        self.assertFalse(fs.merk_rate_lik_betalt(dict(a, utbytte_12m_antall=4)))

    def test_dnb_ganger_ikke_opp_uten_utbetalinger(self):
        # Regelen bor i dnb_arsrate() siden 22.11.2026 (Vistin), og main() kaller den.
        self.assertEqual(fs.dnb_arsrate(dict(self.OKEA, utbytte_12m_antall=0), 2.0, "2026-12-02"), 2.0)
        self.assertEqual(fs.dnb_arsrate(dict(self.OKEA, utbytte_12m_antall=4), 2.0, "2026-12-02"), 8.0)
        kilde = inspect.getsource(fs.main)
        self.assertIn("dnb_arsrate(aksje, dnb_belop", kilde)
        self.assertIn("merk_kunngjort_rate(aksje) or merk_betalt_og_kunngjort(aksje) "
                      "or merk_rate_lik_betalt(aksje)", kilde)

    def test_okea_i_tickers(self):
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("OKEA"), "Kvartalsvis")
        self.assertNotIn("ikke foreslått noe utbytte for 2026", fs.BESKRIVELSER["OKEA"])

    # ── AKAST: kapital, uregelmessig og det ekstraordinære i februar ──────
    AKAST_FEB = ("Extraordinary cash dividend: 0.4 per share\nDeclared currency: NOK\n"
                 "Ex-date: 16 February 2026\nThe distribution will be classified as a "
                 "repayment of paid-in capital.")
    AKAST = {"ticker": "AKAST", "frekvens": "Uregelmessig", "pris": 9.21,
             "utbytte_per_aksje": 0.75, "utbytte_yield": 8.14,
             "utbytte_12m": 4.9, "utbytte_12m_antall": 4,
             "utbytte_12m_liste": [{"ex_dato": "2026-02-16", "belop": 0.4},
                                   {"ex_dato": "2026-05-18", "belop": 1.5},
                                   {"ex_dato": "2026-08-25", "belop": 0.5},
                                   {"ex_dato": "2026-11-13", "belop": 2.5}],
             "utbytte_per_ar": {"2021": 0.0, "2022": 0.0, "2023": 0.0,
                                "2024": 0.0, "2025": 0.75}}

    def test_akast_tittel_leses_for_kapital(self):
        for t in ("Akastor ASA: Declaration of cash dividend",
                  "Akastor ASA: Declaration of extraordinary cash dividend"):
            self.assertTrue(fs._KAPITAL_TITTEL.search(t), t)
        gml_liste, gml_tekst = fs._newsweb_meldinger, fs._newsweb_tekst
        fs._newsweb_meldinger = lambda _t: [
            {"title": "Akastor ASA: Declaration of cash dividend", "messageId": 686159,
             "publishedTime": "2026-11-11T07:00"}]
        fs._newsweb_tekst = lambda _m: ("decided to pay a cash dividend of NOK 2.50 per share. "
                                        "The distribution will be classified as a repayment "
                                        "of paid-in capital.")
        try:
            kt = fs.hent_kapitaltilbake("AKAST", i_dag=datetime.date(2026, 11, 22))
        finally:
            fs._newsweb_meldinger, fs._newsweb_tekst = gml_liste, gml_tekst
        self.assertEqual(kt["andel"], 1.0)

    def test_akast_ekstraordinaert_belop_leses(self):
        u = fs._parse_utbetalinger(self.AKAST_FEB)
        self.assertEqual([(x["ex_dato"], x["belop"], x["valuta"]) for x in u],
                         [("2026-02-16", 0.4, "NOK")])

    def test_akast_hel_engangsutbetaling_trekkes_fra(self):
        funn = [{"ex_dato": "2026-02-16", "ekstra": 0.4, "total": None, "valuta": "NOK",
                 "melding_dato": "2026-02-12"}]
        self.assertIsNone(fs.ekstra_i_kroner(self.AKAST, [dict(f) for f in funn]))
        fs.fyll_total_fra_serie(self.AKAST, funn)
        self.assertEqual(funn[0]["total"], 0.4)
        ekstra = fs.ekstra_i_kroner(self.AKAST, funn)
        self.assertEqual(ekstra, 0.4)
        self.assertEqual(fs.hele_engangsutbetalinger(funn), 1)
        uten = dict(self.AKAST, utbytte_12m=4.9 - ekstra, utbytte_12m_antall=3)
        self.assertTrue(fs.betalt_kan_bli_arsrate(uten))
        a = dict(self.AKAST)
        fs.bruk_betalt_som_arsrate(a, ekstra)
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"]), (4.5, 48.86))
        self.assertEqual(fs.arsrate_merke(a), "siste 12 mnd, uten engangsutbytte")

    def test_bare_hele_kronebelop_faar_total(self):
        # En dollar, eller en del av utbetalingen, gir fortsatt ingen total.
        for f in ({"ex_dato": "2026-02-16", "ekstra": 0.4, "total": None, "valuta": "USD"},
                  {"ex_dato": "2026-05-18", "ekstra": 0.5, "total": None, "valuta": "NOK"}):
            fs.fyll_total_fra_serie(self.AKAST, [f])
            self.assertIsNone(f["total"])

    def test_akast_i_tickers(self):
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("AKAST"), "Uregelmessig")

    # ── SOFF: 0,12 av 0,30 USD ekstraordinært (presentasjonen, 685540) ────
    SOFF = {"ticker": "SOFF", "frekvens": "Kvartalsvis", "pris": 65.0,
            "utbytte_per_aksje": 5.63, "utbytte_yield": 8.66,
            "utbytte_12m": 6.1396, "utbytte_12m_antall": 5,
            "utbytte_12m_liste": [{"ex_dato": "2025-11-25", "belop": 0.5119},
                                  {"ex_dato": "2026-03-10", "belop": 0.4832},
                                  {"ex_dato": "2026-05-20", "belop": 0.9169},
                                  {"ex_dato": "2026-07-17", "belop": 1.4592},
                                  {"ex_dato": "2026-11-06", "belop": 2.7683}],
            "utbytte_runde": [{"ex_dato": "2026-03-10", "belop": 0.4832},
                              {"ex_dato": "2026-05-20", "belop": 0.9169},
                              {"ex_dato": "2026-07-17", "belop": 1.4592},
                              {"ex_dato": "2026-11-06", "belop": 2.7683}]}

    def test_soff_saerutbytte_i_tickers(self):
        s = fs.SAERUTBYTTE["SOFF"]
        self.assertEqual(s, [{"ex_dato": "2026-11-06", "belop": 1.1073, "melding": "685540"}])
        # 0,12 av 0,30 dollar, regnet om med selskapets kronebeløp 2,76834 (685858).
        self.assertAlmostEqual(0.12 / 0.30 * 2.76834, s[0]["belop"], places=4)

    def test_soff_engangsdelen_trekkes_fra(self):
        kandidat = fs.med_runde(self.SOFF)
        saer = fs.saerutbytte_i_vindu(kandidat)
        self.assertEqual(len(saer), 1)
        self.assertEqual((saer[0]["ekstra"], saer[0]["total"]), (1.1073, 2.7683))
        funn = fs.med_saerutbytte([], saer)
        ekstra = fs.ekstra_i_kroner(kandidat, funn)
        self.assertAlmostEqual(ekstra, 1.1073, places=4)
        self.assertEqual(fs.hele_engangsutbetalinger(funn), 0)
        a = dict(self.SOFF)
        fs.bruk_betalt_som_arsrate(a, ekstra)
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"]), (4.52, 6.95))
        self.assertEqual(fs.arsrate_merke(a), "siste fire utbetalinger, uten engangsutbytte")

    def test_saerutbytte_erstatter_newsweb_funn_for_samme_ex(self):
        saer = [{"ex_dato": "2026-11-06", "ekstra": 1.1073, "total": 2.7683, "valuta": "NOK"}]
        nw = [{"ex_dato": "2026-11-05", "ekstra": None, "total": None, "valuta": None},
              {"ex_dato": "2026-03-10", "ekstra": None, "total": None, "valuta": None}]
        ut = fs.med_saerutbytte(nw, saer)
        self.assertEqual([f["ex_dato"] for f in ut], ["2026-03-10", "2026-11-06"])

    # ── HUNT: 5-årssnitt 115,86 % ─────────────────────────────────────────
    HUNT = {"ticker": "HUNT", "pris": 16.26, "utbytte_12m": 4.03,
            "utbytte_per_ar": {"2021": 26.5247, "2022": 26.5247, "2023": 40.8481,
                               "2024": 0.0, "2025": 0.3},
            "utbytte_forste_ar": 2021, "snitt_yield_5ar": 115.86}

    def test_hunt_snitt_vises_ikke(self):
        r = {x["periode"]: x for x in fs.utbytte_perioder(self.HUNT)}
        self.assertIsNotNone(r["2"]["yield"])          # 2024–2025
        for p in ("3", "4", "5"):
            self.assertIsNone(r[p]["yield"], p)
        a = dict(self.HUNT)
        fs.sett_snitt_felter(a)
        self.assertEqual(a["snitt_yield_5ar"], 0)

    def test_vanlig_snitt_uendret(self):
        a = {"pris": 100.0, "utbytte_12m": 5.0, "utbytte_forste_ar": 2010,
             "utbytte_per_ar": {"2021": 4.0, "2022": 4.5, "2023": 5.0, "2024": 5.0, "2025": 5.5}}
        fs.sett_snitt_felter(a)
        self.assertEqual(a["snitt_yield_5ar"], 4.8)

    # ── HSHP: «Contributed Surplus» er ikke innbetalt kapital (683670) ────
    def test_hshp_contributed_surplus_er_ikke_kapital(self):
        tekst = ("The Board has approved a cash distribution of US$0.28 per share for "
                 "September 2026. The distribution will be made from the Company's "
                 "Contributed Surplus account.")
        self.assertIsNone(fs._parse_kapitaltilbake(tekst))


class TestRapportbunken2211Del2(unittest.TestCase):
    """ARCH (utdelinger på pause) og VISTIN (delt årsutbetaling), 22.11.2026."""

    # ── ARCH: pause meldt 21.10.2026 (684465) ──────────────────────────────
    ARCH_TITTEL = "Archer Limited: Archer distribution of shareholder return - NOK 0.62 per share"
    ARCH_TEKST = ("Archer Limited announces that the Board of Directors has approved a cash "
                  "distribution to shareholders as specified below. The distribution will be in "
                  "the form of return of capital and will be made from the Company's Contributed "
                  "Surplus account which consists of previously paid in share premium transferred "
                  "from the Company's Share Premium account.\n"
                  "Return of capital: NOK 0.62 per share\nDeclared currency: NOK\n"
                  "Ex-date: August 18, 2026\n")
    PAUSE = {"type": "utbytte_pause", "dato": "2026-10-21", "melding": "684465",
             "tekst": "Archer har satt utdelingene på pause."}
    ARCH = {"ticker": "ARCH", "frekvens": "Kvartalsvis", "pris": 16.7,
            "utbytte_per_aksje": 2.48, "utbytte_yield": 14.85, "ex_dato": None,
            "arsrate_kilde": "siste_utbetalinger", "arsrate_antall": 4,
            "utbytte_12m": 1.86, "utbytte_12m_antall": 3,
            "utbytte_12m_liste": [{"ex_dato": "2026-02-04", "belop": 0.62},
                                  {"ex_dato": "2026-05-20", "belop": 0.62},
                                  {"ex_dato": "2026-08-18", "belop": 0.62}],
            "utbetalinger": [["2025-11-06", 0.62], ["2026-02-04", 0.62],
                             ["2026-05-20", 0.62], ["2026-08-18", 0.62]]}

    def test_arch_tittel_og_tekst_gir_kapital(self):
        self.assertTrue(fs._KAPITAL_TITTEL.search(self.ARCH_TITTEL))
        # Pauseraporten og ex-dagsmeldingen er ikke utbyttemeldinger om neste utbetaling.
        for t in ("Archer Limited: Q3 2026 trading and shareholder distribution update",
                  "Archer Limited - Ex cash distribution NOK 0.62 today"):
            self.assertFalse(fs._KAPITAL_TITTEL.search(t), t)
        self.assertEqual(fs._parse_kapitaltilbake(self.ARCH_TEKST), 1.0)

    def test_return_of_capital_gjelder_ikke_nektet_eller_contributed_surplus_alene(self):
        # HSHP-fella: «Contributed Surplus» alene er ikke innbetalt kapital (683670).
        self.assertIsNone(fs._parse_kapitaltilbake(
            "The distribution will be made from the Company's Contributed Surplus account."))
        self.assertIsNone(fs._parse_kapitaltilbake(
            "The distribution will not be a return of capital."))

    def test_arch_henter_kapital_fra_nyeste_utbyttemelding(self):
        gml_liste, gml_tekst = fs._newsweb_meldinger, fs._newsweb_tekst
        fs._newsweb_meldinger = lambda _t: [
            {"title": "Archer Limited: Q3 2026 trading and shareholder distribution update",
             "messageId": 684465, "publishedTime": "2026-10-21T06:00"},
            {"title": self.ARCH_TITTEL, "messageId": 679579, "publishedTime": "2026-08-13T15:00"}]
        fs._newsweb_tekst = lambda _m: self.ARCH_TEKST
        try:
            kt = fs.hent_kapitaltilbake("ARCH", i_dag=datetime.date(2026, 11, 22))
        finally:
            fs._newsweb_meldinger, fs._newsweb_tekst = gml_liste, gml_tekst
        self.assertEqual((kt["andel"], kt["melding_id"]), (1.0, 679579))

    def test_pause_nuller_arsraten(self):
        a = dict(self.ARCH)
        self.assertTrue(fs.bruk_utbytte_pause(a, self.PAUSE, datetime.date(2026, 11, 22)))
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"], a["arsrate_kilde"]),
                         (0.0, 0.0, "pause"))
        self.assertNotIn("arsrate_antall", a)
        self.assertEqual(a["utbytte_12m"], 1.86)       # det som er betalt, står
        self.assertEqual(fs.arsrate_merke(a), "utdelinger på pause")

    def test_pause_oppheves_av_ny_utbetaling_eller_ny_ex_dato(self):
        i_dag = datetime.date(2026, 11, 22)
        ny = dict(self.ARCH, utbetalinger=self.ARCH["utbetalinger"] + [["2027-02-10", 0.30]])
        self.assertFalse(fs.bruk_utbytte_pause(ny, self.PAUSE, i_dag))
        self.assertEqual(ny["utbytte_yield"], 14.85)
        kunngjort = dict(self.ARCH, ex_dato="2027-02-10")
        self.assertFalse(fs.bruk_utbytte_pause(kunngjort, self.PAUSE, i_dag))
        # En passert ex-dato fra før meldingen er ikke en ny utdeling.
        gammel = dict(self.ARCH, ex_dato="2026-08-18")
        self.assertTrue(fs.bruk_utbytte_pause(gammel, self.PAUSE, i_dag))

    def test_pause_gjelder_bare_hendelsestypen(self):
        a = dict(self.ARCH)
        self.assertFalse(fs.bruk_utbytte_pause(a, dict(self.PAUSE, type="fusjon"), datetime.date(2026, 11, 22)))
        self.assertFalse(fs.bruk_utbytte_pause(a, None))
        self.assertEqual(a["utbytte_yield"], 14.85)

    def test_hendelsen_faller_bort_nar_pausen_er_over(self):
        a = dict(self.ARCH)
        fs.sett_hendelse(a, self.PAUSE, datetime.date(2026, 11, 22))
        self.assertEqual(a["hendelse"]["melding"], "684465")
        a["utbetalinger"] = a["utbetalinger"] + [["2027-02-10", 0.30]]
        fs.sett_hendelse(a, self.PAUSE, datetime.date(2027, 2, 11))
        self.assertNotIn("hendelse", a)

    def test_pause_tar_aksjen_ut_av_rangering_og_malene(self):
        a = dict(self.ARCH, sektor="Energitjenester", hendelse=self.PAUSE)
        self.assertFalse(fs.i_rangering(a))
        self.assertEqual(fs._beregn_mal_py(dict(a, utbytte_yield=7.0)), [])
        self.assertIn("utdelingene på pause", fs.HENDELSE_TITTEL["utbytte_pause"].replace("satt ", ""))
        self.assertEqual(fs.HENDELSE_KORT["utbytte_pause"], "utdeling på pause")

    def test_kapitalnotatet_bruker_fortid_ved_pause(self):
        a = dict(self.ARCH, kapital_tilbake={"andel": 1.0, "melding_dato": "2026-08-13"})
        assert "betaler selskapet ut" in fs.lag_kapital_note(a, fs._nf)
        a["arsrate_kilde"] = "pause"
        note = fs.lag_kapital_note(a, fs._nf)
        self.assertIn("var den siste utbetalingen", note)
        self.assertNotIn("betaler selskapet ut", note)

    def test_faq_sier_ikke_at_selskapet_betaler(self):
        a = dict(self.ARCH, navn="Archer Limited", ar_med_utbytte=2, utbytteaar=[2025, 2026],
                 payout_ratio=0, hendelse=self.PAUSE)
        a = dict(a, utbytte_per_aksje=0.0, utbytte_yield=0.0, arsrate_kilde="pause")
        tekst = json.dumps(fs._lag_faq_seksjon(a, datetime.date(2026, 11, 22)), ensure_ascii=False)
        self.assertIn("har satt utdelingene til aksjonærene på pause (21. okt 2026)", tekst)
        self.assertIn("Før pausen betalte selskapet ut fire ganger i året", tekst)
        self.assertNotIn("betaler utbytte fire ganger", tekst)

    # BlueNord (24.11.2026): en fusjon der selskapet har sagt at det ikke vedtar
    # flere utbytter før fusjonen er gjennomført. Rapporten for tredje kvartal
    # (684964): «may not declare and distribute any further dividends prior to
    # the Effective Date». Siden viste 180,58 kr i året (35,62 %).
    FUSJON = {"type": "fusjon", "dato": "2026-08-24", "melding": "680568",
              "ingen_utbytte": True, "tekst": "BlueNord skal fusjoneres inn i Vår Energi."}
    BNOR = {"ticker": "BNOR", "utbytte_per_aksje": 180.58, "utbytte_yield": 35.62,
            "arsrate_kilde": "siste_utbetalinger", "arsrate_antall": 4, "frekvens": "Kvartalsvis",
            "utbytte_12m": 180.58,
            "ex_dato": None,
            "utbetalinger": [["2025-11-20", 36.17], ["2026-02-20", 36.17],
                             ["2026-05-22", 36.17], ["2026-07-17", 66.82]]}

    def test_fusjon_med_ingen_utbytte_nuller_raten(self):
        a = dict(self.BNOR)
        self.assertTrue(fs.bruk_utbytte_pause(a, self.FUSJON, datetime.date(2026, 11, 24)))
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"], a["arsrate_kilde"]),
                         (0.0, 0.0, "pause"))
        self.assertEqual(a["utbytte_12m"], 180.58)     # det som er betalt, står
        self.assertEqual(fs.arsrate_merke(a), "utdelinger på pause")

    def test_fusjon_uten_flagg_nulles_ikke(self):
        a = dict(self.BNOR)
        h = {k: v for k, v in self.FUSJON.items() if k != "ingen_utbytte"}
        self.assertFalse(fs.bruk_utbytte_pause(a, h, datetime.date(2026, 11, 24)))
        self.assertFalse(fs.bruk_utbytte_pause(a, dict(self.FUSJON, ingen_utbytte="ja"),
                                               datetime.date(2026, 11, 24)))
        self.assertEqual(a["utbytte_yield"], 35.62)

    def test_fusjon_pausen_oppheves_av_ny_utbetaling_eller_ex_dato(self):
        i_dag = datetime.date(2026, 11, 24)
        ny = dict(self.BNOR, utbetalinger=self.BNOR["utbetalinger"] + [["2026-12-10", 5.0]])
        self.assertFalse(fs.bruk_utbytte_pause(ny, self.FUSJON, i_dag))
        kunngjort = dict(self.BNOR, ex_dato="2026-12-10")
        self.assertFalse(fs.bruk_utbytte_pause(kunngjort, self.FUSJON, i_dag))
        self.assertEqual(kunngjort["utbytte_yield"], 35.62)

    def test_fusjon_beholder_hendelsen_og_faq_sier_ikke_pause(self):
        a = dict(self.BNOR, navn="BlueNord ASA", ar_med_utbytte=2, utbytteaar=[2025, 2026], payout_ratio=0)
        fs.sett_hendelse(a, self.FUSJON, datetime.date(2026, 11, 24))
        self.assertEqual(a["hendelse"]["type"], "fusjon")          # fusjonsboksen står
        fs.bruk_utbytte_pause(a, self.FUSJON, datetime.date(2026, 11, 24))
        tekst = json.dumps(fs._lag_faq_seksjon(a, datetime.date(2026, 11, 24)), ensure_ascii=False)
        self.assertIn("har sagt at selskapet ikke vedtar flere utbytter før fusjonen er gjennomført", tekst)
        self.assertNotIn("på pause (24. aug", tekst)
        self.assertNotIn("betaler utbytte fire ganger", tekst)

    def test_bare_bnor_har_flagget_i_tickers_json(self):
        med = [t for t, h in fs.HENDELSE.items() if h.get("ingen_utbytte")]
        self.assertEqual(med, ["BNOR"])
        h = fs.HENDELSE["BNOR"]
        self.assertEqual((h["type"], h["melding"], h["dato"]), ("fusjon", "680568", "2026-08-24"))
        self.assertTrue(fs.gyldig_hendelse(h))

    def test_arch_i_tickers_json(self):
        h = fs.HENDELSE["ARCH"]
        self.assertEqual((h["type"], h["melding"], h["dato"]), ("utbytte_pause", "684465", "2026-10-21"))
        self.assertTrue(fs.gyldig_hendelse(h))
        # Ingen tall som kan endre seg i teksten; datoer og kroner står som fakta.
        self.assertNotRegex(h["tekst"], r"\d+(?:[.,]\d+)?\s*(?:%|prosent|kr\b|NOK)")

    # ── VISTIN: «additional ordinary» etter 1,00 kr i mai (685078, 665600) ──
    VISTIN = {"ticker": "VISTIN", "frekvens": "Årlig", "pris": 19.0,
              "utbytte_per_aksje": 0.5, "utbytte_12m": 1.0, "utbytte_12m_antall": 1,
              "utbytte_12m_liste": [{"ex_dato": "2026-05-22", "belop": 1.0}]}

    def test_vistin_ann_er_andre_del_av_aaret(self):
        self.assertEqual(fs.delt_arsutbytte(self.VISTIN, 0.5, "2026-11-24"), 1.5)
        # Før rettingen ble det kunngjorte beløpet ganget med 1 og sto som årsrate.
        self.assertEqual(fs.dnb_arsrate(self.VISTIN, 0.5, "2026-11-24"), 1.5)

    def test_arlig_betaler_paa_skjema_er_uberort(self):
        a = dict(self.VISTIN, utbytte_12m_liste=[{"ex_dato": "2025-11-10", "belop": 1.0}])
        self.assertIsNone(fs.delt_arsutbytte(a, 1.1, "2026-11-09"))     # 364 dager
        self.assertEqual(fs.dnb_arsrate(a, 1.1, "2026-11-09"), 1.1)
        # Opptil 45 dager tidligere enn årsdagen er fortsatt samme utbetaling.
        a = dict(self.VISTIN, utbytte_12m_liste=[{"ex_dato": "2025-12-20", "belop": 1.0}])
        self.assertIsNone(fs.delt_arsutbytte(a, 1.1, "2026-11-09"))     # 324 dager
        a = dict(self.VISTIN, utbytte_12m_liste=[{"ex_dato": "2026-01-10", "belop": 1.0}])
        self.assertEqual(fs.delt_arsutbytte(a, 1.1, "2026-11-09"), 2.1)  # 303 dager

    def test_bare_arlige_betalere_og_bare_kroner(self):
        for frekvens in ("Halvårlig", "Kvartalsvis", "Uregelmessig"):
            a = dict(self.VISTIN, frekvens=frekvens)
            self.assertIsNone(fs.delt_arsutbytte(a, 0.5, "2026-11-24"), frekvens)
        self.assertEqual(fs.dnb_arsrate(dict(self.VISTIN, frekvens="Halvårlig",
                                             utbytte_12m_antall=2), 0.5, "2026-11-24"), 1.0)
        self.assertIsNone(fs.delt_arsutbytte(self.VISTIN, 0, "2026-11-24"))
        self.assertIsNone(fs.delt_arsutbytte(dict(self.VISTIN, utbytte_12m_liste=[]), 0.5, "2026-11-24"))

    def test_frekvens_satt_for_hand_er_uberort(self):
        # NORBT, SB68, SOAG og KOG er «Årlig» i tickers.json fordi høstbetalingen er et tillegg.
        a = dict(self.VISTIN, ticker="NORBT")
        self.assertIn("NORBT", fs.FREKVENS_OVERSTYRT)
        self.assertIsNone(fs.delt_arsutbytte(a, 0.5, "2026-11-24"))
        self.assertEqual(fs.dnb_arsrate(a, 0.5, "2026-11-24"), 0.5)

    def test_paa_ex_dagen_telles_utbetalingen_ikke_to_ganger(self):
        a = dict(self.VISTIN, utbytte_12m_antall=2,
                 utbytte_12m_liste=[{"ex_dato": "2026-05-22", "belop": 1.0},
                                    {"ex_dato": "2026-11-24", "belop": 0.5}])
        self.assertEqual(fs.delt_arsutbytte(a, 0.5, "2026-11-24"), 1.5)

    def test_vistin_merkelapp(self):
        a = dict(self.VISTIN, utbytte_per_aksje=1.5, annonsert_utbytte=0.5,
                 annonsert_ex="2026-11-24")
        i_dag = datetime.date(2026, 11, 22)
        self.assertTrue(fs.merk_betalt_og_kunngjort(a, i_dag))
        self.assertEqual(fs.arsrate_merke(a), "betalt og kunngjort")
        self.assertIn("pluss den kunngjorte utbetalingen", fs._faq_arsrate_ledd(a))
        # Et forslag generalforsamlingen ikke har vedtatt, eller en rate et senere steg har satt, merkes ikke.
        self.assertFalse(fs.merk_betalt_og_kunngjort(dict(a, arsrate_kilde=None, ex_forbehold="2026-12-01"), i_dag))
        self.assertFalse(fs.merk_betalt_og_kunngjort(dict(a, arsrate_kilde=None, utbytte_per_aksje=0.5), i_dag))
        self.assertFalse(fs.merk_betalt_og_kunngjort(dict(a, arsrate_kilde=None), datetime.date(2026, 11, 25)))


class TestFikser2211(unittest.TestCase):
    """Fem funn fra kvartalsrapportene, 22.11.2026: BOR, BEWI, HUNT, AKAST, HSPG.

    Hver test feilet før rettingen. Meldingstekstene er forkortet, uten
    kontaktpersoner.
    """

    BOR_MELDINGER = [
        {"publishedTime": "2026-11-03T06:00", "messageId": 685408,
         "title": "BOR - EX. DIVIDEND NOK 1.50 TODAY"},
        {"publishedTime": "2026-10-30T07:01", "messageId": 685182,
         "title": "Borgestad ASA: Key information relating to the cash dividend to be paid by Borgestad ASA"},
        {"publishedTime": "2026-10-30T07:00", "messageId": 685169,
         "title": "Borgestad ASA: Interim financial report for third quarter 2026 and NOK 1.50 dividend distribution"},
        {"publishedTime": "2026-03-02T06:00", "messageId": 667200,
         "title": "BOR \u2013 EX. DIVIDEND NOK 0.50 TODAY"},
        {"publishedTime": "2026-02-26T07:01", "messageId": 666876,
         "title": "Borgestad ASA: Key information relating to the cash dividend to be paid by Borgestad ASA"},
        {"publishedTime": "2026-02-26T07:00", "messageId": 666846,
         "title": "Borgestad ASA: Interim financial report for fourth quarter 2025 and NOK 0.5 additional dividend distribution"},
    ]
    BOR_TEKSTER = {
        685408: "Issuer: Borgestad ASA\nEx. date: 3 November 2026\nDividend amount: NOK 1.50 per share\n",
        685182: ("The board of directors has resolved to distribute a dividend of NOK 1.50 per share "
                 "based on the annual accounts for 2025.\nDividend amount: NOK 1.50 per share\n"
                 "Announced currency: Norwegian kroner (NOK)\nEx-date: 3 November 2026\n"
                 "Payment date: 6 November 2026\nDate of approval: 30 October 2026\n"),
        685169: ("Borgestad ASA will distribute an extraordinary dividend of NOK 1.50 per share, "
                 "payable on or about November 6, 2026. For Norwegian tax purposes, the distribution "
                 "shall be in the form of repayment of paid-in equity."),
        667200: "Issuer: Borgestad ASA\nEx. date: 2 March 2026\nDividend amount: NOK 0.50 per share\n",
        666876: ("The board of directors has resolved to distribute an additional dividend of NOK 0.50 "
                 "per share based on the annual accounts for 2024.\nDividend amount: NOK 0.50 per share\n"
                 "Announced currency:  Norwegian kroner (NOK)\nEx-date: 2 March 2026\n"
                 "Payment date: 6 March 2026\nDate of approval: 26 February 2026\n"),
        666846: ("Borgestad ASA will distribute a dividend of NOK 0.50 per share, payable March 6, 2026. "
                 "The board has resolved to distribute an additional dividend of NOK 0.50 per share "
                 "based on the annual accounts for 2024."),
    }
    BOR_RAD = {"ticker": "BOR", "frekvens": "Halvårlig", "pris": 15.05,
               "utbytte_per_aksje": 0.8, "utbytte_yield": 5.32,
               "utbytte_12m": 2.0, "utbytte_12m_antall": 2,
               "utbytte_12m_liste": [{"ex_dato": "2026-03-02", "belop": 0.5},
                                     {"ex_dato": "2026-11-03", "belop": 1.5}],
               "utbytte_per_ar": {"2021": 0.0, "2022": 0.0, "2023": 0.0, "2024": 0.0, "2025": 0.8}}

    BEWI_MELDINGER = [
        {"publishedTime": "2026-11-16T07:00", "messageId": 686605,
         "title": "BEWI ASA - Updated key information related to dividend"},
        {"publishedTime": "2026-11-04T17:31", "messageId": 685546,
         "title": "BEWI ASA - Key information related to dividend"},
        {"publishedTime": "2026-11-04T17:30", "messageId": 685533,
         "title": "BEWI ASA - Proposed extraordinary dividend of NOK 1.15 per share"},
    ]
    _BEWI_NOKKEL = ("Dividend amount: NOK 1.15 per share\nDeclared currency: NOK\n"
                    "Last day including right: 1 December 2026\nEx-date: 2 December 2026\n"
                    "Record date: 3 December 2026\nPayment date: 10 December 2026\n"
                    "Date of approval: 1 December 2026\nThe dividend is subject to approval by "
                    "the extraordinary general meeting to be held on 1 December 2026.\n")
    BEWI_TEKSTER = {
        686605: _BEWI_NOKKEL,
        685546: _BEWI_NOKKEL,
        685533: ("The board of directors of BEWI ASA has resolved to propose an extraordinary cash "
                 "dividend of NOK 1.15 per share, based on the company's approved annual accounts for 2025."),
    }

    HUNT_MELDINGER = [
        {"publishedTime": "2026-09-02T07:00", "messageId": 681427,
         "title": "Hunter Group ASA - Key information relating to proposed cash dividend"},
        {"publishedTime": "2026-08-27T07:00", "messageId": 680928,
         "title": "Hunter Group ASA - NOK 1.50 dividend proposal"},
    ]
    HUNT_TEKSTER = {
        681427: ("Dividend amount: NOK 1.50 per share\nDeclared currency: NOK\n"
                 "Dividend classification: NOK 1.50 as extraordinary dividend\n"
                 "Ex-date: 29 September 2026\nRecord date: 30 September 2026\n"
                 "Date of approval: Expected on 28 September 2026\n"),
        680928: ("In line with its focus on shareholder returns, the board has proposed a dividend "
                 "of NOK 1.50 per share, subject to EGM approval"),
    }

    def _funn(self, ticker, meldinger, tekster, i_dag):
        gml = fs._newsweb_meldinger, fs._newsweb_tekst
        fs._newsweb_meldinger = lambda t: meldinger
        fs._newsweb_tekst = lambda mid: tekster.get(mid, "")
        try:
            return fs.ekstraordinaere_i_vindu(ticker, i_dag)
        finally:
            fs._newsweb_meldinger, fs._newsweb_tekst = gml

    # ── BOR ──────────────────────────────────────────────────────────────
    def test_bor_begge_engangsutbetalinger_faar_belop(self):
        funn = self._funn("BOR", self.BOR_MELDINGER, self.BOR_TEKSTER, datetime.date(2026, 11, 22))
        self.assertEqual(sorted((f["ex_dato"], f["ekstra"], f["total"]) for f in funn),
                         [("2026-03-02", 0.5, 0.5), ("2026-11-03", 1.5, 1.5)])

    def test_bor_bare_engangsutbytte_gir_null_med_merkelapp(self):
        funn = self._funn("BOR", self.BOR_MELDINGER, self.BOR_TEKSTER, datetime.date(2026, 11, 22))
        a = dict(self.BOR_RAD)
        ekstra = fs.ekstra_i_kroner(a, funn)
        self.assertEqual(ekstra, 2.0)
        self.assertTrue(fs.bare_engangsutbytte(a, funn, ekstra, datetime.date(2026, 11, 22)))
        fs.bruk_bare_engangsutbytte(a)
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"]), (0.0, 0.0))
        self.assertEqual(fs.arsrate_merke(a), "bare engangsutbytte siste 12 mnd")
        self.assertFalse(fs.yield_er_delaar(a))

    def test_bare_engangsutbytte_krever_at_alt_er_engangs(self):
        i_dag = datetime.date(2026, 11, 22)
        a = dict(self.BOR_RAD)
        en = [{"ex_dato": "2026-11-03", "ekstra": 1.5, "total": 1.5}]
        self.assertFalse(fs.bare_engangsutbytte(a, en, 1.5, i_dag))
        # Frontline-formen: engangsdelen ligger i en utbetaling med ordinært utbytte.
        delvis = [{"ex_dato": "2026-03-02", "ekstra": 0.5, "total": 0.5},
                  {"ex_dato": "2026-11-03", "ekstra": 1.0, "total": 1.5}]
        self.assertFalse(fs.bare_engangsutbytte(a, delvis, 1.5, i_dag))
        # Et ordinært utbytte er kunngjort og kommer: da er det en løpende rate.
        alt = [{"ex_dato": "2026-03-02", "ekstra": 0.5, "total": 0.5},
               {"ex_dato": "2026-11-03", "ekstra": 1.5, "total": 1.5}]
        self.assertTrue(fs.bare_engangsutbytte(a, alt, 2.0, i_dag))
        self.assertFalse(fs.bare_engangsutbytte(
            dict(a, annonsert_utbytte=0.8, annonsert_ex="2027-05-28"), alt, 2.0, i_dag))

    def test_bor_faq_og_payout(self):
        a = dict(self.BOR_RAD, navn="Borgestad ASA", sektor="Materialer", arsrate_kilde="kun_engangs",
                 utbytte_per_aksje=0.0, utbytte_yield=0.0, payout_ratio=40.0,
                 ar_med_utbytte=2, utbytteaar=[2025, 2026], historiske_utbytter=[])
        tekst = "".join(fs._lag_faq_seksjon(a, "2026-11-22"))
        self.assertIn("har ikke betalt ordinært utbytte de siste 12 månedene", tekst)
        self.assertNotIn("payout ratio", tekst.lower())

    def test_prosabelop_leses_bare_med_per_share_og_ikke_nektet(self):
        self.assertEqual(fs._ekstra_belop_i_prosa(
            "will distribute an extraordinary dividend of NOK 1.50 per share"), {("NOK", 1.5)})
        self.assertEqual(fs._ekstra_belop_i_prosa(
            "an extraordinary cash dividend of NOK 1.15 per share"), {("NOK", 1.15)})
        self.assertEqual(fs._ekstra_belop_i_prosa("a special dividend of USD 200 million"), set())
        self.assertEqual(fs._ekstra_belop_i_prosa(
            "The board will not propose an extraordinary dividend of NOK 2.00 per share"), set())
        self.assertEqual(fs._ekstra_belop_i_prosa("a dividend of NOK 2.00 per share"), set())

    def test_pressemelding_uten_annen_nokkelinfo_faar_ikke_belop(self):
        # Ingen «Key information» med samme beløp: funnet står uten beløp, som før.
        meldinger = [m for m in self.BOR_MELDINGER if m["messageId"] in (685169, 685408)]
        funn = self._funn("BOR", meldinger, self.BOR_TEKSTER, datetime.date(2026, 11, 22))
        self.assertEqual([(f["ex_dato"], f["ekstra"]) for f in funn], [(None, None)])

    # ── BEWI ─────────────────────────────────────────────────────────────
    def test_bewi_foreslaatt_ekstraordinaert_er_engangs(self):
        funn = self._funn("BEWI", self.BEWI_MELDINGER, self.BEWI_TEKSTER, datetime.date(2026, 11, 22))
        self.assertEqual([(f["ex_dato"], f["ekstra"], f["total"]) for f in funn],
                         [("2026-12-02", 1.15, 1.15)])

    def test_bewi_etter_ex_er_raten_null(self):
        i_dag = datetime.date(2026, 12, 3)
        a = {"ticker": "BEWI", "frekvens": "Uregelmessig", "pris": 18.02,
             "utbytte_per_aksje": 1.15, "utbytte_12m": 1.15, "utbytte_12m_antall": 1,
             "utbytte_12m_liste": [{"ex_dato": "2026-12-02", "belop": 1.15}],
             "utbytte_per_ar": {"2021": 0.42, "2022": 1.1, "2023": 0.0, "2024": 0.0, "2025": 0.0}}
        # Avviket er null, så bare porten for uregelmessige betalere slipper den til.
        self.assertFalse(fs.betalt_kan_bli_arsrate(a, i_dag))
        self.assertTrue(fs.betalt_kan_bli_arsrate(a, i_dag, min_avvik=0))
        funn = self._funn("BEWI", self.BEWI_MELDINGER, self.BEWI_TEKSTER, i_dag)
        ekstra = fs.ekstra_i_kroner(a, funn)
        self.assertTrue(fs.bare_engangsutbytte(a, funn, ekstra, i_dag))

    # ── HUNT ─────────────────────────────────────────────────────────────
    def test_hunt_flagg_og_frekvens_i_tickers(self):
        self.assertIn("HUNT", fs.EKSTRAORDINAERT_ER_ORDINAERT)
        self.assertEqual(fs.FREKVENS_OVERSTYRT.get("HUNT"), "Uregelmessig")

    def test_hunt_ekstraordinaert_er_ikke_engangs(self):
        funn = self._funn("HUNT", self.HUNT_MELDINGER, self.HUNT_TEKSTER, datetime.date(2026, 11, 22))
        self.assertEqual(funn, [])
        # Uten flagget er det et engangsutbytte, som før.
        andre = self._funn("XHUNT", self.HUNT_MELDINGER, self.HUNT_TEKSTER, datetime.date(2026, 11, 22))
        self.assertEqual([(f["ex_dato"], f["ekstra"]) for f in andre], [("2026-09-29", 1.5)])
        # «Special» står igjen også for flaggede selskaper.
        self.assertTrue(fs._har_ekstraordinaer(fs._uten_tillegg("a special dividend", "HUNT")))

    def test_hunt_betalt_blir_arsrate(self):
        a = {"ticker": "HUNT", "frekvens": "Uregelmessig", "pris": 16.26,
             "utbytte_per_aksje": 0.3, "utbytte_yield": 1.85,
             "utbytte_12m": 4.03, "utbytte_12m_antall": 5,
             "utbytte_12m_liste": [{"ex_dato": "2025-12-01", "belop": 0.3},
                                   {"ex_dato": "2026-03-02", "belop": 0.4},
                                   {"ex_dato": "2026-03-26", "belop": 0.58},
                                   {"ex_dato": "2026-06-30", "belop": 1.25},
                                   {"ex_dato": "2026-09-29", "belop": 1.5}],
             "utbytte_per_ar": {"2021": 26.5247, "2022": 26.5247, "2023": 40.8481,
                                "2024": 0.0, "2025": 0.3}}
        self.assertTrue(fs.betalt_kan_bli_arsrate(a, datetime.date(2026, 11, 22)))
        fs.bruk_betalt_som_arsrate(a)
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"]), (4.03, 24.78))
        self.assertEqual(fs.arsrate_merke(a), "siste 12 mnd")
        # Ingen boks om «ekstraordinært utbytte i yielden».
        self.assertFalse(fs.bor_hente_utbyttesplitt(a))

    # ── AKAST ────────────────────────────────────────────────────────────
    def test_akast_utenfor_rangering(self):
        self.assertEqual(fs.UTENFOR_RANGERING.get("AKAST", {}).get("grunn"), "salgsproveny")
        a = {"ticker": "AKAST", "utbytte_yield": 48.86}
        fs.sett_utenfor_rangering(a, fs.UTENFOR_RANGERING["AKAST"])
        self.assertEqual(a["utenfor_rangering"], "salgsproveny")
        self.assertFalse(fs.i_rangering(a))
        self.assertEqual(fs.rangering_merke(a), "utdeling fra salg")
        b = {"ticker": "AKSO", "utbytte_yield": 5.0}
        self.assertEqual([x["ticker"] for x in fs.sektor_topp([a, b])], ["AKSO"])
        self.assertEqual(fs.sektor_snitt_yield([a, b]), 5.0)
        # Feltet faller bort når det tas ut av tickers.json.
        fs.sett_utenfor_rangering(a, None)
        self.assertNotIn("utenfor_rangering", a)
        self.assertTrue(fs.i_rangering(a))

    # ── HSPG ─────────────────────────────────────────────────────────────
    def test_hspg_pause(self):
        h = fs.HENDELSE.get("HSPG")
        self.assertEqual((h["type"], h["melding"], h["dato"]), ("utbytte_pause", "685441", "2026-11-03"))
        a = {"ticker": "HSPG", "frekvens": "Årlig", "pris": 125.0,
             "utbytte_per_aksje": 5.0, "utbytte_yield": 4.0,
             "utbytte_12m_liste": [{"ex_dato": "2026-03-20", "belop": 5.0}],
             "utbetalinger": [["2026-03-20", 5.0]]}
        self.assertTrue(fs.bruk_utbytte_pause(a, h, datetime.date(2026, 11, 22)))
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"]), (0.0, 0.0))
        self.assertEqual(fs.arsrate_merke(a), "utdelinger på pause")
        fs.sett_hendelse(a, h, datetime.date(2026, 11, 22))
        self.assertFalse(fs.i_rangering(a))


class TestBwlpgProsabelop(unittest.TestCase):
    """BW LPG skriver beløpet i løpende tekst, ikke som «Dividend amount:» (24.11.2026).

    Aksjesiden hadde riktig ex-dato og betalingsdato, men ingen kunngjort sum, så
    beløpet manglet i tittel, ingress og utbyttekalender. Meldingstekstene er de
    relevante avsnittene fra 687253 (tredje kvartal) og 681100 (andre kvartal),
    uten kontaktpersonen.
    """

    I_DAG = datetime.date(2026, 11, 24)
    Q3 = (
        "Singapore, 24 November 2026\n\n"
        "BW LPG Limited (\"BW LPG\" or the \"Company\", OSE ticker code: \"BWLPG.OL\", NYSE\n"
        "ticker code \"BWLP\") provides the following key information relating to the\n"
        "Company's cash dividend for Q3 2026:\n\n"
        "The Board has approved a dividend of US$1.30 per share on 23 November 2026.\n"
        "For shares registered with Euronext VPS, dividend per share is NOK12.7189.\n\n"
        "Record date: 4 December 2026\n\n"
        "Shares registered with Euronext VPS - Oslo Stock Exchange\n"
        "=============================================================\n"
        "Last trading day including the right to receive this dividend: 2 December 2026\n"
        "Ex-date: 3 December 2026\n"
        "Dividend payment date: On or about 14 December 2026\n\n"
        "Shares registered with Depository Trust Company -- New York Stock Exchange\n"
        "=============================================================\n"
        "Last trading day including the right to receive this dividend: 3 December 2026\n"
        "Ex-date: 4 December 2026\n"
        "Dividend payment date: On or about 14 December 2026\n")
    # Andre kvartal: setningene brytes midt i, og «NOK8.8914» står uten mellomrom.
    Q2 = (
        "Singapore, 28 August 2026\n\n"
        "The Board has approved a dividend of US$0.95 per share on 27 August 2026. For\n"
        "shares registered with Euronext VPS, dividend per share is NOK8.8914.\n\n"
        "Record date: 8 September 2026\n\n"
        "Shares registered with Euronext VPS - Oslo Stock Exchange\n"
        "=============================================================\n"
        "Last trading day including the right to receive this dividend: 4 September\n"
        "2026\n"
        "Ex-date: 7 September 2026\n"
        "Dividend payment date: On or about 16 September 2026\n\n"
        "Shares registered with Depository Trust Company -- New York Stock Exchange\n"
        "=============================================================\n"
        "Ex-date: 8 September 2026\n"
        "Dividend payment date: On or about 16 September 2026\n")

    # Raden slik BWLPG så ut 24.11.2026, med tallene fra aksjer.json.
    BWLPG = {
        "ticker": "BWLPG", "navn": "BW LPG Limited", "bors": "Oslo Børs", "sektor": "Shipping",
        "pris": 218.8, "frekvens": "Kvartalsvis", "valuta": "NOK",
        "ex_dato": "2026-12-03", "betaling_dato": "2026-12-14",
        "utbytte_per_aksje": 24.99, "utbytte_yield": 11.42, "arsrate_kilde": "betalt_12m",
        "utbytte_12m": 24.992, "utbytte_12m_antall": 4,
        "utbytte_12m_liste": [{"ex_dato": "2025-12-11", "belop": 3.927},
                              {"ex_dato": "2026-03-12", "belop": 5.596},
                              {"ex_dato": "2026-06-11", "belop": 6.5777},
                              {"ex_dato": "2026-09-07", "belop": 8.8914}],
        "utbetalinger": [["2025-12-11", 3.927], ["2026-03-12", 5.596],
                         ["2026-06-11", 6.5777], ["2026-09-07", 8.8914]],
    }
    ANNONSERT = {"annonsert_utbytte": 12.7189, "annonsert_ex": "2026-12-03",
                 "annonsert_utland": {"belop": 1.3, "valuta": "USD", "ex": "2026-12-03"}}

    def test_tredje_kvartal_gir_kroner_og_dollar(self):
        u = fs._parse_utbetalinger(self.Q3)
        self.assertEqual(len(u), 1)
        self.assertEqual((u[0]["ex_dato"], u[0]["betaling_dato"]), ("2026-12-03", "2026-12-14"))
        self.assertEqual((u[0]["belop"], u[0]["valuta"]), (12.7189, "NOK"))
        self.assertEqual((u[0]["belop_utland"], u[0]["valuta_utland"]), (1.3, "USD"))
        self.assertFalse(u[0]["forbehold"])

    def test_andre_kvartal_med_linjeskift_og_nok_uten_mellomrom(self):
        u = fs._parse_utbetalinger(self.Q2)
        self.assertEqual(len(u), 1)
        self.assertEqual(u[0]["ex_dato"], "2026-09-07")
        self.assertEqual((u[0]["belop"], u[0]["valuta"]), (8.8914, "NOK"))
        self.assertEqual((u[0]["belop_utland"], u[0]["valuta_utland"]), (0.95, "USD"))

    def test_neste_utbetaling_gir_begge_belop_til_ex_datoen_som_vises(self):
        n = fs.neste_utbetaling(self.Q3, self.I_DAG)
        self.assertEqual(n["ex_dato"], "2026-12-03")
        self.assertEqual((n["belop"], n["valuta"]), (12.7189, "NOK"))
        self.assertEqual((n["belop_utland"], n["valuta_utland"]), (1.3, "USD"))
        self.assertIsNone(n["ex_forbehold"])

    def test_nok_uten_mellomrom_dollartegn_og_tegnsetting(self):
        f = fs._prosa_belop
        self.assertEqual(f("The Board has approved a dividend of US$1.30 per share on 23 November."),
                         {"belop": 1.3, "valuta": "USD", "belop_utland": None, "valuta_utland": None})
        self.assertEqual(f("dividend per share is NOK12.7189.")["belop"], 12.7189)
        self.assertEqual(f("dividend per share is NOK 12.7189")["belop"], 12.7189)
        self.assertEqual(f("The Board has declared a cash dividend of $0.24 per share,")["valuta"], "USD")
        # Kommaet etter tallet er tegnsetting, ikke en del av det («USD 0.24,»).
        self.assertEqual(f("dividend per share is USD 0.24, payable in December")["belop"], 0.24)

    def test_tall_trunkeres_aldri(self):
        # «1,300.50» må ikke bli 1,30 eller 1,3.
        self.assertIsNone(fs._prosa_belop("dividend per share is NOK 1,300.50"))
        self.assertIsNone(fs._prosa_belop("approved a dividend of NOK 1,300.50 per share"))

    def test_storrelsessuffiks_er_totalen_ikke_per_aksje(self):
        f = fs._prosa_belop
        self.assertIsNone(f("dividend per share is USD 100m"))
        self.assertIsNone(f("dividend per share is USD 100 million"))
        self.assertIsNone(f("dividend per share is NOK 2.4 billion"))
        self.assertIsNone(f("The Board has approved a dividend of USD 100m per share"))
        self.assertIsNone(f("The Board has approved a dividend of NOK 2.4 billion in total"))

    def test_to_ulike_belop_i_samme_valuta_er_tvetydig(self):
        f = fs._prosa_belop
        self.assertIsNone(f("approved a dividend of NOK 1.00 per share. Dividend per share is NOK 2.00."))
        self.assertIsNone(f("approved a dividend of US$0.50 per share and declared a dividend of US$0.60 per share"))
        # Samme beløp to ganger er ikke tvetydig.
        self.assertEqual(f("approved a dividend of NOK 1.00 per share. Dividend per share is NOK1.00.")["belop"], 1.0)

    def test_engangsutbytte_i_meldingen_gir_ingen_prosabelop(self):
        # Frontlines melding om et special one-time dividend nevner det forrige utbyttet
        # («previously declared dividend of $2.61 per share», 682180). Beløpet hører ikke
        # til ex-datoen som står i en slik melding.
        tekst = ("The Board has declared a special one-time dividend of $0.80 per share, in addition "
                 "to the previously declared dividend of $2.61 per share for the second quarter.\n"
                 "Ex-date: 24 September 2026\nPayment date: 8 October 2026\n")
        self.assertIsNone(fs._prosa_belop(tekst))
        u = fs._parse_utbetalinger(tekst)
        self.assertEqual(u[0]["ex_dato"], "2026-09-24")
        self.assertIsNone(u[0]["belop"])

    def test_nektende_form_teller_ikke(self):
        self.assertIsNone(fs._prosa_belop("The Board has not approved a dividend of NOK 5.00 per share."))

    def test_ekstraordinaert_ord_foran_beloepet_er_ikke_ordinaert(self):
        f = fs._prosa_belop
        self.assertIsNone(f("The Board has approved an extraordinary dividend of NOK 5.00 per share."))
        self.assertIsNone(f("The Board has approved an additional dividend of NOK 0.50 per share."))
        self.assertIsNone(f("The Board has approved a total dividend of USD 0.61 per share."))
        self.assertIsNone(f("The Board proposes a dividend of NOK 2.15 per share."))

    def test_melding_uten_belop_gir_fortsatt_none(self):
        tekst = ("Key information relating to the cash dividend:\n"
                 "Record date: 4 December 2026\nEx-date: 3 December 2026\n"
                 "Dividend payment date: On or about 14 December 2026\n")
        u = fs._parse_utbetalinger(tekst)
        self.assertEqual(u[0]["ex_dato"], "2026-12-03")
        self.assertIsNone(u[0]["belop"])
        self.assertIsNone(u[0]["valuta"])
        self.assertIsNone(u[0]["belop_utland"])
        self.assertIsNone(fs._prosa_belop(tekst))

    def test_flere_utbetalinger_i_en_melding_faar_ikke_prosabelop(self):
        # To ex-datoer, og et beløp i teksten som ikke kan knyttes til noen av dem.
        tekst = ("Tranche 1:\nEx-date: 29 June 2026.\n"
                 "Tranche 2:\nEx-date: 29 September 2026.\n"
                 "The Board has approved a dividend of NOK 1.00 per share.\n")
        u = fs._parse_utbetalinger(tekst)
        self.assertEqual([x["ex_dato"] for x in u], ["2026-06-29", "2026-09-29"])
        self.assertEqual([x["belop"] for x in u], [None, None])

    def test_linjen_dividend_amount_gaar_foran_teksten(self):
        tekst = ("The Board has approved a dividend of US$0.40 per share. For shares registered with "
                 "Euronext VPS, dividend per share is NOK 4.00.\n"
                 "Dividend amount: USD 0.40 per share\nEx-date: 20 November 2026\n")
        u = fs._parse_utbetalinger(tekst)
        self.assertEqual((u[0]["belop"], u[0]["valuta"]), (0.4, "USD"))
        self.assertIsNone(u[0]["belop_utland"])

    def test_forslag_gir_forbehold_som_for(self):
        tekst = ("The Board has approved a dividend of NOK 5.00 per share, subject to approval by the "
                 "general meeting.\nDate of approval: 12 May 2026\nEx-date: 15 May 2026\n"
                 "Payment date: 27 May 2026\n")
        n = fs.neste_utbetaling(tekst, datetime.date(2026, 4, 30))
        self.assertEqual((n["belop"], n["valuta"]), (5.0, "NOK"))
        self.assertEqual(n["ex_forbehold"], "2026-05-12")
        # Etter generalforsamlingen er det vedtatt.
        self.assertIsNone(fs.neste_utbetaling(tekst, datetime.date(2026, 5, 14))["ex_forbehold"])

    def test_bruk_newsweb_belop_setter_kroner_og_dollar(self):
        a = {}
        nw = fs.neste_utbetaling(self.Q3, self.I_DAG)
        self.assertFalse(fs.bruk_newsweb_belop(a, nw))
        self.assertEqual(a["annonsert_utbytte"], 12.7189)
        self.assertEqual(a["annonsert_ex"], "2026-12-03")
        self.assertEqual(a["annonsert_utland"], {"belop": 1.3, "valuta": "USD", "ex": "2026-12-03"})

    def test_bruk_newsweb_belop_lar_ingen_gammel_utland_henge(self):
        a = {"annonsert_utland": {"belop": 0.95, "valuta": "USD", "ex": "2026-09-07"}}
        fs.bruk_newsweb_belop(a, {"ex_dato": "2026-12-03", "belop": 5.0, "valuta": "NOK"})
        self.assertNotIn("annonsert_utland", a)

    def test_regel_5_staar_ikke_ned_for_et_dollarerklart_utbytte(self):
        # Uten dette sto «betalt siste 12 mnd» ned så snart kronebeløpet var lest, og
        # årsraten falt tilbake til Yahoos anslag (12,00 kr, 5,48 %) i stedet for 24,99.
        a = dict(self.BWLPG, utbytte_per_aksje=12.0, utbytte_yield=5.48, **self.ANNONSERT)
        self.assertTrue(fs.betalt_kan_bli_arsrate(fs.med_runde(a), self.I_DAG))

    def test_regel_5_staar_fortsatt_ned_for_et_kroneutbytte(self):
        # Uendret: et kunngjort NOK-utbytte uten dollarbeløp er ferskere enn vinduet.
        a = dict(self.BWLPG, utbytte_per_aksje=12.0, utbytte_yield=5.48,
                 annonsert_utbytte=12.7189, annonsert_ex="2026-12-03")
        self.assertFalse(fs.betalt_kan_bli_arsrate(fs.med_runde(a), self.I_DAG))
        # Et dollarbeløp for en annen ex-dato endrer ikke det.
        a["annonsert_utland"] = {"belop": 0.95, "valuta": "USD", "ex": "2026-09-07"}
        self.assertFalse(fs.betalt_kan_bli_arsrate(fs.med_runde(a), self.I_DAG))

    def test_arsraten_er_uendret_gjennom_steget(self):
        # Raden slik NewsWeb-steget i main() lar den, med Yahoos anslag som rate.
        a = dict(self.BWLPG, utbytte_per_aksje=12.0, utbytte_yield=5.48)
        a.pop("arsrate_kilde")
        fs.bruk_newsweb_belop(a, fs.neste_utbetaling(self.Q3, self.I_DAG))
        self.assertTrue(fs.betalt_kan_bli_arsrate(fs.med_runde(a), self.I_DAG))
        fs.bruk_betalt_som_arsrate(a, 0.0)
        self.assertEqual((a["utbytte_per_aksje"], a["utbytte_yield"], a["arsrate_kilde"]),
                         (24.99, 11.42, "betalt_12m"))

    def test_dnb_med_dollarbelop_merket_som_kroner_rettes_av_betalt_siste_12_mnd(self):
        # Hvis DNB senere lister BW LPG med «1.30» uten valuta, tar DNB-steget det som kroner og
        # ganger med fire. Meldingens kronebeløp erstatter beløpet, og regel 5 holder ikke
        # den feil utledede raten fast.
        a = dict(self.BWLPG, utbytte_per_aksje=5.2, utbytte_yield=2.38,
                 annonsert_utbytte=1.3, annonsert_ex="2026-12-03")
        a.pop("arsrate_kilde")
        self.assertFalse(fs.bruk_newsweb_belop(a, fs.neste_utbetaling(self.Q3, self.I_DAG)))
        self.assertEqual(a["annonsert_utbytte"], 12.7189)
        self.assertTrue(fs.betalt_kan_bli_arsrate(fs.med_runde(a), self.I_DAG))

    def test_tittel_ingress_og_kalender_viser_belopet(self):
        a = dict(self.BWLPG, **self.ANNONSERT)
        t = fs.utbytte_i_tittel(a, "2026-11-24")
        self.assertEqual((t["belop"], t["valuta"], t["ex"], t["art"]), (12.7189, "NOK", "2026-12-03", "neste"))
        tittel = fs.lag_aksje_tittel(a, "2026-11-24")
        self.assertIn("12,72\u00a0kr per aksje", tittel)
        self.assertIn("ex-dato 3. des", tittel)
        self.assertLessEqual(len(tittel), fs.TITTEL_TAK)
        ingress = fs.lag_aksje_ingress(a, "2026-11-24")
        self.assertIn("betaler 12,72\u00a0kr per aksje med ex-dato", ingress)
        rader = [r for r in fs.kalender_rader([a], self.I_DAG) if r["ex"] == datetime.date(2026, 12, 3)]
        self.assertEqual(len(rader), 1)
        self.assertEqual((rader[0]["belop"], rader[0]["valuta"]), (12.7189, "NOK"))

    def test_uten_belop_er_tittelen_som_for(self):
        a = dict(self.BWLPG)
        self.assertIsNone(fs.utbytte_i_tittel(a, "2026-11-24"))
        self.assertNotIn("per aksje", fs.lag_aksje_tittel(a, "2026-11-24"))


class TestInterOveralt(unittest.TestCase):
    """Inter på alle sider (designrunden 22.11.2026).

    44 sider satte `body { font-family: system-ui … }` eller `-apple-system`
    i sin egen <style> og viste systemfonten: alle artiklene, /aksjer/,
    sektorsidene, topplistene, rapportkalenderen og ni håndskrevne sider. En
    leser som gikk fra en aksjeside til en artikkel, byttet font.
    """

    _BODY = r"body\s*\{\{?[^}]*?font-family:\s*([^;}]+)"

    def _forste(self, stabel):
        return stabel.strip().split(",")[0].strip().strip("'\"")

    def test_haandskrevne_sider(self):
        import re as _re
        sett = 0
        generert = {os.path.join("rapportkalender", "index.html")}
        for mappe, under, filer in os.walk(_REPO):
            under[:] = [d for d in under if d not in (".git", ".claude", "node_modules", "test-results", "promo", "aksjer")]
            for navn in filer:
                if not navn.endswith(".html"):
                    continue
                sti = os.path.join(mappe, navn)
                rel = os.path.relpath(sti, _REPO)
                if rel in generert:
                    continue
                for stabel in _re.findall(self._BODY, open(sti, encoding="utf-8").read()):
                    sett += 1
                    self.assertEqual(self._forste(stabel), "Inter", f"{rel}: body bruker {stabel.strip()}")
        self.assertGreater(sett, 15)

    def test_malene(self):
        import re as _re
        kilde = open(os.path.join(_REPO, "scripts", "fetch_stocks.py"), encoding="utf-8").read()
        stabler = _re.findall(self._BODY, kilde)
        self.assertGreaterEqual(len(stabler), 5)
        for stabel in stabler:
            self.assertEqual(self._forste(stabel), "Inter", f"mal: body bruker {stabel.strip()}")

    def test_stilarket_har_fonten(self):
        """Oversikten og topplistene laster bare style.css, så @font-face må stå der."""
        css = open(os.path.join(_REPO, "assets", "style.css"), encoding="utf-8").read()
        self.assertIn('font-family: "Inter"', css)
        self.assertIn("fonts/inter-latin-wght-normal.woff2", css)
        self.assertTrue(os.path.exists(os.path.join(_REPO, "assets", "fonts", "inter-latin-wght-normal.woff2")))

    def test_aldri_google_fonts(self):
        """Nettstedet og malene. tallkontroll_side.py lager en privat
        Artifact-side på claude.ai, ikke en side på exday.no."""
        stier = [os.path.join(_REPO, "scripts", "fetch_stocks.py")]
        for mappe, under, filer in os.walk(_REPO):
            under[:] = [d for d in under if d not in (".git", ".claude", ".github", "node_modules",
                                                      "test-results", "scripts", "tests", "promo")]
            stier += [os.path.join(mappe, n) for n in filer if n.endswith((".html", ".css", ".js"))]
        for sti in stier:
            tekst = open(sti, encoding="utf-8", errors="ignore").read()
            self.assertNotIn("fonts.googleapis.com", tekst, sti)


class TestDagsendring(unittest.TestCase):
    """Dagens endring i kurshodet på aksjesiden (designrunden 22.11.2026).

    Samme regel som slaaSammenKurs() i app.js: endringen vises bare når den
    kan regnes for kursen siden viser, og datoen står alltid ved siden av.
    """

    FRE = datetime.date(2026, 11, 20)

    def test_samme_dag_samme_kurs(self):
        p = {"pris": 383.3, "forrige_kurs": 389.2, "endring_krs": -5.9, "endring_pct": -1.5159,
             "dato": "2026-11-20", "forrige_dato": "2026-11-19"}
        e = fs.dagsendring(383.3, self.FRE, p)
        self.assertAlmostEqual(e["krs"], -5.9)
        self.assertAlmostEqual(e["pct"], -1.5159)

    def test_samme_dag_annen_kurs_regnes_mot_forrige(self):
        p = {"pris": 380.0, "forrige_kurs": 389.2, "endring_krs": -9.2, "endring_pct": -2.36, "dato": "2026-11-20"}
        e = fs.dagsendring(383.3, self.FRE, p)
        self.assertAlmostEqual(e["krs"], -5.9)

    def test_priser_fra_dagen_foer(self):
        p = {"pris": 389.2, "dato": "2026-11-19"}
        e = fs.dagsendring(383.3, self.FRE, p)
        self.assertAlmostEqual(e["krs"], -5.9)
        mandag = datetime.date(2026, 11, 23)
        e = fs.dagsendring(390.0, mandag, {"pris": 383.3, "dato": "2026-11-20"})
        self.assertAlmostEqual(e["krs"], 6.7)

    def test_ukjent_gir_ingenting(self):
        self.assertIsNone(fs.dagsendring(383.3, self.FRE, None))
        self.assertIsNone(fs.dagsendring(383.3, None, {"pris": 1, "dato": "2026-11-20"}))
        self.assertIsNone(fs.dagsendring(383.3, self.FRE, {"pris": 380, "dato": "2026-11-17"}))
        self.assertIsNone(fs.dagsendring(0, self.FRE, {"pris": 380, "dato": "2026-11-20", "endring_krs": 1, "endring_pct": 1}))

    def test_format(self):
        ned = fs._endring_html({"krs": -5.9, "pct": -1.5159})
        self.assertIn("\u22125,90 (\u22121,52\u00a0%)", ned)
        self.assertIn("kh-ned", ned)
        opp = fs._endring_html({"krs": 2.0, "pct": 0.5})
        self.assertIn("+2,00 (+0,50\u00a0%)", opp)
        self.assertIn("kh-opp", opp)
        self.assertIn("kh-flat", fs._endring_html({"krs": 0.0, "pct": 0.0}))

    def test_kurshodet_viser_endring_og_dato(self):
        a = {"ticker": "EQNR", "pris": 383.3, "hentet": "2026-11-20T16:45:00Z", "utbytte_yield": 3.98,
             "utbytte_per_aksje": 15.25}
        p = {"EQNR": {"pris": 383.3, "forrige_kurs": 389.2, "endring_krs": -5.9, "endring_pct": -1.5159,
                      "dato": "2026-11-20"}}
        h = fs._lag_kurshode(a, "NOK", priser=p)
        self.assertIn("kh-endring", h)
        self.assertIn("Kurs 20. nov", h)
        self.assertNotIn("kh-endring", fs._lag_kurshode(a, "NOK", priser={}))


class TestTrykkflater(unittest.TestCase):
    """Trykkflater på minst 44 px og 16 px skrift i felt (designrunden 22.11.2026)."""

    def setUp(self):
        self.css = open(os.path.join(_REPO, "assets", "style.css"), encoding="utf-8").read()

    def test_menyknappene(self):
        self.assertIn(".site-dark-btn { min-width: 44px; min-height: 44px; }", self.css)
        self.assertIn(".site-nav-burger { width: 44px; height: 44px;", self.css)

    def test_kalenderen_zoomer_ikke(self):
        self.assertIn(".kal-felt { font-size: 1rem; min-height: 44px; }", self.css)

    def test_periodeknappene_paa_aksjesiden(self):
        import re as _re
        kilde = open(os.path.join(_REPO, "scripts", "fetch_stocks.py"), encoding="utf-8").read()
        regel = _re.search(r"\.kp-btn \{\{([^}]*)\}\}", kilde).group(1)
        self.assertIn("min-height: 44px", regel)
        self.assertIn("min-width: 44px", regel)


class TestEnGrafstil(unittest.TestCase):
    """Runde akser og samme periodeknapper på aksjesiden og i appen.

    Kursgrafen på aksjesiden viste 226 / 340 / 454 og søylene 11,88 / 23,76 /
    35,64, mens appen viste 200 / 300 / 400 / 500. Knappene het «1 år, YTD …»
    på siden og «YTD, 1å …» i appen (designrunden 22.11.2026, forslag 4).
    """

    def _pen(self, akse):
        import math as _m
        steg = akse["steg"]
        tier = 10 ** _m.floor(_m.log10(steg) + 1e-9)
        self.assertTrue(any(abs(steg - f * tier) < 1e-9 * tier for f in (1, 2, 2.5, 5)), steg)
        for v in akse["verdier"]:
            self.assertAlmostEqual(v / steg, round(v / steg), places=6)

    def test_pent_akse(self):
        a = fs.pent_akse(226.4, 454.6)
        self.assertEqual(a["verdier"], [200, 300, 400, 500])
        for lo, hi in [(226.4, 454.6), (0, 35.64), (0.12, 0.98), (48.0, 85.5), (0, 3.81), (5, 5)]:
            a = fs.pent_akse(lo, hi)
            self._pen(a)
            self.assertLessEqual(a["fra"], lo)
            self.assertGreaterEqual(a["til"], hi)

    def test_utbyttesoylene(self):
        hist = [{"ar": 2022, "utbytte": 11.88, "yield": 3.1}, {"ar": 2023, "utbytte": 35.64, "yield": 9.3},
                {"ar": 2024, "utbytte": 23.76, "yield": 6.2}]
        svg = fs._generer_hist_chart(hist)
        import re as _re
        etiketter = _re.findall(r'text-anchor="end" font-size="10" fill="#9ca3af">([^<]+)</text>', svg)
        self.assertEqual(etiketter, ["0", "10", "20", "30", "40"])
        # Koordinatene har punktum, aldri komma.
        self.assertNotRegex(svg, r'(?:x|y|y1|y2|height)="[0-9]+,[0-9]')

    def test_samme_pentakse_i_malen_og_appen(self):
        import re as _re
        ui = open(os.path.join(_REPO, "assets", "ui.js"), encoding="utf-8").read()
        kilde = open(os.path.join(_REPO, "scripts", "fetch_stocks.py"), encoding="utf-8").read()
        app = _re.search(r"^function pentAkse\(.*?^\}", ui, _re.S | _re.M).group(0)
        mal = _re.search(r"^    function pentAkse\(.*?^    \}\}$", kilde, _re.S | _re.M).group(0)
        norm = lambda t: [l.strip() for l in t.replace("{{", "{").replace("}}", "}").split("\n") if l.strip()]
        self.assertEqual(norm(mal), norm(app))
        self.assertIn("akse.verdier.forEach", kilde)
        self.assertNotIn("[mn,(mn+mx)/2,mx]", kilde)

    def test_like_periodeknapper(self):
        import re as _re
        ui = open(os.path.join(_REPO, "assets", "ui.js"), encoding="utf-8").read()
        kilde = open(os.path.join(_REPO, "scripts", "fetch_stocks.py"), encoding="utf-8").read()
        mal = _re.findall(r'class="kp-btn[^"]*" data-p="(\w+)">([^<]+)</button>', kilde)
        app = _re.findall(r"\['([^']+)','(\w+)'\]", _re.search(r"const perioder = \[(.*?)\];", ui).group(1))
        self.assertEqual([(p, l) for p, l in mal], [(p, l) for l, p in app])
        self.assertEqual([l for _, l in mal], ["1 år", "YTD", "2 år", "3 år", "5 år"])


class TestSidetopp(unittest.TestCase):
    """Én sidetopp (designrunde 2, 23.11.2026).

    Overskriften var 400, 700 eller 800 i vekt og 22 til 30 px, bakgrunnen
    var hvit, gray-50 eller slate-50, brødsmulen skilte med «›» eller «/» og
    la samme sektor under «Utforsk» på aksjesiden og under «Aksjer › Sektorer»
    på sektorsiden, og tallrutene hadde etiketten under tallet og en enslig
    tredje rute ved to kolonner. JSON-LD sa «Hjem › Utforsk › EQNR» mens
    siden viste en annen sti.

    Malene leses ved å lage sidene i en midlertidig mappe. De håndskrevne
    sidene leses fra repoet, uten de genererte blokkene (utbyttekalenderens
    tabell) og uten de genererte filene, som boten lager på nytt etter flett.
    """

    AKSJER = [
        {"ticker": "AAA", "navn": "Alfa ASA", "sektor": "Finans", "bors": "Oslo Børs", "pris": 100.0,
         "utbytte_yield": 5.5, "utbytte_per_aksje": 5.5, "frekvens": "Årlig", "ar_med_utbytte": 6,
         "rapport_dato": "2026-12-15", "ex_dato": "2027-04-01", "kurs_historikk": []},
        {"ticker": "BBB", "navn": "Beta ASA", "sektor": "Finans", "bors": "Oslo Børs", "pris": 50.0,
         "utbytte_yield": 7.0, "utbytte_per_aksje": 3.5, "frekvens": "Kvartalsvis", "ar_med_utbytte": 9,
         "rapport_dato": "2027-02-03", "kurs_historikk": []},
        {"ticker": "CCC", "navn": "Gamma ASA", "sektor": "Shipping", "bors": "Oslo Børs", "pris": 20.0,
         "utbytte_yield": 9.0, "utbytte_per_aksje": 1.8, "frekvens": "Halvårlig", "ar_med_utbytte": 4,
         "rapport_dato": "2027-02-10", "kurs_historikk": []},
    ]
    I_DAG = datetime.date(2026, 11, 23)

    # Håndskrevne sider som er bygd som app-flater med en liten tittelrad, og
    # sider uten egen overskrift. De hører ikke til malen for sidetopp.
    UNNTATT = {"app", "bevegelser", "uke", "innstillinger", "kalkulator", "sektor", "promo", "aksjer",
               "rapportkalender", "node_modules", "test-results", ".claude", ".git"}

    # Sider som skal ha brødsmule, og stien de skal ha. Resten av stien til
    # artiklene leses fra siden selv; her låses bare begynnelsen.
    MED_BRODSMULE = {
        "faq/index.html": ["FAQ"],
        "om/index.html": ["Om"],
        "metode/index.html": ["Metode og datakilder"],
        "personvern/index.html": ["Personvern"],
        "vilkaar/index.html": ["Vilkår for bruk"],
        "utforsk/index.html": ["Utforsk"],
        "avnoteringer/index.html": ["Aksjer", "Avnoterte aksjer"],
        "utbyttekalkulator/index.html": ["Utbyttekalkulator"],
        "artikler/index.html": ["Artikler"],
        "verktoy/index.html": ["Verktøy"],
        "verktoy/kalkulator/index.html": ["Verktøy", "Kalkulator"],
        "verktoy/huslan-vs-investering/index.html": ["Verktøy", "Huslån vs. Investering"],
        "verktoy/fire-kalkulator/index.html": ["Verktøy", "FIRE-kalkulator"],
        "verktoy/sektorrebalansering/index.html": ["Verktøy", "Sektorrebalansering"],
    }

    # ── lesing ────────────────────────────────────────────────────────────

    @staticmethod
    def _brodsmule_synlig(side):
        m = re.search(r'<nav class="brodsmule"[^>]*>(.*?)</nav>', side, re.S)
        if not m:
            return None
        deler = re.sub(r'<span class="brodsmule-skille"[^>]*>(.*?)</span>', r'|\1|', m.group(1))
        navn = [html.unescape(re.sub(r"<[^>]+>", "", t)).strip() for t in re.split(r"\|[^|]*\|", deler)]
        skilletegn = set(re.findall(r'<span class="brodsmule-skille"[^>]*>(.*?)</span>', m.group(1)))
        lenker = re.findall(r'<a href="([^"]*)">', m.group(1))
        return {"navn": navn, "skille": skilletegn, "lenker": lenker, "html": m.group(1)}

    @staticmethod
    def _brodsmule_ld(side):
        """BreadcrumbList som egen blokk, i @graph eller som `breadcrumb` i en WebPage."""
        funn = []

        def let(x):
            if isinstance(x, dict):
                if x.get("@type") == "BreadcrumbList":
                    funn.append([i["name"] for i in x["itemListElement"]])
                for v in x.values():
                    let(v)
            elif isinstance(x, list):
                for v in x:
                    let(v)
        for blokk in re.findall(r'<script type="application/ld\+json">(.*?)</script>', side, re.S):
            let(json.loads(blokk))
        return funn

    def _lag_malene(self):
        """{navn: html} for hver mal, laget av små, ekte data."""
        rot = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, rot, ignore_errors=True)
        sider = {}
        a = dict(self.AKSJER[0])
        sider["aksje"] = fs._aksje_side_html(a, str(self.I_DAG))
        fs.generer_aksjesider(self.AKSJER, rot)
        fs.generer_sektorsider(self.AKSJER, rot)
        fs.generer_topplistesider(self.AKSJER, rot)
        fs.generer_rapportkalender(self.AKSJER, rot, i_dag=self.I_DAG)
        rapport = {"periode": "2026-Q3", "dato": "2026-10-21", "melding": "1", "tittel": "Q3",
                   "resultat": "Resultatet var 1,0 milliard kroner.", "nokkeltall": [],
                   "utbytte": "Ingen endring.", "plan": "", "ellers": [], "skrevet": "2026-11-21"}
        sider["rapportside"] = fs._rapportside_html(a, [rapport], str(self.I_DAG))
        for sti, navn in [(("aksjer", "index.html"), "oversikt"),
                          (("aksjer", "sektor", "index.html"), "sektorindeks"),
                          (("aksjer", "sektor", "finans", "index.html"), "sektor"),
                          (("aksjer", "hoyest-utbytte", "index.html"), "toppliste"),
                          (("rapportkalender", "index.html"), "rapportkalender")]:
            with open(os.path.join(rot, *sti), encoding="utf-8") as f:
                sider[navn] = f.read()
        kropp = fs.lag_kalender_kropp(fs.kalender_rader(self.AKSJER, self.I_DAG), self.I_DAG)
        hode = fs.lag_kalender_hode(fs.kalender_rader(self.AKSJER, self.I_DAG), self.I_DAG)
        sider["utbyttekalender"] = hode + "\n" + kropp
        return sider

    def _haandskrevne(self):
        """{relativ sti: html uten genererte blokker}."""
        ut = {}
        for mappe, under, filer in os.walk(_REPO):
            under[:] = [d for d in under if d not in self.UNNTATT]
            for navn in filer:
                if navn != "index.html" and navn != "404.html" or mappe == _REPO and navn != "index.html":
                    continue
                sti = os.path.join(mappe, navn)
                rel = os.path.relpath(sti, _REPO)
                tekst = open(sti, encoding="utf-8").read()
                tekst = re.sub(r"<!--KAL:START-->.*?<!--KAL:SLUTT-->", "", tekst, flags=re.S)
                tekst = re.sub(r"<!--KAL-HODE:START-->.*?<!--KAL-HODE:SLUTT-->", "", tekst, flags=re.S)
                ut[rel] = tekst
        return ut

    # ── brødsmulen ────────────────────────────────────────────────────────

    def test_brodsmule_og_ld_bygges_av_samme_sti(self):
        sti = fs.sti_aksje("Energi", "EQNR") + [("Rapporter", "/aksjer/EQNR/rapporter/")]
        nav, ld = fs.brodsmule(sti)
        syn = self._brodsmule_synlig(nav)
        navn_ld = [i["name"] for i in ld["itemListElement"]]
        self.assertEqual(syn["navn"], navn_ld)
        self.assertEqual(navn_ld, ["exday.no", "Aksjer", "Sektorer", "Energi", "EQNR", "Rapporter"])
        self.assertEqual(syn["skille"], {fs.BRODSMULE_SKILLETEGN})
        self.assertEqual(fs.BRODSMULE_SKILLETEGN, "›")
        self.assertEqual([i["position"] for i in ld["itemListElement"]], [1, 2, 3, 4, 5, 6])
        # siste ledd er siden selv: ingen lenke, men aria-current
        self.assertEqual(len(syn["lenker"]), 5)
        self.assertIn('<span aria-current="page">Rapporter</span>', nav)
        self.assertTrue(all(h.startswith("/") for h in syn["lenker"]))

    def test_stien_til_en_side_er_stien_over_pluss_ett_ledd(self):
        sektor = [n for n, _ in fs.sti_sektor("Energi")]
        self.assertEqual([n for n, _ in fs.sti_aksjer()], ["Aksjer"])
        self.assertEqual([n for n, _ in fs.sti_sektorer()], ["Aksjer", "Sektorer"])
        self.assertEqual(sektor, ["Aksjer", "Sektorer", "Energi"])
        self.assertEqual([n for n, _ in fs.sti_aksje("Energi", "EQNR")], sektor + ["EQNR"])
        self.assertEqual(fs.sti_sektor("Fornybar energi")[-1], ("Fornybar energi", "/aksjer/sektor/fornybar-energi/"))

    def test_malene_viser_samme_sti_i_siden_og_i_json_ld(self):
        sider = self._lag_malene()
        self.assertEqual(set(sider), {"aksje", "rapportside", "oversikt", "sektorindeks", "sektor",
                                      "toppliste", "rapportkalender", "utbyttekalender"})
        forventet = {
            "aksje": ["exday.no", "Aksjer", "Sektorer", "Finans", "AAA"],
            "rapportside": ["exday.no", "Aksjer", "Sektorer", "Finans", "AAA", "Rapporter"],
            "oversikt": ["exday.no", "Aksjer"],
            "sektorindeks": ["exday.no", "Aksjer", "Sektorer"],
            "sektor": ["exday.no", "Aksjer", "Sektorer", "Finans"],
            "toppliste": ["exday.no", "Aksjer", "Aksjer med høyest utbytte"],
            "rapportkalender": ["exday.no", "Rapportkalender"],
            "utbyttekalender": ["exday.no", "Utbyttekalender"],
        }
        for navn, side in sider.items():
            with self.subTest(side=navn):
                syn = self._brodsmule_synlig(side)
                self.assertIsNotNone(syn, f"{navn} mangler brødsmule")
                self.assertEqual(syn["navn"], forventet[navn])
                self.assertEqual(syn["skille"], {"›"})
                self.assertEqual(self._brodsmule_ld(side), [forventet[navn]])
                self.assertNotIn("Utforsk", syn["navn"])
                self.assertNotIn('<span>/</span>', side)
                self.assertNotIn('class="breadcrumb"', side)

    # ── overskriften ──────────────────────────────────────────────────────

    def test_stilarket_har_en_overskrift(self):
        css = open(os.path.join(_REPO, "assets", "style.css"), encoding="utf-8").read()
        regel = re.search(r"\.side-h1 \{([^}]*)\}", css).group(1)
        self.assertIn("font-weight: 700", regel)
        self.assertIn("font-size: 1.4rem", regel)
        self.assertRegex(css, r"@media \(min-width: 481px\) \{ \.side-h1 \{ font-size: 1\.75rem; \} \}")

    def test_malene_bruker_overskriften_og_setter_ikke_egen_storrelse(self):
        for navn, side in self._lag_malene().items():
            with self.subTest(side=navn):
                h1 = re.findall(r"<h1([^>]*)>", side)
                self.assertEqual(len(h1), 1, navn)
                self.assertIn("side-h1", h1[0])
                stil = "\n".join(re.findall(r"<style>(.*?)</style>", side, re.S))
                for regel in re.findall(r"(?<![\w.-])h1\s*\{([^}]*)\}", stil):
                    self.assertNotIn("font-size", regel, f"{navn}: h1 setter egen størrelse")
                    self.assertNotIn("font-weight", regel, f"{navn}: h1 setter egen vekt")

    def test_haandskrevne_sider_bruker_overskriften(self):
        sett = 0
        for rel, side in self._haandskrevne().items():
            for attr in re.findall(r"<h1([^>]*)>", side):
                if "sr-only" in attr:
                    continue
                sett += 1
                self.assertIn("side-h1", attr, f"{rel}: h1 uten side-h1")
                self.assertNotRegex(attr, r"text-(?:2xl|3xl|4xl)|font-(?:bold|extrabold|semibold)",
                                    f"{rel}: h1 har egen størrelse eller vekt")
        self.assertGreater(sett, 20)

    # ── bakgrunnen ────────────────────────────────────────────────────────

    def test_malene_har_gray_50_og_gray_950(self):
        for navn, side in self._lag_malene().items():
            if navn == "utbyttekalender":
                continue   # kroppen ligger i en håndskrevet side, som testes under
            with self.subTest(side=navn):
                stil = "\n".join(re.findall(r"<style>(.*?)</style>", side, re.S))
                lys = re.findall(r"(?m)^\s*body\s*\{[^}]*?background:\s*([^;}]+)", stil)
                mork = re.findall(r"(?m)^\s*\.dark body\s*\{[^}]*?background:\s*([^;}]+)", stil)
                self.assertEqual([b.strip() for b in lys], ["#f9fafb"], navn)
                self.assertEqual([b.strip() for b in mork], ["#030712"], navn)

    def test_haandskrevne_sider_har_gray_50_og_gray_950(self):
        sett = 0
        for rel, side in self._haandskrevne().items():
            m = re.search(r'<body class="([^"]*)"', side)
            if not m or "dark:" not in side:
                continue
            sett += 1
            klasser = m.group(1).split()
            self.assertIn("bg-gray-50", klasser, f"{rel}: bakgrunnen er ikke gray-50")
            self.assertIn("dark:bg-gray-950", klasser, f"{rel}: mørk bakgrunn er ikke gray-950")
            self.assertNotIn("bg-white", klasser, rel)
        self.assertGreater(sett, 25)

    # ── brødsmulen på de håndskrevne sidene ───────────────────────────────

    def test_haandskrevne_sider_har_brodsmule_som_stemmer_med_json_ld(self):
        sider = self._haandskrevne()
        stier = {}
        for rel, side in sider.items():
            gammel = re.search(r'<nav[^>]*aria-label="Brødsmul[^"]*"[^>]*>', side)
            if gammel:
                self.assertIn('class="brodsmule"', gammel.group(0), f"{rel}: gammel brødsmule")
            syn = self._brodsmule_synlig(side)
            if rel in self.MED_BRODSMULE or rel.startswith("artikler/"):
                self.assertIsNotNone(syn, f"{rel} mangler brødsmule")
            if syn is None:
                continue
            self.assertEqual(syn["skille"], {"›"}, rel)
            self.assertEqual(syn["navn"][0], "exday.no", rel)
            ld = self._brodsmule_ld(side)
            self.assertEqual(ld, [syn["navn"]], f"{rel}: synlig sti og JSON-LD er ulike")
            if rel in self.MED_BRODSMULE:
                self.assertEqual(syn["navn"][1:], self.MED_BRODSMULE[rel], rel)
            if rel.startswith("artikler/") and rel != "artikler/index.html":
                self.assertEqual(syn["navn"][1], "Artikler", rel)
                self.assertEqual(len(syn["navn"]), 3, rel)
            # hvert ledd unntatt det siste lenker til en side som finnes
            for href in syn["lenker"]:
                self.assertTrue(os.path.exists(os.path.join(_REPO, href.strip("/"), "index.html")) or href == "/",
                                f"{rel}: lenken {href} finnes ikke")
            stier[rel] = syn["navn"]
        self.assertGreater(len(stier), 24)

    def test_stien_over_er_prefikset_ogsaa_mellom_mal_og_haandskrevne_sider(self):
        """Hver side lenker til siden over, og den siden har stien minus ett ledd."""
        stier = {}
        malene = self._lag_malene()
        for navn, url in [("aksje", "/aksjer/AAA/"), ("rapportside", "/aksjer/AAA/rapporter/"),
                          ("oversikt", "/aksjer/"), ("sektorindeks", "/aksjer/sektor/"),
                          ("sektor", "/aksjer/sektor/finans/"), ("toppliste", "/aksjer/hoyest-utbytte/"),
                          ("rapportkalender", "/rapportkalender/"), ("utbyttekalender", "/utbyttekalender/")]:
            stier[url] = self._brodsmule_synlig(malene[navn])
        for rel, side in self._haandskrevne().items():
            syn = self._brodsmule_synlig(side)
            if syn:
                stier["/" + rel[:-len("index.html")]] = syn
        sjekket = 0
        for url, syn in stier.items():
            if len(syn["navn"]) < 3:
                continue
            over = syn["lenker"][-1]   # leddet rett over er siste lenke
            if over in stier:
                sjekket += 1
                self.assertEqual(stier[over]["navn"], syn["navn"][:-1],
                                 f"{url} ligger under {over}, men stiene passer ikke")
        self.assertGreater(sjekket, 12)

    # ── tallrutene ────────────────────────────────────────────────────────

    def test_kolonner_etter_antall_ruter(self):
        css = open(os.path.join(_REPO, "assets", "style.css"), encoding="utf-8").read()
        for n, kol in [(1, 1), (2, 2), (3, 3), (4, 2), (6, 3)]:
            self.assertIn(f"tallruter-n{n}", fs.tallruter_html([("e", "1")] * n))
        # 2 og 4 gir to kolonner på telefon, 3 og 6 gir tre. Alle andre antall
        # (1, 5, 7 …) får grunnregelen med én kolonne, aldri en enslig rute.
        for n, kol in [(2, 2), (4, 2), (3, 3), (6, 3)]:
            self.assertRegex(css, rf"\.tallruter-n{n}[^{{]*\{{ grid-template-columns: repeat\({kol}, minmax\(0, 1fr\)\); \}}")
        self.assertRegex(css, r"\.tallruter \{[^}]*grid-template-columns: minmax\(0, 1fr\);")
        self.assertNotRegex(css, r"tallruter-n5|tallruter-n7")
        # 4 ruter fyller raden også bredt: fire kolonner fra 640 px
        self.assertRegex(css, r"min-width: 640px\) \{ \.tallruter-n4 \{ grid-template-columns: repeat\(4,")
        self.assertIn("tallruter-tekst", fs.tallruter_html([("e", "1")] * 3, tekst=True))

    def test_etiketten_staar_over_tallet_og_antallet_stemmer(self):
        sider = self._lag_malene()
        sider.update({"/" + rel: s for rel, s in self._haandskrevne().items()})
        sett = 0
        for navn, side in sider.items():
            for klasse, rute_html in re.findall(r'<dl class="(tallruter[^"]*)"[^>]*>(.*?)</dl>', side, re.S):
                sett += 1
                n = int(re.search(r"tallruter-n(\d+)", klasse).group(1))
                self.assertEqual(rute_html.count('class="tallrute"'), n, f"{navn}: klassen sier {n} ruter")
                for celle in re.findall(r'<div class="tallrute">(.*?)</div>(?=<div class="tallrute">|$)', rute_html, re.S):
                    self.assertLess(celle.index("<dt>"), celle.index("<dd>"), f"{navn}: etiketten må stå først")
        self.assertGreaterEqual(sett, 6)   # oversikt, sektor, toppliste, rapportkalender, rapportside, /om/

    def test_ingen_gamle_tallruter(self):
        """Etiketten under tallet og fire slags rutenett er borte fra malene og sidene."""
        kilde = open(os.path.join(_REPO, "scripts", "fetch_stocks.py"), encoding="utf-8").read()
        for gammelt in ('class="stat"', 'class="stats"', "stat-val", "hero-stat", 'class="rute"', 'class="ruter"'):
            self.assertNotIn(gammelt, kilde, f"malen har fortsatt {gammelt}")
        for rel, side in self._haandskrevne().items():
            for gammelt in ("stat-box", "stat-grid", "stat-num"):
                self.assertNotIn(gammelt, side, f"{rel}: {gammelt}")


class TestLinjelengde(unittest.TestCase):
    """Lesebredde (designrunde 3, 23.11.2026).

    Median tegn per linje i løpende tekst var 82 på aksjesiden, 86 på forsiden,
    103 på sektorsiden og utbyttekalenderen, 105 på rapportkalenderen og 109 på
    /verktoy/ ved 1280 px. Artiklene lå på 70 til 72. Avsnitt, ingresser,
    FAQ-svar, selskapstekst og analysetekst har fått `.les` (54ch), og tabeller,
    tallruter, grafer, kort og kalenderkontroller har full bredde.

    En enhet i `ch` er bredden av sifferet 0, og i Inter er den ca. 20 % bredere
    enn en vanlig bokstav. Et direkte 68ch gir derfor fortsatt 82 tegn, og
    testen under krever en verdi rundt 54ch.

    Malene leses ved å lage sidene (små fixtures, pluss EQNR og ISLAX fra
    data/aksjer.json). De håndskrevne sidene leses fra repoet, uten de
    genererte blokkene, som boten lager på nytt.
    """

    AKSJER = TestSidetopp.AKSJER
    I_DAG = TestSidetopp.I_DAG
    UNNTATT = TestSidetopp.UNNTATT
    _lag_malene = TestSidetopp._lag_malene
    _eksempel = None

    LANG = 160   # tegn. Kortere avsnitt går ikke over mange linjer.
    # Klasser som gjør et avsnitt til tekst i et kort eller en kontrollflate. Der
    # følger bredden kortet, og tabeller og kort beholder full bredde.
    KORT = {"rounded-xl", "artikel-kort", "info-bar", "cta", "std-footer", "konto-rad", "hero", "kal-uke"}
    # Siden som skal ha lesebredden: de håndskrevne i omfanget.
    SIDER = ["index.html", "utbyttekalender/index.html", "verktoy/index.html",
             "verktoy/fire-kalkulator/index.html", "verktoy/huslan-vs-investering/index.html",
             "verktoy/sektorrebalansering/index.html", "verktoy/kalkulator/index.html"]
    # Elementer med full bredde: `.les` hverken står på dem eller omslutter dem.
    FULL_BREDDE = {"tallruter", "kh-tall", "kurshode", "kal-ramme", "kal-kontroller", "nylig", "tabell-ramme",
                   "ak-grid", "sek-grid", "rel-grid", "topplister", "hero"}

    @staticmethod
    def _css():
        css = open(os.path.join(_REPO, "assets", "style.css"), encoding="utf-8").read()
        return css, re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    class _Blokker(HTMLParser):
        """Samler p, li og FAQ-svar med teksten og stien opp til roten."""
        TOMME = {"br", "img", "input", "meta", "link", "hr", "source", "area", "base", "col", "wbr"}

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stabel = []
            self.blokker = []
            self.apne = []
            self.skjult = 0
            self.elementer = []   # (tag, klasser, sti) for hvert element

        def handle_starttag(self, tag, attrs):
            if tag in self.TOMME:
                return
            kl = set((dict(attrs).get("class") or "").split())
            self.elementer.append((tag, kl, list(self.stabel)))
            if tag in ("script", "style"):
                self.skjult += 1
            self.stabel.append((tag, kl))
            if tag in ("p", "li") or (tag == "div" and "faq-svar" in kl):
                self.blokker.append({"tag": tag, "kl": kl, "sti": list(self.stabel), "tekst": ""})
                self.apne.append((len(self.stabel), len(self.blokker) - 1))

        def handle_startendtag(self, tag, attrs):
            pass

        def handle_endtag(self, tag):
            for i in range(len(self.stabel) - 1, -1, -1):
                if self.stabel[i][0] == tag:
                    del self.stabel[i:]
                    break
            self.apne = [(d, i) for d, i in self.apne if d <= len(self.stabel)]
            if tag in ("script", "style"):
                self.skjult = max(0, self.skjult - 1)

        def handle_data(self, data):
            if self.skjult:
                return
            for _, i in self.apne:
                self.blokker[i]["tekst"] += data

    def _les(self, side):
        p = self._Blokker()
        p.feed(side)
        return p

    @staticmethod
    def _dekket(b):
        return any("les" in kl for _, kl in b["sti"])

    def _unntatt(self, b):
        return any(t == "footer" or (self.KORT & kl) for t, kl in b["sti"])

    def _lange_uten_les(self, side):
        p = self._les(side)
        lange = [b for b in p.blokker
                 if len(" ".join(b["tekst"].split())) >= self.LANG and not self._unntatt(b)]
        return lange, [" ".join(b["tekst"].split())[:50] for b in lange if not self._dekket(b)]

    def _side(self, rel):
        """En håndskrevet side uten blokkene datajobben skriver."""
        side = open(os.path.join(_REPO, *rel.split("/")), encoding="utf-8").read()
        for navn in ("KAL", "KAL-HODE", "EXMND", "UKA", "ARTIKLER"):
            side = re.sub(rf"<!--{navn}:START-->.*?<!--{navn}:SLUTT-->", "", side, flags=re.S)
        return side

    def _eksempelsider(self):
        if TestLinjelengde._eksempel is not None:
            return TestLinjelengde._eksempel
        sider = self._lag_malene()
        sti = os.path.join(_REPO, "data", "aksjer.json")
        if os.path.exists(sti):
            rader = {r["ticker"]: r for r in json.load(open(sti, encoding="utf-8"))["aksjer"]}
            for t in ("EQNR", "ISLAX"):
                if t in rader:
                    sider["aksje-" + t] = fs._aksje_side_html(dict(rader[t]), str(self.I_DAG))
        sider["månedsoversikt"] = fs.lag_exmnd_blokk(self.AKSJER, self.I_DAG)
        TestLinjelengde._eksempel = sider
        return sider

    # ── stilarket ─────────────────────────────────────────────────────────

    def test_stilarket_har_en_regel_utenfor_layer(self):
        css, rent = self._css()
        m = re.search(r":root \{ --lese-bredde: (\d+(?:\.\d+)?)ch; \}", rent)
        self.assertIsNotNone(m, "--lese-bredde mangler")
        # 68ch gir 82 tegn i Inter. 50 til 58ch gir 60 til 75 tegn i median.
        self.assertTrue(50 <= float(m.group(1)) <= 58, f"{m.group(1)}ch gir ikke 60 til 75 tegn per linje")
        regel = ".les p, .les li, p.les, li.les { max-width: var(--lese-bredde); }"
        self.assertIn(regel, rent)
        # Utenfor @layer, slik at den slår Tailwinds max-w-*: klammedybde 0 ved regelen.
        foran = rent[:rent.index(regel)]
        self.assertEqual(foran.count("{"), foran.count("}"), "regelen ligger inne i en blokk eller @layer")

    def test_ch_brukes_ikke_til_annet(self):
        _, rent = self._css()
        funn = re.findall(r"[\d.]+ch\b", rent)
        self.assertEqual(len(funn), 1, f"ch skal bare stå i --lese-bredde: {funn}")

    def test_regelen_treffer_bare_tekst(self):
        """Selektorene som nevner .les treffer p, li og FAQ-svaret, aldri tabeller, tallruter, grafer eller kort."""
        _, rent = self._css()
        valgte = []
        for velger, _ in re.findall(r"([^{}]+)\{([^{}]*)\}", rent):
            for del_ in velger.split(","):
                if re.search(r"\.les\b(?!-)", del_):
                    valgte.append(" ".join(del_.split()))
        self.assertEqual(sorted(valgte), sorted([".les p", ".les li", "p.les", "li.les", ".faq-svar.les"]))
        for v in valgte:
            self.assertNotRegex(v, r"table|td\b|th\b|dd\b|dt\b|svg|tallrute|kh-tall|hero|kal-|grid|\*")

    # ── malene og sidene ──────────────────────────────────────────────────

    def test_lang_tekst_i_malene_har_lesebredde(self):
        minst = {"aksje-EQNR": 8, "sektor": 4, "toppliste": 2, "rapportkalender": 4, "rapportside": 1,
                 "utbyttekalender": 2, "månedsoversikt": 1}
        sett = {}
        for navn, side in self._eksempelsider().items():
            with self.subTest(side=navn):
                lange, mangler = self._lange_uten_les(side)
                sett[navn] = len(lange)
                self.assertEqual(mangler, [], f"{navn}: lang tekst uten .les")
        for navn, n in minst.items():
            if navn in sett:
                self.assertGreaterEqual(sett[navn], n, f"{navn}: testen fant bare {sett[navn]} lange blokker")

    def test_lang_tekst_paa_haandskrevne_sider_har_lesebredde(self):
        sett = 0
        for rel in self.SIDER:
            with self.subTest(side=rel):
                lange, mangler = self._lange_uten_les(self._side(rel))
                sett += len(lange)
                self.assertEqual(mangler, [], f"{rel}: lang tekst uten .les")
        self.assertGreater(sett, 40)

    def test_alle_faq_svar_har_lesebredde(self):
        sider = {"index.html": self._side("index.html")}
        sider.update({n: s for n, s in self._eksempelsider().items() if n.startswith("aksje-")})
        sett = 0
        for navn, side in sider.items():
            for b in self._les(side).blokker:
                if b["tag"] == "div" and "faq-svar" in b["kl"]:
                    sett += 1
                    self.assertIn("les", b["kl"], f"{navn}: FAQ-svar uten .les")
        self.assertGreaterEqual(sett, 5)

    def test_full_bredde_beholdes(self):
        """`.les` står aldri på, eller rundt, tallruter, grafer, tabellrammer, kalenderkontroller og kortrutenett."""
        sider = {n: s for n, s in self._eksempelsider().items()}
        sider.update({"/" + rel: self._side(rel) for rel in self.SIDER})
        sett = 0
        for navn, side in sider.items():
            for tag, kl, sti in self._les(side).elementer:
                if tag in ("table", "svg", "dl", "canvas", "button", "input", "select"):
                    self.assertNotIn("les", kl, f"{navn}: .les på <{tag}>")
                if self.FULL_BREDDE & kl:
                    sett += 1
                    self.assertNotIn("les", kl, f"{navn}: .les på {sorted(kl)}")
                    omsluttende = [k for _, k in sti if "les" in k]
                    self.assertEqual(omsluttende, [], f"{navn}: {sorted(kl)} ligger inne i en .les")
        self.assertGreaterEqual(sett, 8)

    def test_malene_setter_ikke_egen_bredde_paa_tekst(self):
        """Bredden settes ett sted. 46rem på sektorteksten hadde samme spesifisitet som .les og kom senere i siden."""
        kilde = open(os.path.join(_REPO, "scripts", "fetch_stocks.py"), encoding="utf-8").read()
        self.assertNotRegex(kilde, r"\.ingress \{\{[^}]*max-width")
        self.assertNotRegex(kilde, r"\.sektor-om p \{\{[^}]*max-width")
        self.assertIn('<p class="ingress les">', kilde)

    def test_ingen_tekst_er_senteret_eller_hoyrejustert_i_en_les(self):
        """Tekstkolonnen ligger mot venstrekanten: ingen .les-blokk bruker mx-auto, text-center eller text-right."""
        sider = {n: s for n, s in self._eksempelsider().items()}
        sider.update({"/" + rel: self._side(rel) for rel in self.SIDER})
        for navn, side in sider.items():
            for b in self._les(side).blokker:
                if self._dekket(b) and not self._unntatt(b):
                    alle = set(b["kl"])
                    for _, kl in b["sti"]:
                        if "les" in kl:
                            alle |= kl
                    self.assertFalse({"mx-auto", "text-center", "text-right"} & alle, f"{navn}: {sorted(alle)}")


class TestTabellForst(unittest.TestCase):
    """Tabellen først og fast tickerkolonne (designrunde 4, 24.11.2026).

    På Finans lå første tabellrad 3 438 px nedover siden ved 390 px, fordi
    sektorteksten sto over tabellen. Og når leseren rullet tabellen sideveis,
    rullet tickeren ut av bildet, så raden bare var tall uten navn. Sektormalen
    har nå tallrutene, en lenke til teksten og hele tabellen først, og teksten
    etter. Tickerkolonnen er `position: sticky` i tabellene på sektorsidene og
    i oversikten på /aksjer/.

    Sticky virker mot nærmeste forelder som ruller, og `overflow: hidden` på
    selve `<table>` gjorde tabellen til den forelderen. Cellen sto da 371 px til
    venstre for rammen ved full rulling (målt i Chromium). Testene leser både
    malene og stilarket, siden begge deler må stemme.
    """

    AKSJER = TestSidetopp.AKSJER
    I_DAG = TestSidetopp.I_DAG
    _lag_malene = TestSidetopp._lag_malene

    @staticmethod
    def _css():
        css = open(os.path.join(_REPO, "assets", "style.css"), encoding="utf-8").read()
        return re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    @staticmethod
    def _stil(side):
        """All CSS i <style>-blokkene på en side, uten kommentarer."""
        deler = re.findall(r"<style[^>]*>(.*?)</style>", side, flags=re.S)
        return re.sub(r"/\*.*?\*/", "", "\n".join(deler), flags=re.S)

    @staticmethod
    def _regler(css):
        """[(velgere, {egenskap: verdi})] for hver enkel regel. Regler inni @media
        leses som vanlige regler (den ytre blokken har klammer og faller utenfor)."""
        ut = []
        for velger, deklarasjoner in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            ds = {}
            for d in deklarasjoner.split(";"):
                if ":" in d:
                    k, v = d.split(":", 1)
                    ds[k.strip()] = " ".join(v.split())
            ut.append(([" ".join(v.split()) for v in velger.split(",")], ds))
        return ut

    def _verdi(self, css, velger, egenskap):
        """Egenskapen i siste regel som har nøyaktig denne velgeren."""
        funn = [ds[egenskap] for velgere, ds in self._regler(css) if velger in velgere and egenskap in ds]
        self.assertTrue(funn, f"fant ingen regel for «{velger}» med {egenskap}")
        return funn[-1]

    def _sektorside(self):
        return self._lag_malene()["sektor"]

    def _alle_sektorsider(self):
        """{sektor: (html, antall aksjer i sektoren)} for hele katalogen, hvis den finnes."""
        sti = os.path.join(_REPO, "data", "aksjer.json")
        if not os.path.exists(sti):
            self.skipTest("data/aksjer.json finnes ikke")
        with open(sti, encoding="utf-8") as f:
            rader = json.load(f)["aksjer"]
        rot = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, rot, ignore_errors=True)
        fs.generer_sektorsider(rader, rot)
        ut = {}
        for sektor in sorted({r["sektor"] for r in rader if r.get("sektor")}):
            side = open(os.path.join(rot, "aksjer", "sektor", fs._sektor_slug(sektor), "index.html"), encoding="utf-8").read()
            ut[sektor] = (side, sum(1 for r in rader if r.get("sektor") == sektor))
        return ut

    @staticmethod
    def _tbody_rader(side):
        tbody = re.search(r"<tbody>(.*?)</tbody>", side, re.S).group(1)
        return re.findall(r"<tr>", tbody)

    # ── rekkefølgen på sektorsiden ────────────────────────────────────────

    def test_tabellen_kommer_for_sektorteksten(self):
        side = self._sektorside()
        tall = side.index('class="tallruter')
        tabell = side.index("<table")
        tekst = side.index('class="sektor-analyse')
        self.assertLess(tall, tabell, "tabellen skal stå under tallrutene")
        self.assertLess(tabell, tekst, "sektorteksten skal stå etter tabellen")
        self.assertLess(tekst, side.index('class="cta"'))

    def test_hver_sektorside_har_tabellen_for_teksten(self):
        sider = self._alle_sektorsider()
        self.assertGreaterEqual(len(sider), 10)
        for sektor, (side, antall) in sider.items():
            with self.subTest(sektor=sektor):
                self.assertLess(side.index("<table"), side.index('class="sektor-analyse'))
                self.assertEqual(len(self._tbody_rader(side)), antall, "alle rader skal være med, ingen skjult")

    def test_ingen_rader_er_skjult_eller_kuttet(self):
        side = self._sektorside()
        self.assertNotIn("<details", side)
        self.assertEqual(len(self._tbody_rader(side)), sum(1 for a in self.AKSJER if a["sektor"] == "Finans"))
        self.assertEqual(side.count("<table"), 1, "en kopi av tabellen er en avkortet variant")
        # Ingen skjuling av rader eller tekst i malens stil.
        self.assertNotRegex(self._stil(side), r"(tr|td|\.sektor-analyse)[^{}]*\{[^}]*display:\s*none")

    def test_all_tekst_er_med(self):
        """Hele analyseteksten ligger i HTML-en, uendret, og det eneste som er
        endret i den er overskriften som pekte «under»."""
        sorterte = sorted([a for a in self.AKSJER if a["sektor"] == "Finans"],
                          key=lambda a: a.get("utbytte_yield", 0), reverse=True)
        analyse = fs._sektor_analyse("Finans", sorterte, self.AKSJER)
        self.assertIn("Finans som utbyttesektor", analyse)
        self.assertIn("Hva driver utbyttet i Finans?", analyse)
        self.assertIn("Slik fungerer utbytte i finans", analyse)
        side = self._sektorside()
        self.assertIn(analyse, side, "analyseblokken skal stå i siden som den er laget")
        ord_i_blokken = len(re.sub(r"<[^>]+>", " ", analyse).split())
        self.assertGreater(ord_i_blokken, 300)

    def test_overskriften_peker_ikke_under(self):
        side = self._sektorside()
        self.assertNotRegex(side, r"tabellen under")
        self.assertIn("<h2>Slik bruker du tabellen</h2>", side)
        # Resten av avsnittet står som før.
        self.assertIn("Aksjene er sortert etter direkteavkastning, høyeste først.", side)

    # ── lenken til teksten ────────────────────────────────────────────────

    def test_ankerlenken_peker_paa_et_id_som_finnes(self):
        for sektor, (side, _) in self._alle_sektorsider().items():
            with self.subTest(sektor=sektor):
                m = re.search(r'<p class="sektor-hopp"><a href="#([^"]+)">(.*?)</a></p>', side, re.S)
                self.assertIsNotNone(m, "lenken ved tabellen mangler")
                mal = m.group(1)
                self.assertEqual(side.count(f'id="{mal}"'), 1, f"#{mal} skal finnes én gang")
                self.assertRegex(side, rf'class="sektor-analyse les" id="{mal}"')
                tekst = " ".join(re.sub(r"<[^>]+>", " ", m.group(2)).split())
                self.assertEqual(tekst, f"Les om hva som driver utbyttet i {sektor}")
                # Lenken står mellom tallrutene og tabellen, og teksten etter tabellen.
                self.assertLess(side.index('class="tallruter'), side.index('class="sektor-hopp"'))
                self.assertLess(side.index('class="sektor-hopp"'), side.index("<table"))
                self.assertLess(side.index("<table"), side.index(f'id="{mal}"'))

    def test_lenken_er_et_strek_svg_uten_skjult_tekst(self):
        side = self._sektorside()
        lenke = re.search(r'<p class="sektor-hopp">.*?</p>', side, re.S).group(0)
        self.assertIn('stroke="currentColor"', lenke)
        self.assertIn('viewBox="0 0 24 24"', lenke)
        self.assertIn('aria-hidden="true"', lenke)

    def test_ingen_lenke_uten_tekst_aa_hoppe_til(self):
        self.assertEqual(fs.sektor_hopp_lenke("Finans", ""), "")
        self.assertEqual(fs.sektor_hopp_lenke("Finans", "<div>uten anker</div>"), "")
        self.assertIn('href="#sektoranalyse"', fs.sektor_hopp_lenke("Finans", '<div id="sektoranalyse"></div>'))

    # ── fast tickerkolonne i malene ───────────────────────────────────────

    def test_tabellene_har_klassen_og_en_ramme_som_ruller(self):
        sider = self._lag_malene()
        self.assertRegex(sider["sektor"], r'<div class="tabell-ramme">\s*<table class="tabell-fast">')
        self.assertRegex(sider["oversikt"], r'<div style="overflow-x:auto;">\s*<table class="tabell-fast">')
        self.assertRegex(self._stil(sider["sektor"]), r"\.tabell-ramme\s*\{[^}]*overflow-x:\s*auto")

    def test_ingen_overflow_paa_selve_tabellen(self):
        """`overflow` på `<table>` gjør tabellen til forelderen sticky festes mot."""
        sider = self._lag_malene()
        for navn in ("sektor", "oversikt"):
            with self.subTest(side=navn):
                for velgere, ds in self._regler(self._stil(sider[navn])):
                    if "table" in velgere or ".tabell-fast" in velgere:
                        self.assertFalse([k for k in ds if k.startswith("overflow")],
                                         f"{navn}: overflow på table: {ds}")
        for velgere, ds in self._regler(self._css()):
            if any(".tabell-fast" in v and "td" not in v and "th" not in v for v in velgere):
                self.assertFalse([k for k in ds if k.startswith("overflow")], f"style.css: {ds}")

    def test_tickerkolonnen_har_sticky_med_bakgrunn(self):
        css = self._css()
        for velger, z in ((".tabell-fast td:first-child", "1"), (".tabell-fast th:first-child", "2")):
            with self.subTest(velger=velger):
                self.assertEqual(self._verdi(css, velger, "position"), "sticky")
                self.assertEqual(self._verdi(css, velger, "left"), "0")
                self.assertEqual(self._verdi(css, velger, "z-index"), z)
                self.assertRegex(self._verdi(css, velger, "background-color"), r"^var\(--fast-bg(-hode)?\)$")
        self.assertEqual(self._verdi(css, ".tabell-fast tbody tr:hover td:first-child", "background-color"),
                         "var(--fast-bg-hover)")

    def test_stilen_ligger_utenfor_layer(self):
        css = self._css()
        regel = ".tabell-fast td:first-child { position: sticky;"
        foran = css[:css.index(regel)]
        self.assertEqual(foran.count("{"), foran.count("}"), "regelen ligger inne i en blokk eller @layer")

    def test_kanten_vises_der_tabellen_kan_rulle(self):
        css = self._css()
        m = re.search(r"@media \(max-width: ([\d.]+)rem\) \{(.*?)\n\}", css[css.index(".tabell-fast td:first-child {"):], re.S)
        self.assertIsNotNone(m)
        self.assertLessEqual(float(m.group(1)), 48)
        self.assertIn("box-shadow: inset -1px 0 0 var(--fast-kant)", m.group(2))
        self.assertIn("::after", m.group(2))
        self.assertIn("--fast-skygge", m.group(2))

    def test_bakgrunnene_matcher_raden_i_begge_temaer(self):
        """Den festede cellen har samme farge som resten av raden, i lyst og mørkt
        tema og ved hover, ellers står det en stripe i kolonnen."""
        sider = self._lag_malene()
        css = self._css()
        lys = {"--fast-bg": self._verdi(css, ".tabell-fast", "--fast-bg"),
               "--fast-bg-hode": self._verdi(css, ".tabell-fast", "--fast-bg-hode"),
               "--fast-bg-hover": self._verdi(css, ".tabell-fast", "--fast-bg-hover")}
        mork = {k: self._verdi(css, ".dark .tabell-fast", k) for k in lys}
        # Sektormalen: tabellen, hodet og hover.
        st = self._stil(sider["sektor"])
        self.assertEqual(lys["--fast-bg"], self._verdi(st, "table", "background"))
        self.assertEqual(lys["--fast-bg-hode"], self._verdi(st, "th", "background"))
        self.assertEqual(lys["--fast-bg-hover"], self._verdi(st, "tr:hover td", "background"))
        self.assertEqual(mork["--fast-bg"], self._verdi(st, ".dark table", "background"))
        self.assertEqual(mork["--fast-bg-hode"], self._verdi(st, ".dark th", "background"))
        self.assertEqual(mork["--fast-bg-hover"], self._verdi(st, ".dark tr:hover td", "background"))
        # Oversikten: kortet rundt tabellen er bakgrunnen, og hodet er gray-50 i lyst tema.
        ov = self._stil(sider["oversikt"])
        self.assertEqual(lys["--fast-bg"], self._verdi(ov, ".alle-aksjer", "background"))
        self.assertEqual(self._verdi(ov, ".tabell-fast", "--fast-bg-hode"), self._verdi(ov, "th", "background"))
        self.assertEqual(lys["--fast-bg-hover"], self._verdi(ov, "tr:hover td", "background"))
        self.assertEqual(mork["--fast-bg"], self._verdi(ov, ".dark .alle-aksjer", "background"))
        self.assertEqual(mork["--fast-bg-hode"], self._verdi(ov, ".dark th", "background"))
        self.assertEqual(mork["--fast-bg-hover"], self._verdi(ov, ".dark tr:hover td", "background"))

    def test_ingen_sebra_som_cellen_maa_matche(self):
        """Ingen av de to malene har radvis bakgrunn. Kommer sebra inn, må den festede
        cellen få samme regel, og da må denne testen oppdateres."""
        sider = self._lag_malene()
        for navn in ("sektor", "oversikt"):
            self.assertNotRegex(self._stil(sider[navn]), r"nth-child\((even|odd|2n)", f"{navn} har sebra")

    def test_trykkflater_og_tallformat_er_uendret(self):
        """Den festede kolonnen setter ikke størrelse, padding eller skrift på cellene."""
        css = self._css()
        for velgere, ds in self._regler(css):
            if any(v.startswith(".tabell-fast") for v in velgere):
                tillatt = {"position", "left", "z-index", "background-color", "box-shadow", "content", "top", "bottom",
                           "width", "pointer-events", "background", "border-collapse", "border-spacing", "border-radius"}
                ukjent = [k for k in ds if k not in tillatt and not k.startswith("--")]
                self.assertEqual(ukjent, [], f"{velgere}: {ukjent}")
        # tabular-nums gjelder fortsatt alle tabeller globalt (tw-input.css, bygd inn i tailwind.css).
        with open(os.path.join(_REPO, "assets", "tailwind.css"), encoding="utf-8") as f:
            tw = f.read()
        self.assertIn("table{font-variant-numeric:tabular-nums}", tw)

    def test_topplistene_er_ikke_rort(self):
        """Toppliste-tabellen har en rangkolonne foran tickeren, så den trenger to festede
        kolonner med egen forskyvning. Den er utenfor runden, og skal ikke få klassen halvveis."""
        sider = self._lag_malene()
        self.assertNotIn("tabell-fast", sider["toppliste"])
        self.assertNotIn("tabell-fast", sider["sektorindeks"])


class TestRapportUtvikling(unittest.TestCase):
    """Rapportsiden over tid (designrunde 5, 24.11.2026).

    Siden viste hver rapport for seg, med «samme periode i fjor» som eneste
    sammenligning. Nå har den siste rapporten en kolonne «Forrige rapport» (og
    «Endring» når den lar seg regne), og «Utvikling over tid» setter
    nøkkeltallene med identisk navn side om side, rapport for rapport.

    Det som ikke er med, er like viktig, og testes like nøye: en side med én
    rapport er som før (også stilarket), en rad uten identisk navn blir ikke
    slått sammen med en annen, og en endring regnes bare der den er sann.
    """

    A = TestSidetopp.AKSJER[0]
    GRAA = {"#fff", "#4b5563", "#6b7280", "#9ca3af", "#e5e7eb", "#f3f4f6", "#1f2937", "#111827", "#374151"}

    @staticmethod
    def _r(periode, rader, dato="2026-10-21"):
        return {"periode": periode, "dato": dato, "melding": "1", "tittel": "t",
                "resultat": "Resultatet var 1,0 milliard kroner.", "utbytte": "Ingen endring.",
                "plan": "", "ellers": [], "skrevet": "2026-11-24",
                "nokkeltall": [{"navn": n, "naa": v, "forrige": f} for n, v, f in rader]}

    def _q3(self):
        return self._r("2026-Q3", [("Resultat etter skatt", "358,9 mill. USD", "56,8 mill. USD"),
                                   ("Egenkapitalavkastning", "14,5 %", "15,8 %")])

    def _q2(self):
        return self._r("2026-Q2", [("Resultat etter skatt", "137,9 mill. USD", "43,4 mill. USD"),
                                   ("Egenkapitalavkastning", "27,0 %", "9,1 %")], dato="2026-08-28")

    def _q1(self):
        return self._r("2026-Q1", [("Resultat etter skatt", "10,0 mill. USD", "9,0 mill. USD"),
                                   ("Egenkapitalavkastning", "5,0 %", "4,0 %")], dato="2026-05-20")

    def _tre(self):
        """Tre rapporter: «Utvikling over tid» vises først fra `SERIE_MIN_RAPPORTER`."""
        return [self._q3(), self._q2(), self._q1()]

    def _side(self, rapporter):
        return fs._rapportside_html(dict(self.A), rapporter, "2026-11-24")

    @staticmethod
    def _css(side):
        return side.split("<style>")[1].split("</style>")[0]

    # ── siden uten noe å sammenligne er som før ──────────────────────────

    def test_en_rapport_gir_siden_som_foer(self):
        side = self._side([self._q3()])
        for ikke in ('id="utvikling"', "Utvikling over tid", "kol-rolle", "rapport-serie", "rapport-flere",
                     "tabell-forklaring", fs.RAPPORT_FORKLARING, fs.RAPPORT_SAMMENLIGNING_CSS, "tabell-fast"):
            self.assertNotIn(ikke, side)
        self.assertNotIn("Forrige rapport", side)

    def test_to_rapporter_uten_identisk_navn_gir_siden_som_foer(self):
        q2 = self._r("2026-Q2", [("Resultat til aksjonærene", "137,9 mill. USD", "43,4 mill. USD"),
                                 ("Egenkapitalavkastning før skatt", "27,0 %", "9,1 %")], dato="2026-08-28")
        side = self._side([self._q3(), q2])
        for ikke in ('id="utvikling"', "kol-rolle", "rapport-serie", "tabell-forklaring", "tabell-fast",
                     fs.RAPPORT_SAMMENLIGNING_CSS):
            self.assertNotIn(ikke, side)
        self.assertNotIn("Forrige rapport", side)
        # Hopp-lenkene til hver rapport er som før.
        self.assertIn('<a href="#2026-q2">2. kv. 2026</a>', side)
        self.assertNotIn('href="#utvikling"', side)

    def test_siden_er_lik_fra_kjoering_til_kjoering(self):
        """lastmod i sitemapen flyttes av innholdshashen, så malen må gi samme side for samme data."""
        liste = [self._q3(), self._q2()]
        self.assertEqual(self._side(liste), self._side(liste))
        self.assertEqual(self._side([self._q3()]), self._side([self._q3()]))

    # ── kolonnen «Forrige rapport» ───────────────────────────────────────

    def test_kolonnen_forrige_rapport_og_etikett_paa_samme_periode_i_fjor(self):
        side = self._side([self._q3(), self._q2()])
        hode = side.split('<table class="rapport-tall rapport-flere tabell-fast">')[1].split("</thead>")[0]
        self.assertEqual(re.findall(r'<span class="kol-rolle">([^<]*)</span><span class="kol-periode">([^<]*)</span>', hode),
                         [("Nå", "3. kv. 2026"), ("Endring", "fra forrige rapport"),
                          ("Forrige rapport", "2. kv. 2026"), ("Samme periode i fjor", "3. kv. 2025")])
        kropp = side.split('<table class="rapport-tall rapport-flere tabell-fast">')[1].split("<tbody>")[1]
        self.assertIn("137,9\u00a0mill. USD", kropp)      # forrige rapports tall
        self.assertIn("+160,3\u00a0%", kropp)                # endringen
        self.assertIn("56,8\u00a0mill. USD", kropp)       # samme periode i fjor, som før

    def test_prosent_gir_prosentpoeng_ikke_prosent(self):
        side = self._side([self._q3(), self._q2()])
        self.assertIn("\u221212,5\u00a0<abbr title=\"prosentpoeng\">pp</abbr>", side)   # 14,5 mot 27,0
        self.assertNotIn("\u221246,3", side)                                              # ikke 14,5 / 27,0 minus 1

    def test_kolonnen_er_bare_i_den_nyeste_rapporten(self):
        q1 = self._r("2026-Q1", [("Resultat etter skatt", "10 mill. USD", "9 mill. USD"),
                                 ("Egenkapitalavkastning", "5,0 %", "4,0 %")], dato="2026-05-20")
        side = self._side([self._q3(), self._q2(), q1])
        self.assertEqual(side.count('<span class="kol-rolle">Forrige rapport</span>'), 1)
        self.assertEqual(side.count('<table class="rapport-tall">'), 2)   # de to eldre, som før

    def test_manglende_kvartal_gir_ingen_forrige_rapport(self):
        """Q3 og Q1 lagret, Q2 mangler: «forrige rapport» er forrige kvartal, og det har vi ikke."""
        q1 = self._r("2026-Q1", [("Resultat etter skatt", "10 mill. USD", "9 mill. USD")], dato="2026-05-20")
        q3_25 = self._r("2025-Q3", [("Resultat etter skatt", "8 mill. USD", "7 mill. USD")], dato="2025-10-20")
        side = self._side([self._q3(), q1, q3_25])
        self.assertNotIn('<span class="kol-rolle">Forrige rapport</span>', side)
        # Men serien finnes, med alle kolonnene og uten endringstall over hullene.
        self.assertIn('id="utvikling"', side)
        serie = side.split('id="utvikling"')[1].split("</section>")[0]
        self.assertIn("1. kv. 2026", serie)
        self.assertNotIn('class="endring"', serie)

    def test_endring_mangler_naar_enhetene_er_ulike(self):
        q3 = self._r("2026-Q3", [("Resultat per aksje", "2,05 USD", "0,38 USD")])
        q2 = self._r("2026-Q2", [("Resultat per aksje", "0,79 NOK", "0,23 NOK")], dato="2026-08-28")
        side = self._side([q3, q2])
        self.assertIn("0,79\u00a0NOK", side)
        self.assertNotIn('<span class="kol-rolle">Endring</span>', side)   # ingen rad kan regnes: ingen kolonne
        self.assertNotIn('class="endring"', side)

    def test_endring_fra_underskudd_og_null_har_ingen_prosent(self):
        q3 = self._r("2026-Q3", [("A", "5 mill. kr", "1 mill. kr"), ("B", "5 mill. kr", "1 mill. kr"),
                                 ("C", "8 mill. kr", "1 mill. kr")])
        q2 = self._r("2026-Q2", [("A", "underskudd på 3 mill. kr", "1 mill. kr"), ("B", "0 mill. kr", "1 mill. kr"),
                                 ("C", "4 mill. kr", "1 mill. kr")], dato="2026-08-28")
        side = self._side([q3, q2])
        tbody = side.split('rapport-flere tabell-fast">')[1].split("</tbody>")[0]
        self.assertEqual(tbody.count('class="endring"'), 1)   # bare C
        self.assertIn("+100,0\u00a0%", tbody)

    # ── «Utvikling over tid» ─────────────────────────────────────────────

    def test_utvikling_staar_etter_den_siste_rapporten_med_hopplenke(self):
        side = self._side(self._tre())
        self.assertLess(side.index('id="2026-q3"'), side.index('id="utvikling"'))
        self.assertLess(side.index('id="utvikling"'), side.index('id="2026-q2"'))
        hopp = side.split('aria-label="Hopp til rapport">')[1].split("</nav>")[0]
        self.assertEqual(re.findall(r'href="#([^"]+)"', hopp), ["2026-q3", "utvikling", "2026-q2", "2026-q1"])

    def test_utvikling_vises_ikke_med_to_rapporter(self):
        """Med to rapporter står de samme tallene i «Forrige rapport»-kolonnen, og serien gjentok dem
        (Q2-tallene sto tre ganger på MPCC, designrapporten 25.11.2026)."""
        side = self._side([self._q3(), self._q2()])
        self.assertNotIn('id="utvikling"', side)
        self.assertNotIn("utvikling-overskrift", side)
        self.assertNotIn('href="#utvikling"', side)
        self.assertIn("rapport-flere", side)       # kolonnen «Forrige rapport» er der som før
        self.assertEqual(fs.SERIE_MIN_RAPPORTER, 3)

    def test_utvikling_har_seks_kolonner_nyeste_til_venstre_og_strek_for_hull(self):
        perioder = ["2026-Q3", "2026-Q2", "2026-Q1", "2025-Q4", "2025-Q3", "2025-Q2", "2025-Q1"]
        liste = []
        for i, p in enumerate(perioder):
            rader = [("A", f"{10 - i} mill. kr", "1 mill. kr")]
            if i != 2:   # B mangler i den tredje
                rader.append(("B", f"{i + 1} mrd. kr", "1 mrd. kr"))
            liste.append(self._r(p, rader, dato=f"2026-{12 - i:02d}-01"))
        side = self._side(liste)
        serie = side.split('id="utvikling"')[1].split("</section>")[0]
        hode = serie.split("<thead>")[1].split("</thead>")[0]
        self.assertEqual(re.findall(r'<th scope="col">([^<]*)</th>', hode),
                         ["3. kv. 2026", "2. kv. 2026", "1. kv. 2026", "4. kv. 2025", "3. kv. 2025", "2. kv. 2025"])
        rad_b = [r for r in serie.split("<tr>") if r.startswith("<td>B</td>")][0]
        celler = re.findall(r"<td>(.*?)</td>", rad_b)
        self.assertEqual(len(celler), 7)         # navn pluss seks
        self.assertEqual(celler[3], "—")         # B mangler i 1. kv. 2026 (tredje kolonne)
        self.assertEqual(serie.count("<tr>"), 3)   # hode, A og B

    def test_utvikling_viser_endring_under_tallet(self):
        side = self._side(self._tre())
        serie = side.split('id="utvikling"')[1].split("</section>")[0]
        self.assertIn("358,9\u00a0mill. USD<span class=\"endring\">", serie)
        self.assertIn("+160,3\u00a0%", serie)
        # Den eldste kolonnen har ingenting å regne mot.
        rad = [r for r in serie.split("<tr>") if r.startswith("<td>Resultat etter skatt</td>")][0]
        self.assertEqual(rad.count('class="endring"'), 2)          # Q3 mot Q2 og Q2 mot Q1
        self.assertNotIn('class="endring"', re.findall(r"<td>(.*?)</td>", rad)[-1])

    def test_utvikling_slaar_ikke_sammen_navn_som_ligner(self):
        q2 = self._r("2026-Q2", [("Resultat etter skatt (justert)", "137,9 mill. USD", "1")], dato="2026-08-28")
        q3 = self._r("2026-Q3", [("Resultat etter skatt", "358,9 mill. USD", "1")])
        q1 = self._r("2026-Q1", [("Annen rad", "1 mill. kr", "1 mill. kr")], dato="2026-05-20")
        self.assertNotIn('id="utvikling"', self._side([q3, q2, q1]))

    def test_navn_i_serien_escapes(self):
        navn = "<img src=x onerror=1>"
        q3 = self._r("2026-Q3", [(navn, "1 mill. kr", "1 mill. kr")])
        q2 = self._r("2026-Q2", [(navn, "2 mill. kr", "1 mill. kr")], dato="2026-08-28")
        q1 = self._r("2026-Q1", [(navn, "3 mill. kr", "1 mill. kr")], dato="2026-05-20")
        side = self._side([q3, q2, q1])
        self.assertNotIn(navn, side)
        self.assertIn("&lt;img src=x onerror=1&gt;", side)

    # ── endringstallet ───────────────────────────────────────────────────

    def test_endringstekst_norsk_format(self):
        import kvartalsrapport as kr
        t = fs._rapport_endring_tekst
        self.assertEqual(t(kr.endring("358,9 mill. USD", "137,9 mill. USD")), "+160,3\u00a0%")
        self.assertEqual(t(kr.endring("14,5 %", "15,8 %")), "\u22121,3\u00a0pp")
        self.assertEqual(t(kr.endring("10 mill. kr", "10 mill. kr")), "0,0\u00a0%")        # null har ikke fortegn
        self.assertEqual(t(kr.endring("5 mill. kr", "10 mill. kr")), "\u221250,0\u00a0%")  # ekte minustegn
        self.assertEqual(t(kr.endring("170 mill. kr", "10 mill. kr")), "+1\u00a0600,0\u00a0%")  # tusenskille
        self.assertEqual(t(None), "")
        self.assertNotIn(".", t(kr.endring("358,9 mill. USD", "137,9 mill. USD")))

    # ── farge, tilgjengelighet og layout ─────────────────────────────────

    def test_tall_og_endring_er_noytrale(self):
        """Høyere kostnader er ikke «bra». Ingen grønn eller rød, og ingen klasser fra kurshodet."""
        css = fs.RAPPORT_SAMMENLIGNING_CSS
        farger = set(re.findall(r"#[0-9a-fA-F]{3,6}\b", css))
        self.assertTrue(farger <= self.GRAA, f"farger utenfor grått: {sorted(farger - self.GRAA)}")
        self.assertNotRegex(css, r"green|red|amber|rgba?\(\s*(?:19|30|46|145|139)\b")
        side = self._side([self._q3(), self._q2()])
        for klasse in ("kh-opp", "kh-ned", "kh-flat", "text-green", "text-red"):
            self.assertNotIn(klasse, side)
        # Hex-verdiene settes sammen av to biter, så Arctic-grepen i CLAUDE.md gir null treff også her.
        for arctic in ("132" "A50", "1E5" "C5C", "2E7" "B7B", "91C" "4D8", "8B2" "020"):
            self.assertNotIn(arctic.lower(), side.lower())

    def test_mork_modus_er_tegnet_for_det_nye(self):
        css = fs.RAPPORT_SAMMENLIGNING_CSS
        for velger in (".dark .endring", ".dark .rapport-serie th", ".dark .rapport-serie td",
                       ".dark .rapport-flere.tabell-fast, .dark .rapport-serie.tabell-fast"):
            self.assertIn(velger, css)
        # Den festede kolonnen har kortets farger i begge temaer, ellers ruller tall synlig under navnet.
        self.assertIn("--fast-bg:#fff", css)
        self.assertIn("--fast-bg:#111827", css)

    def test_tabellene_ruller_i_egen_ramme_og_har_fast_forste_kolonne(self):
        side = self._side(self._tre())
        for tabell in ('<table class="rapport-tall rapport-flere tabell-fast">',
                       '<table class="rapport-serie tabell-fast" aria-label="Nøkkeltall rapport for rapport">'):
            ramme = side.split(tabell)[0].rsplit("<", 1)[1]
            self.assertEqual(ramme, 'div class="tabell-ramme">', tabell)
        # `overflow` står på rammen, aldri på selve tabellen: ellers er tabellen rullefeltet og
        # den festede kolonnen fester seg ikke mot rammen (se «Design round 4»).
        css = self._css(side)
        for velger, kropp in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            # `.rapport-tall thead` er den skjulte tabellhodet på mobil (sr-only), ikke en rullende tabell.
            if re.search(r"rapport-(?:serie|flere|tall)|tabell-fast", velger) and not re.search(r"tabell-ramme|thead", velger):
                self.assertNotIn("overflow:", kropp.replace("overflow-wrap", ""), velger)

    def test_skjult_tekst_i_endringen_hoerer_til_rammen(self):
        """`.sr-only` er position:absolute. I en celle uten plassert forelder står den ved forelderen
        utenfor `.tabell-ramme`, og ligger den i en kolonne utenfor skjermen, ruller hele siden
        sideveis (målt 795 px ved 390 px med seks rapporter). Endringen er derfor `position:relative`.
        Tabellen har ingen `<caption class="sr-only">` av samme grunn: etiketten står som aria-label."""
        css = fs.RAPPORT_SAMMENLIGNING_CSS
        regel = re.search(r"\.endring \{([^{}]*)\}", css)
        self.assertIsNotNone(regel)
        self.assertIn("position:relative", regel.group(1))
        side = self._side(self._tre())
        self.assertNotIn("<caption", side)
        self.assertIn('<table class="rapport-serie tabell-fast" aria-label="Nøkkeltall rapport for rapport">', side)

    def test_festet_kolonne_faar_separate_kanter(self):
        """`table.rapport-tall` har border-collapse: collapse, som slår .tabell-fast (lavere spesifisitet)."""
        css = fs.RAPPORT_SAMMENLIGNING_CSS
        self.assertIn("table.rapport-flere { border-collapse:separate; border-spacing:0; }", css)
        self.assertNotIn("border-collapse:collapse", css)

    def test_smal_skjerm_stabler_ikke_tabellen_med_forrige_rapport(self):
        """Stablet ble seks rader 982 px ved 390 px, og «Endring» sto ved siden av «Samme periode i
        fjor» selv om den er regnet mot «Forrige rapport» (designrapporten 25.11.2026). Under 30rem er
        den en vanlig tabell som ruller sideveis med fast første kolonne, som «Utvikling over tid»."""
        css = fs.RAPPORT_SAMMENLIGNING_CSS
        media = css.split("@media (max-width: 30rem) {")[1].split("\n    }")[0]
        self.assertIn("table.rapport-flere { display:table;", media)
        self.assertIn(".rapport-flere tr { display:table-row;", media)
        self.assertIn(".rapport-flere td[data-p]::before { display:none; }", css)
        # Den festede første kolonnen skal ikke slås av.
        self.assertNotRegex(media, r"first-child[^{}]*\{[^{}]*position:static")
        self.assertNotIn("::after { display:none; }", media)

    def test_lesbare_etiketter(self):
        side = self._side(self._tre())
        self.assertIn('<span class="sr-only">Endring fra forrige rapport: </span>', side)
        self.assertIn('aria-labelledby="utvikling-overskrift"', side)
        # Den stablede visningen får rolle og periode på to linjer fra data-p.
        self.assertIn('data-p="Forrige rapport&#10;2. kv. 2026"', side)

    # ── tekst ────────────────────────────────────────────────────────────

    def test_teksten_kan_ikke_gaa_ut_paa_dato(self):
        """Ingen tall, ingen yield og ingen kurs i forklaringen, og ingen tankestrek (SKRIVESTIL.md)."""
        side = self._side(self._tre())
        intro = re.search(r'<section class="rapport utvikling".*?<p class="les">(.*?)</p>', side, re.S).group(1)
        for tekst in (fs.RAPPORT_FORKLARING, intro):
            self.assertIsNone(re.search(r"\d", tekst), tekst)
            self.assertNotRegex(tekst, r"yield|kurs|direkteavkastning")
            self.assertNotIn("—", tekst)
            self.assertNotIn("–", tekst)
        import sjekk_sprak as sjekk
        funn = sjekk.vurder([fs.RAPPORT_FORKLARING, intro])
        self.assertEqual((funn["streker"], funn["vendinger"]), (0, []))
        self.assertIn("«Forrige rapport» er rapporten for perioden rett før", fs.RAPPORT_FORKLARING)
        self.assertIn("regnet ut av oss", fs.RAPPORT_FORKLARING)

    def test_forklaringen_staar_bare_naar_siden_har_noe_aa_forklare(self):
        self.assertIn(fs.RAPPORT_FORKLARING, self._side([self._q3(), self._q2()]))
        self.assertNotIn(fs.RAPPORT_FORKLARING, self._side([self._q3()]))

    # ── resten av nettstedet ─────────────────────────────────────────────

    def test_boksen_paa_aksjesiden_har_ikke_den_nye_kolonnen(self):
        boks = fs.lag_rapport_boks(dict(self.A), {"AAA": [self._q3(), self._q2()]})
        self.assertIn('id="kvartalsrapport"', boks)
        for ikke in ("Forrige rapport", "rapport-flere", "kol-rolle", "tabell-fast"):
            self.assertNotIn(ikke, boks)

    def test_ingen_ny_url(self):
        """Alt står på /aksjer/{TICKER}/rapporter/. Ingen side per rapport, ingen ny sti i sitemapen."""
        kilde = inspect.getsource(fs.generer_rapportsider) + inspect.getsource(fs._rapportside_html)
        self.assertNotRegex(kilde, r"rapporter/\{[^}]*\}/")
        side = self._side([self._q3(), self._q2()])
        self.assertIn('rel="canonical" href="https://exday.no/aksjer/AAA/rapporter/"', side)

    def test_ekte_data_bruker_malen_bare_der_det_er_noe_aa_vise(self):
        """Hver side i data/rapporter/: seksjonen og kolonnen står der og bare der serien og forrige
        rapport finnes. Siden gir samme resultat uansett hvor mange selskaper som får flere rapporter."""
        import kvartalsrapport as kr
        alle = kr.les_rapporter(_REPO)
        self.assertTrue(alle, "ingen rapporter funnet")
        rad = {a["ticker"]: a for a in json.load(open(os.path.join(_REPO, "data", "aksjer.json"),
                                                      encoding="utf-8"))["aksjer"]}
        sett = 0
        for ticker, liste in alle.items():
            if ticker not in rad:
                continue
            sett += 1
            side = fs._rapportside_html(dict(rad[ticker]), liste, "2026-11-24")
            serie = kr.serie(liste)
            self.assertEqual('id="utvikling"' in side,
                             serie is not None and len(serie["kolonner"]) >= fs.SERIE_MIN_RAPPORTER, ticker)
            self.assertEqual("rapport-flere" in side,
                             bool(kr.mot_forrige(liste[0], kr.forrige_rapport(liste, liste[0]))), ticker)
            # Forklaringen står rett over tabellen den handler om, ikke øverst på siden.
            self.assertEqual(fs.RAPPORT_FORKLARING in side, "rapport-flere" in side, ticker)
        self.assertGreater(sett, 50)


class TestRapportsideDesign2511(unittest.TestCase):
    """Designgjennomgangen av rapportsiden, 25.11.2026 (MPCC, to rapporter).

    Seks funn: overskriften havnet under menyen ved hopp, tabellen «Forrige rapport» ble 982 px
    stablet, serien gjentok de samme tallene, forklaringen sto over tallrutene, «Utbetales» viste
    frekvensen i stedet for datoen, og kilden manglet. Hjelpemetodene er de samme som i
    `TestRapportUtvikling`.
    """

    A = TestRapportUtvikling.A
    _r = staticmethod(TestRapportUtvikling._r)
    _q3 = TestRapportUtvikling._q3
    _q2 = TestRapportUtvikling._q2
    _side = TestRapportUtvikling._side
    _css = staticmethod(TestRapportUtvikling._css)

    def test_hopp_til_rapport_havner_under_menyen(self):
        css = self._css(self._side([self._q3()]))
        regel = re.search(r"\n    \.rapport \{([^{}]*)\}", css)
        self.assertIsNotNone(regel)
        self.assertRegex(regel.group(1), r"scroll-margin-top:\s*7rem")

    def test_forklaringen_er_en_kort_fotnote_rett_under_tabellen(self):
        """Over tabellen var den 254 px grå tekst før første tall ved 390 px (designsjekk 26.11.2026)."""
        side = self._side([self._q3(), self._q2()])
        self.assertEqual(side.count(fs.RAPPORT_FORKLARING), 1)
        tabell_slutt = side.index("</table></div>", side.index('<table class="rapport-tall rapport-flere'))
        self.assertLess(tabell_slutt, side.index(fs.RAPPORT_FORKLARING))
        self.assertLess(side.index(fs.RAPPORT_FORKLARING), side.index("<h3>Utbyttet</h3>"))
        self.assertLessEqual(len(fs.RAPPORT_FORKLARING.split()), 40)

    def test_endring_staar_rett_etter_naa(self):
        """390 px viser to tallkolonner, og endringen er det leseren vil se."""
        side = self._side([self._q3(), self._q2()])
        hode = side.split('<table class="rapport-tall rapport-flere tabell-fast">')[1].split("</thead>")[0]
        roller = re.findall(r'<span class="kol-rolle">([^<]*)</span>', hode)
        self.assertEqual(roller[:2], ["Nå", "Endring"])
        rad = side.split('<table class="rapport-tall rapport-flere tabell-fast">')[1].split("<tbody>")[1].split("</tr>")[0]
        celler = re.findall(r"<td[^>]*>(.*?)</td>", rad)
        self.assertIn("358,9", celler[1])
        self.assertIn("+160,3", celler[2])
        self.assertIn("137,9", celler[3])

    def test_ingen_automatisk_orddeling_i_navnekolonnen(self):
        """«Justert re-sultat» og «Driftsinn-tekter» ved 390 px."""
        css = fs.RAPPORT_SAMMENLIGNING_CSS
        self.assertNotIn("hyphens:auto", css)
        self.assertNotIn("overflow-wrap:break-word", css)

    def test_forklaringen_nevner_engangsposter_og_strek_og_er_uten_tall(self):
        self.assertIn("engangsposter", fs.RAPPORT_FORKLARING)
        self.assertIn("En strek i en celle", fs.RAPPORT_FORKLARING)

    def test_newsweb_lenken_har_egen_linje_og_trykkflate(self):
        side = self._side([self._q3()])
        self.assertIn('<p class="rapport-meta rapport-kilde"><a href="https://newsweb.oslobors.no/message/1" '
                      'rel="noopener">Kilde: børsmeldingen på NewsWeb</a></p>', side)
        self.assertNotIn(" · <a href=\"https://newsweb", side)
        self.assertRegex(self._css(side), r"\.rapport-kilde a \{[^}]*min-height:44px")

    def test_rutene_har_kilde_uten_tall_og_dato(self):
        side = self._side([self._q3()])
        linje = re.search(r'<p class="tallruter-kilde les">(.*?)</p>', side, re.S).group(1)
        self.assertIsNone(re.search(r"\d", linje.replace('href="/aksjer/AAA/"', "")), linje)
        self.assertIn('href="/metode/"', linje)
        self.assertIn('href="/aksjer/AAA/"', linje)
        self.assertLess(side.index('class="tallruter'), side.index('class="tallruter-kilde'))

    def _tile(self, **felt):
        a = dict(self.A, ex_dato="2026-12-10", betaling_dato="2026-12-17", frekvens="Kvartalsvis")
        a.update(felt)
        return fs._rapport_utbytte_naa(a, "2026-11-26")

    def test_utbetales_viser_datoen_naar_den_er_kjent(self):
        rute = self._tile()
        self.assertIn("<dt>Utbetales</dt><dd>17. des 2026", rute)
        self.assertIn("rundt, kvartalsvis", rute)

    def test_utbetales_viser_frekvensen_uten_kommende_betaling(self):
        for felt in ({"betaling_dato": ""}, {"betaling_dato": "2026-11-20"}, {"ex_dato": ""}):
            rute = self._tile(**felt)
            self.assertIn("<dt>Utbetales</dt><dd>kvartalsvis", rute, felt)
            self.assertNotIn("rundt", rute)

    def test_per_aksje_staar_i_merknaden_ikke_i_verdien(self):
        """«0,04 USD per aksje» ble brutt over to linjer ved 390 px og gjorde rutene ujevne."""
        a = dict(self.A, annonsert_utbytte=0.04, annonsert_ex="2026-12-10", ex_dato="2026-12-10")
        rute = fs._rapport_utbytte_naa(a, "2026-11-26")
        for dd in re.findall(r"<dd>(.*?)</dd>", rute):
            verdi = dd.split('<span class="tallrute-note">')[0]
            self.assertNotIn("per aksje", verdi)

    def test_rapport_agenten_vet_om_engangsposter_og_faste_rader(self):
        tekst = open(os.path.join(_REPO, ".claude", "agents", "rapport.md"), encoding="utf-8").read()
        self.assertIn("Justert resultat", tekst)
        self.assertIn("engangsposter", tekst)


if __name__ == "__main__":
    unittest.main(verbosity=2)
