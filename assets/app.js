'use strict';

// ── STATE ──────────────────────────────────────────────────────────────────
let alleAksjer = [];
let sortering = { kol: 'utbytte_yield', retning: 'desc' };
let aktivTab = 'oversikt';

// ── INIT ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initDarkMode();
  initTabs();
  initFilter();
  lastData();
});

// ── DATA ───────────────────────────────────────────────────────────────────
async function lastData() {
  try {
    const resp = await fetch('data/aksjer.json');
    const json = await resp.json();

    // Støtter både {aksjer:[...]} og flat array
    alleAksjer = Array.isArray(json) ? json : json.aksjer;

    // Sist oppdatert
    const ts = json.sist_oppdatert;
    if (ts) {
      const d = new Date(ts);
      document.getElementById('sist-oppdatert').textContent =
        'Oppdatert ' + d.toLocaleDateString('nb-NO', { day:'numeric', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' });
    }

    byggSektorFilter();
    oppdaterSammendrag();
    visOversikt();
    visKalender();
  } catch (e) {
    console.error('Feil ved lasting av data:', e);
  }
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
    document.getElementById('filter-bar').classList.toggle('hidden', aktivTab !== 'oversikt');
  });
}

// ── FILTER ─────────────────────────────────────────────────────────────────
function initFilter() {
  ['sok', 'filter-sektor', 'filter-frekvens', 'filter-yield'].forEach(id => {
    document.getElementById(id).addEventListener('input', visOversikt);
  });
  document.getElementById('reset-filter').addEventListener('click', () => {
    document.getElementById('sok').value = '';
    document.getElementById('filter-sektor').value = '';
    document.getElementById('filter-frekvens').value = '';
    document.getElementById('filter-yield').value = '';
    visOversikt();
  });

  // Kolonnesortering
  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const kol = th.dataset.col;
      sortering.retning = sortering.kol === kol && sortering.retning === 'desc' ? 'asc' : 'desc';
      sortering.kol = kol;
      visOversikt();
    });
  });
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

  return alleAksjer.filter(a => {
    if (sok && !a.ticker.toLowerCase().includes(sok) && !a.navn.toLowerCase().includes(sok)) return false;
    if (sektor && a.sektor !== sektor) return false;
    if (frekvens && a.frekvens !== frekvens) return false;
    if (a.utbytte_yield < minYield) return false;
    return true;
  });
}

