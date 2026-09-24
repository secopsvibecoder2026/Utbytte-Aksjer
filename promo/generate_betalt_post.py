"""Promobilder for boksen «Faktisk betalt utbytte» på aksjesidene.

Lager to JPEG-er:

* facebook-betalt.jpg   1200×628  — lenkebilde for Facebook
* instagram-betalt.jpg  1080×1350 — 4:5, største feed-format Instagram viser

Et tips, ikke en funksjonskunngjøring. Bildet har bevisst **ingen aksjenavn og
ingen tall**: søylene er en illustrasjon av forskjellen mellom anslag og betalt,
ikke et mål på noen bestemt aksje. Et ekte tall ville gått ut på dato, og å
navngi en aksje der overskriften er for høy ville vært å reklamere for at vårt
eget hovedtall er feil — boksen på siden er stedet som forklarer det.

Kjør: python promo/generate_betalt_post.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from promo_felles import (  # noqa: E402
    ImageDraw, ROOT, GRONN, GRONN_L, GRONN_XL, LYS, HVIT, GRA, KORT, KANT,
    fnt, bredde, skriv_brutt, bakgrunn, logo, merkelapp,
)

URL = "exday.no/aksjer/"
PERIODER = ("12 mnd", "1 år", "2 år", "3 år", "4 år", "5 år")


def betaltkort(draw, x, y, w, h, skala=1.0):
    """Illustrasjon av boksen slik den ser ut på siden, uten tall.

    Periodevelgeren øverst er den samme som i appen, med «12 mnd» valgt.
    Under den to søyler mot felles akse: anslaget og det som faktisk ble
    betalt. Lengdene er valgt for å vise *at* de kan sprike, ikke hvor mye.
    """
    s = skala
    draw.rounded_rectangle([x, y, x + w, y + h], radius=int(18 * s), fill=KORT)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=int(18 * s), outline=KANT, width=2)

    pad = int(28 * s)
    draw.text((x + pad, y + pad), "Faktisk betalt utbytte", font=fnt(int(20 * s)), fill=HVIT)
    draw.text((x + pad, y + pad + int(32 * s)), "Velg periode", font=fnt(int(14 * s), False), fill=GRA)

    # Periodevelger — fordelt jevnt over kortets bredde.
    py = y + pad + int(64 * s)
    ph = int(34 * s)
    mellom = int(8 * s)
    pb = (w - 2 * pad - mellom * (len(PERIODER) - 1)) / len(PERIODER)
    pf = fnt(int(13 * s))
    for i, navn in enumerate(PERIODER):
        px = x + pad + i * (pb + mellom)
        aktiv = i == 0
        if aktiv:
            draw.rounded_rectangle([px, py, px + pb, py + ph], radius=ph // 2, fill=GRONN)
        else:
            draw.rounded_rectangle([px, py, px + pb, py + ph], radius=ph // 2, outline=KANT, width=2)
        draw.text((px + (pb - bredde(draw, navn, pf)) / 2, py + (ph - int(13 * s)) / 2 - 1),
                  navn, font=pf, fill=HVIT if aktiv else GRA)

    # To søyler mot felles akse.
    sy = py + ph + int(46 * s)
    sh = int(34 * s)
    maks_b = w - 2 * pad
    lf = fnt(int(16 * s), False)
    for navn, andel, farge, tekstfarge in (
        ("Oppgitt direkteavkastning (anslag)", 0.92, (71, 85, 105), LYS),
        ("Betalt siste 12 mnd", 0.55, GRONN_L, GRONN_L),
    ):
        draw.text((x + pad, sy), navn, font=lf, fill=tekstfarge)
        by = sy + int(28 * s)
        draw.rounded_rectangle([x + pad, by, x + pad + maks_b, by + sh], radius=int(8 * s),
                               fill=(20, 52, 32))
        draw.rounded_rectangle([x + pad, by, x + pad + int(maks_b * andel), by + sh],
                               radius=int(8 * s), fill=farge)
        sy = by + sh + int(30 * s)

    # Samme vilkår som vist_over_betalt(): forklaringen står bare der gapet er stort.
    skriv_brutt(draw, x + pad, sy + int(4 * s),
                "Er avstanden stor, forklarer siden hvorfor.",
                fnt(int(15 * s), False), maks_b, LYS, int(22 * s))

    # Undertekst: sier rett ut at søylene ikke er data.
    draw.text((x + pad, y + h - pad - int(16 * s)), "Illustrasjon — ikke en bestemt aksje",
              font=fnt(int(13 * s), False), fill=GRA)


def facebook():
    W, H = 1200, 628
    img = bakgrunn(W, H)
    img = logo(img, 60, 44, 180)
    d = ImageDraw.Draw(img)
    LX = 60

    merkelapp(d, LX, 116, "TIPS")
    d.text((LX, 166), "Direkteavkastning", font=fnt(46), fill=HVIT)
    d.text((LX, 220), "er ofte et anslag.", font=fnt(46), fill=GRONN_L)

    d.text((LX, 296), "Se hva selskapet faktisk har betalt —", font=fnt(20, False), fill=LYS)
    d.text((LX, 324), "siste 12 måneder og snitt for 1–5 år.", font=fnt(20, False), fill=LYS)

    by = 400
    knapp = "Se aksjene  →"
    d.rounded_rectangle([LX, by, LX + bredde(d, knapp, fnt(19)) + 44, by + 52], radius=12, fill=GRONN)
    d.text((LX + 22, by + 13), knapp, font=fnt(19), fill=HVIT)
    d.text((LX, by + 68), URL, font=fnt(13, False), fill=GRONN_XL)

    betaltkort(d, 640, 84, 500, 460)

    d.text((LX, H - 44), "exday.no  ·  Utbytteaksjer på Oslo Børs", font=fnt(14, False), fill=GRA)
    return img


def instagram():
    W, H = 1080, 1350
    img = bakgrunn(W, H)
    img = logo(img, 72, 64, 220)
    d = ImageDraw.Draw(img)
    LX = 72

    merkelapp(d, LX, 170, "TIPS", 18)
    d.text((LX, 236), "Direkteavkastning", font=fnt(62), fill=HVIT)
    d.text((LX, 310), "er ofte et anslag.", font=fnt(62), fill=GRONN_L)
    # Brutt for hånd: automatisk bryting etterlot «for 1–5 år.» alene på linje to.
    d.text((LX, 404), "Se hva selskapet faktisk har betalt —", font=fnt(28, False), fill=LYS)
    d.text((LX, 442), "siste 12 måneder og snitt for 1–5 år.", font=fnt(28, False), fill=LYS)

    betaltkort(d, LX, 530, W - 2 * LX, 600, skala=1.3)

    # «aksjesidene», ikke «hver aksjeside»: boksen mangler der det ikke finnes
    # noen utbyttehistorikk å vise.
    d.text((LX, 1200), "Se det på aksjesidene på exday.no", font=fnt(26), fill=HVIT)
    d.text((LX, 1240), "Utbytteaksjer på Oslo Børs", font=fnt(20, False), fill=GRONN_XL)
    return img


if __name__ == "__main__":
    for navn, lag in (("facebook-betalt.jpg", facebook), ("instagram-betalt.jpg", instagram)):
        ut = os.path.join(ROOT, "promo", navn)
        lag().save(ut, "JPEG", quality=92, optimize=True, progressive=True)
        print("Lagret:", ut)
