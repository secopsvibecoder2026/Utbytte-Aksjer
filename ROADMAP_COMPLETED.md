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
