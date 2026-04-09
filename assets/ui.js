'use strict';

// ── KALENDER-BADGE KONFIGURASJONER ─────────────────────────────────────────
const KAL_TYPER = {
  ex:      { label: 'Ex-dag',    bg: 'bg-orange-100 dark:bg-orange-900/40', text: 'text-orange-700 dark:text-orange-300', dag: 'text-orange-600 dark:text-orange-400' },
  utbytte: { label: 'Utbytte',   bg: 'bg-green-100 dark:bg-green-900/40',  text: 'text-green-700 dark:text-green-300',   dag: 'text-green-600 dark:text-green-400'   },
  rapport: { label: 'Rapport',   bg: 'bg-blue-100 dark:bg-blue-900/40',    text: 'text-blue-700 dark:text-blue-300',     dag: 'text-blue-600 dark:text-blue-400'     },
};


const SEKTOR_FARGE = {
  'Energi':                  '#64748b',
  'Finans':                  '#2563eb',
  'Shipping':                '#3b82f6',
  'Havbruk':                 '#14b8a6',
  'Industri':                '#6366f1',
  'Materialer':              '#0891b2',
  'Fornybar energi':         '#0d9488',
  'Telekommunikasjon':       '#818cf8',
  'Forbruksvarer':           '#94a3b8',
  'Energitjenester':         '#475569',
  'Konsulent':               '#334155',
  'Informasjonsteknologi':   '#1d4ed8',
  'Helsevern':               '#2dd4bf',
  'Kommunikasjonstjenester': '#4f46e5',
};
const FARGE_FALLBACK = '#94a3b8';
// Sekvensiell palett for individuelle aksjer i donut/bar-charts
const CHART_FARGER = [
  '#2563eb',
  '#14b8a6',
  '#6366f1',
  '#0891b2',
  '#3b82f6',
  '#0d9488',
  '#4f46e5',
  '#60a5fa',
];


function visVelkomstModal() {
  if (localStorage.getItem('velkommen_vist')) return;
  const modal = document.getElementById('velkommen-modal');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  document.getElementById('velk-navn-input').focus();

  function lukkOgMerk() {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    localStorage.setItem('velkommen_vist', '1');
  }

  function lagreOgLukk() {
    const navn = (document.getElementById('velk-navn-input').value || '').trim();
    if (navn) lagreProfil(navn, 0, 0);
    visGreeting();
    lukkOgMerk();
  }

  document.getElementById('velk-start').addEventListener('click', lagreOgLukk);
  document.getElementById('velk-navn-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') lagreOgLukk();
  });

  document.getElementById('velk-importer').addEventListener('click', () => {
    lukkOgMerk();
    document.querySelector('[data-tab="portfolio"]')?.click();
    setTimeout(() => document.getElementById('json-importer-fil')?.click(), 150);
  });
}


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


// ── TILBAKE TIL TOPPEN ────────────────────────────────────────────────────────
function initTilbakeTopp() {
  const btn = document.getElementById('tilbake-topp');
  if (!btn) return;
  const TERSKEL = 200;
  function sjekkScroll() {
    const scrolled = window.pageYOffset
      || window.scrollY
      || document.documentElement.scrollTop
      || document.body.scrollTop
      || 0;
    if (scrolled >= TERSKEL) {
      btn.classList.remove('hidden');
    } else {
      btn.classList.add('hidden');
    }
  }
  window.addEventListener('scroll', sjekkScroll, { passive: true });
  document.addEventListener('scroll', sjekkScroll, { passive: true });
  // Fallback: poll kvert sekund i tilfelle scroll-events ikke fyrer
  setInterval(sjekkScroll, 1000);
  btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
}

// ── SWIPE-NAVIGASJON ─────────────────────────────────────────────────────────
function initSwipe() {
  const FANER = ['oversikt', 'kalender', 'portfolio', 'verktoy'];
  let startX = 0, startY = 0;

  function byttTab(retning) {
    const idx = FANER.indexOf(aktivTab);
    const nyIdx = idx + retning;
    if (nyIdx < 0 || nyIdx >= FANER.length) return;
    document.querySelector(`.tab-btn[data-tab="${FANER[nyIdx]}"]`)?.click();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  document.addEventListener('touchstart', e => {
    startX = e.touches[0].clientX;
    startY = e.touches[0].clientY;
  }, { passive: true });

  document.addEventListener('touchend', e => {
    const dx = e.changedTouches[0].clientX - startX;
    const dy = e.changedTouches[0].clientY - startY;
    // Kun horisontal swipe: dx > 50px og klart mer horisontal enn vertikal
    if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
    byttTab(dx < 0 ? 1 : -1);
  }, { passive: true });
}

function initTabs() {
  document.getElementById('tab-nav').addEventListener('click', e => {
    const btn = e.target.closest('.tab-btn');
    if (!btn) return;
    aktivTab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b === btn));
    document.getElementById('tab-oversikt').classList.toggle('hidden', aktivTab !== 'oversikt');
    document.getElementById('tab-kalender').classList.toggle('hidden', aktivTab !== 'kalender');
    document.getElementById('tab-portfolio').classList.toggle('hidden', aktivTab !== 'portfolio');
    document.getElementById('tab-verktoy').classList.toggle('hidden', aktivTab !== 'verktoy');
    document.getElementById('oversikt-sub-nav').classList.toggle('hidden', aktivTab !== 'oversikt');
    document.getElementById('verktoy-sub-nav').classList.toggle('hidden', aktivTab !== 'verktoy');
    const erAksjerSubtab = aktivTab === 'oversikt' && aktivOversiktSubTab === 'aksjer';
    document.getElementById('filter-bar').classList.toggle('hidden', aktivTab === 'verktoy' || !erAksjerSubtab);
    document.getElementById('filter-ekstra').classList.toggle('hidden', !erAksjerSubtab);
    if (aktivTab === 'portfolio') visPortefolje();
    if (aktivTab === 'kalender') visKalender();
    if (aktivTab === 'oversikt') visOversikt();
    if (aktivTab === 'verktoy' && !window._pfSisteData) visPortefolje();
  });
}


function initOversiktSubTabs() {
  const nav = document.getElementById('oversikt-sub-nav');
  if (!nav) return;
  initTopplistor();
  nav.addEventListener('click', e => {
    const btn = e.target.closest('.sub-tab-btn');
    if (!btn) return;
    aktivOversiktSubTab = btn.dataset.subtab;
    nav.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.toggle('active', b === btn));
    document.getElementById('subtab-aksjer').classList.toggle('hidden', aktivOversiktSubTab !== 'aksjer');
    document.getElementById('subtab-bevegelser').classList.toggle('hidden', aktivOversiktSubTab !== 'bevegelser');
    document.getElementById('subtab-sektor').classList.toggle('hidden', aktivOversiktSubTab !== 'sektor');
    document.getElementById('subtab-topplistor').classList.toggle('hidden', aktivOversiktSubTab !== 'topplistor');
    const erAksjer = aktivOversiktSubTab === 'aksjer';
    document.getElementById('filter-bar').classList.toggle('hidden', !erAksjer);
    document.getElementById('filter-ekstra').classList.toggle('hidden', !erAksjer);
    if (aktivOversiktSubTab === 'sektor') visSektorer();
    if (aktivOversiktSubTab === 'bevegelser') visDagensBevegelser();
    if (aktivOversiktSubTab === 'topplistor') visTopplistor();
  });
}

// ── FIRE-KALKULATOR ──────────────────────────────────────────────────────────
function brukPortefoljeDataFire() {
  const pf = hentPF();
  const tickers = Object.keys(pf);
  const info = document.getElementById('fire-pf-info');

  if (!tickers.length || !alleAksjer.length) {
    info.textContent = 'Ingen porteføljedata — legg til aksjer i Portefølje-fanen først.';
    info.classList.remove('hidden');
    return;
  }

  let totalVerdi = 0, totalAr = 0, antallAksjer = 0;
  tickers.forEach(ticker => {
    const a = alleAksjer.find(x => x.ticker === ticker);
    const antall = pf[ticker];
    if (!a || antall < 1) return;
    const verdi = antall * (a.pris || 0);
    totalVerdi += verdi;
    totalAr    += antall * (a.utbytte_per_aksje || 0);
    antallAksjer++;
  });

  if (totalVerdi <= 0) {
    info.textContent = 'Mangler kursinformasjon for porteføljen. Prøv igjen om litt.';
    info.classList.remove('hidden');
    return;
  }

  const vektetYield = (totalAr / totalVerdi * 100);
  document.getElementById('fire-portefolje').value = Math.round(totalVerdi);
  document.getElementById('fire-yield').value = vektetYield.toFixed(2);

  info.textContent = `Hentet fra portefølje: ${antallAksjer} selskaper · ${Math.round(totalVerdi).toLocaleString('nb-NO')} kr · vektet yield ${vektetYield.toFixed(2)}%`;
  info.classList.remove('hidden');
  beregnFire();
}

function beregnFire() {
  const maaned   = parseFloat(document.getElementById('fire-maaned')?.value) || 0;
  const yieldPct = parseFloat(document.getElementById('fire-yield')?.value)  || 5;
  const pf       = parseFloat(document.getElementById('fire-portefolje')?.value) || 0;
  const sparing  = parseFloat(document.getElementById('fire-sparing')?.value) || 0;
  const konto    = document.querySelector('input[name="fire-konto"]:checked')?.value || 'ask';

  const SKATT = konto === 'ask' ? 0.3784 : konto === 'vanlig' ? 0.22 : 0;
  const yieldR = yieldPct / 100;

  // Brutto utbytte nødvendig per år = netto / (1 - skatt)
  const bruttoAar = (maaned * 12) / (1 - SKATT);
  const kapital   = SKATT === 0 ? (maaned * 12) / yieldR : bruttoAar / yieldR;

  // Antall år til FIRE med compound growth (yield reinvestert + sparing)
  // FV = PV*(1+r)^n + PMT*((1+r)^n - 1)/r >= kapital
  const PMT = sparing * 12;
  let ar = null;
  if (pf >= kapital) {
    ar = 0;
  } else if (PMT === 0 && pf === 0) {
    ar = null;
  } else {
    for (let n = 1; n <= 100; n++) {
      const fv = pf * Math.pow(1 + yieldR, n) + (PMT > 0 ? PMT * (Math.pow(1 + yieldR, n) - 1) / yieldR : 0);
      if (fv >= kapital) { ar = n; break; }
    }
  }

  const prosent = kapital > 0 ? Math.min(100, (pf / kapital) * 100) : 0;
  const fireAar = ar !== null ? new Date().getFullYear() + ar : null;

  // Oppdater DOM
  const fmt = v => v >= 1e6
    ? (v / 1e6).toLocaleString('nb', { maximumFractionDigits: 2 }) + ' mill. kr'
    : Math.round(v).toLocaleString('nb') + ' kr';

  document.getElementById('fire-ut-kapital').textContent = fmt(kapital);
  document.getElementById('fire-ut-brutto').textContent  = fmt(bruttoAar);
  document.getElementById('fire-ut-ar').textContent      = ar === null ? '> 100 år' : ar === 0 ? 'Allerede FIRE! 🎉' : ar + ' år';
  document.getElementById('fire-ut-prosent').textContent = prosent.toFixed(1) + '%';
  document.getElementById('fire-ut-bar').style.width     = prosent + '%';

  const tl = document.getElementById('fire-ut-tidslinje');
  if (ar !== null && ar > 0) {
    const halvveis = pf > 0 || PMT > 0
      ? (() => {
          for (let n = 1; n <= 100; n++) {
            const fv = pf * Math.pow(1 + yieldR, n) + (PMT > 0 ? PMT * (Math.pow(1 + yieldR, n) - 1) / yieldR : 0);
            if (fv >= kapital / 2) return n;
          }
          return null;
        })()
      : null;
    tl.innerHTML =
      (halvveis ? `<p>📍 Halvveis om ${halvveis} år (${new Date().getFullYear() + halvveis})</p>` : '') +
      `<p>🏁 FIRE-dato: ${fireAar}</p>` +
      `<p>💡 Netto månedlig utbytte ved FIRE: ${Math.round(maaned).toLocaleString('nb')} kr</p>`;
  } else if (ar === 0) {
    tl.innerHTML = '<p>🎉 Porteføljen din dekker allerede målet ditt!</p>';
  } else {
    tl.innerHTML = '<p>Fyll inn månedlig sparing eller nåværende portefølje for å beregne tid til FIRE.</p>';
  }
}

function initFire() {
  ['fire-maaned','fire-yield','fire-portefolje','fire-sparing'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', beregnFire);
  });
  document.querySelectorAll('input[name="fire-konto"]').forEach(r => {
    r.addEventListener('change', beregnFire);
  });
  document.getElementById('fire-bruk-pf')?.addEventListener('click', brukPortefoljeDataFire);
  beregnFire();
}

