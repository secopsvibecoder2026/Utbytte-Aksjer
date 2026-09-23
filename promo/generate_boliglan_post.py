"""Promobilder for artikkelen «Nedbetale boliglånet eller investere?».

Lager to JPEG-er:

* facebook-boliglan.jpg   1200×628  — lenkebilde for Facebook
* instagram-boliglan.jpg  1080×1350 — 4:5, største feed-format Instagram viser

JPEG, ikke PNG: Instagram tar bare JPEG (se «Automatisk publisering til
Facebook og Instagram» i ROADMAP.md). Lerretet holdes i RGB hele veien, så
lagringen kan ikke feile på en alfakanal.

Tallene i bildet er artikkelens *regneeksempel* — 5,5 % rente og 8 % forventet
avkastning — ikke levende data. De kan derfor ikke gå ut på dato slik antallet
aksjer i facebook-post.html gjorde. Rentefradraget (22 %) og skattesatsen på
aksjeinntekt (37,84 %) er 2026-satser; endres de, må både artikkelen og dette
bildet oppdateres.

Kjør: python promo/generate_boliglan_post.py
"""
from PIL import Image, ImageDraw, ImageFont
import os

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
URL = "exday.no/artikler/nedbetale-boliglan-eller-investere/"

# Farger — prosjektets grønne palett (se CLAUDE.md), ikke noe annet.
BG1 = (5, 46, 22)
BG2 = (20, 83, 45)
GRONN = (22, 163, 74)        # green-600
GRONN_L = (74, 222, 128)     # green-400
GRONN_XL = (134, 239, 172)   # green-300
LYS = (220, 252, 231)        # green-100
HVIT = (255, 255, 255)
GRA = (156, 163, 175)
KORT = (12, 38, 22)
KANT = (31, 90, 52)

# Regneeksempelet fra artikkelen. Holdes samlet her så det er ett sted å rette.
LAN_NOMINELT, LAN_REELT = 5.50, 4.29      # 5,5 % × (1 − 0,22)
AKSJE_NOMINELT, AKSJE_REELT = 8.00, 4.97  # 8 % × (1 − 0,3784)


def nf(v, d=2):
    """Norsk tallformat: komma som desimalskille."""
    return f"{v:.{d}f}".replace(".", ",")


def fnt(size, fet=True):
    return ImageFont.truetype(BOLD if fet else NORMAL, size)


def bredde(draw, tekst, font):
    x0, _, x1, _ = draw.textbbox((0, 0), tekst, font=font)
    return x1 - x0


def bryt(draw, tekst, font, maks):
    """Bryter tekst i linjer som får plass innenfor `maks` piksler.

    Målt, ikke telt i tegn: DejaVu er proporsjonal, så «37,84 %» og «iiii»
    tar svært ulik plass. Første utkast brøt ikke i det hele tatt, og
    fotnoten løp ut av Facebook-bildet på høyre side.
    """
    # split(" "), ikke split(): Python regner hardt mellomrom (U+00A0) som
    # blanktegn, og da ville «37,84 %» kunne brytes mellom tall og prosenttegn.
    linjer, linje = [], ""
    for ord_ in tekst.split(" "):
        forsok = f"{linje} {ord_}".strip()
        if bredde(draw, forsok, font) <= maks:
            linje = forsok
        else:
            linjer.append(linje)
            linje = ord_
    if linje:
        linjer.append(linje)
    return linjer


def skriv_brutt(draw, x, y, tekst, font, maks, farge, linjeavstand):
    for i, l in enumerate(bryt(draw, tekst, font, maks)):
        draw.text((x, y + i * linjeavstand), l, font=font, fill=farge)


def bakgrunn(w, h):
    img = Image.new("RGB", (w, h), BG1)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(BG1, BG2)))
    # Dekorsirkler, blandet inn uten å etterlate en alfakanal.
    lag = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lag)
    ld.ellipse([w - 440, -200, w + 160, 400], fill=(34, 197, 94, 14))
    ld.ellipse([-120, h - 260, 260, h + 120], fill=(34, 197, 94, 10))
    img = Image.alpha_composite(img.convert("RGBA"), lag).convert("RGB")
    ImageDraw.Draw(img).rectangle([0, 0, w, 5], fill=GRONN)
    return img


