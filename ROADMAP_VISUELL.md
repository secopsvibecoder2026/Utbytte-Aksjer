# exday.no — Visuell og UX-gjennomgang

Full gjennomgang av alle sider (april 2026).
Eksisterende veikart: [ROADMAP.md](ROADMAP.md) · Ideer: [ROADMAP_NYE_IDEER.md](ROADMAP_NYE_IDEER.md)

---

## 🔴 Kritisk — Fikses først

### V1. Blå knapp og blå theme-color på utbyttekalender ✅
**Side: `/utbyttekalender/`**

Hele siden bruker grønn som merkefarge, men kalender-siden har feil farge to steder:

- `<meta name="theme-color" content="#2563eb">` → blå. Brukere på Android/Chrome ser blå statuslinje når de åpner kalender-siden. Alle andre sider er grønne (`#15803d` eller `#16a34a`).
- Hoved-CTA-knappen: `bg-blue-600 hover:bg-blue-700` → skal være `bg-brand-600 hover:bg-brand-700` (grønn).

**Fix:**
- [x] Bytt `theme-color` til `#16a34a`
- [x] Bytt CTA-klasser fra `bg-blue-600` til `bg-brand-600` (eller `bg-green-600`)

---

### V2. Aksjesider ser ut som en annen nettside ✅
**Sider: `/aksjer/TICKER/`, `/aksjer/hoyest-utbytte/`, `/aksjer/konsistente-utbytteaksjer/`, `/aksjer/sektor/*/`**

Alle genererte aksjesider bruker et annet CSS-system enn resten av appen:
- Ingen Tailwind, kun inline `<style>`-blokker med hardkodede farger (`#16a34a`, `#f9fafb`, `#111827`)
- Ingen dark mode
- Ingen dark-toggle-knapp i header
- Annerledes header-stil og breadcrumb-format
- Ingen PWA theme-color

Resultatet er at brukere som klikker fra aksjemodalen til en aksje-side opplever et visuelt brudd — som å forlate nettsiden.

**Fix:**
- [x] Oppdater `scripts/fetch_stocks.py` (HTML-template for aksjesider) til å bruke samme header-struktur som `/uke/` og `/bevegelser/`
- [x] Legg til dark mode (`localStorage.getItem('theme') === 'dark'`) og dark toggle
- [x] Bytt hardkodede farger med CSS dark-mode-varianter
- [x] Legg til `<meta name="theme-color" content="#16a34a">`

---

### V3. `localStorage`-nøkkel-kaos — dark mode virker ikke på tvers av sider ✅
**Alle sider**

Tre forskjellige nøkkelnavn brukes for dark mode-preferansen, avhengig av hvilken side man er på:

| Side | Nøkkel brukt |
|------|-------------|
| `/uke/`, `/bevegelser/`, `/utbyttekalender/` | `'theme'` |
| `/innstillinger/` | `'darkMode'` |
| `/personvern/`, `/faq/` | `'tema'` |

Konsekvens: Slår man på dark mode fra `/innstillinger/` (skriver `'darkMode'`) og går til `/uke/` (leser `'theme'`), er siden lys igjen.

**Fix:**
- [x] Standardiser til én nøkkel overalt: `'theme'`
- [x] Erstatt alle `localStorage.getItem('darkMode')` og `localStorage.getItem('tema')` → `'theme'`
- [x] Oppdatert `innstillinger/index.html`, `personvern/index.html` og `faq/index.html`

---

## 🟠 Høy prioritet

### V4. `theme-color` er inkonsistent på tvers av sider ✅
**Alle sider**

Tre ulike verdier brukes — ingen er enige om "exday-grønn":

| Side | theme-color |
|------|-------------|
| `/uke/`, `/bevegelser/` | `#15803d` (mørk grønn) |
| `/utbyttekalkulator/`, `/innstillinger/` | `#16a34a` (standardgrønn) |
| `/utbyttekalender/` | `#2563eb` (blå — se V1) |
| Aksjesider | (mangler) |

**Fix:**
- [x] Valgt én verdi: `#16a34a`
- [x] Oppdatert alle `<meta name="theme-color">` til `#16a34a`

---