function initVerktoySubTabs() {
  const nav = document.getElementById('verktoy-sub-nav');
  if (!nav) return;

  initFire();

  // Nullstill rebalanserings-mål
  document.getElementById('rebal-nullstill')?.addEventListener('click', () => {
    if (typeof lagreRebalanseringsmaal === 'function') lagreRebalanseringsmaal({});
    const beholdning = window._pfSisteData?.beholdning || [];
    if (typeof visRebalansering === 'function') visRebalansering(beholdning);
  });

  nav.addEventListener('click', e => {
    const btn = e.target.closest('[data-verktoy-subtab]');
    if (!btn) return;
    nav.querySelectorAll('[data-verktoy-subtab]').forEach(b => b.classList.toggle('active', b === btn));
    const subtab = btn.dataset.verktoySubtab;
    document.getElementById('verktoy-subtab-kalkulator').classList.toggle('hidden', subtab !== 'kalkulator');
    document.getElementById('verktoy-subtab-annonsert').classList.toggle('hidden', subtab !== 'annonsert');
    document.getElementById('verktoy-subtab-fire').classList.toggle('hidden', subtab !== 'fire');
    document.getElementById('verktoy-subtab-rebalansering').classList.toggle('hidden', subtab !== 'rebalansering');
    if (subtab === 'rebalansering' && typeof visRebalansering === 'function') {
      visRebalansering(window._pfSisteData?.beholdning || []);
    }
    if (subtab === 'fire') beregnFire();
    if (subtab === 'annonsert') initAnnonsertKalkulator();
  });
}

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
    document.getElementById('filter-liste').value = '';
    visKunFavoritter = false;
    aktivListeFilter = '';
    oppdaterFavBtn();
    visOversikt();
  });

  document.getElementById('filter-fav').addEventListener('click', () => {
    visKunFavoritter = !visKunFavoritter;
    oppdaterFavBtn();
    visOversikt();
  });

  document.getElementById('filter-liste').addEventListener('change', e => {
    aktivListeFilter = e.target.value;
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

  // Paginering
  document.getElementById('paginering-kontroller')?.addEventListener('click', e => {
    const perBtn = e.target.closest('[data-per-side]');
    if (perBtn) {
      paginering.perSide = parseInt(perBtn.dataset.perSide, 10);
      paginering.side = 1;
      localStorage.setItem('paginering-per-side', paginering.perSide);
      visOversikt(true);
      return;
    }
    const sideBtn = e.target.closest('[data-side]');
    if (sideBtn && !sideBtn.disabled) {
      paginering.side = parseInt(sideBtn.dataset.side, 10);
      visOversikt(true);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
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


function byggListeFilter() {
  const sel = document.getElementById('filter-liste');
  if (!sel) return;
  const pfAntall = Object.keys(hentPF()).length;
  const lister = hentWatchlister();
  sel.innerHTML = '<option value="">Alle lister</option>';
  if (pfAntall > 0) {
    const o = document.createElement('option');
    o.value = 'pf'; o.textContent = `Portefølje (${pfAntall})`;
    sel.appendChild(o);
  }
  lister.forEach(w => {
    const o = document.createElement('option');
    o.value = `wl:${w.id}`; o.textContent = `${w.navn} (${(w.tickers||[]).length})`;
    sel.appendChild(o);
  });
  sel.value = aktivListeFilter;
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

  let listeTickers = null;
  if (aktivListeFilter === 'pf') {
    listeTickers = new Set(Object.keys(hentPF()));
  } else if (aktivListeFilter.startsWith('wl:')) {
    const id = aktivListeFilter.slice(3);
    const liste = hentWatchlister().find(w => w.id === id);
    listeTickers = new Set(liste?.tickers || []);
  }

  return alleAksjer.filter(a => {
    if (visKunFavoritter && !fav.has(a.ticker)) return false;
    if (listeTickers && !listeTickers.has(a.ticker)) return false;
    if (sok && !a.ticker.toLowerCase().includes(sok) && !a.navn.toLowerCase().includes(sok)) return false;
    if (sektor && a.sektor !== sektor) return false;
    if (frekvens && a.frekvens !== frekvens) return false;
    if (a.utbytte_yield < minYield) return false;
    return true;
  });
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
  visGreeting();
}

function initProfil() { initInnstillinger(); }


function oppdaterSammendrag() {
  const pf = hentPF();
  const fav = hentFav();
  const harPersonligData = Object.keys(pf).length > 0 || fav.size > 0;
  if (harPersonligData) {
    oppdaterPersonligSammendrag(pf, fav);
  } else {
    oppdaterGeneriskSammendrag();
  }
  oppdaterSpareMaalBar(pf);
}

function oppdaterSpareMaalBar(pf) {
  const { spareMaal } = hentProfil();
  const wrapper = document.getElementById('sparemaal-bar-wrapper');
  if (!wrapper) return;
  if (!spareMaal || spareMaal <= 0) { wrapper.classList.add('hidden'); return; }

  const totalVerdi = Object.entries(pf).reduce((s, [ticker, antall]) => {
    const a = alleAksjer.find(x => x.ticker === ticker);
    return s + (a ? antall * (a.pris || 0) : 0);
  }, 0);

  const pct = Math.min(100, totalVerdi / spareMaal * 100);
  document.getElementById('sparemaal-bar').style.width = pct.toFixed(1) + '%';
  document.getElementById('sparemaal-bar-tekst').textContent =
    totalVerdi.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr'
    + ' av ' + spareMaal.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr'
    + ' (' + pct.toFixed(1) + '%)';
  wrapper.classList.remove('hidden');
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

  // Kort 1: Ex-datoer denne måneden (fra portefølje + favoritter)
  const nå = new Date();
  const denneMåneden = alleAksjer.filter(a => {
    if (!alleTickere.has(a.ticker) || !a.ex_dato) return false;
    const d = new Date(a.ex_dato);
    return d >= idag && d.getMonth() === nå.getMonth() && d.getFullYear() === nå.getFullYear();
  }).sort((a, b) => new Date(a.ex_dato) - new Date(b.ex_dato));
  const månedNavn = nå.toLocaleString('nb-NO', { month: 'long' });
  document.getElementById('stat-card1-label').textContent = 'Ex-datoer i ' + månedNavn;
  document.getElementById('stat-antall').textContent = denneMåneden.length || '—';
  document.getElementById('stat-hoyest-navn').textContent = denneMåneden.length
    ? denneMåneden.slice(0,3).map(a => a.ticker).join(', ') + (denneMåneden.length > 3 ? ` +${denneMåneden.length - 3}` : '')
    : 'Ingen denne måneden';

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

  // Kort 3: Høyeste yield i portefølje
  const pfMedYield = alleAksjer
    .filter(a => pf[a.ticker] && a.utbytte_yield > 0)
    .sort((a, b) => b.utbytte_yield - a.utbytte_yield);
  document.getElementById('stat-card3-label').textContent = 'Høyeste yield';
  if (pfMedYield.length) {
    document.getElementById('stat-snitt-yield').textContent = pfMedYield[0].utbytte_yield.toFixed(2) + '%';
    document.getElementById('stat-snitt-sub').textContent = pfMedYield[0].ticker + ' · ' + pfMedYield[0].navn.split(' ')[0];
  } else {
    document.getElementById('stat-snitt-yield').textContent = '—';
    document.getElementById('stat-snitt-sub').textContent = 'Legg til aksjer';
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


function visOversikt(bevarSide = false) {
  if (!bevarSide) paginering.side = 1;
  visHvaSkjerIDag();
  visDagensBevegelser();
  const alleData = sorterAksjer(filtrerteAksjer());
  const tbody = document.getElementById('tabell-body');
  const kortBody = document.getElementById('kort-body');
  const ingenEl = document.getElementById('ingen-resultater');
  const ingenMobilEl = document.getElementById('ingen-resultater-mobil');
  const antallEl = document.getElementById('antall-vist');

  // ── PAGINERING ────────────────────────────────────────────────────────────
  const totalAntall = alleData.length;
  const perSide = paginering.perSide;
  const sidetall = perSide === 0 ? 1 : Math.max(1, Math.ceil(totalAntall / perSide));
  if (paginering.side > sidetall) paginering.side = sidetall;
  if (paginering.side < 1) paginering.side = 1;
  const sideFra = perSide === 0 ? 0 : (paginering.side - 1) * perSide;
  const sideTil = perSide === 0 ? totalAntall : Math.min(sideFra + perSide, totalAntall);
  const data = alleData.slice(sideFra, sideTil);

  // Oppdater sorteringsikoner og aria-sort
  document.querySelectorAll('th.sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === sortering.kol) {
      th.classList.add('sort-' + sortering.retning);
      th.setAttribute('aria-sort', sortering.retning === 'asc' ? 'ascending' : 'descending');
    } else {
      th.setAttribute('aria-sort', 'none');
    }
  });

  // Sync mobilsort-dropdown med faktisk sorteringstilstand
  const mobilSortEl = document.getElementById('mobil-sort');
  if (mobilSortEl) {
    const val = sortering.kol + '_' + sortering.retning;
    if (mobilSortEl.value !== val) mobilSortEl.value = val;
  }

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
  if (perSide === 0 || totalAntall <= perSide) {
    antallEl.textContent = `Viser ${totalAntall} av ${alleAksjer.length} aksjer`;
  } else {
    antallEl.textContent = `Viser ${sideFra + 1}–${sideTil} av ${totalAntall} aksjer`;
  }

  const idag = new Date(); idag.setHours(0,0,0,0);
  const om30 = new Date(idag); om30.setDate(om30.getDate() + 30);
  const _ad = hentAlleAksjeData();

  const bekreftet = data.filter(a => a.ex_dato);
  const estimert  = data.filter(a => !a.ex_dato);
  const visSeksjon = bekreftet.length > 0 && estimert.length > 0;

  const tabellSeksjonHeader = (label, sublabel) => `
    <tr class="bg-gray-100 dark:bg-gray-800">
      <td colspan="17" class="px-4 py-2">
        <span class="text-xs font-semibold text-gray-700 dark:text-gray-200 uppercase tracking-wide">${label}</span>
        <span class="text-xs text-gray-400 dark:text-gray-500 ml-2">${sublabel}</span>
      </td>
    </tr>`;

  const kortSeksjonHeader = (label, sublabel) => `
    <div class="px-1 pt-4 pb-1 border-b border-gray-200 dark:border-gray-700 mb-2">
      <span class="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">${label}</span>
      <span class="text-xs text-gray-400 dark:text-gray-500 ml-2">${sublabel}</span>
    </div>`;

  const byggTabellRad = a => {
    const exDato = a.ex_dato ? new Date(a.ex_dato + 'T00:00:00') : null; // lokal midnatt
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
        <div class="font-medium leading-tight">${a.navn} ${a.data_kilde && a.data_kilde !== 'yahoo' ? '<span class="text-xs text-amber-500 dark:text-amber-400" title="Data kan være utdatert">⚠ begrenset data</span>' : ''}</div>
        <div class="text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1.5">
          ${a.sektor}
          ${_harNotat ? '<span title="Har notat" class="opacity-60">✏</span>' : ''}
          ${_underMal ? '<span title="Under målpris" class="text-blue-500 dark:text-blue-400">🎯</span>' : ''}
        </div>
      </td>
      <td class="px-4 py-3 text-right font-medium">
        ${fmt(a.pris)}
        ${a.endring_pct !== undefined && a.endring_pct !== 0
          ? `<span class="block text-xs font-normal ${a.endring_pct > 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400'}">${a.endring_pct > 0 ? '+' : ''}${a.endring_pct.toFixed(2)}%</span>`
          : `<span class="text-xs text-gray-400">${a.valuta}</span>`}
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
        ${a.utbytte_vekst_5ar ? (a.utbytte_vekst_5ar > 0 ? '+' : '') + a.utbytte_vekst_5ar.toFixed(1) + '%' : '—'}
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
      <td class="px-2 py-3 text-center">
        <button class="sammenlign-btn p-1.5 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-brand-500 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors" data-ticker="${a.ticker}" aria-label="Legg til i sammenligning" title="Sammenlign">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v18M5 8l-2 8M21 8l-2 8M3 16h4M17 16h4M5 8h4m6 0h4"/><circle cx="12" cy="3" r="1"/></svg>
        </button>
      </td>
    </tr>`;
  };

  let tabellHtml = '';
  if (visSeksjon) tabellHtml += tabellSeksjonHeader('Annonsert / vedtatt', `ex-dato kjent — ${bekreftet.length} aksjer`);
  tabellHtml += bekreftet.map(byggTabellRad).join('');
  if (visSeksjon) tabellHtml += tabellSeksjonHeader('Forventet / estimert', `basert på siste 12 mnd — ${estimert.length} aksjer`);
  tabellHtml += estimert.map(byggTabellRad).join('');
  tbody.innerHTML = tabellHtml;

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
    const samBtn = e.target.closest('.sammenlign-btn');
    if (samBtn) {
      e.stopPropagation();
      toggleSammenlign(samBtn.dataset.ticker);
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

  const byggKort = a => {
    const exDato = a.ex_dato ? new Date(a.ex_dato + 'T00:00:00') : null; // lokal midnatt
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
      <button class="sammenlign-btn shrink-0 p-1.5 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-brand-500 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors" data-ticker="${escHtml(a.ticker)}" aria-label="Legg til i sammenligning" title="Sammenlign">
        <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v18M5 8l-2 8M21 8l-2 8M3 16h4M17 16h4M5 8h4m6 0h4"/><circle cx="12" cy="3" r="1"/></svg>
      </button>
      <div class="text-right shrink-0 space-y-0.5">
        <span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span>
        <div class="text-xs ${payoutKlasse(a.payout_ratio)}">Payout ${a.payout_ratio > 0 ? a.payout_ratio.toFixed(0)+'%' : '—'}</div>
      </div>
    </div>`;

    // ── NORMALT MOBILKORT (full detalj) ────────────────────────────────
    const kildeStr = a.data_kilde && a.data_kilde !== 'yahoo'
      ? `<span class="text-xs text-amber-500 dark:text-amber-400" title="Data kan være utdatert">⚠ begrenset data</span>`
      : '';
    const normalKort = `
    <div class="aksje-kort ${snartEx ? 'snart-ex' : ''}" data-ticker="${a.ticker}">
      <div class="flex items-start justify-between gap-2 mb-2">
        <div class="flex items-start gap-2">
          ${stjerne(a.ticker, 'mt-0.5 shrink-0')}
          <div>
            <span class="font-mono font-bold text-brand-700 dark:text-brand-400 text-base">${a.ticker}</span>
            <span class="frekvens-badge ml-2">${a.frekvens}</span>
            <div class="text-sm text-gray-600 dark:text-gray-400 mt-0.5 leading-tight">${a.navn}</div>
            ${kildeStr}
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
          ${a.endring_pct !== undefined && a.endring_pct !== 0
            ? `<div class="text-xs font-medium ${a.endring_pct > 0 ? 'text-green-500 dark:text-green-400' : 'text-red-500 dark:text-red-400'}">${a.endring_pct > 0 ? '+' : ''}${a.endring_pct.toFixed(2)}%</div>`
            : `<div class="text-xs text-gray-400">${a.valuta}</div>`}
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
          <div class="font-semibold text-sm mt-0.5 ${vekstKlasse(a.utbytte_vekst_5ar)}">${a.utbytte_vekst_5ar ? (a.utbytte_vekst_5ar>0?'+':'')+a.utbytte_vekst_5ar.toFixed(1)+'%' : '—'}</div>
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
        <div class="flex items-center gap-2">
          <button class="sammenlign-btn flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-brand-500 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors" data-ticker="${escHtml(a.ticker)}" aria-label="Legg til i sammenligning">
            <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v18M5 8l-2 8M21 8l-2 8M3 16h4M17 16h4M5 8h4m6 0h4"/><circle cx="12" cy="3" r="1"/></svg>
            <span>Sammenlign</span>
          </button>
          <svg class="w-4 h-4 text-gray-300 dark:text-gray-600" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
        </div>
      </div>
    </div>`;

    return kompaktModus ? kompaktKort : normalKort;
  };

  let kortHtml = '';
  if (visSeksjon) kortHtml += kortSeksjonHeader('Annonsert / vedtatt', `ex-dato kjent — ${bekreftet.length} aksjer`);
  kortHtml += bekreftet.map(byggKort).join('');
  if (visSeksjon) kortHtml += kortSeksjonHeader('Forventet / estimert', `basert på siste 12 mnd — ${estimert.length} aksjer`);
  kortHtml += estimert.map(byggKort).join('');
  kortBody.innerHTML = kortHtml;

  // Klikk via event delegation (kort) – ingen minnelekasje
  kortBody.onclick = e => {
    const sammenlignBtn = e.target.closest('.sammenlign-btn');
    if (sammenlignBtn) {
      e.stopPropagation();
      toggleSammenlign(sammenlignBtn.dataset.ticker);
      return;
    }
    const favBtn = e.target.closest('.fav-btn');
    if (favBtn) {
      e.stopPropagation();
      toggleFav(favBtn.dataset.ticker);
      oppdaterFavBtn();
      visOversikt(true);
      return;
    }
    const kort = e.target.closest('[data-ticker]');
    if (!kort) return;
    const aksje = alleAksjer.find(a => a.ticker === kort.dataset.ticker);
    if (aksje) visModal(aksje);
  };

  renderPaginering(totalAntall, sidetall);
}

function renderPaginering(totalAntall, sidetall) {
  const el = document.getElementById('paginering-kontroller');
  if (!el) return;
  const { side, perSide } = paginering;

  const perSideAlternativer = [
    { val: 25, label: '25' },
    { val: 50, label: '50' },
    { val: 75, label: '75' },
    { val: 100, label: '100' },
    { val: 0, label: 'Alle' },
  ];

  const perSideHtml = perSideAlternativer.map(({ val, label }) => {
    const aktiv = val === perSide;
    return `<button data-per-side="${val}" class="px-2.5 py-1 rounded text-xs font-medium transition-colors ${
      aktiv
        ? 'bg-brand-600 text-white dark:bg-brand-500'
        : 'text-gray-500 dark:text-gray-400 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-gray-100 dark:hover:bg-gray-800'
    }">${label}</button>`;
  }).join('');

  const visNav = perSide !== 0 && sidetall > 1;
  const navHtml = visNav ? `
    <div class="flex items-center gap-1">
      <button data-side="${side - 1}" ${side <= 1 ? 'disabled' : ''} class="px-2.5 py-1 rounded text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 disabled:cursor-default transition-colors">‹ Forrige</button>
      <span class="text-xs text-gray-400 dark:text-gray-500 px-1">Side ${side} av ${sidetall}</span>
      <button data-side="${side + 1}" ${side >= sidetall ? 'disabled' : ''} class="px-2.5 py-1 rounded text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-brand-600 dark:hover:text-brand-400 hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30 disabled:cursor-default transition-colors">Neste ›</button>
    </div>` : '';

  el.innerHTML = `
    <div class="flex items-center gap-1">
      <span class="text-xs text-gray-400 dark:text-gray-500 mr-1">Vis:</span>
      ${perSideHtml}
    </div>
    ${navHtml}`;
}

function sorterAksjer(data) {
  const { kol, retning } = sortering;
  const hentVerdi = (a) => kol === 'utbytte_score' ? beregnScore(a) : a[kol];
  return [...data].sort((a, b) => {
    let va = hentVerdi(a), vb = hentVerdi(b);
    if (va == null) va = retning === 'asc' ? Infinity : -Infinity;
    if (vb == null) vb = retning === 'asc' ? Infinity : -Infinity;
    if (typeof va === 'string') return retning === 'asc' ? va.localeCompare(vb, 'nb') : vb.localeCompare(va, 'nb');
    return retning === 'asc' ? va - vb : vb - va;
  });
}


function initTopplistor() {
  const pillBar = document.getElementById('toppliste-pill-bar');
  const container = document.getElementById('toppliste-innhold');
  if (!pillBar || pillBar.dataset.init) return;
  pillBar.dataset.init = '1';
  pillBar.addEventListener('click', e => {
    const pill = e.target.closest('.toppliste-pill');
    if (!pill) return;
    pillBar.querySelectorAll('.toppliste-pill').forEach(b => b.classList.toggle('active', b === pill));
    visTopplistor(pill.dataset.liste);
  });
  container.addEventListener('click', e => {
    const rad = e.target.closest('.toppliste-rad');
    if (!rad) return;
    const aksje = alleAksjer.find(x => x.ticker === rad.dataset.ticker);
    if (aksje) visModal(aksje);
  });
}

function visTopplistor(liste = 'yield') {
  const container = document.getElementById('toppliste-innhold');
  if (!container || !alleAksjer.length) return;

  const LISTER = {
    yield:      { felt: 'utbytte_yield',    retning: 'desc',
                  filter: a => a.utbytte_yield > 0,
                  label:  a => a.utbytte_yield.toFixed(2) + '% yield' },
    vekst:      { felt: 'utbytte_vekst_5ar', retning: 'desc',
                  filter: a => a.utbytte_vekst_5ar > 0,
                  label:  a => '+' + a.utbytte_vekst_5ar.toFixed(1) + '% vekst/år' },
    konsistent: { felt: 'ar_med_utbytte',   retning: 'desc',
                  filter: a => a.ar_med_utbytte > 0,
                  label:  a => a.ar_med_utbytte + ' år m/utbytte' },
    payout:     { felt: 'payout_ratio',     retning: 'asc',
                  filter: a => a.payout_ratio > 0 && a.payout_ratio < 100,
                  label:  a => a.payout_ratio.toFixed(0) + '% payout' },
  };

  const cfg = LISTER[liste];
  if (!cfg) return;

  const topp = alleAksjer
    .filter(cfg.filter)
    .sort((a, b) => cfg.retning === 'desc' ? b[cfg.felt] - a[cfg.felt] : a[cfg.felt] - b[cfg.felt])
    .slice(0, 10);

  if (!topp.length) {
    container.innerHTML = '<p class="text-gray-400 dark:text-gray-600 py-8 text-center text-sm">Ingen data tilgjengelig.</p>';
    return;
  }

  container.innerHTML = topp.map((a, i) => `
    <div class="toppliste-rad" data-ticker="${a.ticker}">
      <span class="toppliste-rang">${i + 1}</span>
      <div class="toppliste-info">
        <span class="font-mono font-bold text-sm text-brand-700 dark:text-brand-400">${a.ticker}</span>
        <span class="toppliste-navn">${a.navn}</span>
        <span class="toppliste-sektor">${a.sektor || ''}</span>
      </div>
      <div class="toppliste-høyre">
        <span class="toppliste-metric">${cfg.label(a)}</span>
        <span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span>
      </div>
    </div>`).join('');
}

function visSektorer() {
  const grid = document.getElementById('sektor-grid');
  if (!grid) return;

  // Group stocks by sector
  const sektorMap = {};
  alleAksjer.forEach(a => {
    const s = a.sektor || 'Ukjent';
    if (!sektorMap[s]) sektorMap[s] = [];
    sektorMap[s].push(a);
  });

  const kort = Object.entries(sektorMap)
    .sort((a, b) => a[0].localeCompare(b[0], 'no'))
    .map(([navn, aksjer]) => {
      const yields = aksjer.map(a => a.utbytte_yield).filter(y => y > 0);
      const snittYield = yields.length ? (yields.reduce((s, y) => s + y, 0) / yields.length) : 0;
      const bestYield = yields.length ? Math.max(...yields) : 0;
      const bestAksje = aksjer.find(a => a.utbytte_yield === bestYield);
      const slug = navn.toLowerCase().replace(/\s+/g, '-').replace(/[æ]/g, 'ae').replace(/[ø]/g, 'o').replace(/[å]/g, 'a');

      return `<a href="/aksjer/sektor/${slug}/" class="block rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm hover:shadow-md hover:border-brand-300 dark:hover:border-brand-700 transition-all group">
        <div class="flex items-start justify-between gap-2 mb-3">
          <div>
            <h3 class="font-semibold text-gray-900 dark:text-gray-100 group-hover:text-brand-700 dark:group-hover:text-brand-400 transition-colors">${navn}</h3>
          </div>
          <span class="text-xs bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 px-2 py-0.5 rounded-full whitespace-nowrap">${aksjer.length} aksjer</span>
        </div>
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <div class="text-xs text-gray-400 dark:text-gray-500 mb-0.5">Snitt yield</div>
            <div class="font-semibold text-brand-600 dark:text-brand-400">${snittYield > 0 ? snittYield.toFixed(1) + ' %' : '—'}</div>
          </div>
          <div>
            <div class="text-xs text-gray-400 dark:text-gray-500 mb-0.5">Høyeste yield</div>
            <div class="font-semibold text-green-600 dark:text-green-400">${bestYield > 0 ? bestYield.toFixed(1) + ' %' : '—'}</div>
          </div>
        </div>
        ${bestAksje ? `<div class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 text-xs text-gray-400 dark:text-gray-500">Beste: <span class="font-medium text-gray-700 dark:text-gray-300">${bestAksje.ticker}</span> — ${bestAksje.navn}</div>` : ''}
      </a>`;
    });

  grid.innerHTML = kort.join('');
}

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
      const d = new Date(dato + 'T00:00:00'); // lokal midnatt, ikke UTC
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
        <div class="flex items-center gap-2 shrink-0">
          <div class="text-right min-w-16 pointer-events-none">
            ${type !== 'rapport' ? `<span class="yield-badge ${yieldKlasse(a.utbytte_yield)} text-sm">${a.utbytte_yield.toFixed(2)}%</span>` : ''}
            ${!erPassert ? `<div class="text-xs text-gray-400 mt-1">${dagerTil === 0 ? 'I dag!' : dagerTil === 1 ? 'I morgen' : `om ${dagerTil}d`}</div>` : '<div class="text-xs text-gray-400 mt-1">Passert</div>'}
          </div>
          <button class="kal-ics-btn p-1.5 rounded-lg text-gray-400 hover:text-brand-600 hover:bg-brand-50 dark:hover:bg-brand-900/20 transition-colors"
                  data-ticker="${a.ticker}" data-type="${type}" data-dato="${dato}"
                  title="Legg til i kalender (.ics)" aria-label="Legg til i kalender (.ics)">
            <svg class="w-4 h-4 pointer-events-none" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
            </svg>
          </button>
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

  // Klikk → ICS-knapp eller modal
  container.onclick = e => {
    const icsBtn = e.target.closest('.kal-ics-btn');
    if (icsBtn) {
      e.stopPropagation();
      const aksje = alleAksjer.find(a => a.ticker === icsBtn.dataset.ticker);
      if (aksje) eksporterEnkeltICS(aksje, icsBtn.dataset.type, icsBtn.dataset.dato);
      return;
    }
    const rad = e.target.closest('[data-ticker]');
    if (!rad) return;
    const aksje = alleAksjer.find(a => a.ticker === rad.dataset.ticker);
    if (aksje) visModal(aksje);
  };
}


function stjerne(ticker, ekstraKlasse = '') {
  const er = erFavoritt(ticker);
  return `<button class="fav-btn ${ekstraKlasse} transition-colors" data-ticker="${ticker}" title="${er ? 'Fjern favoritt' : 'Legg til favoritt'}" aria-label="${er ? 'Fjern fra favoritter' : 'Legg til i favoritter'}">
    <svg class="w-4 h-4 pointer-events-none ${er ? 'text-yellow-400' : 'text-gray-300 dark:text-gray-600'}" aria-hidden="true" fill="${er ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/></svg>
  </button>`;
}


function genererDelLink() {
  const pf    = hentAktivPF();
  const beholdning = hentPF();
  const navn  = pf.navn || 'Min portefølje';
  let totalVerdi = 0, totalAr = 0;
  const posisjoner = [];

  Object.entries(beholdning).forEach(([ticker, antall]) => {
    const aksje = alleAksjer.find(a => a.ticker === ticker);
    if (!aksje || !antall) return;
    const verdi = antall * (aksje.pris || 0);
    const ar    = antall * (aksje.utbytte_pr_aksje || 0);
    totalVerdi += verdi;
    totalAr    += ar;
    posisjoner.push([ticker, verdi, aksje.utbytte_yield || 0]);
  });

  const yieldPct = totalVerdi > 0 ? totalAr / totalVerdi * 100 : 0;
  const topp5 = posisjoner
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([t, v, y]) => [t, Math.round(totalVerdi > 0 ? v / totalVerdi * 1000 : 0) / 10, Math.round(y * 10) / 10]);

  const data = {
    n:  navn,
    v:  Math.round(totalVerdi),
    y:  Math.round(totalAr),
    yp: Math.round(yieldPct * 10) / 10,
    t:  topp5,
    d:  new Date().toISOString().slice(0, 10)
  };

  const encoded = btoa(encodeURIComponent(JSON.stringify(data)));
  const url = `${location.origin}${location.pathname}?del=${encoded}`;

  navigator.clipboard.writeText(url).then(() => {
    const btn = document.getElementById('pf-del-btn');
    if (btn) { const o = btn.textContent; btn.textContent = '✓ Lenke kopiert!'; setTimeout(() => { btn.textContent = o; }, 2500); }
  }).catch(() => { prompt('Kopier lenken:', url); });
}

function visDeltPortefolje(data) {
  const modal = document.getElementById('del-modal');
  if (!modal) return;
  const fmtK = v => Math.round(v || 0).toLocaleString('nb-NO') + ' kr';
  document.getElementById('del-modal-navn').textContent    = data.n || 'Delt portefølje';
  document.getElementById('del-modal-dato').textContent    = 'Delt ' + (data.d || '');
  document.getElementById('del-modal-verdi').textContent   = fmtK(data.v);
  document.getElementById('del-modal-utbytte').textContent = fmtK(data.y);
  document.getElementById('del-modal-yield').textContent   = (data.yp || 0).toFixed(1) + '%';

  const topp = document.getElementById('del-modal-topp');
  if (topp && data.t && data.t.length > 0) {
    topp.innerHTML = `<p class="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Topp posisjoner</p>` +
      data.t.map(([ticker, vekt, y]) => `
        <div class="flex items-center justify-between py-1.5 border-b border-gray-100 dark:border-gray-800 last:border-0">
          <span class="font-mono font-bold text-brand-700 dark:text-brand-400 text-sm">${ticker}</span>
          <div class="text-right text-sm">
            <span class="text-gray-500 dark:text-gray-400">${vekt}% av port.</span>
            <span class="ml-3 font-semibold text-green-600 dark:text-green-400">${y}% yield</span>
          </div>
        </div>`).join('');
  }

  modal.classList.remove('hidden');
  const lukk = () => modal.classList.add('hidden');
  document.getElementById('del-modal-lukk').onclick = lukk;
  modal.onclick = e => { if (e.target === modal) lukk(); };
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

// ── JSON BACKUP ───────────────────────────────────────────────────────────
function eksporterJSON() {
  const backup = {
    versjon: 5,
    eksportert: new Date().toISOString(),
    profil: {
      navn:      localStorage.getItem('profil_navn') || '',
      mal_mnd:   localStorage.getItem('profil_mal_mnd') || '0',
      sparemaal: localStorage.getItem('profil_sparemaal') || '0'
    },
    portefoljer:      hentPortefoljer(),
    aktiv_pf:         hentAktivPFId(),
    watchlister:      hentWatchlister(),
    favoritter:       JSON.parse(localStorage.getItem('fav_aksjer') || '[]'),
    aksje_data:       JSON.parse(localStorage.getItem('aksje_data') || '{}'),
    notif_aksjer:     JSON.parse(localStorage.getItem('notif_aksjer') || '[]'),
    historikk:        JSON.parse(localStorage.getItem('pf_historikk') || '{}'),
    rebalansering:    JSON.parse(localStorage.getItem('pf_rebalansering') || '{}'),
    tema:             localStorage.getItem('tema') || '',
    sortering:        localStorage.getItem('sortering') || '',
    paginering:       localStorage.getItem('paginering-per-side') || '25',
    rebal_skjul_tomme: localStorage.getItem('rebal-skjul-tomme') || 'true',
    streak: {
      teller:      localStorage.getItem('streak_teller') || '1',
      sist_besok:  localStorage.getItem('streak_sist_besok') || ''
    },
    milepeler: JSON.parse(localStorage.getItem('milepeler_oppnaad') || '[]')
  };
  const blob = new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  const dato = new Date().toISOString().slice(0, 10);
  a.href = url; a.download = `exday-backup-${dato}.json`; a.click();
  URL.revokeObjectURL(url);
}

function parseJSONBackup(tekst) {
  try {
    const b = JSON.parse(tekst);
    if (!b || typeof b.versjon !== 'number' || b.versjon < 1 || b.versjon > 5) return null;
    return b;
  } catch { return null; }
}

function visJSONPreview(backup) {
  const el  = document.getElementById('json-importer-innhold');
  const p   = backup.profil || {};
  const pfl = backup.portefoljer || (backup['portefølje'] ? { default: { beholdning: backup['portefølje'] } } : {});
  const antallPF  = Object.keys(pfl).length;
  const antallPos = Object.values(pfl).reduce((s, pf) => s + Object.keys(pf.beholdning || {}).length, 0);
  const antallTx  = Object.values(pfl).reduce((s, pf) => s + Object.values(pf.transaksjoner || {}).reduce((t, l) => t + l.length, 0), 0);
  const wl  = backup.watchlister || [];
  const fav = backup.favoritter  || [];
  const na  = backup.notif_aksjer || [];
  const antallRebal = Object.keys(backup.rebalansering || {}).length;
  const linjer = [
    p.navn ? `Profil: ${p.navn}` : 'Profil: (ikke satt)',
    `${antallPF} portefølje${antallPF !== 1 ? 'r' : ''} · ${antallPos} posisjoner · ${antallTx} transaksjoner`,
    `Favoritter: ${fav.length} · Watchlister: ${wl.length} · Varsler: ${na.length} aksjer`
      + (antallRebal ? ` · Rebalansering: ${antallRebal} sektormål` : ''),
    `Eksportert: ${backup.eksportert ? new Date(backup.eksportert).toLocaleDateString('nb-NO') : 'ukjent'} (format v${backup.versjon})`
  ];
  el.innerHTML = linjer.map(l => `<p>• ${l}</p>`).join('');
  document.getElementById('json-importer-preview').classList.remove('hidden');
}

function bekreftJSONImport(backup) {
  const fav = backup.favoritter || [];
  const p   = backup.profil || {};

  // v3+: portefoljer-struktur. v1/v2: migrer gammel enkelt-portefølje.
  if (backup.portefoljer) {
    lagrePortefoljer(backup.portefoljer);
    if (backup.aktiv_pf) settAktivPFId(backup.aktiv_pf);
  } else {
    const gammelPF = backup['portefølje'] || backup.portefolje || {};
    const gammelTx = backup.transaksjoner || {};
    lagrePortefoljer({ default: { id: 'default', navn: 'Min portefølje', beholdning: gammelPF, transaksjoner: gammelTx } });
    settAktivPFId('default');
  }
  if (backup.watchlister)  lagreWatchlister(backup.watchlister);
  localStorage.setItem('fav_aksjer', JSON.stringify(fav));
  if (backup.aksje_data)        localStorage.setItem('aksje_data',           JSON.stringify(backup.aksje_data));
  if (backup.notif_aksjer)      localStorage.setItem('notif_aksjer',         JSON.stringify(backup.notif_aksjer));
  if (backup.historikk)         localStorage.setItem('pf_historikk',         JSON.stringify(backup.historikk));
  if (backup.rebalansering && Object.keys(backup.rebalansering).length)
                                localStorage.setItem('pf_rebalansering',     JSON.stringify(backup.rebalansering));
  if (backup.tema)              localStorage.setItem('tema',                  backup.tema);
  if (backup.sortering)         localStorage.setItem('sortering',             backup.sortering);
  if (backup.paginering)        localStorage.setItem('paginering-per-side',   backup.paginering);
  if (backup.rebal_skjul_tomme !== undefined)
                                localStorage.setItem('rebal-skjul-tomme',     backup.rebal_skjul_tomme);
  if (backup.streak) {
    localStorage.setItem('streak_teller',     backup.streak.teller);
    localStorage.setItem('streak_sist_besok', backup.streak.sist_besok);
  }
  if (backup.milepeler)         localStorage.setItem('milepeler_oppnaad',    JSON.stringify(backup.milepeler));
  lagreProfil(p.navn || '', parseFloat(p.mal_mnd) || 0, parseFloat(p.sparemaal) || 0);
  oppdaterPortefoljeVelger();

  document.getElementById('json-importer-preview').classList.add('hidden');
  visGreeting();
  oppdaterSpareMaalBar(pf);
  oppdaterSammendrag();
  if (aktivTab === 'portfolio') visPortefolje();
}


function initJSONBackup() {
  document.getElementById('pf-eksport-json')?.addEventListener('click', eksporterJSON);

  const filInput = document.getElementById('json-importer-fil');
  document.getElementById('pf-importer-json')?.addEventListener('click', () => filInput?.click());
  filInput.addEventListener('change', () => {
    const fil = filInput.files[0];
    if (!fil) return;
    const reader = new FileReader();
    reader.onload = e => {
      const backup = parseJSONBackup(e.target.result);
      if (!backup) {
        alert('Ugyldig backup-fil. Kontroller at du har valgt riktig .json-fil fra exday.no.');
        return;
      }
      window._pendingJSONBackup = backup;
      visJSONPreview(backup);
    };
    reader.readAsText(fil, 'UTF-8');
    filInput.value = '';
  });

  document.getElementById('json-importer-bekreft').addEventListener('click', () => {
    if (window._pendingJSONBackup) bekreftJSONImport(window._pendingJSONBackup);
    window._pendingJSONBackup = null;
  });
  document.getElementById('json-importer-avbryt').addEventListener('click', () => {
    document.getElementById('json-importer-preview').classList.add('hidden');
    window._pendingJSONBackup = null;
  });
}


// ── AUTO-BACKUP ────────────────────────────────────────────────────────────
// Chrome/Edge: File System Access API → skriver stille til en fast fil på disk
// Firefox/Safari/andre: automatisk nedlasting én gang per uke

const _BACKUP_DB       = 'exday-autobackup';
const _BACKUP_STORE    = 'filehandle';
const _BACKUP_KEY      = 'handle';
const _SIST_BACKUP_KEY = 'autobackup_sist';
const _BACKUP_SNOOZE   = 'autobackup_snooze';
const _BACKUP_AV_KEY   = 'autobackup_av';
const _DAGER_MELLOM    = 7;

function _erChromiumMedFilAPI() {
  return (
    typeof window.showSaveFilePicker === 'function' &&
    /Chrome|Edg/.test(navigator.userAgent) &&
    !/Firefox/.test(navigator.userAgent)
  );
}

function _aapneBackupDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(_BACKUP_DB, 2);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains(_BACKUP_STORE)) db.createObjectStore(_BACKUP_STORE);
      if (!db.objectStoreNames.contains('autokopi')) db.createObjectStore('autokopi');
    };
    req.onsuccess  = e => resolve(e.target.result);
    req.onerror    = e => reject(e.target.error);
  });
}

// Lagrer backup stille til IndexedDB ved hvert sidelast (fungerer på alle nettlesere inkl. iOS)
async function autoLagreIDB() {
  try {
    if (!_harData()) return;
    const blob = _lagBackupBlob();
    const tekst = await blob.text();
    const db = await _aapneBackupDB();
    await new Promise((resolve, reject) => {
      const tx  = db.transaction('autokopi', 'readwrite');
      tx.objectStore('autokopi').put({ dato: new Date().toISOString(), json: tekst }, 'siste');
      tx.oncomplete = resolve;
      tx.onerror    = e => reject(e.target.error);
    });
  } catch (e) { console.warn('autoLagreIDB feil:', e); }
}

async function hentAutoKopiIDB() {
  try {
    const db = await _aapneBackupDB();
    return await new Promise((resolve, reject) => {
      const tx  = db.transaction('autokopi', 'readonly');
      const req = tx.objectStore('autokopi').get('siste');
      req.onsuccess = e => resolve(e.target.result || null);
      req.onerror   = e => reject(e.target.error);
    });
  } catch { return null; }
}

async function _hentFilhandle() {
  try {
    const db = await _aapneBackupDB();
    return new Promise((resolve, reject) => {
      const tx  = db.transaction(_BACKUP_STORE, 'readonly');
      const req = tx.objectStore(_BACKUP_STORE).get(_BACKUP_KEY);
      req.onsuccess = e => resolve(e.target.result || null);
      req.onerror   = e => reject(e.target.error);
    });
  } catch { return null; }
}

async function _lagreFilhandle(handle) {
  try {
    const db = await _aapneBackupDB();
    return new Promise((resolve, reject) => {
      const tx  = db.transaction(_BACKUP_STORE, 'readwrite');
      const req = tx.objectStore(_BACKUP_STORE).put(handle, _BACKUP_KEY);
      req.onsuccess = () => resolve();
      req.onerror   = e => reject(e.target.error);
    });
  } catch { /* stille feil */ }
}

function _lagBackupBlob() {
  const backup = {
    versjon: 5,
    eksportert: new Date().toISOString(),
    profil: {
      navn:      localStorage.getItem('profil_navn') || '',
      mal_mnd:   localStorage.getItem('profil_mal_mnd') || '0',
      sparemaal: localStorage.getItem('profil_sparemaal') || '0'
    },
    portefoljer:       hentPortefoljer(),
    aktiv_pf:          hentAktivPFId(),
    watchlister:       hentWatchlister(),
    favoritter:        JSON.parse(localStorage.getItem('fav_aksjer') || '[]'),
    aksje_data:        JSON.parse(localStorage.getItem('aksje_data') || '{}'),
    notif_aksjer:      JSON.parse(localStorage.getItem('notif_aksjer') || '[]'),
    historikk:         JSON.parse(localStorage.getItem('pf_historikk') || '{}'),
    rebalansering:     JSON.parse(localStorage.getItem('pf_rebalansering') || '{}'),
    tema:              localStorage.getItem('tema') || '',
    sortering:         localStorage.getItem('sortering') || '',
    paginering:        localStorage.getItem('paginering-per-side') || '25',
    rebal_skjul_tomme: localStorage.getItem('rebal-skjul-tomme') || 'true',
    streak: {
      teller:     localStorage.getItem('streak_teller') || '1',
      sist_besok: localStorage.getItem('streak_sist_besok') || ''
    },
    milepeler: JSON.parse(localStorage.getItem('milepeler_oppnaad') || '[]')
  };
  return new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' });
}

async function _skrivTilFil(handle, blob) {
  try {
    const perm = await handle.queryPermission({ mode: 'readwrite' });
    if (perm !== 'granted') {
      const req = await handle.requestPermission({ mode: 'readwrite' });
      if (req !== 'granted') return false;
    }
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();
    return true;
  } catch { return false; }
}

async function _velgOgLagreFil(blob) {
  try {
    const dato   = new Date().toISOString().slice(0, 10);
    const handle = await window.showSaveFilePicker({
      suggestedName: `exday-backup-${dato}.json`,
      types: [{ description: 'JSON backup', accept: { 'application/json': ['.json'] } }]
    });
    await _lagreFilhandle(handle);
    await _skrivTilFil(handle, blob);
    return true;
  } catch { return false; }
}

async function _autoNedlasting(blob) {
  const dato = new Date().toISOString().slice(0, 10);
  const filnavn = `exday-backup-${dato}.json`;
  // Web Share API med filer: iOS 15+ åpner del-ark → "Lagre i Filer" / AirDrop / etc.
  try {
    const fil = new File([blob], filnavn, { type: 'application/json' });
    if (navigator.canShare && navigator.canShare({ files: [fil] })) {
      await navigator.share({ files: [fil], title: 'exday backup' });
      return;
    }
  } catch (e) { if (e.name !== 'AbortError') console.warn('share feil:', e); }
  // Fallback: vanlig nedlasting
  const url = URL.createObjectURL(blob);
  const a   = document.createElement('a');
  a.href = url; a.download = filnavn; a.click();
  URL.revokeObjectURL(url);
}

function _harData() {
  const fav = JSON.parse(localStorage.getItem('fav_aksjer') || '[]');
  if (fav.length > 0) return true;
  const pf  = hentPortefoljer();
  const harPF = Object.values(pf).some(p => Object.keys(p.beholdning || {}).length > 0);
  if (harPF) return true;
  const wl = hentWatchlister();
  if (wl.length > 0) return true;
  if (localStorage.getItem('profil_navn')) return true;
  const trx = JSON.parse(localStorage.getItem('pf_transaksjoner') || '{}');
  return Object.values(trx).some(t => Array.isArray(t) && t.length > 0);
}

function _lagBackupToast(tittel, tekst, knappTekst, onKlikk) {
  const el = document.createElement('div');
  el.className = 'fixed bottom-4 right-4 z-50 max-w-sm w-full bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-xl p-4 flex flex-col gap-2';
  el.innerHTML =
    `<div class="flex items-start justify-between gap-2">
      <div>
        <p class="text-sm font-semibold text-gray-800 dark:text-gray-100">${tittel}</p>
        <p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">${tekst}</p>
      </div>
      <button class="bt-lukk text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl leading-none shrink-0">×</button>
    </div>
    <div class="flex gap-2">
      <button class="bt-ok flex-1 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-semibold rounded-lg transition-colors">${knappTekst}</button>
      <button class="bt-senere text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 px-2 transition-colors">Senere</button>
    </div>`;
  const lukk = (snooze = false) => {
    if (snooze) localStorage.setItem(_BACKUP_SNOOZE, Date.now().toString());
    el.remove();
  };
  el.querySelector('.bt-lukk').addEventListener('click', () => lukk(true));
  el.querySelector('.bt-senere').addEventListener('click', () => lukk(true));
  el.querySelector('.bt-ok').addEventListener('click', async () => { await onKlikk(); lukk(false); });
  setTimeout(() => lukk(false), 30_000);
  return el;
}

async function initAutoBackup() {
  try {
    if (!_harData()) return;

    // Sjekk om backup er slått av av bruker (satt til 'nei' fra innstillinger)
    if (localStorage.getItem(_BACKUP_AV_KEY) === 'nei') return;

    // Sjekk snooze (snoozet = toast ble lukket uten handling)
    const snooze = parseInt(localStorage.getItem(_BACKUP_SNOOZE) || '0', 10);
    const dagSidenSnooze = snooze ? Math.floor((Date.now() - snooze) / 86_400_000) : 99;
    if (dagSidenSnooze < _DAGER_MELLOM) return;

    const blob = _lagBackupBlob();

    if (_erChromiumMedFilAPI()) {
      // ── Chrome/Edge ──────────────────────────────────────────────────────
      const handle = await _hentFilhandle();
      if (handle) {
        const ok = await _skrivTilFil(handle, blob);
        if (ok) { localStorage.setItem(_SIST_BACKUP_KEY, new Date().toISOString()); return; }
        // Tillatelse tapt — fall gjennom til nytt filvalg
      }
      const toast = _lagBackupToast(
        '💾 Automatisk backup',
        'Velg en fil på datamaskinen — appen oppdaterer den automatisk neste gang du åpner exday.',
        'Velg fil',
        async () => {
          const ok = await _velgOgLagreFil(blob);
          if (ok) localStorage.setItem(_SIST_BACKUP_KEY, new Date().toISOString());
        }
      );
      document.body.appendChild(toast);

    } else {
      // ── Firefox / Safari / andre ─────────────────────────────────────────
      const sist     = localStorage.getItem(_SIST_BACKUP_KEY);
      const dagSiden = sist
        ? Math.floor((Date.now() - new Date(sist).getTime()) / 86_400_000)
        : _DAGER_MELLOM + 1;
      if (dagSiden < _DAGER_MELLOM) return;

      const toast = _lagBackupToast(
        '💾 Ukentlig backup',
        `Det er ${dagSiden} dager siden sist backup av portefølje og favoritter.`,
        'Last ned nå',
        () => { _autoNedlasting(blob); localStorage.setItem(_SIST_BACKUP_KEY, new Date().toISOString()); }
      );
      document.body.appendChild(toast);
    }
  } catch (e) {
    console.warn('initAutoBackup feil:', e);
  }
}


function eksporterEnkeltICS(a, type, dato) {
  const pf = hentPF();
  const datoStr = d => d.replace(/-/g, '');
  const ds = datoStr(dato);
  const neste = new Date(dato); neste.setDate(neste.getDate() + 1);
  const dsNeste = neste.toISOString().slice(0,10).replace(/-/g,'');

  let summary, description;
  if (type === 'ex') {
    summary     = `${a.ticker} Ex-dato`;
    description = `Ex-dato for ${a.navn}. Yield: ${a.utbytte_yield.toFixed(2)}%. Siste utbytte: ${a.siste_utbytte || '—'} ${a.valuta}.`;
  } else if (type === 'utbytte') {
    const belop = pf[a.ticker]
      ? `Estimert utbetaling: ${(pf[a.ticker] * (a.utbytte_per_aksje || 0) / (({Månedlig:12,Kvartalsvis:4,Halvårlig:2,Årlig:1}[a.frekvens]||1))).toLocaleString('nb-NO',{maximumFractionDigits:0})} kr. `
      : '';
    summary     = `${a.ticker} Utbetaling`;
    description = `${belop}Utbyttebetaling fra ${a.navn}.`;
  } else {
    summary     = `${a.ticker} Kvartalsrapport`;
    description = `Kvartalsrapport for ${a.navn}.`;
  }

  const ics = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//exday.no//Utbyttekalender//NO',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    'BEGIN:VEVENT',
    `DTSTART;VALUE=DATE:${ds}`,
    `DTEND;VALUE=DATE:${dsNeste}`,
    `SUMMARY:${summary}`,
    `DESCRIPTION:${description}`,
    `UID:exday-${type}-${a.ticker}-${dato}@exday.no`,
    'END:VEVENT',
    'END:VCALENDAR'
  ].join('\r\n');

  const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const el   = document.createElement('a');
  el.href = url;
  el.download = `${a.ticker}-${type}-${dato}.ics`;
  el.click();
  URL.revokeObjectURL(url);
}


function visModal(a) {
  const overlay = document.getElementById('modal-overlay');
  const body = document.getElementById('modal-body');
  const idag = new Date(); idag.setHours(0,0,0,0);
  const exDato = a.ex_dato ? new Date(a.ex_dato + 'T00:00:00') : null; // lokal midnatt
  const dagerTilEx = exDato ? Math.ceil((exDato - idag) / (1000*60*60*24)) : null;

  body.innerHTML = `
    <div class="flex items-start justify-between mb-4">
      <div>
        <h2 id="modal-aksje-tittel" class="text-2xl font-bold text-brand-700 dark:text-brand-400">${a.ticker}</h2>
        <p class="text-gray-600 dark:text-gray-400">${a.navn}</p>
        <p class="text-xs text-gray-400 mt-0.5">${a.sektor} · ${a.bors}</p>
      </div>
      <div class="flex items-center gap-1">
        ${stjerne(a.ticker, 'p-1 hover:scale-110')}
        <a href="/aksjer/${a.ticker}/" target="_blank" rel="noopener" class="text-gray-400 hover:text-brand-600 dark:hover:text-brand-400 p-1 transition-colors" aria-label="Åpne full aksjesiden" title="Se full aksjesiden">
          <svg class="w-5 h-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
        </a>
        <button id="modal-del" class="text-gray-400 hover:text-brand-600 dark:hover:text-brand-400 p-1 transition-colors" aria-label="Del lenke" title="Kopier lenke">
          <svg class="w-5 h-5" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/></svg>
        </button>
        <button id="modal-close" class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 p-1" aria-label="Lukk">
          <svg class="w-6 h-6" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </div>
    </div>

    ${a.beskrivelse_fakta ? `<div class="om-selskap-boks"><p class="om-selskap-label">Om selskapet</p><p class="om-selskap-tekst">${escHtml(a.beskrivelse_fakta)}</p></div>` : a.beskrivelse ? `<div class="om-selskap-boks"><p class="om-selskap-label">Om selskapet</p><p class="om-selskap-tekst">${escHtml(a.beskrivelse)}</p></div>` : ''}

    ${a.ai_oppsummering ? `<div class="ai-opp-boks"><p class="ai-opp-label">AI-oppsummering${a.ai_oppsummering_dato ? ` <span class="ai-opp-dato">${escHtml(a.ai_oppsummering_dato)}</span>` : ''}</p><p class="ai-opp-tekst">${escHtml(a.ai_oppsummering)}</p></div>` : ''}

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
            ${dagerTilEx !== null && dagerTilEx >= 0 ? ` <span class="text-xs">(${dagerTilEx === 0 ? 'i dag!' : dagerTilEx === 1 ? 'i morgen' : 'om ' + dagerTilEx + ' dager'})</span>` : ''}
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
    ${modalKalkulator(a)}
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

  // Utbytte-kalkulator: live-oppdatering
  const _kalIn = document.getElementById('modal-kal-belop');
  if (_kalIn) {
    _kalIn.addEventListener('input', () => _oppdaterModalKalkulator(a));
    _oppdaterModalKalkulator(a);
  }
}

function modalKalkulator(a) {
  const harData = (a.pris > 0) && (a.utbytte_per_aksje > 0 || a.utbytte_yield > 0);
  if (!harData) return '';
  const fmtKr = v => new Intl.NumberFormat('nb-NO', { style: 'currency', currency: 'NOK', maximumFractionDigits: 0 }).format(v);
  const startBelop = 10000;
  const kurs = a.pris;
  const upa  = a.utbytte_per_aksje || 0;
  const antall = kurs > 0 ? Math.floor(startBelop / kurs) : 0;
  const utbAar = upa > 0 ? antall * upa : (a.utbytte_yield / 100) * (antall * kurs);
  return `
    <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
      <h3 class="text-sm font-semibold text-gray-800 dark:text-gray-200 mb-3">Beregn utbytte</h3>
      <div class="rounded-lg bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 p-4 space-y-3">
        <div class="flex items-center gap-3">
          <label class="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">Invester (kr)</label>
          <input id="modal-kal-belop" type="number" min="1" step="1000" value="${startBelop}"
            class="filter-input flex-1 text-right font-semibold" />
        </div>
        <div class="grid grid-cols-3 gap-2 text-center text-xs">
          <div class="rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-2.5">
            <p class="text-gray-400 mb-0.5">Antall aksjer</p>
            <p id="modal-kal-antall" class="font-bold text-brand-600 dark:text-brand-400 text-base">${antall}</p>
            <p id="modal-kal-kurs" class="text-gray-400 mt-0.5">@ ${fmt(kurs)} ${a.valuta}</p>
          </div>
          <div class="rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-2.5">
            <p class="text-gray-400 mb-0.5">Utbytte / år</p>
            <p id="modal-kal-aar" class="font-bold text-green-600 dark:text-green-400 text-base">${fmtKr(utbAar)}</p>
            <p id="modal-kal-mnd" class="text-gray-400 mt-0.5">${fmtKr(utbAar / 12)} / mnd</p>
          </div>
          <div class="rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 p-2.5">
            <p class="text-gray-400 mb-0.5">Etter skatt</p>
            <p id="modal-kal-netto" class="font-bold text-gray-700 dark:text-gray-300 text-base">${fmtKr(utbAar * 0.6216)}</p>
            <p class="text-gray-400 mt-0.5">37,84% skatt</p>
          </div>
        </div>
      </div>
    </div>`;
}

function _oppdaterModalKalkulator(a) {
  const input   = document.getElementById('modal-kal-belop');
  const antallEl = document.getElementById('modal-kal-antall');
  const aarEl   = document.getElementById('modal-kal-aar');
  const mndEl   = document.getElementById('modal-kal-mnd');
  const nettoEl = document.getElementById('modal-kal-netto');
  if (!input || !antallEl) return;

  const fmtKr = v => new Intl.NumberFormat('nb-NO', { style: 'currency', currency: 'NOK', maximumFractionDigits: 0 }).format(v);
  const belop  = parseFloat(input.value) || 0;
  const kurs   = a.pris || 0;
  const upa    = a.utbytte_per_aksje || 0;
  const antall = kurs > 0 ? Math.floor(belop / kurs) : 0;
  const utbAar = upa > 0 ? antall * upa : (a.utbytte_yield / 100) * (antall * kurs);

  antallEl.textContent = new Intl.NumberFormat('nb-NO').format(antall);
  aarEl.textContent    = fmtKr(utbAar);
  mndEl.textContent    = fmtKr(utbAar / 12) + ' / mnd';
  nettoEl.textContent  = fmtKr(utbAar * 0.6216);
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
  overlay.addEventListener('click', e => { if (e.target.closest('#modal-close')) lukkModal(); });
  // Del-knapp: kopier ?aksje= URL til clipboard
  overlay.addEventListener('click', e => {
    if (!e.target.closest('#modal-del')) return;
    const url = location.origin + location.pathname + location.search;
    navigator.clipboard.writeText(url).then(() => {
      const btn = e.target.closest('#modal-del');
      const orig = btn.innerHTML;
      btn.innerHTML = '<span class="text-xs font-semibold text-brand-600 dark:text-brand-400 px-1">Kopiert!</span>';
      setTimeout(() => { btn.innerHTML = orig; }, 2000);
    });
  });
  // Favoritt-toggle i modal
  overlay.addEventListener('click', e => {
    const btn = e.target.closest('.fav-btn');
    if (!btn) return;
    toggleFav(btn.dataset.ticker);
    oppdaterFavBtn();
    // Re-render stjernen inne i modal uten å lukke
    visModal(alleAksjer.find(x => x.ticker === btn.dataset.ticker));
  });
  // ESC lukker alle modaler
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    // Aksje-modal
    const aksjeModal = document.getElementById('modal-overlay');
    if (aksjeModal && !aksjeModal.classList.contains('hidden')) { lukkModal(); return; }
    // Del-modal
    const delModal = document.getElementById('del-modal');
    if (delModal && !delModal.classList.contains('hidden')) { delModal.classList.add('hidden'); delModal.classList.remove('flex'); return; }
    // Velkommen-modal
    const velkModal = document.getElementById('velkommen-modal');
    if (velkModal && velkModal.classList.contains('flex')) { velkModal.classList.remove('flex'); velkModal.classList.add('hidden'); return; }
    // QR-modal
    const qrModal = document.getElementById('qr-modal');
    if (qrModal && qrModal.classList.contains('flex')) { qrModal.classList.remove('flex'); qrModal.classList.add('hidden'); }
  });
}

function modalKort(label, value) {
  return `<div class="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
    <p class="text-xs text-gray-400 mb-1">${label}</p>
    <p class="font-semibold">${value}</p>
  </div>`;
}


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

function beregnBaerekraft(a) {
  let poeng = 0, maks = 0;

  // Payout ratio (0-4p): hjertet av bærekraft
  if (a.payout_ratio > 0) {
    maks += 4;
    if      (a.payout_ratio <= 40) poeng += 4;
    else if (a.payout_ratio <= 60) poeng += 3;
    else if (a.payout_ratio <= 75) poeng += 2;
    else if (a.payout_ratio <= 90) poeng += 1;
  }

  // Utbyttevekst 5 år (0-3p)
  if (a.utbytte_vekst_5ar != null) {
    maks += 3;
    const v = a.utbytte_vekst_5ar;
    if      (v > 8)  poeng += 3;
    else if (v > 0)  poeng += 2;
    else if (v > -5) poeng += 1;
  }

  // År med utbytte (0-2p)
  maks += 2;
  const ar = a.ar_med_utbytte || 0;
  if      (ar >= 10) poeng += 2;
  else if (ar >= 5)  poeng += 1;

  // Yield-konsistens vs 5-år snitt (0-1p)
  if (a.snitt_yield_5ar > 0 && a.utbytte_yield > 0) {
    maks += 1;
    if (Math.abs(a.utbytte_yield - a.snitt_yield_5ar) / a.snitt_yield_5ar <= 0.35) poeng += 1;
  }

  if (maks === 0) return null;
  const pct = poeng / maks;
  if (pct >= 0.70) return { grad: 'Trygg',    farge: 'text-teal-600 dark:text-teal-400',   bg: 'bg-teal-50 dark:bg-teal-900/30',   poeng, maks };
  if (pct >= 0.45) return { grad: 'Moderat',  farge: 'text-blue-600 dark:text-blue-400',   bg: 'bg-blue-50 dark:bg-blue-900/30',   poeng, maks };
  return             { grad: 'Svak',     farge: 'text-red-500 dark:text-red-400',     bg: 'bg-red-50 dark:bg-red-900/30',     poeng, maks };
}

function baerekraftVisning(a) {
  const b = beregnBaerekraft(a);
  if (!b) return '';
  const po = a.payout_ratio;
  const v  = a.utbytte_vekst_5ar;
  const ar = a.ar_med_utbytte || 0;
  const snitt = a.snitt_yield_5ar || 0;

  const linje = (label, verdi, ok) =>
    `<div class="flex justify-between items-center py-1 border-b border-gray-100 dark:border-gray-800 last:border-0">
       <span class="text-xs text-gray-500 dark:text-gray-400">${label}</span>
       <span class="text-xs font-medium ${ok ? 'text-teal-600 dark:text-teal-400' : 'text-red-500 dark:text-red-400'}">${verdi}</span>
     </div>`;

  return `
    <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
      <div class="flex justify-between items-center mb-2">
        <span class="text-sm font-semibold">Bærekraft-analyse</span>
        <span class="text-xs font-semibold px-2 py-0.5 rounded-full ${b.bg} ${b.farge}">${b.grad}</span>
      </div>
      <div class="bg-gray-50 dark:bg-gray-800/50 rounded-lg p-3 space-y-0">
        ${linje('Payout ratio',      po > 0 ? po.toFixed(0)+'%' : '—',   po > 0 && po <= 75)}
        ${linje('Utbyttevekst 5 år', v != null ? (v>=0?'+':'')+v.toFixed(1)+'%' : '—', v != null && v > 0)}
        ${linje('År med utbytte',    ar > 0 ? ar+' år' : '—',            ar >= 5)}
        ${linje('Yield-konsistens',  snitt > 0 ? 'snitt '+snitt.toFixed(1)+'%' : '—', snitt > 0 && Math.abs((a.utbytte_yield||0) - snitt) / snitt <= 0.35)}
      </div>
    </div>`;
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
    </div>
    ${baerekraftVisning(a)}`;
}

function visScoreInfoModal() {
  const overlay = document.getElementById('modal-overlay');
  const body    = document.getElementById('modal-body');
  body.innerHTML = `
    <div class="flex items-start justify-between mb-4">
      <h2 class="text-lg font-bold">Utbytte-score — slik beregnes den</h2>
      <button id="modal-close" class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 p-1" aria-label="Lukk">
        <svg class="w-6 h-6" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
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


function initKalkulator() {
  document.getElementById('kal-beregn').addEventListener('click', beregnKalkulator);

  // Avansert-toggle
  document.getElementById('kal-avansert-toggle').addEventListener('click', () => {
    const panel = document.getElementById('kal-avansert');
    const ikon  = document.getElementById('kal-avansert-ikon');
    const aapen = panel.classList.toggle('hidden');
    ikon.style.transform = aapen ? '' : 'rotate(90deg)';
  });

  // Portefølje-knapp
  document.getElementById('kal-bruk-pf').addEventListener('click', brukPortefoljeData);

  // Beregn automatisk ved endring
  ['kal-startbelop','kal-yield','kal-ar','kal-vekst','kal-sparing','kal-reinvester',
   'kal-skatt-aktiv','kal-skattesats','kal-inflasjon-aktiv','kal-inflasjon']
    .forEach(id => document.getElementById(id).addEventListener('input', beregnKalkulator));
  beregnKalkulator();
}

function brukPortefoljeData() {
  const pf = hentPF();
  const tickers = Object.keys(pf);
  if (!tickers.length || !alleAksjer.length) {
    document.getElementById('kal-pf-info').textContent = 'Ingen porteføljedata — legg til aksjer i Portefølje-fanen først.';
    document.getElementById('kal-pf-info').classList.remove('hidden');
    return;
  }

  let totalVerdi = 0, totalAr = 0, antallAksjer = 0;
  tickers.forEach(ticker => {
    const a = alleAksjer.find(x => x.ticker === ticker);
    const antall = pf[ticker];
    if (!a || antall < 1) return;
    const verdi = antall * (a.pris || 0);
    totalVerdi += verdi;
    totalAr    += antall * (a.utbytte_per_aksje || 0);
    antallAksjer++;
  });

  if (totalVerdi <= 0) {
    document.getElementById('kal-pf-info').textContent = 'Mangler kursinformasjon for porteføljen. Prøv igjen om litt.';
    document.getElementById('kal-pf-info').classList.remove('hidden');
    return;
  }

  const vektetYield = (totalAr / totalVerdi * 100);

  document.getElementById('kal-startbelop').value = Math.round(totalVerdi);
  document.getElementById('kal-yield').value = vektetYield.toFixed(2);

  const info = document.getElementById('kal-pf-info');
  info.textContent = `Hentet fra portefølje: ${antallAksjer} selskaper · markedsverdi ${Math.round(totalVerdi).toLocaleString('nb-NO')} kr · vektet yield ${vektetYield.toFixed(2)}%`;
  info.classList.remove('hidden');

  beregnKalkulator();
}

function _simulerKalkulator(startbelop, yieldFaktor, vekstFaktor, sparingAr, antallAr, medDRIP, skattFaktor, inflasjonFaktor) {
  let verdi = startbelop;
  let totUtbytte = 0, totUtbytteNetto = 0, totSkatt = 0, totInnbetalt = startbelop;
  const rader = [];
  for (let ar = 1; ar <= antallAr; ar++) {
    const baseForUtbytte = verdi + sparingAr * 0.5;
    const utbytteIAr     = baseForUtbytte * yieldFaktor;
    const skattIAr       = utbytteIAr * skattFaktor;
    const utbytteNetto   = utbytteIAr - skattIAr;
    verdi += sparingAr;
    if (medDRIP) verdi += utbytteNetto;   // reinvester kun etter skatt
    verdi = verdi * (1 + vekstFaktor);
    totUtbytte      += utbytteIAr;
    totUtbytteNetto += utbytteNetto;
    totSkatt        += skattIAr;
    totInnbetalt    += sparingAr;
    // Realverdi: deflatér med kumulert inflasjon
    const realFaktor = Math.pow(1 + inflasjonFaktor, ar);
    rader.push({ ar, verdi, verdiReal: verdi / realFaktor, utbytteIAr, utbytteNetto, totUtbytte });
  }
  return { rader, totUtbytte, totUtbytteNetto, totSkatt, totInnbetalt, verdi };
}

function tegneKalkulatorGraf(raderMed, raderUten) {
  const el = document.getElementById('kal-graf');
  if (!el) return;
  const W = 560, H = 180;
  const PAD = { top: 12, right: 16, bottom: 28, left: 58 };
  const iW = W - PAD.left - PAD.right;
  const iH = H - PAD.top - PAD.bottom;
  const n  = raderMed.length;
  const maxVal = Math.max(...raderMed.map(r => r.verdi));

  const xS = i  => PAD.left + (n > 1 ? (i / (n - 1)) : 0.5) * iW;
  const yS = v  => PAD.top + iH - (v / maxVal) * iH;
  const pts = r => r.map((p, i) => `${xS(i).toFixed(1)},${yS(p.verdi).toFixed(1)}`).join(' ');

  const fmtY = v => v >= 1e6 ? (v/1e6).toFixed(1)+'M' : v >= 1e3 ? Math.round(v/1e3)+'k' : v.toFixed(0);

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map(f => {
    const v = maxVal * f, y = yS(v).toFixed(1);
    return `<line x1="${PAD.left}" y1="${y}" x2="${W - PAD.right}" y2="${y}" stroke="currentColor" stroke-opacity="0.08" stroke-width="1"/>
            <text x="${PAD.left - 5}" y="${y}" text-anchor="end" dominant-baseline="middle" font-size="9" fill="currentColor" opacity="0.45">${fmtY(v)}</text>`;
  }).join('');

  const step = Math.max(1, Math.floor(n / 5));
  const xLabels = raderMed
    .filter((_, i) => i === 0 || (i + 1) % step === 0 || i === n - 1)
    .map(r => `<text x="${xS(r.ar - 1).toFixed(1)}" y="${H - PAD.bottom + 13}" text-anchor="middle" font-size="9" fill="currentColor" opacity="0.45">År ${r.ar}</text>`)
    .join('');

  el.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" class="w-full" style="max-height:190px">
      ${gridLines}
      <polyline points="${pts(raderUten)}" fill="none" stroke="#94a3b8" stroke-width="2" stroke-dasharray="6,3"/>
      <polyline points="${pts(raderMed)}"  fill="none" stroke="#2563eb" stroke-width="2.5"/>
      ${xLabels}
      <line x1="${PAD.left}" y1="${H-6}" x2="${PAD.left+18}" y2="${H-6}" stroke="#2563eb" stroke-width="2.5"/>
      <text x="${PAD.left+22}" y="${H-3}" font-size="9" fill="currentColor" opacity="0.65">Med DRIP</text>
      <line x1="${PAD.left+80}" y1="${H-6}" x2="${PAD.left+98}" y2="${H-6}" stroke="#94a3b8" stroke-width="2" stroke-dasharray="6,3"/>
      <text x="${PAD.left+102}" y="${H-3}" font-size="9" fill="currentColor" opacity="0.65">Uten DRIP</text>
    </svg>`;
}

function beregnKalkulator() {
  const startbelop   = Math.max(0, parseFloat(document.getElementById('kal-startbelop').value) || 0);
  const yieldPct     = Math.max(0, Math.min(50, parseFloat(document.getElementById('kal-yield').value) || 0));
  const antallAr     = Math.max(1, Math.min(40, parseInt(document.getElementById('kal-ar').value) || 1));
  const vekstPct     = Math.max(0, Math.min(30, parseFloat(document.getElementById('kal-vekst').value) || 0));
  const sparingMnd   = Math.max(0, parseFloat(document.getElementById('kal-sparing').value) || 0);
  const reinvester   = document.getElementById('kal-reinvester').checked;
  const skattAktiv   = document.getElementById('kal-skatt-aktiv').checked;
  const skattPct     = Math.max(0, Math.min(60, parseFloat(document.getElementById('kal-skattesats').value) || 37.84));
  const inflAktiv    = document.getElementById('kal-inflasjon-aktiv').checked;
  const inflPct      = Math.max(0, Math.min(20, parseFloat(document.getElementById('kal-inflasjon').value) || 2.5));

  if (startbelop <= 0 && sparingMnd <= 0) return;

  const fmtKr        = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';
  const yieldFaktor  = yieldPct / 100;
  const vekstFaktor  = vekstPct / 100;
  const sparingAr    = sparingMnd * 12;
  const skattFaktor  = skattAktiv ? skattPct / 100 : 0;
  const inflFaktor   = inflAktiv  ? inflPct  / 100 : 0;

  const med   = _simulerKalkulator(startbelop, yieldFaktor, vekstFaktor, sparingAr, antallAr, true,  skattFaktor, inflFaktor);
  const uten  = _simulerKalkulator(startbelop, yieldFaktor, vekstFaktor, sparingAr, antallAr, false, skattFaktor, inflFaktor);
  const aktiv = reinvester ? med : uten;
  const sisteRad = aktiv.rader[aktiv.rader.length - 1];

  document.getElementById('kal-res-ar').textContent        = antallAr;
  document.getElementById('kal-res-ar2').textContent       = antallAr;
  document.getElementById('kal-res-verdi').textContent     = fmtKr(aktiv.verdi);
  document.getElementById('kal-res-utbytte').textContent   = fmtKr(aktiv.totUtbytte);
  document.getElementById('kal-res-innbetalt').textContent = fmtKr(aktiv.totInnbetalt);
  document.getElementById('kal-res-mnd').textContent       = fmtKr(sisteRad.utbytteIAr / 12);
  document.getElementById('kal-res-drip').textContent      = fmtKr(med.verdi - uten.verdi);

  // Inflasjonsjustert verdi
  const verdiRealEl = document.getElementById('kal-res-verdi-real');
  if (inflAktiv && inflFaktor > 0) {
    verdiRealEl.textContent = `≈ ${fmtKr(sisteRad.verdiReal)} i dagens kroneverdi`;
    verdiRealEl.classList.remove('hidden');
  } else {
    verdiRealEl.classList.add('hidden');
  }

  // Etter-skatt utbytte
  const utbytteNettoEl = document.getElementById('kal-res-utbytte-netto');
  const mndNettoEl     = document.getElementById('kal-res-mnd-netto');
  if (skattAktiv) {
    utbytteNettoEl.textContent = `${fmtKr(aktiv.totUtbytteNetto)} etter skatt`;
    utbytteNettoEl.classList.remove('hidden');
    mndNettoEl.textContent = `${fmtKr(sisteRad.utbytteNetto / 12)} etter skatt`;
    mndNettoEl.classList.remove('hidden');
  } else {
    utbytteNettoEl.classList.add('hidden');
    mndNettoEl.classList.add('hidden');
  }

  // Skatt-kort
  const skattKort = document.getElementById('kal-res-skatt-kort');
  if (skattAktiv) {
    document.getElementById('kal-res-skatt').textContent = fmtKr(aktiv.totSkatt);
    skattKort.classList.remove('hidden');
  } else {
    skattKort.classList.add('hidden');
  }

  // Etter-skatt kolonne i tabell
  const thNetto = document.getElementById('kal-th-netto');
  if (skattAktiv) thNetto.classList.remove('hidden'); else thNetto.classList.add('hidden');

  tegneKalkulatorGraf(med.rader, uten.rader);

  document.getElementById('kal-tabell').innerHTML = aktiv.rader.map(r => `
    <tr class="hover:bg-gray-50 dark:hover:bg-gray-800/50">
      <td class="px-4 py-2 text-gray-500 dark:text-gray-400">${r.ar}</td>
      <td class="px-4 py-2 text-right font-medium">${fmtKr(r.verdi)}${inflAktiv ? `<span class="block text-xs text-gray-400">${fmtKr(r.verdiReal)}</span>` : ''}</td>
      <td class="px-4 py-2 text-right text-green-600 dark:text-green-400">${fmtKr(r.utbytteIAr)}</td>
      ${skattAktiv ? `<td class="px-4 py-2 text-right text-amber-600 dark:text-amber-400">${fmtKr(r.utbytteNetto)}</td>` : ''}
      <td class="px-4 py-2 text-right text-gray-500 dark:text-gray-400">${fmtKr(r.totUtbytte)}</td>
    </tr>`).join('');

  document.getElementById('kal-resultat').classList.remove('hidden');
}


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


let _priserCache = null;
let _priserCacheTs = 0;

async function hentPriser() {
  const now = Date.now();
  if (_priserCache && now - _priserCacheTs < 5 * 60 * 1000) return _priserCache;
  try {
    const r = await fetch('data/priser.json');
    if (!r.ok) return null;
    _priserCache = await r.json();
    _priserCacheTs = now;
    return _priserCache;
  } catch { return null; }
}

async function visDagensBevegelser() {
  const el = document.getElementById('dagens-bevegelser');
  const tomEl = document.getElementById('bevegelser-tom');
  if (!el || !alleAksjer.length) return;

  const data = await hentPriser();
  if (!data || !data.aksjer) {
    el.innerHTML = '';
    if (tomEl) tomEl.classList.remove('hidden');
    return;
  }
  if (tomEl) tomEl.classList.add('hidden');

  const aksjerMap = Object.fromEntries(alleAksjer.map(a => [a.ticker, a]));

  const bevegelser = Object.entries(data.aksjer)
    .map(([ticker, p]) => ({ ticker, ...p, aksje: aksjerMap[ticker] }))
    .filter(b => b.aksje && (b.endring_pct !== 0 || b.endring_krs !== 0));

  if (!bevegelser.length) { el.classList.add('hidden'); return; }

  const sorted = [...bevegelser].sort((a, b) => b.endring_pct - a.endring_pct);
  const gainers = sorted.slice(0, 5).filter(b => b.endring_pct > 0);
  const losers = sorted.slice(-5).reverse().filter(b => b.endring_pct < 0);

  if (!gainers.length && !losers.length) {
    el.innerHTML = '';
    if (tomEl) tomEl.classList.remove('hidden');
    return;
  }

  const radHtml = (b, pos) => {
    const pctTxt = (pos ? '+' : '') + b.endring_pct.toFixed(2) + '%';
    const pctCls = pos ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400';
    const tickerCls = pos ? 'text-green-700 dark:text-green-300' : 'text-red-600 dark:text-red-400';
    const ikon = pos ? '▲' : '▼';
    return `<div class="bevegelse-rad flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer transition-colors" data-ticker="${b.ticker}">
      <span class="font-mono font-bold text-sm w-14 shrink-0 ${tickerCls}">${b.ticker}</span>
      <span class="text-xs text-gray-500 dark:text-gray-400 flex-1 truncate">${b.aksje.navn}</span>
      <span class="text-xs text-gray-400 dark:text-gray-500 shrink-0">${b.pris.toLocaleString('nb-NO', { maximumFractionDigits: 2 })}</span>
      <span class="text-xs font-semibold w-16 text-right shrink-0 ${pctCls}">${ikon} ${pctTxt}</span>
    </div>`;
  };

  const ts = data.oppdatert
    ? new Date(data.oppdatert).toLocaleTimeString('nb-NO', { hour: '2-digit', minute: '2-digit' })
    : '';

  el.innerHTML = `
    <div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3 shadow-sm">
      <div class="flex items-center justify-between mb-2">
        <p class="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500">Dagens bevegelser</p>
        ${ts ? `<span class="text-xs text-gray-400 dark:text-gray-600">Oppdatert ${ts}</span>` : ''}
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
        ${gainers.length ? `
          <div>
            <p class="text-xs font-medium text-green-600 dark:text-green-400 mb-0.5 px-2">Vinnere</p>
            ${gainers.map(b => radHtml(b, true)).join('')}
          </div>` : ''}
        ${losers.length ? `
          <div class="${gainers.length ? 'mt-2 sm:mt-0' : ''}">
            <p class="text-xs font-medium text-red-500 dark:text-red-400 mb-0.5 px-2">Tapere</p>
            ${losers.map(b => radHtml(b, false)).join('')}
          </div>` : ''}
      </div>
    </div>`;

  el.querySelectorAll('[data-ticker]').forEach(kort => {
    kort.addEventListener('click', () => {
      const aksje = alleAksjer.find(a => a.ticker === kort.dataset.ticker);
      if (aksje) visModal(aksje);
    });
  });
}



function sjekkQRParam() {
  const params = new URLSearchParams(location.search);
  const raw = params.get('pf');
  if (!raw) return;
  history.replaceState(null, '', location.pathname);
  try {
    const payload = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(raw), c => c.charCodeAt(0))));
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
  const encoded = btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(payload))));
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
  if (!container) return;
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


