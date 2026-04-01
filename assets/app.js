'use strict';

// ── STATE ──────────────────────────────────────────────────────────────────
let alleAksjer = [];
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
  initPortefolje();
  initKalkulator();
  initVarsler();
  sjekkQRParam();
  visVelkomstModal();
  initProfil();
  initStreak();
  lastData();
});

function visVelkomstModal() {
  if (localStorage.getItem('velkommen_vist')) return;
  const modal  = document.getElementById('velkommen-modal');
  const steg1  = document.getElementById('velk-steg1');
  const steg2  = document.getElementById('velk-steg2');
  modal.classList.remove('hidden');
  modal.classList.add('flex');

  function lukkOgMerk() {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    localStorage.setItem('velkommen_vist', '1');
  }

  // Steg 1 → Steg 2
  document.getElementById('velk-neste').addEventListener('click', () => {
    steg1.classList.add('hidden');
    steg2.classList.remove('hidden');
    document.getElementById('velk-navn-input').focus();
  });

  // Lagre profil og start
  document.getElementById('velk-lagre').addEventListener('click', () => {
    const navn      = (document.getElementById('velk-navn-input').value || '').trim();
    const spareMaal = parseFloat(document.getElementById('velk-sparemaal-input').value) || 0;
    const malMnd    = parseFloat(document.getElementById('velk-mal-input').value) || 0;
    lagreProfil(navn, malMnd, spareMaal);
    visGreeting();
    lukkOgMerk();
  });

  // Importer CSV
  document.getElementById('velk-importer').addEventListener('click', () => {
    lukkOgMerk();
    // Switch to portfolio tab and trigger file import
    const pfTab = document.querySelector('[data-tab="portfolio"]');
    if (pfTab) pfTab.click();
    setTimeout(() => {
      const fil = document.getElementById('pf-importer-fil');
      if (fil) fil.click();
    }, 150);
  });

  // Gjest — hopp over
  document.getElementById('velk-gjest').addEventListener('click', lukkOgMerk);
}

// ── DATA ───────────────────────────────────────────────────────────────────
async function lastData() {
  try {
    const resp = await fetch('data/aksjer.json');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const json = await resp.json();

    alleAksjer = Array.isArray(json) ? json : json.aksjer;

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

// ── VIEW TOGGLE ────────────────────────────────────────────────────────────
function initViewToggle() {
  ['view-toggle-desktop', 'view-toggle-mobil'].forEach(id => {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', () => {
      kompaktModus = !kompaktModus;
      oppdaterViewToggle();
      visOversikt();
    });
  });
}

function oppdaterViewToggle() {
  const oversikt = document.getElementById('tab-oversikt');
  oversikt.classList.toggle('vis-kompakt', kompaktModus);

  const label = kompaktModus ? 'Normal' : 'Kompakt';
  ['view-label-desktop', 'view-label-mobil'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = label;
  });
}

// ── DARK MODE ──────────────────────────────────────────────────────────────
function initDarkMode() {
  const root = document.documentElement;
  const btn = document.getElementById('dark-toggle');
  const moon = document.getElementById('icon-moon');
  const sun = document.getElementById('icon-sun');

  const pref = localStorage.getItem('tema') ||
    (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  settTema(pref);

  btn.addEventListener('click', () => {
    settTema(root.classList.contains('dark') ? 'light' : 'dark');
  });

  function settTema(t) {
    root.classList.toggle('dark', t === 'dark');
    moon.classList.toggle('hidden', t === 'dark');
    sun.classList.toggle('hidden', t !== 'dark');
    localStorage.setItem('tema', t);
  }
}

// ── TABS ───────────────────────────────────────────────────────────────────
function initTabs() {
  document.getElementById('tab-nav').addEventListener('click', e => {
    const btn = e.target.closest('.tab-btn');
    if (!btn) return;
    aktivTab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
    document.getElementById('tab-oversikt').classList.toggle('hidden', aktivTab !== 'oversikt');
    document.getElementById('tab-kalender').classList.toggle('hidden', aktivTab !== 'kalender');
    document.getElementById('tab-portfolio').classList.toggle('hidden', aktivTab !== 'portfolio');
    document.getElementById('tab-kalkulator').classList.toggle('hidden', aktivTab !== 'kalkulator');
    const skjulFilter = aktivTab === 'kalkulator';
    document.getElementById('filter-bar').classList.toggle('hidden', skjulFilter);
    document.getElementById('filter-ekstra').classList.toggle('hidden', aktivTab !== 'oversikt');
    if (aktivTab === 'portfolio') visPortefolje();
    if (aktivTab === 'kalender') visKalender();
    if (aktivTab === 'oversikt') visOversikt();
  });
}

// ── FILTER ─────────────────────────────────────────────────────────────────
function initFilter() {
  document.getElementById('sok').addEventListener('input', () => {
    if (aktivTab === 'kalender') visKalender();
    else if (aktivTab === 'portfolio') visPortefolje();
    else visOversikt();
  });
  ['filter-sektor', 'filter-frekvens', 'filter-yield'].forEach(id => {
    document.getElementById(id).addEventListener('input', visOversikt);
  });
  document.getElementById('reset-filter').addEventListener('click', () => {
    document.getElementById('sok').value = '';
    document.getElementById('filter-sektor').value = '';
    document.getElementById('filter-frekvens').value = '';
    document.getElementById('filter-yield').value = '';
    visKunFavoritter = false;
    oppdaterFavBtn();
    visOversikt();
  });

  document.getElementById('filter-fav').addEventListener('click', () => {
    visKunFavoritter = !visKunFavoritter;
    oppdaterFavBtn();
    visOversikt();
  });

  // Kolonnesortering (desktop)
  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const kol = th.dataset.col;
      sortering.retning = sortering.kol === kol && sortering.retning === 'desc' ? 'asc' : 'desc';
      sortering.kol = kol;
      localStorage.setItem('sortering', JSON.stringify(sortering));
      visOversikt();
    });
  });

  // Mobilsortering
  document.getElementById('mobil-sort').addEventListener('change', e => {
    const val = e.target.value;
    const lastUs = val.lastIndexOf('_');
    sortering.kol = val.slice(0, lastUs);
    sortering.retning = val.slice(lastUs + 1);
    localStorage.setItem('sortering', JSON.stringify(sortering));
    visOversikt();
  });
}

function oppdaterFavBtn() {
  const btn = document.getElementById('filter-fav');
  if (!btn) return;
  const antall = hentFav().size;
  if (visKunFavoritter) {
    btn.className = 'filter-input text-sm font-medium bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300 border-yellow-300 dark:border-yellow-700';
    btn.textContent = `★ Favoritter (${antall})`;
  } else {
    btn.className = 'filter-input text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors';
    btn.textContent = antall > 0 ? `☆ Favoritter (${antall})` : '☆ Favoritter';
  }
}

function byggSektorFilter() {
  const sektorer = [...new Set(alleAksjer.map(a => a.sektor))].sort();
  const sel = document.getElementById('filter-sektor');
  sektorer.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s; opt.textContent = s;
    sel.appendChild(opt);
  });
}

function filtrerteAksjer() {
  const sok = document.getElementById('sok').value.toLowerCase().trim();
  const sektor = document.getElementById('filter-sektor').value;
  const frekvens = document.getElementById('filter-frekvens').value;
  const minYield = parseFloat(document.getElementById('filter-yield').value) || 0;
  const fav = hentFav();

  return alleAksjer.filter(a => {
    if (visKunFavoritter && !fav.has(a.ticker)) return false;
    if (sok && !a.ticker.toLowerCase().includes(sok) && !a.navn.toLowerCase().includes(sok)) return false;
    if (sektor && a.sektor !== sektor) return false;
    if (frekvens && a.frekvens !== frekvens) return false;
    if (a.utbytte_yield < minYield) return false;
    return true;
  });
}

// ── STREAK + MILEPÆLER ─────────────────────────────────────────────────────
function initStreak() {
  const idag      = new Date().toISOString().slice(0, 10);
  const sistBesok = localStorage.getItem('streak_sist_besok') || '';
  let streak      = parseInt(localStorage.getItem('streak_teller') || '1', 10);

  if (sistBesok !== idag) {
    const igaar = new Date();
    igaar.setDate(igaar.getDate() - 1);
    streak = sistBesok === igaar.toISOString().slice(0, 10) ? streak + 1 : 1;
    localStorage.setItem('streak_sist_besok', idag);
    localStorage.setItem('streak_teller', streak);
  }

  if (streak >= 2) {
    const el = document.getElementById('streak-badge');
    if (el) {
      el.textContent = `🔥 ${streak}`;
      el.title = `${streak} dager på rad!`;
      el.classList.remove('hidden');
    }
  }
}

function sjekkMilepeler(totalAr) {
  const GRENSER = [1000, 5000, 10000, 25000, 50000, 100000, 250000, 500000, 1000000];
  let oppnaadde;
  try { oppnaadde = JSON.parse(localStorage.getItem('milepeler_oppnaad') || '[]'); } catch { oppnaadde = []; }

  for (const g of GRENSER) {
    if (totalAr >= g && !oppnaadde.includes(g)) {
      oppnaadde.push(g);
      localStorage.setItem('milepeler_oppnaad', JSON.stringify(oppnaadde));
      visMilepelToast(g);
      break; // én melding om gangen
    }
  }
}

function visMilepelToast(belop) {
  const toast = document.getElementById('milestone-toast');
  const text  = document.getElementById('milestone-toast-text');
  if (!toast || !text) return;
  const fmt = v => v.toLocaleString('nb-NO') + ' kr';
  text.textContent = `🏆 Ny milepæl: ${fmt(belop)} i estimert årlig utbytte!`;
  toast.classList.remove('hidden');
  setTimeout(() => toast.classList.add('hidden'), 6000);
}

// ── PROFIL ─────────────────────────────────────────────────────────────────
function hentProfil() {
  return {
    navn:      localStorage.getItem('profil_navn') || '',
    malMnd:    parseFloat(localStorage.getItem('profil_mal_mnd') || '0'),
    spareMaal: parseFloat(localStorage.getItem('profil_sparemaal') || '0')
  };
}

function lagreProfil(navn, malMnd, spareMaal) {
  localStorage.setItem('profil_navn', navn);
  localStorage.setItem('profil_mal_mnd', malMnd);
  localStorage.setItem('profil_sparemaal', spareMaal);
}

function visGreeting() {
  const { navn } = hentProfil();
  const el = document.getElementById('profil-hilsen');
  if (!el) return;
  if (!navn) { el.classList.add('hidden'); return; }
  const t = new Date().getHours();
  const hilsen = t < 10 ? 'God morgen' : t < 17 ? 'God dag' : 'God kveld';
  el.textContent = `${hilsen}, ${navn}`;
  el.classList.remove('hidden');
}

function initInnstillinger() {
  const btn   = document.getElementById('profil-btn');
  const modal = document.getElementById('innstillinger-modal');
  const lukkBtn  = document.getElementById('innstillinger-lukk');
  const avbrytBtn = document.getElementById('innstillinger-avbryt');
  const lagreBtn = document.getElementById('profil-lagre');
  const navnIn   = document.getElementById('profil-navn-input');
  const spareMaalIn = document.getElementById('profil-sparemaal-input');
  const malIn    = document.getElementById('profil-mal-input');

  // Tab switching inside modal
  modal.querySelectorAll('.innst-tab-btn').forEach(tabBtn => {
    tabBtn.addEventListener('click', () => {
      const tab = tabBtn.dataset.innstTab;
      modal.querySelectorAll('.innst-tab-btn').forEach(b => {
        const active = b === tabBtn;
        b.classList.toggle('text-brand-600', active);
        b.classList.toggle('dark:text-brand-400', active);
        b.classList.toggle('border-brand-600', active);
        b.classList.toggle('dark:border-brand-400', active);
        b.classList.toggle('text-gray-500', !active);
        b.classList.toggle('dark:text-gray-400', !active);
        b.classList.toggle('border-transparent', !active);
      });
      document.getElementById('innst-profil').classList.toggle('hidden', tab !== 'profil');
      document.getElementById('innst-varsler').classList.toggle('hidden', tab !== 'varsler');
      if (tab === 'varsler') visVarslerTab();
    });
  });

  function apneModal(startTab) {
    const p = hentProfil();
    navnIn.value      = p.navn;
    spareMaalIn.value = p.spareMaal || '';
    malIn.value       = p.malMnd || '';
    // Reset to profil tab unless varsler requested
    if (startTab === 'varsler') {
      modal.querySelector('[data-innst-tab="varsler"]').click();
    } else {
      modal.querySelector('[data-innst-tab="profil"]').click();
    }
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    if (startTab !== 'varsler') navnIn.focus();
  }

  function lukkInnstillingerModal() {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
  }

  btn.addEventListener('click', () => apneModal('profil'));
  lukkBtn.addEventListener('click', lukkInnstillingerModal);
  avbrytBtn.addEventListener('click', lukkInnstillingerModal);
  modal.addEventListener('click', e => { if (e.target === modal) lukkInnstillingerModal(); });

  lagreBtn.addEventListener('click', () => {
    lagreProfil(navnIn.value.trim(), parseFloat(malIn.value) || 0, parseFloat(spareMaalIn.value) || 0);
    lukkInnstillingerModal();
    visGreeting();
    if (aktivTab === 'portfolio') visPortefolje();
  });

  visGreeting();
}

// Keep legacy alias so any existing call to initProfil() still works during transition
function initProfil() { initInnstillinger(); }

