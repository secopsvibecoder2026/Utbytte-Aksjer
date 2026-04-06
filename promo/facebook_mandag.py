"""
Mandagspost generator – exday.no
Kjør: python3 promo/facebook_mandag.py
Genererer:
  - promo/facebook_mandag.txt   (ferdig posttekst til Facebook)
  - promo/facebook_mandag.png   (1200x628px bilde)
"""

import json, datetime, os, textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA   = os.path.join(ROOT, "data", "aksjer.json")
OUT_TXT = os.path.join(ROOT, "promo", "facebook_mandag.txt")
OUT_PNG = os.path.join(ROOT, "promo", "facebook_mandag.png")
LOGO   = os.path.join(ROOT, "logo", "exday_logo_inverse.png")

# ── FARGER ────────────────────────────────────────────────────────────────────
BG       = (17, 24, 39)       # gray-900
CARD     = (31, 41, 55)       # gray-800
GREEN    = (22, 163, 74)      # brand-600
GREEN_L  = (74, 222, 128)     # brand-400
WHITE    = (255, 255, 255)
GRAY     = (156, 163, 175)    # gray-400
ORANGE   = (251, 146, 60)     # orange-400
BLUE     = (96, 165, 250)     # blue-400

# ── FONTS ─────────────────────────────────────────────────────────────────────
def fnt(size, bold=False):
    for name in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if os.path.exists(name):
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()

# ── DATA ──────────────────────────────────────────────────────────────────────
def hent_uke_data():
    with open(DATA) as f:
        data = json.load(f)
    aksjer = data["aksjer"]

    today  = datetime.date.today()
    monday = today - datetime.timedelta(days=today.weekday())
    friday = monday + datetime.timedelta(days=4)
    uke_nr = monday.isocalendar()[1]

    def i_uke(dato_str, fra, til):
        if not dato_str: return False
        try: return fra.isoformat() <= dato_str <= til.isoformat()
        except: return False

    ex_denne  = sorted([a for a in aksjer if i_uke(a.get("ex_dato"), monday, friday)],
                       key=lambda a: a["ex_dato"])
    bet_denne = sorted([a for a in aksjer if i_uke(a.get("betaling_dato"), monday, friday)],
                       key=lambda a: a["betaling_dato"])
    rap_denne = sorted([a for a in aksjer if i_uke(a.get("rapport_dato"), monday, friday)],
                       key=lambda a: a["rapport_dato"])

    return {
        "monday": monday, "friday": friday, "uke_nr": uke_nr,
        "ex_denne": ex_denne, "bet_denne": bet_denne, "rap_denne": rap_denne,
    }

def fmt_dato_no(dato_str):
    if not dato_str: return ""
    d = datetime.date.fromisoformat(dato_str)
    mnd = ["","jan","feb","mar","apr","mai","jun","jul","aug","sep","okt","nov","des"]
    return f"{d.day}. {mnd[d.month]}"

# ── POSTTEKST ─────────────────────────────────────────────────────────────────
def lag_posttekst(d):
    uke    = d["uke_nr"]
    man    = fmt_dato_no(d["monday"].isoformat())
    fre    = fmt_dato_no(d["friday"].isoformat())
    linjer = []

    linjer.append(f"🗓️ God mandag! Her er utbytteuken du bør følge med på — uke {uke} ({man}–{fre})")
    linjer.append("")

    # Ex-datoer denne uken
    if d["ex_denne"]:
        antall_ex = len(d["ex_denne"])
        ex_tekst = "Én aksje har" if antall_ex == 1 else f"{antall_ex} aksjer har"
        linjer.append(f"📌 {ex_tekst} ex-dato denne uken.")
        linjer.append("Kjøper du innen dagen FØR ex-dato, er du med på utbyttet 💰")
        linjer.append("")
        for a in d["ex_denne"]:
            yield_str = f"  →  {a['utbytte_yield']:.1f}% yield" if a.get("utbytte_yield") else ""
            utb_str   = f"  ·  {a['utbytte_per_aksje']:.2f} {a.get('valuta','NOK')} per aksje" if a.get("utbytte_per_aksje") else ""
            linjer.append(f"  📍 {fmt_dato_no(a['ex_dato'])} — {a['navn']} ({a['ticker']}){yield_str}{utb_str}")
    else:
        linjer.append("📌 Ingen ex-datoer denne uken — rolig uke på utbyttesiden.")
    linjer.append("")

    # Utbetalinger denne uken
    if d["bet_denne"]:
        antall_bet = len(d["bet_denne"])
        bet_fl = "utbetalinger" if antall_bet > 1 else "utbetaling"
        linjer.append(f"💸 {antall_bet} {bet_fl} lander på kontoen denne uken:")
        for a in d["bet_denne"]:
            utb_str = f"  ·  {a['utbytte_per_aksje']:.2f} {a.get('valuta','NOK')} per aksje" if a.get("utbytte_per_aksje") else ""
            linjer.append(f"  💰 {fmt_dato_no(a['betaling_dato'])} — {a['navn']} ({a['ticker']}){utb_str}")
        linjer.append("")

    # Rapporter denne uken
    if d["rap_denne"]:
        antall_rap = len(d["rap_denne"])
        rap_fl = "kvartalsrapporter" if antall_rap > 1 else "kvartalsrapport"
        linjer.append(f"📊 {antall_rap} {rap_fl} denne uken — følg med på tallene:")
        for a in d["rap_denne"]:
            linjer.append(f"  📋 {fmt_dato_no(a['rapport_dato'])} — {a['navn']} ({a['ticker']})")
        linjer.append("")

    # Lenker
    linjer.append("🔗 Les mer om ukens aksjer:")
    linjer.append(f"  📅 Utbyttekalender: exday.no/utbyttekalender/")
    if d["ex_denne"]:
        for a in d["ex_denne"]:
            linjer.append(f"  📈 {a['navn']}: exday.no/aksjer/{a['ticker']}/")
    linjer.append("")
    linjer.append("👉 Full oversikt over alle norske utbytteaksjer: exday.no")
    linjer.append("")
    linjer.append("#utbytte #OsloBørs #aksjer #exday #utbytteaksjer #investering #passivInntekt #uke" + str(uke))

    return "\n".join(linjer)

