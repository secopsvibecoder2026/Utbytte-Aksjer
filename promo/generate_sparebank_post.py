"""Genererer Facebook-promo PNG (1200x628) for exday.no — artikkel om sparebanker"""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1200, 628
BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
ROOT   = os.path.join(os.path.dirname(__file__), "..")

# Farger
BG1     = (5, 46, 22)
BG2     = (20, 83, 45)
GREEN   = (22, 163, 74)
GREEN_L = (74, 222, 128)
WHITE   = (255, 255, 255)
GRAY    = (156, 163, 175)
DARK    = (17, 24, 39)
CARD    = (31, 41, 55)

img = Image.new("RGB", (W, H), BG1)
draw = ImageDraw.Draw(img)

# Bakgrunnsgradient
for y in range(H):
    t = y / H
    r = int(BG1[0] + (BG2[0] - BG1[0]) * t)
    g = int(BG1[1] + (BG2[1] - BG1[1]) * t)
    b = int(BG1[2] + (BG2[2] - BG1[2]) * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# Dekor-sirkler
circle_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
cd = ImageDraw.Draw(circle_img)
cd.ellipse([760, -180, 1310, 370], fill=(34, 197, 94, 12))
cd.ellipse([-50, 420, 320, 770],   fill=(34, 197, 94, 10))
img = Image.alpha_composite(img.convert("RGBA"), circle_img).convert("RGB")
draw = ImageDraw.Draw(img)

def fnt(size, bold=True):
    return ImageFont.truetype(BOLD if bold else NORMAL, size)

# ── LOGO (øvre venstre) ───────────────────────────────────────────────────────
LX = 60
logo_path = os.path.join(ROOT, "logo/exday_logo_inverse.png")
if os.path.exists(logo_path):
    logo = Image.open(logo_path).convert("RGBA")
    logo_w = 190
    logo_h = int(logo.height * logo_w / logo.width)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
    img_rgba = img.convert("RGBA")
    img_rgba.paste(logo, (LX, 44), logo)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

# ── BADGE ──────────────────────────────────────────────────────────────────────
BY = 118
draw.rounded_rectangle([LX, BY, LX + 130, BY + 32], radius=16, fill=(21, 128, 61))
draw.text((LX + 16, BY + 6), "GUIDE", font=fnt(14), fill=WHITE)

# ── TITTEL ────────────────────────────────────────────────────────────────────
TY = 168
draw.text((LX, TY),      "Sparebanker på",   font=fnt(48), fill=WHITE)
draw.text((LX, TY + 56),  "Oslo Børs",         font=fnt(48), fill=GREEN_L)

draw.text((LX, TY + 128), "Hvorfor de gir stabile utbytter",  font=fnt(20, bold=False), fill=(220, 252, 231))
draw.text((LX, TY + 156), "år etter år",                       font=fnt(20, bold=False), fill=(220, 252, 231))

# ── STAT-BOKS ────────────────────────────────────────────────────────────────
SBY = TY + 210
draw.rounded_rectangle([LX, SBY, LX + 460, SBY + 92], radius=14, fill=(15, 50, 25))
draw.rounded_rectangle([LX, SBY, LX + 460, SBY + 92], radius=14, outline=GREEN, width=2)
draw.text((LX + 20, SBY + 12), "3 banker med utbytte 27 år på rad", font=fnt(15, bold=False), fill=GRAY)
draw.line([(LX + 20, SBY + 42), (LX + 440, SBY + 42)], fill=(31, 41, 55), width=1)
draw.text((LX + 20, SBY + 52), "30 sparebanker  ·  6,19 % median-yield", font=fnt(19), fill=GREEN_L)

# CTA
btn_y = SBY + 116
draw.rounded_rectangle([LX, btn_y, LX + 300, btn_y + 50], radius=12, fill=GREEN)
draw.text((LX + 20, btn_y + 12), "Les artikkelen  →", font=fnt(18), fill=WHITE)
draw.text((LX, btn_y + 68), "exday.no/artikler/sparebanker-oslo-bors/", font=fnt(13, bold=False), fill=(134, 239, 172))

# ── HØYRE SIDE: kort med de tre 27-års-bankene ────────────────────────────────
CX, CY, CW = 800, 130, 340
banker = [
    ("MING", "SpareBank 1 SMN",     "27 år på rad", "6,7 % yield"),
    ("SBMO", "Sparebanken Møre",     "27 år på rad", "6,2 % yield"),
    ("SBNOR","Sparebanken Norge",    "27 år på rad", "6,1 % yield"),
]
row_h = 118
for i, (ticker, navn, streak, yld) in enumerate(banker):
    y1 = CY + i * (row_h + 16)
    y2 = y1 + row_h
    draw.rounded_rectangle([CX, y1, CX + CW, y2], radius=16, fill=CARD)
    draw.rounded_rectangle([CX, y1, CX + CW, y2], radius=16, outline=(55, 65, 81), width=1)

    # Ticker-badge
    draw.rounded_rectangle([CX + 20, y1 + 20, CX + 100, y1 + 48], radius=10, fill=GREEN)
    draw.text((CX + 32, y1 + 25), ticker, font=fnt(15), fill=WHITE)

    draw.text((CX + 20, y1 + 58), navn, font=fnt(18), fill=WHITE)
    draw.text((CX + 20, y1 + 86), f"{streak}  ·  {yld}", font=fnt(14, bold=False), fill=GREEN_L)

# Bunntekst
draw.text((LX, H - 46), "exday.no  ·  Norges utbytteoversikt  ·  191 aksjer på Oslo Børs", font=fnt(14, bold=False), fill=GRAY)

# Grønn strek topp
draw.rectangle([0, 0, W, 5], fill=GREEN)

OUT = os.path.join(ROOT, "promo", "facebook-sparebanker.png")
img.save(OUT, "PNG", optimize=True)
print(f"PNG: {OUT}")