// ── SAMMENLIGNINGSVERKTØY ─────────────────────────────────────────────────────
let sammenlignBasket = [];

function toggleSammenlign(ticker) {
  const idx = sammenlignBasket.indexOf(ticker);
  if (idx >= 0) {
    sammenlignBasket.splice(idx, 1);
  } else {
    if (sammenlignBasket.length >= 3) sammenlignBasket.shift();
    sammenlignBasket.push(ticker);
  }
  oppdaterSammenlignSkuff();
  document.querySelectorAll(`.sammenlign-btn[data-ticker="${ticker}"]`).forEach(btn => {
    const aktiv = sammenlignBasket.includes(ticker);
    btn.classList.toggle('text-brand-600',       aktiv);
    btn.classList.toggle('dark:text-brand-400',  aktiv);
    btn.classList.toggle('border-brand-500',     aktiv);
    btn.classList.toggle('bg-brand-50',          aktiv);
    btn.classList.toggle('dark:bg-brand-900/20', aktiv);
    btn.title     = aktiv ? 'Fjern fra sammenligning' : 'Sammenlign';
    btn.setAttribute('aria-label', aktiv ? 'Fjern fra sammenligning' : 'Legg til i sammenligning');
  });
}

function oppdaterSammenlignSkuff() {
  const skuff = document.getElementById('sammenlign-skuff');
  if (!skuff) return;
  if (sammenlignBasket.length === 0) { skuff.classList.add('hidden'); return; }
  skuff.classList.remove('hidden');
  const valgteEl = document.getElementById('sammenlign-valgte');
  valgteEl.innerHTML = sammenlignBasket.map(t => `
    <span class="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 pl-2.5 pr-1.5 py-1 rounded-full text-sm font-mono font-semibold text-brand-700 dark:text-brand-400">
      ${escHtml(t)}
      <button class="sammenlign-fjern-btn text-gray-400 hover:text-red-500 leading-none text-base ml-0.5" data-ticker="${escHtml(t)}" aria-label="Fjern ${escHtml(t)}">×</button>
    </span>`).join('');
  valgteEl.onclick = e => {
    const btn = e.target.closest('.sammenlign-fjern-btn');
    if (btn) { e.stopPropagation(); toggleSammenlign(btn.dataset.ticker); }
  };
  document.getElementById('sammenlign-vis').disabled = sammenlignBasket.length < 2;
}

