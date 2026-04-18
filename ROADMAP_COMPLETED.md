# exday.no — Fullførte funksjoner

Alle punkter som er ferdig implementert.

---

- **1. Favoritter** — stjerneikon, filter og prioritert visning
- **2. Porteføljakalkulator** — forventet utbytte/år, vektet yield, tidslinje
- **3. CSV eksport og import** — round-trip med forhåndsvisning; profil-metadata inkludert
- **4. Kalender** — kommende ex-datoer og betalingsdatoer, filtrerbar per måned
- **5. Historiske data og 5-årssnitt** — utbyttegraf per aksje, snitt yield sorterbar kolonne
- **6. Utbyttescore** — automatisk score 0–10 basert på yield, payout, vekst og historikk
- **7. SEO og synlighet** — sitemap, JSON-LD Dataset-schema, semantisk markup
- **8. PWA + push-varsler** — installerbar app, Service Worker, push-varsler for ex-datoer
- **9. Branding** — logo lys/mørk, favicon, PWA-ikon
- **10. GDPR / personvernside** — dokumentasjon av lokal datalagring
- **11. Utbyttekalkulator over tid** — DRIP-reinvestering, år-for-år-tabell
- **12. Fargedesign** — dempede farger, nøytral tabellhover
- **13. Daglig engasjement** — besøksstreak, milepæl-toasts, "Hva skjer i dag?"
- **14. Porteføljesynkronisering** — QR-kode for overføring mellom enheter
- **15. Velkomstmelding** — onboarding-modal for nye brukere med profil-oppsett
- **16. Personlig profil og mål** — navn, månedlig utbyttemål, hilsen på dashboard
- **17. "Hva skjer i dag?"** — ex-dato i dag/morgen, utbetaling denne uken, siste sjanse
- **18. Notat og prisvarsler** — notatfelt og målpris per aksje i modal
- **19. Streaks og milepæler** — 🔥-streak i header, toast ved porteføljemilepæler
- **20. Lavthengende forbedringer** — sortering huskes, `?aksje=`-param, score-forklaring, søk huskes
- **21. Innstillinger-panel og onboarding** — tannhjul-meny med Profil + Varsler; utvidet profil med sparemål
- **22. Portefølje sub-tabs** — Beholdning og Statistikk som egne faner; ekstra nøkkeltall (P/E, utbetalinger/år, sparemål-fremgang, porteføljeprofil)
- **23. Sparemål-progresjon på dashbordet** — fremgangsbar under stat-kortene; vises kun når sparemål er satt
- **24. Del-link for enkeltaksjer** — del-ikon i modal-header kopierer `?aksje=`-URL til clipboard med "Kopiert!"-bekreftelse
- **26. Historisk porteføljeutvikling** — daglig snapshot i localStorage, SVG-kurve på Statistikk-fanen (siste 30 dager)
- **27. Full backup — JSON-eksport og -import** — eksporterer portefølje, favoritter, notater, profil og streak til JSON; import med forhåndsvisning og bekreftelse
- **28. Utbyttekalender med ICS-eksport** — "Last ned kalender (.ics)"-knapp i Kalender-fanen; ex-datoer og betalingsdatoer for alle aksjer, portefølje- og favoritthendelser markert med ⭐
- **25. Individuelle SEO-sider per aksje** — `/aksjer/TICKER/index.html` genereres automatisk av fetch_stocks.py; JSON-LD BreadcrumbList + FinancialProduct schema; sitemap.xml med 69 URL-er
- **CMP. Google Consent Management Platform** — erstattet egendefinert samtykkebanner med Googles Privacy & Messaging CMP (IAB TCF v2.3); Consent Mode v2 med standard avviste signaler
- **LocalStorage v3-migrering** — versjonssystem med migreringskjede (v0→v1→v2→v3); automatisk migrering fra gamle nøkler til ny multi-portefølje-struktur
- **35. Transaksjonslogg og kostbasis (VWAP)** — registrer kjøp/salg med dato, antall og kurs; beregner vektet snittpris (VWAP), urealisert gevinst/tap og faktisk beholdning; lagres som `pf_portefoljer`
- **36. Flere porteføljer og watchlister** — støtte for flere navngitte porteføljer med bytte i Portefølje-fanen; watchliste-funksjon separat fra portefølje og favoritter
- **37. OSEBX-sammenligning** — henter ^OSEAX 30-dagers historikk via yfinance; normalisert OSEBX-linje (stiplet grå) overlay i historikk-kurven; «Slår du indeksen?»-indikator i Statistikk-fanen
- **38. Skatteberegning — skjermingsfradrag** — beregner skjermingsfradrag basert på VWAP-kostpris × 3,1% per posisjon; netto utbytte etter skatt (37,84% aksjonærmodellen) i Statistikk-fanen
- **35b. Faktisk avkastning** — ny transaksjonstype «Utbytte mottatt»; stat-kort viser (markedsverdi + mottatt utbytte − kostpris) / kostpris; gul badge i logg; footer summerer total avkastning inkl. utbytte
- **39. Del portefølje** — «Del portefølje»-knapp genererer `?del=`-URL med base64-kodet sammendrag (verdi, yield, topp 5 posisjoner); kopier til clipboard; mottaker får read-only modal automatisk ved sidelasting
- **T1. Del opp app.js** — splittet 3 500-linjersfilen i `storage.js` (23 localStorage-funksjoner), `ui.js` (2 095 linjer, all UI-logikk), `portefolje.js` (1 136 linjer, porteføljelogikk), `app.js` (109 linjer, bootstrap); index.html laster dem i avhengighetsrekkefølge
- **T4. Enhetstester for kritisk logikk** — 37 tester (Node.js `node:test`): `beregnKostbasis` med injisert txMap, `beregnScore`, `fmt`, `formaterDato`, `yieldKlasse`, `payoutKlasse`, `vekstKlasse`, `beregnYtdInntekt`, `hentFav`/`toggleFav`; kjøres med `npm test`
- **T2. Feilhåndtering overfor brukeren** — rød feilbanner med «Prøv igjen»-knapp ved lastfeil; cacher JSON til localStorage ved suksess; ved feil lastes cache med gul advarsel og dato; tom tilstand med forklarende tekst når ingen cache finnes
- **35c. TWR/IRR — tidskorrigert avkastning** — `beregnIRR()` via Newton-Raphson fra full transaksjonshistorikk + nåværende verdi; annualisert IRR-kort i Statistikk-fanen; `beregnTWRSerie()` eliminerer innskuddseffekt fra historikk-kurven; blå TWR-linje i grafen vises når den avviker fra råverdi
- **T3. Tilgjengelighet (accessibility)** — `aria-label` på alle ikonknapper (tannhjul, sol/måne, stjerne); `role="dialog"` + `aria-modal="true"` + `aria-labelledby` på alle modaler; Escape-tast lukker alle modaler; `aria-sort` på sorterbare kolonner; `aria-hidden="true"` på dekorative SVG-er

