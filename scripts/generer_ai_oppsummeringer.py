#!/usr/bin/env python3
"""
Genererer norske AI-oppsummeringer for alle aksjer i data/aksjer.json.
90-130 ord per aksje. Intelligent tolkning av nøkkeltall.
"""

import json
import random
from datetime import datetime

DATO = datetime.now().strftime("%Y-%m-%d")
DATO_TID = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

# Sektor-normale P/E-områder
SEKTOR_PE = {
    "Finans": (8, 14),
    "Energi": (10, 18),
    "Telekommunikasjon": (14, 22),
    "Forbruksvarer": (16, 24),
    "Konsumvarer": (14, 22),
    "Industri": (14, 22),
    "Eiendom": (16, 28),
    "Helsevern": (18, 30),
    "Materialer": (12, 20),
    "Informasjonsteknologi": (20, 35),
    "Havbruk": (10, 20),
    "Sjømat": (10, 20),
    "Shipping": (6, 14),
    "Forsyning": (14, 22),
    "Offshore": (10, 18),
    "Energitjenester": (10, 18),
    "Gjødsel": (8, 16),
    "Forsikring": (10, 16),
    "Fornybar energi": (18, 35),
}


def safe(v):
    return v if v is not None else 0


def sektor_pe_label(pe, sektor):
    low, high = SEKTOR_PE.get(sektor, (12, 22))
    if pe <= 0:
        return None
    if pe < low * 0.7:
        return "svært lavt"
    if pe < low:
        return "lavt"
    if pe <= high:
        return "normalt for sektoren"
    if pe <= high * 1.5:
        return "noe høyt"
    if pe <= high * 2.5:
        return "klart høyt"
    return "ekstremt høyt"