function visKomparasjonsModal() {
  const aksjer = sammenlignBasket.map(t => alleAksjer.find(a => a.ticker === t)).filter(Boolean);
  if (aksjer.length < 2) return;

  const RADER = [
    { label: 'Kurs',            fn: a => fmt(a.pris) + ' ' + a.valuta },
    { label: 'Yield',           fn: a => `<span class="${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span>` },
    { label: 'Utbytte/aksje',   fn: a => fmt(a.utbytte_per_aksje) + ' ' + a.valuta },
    { label: 'Payout ratio',    fn: a => a.payout_ratio > 0 ? `<span class="${payoutKlasse(a.payout_ratio)}">${a.payout_ratio.toFixed(0)}%</span>` : '—' },
    { label: 'Vekst 5år',       fn: a => a.utbytte_vekst_5ar !== 0 ? `<span class="${vekstKlasse(a.utbytte_vekst_5ar)}">${a.utbytte_vekst_5ar > 0 ? '+' : ''}${a.utbytte_vekst_5ar.toFixed(1)}%</span>` : '—' },
    { label: 'Snitt yield 5år', fn: a => a.snitt_yield_5ar > 0 ? `<span class="${yieldKlasse(a.snitt_yield_5ar)}">${a.snitt_yield_5ar.toFixed(1)}%</span>` : '—' },
    { label: 'P/E',             fn: a => a.pe_ratio > 0 ? a.pe_ratio.toFixed(1) : '—' },
    { label: 'P/B',             fn: a => a.pb_ratio > 0 ? a.pb_ratio.toFixed(1) : '—' },
    { label: 'Score',           fn: a => scoreBadge(beregnScore(a)) },
    { label: 'År m/utbytte',    fn: a => a.ar_med_utbytte > 0 ? a.ar_med_utbytte + ' år' : '—' },
    { label: 'Markedsverdi',    fn: a => a.markedsverdi_mrd > 0 ? a.markedsverdi_mrd.toFixed(1) + ' mrd kr' : '—' },
    { label: 'Sektor',          fn: a => a.sektor },
    { label: 'Frekvens',        fn: a => `<span class="frekvens-badge">${a.frekvens}</span>` },
    { label: 'Ex-dato',         fn: a => a.ex_dato ? formaterDato(a.ex_dato) : '—' },
    { label: 'Betalingsdato',   fn: a => a.betaling_dato ? formaterDato(a.betaling_dato) : '—' },
  ];

  document.getElementById('sammenlign-modal-body').innerHTML = `
    <table class="w-full text-sm min-w-[360px]">
      <thead>
        <tr class="border-b border-gray-100 dark:border-gray-800">
          <th class="text-left py-2 pr-4 text-xs font-semibold uppercase tracking-wide text-gray-400 w-28 sm:w-36"></th>
          ${aksjer.map(a => `
            <th class="py-2 px-2 text-center">
              <div class="font-mono font-bold text-brand-700 dark:text-brand-400">${a.ticker}</div>
              <div class="text-xs text-gray-400 font-normal mt-0.5 hidden sm:block truncate max-w-[110px] mx-auto">${a.navn}</div>
            </th>`).join('')}
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-50 dark:divide-gray-800/50">
        ${RADER.map(r => `
          <tr class="hover:bg-gray-50 dark:hover:bg-gray-800/30">
            <td class="py-2 pr-4 text-xs text-gray-500 dark:text-gray-400 font-medium">${r.label}</td>
            ${aksjer.map(a => `<td class="py-2 px-2 text-center">${r.fn(a)}</td>`).join('')}
          </tr>`).join('')}
      </tbody>
    </table>
    <p class="text-xs text-gray-400 mt-4 text-center">Del: <a href="?sammenlign=${sammenlignBasket.join(',')}" class="text-brand-600 hover:underline">${location.origin}?sammenlign=${sammenlignBasket.join(',')}</a></p>`;

  const modal = document.getElementById('sammenlign-modal');
  modal.classList.remove('hidden');
  modal.classList.add('flex');
  document.body.style.overflow = 'hidden';
}

