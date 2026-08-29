#!/usr/bin/env python3
"""
test_sjekk_utdaterte.py — Tester for deteksjon av utdaterte aksjer.

Kjøres uten nettverk og uten tredjepartspakker:

    python scripts/test_sjekk_utdaterte.py

Scenarioene er modellert på faktiske hendelser i prosjektet: ABL→Aqualis
(navneendring), COOL (avnotering), STRO/SNI og VENDA/VEND (duplikater).
"""

import datetime
import unittest

from sjekk_utdaterte import (
    ALVOR_ADVARSEL,
    ALVOR_INFO,
    ALVOR_KRITISK,
    analyser,
    finn_duplikat_data,
    finn_duplikat_navn,
    finn_duplikat_ticker_yf,
    finn_manglende_data,
    navn_likhet,
    normaliser_navn,
    vurder_ticker,
)

IDAG = datetime.date(2026, 8, 8)


def _dato(dager_siden):
    return (IDAG - datetime.timedelta(days=dager_siden)).isoformat()


def _typer(varsler):
    return {v["type"] for v in varsler}


class TestNavnenormalisering(unittest.TestCase):

    def test_fjerner_selskapsform(self):
        self.assertEqual(normaliser_navn("Equinor ASA"), "equinor")
        self.assertEqual(normaliser_navn("Frontline PLC"), "frontline")
        self.assertEqual(normaliser_navn("Hafnia Limited"), "hafnia")
        self.assertEqual(normaliser_navn("ABL Group ASA"), "abl")

    def test_bevarer_aksjeklasse(self):
        # A- og B-aksjer må ikke kollapse til samme streng.
        a = normaliser_navn("Wilh. Wilhelmsen Holding")
        b = normaliser_navn("Wilh. Wilhelmsen Holding B")
        self.assertNotEqual(a, b)

    def test_tomt_navn(self):
        self.assertEqual(normaliser_navn(""), "")
        self.assertEqual(normaliser_navn(None), "")


class TestNavnLikhet(unittest.TestCase):

    def test_identiske_navn_etter_normalisering(self):
        self.assertEqual(navn_likhet("Equinor ASA", "Equinor"), 1.0)
        self.assertEqual(navn_likhet("DNB Bank ASA", "DNB Bank ASA"), 1.0)

    def test_prefiks_regnes_som_treff(self):
        # Yahoo er ofte mer ordrik enn vår katalog uten at selskapet er endret.
        self.assertEqual(navn_likhet("Equinor ASA", "Equinor Energy ASA"), 1.0)

    def test_ekte_navneendring_gir_lav_likhet(self):
        # Den faktiske ABL→Aqualis-hendelsen fra juni 2026.
        self.assertLess(navn_likhet("ABL Group ASA", "Aqualis ASA"), 0.6)

    def test_manglende_navn_roper_ikke_ulv(self):
        self.assertEqual(navn_likhet("Equinor ASA", ""), 1.0)


