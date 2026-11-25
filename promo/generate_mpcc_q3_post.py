"""Promobilder for oppsummeringen av MPC Container Ships' rapport for 3. kvartal 2026.

Lager to JPEG-er:

* facebook-mpcc-q3-2026.jpg   1200×628  (lenkebilde for Facebook)
* instagram-mpcc-q3-2026.jpg  1080×1350 (4:5)

Alle tall er ekte og står i data/rapporter/MPCC.json (periode 2026-Q3,
NewsWeb 687333 og utbyttemelding 687337). Ingen yield, kurs eller kronebeløp:
de ville gått ut på dato før innlegget ble postet. Tallene er nøytrale (hvitt),
ikke grønt eller rødt, slik STYLE.md sier: et lavere resultat er ikke en farge.

Utbyttestripa nederst i kortet viser tre kvartaler (3. kv. 2025, 2. kv. 2026,
3. kv. 2026). Det er poenget med rapportsiden: historikken bygges opp per kvartal.

Kjør: python promo/generate_mpcc_q3_post.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from promo_felles import (  # noqa: E402
    ImageDraw, ROOT, GRONN, GRONN_L, GRONN_XL, LYS, HVIT, GRA, KORT, KANT,
    fnt, bredde, bakgrunn, logo, merkelapp,
)

URL = "exday.no/aksjer/MPCC/rapporter/"

# (navn, nå, samme kvartal i fjor). Alle fra nokkeltall i MPCC.json.
NOKKELTALL = (
    ("Resultat, mill. USD", "45,2", "53,6"),
    ("Justert resultat, mill. USD", "36,1", "45,0"),
    ("Driftsinntekter, mill. USD", "113,1", "125,9"),
    ("Snittrate per dag, USD", "25 333", "26 523"),
)

# Utbytte per aksje i USD, eldst først.
UTBYTTE = (("3. kv. 2025", 0.05, "0,05"), ("2. kv. 2026", 0.04, "0,04"), ("3. kv. 2026", 0.04, "0,04"))

DATOER = (
    ("Siste dag med rett", "9. desember"),
    ("Ex-dato", "10. desember"),
    ("Utbetaling", "rundt 17. desember"),
)

STOLPE_GAMMEL = (71, 85, 105)   # samme grå som anslagsstolpen i generate_betalt_post.py


def tallkort(draw, x, y, w, h, s=1.0):
    """Nøkkeltall mot samme kvartal i fjor, og utbyttet over tre kvartaler."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=int(18 * s), fill=KORT)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=int(18 * s), outline=KANT, width=2)

    pad = int(26 * s)
    draw.text((x + pad, y + pad), "3. kvartal, mot samme kvartal i fjor", font=fnt(int(18 * s)), fill=HVIT)

    # Kolonnehoder, høyrejustert over tallene.
    k2 = x + w - pad                       # høyre kant, i fjor
    k1 = k2 - int(108 * s)                 # høyre kant, nå
    hf = fnt(int(13 * s), False)
    hy = y + pad + int(40 * s)
    for tekst, kant in (("2026", k1), ("2025", k2)):
        draw.text((kant - bredde(draw, tekst, hf), hy), tekst, font=hf, fill=GRA)

    ry = hy + int(28 * s)
    radh = int(40 * s)
    lf = fnt(int(15 * s), False)
    tf = fnt(int(19 * s))
    tf_gammel = fnt(int(19 * s), False)
    for navn, naa, ifjor in NOKKELTALL:
        draw.line([x + pad, ry, x + w - pad, ry], fill=KANT, width=1)
        my = ry + (radh - int(19 * s)) / 2
        draw.text((x + pad, my + int(2 * s)), navn, font=lf, fill=LYS)
        draw.text((k1 - bredde(draw, naa, tf), my), naa, font=tf, fill=HVIT)
        draw.text((k2 - bredde(draw, ifjor, tf_gammel), my), ifjor, font=tf_gammel, fill=GRA)
        ry += radh
    draw.line([x + pad, ry, x + w - pad, ry], fill=KANT, width=1)

    # Utbytte per aksje over tre kvartaler: stolper med felles skala.
    uy = ry + int(24 * s)
    draw.text((x + pad, uy), "Utbytte per aksje, USD", font=fnt(int(16 * s)), fill=HVIT)
    bunn = y + h - pad - int(22 * s)      # plass til kvartalsnavn under stolpene
    topp = uy + int(34 * s) + int(22 * s)  # plass til beløpet over høyeste stolpe
    maks_h = bunn - topp
    n = len(UTBYTTE)
    mellom = int(22 * s)
    sb = (w - 2 * pad - mellom * (n - 1)) / n
    bf = fnt(int(16 * s))
    kf = fnt(int(13 * s), False)
    maks = max(v for _, v, _ in UTBYTTE)
    for i, (kvartal, verdi, tekst) in enumerate(UTBYTTE):
        sx = x + pad + i * (sb + mellom)
        sh = maks_h * verdi / maks
        siste = i == n - 1
        draw.rounded_rectangle([sx, bunn - sh, sx + sb, bunn], radius=int(6 * s),
                               fill=GRONN if siste else STOLPE_GAMMEL)
        draw.text((sx + (sb - bredde(draw, tekst, bf)) / 2, bunn - sh - int(24 * s)),
                  tekst, font=bf, fill=HVIT)
        draw.text((sx + (sb - bredde(draw, kvartal, kf)) / 2, bunn + int(6 * s)),
                  kvartal, font=kf, fill=LYS if siste else GRA)