def generer_oppsummering(aksje):
    ticker = aksje.get("ticker", "")
    sektor = aksje.get("sektor", "")
    pe = aksje.get("pe_ratio") or 0
    y = aksje.get("utbytte_yield") or 0
    pr = aksje.get("payout_ratio") or 0
    vekst = aksje.get("utbytte_vekst_5ar") or 0
    ar = aksje.get("ar_med_utbytte") or 0
    snitt_y = aksje.get("snitt_yield_5ar") or 0
    pb = aksje.get("pb_ratio") or 0
    pris = aksje.get("pris") or 0
    hoy = aksje.get("52u_hoy") or 0
    lav = aksje.get("52u_lav") or 0
    frekvens = aksje.get("frekvens", "") or ""
    mrd = aksje.get("markedsverdi_mrd") or 0
    siste_utbytte = aksje.get("siste_utbytte") or 0
    hist = aksje.get("historiske_utbytter") or []

    setninger = []

    # === EKSTRAORDINÆR YIELD ===
    if y > 15:
        setninger.append(
            f"Advarsel: Direkteavkastningen på {y:.1f}% er ekstraordinært høy og skyldes trolig et engangs- eller spesialutbytte — dette nivået er ikke representativt for normalt inntjeningsbasert utbytte."
        )
        if snitt_y and 0 < snitt_y < 50:
            if snitt_y < 15:
                setninger.append(
                    f"5-årssnittlig yield på {snitt_y:.1f}% gir et bedre bilde av det historiske normalleiet."
                )
            else:
                setninger.append(
                    f"Historisk snittavkastning på {snitt_y:.1f}% viser at ekstraordinære utbytter er et gjentakende mønster i dette selskapet."
                )
    elif y == 0 or y < 0.1:
        # Aksjer uten utbytte
        if siste_utbytte > 0:
            setninger.append(
                f"{ticker} betaler for øyeblikket ikke utbytte, men har historisk hatt utbetalinger — siste kjente utbytte var {siste_utbytte:.2f} NOK per aksje."
            )
        else:
            setninger.append(
                f"{ticker} er for øyeblikket ikke en utbytteaksje, og all verdiskapning forventes kanalisert gjennom kursvekst."
            )
        # Snitt yield
        if snitt_y and snitt_y > 2:
            setninger.append(
                f"Historisk har selskapet levert {snitt_y:.1f}% snittlig yield, så utbyttepolitikken kan gjenopptas."
            )
        elif hist and len(hist) >= 2:
            forste = hist[0]
            setninger.append(
                f"Selskapet betalte utbytte i {forste['ar']} og er kjent som en potensiell utbyttebetaler igjen ved sterkere inntjening."
            )
    else:
        # Normal yield
        if y > 10:
            setninger.append(
                f"Direkteavkastningen på {y:.1f}% er svært høy — attraktivt for inntektssøkende, men krever kritisk vurdering av bærekraft."
            )
        elif y > 7:
            setninger.append(
                f"Direkteavkastningen på {y:.1f}% er klart over snittet for Oslo Børs og meget attraktiv for inntektsinvestorer."
            )
        elif y > 5:
            setninger.append(
                f"Direkteavkastningen på {y:.1f}% er solid og godt over normalt rentenivå, noe som gjør aksjen interessant for utbyttejegere."
            )
        elif y > 3:
            setninger.append(
                f"Direkteavkastningen på {y:.1f}% er moderat, men tilstrekkelig for langsiktige utbytteinvestorer."
            )
        else:
            setninger.append(
                f"Direkteavkastningen på {y:.1f}% er lav — aksjen egner seg primært for investorer som verdsetter stabilitet og potensielt utbyttevekst fremfor umiddelbar inntekt."
            )

    # === P/E VURDERING ===
    if pe and pe > 0:
        if pe > 400:
            setninger.append(
                f"P/E på {pe:.0f} er meningsløst høy og gjenspeiler midlertidig svake resultater — konvensjonell P/E-analyse er lite relevant her; kontantstrøm og utbytteevne bør vektlegges i stedet."
            )
        elif pe > 0:
            label = sektor_pe_label(pe, sektor)
            if label == "svært lavt":
                if y > 4:
                    setninger.append(
                        f"P/E på {pe:.1f} er svært lavt for {sektor.lower()}-sektoren, og kombinert med {y:.1f}% yield fremstår verdsettelsen som meget attraktiv."
                    )
                else:
                    setninger.append(
                        f"P/E på {pe:.1f} er svært lavt og indikerer at markedet priser aksjen med betydelig rabatt sammenlignet med sektornormen."
                    )
            elif label == "lavt":
                setninger.append(
                    f"P/E på {pe:.1f} er lavt for {sektor.lower()}-sektoren og tyder på attraktiv inngangsverdi — forutsatt at inntjeningen er normalisert."
                )
            elif label == "normalt for sektoren":
                setninger.append(
                    f"P/E på {pe:.1f} er i tråd med normalt nivå for {sektor.lower()}-sektoren og gir et balansert bilde av verdsettelsen."
                )
            elif label == "noe høyt":
                setninger.append(
                    f"P/E på {pe:.1f} er noe over sektorsnittet for {sektor.lower()} — aksjen er ikke billig, men premien kan forsvares av sterk merkevare og stabile kontantstrømmer."
                )
            elif label == "klart høyt":
                if y > 5:
                    setninger.append(
                        f"P/E på {pe:.1f} er klart høyt for sektoren til tross for {y:.1f}% yield — investorer betaler en tydelig premium, noe som øker risikoen ved inntjeningsskuffelser."
                    )
                else:
                    setninger.append(
                        f"P/E på {pe:.1f} er klart over sektorsnittet og krever solid inntjeningsvekst for å rettferdiggjøre dagens kurs."
                    )
            else:
                setninger.append(
                    f"P/E på {pe:.1f} er ekstremt høyt og gjenspeiler enten midlertidige svake resultater eller at markedet priser inn et kraftig inntjeningshopp fremover."
                )

    # === PAYOUT RATIO ===
    if pr and pr > 0 and y > 0.1:
        if pr < 0:
            setninger.append(
                "Negativ utbetalingsgrad indikerer at utbyttet finansieres utenfor ordinær drift — ikke bærekraftig langsiktig."
            )
        elif pr < 35:
            setninger.append(
                f"Utbetalingsgraden på {pr:.0f}% er konservativt lav og gir god buffer for utbytteøkninger — selskapet beholder mesteparten av overskuddet til reinvestering."
            )
        elif pr < 55:
            setninger.append(
                f"Utbetalingsgraden på {pr:.0f}% er solid og forsvarlig, med god sikkerhetsmargin for utbyttet selv ved svakere kvartal."
            )
        elif pr < 75:
            setninger.append(
                f"Utbetalingsgraden på {pr:.0f}% er moderat høy, men bærekraftig dersom inntjeningen holder seg stabil."
            )
        elif pr < 100:
            setninger.append(
                f"Utbetalingsgraden på {pr:.0f}% er høy og gir begrenset sikkerhetsmargin — utbyttet er sårbart ved inntjeningsfall."
            )
        elif pr < 150:
            setninger.append(
                f"Utbetalingsgraden på {pr:.0f}% overstiger årsresultatet, noe som er et advarselstegn — utbyttet er sannsynlig finansiert av sterk fri kontantstrøm, men er ikke bærekraftig over tid."
            )
        else:
            setninger.append(
                f"Utbetalingsgraden på {pr:.0f}% er ekstremt høy og reflekterer at selskapet benytter en kontantstrøm-basert utbyttepolitikk fremfor regnskapsmessig overskudd — vanlig i E&P-selskaper, men innebærer økt risiko ved lavere oljepriser."
            )

    # === VEKSTTRENDER ===
    if vekst and vekst != 0 and y > 0.1:
        if vekst > 20:
            setninger.append(
                f"Utbytteveksten på {vekst:.1f}% per år siste fem år er bemerkelsesverdig sterk og gir imponerende realavkastning for langsiktige aksjonærer."
            )
        elif vekst > 10:
            setninger.append(
                f"Med {vekst:.1f}% gjennomsnittlig utbyttevekst per år siste fem år leverer selskapet godt over inflasjonen og styrker kjøpekraften for utbytteinvestorer."
            )
        elif vekst > 3:
            setninger.append(
                f"Utbytteveksten på {vekst:.1f}% per år er moderat positiv og holder tritt med inflasjon."
            )
        elif vekst > 0:
            setninger.append(
                f"Utbytteveksten på {vekst:.1f}% per år er beskjeden, men positiv — langsiktig retning er riktig."
            )
        elif vekst > -8:
            setninger.append(
                f"Utbyttet har falt med {abs(vekst):.1f}% per år siste fem år, noe som reflekterer press på inntjeningen og bør monitoreres nøye."
            )
        else:
            setninger.append(
                f"Utbyttet har falt med {abs(vekst):.1f}% per år siste fem år — et tydelig faresignal som indikerer strukturell svekkelse i inntjeningen."
            )

    # === HISTORIKK ===
    if ar >= 25:
        setninger.append(
            f"Med {ar} år sammenhengende utbytte er {ticker} en av de mest pålitelige utbyttebetalerne på Oslo Børs — historikken bygger tillit til langsiktig kapitalavkastning."
        )
    elif ar >= 15:
        setninger.append(
            f"Selskapet har betalt utbytte i {ar} år på rad — solid historikk som underbygger ledelsens langsiktige fokus på aksjonæravkastning."
        )
    elif ar >= 8:
        setninger.append(
            f"Selskapet har betalt utbytte i {ar} år på rad, noe som gir god forutsigbarhet for utbytteinvestorer."
        )
    elif ar >= 3:
        setninger.append(
            f"Med {ar} år utbyttehistorikk er grunnlaget for langsiktig pålitelighet i ferd med å etableres — men historikken er ennå begrenset."
        )
    elif ar > 0:
        setninger.append(
            f"Begrenset utbyttehistorikk på {ar} år gir lite grunnlag for å vurdere langsiktig konsistens."
        )
    else:
        setninger.append(
            "Selskapet mangler registrert sammenhengende utbyttehistorikk, noe som gjør det vanskelig å bedømme påliteligheten på lang sikt."
        )

    # === HISTORISK YIELD-TREND (fra historiske_utbytter) ===
    if len(hist) >= 3 and y > 0.1:
        siste_yields = [h["yield"] for h in hist[-3:] if h.get("yield")]
        if siste_yields and len(siste_yields) >= 2:
            trend = siste_yields[-1] - siste_yields[0]
            if abs(trend) > 2:
                if trend > 0:
                    setninger.append(
                        f"Historisk yield-trend er stigende de siste tre år, noe som reflekterer voksende utbyttebetalinger."
                    )
                else:
                    setninger.append(
                        f"Historisk yield-trend har vært fallende de siste tre år, primært drevet av kursvekst."
                    )

    # === KURSPOSISJON ===
    if pris and hoy and lav and hoy > lav:
        posisjon = (pris - lav) / (hoy - lav)
        if posisjon > 0.90:
            setninger.append(
                "Aksjen handles nær 52-ukers topp og gir begrenset margin of safety for nye investorer."
            )
        elif posisjon < 0.15:
            setninger.append(
                f"Kursen er nær 52-ukers bunn — potensielt attraktivt inngangspunkt for tålmodige, langsiktige investorer."
            )
        elif posisjon < 0.35:
            setninger.append(
                f"Aksjen handles i nedre del av 52-ukersintervallet, noe som kan by på interessante inngangsmuligheter."
            )

    # === P/B ===
    if pb and pb > 0:
        if sektor in ("Finans", "Forsikring"):
            if pb < 1.0:
                setninger.append(
                    f"P/B under 1 ({pb:.2f}) er uvanlig for finansaksjer og kan bety at markedet priser inn økt taprisiko eller at aksjen er underpriset."
                )
            elif pb < 1.5:
                setninger.append(f"P/B på {pb:.2f} er moderat og fornuftig for finanssektoren.")
        elif sektor == "Eiendom":
            if pb < 1.0:
                setninger.append(f"P/B på {pb:.2f} tyder på at eiendomsporteføljen handles med rabatt til bokført verdi.")
        elif pb > 5 and pe and pe > 0:
            setninger.append(
                f"Høy P/B på {pb:.2f} reflekterer markedets forventning om sterk fremtidig avkastning på egenkapitalen."
            )

    # === FREKVENS ===
    if frekvens == "Kvartalsvis" and y > 0.1:
        setninger.append("Kvartalsvis utbetaling gir god likviditetsflyt og reduserer reinvesteringsrisiko.")
    elif frekvens == "Månedlig" and y > 0.1:
        setninger.append("Månedlig utbetaling er sjeldent på Oslo Børs og meget gunstig for inntektsinvestorer.")

    # === MARKEDSVERDI-KONTEKST ===
    if mrd and mrd > 0:
        if mrd > 200:
            setninger.append(
                f"Med markedsverdi på {mrd:.0f} milliarder NOK er {ticker} et av de større selskapene på Oslo Børs, noe som gir god likviditet og institusjonell interesse."
            )
        elif mrd < 5:
            setninger.append(
                f"Lav markedsverdi på {mrd:.1f} mrd NOK innebærer lavere likviditet og høyere kurssvingninger enn for større selskaper."
            )

    # === KONKLUSJON ===
    score = 0
    if 3.5 <= y <= 10:
        score += 2
    elif y > 10 or (y > 0 and y < 3):
        score += 1
    if 0 < pr < 65:
        score += 2
    elif 65 <= pr < 85:
        score += 1
    elif pr >= 100:
        score -= 1
    if pe > 0:
        low, high = SEKTOR_PE.get(sektor, (12, 22))
        if pe < high:
            score += 1
    if vekst > 5:
        score += 2
    elif vekst > 0:
        score += 1
    elif vekst < -5:
        score -= 1
    if ar >= 20:
        score += 2
    elif ar >= 10:
        score += 1

    if score >= 7:
        kvalitet = "høy"
        konklusjoner = [
            f"Samlet sett fremstår {ticker} som et solid utbyttealternativ med høy kvalitet — attraktiv yield, bærekraftig utbetalingsgrad og lang historikk gir god inntektssikkerhet.",
            f"{ticker} scorer sterkt på de viktigste utbyttemålene og passer godt for langsiktige utbytteinvestorer med lav til moderat risikotoleranse.",
            f"Høy utbyttekvalitet totalt sett — {ticker} er et naturlig kjernevalg i en norsk utbytteportefølje.",
        ]
    elif score >= 4:
        kvalitet = "moderat"
        if pr > 90:
            konklusjoner = [
                f"Moderat utbyttekvalitet totalt sett — {ticker} har interessant yield, men den høye utbetalingsgraden krever at kontantstrøm og inntjening holder seg.",
                f"{ticker} er et moderat alternativ for utbytteinvestorer — yield er tiltrekkende, men bærekraften avhenger av stabil drift fremover.",
                f"Samlet sett moderat egnet for utbytteinvestorer — payout ratio er den primære risikofaktoren og bør monitoreres.",
            ]
        elif y < 3:
            konklusjoner = [
                f"{ticker} er primært interessant som vekstalternativ; utbyttet er lavt og egner seg best for investorer med lang horisont.",
                f"Lav direkteavkastning gjør {ticker} til et moderat valg for utbytteinvestorer — best egnet i kombinasjon med aksjer som gir høyere løpende inntekt.",
                f"Moderat utbyttekvalitet — stabiliteten er til stede, men yield er for lav til å stå alene som inntektskilde.",
            ]
        else:
            konklusjoner = [
                f"Samlet sett et moderat alternativ for utbytteinvestorer i {sektor.lower()}-sektoren — noen sterke sider, men også faktorer som trekker ned.",
                f"{ticker} passer for investorer med moderat risikotoleranse som søker balanse mellom løpende inntekt og kurseksponering.",
                f"Moderat utbyttekvalitet — kan inngå som del av en diversifisert norsk utbytteportefølje.",
            ]
    else:
        kvalitet = "lav"
        konklusjoner = [
            f"{ticker} har lav utbyttekvalitet etter en helhetsvurdering — yield alene rettferdiggjør ikke posisjonen uten at fundamentale tall forbedres.",
            f"Lav utbyttekvalitet totalt sett — investorer bør vurdere om risikoen er tilstrekkelig kompensert gjennom direkteavkastningen.",
            f"{ticker} anbefales med forsiktighet for rene utbytteinvestorer — inntjeningssituasjonen gir liten trygghet for fremtidige utbetalinger.",
        ]

    random.seed(hash(ticker) % 1000)
    konklusjon_setning = random.choice(konklusjoner)

    # === SAMLE OG JUSTERE LENGDE ===
    # Konklusjonen beskyttes — klipp kun i brødteksten
    konklusjon_ord = len(konklusjon_setning.split())
    maks_kropp = 130 - konklusjon_ord

    kropp = " ".join(setninger)
    kropp_ord = kropp.split()

    if len(kropp_ord) > maks_kropp:
        klipp = " ".join(kropp_ord[:maks_kropp])
        siste = max(klipp.rfind(". "), klipp.rfind("! "))
        if siste > 60:
            kropp = klipp[:siste + 1]
        else:
            kropp = klipp.rstrip(",;:") + "."

    tekst = kropp.rstrip() + " " + konklusjon_setning

    # For kort — legg til ekstra setning
    antall = len(tekst.split())
    if antall < 90:
        ekstra = []
        # Snitt yield kommentar
        if snitt_y and snitt_y > 0 and abs(snitt_y - y) > 1.5:
            if y > snitt_y:
                ekstra.append(
                    f"Nåværende yield på {y:.1f}% er høyere enn 5-årssnitt på {snitt_y:.1f}%, noe som kan indikere underprising eller økt risikopremie."
                )
            else:
                ekstra.append(
                    f"5-årssnittlig yield på {snitt_y:.1f}% er over nåværende {y:.1f}%, noe som gjenspeiler kursvekst over perioden."
                )
        # Sektor-kommentar (kun for aksjer som faktisk betaler utbytte)
        if sektor and y > 0.1:
            ekstra.append(
                f"Innenfor {sektor.lower()}-sektoren på Oslo Børs er {ticker} blant de mer fremtredende utbyttebetalerne."
            )
        # Lav PE ekstra
        if pe and 0 < pe < 10:
            ekstra.append(
                f"Den lave P/E på {pe:.1f} bør ses i lys av sykliske svingninger — gjennomsnittlig inntjening over en hel syklus er et bedre sammenligningsgrunnlag."
            )
        # Utbyttefrekvens
        if frekvens and frekvens not in ("Kvartalsvis", "Månedlig") and y > 0:
            ekstra.append(
                f"Utbyttet utbetales {frekvens.lower()}, noe som er typisk for selskaper i {sektor.lower()}-sektoren."
            )
        # Legg til inntil to ekstra
        for e in ekstra[:2]:
            ny_tekst = tekst.rstrip(".") + ". " + e
            if len(ny_tekst.split()) <= 135:
                tekst = ny_tekst
            if len(tekst.split()) >= 90:
                break

    # Siste justering — fortsatt for kort: legg til kontekstuell observasjon
    antall = len(tekst.split())
    if antall < 90:
        # Prøv ulike kontekstuavhengige setninger
        padding_kandidater = [
            f"Investorer bør følge inntjeningsutviklingen nøye for {ticker} og vurdere aksjen i lys av egne mål for inntekt versus kursavkastning.",
            f"En grundig gjennomgang av selskapets balanse og kontantstrømsutvikling anbefales før man tar en investeringsbeslutning i {ticker}.",
            f"For en fullstendig vurdering bør {ticker} ses i kontekst av bredere sektordynamikk, rentenivå og makroøkonomiske utsikter.",
            f"Uansett utbytteprofil bør {ticker} vurderes opp mot den øvrige porteføljens eksponering mot {sektor.lower() if sektor else 'sektoren'} for å sikre god risikospredning.",
            f"Aktive utbytteinvestorer bør følge kvartalsvise resultater og eventuelle policyendringer for {ticker} tett, ettersom disse vil påvirke fremtidig inntektsevne.",
        ]
        random.seed(hash(ticker + "_pad") % 1000)
        for generell in random.sample(padding_kandidater, len(padding_kandidater)):
            ny_tekst = tekst.rstrip(".") + ". " + generell
            if len(ny_tekst.split()) <= 135:
                tekst = ny_tekst
            if len(tekst.split()) >= 90:
                break

    return tekst.strip()


def main():
    with open("data/aksjer.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    aksjer = data["aksjer"]

    for aksje in aksjer:
        oppsummering = generer_oppsummering(aksje)
        aksje["ai_oppsummering"] = oppsummering
        aksje["ai_oppsummering_dato"] = DATO_TID

    data["aksjer"] = aksjer

    with open("data/aksjer.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Ferdig! Oppdaterte {len(aksjer)} aksjer.")

    lengder = [len(a["ai_oppsummering"].split()) for a in aksjer]
    print(f"Ord: min={min(lengder)}, maks={max(lengder)}, snitt={sum(lengder)/len(lengder):.1f}")
    under = sum(1 for l in lengder if l < 90)
    over = sum(1 for l in lengder if l > 130)
    print(f"Under 90 ord: {under} | Over 130 ord: {over}")

    if under > 0:
        print("Fortsatt for korte:")
        for a in aksjer:
            l = len(a["ai_oppsummering"].split())
            if l < 90:
                print(f"  {a['ticker']}: {l} ord")


if __name__ == "__main__":
    main()
