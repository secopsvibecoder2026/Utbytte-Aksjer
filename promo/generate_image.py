"""Genererer Facebook-promo PNG (1200x628) for exday.no"""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1200, 628
BOLD   = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Farger
BG1     = (5, 46, 22)    # #052e16
BG2     = (20, 83, 45)   # #14532d
GREEN   = (22, 163, 74)  # #16a34a
GREEN_L = (74, 222, 128) # #4ade80
WHITE   = (255, 255, 255)
GRAY    = (156, 163, 175) # #9ca3af
DARK    = (17, 24, 39)   # #111827
CARD    = (31, 41, 55)   # #1f2937
YELLOW  = (251, 191, 36) # #fbbf24
RED_L   = (248, 113, 113)
TRANS_G = (34, 197, 94, 20)

img = Image.new("RGB", (W, H), BG1)
draw = ImageDraw.Draw(img)

# Bakgrunnsgradient (simulert med horisontale linjer)
for y in range(H):
    t = y / H
    r = int(BG1[0] + (BG2[0] - BG1[0]) * t)
    g = int(BG1[1] + (BG2[1] - BG1[1]) * t)
    b = int(BG1[2] + (BG2[2] - BG1[2]) * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# Dekor-sirkler (subtile)
from PIL import ImageFilter
circle_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
cd = ImageDraw.Draw(circle_img)
cd.ellipse([650, -200, 1150, 300], fill=(34, 197, 94, 15))
cd.ellipse([0, 380, 350, 730], fill=(34, 197, 94, 10))
img = Image.alpha_composite(img.convert("RGBA"), circle_img).convert("RGB")
draw = ImageDraw.Draw(img)

# ── FONTER ──────────────────────────────────────────────────────────────────
def fnt(size, bold=True):
    return ImageFont.truetype(BOLD if bold else NORMAL, size)

# ── VENSTRE SIDE ─────────────────────────────────────────────────────────────
LX = 60  # left margin

# Logo-boks
draw.rounded_rectangle([LX, 50, LX+54, 104], radius=12, fill=GREEN)
draw.text((LX+10, 58), "ex", font=fnt(28), fill=WHITE)

# Logo-tekst
draw.text((LX+66, 52), "exday.no", font=fnt(26), fill=WHITE)
draw.text((LX+66, 84), "Norges utbytteoversikt", font=fnt(13, bold=False), fill=GREEN_L)

# Tagline
draw.text((LX, 130), "Finn de beste", font=fnt(48), fill=WHITE)
draw.text((LX, 182), "utbytteaksjene", font=fnt(48), fill=GREEN_L)
draw.text((LX, 234), "på Oslo Børs", font=fnt(48), fill=WHITE)

# Undertekst
sub = "Yield, ex-dato, score og kalkulator for alle norske"
draw.text((LX, 302), sub, font=fnt(17, bold=False), fill=(134, 239, 172))
draw.text((LX, 326), "utbytteaksjer — gratis og uten innlogging.", font=fnt(17, bold=False), fill=(134, 239, 172))

# Feature-liste
features = [
    "Direkteavkastning og ex-datoer oppdatert daglig",
    "Utbyttekalkulator med DRIP-reinvestering",
    "Porteføljeoppfølging og watchlister",
    "Score 0–10 basert på historikk og stabilitet",
    "Kalender med alle kommende ex-datoer",
]
fy = 368
for feat in features:
    # Grønn sirkel/hake
    draw.ellipse([LX, fy+1, LX+20, fy+21], fill=GREEN)
    draw.text((LX+5, fy+2), "✓", font=fnt(11), fill=WHITE)
    draw.text((LX+28, fy), feat, font=fnt(15, bold=False), fill=(220, 252, 231))
    fy += 28

# CTA-knapp
btn_y = 540
draw.rounded_rectangle([LX, btn_y, LX+280, btn_y+48], radius=12, fill=GREEN)
draw.text((LX+18, btn_y+10), "Prøv gratis på exday.no  →", font=fnt(17), fill=WHITE)

# ── HØYRE: TELEFON-MOCKUP ────────────────────────────────────────────────────
PX = 820   # telefon x-start
PY = 40    # telefon y-start
PW = 260   # bredde
PH = 540   # høyde
PR = 36    # corner radius

# Telefon-ytre (skygge)
shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
for i in range(20, 0, -1):
    sd.rounded_rectangle(
        [PX - i, PY + i, PX + PW + i, PY + PH + i],
        radius=PR + i, fill=(0, 0, 0, 8)
    )
img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
draw = ImageDraw.Draw(img)

# Telefon-ramme
draw.rounded_rectangle([PX, PY, PX+PW, PY+PH], radius=PR, fill=(15, 23, 42), outline=(30, 58, 47), width=3)

# Skjerm (indre)
draw.rounded_rectangle([PX+3, PY+3, PX+PW-3, PY+PH-3], radius=PR-2, fill=DARK)

# Notch
draw.rounded_rectangle([PX+90, PY+12, PX+170, PY+30], radius=10, fill=(15, 23, 42))

# App-header
draw.rectangle([PX+4, PY+38, PX+PW-4, PY+72], fill=DARK)
draw.text((PX+14, PY+46), "ex", font=fnt(18), fill=GREEN_L)
draw.text((PX+34, PY+46), "day", font=fnt(18, bold=False), fill=WHITE)
# Settings + sun ikoner
draw.rounded_rectangle([PX+PW-52, PY+46, PX+PW-32, PY+64], radius=5, fill=CARD)
draw.rounded_rectangle([PX+PW-28, PY+46, PX+PW-8, PY+64], radius=5, fill=CARD)
# Separator
draw.line([(PX+4, PY+73), (PX+PW-4, PY+73)], fill=(31, 41, 55))

# Stats-bar
SBY = PY + 80
draw.rounded_rectangle([PX+10, SBY, PX+PW-10, SBY+44], radius=8, fill=CARD)
# Separator lines
draw.line([(PX+90, SBY+6), (PX+90, SBY+38)], fill=(55, 65, 81))
draw.line([(PX+170, SBY+6), (PX+170, SBY+38)], fill=(55, 65, 81))
# Stat 1
draw.text((PX+22, SBY+5), "124", font=fnt(13), fill=GREEN_L)
draw.text((PX+14, SBY+24), "Aksjer", font=fnt(10, bold=False), fill=GRAY)
# Stat 2
draw.text((PX+98, SBY+5), "8.2%", font=fnt(13), fill=GREEN_L)
draw.text((PX+93, SBY+24), "Høyeste", font=fnt(10, bold=False), fill=GRAY)
# Stat 3
draw.text((PX+176, SBY+5), "4.1%", font=fnt(13), fill=GREEN_L)
draw.text((PX+174, SBY+24), "Snitt", font=fnt(10, bold=False), fill=GRAY)

# Aksje-rader
aksjer = [
    ("EQNR", "Equinor ASA",   "6.8%", "Ex: 14. mai", "8", GREEN_L, True),
    ("DNB",  "DNB Bank ASA",  "5.9%", "Ex: 22. apr", "7", GREEN_L, False),
    ("TEL",  "Telenor ASA",   "5.7%", "Ex: 7. mai",  "6", GREEN_L, False),
    ("MOWI", "Mowi ASA",      "4.4%", "Ex: 30. apr", "4", RED_L,   False),
    ("AKER", "Aker ASA",      "4.1%", "Ex: 12. mai", "5", GREEN_L, False),
]

AY = SBY + 52
for ticker, name, yld, ex, score, score_col, highlight in aksjer:
    row_bg = (20, 83, 45) if highlight else CARD
    draw.rounded_rectangle([PX+10, AY, PX+PW-10, AY+52], radius=8, fill=row_bg)
    # Ticker
    draw.text((PX+18, AY+6),  ticker, font=fnt(13), fill=GREEN_L)
    draw.text((PX+18, AY+24), name,   font=fnt(9, bold=False), fill=GRAY)
    draw.text((PX+18, AY+38), ex,     font=fnt(9, bold=False), fill=YELLOW)
    # Yield
    draw.text((PX+PW-70, AY+8), yld, font=fnt(16), fill=WHITE)
    # Score-sirkel
    draw.ellipse([PX+PW-48, AY+30, PX+PW-26, AY+50], outline=score_col, width=1, fill=BG1)
    draw.text((PX+PW-43, AY+32), score, font=fnt(11), fill=score_col)
    AY += 58

# Tab-bar
TBY = PY + PH - 52
draw.rectangle([PX+4, TBY, PX+PW-4, PY+PH-4], fill=(15, 23, 42))
draw.line([(PX+4, TBY), (PX+PW-4, TBY)], fill=CARD)
tabs = [("📊", "Oversikt"), ("📅", "Kalender"), ("💼", "Portefølje"), ("🧮", "Kalk.")]
tx = PX + 22
for i, (icon, label) in enumerate(tabs):
    col = GREEN_L if i == 0 else GRAY
    draw.text((tx, TBY+6),  icon,  font=fnt(14, bold=False), fill=col)
    draw.text((tx-2, TBY+26), label, font=fnt(8, bold=False),  fill=col)
    tx += 58

# ── LAGRE ────────────────────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(__file__), "facebook-post.png")
img.save(out, "PNG", optimize=True)
print(f"Lagret: {out}  ({W}x{H}px)")
