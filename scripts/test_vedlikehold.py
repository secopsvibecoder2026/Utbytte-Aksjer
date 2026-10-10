#!/usr/bin/env python3
"""Tester for vedlikehold.py — klassifisering og oppsummering, uten nett.

Titlene er ekte NewsWeb-titler fra 30.09–09.10.2026. Hvert mønster skal ha et
treff det ble skrevet for, og en tittel det ikke skal treffe.
"""
import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vedlikehold as v  # noqa: E402

UTC = datetime.timezone.utc


def melding(utsteder, tittel, kategori=1010, dato="2026-10-02T08:00:00Z", mid=1):
    return {"issuerSign": utsteder, "issuerName": f"{utsteder} ASA", "title": tittel,
            "publishedTime": dato, "messageId": mid,
            "category": [{"id": kategori, "category_en": "x"}]}


KATALOG = {"AKVA": ["AKVA"], "AQUA": ["AQUA"], "ELMRA": ["ELMRA"], "AKER": ["AKER"],
           "ODF": ["ODF", "ODFB"], "TORM": ["TORM"]}


class TestUtAvKatalogen(unittest.TestCase):
    def test_anbefalt_bud_er_mulig_ut(self):
        r = v.klassifiser([melding("AKVA", "AKVA group ASA: Agreement between AKVA group and "
                                   "Yanmar on a recommended voluntary cash offer for all "
                                   "shares in AKVA group")], KATALOG)
        self.assertEqual([f["utsteder"] for f in r["ut_mulig"]], ["AKVA"])
        self.assertEqual(r["ut_vedtatt"], [])

    def test_siste_handelsdag_er_avgjort(self):
        r = v.klassifiser([melding("AKER", "Aker BioMarine: Last day of trading")], KATALOG)
        self.assertEqual(len(r["ut_vedtatt"]), 1)

    def test_kjoperen_i_en_fusjon_er_ikke_paa_vei_ut(self):
        # Aker kjøpte Aker BioMarine. Den første versjonen av mønsteret merket
        # Aker selv som avgjort ut.
        r = v.klassifiser([
            melding("AKER", "Aker ASA: Conditions for completion of merger with Aker "
                    "BioMarine satisfied"),
            melding("AKER", "Aker ASA: Merger with Aker BioMarine completed", mid=2)], KATALOG)
        self.assertEqual(r["ut_vedtatt"], [])

    def test_emisjon_er_ikke_et_bud(self):
        r = v.klassifiser([
            melding("TORM", "TORM plc announces secondary public offering of its class A "
                    "common shares by a selling shareholder"),
            melding("AKER", "Mutares announces results of partial repurchase offer for "
                    "outstanding Nordic Bond 2023/2027", mid=2)], KATALOG)
        self.assertEqual(r["ut_mulig"], [])

    def test_b_aksjen_folger_utstederen(self):
        r = v.klassifiser([melding("ODF", "Odfjell SE: Last day of trading")], KATALOG)
        self.assertEqual(r["ut_vedtatt"][0]["tickere"], ["ODF", "ODFB"])


class TestMarkedOgStans(unittest.TestCase):
    def test_flytting_til_growth_fanges(self):
        r = v.klassifiser([melding("AQUA", "Aqualis ASA: Initiates the process of re-listing "
                                   "to Euronext Growth Oslo", kategori=1104)], KATALOG)
        self.assertEqual([f["utsteder"] for f in r["marked"]], ["AQUA"])

    def test_obligasjonslan_er_ikke_markedsbytte(self):
        r = v.klassifiser([melding("AKER", "Euronext Oslo Børs – Aker ASA - Received "
                                   "application for listing of bonds")], KATALOG)
        self.assertEqual(r["marked"], [])

    def test_handelsstans_paa_kategori(self):
        r = v.klassifiser([melding("AKVA", "OSLO BØRS – TRADING SUSPENSION", kategori=1202)],
                          KATALOG)
        self.assertEqual(len(r["handelsstans"]), 1)


class TestInnIKatalogen(unittest.TestCase):
    def test_ny_notering_utenfor_katalogen(self):
        r = v.klassifiser([melding("VLCC", "Volare Shipping Ltd.: First Day of Trading on "
                                   "Euronext Growth Oslo and Publication of Information "
                                   "Document", kategori=1103)], KATALOG)
        self.assertEqual([f["utsteder"] for f in r["nye_noteringer"]], ["VLCC"])

    def test_obligasjoner_er_ikke_nye_aksjer(self):
        r = v.klassifiser([
            melding("NPRO", "Euronext Oslo Børs – Norwegian Property ASA - Received "
                    "application for listing of bonds"),
            melding("-", "Euronext Oslo Børs - Norges Bank - Received application for listing "
                    "of central bank certificate", kategori=1207, mid=2)], KATALOG)
        self.assertEqual(r["nye_noteringer"], [])

    def test_utbyttebetaler_utenfor_katalogen(self):
        r = v.klassifiser([
            melding("PPG", "Ex dividend NOK 2.5000 today", kategori=1101, mid=1),
            melding("PPG", "Ex utbytte NOK 2.5000 i dag", kategori=1101, mid=2),
            melding("DVD", "Deep Value Driller AS - EX. DIVIDEND NOK 20.60 TODAY",
                    kategori=1101, mid=3)], KATALOG, euronext_symboler={"PPG"})
        k = {x["utsteder"]: x for x in r["utbytte_utenfor_katalogen"]}
        self.assertEqual(k["PPG"]["antall"], 2)
        self.assertTrue(k["PPG"]["pa_euronext"])
        self.assertFalse(k["DVD"]["pa_euronext"])
        self.assertEqual(r["utbytte_utenfor_katalogen"][0]["utsteder"], "PPG")

    def test_utbytte_fra_egen_aksje_er_ikke_kandidat(self):
        r = v.klassifiser([melding("AKVA", "AKVA: Key information relating to the cash "
                                   "dividend")], KATALOG)
        self.assertEqual(r["utbytte_utenfor_katalogen"], [])

    def test_renteregulering_er_ikke_utbytte(self):
        r = v.klassifiser([melding("SBNOR", "SBNOR - Dividend-linked interest adjustment",
                                   kategori=1105)], KATALOG)
        self.assertEqual(r["utbytte_utenfor_katalogen"], [])

    def test_ukjent_euronext_er_none_ikke_false(self):
        r = v.klassifiser([melding("PPG", "Ex dividend NOK 2.5000 today")], KATALOG)
        self.assertIsNone(r["utbytte_utenfor_katalogen"][0]["pa_euronext"])