function initSammenligning() {
  // Hint-knapp i mobil-sort-rad: åpner skuffen og viser en toast om funksjonen
  document.getElementById('mobil-sammenlign-hint')?.addEventListener('click', () => {
    const skuff = document.getElementById('sammenlign-skuff');
    if (sammenlignBasket.length >= 2) {
      visKomparasjonsModal();
    } else {
      // Finn første tilgjengelige sammenlign-knapp og animér den
      const forsteBtn = document.querySelector('.sammenlign-btn[data-ticker]');
      if (forsteBtn) {
        forsteBtn.classList.add('ring-2', 'ring-brand-500', 'ring-offset-1');
        forsteBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(() => forsteBtn.classList.remove('ring-2', 'ring-brand-500', 'ring-offset-1'), 1800);
      }
      // Vis kort melding
      let toast = document.getElementById('sammenlign-toast');
      if (!toast) {
        toast = document.createElement('div');
        toast.id = 'sammenlign-toast';
        toast.className = 'fixed bottom-20 left-1/2 -translate-x-1/2 z-50 bg-gray-900 dark:bg-gray-700 text-white text-sm px-4 py-2 rounded-full shadow-lg pointer-events-none transition-opacity';
        document.body.appendChild(toast);
      }
      toast.textContent = 'Trykk ⚖ på en aksje for å sammenligne';
      toast.style.opacity = '1';
      setTimeout(() => { toast.style.opacity = '0'; }, 2500);
    }
  });

  document.getElementById('sammenlign-vis')?.addEventListener('click', visKomparasjonsModal);
  document.getElementById('sammenlign-tom')?.addEventListener('click', () => {
    sammenlignBasket = [];
    oppdaterSammenlignSkuff();
    visOversikt();
  });
  const lukkModal = () => {
    document.getElementById('sammenlign-modal').classList.add('hidden');
    document.getElementById('sammenlign-modal').classList.remove('flex');
    document.body.style.overflow = '';
  };
  document.getElementById('sammenlign-modal-lukk')?.addEventListener('click', lukkModal);
  document.getElementById('sammenlign-modal')?.addEventListener('click', e => {
    if (e.target === e.currentTarget) lukkModal();
  });

  // URL-param: ?sammenlign=EQNR,DNB,ORK
  const param = new URLSearchParams(location.search).get('sammenlign');
  if (param) {
    param.split(',').slice(0, 3).forEach(t => {
      const upper = t.trim().toUpperCase();
      if (upper && !sammenlignBasket.includes(upper)) sammenlignBasket.push(upper);
    });
    if (sammenlignBasket.length >= 2) window._pendingKomparasjon = true;
  }
}