class TestDuplikater(unittest.TestCase):

    def test_duplikat_ticker_yf(self):
        # STRO/SNI-tilfellet: to oppføringer peker på samme Yahoo-ticker.
        tickere = [
            {"ticker": "STRO", "ticker_yf": "SNI.OL", "navn": "Stolt-Nielsen"},
            {"ticker": "SNI", "ticker_yf": "SNI.OL", "navn": "Stolt-Nielsen"},
            {"ticker": "EQNR", "ticker_yf": "EQNR.OL", "navn": "Equinor ASA"},
        ]
        varsler = finn_duplikat_ticker_yf(tickere)
        self.assertEqual(len(varsler), 1)
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_KRITISK)
        self.assertIn("SNI.OL", varsler[0]["melding"])

    def test_ingen_duplikat_gir_ingen_varsel(self):
        tickere = [
            {"ticker": "EQNR", "ticker_yf": "EQNR.OL"},
            {"ticker": "DNB", "ticker_yf": "DNB.OL"},
        ]
        self.assertEqual(finn_duplikat_ticker_yf(tickere), [])

    def test_identiske_data_oppdages(self):
        aksjer = [
            {"ticker": "VEND", "pris": 10.0, "utbytte_per_aksje": 1.0,
             "52u_hoy": 12.0, "52u_lav": 8.0},
            {"ticker": "VENDA", "pris": 10.0, "utbytte_per_aksje": 1.0,
             "52u_hoy": 12.0, "52u_lav": 8.0},
        ]
        varsler = finn_duplikat_data(aksjer)
        self.assertEqual(len(varsler), 1)
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_KRITISK)

    def test_nullrader_matcher_ikke_hverandre(self):
        # To aksjer uten data skal ikke rapporteres som duplikater av hverandre.
        aksjer = [
            {"ticker": "A", "pris": 0, "utbytte_per_aksje": 0, "52u_hoy": 0, "52u_lav": 0},
            {"ticker": "B", "pris": 0, "utbytte_per_aksje": 0, "52u_hoy": 0, "52u_lav": 0},
        ]
        self.assertEqual(finn_duplikat_data(aksjer), [])

    def test_ulik_kurs_er_ikke_duplikat(self):
        aksjer = [
            {"ticker": "SRBNK", "pris": 148.6, "utbytte_per_aksje": 12.0,
             "52u_hoy": 160.0, "52u_lav": 120.0},
            {"ticker": "SB1NO", "pris": 212.5, "utbytte_per_aksje": 12.0,
             "52u_hoy": 230.0, "52u_lav": 180.0},
        ]
        self.assertEqual(finn_duplikat_data(aksjer), [])


class TestDuplikatNavn(unittest.TestCase):

    def test_samme_navn_pa_to_tickere(self):
        # WALWIL/WAWI-tilfellet slik det faktisk står i katalogen: ulik
        # ticker_yf, identisk navn, og bare den ene leverer data.
        tickere = [
            {"ticker": "WAWI", "ticker_yf": "WAWI.OL", "navn": "Wallenius Wilhelmsen ASA"},
            {"ticker": "WALWIL", "ticker_yf": "WALWIL.OL", "navn": "Wallenius Wilhelmsen ASA"},
        ]
        varsler = finn_duplikat_navn(tickere)
        self.assertEqual(len(varsler), 1)
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_KRITISK)
        self.assertIn("WALWIL", varsler[0]["ticker"])

    def test_navn_som_bare_skiller_pa_selskapsform(self):
        tickere = [
            {"ticker": "A", "ticker_yf": "A.OL", "navn": "Equinor ASA"},
            {"ticker": "B", "ticker_yf": "B.OL", "navn": "Equinor AS"},
        ]
        self.assertEqual(len(finn_duplikat_navn(tickere)), 1)

    def test_aksjeklasser_er_ikke_duplikat(self):
        # A- og B-aksjer er separate papirer og skal ikke flagges.
        tickere = [
            {"ticker": "WWI", "ticker_yf": "WWI.OL", "navn": "Wilh. Wilhelmsen Holding"},
            {"ticker": "WWIB", "ticker_yf": "WWIB.OL", "navn": "Wilh. Wilhelmsen Holding B"},
        ]
        self.assertEqual(finn_duplikat_navn(tickere), [])

    def test_ulike_selskaper_gir_ingen_varsel(self):
        tickere = [
            {"ticker": "EQNR", "ticker_yf": "EQNR.OL", "navn": "Equinor ASA"},
            {"ticker": "DNB", "ticker_yf": "DNB.OL", "navn": "DNB Bank ASA"},
        ]
        self.assertEqual(finn_duplikat_navn(tickere), [])


