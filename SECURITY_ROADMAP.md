# Security Roadmap — exday.no

> Gjennomgang utført: 2026-04-06  
> Scope: Statisk GitHub Pages PWA med Python-datahenter og CI/CD  
> Filer: `index.html`, `assets/*.js`, `sw.js`, `scripts/fetch_stocks.py`, `.github/workflows/`

---

## Sammendrag

| Alvorlighetsgrad | Antall | Status |
|---|---|---|
| Kritisk | 2 | ✅ Fikset 2026-04-06 |
| Høy | 1 | Åpen |
| Medium | 4 | Åpen |
| Lav | 8 | Åpen |
| Info | 3 | OK |

---

## Fase 1 — Kritisk ✅ Fikset 2026-04-06

### XSS via inline onclick-handlere
**Fil:** `assets/ui.js` (linje 1035, 2814)  
**Status:** ✅ **Fikset** — commit `dab3d38+`

Inline `onclick="...${a.ticker}"` er fjernet. Erstattet med:
- `data-ticker="${escHtml(a.ticker)}"` på knappene
- Delegerte event-lyttere i `kortBody.onclick` og `valgteEl.onclick`
- `escHtml()` helper lagt til i `app.js` (globalt tilgjengelig)

---

### XSS via `innerHTML` med selskapsbeskrivelser
**Fil:** `assets/ui.js` (linje 1766)  
**Status:** ✅ **Fikset** — commit `dab3d38+`

`a.beskrivelse` saniteres nå med `escHtml()` før innsetning i `innerHTML`:
```js
${a.beskrivelse ? `<p ...>${escHtml(a.beskrivelse)}</p>` : ''}
```
`escHtml()` escaperer `&`, `<`, `>`, `"`, `'` til HTML-entiteter.

---

## Fase 2 — Høy (innen 2 uker)

### URL-injeksjon i Python-skript
**Fil:** `scripts/fetch_stocks.py`  
**Problem:** Ticker-strenger brukes direkte i URL-bygging uten encoding:
```python
f"{_NEWSWEB_API}/v1/newsreader/list?issuer={ticker}&limit=500"
```
Spesialtegn i en ticker (`?`, `&`, `#`) kan gi query-parameter-injeksjon.

**Fix:**
```python
from urllib.parse import quote
f"{_NEWSWEB_API}/v1/newsreader/list?issuer={quote(ticker, safe='')}&limit=500"
```

Legg også til format-validering av tickers ved innlesing:
```python
import re
TICKER_RE = re.compile(r'^[A-Z0-9]{1,10}$')
if not TICKER_RE.match(ticker):
    raise ValueError(f"Ugyldig ticker-format: {ticker}")
```

---

### Utdaterte `escape`/`unescape`-funksjoner
**Fil:** `assets/ui.js` (QR-kode-deling)  
**Problem:** `escape()` og `unescape()` er deprecated og ikke del av ES-standarden:
```js
const payload = JSON.parse(decodeURIComponent(escape(atob(raw))));
const encoded = btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
```

**Fix:**
```js
const payload = JSON.parse(decodeURIComponent(atob(raw)));
const encoded = btoa(encodeURIComponent(JSON.stringify(payload)));
```

---

## Fase 3 — Medium (innen 1 måned)

### Manglende Content Security Policy (CSP)
**Fil:** `index.html`  
**Problem:** Ingen CSP betyr at nettleseren tillater inline scripts, externe ressurser uten kontroll, og framing.

**Fix:** Legg til i `<head>`:
```html
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self'
    https://pagead2.googlesyndication.com
    https://www.googletagmanager.com
    https://cdnjs.cloudflare.com;
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: https:;
  connect-src 'self'
    https://newsweb.oslobors.no
    https://live.euronext.com
    https://www.googletagmanager.com;
  frame-ancestors 'none';
  base-uri 'self';
">
```
NB: GitHub Pages støtter ikke HTTP-headere per fil, men CSP via `<meta>` gir god beskyttelse for de fleste angrepsvektorer.

---

### Ingen Subresource Integrity (SRI) på CDN-script
**Fil:** `index.html` (QRCode-bibliotek fra cdnjs)  
**Problem:**
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcode.js/1.0.0/qrcode.min.js"></script>
```
Ingen hash betyr at kompromittert CDN gir full kode-eksekvering.

**Fix:**
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcode.js/1.0.0/qrcode.min.js"
        integrity="sha256-<HASH_HER>"
        crossorigin="anonymous"></script>
```
Alternativ: vendoring — kopier filen inn i `assets/` og server den selv.

---

### Manglende sikkerhetsheadere
GitHub Pages tillater ikke egendefinerte HTTP-headere, men følgende bør dokumenteres og legges til om man bytter til Netlify/Vercel/Cloudflare Pages:

| Header | Anbefalt verdi |
|---|---|
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `geolocation=(), camera=(), microphone=()` |

---

### Analytics-tracking og GDPR
**Fil:** `index.html`  
Google Analytics (G-X6C9PERKMB) og AdSense (ca-pub-3981936786393038) er eksponert i kildekoden.

- **Tracking-ID-er er ikke hemmeligheter** — de er ment å være offentlige
- **Consent Mode v2 er implementert** — analytics er denied som standard, OK
- Sørg for at personvernsiden (`/personvern/`) er oppdatert og reflekterer faktisk databehandling

---

## Fase 4 — Lav / Info

### localStorage-data (portefølje)
Porteføljedata lagres i klartekst i `localStorage`. Dette er bevisst og akseptabelt da:
- Data er brukeregenregistrert (ikke sensitiv finansdata fra backend)
- Ingen autentisering skjer klientside
- XSS er den primære risikoen — reduseres av Fase 1-fikser

### QR-kode-deling uten kryptografisk signering
QR-koder inneholder Base64-kodet JSON med tidsstempel. 5-minutters utløp er OK.  
For høyere sikkerhet: legg til HMAC-SHA256 signering (krever backend-nøkkel).

### Service worker
Caching-strategi er network-first for data og HTML — bra.  
Cache-busting skjer automatisk via SHA i CI/CD — bra.  
Ingen sikkerhetsrisikoer identifisert.

### Python-skript — subprocess og eval
Ingen bruk av `subprocess`, `os.system()`, `eval()` eller `shell=True` funnet.  
`json.dump()` med `_sanitize()` forhindrer `Infinity`/`NaN` i JSON-output — bra.

---

## Det som allerede er bra

- HTTPS enforced av GitHub Pages
- Ingen hardkodede hemmeligheter eller API-nøkler i kodebasen
- Python-skriptene har timeouts og graceful error handling
- CI/CD med minimale permissions (`contents: write`, `pages: write`, `id-token: write`)
- Ingen `eval()`, `Function()` eller tilsvarende i frontend-kode
- `aksjer.json` og `tickers.json` er ikke eksponert for indeksering (`/data/` i robots.txt)
- Consent Mode v2 er korrekt implementert

---

## Neste steg

- [x] Fase 1: Bytt inline onclick → data-attributter i `ui.js`
- [x] Fase 1: Sanitér `beskrivelse`-felt i `innerHTML`
- [ ] Fase 2: Legg til `urllib.parse.quote()` i `fetch_stocks.py`
- [ ] Fase 2: Legg til ticker-format-validering i Python
- [ ] Fase 2: Erstatt `escape`/`unescape` med standard encoding
- [ ] Fase 3: Legg til CSP-header i `index.html`
- [ ] Fase 3: Legg til SRI-hash på QRCode CDN-script (eller vendor det)
- [ ] Fase 3: Dokumenter sikkerhetsheadere til eventuell plattformmigrering