def logo(img, x, y, bredde_px):
    sti = os.path.join(ROOT, "logo", "exday_logo_inverse.png")
    if not os.path.exists(sti):
        return img
    lg = Image.open(sti).convert("RGBA")
    lg = lg.resize((bredde_px, int(lg.height * bredde_px / lg.width)), Image.LANCZOS)
    rgba = img.convert("RGBA")
    rgba.paste(lg, (x, y), lg)
    return rgba.convert("RGB")


def merkelapp(draw, x, y, tekst, storrelse=14):
    f = fnt(storrelse)
    b = bredde(draw, tekst, f)
    draw.rounded_rectangle([x, y, x + b + 32, y + storrelse + 18], radius=(storrelse + 18) // 2,
                           fill=(21, 128, 61))
    draw.text((x + 16, y + 8), tekst, font=f, fill=HVIT)


def stolpediagram(draw, x, y, w, h, skala=1.0):
    """Kortet som bærer poenget: gapet før skatt mot gapet etter.

    To grupper med to søyler hver. Høyden er proporsjonal med prosenten mot en
    felles akse, så leseren *ser* at avstanden krymper — det er hele
    artikkelens poeng i ett bilde, og grunnen til at dette er et diagram og
    ikke en tabell.
    """
    s = skala
    draw.rounded_rectangle([x, y, x + w, y + h], radius=int(18 * s), fill=KORT)
    draw.rounded_rectangle([x, y, x + w, y + h], radius=int(18 * s), outline=KANT, width=2)

    pad = int(28 * s)
    tittel_f = fnt(int(17 * s))
    draw.text((x + pad, y + pad), "Avkastning per år, eksempel", font=tittel_f, fill=LYS)

    # Forklaring
    ly = y + pad + int(34 * s)
    for i, (farge, navn) in enumerate(((LYS, "Betale ned lån"), (GRONN_L, "Aksjer"))):
        lx = x + pad + i * int(190 * s)
        draw.rounded_rectangle([lx, ly + 3, lx + int(16 * s), ly + 3 + int(16 * s)], radius=4, fill=farge)
        draw.text((lx + int(24 * s), ly), navn, font=fnt(int(15 * s), False), fill=GRA)

    # Plottområde
    topp = ly + int(52 * s)
    bunn = y + h - pad - int(78 * s)
    hoyde = bunn - topp
    maks = 9.0
    grp_b = (w - 2 * pad) / 2
    sbredde = int(66 * s)
    mellom = int(14 * s)

    grupper = (
        ("Før skatt", LAN_NOMINELT, AKSJE_NOMINELT),
        ("Etter skatt", LAN_REELT, AKSJE_REELT),
    )
    verdi_f = fnt(int(17 * s))
    for g, (navn, lan, aksje) in enumerate(grupper):
        gx = x + pad + g * grp_b
        midt = gx + grp_b / 2
        x1 = int(midt - sbredde - mellom / 2)
        x2 = int(midt + mellom / 2)
        for sx, verdi, farge in ((x1, lan, LYS), (x2, aksje, GRONN_L)):
            sh = int(hoyde * verdi / maks)
            draw.rounded_rectangle([sx, bunn - sh, sx + sbredde, bunn], radius=int(8 * s), fill=farge)
            tekst = nf(verdi) + " %"
            draw.text((sx + (sbredde - bredde(draw, tekst, verdi_f)) / 2, bunn - sh - int(26 * s)),
                      tekst, font=verdi_f, fill=HVIT)
        gf = fnt(int(16 * s), False)
        draw.text((midt - bredde(draw, navn, gf) / 2, bunn + int(12 * s)), navn, font=gf, fill=GRA)

    draw.line([(x + pad, bunn), (x + w - pad, bunn)], fill=KANT, width=2)

    # Konklusjonen, under aksen
    ky = bunn + int(44 * s)
    f1, f2 = fnt(int(16 * s), False), fnt(int(16 * s))
    del1 = "Forspranget krymper fra "
    del2 = "2,5 til 0,68 prosentpoeng"
    total = bredde(draw, del1, f1) + bredde(draw, del2, f2)
    kx = x + (w - total) / 2
    draw.text((kx, ky), del1, font=f1, fill=LYS)
    draw.text((kx + bredde(draw, del1, f1), ky), del2, font=f2, fill=GRONN_L)