class TestManglendeData(unittest.TestCase):

    def test_ticker_uten_rad_i_aksjer_json(self):
        tickere = [
            {"ticker": "EQNR", "ticker_yf": "EQNR.OL", "navn": "Equinor ASA"},
            {"ticker": "NOFI", "ticker_yf": "NOFI.OL", "navn": "Norway Royal Salmon ASA"},
        ]
        aksjer = [{"ticker": "EQNR", "pris": 300.0}]
        varsler = finn_manglende_data(tickere, aksjer)
        self.assertEqual(len(varsler), 1)
        self.assertEqual(varsler[0]["ticker"], "NOFI")
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_KRITISK)

    def test_alle_har_data(self):
        tickere = [{"ticker": "EQNR", "ticker_yf": "EQNR.OL", "navn": "Equinor ASA"}]
        aksjer = [{"ticker": "EQNR", "pris": 300.0}]
        self.assertEqual(finn_manglende_data(tickere, aksjer), [])

    def test_tom_aksjeliste_rapporterer_ingenting(self):
        # Uten aksjer.json vet vi ingenting — da skal ikke alt flagges.
        tickere = [{"ticker": "EQNR", "ticker_yf": "EQNR.OL", "navn": "Equinor ASA"}]
        self.assertEqual(finn_manglende_data(tickere, []), [])

    def test_nylig_lagt_til_ticker_er_bare_info(self):
        # JAREN-tilfellet: lagt til i katalogen etter forrige henting, så den
        # mangler data uten at noe er galt.
        tickere = [
            {"ticker": "EQNR", "ticker_yf": "EQNR.OL", "navn": "Equinor ASA"},
            {"ticker": "JAREN", "ticker_yf": "JAREN.OL", "navn": "Jæren Sparebank"},
        ]
        aksjer = [{"ticker": "EQNR", "pris": 300.0}]
        hentelogg = {"tickere": {"EQNR": {"ok": True}}}
        varsler = finn_manglende_data(tickere, aksjer, hentelogg)
        self.assertEqual(len(varsler), 1)
        self.assertEqual(varsler[0]["ticker"], "JAREN")
        self.assertEqual(varsler[0]["type"], "ny_ticker")
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_INFO)

    def test_ticker_som_feiler_i_hentelogg_er_fortsatt_kritisk(self):
        # Står i hentelogget med ok=False → reelt problem, ikke en ny ticker.
        tickere = [{"ticker": "NOFI", "ticker_yf": "NOFI.OL", "navn": "Norway Royal Salmon"}]
        aksjer = [{"ticker": "EQNR", "pris": 300.0}]
        hentelogg = {"tickere": {"EQNR": {"ok": True}, "NOFI": {"ok": False}}}
        varsler = finn_manglende_data(tickere, aksjer, hentelogg)
        self.assertEqual(varsler[0]["type"], "ingen_data")
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_KRITISK)

    def test_uten_hentelogg_beholdes_kritisk(self):
        # Første kjøring, ingen hentelogg ennå — da er den strenge tolkningen
        # riktig, slik at katalogsjekken er nyttig fra dag én.
        tickere = [{"ticker": "NOFI", "ticker_yf": "NOFI.OL", "navn": "Norway Royal Salmon"}]
        aksjer = [{"ticker": "EQNR", "pris": 300.0}]
        varsler = finn_manglende_data(tickere, aksjer, {})
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_KRITISK)