// ── SAMMENDRAG ─────────────────────────────────────────────────────────────
function oppdaterSammendrag() {
  const pf = hentPF();
  const fav = hentFav();
  const harPersonligData = Object.keys(pf).length > 0 || fav.size > 0;
  if (harPersonligData) {
    oppdaterPersonligSammendrag(pf, fav);
  } else {
    oppdaterGeneriskSammendrag();
  }
}

function oppdaterGeneriskSammendrag() {
  document.getElementById('stat-card1-label').textContent = 'Aksjer sporet';
  document.getElementById('stat-card2-label').textContent = 'Høyeste yield';
  document.getElementById('stat-card3-label').textContent = 'Gj.snitt yield';
  document.getElementById('stat-card4-label').textContent = 'Neste ex-dato';

  document.getElementById('stat-antall').textContent = alleAksjer.length;
  document.getElementById('stat-snitt-sub').textContent = '';

  const medYield = alleAksjer.filter(a => a.utbytte_yield > 0);
  if (medYield.length) {
    const snitt = medYield.reduce((s, a) => s + a.utbytte_yield, 0) / medYield.length;
    document.getElementById('stat-snitt-yield').textContent = snitt.toFixed(2) + '%';
    const hoyest = [...medYield].sort((a, b) => b.utbytte_yield - a.utbytte_yield)[0];
    document.getElementById('stat-hoyest-yield').textContent = hoyest.utbytte_yield.toFixed(2) + '%';
    document.getElementById('stat-hoyest-navn').textContent = hoyest.ticker;
  }

  const idag = new Date(); idag.setHours(0,0,0,0);
  const fremtidige = alleAksjer
    .filter(a => a.ex_dato && new Date(a.ex_dato) >= idag)
    .sort((a, b) => new Date(a.ex_dato) - new Date(b.ex_dato));
  if (fremtidige.length) {
    const neste = fremtidige[0];
    document.getElementById('stat-neste-ex').textContent = formaterDato(neste.ex_dato);
    document.getElementById('stat-neste-ex-navn').textContent = neste.ticker;
  }
}

function oppdaterPersonligSammendrag(pf, fav) {
  const idag = new Date(); idag.setHours(0,0,0,0);
  const om7 = new Date(idag); om7.setDate(om7.getDate() + 7);
  const om3 = new Date(idag); om3.setDate(om3.getDate() + 3);
  const alleTickere = new Set([...Object.keys(pf), ...fav]);

  // Kort 1: Ex-dato denne uken (fra portefølje + favoritter)
  const exDenneUken = alleAksjer.filter(a =>
    alleTickere.has(a.ticker) && a.ex_dato &&
    new Date(a.ex_dato) >= idag && new Date(a.ex_dato) <= om7
  ).sort((a, b) => new Date(a.ex_dato) - new Date(b.ex_dato));
  document.getElementById('stat-card1-label').textContent = 'Ex-dato denne uken';
  document.getElementById('stat-antall').textContent = exDenneUken.length || '—';
  document.getElementById('stat-hoyest-navn').textContent = exDenneUken.length
    ? exDenneUken.slice(0,3).map(a => a.ticker).join(', ') + (exDenneUken.length > 3 ? '…' : '')
    : 'Ingen denne uken';

  // Kort 2: Neste utbetaling fra portefølje
  const nesteBetaling = alleAksjer
    .filter(a => pf[a.ticker] && a.betaling_dato && new Date(a.betaling_dato) >= idag)
    .sort((a, b) => new Date(a.betaling_dato) - new Date(b.betaling_dato))[0];
  document.getElementById('stat-card2-label').textContent = 'Neste utbetaling';
  if (nesteBetaling) {
    const belop = pf[nesteBetaling.ticker] * (nesteBetaling.siste_utbytte || nesteBetaling.utbytte_per_aksje || 0);
    document.getElementById('stat-hoyest-yield').textContent =
      belop > 0 ? belop.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr' : formaterDato(nesteBetaling.betaling_dato);
    document.getElementById('stat-hoyest-navn').textContent = nesteBetaling.ticker + ' · ' + formaterDato(nesteBetaling.betaling_dato);
  } else {
    document.getElementById('stat-hoyest-yield').textContent = '—';
    document.getElementById('stat-hoyest-navn').textContent = 'Ingen planlagt';
  }

  // Kort 3: Siste sjanse (ex ≤ 3 dager, yield ≥ 5%)
  const sistesjanse = alleAksjer.filter(a =>
    a.ex_dato && a.utbytte_yield >= 5 &&
    new Date(a.ex_dato) >= idag && new Date(a.ex_dato) <= om3
  ).sort((a, b) => b.utbytte_yield - a.utbytte_yield)[0];
  document.getElementById('stat-card3-label').textContent = 'Siste sjanse';
  if (sistesjanse) {
    const dager = Math.ceil((new Date(sistesjanse.ex_dato) - idag) / 86400000);
    document.getElementById('stat-snitt-yield').textContent = sistesjanse.utbytte_yield.toFixed(1) + '%';
    document.getElementById('stat-snitt-sub').textContent = sistesjanse.ticker + ' · ex ' + (dager === 0 ? 'i dag' : `om ${dager}d`);
  } else {
    document.getElementById('stat-snitt-yield').textContent = '—';
    document.getElementById('stat-snitt-sub').textContent = 'Ingen innen 3 dager';
  }

  // Kort 4: Neste ex-dato (generisk, uendret)
  document.getElementById('stat-card4-label').textContent = 'Neste ex-dato';
  const fremtidige = alleAksjer
    .filter(a => a.ex_dato && new Date(a.ex_dato) >= idag)
    .sort((a, b) => new Date(a.ex_dato) - new Date(b.ex_dato));
  if (fremtidige.length) {
    document.getElementById('stat-neste-ex').textContent = formaterDato(fremtidige[0].ex_dato);
    document.getElementById('stat-neste-ex-navn').textContent = fremtidige[0].ticker;
  }
}

// ── HVA SKJER I DAG ────────────────────────────────────────────────────────
function visHvaSkjerIDag() {
  const el = document.getElementById('hva-skjer-idag');
  if (!el || !alleAksjer.length) return;

  const pf  = hentPF();
  const fav = hentFav();
  const idag    = new Date(); idag.setHours(0,0,0,0);
  const imorgen = new Date(idag); imorgen.setDate(idag.getDate() + 1);
  const om7     = new Date(idag); om7.setDate(idag.getDate() + 7);

  const dagStr     = idag.toISOString().slice(0,10);
  const imorgenStr = imorgen.toISOString().slice(0,10);
  const fmtKr = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';

  const pills = [];

  // 1. Utbetaling i dag (portefølje)
  alleAksjer.forEach(a => {
    if (!pf[a.ticker] || !a.betaling_dato) return;
    if (a.betaling_dato.slice(0,10) !== dagStr) return;
    const belop = pf[a.ticker] * (a.siste_utbytte || a.utbytte_per_aksje || 0);
    const belopTekst = belop > 0 ? ` (~${fmtKr(belop)})` : '';
    pills.push(`<span class="dag-pill dag-pill-utbetaling cursor-pointer" data-ticker="${a.ticker}">
      💰 Utbetaling i dag: <strong>${a.ticker}</strong>${belopTekst}
    </span>`);
  });

  // 2. Ex-dato i dag – portefølje/favoritter (du eier allerede → ingen advarsel)
  alleAksjer.forEach(a => {
    if (!a.ex_dato || a.ex_dato.slice(0,10) !== dagStr) return;
    const erMin = pf[a.ticker] || fav.has(a.ticker);
    if (!erMin) return;
    pills.push(`<span class="dag-pill dag-pill-ex cursor-pointer" data-ticker="${a.ticker}">
      📅 Ex-dato i dag: <strong>${a.ticker}</strong> (${a.utbytte_yield.toFixed(1)}%)
    </span>`);
  });

  // 3. Ex-dato i dag – høy-yield aksjer du IKKE eier (siste sjanse i dag)
  alleAksjer.forEach(a => {
    if (!a.ex_dato || a.ex_dato.slice(0,10) !== dagStr) return;
    if (pf[a.ticker] || fav.has(a.ticker)) return;
    if (a.utbytte_yield < 4) return;
    pills.push(`<span class="dag-pill dag-pill-siste cursor-pointer" data-ticker="${a.ticker}">
      ⚡ Siste sjanse i dag: <strong>${a.ticker}</strong> ${a.utbytte_yield.toFixed(1)}%
    </span>`);
  });

  // 4. Ex-dato i morgen – siste sjanse (høy yield, ikke i portefølje)
  alleAksjer.forEach(a => {
    if (!a.ex_dato || a.ex_dato.slice(0,10) !== imorgenStr) return;
    if (pf[a.ticker]) return;
    if (a.utbytte_yield < 4) return;
    pills.push(`<span class="dag-pill dag-pill-siste cursor-pointer" data-ticker="${a.ticker}">
      ⚡ Siste sjanse i morgen: <strong>${a.ticker}</strong> ${a.utbytte_yield.toFixed(1)}%
    </span>`);
  });

  // 5. Utbetalinger denne uken (portefølje, fra i morgen)
  const ukeBetalinger = alleAksjer.filter(a =>
    pf[a.ticker] && a.betaling_dato &&
    new Date(a.betaling_dato) > idag && new Date(a.betaling_dato) <= om7
  ).sort((a, b) => new Date(a.betaling_dato) - new Date(b.betaling_dato));

  if (ukeBetalinger.length) {
    const totalUke = ukeBetalinger.reduce((s, a) =>
      s + pf[a.ticker] * (a.siste_utbytte || a.utbytte_per_aksje || 0), 0);
    const tickerListe = ukeBetalinger.slice(0,3).map(a => a.ticker).join(', ')
      + (ukeBetalinger.length > 3 ? ` +${ukeBetalinger.length - 3}` : '');
    pills.push(`<span class="dag-pill dag-pill-uke">
      📬 Utbetalinger denne uken: ${tickerListe}${totalUke > 0 ? ` (~${fmtKr(totalUke)})` : ''}
    </span>`);
  }

  // 6. Aksjer under målpris
  const _adDag = hentAlleAksjeData();
  alleAksjer.forEach(a => {
    const d = _adDag[a.ticker];
    if (!d || !d.malPris || d.malPris <= 0) return;
    if (a.pris <= 0 || a.pris > d.malPris) return;
    pills.push(`<span class="dag-pill dag-pill-malpris cursor-pointer" data-ticker="${a.ticker}">
      🎯 Under målpris: <strong>${a.ticker}</strong> (${a.pris.toFixed(0)} / mål ${d.malPris.toFixed(0)})
    </span>`);
  });

  if (!pills.length) { el.classList.add('hidden'); return; }

  const datoTekst = idag.toLocaleDateString('nb-NO', { weekday: 'long', day: 'numeric', month: 'long' });
  el.innerHTML = `
    <div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3 shadow-sm">
      <p class="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-2.5">
        I dag · ${datoTekst.charAt(0).toUpperCase() + datoTekst.slice(1)}
      </p>
      <div class="flex flex-wrap gap-2">${pills.join('')}</div>
    </div>`;
  el.classList.remove('hidden');

  el.querySelectorAll('[data-ticker]').forEach(pill => {
    pill.addEventListener('click', () => {
      const aksje = alleAksjer.find(a => a.ticker === pill.dataset.ticker);
      if (aksje) visModal(aksje);
    });
  });
}