### V5. `personvern`-siden bruker CDN-Tailwind i stedet for lokal ✅
**Side: `/personvern/`**

```html
<script src="https://cdn.tailwindcss.com"></script>  <!-- ← tregere, ekstern avhengighet -->
```

Alle andre sider bruker lokal `/assets/tailwind.css`. CDN-versjonen er langsommere, blokkeres av CSP-er, og kan skille seg visuelt fra den lokalt bygde versjonen.

Samme gjelder `/faq/index.html` som ble skrevet med CDN-Tailwind.

**Fix:**
- [x] Erstatt CDN-`<script>` med lokal `tailwind.css` + `style.css` på `/personvern/` og `/faq/`
- [x] Lagt til dark toggle-knapp i headeren på begge sider
- [x] System-preference fallback lagt til i dark mode init

---

### V6. Knapp- og lenkestil er inkonsistent mellom sider ✅
**Alle sider**

Primærknapper bruker tre forskjellige klassekombinasjoner:

- `/utbyttekalender/`: `bg-blue-600` (feil farge, se V1)
- `/utbyttekalkulator/`: `bg-green-600 hover:bg-green-700`
- `/uke/`, `/bevegelser/`: `.brand-600`, `.brand-700` (egendefinerte klasser)
- Aksjesider: hardkodede `background: #16a34a`

**Fix:**
- [x] Standardisert til `bg-brand-600 hover:bg-brand-700` på alle sider
- [x] Oppdatert `/utbyttekalkulator/` og `/utbyttekalender/`

---

### V7. Navigasjonsstruktur er uferdig — siden er vanskelig å utforske ✅
**Hele appen**

Det finnes ingen global navigasjon. Brukere kan gå seg vill:

- Fra `/aksjer/EQNR/` er det ingen lenke til `/utbyttekalender/`, `/utbyttekalkulator/` eller tilbake til aksjelisteoversikten — kun en brødsmule til `/aksjer/`
- `/faq/` og `/personvern/` er kun lenket fra footeren på hovedsiden — ikke fra noen andre sider
- `/uke/` og `/bevegelser/` er kun tilgjengelige via forsidens sticky header — ikke fra aksjesidene

**Fix:**
- [x] Mini-nav på alle genererte aksjesider (kalender, kalkulator, høyest yield, sektor)
- [x] FAQ-lenke i footer på `/uke/`, `/utbyttekalender/`, `/utbyttekalkulator/`, `/bevegelser/`

---

### V8. Rotete footer-seksjon på forsiden ✅
**Side: `/index.html`**

Footeren inneholder kun én linje med lenker (personvern + FAQ), men ingen strukturert sitemap eller navigasjon. Sammenlignet med innholdet på siden er footeren minimal. Brukere som scroller til bunnen for å orientere seg finner lite.

**Fix:**
- [x] Footer på alle undersider: Kalender · Kalkulator · Høyest yield · FAQ · Personvern
- [x] FAQ-lenke lagt til i footer på forsiden

---

## 🟡 Medium prioritet

### V9. Inline `<style>`-blokker på alle sider — vedlikehold er kronglete ✅
**Alle sider**

Sidesspesifikk CSS er spredd i individuelle `<style>`-tagger per side, i stedet for felles stilark. Eksempel fra `/uke/index.html`: 45 linjer med egne klasser (`.uke-seksjon`, `.uke-rad`, `.uke-badge`, etc.) som ikke er tilgjengelige på andre sider.

**Problem:** Hvis man vil endre spacing, border-radius eller hover-farge på "rader med aksjer", må det gjøres på 10+ steder.

**Fix:**
- [x] Flytt gjentakende header-komponenter (`.ak-header`, `.ak-inner`, `.ak-left`, `.ak-back`, `.ak-sep`, `.ak-cur`, `.ak-toggle`) til `/assets/style.css`
- [x] Fjern duplikate `.ak-*`-stiler fra sektor- og toppliste-templates i `fetch_stocks.py`
- [x] La siden-spesifikk CSS beholdes inline, men kun det som faktisk er unikt for den siden

---

### V10. Utbyttekalender — mobilvisning for tabeller ✅
**Side: `/utbyttekalender/`**

