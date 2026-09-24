#!/usr/bin/env python3
"""
valider_data.py — Datakvalitetssjekk for data/aksjer.json

Kjøres automatisk etter fetch_stocks.py i GitHub Actions.
Avslutter med kode 1 hvis det finnes kritiske feil (yield-avvik > 2%).
"""

import json
import sys
import os

# Støtter kjøring fra repo-rot eller scripts/-mappen
AKSJER_JSON = os.path.join(os.path.dirname(__file__), '..', 'data', 'aksjer.json')


# Sjekk 10 — samme grenser og samme regel som vist_over_betalt() i
# fetch_stocks.py. Kopiert fordi dette skriptet må kjøre uten yfinance;
# TestVistOverBetalt.test_samsvar_med_valider_data holder de to like.
VIST_OVER_BETALT_PP = 1.0
VIST_OVER_BETALT_ANDEL = 0.3


def vist_over_betalt(a):
    """(vist yield, betalt 12 mnd yield) når det viste tallet er vesentlig høyere."""
    if a.get('utbytte_12m') is None:
        return None
    pris = a.get('pris') or 0
    vist = float(a.get('utbytte_yield') or 0)
    if pris <= 0 or vist <= 0:
        return None
    betalt = float(a['utbytte_12m']) / pris * 100
    if vist - betalt >= VIST_OVER_BETALT_PP and (vist - betalt) / vist >= VIST_OVER_BETALT_ANDEL:
        return round(vist, 2), round(betalt, 2)
    return None


