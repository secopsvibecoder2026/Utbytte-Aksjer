"""Felles byggesteiner for promobildene i promo/.

Flyttet ut av generate_boliglan_post.py da den andre generatoren kom, så
farger, bryting og bakgrunn bare finnes ett sted. Fargene er prosjektets
grønne palett (se CLAUDE.md) — ingen andre.
"""
from PIL import Image, ImageDraw, ImageFont
import os

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

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
