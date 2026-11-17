"""Promobilde for artikkelen «Utbytte i 2027: når selskapene foreslår, vedtar og betaler».

Lager én JPEG:

* facebook-vedtas.jpg  1200×628  (lenkebilde for Facebook)

Bare Facebook, etter ønske fra eieren. Det finnes derfor ingen Instagram-versjon.

Et tips, ikke en kunngjøring. Bildet har **ingen tall som kan drive**:
månedsrutene for 2027 er en illustrasjon og står alle tomme, ikke et mål på
hvor mange ex-datoer som er meldt. Et ekte antall ville gått ut på dato før
innlegget ble postet. Statuspillene er de tre statusene utbyttekalenderen
faktisk bruker.

Kjør: python promo/generate_vedtas_post.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from promo_felles import (  # noqa: E402
    ImageDraw, ROOT, GRONN, GRONN_L, GRONN_XL, LYS, HVIT, GRA, KORT, KANT,
    fnt, bredde, bakgrunn, logo, merkelapp,
)

URL = "exday.no/artikler/slik-vedtas-utbytte/"
MANEDER = ("jan", "feb", "mar", "apr", "mai", "jun",
           "jul", "aug", "sep", "okt", "nov", "des")

# Statusfargene følger rollene i CLAUDE.md: amber advarer (et forslag kan
# endres), grønt er vedtatt, grått er ferdig. Amber er palettens amber-500/700.
AMBER = (185, 138, 58)       # amber-500
AMBER_MORK = (87, 61, 27)    # amber-900
SKIFER = (71, 85, 105)       # samme grå som anslagsstolpen i generate_betalt_post.py
TOM_RUTE = (16, 46, 28)


def kalenderkort(draw, x, y, w, h):
    """En tom 2027-kalender over de tre statusene, uten tall."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=18, fill=KORT)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=18, outline=KANT, width=2)

    pad = 28
    draw.text((x + pad, y + pad), "Utbyttekalender 2027", font=fnt(20), fill=HVIT)
    # Ikke «meldt så langt»: rutene er tomme med vilje, og en og annen
    # 2027-dato er alltid meldt tidlig (Equinor). Teksten sier bare hva som skjer.
    draw.text((x + pad, y + pad + 32), "Datoene kommer etter hvert som selskapene melder dem",
              font=fnt(14, False), fill=GRA)

    # 6 × 2 månedsruter, alle tomme.
    gy = y + pad + 66
    kol, rad = 6, 2
    mellom = 10
    rb = (w - 2 * pad - mellom * (kol - 1)) / kol
    rh = 58
    mf = fnt(13, False)
    for i, navn in enumerate(MANEDER):
        rx = x + pad + (i % kol) * (rb + mellom)
        ry = gy + (i // kol) * (rh + mellom)
        draw.rounded_rectangle([rx, ry, rx + rb, ry + rh], radius=8, fill=TOM_RUTE, outline=KANT, width=1)
        draw.text((rx + (rb - bredde(draw, navn, mf)) / 2, ry + 9), navn, font=mf, fill=GRA)
        # En kort, svak strek der en dato ville stått.
        sx = rx + rb / 2
        draw.line([sx - 9, ry + 40, sx + 9, ry + 40], fill=KANT, width=2)

    # Statusrekka: foreslått → vedtatt → betalt.
    sy = gy + 2 * rh + mellom + 44
    draw.text((x + pad, sy), "Når datoene kommer, har hver en status", font=fnt(15, False), fill=LYS)
    py = sy + 36
    ph = 40
    pf = fnt(16)
    pil = fnt(18)
    statuser = (
        ("Foreslått", AMBER_MORK, AMBER, (234, 217, 176)),   # amber-200 som tekst
        ("Vedtatt", GRONN, GRONN, HVIT),
        ("Betalt", SKIFER, SKIFER, LYS),
    )
    pilbredde = bredde(draw, "→", pil) + 16
    tekstbredder = [bredde(draw, s[0], pf) + 32 for s in statuser]
    ledig = w - 2 * pad - 2 * pilbredde - sum(tekstbredder)
    ekstra = max(0, ledig) / len(statuser)
    px = x + pad
    for i, ((navn, fyll, kant, tekstfarge), tb) in enumerate(zip(statuser, tekstbredder)):
        pb = tb + ekstra
        draw.rounded_rectangle([px, py, px + pb, py + ph], radius=ph // 2, fill=fyll, outline=kant, width=2)
        draw.text((px + (pb - bredde(draw, navn, pf)) / 2, py + 10), navn, font=pf, fill=tekstfarge)
        px += pb
        if i < len(statuser) - 1:
            draw.text((px + 8, py + 8), "→", font=pil, fill=GRA)
            px += pilbredde

    draw.text((x + pad, y + h - pad - 16), "Illustrasjon, ikke meldte datoer",
              font=fnt(13, False), fill=GRA)


def facebook():
    W, H = 1200, 628
    img = bakgrunn(W, H)
    img = logo(img, 60, 44, 180)
    d = ImageDraw.Draw(img)
    LX = 60

    merkelapp(d, LX, 116, "TIPS")
    # 42 px: på 44 px gikk andre linje inn under kortet og kuttet «?».
    d.text((LX, 166), "Hvorfor er kalenderen", font=fnt(42), fill=HVIT)
    d.text((LX, 218), "for 2027 nesten tom?", font=fnt(42), fill=GRONN_L)

    d.text((LX, 292), "Ex-datoen kommer med forslaget til utbytte.", font=fnt(19, False), fill=LYS)
    d.text((LX, 320), "Og et forslag er ikke et vedtak.", font=fnt(19, False), fill=LYS)

    by = 400
    knapp = "Les artikkelen  →"
    d.rounded_rectangle([LX, by, LX + bredde(d, knapp, fnt(19)) + 44, by + 52], radius=12, fill=GRONN)
    d.text((LX + 22, by + 13), knapp, font=fnt(19), fill=HVIT)
    d.text((LX, by + 68), URL, font=fnt(13, False), fill=GRONN_XL)

    kalenderkort(d, 640, 84, 500, 460)

    d.text((LX, H - 44), "exday.no  ·  Utbytteaksjer på Oslo Børs", font=fnt(14, False), fill=GRA)
    return img


if __name__ == "__main__":
    ut = os.path.join(ROOT, "promo", "facebook-vedtas.jpg")
    facebook().save(ut, "JPEG", quality=92, optimize=True, progressive=True)
    print("Lagret:", ut)
