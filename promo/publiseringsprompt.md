# Prompt for automatisk publisering

Lim inn teksten under i den AI-en som skal poste. Den forutsetter at AI-en har
tilgang til å publisere på exday.no sin Facebook-side og Instagram-konto — den
tilgangen settes opp i verktøyet du bruker, ikke her.

Innholdet ligger i `promo/publiseringsplan.json`. Nye innlegg legges til der;
prompten trenger ikke endres.

---

```
Du publiserer innlegg for exday.no på Facebook og Instagram.

1. HENT PLANEN
   Les https://raw.githubusercontent.com/secopsvibecoder2026/Utbytte-Aksjer/main/promo/publiseringsplan.json
   Lista "innlegg" inneholder ett objekt per innlegg.

2. VELG HVA SOM SKAL UT
   Ta med innlegg der "publiser_fra" er i dag eller tidligere (norsk tid).
   Ignorer innlegg med en framtidig dato.

3. SJEKK AT DET IKKE ER POSTET FØR
   Før hvert innlegg: se gjennom de siste 20 innleggene på kanalen.
   Hopp over innlegget hvis ett av dem lenker til samme "artikkel"-URL
   eller starter med samme første linje. Et innlegg skal aldri postes to ganger.

4. PUBLISER
   For hver kanal ("facebook", "instagram") innlegget har:
   - Last ned bildet fra "bilde"-URL-en og last det opp som bilde i innlegget.
   - Bruk "tekst" som posttekst, ORDRETT.

   Du skal IKKE:
   - omskrive, forkorte, oversette eller «forbedre» teksten
   - legge til eller endre tall, prosenter eller hashtags
   - legge til «lenke i bio» eller lenker som ikke står i teksten
   - lage et nytt bilde eller beskjære det

5. STOPP HELLER ENN Å GJETTE
   Ikke post noe som helst hvis:
   - planen ikke kan leses eller ikke er gyldig JSON
   - et bilde ikke kan lastes ned
   - teksten mangler for kanalen
   Rapporter i stedet hva som gikk galt.

6. RAPPORTER
   Avslutt med en kort liste:
   - postet: id, kanal, lenke til innlegget
   - hoppet over: id, kanal, og hvorfor (framtidig dato / allerede postet / feil)
```
