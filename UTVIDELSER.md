# exday.no — Utvidelser (agenter og premium)

Forslag til nye AI-agenter og nye inntektskilder, utover det som allerede står i
`ROADMAP.md` og `ROADMAP_NYE_IDEER.md`. De filene er funksjoner for produktet;
denne er *hvordan vi bygger og drifter det videre* — agenter som gjør jobber vi
i dag gjør manuelt i en økt, og nye måter å tjene penger på.

Rekkefølgen følger prioriteringen: **1) riktige tall, 2) Ads, 3) automatisk
posting, 4) funksjonalitet.**

---

## Allerede bygget: tallkontroll

`.claude/agents/tallkontroll.md` er malen de andre agentforslagene under
følger: en klar oppgave, egne verktøy, et skript som gjør den maskinelle delen
(`scripts/tallkontroll.py`), og en instruks om å skille bekreftet fra
mistenkt. Den kjører nå automatisk to steder — se «Tallkontroll i
datajobben» og «Ukentlig tallkontroll» i `CLAUDE.md`.

---

## 1. Agent for promo

**Bygget 2026-09-28** — se `.claude/agents/promo.md`. Lager tekst og bilder
som beskrevet under, og valgfritt en kort, stille video
(`promo_felles.lag_kenburns_video()`) når ffmpeg finnes i økten; den mekaniske
delen (hvilke artikler er aldri promotert, dager siden forrige innlegg) ligger
i `promo/finn_kandidater.py`. Video-kodingen er ikke ende-til-ende testet i
utviklingsøkten som bygget den — se advarselen i `CLAUDE.md`.

**Hva den gjør:** Ser gjennom nye artikler, funksjoner og rettinger siden
forrige promo, velger det som gir mest verdi, og lager Facebook/Instagram-bilde
og -tekst etter mønsteret i `promo/promo_felles.py` og
`promo/generate_betalt_post.py`. Legger resultatet i
`promo/publiseringsplan.json` med en `publiser_fra`-dato.

**Hvorfor en agent, ikke bare et skript:** Valget av *hva* som er verdt å
promotere er et redaksjonelt skjønn — samme type vurdering som å velge mellom
en funksjonskunngjøring og et nøytralt tips (se hvordan «Faktisk betalt
utbytte»-posten ble bygget). Et skript kan generere bildet; det kan ikke
avgjøre om et tall i bildet vil gå ut på dato eller om posten utilsiktet
reklamerer for en feil i eget hovedtall.

**Faste vakter agenten må arve:**
- Ingen Arctic-farger (samme grep som i `CLAUDE.md`).
- Ingen tall i bilder som kan drifte — se «Never freeze live numbers into
  stored prose».
- Sjekk at teksten ikke lover noe konkurrenter kan motbevise, og at den ikke
  navngir en aksje der vårt eget hovedtall er kjent for høyt (GOD, KID, BOR,
  REACH, MGN — Sjekk 10 i `valider_data.py`).
- `promo/publiseringsprompt.md` er kontrakten mot posting-AI-en: teksten
  postes ordrett. Agenten må skrive den ferdig, ikke som utkast.

**Effekt:** Fra «vi bør huske å lage promo» til at det skjer av seg selv etter
hver relevant endring — direkte på Pri 3.

---

## 2. Agent for artikler

**Bygget 2026-10-06**, se `.claude/agents/artikkel.md`. Foreslår emne og
disposisjon og venter på godkjenning før den skriver, som beskrevet under.
Både den og promo-agenten følger `SKRIVESTIL.md`, og `scripts/sjekk_sprak.py`
måler det som kan telles (tankestreker og maskinvendinger).

**Hva den gjør:** Skriver nye artikler til `/artikler/` etter malen i
`CLAUDE.md` (1 500–3 000 ord, footer, JSON-LD, innholdsfortegnelse), oppdaterer
`artikler/index.html`, `ARTIKLER`-konstanten i `assets/ui.js` og
`generer_sitemap()` — de tre stedene en ny artikkel må registreres for faktisk
å bli synlig og indeksert.

**Hvorfor en agent:** Artikkelmalen har mange småregler som er lette å glemme
ett av gangen (se «Gjør artikkelen synlig i appen» — feil `sektorer`-verdi
feiler stille). En agent med disse reglene i systemprompten unngår at hver
artikkel blir en ny runde med «hvorfor dukker den ikke opp i appen».

**Temaer med åpenbart hull i dag** (ikke dekket av de 12 artiklene):
tilbakebetaling av innbetalt kapital vs. utbytte (STST/ENH-saken egner seg som
lærestykke), hvordan lese en NewsWeb-melding selv, forskjellen på ex-dato og
utbetalingsdato (kan bygges videre fra `hva-er-ex-dato`).

**Vakt:** Etter «Breaking the template» skal ikke artiklene bli quantity over
quality — én god artikkel i måneden er bedre for AdSense-vurderingen enn fire
tynne. Agenten bør foreslå emne og disposisjon *til godkjenning* før den
skriver 2 000 ord.

**Effekt:** Flere sider med egen, ikke-generert tekst — direkte på Pri 2
(AdSense) og styrker organisk søk.

### 2b. Agent for selskapstekster

**Bygget 2026-10-06**, se `.claude/agents/selskapstekst.md`. Skriver om
teksten under «Om selskapet» på aksjesidene og i appen, høyst ti aksjer per
kjøring, til 180–280 ord i to eller tre avsnitt. Lagrer bare gjennom
`valider_innledning.py --skriv`, som avviser tall som drifter, brudd på
`SKRIVESTIL.md` og fraser som går igjen i mange tekster. Køen
(`--ko`) tar stilbrudd først og de største selskapene først. DNB er skrevet
som prøve; 154 gjenstår.

