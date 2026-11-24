#!/usr/bin/env python3
"""Tester for kvartalsrapport.py og rapportsidene: stdlib unittest, ingen nett.

    python scripts/test_kvartalsrapport.py

Det viktigste her er tallkontrollen. Den skal slippe gjennom tall som står i
kilden (også avrundet, og millioner skrevet som milliarder), og stoppe tall
som er regnet ut, husket eller hentet fra feil tabellrad. Kildetekstene under
er klipp fra ekte rapporter (DNB, Vår Energi og Equinor, tredje kvartal 2026).
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kvartalsrapport as kr  # noqa: E402
import fetch_stocks as fs  # noqa: E402
import vedlikehold as vh  # noqa: E402

ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DNB_KILDE = """# exday kilde
# ticker: DNB
# meldinger: 684467
=== MELDING 684467: Solid results across operations in the Nordics (2026-10-21) ===

DNB delivered profits after tax of NOK 9.8 billion in the third quarter of 2026, which is
a decrease of NOK 839 million, or 7.9 per cent, compared with the corresponding period last year.
Assets under management reached NOK 1,849 billion, up NOK 67.6 billion from the previous quarter.

=== VEDLEGG 334755: Quarterly_Report_DNB_Group_3Q26.pdf ===
                                              3rd quarter      3rd quarter
Amounts in NOK million                            2026            2025
Net interest income                              16,102          16,555
Profit for the period                             9,844          10,684
Return on equity, annualised (per cent)            14.5            15.8
Earnings per share (NOK)                           6.50            7.02
"""

VAR_KILDE = """    Production                               Petroleum revenues
    kboepd                                   USD million



    369                                      3 566
    (376)                                    (3 705)

 - Long term dividend policy of 25-30% of CFFO after tax over the cycles