Tabellen har en kortvisning på mobil, men månedspillene (januar–desember) vises i én horisontal rekke uten wrapping og kan gå utenfor skjermen på smalere enheter. Ingen `overflow-x: auto` er satt.

**Fix:**
- [x] Lagt til `overflow-x: auto; padding-bottom: 0.25rem` på måneds-nav-raden

---

### V11. Utbyttekalkulator — avansert panel har dårlig åpne/lukke-indikasjon ✅
**Side: `/utbyttekalkulator/`**

Det avanserte innstillingspanelet har en chevron-ikon som indikerer åpen/lukket, men chevronet roterer ikke (ingen CSS transition). Brukere kan overse at det er klikbart.

**Fix:**
- [x] Lagt til `transition: transform 0.2s ease` inline på chevronet (via style-attributt for pålitelig animasjon)
- [x] Roterer 180° når panelet er åpent

---

### V12. Bevegelser-siden mangler forklaring på hva "stor bevegelse" betyr ✅
**Side: `/bevegelser/`**

Siden viser "store kursendringer i dag", men definerer ikke terskelen (er det >2%? >5%?). En ny bruker forstår ikke hva som kvalifiserer.

**Fix:**
- [x] Oppdatert «Om kursbevegelsene»-tekst til å forklare at alle aksjer vises sortert etter prosentendring

---

### V13. Aksjesider — graf og historikk mangler visuell forklaring ✅
**Sider: `/aksjer/TICKER/`**

Utbyttehistorikk-grafen på aksjesidene viser bare søyler uten akse-forklaring på Y-aksen. Nye brukere forstår ikke enhetene (NOK? prosent?).

**Fix:**
- [x] Lagt til Y-akse med ticks og labels (viser NOK-verdier)
- [x] Lagt til hover-tooltip med eksakt verdi og år (ren SVG + inline JS `showTip`/`hideTip`)
- [x] Dark mode CSS for grafen (grønn søyle, mørke akse-linjer)

---

### V14. Sektor-ikoner mangler på sektorsidene ✅
**Sider: `/aksjer/sektor/*/`**

Sektorsider viser kun sektornavn som tekst — ingen ikon eller fargekoding per sektor. På forsiden er det heller ingen visuell distinksjon mellom sektorer.

**Fix:**
- [x] Lagt til `SEKTOR_IKONER`-dict i `fetch_stocks.py` med emoji per sektor (⚡ Energi, 🏦 Finans, 🚢 Shipping, 🐟 Sjømat, etc.)
- [x] Ikon brukes i sektor-h1 og i aksjesiders breadcrumb/undertittel

---

### V15. `/kalkulator/` er en usynlig redirect uten stil ✅
**Side: `/kalkulator/`**

Siden er kun en `<meta http-equiv="refresh">` + `window.location.replace()` uten design. Brukere med treg nettverkstilkobling ser en hvit blank side i 0–2 sekunder.

**Fix:**
- [x] Lagt til spinner-animasjon og «Videresendes til utbyttekalkulator…»-tekst med fallback-lenke

---

## 🟢 Lavere prioritet / Polering

### V16. Breadcrumb-format varierer ✅
**Sider: aksjesider vs. hovednivå-sider**

- Aksjesider: `exday.no › Aksjer › EQNR` (pil-tegn)
- Hovednivå-sider (`/uke/`, etc.): `exday.no / Ukens oversikt` (skråstrek)

**Fix:**
- [x] Standardisert alle `.breadcrumb`-separator fra `›` til `/` i aksje-, sektor- og toppliste-templates i `fetch_stocks.py`

---

### V17. Dark mode på grafer og charts er ikke testet ✅
**Sider: `/utbyttekalkulator/`, aksjesider**

Grafene rendres med hardkodede lysegrå bakgrunner og mørke labels. I dark mode kan dette gi hvit boks mot mørk side.

**Fix:**
- [x] Verifisert: kalkulator-grafen sjekker `isDark` ved rendering og bruker mørke farger (`#60a5fa`, `#6b7280`)
- [x] Aksjesider SVG-grafer: dark mode CSS allerede lagt til (`.dark .hbar { fill: #22c55e; }`, `.dark .ytick { stroke: #1f2937; }`)