def datoliste(draw, x, y, s=1.0, radh=34):
    lf = fnt(int(17 * s), False)
    vf = fnt(int(17 * s))
    etikett_b = max(bredde(draw, e, lf) for e, _ in DATOER) + int(18 * s)
    for i, (etikett, verdi) in enumerate(DATOER):
        ry = y + i * int(radh * s)
        draw.text((x, ry), etikett, font=lf, fill=GRA)
        draw.text((x + etikett_b, ry), verdi, font=vf, fill=HVIT)


def facebook():
    W, H = 1200, 628
    img = bakgrunn(W, H)
    img = logo(img, 60, 44, 180)
    d = ImageDraw.Draw(img)
    LX = 60

    merkelapp(d, LX, 112, "KVARTALSRAPPORT")
    d.text((LX, 160), "MPC Container Ships", font=fnt(42), fill=HVIT)
    d.text((LX, 212), "0,04 dollar per aksje", font=fnt(42), fill=GRONN_L)
    d.text((LX, 276), "Samme utbytte som for 2. kvartal.", font=fnt(20, False), fill=LYS)
    d.text((LX, 304), "Fastsatt i dollar, utbetales i kroner.", font=fnt(20, False), fill=LYS)

    datoliste(d, LX, 362)

    by = 482
    knapp = "Les oppsummeringen  →"
    d.rounded_rectangle([LX, by, LX + bredde(d, knapp, fnt(18)) + 40, by + 48], radius=12, fill=GRONN)
    d.text((LX + 20, by + 13), knapp, font=fnt(18), fill=HVIT)
    d.text((LX, by + 60), URL, font=fnt(13, False), fill=GRONN_XL)

    tallkort(d, 640, 60, 500, 510)

    d.text((640, H - 44), "Kilde: selskapets rapport for 3. kvartal 2026", font=fnt(13, False), fill=GRA)
    return img


def instagram():
    W, H = 1080, 1350
    img = bakgrunn(W, H)
    img = logo(img, 72, 64, 220)
    d = ImageDraw.Draw(img)
    LX = 72

    merkelapp(d, LX, 168, "KVARTALSRAPPORT", 18)
    d.text((LX, 228), "MPC Container Ships", font=fnt(58), fill=HVIT)
    d.text((LX, 298), "0,04 dollar per aksje", font=fnt(58), fill=GRONN_L)
    d.text((LX, 384), "Samme utbytte som for 2. kvartal. Fastsatt", font=fnt(26, False), fill=LYS)
    d.text((LX, 420), "i dollar, utbetales i kroner.", font=fnt(26, False), fill=LYS)

    datoliste(d, LX, 472, s=1.35)

    tallkort(d, LX, 618, W - 2 * LX, 600, s=1.3)

    d.text((LX, 1244), "Kontrakter for 90 % av dagene i 2027", font=fnt(24), fill=HVIT)
    d.text((LX, 1284), URL, font=fnt(20, False), fill=GRONN_XL)
    return img


if __name__ == "__main__":
    for navn, lag in (("facebook-mpcc-q3-2026.jpg", facebook), ("instagram-mpcc-q3-2026.jpg", instagram)):
        ut = os.path.join(ROOT, "promo", navn)
        lag().save(ut, "JPEG", quality=92, optimize=True, progressive=True)
        print("Lagret:", ut)
