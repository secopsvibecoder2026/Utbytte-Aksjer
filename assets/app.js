'use strict';

// ── HELPERS ────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;');
}

// ── STATE ──────────────────────────────────────────────────────────────────
let alleAksjer = [];
let osebxHistorikk = {};   // { "2026-03-01": 1423.5, ... } fra aksjer.json
let aksjerSistOppdatert = '';  // sist_oppdatert fra aksjer.json, se slaaSammenKurs()

// (SKJERMINGSRENTE og SKATTESATS er definert i storage.js)
let sortering = (() => {
  try {
    const s = JSON.parse(localStorage.getItem('sortering') || '{}');
    return (s.kol && s.retning) ? s : { kol: 'utbytte_yield', retning: 'desc' };
  } catch { return { kol: 'utbytte_yield', retning: 'desc' }; }
})();
let aktivTab = 'oversikt';
let aktivOversiktSubTab = 'aksjer';
let kompaktModus = false;
let visKunFavoritter = false;
let paginering = (() => {
  const lagret = parseInt(localStorage.getItem('paginering-per-side') || '25', 10);
  const perSide = [25, 50, 75, 100, 0].includes(lagret) ? lagret : 25;
  return { side: 1, perSide };
})();
let aktivListeFilter = ''; // '' = alle, 'pf' = portefølje, 'wl:{id}' = watchliste
let aktivMalFilter = '';    // '' = alle, 'stabil', 'vekst', 'hoy_yield', 'kvartalsvis'
let aktivRisikoFilter = ''; // '' = alle, 'lav', 'moderat', 'hoy'
let alleHendelser = [];     // Akkumulerte rapport-hendelser fra hendelser.json

// ── INIT ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDarkMode();
  initTabs();
  initOversiktSubTabs();
  initVerktoySubTabs();
  initSwipe();
  initTilbakeTopp();
  initFilter();
  oppdaterFavBtn();
  byggListeFilter();
  initViewToggle();
  initModal();
  initPFSubTabs();
  initKalSubTabs();
  initPortefoljeVelger();
  initPortefolje();
  initWatchlister();
  initJSONBackup();
  initKalkulator();
  initVarsler();
  initSammenligning();
  sjekkQRParam();
  visVelkomstModal();
  initProfil();
  sjekkStartsideForslag();
  lastData();

  // Del-portefølje-knapp
  const delBtn = document.getElementById('pf-del-btn');
  if (delBtn) delBtn.addEventListener('click', genererDelLink);

  // Vis delt portefølje hvis ?del= er i URL
  const delParam = new URLSearchParams(location.search).get('del');
  if (delParam) {
    try { visDeltPortefolje(JSON.parse(decodeURIComponent(atob(delParam)))); } catch(e) { /* ugyldig lenke */ }
  }

  // Nordnet CSV-import via innstillinger-siden: hent pending CSV og prosesser etter data lastes
  if (new URLSearchParams(location.search).get('nordnet-import') === '1') {
    const csv = localStorage.getItem('pf_nordnet_pending');
    if (csv) {
      window._pendingNordnetCSV = csv;
      localStorage.removeItem('pf_nordnet_pending');
    }
  }
});

// ── DATA ───────────────────────────────────────────────────────────────────
const CACHE_NØKKEL = 'aksjer_json_cache';

function visFeilBanner(melding) {
  const banner = document.getElementById('data-feil-banner');
  if (!banner) return;
  document.getElementById('data-feil-tekst').textContent = melding;
  banner.classList.remove('hidden');
  banner.classList.add('flex');
}

function skjulFeilBanner() {
  const banner = document.getElementById('data-feil-banner');
  if (!banner) return;
  banner.classList.add('hidden');
  banner.classList.remove('flex');
}

function visCacheBanner(ts) {
  const banner = document.getElementById('data-cache-banner');
  if (!banner) return;
  const datoTekst = ts
    ? 'Viser lagrede data fra ' + new Date(ts).toLocaleDateString('nb-NO', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) + '.'
    : 'Viser lagrede data fra sist vellykkede henting.';
  document.getElementById('data-cache-tekst').textContent = datoTekst;
  banner.classList.remove('hidden');
  banner.classList.add('flex');
  document.getElementById('data-cache-lukk').onclick = () => {
    banner.classList.add('hidden');
    banner.classList.remove('flex');
  };
}

