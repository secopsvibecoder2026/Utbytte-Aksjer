'use strict';

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
let kompaktModus = false;
let visKunFavoritter = false;

// ── INIT ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDarkMode();
  initTabs();
  initFilter();
  oppdaterFavBtn();
  initViewToggle();
  initModal();
  initPFSubTabs();
  initPortefoljeVelger();
  initPortefolje();
  initTransaksjoner();
  initWatchlister();
  initJSONBackup();
  initKalkulator();
  initVarsler();
  sjekkQRParam();
  visVelkomstModal();
  initProfil();
  initStreak();
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
async function lastData() {
  try {
    const resp = await fetch('data/aksjer.json');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();

    alleAksjer    = Array.isArray(json) ? json : json.aksjer;
    osebxHistorikk = json.osebx_historikk || {};

    // Sist oppdatert + advarsel hvis data er gammel
    const ts = json.sist_oppdatert;
    if (ts) {
      const d = new Date(ts);
      const timerSiden = (Date.now() - d.getTime()) / 3600000;
      const tidstekst = 'Oppdatert ' + d.toLocaleDateString('nb-NO', { day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' });
      const el = document.getElementById('sist-oppdatert');
      el.textContent = tidstekst;
      if (timerSiden > 24) {
        el.textContent += ' ⚠️ Data kan være utdatert';
        el.classList.add('text-yellow-500');
      }
    }

    byggSektorFilter();
    oppdaterSammendrag();
    visOversikt();
    visKalender();
    sjekkExDatoerDirekte();

    // 20b: ?aksje=EQNR åpner modal direkte
    const urlAksje = new URLSearchParams(location.search).get('aksje');
    if (urlAksje) {
      const treff = alleAksjer.find(a => a.ticker.toUpperCase() === urlAksje.toUpperCase());
      if (treff) visModal(treff);
    }

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
  } catch (e) {
    console.error('Feil ved lasting av data:', e);
    document.getElementById('sist-oppdatert').textContent = '⚠️ Kunne ikke laste data – prøv igjen senere';
    document.getElementById('sist-oppdatert').classList.add('text-red-500');
    // Clear skeleton placeholders so they don't linger on error
    document.getElementById('tabell-body').innerHTML = '';
    document.getElementById('kort-body').innerHTML = '';
    ['stat-antall','stat-hoyest-yield','stat-snitt-yield','stat-neste-ex'].forEach(id => {
      document.getElementById(id).textContent = '—';
    });
  }
}