// --- ANNONSERT UTBYTTE-KALKULATOR ---

let _annValgtAksje = null;
let _annInitiert = false;

function initAnnonsertKalkulator() {
  if (_annInitiert) { _annOppdaterResultat(); return; }
  _annInitiert = true;

  const sokEl     = document.getElementById('ann-sok');
  const forslagEl = document.getElementById('ann-forslag');
  const nullstillEl = document.getElementById('ann-nullstill');
  const belopEl   = document.getElementById('ann-belop');

  function lukkForslag() { forslagEl.classList.add('hidden'); }

  function visForslag(tekst) {
    const t = tekst.trim().toLowerCase();
    const alle = window.alleAksjer || [];
    const treff = alle
      .filter(a => a.ticker.toLowerCase().includes(t) || (a.navn || '').toLowerCase().includes(t))
      .slice(0, 12);

    if (!treff.length) { lukkForslag(); return; }

    forslagEl.innerHTML = treff.map(a => {
      const yield_ = a.utbytte_yield || 0;
      const yieldStr = yield_ > 0 ? `<span class="text-green-600 dark:text-green-400 font-medium">${yield_.toFixed(1)}%</span>` : '<span class="text-gray-400">—</span>';
      return `<li class="flex items-center justify-between px-3 py-2 hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
                  data-ticker="${escHtml(a.ticker)}">
        <span><span class="font-semibold">${escHtml(a.ticker)}</span> <span class="text-gray-500 dark:text-gray-400 text-xs">${escHtml(a.navn || '')}</span></span>
        ${yieldStr}
      </li>`;
    }).join('');
    forslagEl.classList.remove('hidden');
  }

  function velgAksje(ticker) {
    const alle = window.alleAksjer || [];
    _annValgtAksje = alle.find(a => a.ticker === ticker) || null;
    if (_annValgtAksje) {
      sokEl.value = `${_annValgtAksje.ticker} — ${_annValgtAksje.navn || ''}`;
      nullstillEl.classList.remove('hidden');
    }
    lukkForslag();
    _annOppdaterResultat();
    _annBygTopp();
  }

  sokEl.addEventListener('input', () => {
    _annValgtAksje = null;
    nullstillEl.classList.add('hidden');
    document.getElementById('ann-resultat').classList.add('hidden');
    document.getElementById('ann-ingen').classList.add('hidden');
    visForslag(sokEl.value);
  });

  sokEl.addEventListener('keydown', e => {
    if (e.key === 'Escape') lukkForslag();
  });

  forslagEl.addEventListener('click', e => {
    const li = e.target.closest('li[data-ticker]');
    if (li) velgAksje(li.dataset.ticker);
  });

  nullstillEl.addEventListener('click', () => {
    _annValgtAksje = null;
    sokEl.value = '';
    nullstillEl.classList.add('hidden');
    document.getElementById('ann-resultat').classList.add('hidden');
    document.getElementById('ann-ingen').classList.add('hidden');
    sokEl.focus();
  });

  belopEl.addEventListener('input', _annOppdaterResultat);

  document.addEventListener('click', e => {
    if (!sokEl.contains(e.target) && !forslagEl.contains(e.target)) lukkForslag();
  });

  _annBygTopp();
}