class TestPerioder(unittest.TestCase):
    def test_deles_i_biter_paa_tre_dager(self):
        d = datetime.date
        self.assertEqual(v.perioder(d(2026, 10, 1), d(2026, 10, 7)),
                         [(d(2026, 10, 1), d(2026, 10, 3)), (d(2026, 10, 4), d(2026, 10, 6)),
                          (d(2026, 10, 7), d(2026, 10, 7))])


class TestKjoringer(unittest.TestCase):
    def test_kansellert_er_ikke_feil(self):
        p = v.oppsummer_kjoringer([
            {"name": "Oppdater kurspriser", "conclusion": "cancelled", "id": 1,
             "created_at": "2026-10-09T08:00:00Z"},
            {"name": "Oppdater kurspriser", "conclusion": "success", "id": 2,
             "created_at": "2026-10-09T08:15:00Z"},
            {"name": "Tester", "conclusion": "failure", "id": 3,
             "created_at": "2026-10-09T09:00:00Z"}])
        self.assertEqual(p["Oppdater kurspriser"]["feilet"], [])
        self.assertEqual(p["Oppdater kurspriser"]["utfall"], {"cancelled": 1, "success": 1})
        self.assertEqual(p["Oppdater kurspriser"]["siste"]["id"], 2)
        self.assertEqual([f["id"] for f in p["Tester"]["feilet"]], [3])


class TestFerskhet(unittest.TestCase):
    def test_fredagens_tall_er_ikke_gamle_paa_lordag(self):
        naa = datetime.datetime(2026, 10, 10, 9, 0, tzinfo=UTC)   # lørdag
        f = v.ferskhet("2026-10-09T20:32:31Z", naa, v.DATAJOBB_TIDER)
        self.assertFalse(f["gammel"])
        self.assertEqual(f["timer"], 12.5)

    def test_uteblitt_kjoring_flagges(self):
        # Onsdag 14:00: 07:00-kjøringen skulle vært ferdig for lengst.
        naa = datetime.datetime(2026, 10, 7, 14, 0, tzinfo=UTC)
        self.assertTrue(v.ferskhet("2026-10-06T16:40:00Z", naa, v.DATAJOBB_TIDER)["gammel"])

    def test_slakk_for_forsinket_kjoring(self):
        # 10:00-kjøringen er ennå innenfor de tre timene GitHub kan forsinke den.
        naa = datetime.datetime(2026, 10, 7, 12, 0, tzinfo=UTC)
        self.assertFalse(v.ferskhet("2026-10-07T07:40:00Z", naa, v.DATAJOBB_TIDER)["gammel"])

    def test_uten_tidsstempel_ingen_pastand(self):
        f = v.ferskhet(None, datetime.datetime(2026, 10, 7, tzinfo=UTC), v.DATAJOBB_TIDER)
        self.assertIsNone(f["gammel"])


class TestEtterslep(unittest.TestCase):
    def test_nettstedet_bak_repoet(self):
        self.assertEqual(v.etterslep("2026-10-09T20:32:31Z", "2026-10-09T16:32:31Z"), 4.0)

    def test_nettstedet_foran_er_null(self):
        # Klonen kan være eldre enn siste deploy; det er ikke et etterslep.
        self.assertEqual(v.etterslep("2026-10-09T16:00:00Z", "2026-10-09T20:00:00Z"), 0.0)

    def test_manglende_tid_er_ukjent(self):
        self.assertIsNone(v.etterslep("2026-10-09T16:00:00Z", None))


class TestTekst(unittest.TestCase):
    def test_uten_nett_rapport_kan_skrives(self):
        r = v.kjor(3, uten_nett=True,
                   naa=datetime.datetime(2026, 10, 10, 9, 0, tzinfo=UTC))
        self.assertNotIn("newsweb", r)
        self.assertIn("== Data", v.som_tekst(r))

    def test_newsweb_som_feilet_sies_rett_ut(self):
        r = v.kjor(3, uten_nett=True,
                   naa=datetime.datetime(2026, 10, 10, 9, 0, tzinfo=UTC))
        r["newsweb"] = None
        self.assertIn("ingenting er avgjort", v.som_tekst(r))


if __name__ == "__main__":
    unittest.main()
