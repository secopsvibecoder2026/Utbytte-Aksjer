"""Genererer Facebook-promo PNG (1200x628) for exday.no — fokus på utbyttekalkulator"""
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
YELLOW  = (251, 191, 36)
RED_L   = (248, 113, 113)

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
cd.ellipse([700, -180, 1250, 370], fill=(34, 197, 94, 12))
cd.ellipse([-50, 400, 320, 750],   fill=(34, 197, 94, 10))
img = Image.alpha_composite(img.convert("RGBA"), circle_img).convert("RGB")
draw = ImageDraw.Draw(img)

def fnt(size, bold=True):
    return ImageFont.truetype(BOLD if bold else NORMAL, size)

# ── LOGO (øvre venstre) ───────────────────────────────────────────────────────
LX = 60
logo_path = os.path.join(ROOT, "logo/exday_logo_inverse.png")
if os.path.exists(logo_path):
    logo = Image.open(logo_path).convert("RGBA")
    logo_w = 200
    logo_h = int(logo.height * logo_w / logo.width)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
    img_rgba = img.convert("RGBA")
    img_rgba.paste(logo, (LX, 46), logo)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.text((LX, 46 + logo_h + 8), "Norges utbytteoversikt", font=fnt(13, bold=False), fill=GREEN_L)

# ── VENSTRE SIDE: Tekst ───────────────────────────────────────────────────────
TY = 140
draw.text((LX, TY),      "Hva får du",       font=fnt(52), fill=WHITE)
draw.text((LX, TY + 58), "i utbytte?",       font=fnt(52), fill=GREEN_L)

draw.text((LX, TY + 132), "Skriv inn antall aksjer —",    font=fnt(19, bold=False), fill=(220, 252, 231))
draw.text((LX, TY + 158), "vi regner ut resten for deg.", font=fnt(19, bold=False), fill=(220, 252, 231))

# Eksempel-boks
EBY = TY + 210
draw.rounded_rectangle([LX, EBY, LX + 470, EBY + 88], radius=14, fill=(15, 50, 25))
draw.rounded_rectangle([LX, EBY, LX + 470, EBY + 88], radius=14, outline=GREEN, width=2)
draw.text((LX + 20, EBY + 10), "100 DNB-aksjer  ×  18,00 kr/aksje", font=fnt(16, bold=False), fill=GRAY)
draw.line([(LX + 20, EBY + 40), (LX + 450, EBY + 40)], fill=(31, 41, 55), width=1)
draw.text((LX + 20, EBY + 50), "= 1 800 kr i utbytte", font=fnt(26), fill=GREEN_L)

# CTA-knapp
btn_y = EBY + 116
draw.rounded_rectangle([LX, btn_y, LX + 320, btn_y + 50], radius=12, fill=GREEN)
draw.text((LX + 20, btn_y + 12), "Beregn ditt utbytte  →", font=fnt(18), fill=WHITE)
draw.text((LX, btn_y + 68), "exday.no", font=fnt(14, bold=False), fill=(134, 239, 172))

# ── HØYRE SIDE: Telefon-mockup ────────────────────────────────────────────────
PX, PY, PW, PH, PR = 790, 30, 320, 558, 36

# Telefon-skygge
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
for i in range(20, 0, -1):
    sd.rounded_rectangle([PX - i, PY + i, PX + PW + i, PY + PH + i], radius=PR + i, fill=(0, 0, 0, 8))
img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
draw = ImageDraw.Draw(img)

# Telefon-kropp
draw.rounded_rectangle([PX, PY, PX + PW, PY + PH], radius=PR, fill=(15, 23, 42), outline=(30, 58, 47), width=3)
draw.rounded_rectangle([PX + 3, PY + 3, PX + PW - 3, PY + PH - 3], radius=PR - 2, fill=DARK)
draw.rounded_rectangle([PX + 110, PY + 14, PX + 210, PY + 30], radius=10, fill=(15, 23, 42))

# App-header
draw.rectangle([PX + 4, PY + 40, PX + PW - 4, PY + 76], fill=DARK)
draw.text((PX + 16, PY + 48), "ex", font=fnt(20), fill=GREEN_L)
draw.text((PX + 38, PY + 48), "day", font=fnt(20, bold=False), fill=WHITE)
draw.text((PX + 76, PY + 48), ".no", font=fnt(14, bold=False), fill=GRAY)
draw.line([(PX + 4, PY + 77), (PX + PW - 4, PY + 77)], fill=(31, 41, 55))