---

### V18. Footer-disclaimer er ulik på alle sider ✅
**Alle sider**

- Noen sider: lang juridisk tekst (3 setninger)
- Andre sider: kortversjon («Ikke finansiell rådgivning. Gjør alltid din egen analyse.»)
- Aksjesider: ingen footer i det hele tatt

**Fix:**
- [x] Alle undersider (uke, bevegelser, utbyttekalkulator) har nå samme kortversjon + nav-lenker
- [x] Footer lagt til på `/utbyttekalender/` (manglet helt)
- [x] Forsiden beholder utvidet disclaimer med datakilde-info (passende for landingsside)

---

### V19. Manglende `aria-label` og tilgjengelighet på interaktive elementer ✅
**Alle sider**

Flere ikonknapper (dark toggle, lukk-knapper) mangler tekstlig beskrivelse for skjermlesere.

**Fix:**
- [x] Verifisert alle icon-only `<button>`-elementer på tvers av alle sider — alle har `aria-label`
- [x] Dark-toggle: `aria-label="Bytt fargemodus"` på alle sider
- [x] Modal-lukk-knapper: `aria-label="Lukk"` finnes
- [x] SVG-illustrasjoner: `aria-hidden="true"` på dekorative ikoner

---

### V20. Ingen «tilbake til toppen»-knapp på lange sider ✅
**Sider: `/index.html`, `/utbyttekalender/`, `/aksjer/TICKER/`**

Forsiden og kalenderen kan bli svært lange, spesielt med mange aksjer. Ingen rask måte å scrolle tilbake til topp.

**Fix:**
- [x] Forsiden: knapp allerede i HTML, scroll-handler i `assets/ui.js`
- [x] `/utbyttekalender/`: lagt til tilbake-til-topp-knapp + inline scroll-handler
- [x] `/uke/`: lagt til tilbake-til-topp-knapp + inline scroll-handler
- [x] `/bevegelser/`: lagt til tilbake-til-topp-knapp + inline scroll-handler
- [x] `/utbyttekalkulator/`: lagt til tilbake-til-topp-knapp + inline scroll-handler

---

## Oppsummering — prioritert rekkefølge

| # | Tiltak | Status | Innsats | Effekt |
|---|--------|--------|---------|--------|
| V1 | Blå knapp/theme-color på kalender | ✅ Fikset | Lav | Høy |
| V3 | Standardiser localStorage-nøkkel | ✅ Fikset | Lav | Høy |
| V4 | Standardiser theme-color meta | ✅ Fikset | Lav | Medium |
| V6 | Konsistente knappfarger (bg-brand-*) | ✅ Fikset | Lav | Medium |
| V5 | CDN → lokal Tailwind (personvern, faq) | ✅ Fikset | Lav | Medium |
| V2 | Aksjesider: dark mode + konsistent header | ✅ Fikset | Høy | Høy |
| V7 | Global mininavigsjon på aksjesider | ✅ Fikset | Medium | Høy |
| V8 | Utvidet footer med sidelenker | ✅ Fikset | Lav | Medium |
| V9 | Felles CSS for gjentakende komponenter | ✅ Fikset | Høy | Medium |
| V10 | Kalender mobilpills scrollbar | ✅ Fikset | Lav | Lav |
| V11 | Kalkulator chevron animasjon | ✅ Fikset | Lav | Lav |
| V12 | Bevegelser-terskel forklaring | ✅ Fikset | Lav | Lav |
| V13 | Aksjesider graf Y-akse og tooltip | ✅ Fikset | Medium | Medium |
| V14 | Sektor-ikoner | ✅ Fikset | Lav | Medium |
| V15 | /kalkulator/ redirect styling | ✅ Fikset | Lav | Lav |
| V16 | Breadcrumb-format varierer | ✅ Fikset | Lav | Lav |
| V17 | Dark mode på grafer | ✅ Fikset | Medium | Lav |
| V18 | Footer-disclaimer standardisering | ✅ Fikset | Lav | Lav |
| V19 | aria-label tilgjengelighet | ✅ Fikset | Medium | Medium |
| V20 | Tilbake-til-topp-knapp | ✅ Fikset | Lav | Lav |
