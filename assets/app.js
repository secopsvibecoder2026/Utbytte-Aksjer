'use strict';

// ── HELPERS ────────────────────────────────────────────────────────────────
function escHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#x27;');
}

// ── STATE ──────────────────────────────────────────────────────────────────
let alleAksjer = [];
let osebxHistorikk = {};   // { "2026-03-01": 1423.5, ... } fra aksjer.json

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

function lastInnData(json) {
  alleAksjer     = Array.isArray(json) ? json : (json.aksjer || []);
  window.alleAksjer = alleAksjer;
  osebxHistorikk = json.osebx_historikk || {};

  const ts = json.sist_oppdatert;
  if (ts) {
    const d = new Date(ts);
    const timerSiden = (Date.now() - d.getTime()) / 3600000;
    const tidstekst = 'Oppdatert ' + d.toLocaleDateString('nb-NO', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    const el = document.getElementById('sist-oppdatert');
    if (el) {
      el.textContent = tidstekst;
      if (timerSiden > 24) {
        el.textContent += ' – kan være utdatert';
        el.classList.add('text-yellow-500');
      }
    }
  }

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
}

async function mergPriser() {
  const data = await hentPriser();
  if (!data || !data.aksjer) return;

  let changed = false;
  alleAksjer.forEach(a => {
    const p = data.aksjer[a.ticker];
    if (!p) return;
    if (p.pris > 0) {
      a.pris = p.pris;
      // Recalkuler yield basert på ny kurs
      if (a.utbytte_per_aksje > 0) {
        a.utbytte_yield = Math.round((a.utbytte_per_aksje / p.pris) * 10000) / 100;
      }
      changed = true;
    }
    a.endring_pct = p.endring_pct ?? 0;
    a.endring_krs = p.endring_krs ?? 0;
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