// ── SAMMENDRAG ─────────────────────────────────────────────────────────────
function oppdaterSammendrag() {
  document.getElementById('stat-antall').textContent = alleAksjer.length;

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

// ── OVERSIKTSTABELL ────────────────────────────────────────────────────────
function visOversikt() {
  const data = sorterAksjer(filtrerteAksjer());
  const tbody = document.getElementById('tabell-body');
  const ingenEl = document.getElementById('ingen-resultater');
  const antallEl = document.getElementById('antall-vist');

  // Oppdater sorteringsikoner
  document.querySelectorAll('th.sortable').forEach(th => {
    th.classList.remove('sort-asc', 'sort-desc');
    if (th.dataset.col === sortering.kol) th.classList.add('sort-' + sortering.retning);
  });

  if (data.length === 0) {
    tbody.innerHTML = '';
    ingenEl.classList.remove('hidden');
    antallEl.textContent = '';
    return;
  }
  ingenEl.classList.add('hidden');
  antallEl.textContent = `Viser ${data.length} av ${alleAksjer.length} aksjer`;

  const idag = new Date(); idag.setHours(0,0,0,0);
  const om30 = new Date(idag); om30.setDate(om30.getDate() + 30);

  tbody.innerHTML = data.map(a => {
    const exDato = a.ex_dato ? new Date(a.ex_dato) : null;
    const snartEx = exDato && exDato >= idag && exDato <= om30;
    const rowClass = snartEx ? 'row-highlight' : '';

    return `
    <tr class="table-row ${rowClass}" data-ticker="${a.ticker}">
      <td class="px-4 py-3 font-mono font-bold text-brand-700 dark:text-brand-400">${a.ticker}</td>
      <td class="px-4 py-3">
        <div class="font-medium leading-tight">${a.navn}</div>
        <div class="text-xs text-gray-400 dark:text-gray-500">${a.sektor}</div>
      </td>
      <td class="px-4 py-3 text-right font-medium">
        ${fmt(a.pris)} <span class="text-xs text-gray-400">${a.valuta}</span>
      </td>
      <td class="px-4 py-3 w-36">
        ${rangebar(a.pris, a['52u_lav'], a['52u_hoy'])}
      </td>
      <td class="px-4 py-3 text-right">
        <span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span>
      </td>
      <td class="px-4 py-3 text-right">${fmt(a.utbytte_per_aksje)}</td>
      <td class="px-4 py-3 text-right">
        <span class="${payoutKlasse(a.payout_ratio)}">${a.payout_ratio > 0 ? a.payout_ratio.toFixed(0) + '%' : '—'}</span>
      </td>
      <td class="px-4 py-3 text-right ${vekstKlasse(a.utbytte_vekst_5ar)}">
        ${a.utbytte_vekst_5ar !== 0 ? (a.utbytte_vekst_5ar > 0 ? '+' : '') + a.utbytte_vekst_5ar.toFixed(1) + '%' : '—'}
      </td>
      <td class="px-4 py-3 text-right text-gray-600 dark:text-gray-400">${a.ar_med_utbytte > 0 ? a.ar_med_utbytte : '—'}</td>
      <td class="px-4 py-3 text-right text-gray-600 dark:text-gray-400">${a.pe_ratio > 0 ? a.pe_ratio.toFixed(1) : '—'}</td>
      <td class="px-4 py-3 text-right text-gray-600 dark:text-gray-400">${a.pb_ratio > 0 ? a.pb_ratio.toFixed(1) : '—'}</td>
      <td class="px-4 py-3 text-center ${snartEx ? 'font-semibold text-orange-600 dark:text-orange-400' : 'text-gray-600 dark:text-gray-400'}">
        ${a.ex_dato ? formaterDato(a.ex_dato) : '—'}
        ${snartEx ? '<span class="block text-xs text-orange-500">Snart!</span>' : ''}
      </td>
      <td class="px-4 py-3 text-center text-gray-500 dark:text-gray-500">${a.betaling_dato ? formaterDato(a.betaling_dato) : '—'}</td>
      <td class="px-4 py-3 text-center">
        <span class="frekvens-badge">${a.frekvens}</span>
      </td>
    </tr>`;
  }).join('');

  // Klikk for detaljer
  tbody.querySelectorAll('tr').forEach(tr => {
    tr.addEventListener('click', () => {
      const aksje = alleAksjer.find(a => a.ticker === tr.dataset.ticker);
      if (aksje) visModal(aksje);
    });
  });
}

function sorterAksjer(data) {
  const { kol, retning } = sortering;
  return [...data].sort((a, b) => {
    let va = a[kol], vb = b[kol];
    if (va == null) va = retning === 'asc' ? Infinity : -Infinity;
    if (vb == null) vb = retning === 'asc' ? Infinity : -Infinity;
    if (typeof va === 'string') return retning === 'asc' ? va.localeCompare(vb, 'nb') : vb.localeCompare(va, 'nb');
    return retning === 'asc' ? va - vb : vb - va;
  });
}

// ── KALENDER ───────────────────────────────────────────────────────────────
function visKalender() {
  const container = document.getElementById('kalender-innhold');
  const idag = new Date(); idag.setHours(0,0,0,0);

  // Grupper etter måned
  const manedsMap = {};
  alleAksjer
    .filter(a => a.ex_dato)
    .sort((a, b) => new Date(a.ex_dato) - new Date(b.ex_dato))
    .forEach(a => {
      const d = new Date(a.ex_dato);
      const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
      if (!manedsMap[key]) manedsMap[key] = [];
      manedsMap[key].push(a);
    });

  if (Object.keys(manedsMap).length === 0) {
    container.innerHTML = '<p class="text-gray-400">Ingen kommende ex-datoer tilgjengelig.</p>';
    return;
  }

  container.innerHTML = Object.entries(manedsMap).map(([key, aksjer]) => {
    const [year, month] = key.split('-');
    const manedNavn = new Date(parseInt(year), parseInt(month)-1, 1)
      .toLocaleDateString('nb-NO', { month: 'long', year: 'numeric' });

    const rader = aksjer.map(a => {
      const exDato = new Date(a.ex_dato);
      const erPassert = exDato < idag;
      const dagerTil = Math.ceil((exDato - idag) / (1000*60*60*24));

      return `
      <div class="kal-rad ${erPassert ? 'opacity-40' : ''}">
        <div class="flex items-center gap-3 flex-1">
          <div class="text-center w-12">
            <div class="text-xs text-gray-400">${['jan','feb','mar','apr','mai','jun','jul','aug','sep','okt','nov','des'][exDato.getMonth()]}</div>
            <div class="text-xl font-bold leading-none ${erPassert ? '' : 'text-orange-600 dark:text-orange-400'}">${exDato.getDate()}</div>
          </div>
          <div class="flex-1">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-mono font-bold text-brand-700 dark:text-brand-400">${a.ticker}</span>
              <span class="text-gray-600 dark:text-gray-400 text-sm">${a.navn}</span>
              <span class="text-xs text-gray-400 dark:text-gray-600">${a.sektor}</span>
            </div>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
              Siste utbytte: <strong>${fmt(a.siste_utbytte)} ${a.valuta}</strong>
              &nbsp;·&nbsp; Betaling: ${a.betaling_dato ? formaterDato(a.betaling_dato) : '—'}
            </div>
          </div>
        </div>
        <div class="text-right min-w-20">
          <span class="yield-badge ${yieldKlasse(a.utbytte_yield)} text-sm">${a.utbytte_yield.toFixed(2)}%</span>
          ${!erPassert ? `<div class="text-xs text-gray-400 mt-1">${dagerTil === 0 ? 'I dag!' : dagerTil === 1 ? 'I morgen' : `om ${dagerTil} dager`}</div>` : '<div class="text-xs text-gray-400 mt-1">Passert</div>'}
        </div>
      </div>`;
    }).join('');

    return `
    <div class="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
      <div class="px-4 py-3 bg-gray-100 dark:bg-gray-900 font-semibold capitalize flex items-center justify-between">
        <span>${manedNavn}</span>
        <span class="text-xs font-normal text-gray-400">${aksjer.length} ex-dato${aksjer.length !== 1 ? 'er' : ''}</span>
      </div>
      <div class="divide-y divide-gray-100 dark:divide-gray-800">${rader}</div>
    </div>`;
  }).join('');
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
      <button id="modal-close" class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 p-1">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
      </button>
    </div>

    ${a.beskrivelse ? `<p class="text-sm text-gray-600 dark:text-gray-400 mb-4 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">${a.beskrivelse}</p>` : ''}

    <div class="grid grid-cols-2 gap-3 mb-4">
      ${modalKort('Kurs', fmt(a.pris) + ' ' + a.valuta)}
      ${modalKort('Utbytteyield', `<span class="${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span>`)}
      ${modalKort('Utbytte/aksje (år)', fmt(a.utbytte_per_aksje) + ' ' + a.valuta)}
      ${modalKort('Siste utbytte', fmt(a.siste_utbytte) + ' ' + a.valuta)}
      ${modalKort('Payout Ratio', `<span class="${payoutKlasse(a.payout_ratio)}">${a.payout_ratio > 0 ? a.payout_ratio.toFixed(0)+'%' : '—'}</span>`)}
      ${modalKort('Utbyttevekst 5år', `<span class="${vekstKlasse(a.utbytte_vekst_5ar)}">${a.utbytte_vekst_5ar !== 0 ? (a.utbytte_vekst_5ar>0?'+':'')+a.utbytte_vekst_5ar.toFixed(1)+'%' : '—'}</span>`)}
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
  `;

  overlay.classList.remove('hidden');
  overlay.classList.add('flex');
  document.getElementById('modal-close').addEventListener('click', lukkModal);

  overlay.addEventListener('click', e => { if (e.target === overlay) lukkModal(); }, { once: true });
}

function lukkModal() {
  const overlay = document.getElementById('modal-overlay');
  overlay.classList.add('hidden');
  overlay.classList.remove('flex');
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

function payoutKlasse(p) {
  if (p <= 0)   return 'text-gray-400';
  if (p <= 50)  return 'text-green-600 dark:text-green-400 font-medium';
  if (p <= 75)  return 'text-yellow-600 dark:text-yellow-400 font-medium';
  return 'text-red-600 dark:text-red-400 font-medium';
}

function vekstKlasse(v) {
  if (v > 10) return 'text-green-600 dark:text-green-400 font-medium';
  if (v > 0)  return 'text-blue-600 dark:text-blue-400';
  if (v < 0)  return 'text-red-500 dark:text-red-400';
  return 'text-gray-400';
}

function rangebar(pris, lav, hoy, stor = false) {
  if (!lav || !hoy || lav >= hoy) return '';
  const pct = Math.min(100, Math.max(0, ((pris - lav) / (hoy - lav)) * 100));
  const h = stor ? 'h-3' : 'h-2';
  return `
  <div class="${stor ? 'px-0 py-2' : ''}">
    ${stor ? `<div class="flex justify-between text-xs text-gray-400 mb-1"><span>${fmt(lav)}</span><span class="font-medium text-gray-700 dark:text-gray-300">${fmt(pris)}</span><span>${fmt(hoy)}</span></div>` : ''}
    <div class="w-full bg-gray-200 dark:bg-gray-700 rounded-full ${h} relative">
      <div class="bg-brand-500 rounded-full ${h}" style="width:${pct}%"></div>
      <div class="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-brand-700 dark:bg-brand-400 border-2 border-white dark:border-gray-900 shadow" style="left:calc(${pct}% - 5px)"></div>
    </div>
    ${stor ? '' : `<div class="flex justify-between text-xs text-gray-400 mt-0.5"><span>${fmt(lav)}</span><span>${fmt(hoy)}</span></div>`}
  </div>`;
}
