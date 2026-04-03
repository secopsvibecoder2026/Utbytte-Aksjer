'use strict';

// Holder styr på hvilke detail-rader som er åpne på tvers av re-renders
const _aapneDetailRader = new Set();

function beregnKostbasis(ticker, txMap) {
  const tx = (txMap !== undefined ? txMap : hentTransaksjoner())[ticker] || [];
  let antall = 0, totalKost = 0, mottattUtbytte = 0;
  tx.forEach(t => {
    if (t.type === 'kjøp') {
      totalKost += t.antall * t.kurs;
      antall    += t.antall;
    } else if (t.type === 'salg') {
      // FIFO-forenkling: reduser kostpris proporsjonalt
      if (antall > 0) {
        const solgt = Math.min(t.antall, antall);
        const andel = solgt / antall;
        totalKost  -= totalKost * andel;
        antall     -= solgt;
      }
    } else if (t.type === 'utbytte') {
      mottattUtbytte += t.antall * t.kurs;
    }
  });
  const vwap = antall > 0 ? totalKost / antall : 0;
  return { antall, totalKost, vwap, mottattUtbytte };
}



// Bygger HTML-innholdet for en rad sin detail-panel (kostbasis + tx-form + logg)
function byggDetailHtml(ticker, kb, marked) {
  const fmtKr   = v => v.toLocaleString('nb-NO', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + '\u00a0kr';
  const fmtKurs = v => v.toLocaleString('nb-NO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const txListe = (hentTransaksjoner()[ticker] || []).slice().sort((a, b) => b.dato.localeCompare(a.dato));

  const harKb  = kb && kb.antall > 0 && kb.totalKost > 0;
  const gevinst = harKb ? marked - kb.totalKost : null;
  const gevPct  = harKb && kb.totalKost > 0 ? (gevinst / kb.totalKost * 100) : null;
  const gevFarge = gevinst !== null
    ? (gevinst >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500') : '';

  const kostbasisHtml = harKb ? `
    <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs py-2 border-b border-gray-100 dark:border-gray-800">
      <span class="text-gray-500">Sn.kurs: <span class="font-medium text-gray-700 dark:text-gray-300">${kb.vwap.toLocaleString('nb-NO', { maximumFractionDigits: 2 })} kr</span></span>
      <span class="text-gray-500">Kostpris: <span class="font-medium text-gray-700 dark:text-gray-300">${fmtKr(kb.totalKost)}</span></span>
      <span class="text-gray-500">Gev./tap: <span class="font-semibold ${gevFarge}">${gevinst >= 0 ? '+' : ''}${fmtKr(gevinst)} (${gevPct >= 0 ? '+' : ''}${gevPct.toFixed(1)}%)</span></span>
      ${kb.mottattUtbytte > 0 ? `<span class="text-gray-500">Utbytte mottatt: <span class="font-medium text-yellow-600 dark:text-yellow-400">${fmtKr(kb.mottattUtbytte)}</span></span>` : ''}
    </div>` : '';

  const idag = new Date().toISOString().slice(0, 10);
  const beholdningAntall = hentPF()[ticker] || '';
  const prefillKurs = kb && kb.vwap > 0 ? kb.vwap.toFixed(2) : '';

  const txLoggHtml = txListe.length > 0
    ? txListe.map(t => {
        const isKjøp    = t.type === 'kjøp';
        const isUtbytte = t.type === 'utbytte';
        const badge = isKjøp
          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
          : isUtbytte
            ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
            : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
        const label = isKjøp ? 'Kjøp' : isUtbytte ? 'Utbytte' : 'Salg';
        const [y, m, d] = t.dato.split('-');
        return `<div class="flex items-center gap-2 py-1.5 text-xs border-b border-gray-100 dark:border-gray-800 last:border-0">
          <span class="text-gray-400 min-w-[4.5rem]">${d}.${m}.${y}</span>
          <span class="px-1.5 py-0.5 rounded text-[10px] font-medium ${badge}">${label}</span>
          <span class="flex-1 text-gray-600 dark:text-gray-400">${t.antall} × ${fmtKurs(t.kurs)} kr</span>
          <span class="font-medium">${fmtKr(t.antall * t.kurs)}</span>
          <button class="pf-tx-slett p-0.5 text-gray-300 hover:text-red-500 transition-colors" data-ticker="${ticker}" data-id="${t.id}" aria-label="Slett transaksjon">
            <svg class="w-3.5 h-3.5 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>`;
      }).join('')
    : '<p class="text-xs text-gray-400 py-2">Ingen transaksjoner ennå.</p>';

  return `<div class="pt-2 space-y-2">
    ${kostbasisHtml}
    <div class="grid grid-cols-2 sm:grid-cols-5 gap-1.5">
      <select class="pf-detail-type filter-input text-xs py-1.5">
        <option value="kjøp">Kjøp</option>
        <option value="salg">Salg</option>
        <option value="utbytte">Utbytte</option>
      </select>
      <input type="date" class="pf-detail-dato filter-input text-xs py-1.5" value="${idag}" />
      <input type="number" min="1" class="pf-detail-antall filter-input text-xs py-1.5" placeholder="Antall" value="${beholdningAntall}" />
      <input type="number" min="0" step="0.01" class="pf-detail-kurs filter-input text-xs py-1.5" placeholder="Kurs / GAV (kr)" value="${prefillKurs}" />
      <button class="pf-detail-legg-til bg-brand-600 hover:bg-brand-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition-colors" data-ticker="${ticker}">+ Legg til</button>
    </div>
    <div class="divide-y divide-gray-100 dark:divide-gray-800">${txLoggHtml}</div>
  </div>`;
}


const STATS_TABS = ['oversikt', 'inntekt', 'beholdning', 'sektorer', 'rebalansering'];
let aktivStatsTab = 'oversikt';

function byttStatsSubTab(tab) {
  aktivStatsTab = tab;
  document.querySelectorAll('.stats-sub-btn').forEach(b => {
    const aktiv = b.dataset.statsTab === tab;
    b.classList.toggle('bg-brand-600', aktiv);
    b.classList.toggle('text-white', aktiv);
    b.classList.toggle('text-gray-500', !aktiv);
    b.classList.toggle('dark:text-gray-400', !aktiv);
    b.classList.toggle('hover:bg-gray-100', !aktiv);
    b.classList.toggle('dark:hover:bg-gray-800', !aktiv);
  });
  STATS_TABS.forEach(t => {
    const el = document.getElementById('stats-sub-' + t);
    if (el) el.classList.toggle('hidden', t !== tab);
  });
  // Tegn charts på nytt når tab aktiveres
  if (window._pfSisteData) {
    const { beholdning, totalAr } = window._pfSisteData;
    if (tab === 'oversikt')      visYieldChart(beholdning);
    if (tab === 'inntekt')       visMaanedChart(beholdning);
    if (tab === 'beholdning')    { visVerdiChart(beholdning); visCharts(beholdning, totalAr); }
    if (tab === 'sektorer')      { visSektorYieldChart(beholdning); visCharts(beholdning, totalAr); }
    if (tab === 'rebalansering') visRebalansering(beholdning);
  }

  // Nullstill rebalanserings-mål
  document.getElementById('rebal-nullstill')?.addEventListener('click', () => {
    lagreRebalanseringsmaal({});
    if (window._pfSisteData) visRebalansering(window._pfSisteData.beholdning);
  });
}

function initPFSubTabs() {
  function byttSubTab(tab) {
    document.querySelectorAll('.pf-sub-btn').forEach(b => {
      const aktiv = b.dataset.pfTab === tab;
      b.classList.toggle('bg-brand-600', aktiv);
      b.classList.toggle('text-white', aktiv);
      b.classList.toggle('text-gray-500', !aktiv);
      b.classList.toggle('dark:text-gray-400', !aktiv);
      b.classList.toggle('hover:bg-gray-100', !aktiv);
      b.classList.toggle('dark:hover:bg-gray-800', !aktiv);
    });
    document.getElementById('pf-sub-beholdning').classList.toggle('hidden', tab !== 'beholdning');
    document.getElementById('pf-sub-statistikk').classList.toggle('hidden', tab !== 'statistikk');
    document.getElementById('pf-sub-watchlister').classList.toggle('hidden', tab !== 'watchlister');
    if (tab === 'statistikk') visPortefolje();
    if (tab === 'watchlister') visWatchlister();
  }

  document.getElementById('tab-portfolio').addEventListener('click', e => {
    const btn = e.target.closest('.pf-sub-btn');
    if (btn) byttSubTab(btn.dataset.pfTab);
    const sBtn = e.target.closest('.stats-sub-btn');
    if (sBtn) byttStatsSubTab(sBtn.dataset.statsTab);
  });
}


function initPortefolje() {
  document.getElementById('pf-legg-til').addEventListener('click', () => {
    const sel       = document.getElementById('pf-velg-aksje');
    const antallEl  = document.getElementById('pf-antall');
    const datoEl    = document.getElementById('pf-kjoepsdato');
    const kursEl    = document.getElementById('pf-kjoepskurs');
    const feilEl    = document.getElementById('pf-feil');
    const ticker    = sel.value;
    const antall    = parseInt(antallEl.value, 10);
    feilEl.classList.add('hidden');
    if (!ticker) { feilEl.textContent = 'Velg en aksje.'; feilEl.classList.remove('hidden'); return; }
    if (!antall || antall < 1) { feilEl.textContent = 'Skriv inn gyldig antall aksjer.'; feilEl.classList.remove('hidden'); return; }

    const pf = hentPF();
    pf[ticker] = antall;
    lagrePF(pf);

    // Valgfritt: lag kjøpstransaksjon hvis dato og kurs er fylt ut
    const dato = datoEl?.value;
    const kurs = parseFloat(kursEl?.value);
    if (dato && kurs > 0) {
      const txData = hentTransaksjoner();
      if (!txData[ticker]) txData[ticker] = [];
      txData[ticker].push({ id: Date.now().toString(), dato, antall, kurs, type: 'kjøp' });
      txData[ticker].sort((a, b) => a.dato.localeCompare(b.dato));
      lagreTransaksjoner(txData);
      // Auto-åpne detail-raden for denne tickeren
      _aapneDetailRader.add(ticker);
    }

    sel.value = '';
    antallEl.value = '';
    if (datoEl) datoEl.value = '';
    if (kursEl) kursEl.value = '';
    visPortefolje();
  });

  document.getElementById('pf-antall').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('pf-legg-til').click();
  });

  document.getElementById('pf-eksport-csv')?.addEventListener('click', eksporterCSV);

  // ── CSV-IMPORT ─────────────────────────────────────────────────────────────
  const filInput = document.getElementById('pf-importer-fil');

  document.getElementById('pf-importer-csv')?.addEventListener('click', () => filInput.click());

  const tomKnapp = document.getElementById('pf-importer-csv-tom');
  if (tomKnapp) tomKnapp.addEventListener('click', () => document.getElementById('json-importer-fil')?.click());

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
  document.getElementById('pf-qr-btn')?.addEventListener('click', visQRModal);
  document.getElementById('qr-lukk').addEventListener('click', () => {
    clearInterval(document.getElementById('qr-modal')._timer);
    document.getElementById('qr-modal').classList.add('hidden');
    document.getElementById('qr-modal').classList.remove('flex');
  });

  // ── INNTEKTSTELLER-MÅL / SPAREMÅL — naviger til innstillinger ────────────────
  const navTilInnst = () => { window.location.href = '/innstillinger/'; };
  const settBtn = document.getElementById('pf-inntekt-mal-sett');
  if (settBtn) settBtn.addEventListener('click', navTilInnst);
  const spareSettBtnInit = document.getElementById('pf-stat-sparemaal-sett');
  if (spareSettBtnInit) spareSettBtnInit.addEventListener('click', navTilInnst);
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


function lagrePortefoljeSnapshot(verdi) {
  const idag = new Date().toISOString().slice(0, 10);
  let historikk = {};
  try { historikk = JSON.parse(localStorage.getItem('pf_historikk') || '{}'); } catch(e) {}
  historikk[idag] = Math.round(verdi);
  const datoer = Object.keys(historikk).sort();
  if (datoer.length > 30) {
    datoer.slice(0, datoer.length - 30).forEach(d => delete historikk[d]);
  }
  localStorage.setItem('pf_historikk', JSON.stringify(historikk));
}


// ── TWR: beregn normalisert TWR-serie fra daglige snapshots + transaksjoner ──
function beregnTWRSerie(historikk, datoer, txMap) {
  const tx = txMap !== undefined ? txMap : hentTransaksjoner();
  const cfPerDag = {};
  Object.values(tx).forEach(liste => {
    liste.forEach(t => {
      if (t.dato < datoer[0]) return;
      if (!cfPerDag[t.dato]) cfPerDag[t.dato] = 0;
      const v = t.antall * t.kurs;
      if (t.type === 'kjøp')       cfPerDag[t.dato] += v;  // nytt kapital inn
      else if (t.type === 'salg')  cfPerDag[t.dato] -= v;  // kapital ut
      // utbytte er intern avkastning — justeres ikke
    });
  });

  const serie = [100];
  for (let i = 1; i < datoer.length; i++) {
    const V0   = historikk[datoer[i - 1]];
    const V1   = historikk[datoer[i]];
    const CF   = cfPerDag[datoer[i - 1]] || 0;
    const denom = V0 + CF;
    serie.push(denom > 0 ? serie[i - 1] * (V1 / denom) : serie[i - 1]);
  }
  return serie;
}

// ── IRR: Newton-Raphson fra transaksjonshistorikk + nåværende porteføljeverdi ──
function beregnIRR(txMap) {
  const tx = txMap !== undefined ? txMap : hentTransaksjoner();
  const alle = Object.entries(tx).flatMap(([ticker, liste]) =>
    liste.map(t => ({ ...t, ticker }))
  ).sort((a, b) => a.dato.localeCompare(b.dato));

  if (alle.length === 0) return { harNokData: false };

  // Kontantstrømmer: negative = penger ut (kjøp), positive = penger inn (salg, utbytte)
  const cashflows = [];
  alle.forEach(t => {
    const v = t.antall * t.kurs;
    if      (t.type === 'kjøp')    cashflows.push({ dato: t.dato, cf: -v });
    else if (t.type === 'salg')    cashflows.push({ dato: t.dato, cf: +v });
    else if (t.type === 'utbytte') cashflows.push({ dato: t.dato, cf: +v });
  });

  // Terminalverdi: nåværende markedsverdi av beholdning
  const pfMap = {};
  alle.forEach(t => {
    if (!pfMap[t.ticker]) pfMap[t.ticker] = 0;
    if      (t.type === 'kjøp') pfMap[t.ticker] += t.antall;
    else if (t.type === 'salg') pfMap[t.ticker] = Math.max(0, pfMap[t.ticker] - t.antall);
  });
  let terminalVerdi = 0;
  Object.entries(pfMap).forEach(([ticker, antall]) => {
    if (antall <= 0) return;
    const aksje = alleAksjer.find(a => a.ticker === ticker);
    if (aksje?.pris > 0) terminalVerdi += antall * aksje.pris;
  });

  if (terminalVerdi <= 0) return { harNokData: false };

  const idag = new Date().toISOString().slice(0, 10);
  cashflows.push({ dato: idag, cf: +terminalVerdi });

  const dag0 = new Date(cashflows[0].dato);
  const cfArr = cashflows.map(c => ({
    t: Math.max(0, (new Date(c.dato) - dag0) / 86400000),
    cf: c.cf
  }));

  const totalDager = cfArr[cfArr.length - 1].t;
  if (totalDager < 1) return { harNokData: false };

  const npv  = r => cfArr.reduce((s, {t, cf}) => s + cf / Math.pow(1 + r, t), 0);
  const dnpv = r => cfArr.reduce((s, {t, cf}) => s - t * cf / Math.pow(1 + r, t + 1), 0);

  let r = 0.0003;
  let konvergen = false;
  for (let i = 0; i < 200; i++) {
    const f = npv(r), df = dnpv(r);
    if (Math.abs(df) < 1e-12) break;
    const rNy = r - f / df;
    if (rNy <= -1) break;
    if (Math.abs(rNy - r) < 1e-10) { r = rNy; konvergen = true; break; }
    r = rNy;
  }

  if (!konvergen) return { harNokData: false };

  return {
    harNokData: true,
    irr_ar:     (Math.pow(1 + r, 365) - 1) * 100,
    periodeAr:  totalDager / 365,
    forsteDato: cashflows[0].dato
  };
}


function visOsebxSammenligning(alleBeholdning, pfPct, osebxPct, invKost, totalReturnKr, forsteTxDato, osebxStartDato) {
  const wrapper = document.getElementById('pf-osebx-sammenligning');
  const innhold = document.getElementById('pf-osebx-innhold');
  if (!wrapper || !innhold) return;

  if (pfPct === null || osebxPct === null) {
    wrapper.classList.remove('hidden');
    innhold.innerHTML = `
      <p class="text-sm text-gray-400 dark:text-gray-500">
        Legg til transaksjoner i porteføljen for å se hvordan du måler deg mot Oslo Børs-indeksen.
      </p>`;
    return;
  }

  const diff   = pfPct - osebxPct;
  const slaer  = diff >= 0;
  const hypoOsebx = invKost * (1 + osebxPct / 100);
  const totalVerdi = invKost + totalReturnKr;
  const diffKr = totalVerdi - hypoOsebx;

  const fmtPct = v => (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
  const fmtKr  = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';

  const maks = Math.max(Math.abs(pfPct), Math.abs(osebxPct), 0.01);
  const pfW  = Math.min(100, Math.abs(pfPct)    / maks * 100);
  const oxW  = Math.min(100, Math.abs(osebxPct) / maks * 100);

  const fraDato = forsteTxDato
    ? new Date(forsteTxDato).toLocaleDateString('nb-NO', { day: 'numeric', month: 'short', year: 'numeric' })
    : osebxStartDato || '—';

  wrapper.classList.remove('hidden');
  innhold.innerHTML = `
    <div class="space-y-3">
      <div>
        <div class="flex justify-between text-xs mb-1">
          <span class="text-gray-500 dark:text-gray-400">Din portefølje</span>
          <span class="font-semibold ${pfPct >= 0 ? 'text-teal-600 dark:text-teal-400' : 'text-red-500'}">${fmtPct(pfPct)}</span>
        </div>
        <div class="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
          <div class="h-full rounded-full ${pfPct >= 0 ? 'bg-teal-500' : 'bg-red-400'}" style="width:${pfW}%"></div>
        </div>
      </div>
      <div>
        <div class="flex justify-between text-xs mb-1">
          <span class="text-gray-500 dark:text-gray-400">OSEBX (Oslo Børs)</span>
          <span class="font-semibold ${osebxPct >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-red-500'}">${fmtPct(osebxPct)}</span>
        </div>
        <div class="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
          <div class="h-full rounded-full ${osebxPct >= 0 ? 'bg-blue-400' : 'bg-red-400'}" style="width:${oxW}%"></div>
        </div>
      </div>
      <div class="pt-2 border-t border-gray-100 dark:border-gray-800 flex justify-between items-center">
        <span class="text-xs text-gray-400">Fra ${fraDato}</span>
        <span class="text-sm font-bold ${slaer ? 'text-teal-600 dark:text-teal-400' : 'text-red-500'}">
          ${fmtPct(diff)} (${diffKr >= 0 ? '+' : ''}${fmtKr(diffKr)})
        </span>
      </div>
    </div>`;
}

function visHistorikkKurve() {
  const wrapper = document.getElementById('pf-historikk-wrapper');
  if (!wrapper) return;

  let historikk = {};
  try { historikk = JSON.parse(localStorage.getItem('pf_historikk') || '{}'); } catch(e) {}

  const datoer = Object.keys(historikk).sort();
  if (datoer.length < 2) { wrapper.classList.add('hidden'); return; }
  wrapper.classList.remove('hidden');

  // Normalisér porteføljelinjen til 100 ved første dato
  const verdier = datoer.map(d => historikk[d]);
  const pf0 = verdier[0];
  const pfNorm = verdier.map(v => v / pf0 * 100);

  // TWR-serie: eliminerer effekten av nye innskudd/uttak
  const twrSerie = beregnTWRSerie(historikk, datoer);
  const twrAvviker = twrSerie.some((v, i) => Math.abs(v - pfNorm[i]) > 0.5);

  // OSEBX: finn felles datoer
  const osebxDatoer = datoer.filter(d => osebxHistorikk[d] != null);
  let osebxPts = null;
  if (osebxDatoer.length >= 2) {
    const osebx0 = osebxHistorikk[osebxDatoer[0]];
    osebxPts = datoer.map((d, i) => {
      if (!osebxHistorikk[d]) return null;
      return [i, osebxHistorikk[d] / osebx0 * 100];
    }).filter(Boolean);
  }

  // Samlet min/max for skalering
  const alleVerdier = [
    ...pfNorm,
    ...(twrAvviker ? twrSerie : []),
    ...(osebxPts ? osebxPts.map(p => p[1]) : [])
  ];
  const min = Math.min(...alleVerdier);
  const max = Math.max(...alleVerdier);
  const range = max - min || 1;

  const W = 800, H = 100, pad = 4;
  const n = datoer.length;
  const xStep = (W - pad * 2) / (n - 1);

  const toSvg = (idx, val) => [
    pad + idx * xStep,
    pad + (1 - (val - min) / range) * (H - pad * 2)
  ];

  const pfPts    = pfNorm.map((v, i) => toSvg(i, v));
  const polyline = pfPts.map(p => p.join(',')).join(' ');
  const areaD    = `M${pfPts[0][0]},${H} ` + pfPts.map(p => `L${p[0]},${p[1]}`).join(' ') + ` L${pfPts[pfPts.length-1][0]},${H} Z`;

  const endring    = pfNorm[pfNorm.length - 1] - 100;
  const endringPct = endring.toFixed(1);
  const positiv    = endring >= 0;
  const farge      = positiv ? '#16a34a' : '#dc2626';
  const fargeLys   = positiv ? '#dcfce7' : '#fee2e2';

  // TWR SVG-linje (blå) — vises kun hvis den avviker fra porteføljelinjen
  let twrSvg = '';
  if (twrAvviker) {
    const twrPts = twrSerie.map((v, i) => toSvg(i, v));
    twrSvg = `<polyline points="${twrPts.map(p => p.join(',')).join(' ')}"
      fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-dasharray="3 2"
      stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`;
  }

  // OSEBX SVG-linje (grå stiplet)
  let osebxSvg = '';
  if (osebxPts) {
    const obxSvgPts = osebxPts.map(([idx, val]) => toSvg(idx, val));
    osebxSvg = `<polyline points="${obxSvgPts.map(p => p.join(',')).join(' ')}"
      fill="none" stroke="#9ca3af" stroke-width="1.5" stroke-dasharray="4 3"
      stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`;
  }

  document.getElementById('pf-historikk-chart').innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" width="100%" height="100%" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="hgrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${farge}" stop-opacity="0.2"/>
          <stop offset="100%" stop-color="${farge}" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      <path d="${areaD}" fill="url(#hgrad)"/>
      ${osebxSvg}
      ${twrSvg}
      <polyline points="${polyline}" fill="none" stroke="${farge}" stroke-width="2.5"
                stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>
      <circle cx="${pfPts[pfPts.length-1][0]}" cy="${pfPts[pfPts.length-1][1]}" r="4" fill="${farge}" vector-effect="non-scaling-stroke"/>
    </svg>`;

  const endringEl = document.getElementById('pf-historikk-endring');
  if (endringEl) {
    endringEl.textContent = (positiv ? '+' : '') + endringPct + '%';
    endringEl.style.backgroundColor = fargeLys;
    endringEl.style.color = farge;
  }

  // Legend
  const legendEl = document.getElementById('pf-historikk-legend');
  if (legendEl) {
    const osebxLegend = osebxPts
      ? `<span class="flex items-center gap-1"><span class="inline-block w-5 border-t-2 border-dashed border-gray-400"></span> OSEBX</span>`
      : '';
    const twrLegend = twrAvviker
      ? `<span class="flex items-center gap-1"><span class="inline-block w-5 border-t-2 border-dashed border-blue-400"></span> TWR</span>`
      : '';
    legendEl.innerHTML = [twrLegend, osebxLegend].filter(Boolean).join('');
  }

  const fmtDato = iso => { const [y,m,d] = iso.split('-'); return d+'.'+m+'.'+y; };
  const fraEl = document.getElementById('pf-historikk-dato-fra');
  const tilEl = document.getElementById('pf-historikk-dato-til');
  if (fraEl) fraEl.textContent = fmtDato(datoer[0]);
  if (tilEl) tilEl.textContent = fmtDato(datoer[datoer.length - 1]);
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
  document.getElementById('pf-inntekt-wrapper').classList.toggle('hidden', !harBeholdning);
  document.getElementById('pf-statistikk-tom').classList.toggle('hidden', harBeholdning);
  // Vis/skjul stats-sub-tabs og sett standard til oversikt ved første lasting
  STATS_TABS.forEach(t => {
    const el = document.getElementById('stats-sub-' + t);
    if (el) el.classList.toggle('hidden', t !== aktivStatsTab);
  });
  oppdaterSammendrag();

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

  const totalArVedtatt  = alleBeholdning.filter(a => a.ex_dato).reduce((s, a) => s + a.forv_ar, 0);
  const totalArEstimert = alleBeholdning.filter(a => !a.ex_dato).reduce((s, a) => s + a.forv_ar, 0);
  const breakdownEl = document.getElementById('pf-stat-ar-breakdown');
  if (breakdownEl && totalArVedtatt > 0 && totalArEstimert > 0) {
    document.getElementById('pf-stat-ar-vedtatt').textContent = fmtKr(totalArVedtatt);
    document.getElementById('pf-stat-ar-estimert').textContent = fmtKr(totalArEstimert);
    breakdownEl.classList.remove('hidden');
  } else if (breakdownEl) {
    breakdownEl.classList.add('hidden');
  }
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
  const { malMnd: profilMalMnd } = hentProfil();
  const malRaw = profilMalMnd > 0 ? profilMalMnd * 12 : 0;
  const malVisEl  = document.getElementById('pf-inntekt-mal-vis');
  const settBtn2  = document.getElementById('pf-inntekt-mal-sett');
  const progEl    = document.getElementById('pf-inntekt-progresjon');
  if (malRaw > 0) {
    if (malVisEl) malVisEl.textContent = fmtKr(malRaw);
    if (settBtn2) settBtn2.classList.add('hidden');
    const pct = Math.min(100, (ytdInntekt / malRaw) * 100);
    document.getElementById('pf-inntekt-pct-tekst').textContent = pct.toFixed(0) + '%';
    document.getElementById('pf-inntekt-mal-tekst').textContent = 'Mål: ' + fmtKr(malRaw);
    document.getElementById('pf-inntekt-bar').style.width = pct + '%';
    progEl.classList.remove('hidden');
  } else {
    if (malVisEl) malVisEl.textContent = '—';
    if (settBtn2) settBtn2.classList.remove('hidden');
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

  // ── EKSTRA NØKKELTALL ─────────────────────────────────────────────────────
  const frekvMap = { 'Månedlig': 12, 'Kvartalsvis': 4, 'Halvårlig': 2, 'Årlig': 1, 'Uregelmessig': 1 };

  document.getElementById('pf-extra-stats').classList.toggle('hidden', !harBeholdning);
  document.getElementById('pf-profil-seksjon').classList.toggle('hidden', !harBeholdning);

  if (harBeholdning) {
    // Estimert beløp neste utbetaling
    if (nestePayout) {
      const perUtbetaling = nestePayout.a.forv_ar / (frekvMap[nestePayout.a.frekvens] || 1);
      document.getElementById('pf-stat-neste-belop').textContent = fmtKr(perUtbetaling);
      document.getElementById('pf-stat-neste-belop-navn').textContent = nestePayout.a.ticker;
    }

    // Vektet P/E (veid etter posisjonsstørrelse, kun aksjer med gyldig P/E)
    const medPE = alleBeholdning.filter(a => a.pe_ratio && a.pe_ratio > 0 && a.pe_ratio < 200);
    const totalVerdiPE = medPE.reduce((s, a) => s + a.antall * (a.pris || 0), 0);
    const vektetPE = totalVerdiPE > 0
      ? medPE.reduce((s, a) => s + (a.antall * (a.pris || 0) / totalVerdiPE) * a.pe_ratio, 0)
      : 0;
    document.getElementById('pf-stat-pe').textContent = vektetPE > 0 ? vektetPE.toFixed(1) : '—';

    // Totale utbetalingshendelser per år
    const totalUtbetalinger = alleBeholdning.reduce((s, a) => s + (frekvMap[a.frekvens] || 1), 0);
    document.getElementById('pf-stat-utbetalinger').textContent = totalUtbetalinger;

    // Sparemål-fremgang
    const { spareMaal } = hentProfil();
    const sparePctEl  = document.getElementById('pf-stat-sparemaal-pct');
    const spareTekstEl = document.getElementById('pf-stat-sparemaal-tekst');
    const spareSettBtn = document.getElementById('pf-stat-sparemaal-sett');
    if (spareMaal > 0) {
      const sparePct = (totalVerdi / spareMaal * 100);
      sparePctEl.textContent   = sparePct.toFixed(1) + '%';
      spareTekstEl.textContent = 'av ' + spareMaal.toLocaleString('nb-NO') + ' kr';
      if (spareSettBtn) spareSettBtn.classList.add('hidden');
    } else {
      sparePctEl.textContent   = '—';
      spareTekstEl.textContent = '';
      if (spareSettBtn) spareSettBtn.classList.remove('hidden');
    }

    // Porteføljeprofil: beste/laveste yield, største posisjon, sektorer
    const sortYield = [...alleBeholdning].sort((a, b) => b.utbytte_yield - a.utbytte_yield);
    const best = sortYield[0];
    const lav  = sortYield[sortYield.length - 1];
    document.getElementById('pf-profil-best-yield').textContent  = `${best.ticker} — ${best.utbytte_yield.toFixed(2)}%`;
    document.getElementById('pf-profil-lav-yield').textContent   = `${lav.ticker} — ${lav.utbytte_yield.toFixed(2)}%`;

    const storst = [...alleBeholdning].sort((a, b) => (b.antall * (b.pris||0)) - (a.antall * (a.pris||0)))[0];
    const storstPct = totalVerdi > 0 ? (storst.antall * (storst.pris||0) / totalVerdi * 100).toFixed(1) : '0';
    document.getElementById('pf-profil-storst').textContent = `${storst.ticker} — ${storstPct}%`;

    const antallSektorer = new Set(alleBeholdning.map(a => a.sektor).filter(Boolean)).size;
    document.getElementById('pf-profil-sektorer').textContent = antallSektorer + ' sektorer';

    // ── FAKTISK AVKASTNING + OSEBX-SAMMENLIGNING ─────────────────────────────
    // Beregnes samlet for å dele data mellom stat-kortene
    const faktiskEl   = document.getElementById('pf-stat-faktisk');
    const faktiskTekst = document.getElementById('pf-stat-faktisk-tekst');
    const osebxEl     = document.getElementById('pf-stat-osebx');
    const osebxTekst  = document.getElementById('pf-stat-osebx-tekst');

    const txMap = hentTransaksjoner();
    let invKost = 0, invMottatt = 0, invMarkert = 0, harTx = false;
    alleBeholdning.forEach(a => {
      const kb = beregnKostbasis(a.ticker, txMap);
      if (kb.totalKost > 0 || kb.mottattUtbytte > 0) {
        invKost    += kb.totalKost;
        invMottatt += kb.mottattUtbytte;
        invMarkert += kb.antall * (a.pris || 0);
        harTx = true;
      }
    });

    let pfPctTotal = null, totalReturnKr = null;
    if (harTx && invKost > 0) {
      totalReturnKr = invMarkert + invMottatt - invKost;
      pfPctTotal    = totalReturnKr / invKost * 100;
      if (faktiskEl) {
        faktiskEl.textContent = (pfPctTotal >= 0 ? '+' : '') + pfPctTotal.toFixed(1) + '%';
        faktiskEl.className   = 'stat-value text-base ' + (pfPctTotal >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500');
        if (faktiskTekst) faktiskTekst.textContent = (totalReturnKr >= 0 ? '+' : '') + fmtKr(totalReturnKr);
      }
    } else if (faktiskEl) {
      faktiskEl.textContent = '—';
      faktiskEl.className   = 'stat-value text-base';
      if (faktiskTekst) faktiskTekst.textContent = 'trenger transaksjoner';
    }

    // OSEBX: bruk transaksjonsdata – tidligste kjøpsdato som startpunkt
    const alleTxDatoer = Object.values(txMap)
      .flatMap(liste => liste.filter(t => t.type === 'kjøp').map(t => t.dato))
      .sort();
    const forsteTxDato  = alleTxDatoer[0] || null;
    const osebxDatoer   = Object.keys(osebxHistorikk).sort();
    const osebxStartDato = forsteTxDato
      ? (osebxDatoer.find(d => d >= forsteTxDato) || osebxDatoer[0])
      : osebxDatoer[0];
    const osebxSluttDato = osebxDatoer[osebxDatoer.length - 1];

    let osebxPctTotal = null;
    if (osebxStartDato && osebxSluttDato && osebxStartDato !== osebxSluttDato) {
      osebxPctTotal = (osebxHistorikk[osebxSluttDato] - osebxHistorikk[osebxStartDato]) / osebxHistorikk[osebxStartDato] * 100;
    }

    if (osebxEl && pfPctTotal !== null && osebxPctTotal !== null) {
      const diff  = pfPctTotal - osebxPctTotal;
      const slaer = diff >= 0;
      osebxEl.textContent = slaer ? '✓ Ja' : '✗ Nei';
      osebxEl.className   = 'stat-value text-base ' + (slaer ? 'text-green-600 dark:text-green-400' : 'text-red-500');
      osebxTekst.textContent = (diff >= 0 ? '+' : '') + diff.toFixed(1) + '% vs indeks';
    } else if (osebxEl) {
      osebxEl.textContent  = '—';
      osebxEl.className    = 'stat-value text-base';
      osebxTekst.textContent = harTx ? 'ingen OSEBX-data' : 'trenger transaksjoner';
    }
    visOsebxSammenligning(alleBeholdning, pfPctTotal, osebxPctTotal, invKost, totalReturnKr, forsteTxDato, osebxStartDato);

    // ── IRR (annualisert intern avkastningsrate) ──────────────────────────────
    const irrEl    = document.getElementById('pf-stat-irr');
    const irrTekst = document.getElementById('pf-stat-irr-tekst');
    if (irrEl) {
      const irr = beregnIRR();
      if (irr.harNokData) {
        const pct = irr.irr_ar;
        irrEl.textContent  = (pct >= 0 ? '+' : '') + pct.toFixed(2) + '%';
        irrEl.className    = 'stat-value text-base ' + (pct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500');
        const aar = irr.periodeAr < 1
          ? Math.round(irr.periodeAr * 12) + ' mnd'
          : irr.periodeAr.toFixed(1) + ' år';
        if (irrTekst) irrTekst.textContent = 'over ' + aar;
      } else {
        irrEl.textContent  = '—';
        irrEl.className    = 'stat-value text-base';
        if (irrTekst) irrTekst.textContent = 'trenger transaksjoner';
      }
    }

    // ── SKATTEBEREGNING (aksjonærmodellen) ────────────────────────────────────
    const nettoEl    = document.getElementById('pf-stat-netto-skatt');
    const skattTekst = document.getElementById('pf-stat-skatt-tekst');
    if (nettoEl) {
      // Skjermingsfradrag = VWAP-kostpris × skjermingsrente per posisjon
      let totalSkjermingsfradrag = 0;
      alleBeholdning.forEach(a => {
        const kb = beregnKostbasis(a.ticker);
        if (kb.totalKost > 0) totalSkjermingsfradrag += kb.totalKost * SKJERMINGSRENTE;
      });
      const skattbartUtbytte = Math.max(0, totalAr - totalSkjermingsfradrag);
      const skatt            = skattbartUtbytte * SKATTESATS;
      const netto            = totalAr - skatt;
      nettoEl.textContent    = fmtKr(netto);
      if (skattTekst) skattTekst.textContent = `skatt: ${fmtKr(skatt)}`;
    }
  }

  // ── HISTORISK SNAPSHOT + KURVE ────────────────────────────────────────────
  lagrePortefoljeSnapshot(totalVerdi);
  visHistorikkKurve();


  // ── BEHOLDNINGSTABELL MED INLINE DETAIL-RADER ────────────────────────────
  const tbody = document.getElementById('pf-tabell-body');
  tbody.innerHTML = beholdning.map(a => {
    const kb      = beregnKostbasis(a.ticker);
    const harKb   = kb.antall > 0 && kb.totalKost > 0;
    const marked  = a.antall * (a.pris || 0);
    const gevinst = harKb ? marked - kb.totalKost : null;
    const gevPct  = harKb && kb.totalKost > 0 ? (gevinst / kb.totalKost * 100) : null;
    const gevFarge = gevinst !== null ? (gevinst >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500') : 'text-gray-400';
    const kostTd = harKb
      ? `<span class="text-xs">${fmtKr(kb.totalKost)}</span><br><span class="text-xs text-gray-400">${kb.vwap.toLocaleString('nb-NO',{maximumFractionDigits:1})} kr/stk</span>`
      : '—';
    const gevTd = gevinst !== null
      ? `<span class="font-semibold ${gevFarge}">${gevinst >= 0 ? '+' : ''}${fmtKr(gevinst)}</span><br><span class="text-xs ${gevFarge}">${gevPct >= 0 ? '+' : ''}${gevPct.toFixed(1)}%</span>`
      : '—';
    const isOpen = _aapneDetailRader.has(a.ticker);
    return `
    <tr class="table-row" data-ticker="${a.ticker}">
      <td class="px-4 py-3 font-mono font-bold text-brand-700 dark:text-brand-400">${a.ticker}</td>
      <td class="px-4 py-3 hidden sm:table-cell text-gray-600 dark:text-gray-400 text-sm">${a.navn}</td>
      <td class="px-4 py-3 text-right">
        <input type="number" min="1" value="${a.antall}"
          class="w-20 text-right text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1 bg-transparent focus:outline-none focus:ring-1 focus:ring-brand-500"
          data-ticker="${a.ticker}" />
      </td>
      <td class="px-4 py-3 text-right"><span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span></td>
      <td class="px-4 py-3 text-right font-semibold">${fmtKr(a.forv_ar)}</td>
      <td class="px-4 py-3 text-right hidden lg:table-cell text-sm">${kostTd}</td>
      <td class="px-4 py-3 text-right hidden lg:table-cell text-sm">${gevTd}</td>
      <td class="px-4 py-3 text-center hidden sm:table-cell text-gray-500 text-sm">${a.ex_dato ? formaterDato(a.ex_dato) : '—'}</td>
      <td class="px-4 py-3 text-center hidden sm:table-cell"><span class="frekvens-badge">${a.frekvens}</span></td>
      <td class="px-4 py-3 text-center">
        <div class="flex items-center justify-center gap-1">
          <button class="pf-detail-toggle p-1 text-gray-400 hover:text-brand-500 transition-colors" data-ticker="${a.ticker}" aria-label="Vis transaksjoner" aria-expanded="${isOpen}">
            <svg class="w-4 h-4 pointer-events-none transition-transform${isOpen ? ' rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
          </button>
          <button class="pf-slett p-1 text-gray-400 hover:text-red-500 transition-colors" data-ticker="${a.ticker}" aria-label="Fjern">
            <svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
      </td>
    </tr>
    <tr class="pf-detail-rad${isOpen ? '' : ' hidden'}" data-for="${a.ticker}">
      <td colspan="10" class="px-4 pb-4 bg-gray-50 dark:bg-gray-900/30 border-b border-gray-100 dark:border-gray-800">
        ${byggDetailHtml(a.ticker, kb, marked)}
      </td>
    </tr>`;
  }).join('');

  // Sum-rad i footer
  document.getElementById('pf-tabell-footer').innerHTML = `
    <tr>
      <td colspan="2" class="px-4 py-3 text-sm text-gray-500">Totalt (${alleBeholdning.length} selskaper)</td>
      <td class="px-4 py-3 text-right text-sm text-gray-500">${alleBeholdning.reduce((s,a)=>s+a.antall,0)} aksjer</td>
      <td></td>
      <td class="px-4 py-3 text-right text-brand-700 dark:text-brand-400">${fmtKr(totalAr)}</td>
      <td colspan="5"></td>
    </tr>`;

  // Event delegation for hele tbody
  tbody.onclick = e => {
    // Expand/kollaps detail-rad
    const toggleBtn = e.target.closest('.pf-detail-toggle');
    if (toggleBtn) {
      const ticker = toggleBtn.dataset.ticker;
      const isOpen = _aapneDetailRader.has(ticker);
      if (isOpen) _aapneDetailRader.delete(ticker); else _aapneDetailRader.add(ticker);
      const rad     = tbody.querySelector(`.pf-detail-rad[data-for="${ticker}"]`);
      const chevron = toggleBtn.querySelector('svg');
      if (rad)     rad.classList.toggle('hidden', isOpen);
      if (chevron) chevron.style.transform = isOpen ? '' : 'rotate(180deg)';
      toggleBtn.setAttribute('aria-expanded', !isOpen);
      return;
    }
    // Legg til transaksjon fra detail-rad
    const leggTilBtn = e.target.closest('.pf-detail-legg-til');
    if (leggTilBtn) {
      const ticker  = leggTilBtn.dataset.ticker;
      const rad     = leggTilBtn.closest('.pf-detail-rad');
      const type    = rad.querySelector('.pf-detail-type').value;
      const datoRaw = rad.querySelector('.pf-detail-dato').value;
      const dato    = datoRaw || new Date().toISOString().slice(0, 10);
      const antall  = parseInt(rad.querySelector('.pf-detail-antall').value, 10);
      const kurs    = parseFloat(rad.querySelector('.pf-detail-kurs').value);
      if (!antall || antall < 1 || !kurs || kurs <= 0) return;
      const txData = hentTransaksjoner();
      if (!txData[ticker]) txData[ticker] = [];
      txData[ticker].push({ id: Date.now().toString(), dato, antall, kurs, type });
      txData[ticker].sort((a, b) => a.dato.localeCompare(b.dato));
      lagreTransaksjoner(txData);
      _aapneDetailRader.add(ticker);
      visPortefolje();
      return;
    }
    // Slett transaksjon fra detail-rad
    const txSlett = e.target.closest('.pf-tx-slett');
    if (txSlett) {
      const { ticker, id } = txSlett.dataset;
      const txData = hentTransaksjoner();
      if (txData[ticker]) {
        txData[ticker] = txData[ticker].filter(t => String(t.id) !== String(id));
        if (!txData[ticker].length) delete txData[ticker];
      }
      lagreTransaksjoner(txData);
      _aapneDetailRader.add(ticker);
      visPortefolje();
      return;
    }
    // Fjern aksje fra portefølje
    const slett = e.target.closest('.pf-slett');
    if (slett) {
      const pf2 = hentPF();
      delete pf2[slett.dataset.ticker];
      lagrePF(pf2);
      visPortefolje();
      return;
    }
    // Rad-klikk → vis modal (ikke på input/knapp)
    const tr = e.target.closest('tr[data-ticker].table-row');
    if (tr && !e.target.closest('input, button')) {
      const aksje = alleAksjer.find(a => a.ticker === tr.dataset.ticker);
      if (aksje) visModal(aksje);
    }
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

  // Lagre for lazy chart-tegning ved tab-bytte
  window._pfSisteData = { beholdning: alleBeholdning, totalAr };
  // Tegn chart for aktiv stats-tab
  if (aktivStatsTab === 'oversikt')      visYieldChart(alleBeholdning);
  if (aktivStatsTab === 'inntekt')       visMaanedChart(alleBeholdning);
  if (aktivStatsTab === 'beholdning')    { visVerdiChart(alleBeholdning); visCharts(alleBeholdning, totalAr); }
  if (aktivStatsTab === 'sektorer')      { visSektorYieldChart(alleBeholdning); visCharts(alleBeholdning, totalAr); }
  if (aktivStatsTab === 'rebalansering') visRebalansering(alleBeholdning);
  if (!['beholdning','sektorer'].includes(aktivStatsTab)) {
    const cw = document.getElementById('pf-charts-wrapper');
    if (cw) cw.style.display = 'none';
  }
}


// ── HJELPERE FOR MÅNEDLIG DISTRIBUSJON ────────────────────────────────────
function _frekvensAntall(f) {
  return { 'Månedlig': 12, 'Kvartalsvis': 4, 'Halvårlig': 2, 'Årlig': 1 }[f] || 1;
}

function _betalingsMaaneder(a) {
  const ant = _frekvensAntall(a.frekvens);
  if (a.betaling_dato) {
    const base = new Date(a.betaling_dato).getMonth();
    const intervall = 12 / ant;
    return Array.from({ length: ant }, (_, i) => Math.round((base + i * intervall) % 12));
  }
  return ({
    'Månedlig':    [0,1,2,3,4,5,6,7,8,9,10,11],
    'Kvartalsvis': [2,5,8,11],
    'Halvårlig':   [5,11],
    'Årlig':       [11],
  })[a.frekvens] || [11];
}

// ── YIELD-FORDELING (Oversikt) ────────────────────────────────────────────
function visYieldChart(beholdning) {
  const el = document.getElementById('pf-yield-chart');
  if (!el || !beholdning.length) return;
  const fmtKr = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';
  const buckets = [
    { label: '< 3%',  min: 0, max: 3,   color: '#cbd5e1', items: [] },
    { label: '3–6%',  min: 3, max: 6,   color: '#94a3b8', items: [] },
    { label: '6–9%',  min: 6, max: 9,   color: '#0d9488', items: [] },
    { label: '≥ 9%',  min: 9, max: 999, color: '#14b8a6', items: [] },
  ];
  beholdning.forEach(a => {
    const y = a.utbytte_yield || 0;
    const b = buckets.find(b => y >= b.min && y < b.max);
    if (b) b.items.push(a);
  });
  const maks = Math.max(...buckets.map(b => b.items.length), 1);
  el.innerHTML = buckets.map(b => {
    const pct = (b.items.length / maks * 100).toFixed(1);
    const forv = b.items.reduce((s, a) => s + a.forv_ar, 0);
    return `
      <div>
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs font-semibold" style="color:${b.color}">${b.label}</span>
          <span class="text-xs text-gray-500 dark:text-gray-400">${b.items.length} aksjer${forv > 0 ? ' · ' + fmtKr(forv) + '/år' : ''}</span>
        </div>
        <div class="h-4 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
          <div class="h-full rounded-full transition-all duration-500" style="width:${pct}%;background:${b.color}"></div>
        </div>
        <p class="text-xs text-gray-400 mt-0.5 truncate">${b.items.map(a => a.ticker).join(', ') || '—'}</p>
      </div>`;
  }).join('');
}

// ── MÅNEDLIG INNTEKT (Inntekt) ────────────────────────────────────────────
function visMaanedChart(beholdning) {
  const el = document.getElementById('pf-maaned-chart');
  if (!el || !beholdning.length) return;
  const mnd = Array(12).fill(0);
  beholdning.forEach(a => {
    const perBetaling = a.forv_ar / _frekvensAntall(a.frekvens);
    _betalingsMaaneder(a).forEach(m => { mnd[m] += perBetaling; });
  });
  const maks = Math.max(...mnd, 1);
  const fmtKr = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';
  const navn = ['Jan','Feb','Mar','Apr','Mai','Jun','Jul','Aug','Sep','Okt','Nov','Des'];
  const iMnd = new Date().getMonth();
  el.innerHTML = `
    <div class="flex items-end gap-0.5 h-28">
      ${mnd.map((v, i) => {
        const h = maks > 0 ? (v / maks * 100).toFixed(1) : 0;
        const er = i === iMnd;
        const bg = er ? '#14b8a6' : '#3b82f6';
        const op = v > 0 ? '1' : '0.15';
        return `<div class="flex-1 flex flex-col items-center justify-end gap-0.5 group relative" title="${navn[i]}: ${fmtKr(v)}">
          <div class="w-full rounded-t-sm transition-all duration-500" style="height:${h}%;background:${bg};opacity:${op};min-height:${v>0?'4px':'0'}"></div>
          <span class="text-[9px] text-gray-400${er ? ' font-bold text-brand-500' : ''}">${navn[i][0]}</span>
        </div>`;
      }).join('')}
    </div>
    <div class="flex justify-between text-xs text-gray-400 mt-2">
      <span>Lavest: <strong>${fmtKr(Math.min(...mnd.filter(v=>v>0)))}</strong></span>
      <span>Høyest: <strong>${fmtKr(Math.max(...mnd))}</strong></span>
    </div>`;
}

// ── VERDIKONSENTRASJON (Beholdning) ───────────────────────────────────────
function visVerdiChart(beholdning) {
  const el = document.getElementById('pf-verdi-chart');
  if (!el || !beholdning.length) return;
  const fmtKr = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';
  const totalVerdi = beholdning.reduce((s, a) => s + a.antall * (a.pris || 0), 0);
  if (!totalVerdi) { el.innerHTML = '<p class="text-xs text-gray-400">Mangler kursinformasjon.</p>'; return; }
  let data = [...beholdning]
    .map(a => ({ label: a.ticker, value: a.antall * (a.pris || 0) }))
    .filter(d => d.value > 0)
    .sort((a, b) => b.value - a.value)
    .map((d, i) => ({ ...d, color: CHART_FARGER[i % CHART_FARGER.length] }));
  const andreVerdi = data.slice(7).reduce((s, d) => s + d.value, 0);
  data = data.slice(0, 7).map((d, i) => ({ ...d, color: CHART_FARGER[i % CHART_FARGER.length] }));
  if (andreVerdi > 0) data.push({ label: 'Andre', value: andreVerdi, color: '#475569' });
  const size = 180, cx = 90, cy = 90, or = 76, ir = 48;
  let angle = -Math.PI / 2, paths = '';
  data.forEach(({ value, color }) => {
    const sweep = (value / totalVerdi) * 2 * Math.PI;
    const end = angle + sweep;
    const lg = sweep > Math.PI ? 1 : 0;
    const [x1,y1] = [cx+or*Math.cos(angle), cy+or*Math.sin(angle)];
    const [x2,y2] = [cx+or*Math.cos(end),   cy+or*Math.sin(end)];
    const [x3,y3] = [cx+ir*Math.cos(end),   cy+ir*Math.sin(end)];
    const [x4,y4] = [cx+ir*Math.cos(angle), cy+ir*Math.sin(angle)];
    paths += `<path d="M${x1},${y1} A${or},${or} 0 ${lg} 1 ${x2},${y2} L${x3},${y3} A${ir},${ir} 0 ${lg} 0 ${x4},${y4}Z" fill="${color}" stroke="white" stroke-width="1.5" class="dark:stroke-gray-900"/>`;
    angle = end;
  });
  const legend = data.map(({ label, value, color }) => `
    <div class="flex items-center gap-2 text-xs">
      <span class="w-2.5 h-2.5 rounded-full shrink-0" style="background:${color}"></span>
      <span class="font-mono font-bold text-gray-700 dark:text-gray-200 shrink-0 w-14">${label}</span>
      <span class="text-gray-400">${(value/totalVerdi*100).toFixed(1)}%</span>
      <span class="ml-auto font-semibold tabular-nums">${fmtKr(value)}</span>
    </div>`).join('');
  el.innerHTML = `
    <div class="flex flex-col sm:flex-row items-center gap-4">
      <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" class="shrink-0">${paths}</svg>
      <div class="space-y-1.5 flex-1 min-w-0">${legend}</div>
    </div>`;
}

// ── YIELD PER SEKTOR (Sektorer) ───────────────────────────────────────────
function visSektorYieldChart(beholdning) {
  const el = document.getElementById('pf-sektor-yield-chart');
  if (!el || !beholdning.length) return;
  const smap = {};
  beholdning.forEach(a => {
    if (!smap[a.sektor]) smap[a.sektor] = { sum: 0, n: 0 };
    smap[a.sektor].sum += a.utbytte_yield || 0;
    smap[a.sektor].n++;
  });
  const sektorer = Object.entries(smap)
    .map(([s, d]) => ({ sektor: s, avg: d.sum / d.n, color: SEKTOR_FARGE[s] || FARGE_FALLBACK }))
    .filter(s => s.avg > 0)
    .sort((a, b) => b.avg - a.avg);
  const maks = sektorer[0]?.avg || 1;
  el.innerHTML = sektorer.map(({ sektor, avg, color }) => `
    <div>
      <div class="flex items-center justify-between mb-1">
        <span class="text-xs font-medium text-gray-700 dark:text-gray-300">${sektor}</span>
        <span class="text-xs font-semibold tabular-nums" style="color:${color}">${avg.toFixed(1)}%</span>
      </div>
      <div class="h-3 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
        <div class="h-full rounded-full transition-all duration-500" style="width:${(avg/maks*100).toFixed(1)}%;background:${color}"></div>
      </div>
    </div>`).join('');
}

function visCharts(beholdning, totalAr) {
  const wrapper = document.getElementById('pf-charts-wrapper');
  if (!beholdning.length || !totalAr) { if (wrapper) wrapper.style.display = 'none'; return; }
  if (wrapper) wrapper.style.display = 'grid';
  const visBeholdning = aktivStatsTab === 'beholdning';
  const visSektorer   = aktivStatsTab === 'sektorer';

  // ── 1. SEKTOR-DONUT (kun på Sektorer-tab) ─────────────────────────────
  if (!visSektorer && !visBeholdning) return;
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

  if (visSektorer) {
    document.getElementById('pf-sektor-chart').innerHTML = `
      <div class="flex flex-col sm:flex-row items-center gap-4">
        <svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" class="shrink-0">${paths}</svg>
        <div class="space-y-1.5 flex-1 min-w-0">${legend}</div>
      </div>`;
  }
  if (!visBeholdning) return;

  // ── 2. TOPP BIDRAGSYTERE ───────────────────────────────────────────────
  const topp = [...beholdning].sort((a, b) => b.forv_ar - a.forv_ar).slice(0, 8);
  const maks = topp[0]?.forv_ar || 1;
  const fmtKr = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';

  document.getElementById('pf-topp-chart').innerHTML = topp.map((a, i) => {
    const pct = (a.forv_ar / maks * 100).toFixed(1);
    const andel = (a.forv_ar / totalAr * 100).toFixed(1);
    const farge = CHART_FARGER[i % CHART_FARGER.length];
    return `
      <div>
        <div class="flex items-center justify-between mb-1">
          <div class="flex items-center gap-1.5">
            <span class="font-mono text-xs font-bold text-gray-700 dark:text-gray-200">${a.ticker}</span>
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
    'Månedlig':      '#14b8a6',
    'Kvartalsvis':   '#0d9488',
    'Halvårlig':     '#6366f1',
    'Årlig':         '#64748b',
    'Uregelmessig':  '#94a3b8',
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


function oppdaterPortefoljeVelger() {
  const pfl = hentPortefoljer();
  const aktivId = hentAktivPFId();
  const sel = document.getElementById('pf-portefolje-velg');
  if (!sel) return;
  sel.innerHTML = Object.values(pfl).map(p =>
    `<option value="${p.id}" ${p.id === aktivId ? 'selected' : ''}>${p.navn}</option>`
  ).join('');
  // Deaktiver slett-knapp hvis bare én portefølje
  const slettBtn = document.getElementById('pf-portefolje-slett');
  if (slettBtn) slettBtn.disabled = Object.keys(pfl).length <= 1;
}

function initPortefoljeVelger() {
  oppdaterPortefoljeVelger();

  document.getElementById('pf-portefolje-velg').addEventListener('change', e => {
    settAktivPFId(e.target.value);
    visPortefolje();
    oppdaterSammendrag();
  });
}


function visWatchlister() {
  const lister   = hentWatchlister();
  const harLister = lister.length > 0;

  document.getElementById('wl-tom').classList.toggle('hidden', harLister);
  document.getElementById('wl-velg-wrapper').classList.toggle('hidden', !harLister);
  document.getElementById('wl-legg-til-wrapper').classList.toggle('hidden', !harLister);

  // Fyll aksje-dropdown (her er alleAksjer alltid lastet)
  const wlAksjeSel = document.getElementById('wl-velg-aksje');
  const valgtAksje = wlAksjeSel.value;
  wlAksjeSel.innerHTML = '<option value="">Velg aksje…</option>';
  [...alleAksjer].sort((a, b) => a.ticker.localeCompare(b.ticker, 'nb')).forEach(a => {
    const o = document.createElement('option');
    o.value = a.ticker; o.textContent = `${a.ticker} – ${a.navn}`;
    wlAksjeSel.appendChild(o);
  });
  if (valgtAksje) wlAksjeSel.value = valgtAksje;

  const sel = document.getElementById('wl-velg');
  const valgt = sel.value || (lister[0]?.id);
  sel.innerHTML = lister.map(w =>
    `<option value="${w.id}" ${w.id === valgt ? 'selected' : ''}>${w.navn} (${w.tickers.length})</option>`
  ).join('');

  const aktivListe = lister.find(w => w.id === valgt) || lister[0];
  const innholdEl  = document.getElementById('wl-innhold');

  if (!aktivListe || aktivListe.tickers.length === 0) {
    innholdEl.innerHTML = '<p class="text-xs text-gray-400 text-center py-4">Ingen aksjer i denne watchlisten ennå.</p>';
    return;
  }

  const fmtKr = v => v.toLocaleString('nb-NO', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' kr';

  innholdEl.innerHTML = `
    <div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-gray-100 dark:bg-gray-900 text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">
            <th class="px-4 py-3 text-left">Ticker</th>
            <th class="px-4 py-3 text-left hidden sm:table-cell">Selskap</th>
            <th class="px-4 py-3 text-right">Kurs</th>
            <th class="px-4 py-3 text-right">Yield</th>
            <th class="px-4 py-3 text-center hidden sm:table-cell">Ex-dato</th>
            <th class="px-4 py-3 text-center">+ Port.</th>
            <th class="px-4 py-3 text-center">Fjern</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
          ${aktivListe.tickers.map(ticker => {
            const a = alleAksjer.find(x => x.ticker === ticker);
            if (!a) return '';
            return `<tr class="table-row cursor-pointer" data-ticker="${ticker}">
              <td class="px-4 py-3 font-mono font-bold text-brand-700 dark:text-brand-400">${ticker}</td>
              <td class="px-4 py-3 hidden sm:table-cell text-gray-600 dark:text-gray-400 text-sm">${a.navn}</td>
              <td class="px-4 py-3 text-right">${a.pris ? fmtKr(a.pris) : '—'}</td>
              <td class="px-4 py-3 text-right"><span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span></td>
              <td class="px-4 py-3 text-center hidden sm:table-cell text-gray-500 text-sm">${a.ex_dato ? formaterDato(a.ex_dato) : '—'}</td>
              <td class="px-4 py-3 text-center">
                <button class="wl-legg-til-pf text-gray-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors p-1" title="Legg til i portefølje" aria-label="Legg til i portefølje"
                        data-ticker="${ticker}">
                  <svg class="w-4 h-4 pointer-events-none" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                </button>
              </td>
              <td class="px-4 py-3 text-center">
                <button class="wl-fjern-ticker text-gray-400 hover:text-red-500 transition-colors p-1"
                        data-liste-id="${aktivListe.id}" data-ticker="${ticker}" aria-label="Fjern fra watchliste">
                  <svg class="w-4 h-4 pointer-events-none" aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                </button>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`;

  // Klikk på rad → modal / legg til portefølje / fjern
  innholdEl.querySelector('tbody').onclick = e => {
    const fjernBtn = e.target.closest('.wl-fjern-ticker');
    if (fjernBtn) {
      const { listeId, ticker } = fjernBtn.dataset;
      const listerNy = hentWatchlister();
      const liste    = listerNy.find(w => w.id === listeId);
      if (liste) { liste.tickers = liste.tickers.filter(t => t !== ticker); lagreWatchlister(listerNy); visWatchlister(); }
      return;
    }
    const pfBtn = e.target.closest('.wl-legg-til-pf');
    if (pfBtn) {
      const { ticker } = pfBtn.dataset;
      // Bytt til Beholdning-fanen, forhåndsvelg aksjen i legg-til-skjemaet
      document.querySelector('[data-pf-tab="beholdning"]').click();
      const sel = document.getElementById('pf-velg-aksje');
      if (sel) sel.value = ticker;
      document.getElementById('pf-antall')?.focus();
      return;
    }
    const rad = e.target.closest('[data-ticker]');
    if (rad) { const a = alleAksjer.find(x => x.ticker === rad.dataset.ticker); if (a) visModal(a); }
  };
}

function initWatchlister() {
  document.getElementById('wl-opprett').addEventListener('click', () => {
    const navnEl = document.getElementById('wl-ny-navn');
    const navn   = navnEl.value.trim();
    if (!navn) return;
    const lister = hentWatchlister();
    lister.push({ id: 'wl_' + Date.now(), navn, tickers: [] });
    lagreWatchlister(lister);
    navnEl.value = '';
    visWatchlister();
  });

  document.getElementById('wl-velg').addEventListener('change', visWatchlister);

  document.getElementById('wl-legg-til').addEventListener('click', () => {
    const ticker  = document.getElementById('wl-velg-aksje').value;
    const listeId = document.getElementById('wl-velg').value;
    if (!ticker || !listeId) return;
    const lister = hentWatchlister();
    const liste  = lister.find(w => w.id === listeId);
    if (liste && !liste.tickers.includes(ticker)) {
      liste.tickers.push(ticker);
      lagreWatchlister(lister);
      visWatchlister();
    }
  });

  document.getElementById('wl-slett-liste').addEventListener('click', () => {
    const listeId = document.getElementById('wl-velg').value;
    if (!listeId) return;
    const lister  = hentWatchlister();
    const navn    = lister.find(w => w.id === listeId)?.navn || '';
    if (!confirm(`Slett watchlisten "${navn}"?`)) return;
    lagreWatchlister(lister.filter(w => w.id !== listeId));
    visWatchlister();
  });
}


// ── REBALANSERING ─────────────────────────────────────────────────────────────
function hentRebalanseringsmaal() {
  try { return JSON.parse(localStorage.getItem('pf_rebalansering') || '{}'); } catch { return {}; }
}
function lagreRebalanseringsmaal(maal) { localStorage.setItem('pf_rebalansering', JSON.stringify(maal)); }

function visRebalansering(alleBeholdning) {
  const el = document.getElementById('rebal-rader');
  if (!el) return;

  const totalVerdi = alleBeholdning.reduce((s, a) => s + a.antall * (a.pris || 0), 0);
  if (totalVerdi <= 0) { el.innerHTML = '<p class="text-xs text-gray-400 text-center py-4">Legg til aksjer med kurs for å se rebalansering.</p>'; return; }

  // Grupper etter sektor
  const sektorMap = {};
  alleBeholdning.forEach(a => {
    const v = a.antall * (a.pris || 0);
    sektorMap[a.sektor] = (sektorMap[a.sektor] || 0) + v;
  });
  const sektorer = Object.entries(sektorMap).sort((a, b) => b[1] - a[1]);
  const maal = hentRebalanseringsmaal();

  el.innerHTML = sektorer.map(([sektor, verdi]) => {
    const naaværendePct = verdi / totalVerdi * 100;
    const maalPct = maal[sektor] !== undefined ? maal[sektor] : Math.round(naaværendePct);
    const diff = naaværendePct - maalPct;
    let statusKlasse, statusTekst;
    if (Math.abs(diff) <= 5) {
      statusKlasse = 'text-green-600 dark:text-green-400'; statusTekst = 'OK';
    } else if (diff < -5) {
      statusKlasse = 'text-orange-500'; statusTekst = `Kjøp +${Math.abs(diff).toFixed(0)}%`;
    } else {
      statusKlasse = 'text-red-500'; statusTekst = `Reduser −${diff.toFixed(0)}%`;
    }
    const barBredde = Math.min(100, naaværendePct).toFixed(1);
    const maalBredde = Math.min(100, maalPct).toFixed(1);
    return `
      <div class="space-y-1" data-sektor="${sektor}">
        <div class="flex items-center gap-3">
          <span class="text-sm font-medium w-36 shrink-0 truncate">${sektor}</span>
          <span class="text-xs text-gray-500 dark:text-gray-400 w-12 text-right shrink-0">${naaværendePct.toFixed(1)}%</span>
          <div class="flex items-center gap-1 flex-1">
            <span class="text-xs text-gray-400 shrink-0">Mål:</span>
            <input type="number" min="0" max="100" step="1" value="${maalPct}"
              class="w-14 text-xs text-center border border-gray-200 dark:border-gray-700 rounded px-1 py-0.5 bg-white dark:bg-gray-800 focus:outline-none focus:border-brand-400"
              data-rebal-sektor="${sektor}" />
            <span class="text-xs font-medium w-20 shrink-0 ${statusKlasse}">${statusTekst}</span>
          </div>
        </div>
        <div class="relative h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
          <div class="absolute top-0 left-0 h-full bg-brand-500/30 rounded-full" style="width:${maalBredde}%"></div>
          <div class="absolute top-0 left-0 h-full bg-brand-500 rounded-full" style="width:${barBredde}%"></div>
        </div>
      </div>`;
  }).join('');

  // Lagre ved input
  el.querySelectorAll('input[data-rebal-sektor]').forEach(inp => {
    inp.addEventListener('change', () => {
      const m = hentRebalanseringsmaal();
      m[inp.dataset.rebalSektor] = Math.max(0, Math.min(100, parseInt(inp.value) || 0));
      lagreRebalanseringsmaal(m);
      visRebalansering(alleBeholdning);
    });
  });
}

// Node.js test export
if (typeof module !== 'undefined') module.exports = { beregnKostbasis, beregnIRR, beregnTWRSerie };