/**
 * Viser hvor gamle dataene er.
 *
 * Dette sto her fra før, men var usynlig i praksis: elementet har `hidden
 * sm:block`, så advarselen «kan være utdatert» viste seg aldri på mobil —
 * der de fleste leser.
 *
 * Det er ikke et teoretisk problem. I august ble ni tickere servert med 16
 * dager gamle tall uten at noe sa fra, og WILS i over tre år. En side som
 * viser en direkteavkastning uten å si når tallet er fra, later som om det
 * er ferskt.
 *
 * Teksten må være kort. Første forsøk skrev «Oppdatert 11. sep., 19:00 ·
 * 2 dager gammel» — på 390 px kuttet `truncate` den til «Oppdatert 1…»,
 * så advarselen forsvant likevel. Er tallene gamle, er *alderen* signalet,
 * ikke klokkeslettet: da vises den i stedet for datoen, ikke i tillegg.
 * Hele tidsstempelet ligger i `title`.
 *
 * «N feilet» sto her til 17.09.2026 og er fjernet. Det var et tall om vår
 * hentejobb, ikke om aksjene leseren ser på: «1 feilet» av 155 sier hverken
 * hvilken aksje det gjelder eller om det er én leseren bryr seg om, og de
 * 154 andre er like ferske som før. `antall_feil` beholdes i `aksjer.json`
 * — det er riktig sted for det, og `sjekk_utdaterte.py` varsler den som
 * faktisk kan gjøre noe. Skal leseren varsles, må varselet stå på *aksjen*
 * som har gamle tall, og da trengs et felt per ticker; aggregatet holder
 * ikke.
 */
function visDataFerskhet(json, naa = Date.now()) {
  const el = document.getElementById('sist-oppdatert');
  if (!el || !json || !json.sist_oppdatert) return;

  const d = new Date(json.sist_oppdatert);
  if (isNaN(d.getTime())) return;

  const kortDato = d.toLocaleDateString('nb-NO', { day: 'numeric', month: 'short' });

  // Alderen telles i børsdager. Med døgn sto «Tall 2 dager gamle» i gult
  // hver mandag morgen, over fredagens sluttkurser, som var de nyeste som
  // fantes. Én børsdag uten ny henting er normalt, siden GitHub ofte starter
  // datajobben timer for sent. To er det ikke, og da skal leseren se det.
  const borsdager = borsdagerMellom(kursdag(json.sist_oppdatert), kursdag(naa));
  const gammel = borsdager >= 2;

  el.textContent = gammel ? 'Tall ' + borsdager + ' børsdager gamle' : 'Oppdatert ' + kortDato;
  el.title = 'Tallene ble hentet ' + d.toLocaleString('nb-NO', {
    day: 'numeric', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }) + '. Kursdata hentes på børsdager.';
  // Gråfargen må *av* når advarselen slås på. text-gray-500 og text-amber-600
  // har samme spesifisitet, så med begge påsatt avgjør rekkefølgen i
  // stilarket — og da sto advarselen grå.
  el.classList.toggle('text-amber-600', gammel);
  el.classList.toggle('dark:text-amber-400', gammel);
  el.classList.toggle('text-gray-500', !gammel);
  el.classList.toggle('dark:text-gray-400', !gammel);
}

