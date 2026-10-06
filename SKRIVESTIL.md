# Skrivestil for exday.no

Gjelder alt som publiseres: artikler, promoinnlegg, selskapstekstene på
aksjesidene og sektortekster. Promo-, artikkel- og selskapstekstagenten leser
denne filen før de skriver. Selskapstekstene sjekkes med
`python scripts/valider_innledning.py --ticker TICKER`, som bruker de samme
målingene.

Målet er at teksten skal lese som om en kunnskapsrik nordmann skrev den til
en venn som sparer i aksjer. Ikke som en presentasjon, ikke som en
pressemelding og ikke som en språkmodell.

Sjekk teksten med `python scripts/sjekk_sprak.py <fil>` før du leverer. Se
nederst for hva skriptet måler.

## Tankestreker

Dette er det tydeligste tegnet på maskinskrevet tekst. Artiklene skrevet før
oktober 2026 hadde mellom 18 og 49 tankestreker hver, rundt to per hundre ord.
Norsk sakprosa har sjelden mer enn én per side.

**Grense: høyst én tankestrek per 200 ord, og aldri to i samme avsnitt.**

En tankestrek erstattes nesten alltid best av noe annet:

| I stedet for | Skriv |
|---|---|
| «Prinsippet er det samme — du kjøper manuelt for utbyttet.» | «Prinsippet er det samme. Du kjøper manuelt for utbyttet.» |
| «Porteføljen vokser lineært — samme kronetilskudd hvert år.» | «Porteføljen vokser lineært, med samme kronetilskudd hvert år.» |
| «Det er lett å blande sammen — og det gjorde vi også.» | «Det er lett å blande sammen. Det gjorde vi også.» |
| «Selskapet har betalt 21 år på rad» — men betyr det sammenhengende? | Står bedre som to setninger, eller med kolon. |

Punktum, komma, kolon og parentes dekker nesten alle tilfeller. Bindestrek i
sammensatte ord («5-årssnitt») og tankestrek i tallområder («2021–2025») er
ikke tankestreker i denne forstand og telles ikke.

## Ord og vendinger som lyder som en maskin

Ikke bruk disse. De sier lite og gjør teksten lik all annen generert tekst:

- «La oss se på …», «La oss dykke ned i …»
- «I denne artikkelen skal vi …», «Her er det du trenger å vite»
- «Kort fortalt», «Kort sagt», «Oppsummert», «Med andre ord» (start heller
  med selve poenget)
- «Det er verdt å merke seg», «Det er viktig å huske på at»
- «Nøkkelen er …», «Svaret er enkelt:», «Spørsmålet er:»
- «ikke bare … men også», «Det handler ikke om X, det handler om Y»
- «robust», «sømløs», «helhetlig», «kraftig verktøy», «navigere»,
  «landskapet», «game changer», «spillveksler», «unik mulighet»
- «uansett hvor du er i …», «enten du er nybegynner eller erfaren»

Én av disse i en tekst er ikke krise. Et mønster av dem er det leseren
merker.

## Setninger og avsnitt

- **Si det konkrete.** «Equinor betalte 3,69 kr per aksje i august» slår
  «Equinor er kjent for et attraktivt utbytte». Har du ikke et konkret tall
  eller eksempel, er setningen ofte unødvendig.
- **Ikke tre av alt.** Generert tekst lister gjerne nøyaktig tre adjektiver
  eller tre punkter. Skriv så mange som det faktisk er.
- **Ingen retoriske spørsmål som du svarer på selv** i neste setning («Hva
  betyr dette for deg? Jo, …»). Ett i en innledning kan gå. Ikke som mønster.
- **Ingen oppsummering til slutt som gjentar avsnittene over.** Avslutt med
  noe leseren kan gjøre, eller slutt når poenget er sagt.
- **Varier lengden.** Korte setninger mellom de lange. Ikke alle avsnitt på
  tre setninger.
- **Overskrifter er beskrivende, ikke spissformulerte.** «Slik beregnes
  skjermingsfradraget» er bedre enn «Skjermingsfradraget: din beste venn».
- **Kolon-overskrifter i teksten** («Fordelen:», «Ulempen:») bare der det
  faktisk er en liste. Ikke som stilgrep foran hvert avsnitt.

## Promoinnlegg spesielt

- Ett poeng per innlegg. Hvis du trenger «og i tillegg», er det to innlegg.
- 🔹-punkter er greit i Facebook-teksten, høyst tre.
- Høyst ett utropstegn, helst ingen.
- Emoji bare som punktmerke eller én foran lenken (👉). Ikke inni setninger.

## Hva sjekk_sprak.py måler

```bash
python scripts/sjekk_sprak.py artikler/min-artikkel/index.html
python scripts/sjekk_sprak.py --plan          # siste innlegg i promo/publiseringsplan.json
python scripts/sjekk_sprak.py --streng FIL    # exit 1 ved brudd
```

- tankestreker per 200 ord, og avsnitt med mer enn én
- vendingene fra listen over

Skriptet fanger det som kan telles. Les teksten høyt for det som ikke kan
det: lyder den som deg, eller som et skjema?