class TestHentestatus(unittest.TestCase):

    def test_vellykket_henting_nullstiller_feiltilstand(self):
        logg = {"ok": True, "vart_navn": "Equinor ASA", "yahoo_navn": "Equinor ASA"}
        forrige = {"sist_ok": _dato(9), "feil_siden": _dato(9)}
        varsler, tilstand = vurder_ticker("EQNR", logg, forrige, IDAG)
        self.assertEqual(varsler, [])
        self.assertEqual(tilstand["sist_ok"], IDAG.isoformat())
        self.assertNotIn("feil_siden", tilstand)

    def test_kort_feil_gir_ingen_varsel(self):
        # Én dags hikke hos Yahoo skal ikke utløse noe.
        logg = {"ok": False, "vart_navn": "Equinor ASA"}
        forrige = {"sist_ok": _dato(1)}
        varsler, _ = vurder_ticker("EQNR", logg, forrige, IDAG)
        self.assertEqual(varsler, [])

    def test_tre_dager_gir_advarsel(self):
        logg = {"ok": False, "vart_navn": "Equinor ASA"}
        forrige = {"sist_ok": _dato(3)}
        varsler, _ = vurder_ticker("EQNR", logg, forrige, IDAG)
        self.assertIn("hentefeil", _typer(varsler))
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_ADVARSEL)

    def test_sju_dager_gir_kritisk_avnoteringsvarsel(self):
        # COOL-tilfellet: avnotert fra Oslo Børs, men pipelinen serverte
        # gamle data videre uten å si fra.
        logg = {"ok": False, "vart_navn": "Cool Company Ltd"}
        forrige = {"sist_ok": _dato(8)}
        varsler, _ = vurder_ticker("COOL", logg, forrige, IDAG)
        self.assertIn("mulig_avnotering", _typer(varsler))
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_KRITISK)

    def test_ukjent_ticker_uten_historikk(self):
        logg = {"ok": False, "vart_navn": "Fantom ASA"}
        varsler, _ = vurder_ticker("ODLD", logg, None, IDAG)
        self.assertIn("aldri_hentet", _typer(varsler))
        # Første dag: bare advarsel — kan være en forbigående nettverksfeil.
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_ADVARSEL)

    def test_aldri_hentet_blir_kritisk_etter_terskelen(self):
        # Ni tickere feilet slik i 16 døgn uten å bli kritiske, fordi
        # alvorligheten var låst til advarsel når sist_ok manglet. Siden
        # GitHub-issuet bare følger kritiske varsler, krevde ingenting
        # handling mens sidene viste gamle tall som ferske.
        logg = {"ok": False, "vart_navn": "DOF Group ASA"}
        forrige = {"feil_siden": _dato(16)}
        varsler, _ = vurder_ticker("DOF", logg, forrige, IDAG)
        self.assertIn("aldri_hentet", _typer(varsler))
        self.assertEqual(varsler[0]["alvorlighet"], ALVOR_KRITISK)
        self.assertIn("16 dager", varsler[0]["melding"])


class TestNavneendring(unittest.TestCase):

    def test_forste_avvik_gir_kun_advarsel(self):
        logg = {"ok": True, "vart_navn": "ABL Group ASA", "yahoo_navn": "Aqualis ASA"}
        varsler, tilstand = vurder_ticker("ABL", logg, {"sist_ok": _dato(1)}, IDAG)
        navnevarsler = [v for v in varsler if v["type"] == "navneendring"]
        self.assertEqual(len(navnevarsler), 1)
        self.assertEqual(navnevarsler[0]["alvorlighet"], ALVOR_ADVARSEL)
        self.assertEqual(tilstand["navn_avvik_siden"], IDAG.isoformat())

    def test_vedvarende_avvik_blir_kritisk(self):
        logg = {"ok": True, "vart_navn": "ABL Group ASA", "yahoo_navn": "Aqualis ASA"}
        forrige = {"sist_ok": _dato(1), "navn_avvik_siden": _dato(3)}
        varsler, _ = vurder_ticker("ABL", logg, forrige, IDAG)
        navnevarsler = [v for v in varsler if v["type"] == "navneendring"]
        self.assertEqual(navnevarsler[0]["alvorlighet"], ALVOR_KRITISK)
        self.assertIn("Aqualis", navnevarsler[0]["melding"])

    def test_navn_som_stemmer_gir_ingen_varsel(self):
        logg = {"ok": True, "vart_navn": "Equinor ASA", "yahoo_navn": "Equinor ASA"}
        varsler, tilstand = vurder_ticker("EQNR", logg, {"sist_ok": _dato(1)}, IDAG)
        self.assertEqual(varsler, [])
        self.assertNotIn("navn_avvik_siden", tilstand)

    def test_avvik_nullstilles_nar_navnet_stemmer_igjen(self):
        logg = {"ok": True, "vart_navn": "Equinor ASA", "yahoo_navn": "Equinor ASA"}
        forrige = {"sist_ok": _dato(1), "navn_avvik_siden": _dato(5)}
        _, tilstand = vurder_ticker("EQNR", logg, forrige, IDAG)
        self.assertNotIn("navn_avvik_siden", tilstand)

    def test_liten_skrivemateforskjell_er_kun_info(self):
        logg = {"ok": True, "vart_navn": "Aker BP ASA", "yahoo_navn": "Aker BP ASA."}
        varsler, _ = vurder_ticker("AKRBP", logg, {"sist_ok": _dato(1)}, IDAG)
        for v in varsler:
            self.assertIn(v["alvorlighet"], (ALVOR_INFO,))