// ── OVERSIKTSTABELL + KORT ─────────────────────────────────────────────────
function visOversikt() {
  visOpportunityFeed();
  visHvaSkjerIDag();
  const data = sorterAksjer(filtrerteAksjer());
  const tbody = document.getElementById('tabell-body');
  const kortBody = document.getElementById('kort-body');
  const ingenEl = document.getElementById('ingen-resultater');
  const ingenMobilEl = document.getElementById('ingen-resultater-mobil');
  const antallEl = document.getElementById('antall-vist');

  // Oppdater sorteringsikoner
  document.querySelectorAll('th.sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === sortering.kol) th.classList.add('sort-' + sortering.retning);
  });

  if (data.length === 0) {
    tbody.innerHTML = '';
    kortBody.innerHTML = '';
    ingenEl.classList.remove('hidden');
    ingenMobilEl.classList.remove('hidden');
    antallEl.textContent = '';
    return;
  }
  ingenEl.classList.add('hidden');
  ingenMobilEl.classList.add('hidden');
  antallEl.textContent = `Viser ${data.length} av ${alleAksjer.length} aksjer`;

  const idag = new Date(); idag.setHours(0,0,0,0);
  const om30 = new Date(idag); om30.setDate(om30.getDate() + 30);
  const _ad = hentAlleAksjeData();

  tbody.innerHTML = data.map(a => {
    const exDato = a.ex_dato ? new Date(a.ex_dato) : null;
    const snartEx = exDato && exDato >= idag && exDato <= om30;
    const rowClass = snartEx ? 'row-highlight' : '';
    const _d = _ad[a.ticker] || {};
    const _harNotat  = !!_d.notat;
    const _underMal  = _d.malPris > 0 && a.pris > 0 && a.pris <= _d.malPris;

    return `
    <tr class="table-row ${rowClass}" data-ticker="${a.ticker}">
      <td class="px-2 py-3 w-8">${stjerne(a.ticker)}</td>
      <td class="px-4 py-3 font-mono font-bold text-brand-700 dark:text-brand-400">${a.ticker}</td>
      <td class="px-4 py-3">
        <div class="font-medium leading-tight">${a.navn}</div>
        <div class="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1.5">
          ${a.sektor}
          ${_harNotat ? '<span title="Har notat" class="opacity-60">✏</span>' : ''}
          ${_underMal ? '<span title="Under målpris" class="text-blue-500 dark:text-blue-400">🎯</span>' : ''}
        </div>
      </td>
      <td class="px-4 py-3 text-right font-medium">
        ${fmt(a.pris)} <span class="text-xs text-gray-400">${a.valuta}</span>
      </td>
      <td class="col-detalj px-4 py-3 w-36">
        ${rangebar(a.pris, a['52u_lav'], a['52u_hoy'])}
      </td>
      <td class="px-4 py-3 text-right">
        <span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span>
      </td>
      <td class="px-4 py-3 text-center">${scoreBadge(beregnScore(a))}</td>
      <td class="col-detalj px-4 py-3 text-right">
        ${a.snitt_yield_5ar > 0 ? `<span class="yield-badge ${yieldKlasse(a.snitt_yield_5ar)}">${a.snitt_yield_5ar.toFixed(1)}%</span>` : '<span class="text-gray-400">—</span>'}
      </td>
      <td class="col-detalj px-4 py-3 text-right">${fmt(a.utbytte_per_aksje)}</td>
      <td class="px-4 py-3 text-right">
        <span class="${payoutKlasse(a.payout_ratio)}">${a.payout_ratio > 0 ? a.payout_ratio.toFixed(0) + '%' : '—'}</span>
      </td>
      <td class="px-4 py-3 text-right ${vekstKlasse(a.utbytte_vekst_5ar)}">
        ${a.utbytte_vekst_5ar !== 0 ? (a.utbytte_vekst_5ar > 0 ? '+' : '') + a.utbytte_vekst_5ar.toFixed(1) + '%' : '—'}
      </td>
      <td class="col-detalj px-4 py-3 text-right text-gray-600 dark:text-gray-400">${a.ar_med_utbytte > 0 ? a.ar_med_utbytte : '—'}</td>
      <td class="col-detalj px-4 py-3 text-right text-gray-600 dark:text-gray-400">${a.pe_ratio > 0 ? a.pe_ratio.toFixed(1) : '—'}</td>
      <td class="col-detalj px-4 py-3 text-right text-gray-600 dark:text-gray-400">${a.pb_ratio > 0 ? a.pb_ratio.toFixed(1) : '—'}</td>
      <td class="px-4 py-3 text-center ${snartEx ? 'font-semibold text-amber-700 dark:text-amber-400 font-semibold' : 'text-gray-600 dark:text-gray-400'}">
        ${a.ex_dato ? formaterDato(a.ex_dato) : '—'}
        ${snartEx ? '<span class="block text-xs text-orange-500">Snart!</span>' : ''}
      </td>
      <td class="col-detalj px-4 py-3 text-center text-gray-500 dark:text-gray-500">${a.betaling_dato ? formaterDato(a.betaling_dato) : '—'}</td>
      <td class="px-4 py-3 text-center">
        <span class="frekvens-badge">${a.frekvens}</span>
      </td>
    </tr>`;
  }).join('');

  // Klikk via event delegation (tabell) – ingen minnelekasje
  tbody.onclick = e => {
    const favBtn = e.target.closest('.fav-btn');
    if (favBtn) {
      e.stopPropagation();
      toggleFav(favBtn.dataset.ticker);
      oppdaterFavBtn();
      visOversikt();
      return;
    }
    const tr = e.target.closest('tr[data-ticker]');
    if (!tr) return;
    const aksje = alleAksjer.find(a => a.ticker === tr.dataset.ticker);
    if (aksje) visModal(aksje);
  };

  // ── MOBIL KORTVISNING ──────────────────────────────────────────────────
  // Bytt mellom space-y-3 (normal) og tett listestil (kompakt)
  kortBody.className = kompaktModus
    ? 'rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm divide-y divide-gray-100 dark:divide-gray-800'
    : 'space-y-3';

  kortBody.innerHTML = data.map(a => {
    const exDato = a.ex_dato ? new Date(a.ex_dato) : null;
    const idag2 = new Date(); idag2.setHours(0,0,0,0);
    const om30b = new Date(idag2); om30b.setDate(om30b.getDate() + 30);
    const snartEx = exDato && exDato >= idag2 && exDato <= om30b;
    const dagerTil = exDato ? Math.ceil((exDato - idag2) / (1000*60*60*24)) : null;

    // ── KOMPAKT MOBILKORT (liste-rad) ──────────────────────────────────
    const kompaktKort = `
    <div class="aksje-kort-kompakt ${snartEx ? 'snart-ex' : ''}" data-ticker="${a.ticker}">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2">
          ${stjerne(a.ticker, 'shrink-0')}
          <span class="font-mono font-bold text-brand-700 dark:text-brand-400 text-sm">${a.ticker}</span>
          <span class="frekvens-badge">${a.frekvens}</span>
          ${snartEx ? `<span class="text-xs text-amber-600 dark:text-amber-400 font-medium">Ex ${dagerTil === 0 ? 'i dag' : dagerTil === 1 ? 'i morgen' : `om ${dagerTil}d`}</span>` : ''}
        </div>
        <div class="text-xs text-gray-500 dark:text-gray-400 truncate">${a.navn}</div>
      </div>
      <div class="text-right shrink-0 space-y-0.5">
        <span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span>
        <div class="text-xs ${payoutKlasse(a.payout_ratio)}">Payout ${a.payout_ratio > 0 ? a.payout_ratio.toFixed(0)+'%' : '—'}</div>
      </div>
    </div>`;

    // ── NORMALT MOBILKORT (full detalj) ────────────────────────────────
    const normalKort = `
    <div class="aksje-kort ${snartEx ? 'snart-ex' : ''}" data-ticker="${a.ticker}">
      <div class="flex items-start justify-between gap-2 mb-2">
        <div class="flex items-start gap-2">
          ${stjerne(a.ticker, 'mt-0.5 shrink-0')}
          <div>
            <span class="font-mono font-bold text-brand-700 dark:text-brand-400 text-base">${a.ticker}</span>
            <span class="frekvens-badge ml-2">${a.frekvens}</span>
            <div class="text-sm text-gray-600 dark:text-gray-400 mt-0.5 leading-tight">${a.navn}</div>
            <div class="text-xs text-gray-400 dark:text-gray-500">${a.sektor}</div>
          </div>
        </div>
        <div class="flex flex-col items-end gap-1 shrink-0">
          <span class="yield-badge ${yieldKlasse(a.utbytte_yield)} text-sm">${a.utbytte_yield.toFixed(2)}%</span>
          ${scoreBadge(beregnScore(a))}
        </div>
      </div>
      <div class="grid grid-cols-3 gap-2 text-center my-3">
        <div class="bg-gray-50 dark:bg-gray-800 rounded-lg py-2 px-1">
          <div class="text-xs text-gray-400 leading-tight">Pris</div>
          <div class="font-semibold text-sm mt-0.5">${fmt(a.pris)}</div>
          <div class="text-xs text-gray-400">${a.valuta}</div>
        </div>
        <div class="bg-gray-50 dark:bg-gray-800 rounded-lg py-2 px-1">
          <div class="text-xs text-gray-400 leading-tight">Utb./aksje</div>
          <div class="font-semibold text-sm mt-0.5">${fmt(a.utbytte_per_aksje)}</div>
          <div class="text-xs text-gray-400">${a.valuta}</div>
        </div>
        <div class="bg-gray-50 dark:bg-gray-800 rounded-lg py-2 px-1">
          <div class="text-xs text-gray-400 leading-tight">Payout</div>
          <div class="font-semibold text-sm mt-0.5 ${payoutKlasse(a.payout_ratio)}">${a.payout_ratio > 0 ? a.payout_ratio.toFixed(0)+'%' : '—'}</div>
        </div>
      </div>
      <div class="grid grid-cols-3 gap-2 text-center mb-3">
        <div class="bg-gray-50 dark:bg-gray-800 rounded-lg py-2 px-1">
          <div class="text-xs text-gray-400 leading-tight">Vekst 5år</div>
          <div class="font-semibold text-sm mt-0.5 ${vekstKlasse(a.utbytte_vekst_5ar)}">${a.utbytte_vekst_5ar !== 0 ? (a.utbytte_vekst_5ar>0?'+':'')+a.utbytte_vekst_5ar.toFixed(1)+'%' : '—'}</div>
        </div>
        <div class="bg-gray-50 dark:bg-gray-800 rounded-lg py-2 px-1">
          <div class="text-xs text-gray-400 leading-tight">P/E</div>
          <div class="font-semibold text-sm mt-0.5">${a.pe_ratio > 0 ? a.pe_ratio.toFixed(1) : '—'}</div>
        </div>
        <div class="bg-gray-50 dark:bg-gray-800 rounded-lg py-2 px-1">
          <div class="text-xs text-gray-400 leading-tight">År m/utb.</div>
          <div class="font-semibold text-sm mt-0.5">${a.ar_med_utbytte > 0 ? a.ar_med_utbytte : '—'}</div>
        </div>
      </div>
      ${rangebar(a.pris, a['52u_lav'], a['52u_hoy'])}
      <div class="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 text-sm">
        <div>
          <span class="text-xs text-gray-400">Ex-dato: </span>
          <span class="${snartEx ? 'text-orange-600 dark:text-orange-400 font-semibold' : 'text-gray-600 dark:text-gray-400'}">
            ${a.ex_dato ? formaterDato(a.ex_dato) : '—'}
          </span>
          ${snartEx && dagerTil !== null ? `<span class="text-xs text-orange-500 ml-1">${dagerTil === 0 ? '(i dag!)' : dagerTil === 1 ? '(i morgen)' : `(om ${dagerTil} d)`}</span>` : ''}
        </div>
        <svg class="w-4 h-4 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
      </div>
    </div>`;

    return kompaktModus ? kompaktKort : normalKort;
  }).join('');

  // Klikk via event delegation (kort) – ingen minnelekasje
  kortBody.onclick = e => {
    const favBtn = e.target.closest('.fav-btn');
    if (favBtn) {
      e.stopPropagation();
      toggleFav(favBtn.dataset.ticker);
      oppdaterFavBtn();
      visOversikt();
      return;
    }
    const kort = e.target.closest('[data-ticker]');
    if (!kort) return;
    const aksje = alleAksjer.find(a => a.ticker === kort.dataset.ticker);
    if (aksje) visModal(aksje);
  };
}

function sorterAksjer(data) {
  const { kol, retning } = sortering;
  const hentVerdi = (a) => kol === 'utbytte_score' ? beregnScore(a) : a[kol];
  const fav = hentFav();
  return [...data].sort((a, b) => {
    // Favoritter alltid øverst (med mindre man filtrerer kun favoritter)
    if (!visKunFavoritter) {
      const fa = fav.has(a.ticker) ? 0 : 1;
      const fb = fav.has(b.ticker) ? 0 : 1;
      if (fa !== fb) return fa - fb;
    }
    let va = hentVerdi(a), vb = hentVerdi(b);
    if (va == null) va = retning === 'asc' ? Infinity : -Infinity;
    if (vb == null) vb = retning === 'asc' ? Infinity : -Infinity;
    if (typeof va === 'string') return retning === 'asc' ? va.localeCompare(vb, 'nb') : vb.localeCompare(va, 'nb');
    return retning === 'asc' ? va - vb : vb - va;
  });
}

// ── KALENDER ───────────────────────────────────────────────────────────────
// Kalender-badge konfigurasjoner
const KAL_TYPER = {
  ex:      { label: 'Ex-dag',    bg: 'bg-orange-100 dark:bg-orange-900/40', text: 'text-orange-700 dark:text-orange-300', dag: 'text-orange-600 dark:text-orange-400' },
  utbytte: { label: 'Utbytte',   bg: 'bg-green-100 dark:bg-green-900/40',  text: 'text-green-700 dark:text-green-300',   dag: 'text-green-600 dark:text-green-400'   },
  rapport: { label: 'Rapport',   bg: 'bg-blue-100 dark:bg-blue-900/40',    text: 'text-blue-700 dark:text-blue-300',     dag: 'text-blue-600 dark:text-blue-400'     },
};