---

## 3. Exday Premium

Et betalt nivå i appen. Under er hva som naturlig hører hjemme der, gruppert
etter hvor mye det er verdt å bygge.

**Det åpenbare — bygg dette først hvis det blir noe av:**
- **Ingen annonser.** Den enkleste og mest forståelige grunnen til å betale,
  og den eneste som ikke krever ny funksjonalitet.
- **E-post/push ved ex-dato og prisvarsel.** `N1` i `ROADMAP_NYE_IDEER.md`
  (prisvarsel) er allerede planlagt som gratis — vurder om selve *varslingen*
  (ikke terskelen) er premium, eller om det er bedre å holde push gratis og
  heller selge e-post (se under).
- **Flere porteføljer / ubegrenset watchlist.** Appen støtter allerede flere
  porteføljer i `pf_portefoljer` — en gratis grense (f.eks. 1 portefølje, 3
  watchlister) er en naturlig linje å trekke.
- **Skattesammendrag som PDF.** `N6` i `ROADMAP_NYE_IDEER.md` er allerede
  planlagt; en nedlastbar PDF med årsoppsummering er en opplagt betalingsgrunn
  for noen som skal levere skattemelding.

**Krever mer arbeid, men henger sammen med noe som allerede finnes:**
- **Ukentlig/månedlig e-postsammendrag.** Utbyttekalender, nye ex-datoer,
  porteføljeutvikling. Krever en e-posttjeneste (SendGrid/Mailgun/Resend) og
  dermed *litt* server-side kjøring — i dag har siden ingen backend utover
  GitHub Actions, så dette bør bygges som en ny scheduled workflow, ikke som
  en endring av arkitekturen.
- **Sektorrebalansering med skatteoptimalisering.** Verktøyet finnes
  (`assets/portefolje.js`); en versjon som foreslår salg med lavest
  gevinstskatt (høyeste kostpris ut først, innenfor FIFO-reglene) er en
  naturlig premium-utvidelse av noe som allerede er bygget.

**Vurder grundig før dette bygges:**
- **API-tilgang for utviklere (betalt).** Dette reiser nøyaktig det samme
  videredistribusjonsspørsmålet som «Betalt datakilde for kurser og utbytte»
  i `ROADMAP.md` allerede har undersøkt for *innkjøp* av data — bare i motsatt
  retning. Selger vi Yahoo/Euronext-avledede tall videre, må det avklares mot
  begges bruksvilkår før noe kunngjøres, ikke etterpå.
- **Abonnement betyr «næring», ikke «hobby».** Samme argument som i
  «Monetisering — donasjoner»: et betalt abonnement er en klarere indikasjon
  på næringsvirksomhet enn en donasjonsknapp, fordi det er en gjentakende,
  planlagt inntekt — nettopp det Skatteetatens fire kriterier ser etter. Dette
  bør avklares samtidig med, ikke etter, donasjonsspørsmålet.

---

## Flere forslag

### Agent for malgjennomgang (nevnt tidligere, ikke bygget)
En agent som kjører før merge og kontrollerer nytt innhold mot reglene i
«Breaking the template» — er den nye seksjonen betinget (vises den ikke
overalt), inneholder den et tall som kan drifte, bryter den et av
kontradiksjons-mønstrene («uten et eneste kutt» / «lite forutsigbar»). Mindre
prekær enn tallkontroll, fordi jeg allerede gjør mye av dette manuelt ved hver
PR — men verdifull hvis endringstakten øker.

### Innebygd widget for andre nettsteder
Et lite, innbakt HTML-kort («EQNR: 5,8 % · neste ex-dato 13. nov.») andre
sider kan bygge inn med en `<iframe>` eller et lite script-tag, med lenke
tilbake til exday.no. Billig å bygge, gir backlinks (SEO) og er gratis
markedsføring — men bør vente til etter AdSense er avklart, siden det er nok
en ny overflate å holde konsistent med resten av malverket.

### Norsk mobilapp (Capacitor-innpakning)
PWA-en er allerede installerbar, men en «ekte» oppføring i App Store/Google
Play gir synlighet blant folk som ikke tenker på nettlesere som apper. Lav
kodekostnad (samme kodebase, en wrapper), men krever utviklerkontoer
($99/år Apple, engangs $25 Google) og en runde med butikkgodkjenning.

### Ting som bevisst er utelatt
- **Automatisert prissjekk mot konkurrenter** (Nordnet, DNB) — trolig i strid
  med deres bruksvilkår for scraping, og løser ikke noe Pri 1–4 faktisk
  trenger.
- **Utvidelse til svenske/danske aksjer** — ikke en «utvidelse», men et nytt
  produkt. Hele datapipelinen (Euronext-CSV, NewsWeb, DNB Markets-skraping)
  er bygget rundt Oslo Børs spesifikt. Egen beslutning, ikke noe å ta med her.

---

## Anbefalt rekkefølge

1. **Tallkontroll ukentlig** (allerede satt opp) — la den gå noen uker og se
   hva slags feil den fortsetter å finne før noe annet bygges.
2. **Agent for promo** — lav risiko, bygger direkte videre på noe som allerede
   fungerer manuelt.
3. **Agent for artikler** — først etter at AdSense er avklart 6. oktober, slik
   at ny redaksjonell tekst ikke blåser opp malandelen midt i en søknadsrunde.
4. **Exday Premium** — vent til AdSense-inntekten er reell nok til å vise om
   trafikken i det hele tatt bærer et betalt nivå. Se «det er ikke kostnad å
   vente» i AdSense-seksjonen av `CLAUDE.md` — samme logikk gjelder her.
