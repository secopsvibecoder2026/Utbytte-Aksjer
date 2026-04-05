# exday.no — Visuell og UX-gjennomgang

Full gjennomgang av alle sider (april 2026).
Eksisterende veikart: [ROADMAP.md](ROADMAP.md) · Ideer: [ROADMAP_NYE_IDEER.md](ROADMAP_NYE_IDEER.md)

---

## 🔴 Kritisk — Fikses først

### V1. Blå knapp og blå theme-color på utbyttekalender
**Side: `/utbyttekalender/`**

Hele siden bruker grønn som merkefarge, men kalender-siden har feil farge to steder:

- `<meta name="theme-color" content="#2563eb">` → blå. Brukere på Android/Chrome ser blå statuslinje når de åpner kalender-siden. Alle andre sider er grønne (`#15803d` eller `#16a34a`).
- Hoved-CTA-knappen: `bg-blue-600 hover:bg-blue-700` → skal være `bg-brand-600 hover:bg-brand-700` (grønn).

**Fix:**
- [ ] Bytt `theme-color` til `#16a34a`
- [ ] Bytt CTA-klasser fra `bg-blue-600` til `bg-brand-600` (eller `bg-green-600`)

---

### V2. Aksjesider ser ut som en annen nettside
**Sider: `/aksjer/TICKER/`, `/aksjer/hoyest-utbytte/`, `/aksjer/konsistente-utbytteaksjer/`, `/aksjer/sektor/*/`**

Alle genererte aksjesider bruker et annet CSS-system enn resten av appen:
- Ingen Tailwind, kun inline `<style>`-blokker med hardkodede farger (`#16a34a`, `#f9fafb`, `#111827`)
- Ingen dark mode
- Ingen dark-toggle-knapp i header
- Annerledes header-stil og breadcrumb-format
- Ingen PWA theme-color

Resultatet er at brukere som klikker fra aksjemodalen til en aksje-side opplever et visuelt brudd — som å forlate nettsiden.

**Fix:**
- [ ] Oppdater `scripts/fetch_stocks.py` (HTML-template for aksjesider) til å bruke samme header-struktur som `/uke/` og `/bevegelser/`
- [ ] Legg til dark mode (`localStorage.getItem('theme') === 'dark'`) og dark toggle
- [ ] Bytt hardkodede farger med Tailwind-klasser og `.brand-*`
- [ ] Legg til `<meta name="theme-color" content="#16a34a">`

---

### V3. `localStorage`-nøkkel-kaos — dark mode virker ikke på tvers av sider
**Alle sider**

Tre forskjellige nøkkelnavn brukes for dark mode-preferansen, avhengig av hvilken side man er på:

| Side | Nøkkel brukt |
|------|-------------|
| `/uke/`, `/bevegelser/`, `/utbyttekalender/` | `'theme'` |
| `/innstillinger/` | `'darkMode'` |
| `/personvern/`, `/faq/` | `'tema'` |

Konsekvens: Slår man på dark mode fra `/innstillinger/` (skriver `'darkMode'`) og går til `/uke/` (leser `'theme'`), er siden lys igjen.

**Fix:**
- [ ] Standardiser til én nøkkel overalt: `'theme'`
- [ ] Søk og erstatt alle `localStorage.getItem('darkMode')` og `localStorage.getItem('tema')` → `'theme'`
- [ ] Oppdater `innstillinger/index.html` og `personvern/index.html`

---

## 🟠 Høy prioritet

### V4. `theme-color` er inkonsistent på tvers av sider
**Alle sider**

Tre ulike verdier brukes — ingen er enige om "exday-grønn":

| Side | theme-color |
|------|-------------|
| `/uke/`, `/bevegelser/` | `#15803d` (mørk grønn) |
| `/utbyttekalkulator/`, `/innstillinger/` | `#16a34a` (standardgrønn) |
| `/utbyttekalender/` | `#2563eb` (blå — se V1) |
| Aksjesider | (mangler) |

**Fix:**
- [ ] Velg én verdi: `#16a34a` (som matcher `brand-600` i Tailwind)
- [ ] Oppdater alle `<meta name="theme-color">` til `#16a34a`

---

### V5. `personvern`-siden bruker CDN-Tailwind i stedet for lokal
**Side: `/personvern/`**

```html
<script src="https://cdn.tailwindcss.com"></script>  <!-- ← tregere, ekstern avhengighet -->
```

Alle andre sider bruker lokal `/assets/tailwind.css`. CDN-versjonen er langsommere, blokkeres av CSP-er, og kan skille seg visuelt fra den lokalt bygde versjonen.

Samme gjelder `/faq/index.html` som ble skrevet med CDN-Tailwind.

**Fix:**
- [ ] Erstatt CDN-`<script>` med `<link rel="stylesheet" href="/assets/tailwind.css" />` + `<link rel="stylesheet" href="/assets/style.css" />` på `/personvern/` og `/faq/`
- [ ] Behold `tailwind.config`-blokken med `darkMode: 'class'` som inline `<script>`