# Aksje-header-kort
AHY = PY + 88
draw.rounded_rectangle([PX + 12, AHY, PX + PW - 12, AHY + 68], radius=10, fill=CARD)
draw.text((PX + 22, AHY + 10), "DNB Bank ASA", font=fnt(15), fill=WHITE)
draw.text((PX + 22, AHY + 32), "Oslo Børs   Finans", font=fnt(11, bold=False), fill=GRAY)
draw.text((PX + PW - 95, AHY + 10), "5.9%",     font=fnt(18), fill=GREEN_L)
draw.text((PX + PW - 90, AHY + 34), "yield",    font=fnt(10, bold=False), fill=GRAY)
draw.line([(PX + 22, AHY + 52), (PX + PW - 22, AHY + 52)], fill=(55, 65, 81))
draw.text((PX + 22, AHY + 56), "Ex-dato:", font=fnt(11, bold=False), fill=GRAY)
draw.text((PX + 100, AHY + 56), "22. april 2026", font=fnt(11), fill=YELLOW)

# Kalkulator-seksjon
KY = AHY + 82
draw.text((PX + 22, KY), "Kalkulator", font=fnt(13), fill=GREEN_L)

# Antall-input
KY += 28
draw.rounded_rectangle([PX + 12, KY, PX + PW - 12, KY + 46], radius=8, fill=(15, 23, 42), outline=(55, 65, 81), width=1)
draw.text((PX + 22, KY + 8),  "Antall aksjer", font=fnt(11, bold=False), fill=GRAY)
draw.text((PX + 22, KY + 26), "100",           font=fnt(15), fill=WHITE)
draw.rounded_rectangle([PX + PW - 60, KY + 8, PX + PW - 18, KY + 38], radius=6, fill=GREEN)
draw.text((PX + PW - 56, KY + 13), "Beregn", font=fnt(10), fill=WHITE)

# Resultat-kort
RY = KY + 62
draw.rounded_rectangle([PX + 12, RY, PX + PW - 12, RY + 170], radius=10, fill=(15, 50, 25), outline=GREEN, width=2)

draw.text((PX + 22, RY + 14), "Utbytte per aksje", font=fnt(11, bold=False), fill=GRAY)
draw.text((PX + PW - 110, RY + 14), "18,00 kr",   font=fnt(13), fill=WHITE)

draw.line([(PX + 22, RY + 40), (PX + PW - 22, RY + 40)], fill=(31, 55, 31))

draw.text((PX + 22, RY + 52),  "Brutto utbytte",  font=fnt(11, bold=False), fill=GRAY)
draw.text((PX + PW - 120, RY + 50), "1 800 kr",   font=fnt(16), fill=WHITE)

draw.text((PX + 22, RY + 80),  "Estimert skatt",  font=fnt(11, bold=False), fill=GRAY)
draw.text((PX + PW - 110, RY + 78), "- 681 kr",   font=fnt(13), fill=RED_L)

draw.line([(PX + 22, RY + 108), (PX + PW - 22, RY + 108)], fill=(31, 55, 31))

draw.text((PX + 22, RY + 118),  "Netto utbytte",  font=fnt(13), fill=GREEN_L)
draw.text((PX + PW - 130, RY + 114), "1 119 kr",  font=fnt(22), fill=GREEN_L)

draw.text((PX + 22, RY + 154),  "Utbetaling ca. mai 2026", font=fnt(10, bold=False), fill=GRAY)

# Tab-bar
TBY = PY + PH - 52
draw.rectangle([PX + 4, TBY, PX + PW - 4, PY + PH - 4], fill=(15, 23, 42))
draw.line([(PX + 4, TBY), (PX + PW - 4, TBY)], fill=CARD)
tabs = [("📊", "Oversikt"), ("📅", "Kalender"), ("💼", "Portefølje"), ("🧮", "Kalk.")]
tx = PX + 18
for i, (icon, label) in enumerate(tabs):
    col = GREEN_L if i == 3 else GRAY
    draw.text((tx, TBY + 6),  icon,  font=fnt(14, bold=False), fill=col)
    draw.text((tx - 2, TBY + 26), label, font=fnt(8, bold=False), fill=col)
    tx += 72

# ── LAGRE ─────────────────────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(__file__), "facebook_kalkulator.png")
img.save(out, "PNG", optimize=True)
print(f"Lagret: {out}  ({W}x{H}px)")