function _annOppdaterResultat() {
  const a = _annValgtAksje;
  const resultatEl = document.getElementById('ann-resultat');
  const ingenEl    = document.getElementById('ann-ingen');
  if (!a) { resultatEl.classList.add('hidden'); ingenEl.classList.add('hidden'); return; }

  const belop  = parseFloat(document.getElementById('ann-belop').value) || 0;
  const kurs   = a.pris || a.kurs || 0;
  const upa    = a.utbytte_per_aksje || 0;
  const yield_ = a.utbytte_yield || 0;
  const snitt5 = a.snitt_yield_5ar || 0;
  const ex     = a.ex_dato || a.neste_ex_dato || '';
  const valuta = a.valuta || 'NOK';

  if (kurs <= 0 && upa <= 0) {
    resultatEl.classList.add('hidden');
    ingenEl.classList.remove('hidden');
    return;
  }

  const antall       = kurs > 0 ? Math.floor(belop / kurs) : 0;
  const faktiskBelop = antall * kurs;
  const utbytteAar   = upa > 0 ? antall * upa : (yield_ / 100) * faktiskBelop;
  const utbytteMnd   = utbytteAar / 12;
  const netto        = utbytteAar * (1 - 0.3784);
  const effYield     = faktiskBelop > 0 ? (utbytteAar / faktiskBelop) * 100 : yield_;

  const fmtKr = v => new Intl.NumberFormat('nb-NO', { style: 'currency', currency: 'NOK', maximumFractionDigits: 0 }).format(v);
  const fmtTall = v => new Intl.NumberFormat('nb-NO', { maximumFractionDigits: 2 }).format(v);

  document.getElementById('ann-res-antall').textContent = fmtTall(antall);
  document.getElementById('ann-res-kurs').textContent   = kurs > 0 ? `@ ${fmtTall(kurs)} ${valuta}` : '—';
  document.getElementById('ann-res-utbytte').textContent = fmtKr(utbytteAar);
  document.getElementById('ann-res-upa').textContent    = upa > 0 ? `${fmtTall(upa)} ${valuta} per aksje` : 'Basert på yield';
  document.getElementById('ann-res-yield').textContent  = effYield > 0 ? `${effYield.toFixed(2)}%` : '—';
  document.getElementById('ann-res-mnd').textContent    = fmtKr(utbytteMnd);
  document.getElementById('ann-res-netto').textContent  = fmtKr(netto);

  const snitt5El = document.getElementById('ann-res-snitt5');
  if (snitt5 > 0) {
    snitt5El.textContent = `5-årssnitt: ${snitt5.toFixed(1)}%`;
    snitt5El.classList.remove('hidden');
  } else {
    snitt5El.classList.add('hidden');
  }

  const exKort = document.getElementById('ann-res-ex-kort');
  if (ex) {
    document.getElementById('ann-res-ex').textContent = formaterDato(ex);
    exKort.classList.remove('hidden');
  } else {
    exKort.classList.add('hidden');
  }

  const infoEl = document.getElementById('ann-aksje-info');
  const infoDeler = [];
  if (a.navn)    infoDeler.push(`<span class="font-medium">${escHtml(a.navn)}</span>`);
  if (a.sektor)  infoDeler.push(`Sektor: ${escHtml(a.sektor)}`);
  if (a.frekvens) infoDeler.push(`Utbyttefrekvens: ${escHtml(a.frekvens)}`);
  if (belop > 0 && faktiskBelop < belop) {
    const rest = belop - faktiskBelop;
    infoDeler.push(`Ubrukt beløp: ${fmtKr(rest)} (${antall} hele aksjer)`);
  }
  infoEl.innerHTML = infoDeler.map(d => `<div>${d}</div>`).join('');

  ingenEl.classList.add('hidden');
  resultatEl.classList.remove('hidden');
}