---

### V6. Knapp- og lenkestil er inkonsistent mellom sider
**Alle sider**

Primærknapper bruker tre forskjellige klassekombinasjoner:

- `/utbyttekalender/`: `bg-blue-600` (feil farge, se V1)
- `/utbyttekalkulator/`: `bg-green-600 hover:bg-green-700`
- `/uke/`, `/bevegelser/`: `.brand-600`, `.brand-700` (egendefinerte klasser)
- Aksjesider: hardkodede `background: #16a34a`

**Fix:**
- [ ] Velg ett mønster — anbefalt: `bg-brand-600 hover:bg-brand-700 text-white`
- [ ] Oppdater `/utbyttekalkulator/` fra `bg-green-*` til `bg-brand-*`

---

### V7. Navigasjonsstruktur er uferdig — siden er vanskelig å utforske
**Hele appen**

Det finnes ingen global navigasjon. Brukere kan gå seg vill:

- Fra `/aksjer/EQNR/` er det ingen lenke til `/utbyttekalender/`, `/utbyttekalkulator/` eller tilbake til aksjelisteoversikten — kun en brødsmule til `/aksjer/`
- `/faq/` og `/personvern/` er kun lenket fra footeren på hovedsiden — ikke fra noen andre sider
- `/uke/` og `/bevegelser/` er kun tilgjengelige via forsidens sticky header — ikke fra aksjesidene

**Fix:**
- [ ] Legg til en konsistent mini-nav på alle aksjesider med lenker til: `/ · /utbyttekalender/ · /utbyttekalkulator/ · /aksjer/`
- [ ] Legg til FAQ-lenke i footeren på `/uke/`, `/utbyttekalender/`, `/utbyttekalkulator/`, `/bevegelser/`
- [ ] Vurder en "hamburger"-meny eller bottom navigation bar for mobil

---

### V8. Rotete footer-seksjon på forsiden
**Side: `/index.html`**

Footeren inneholder kun én linje med lenker (personvern + FAQ), men ingen strukturert sitemap eller navigasjon. Sammenlignet med innholdet på siden er footeren minimal. Brukere som scroller til bunnen for å orientere seg finner lite.

**Fix:**
- [ ] Utvid footer med 2–3 kolonner: «Sider», «Topp-aksjer», «Om exday.no»
- [ ] Eksempel: Kalender · Kalkulator · Ukens oversikt · FAQ · Personvern

---

## 🟡 Medium prioritet

### V9. Inline `<style>`-blokker på alle sider — vedlikehold er kronglete
**Alle sider**

Sidesspesifikk CSS er spredd i individuelle `<style>`-tagger per side, i stedet for felles stilark. Eksempel fra `/uke/index.html`: 45 linjer med egne klasser (`.uke-seksjon`, `.uke-rad`, `.uke-badge`, etc.) som ikke er tilgjengelige på andre sider.

**Problem:** Hvis man vil endre spacing, border-radius eller hover-farge på "rader med aksjer", må det gjøres på 10+ steder.

**Fix:**
- [ ] Flytt gjentakende komponenter (tabellrader, seksjonskort, badges) til `/assets/style.css`
- [ ] La siden-spesifikk CSS beholdes inline, men kun det som faktisk er unikt for den siden

---

### V10. Utbyttekalender — mobilvisning for tabeller
**Side: `/utbyttekalender/`**

Tabellen har en kortvisning på mobil, men månedspillene (januar–desember) vises i én horisontal rekke uten wrapping og kan gå utenfor skjermen på smalere enheter. Ingen `overflow-x: auto` er satt.

**Fix:**
- [ ] Legg til `overflow-x: auto` eller `flex-wrap: wrap` på pill-raden
- [ ] Vurder å kollapse til en `<select>`-dropdown på `< 480px`

---

### V11. Utbyttekalkulator — avansert panel har dårlig åpne/lukke-indikasjon
**Side: `/utbyttekalkulator/`**

Det avanserte innstillingspanelet har en chevron-ikon som indikerer åpen/lukket, men chevronet roterer ikke (ingen CSS transition). Brukere kan overse at det er klikbart.

**Fix:**
- [ ] Legg til `transition: transform 0.2s` på chevronet
- [ ] Roter 180° når panelet er åpent (samme mønster som FAQ-siden nå bruker)

---

### V12. Bevegelser-siden mangler forklaring på hva "stor bevegelse" betyr
**Side: `/bevegelser/`**

Siden viser "store kursendringer i dag", men definerer ikke terskelen (er det >2%? >5%?). En ny bruker forstår ikke hva som kvalifiserer.

**Fix:**
- [ ] Legg til en liten infotekst eller tooltip: «Viser aksjer med kursendring > X% siste børsdag»

---