function visKalender() {
  const container = document.getElementById('kalender-innhold');
  const idag = new Date(); idag.setHours(0,0,0,0);
  const sok = (document.getElementById('sok')?.value || '').toLowerCase().trim();

  // Bygg flat liste av alle hendelser (ex, utbytte, rapport)
  const hendelser = [];
  alleAksjer.forEach(a => {
    if (sok && !a.ticker.toLowerCase().includes(sok) && !a.navn.toLowerCase().includes(sok)) return;
    if (a.ex_dato)      hendelser.push({ dato: a.ex_dato,      type: 'ex',      aksje: a });
    if (a.betaling_dato) hendelser.push({ dato: a.betaling_dato, type: 'utbytte', aksje: a });
    if (a.rapport_dato) hendelser.push({ dato: a.rapport_dato,  type: 'rapport', aksje: a });
  });
  hendelser.sort((x, y) => new Date(x.dato) - new Date(y.dato));

  // Grupper per måned
  const manedsMap = {};
  hendelser.forEach(h => {
    const d = new Date(h.dato);
    const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
    if (!manedsMap[key]) manedsMap[key] = [];
    manedsMap[key].push(h);
  });

  if (Object.keys(manedsMap).length === 0) {
    container.innerHTML = '<p class="text-gray-400 py-8 text-center">Ingen hendelser matcher søket.</p>';
    return;
  }

  const MANED = ['jan','feb','mar','apr','mai','jun','jul','aug','sep','okt','nov','des'];

  container.innerHTML = Object.entries(manedsMap).map(([key, hendelseListe]) => {
    const [year, month] = key.split('-');
    const manedNavn = new Date(parseInt(year), parseInt(month)-1, 1)
      .toLocaleDateString('nb-NO', { month: 'long', year: 'numeric' });

    const rader = hendelseListe.map(({ dato, type, aksje: a }) => {
      const d = new Date(dato);
      const erPassert = d < idag;
      const dagerTil = Math.ceil((d - idag) / (1000*60*60*24));
      const cfg = KAL_TYPER[type];

      let detalj = '';
      if (type === 'ex') {
        detalj = `Siste utbytte: <strong>${fmt(a.siste_utbytte)} ${a.valuta}</strong>`;
      } else if (type === 'utbytte') {
        detalj = `Utbetaling: <strong>${fmt(a.siste_utbytte)} ${a.valuta}</strong> per aksje`;
      } else if (type === 'rapport') {
        detalj = `Kvartalsrapport`;
      }

      return `
      <div class="kal-rad cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors ${erPassert ? 'opacity-40' : ''}" data-ticker="${a.ticker}">
        <div class="flex items-center gap-3 flex-1 pointer-events-none">
          <div class="text-center w-12 shrink-0">
            <div class="text-xs text-gray-400">${MANED[d.getMonth()]}</div>
            <div class="text-xl font-bold leading-none ${erPassert ? 'text-gray-400' : cfg.dag}">${d.getDate()}</div>
          </div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-xs font-semibold px-1.5 py-0.5 rounded ${cfg.bg} ${cfg.text}">${cfg.label}</span>
              <span class="font-mono font-bold text-brand-700 dark:text-brand-400">${a.ticker}</span>
              <span class="text-gray-600 dark:text-gray-400 text-sm truncate">${a.navn}</span>
            </div>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">${detalj}</div>
          </div>
        </div>
        <div class="text-right min-w-16 shrink-0 pointer-events-none">
          ${type !== 'rapport' ? `<span class="yield-badge ${yieldKlasse(a.utbytte_yield)} text-sm">${a.utbytte_yield.toFixed(2)}%</span>` : ''}
          ${!erPassert ? `<div class="text-xs text-gray-400 mt-1">${dagerTil === 0 ? 'I dag!' : dagerTil === 1 ? 'I morgen' : `om ${dagerTil}d`}</div>` : '<div class="text-xs text-gray-400 mt-1">Passert</div>'}
        </div>
      </div>`;
    }).join('');

    const antEx      = hendelseListe.filter(h => h.type === 'ex').length;
    const antUtbytte = hendelseListe.filter(h => h.type === 'utbytte').length;
    const antRapport = hendelseListe.filter(h => h.type === 'rapport').length;
    const oppsummer = [
      antEx      ? `${antEx} ex-dag`      : '',
      antUtbytte ? `${antUtbytte} utbytte` : '',
      antRapport ? `${antRapport} rapport` : '',
    ].filter(Boolean).join(' · ');

    return `
    <div class="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
      <div class="px-4 py-3 bg-gray-100 dark:bg-gray-900 font-semibold capitalize flex items-center justify-between">
        <span>${manedNavn}</span>
        <span class="text-xs font-normal text-gray-400">${oppsummer}</span>
      </div>
      <div class="divide-y divide-gray-100 dark:divide-gray-800" data-kal-gruppe>${rader}</div>
    </div>`;
  }).join('');

  // Klikk → modal
  container.onclick = e => {
    const rad = e.target.closest('[data-ticker]');
    if (!rad) return;
    const aksje = alleAksjer.find(a => a.ticker === rad.dataset.ticker);
    if (aksje) visModal(aksje);
  };
}

// ── FAVORITTER ─────────────────────────────────────────────────────────────
function hentFav() {
  try { return new Set(JSON.parse(localStorage.getItem('fav_aksjer') || '[]')); } catch { return new Set(); }
}
function lagreFav(fav) { localStorage.setItem('fav_aksjer', JSON.stringify([...fav])); }
function erFavoritt(ticker) { return hentFav().has(ticker); }
function toggleFav(ticker) {
  const fav = hentFav();
  if (fav.has(ticker)) fav.delete(ticker); else fav.add(ticker);
  lagreFav(fav);
}

function stjerne(ticker, ekstraKlasse = '') {
  const er = erFavoritt(ticker);
  return `<button class="fav-btn ${ekstraKlasse} transition-colors" data-ticker="${ticker}" title="${er ? 'Fjern favoritt' : 'Legg til favoritt'}" aria-label="Favoritt">
    <svg class="w-4 h-4 pointer-events-none ${er ? 'text-yellow-400' : 'text-gray-300 dark:text-gray-600'}" fill="${er ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>
  </button>`;
}

// ── PORTEFØLJEKALKULATOR ───────────────────────────────────────────────────
function hentPF() {
  try { return JSON.parse(localStorage.getItem('pf_beholdning') || '{}'); } catch { return {}; }
}
function lagrePF(pf) { localStorage.setItem('pf_beholdning', JSON.stringify(pf)); }

function initPortefolje() {
  document.getElementById('pf-legg-til').addEventListener('click', () => {
    const sel = document.getElementById('pf-velg-aksje');
    const antallEl = document.getElementById('pf-antall');
    const feilEl = document.getElementById('pf-feil');
    const ticker = sel.value;
    const antall = parseInt(antallEl.value, 10);
    feilEl.classList.add('hidden');
    if (!ticker) { feilEl.textContent = 'Velg en aksje.'; feilEl.classList.remove('hidden'); return; }
    if (!antall || antall < 1) { feilEl.textContent = 'Skriv inn gyldig antall aksjer.'; feilEl.classList.remove('hidden'); return; }
    const pf = hentPF();
    pf[ticker] = antall;
    lagrePF(pf);
    sel.value = '';
    antallEl.value = '';
    visPortefolje();
  });

  document.getElementById('pf-antall').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('pf-legg-til').click();
  });

  document.getElementById('pf-eksport-csv').addEventListener('click', eksporterCSV);

  // ── CSV-IMPORT ─────────────────────────────────────────────────────────────
  const filInput = document.getElementById('pf-importer-fil');

  function triggerFilInput() { filInput.click(); }

  document.getElementById('pf-importer-csv').addEventListener('click', triggerFilInput);

  const tomKnapp = document.getElementById('pf-importer-csv-tom');
  if (tomKnapp) tomKnapp.addEventListener('click', triggerFilInput);

  filInput.addEventListener('change', () => {
    const fil = filInput.files[0];
    if (!fil) return;
    const reader = new FileReader();
    reader.onload = e => {
      const { gyldig, ukjent, profil } = parseCSV(e.target.result);
      window._importProfil = profil;
      visImportPreview(gyldig, ukjent);
    };
    reader.readAsText(fil, 'UTF-8');
    filInput.value = '';
  });

  document.getElementById('pf-importer-bekreft-legg-til').addEventListener('click', () => {
    bekreftImport(window._importData, false);
  });
  document.getElementById('pf-importer-bekreft-erstatt').addEventListener('click', () => {
    bekreftImport(window._importData, true);
  });
  document.getElementById('pf-importer-avbryt').addEventListener('click', () => {
    document.getElementById('pf-importer-preview').classList.add('hidden');
    window._importData = null;
  });

  // ── QR-KODE ────────────────────────────────────────────────────────────────
  document.getElementById('pf-qr-btn').addEventListener('click', visQRModal);
  document.getElementById('qr-lukk').addEventListener('click', () => {
    clearInterval(document.getElementById('qr-modal')._timer);
    document.getElementById('qr-modal').classList.add('hidden');
    document.getElementById('qr-modal').classList.remove('flex');
  });

  // ── INNTEKTSTELLER-MÅL ─────────────────────────────────────────────────────
  const malInput = document.getElementById('pf-inntekt-mal');
  malInput.value = localStorage.getItem('pf_inntekt_mal') || '';
  malInput.addEventListener('change', () => {
    localStorage.setItem('pf_inntekt_mal', malInput.value);
    visPortefolje();
  });
}

function fyllPFDropdown() {
  const sel = document.getElementById('pf-velg-aksje');
  const pf = hentPF();
  const valgt = sel.value;
  sel.innerHTML = '<option value="">Velg aksje…</option>';
  [...alleAksjer]
    .sort((a, b) => a.ticker.localeCompare(b.ticker, 'nb'))
    .forEach(a => {
      const opt = document.createElement('option');
      opt.value = a.ticker;
      opt.textContent = `${a.ticker} – ${a.navn}`;
      if (pf[a.ticker]) opt.textContent += ` (${pf[a.ticker]} aksjer)`;
      sel.appendChild(opt);
    });
  if (valgt) sel.value = valgt;
}

