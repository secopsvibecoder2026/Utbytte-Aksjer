"""Promobilder for tipset «år på rad betyr ikke alltid sammenhengende».

Lager to JPEG-er:

* facebook-rekke.jpg   1200×628  — lenkebilde for Facebook
* instagram-rekke.jpg  1080×1350 — 4:5, største feed-format Instagram viser

Et tips, ikke en funksjonskunngjøring. «X år på rad med utbytte» leses ofte
som et helsetegn — men totalt antall år selskapet noensinne har betalt og en
faktisk *sammenhengende* rekke er to forskjellige tall, og siden vår blandet
dem sammen helt til 2026-09-26 (se «'År på rad' er streak, ikke tellingen» i
CLAUDE.md). Bildet er bevisst en illustrasjon av selve forvekslingen — en rad
med årsmarkører der to er brutt — uten å navngi noen aksje eller vise et
faktisk antall år, siden det tallet regnes på nytt hver kjøring og ville gått
ut på dato i et lagret bilde.

Kjør: python promo/generate_rekke_post.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from promo_felles import (  # noqa: E402
    ImageDraw, ROOT, GRONN, GRONN_L, GRONN_XL, LYS, HVIT, GRA, KORT, KANT,
    fnt, bredde, skriv_brutt, bakgrunn, logo, merkelapp,
)

URL = "exday.no/aksjer/"

# Mønsteret på årsmarkørene. True = utbytte betalt det året, False = brudd.
# To brudd, midt i rekken — nok til å vise poenget uten å late som det er en
# bestemt aksjes historikk (14 år er ikke et tall vi noensinne viser på siden).
AAR_MONSTER = [True, True, True, True, False, True, True, True, False, True, True, True, True, True]


def rekkekort(draw, x, y, w, h, skala=1.0):
    """Illustrasjon av årsmarkører med to brudd og dagens (korte) rekke.

    Viser *forskjellen* mellom «år med utbytte» (alle grønne + brutte
    markører til sammen) og «rekke» (bare markørene etter siste brudd) —
    ikke et bestemt antall år for en bestemt aksje.
    """
    s = skala
    draw.rounded_rectangle([x, y, x + w, y + h], radius=int(18 * s), fill=KORT)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=int(18 * s), outline=KANT, width=2)

    pad = int(28 * s)
    draw.text((x + pad, y + pad), "År med utbytte, år for år", font=fnt(int(20 * s)), fill=HVIT)
    draw.text((x + pad, y + pad + int(32 * s)), "Illustrasjon", font=fnt(int(14 * s), False), fill=GRA)

    # Årsmarkører fordelt jevnt over kortets bredde.
    n = len(AAR_MONSTER)
    my = y + pad + int(80 * s)
    mb = int(24 * s)
    mellom = int(8 * s)
    total_b = w - 2 * pad
    steg = (total_b - mb) / (n - 1)
    midtpunkter = []
    for i, betalt in enumerate(AAR_MONSTER):
        mx = x + pad + i * steg
        if betalt:
            draw.rounded_rectangle([mx, my, mx + mb, my + mb], radius=int(5 * s), fill=GRONN)
        else:
            draw.rounded_rectangle([mx, my, mx + mb, my + mb], radius=int(5 * s),
                                   outline=GRA, width=2)
        midtpunkter.append(mx + mb / 2)

    # «Brudd»-piler ned mot de to hule markørene.
    bf = fnt(int(13 * s), False)
    for i, betalt in enumerate(AAR_MONSTER):
        if not betalt:
            tekst = "Brudd"
            tx = midtpunkter[i] - bredde(draw, tekst, bf) / 2
            draw.text((tx, my + mb + int(10 * s)), tekst, font=bf, fill=GRA)

    # Klamme under siste, ubrutte strekk — «dagens rekke».
    siste_brudd = max(i for i, b in enumerate(AAR_MONSTER) if not b)
    kx0 = midtpunkter[siste_brudd + 1] - mb / 2
    kx1 = midtpunkter[-1] + mb / 2
    ky = my + mb + int(46 * s)
    draw.line([(kx0, ky), (kx1, ky)], fill=GRONN_L, width=int(3 * s))
    draw.line([(kx0, ky), (kx0, ky - int(8 * s))], fill=GRONN_L, width=int(3 * s))
    draw.line([(kx1, ky), (kx1, ky - int(8 * s))], fill=GRONN_L, width=int(3 * s))
    kt = "Dagens rekke"
    draw.text(((kx0 + kx1) / 2 - bredde(draw, kt, fnt(int(15 * s))) / 2, ky + int(10 * s)),
              kt, font=fnt(int(15 * s)), fill=GRONN_L)

    # Forklarende linje: hvorfor de to tallene ikke er det samme.
    fy = ky + int(48 * s)
    skriv_brutt(draw, x + pad, fy,
                "Totalt antall år er ikke det samme som en sammenhengende rekke.",
                fnt(int(15 * s), False), total_b, LYS, int(22 * s))

    draw.text((x + pad, y + h - pad - int(16 * s)), "Illustrasjon — ikke en bestemt aksje",
              font=fnt(int(13 * s), False), fill=GRA)


def facebook():
    W, H = 1200, 628
    img = bakgrunn(W, H)
    img = logo(img, 60, 44, 180)
    d = ImageDraw.Draw(img)
    LX = 60

    merkelapp(d, LX, 116, "TIPS")
    d.text((LX, 166), "«X år på rad»", font=fnt(44), fill=HVIT)
    d.text((LX, 220), "betyr ikke alltid det.", font=fnt(44), fill=GRONN_L)

    d.text((LX, 296), "En finanskrise eller pandemi kan bryte", font=fnt(20, False), fill=LYS)
    d.text((LX, 324), "rekken uten at totalen synker.", font=fnt(20, False), fill=LYS)

    by = 400
    knapp = "Se utbyttehistorikk  →"
    d.rounded_rectangle([LX, by, LX + bredde(d, knapp, fnt(19)) + 44, by + 52], radius=12, fill=GRONN)
    d.text((LX + 22, by + 13), knapp, font=fnt(19), fill=HVIT)
    d.text((LX, by + 68), URL, font=fnt(13, False), fill=GRONN_XL)

    rekkekort(d, 620, 122, 520, 380)

    d.text((LX, H - 44), "exday.no  ·  Utbytteaksjer på Oslo Børs", font=fnt(14, False), fill=GRA)
    return img


def instagram():
    W, H = 1080, 1350
    img = bakgrunn(W, H)
    img = logo(img, 72, 64, 220)
    d = ImageDraw.Draw(img)
    LX = 72

    merkelapp(d, LX, 170, "TIPS", 18)
    d.text((LX, 236), "«X år på rad»", font=fnt(58), fill=HVIT)
    d.text((LX, 306), "betyr ikke alltid det.", font=fnt(58), fill=GRONN_L)
    d.text((LX, 396), "En krise kan bryte rekken uten at", font=fnt(28, False), fill=LYS)
    d.text((LX, 434), "det totale antallet år synker.", font=fnt(28, False), fill=LYS)

    rekkekort(d, LX, 520, W - 2 * LX, 500, skala=1.3)

    d.text((LX, 1140), "Se rekken på aksjesidene på exday.no", font=fnt(26), fill=HVIT)
    d.text((LX, 1180), "Utbytteaksjer på Oslo Børs", font=fnt(20, False), fill=GRONN_XL)
    return img


if __name__ == "__main__":
    for navn, lag in (("facebook-rekke.jpg", facebook), ("instagram-rekke.jpg", instagram)):
        ut = os.path.join(ROOT, "promo", navn)
        lag().save(ut, "JPEG", quality=92, optimize=True, progressive=True)
        print("Lagret:", ut)