# ── PNG ───────────────────────────────────────────────────────────────────────
W, H = 1200, 628

def rund_rekt(draw, x1, y1, x2, y2, r, farge):
    draw.rounded_rectangle([x1, y1, x2, y2], radius=r, fill=farge)

def lag_png(d):
    img  = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Logo
    if os.path.exists(LOGO):
        logo = Image.open(LOGO).convert("RGBA")
        lw   = 180
        lh   = int(logo.height * lw / logo.width)
        logo = logo.resize((lw, lh), Image.LANCZOS)
        img_rgba = img.convert("RGBA")
        img_rgba.paste(logo, (56, 40), logo)
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

    # Tittel
    uke   = d["uke_nr"]
    man   = fmt_dato_no(d["monday"].isoformat())
    fre   = fmt_dato_no(d["friday"].isoformat())
    draw.text((56, 40 + 42), f"Uke {uke}  ·  {man} – {fre}  ·  Oslo Børs", font=fnt(16), fill=GREEN_L)
    draw.text((56, 96), "Hva skjer på\nOslo Børs denne uken?", font=fnt(38, bold=True), fill=WHITE)

    # Tre kolonner
    col_w  = 330
    col_gap = 24
    col_h  = 300
    top_y  = 210
    cols   = [
        (56,                    top_y, 56 + col_w,                top_y + col_h),
        (56+col_w+col_gap,      top_y, 56+col_w*2+col_gap,        top_y + col_h),
        (56+col_w*2+col_gap*2,  top_y, 56+col_w*3+col_gap*2,      top_y + col_h),
    ]

    def kortnavn(navn):
        # Fjern ASA, Ltd, AS o.l. for kompakthet i PNG
        for suf in (" ASA", " AS", " Ltd", " Limited", " Holding", " Group", " Bank"):
            navn = navn.replace(suf, "")
        return navn.strip()

    def kolonne(idx, tittel, ikon, items, farge_tittel):
        x1, y1, x2, y2 = cols[idx]
        rund_rekt(draw, x1, y1, x2, y2, 14, CARD)
        draw.text((x1+16, y1+14), f"{ikon} {tittel}", font=fnt(14, bold=True), fill=farge_tittel)
        y = y1 + 46
        if not items:
            draw.text((x1+16, y), "Ingen denne uken", font=fnt(13), fill=GRAY)
            return
        for row in items[:8]:
            if y + 22 > y2 - 12: break
            draw.text((x1+16, y), row, font=fnt(13), fill=WHITE)
            y += 22

    # Kol 1: Ex-datoer — fullt navn
    ex_rader = [
        f"{fmt_dato_no(a['ex_dato'])}  {kortnavn(a['navn'])}  {a['utbytte_yield']:.1f}%"
        if a.get('utbytte_yield') else
        f"{fmt_dato_no(a['ex_dato'])}  {kortnavn(a['navn'])}"
        for a in d["ex_denne"]
    ]
    kolonne(0, "Ex-datoer", "📌", ex_rader, GREEN_L)

    # Kol 2: Rapporter — fullt navn
    rap_rader = [f"{fmt_dato_no(a['rapport_dato'])}  {kortnavn(a['navn'])}" for a in d["rap_denne"]]
    kolonne(1, "Rapporter", "📊", rap_rader, ORANGE)

    # Kol 3: Utbetalinger — fullt navn
    if d["bet_denne"]:
        bet_rader = [
            f"{fmt_dato_no(a['betaling_dato'])}  {kortnavn(a['navn'])}  {a['utbytte_per_aksje']:.2f} {a.get('valuta','NOK')}"
            if a.get('utbytte_per_aksje') else
            f"{fmt_dato_no(a['betaling_dato'])}  {kortnavn(a['navn'])}"
            for a in d["bet_denne"]
        ]
        kolonne(2, "Utbetalinger", "💰", bet_rader, BLUE)
    else:
        kolonne(2, "Utbetalinger", "💰", ["Ingen denne uken"], BLUE)

    # Bunntekst
    draw.text((56, H - 52), "exday.no  ·  Norges utbytteoversikt  ·  Oppdateres daglig", font=fnt(14), fill=GRAY)

    # Grønn strek topp
    draw.rectangle([0, 0, W, 5], fill=GREEN)

    img.save(OUT_PNG, "PNG", optimize=True)
    print(f"PNG: {OUT_PNG}")

# ── MAIN ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    d    = hent_uke_data()
    tekst = lag_posttekst(d)

    with open(OUT_TXT, "w") as f:
        f.write(tekst)

    print("=" * 60)
    print(tekst)
    print("=" * 60)
    print(f"Tekst: {OUT_TXT}")

    lag_png(d)
    print("Ferdig!")