function visPortefolje() {
  fyllPFDropdown();
  const pf = hentPF();
  const sok = (document.getElementById('sok')?.value || '').toLowerCase().trim();
  const idag = new Date(); idag.setHours(0,0,0,0);

  const alleBeholdning = Object.entries(pf)
    .map(([ticker, antall]) => {
      const a = alleAksjer.find(x => x.ticker === ticker);
      if (!a || antall < 1) return null;
      return { ...a, antall, forv_ar: antall * (a.utbytte_per_aksje || 0) };
    })
    .filter(Boolean)
    .sort((a, b) => b.forv_ar - a.forv_ar);

  const beholdning = sok
    ? alleBeholdning.filter(a => a.ticker.toLowerCase().includes(sok) || a.navn.toLowerCase().includes(sok))
    : alleBeholdning;

  const harBeholdning = alleBeholdning.length > 0;
  document.getElementById('pf-tom').classList.toggle('hidden', harBeholdning);
  document.getElementById('pf-beholdning-wrapper').classList.toggle('hidden', !harBeholdning);
  document.getElementById('pf-tidslinje-wrapper').classList.toggle('hidden', !harBeholdning);
  document.getElementById('pf-charts-wrapper').style.display = harBeholdning ? 'grid' : 'none';

  document.getElementById('pf-inntekt-wrapper').classList.toggle('hidden', !harBeholdning);
  oppdaterSammendrag(); // oppdater topkort når portefølje endres

  if (!harBeholdning) {
    ['pf-stat-ar','pf-stat-mnd','pf-stat-antall','pf-stat-neste','pf-stat-yield','pf-stat-verdi']
      .forEach(id => { document.getElementById(id).textContent = '—'; });
    document.getElementById('pf-stat-neste-navn').textContent = '';
    return;
  }

  // ── SAMMENDRAG ────────────────────────────────────────────────────────────
  const totalAr = alleBeholdning.reduce((s, a) => s + a.forv_ar, 0);
  const totalVerdi = alleBeholdning.reduce((s, a) => s + a.antall * (a.pris || 0), 0);
  const fmtKr = v => v.toLocaleString('nb-NO', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' kr';

  sjekkMilepeler(totalAr);
  document.getElementById('pf-stat-ar').textContent = fmtKr(totalAr);
  document.getElementById('pf-stat-mnd').textContent = fmtKr(totalAr / 12);
  document.getElementById('pf-stat-antall').textContent = alleBeholdning.length;
  document.getElementById('pf-stat-verdi').textContent = fmtKr(totalVerdi);

  // Månedlig mål fra profil
  const { malMnd } = hentProfil();
  const mndMalEl = document.getElementById('pf-mnd-mål');
  if (mndMalEl) {
    if (malMnd > 0) {
      const mndPct = Math.min(100, ((totalAr / 12) / malMnd) * 100);
      document.getElementById('pf-mnd-mål-pct').textContent = mndPct.toFixed(0) + '%';
      document.getElementById('pf-mnd-mål-tekst').textContent = 'av ' + malMnd.toLocaleString('nb-NO') + ' kr';
      document.getElementById('pf-mnd-mål-bar').style.width = mndPct + '%';
      mndMalEl.classList.remove('hidden');
    } else {
      mndMalEl.classList.add('hidden');
    }
  }

  // Vektet yield = totalAr / totalVerdi × 100
  const vektetYield = totalVerdi > 0 ? (totalAr / totalVerdi * 100) : 0;
  document.getElementById('pf-stat-yield').textContent = vektetYield > 0 ? vektetYield.toFixed(2) + '%' : '—';

  // ── INNTEKTSTELLER ────────────────────────────────────────────────────────
  const ytdInntekt = beregnYtdInntekt(alleBeholdning);
  document.getElementById('pf-inntekt-ar').textContent = fmtKr(ytdInntekt);
  const malRaw = parseFloat(localStorage.getItem('pf_inntekt_mal') || '0');
  const progEl = document.getElementById('pf-inntekt-progresjon');
  if (malRaw > 0) {
    const pct = Math.min(100, (ytdInntekt / malRaw) * 100);
    document.getElementById('pf-inntekt-pct-tekst').textContent = pct.toFixed(0) + '%';
    document.getElementById('pf-inntekt-mal-tekst').textContent = 'Mål: ' + fmtKr(malRaw);
    document.getElementById('pf-inntekt-bar').style.width = pct + '%';
    progEl.classList.remove('hidden');
  } else {
    progEl.classList.add('hidden');
  }

  // Neste utbetaling: bruk betaling_dato, fallback til ex_dato
  const nesteRef = a => {
    if (a.betaling_dato && new Date(a.betaling_dato) >= idag) return new Date(a.betaling_dato);
    if (a.ex_dato && new Date(a.ex_dato) >= idag) return new Date(a.ex_dato);
    return null;
  };
  const nestePayout = [...alleBeholdning]
    .map(a => ({ a, dato: nesteRef(a) }))
    .filter(x => x.dato)
    .sort((x, y) => x.dato - y.dato)[0];
  if (nestePayout) {
    const erBetaling = nestePayout.a.betaling_dato && new Date(nestePayout.a.betaling_dato) >= idag;
    document.getElementById('pf-stat-neste').textContent = formaterDato(erBetaling ? nestePayout.a.betaling_dato : nestePayout.a.ex_dato);
    document.getElementById('pf-stat-neste-navn').textContent = nestePayout.a.ticker + (erBetaling ? '' : ' (ex)');
  } else {
    document.getElementById('pf-stat-neste').textContent = '—';
    document.getElementById('pf-stat-neste-navn').textContent = '';
  }

  // ── BEHOLDNINGSTABELL ─────────────────────────────────────────────────────
  const tbody = document.getElementById('pf-tabell-body');
  tbody.innerHTML = beholdning.map(a => `
    <tr class="table-row cursor-pointer" data-ticker="${a.ticker}">
      <td class="px-4 py-3 font-mono font-bold text-brand-700 dark:text-brand-400">${a.ticker}</td>
      <td class="px-4 py-3 hidden sm:table-cell text-gray-600 dark:text-gray-400 text-sm">${a.navn}</td>
      <td class="px-4 py-3 text-right">
        <input type="number" min="1" value="${a.antall}"
          class="w-20 text-right text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1 bg-transparent focus:outline-none focus:ring-1 focus:ring-brand-500"
          data-ticker="${a.ticker}" />
      </td>
      <td class="px-4 py-3 text-right"><span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span></td>
      <td class="px-4 py-3 text-right font-semibold">${fmtKr(a.forv_ar)}</td>
      <td class="px-4 py-3 text-center hidden sm:table-cell text-gray-500 text-sm">${a.ex_dato ? formaterDato(a.ex_dato) : '—'}</td>
      <td class="px-4 py-3 text-center hidden sm:table-cell"><span class="frekvens-badge">${a.frekvens}</span></td>
      <td class="px-4 py-3 text-center">
        <button class="pf-slett text-gray-400 hover:text-red-500 transition-colors p-1" data-ticker="${a.ticker}" title="Fjern">
          <svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </td>
    </tr>`).join('');

  // Sum-rad i footer
  document.getElementById('pf-tabell-footer').innerHTML = `
    <tr>
      <td colspan="2" class="px-4 py-3 text-sm text-gray-500">Totalt (${alleBeholdning.length} selskaper)</td>
      <td class="px-4 py-3 text-right text-sm text-gray-500">${alleBeholdning.reduce((s,a)=>s+a.antall,0)} aksjer</td>
      <td></td>
      <td class="px-4 py-3 text-right text-brand-700 dark:text-brand-400">${fmtKr(totalAr)}</td>
      <td colspan="3"></td>
    </tr>`;

  // Event delegation: klikk på rad → modal (ikke slett-knapp eller input)
  tbody.onclick = e => {
    const btn = e.target.closest('.pf-slett');
    if (btn) {
      const pf2 = hentPF();
      delete pf2[btn.dataset.ticker];
      lagrePF(pf2);
      visPortefolje();
      return;
    }
    const tr = e.target.closest('tr[data-ticker]');
    if (!tr || e.target.closest('input, button')) return;
    const aksje = alleAksjer.find(a => a.ticker === tr.dataset.ticker);
    if (aksje) visModal(aksje);
  };
  tbody.addEventListener('change', e => {
    if (!e.target.matches('input[data-ticker]')) return;
    const v = parseInt(e.target.value, 10);
    if (!v || v < 1) { e.target.value = hentPF()[e.target.dataset.ticker]; return; }
    const pf2 = hentPF();
    pf2[e.target.dataset.ticker] = v;
    lagrePF(pf2);
    visPortefolje();
  });

  // ── KVARTALSVIS TIDSLINJE ─────────────────────────────────────────────────
  const frekvensPerAr = { 'Månedlig': 12, 'Kvartalsvis': 4, 'Halvårlig': 2, 'Årlig': 1, 'Uregelmessig': 1 };
  const kvartaler = ['K1 (jan–mar)', 'K2 (apr–jun)', 'K3 (jul–sep)', 'K4 (okt–des)'];
  const kvartalSummer = [0, 0, 0, 0];

  beholdning.forEach(a => {
    const perAr = frekvensPerAr[a.frekvens] || 1;
    const perUtbetaling = a.forv_ar / perAr;
    if (perAr >= 12) {
      // Månedlig: fordel jevnt over alle 4 kvartaler
      kvartalSummer.forEach((_, i) => { kvartalSummer[i] += perUtbetaling * 3; });
    } else if (perAr === 4) {
      // Kvartalsvis: ett utbytte per kvartal
      kvartalSummer.forEach((_, i) => { kvartalSummer[i] += perUtbetaling; });
    } else if (perAr === 2) {
      // Halvårlig: to kvartaler (K1 og K3, eller bruk betaling_dato)
      const betalMnd = a.betaling_dato ? new Date(a.betaling_dato).getMonth() : null;
      if (betalMnd !== null) {
        const k = Math.floor(betalMnd / 3);
        kvartalSummer[k] += perUtbetaling;
        kvartalSummer[(k + 2) % 4] += perUtbetaling;
      } else {
        kvartalSummer[0] += perUtbetaling;
        kvartalSummer[2] += perUtbetaling;
      }
    } else {
      // Årlig / uregelmessig: legg i betalingsmånedens kvartal
      const betalMnd = a.betaling_dato ? new Date(a.betaling_dato).getMonth()
        : a.ex_dato ? new Date(a.ex_dato).getMonth() : 0;
      kvartalSummer[Math.floor(betalMnd / 3)] += perUtbetaling;
    }
  });

  const maksKvartal = Math.max(...kvartalSummer);
  document.getElementById('pf-tidslinje').innerHTML = kvartaler.map((label, i) => {
    const v = kvartalSummer[i];
    const pct = maksKvartal > 0 ? (v / maksKvartal * 100).toFixed(1) : 0;
    return `
      <div class="flex items-center gap-3">
        <span class="text-xs text-gray-500 dark:text-gray-400 w-28 shrink-0">${label}</span>
        <div class="flex-1 h-5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
          <div class="h-full bg-brand-500 rounded-full transition-all" style="width:${pct}%"></div>
        </div>
        <span class="text-xs font-semibold w-24 text-right tabular-nums">${fmtKr(v)}</span>
      </div>`;
  }).join('');

  visCharts(alleBeholdning, totalAr);
}

// ── PORTEFØLJE-DIAGRAMMER ──────────────────────────────────────────────────
const SEKTOR_FARGE = {
  'Energi':            '#f97316',
  'Finans':            '#3b82f6',
  'Shipping':          '#1e40af',
  'Havbruk':           '#14b8a6',
  'Industri':          '#8b5cf6',
  'Materialer':        '#a16207',
  'Fornybar energi':   '#22c55e',
  'Telekommunikasjon': '#ec4899',
  'Forbruksvarer':     '#eab308',
  'Energitjenester':   '#ef4444',
  'Konsulent':         '#64748b',
};
const FARGE_FALLBACK = '#9ca3af';

function visCharts(beholdning, totalAr) {
  const wrapper = document.getElementById('pf-charts-wrapper');
  if (!beholdning.length || !totalAr) { wrapper.style.display = 'none'; return; }
  wrapper.style.display = 'grid';

  // ── 1. SEKTOR-DONUT ────────────────────────────────────────────────────
  const sektorMap = {};
  beholdning.forEach(a => {
    sektorMap[a.sektor] = (sektorMap[a.sektor] || 0) + a.forv_ar;
  });
  const sektorData = Object.entries(sektorMap)
    .filter(([, v]) => v > 0)
    .map(([s, v]) => ({ label: s, value: v, color: SEKTOR_FARGE[s] || FARGE_FALLBACK }))
    .sort((a, b) => b.value - a.value);

  const size = 180, cx = size / 2, cy = size / 2, or = 76, ir = 48;
  let angle = -Math.PI / 2, paths = '';
  sektorData.forEach(({ value, color }) => {
    const sweep = (value / totalAr) * 2 * Math.PI;
    const end = angle + sweep;
    const lg = sweep > Math.PI ? 1 : 0;
    const x1 = cx + or * Math.cos(angle),  y1 = cy + or * Math.sin(angle);
    const x2 = cx + or * Math.cos(end),    y2 = cy + or * Math.sin(end);
    const x3 = cx + ir * Math.cos(end),    y3 = cy + ir * Math.sin(end);
    const x4 = cx + ir * Math.cos(angle),  y4 = cy + ir * Math.sin(angle);
    paths += `<path d="M${x1},${y1} A${or},${or} 0 ${lg} 1 ${x2},${y2} L${x3},${y3} A${ir},${ir} 0 ${lg} 0 ${x4},${y4}Z" fill="${color}" stroke="white" stroke-width="1.5" class="dark:stroke-gray-900"/>`;
    angle = end;
  });

  const legend = sektorData.map(({ label, value, color }) => {
    const pct = (value / totalAr * 100).toFixed(1);
    return `<div class="flex items-center gap-2 text-xs">
      <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${color}"></span>
      <span class="text-gray-600 dark:text-gray-400 truncate flex-1">${label}</span>
      <span class="font-semibold tabular-nums">${pct}%</span>
    </div>`;
  }).join('');

  document.getElementById('pf-sektor-chart').innerHTML = `
    <div class="flex flex-col sm:flex-row items-center gap-4">
      <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" class="shrink-0">${paths}</svg>
      <div class="space-y-1.5 flex-1 min-w-0">${legend}</div>
    </div>`;

  // ── 2. TOPP BIDRAGSYTERE ───────────────────────────────────────────────
  const topp = [...beholdning].sort((a, b) => b.forv_ar - a.forv_ar).slice(0, 8);
  const maks = topp[0]?.forv_ar || 1;
  const fmtKr = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';

  document.getElementById('pf-topp-chart').innerHTML = topp.map(a => {
    const pct = (a.forv_ar / maks * 100).toFixed(1);
    const andel = (a.forv_ar / totalAr * 100).toFixed(1);
    const farge = SEKTOR_FARGE[a.sektor] || FARGE_FALLBACK;
    return `
      <div>
        <div class="flex items-center justify-between mb-1">
          <div class="flex items-center gap-1.5">
            <span class="font-mono text-xs font-bold text-brand-700 dark:text-brand-400">${a.ticker}</span>
            <span class="text-xs text-gray-400">${andel}%</span>
          </div>
          <span class="text-xs font-semibold tabular-nums">${fmtKr(a.forv_ar)}</span>
        </div>
        <div class="h-3 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
          <div class="h-full rounded-full" style="width:${pct}%;background:${farge}"></div>
        </div>
      </div>`;
  }).join('');

  // ── 3. FREKVENSFORDELING ───────────────────────────────────────────────
  const frekvensMap = {};
  beholdning.forEach(a => {
    frekvensMap[a.frekvens] = (frekvensMap[a.frekvens] || 0) + a.forv_ar;
  });
  const frekvensOrder = ['Månedlig','Kvartalsvis','Halvårlig','Årlig','Uregelmessig'];
  const frekvensFarge = {
    'Månedlig':      '#22c55e',
    'Kvartalsvis':   '#3b82f6',
    'Halvårlig':     '#8b5cf6',
    'Årlig':         '#f97316',
    'Uregelmessig':  '#9ca3af',
  };

  document.getElementById('pf-frekvens-chart').innerHTML = frekvensOrder
    .filter(f => frekvensMap[f])
    .map(f => {
      const v = frekvensMap[f];
      const pct = (v / totalAr * 100).toFixed(1);
      const antall = beholdning.filter(a => a.frekvens === f).length;
      const farge = frekvensFarge[f];
      return `
        <div class="flex-1 min-w-36 rounded-xl p-3 border border-gray-100 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
          <div class="flex items-center gap-2 mb-2">
            <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${farge}"></span>
            <span class="text-xs font-semibold">${f}</span>
          </div>
          <div class="text-lg font-bold tabular-nums">${pct}%</div>
          <div class="text-xs text-gray-400">${fmtKr(v)} / år · ${antall} aksje${antall !== 1 ? 'r' : ''}</div>
          <div class="mt-2 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div class="h-full rounded-full" style="width:${pct}%;background:${farge}"></div>
          </div>
        </div>`;
    }).join('');
}

function eksporterCSV() {
  const pf = hentPF();
  const { navn, malMnd, spareMaal } = hentProfil();
  const profilLinje = `#exday-profil,navn=${navn},sparemaal=${spareMaal},mal_mnd=${malMnd}`;
  const rader = [['Ticker','Selskap','Antall','Kurs','Utbytte/aksje','Forv. utbytte/år','Yield %','Ex-dato','Frekvens']];
  Object.entries(pf).forEach(([ticker, antall]) => {
    const a = alleAksjer.find(x => x.ticker === ticker);
    if (!a) return;
    rader.push([
      a.ticker, `"${a.navn}"`, antall,
      a.pris.toFixed(2), (a.utbytte_per_aksje||0).toFixed(2),
      (antall * (a.utbytte_per_aksje||0)).toFixed(2),
      a.utbytte_yield.toFixed(2),
      a.ex_dato || '', a.frekvens
    ]);
  });
  const csv = profilLinje + '\n' + rader.map(r => r.join(',')).join('\n');
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'portef\u00F8lje-exday.csv'; a.click();
  URL.revokeObjectURL(url);
}

function parseCSV(tekst) {
  // Fjern BOM
  if (tekst.charCodeAt(0) === 0xFEFF) tekst = tekst.slice(1);
  let linjer = tekst.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
  if (!linjer.length) return { gyldig: [], ukjent: [], profil: null };

  // Les profil-metadata fra første linje hvis den starter med #exday-profil
  let profil = null;
  if (linjer[0].startsWith('#exday-profil,')) {
    const deler = linjer[0].slice('#exday-profil,'.length).split(',');
    profil = {};
    deler.forEach(del => {
      const eq = del.indexOf('=');
      if (eq > -1) profil[del.slice(0, eq)] = del.slice(eq + 1);
    });
    linjer = linjer.slice(1);
  }

  let tickerIdx = 0, antallIdx = 2;

  // Header-deteksjon: finn kolonne-indekser dynamisk
  const forste = linjer[0] ? linjer[0].toLowerCase() : '';
  if (forste.includes('ticker') || forste.includes('antall') || forste.includes('selskap')) {
    const cols = linjer[0].split(',').map(c => c.trim().toLowerCase());
    const ti = cols.findIndex(c => c === 'ticker');
    const ai = cols.findIndex(c => c === 'antall');
    if (ti !== -1) tickerIdx = ti;
    if (ai !== -1) antallIdx = ai;
    linjer.shift(); // fjern header
  }

  const kjenteTickers = new Set(alleAksjer.map(a => a.ticker));
  const gyldig = [], ukjent = [];

  for (const linje of linjer) {
    const deler = linje.split(',');
    const ticker = (deler[tickerIdx] || '').replace(/"/g, '').trim().toUpperCase();
    const antall = parseInt((deler[antallIdx] || '').replace(/"/g, '').trim(), 10);
    if (!ticker) continue;
    if (kjenteTickers.has(ticker) && antall > 0) {
      gyldig.push({ ticker, antall });
    } else {
      ukjent.push(ticker);
    }
  }

  return { gyldig, ukjent, profil };
}

function visImportPreview(gyldig, ukjent) {
  window._importData = gyldig;
  const previewEl = document.getElementById('pf-importer-preview');
  const innholdEl = document.getElementById('pf-importer-innhold');

  let html = '';

  if (!gyldig.length && !ukjent.length) {
    html = '<p class="text-sm text-red-500">Filen ser tom ut eller har uventet format.</p>';
    document.getElementById('pf-importer-bekreft-legg-til').classList.add('hidden');
    document.getElementById('pf-importer-bekreft-erstatt').classList.add('hidden');
  } else if (!gyldig.length) {
    html = `<p class="text-sm text-red-500">Ingen kjente tickers funnet. Ukjente: ${ukjent.join(', ')}</p>`;
    document.getElementById('pf-importer-bekreft-legg-til').classList.add('hidden');
    document.getElementById('pf-importer-bekreft-erstatt').classList.add('hidden');
  } else {
    const preview = gyldig.slice(0, 6).map(({ ticker, antall }) => `${ticker} (${antall})`).join(', ');
    const mer = gyldig.length > 6 ? ` og ${gyldig.length - 6} til…` : '';
    html += `<p class="text-sm text-green-600 dark:text-green-400">✅ ${gyldig.length} aksje${gyldig.length !== 1 ? 'r' : ''} funnet: ${preview}${mer}</p>`;
    if (ukjent.length) {
      html += `<p class="text-sm text-yellow-600 dark:text-yellow-400 mt-1">⚠️ ${ukjent.length} ukjente tickers ignoreres: ${ukjent.join(', ')}</p>`;
    }
    document.getElementById('pf-importer-bekreft-legg-til').classList.remove('hidden');
    document.getElementById('pf-importer-bekreft-erstatt').classList.remove('hidden');
  }

  innholdEl.innerHTML = html;
  previewEl.classList.remove('hidden');
  previewEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function bekreftImport(data, erstatt) {
  if (!data || !data.length) return;
  const pf = erstatt ? {} : hentPF();
  data.forEach(({ ticker, antall }) => { pf[ticker] = antall; });
  lagrePF(pf);
  // Restore profile data when doing a full replacement import
  if (erstatt && window._importProfil) {
    const p = window._importProfil;
    lagreProfil(p.navn || '', parseFloat(p.mal_mnd) || 0, parseFloat(p.sparemaal) || 0);
    visGreeting();
  }
  document.getElementById('pf-importer-preview').classList.add('hidden');
  window._importData  = null;
  window._importProfil = null;
  visPortefolje();
}

// ── AKSJE-BRUKERDATA (notat + målpris) ────────────────────────────────────
function hentAlleAksjeData() {
  try { return JSON.parse(localStorage.getItem('aksje_data') || '{}'); } catch { return {}; }
}
function hentAksjeData(ticker) {
  return hentAlleAksjeData()[ticker] || { notat: '', malPris: 0 };
}
function lagreAksjeData(ticker, data) {
  const all = hentAlleAksjeData();
  all[ticker] = { ...all[ticker], ...data };
  localStorage.setItem('aksje_data', JSON.stringify(all));
}

// ── MODAL ─────────────────────────────────────────────────────────────────
function visModal(a) {
  const overlay = document.getElementById('modal-overlay');
  const body = document.getElementById('modal-body');
  const idag = new Date(); idag.setHours(0,0,0,0);
  const exDato = a.ex_dato ? new Date(a.ex_dato) : null;
  const dagerTilEx = exDato ? Math.ceil((exDato - idag) / (1000*60*60*24)) : null;

  body.innerHTML = `
    <div class="flex items-start justify-between mb-4">
      <div>
        <h2 class="text-2xl font-bold text-brand-700 dark:text-brand-400">${a.ticker}</h2>
        <p class="text-gray-600 dark:text-gray-400">${a.navn}</p>
        <p class="text-xs text-gray-400 mt-0.5">${a.sektor} · ${a.bors}</p>
      </div>
      <div class="flex items-center gap-1">
        ${stjerne(a.ticker, 'p-1 hover:scale-110')}
        <button id="modal-close" class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 p-1" aria-label="Lukk">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
    </div>

    ${a.beskrivelse ? `<p class="text-sm text-gray-600 dark:text-gray-400 mb-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">${a.beskrivelse}</p>` : ''}

    <div class="grid grid-cols-2 gap-3 mb-4">
      ${modalKort('Kurs', fmt(a.pris) + ' ' + a.valuta)}
      ${modalKort('Utbytteyield', `<span class="${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span>`)}
      ${modalKort('Utbytte/aksje (år)', fmt(a.utbytte_per_aksje) + ' ' + a.valuta)}
      ${modalKort('Siste utbytte', fmt(a.siste_utbytte) + ' ' + a.valuta)}
      ${modalKort('Payout Ratio', `<span class="${payoutKlasse(a.payout_ratio)}">${a.payout_ratio > 0 ? a.payout_ratio.toFixed(0)+'%' : '—'}</span>`)}
      ${modalKort('Utbyttevekst 5år', `<span class="${vekstKlasse(a.utbytte_vekst_5ar)}">${a.utbytte_vekst_5ar !== 0 ? (a.utbytte_vekst_5ar>0?'+':'')+a.utbytte_vekst_5ar.toFixed(1)+'%' : '—'}</span>`)}
      ${modalKort('Snitt yield 5år', a.snitt_yield_5ar > 0 ? `<span class="${yieldKlasse(a.snitt_yield_5ar)}">${a.snitt_yield_5ar.toFixed(1)}%</span>` : '—')}
      ${modalKort('P/E', a.pe_ratio > 0 ? a.pe_ratio.toFixed(1) : '—')}
      ${modalKort('P/B', a.pb_ratio > 0 ? a.pb_ratio.toFixed(1) : '—')}
      ${modalKort('Markedsverdi', a.markedsverdi_mrd > 0 ? a.markedsverdi_mrd.toFixed(1) + ' mrd' : '—')}
      ${modalKort('År m/utbytte', a.ar_med_utbytte > 0 ? a.ar_med_utbytte + ' år' : '—')}
    </div>

    <div class="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <div class="bg-orange-50 dark:bg-orange-950/30 px-4 py-3">
        <h3 class="font-semibold text-sm text-orange-800 dark:text-orange-300">Utbyttedatoer</h3>
      </div>
      <div class="p-4 space-y-2 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-500">Ex-dato</span>
          <span class="font-medium ${dagerTilEx !== null && dagerTilEx >= 0 ? 'text-orange-600 dark:text-orange-400' : ''}">
            ${a.ex_dato ? formaterDato(a.ex_dato) : '—'}
            ${dagerTilEx !== null && dagerTilEx >= 0 ? ` <span class="text-xs">(om ${dagerTilEx} dager)</span>` : ''}
          </span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">Betalingsdato</span>
          <span class="font-medium">${a.betaling_dato ? formaterDato(a.betaling_dato) : '—'}</span>
        </div>
        <div class="flex justify-between">
          <span class="text-gray-500">Frekvens</span>
          <span class="frekvens-badge">${a.frekvens}</span>
        </div>
      </div>
    </div>

    <div class="mt-4">
      ${rangebar(a.pris, a['52u_lav'], a['52u_hoy'], true)}
    </div>

    ${historiskChart(a)}
    ${scoreForklaring(a)}
    ${notatSeksjon(a)}
  `;

  overlay.classList.remove('hidden');
  overlay.classList.add('flex');

  // Sett ?aksje= i URL slik at siden kan deles
  const _url = new URL(location.href);
  _url.searchParams.set('aksje', a.ticker);
  history.replaceState(null, '', _url.toString());

  // Notat + målpris: live-lagring
  const _malIn  = document.getElementById('modal-malpris');
  const _notIn  = document.getElementById('modal-notat');
  if (_malIn) {
    _malIn.addEventListener('change', () => {
      lagreAksjeData(a.ticker, { malPris: parseFloat(_malIn.value) || 0 });
      visOversikt();
      visHvaSkjerIDag();
    });
  }
  if (_notIn) {
    _notIn.addEventListener('input', () => {
      lagreAksjeData(a.ticker, { notat: _notIn.value });
    });
  }
}

function historiskChart(a) {
  const hist = a.historiske_utbytter;
  if (!hist || hist.length === 0) return '';

  const maxDiv = Math.max(...hist.map(h => h.utbytte));

  const bars = hist.map(h => {
    const heightPct = maxDiv > 0 ? (h.utbytte / maxDiv * 100).toFixed(1) : 0;
    const barColor = h.yield >= 7 ? 'bg-green-500' : h.yield >= 4 ? 'bg-blue-500' : 'bg-gray-400';
    return `
      <div class="flex flex-col items-center gap-0.5 flex-1 min-w-0">
        <span class="text-xs text-gray-500 dark:text-gray-400">${h.yield.toFixed(1)}%</span>
        <div class="w-full flex items-end rounded-t overflow-hidden" style="height:52px">
          <div class="w-full ${barColor} rounded-t transition-all" style="height:${heightPct}%"></div>
        </div>
        <span class="text-xs font-medium text-gray-700 dark:text-gray-300 tabular-nums">${h.utbytte.toFixed(2)}</span>
        <span class="text-xs text-gray-400">${h.ar}</span>
      </div>`;
  }).join('');

  const snittHtml = a.snitt_yield_5ar > 0
    ? `<span class="text-xs text-gray-500 dark:text-gray-400">Snitt yield: <span class="font-semibold text-gray-700 dark:text-gray-300">${a.snitt_yield_5ar.toFixed(1)}%</span></span>`
    : '';

  return `
    <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
      <div class="flex justify-between items-center mb-3">
        <span class="text-sm font-semibold text-gray-800 dark:text-gray-200">Historiske utbytter</span>
        ${snittHtml}
      </div>
      <div class="flex items-end gap-1.5">${bars}</div>
    </div>`;
}

function lukkModal() {
  const overlay = document.getElementById('modal-overlay');
  overlay.classList.add('hidden');
  overlay.classList.remove('flex');
  // Fjern ?aksje= fra URL uten å laste siden på nytt
  const url = new URL(location.href);
  if (url.searchParams.has('aksje')) {
    url.searchParams.delete('aksje');
    history.replaceState(null, '', url.pathname + (url.search !== '?' ? url.search : ''));
  }
}

// ── MODAL INIT (én gang) ───────────────────────────────────────────────────
function initModal() {
  const overlay = document.getElementById('modal-overlay');
  // Klikk på overlay-bakgrunn lukker modal
  overlay.addEventListener('click', e => { if (e.target === overlay) lukkModal(); });
  // Klikk på lukk-knapp via event delegation
  overlay.addEventListener('click', e => { if (e.target.closest('#modal-close')) lukkModal(); });
  // Favoritt-toggle i modal
  overlay.addEventListener('click', e => {
    const btn = e.target.closest('.fav-btn');
    if (!btn) return;
    toggleFav(btn.dataset.ticker);
    oppdaterFavBtn();
    // Re-render stjernen inne i modal uten å lukke
    visModal(alleAksjer.find(x => x.ticker === btn.dataset.ticker));
  });
  // ESC lukker modal
  document.addEventListener('keydown', e => { if (e.key === 'Escape') lukkModal(); });
}

function modalKort(label, value) {
  return `<div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
    <p class="text-xs text-gray-400 mb-1">${label}</p>
    <p class="font-semibold">${value}</p>
  </div>`;
}

// ── HJELPEFUNKSJONER ───────────────────────────────────────────────────────
function fmt(v) {
  if (v == null || v === 0) return '—';
  return Number(v).toLocaleString('nb-NO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formaterDato(str) {
  if (!str) return '—';
  const d = new Date(str);
  return d.toLocaleDateString('nb-NO', { day: 'numeric', month: 'short', year: 'numeric' });
}

function yieldKlasse(y) {
  if (y >= 10) return 'yield-hoy';
  if (y >= 6)  return 'yield-god';
  if (y >= 3)  return 'yield-middels';
  return 'yield-lav';
}

// ── UTBYTTE-SCORE (1–10) ───────────────────────────────────────────────────
// Poengsum for utbyttekvalitet basert på 5 kriterier (maks 10 poeng):
//   1. Yield-nivå          0–3 p
//   2. Payout-bærekraft    0–2 p
//   3. Utbyttevekst 5 år   0–2 p
//   4. År med utbytte      0–2 p
//   5. Yield-stabilitet    0–1 p  (snitt yield 5å vs. dagens yield)

function beregnScore(a) {
  let p = 0;

  // 1. Yield-nivå (0–3)
  const y = a.utbytte_yield || 0;
  if      (y >= 10) p += 3;
  else if (y >= 6)  p += 2;
  else if (y >= 3)  p += 1;

  // 2. Payout-bærekraft (0–2): lavt payout = bærekraftig
  const po = a.payout_ratio || 0;
  if      (po > 0 && po <= 50)  p += 2;
  else if (po > 0 && po <= 75)  p += 1;
  // payout > 75% eller 0 (ukjent) = 0 poeng

  // 3. Utbyttevekst 5 år CAGR (0–2)
  const vekst = a.utbytte_vekst_5ar || 0;
  if      (vekst > 10) p += 2;
  else if (vekst > 0)  p += 1;

  // 4. År med utbytte = konsistens (0–2)
  const ar = a.ar_med_utbytte || 0;
  if      (ar >= 10) p += 2;
  else if (ar >= 5)  p += 1;

  // 5. Yield-stabilitet: snitt yield 5å nær dagens yield (0–1)
  const snitt = a.snitt_yield_5ar || 0;
  if (snitt > 0 && y > 0) {
    const avvik = Math.abs(y - snitt) / snitt;
    if (avvik <= 0.3) p += 1;  // innenfor 30% = stabilt
  }

  return Math.min(10, Math.max(1, p));
}

function scoreBadge(score) {
  let cls;
  if      (score >= 8) cls = 'score-høy';
  else if (score >= 5) cls = 'score-middels';
  else                 cls = 'score-lav';
  return `<span class="score-badge ${cls}">${score}<span class="score-av10">/10</span></span>`;
}

function scoreForklaring(a) {
  const y = a.utbytte_yield || 0;
  const po = a.payout_ratio || 0;
  const vekst = a.utbytte_vekst_5ar || 0;
  const ar = a.ar_med_utbytte || 0;
  const snitt = a.snitt_yield_5ar || 0;

  const p1 = y >= 10 ? 3 : y >= 6 ? 2 : y >= 3 ? 1 : 0;
  const p2 = (po > 0 && po <= 50) ? 2 : (po > 0 && po <= 75) ? 1 : 0;
  const p3 = vekst > 10 ? 2 : vekst > 0 ? 1 : 0;
  const p4 = ar >= 10 ? 2 : ar >= 5 ? 1 : 0;
  const p5 = (snitt > 0 && y > 0 && Math.abs(y - snitt) / snitt <= 0.3) ? 1 : 0;

  const rad = (label, poeng, maks, tekst) =>
    `<div class="flex justify-between items-center py-1 border-b border-gray-100 dark:border-gray-800 last:border-0">
      <span class="text-xs text-gray-500 dark:text-gray-400">${label}</span>
      <div class="flex items-center gap-2">
        <span class="text-xs text-gray-400">${tekst}</span>
        <span class="text-xs font-semibold ${poeng > 0 ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}">${poeng}/${maks}</span>
      </div>
    </div>`;

  return `
    <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
      <div class="flex justify-between items-center mb-2">
        <span class="text-sm font-semibold">Utbytte-score</span>
        ${scoreBadge(beregnScore(a))}
      </div>
      <div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 space-y-0">
        ${rad('Yield-nivå', p1, 3, y > 0 ? y.toFixed(1)+'%' : '—')}
        ${rad('Payout-bærekraft', p2, 2, po > 0 ? po.toFixed(0)+'%' : '—')}
        ${rad('Vekst 5 år', p3, 2, vekst !== 0 ? (vekst>0?'+':'')+vekst.toFixed(1)+'%' : '—')}
        ${rad('År med utbytte', p4, 2, ar > 0 ? ar+' år' : '—')}
        ${rad('Yield-stabilitet', p5, 1, snitt > 0 ? 'snitt '+snitt.toFixed(1)+'%' : '—')}
      </div>
    </div>`;
}

function visScoreInfoModal() {
  const overlay = document.getElementById('modal-overlay');
  const body    = document.getElementById('modal-body');
  body.innerHTML = `
    <div class="flex items-start justify-between mb-4">
      <h2 class="text-lg font-bold">Utbytte-score — slik beregnes den</h2>
      <button id="modal-close" class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 p-1">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>
    <p class="text-sm text-gray-600 dark:text-gray-400 mb-4">Scoren (1–10) måler utbyttekvalitet basert på fem kriterier. Høy score betyr ikke nødvendigvis lav risiko — gjør alltid egen analyse.</p>
    <div class="space-y-3">
      ${[
        ['Yield-nivå',       '0–3 p', '≥10%→3p · ≥6%→2p · ≥3%→1p'],
        ['Payout-bærekraft', '0–2 p', '≤50%→2p · ≤75%→1p · >75%→0p'],
        ['Utbyttevekst 5år', '0–2 p', 'CAGR >10%→2p · >0%→1p'],
        ['År med utbytte',   '0–2 p', '≥10 år→2p · ≥5 år→1p'],
        ['Yield-stabilitet', '0–1 p', 'Snitt yield 5å avviker ≤30% fra dagens yield'],
      ].map(([k, p, t]) => `
        <div class="rounded-lg bg-gray-50 dark:bg-gray-800 p-3 flex items-start justify-between gap-4">
          <div>
            <p class="text-sm font-semibold">${k}</p>
            <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">${t}</p>
          </div>
          <span class="text-xs font-bold text-brand-600 dark:text-brand-400 shrink-0">${p}</span>
        </div>`).join('')}
    </div>`;
  overlay.classList.remove('hidden');
  overlay.classList.add('flex');
}

function notatSeksjon(a) {
  const d = hentAksjeData(a.ticker);
  const underMal = d.malPris > 0 && a.pris > 0 && a.pris <= d.malPris;
  return `
    <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
      <h3 class="text-sm font-semibold mb-3">Mine notater</h3>
      <div class="space-y-3">
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Målpris (${a.valuta})</label>
          <div class="flex items-center gap-3">
            <input id="modal-malpris" type="number" min="0" step="1" placeholder="—"
              value="${d.malPris || ''}"
              class="filter-input w-28 text-sm text-right" />
            <span class="text-xs text-gray-400">Nå: ${a.pris ? a.pris.toFixed(0) : '—'} ${a.valuta}${underMal ? ' · <span class="text-blue-500 dark:text-blue-400 font-semibold">Under mål ✓</span>' : ''}</span>
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Notat</label>
          <textarea id="modal-notat" rows="2" placeholder="Skriv en kort notis…"
            class="filter-input w-full text-sm resize-none">${d.notat || ''}</textarea>
        </div>
      </div>
    </div>`;
}

function payoutKlasse(p) {
  if (p <= 0)   return 'text-gray-400';
  if (p <= 50)  return 'text-gray-700 dark:text-gray-300 font-medium';
  if (p <= 75)  return 'text-amber-700 dark:text-amber-400 font-medium';
  return 'text-red-600 dark:text-red-400 font-medium';
}

function vekstKlasse(v) {
  if (v > 10) return 'text-emerald-700 dark:text-emerald-400 font-medium';
  if (v > 0)  return 'text-gray-600 dark:text-gray-400';
  if (v < 0)  return 'text-red-500 dark:text-red-400';
  return 'text-gray-400';
}

function rangebar(pris, lav, hoy, stor = false) {
  if (!lav || !hoy || lav >= hoy) return '';
  const pct = Math.min(100, Math.max(0, ((pris - lav) / (hoy - lav)) * 100));

  // Color reflects position: red = near 52w low, blue = mid, green = near 52w high
  const barColor = pct >= 70 ? 'bg-green-500' : pct >= 35 ? 'bg-blue-500' : 'bg-red-400';
  const dotColor = pct >= 70
    ? 'bg-green-700 dark:bg-green-400'
    : pct >= 35
    ? 'bg-blue-700 dark:bg-blue-400'
    : 'bg-red-600 dark:bg-red-400';

  if (stor) {
    return `
    <div class="py-1">
      <div class="flex justify-between items-center mb-2">
        <span class="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">52-ukers kursrange</span>
        <span class="text-xs text-gray-500 dark:text-gray-400">${pct.toFixed(0)}% fra lavpunkt</span>
      </div>
      <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-3 relative">
        <div class="${barColor} rounded-full h-3 transition-all" style="width:${pct}%"></div>
        <div class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full ${dotColor} border-2 border-white dark:border-gray-900 shadow" style="left:calc(${pct}% - 6px)"></div>
      </div>
      <div class="flex justify-between text-xs text-gray-500 dark:text-gray-400 mt-1.5">
        <span>Lav <span class="font-medium text-gray-700 dark:text-gray-300">${fmt(lav)}</span></span>
        <span>Nå <span class="font-semibold text-gray-900 dark:text-gray-100">${fmt(pris)}</span></span>
        <span>Høy <span class="font-medium text-gray-700 dark:text-gray-300">${fmt(hoy)}</span></span>
      </div>
    </div>`;
  }

  // Small version for table
  return `
  <div>
    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 relative">
      <div class="${barColor} rounded-full h-2" style="width:${pct}%"></div>
      <div class="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full ${dotColor} border-2 border-white dark:border-gray-900 shadow" style="left:calc(${pct}% - 5px)"></div>
    </div>
    <div class="flex justify-between text-xs text-gray-400 mt-0.5"><span>${fmt(lav)}</span><span>${pct.toFixed(0)}%</span><span>${fmt(hoy)}</span></div>
  </div>`;
}

// ── PWA / VARSLER ─────────────────────────────────────────────────────────────

function hentNotifPrefs() {
  try {
    // Første gang: arv favoritter som standard så listen ikke er tom
    if (localStorage.getItem('notif_aksjer') === null) {
      const fav = hentFav();
      if (fav.size > 0) return fav;
    }
    return new Set(JSON.parse(localStorage.getItem('notif_aksjer') || '[]'));
  } catch { return new Set(); }
}

function lagreNotifPrefs(prefs) {
  localStorage.setItem('notif_aksjer', JSON.stringify([...prefs]));
  if ('caches' in window) {
    caches.open('notif-prefs-v1').then(cache =>
      cache.put('/notif-prefs', new Response(JSON.stringify([...prefs]), {
        headers: { 'Content-Type': 'application/json' },
      }))
    );
  }
}

// ── UTBYTTEKALKULATOR ─────────────────────────────────────────────────────
function initKalkulator() {
  document.getElementById('kal-beregn').addEventListener('click', beregnKalkulator);
  // Beregn automatisk ved endring
  ['kal-startbelop','kal-yield','kal-ar','kal-vekst','kal-sparing','kal-reinvester']
    .forEach(id => document.getElementById(id).addEventListener('input', beregnKalkulator));
  beregnKalkulator();
}

function beregnKalkulator() {
  const startbelop  = Math.max(0, parseFloat(document.getElementById('kal-startbelop').value) || 0);
  const yieldPct    = Math.max(0, Math.min(50, parseFloat(document.getElementById('kal-yield').value) || 0));
  const antallAr    = Math.max(1, Math.min(40, parseInt(document.getElementById('kal-ar').value) || 1));
  const vekstPct    = Math.max(0, Math.min(30, parseFloat(document.getElementById('kal-vekst').value) || 0));
  const sparingMnd  = Math.max(0, parseFloat(document.getElementById('kal-sparing').value) || 0);
  const reinvester  = document.getElementById('kal-reinvester').checked;

  if (startbelop <= 0 && sparingMnd <= 0) return;

  const fmtKr = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';
  const yieldFaktor = yieldPct / 100;
  const vekstFaktor = vekstPct / 100;
  const sparingAr   = sparingMnd * 12;

  let verdi = startbelop;
  let totUtbytte = 0;
  let totInnbetalt = startbelop;
  const rader = [];

  for (let ar = 1; ar <= antallAr; ar++) {
    // Månedlig sparing legges til gjennom året (enkel approx: halvparten av årssparingen er investert i snitt)
    const nySparing = sparingAr;
    const baseForUtbytte = verdi + nySparing * 0.5;
    const utbytteIAr = baseForUtbytte * yieldFaktor;

    verdi += nySparing;
    if (reinvester) {
      verdi += utbytteIAr;
    }
    // Kursvekst på hele porteføljen
    verdi = verdi * (1 + vekstFaktor);

    totUtbytte += utbytteIAr;
    totInnbetalt += nySparing;

    rader.push({ ar, verdi, utbytteIAr, totUtbytte });
  }

  // Oppdater sammendragskort
  document.getElementById('kal-res-ar').textContent  = antallAr;
  document.getElementById('kal-res-ar2').textContent = antallAr;
  document.getElementById('kal-res-verdi').textContent    = fmtKr(verdi);
  document.getElementById('kal-res-utbytte').textContent  = fmtKr(totUtbytte);
  document.getElementById('kal-res-innbetalt').textContent = fmtKr(totInnbetalt);
  document.getElementById('kal-res-mnd').textContent = fmtKr(rader[rader.length - 1].utbytteIAr / 12);

  // Tabell
  document.getElementById('kal-tabell').innerHTML = rader.map(r => `
    <tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50">
      <td class="px-4 py-2 text-gray-500 dark:text-gray-400">${r.ar}</td>
      <td class="px-4 py-2 text-right font-medium">${fmtKr(r.verdi)}</td>
      <td class="px-4 py-2 text-right text-green-600 dark:text-green-400">${fmtKr(r.utbytteIAr)}</td>
      <td class="px-4 py-2 text-right text-gray-500 dark:text-gray-400">${fmtKr(r.totUtbytte)}</td>
    </tr>`).join('');

  document.getElementById('kal-resultat').classList.remove('hidden');
}

// ── INNTEKTSTELLER ────────────────────────────────────────────────────────
function beregnYtdInntekt(alleBeholdning) {
  const idag = new Date();
  const currentYear = idag.getFullYear();
  const currentMonth = idag.getMonth(); // 0=jan
  const frekvensPerAr = { 'Månedlig': 12, 'Kvartalsvis': 4, 'Halvårlig': 2, 'Årlig': 1, 'Uregelmessig': 1 };
  let total = 0;

  alleBeholdning.forEach(a => {
    // 1. betaling_dato som allerede har passert i år
    if (a.betaling_dato) {
      const bd = new Date(a.betaling_dato);
      if (bd.getFullYear() === currentYear && bd < idag) {
        total += a.antall * (a.siste_utbytte || 0);
        return;
      }
    }
    // 2. historiske_utbytter for inneværende år
    const histIAr = (a.historiske_utbytter || []).find(h => h.ar === currentYear);
    if (histIAr) {
      total += a.antall * histIAr.utbytte;
      return;
    }
    // 3. Frekvensbasert estimat — andel av året som er gått
    const perAr = frekvensPerAr[a.frekvens] || 1;
    const estimertBetalinger = Math.floor((currentMonth / 12) * perAr);
    if (estimertBetalinger > 0) {
      total += a.antall * (a.utbytte_per_aksje || 0) * (estimertBetalinger / perAr);
    }
  });
  return total;
}

// ── OPPORTUNITY FEED ──────────────────────────────────────────────────────
function visOpportunityFeed() {
  const el = document.getElementById('opportunity-feed');
  if (!el || !alleAksjer.length) return;
  const idag = new Date(); idag.setHours(0,0,0,0);
  const om10 = new Date(idag); om10.setDate(om10.getDate() + 10);

  const muligheter = alleAksjer
    .filter(a => a.ex_dato && a.utbytte_yield >= 5)
    .filter(a => { const d = new Date(a.ex_dato); return d >= idag && d <= om10; })
    .sort((a, b) => new Date(a.ex_dato) - new Date(b.ex_dato));

  if (!muligheter.length) { el.classList.add('hidden'); return; }

  el.classList.remove('hidden');
  el.innerHTML = `
    <div class="rounded-xl border border-amber-200 dark:border-amber-800/60 bg-amber-50 dark:bg-amber-950/20 p-4">
      <p class="text-xs font-semibold uppercase tracking-widest text-amber-700 dark:text-amber-400 mb-3">Verdt å se på nå</p>
      <div class="flex flex-wrap gap-2">
        ${muligheter.map(a => {
          const dager = Math.ceil((new Date(a.ex_dato) - idag) / 86400000);
          return `<div class="opportunity-kort" data-ticker="${a.ticker}">
            <span class="font-mono font-bold text-sm">${a.ticker}</span>
            <span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(1)}%</span>
            <span class="text-xs text-gray-400">ex ${dager === 0 ? 'i dag' : `om ${dager}d`}</span>
          </div>`;
        }).join('')}
      </div>
    </div>`;

  el.onclick = e => {
    const kort = e.target.closest('[data-ticker]');
    if (kort) visModal(alleAksjer.find(a => a.ticker === kort.dataset.ticker));
  };
}

// ── QR-KODE SYNKRONISERING ────────────────────────────────────────────────
function sjekkQRParam() {
  const params = new URLSearchParams(location.search);
  const raw = params.get('pf');
  if (!raw) return;
  history.replaceState(null, '', location.pathname);
  try {
    const payload = JSON.parse(decodeURIComponent(escape(atob(raw))));
    if (!payload.ts || !payload.pf) return;
    if (Date.now() - payload.ts > 5 * 60 * 1000) {
      alert('QR-koden er utløpt (eldre enn 5 minutter). Generer en ny fra avsender-enheten.');
      return;
    }
    window._pendingQRImport = payload.pf;
  } catch { /* ugyldig data, ignorer */ }
}

function visQRModal() {
  const pf = hentPF();
  if (!Object.keys(pf).length) return;

  if (typeof QRCode === 'undefined') {
    alert('QR-biblioteket er ikke tilgjengelig. Sjekk internettforbindelsen og prøv igjen.');
    return;
  }

  const payload = { ts: Date.now(), pf };
  const encoded = btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
  const url = `${location.origin}${location.pathname}?pf=${encoded}`;

  const wrapper = document.getElementById('qr-canvas-wrapper');
  wrapper.innerHTML = '';
  new QRCode(wrapper, {
    text: url, width: 200, height: 200,
    colorDark: document.documentElement.classList.contains('dark') ? '#f3f4f6' : '#111827',
    colorLight: document.documentElement.classList.contains('dark') ? '#111827' : '#ffffff',
    correctLevel: QRCode.CorrectLevel.M
  });

  const modal = document.getElementById('qr-modal');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  document.getElementById('qr-utlopt').classList.add('hidden');

  const expiresAt = payload.ts + 5 * 60 * 1000;
  clearInterval(modal._timer);
  modal._timer = setInterval(() => {
    const remaining = expiresAt - Date.now();
    if (remaining <= 0) {
      clearInterval(modal._timer);
      document.getElementById('qr-countdown').textContent = '0:00';
      document.getElementById('qr-utlopt').classList.remove('hidden');
      return;
    }
    const m = Math.floor(remaining / 60000);
    const s = Math.floor((remaining % 60000) / 1000);
    document.getElementById('qr-countdown').textContent = `${m}:${s.toString().padStart(2, '0')}`;
  }, 1000);
}

async function initVarsler() {
  if (!('serviceWorker' in navigator)) return;
  try {
    await navigator.serviceWorker.register('/sw.js');
  } catch (e) {
    console.warn('Service Worker registrering feilet:', e);
  }
}

async function registrerPeriodicSync() {
  if (!('serviceWorker' in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.ready;
    if ('periodicSync' in reg) {
      const status = await navigator.permissions.query({ name: 'periodic-background-sync' });
      if (status.state === 'granted') {
        await reg.periodicSync.register('sjekk-ex-datoer', { minInterval: 24 * 60 * 60 * 1000 });
      }
    }
  } catch (e) {
    console.warn('Periodic sync ikke tilgjengelig:', e);
  }
}

// Fallback: sjekk direkte i nettleseren når appen åpnes (fungerer uten periodic sync)
async function sjekkExDatoerDirekte() {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  const prefs = hentNotifPrefs();
  if (!prefs.size) return;

  const idag = new Date(); idag.setHours(0, 0, 0, 0);
  const PREFIKS = 'notif_vist_';

  for (const a of alleAksjer) {
    if (!prefs.has(a.ticker) || !a.ex_dato) continue;
    const exDato = new Date(a.ex_dato); exDato.setHours(0, 0, 0, 0);
    const dager = Math.round((exDato - idag) / (1000 * 60 * 60 * 24));
    if (dager < 0 || dager > 7) continue;

    const key = PREFIKS + a.ticker + '_' + a.ex_dato;
    if (localStorage.getItem(key)) continue;

    const tittel = dager === 0
      ? `${a.ticker} ex-dato er i dag!`
      : `${a.ticker} ex-dato om ${dager} dag${dager === 1 ? '' : 'er'}`;
    const kropp = dager === 0
      ? `${a.navn} – du må eie aksjen i dag for å motta utbytte`
      : `${a.navn} – ex-dato ${new Date(a.ex_dato).toLocaleDateString('nb-NO', { day: 'numeric', month: 'long' })}`;

    new Notification(tittel, { body: kropp, icon: '/assets/icon.svg', tag: key });
    localStorage.setItem(key, '1');
  }
}

function visVarslerTab() {
  const container = document.getElementById('varsler-innhold');
  const harNotif = 'Notification' in window && 'serviceWorker' in navigator;
  const tillatelse = harNotif ? Notification.permission : 'unsupported';
  const prefs = hentNotifPrefs();

  // Status-kort
  let statusHtml;
  if (!harNotif) {
    statusHtml = `
      <div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50 p-4">
        <p class="font-semibold text-sm mb-1">Varsler støttes ikke</p>
        <p class="text-sm text-gray-500">Nettleseren din støtter ikke push-varsler. Prøv Chrome, Edge eller Safari på iOS 16.4+.</p>
      </div>`;
  } else if (tillatelse === 'denied') {
    statusHtml = `
      <div class="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4">
        <p class="font-semibold text-sm text-red-800 dark:text-red-300 mb-1">Varsler er blokkert</p>
        <p class="text-sm text-red-700 dark:text-red-400">Gå til nettleserinnstillinger → Nettstedsinnstillinger → Varslinger, og tillat exday.no.</p>
      </div>`;
  } else if (tillatelse === 'granted') {
    statusHtml = `
      <div class="rounded-xl border border-green-200 dark:border-green-800 bg-green-50 dark:bg-green-900/20 p-4 flex items-start gap-3">
        <svg class="w-5 h-5 text-green-600 dark:text-green-400 shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>
        <div>
          <p class="font-semibold text-sm text-green-800 dark:text-green-300">Varsler er aktivert</p>
          <p class="text-sm text-green-700 dark:text-green-400 mt-0.5">Du får beskjed når valgte aksjer nærmer seg ex-dato (varsler opp til 7 dager i forveien).</p>
        </div>
      </div>`;
  } else {
    statusHtml = `
      <div class="rounded-xl border border-brand-200 dark:border-brand-800 bg-brand-50 dark:bg-brand-900/20 p-4 flex items-center justify-between gap-4">
        <div>
          <p class="font-semibold text-sm text-brand-900 dark:text-brand-200">Aktiver ex-dato-varsler</p>
          <p class="text-sm text-brand-700 dark:text-brand-400 mt-0.5">Få varsler når aksjer du følger nærmer seg ex-dato.</p>
        </div>
        <button id="aktiver-varsler-btn" class="shrink-0 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white text-sm font-medium rounded-lg transition-colors">
          Aktiver
        </button>
      </div>`;
  }

  // Installeringsinfo (kun om ikke allerede installert som PWA)
  const erPWA = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;
  const installHtml = erPWA ? '' : `
    <div class="rounded-xl border border-gray-200 dark:border-gray-800 p-4 flex items-start gap-3">
      <svg class="w-5 h-5 text-gray-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"/></svg>
      <div>
        <p class="font-semibold text-sm">Installer som app</p>
        <p class="text-sm text-gray-500 mt-0.5">I Chrome/Edge: trykk menyknappen og velg "Installer app". På iOS Safari: trykk Del-knappen og "Legg til på hjem-skjerm".</p>
      </div>
    </div>`;

  // Aksjeliste
  const listeHtml = alleAksjer.length === 0
    ? `<div class="text-sm text-gray-400 py-4 text-center">Laster aksjedata…</div>`
    : `<div class="flex items-center justify-between mb-3">
        <h3 class="font-semibold text-sm">Aksjer å varsle for</h3>
        <div class="flex gap-3">
          <button id="varsler-velg-alle" class="text-xs text-brand-600 dark:text-brand-400 hover:underline">Velg alle</button>
          <button id="varsler-fjern-alle" class="text-xs text-gray-400 hover:underline">Fjern alle</button>
        </div>
      </div>
      <div class="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden divide-y divide-gray-100 dark:divide-gray-800">
        ${[...alleAksjer].sort((a, b) => a.ticker.localeCompare(b.ticker, 'nb')).map(a => {
          const aktiv = prefs.has(a.ticker);
          const exInfo = a.ex_dato ? formaterDato(a.ex_dato) : '—';
          return `<label class="flex items-center gap-3 px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer transition-colors">
            <input type="checkbox" class="notif-toggle w-4 h-4 rounded cursor-pointer accent-brand-600"
              data-ticker="${a.ticker}" ${aktiv ? 'checked' : ''} />
            <div class="flex-1 min-w-0">
              <span class="font-mono font-bold text-sm text-brand-700 dark:text-brand-400">${a.ticker}</span>
              <span class="text-sm text-gray-600 dark:text-gray-400 ml-2 truncate">${a.navn}</span>
            </div>
            <span class="text-xs text-gray-400 shrink-0">Ex: ${exInfo}</span>
          </label>`;
        }).join('')}
      </div>`;

  container.innerHTML = statusHtml + installHtml + `<div>${listeHtml}</div>`;

  // Bind events
  document.getElementById('aktiver-varsler-btn')?.addEventListener('click', async () => {
    const perm = await Notification.requestPermission();
    if (perm === 'granted') {
      await registrerPeriodicSync();
      visVarslerTab();
    }
  });

  container.addEventListener('change', e => {
    const cb = e.target.closest('.notif-toggle');
    if (!cb) return;
    const p = hentNotifPrefs();
    if (cb.checked) p.add(cb.dataset.ticker); else p.delete(cb.dataset.ticker);
    lagreNotifPrefs(p);
  });

  document.getElementById('varsler-velg-alle')?.addEventListener('click', () => {
    const p = new Set(alleAksjer.map(a => a.ticker));
    lagreNotifPrefs(p);
    container.querySelectorAll('.notif-toggle').forEach(cb => { cb.checked = true; });
  });

  document.getElementById('varsler-fjern-alle')?.addEventListener('click', () => {
    lagreNotifPrefs(new Set());
    container.querySelectorAll('.notif-toggle').forEach(cb => { cb.checked = false; });
  });
}