function lastInnData(json) {
  alleAksjer     = Array.isArray(json) ? json : (json.aksjer || []);
  window.alleAksjer = alleAksjer;
  osebxHistorikk = json.osebx_historikk || {};
  aksjerSistOppdatert = (json && json.sist_oppdatert) || '';

  visDataFerskhet(json);

  byggSektorFilter();
  byggListeFilter();
  oppdaterSammendrag();
  visOversikt();
  visKalender();
  mergPriser();
  sjekkExDatoerDirekte();

  const urlAksje = new URLSearchParams(location.search).get('aksje');
  if (urlAksje) {
    const treff = alleAksjer.find(a => a.ticker.toUpperCase() === urlAksje.toUpperCase());
    if (treff) visModal(treff);
  }

  if (window._pendingKomparasjon) {
    window._pendingKomparasjon = false;
    oppdaterSammenlignSkuff();
    visKomparasjonsModal();
  }

  // Stille auto-lagring til IndexedDB på hvert sidelast (alle nettlesere inkl. iOS)
  autoLagreIDB();
  // Auto-backup toast (Chrome/Edge: filvalg; Firefox/Safari/iOS: ukentlig nedlastingspåminnelse)
  setTimeout(() => initAutoBackup(), 3000);

  if (window._pendingQRImport) {
    const gyldig = Object.entries(window._pendingQRImport)
      .filter(([t]) => alleAksjer.find(a => a.ticker === t))
      .map(([ticker, antall]) => ({ ticker, antall: Number(antall) }));
    window._pendingQRImport = null;
    if (gyldig.length) {
      document.querySelector('[data-tab="portfolio"]').click();
      visImportPreview(gyldig, []);
    }
  }

  if (window._pendingNordnetCSV) {
    const csv = window._pendingNordnetCSV;
    window._pendingNordnetCSV = null;
    const result = parseNordnetCSV(csv);
    if (result.gyldig.length || (result.dummy && result.dummy.length)) {
      document.querySelector('[data-tab="portfolio"]').click();
      visImportPreview(result.gyldig, result.dummy || [], result.ukjent);
    }
  }
}

// ── KURS: aksjer.json mot priser.json ──────────────────────────────────────
// Begge filene har kurs, og den nyeste skal vinne. mergPriser() lot alltid
// priser.json vinne. Datajobben og prisjobben går hver for seg, og GitHub
// forsinker dem kraftig: 09.10.2026 kom datajobben 13:57 UTC med dagens kurs,
// mens priser.json fortsatt hadde gårsdagens sluttkurs til 15:03. I den timen
// viste appen 08.10-kurser for 135 av 154 aksjer, opptil 5,4 % feil, mens
// aksjesidene viste dagens.

// Datoen et tidspunkt faller på i Oslo. Børsdagen følger Oslo, ikke
// nettleserens tidssone.
function osloDato(tid) {
  const d = new Date(tid);
  if (!tid || isNaN(d)) return '';
  return new Intl.DateTimeFormat('sv-SE', { timeZone: 'Europe/Oslo' }).format(d);
}

function _isoPluss(iso, dager) {
  const d = new Date(iso + 'T12:00:00Z');
  d.setUTCDate(d.getUTCDate() + dager);
  return d.toISOString().slice(0, 10);
}

// Børsdagen en dato hører til: lørdag og søndag er fredagens. Helligdager
// kjenner funksjonen ikke, og der blir svaret bare mer forsiktig (se under).
function borsdag(iso) {
  if (!iso) return '';
  const ukedag = new Date(iso + 'T12:00:00Z').getUTCDay();
  return ukedag === 6 ? _isoPluss(iso, -1) : ukedag === 0 ? _isoPluss(iso, -2) : iso;
}

function forrigeBorsdag(iso) {
  return iso ? borsdag(_isoPluss(borsdag(iso), -1)) : '';
}

// Oslo Børs åpner 09:00. En kurs hentet før det, er forrige børsdags
// sluttkurs, selv om kalenderen har gått videre.
const BORS_APNER_TIME = 9;

function _osloTime(tid) {
  const d = new Date(tid);
  if (!tid || isNaN(d)) return NaN;
  return Number(new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Oslo', hour: '2-digit', hourCycle: 'h23',
  }).format(d));
}

// Børsdagen kursen fra et tidspunkt gjelder. Datajobben skrev aksjer.json
// 01:21 natt til tirsdag 13.10.2026 med mandagens sluttkurs. Som «tirsdag»
// ble den målt mot mandagens sluttkurs i priser.json, og hele appen viste
// 0,00 % til prisjobben kom ti timer senere.
function kursdag(tid) {
  const dato = osloDato(tid);
  if (!dato) return '';
  return borsdag(_osloTime(tid) < BORS_APNER_TIME ? _isoPluss(dato, -1) : dato);
}