class TestFastfrossetKurs(unittest.TestCase):

    def test_fersk_handel_gir_ingen_varsel(self):
        logg = {"ok": True, "vart_navn": "Equinor ASA", "yahoo_navn": "Equinor ASA",
                "siste_handelsdato": _dato(1)}
        varsler, _ = vurder_ticker("EQNR", logg, {"sist_ok": _dato(1)}, IDAG)
        self.assertNotIn("fastfrosset_kurs", _typer(varsler))

    def test_gammel_handel_gir_advarsel(self):
        logg = {"ok": True, "vart_navn": "Cool Company Ltd", "yahoo_navn": "Cool Company Ltd",
                "siste_handelsdato": _dato(20)}
        varsler, _ = vurder_ticker("COOL", logg, {"sist_ok": _dato(1)}, IDAG)
        self.assertIn("fastfrosset_kurs", _typer(varsler))

    def test_helg_teller_ikke_som_borsdager(self):
        # Fredag → mandag er én børsdag, ikke tre.
        fredag = datetime.date(2026, 8, 7)
        mandag = datetime.date(2026, 8, 10)
        logg = {"ok": True, "vart_navn": "X", "yahoo_navn": "X",
                "siste_handelsdato": fredag.isoformat()}
        varsler, _ = vurder_ticker("X", logg, {"sist_ok": _dato(1)}, mandag)
        self.assertNotIn("fastfrosset_kurs", _typer(varsler))


class TestMarkedsverdi(unittest.TestCase):

    def test_bortfalt_markedsverdi_gir_advarsel(self):
        logg = {"ok": True, "vart_navn": "X ASA", "yahoo_navn": "X ASA", "markedsverdi": 0}
        forrige = {"sist_ok": _dato(1), "sist_markedsverdi": 5_000_000_000}
        varsler, _ = vurder_ticker("X", logg, forrige, IDAG)
        self.assertIn("markedsverdi_borte", _typer(varsler))

    def test_markedsverdi_lagres(self):
        logg = {"ok": True, "vart_navn": "X ASA", "yahoo_navn": "X ASA",
                "markedsverdi": 1_234_000_000}
        _, tilstand = vurder_ticker("X", logg, {"sist_ok": _dato(1)}, IDAG)
        self.assertEqual(tilstand["sist_markedsverdi"], 1_234_000_000)