---

## Visuell og UX-gjennomgang (april 2026)

- **V1. Blå theme-color og CTA på utbyttekalender** — `theme-color` endret fra `#2563eb` til `#16a34a`; CTA-knapp fra `bg-blue-600` til `bg-brand-600`
- **V2. Aksjesider visuelt brudd** — alle genererte aksjesider (`/aksjer/TICKER/`, sektor, toppliste) fikk dark mode, sticky header med dark-toggle, `theme-color` og konsistent header-struktur via `fetch_stocks.py`-templates
- **V3. localStorage-nøkkel-kaos** — standardisert dark mode-nøkkel til `'theme'` på tvers av alle sider; `innstillinger`, `personvern` og `faq` brukte tidligere `'darkMode'` og `'tema'`
- **V4. Inkonsistent theme-color** — alle `<meta name="theme-color">` standardisert til `#16a34a`
- **V5. CDN-Tailwind på personvern og faq** — erstattet `cdn.tailwindcss.com` med lokal `tailwind.css` + `style.css`; dark-toggle og system-preference fallback lagt til
- **V6. Inkonsistente knappfarger** — standardisert alle primærknapper til `bg-brand-600 hover:bg-brand-700`
- **V7. Manglende navigasjon** — mini-nav lagt til på alle genererte aksjesider; FAQ-lenke i footer på alle undersider
- **V8. Rotete footer** — footer med nav-lenker (Kalender · Kalkulator · Høyest yield · FAQ · Personvern) lagt til på alle undersider
- **V9. Duplisert inline CSS** — felles `.ak-header`, `.ak-inner`, `.ak-back`, `.ak-toggle` m.fl. flyttet til `/assets/style.css`; duplikater fjernet fra sektor- og toppliste-templates
- **V10. Kalender mobilscroll** — `overflow-x: auto` lagt til på måneds-nav-raden
- **V11. Kalkulator chevron-animasjon** — `transition: transform 0.2s ease` lagt til inline; roterer 180° ved åpning
- **V12. Bevegelser-forklaring** — «Om kursbevegelsene»-tekst oppdatert til å forklare at alle aksjer vises sortert etter prosentendring
- **V13. Aksjesider graf Y-akse og tooltip** — inline SVG-bar-chart fikk Y-akse med ticks og labels (NOK-verdier) og hover-tooltip via `showTip`/`hideTip`; dark mode CSS
- **V14. Sektor-ikoner** — `SEKTOR_IKONER`-dict med emoji per sektor (⚡🏦🚢🐟💻🏗️🏢 m.fl.) lagt til i `fetch_stocks.py`; brukes i h1 og breadcrumb
- **V15. /kalkulator/ redirect** — lagt til CSS-spinner og «Videresendes til utbyttekalkulator…»-tekst med fallback-lenke
- **V16. Breadcrumb-separatorer** — alle `.breadcrumb`-separatorer standardisert fra `›` til `/` i alle genererte sider
- **V17. Dark mode på grafer** — verifisert: kalkulator-grafen sjekker `isDark` ved rendering; SVG-grafer har `.dark .hbar` og `.dark .ytick` CSS
- **V18. Footer-disclaimer** — footer lagt til på `/utbyttekalender/` (manglet helt); alle undersider har nå identisk kortversjon
- **V19. aria-label tilgjengelighet** — verifisert at alle icon-only knapper har `aria-label` på tvers av alle sider
- **V20. Tilbake-til-topp** — knapp + scroll-handler lagt til på `/uke/`, `/bevegelser/`, `/utbyttekalender/`, `/utbyttekalkulator/`
- **Transaksjoner slått sammen med Beholdning** — egne kjøpsdato/kjøpskurs-felt direkte i «Legg til aksje»-skjemaet; transaksjonslogg og kostbasis-tabell i kollapserbar seksjon under beholdningslisten; Transaksjoner-fanen fjernet
- **Innstillinger som egen URL (/innstillinger/)** — innstillinger-modal fjernet; tannhjul-knapp er nå en `<a href="/innstillinger/">`; standalone side med profil, porteføljeadministrasjon (opprett/gi nytt navn/slett), varsler, guide og data-seksjon; ingen full-sideominnlasting ved navigasjon
- **Forenklet onboarding** — ett-stegs modal med bare brukernavn + «Gjenopprett backup»-knapp; tom portefølje viser inline 3-stegs guide som forsvinner automatisk når første aksje legges til
- **T5. Tailwind CDN erstattet med statisk CSS** — fjernet `cdn.tailwindcss.com` (~350 KB runtime JS) fra alle sider; bygger `assets/tailwind.css` (~44 KB, minifisert) med `@tailwindcss/cli`; eliminerer tregheten ved navigasjon til /innstillinger/; `npm run build:css` og `npm run watch:css` lagt til
- **Kostbasis/transaksjoner flyttet til beholdningen** — seksjonen lå tidligere isolert nederst; vises nå direkte under beholdningstabellen og skjules/vises i takt med resten av beholdningsinnholdet
- **SW cache-strategi og auto-bump** — Service Worker brukte cache-first for alt, brukere så aldri nye versjoner uten å slette cookies; HTML (navigate) er nå nettverks-first, JS/CSS er stale-while-revalidate; PRECACHE utvidet med storage.js, ui.js, portefolje.js, tailwind.css; GitHub Actions bumper cache-navn til `exday-v{git-sha}` på hvert deploy slik at gamle cacher ryddes automatisk
- **SW robust install (Promise.allSettled)** — `cache.addAll()` er atomisk og aborterte hele SW-installasjonen om én URL feilet (f.eks. /innstillinger/ ikke propagert enda); erstattet med `Promise.allSettled` + individuelle fetch/put med `.catch(()=>{})` så partielt cache ikke hindrer install; `cache:'reload'` på install-fetcher og `cache:'no-cache'` på navigate-fetcher eliminerer GitHub Pages `max-age=600`-laget
- **JSON backup v4 — fullstendig og reparert** — `parseJSONBackup` avviste alle backups nyere enn v1 pga. `b.versjon !== 1`-sjekk (kritisk bug); rettet til `typeof b.versjon !== 'number'`; eksport bumpa til v4 og inkluderer nå alle brukernøkler: `pf_portefoljer`, `pf_aktiv`, `fav_aksjer`, `aksje_data`, `notif_aksjer`, `pf_historikk`, `tema`, `sortering`, `streak_teller`, `streak_sist_besok`, `milepeler_oppnaad`, `profil_navn`, `profil_mal_mnd`, `profil_sparemaal`, `pf_watchlister`; import restaurerer samtlige felt og gir forhåndsvisning med posisjon- og transaksjonstelling
- **Backup-knapper og søk — opprydding** — 5 backup/CSV-knapper fjernet fra beholdnings-headeren (Importer CSV, Last ned CSV, Importer backup, Last ned backup, Send til mobil); samlet i Innstillinger → Data med full import-flyt (forhåndsvisning + bekreftelse → redirect til /); søkefeltets placeholder overlappet forstørrelsesglasset på mobil — rettet med `pl-10` i stedet for `pl-9`
- **Kostbasis og transaksjoner — full inline-integrasjon per rad** — kostbasis/transaksjonsloggen lå i en separat kollapserbar seksjon under hele beholdningstabellen; refaktorert til å ligge direkte i hver beholdningsrad: chevron-knapp i raden utvider en sub-rad (`<tr class="pf-detail-rad">`) med kostbasis-sammendrag, transaksjonsskjema og transaksjonslogg med sletteknapper; expand/collapse-tilstand lagres i modul-nivå `Set` og overlever re-renders; IRR, TWR og kostbasis-stats beregnes fra samme transaksjonsdata som før
- **SEO — OG/Twitter meta-tagger på alle genererte sider** — `og:image` (1200×630), `og:image:width/height`, `og:locale` (nb_NO), `og:site_name` (exday.no) og Twitter Card (`summary_large_image` med title, description og image) lagt til i alle fire templates i `fetch_stocks.py`: aksjesider, sektorsider, oversiktsside og topplistesider; alle 184 aksjesider, 16 sektorsider og topplister regenerert
- **N8. Månedlig utbytteplanlegger** — månedlig utbyttemål (`profil_mal_mnd`) lagres i profil; fremgangsbar under stat-kortene viser «Du er X % av veien til målet ditt»; skjules automatisk når mål ikke er satt
- **Betalingskalender — «Mine utbetalinger»** — ny sub-fane i Kalender-fanen; filtrerer på aksjer i portefølje; viser betaling_dato (eller ex_dato som fallback) per aksje med antall × kroner per aksje = forventet utbetaling; gruppert per måned med totalssum i måneds-header; klikk åpner aksjemodal; tom-tilstand med hjelpetekst
- **T9. E2E-tester med Playwright** — `tests/app.e2e.js` med 8 tester (Chromium, headless): søkfiltrering, nullstill søk, åpne modal, lukke med Escape, lukke med knapp, legg til aksje i portefølje, feilmelding ved manglende antall, fullstendig flyt søk→modal→portefølje; `npm run test:e2e` kjører alle via `playwright.config.js` med innebygd Python HTTP-server
- **N14. Internlenking mellom aksjesider** — «Andre {sektor}-aksjer med utbytte»-seksjon på bunnen av hver aksje-side; genereres automatisk i `_aksje_side_html()` med yield-info og lenke til sektorsiden