// Antall børsdager etter `fra`, til og med `til`. Helligdager telles med.
function borsdagerMellom(fra, til) {
  if (!fra || !til || til <= fra) return 0;
  let n = 0;
  let d = fra;
  for (let i = 0; i < 400 && d < til; i++) {
    d = _isoPluss(d, 1);
    const ukedag = new Date(d + 'T12:00:00Z').getUTCDay();
    if (ukedag !== 0 && ukedag !== 6) n++;
  }
  return n;
}

function _endringMot(pris, forrige) {
  if (!(pris > 0) || !(forrige > 0)) return { endringPct: undefined, endringKrs: undefined };
  return {
    endringPct: Math.round((pris / forrige - 1) * 1000000) / 10000,
    endringKrs: Math.round((pris - forrige) * 100) / 100,
  };
}

/**
 * Kursen og dagens endring for én aksje, fra den nyeste av de to filene.
 *
 * p.dato er børsdagen kursen i priser.json gjelder. aksjer.json har ingen
 * kursdato per aksje, bare tidspunktet datajobben gikk; kursen den hentet
 * gjelder børsdagen det tidspunktet faller på, og før børsåpning den forrige
 * (kursdag()).
 *
 * Endring som ikke er kjent, er undefined, og da viser kortet ingenting.
 * Gårsdagens endring ved siden av dagens kurs ville vært feil på en ny måte.
 */
function slaaSammenKurs(aksjePris, p, priserOppdatert, aksjerOppdatert) {
  const fraPriser = { pris: p.pris, endringPct: p.endring_pct, endringKrs: p.endring_krs };
  const dag = kursdag(aksjerOppdatert);
  // Mangler en av datoene, vet vi ikke hvem som er nyest. Da som før.
  if (!p.dato || !dag || !(aksjePris > 0) || p.dato > dag) return fraPriser;
  if (p.dato === dag) {
    // Samme børsdag: den som ble hentet sist, har kursen. Endringen regnes
    // mot gårsdagens sluttkurs uansett, så den passer til kursen som vises.
    if (Date.parse(priserOppdatert) >= Date.parse(aksjerOppdatert)) return fraPriser;
    return { pris: aksjePris, ..._endringMot(aksjePris, p.forrige_kurs) };
  }
  // priser.json gjelder en tidligere børsdag. Er det dagen før, er kursen der
  // gårsdagens sluttkurs, og endringen kan regnes. Ellers er den ukjent.
  const iGaar = p.dato === forrigeBorsdag(dag) ? p.pris : undefined;
  return { pris: aksjePris, ..._endringMot(aksjePris, iGaar) };
}

async function mergPriser() {
  const data = await hentPriser();
  if (!data || !data.aksjer) return;

  let changed = false;
  alleAksjer.forEach(a => {
    const p = data.aksjer[a.ticker];
    if (!p) return;
    const k = slaaSammenKurs(a.pris, p, data.oppdatert, aksjerSistOppdatert);
    if (k.pris > 0) {
      a.pris = k.pris;
      // Recalkuler yield basert på ny kurs
      if (a.utbytte_per_aksje > 0) {
        a.utbytte_yield = Math.round((a.utbytte_per_aksje / k.pris) * 10000) / 100;
      }
    }
    a.endring_pct = k.endringPct;
    a.endring_krs = k.endringKrs;
    changed = true;
  });

  // Re-render kun om brukeren faktisk ser oversikten
  if (changed && aktivTab === 'oversikt') visOversikt();
}