class TestAnalyserHelhet(unittest.TestCase):

    def _grunnoppsett(self):
        tickere = [
            {"ticker": "EQNR", "ticker_yf": "EQNR.OL", "navn": "Equinor ASA"},
            {"ticker": "ABL", "ticker_yf": "ABL.OL", "navn": "ABL Group ASA"},
        ]
        aksjer = [
            {"ticker": "EQNR", "pris": 300.0, "utbytte_per_aksje": 18.0,
             "52u_hoy": 320.0, "52u_lav": 250.0},
            {"ticker": "ABL", "pris": 15.0, "utbytte_per_aksje": 1.0,
             "52u_hoy": 18.0, "52u_lav": 12.0},
        ]
        hentelogg = {"tickere": {
            "EQNR": {"ok": True, "vart_navn": "Equinor ASA", "yahoo_navn": "Equinor ASA"},
            "ABL": {"ok": True, "vart_navn": "ABL Group ASA", "yahoo_navn": "Aqualis ASA"},
        }}
        return tickere, aksjer, hentelogg

    def test_finner_navneendring_ende_til_ende(self):
        tickere, aksjer, hentelogg = self._grunnoppsett()
        status = {"tickere": {"ABL": {"sist_ok": _dato(1), "navn_avvik_siden": _dato(4)}}}
        varsler, ny_status = analyser(tickere, aksjer, hentelogg, status, IDAG)
        kritiske = [v for v in varsler if v["alvorlighet"] == ALVOR_KRITISK]
        self.assertEqual(len(kritiske), 1)
        self.assertEqual(kritiske[0]["ticker"], "ABL")
        self.assertEqual(kritiske[0]["type"], "navneendring")
        self.assertIn("ABL", ny_status["tickere"])

    def test_varsler_sorteres_med_kritiske_forst(self):
        tickere, aksjer, hentelogg = self._grunnoppsett()
        hentelogg["tickere"]["EQNR"] = {
            "ok": True, "vart_navn": "Equinor ASA", "yahoo_navn": "Equinor ASA.",
        }
        status = {"tickere": {"ABL": {"sist_ok": _dato(1), "navn_avvik_siden": _dato(4)}}}
        varsler, _ = analyser(tickere, aksjer, hentelogg, status, IDAG)
        if len(varsler) > 1:
            self.assertEqual(varsler[0]["alvorlighet"], ALVOR_KRITISK)

    def test_ticker_uten_hentelogg_beholder_tilstand(self):
        # En kjøring der en ticker mangler i loggen skal ikke slette historikken.
        tickere, aksjer, hentelogg = self._grunnoppsett()
        del hentelogg["tickere"]["ABL"]
        status = {"tickere": {"ABL": {"sist_ok": _dato(4), "navn_avvik_siden": _dato(4)}}}
        _, ny_status = analyser(tickere, aksjer, hentelogg, status, IDAG)
        self.assertEqual(ny_status["tickere"]["ABL"]["sist_ok"], _dato(4))

    def test_fjernet_ticker_faller_ut_av_tilstanden(self):
        tickere, aksjer, hentelogg = self._grunnoppsett()
        status = {"tickere": {"GAMMEL": {"sist_ok": _dato(30)}}}
        _, ny_status = analyser(tickere, aksjer, hentelogg, status, IDAG)
        self.assertNotIn("GAMMEL", ny_status["tickere"])

    def test_ren_katalog_gir_ingen_varsler(self):
        tickere, aksjer, hentelogg = self._grunnoppsett()
        hentelogg["tickere"]["ABL"] = {
            "ok": True, "vart_navn": "ABL Group ASA", "yahoo_navn": "ABL Group ASA",
        }
        varsler, _ = analyser(tickere, aksjer, hentelogg, {}, IDAG)
        self.assertEqual(varsler, [])

    def test_tom_hentelogg_finner_fortsatt_katalogduplikater(self):
        tickere = [
            {"ticker": "STRO", "ticker_yf": "SNI.OL"},
            {"ticker": "SNI", "ticker_yf": "SNI.OL"},
        ]
        varsler, _ = analyser(tickere, [], {}, {}, IDAG)
        self.assertIn("duplikat_ticker_yf", _typer(varsler))

    def test_ingen_data_undertrykker_aldri_hentet(self):
        # Begge sjekkene beskriver samme situasjon — kun den kritiske beholdes.
        tickere = [{"ticker": "NOFI", "ticker_yf": "NOFI.OL", "navn": "Norway Royal Salmon"}]
        aksjer = [{"ticker": "EQNR", "pris": 300.0}]
        hentelogg = {"tickere": {"NOFI": {"ok": False, "vart_navn": "Norway Royal Salmon"}}}
        varsler, _ = analyser(tickere, aksjer, hentelogg, {}, IDAG)
        typer = _typer(varsler)
        self.assertIn("ingen_data", typer)
        self.assertNotIn("aldri_hentet", typer)


if __name__ == "__main__":
    unittest.main(verbosity=2)