function _annBygTopp() {
  const liste = document.getElementById('ann-topp-liste');
  if (!liste) return;
  const alle = window.alleAksjer || [];
  const topp = alle
    .filter(a => (a.utbytte_yield || 0) > 0)
    .sort((a, b) => (b.utbytte_yield || 0) - (a.utbytte_yield || 0))
    .slice(0, 10);

  if (!topp.length) { liste.innerHTML = '<p class="text-xs text-gray-400">Ingen data tilgjengelig.</p>'; return; }

  liste.innerHTML = topp.map((a, i) => {
    const yield_ = (a.utbytte_yield || 0).toFixed(1);
    return `<button class="ann-topp-btn w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors text-left"
                data-ticker="${escHtml(a.ticker)}">
      <span class="flex items-center gap-2">
        <span class="text-xs font-mono text-gray-400 w-4">${i + 1}.</span>
        <span class="font-semibold">${escHtml(a.ticker)}</span>
        <span class="text-gray-500 dark:text-gray-400 text-xs hidden sm:inline">${escHtml(a.navn || '')}</span>
      </span>
      <span class="font-semibold text-green-600 dark:text-green-400">${yield_}%</span>
    </button>`;
  }).join('');

  liste.addEventListener('click', e => {
    const btn = e.target.closest('.ann-topp-btn[data-ticker]');
    if (!btn) return;
    const ticker = btn.dataset.ticker;
    const alle2  = window.alleAksjer || [];
    _annValgtAksje = alle2.find(a => a.ticker === ticker) || null;
    if (_annValgtAksje) {
      const sokEl = document.getElementById('ann-sok');
      sokEl.value = `${_annValgtAksje.ticker} — ${_annValgtAksje.navn || ''}`;
      document.getElementById('ann-nullstill').classList.remove('hidden');
      _annOppdaterResultat();
    }
  });
}

// Node.js test export
if (typeof module !== 'undefined') module.exports = { fmt, formaterDato, yieldKlasse, payoutKlasse, vekstKlasse, beregnScore, beregnBaerekraft, beregnYtdInntekt };