async function lastData() {
  skjulFeilBanner();
  try {
    const [aksjerResp, hendelserResp] = await Promise.all([
      fetch('/data/aksjer.json'),
      fetch('/data/hendelser.json').catch(() => null),
    ]);
    if (!aksjerResp.ok) throw new Error(`HTTP ${aksjerResp.status}`);
    const json = await aksjerResp.json();

    if (hendelserResp && hendelserResp.ok) {
      try {
        const hData = await hendelserResp.json();
        alleHendelser = hData.hendelser || [];
      } catch { alleHendelser = []; }
    }

    // Lagre i cache for fallback
    try { localStorage.setItem(CACHE_NØKKEL, JSON.stringify(json)); } catch { /* quota */ }

    lastInnData(json);
  } catch (e) {
    console.error('Feil ved lasting av data:', e);

    // Prøv cache
    let cachetJson = null;
    try { cachetJson = JSON.parse(localStorage.getItem(CACHE_NØKKEL) || 'null'); } catch { /* ignore */ }

    if (cachetJson) {
      lastInnData(cachetJson);
      visCacheBanner(cachetJson.sist_oppdatert);
      visFeilBanner('Kunne ikke hente nye data. Viser siste lagrede versjon.');
    } else {
      // Ingen cache — vis tom tilstand og feilmelding
      document.getElementById('tabell-body').innerHTML =
        '<tr><td colspan="9" class="px-4 py-12 text-center text-gray-400 text-sm">Ingen data tilgjengelig</td></tr>';
      document.getElementById('kort-body').innerHTML = '';
      ['stat-antall','stat-hoyest-yield','stat-snitt-yield','stat-neste-ex'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '—';
      });
      visFeilBanner('Ingen lagrede data. Sjekk internettforbindelsen og prøv igjen.');
    }

    const oppdEl = document.getElementById('sist-oppdatert');
    if (oppdEl) oppdEl.textContent = '⚠️ Feil ved lasting';
  }
}

// Retry-knapp
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('data-feil-retry')?.addEventListener('click', lastData);
});

// ── STARTSIDE-FORSLAG ──────────────────────────────────────────────────────
function sjekkStartsideForslag() {
  if (localStorage.getItem('start_side') === 'app') return;
  if (localStorage.getItem('startside_forslag_avvist')) return;
  if (!localStorage.getItem('velkommen_vist')) return; // ikke vis før onboarding er ferdig

  const teller = parseInt(localStorage.getItem('app_besok_teller') || '0', 10) + 1;
  localStorage.setItem('app_besok_teller', String(teller));
  if (teller < 2) return;

  setTimeout(() => {
    const toast = document.createElement('div');
    toast.id = 'startside-forslag-toast';
    toast.style.cssText = 'position:fixed;bottom:5rem;left:50%;transform:translateX(-50%);z-index:9999;background:#1f2937;color:#f3f4f6;border-radius:0.75rem;box-shadow:0 8px 24px rgba(0,0,0,0.4);padding:1rem 1.25rem;max-width:22rem;width:calc(100% - 2rem);display:flex;flex-direction:column;gap:0.75rem;';
    toast.innerHTML = '<div style="font-size:0.875rem;font-weight:600;">Vil du åpne appen direkte?</div>'
      + '<div style="font-size:0.8rem;color:#9ca3af;line-height:1.4;">Hopp over landingssiden og gå rett hit når du besøker exday.no</div>'
      + '<div style="display:flex;gap:0.5rem;">'
      + '<button id="startside-forslag-ja" style="flex:1;background:#16a34a;color:#fff;border:none;border-radius:0.5rem;padding:0.5rem;font-size:0.8rem;font-weight:600;cursor:pointer;">Ja, aktiver</button>'
      + '<button id="startside-forslag-nei" style="flex:1;background:#374151;color:#d1d5db;border:none;border-radius:0.5rem;padding:0.5rem;font-size:0.8rem;cursor:pointer;">Nei takk</button>'
      + '</div>';
    document.body.appendChild(toast);

    document.getElementById('startside-forslag-ja').addEventListener('click', () => {
      localStorage.setItem('start_side', 'app');
      toast.remove();
    });
    document.getElementById('startside-forslag-nei').addEventListener('click', () => {
      localStorage.setItem('startside_forslag_avvist', '1');
      toast.remove();
    });
  }, 3000);
}

// Eksport for testene. Samme mønster som storage.js/ui.js/portefolje.js:
// nettleseren ser ingen `module`, så dette er en no-op der.
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { escHtml, visDataFerskhet, osloDato, borsdag, forrigeBorsdag, kursdag, borsdagerMellom, slaaSammenKurs };
}