"""


def _rapport(**kw):
    r = {
        "periode": "2026-Q3", "dato": "2026-10-21", "melding": "684467",
        "tittel": "Solid results across operations in the Nordics",
        "resultat": ("DNB fikk et resultat etter skatt på 9,8 milliarder kroner i tredje kvartal, "
                     "839 millioner eller 7,9 % lavere enn i samme kvartal i fjor. "
                     "Egenkapitalavkastningen var 14,5 %, mot 15,8 % året før."),
        "nokkeltall": [
            {"navn": "Resultat etter skatt", "naa": "9 844 mill. kr", "forrige": "10 684 mill. kr"},
            {"navn": "Egenkapitalavkastning", "naa": "14,5 %", "forrige": "15,8 %"},
        ],
        "utbytte": ("DNB betaler utbytte én gang i året. Rapporten for tredje kvartal sier "
                    "ikke noe om utbyttet for 2026."),
        "plan": "",
        "ellers": [],
        "skrevet": "2026-11-21",
    }
    r.update(kw)
    return r


class TestPerioder(unittest.TestCase):
    def test_tekst_og_kort(self):
        self.assertEqual(kr.periode_tekst("2026-Q3"), "3. kvartal 2026")
        self.assertEqual(kr.periode_tekst("2026-H1"), "1. halvår 2026")
        self.assertEqual(kr.periode_tekst("2026-AR"), "året 2026")
        self.assertEqual(kr.periode_kort("2026-Q3"), "3. kv. 2026")
        self.assertEqual(kr.forrige_periode("2026-Q3"), "2025-Q3")
        self.assertEqual(kr.anker("2026-Q3"), "2026-q3")

    def test_perioden_rett_for(self):
        """«Forrige rapport» er perioden rett før, ikke samme periode i fjor (det er forrige_periode)."""
        self.assertEqual(kr.foregaaende_periode("2026-Q3"), "2026-Q2")
        self.assertEqual(kr.foregaaende_periode("2026-Q1"), "2025-Q4")
        self.assertEqual(kr.foregaaende_periode("2026-H2"), "2026-H1")
        self.assertEqual(kr.foregaaende_periode("2026-H1"), "2025-H2")
        self.assertEqual(kr.foregaaende_periode("2026-AR"), "2025-AR")
        self.assertEqual(kr.foregaaende_periode("2026-X9"), "")
        self.assertEqual(kr.foregaaende_periode(None), "")

    def test_kode_i_tittelen(self):
        self.assertEqual(fs._periode_kode("2026-Q3"), "Q3 2026")
        self.assertEqual(fs._periode_kode("2026-H1"), "H1 2026")
        self.assertEqual(fs._periode_kode("2026-AR"), "2026")


class TestTallITekst(unittest.TestCase):
    def test_aar_dato_og_periode_telles_ikke(self):
        t = kr.tall_i_tekst("I 3. kvartal 2026, lagt fram 21. oktober 2026 (Q3 og 3Q26), "
                            "var resultatet 9,8 mrd.")
        self.assertEqual([x[0] for x in t], ["9,8"])
        self.assertEqual(t[0][3], "mrd")

    def test_selskapsnavn_med_tall(self):
        t = kr.tall_i_tekst("SpareBank 1 SMN tjente 1 234,5 mill.", ["SpareBank 1 SMN"])
        self.assertEqual([(x[0], x[1], x[2], x[3]) for x in t], [("1 234,5", 1234.5, 1, "mill")])

    def test_spenn_og_prosent(self):
        t = kr.tall_i_tekst("25–30 % av kontantstrømmen")
        self.assertEqual([x[1] for x in t], [25.0, 30.0])
        self.assertEqual(t[1][3], "%")

    def test_tusen_skilt_med_mellomrom_er_ikke_et_aarstall(self):
        t = kr.tall_i_tekst("I alt 2 026 millioner")
        self.assertEqual([x[1] for x in t], [2026.0])


class TestKildetall(unittest.TestCase):
    def test_engelsk_og_norsk_skrivemaate(self):
        self.assertEqual(kr._verdier("9,844"), {9844.0})
        self.assertEqual(kr._verdier("1.125"), {1125.0})
        self.assertEqual(kr._verdier("1.125", per_aksje=True), {1125.0, 1.125})
        self.assertEqual(kr._verdier("0.375"), {0.375})
        self.assertEqual(kr._verdier("12,35"), {12.35})
        self.assertEqual(kr._verdier("1,849.5"), {1849.5})
        self.assertEqual(kr._verdier("1.849,5"), {1849.5})
        self.assertEqual(kr._verdier("3 566"), {3566.0})

    def test_prosent_bare_fra_linjer_om_prosent(self):
        k = kr.Kilde(DNB_KILDE)
        self.assertIn(14.5, k.prosent)
        self.assertIn(7.9, k.prosent)
        self.assertNotIn(6.5, k.prosent)  # resultat per aksje, ikke prosent


class TestTallkontroll(unittest.TestCase):
    def test_riktige_tall_slipper_gjennom(self):
        self.assertEqual(kr.tall_uten_kilde(_rapport(), DNB_KILDE, ["DNB Bank ASA"]), [])

    def test_millioner_som_milliarder(self):
        r = _rapport(nokkeltall=[
            {"navn": "Resultat etter skatt", "naa": "9,8 mrd. kr", "forrige": "10,7 mrd. kr"},
            {"navn": "Resultat per aksje", "naa": "6,50 kr", "forrige": "7,02 kr"}])
        self.assertEqual(kr.tall_uten_kilde(r, DNB_KILDE), [])

    def test_millioner_som_milliarder_krever_mrd(self):
        """Uten «mrd.» etter tallet er 9,8 ikke det samme som 9 844."""
        r = _rapport(resultat="Resultatet var 10,7 i kvartalet, et tall uten enhet som ikke står i kilden.")
        self.assertIn(("resultat", "10,7"), kr.tall_uten_kilde(r, DNB_KILDE))

    def test_utregnet_endring_stoppes(self):
        """9 844 mot 10 684 er 7,86 % ned. Kilden sier 7,9; 8 er regnet ut."""
        r = _rapport(resultat="Resultatet falt med 8,4 % til 9,8 milliarder kroner i tredje kvartal "
                              "ifølge rapporten, og egenkapitalavkastningen var 14,5 %.")
        self.assertIn(("resultat", "8,4"), kr.tall_uten_kilde(r, DNB_KILDE))

    def test_prosent_maa_staa_paa_en_prosentlinje(self):
        """6,50 står i kilden, men som kroner per aksje, ikke som prosent."""
        r = _rapport(resultat="Egenkapitalavkastningen var 6,50 % i tredje kvartal, mot 15,8 % i samme "
                              "kvartal i fjor, og resultatet var 9,8 milliarder kroner.")
        self.assertIn(("resultat", "6,50"), kr.tall_uten_kilde(r, DNB_KILDE))

    def test_oppdiktet_tall_stoppes(self):
        r = _rapport(utbytte="Styret foreslår et utbytte på 17,25 kroner per aksje.")
        self.assertIn(("utbytte", "17,25"), kr.tall_uten_kilde(r, DNB_KILDE))


class TestParkontroll(unittest.TestCase):
    def test_samme_linje(self):
        self.assertEqual(kr.par_uten_kilde(_rapport(), DNB_KILDE), [])

    def test_kolonne_over_hverandre(self):
        """Vår Energis nøkkeltallsruter: forrige periode i parentes under."""
        r = {"nokkeltall": [{"navn": "Produksjon", "naa": "369 kboe/d", "forrige": "376 kboe/d"},
                            {"navn": "Inntekter", "naa": "3 566 mill. USD", "forrige": "3 705 mill. USD"}]}
        self.assertEqual(kr.par_uten_kilde(r, VAR_KILDE), [])

    def test_tall_fra_to_rader_stoppes(self):
        r = {"nokkeltall": [{"navn": "Resultat", "naa": "9 844 mill. kr", "forrige": "16 555 mill. kr"}]}
        self.assertEqual([x[0] for x in kr.par_uten_kilde(r, DNB_KILDE)], [0])
        r = {"nokkeltall": [{"navn": "Feil", "naa": "369 kboe/d", "forrige": "3 705 mill. USD"}]}
        self.assertEqual([x[0] for x in kr.par_uten_kilde(r, VAR_KILDE)], [0])


class TestFeltOgSprak(unittest.TestCase):
    I_DAG = "2026-11-21"

    def test_gyldig_oppsummering(self):
        feil, _ = kr.vurder_oppsummering("DNB", _rapport(), DNB_KILDE, ["684467"], self.I_DAG)
        self.assertEqual(feil, [])

    def test_feil_melding_i_kilden(self):
        feil, _ = kr.vurder_oppsummering("DNB", _rapport(melding="999"), DNB_KILDE, ["684467"], self.I_DAG)
        self.assertTrue(any("kilden er hentet for melding" in f for f in feil), feil)

    def test_mangler_og_form(self):
        feil, _ = kr.sjekk_felt(_rapport(periode="Q3-2026", resultat=""), self.I_DAG)
        self.assertTrue(any("«resultat» mangler" in f for f in feil))
        self.assertTrue(any("«periode» må være" in f for f in feil))
        feil, _ = kr.sjekk_felt(_rapport(dato="2026-12-01"), self.I_DAG)
        self.assertTrue(any("fram i tid" in f for f in feil))
        feil, _ = kr.sjekk_felt(_rapport(nokkeltall=[{"navn": "A", "naa": "1"}]), self.I_DAG)
        self.assertTrue(any("skal ha 2–6" in f for f in feil))

    def test_punktum_som_desimaltegn(self):
        feil, _ = kr.sjekk_felt(_rapport(utbytte="Utbyttet er 0.39 dollar per aksje for kvartalet."), self.I_DAG)
        self.assertTrue(any("komma som desimaltegn" in f for f in feil), feil)

    def test_raad_stoppes_vurdering_varsles(self):
        feil, varsler = kr.sjekk_felt(_rapport(
            resultat="Et sterkt kvartal. Vi anbefaler aksjen til alle som vil ha utbytte, og "
                     "resultatet var 9,8 milliarder kroner i tredje kvartal i år."), self.I_DAG)
        self.assertTrue(any("anbefal" in f for f in feil), feil)
        self.assertTrue(any("sterkt" in v for v in varsler), varsler)

    def test_tankestrek_og_vending(self):
        r = _rapport(utbytte="Kort fortalt: DNB betaler én gang i året — rapporten sier ingenting nytt.")
        feil = kr.sjekk_sprak(r)
        self.assertTrue(any("tankestrek" in f for f in feil), feil)
        self.assertTrue(any("Kort fortalt" in f for f in feil), feil)


class TestRapportmeldinger(unittest.TestCase):
    def test_titler(self):
        ja = ["Equinor third quarter 2026 results", "Delårsregnskap 3. kvartal 2026",
              "Måsøval AS Q3 26 Report", "Kvartalsrapport Q3 2026",
              "Borr Drilling Limited - Filing of Interim Financial Report on Form 6-K",
              "Sparebank 68° Nord: Delårsrapport Q3 2026- sterkt resultat"]
        nei = ["Vår Energi: Third quarter 2026 trading update",
               "Invitation to DNB's third quarter presentation, Wednesday, 21 October 2026",
               "Basis swap and AT1 impact Q3 2026",
               "PRESS RELEASE: CHANGED PUBLICATION DATE Q3 2026 RESULTS",
               "Cadeler plc: Notice of Upcoming Q3 2026 Earnings Release and Presentation on 23 November",
               "BW LPG Limited – Q3 2026 Financial Report Release and Earnings Presentation on 26 November",
               "Bahnhof sin delårsrapport for Q3 2026 er publisert i supplement til tilbuddokumentet",
               "Equinor ASA: Key information relating to cash dividend for third quarter 2026."]
        for t in ja:
            self.assertTrue(kr.er_rapporttittel(t), t)
        for t in nei:
            self.assertFalse(kr.er_rapporttittel(t), t)

    def test_feil_meldinger_via_rapportdatoen(self):
        """Lenken i hendelser.json pekte på utbyttemeldinger, påminnelser og
        datterselskaper (køen 21.11.2026). De skal ikke inn, heller ikke via id."""
        def m(mid, tittel):
            return {"messageId": mid, "publishedTime": "2026-11-04T07:00", "title": tittel}
        meldinger = [m(1, "Mowi ASA (OSE: MOWI): Quarterly dividend"),
                     m(2, "Reminder: Presentation of 3rd quarter 2026 accounts"),
                     m(3, "Grameenphone - results for the third quarter 2026"),
                     m(4, "Fremtind Holding-konsernets resultater for tredje kvartal 2026"),
                     m(5, "Sparebanken Norge - resultatpresentasjon tredje kvartal 2026 - fredag 30. oktober"),
                     m(6, "PRESS RELEASE: CMB.TECH ANNOUNCES Q3 2026 RESULTS ON 26/11/2026"),
                     m(7, "ABGSC to publish Q3 2026 Interim Report on 13 October")]
        alle = {str(i) for i in range(1, 8)}
        for ticker, navn in (("MOWI", "Mowi ASA"), ("TEL", "Telenor ASA"),
                             ("MING", "SpareBank 1 SMN"), ("ABG", "ABG Sundal Collier Holding ASA")):
            self.assertEqual(kr.rapportmeldinger(meldinger, alle, ticker, navn), [], ticker)

    def test_egne_rapporter_beholdes(self):
        def m(mid, tittel):
            return {"messageId": mid, "publishedTime": "2026-11-04T07:00", "title": tittel}
        for ticker, navn, tittel in (
                ("ABG", "ABG Sundal Collier Holding ASA", "ABGSC - Q3 2026 Interim Report"),
                ("KOG", "Kongsberg Gruppen ASA", "Q3 2026: KONGSBERG delivers a strong third quarter"),
                ("HAUTO", "Höegh Autoliners ASA",
                 "Höegh Autoliners ASA: Third quarter results and distribution of dividends"),
                ("CMBTO", "CMB.TECH NV", "PRESS RELEASE: CMB.TECH ANNOUNCES Q3 2026 RESULTS"),
                ("POL", "Polaris Media ASA", "3. kvartal 2026: Fortsatt resultatvekst for Polaris Media"),
                ("ITERA", "Itera ASA", "Korreksjon: Delårsrapport 3. kvartal 2026")):
            self.assertEqual(len(kr.rapportmeldinger([m(1, tittel)], {"1"}, ticker, navn)), 1, tittel)

    def test_dnb_via_rapportdatoen(self):
        """DNBs tittel sier ikke hvilket kvartal; lenken i hendelser.json gjør det."""
        meldinger = [{"messageId": 684467, "publishedTime": "2026-10-21T05:30",
                      "title": "Solid results across operations in the Nordics"},
                     {"messageId": 684281, "publishedTime": "2026-10-19T07:13",
                      "title": "Reminder: Invitation to DNB's third quarter presentation"}]
        hendelser = [{"ticker": "DNB", "type": "rapport", "dato": "2026-10-21",
                      "url": "https://newsweb.oslobors.no/message/684467"}]
        self.assertEqual(kr.rapportmeldinger(meldinger), [])
        r = kr.rapportmeldinger(meldinger, kr.hendelse_ider(hendelser, "DNB"))
        self.assertEqual([g["ider"] for g in r], [["684467"]])

    def test_norsk_og_engelsk_samme_dag(self):
        meldinger = [{"messageId": 684945, "publishedTime": "2026-10-28T05:45",
                      "title": "Equinor third quarter 2026 results"},
                     {"messageId": 684944, "publishedTime": "2026-10-28T05:45",
                      "title": "Equinors resultater for tredje kvartal 2026"}]
        r = kr.rapportmeldinger(meldinger)
        self.assertEqual(len(r), 1)
        self.assertEqual(sorted(r[0]["ider"]), ["684944", "684945"])

    def test_venter(self):
        import datetime
        i_dag = datetime.date(2026, 11, 21)
        rapporter = [{"dato": "2026-10-21", "ider": ["684467"], "titler": ["x"]}]
        self.assertEqual(kr.venter([], rapporter, i_dag)["ider"], ["684467"])
        self.assertIsNone(kr.venter([{"melding": "684467", "dato": "2026-10-21"}], rapporter, i_dag))
        self.assertIsNone(kr.venter([], rapporter, datetime.date(2027, 6, 1)))  # for gammel

    def test_vedlikehold_ko(self):
        rm = [{"tickere": ["EQNR"], "dato": "2026-10-28", "id": 684945,
               "tittel": "Equinor third quarter 2026 results"},
              {"tickere": ["ODF", "ODFB"], "dato": "2026-11-05", "id": 1, "tittel": "Odfjell: Q3 results"}]
        h = [{"ticker": "DNB", "dato": "2026-10-21", "type": "rapport",
              "url": "https://newsweb.oslobors.no/message/684467"},
             {"ticker": "DNB", "dato": "2027-02-04", "type": "rapport"}]
        ut = vh.rapporter_uten_oppsummering(rm, h, {}, "2026-10-01", "2026-11-21",
                                            {"ODFB": "ODF"}, {"684467": "Solid results"})
        self.assertEqual([x["ticker"] for x in ut], ["ODF", "EQNR", "DNB"])
        self.assertEqual(ut[2]["tittel"], "Solid results")
        ut = vh.rapporter_uten_oppsummering(rm, h, {"DNB": [{"melding": "684467", "dato": "2026-10-21"}]},
                                            "2026-10-01", "2026-11-21", {"ODFB": "ODF"})
        self.assertNotIn("DNB", [x["ticker"] for x in ut])

    def test_utbyttemeldinger_hører_til_rapporten(self):
        """Vår Energi: rapporten 21.10 sa «USD 400 million»; beløpet per aksje
        (1,368 kr) stod i utbyttemeldingen samme dag, og forrige (1,355 kr) i
        meldingen fra juli."""
        meldinger = [
            {"messageId": 686644, "publishedTime": "2026-11-17T06:00", "title": "Vår Energi ASA: Ex dividend Q3 2026"},
            {"messageId": 684458, "publishedTime": "2026-10-21T05:01", "title": "Vår Energi reports strong financial results"},
            {"messageId": 684450, "publishedTime": "2026-10-21T05:00",
             "title": "Key information relating to cash dividend to be paid by Vår Energi ASA"},
            {"messageId": 678463, "publishedTime": "2026-07-21T05:00",
             "title": "Key information relating to cash dividend to be paid by Vår Energi ASA"},
            {"messageId": 672910, "publishedTime": "2026-05-08T05:00",
             "title": "Key information relating to cash dividend to be paid by Vår Energi ASA"},
        ]
        self.assertEqual(kr.utbyttemeldinger(meldinger, "2026-10-21"), ["684450", "678463"])
        # Equinor melder på norsk og engelsk samme dag: én av dem holder.
        eq = [{"messageId": 684947, "publishedTime": "2026-10-28T05:46",
               "title": "Equinor ASA: Key information relating to cash dividend for third quarter 2026."},
              {"messageId": 684946, "publishedTime": "2026-10-28T05:46",
               "title": "Equinor ASA: Nøkkelinformasjon angående kontantutbytte for tredje kvartal 2026."}]
        self.assertEqual(kr.utbyttemeldinger(eq, "2026-10-28"), ["684947"])
        self.assertEqual(kr.utbyttemeldinger(eq, ""), [])

    def test_utbyttemeldinger_flere_samme_dag_og_engangs_foer(self):
        def m(mid, dag, tittel):
            return {"messageId": mid, "publishedTime": dag + "T07:00", "title": tittel}
        # Gjensidige: ordinært og særutbytte samme dag, begge på engelsk.
        gjf = [m(2, "2026-01-27", "Key information relating to the ordinary cash dividend"),
               m(1, "2026-01-27", "Key information relating to the special cash dividend")]
        self.assertEqual(kr.utbyttemeldinger(gjf, "2026-01-27"), ["2", "1"])
        # Mowi: «Quarterly dividend».
        mowi = [m(685530, "2026-11-04", "Mowi ASA (OSE: MOWI): Quarterly dividend"),
                m(680022, "2026-08-18", "Mowi ASA (OSE: MOWI): Quarterly dividend")]
        self.assertEqual(kr.utbyttemeldinger(mowi, "2026-11-04"), ["685530", "680022"])
        # Frontline: forrige melding var engangsutbyttet, så den ordinære før
        # den tas med også.
        fro = [m(687050, "2026-11-20", "Key information relating to the dividend to be paid by Frontline plc"),
               m(682181, "2026-09-11", "Key information relating to the special one-time dividend"),
               m(681123, "2026-08-28", "Key information relating to the dividend to be paid by Frontline plc"),
               m(678000, "2026-05-28", "Key information relating to the dividend to be paid by Frontline plc")]
        self.assertEqual(kr.utbyttemeldinger(fro, "2026-11-20"), ["687050", "682181", "681123"])

    def test_hovedvedlegg(self):
        dnb = [{"name": "Presentation_3Q26.pdf", "id": 1}, {"name": "Factbook_3Q26.pdf", "id": 2},
               {"name": "Quarterly_Report_DNB_Group_3Q26.pdf", "id": 3}]
        var = [{"name": "Third_quarter_2026_presentation_Var_Energi_ASA.pdf", "id": 4},
               {"name": "Third_quarter_2026_Var_Energi_ASA.pdf", "id": 5}]
        eq = [{"name": "Equinor Financial Statements and Review Third Quarter 2026.pdf", "id": 6},
              {"name": "CFO presentation Third quarter 2026 results.pdf", "id": 7}]
        self.assertEqual(kr.hovedvedlegg(dnb)["id"], 3)
        self.assertEqual(kr.hovedvedlegg(var)["id"], 5)
        self.assertEqual(kr.hovedvedlegg(eq)["id"], 6)
        self.assertIsNone(kr.hovedvedlegg([{"name": "Presentation.pdf", "id": 8}]))


class TestLagring(unittest.TestCase):
    def test_bytter_samme_periode_og_sorterer(self):
        d = tempfile.mkdtemp()
        try:
            kr.lagre("DNB", _rapport(periode="2026-Q2", dato="2026-07-14"), d)
            kr.lagre("DNB", _rapport(), d)
            kr.lagre("DNB", _rapport(resultat="ny tekst"), d)
            alle = kr.les_rapporter(d)
            self.assertEqual([r["periode"] for r in alle["DNB"]], ["2026-Q3", "2026-Q2"])
            self.assertEqual(alle["DNB"][0]["resultat"], "ny tekst")
        finally:
            shutil.rmtree(d)


class TestSider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROT, "data", "aksjer.json"), encoding="utf-8") as f:
            cls.aksjer = json.load(f)["aksjer"]
        cls.rad = {a["ticker"]: a for a in cls.aksjer}

    def test_titler_og_meta_holder_lengden(self):
        for a in self.aksjer:
            for p in ("2026-Q3", "2026-H1", "2026-AR"):
                t = fs.rapportside_tittel(a, {"periode": p})
                self.assertLessEqual(len(t), 60 + 8, t)
                m = fs.rapportside_meta(a, {"periode": p, "dato": "2026-10-21"})
                self.assertLessEqual(len(m), 155, m)

    def test_boks_bare_med_oppsummering(self):
        dnb = self.rad["DNB"]
        self.assertEqual(fs.lag_rapport_boks(dnb, {}), "")
        boks = fs.lag_rapport_boks(dnb, {"DNB": [_rapport()]})
        self.assertIn('href="/aksjer/DNB/rapporter/#2026-q3"', boks)
        self.assertIn("Siste kvartalsrapport: 3. kvartal 2026", boks)

    def test_b_aksjen_lenker_til_a_aksjen(self):
        if "WWIB" not in self.rad:
            self.skipTest("WWIB ikke i katalogen")
        boks = fs.lag_rapport_boks(self.rad["WWIB"], {"WWI": [_rapport()]})
        self.assertIn('href="/aksjer/WWI/rapporter/', boks)

    def test_fanemeny_henger_sammen(self):
        # Uten oppsummering: ingen «Rapporter»-fane.
        uten = fs.lag_aksje_faner("DNB")
        self.assertNotIn("Rapporter", uten)
        self.assertIn('href="#utbytte"', uten)
        # Aksjesiden lenker til rapportsiden, B-aksjen til A-aksjens.
        self.assertIn('href="/aksjer/DNB/rapporter/"', fs.lag_aksje_faner("DNB", "DNB"))
        self.assertIn('href="/aksjer/WWI/rapporter/"', fs.lag_aksje_faner("WWIB", "WWI"))
        # Rapportsiden: fanene går tilbake til aksjesiden, Rapporter er aktiv.
        side = fs._rapportside_html(self.rad["DNB"], [_rapport()], "2026-11-21")
        self.assertIn('href="/aksjer/DNB/#utbytte"', side)
        self.assertIn('aria-current="page">Rapporter</a>', side)

    def test_aksjesiden_har_rapportfanen(self):
        side = fs._aksje_side_html(self.rad["DNB"], "2026-11-21", rapporter={"DNB": [_rapport()]})
        meny = side.split('id="ak-tabnav"')[1].split("</nav>")[0]
        self.assertIn('href="/aksjer/DNB/rapporter/" class="ak-side">Rapporter', meny)
        uten = fs._aksje_side_html(self.rad["DNB"], "2026-11-21")
        self.assertNotIn(">Rapporter<", uten.split('id="ak-tabnav"')[1].split("</nav>")[0])

    def test_tekst_escapes(self):
        side = fs._rapportside_html(self.rad["DNB"], [_rapport(resultat="<script>alert(1)</script>")],
                                    "2026-11-21")
        self.assertNotIn("<script>alert(1)</script>", side)
        self.assertIn("&lt;script&gt;", side)

    def test_side_har_tema_i_head_og_ingen_tankestrek_i_malen(self):
        side = fs._rapportside_html(self.rad["DNB"], [_rapport()], "2026-11-21")
        hode = side.split("</head>")[0]
        self.assertIn("localStorage.getItem('tema')", hode)
        self.assertIn('rel="canonical" href="https://exday.no/aksjer/DNB/rapporter/"', side)
        self.assertNotIn("—", side.split("<body>")[1].split("<footer")[0])

    def test_aksjesiden_viser_boksen(self):
        html_ = fs._aksje_side_html(self.rad["DNB"], "2026-11-21", rapporter={"DNB": [_rapport()]})
        self.assertIn('id="kvartalsrapport"', html_)
        self.assertNotIn('id="kvartalsrapport"',
                         fs._aksje_side_html(self.rad["DNB"], "2026-11-21", rapporter={}))

    def test_generer_og_rydd(self):
        d = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(d, "aksjer", "EQNR", "rapporter"))
            with open(os.path.join(d, "aksjer", "EQNR", "rapporter", "index.html"), "w") as f:
                f.write("gammel")
            skrevet = fs.generer_rapportsider(self.aksjer, d, {"DNB": [_rapport()]}, "2026-11-21")
            self.assertEqual(skrevet, ["DNB"])
            self.assertTrue(os.path.isfile(os.path.join(d, "aksjer", "DNB", "rapporter", "index.html")))
            self.assertFalse(os.path.exists(os.path.join(d, "aksjer", "EQNR", "rapporter")))
        finally:
            shutil.rmtree(d)


def _tall(verdi, enhet="usd"):
    """Det en tolket verdi skal være: (tall som Decimal, normalisert enhet)."""
    from decimal import Decimal
    return Decimal(str(verdi)), enhet


class TestTolkVerdi(unittest.TestCase):
    """Verdiene i `nokkeltall` er tekst skrevet av agenten. Bare det som er ett tall
    med enhet blir tolket, og alt annet gir None, så ingen endring regnes av gjetting."""

    def _les(self, tekst):
        v = kr.tolk_verdi(tekst)
        self.assertIsNotNone(v, tekst)
        return v.verdi, v.enhet

    def test_millioner_og_valuta(self):
        self.assertEqual(self._les("358,9 mill. USD"), _tall(358_900_000))
        self.assertEqual(self._les("2,05 USD"), _tall("2.05"))

    def test_tusenskille_med_vanlig_hardt_og_smalt_mellomrom(self):
        for tekst in ("1 204 mill. kr", "1\u00a0204 mill. kr", "1\u202f204 mill. kr"):
            self.assertEqual(self._les(tekst), _tall(1_204_000_000, "nok"), repr(tekst))
        self.assertEqual(self._les("84 100 USD per dag"), _tall(84100, "usd per dag"))

    def test_milliarder_og_millioner_er_samme_beloep(self):
        self.assertEqual(self._les("5,6 mrd. kr"), self._les("5 600 mill. kr"))
        self.assertEqual(self._les("20 tusen kr"), _tall(20000, "nok"))

    def test_valutaene_skrives_likt(self):
        self.assertEqual(self._les("1,30 kr")[1], self._les("1,30 NOK")[1])
        self.assertEqual(self._les("1,30 kroner")[1], "nok")
        self.assertEqual(self._les("1,30 dollar")[1], "usd")
        self.assertNotEqual(self._les("1,30 USD")[1], self._les("1,30 EUR")[1])

    def test_prosent(self):
        v = kr.tolk_verdi("12,5 %")
        self.assertTrue(v.prosent)
        self.assertEqual(self._les("12,5 prosent"), self._les("12,5 %"))

    def test_negative_tall_og_underskudd(self):
        self.assertEqual(self._les("\u22125,2 mill. USD"), _tall(-5_200_000))
        self.assertEqual(self._les("-5,2 %"), _tall("-5.2", "%"))
        self.assertEqual(self._les("+5,2 %"), _tall("5.2", "%"))
        self.assertEqual(self._les("underskudd på 29,5 mill. USD"), _tall(-29_500_000))
        self.assertEqual(self._les("29,5 mill. USD underskudd"), _tall(-29_500_000))
        # Underskudd og minus er ikke to minus.
        self.assertEqual(self._les("underskudd \u22125 mill. kr"), _tall(-5_000_000, "nok"))

    def test_det_som_ikke_er_ett_tall_gir_none(self):
        for tekst in ("underskudd", "ca. 12 mrd.", "rundt 12 %", "12 til 14 %", "n/a", "", None,
                      "USD/foe", "5 6000 kr", "mill. USD"):
            self.assertIsNone(kr.tolk_verdi(tekst), repr(tekst))


class TestEndring(unittest.TestCase):
    def test_prosent_endring(self):
        e = kr.endring("358,9 mill. USD", "137,9 mill. USD")
        self.assertEqual((e["type"], str(e["verdi"])), ("prosent", "160.3"))
        e = kr.endring("2,05 USD", "0,79 USD")
        self.assertEqual(str(e["verdi"]), "159.5")

    def test_prosentpoeng_for_tall_i_prosent(self):
        e = kr.endring("14,5 %", "15,8 %")
        self.assertEqual((e["type"], str(e["verdi"]), e["desimaler"]), ("pp", "-1.3", 1))
        # Desimalene følger tallene: to desimaler inn, to ut.
        e = kr.endring("12,35 %", "12,10 %")
        self.assertEqual((str(e["verdi"]), e["desimaler"]), ("0.25", 2))
        # Også fra et negativt grunnlag: forskjellen i poeng trenger ikke positivt tall.
        self.assertEqual(str(kr.endring("2,0 %", "-1,5 %")["verdi"]), "3.5")

    def test_mrd_mot_mill_er_samme_beloep(self):
        self.assertEqual(str(kr.endring("5,6 mrd. kr", "5 600 mill. kr")["verdi"]), "0.0")
        self.assertEqual(str(kr.endring("6,6 mrd. kr", "5 600 mill. kr")["verdi"]), "17.9")

    def test_ulike_enheter_gir_ingen_endring(self):
        self.assertIsNone(kr.endring("1,30 USD", "1,30 NOK"))
        self.assertIsNone(kr.endring("12,5 %", "12,5 mill. kr"))
        # Samme valuta, men et resultat mot et beløp per aksje er ikke samme størrelse.
        self.assertIsNone(kr.endring("5 mill. kr", "5 kr"))
        self.assertIsNone(kr.endring("84 100 USD per dag", "84 100 USD"))

    def test_kan_ikke_tolkes_gir_ingen_endring(self):
        self.assertIsNone(kr.endring("ca. 12 mrd. kr", "10 mrd. kr"))
        self.assertIsNone(kr.endring("12 mrd. kr", ""))
        self.assertIsNone(kr.endring(None, "12 mrd. kr"))

    def test_grunnlaget_maa_vaere_positivt(self):
        """En endring fra underskudd er ikke en prosent, og null har ingen prosent."""
        self.assertIsNone(kr.endring("10 mill. kr", "underskudd på 5 mill. kr"))
        self.assertIsNone(kr.endring("10 mill. kr", "0 mill. kr"))
        self.assertIsNone(kr.endring("underskudd 3 mill. kr", "4 mill. kr"))   # til underskudd
        self.assertIsNone(kr.endring("-3 mill. kr", "-4 mill. kr"))
        self.assertEqual(str(kr.endring("0 mill. kr", "4 mill. kr")["verdi"]), "-100.0")

    def test_avrunding_gaar_opp_ved_halvt(self):
        """1,25 blir 1,3, ikke 1,2 som round() gir."""
        self.assertEqual(str(kr.endring("101,25 mill. kr", "100 mill. kr")["verdi"]), "1.3")


def _r(periode, rader, dato=None):
    """En rapport med bare det serien trenger. rader er (navn, nå)."""
    return {"periode": periode, "dato": dato or f"{periode[:4]}-{int(periode[-1]) * 3:02d}-20",
            "nokkeltall": [{"navn": n, "naa": v, "forrige": "1"} for n, v in rader]}


class TestSerie(unittest.TestCase):
    def test_bare_identiske_navn_i_minst_to_rapporter(self):
        liste = [_r("2026-Q3", [("Resultat etter skatt", "10 mill. kr"), ("Bare her", "1 kr")]),
                 _r("2026-Q2", [("Resultat etter skatt", "8 mill. kr"), ("Bare i den", "2 kr")])]
        s = kr.serie(liste)
        self.assertEqual([r["navn"] for r in s["rader"]], ["Resultat etter skatt"])
        self.assertEqual([k["periode"] for k in s["kolonner"]], ["2026-Q3", "2026-Q2"])

    def test_ingen_uklar_matching(self):
        liste = [_r("2026-Q3", [("Resultat etter skatt", "10 mill. kr")]),
                 _r("2026-Q2", [("Resultat til aksjonærene", "8 mill. kr")])]
        self.assertIsNone(kr.serie(liste))

    def test_trim_og_casefold_men_ingenting_mer(self):
        liste = [_r("2026-Q3", [("Resultat per aksje", "2 kr")]),
                 _r("2026-Q2", [("  resultat PER aksje ", "1 kr")])]
        s = kr.serie(liste)
        self.assertEqual(s["rader"][0]["navn"], "Resultat per aksje")   # navnet fra den nyeste
        self.assertEqual([c["tekst"] for c in s["rader"][0]["celler"]], ["2 kr", "1 kr"])
        # Et annet ord, en ekstra bokstav eller et annet skilletegn er ikke samme tall.
        for annet in ("Resultat pr. aksje", "Resultat per aksjer", "Resultat-per-aksje"):
            self.assertIsNone(kr.serie([_r("2026-Q3", [("Resultat per aksje", "2 kr")]),
                                        _r("2026-Q2", [(annet, "1 kr")])]), annet)

    def test_ingen_serie_uten_to_rapporter(self):
        self.assertIsNone(kr.serie([_r("2026-Q3", [("A", "1 kr")])]))
        self.assertIsNone(kr.serie([]))
        self.assertIsNone(kr.serie(None))

    def test_opptil_seks_kolonner_nyeste_foerst(self):
        perioder = ["2026-Q3", "2026-Q2", "2026-Q1", "2025-Q4", "2025-Q3", "2025-Q2", "2025-Q1"]
        liste = [_r(p, [("A", f"{i + 1} mill. kr")]) for i, p in enumerate(perioder)]
        s = kr.serie(liste)
        self.assertEqual([k["periode"] for k in s["kolonner"]], perioder[:6])
        self.assertEqual(len(s["rader"][0]["celler"]), 6)

    def test_raden_telles_blant_de_viste_kolonnene(self):
        """Et navn som står i den nyeste og i den sjuende, men ikke i noen av de fem mellom, gir ingen rad:
        tabellen ville vist ett tall på en rad som skal vise en serie."""
        liste = [_r("2026-Q3", [("A", "1 kr")])] + [_r(p, [("B", "1 kr")]) for p in
                                                   ("2026-Q2", "2026-Q1", "2025-Q4", "2025-Q3")]
        liste += [_r("2025-Q2", [("C", "1 kr")]), _r("2025-Q1", [("A", "1 kr")])]
        s = kr.serie(liste)
        self.assertEqual([r["navn"] for r in s["rader"]], ["B"])

    def test_manglende_tall_er_none_og_gir_ingen_endring_over_hullet(self):
        liste = [_r("2026-Q3", [("A", "30 mill. kr")]),
                 _r("2026-Q2", [("B", "1 kr")]),
                 _r("2026-Q1", [("A", "20 mill. kr")]),
                 _r("2025-Q4", [("A", "10 mill. kr")])]
        a = next(r for r in kr.serie(liste)["rader"] if r["navn"] == "A")
        self.assertEqual([c["tekst"] for c in a["celler"]], ["30 mill. kr", None, "20 mill. kr", "10 mill. kr"])
        self.assertIsNone(a["celler"][0]["endring"])        # Q2 mangler: ingenting å regne mot
        self.assertIsNone(a["celler"][1]["endring"])
        self.assertEqual(str(a["celler"][2]["endring"]["verdi"]), "100.0")   # Q1 mot Q4

    def test_endring_bare_mot_perioden_rett_foer(self):
        # 2026-Q3 og 2026-Q1: et kvartal mangler, så Q3 har ingen «forrige rapport».
        liste = [_r("2026-Q3", [("A", "30 mill. kr")]), _r("2026-Q1", [("A", "20 mill. kr")])]
        celler = kr.serie(liste)["rader"][0]["celler"]
        self.assertEqual([c["tekst"] for c in celler], ["30 mill. kr", "20 mill. kr"])
        self.assertIsNone(celler[0]["endring"])
        # Kvartalsskiftet over nyttår er rett før: 2026-Q1 mot 2025-Q4.
        celler = kr.serie([_r("2026-Q1", [("A", "30 mill. kr")]), _r("2025-Q4", [("A", "20 mill. kr")])])["rader"][0]["celler"]
        self.assertEqual(str(celler[0]["endring"]["verdi"]), "50.0")

    def test_tom_celle_er_ikke_et_tall(self):
        liste = [_r("2026-Q3", [("A", "")]), _r("2026-Q2", [("A", "1 kr")])]
        self.assertIsNone(kr.serie(liste))   # bare ett tall, så ingen serie

    def test_forrige_rapport_er_bare_perioden_rett_foer(self):
        q3, q2, q1 = _r("2026-Q3", []), _r("2026-Q2", []), _r("2026-Q1", [])
        self.assertIs(kr.forrige_rapport([q3, q2, q1], q3), q2)
        self.assertIsNone(kr.forrige_rapport([q3, q1], q3))
        self.assertIsNone(kr.forrige_rapport([q3], q3))
        self.assertIsNone(kr.forrige_rapport([_r("2026-H2", []), _r("2026-Q2", [])], _r("2026-H2", [])))

    def test_mot_forrige_tar_bare_identiske_navn(self):
        ny = _r("2026-Q3", [("A", "30 mill. kr"), ("B", "5 mill. kr"), ("C", "7 USD")])
        gammel = _r("2026-Q2", [("a", "20 mill. kr"), ("B ekstra", "1 mill. kr"), ("C", "7 NOK")])
        m = kr.mot_forrige(ny, gammel)
        self.assertEqual(sorted(m), ["a", "c"])
        self.assertEqual(str(m["a"]["endring"]["verdi"]), "50.0")
        self.assertIsNone(m["c"]["endring"])        # USD mot NOK
        self.assertEqual(kr.mot_forrige(ny, None), {})


class TestSerievarsel(unittest.TestCase):
    """`--skriv` varsler (stopper ikke) når en rad ikke lar seg lese som en serie."""

    def test_samme_navn_annen_valuta(self):
        v = kr.serie_varsler(_r("2026-Q3", [("Resultat per aksje", "2,05 USD")]),
                             _r("2026-Q2", [("Resultat per aksje", "0,79 NOK")]))
        self.assertEqual(len(v), 1)
        self.assertIn("«Resultat per aksje»", v[0])
        self.assertIn("2. kv. 2026", v[0])
        self.assertIn("kan ikke endringen regnes ut", v[0])
        self.assertIn("henger ikke sammen", v[0])

    def test_samme_navn_annen_skala_regnes_om_men_varsles(self):
        v = kr.serie_varsler(_r("2026-Q3", [("Inntekter", "1,2 mrd. USD")]),
                             _r("2026-Q2", [("Inntekter", "980 mill. USD")]))
        self.assertEqual(len(v), 1)
        self.assertIn("regnes om", v[0])
        self.assertNotIn("kan ikke", v[0])

    def test_beloep_mot_resultat_kan_ikke_regnes(self):
        v = kr.serie_varsler(_r("2026-Q3", [("Utbytte", "1,30 kr")]), _r("2026-Q2", [("Utbytte", "95 mill. kr")]))
        self.assertEqual(len(v), 1)
        self.assertIn("kan ikke endringen regnes ut", v[0])

    def test_samme_enhet_gir_ingen_varsler(self):
        self.assertEqual(kr.serie_varsler(_r("2026-Q3", [("Inntekter", "1,2 mrd. kr")]),
                                          _r("2026-Q2", [("Inntekter", "1,1 mrd. NOK")])), [])
        self.assertEqual(kr.serie_varsler(_r("2026-Q3", [("A", "10 mill. kr")]),
                                          _r("2026-Q2", [("A", "underskudd på 5 mill. kr")])), [])

    def test_navn_som_ligner_varsles_som_spoersmaal(self):
        v = kr.serie_varsler(_r("2026-Q3", [("Utbytte per aksje", "1,30 USD")]),
                             _r("2026-Q2", [("Utbytte pr. aksje", "0,95 USD")]))
        self.assertEqual(len(v), 1)
        self.assertIn("ligner på «Utbytte pr. aksje»", v[0])
        self.assertIn("nøyaktig samme navn", v[0])
        # Et ord lagt til eller tatt bort ligner også.
        self.assertEqual(len(kr.serie_varsler(_r("2026-Q3", [("Inntekter skipsfart", "1 kr")]),
                                              _r("2026-Q2", [("Inntekter skipsfart (TCE)", "1 kr")]))), 1)

    def test_identisk_navn_og_to_ulike_tall_gir_ingen_varsel(self):
        """«Resultat før skatt» og «Resultat etter skatt» står i begge rapportene: to tall, ikke ett med to navn."""
        rader = [("Resultat før skatt", "9 mill. kr"), ("Resultat etter skatt", "7 mill. kr")]
        self.assertEqual(kr.serie_varsler(_r("2026-Q3", rader), _r("2026-Q2", rader)), [])

    def test_navn_som_ikke_ligner_gir_ingen_varsel(self):
        self.assertEqual(kr.serie_varsler(_r("2026-Q3", [("Inntekter", "1 kr")]),
                                          _r("2026-Q2", [("Resultat", "1 kr")])), [])
        self.assertEqual(kr.serie_varsler(_r("2026-Q3", [("Resultat etter skatt", "1 kr")]),
                                          _r("2026-Q2", [("Kontantstrøm fra driften", "1 kr")])), [])

    def test_ny_rad_er_greit(self):
        self.assertEqual(kr.serie_varsler(_r("2026-Q3", [("A", "1 kr"), ("Helt ny rad", "2 kr")]),
                                          _r("2026-Q2", [("A", "1 kr")])), [])

    def test_ingen_forrige_rapport_gir_ingen_varsler(self):
        self.assertEqual(kr.serie_varsler(_r("2026-Q3", [("A", "1 kr")]), None), [])

    def test_varslene_stopper_ikke_lagringen(self):
        """vurder_oppsummering gir dem i `varsler`, aldri i `feil`."""
        rapport = _rapport(nokkeltall=[
            {"navn": "Resultat etter skatt", "naa": "9,8 mrd. kr", "forrige": "10 684 mill. kr"},
            {"navn": "Egenkapitalavkastning", "naa": "14,5 %", "forrige": "15,8 %"}])
        forrige = _r("2026-Q2", [("Resultat etter skatt", "9 000 mill. kr")])
        feil0, varsler0 = kr.vurder_oppsummering("DNB", rapport)
        feil, varsler = kr.vurder_oppsummering("DNB", rapport, forrige=forrige)
        self.assertEqual(feil, feil0)
        self.assertEqual(len(varsler), len(varsler0) + 1)
        self.assertTrue(any("regnes om" in v for v in varsler))

    def test_forrige_lagrede_er_den_nyeste_eldre_og_aldri_samme_periode(self):
        d = tempfile.mkdtemp()
        try:
            kr.lagre("DNB", _rapport(periode="2026-Q1", dato="2026-04-20"), d)
            kr.lagre("DNB", _rapport(periode="2026-Q2", dato="2026-07-14"), d)
            kr.lagre("DNB", _rapport(periode="2026-Q3", dato="2026-10-21"), d)
            ny = _rapport(periode="2026-Q3", dato="2026-10-21")
            self.assertEqual(kr.forrige_lagrede("DNB", ny, d)["periode"], "2026-Q2")
            eldst = _rapport(periode="2026-Q1", dato="2026-04-20")
            self.assertIsNone(kr.forrige_lagrede("DNB", eldst, d))
            self.assertIsNone(kr.forrige_lagrede("EQNR", ny, d))
        finally:
            shutil.rmtree(d)


class TestLagrede(unittest.TestCase):
    def test_alle_lagrede_bestaar_form_og_sprak(self):
        """Det CI kjører med --sjekk: en håndredigert fil skal ikke slippe gjennom."""
        for ticker, liste in kr.les_rapporter().items():
            for r in liste:
                feil, _ = kr.vurder_oppsummering(ticker, r)
                self.assertEqual(feil, [], f"{ticker} {r.get('periode')}")


if __name__ == "__main__":
    unittest.main(verbosity=1)
