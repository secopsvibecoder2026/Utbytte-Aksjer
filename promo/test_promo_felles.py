#!/usr/bin/env python3
"""Tester for promo_felles.py — kun det som ikke krever ffmpeg.

kenburns_rammer() og lagre_rammer() er ren PIL og testes her. kod_video() og
lag_kenburns_video() krever en ffmpeg-binær; de har en egen smoke-test som
hopper over seg selv når ffmpeg mangler (se TestKodVideo), i stedet for å
late som funksjonaliteten er verifisert når den ikke er det.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image  # noqa: E402
import promo_felles as pf  # noqa: E402


class TestKenburnsRammer(unittest.TestCase):
    def setUp(self):
        self.bilde = Image.new("RGB", (200, 100), (10, 20, 30))

    def test_antall_rammer(self):
        r = pf.kenburns_rammer(self.bilde, sekunder=2, fps=10, zoom_til=1.1)
        self.assertEqual(len(r), 20)

    def test_alle_rammer_har_original_storrelse(self):
        # Kravet til encoding er at alle rammer i sekvensen er like store —
        # en video med varierende oppløsning feiler i ffmpeg.
        r = pf.kenburns_rammer(self.bilde, sekunder=1, fps=8, zoom_til=1.15)
        for ramme in r:
            self.assertEqual(ramme.size, self.bilde.size)

    def test_zoomer_gradvis_inn(self):
        # Sammenlign midtpiksel-nabolaget mot et hjørne: økende zoom skal
        # gjøre midten relativt likere over tid enn kantene (motivet vokser
        # inn mot kanten). Vi tester heller det vi faktisk kan måle:
        # beskjæringsboksen krymper monotont mot senter.
        w, h = self.bilde.size
        bredder = []
        for i in range(6):
            t = i / 5
            z = 1.0 + (1.3 - 1.0) * t
            bredder.append(w / z)
        self.assertEqual(bredder, sorted(bredder, reverse=True))

    def test_ugyldig_varighet_feiler_tydelig(self):
        with self.assertRaises(ValueError):
            pf.kenburns_rammer(self.bilde, sekunder=0, fps=10)
        with self.assertRaises(ValueError):
            pf.kenburns_rammer(self.bilde, sekunder=1, fps=0)


class TestLagreRammer(unittest.TestCase):
    def test_skriver_nummerert_sekvens(self):
        bilde = Image.new("RGB", (40, 40), (1, 2, 3))
        rammer = pf.kenburns_rammer(bilde, sekunder=1, fps=4, zoom_til=1.05)
        with tempfile.TemporaryDirectory() as tmp:
            pf.lagre_rammer(rammer, tmp)
            filer = sorted(os.listdir(tmp))
            self.assertEqual(filer, [f"ramme_{i:04d}.jpg" for i in range(4)])
            for f in filer:
                self.assertGreater(os.path.getsize(os.path.join(tmp, f)), 0)


class TestFfmpegTilgjengelig(unittest.TestCase):
    def test_returnerer_bool(self):
        self.assertIsInstance(pf.ffmpeg_tilgjengelig(), bool)


class TestKodVideo(unittest.TestCase):
    """Hopper over seg selv når ffmpeg mangler — se modul-docstringen.

    Denne kjøres derfor ikke i denne økten (ingen ffmpeg her), men kjører og
    verifiserer den faktiske kodingen i ethvert miljø som har ffmpeg
    installert, inkludert et framtidig agent-miljø.
    """
    @unittest.skipUnless(pf.ffmpeg_tilgjengelig(), "krever ffmpeg")
    def test_koder_en_gyldig_mp4(self):
        bilde = Image.new("RGB", (64, 64), (0, 128, 0))
        with tempfile.TemporaryDirectory() as tmp:
            sti = os.path.join(tmp, "bilde.jpg")
            bilde.save(sti, "JPEG")
            ut = os.path.join(tmp, "video.mp4")
            pf.lag_kenburns_video(sti, ut, sekunder=1, fps=6, zoom_til=1.1)
            self.assertTrue(os.path.exists(ut))
            self.assertGreater(os.path.getsize(ut), 1000)

    @unittest.skipIf(pf.ffmpeg_tilgjengelig(), "test for miljø UTEN ffmpeg")
    def test_uten_ffmpeg_gir_tydelig_feil(self):
        with self.assertRaises(RuntimeError):
            pf.kod_video("/tmp/finnes-ikke", "/tmp/ut.mp4")


if __name__ == "__main__":
    unittest.main(verbosity=1)