### V13. Aksjesider — graf og historikk mangler visuell forklaring
**Sider: `/aksjer/TICKER/`**

Utbyttehistorikk-grafen på aksjesidene viser bare søyler uten akse-forklaring på Y-aksen. Nye brukere forstår ikke enhetene (NOK? prosent?).

**Fix:**
- [ ] Legg til Y-akse-label: «NOK per aksje»
- [ ] Legg til tooltip på hover med eksakt verdi og år

---

### V14. Sektor-ikoner mangler på sektorsidene
**Sider: `/aksjer/sektor/*/`**

Sektorsider viser kun sektornavn som tekst — ingen ikon eller fargekoding per sektor. På forsiden er det heller ingen visuell distinksjon mellom sektorer.

**Fix:**
- [ ] Legg til enkle emoji- eller SVG-ikoner per sektor (⚡ Energi, 🏦 Finans, 🚢 Shipping, 🐟 Sjømat, etc.)
- [ ] Konsistente fargebadges per sektor på alle steder de vises

---

### V15. `/kalkulator/` er en usynlig redirect uten stil
**Side: `/kalkulator/`**

Siden er kun en `<meta http-equiv="refresh">` + `window.location.replace()` uten design. Brukere med treg nettverkstilkobling ser en hvit blank side i 0–2 sekunder.

**Fix:**
- [ ] Legg til minimal styling med spinner og «Du videresendes til kalkulatoren…»-tekst
- [ ] Vurder om siden er nødvendig — kan slettes og erstattes med en `_redirects`-fil (Netlify) eller serversideregel

---

## 🟢 Lavere prioritet / Polering

### V16. Breadcrumb-format varierer
**Sider: aksjesider vs. hovednivå-sider**

- Aksjesider: `exday.no › Aksjer › EQNR` (pil-tegn)
- Hovednivå-sider (`/uke/`, etc.): `exday.no / Ukens oversikt` (skråstrek)

**Fix:**
- [ ] Standardiser til `›`-format overalt, eller konsekvent `/`

---

### V17. Dark mode på grafer og charts er ikke testet
**Sider: `/utbyttekalkulator/`, aksjesider**

Grafene rendres med hardkodede lysegrå bakgrunner og mørke labels. I dark mode kan dette gi hvit boks mot mørk side.

**Fix:**
- [ ] Test graf-komponentene i dark mode
- [ ] Legg til `dark:`-varianter for canvas-bakgrunn og grid-linjefarger

---

### V18. Footer-disclaimer er ulik på alle sider
**Alle sider**

- Noen sider: lang juridisk tekst (3 setninger)
- Andre sider: kortversjon («Ikke finansiell rådgivning. Gjør alltid din egen analyse.»)
- Aksjesider: ingen footer i det hele tatt

**Fix:**
- [ ] Standardiser footerteksten til én versjon
- [ ] Legg til minimal footer på aksjesider

---

### V19. Manglende `aria-label` og tilgjengelighet på interaktive elementer
**Alle sider**

Flere ikonknapper (dark toggle, lukk-knapper) mangler tekstlig beskrivelse for skjermlesere.

**Fix:**
- [ ] Sjekk alle `<button>`-elementer uten synlig tekst — legg til `aria-label="..."`
- [ ] Kjør Lighthouse accessibility audit og ta ned score til 0 kritiske feil

---

### V20. Ingen «tilbake til toppen»-knapp på lange sider
**Sider: `/index.html`, `/utbyttekalender/`, `/aksjer/TICKER/`**

Forsiden og kalenderen kan bli svært lange, spesielt med mange aksjer. Ingen rask måte å scrolle tilbake til topp.

**Fix:**
- [ ] Legg til en enkel `↑`-knapp som vises etter 500px scroll, med `window.scrollTo({top:0, behavior:'smooth'})`

---

## Oppsummering — prioritert rekkefølge

| # | Tiltak | Innsats | Effekt |
|---|--------|---------|--------|
| V1 | Blå knapp/theme-color på kalender | Lav | Høy |
| V3 | Standardiser localStorage-nøkkel | Lav | Høy |
| V4 | Standardiser theme-color meta | Lav | Medium |
| V1+V6 | Konsistente knappfarger | Lav | Medium |
| V5 | CDN → lokal Tailwind (personvern, faq) | Lav | Medium |
| V2 | Aksjesider: dark mode + konsistent header | Høy | Høy |
| V7 | Global mininavigsjon på aksjesider | Medium | Høy |
| V8 | Utvidet footer med sidelenker | Lav | Medium |
| V9 | Felles CSS for gjentakende komponenter | Høy | Medium |
| V10 | Kalender mobilpills scrollbar | Lav | Lav |
| V11 | Kalkulator chevron animasjon | Lav | Lav |
| V14 | Sektor-ikoner | Lav | Medium |
| V20 | Tilbake-til-topp-knapp | Lav | Lav |