def fotnote():
    # Hardt mellomrom mellom tall og «%», så de aldri havner på hver sin linje.
    p = "\u00a0%"
    return (f"Eksempel: {nf(LAN_NOMINELT, 1)}{p} rente, {nf(AKSJE_NOMINELT, 0)}{p} forventet avkastning, "
            f"22{p} rentefradrag og 37,84{p} skatt på aksjeinntekt.")


def facebook():
    W, H = 1200, 628
    img = bakgrunn(W, H)
    img = logo(img, 60, 44, 180)
    d = ImageDraw.Draw(img)
    LX = 60

    merkelapp(d, LX, 116, "ARTIKKEL")
    d.text((LX, 166), "Nedbetale", font=fnt(46), fill=HVIT)
    d.text((LX, 220), "boliglånet eller", font=fnt(46), fill=HVIT)
    d.text((LX, 274), "investere?", font=fnt(46), fill=GRONN_L)

    d.text((LX, 346), "Etter rentefradrag og skatt er", font=fnt(20, False), fill=LYS)
    d.text((LX, 374), "forskjellen mindre enn du tror.", font=fnt(20, False), fill=LYS)

    by = 430
    d.rounded_rectangle([LX, by, LX + 290, by + 52], radius=12, fill=GRONN)
    d.text((LX + 22, by + 13), "Les artikkelen  →", font=fnt(19), fill=HVIT)
    d.text((LX, by + 68), URL, font=fnt(13, False), fill=GRONN_XL)

    stolpediagram(d, 640, 70, 500, 460)
    skriv_brutt(d, 640, 544, fotnote(), fnt(12, False), 500, GRA, 17)

    d.text((LX, H - 44), "exday.no  ·  Utbytteaksjer på Oslo Børs", font=fnt(14, False), fill=GRA)
    return img


def instagram():
    W, H = 1080, 1350
    img = bakgrunn(W, H)
    img = logo(img, 72, 64, 220)
    d = ImageDraw.Draw(img)
    LX = 72

    merkelapp(d, LX, 170, "ARTIKKEL", 18)
    d.text((LX, 236), "Nedbetale boliglånet", font=fnt(62), fill=HVIT)
    d.text((LX, 310), "eller investere?", font=fnt(62), fill=GRONN_L)
    d.text((LX, 404), "Etter rentefradrag og skatt er forskjellen", font=fnt(28, False), fill=LYS)
    d.text((LX, 442), "mindre enn du tror.", font=fnt(28, False), fill=LYS)

    stolpediagram(d, LX, 520, W - 2 * LX, 600, skala=1.3)
    skriv_brutt(d, LX, 1140, fotnote(), fnt(17, False), W - 2 * LX, GRA, 26)

    d.text((LX, 1230), "Les hele artikkelen på exday.no", font=fnt(26), fill=HVIT)
    d.text((LX, 1270), "Utbytteaksjer på Oslo Børs", font=fnt(20, False), fill=GRONN_XL)
    return img


if __name__ == "__main__":
    for navn, lag in (("facebook-boliglan.jpg", facebook), ("instagram-boliglan.jpg", instagram)):
        ut = os.path.join(ROOT, "promo", navn)
        lag().save(ut, "JPEG", quality=92, optimize=True, progressive=True)
        print("Lagret:", ut)