def valider_data(filsti=AKSJER_JSON):
    """Les aksjer.json og kjør alle datakvalitetssjekker."""
    with open(filsti, encoding='utf-8') as f:
        data = json.load(f)

    aksjer = data.get('aksjer', [])
    advarsler = []
    kritiske_feil = []

    # Feltene kan være null i tillegg til fraværende: fetch_stocks.py setter
    # bevisst snitt_yield_5ar til null når ingen yield er troverdig. dict.get()
    # med standardverdi fanger kun det fraværende tilfellet, så en eksplisitt
    # null ville krasjet sammenligningene under.
    def _tall(kilde, felt, standard=0):
        v = kilde.get(felt)
        return v if isinstance(v, (int, float)) else standard

    for a in aksjer:
        ticker = a.get('ticker', '?')
        pris = _tall(a, 'pris')
        utbytte_per_aksje = _tall(a, 'utbytte_per_aksje')
        utbytte_yield = _tall(a, 'utbytte_yield')
        snitt_yield_5ar = _tall(a, 'snitt_yield_5ar')
        payout_ratio = _tall(a, 'payout_ratio')
        historiske_utbytter = a.get('historiske_utbytter') or []

        # Sjekk 1: utbytte_yield skal stemme overens med utbytte_per_aksje / pris
        if pris > 0 and utbytte_per_aksje > 0:
            beregnet_yield = round(utbytte_per_aksje / pris * 100, 2)
            avvik = abs(beregnet_yield - utbytte_yield)
            if avvik > 2.0:
                feilmelding = (
                    f"KRITISK {ticker}: utbytte_yield={utbytte_yield}% "
                    f"men utbytte_per_aksje/pris={beregnet_yield}% "
                    f"(avvik={avvik:.2f}%)"
                )
                kritiske_feil.append(feilmelding)
            elif avvik > 0.5:
                advarsler.append(
                    f"ADVARSEL {ticker}: yield-avvik={avvik:.2f}% "
                    f"(lagret={utbytte_yield}%, beregnet={beregnet_yield}%)"
                )

        # Sjekk 2: utbytte_yield > 60% er mistenkelig
        if utbytte_yield > 60:
            advarsler.append(
                f"ADVARSEL {ticker}: utbytte_yield={utbytte_yield}% er usannsynlig høy (>60%)"
            )

        # Sjekk 3: snitt_yield_5ar > 200% er mistenkelig
        if snitt_yield_5ar > 200:
            advarsler.append(
                f"ADVARSEL {ticker}: snitt_yield_5ar={snitt_yield_5ar}% er usannsynlig høy (>200%)"
            )

        # Sjekk 4: historiske yields > 200% er mistenkelige
        # yield kan være None når fetch_stocks.py ikke fant et troverdig tall —
        # det er en bevisst markering, ikke et avvik å rapportere.
        for h in historiske_utbytter:
            hist_yield = h.get('yield')
            ar = h.get('ar', '?')
            if hist_yield is not None and hist_yield > 200:
                advarsler.append(
                    f"ADVARSEL {ticker} {ar}: historisk yield={hist_yield}% er usannsynlig høy (>200%)"
                )

        # Sjekk 5: utbytte_per_aksje > 5x siste år i historiske_utbytter (delår-unntak)
        if utbytte_per_aksje > 0 and historiske_utbytter:
            siste_ar = max(historiske_utbytter, key=lambda x: x.get('ar', 0))
            siste_historisk_utbytte = siste_ar.get('utbytte', 0)
            if siste_historisk_utbytte > 0 and utbytte_per_aksje > siste_historisk_utbytte * 5:
                advarsler.append(
                    f"ADVARSEL {ticker}: utbytte_per_aksje={utbytte_per_aksje} "
                    f"er >5x siste historiske år ({siste_ar['ar']}: {siste_historisk_utbytte}) "
                    f"— mulig delår eller feil"
                )

        # Sjekk 6: tall på siden som ikke kan stemme sammen.
        #
        # Alle sjekkene over måler yield mot utbytte_per_aksje og kurs, og de
        # tre henger sammen. Men historiske beløp og 52-ukers høy sjekkes ikke
        # mot dagens kurs i det hele tatt. 2020 Bulkers viste «2026: 133,57 NOK
        # per aksje» og «52-ukers kurs 2,56 – 152,00» på en aksje som koster
        # 4,35 kr — etter en stor kapitalutdeling i mai 2026 som gjorde de
        # gamle tallene uforenlige med dagens kurs. Rapporten sa likevel
        # «Datakvalitet OK».
        if pris > 0:
            for h in historiske_utbytter:
                belop = h.get('utbytte') or 0
                # Terskel 2x: et utbytte litt over kursen kan være et ekte
                # toppår for en shippingaksje (GSF 1,2x, WEST 1,3x). Det
                # dobbelte av kursen er derimot ikke en utbetaling — det er
                # tall fra to ulike aksjebaser.
                if belop > pris * 2:
                    advarsler.append(
                        f"ADVARSEL {ticker} {h.get('ar')}: historisk utbytte "
                        f"{belop} > dagens kurs {pris} — beløpet kan ikke "
                        f"sammenlignes med dagens kurs (splitt, spleis eller "
                        f"kapitalutdeling?)"
                    )
                    break
            hoy52 = _tall(a, '52u_hoy')
            if hoy52 > pris * 3:
                advarsler.append(
                    f"ADVARSEL {ticker}: 52-ukers høy {hoy52} er {hoy52/pris:.0f}x "
                    f"dagens kurs {pris} — serien er neppe justert for en "
                    f"selskapshendelse"
                )

        # Sjekk 7: årsraten er lavere enn én enkelt utbetaling.
        #
        # utbytte_per_aksje skal være utbyttet for et helt år. For en aksje
        # som betaler flere ganger i året kan den derfor ikke være mindre enn
        # én utbetaling — da er tallet en delsum, og yielden på siden blir for
        # lav. Årsaken er kryssvalideringen i fetch_stocks.py, som bytter ut
        # Yahoos rate med totalen for siste hele kalenderår: for et selskap
        # som startet eller trappet opp utbyttet i løpet av det året er den
        # totalen et delår. SATS viste 1,37 % mot reelle ~3 %, Entra 1,04 %
        # mot 2,08 % (to like utbetalinger à 1,10 kr).
        #
        # Sjekken gir bare varsel — den retter ikke tallet. Å utlede den
        # riktige årsraten krever at ordinære utbytter skilles fra
        # ekstraordinære, og det finnes ingen regel som treffer for alle:
        # summen av siste 12 mnd gjør GSF til 116 % yield, mens Yahoos rate
        # gjør Entra til halvparten av det aksjonæren faktisk fikk.
        pr_ar = {'Månedlig': 12, 'Kvartalsvis': 4, 'Halvårlig': 2}
        if a.get('frekvens') in pr_ar and utbytte_per_aksje > 0:
            siste_utbytte = _tall(a, 'siste_utbytte')
            if 0 < utbytte_per_aksje < siste_utbytte:
                advarsler.append(
                    f"ADVARSEL {ticker}: utbytte_per_aksje={utbytte_per_aksje} "
                    f"er lavere enn siste enkeltutbetaling ({siste_utbytte}) "
                    f"for en {a['frekvens'].lower()} betaler — årsraten er "
                    f"trolig et delår, og yielden ({utbytte_yield}%) for lav"
                )

        # Sjekk 8: én enkeltutbetaling større enn hele aksjekursen.
        #
        # siste_utbytte valideres ingen andre steder — alle sjekkene over går
        # via utbytte_per_aksje, og den kan være 0 samtidig som siste_utbytte
        # er tull. KMC Properties sto med siste_utbytte=6958,03 på en aksje
        # til 24,80 kr, med utbytte_per_aksje=0 og tom utbyttehistorikk, og
        # slapp gjennom hver eneste sjekk.
        #
        # Feltet er ikke bare pynt: appen viser det som «Siste utbytte» i
        # aksjelisten og bruker det til å regne ut forventet utbetaling for
        # porteføljen (assets/ui.js), så et vrøvletall gir brukeren en
        # forventet utbetaling som er tusen ganger for høy.
        siste_utbytte = _tall(a, 'siste_utbytte')
        if pris > 0 and siste_utbytte > pris:
            advarsler.append(
                f"ADVARSEL {ticker}: siste_utbytte={siste_utbytte} er større "
                f"enn hele aksjekursen ({pris}) — én utbetaling kan ikke "
                f"overstige kursen uten en selskapshendelse"
            )

    # Sjekk 10: vi viser en yield høyere enn det selskapet faktisk har betalt.
    #
    # Alle sjekkene over sammenligner våre egne felt med hverandre. Ingen av
    # dem spør om tallet stemmer med virkeligheten, så et utbytte som hadde
    # stoppet, eller et engangsbeløp regnet som årlig, passerte hver eneste
    # en. Målt 24.09.2026: GOD 14,1 % mot 3,5 % betalt, KID 8,4 % mot 4,2 %,
    # BOR 5,7 % mot 2,9 %, REACH og MGN med yield uten én utbetaling på over
    # et år. Alle ble funnet fordi noen spurte, ikke fordi noe varslet.
    #
    # Bare retningen «vist over betalt»: under er som regel en ekstraordinær
    # utdeling i vinduet, og da er det riktig å ikke vise den som løpende.
    # Varsler, blokkerer ikke — en ny betaler som har tatt én kvartalsutbetaling
    # vil ligge over, og det kan være riktig.
    i_dag = data.get('sist_oppdatert', '')[:10]
    over = []
    for a in aksjer:
        r = vist_over_betalt(a)
        if not r:
            continue
        vist, betalt = r
        hint = []
        if not a.get('utbytte_12m'):
            hint.append('ingen utbetaling siste 12 mnd — har utbyttet stoppet?')
        ex = a.get('ex_dato') or ''
        if ex and ex >= i_dag:
            hint.append(f'kommende ex-dato {ex} — engangsbeløp regnet som årlig?')
        forventet = {'Månedlig': 12, 'Kvartalsvis': 4, 'Halvårlig': 2, 'Årlig': 1}.get(a.get('frekvens'))
        antall = a.get('utbytte_12m_antall') or 0
        if forventet and 0 < antall < forventet:
            hint.append(f'{antall} av {forventet} utbetalinger i vinduet — ny eller hevet betaler?')
        over.append((vist - betalt, a.get('ticker', '?'), vist, betalt, hint))
    for _, ticker, vist, betalt, hint in sorted(over, reverse=True):
        advarsler.append(
            f"ADVARSEL {ticker}: vist yield {vist} % er høyere enn det som er "
            f"betalt siste 12 mnd ({betalt} %)"
            + (f" — {'; '.join(hint)}" if hint else "")
        )
    if not any(a.get('utbytte_12m') is not None for a in aksjer):
        print("Sjekk 10 hoppet over: utbytte_12m finnes ikke ennå (kommer ved neste fulle henting).")

    # Skriv ut rapport
    print("=" * 60)
    print("DATAKVALITETSRAPPORT — aksjer.json")
    print("=" * 60)
    print(f"Antall aksjer kontrollert: {len(aksjer)}")
    print()

    if advarsler:
        print(f"Advarsler ({len(advarsler)}):")
        for a in advarsler:
            print(f"  {a}")
        print()
    else:
        print("Ingen advarsler funnet.")
        print()

    if kritiske_feil:
        print(f"KRITISKE FEIL ({len(kritiske_feil)}):")
        for f in kritiske_feil:
            print(f"  {f}")
        print()
        print("Avslutt med kode 1 — kritiske feil funnet.")
        return False
    else:
        print("Ingen kritiske feil. Datakvalitet OK.")
        return True


if __name__ == '__main__':
    ok = valider_data()
    sys.exit(0 if ok else 1)
