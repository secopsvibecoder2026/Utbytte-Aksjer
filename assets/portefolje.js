'use strict';

// Holder styr på hvilke detail-rader som er åpne på tvers av re-renders
const _aapneDetailRader = new Set();

// Lagrer OSEBX-tilstand for periodebytte uten full re-render av portefølje
let _pfOsebxState = null;

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

  return `<div class="pt-2 space-y-3">
    ${kostbasisHtml}
    <div>
      <p class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-1.5">Ny transaksjon</p>
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
    </div>
    <div>
      <p class="text-xs font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wide mb-1">Historikk</p>
      <div class="divide-y divide-gray-100 dark:divide-gray-800">${txLoggHtml}</div>
    </div>
  </div>`;
}


const STATS_TABS = ['oversikt', 'inntekt', 'beholdning', 'sektorer'];
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
    if (tab === 'sektorer')      { visHHI(beholdning); visSektorYieldChart(beholdning); visCharts(beholdning, totalAr); }
  }
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
    document.getElementById('pf-sub-analyse').classList.toggle('hidden', tab !== 'analyse');
    if (tab === 'statistikk') visPortefolje();
    if (tab === 'watchlister') visWatchlister();
    if (tab === 'analyse') visAnalyse();
  }

  document.getElementById('tab-portfolio').addEventListener('click', e => {
    const btn = e.target.closest('.pf-sub-btn');
    if (btn) byttSubTab(btn.dataset.pfTab);
    const sBtn = e.target.closest('.stats-sub-btn');
    if (sBtn) byttStatsSubTab(sBtn.dataset.statsTab);
    const periodeBtn = e.target.closest('[data-osebx-periode]');
    if (periodeBtn) _oppdaterOsebxPeriode(periodeBtn.dataset.osebxPeriode);
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

  // Skjul/vis valgfri kostbasis-seksjon
  document.getElementById('pf-kjop-toggle')?.addEventListener('click', () => {
    const valgfritt = document.getElementById('pf-kjop-valgfritt');
    const chevron   = document.getElementById('pf-kjop-chevron');
    const toggle    = document.getElementById('pf-kjop-toggle');
    const aapen = !valgfritt.classList.contains('hidden');
    valgfritt.classList.toggle('hidden', aapen);
    if (chevron) chevron.style.transform = aapen ? '' : 'rotate(180deg)';
    toggle.setAttribute('aria-expanded', !aapen);
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
      const buf = e.target.result;
      const bytes = new Uint8Array(buf);
      // Detekter UTF-16 LE BOM (FF FE) — brukt av Nordnet
      const erUTF16 = bytes[0] === 0xFF && bytes[1] === 0xFE;
      let tekst = new TextDecoder(erUTF16 ? 'utf-16le' : 'utf-8').decode(buf);
      if (tekst.charCodeAt(0) === 0xFEFF) tekst = tekst.slice(1); // fjern BOM
      // Nordnet-format: tab-separert med 'Navn'-kolonne
      const forsteLinje = tekst.split(/\r?\n/)[0] || '';
      const erNordnet = forsteLinje.includes('\t') && /navn/i.test(forsteLinje);
      const result = erNordnet ? parseNordnetCSV(tekst) : parseCSV(tekst);
      window._importProfil = result.profil;
      visImportPreview(result.gyldig, result.dummy || [], result.ukjent);
    };
    reader.readAsArrayBuffer(fil);
    filInput.value = '';
  });

  document.getElementById('pf-importer-bekreft-legg-til').addEventListener('click', () => {
    bekreftImport(window._importData, false);
  });
  document.getElementById('pf-importer-bekreft-erstatt').addEventListener('click', () => {
    bekreftImport(window._importData, true);
  });
  document.getElementById('pf-importer-bekreft-ny').addEventListener('click', () => {
    const navnInput = document.getElementById('pf-importer-ny-navn');
    const navn = navnInput.value.trim();
    if (!navn) { navnInput.focus(); return; }
    bekreftImport(window._importData, false, navn);
  });
  document.getElementById('pf-importer-ny-navn').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('pf-importer-bekreft-ny').click();
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
  if (totalDager < 30) return { harNokData: false, forKort: true };  // IRR er ikke meningsfull under 30 dager

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


function _osebxStartForPeriode(periode, osebxDatoer, osebxSluttDato, forsteTxDato) {
  let startDato;
  if (periode === 'ytd') {
    const ar = new Date(osebxSluttDato).getFullYear();
    startDato = osebxDatoer.find(d => d >= ar + '-01-01') || osebxDatoer[0];
  } else if (periode === '1ar') {
    const for1ar = new Date(osebxSluttDato);
    for1ar.setFullYear(for1ar.getFullYear() - 1);
    startDato = osebxDatoer.find(d => d >= for1ar.toISOString().slice(0, 10)) || osebxDatoer[0];
  } else { // 'kjop'
    if (forsteTxDato) {
      startDato = osebxDatoer.find(d => d >= forsteTxDato) || osebxDatoer[0];
      if (startDato === osebxSluttDato && osebxDatoer.length > 1) {
        startDato = osebxDatoer[osebxDatoer.length - 2];
      }
    } else {
      const for12mnd = new Date(osebxSluttDato);
      for12mnd.setFullYear(for12mnd.getFullYear() - 1);
      startDato = osebxDatoer.find(d => d >= for12mnd.toISOString().slice(0, 10)) || osebxDatoer[0];
    }
  }
  return startDato;
}


function _oppdaterOsebxPeriode(periode) {
  if (!_pfOsebxState) return;
  const { alleBeholdning, pfPct, invKost, totalReturnKr, forsteTxDato } = _pfOsebxState;
  const osebxDatoer    = Object.keys(osebxHistorikk).sort();
  const osebxSluttDato = osebxDatoer[osebxDatoer.length - 1];
  const startDato      = _osebxStartForPeriode(periode, osebxDatoer, osebxSluttDato, forsteTxDato);
  let osebxPct = null;
  if (startDato && osebxSluttDato && startDato !== osebxSluttDato) {
    osebxPct = (osebxHistorikk[osebxSluttDato] - osebxHistorikk[startDato]) / osebxHistorikk[startDato] * 100;
  }
  _pfOsebxState.aktivPeriode = periode;
  visOsebxSammenligning(alleBeholdning, pfPct, osebxPct, invKost, totalReturnKr, forsteTxDato, startDato, osebxSluttDato, periode);

  // Oppdater stat-kortet
  const osebxEl    = document.getElementById('pf-stat-osebx');
  const osebxTekst = document.getElementById('pf-stat-osebx-tekst');
  if (!osebxEl) return;
  if (osebxPct !== null) {
    if (pfPct !== null) {
      const diff  = pfPct - osebxPct;
      const slaer = diff >= 0;
      osebxEl.textContent = slaer ? '✓ Ja' : '✗ Nei';
      osebxEl.className   = 'stat-value text-base ' + (slaer ? 'text-green-600 dark:text-green-400' : 'text-red-500');
      if (osebxTekst) osebxTekst.textContent = (diff >= 0 ? '+' : '') + diff.toFixed(1) + '% vs indeks';
    } else {
      osebxEl.textContent = (osebxPct >= 0 ? '+' : '') + osebxPct.toFixed(1) + '%';
      osebxEl.className   = 'stat-value text-base ' + (osebxPct >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-red-500');
      const label = { ytd: 'OSEBX YTD', '1ar': 'OSEBX 1 år', kjop: 'OSEBX siden kjøp' }[periode] || 'OSEBX';
      if (osebxTekst) osebxTekst.textContent = label;
    }
  }
}


function visOsebxSammenligning(alleBeholdning, pfPct, osebxPct, invKost, totalReturnKr, forsteTxDato, osebxStartDato, osebxSluttDato, aktivPeriode) {
  const wrapper = document.getElementById('pf-osebx-sammenligning');
  const innhold = document.getElementById('pf-osebx-innhold');
  if (!wrapper || !innhold) return;

  const periode = aktivPeriode || 'kjop';
  const fmtDato = d => new Date(d + 'T00:00:00').toLocaleDateString('nb-NO', { day: 'numeric', month: 'short' });

  const periodeKnapper = `
    <div class="flex gap-1 mb-3" role="group" aria-label="Velg tidsperiode">
      ${forsteTxDato ? `<button class="text-xs px-2 py-1 rounded ${periode === 'kjop' ? 'bg-teal-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'}" data-osebx-periode="kjop">Siden kjøp</button>` : ''}
      <button class="text-xs px-2 py-1 rounded ${periode === 'ytd' ? 'bg-teal-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'}" data-osebx-periode="ytd">YTD</button>
      <button class="text-xs px-2 py-1 rounded ${periode === '1ar' ? 'bg-teal-600 text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'}" data-osebx-periode="1ar">1 år</button>
    </div>`;

  if (osebxPct === null) {
    wrapper.classList.remove('hidden');
    innhold.innerHTML = `<p class="text-sm text-gray-400 dark:text-gray-500">Ingen OSEBX-data tilgjengelig.</p>`;
    return;
  }

  const datoLabel = (osebxStartDato && osebxSluttDato)
    ? `${fmtDato(osebxStartDato)} – ${fmtDato(osebxSluttDato)}`
    : '—';

  // Kun OSEBX – ingen porteføljedata ennå
  if (pfPct === null) {
    const fmtPct = v => (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
    wrapper.classList.remove('hidden');
    innhold.innerHTML = `
      <div class="space-y-3">
        ${periodeKnapper}
        <div>
          <div class="flex justify-between text-xs mb-1">
            <span class="text-gray-500 dark:text-gray-400">OSEBX (Oslo Børs)</span>
            <span class="font-semibold ${osebxPct >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-red-500'}">${fmtPct(osebxPct)}</span>
          </div>
          <div class="h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
            <div class="h-full rounded-full ${osebxPct >= 0 ? 'bg-blue-400' : 'bg-red-400'}" style="width:100%"></div>
          </div>
        </div>
        <p class="text-xs text-gray-400 dark:text-gray-500">${datoLabel} · Legg til transaksjoner for å sammenligne mot din portefølje.</p>
      </div>`;
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

  wrapper.classList.remove('hidden');
  innhold.innerHTML = `
    <div class="space-y-3">
      ${periodeKnapper}
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
        <span class="text-xs text-gray-400">${datoLabel}</span>
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


function visMiniSektorChart(beholdning) {
  const container = document.getElementById('pf-mini-sektor-chart');
  if (!container || !beholdning || !beholdning.length) return;

  const sektorMap = {};
  let totVerdi = 0;
  beholdning.forEach(a => {
    const s = a.sektor || 'Annet';
    const v = a.antall * (a.pris || 0);
    sektorMap[s] = (sektorMap[s] || 0) + v;
    totVerdi += v;
  });
  if (totVerdi === 0) return;

  const sortert = Object.entries(sektorMap).sort((a, b) => b[1] - a[1]);
  const farger = ['#2563eb', '#14b8a6', '#6366f1', '#0891b2', '#3b82f6', '#0d9488', '#4f46e5', '#60a5fa', '#10b981', '#f59e0b', '#f97316', '#ec4899'];

  container.innerHTML = sortert.map(([sektor, verdi], i) => {
    const pct = (verdi / totVerdi * 100);
    const farge = farger[i % farger.length];
    return `<div class="flex items-center gap-2 text-xs">
      <span class="w-28 shrink-0 text-gray-600 dark:text-gray-400 truncate">${escHtml(sektor)}</span>
      <div class="flex-1 bg-gray-100 dark:bg-gray-800 rounded-full h-2 overflow-hidden">
        <div class="h-2 rounded-full" style="width:${pct.toFixed(1)}%;background:${farge}"></div>
      </div>
      <span class="w-9 text-right text-gray-500">${pct.toFixed(0)}%</span>
    </div>`;
  }).join('');
}

// Sjekk om noen dummy-aksjer nå har blitt lagt til i appen, migrer dem automatisk
function sjekkDummyAktivering() {
  const meta = hentDummyMeta();
  if (!Object.keys(meta).length) return false;
  const pf = hentPF();
  const tx = hentTransaksjoner();
  function norm(n) { return n.toLowerCase().replace(/\b(asa|as)\b\.?/g, '').replace(/\s+/g, ' ').trim(); }
  const navnMap = {};
  (window.alleAksjer || []).forEach(a => { navnMap[norm(a.navn)] = a.ticker; });
  let aktivert = false;
  Object.entries(meta).forEach(([dummyTicker, info]) => {
    const realTicker = navnMap[norm(info.nordnetNavn)];
    if (!realTicker || !pf[dummyTicker]) return;
    // Migrer beholdning
    pf[realTicker] = (pf[realTicker] || 0) + pf[dummyTicker];
    delete pf[dummyTicker];
    // Migrer transaksjoner
    if (tx[dummyTicker]) {
      if (!tx[realTicker]) tx[realTicker] = [];
      tx[realTicker] = tx[realTicker].concat(tx[dummyTicker]);
      tx[realTicker].sort((a, b) => a.dato.localeCompare(b.dato));
      delete tx[dummyTicker];
    }
    delete meta[dummyTicker];
    aktivert = true;
    const toast = document.getElementById('milestone-toast');
    const text  = document.getElementById('milestone-toast-text');
    if (toast && text) {
      text.textContent = `${info.nordnetNavn} er nå tilgjengelig i appen (${realTicker}) — porteføljen er oppdatert!`;
      toast.classList.remove('hidden');
      setTimeout(() => toast.classList.add('hidden'), 8000);
    }
  });
  if (aktivert) { lagrePF(pf); lagreTransaksjoner(tx); lagreDummyMeta(meta); }
  return aktivert;
}

function visPortefolje() {
  if (sjekkDummyAktivering()) return visPortefolje();
  fyllPFDropdown();
  const pf = hentPF();
  const sok = (document.getElementById('sok')?.value || '').toLowerCase().trim();
  const idag = new Date(); idag.setHours(0,0,0,0);

  const dummyMeta = hentDummyMeta();
  const alleBeholdning = Object.entries(pf)
    .filter(([ticker]) => !ticker.startsWith('_'))
    .map(([ticker, antall]) => {
      const a = alleAksjer.find(x => x.ticker === ticker);
      if (!a || antall < 1) return null;
      return { ...a, antall, forv_ar: antall * (a.utbytte_per_aksje || 0) };
    })
    .filter(Boolean)
    .sort((a, b) => b.forv_ar - a.forv_ar);

  const dummyBeholdning = Object.entries(pf)
    .filter(([ticker]) => ticker.startsWith('_'))
    .map(([ticker, antall]) => {
      if (antall < 1) return null;
      const meta = dummyMeta[ticker] || {};
      return { ticker, navn: meta.nordnetNavn || ticker, antall, erDummy: true };
    })
    .filter(Boolean);

  const beholdning = sok
    ? alleBeholdning.filter(a => a.ticker.toLowerCase().includes(sok) || a.navn.toLowerCase().includes(sok))
    : alleBeholdning;

  const harBeholdning = alleBeholdning.length > 0 || dummyBeholdning.length > 0;
  document.getElementById('pf-tom').classList.toggle('hidden', harBeholdning);
  document.getElementById('pf-beholdning-wrapper').classList.toggle('hidden', !harBeholdning);
  document.getElementById('pf-tidslinje-wrapper').classList.toggle('hidden', !harBeholdning);
  document.getElementById('pf-inntekt-wrapper').classList.toggle('hidden', !harBeholdning);
  document.getElementById('pf-statistikk-tom').classList.toggle('hidden', harBeholdning);
  document.getElementById('pf-top-strip')?.classList.toggle('hidden', !harBeholdning);
  document.getElementById('pf-mini-sektor-wrapper')?.classList.toggle('hidden', !harBeholdning);
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

  // Fyll sammendrag-strip øverst i Beholdning-fanen
  const topVerdiEl = document.getElementById('pf-top-verdi');
  if (topVerdiEl) topVerdiEl.textContent = fmtKr(totalVerdi);
  const topArEl = document.getElementById('pf-top-ar');
  if (topArEl) topArEl.textContent = fmtKr(totalAr);
  const topYieldEl = document.getElementById('pf-top-yield');
  if (topYieldEl) topYieldEl.textContent = vektetYield > 0 ? vektetYield.toFixed(2) + '%' : '—';
  const topAntallEl = document.getElementById('pf-top-antall');
  if (topAntallEl) topAntallEl.textContent = alleBeholdning.length;

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

    // OSEBX: bruk tidligste kjøpsdato som startpunkt (eller 12 mnd), med støtte for periodebytte
    const alleTxDatoer = Object.values(txMap)
      .flatMap(liste => liste.filter(t => t.type === 'kjøp').map(t => t.dato))
      .sort();
    const forsteTxDato   = alleTxDatoer[0] || null;
    const osebxDatoer    = Object.keys(osebxHistorikk).sort();
    const osebxSluttDato = osebxDatoer[osebxDatoer.length - 1];

    // Behold aktiv periode ved re-render, ellers velg 'kjop' (eller 'ytd' om ingen kjøp)
    const aktivPeriode   = (_pfOsebxState && _pfOsebxState.aktivPeriode) || (forsteTxDato ? 'kjop' : 'ytd');
    const osebxStartDato = _osebxStartForPeriode(aktivPeriode, osebxDatoer, osebxSluttDato, forsteTxDato);

    let osebxPctTotal = null;
    if (osebxStartDato && osebxSluttDato && osebxStartDato !== osebxSluttDato) {
      osebxPctTotal = (osebxHistorikk[osebxSluttDato] - osebxHistorikk[osebxStartDato]) / osebxHistorikk[osebxStartDato] * 100;
    }

    // Lagre tilstand for periodebytte uten full re-render
    _pfOsebxState = { alleBeholdning, pfPct: pfPctTotal, invKost, totalReturnKr, forsteTxDato, aktivPeriode };

    if (osebxEl && pfPctTotal !== null && osebxPctTotal !== null) {
      const diff  = pfPctTotal - osebxPctTotal;
      const slaer = diff >= 0;
      osebxEl.textContent = slaer ? '✓ Ja' : '✗ Nei';
      osebxEl.className   = 'stat-value text-base ' + (slaer ? 'text-green-600 dark:text-green-400' : 'text-red-500');
      if (osebxTekst) osebxTekst.textContent = (diff >= 0 ? '+' : '') + diff.toFixed(1) + '% vs indeks';
    } else if (osebxEl && osebxPctTotal !== null) {
      osebxEl.textContent = (osebxPctTotal >= 0 ? '+' : '') + osebxPctTotal.toFixed(1) + '%';
      osebxEl.className   = 'stat-value text-base ' + (osebxPctTotal >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-red-500');
      const label = { ytd: 'OSEBX YTD', '1ar': 'OSEBX 1 år', kjop: 'OSEBX siden kjøp' }[aktivPeriode] || 'OSEBX';
      if (osebxTekst) osebxTekst.textContent = label;
    } else if (osebxEl) {
      osebxEl.textContent  = '—';
      osebxEl.className    = 'stat-value text-base';
      if (osebxTekst) osebxTekst.textContent = 'oppdateres daglig';
    }
    visOsebxSammenligning(alleBeholdning, pfPctTotal, osebxPctTotal, invKost, totalReturnKr, forsteTxDato, osebxStartDato, osebxSluttDato, aktivPeriode);

    // ── IRR (annualisert intern avkastningsrate) ──────────────────────────────
    const irrEl    = document.getElementById('pf-stat-irr');
    const irrTekst = document.getElementById('pf-stat-irr-tekst');
    if (irrEl) {
      const irr = beregnIRR();
      if (irr.harNokData) {
        const pct = irr.irr_ar;
        irrEl.textContent  = (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%';
        irrEl.className    = 'stat-value text-base ' + (pct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500');
        const mnd = Math.round(irr.periodeAr * 12);
        const aar = irr.periodeAr < 1
          ? (mnd < 1 ? '< 1 mnd' : mnd + ' mnd')
          : irr.periodeAr.toFixed(1) + ' år';
        if (irrTekst) irrTekst.textContent = 'over ' + aar;
      } else {
        irrEl.textContent  = '—';
        irrEl.className    = 'stat-value text-base';
        if (irrTekst) irrTekst.textContent = irr.forKort ? 'trenger 30 dager' : 'trenger transaksjoner';
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
      <td colspan="10" class="px-4 pb-4 bg-gray-50 dark:bg-gray-900/30 border-b border-gray-100 dark:border-gray-800" style="border-left:3px solid #4f7bcc">
        ${byggDetailHtml(a.ticker, kb, marked)}
      </td>
    </tr>`;
  }).join('');

  // Dummy-rader nederst i tabellen
  if (dummyBeholdning.length) {
    tbody.innerHTML += `<tr><td colspan="10" class="px-4 pt-4 pb-1 text-xs text-gray-400 dark:text-gray-600 uppercase tracking-wide">Plassholdere (ikke tilgjengelig i appen ennå)</td></tr>` +
      dummyBeholdning.map(a => {
        const kb = beregnKostbasis(a.ticker);
        const harKb = kb.antall > 0 && kb.totalKost > 0;
        const kostTd = harKb ? `<span class="text-xs">${fmtKr(kb.totalKost)}</span><br><span class="text-xs text-gray-400">${kb.vwap.toLocaleString('nb-NO',{maximumFractionDigits:1})} kr/stk</span>` : '—';
        const isOpen = _aapneDetailRader.has(a.ticker);
        return `
    <tr class="table-row opacity-50" data-ticker="${escHtml(a.ticker)}">
      <td class="px-4 py-3 font-mono text-xs text-gray-400 dark:text-gray-600">—</td>
      <td class="px-4 py-3 hidden sm:table-cell text-gray-500 dark:text-gray-500 text-sm italic">${escHtml(a.navn)}</td>
      <td class="px-4 py-3 text-right text-sm text-gray-500">${a.antall}</td>
      <td class="px-4 py-3 text-right text-gray-400 text-xs">—</td>
      <td class="px-4 py-3 text-right text-gray-400 text-xs">—</td>
      <td class="px-4 py-3 text-right hidden lg:table-cell text-sm">${kostTd}</td>
      <td class="px-4 py-3 text-right hidden lg:table-cell text-sm text-gray-400">—</td>
      <td class="px-4 py-3 text-center hidden sm:table-cell text-gray-400 text-xs">—</td>
      <td class="px-4 py-3 text-center hidden sm:table-cell"><span class="text-xs text-amber-500 dark:text-amber-400">plassholder</span></td>
      <td class="px-4 py-3 text-center">
        <div class="flex items-center justify-center gap-1">
          <button class="pf-detail-toggle p-1 text-gray-400 hover:text-brand-500 transition-colors" data-ticker="${escHtml(a.ticker)}" aria-label="Vis transaksjoner" aria-expanded="${isOpen}">
            <svg class="w-4 h-4 pointer-events-none transition-transform${isOpen ? ' rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
          </button>
          <button class="pf-slett p-1 text-gray-400 hover:text-red-500 transition-colors" data-ticker="${escHtml(a.ticker)}" aria-label="Fjern">
            <svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
      </td>
    </tr>
    <tr class="pf-detail-rad${isOpen ? '' : ' hidden'}" data-for="${escHtml(a.ticker)}">
      <td colspan="10" class="px-4 pb-4 bg-gray-50 dark:bg-gray-900/30 border-b border-gray-100 dark:border-gray-800" style="border-left:3px solid #d97706">
        ${byggDetailHtml(a.ticker, kb, 0)}
      </td>
    </tr>`;
      }).join('');
  }

  // Sum-rad i footer
  document.getElementById('pf-tabell-footer').innerHTML = `
    <tr>
      <td colspan="2" class="px-4 py-3 text-sm text-gray-500">Totalt (${alleBeholdning.length} selskaper)</td>
      <td class="px-4 py-3 text-right text-sm text-gray-500">${alleBeholdning.reduce((s,a)=>s+a.antall,0)} aksjer</td>
      <td></td>
      <td class="px-4 py-3 text-right text-brand-700 dark:text-brand-400">${fmtKr(totalAr)}</td>
      <td colspan="5"></td>
    </tr>`;

  // Mobilkort med utvidbare detalj-paneler
  const kortBody = document.getElementById('pf-kort-body');
  if (kortBody) {
    kortBody.innerHTML = beholdning.map(a => {
      const kb     = beregnKostbasis(a.ticker);
      const harKb  = kb.antall > 0 && kb.totalKost > 0;
      const marked = a.antall * (a.pris || 0);
      const gevinst = harKb ? marked - kb.totalKost : null;
      const gevFarge = gevinst !== null ? (gevinst >= 0 ? 'color:#16a34a' : 'color:#ef4444') : '';
      const isOpen   = _aapneDetailRader.has(a.ticker);
      return `<div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
        <div class="p-3 flex items-start justify-between gap-2 cursor-pointer select-none pf-kort-header" data-ticker="${escHtml(a.ticker)}">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="font-mono font-bold text-brand-700 dark:text-brand-400">${escHtml(a.ticker)}</span>
              <span class="yield-badge ${yieldKlasse(a.utbytte_yield)}">${a.utbytte_yield.toFixed(2)}%</span>
            </div>
            <div class="text-xs text-gray-500 dark:text-gray-400 truncate">${escHtml(a.navn)}</div>
            <div class="flex items-center gap-3 mt-1.5 text-xs">
              <span class="text-gray-500">${a.antall} aksjer${a.pris ? ' · ' + a.pris.toLocaleString('nb-NO', {maximumFractionDigits: 2}) + ' kr' : ''}</span>
              <span class="font-semibold text-brand-700 dark:text-brand-400 ml-auto">${fmtKr(a.forv_ar)}/år</span>
            </div>
            ${gevinst !== null ? `<div class="mt-1 text-xs font-medium" style="${gevFarge}">${gevinst >= 0 ? '+' : ''}${fmtKr(gevinst)} (${(gevinst / kb.totalKost * 100).toFixed(1)}%)</div>` : ''}
          </div>
          <svg class="w-4 h-4 text-gray-400 shrink-0 mt-0.5 transition-transform${isOpen ? ' rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div class="pf-kort-detalj pf-detail-rad${isOpen ? '' : ' hidden'} border-t border-gray-100 dark:border-gray-800 px-3 pb-3" style="border-left:3px solid #4f7bcc" data-for="${escHtml(a.ticker)}">
          ${byggDetailHtml(a.ticker, kb, marked)}
        </div>
      </div>`;
    }).join('');

    // Dummy-kort mobilvisning
    if (dummyBeholdning.length) {
      kortBody.innerHTML += `<div class="text-xs text-gray-400 dark:text-gray-600 uppercase tracking-wide px-1 pt-2">Plassholdere</div>` +
        dummyBeholdning.map(a => {
          const kb    = beregnKostbasis(a.ticker);
          const isOpen = _aapneDetailRader.has(a.ticker);
          return `<div class="bg-white dark:bg-gray-900 rounded-xl border border-amber-200 dark:border-amber-900/40 shadow-sm overflow-hidden opacity-60">
        <div class="p-3 flex items-start justify-between gap-2 cursor-pointer select-none pf-kort-header" data-ticker="${escHtml(a.ticker)}">
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="text-xs text-amber-600 dark:text-amber-400 font-medium">Plassholder</span>
            </div>
            <div class="text-sm text-gray-600 dark:text-gray-400 italic">${escHtml(a.navn)}</div>
            <div class="text-xs text-gray-400 mt-1">${a.antall} aksjer · data mangler</div>
          </div>
          <svg class="w-4 h-4 text-gray-400 shrink-0 mt-0.5 transition-transform${isOpen ? ' rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
        </div>
        <div class="pf-kort-detalj pf-detail-rad${isOpen ? '' : ' hidden'} border-t border-amber-100 dark:border-amber-900/30 px-3 pb-3" style="border-left:3px solid #d97706" data-for="${escHtml(a.ticker)}">
          ${byggDetailHtml(a.ticker, kb, 0)}
        </div>
      </div>`;
        }).join('');
    }

    kortBody.onclick = e => {
      // Klikk inne i detalj-panel — håndter knapper
      if (e.target.closest('.pf-kort-detalj')) {
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
        return;
      }
      // Klikk på korthodet → toggle detalj
      const header = e.target.closest('.pf-kort-header');
      if (!header) return;
      const ticker = header.dataset.ticker;
      const isOpen = _aapneDetailRader.has(ticker);
      if (isOpen) _aapneDetailRader.delete(ticker); else _aapneDetailRader.add(ticker);
      const panel  = kortBody.querySelector(`.pf-kort-detalj[data-for="${ticker}"]`);
      const chevron = header.querySelector('svg');
      if (panel)  panel.classList.toggle('hidden', isOpen);
      if (chevron) chevron.style.transform = isOpen ? '' : 'rotate(180deg)';
    };
  }

  // Sektorfordeling
  visMiniSektorChart(alleBeholdning);

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
      const ticker2 = slett.dataset.ticker;
      const pf2 = hentPF();
      delete pf2[ticker2];
      lagrePF(pf2);
      if (ticker2.startsWith('_')) {
        const meta2 = hentDummyMeta();
        delete meta2[ticker2];
        lagreDummyMeta(meta2);
      }
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
  if (aktivStatsTab === 'sektorer')      { visHHI(alleBeholdning); visSektorYieldChart(alleBeholdning); visCharts(alleBeholdning, totalAr); }
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

// ── HHI-KONSENTRASJONSINDEKS ──────────────────────────────────────────────
function visHHI(beholdning) {
  if (!document.getElementById('hhi-aksje-score')) return;

  const totalVerdi = beholdning.reduce((s, a) => s + a.antall * (a.pris || 0), 0);
  if (totalVerdi <= 0) return;

  // HHI per aksje (basert på markedsverdi)
  const hhiAksje = beholdning.reduce((s, a) => {
    const andel = (a.antall * (a.pris || 0)) / totalVerdi * 100;
    return s + andel * andel;
  }, 0);

  // HHI per sektor
  const sektorMap = {};
  beholdning.forEach(a => {
    sektorMap[a.sektor || 'Ukjent'] = (sektorMap[a.sektor || 'Ukjent'] || 0) + a.antall * (a.pris || 0);
  });
  const hhiSektor = Object.values(sektorMap).reduce((s, v) => {
    const andel = v / totalVerdi * 100;
    return s + andel * andel;
  }, 0);

  function hhiInfo(hhi) {
    if (hhi < 1000)  return { farge: '#16a34a', tekst: 'Godt diversifisert' };
    if (hhi < 2500)  return { farge: '#d97706', tekst: 'Moderat konsentrasjon' };
    return               { farge: '#dc2626', tekst: 'Høy konsentrasjon' };
  }

  const ia = hhiInfo(hhiAksje), is_ = hhiInfo(hhiSektor);

  document.getElementById('hhi-aksje-score').textContent = Math.round(hhiAksje).toLocaleString('nb');
  document.getElementById('hhi-aksje-score').style.color = ia.farge;
  document.getElementById('hhi-aksje-label').textContent = ia.tekst;
  document.getElementById('hhi-aksje-label').style.color = ia.farge;

  document.getElementById('hhi-sektor-score').textContent = Math.round(hhiSektor).toLocaleString('nb');
  document.getElementById('hhi-sektor-score').style.color = is_.farge;
  document.getElementById('hhi-sektor-label').textContent = is_.tekst;
  document.getElementById('hhi-sektor-label').style.color = is_.farge;

  // Finn dominerende aksje og sektor
  const toppAksje = [...beholdning].sort((a, b) =>
    (b.antall * (b.pris || 0)) - (a.antall * (a.pris || 0)))[0];
  const toppSektor = Object.entries(sektorMap).sort((a, b) => b[1] - a[1])[0];

  const toppAksjeAndel = toppAksje ? (toppAksje.antall * (toppAksje.pris || 0) / totalVerdi * 100).toFixed(1) : 0;
  const toppSektorAndel = toppSektor ? (toppSektor[1] / totalVerdi * 100).toFixed(1) : 0;

  document.getElementById('hhi-detaljer').innerHTML =
    `<p>📌 Største aksjeposisjon: <strong>${toppAksje?.ticker || '—'}</strong> (${toppAksjeAndel}% av porteføljen)</p>` +
    `<p>📌 Største sektor: <strong>${toppSektor?.[0] || '—'}</strong> (${toppSektorAndel}% av porteføljen)</p>` +
    `<p class="mt-1 text-gray-400">HHI &lt; 1 000 = diversifisert · 1 000–2 500 = moderat · &gt; 2 500 = konsentrert</p>`;
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

function _rebalSlug(sektor) {
  return sektor.toLowerCase()
    .replace(/æ/g, 'ae').replace(/ø/g, 'o').replace(/å/g, 'a')
    .replace(/\s+/g, '-');
}

function visRebalansering(alleBeholdning) {
  const el     = document.getElementById('rebal-rader');
  const hdrEl  = document.getElementById('rebal-header-info');
  if (!el) return;

  const fmtKr = v => v.toLocaleString('nb-NO', { maximumFractionDigits: 0 }) + ' kr';

  const totalVerdi = alleBeholdning.reduce((s, a) => s + a.antall * (a.pris || 0), 0);
  if (totalVerdi <= 0) {
    el.innerHTML = '<p class="text-xs text-gray-400 dark:text-gray-500 text-center py-6">Legg til aksjer med kurs for å se rebalansering.</p>';
    if (hdrEl) hdrEl.innerHTML = '';
    return;
  }

  // Grupper etter sektor (portefølje)
  const sektorMap = {};
  alleBeholdning.forEach(a => {
    const v = a.antall * (a.pris || 0);
    if (a.sektor) sektorMap[a.sektor] = (sektorMap[a.sektor] || 0) + v;
  });

  // Tell aksjer og legg til sektorer uten holdings
  const sektorAntall = {};
  const sektorIPortefolje = {};
  (window.alleAksjer || []).forEach(a => {
    if (!a.sektor) return;
    sektorAntall[a.sektor] = (sektorAntall[a.sektor] || 0) + 1;
    if (!(a.sektor in sektorMap)) sektorMap[a.sektor] = 0;
  });
  alleBeholdning.forEach(a => {
    if (a.sektor) sektorIPortefolje[a.sektor] = (sektorIPortefolje[a.sektor] || 0) + 1;
  });

  const sektorer = Object.entries(sektorMap).sort((a, b) => b[1] - a[1]);
  const maal = hentRebalanseringsmaal();

  // Beregn mål-sum
  const totalMaal = sektorer.reduce((s, [sek]) => {
    return s + (maal[sek] !== undefined ? maal[sek] : Math.round(sektorMap[sek] / totalVerdi * 100));
  }, 0);
  const maalOk = Math.abs(totalMaal - 100) <= 1;

  // Vis bare sektorer med aktivitet (skjul-toggle)
  const skjulTomme = localStorage.getItem('rebal-skjul-tomme') !== 'false';

  // Header-info
  if (hdrEl) {
    const maalFarge = maalOk ? 'text-green-600 dark:text-green-400' : 'text-orange-500';
    hdrEl.innerHTML = `
      <div class="flex items-center gap-1.5">
        <span class="text-xs text-gray-500 dark:text-gray-400">Total mål:</span>
        <span class="text-xs font-semibold ${maalFarge}">${totalMaal}%</span>
        ${maalOk
          ? '<span class="text-[10px] bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-400 rounded-full px-1.5 py-0.5">✓ OK</span>'
          : '<span class="text-[10px] bg-orange-100 dark:bg-orange-900/40 text-orange-600 dark:text-orange-400 rounded-full px-1.5 py-0.5">bør være 100%</span>'
        }
      </div>
      <label class="flex items-center gap-1.5 cursor-pointer select-none">
        <input type="checkbox" id="rebal-skjul-cb" ${skjulTomme ? 'checked' : ''} class="w-3.5 h-3.5 accent-brand-600">
        <span class="text-xs text-gray-400 dark:text-gray-500">Skjul tomme</span>
      </label>`;
    hdrEl.querySelector('#rebal-skjul-cb')?.addEventListener('change', e => {
      localStorage.setItem('rebal-skjul-tomme', e.target.checked ? 'true' : 'false');
      visRebalansering(alleBeholdning);
    });
  }

  // Render rader
  el.innerHTML = sektorer.map(([sektor, verdi]) => {
    const naaværendePct = verdi / totalVerdi * 100;
    const maalPct = maal[sektor] !== undefined ? maal[sektor] : Math.round(naaværendePct);

    // Skjul tomme sektorer hvis toggle er på
    if (skjulTomme && naaværendePct === 0 && maalPct === 0) return '';

    const diff = naaværendePct - maalPct;
    const totalt = sektorAntall[sektor] || 0;
    const eid    = sektorIPortefolje[sektor] || 0;
    const slug   = _rebalSlug(sektor);

    let statusKlasse, statusTekst, barFarge, kjopLenke = '';
    if (maalPct === 0 && naaværendePct === 0) {
      statusKlasse = 'text-gray-400'; statusTekst = '—'; barFarge = 'bg-gray-300 dark:bg-gray-700';
    } else if (maalPct > 0 && naaværendePct === 0) {
      const kr = maalPct / 100 * totalVerdi;
      statusKlasse = 'text-orange-500'; statusTekst = `Kjøp +${maalPct}% · ${fmtKr(kr)}`; barFarge = 'bg-orange-400';
      kjopLenke = `<a href="/aksjer/sektor/${slug}/" class="text-[11px] text-brand-600 dark:text-brand-400 font-medium hover:underline shrink-0">Utforsk aksjer →</a>`;
    } else if (Math.abs(diff) <= 5) {
      statusKlasse = 'text-green-600 dark:text-green-400'; statusTekst = 'OK'; barFarge = 'bg-green-500';
    } else if (diff < -5) {
      const kr = Math.abs(diff) / 100 * totalVerdi;
      statusKlasse = 'text-orange-500'; statusTekst = `Kjøp +${Math.abs(diff).toFixed(0)}% · ${fmtKr(kr)}`; barFarge = 'bg-orange-400';
      kjopLenke = `<a href="/aksjer/sektor/${slug}/" class="text-[11px] text-brand-600 dark:text-brand-400 font-medium hover:underline shrink-0">Finn aksjer →</a>`;
    } else {
      const kr = Math.abs(diff) / 100 * totalVerdi;
      statusKlasse = 'text-red-500'; statusTekst = `Reduser −${diff.toFixed(0)}% · ${fmtKr(kr)}`; barFarge = 'bg-red-400';
    }

    const chipTekst = totalt > 0
      ? (eid > 0 ? `${eid} av ${totalt} aksjer` : `${totalt} tilgjengelig`)
      : '';

    const barBredde  = Math.min(100, naaværendePct).toFixed(1);
    const maalBredde = Math.min(100, maalPct).toFixed(1);

    return `
      <div class="py-3" data-sektor="${sektor}">
        <div class="flex items-center justify-between gap-2 mb-1">
          <div class="min-w-0">
            <div class="flex items-center gap-1.5 flex-wrap">
              <a href="/aksjer/sektor/${slug}/"
                 class="text-sm font-semibold text-gray-900 dark:text-gray-100 hover:text-brand-600 dark:hover:text-brand-400 hover:underline">${sektor}</a>
              ${chipTekst ? `<span class="text-xs ${eid > 0 ? 'text-brand-500 dark:text-brand-400' : 'text-gray-400 dark:text-gray-500'} shrink-0">${chipTekst}</span>` : ''}
            </div>
            <div class="flex items-center gap-2 mt-0.5 flex-wrap">
              <p class="text-xs ${statusKlasse}">${statusTekst}</p>
              ${kjopLenke}
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <span class="text-xs text-gray-400 dark:text-gray-600">${naaværendePct.toFixed(1)}% →</span>
            <input type="number" min="0" max="100" step="1" value="${maalPct}"
              class="w-12 text-xs text-center border border-gray-200 dark:border-gray-700 rounded-md px-1 py-1 bg-white dark:bg-gray-800 focus:outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-400/30"
              data-rebal-sektor="${sektor}" />
            <span class="text-xs text-gray-400 dark:text-gray-600">%</span>
          </div>
        </div>
        <div class="relative h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden mt-1.5">
          <div class="absolute inset-y-0 left-0 bg-gray-300 dark:bg-gray-700 rounded-full" style="width:${maalBredde}%"></div>
          <div class="absolute inset-y-0 left-0 ${barFarge} rounded-full transition-all duration-300" style="width:${barBredde}%"></div>
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

function visAnalyse() {
  const el = document.getElementById('pf-sub-analyse');
  if (!el) return;

  const pf = hentPF();
  const beholdning = Object.entries(pf)
    .map(([ticker, antall]) => {
      const a = (window.alleAksjer || []).find(x => x.ticker === ticker);
      if (!a || !antall) return null;
      const verdi = antall * (a.pris || 0);
      return { ...a, antall, verdi, forv_ar: antall * (a.utbytte_per_aksje || 0) };
    })
    .filter(Boolean);

  if (beholdning.length === 0) {
    el.innerHTML = `<div class="text-center py-10 text-gray-400 dark:text-gray-600">
      <svg class="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
      <p class="text-sm font-medium">Ingen beholdning</p>
      <p class="text-xs mt-1">Legg til aksjer i Beholdning for å se porteføljeanalysen.</p>
    </div>`;
    return;
  }

  const totalVerdi = beholdning.reduce((s, a) => s + a.verdi, 0);
  const isDark = document.documentElement.classList.contains('dark');

  // ── DIMENSJON 1: Diversifisering ─────────────────────────────────────
  const antallAksjer = beholdning.length;
  const sektorSett = new Set(beholdning.map(a => a.sektor).filter(Boolean));
  const antallSektorer = sektorSett.size;
  const d1Aksjer = antallAksjer >= 15 ? 10 : antallAksjer >= 10 ? 9 : antallAksjer >= 6 ? 6 : antallAksjer >= 3 ? 3 : 1;
  const d1Sekt  = antallSektorer >= 6 ? 10 : antallSektorer >= 5 ? 9 : antallSektorer >= 4 ? 7 : antallSektorer >= 3 ? 5 : antallSektorer >= 2 ? 3 : 0;
  const d1 = Math.min(20, d1Aksjer + d1Sekt);

  const d1Tekst = antallAksjer < 6
    ? `Du har kun ${antallAksjer} aksje${antallAksjer === 1 ? '' : 'r'} i ${antallSektorer} sektor${antallSektorer === 1 ? '' : 'er'}. Anbefalt: 12–18 aksjer i minst 5 sektorer.`
    : antallAksjer > 25
    ? `${antallAksjer} aksjer er mye — risikoen for «dyr indeks» øker. Vurder å konsentrere om de beste 15–20.`
    : antallSektorer < 4
    ? `${antallAksjer} aksjer, men bare ${antallSektorer} sektorer. God spredning innad, men sektorkonsentrasjonen er høy.`
    : `${antallAksjer} aksjer fordelt på ${antallSektorer} sektorer — god diversifisering.`;

  // ── DIMENSJON 2: Konsentrasjonsrisiko ────────────────────────────────
  const posisjoner = beholdning
    .map(a => ({ ticker: a.ticker, navn: a.navn, pct: totalVerdi > 0 ? a.verdi / totalVerdi * 100 : 0 }))
    .sort((a, b) => b.pct - a.pct);
  const storstePos = posisjoner[0];

  const sektorVerdier = {};
  beholdning.forEach(a => {
    const s = a.sektor || 'Ukjent';
    sektorVerdier[s] = (sektorVerdier[s] || 0) + a.verdi;
  });
  const sektorArr = Object.entries(sektorVerdier)
    .map(([s, v]) => ({ sektor: s, pct: totalVerdi > 0 ? v / totalVerdi * 100 : 0 }))
    .sort((a, b) => b.pct - a.pct);
  const storsteSektor = sektorArr[0] || { sektor: '—', pct: 0 };

  const posScore  = storstePos.pct < 10 ? 10 : storstePos.pct < 15 ? 8 : storstePos.pct < 20 ? 5 : storstePos.pct < 30 ? 2 : 0;
  const sektScore = storsteSektor.pct < 25 ? 10 : storsteSektor.pct < 35 ? 7 : storsteSektor.pct < 45 ? 4 : storsteSektor.pct < 60 ? 2 : 0;
  const d2 = Math.min(20, posScore + sektScore);

  const d2Tekst = storsteSektor.pct > 35
    ? `${storsteSektor.sektor} utgjør ${storsteSektor.pct.toFixed(0)}% av porteføljen — over anbefalt maks på 30%. Største enkeltposisjon er ${escHtml(storstePos.navn)} med ${storstePos.pct.toFixed(1)}%.`
    : storstePos.pct > 15
    ? `${escHtml(storstePos.navn)} (${storstePos.ticker}) er din største posisjon med ${storstePos.pct.toFixed(1)}% — vurder å spre litt mer. Største sektor er ${storsteSektor.sektor} med ${storsteSektor.pct.toFixed(0)}%.`
    : `Lav konsentrasjonsrisiko. Største posisjon er ${escHtml(storstePos.navn)} med ${storstePos.pct.toFixed(1)}%, største sektor ${storsteSektor.sektor} med ${storsteSektor.pct.toFixed(0)}%.`;

  // ── DIMENSJON 3: Risikoprofil ─────────────────────────────────────────
  const SYKLISKE = new Set(['Energi', 'Shipping', 'Skipsfart', 'Havbruk', 'Energitjenester']);
  const sykliskVerdi = beholdning.filter(a => SYKLISKE.has(a.sektor)).reduce((s, a) => s + a.verdi, 0);
  const sykliskPct   = totalVerdi > 0 ? sykliskVerdi / totalVerdi * 100 : 0;
  const d3 = sykliskPct < 20 ? 20 : sykliskPct < 30 ? 17 : sykliskPct < 40 ? 13 : sykliskPct < 50 ? 9 : sykliskPct < 60 ? 5 : 2;

  const d3Tekst = sykliskPct < 20
    ? `Lav eksponering mot sykliske sektorer (${sykliskPct.toFixed(0)}%). Porteføljen er godt forankret i stabile inntektskilder.`
    : sykliskPct < 40
    ? `${sykliskPct.toFixed(0)}% i sykliske sektorer (energi, shipping, havbruk) — akseptabelt nivå. Vær forberedt på utbyttesvingninger ved markedsfall.`
    : `${sykliskPct.toFixed(0)}% er i sykliske sektorer. Disse kan kutte utbyttet kraftig ved lav oljepris eller svake fraktrater — vurder å øke stabileandelen.`;

  // ── DIMENSJON 4: Yield-bærekraft ──────────────────────────────────────
  const medPayout = beholdning.filter(a => (a.payout_ratio || 0) > 0 && (a.payout_ratio || 0) < 400);
  const snittPayout = medPayout.length > 0
    ? medPayout.reduce((s, a) => s + a.payout_ratio, 0) / medPayout.length
    : null;
  const hoeyYieldAksjer = beholdning.filter(a => (a.utbytte_yield || 0) > 15);
  const hoeyYieldPct    = totalVerdi > 0
    ? hoeyYieldAksjer.reduce((s, a) => s + a.verdi, 0) / totalVerdi * 100
    : 0;

  const payoutScore    = snittPayout === null ? 10 : snittPayout < 40 ? 15 : snittPayout < 60 ? 12 : snittPayout < 75 ? 8 : snittPayout < 90 ? 4 : 0;
  const hoeyYieldScore = hoeyYieldPct < 5 ? 5 : hoeyYieldPct < 15 ? 2 : 0;
  const d4 = Math.min(20, payoutScore + hoeyYieldScore);

  const d4PayoutTekst = snittPayout === null
    ? 'Payout ratio-data mangler for dine aksjer.'
    : snittPayout > 80
    ? `Snitt payout ratio er ${snittPayout.toFixed(0)}% — høyt. Mange selskaper har lite buffer mot inntjeningsfall.`
    : snittPayout > 60
    ? `Snitt payout ratio er ${snittPayout.toFixed(0)}% — akseptabelt, men følg med på inntjeningen.`
    : `Snitt payout ratio er ${snittPayout.toFixed(0)}% — godt nivå med buffer til å opprettholde utbyttet.`;
  const d4Tekst = hoeyYieldAksjer.length > 0
    ? `${d4PayoutTekst} ${hoeyYieldAksjer.length} aksje${hoeyYieldAksjer.length > 1 ? 'r' : ''} (${hoeyYieldAksjer.map(a => a.ticker).join(', ')}) har yield over 15% — vurder bærekraften.`
    : d4PayoutTekst;

  // ── DIMENSJON 5: Inntektsstabilitet ──────────────────────────────────
  const medAr = beholdning.filter(a => (a.ar_med_utbytte || 0) > 0);
  const snittAr = medAr.length > 0
    ? medAr.reduce((s, a) => s + a.ar_med_utbytte, 0) / medAr.length
    : 0;
  const d5 = snittAr >= 20 ? 20 : snittAr >= 15 ? 17 : snittAr >= 10 ? 13 : snittAr >= 5 ? 8 : 3;

  const d5Tekst = snittAr >= 15
    ? `Selskapene dine har i snitt betalt utbytte i ${snittAr.toFixed(0)} år — sterk track record gjennom ulike markedsperioder.`
    : snittAr >= 10
    ? `${snittAr.toFixed(0)} år i snitt er bra, men det er rom for flere stabile langsiktige utbyttebetalere (mål: 15+ år).`
    : snittAr >= 5
    ? `Snitt ${snittAr.toFixed(0)} år med utbytte. Porteføljen mangler erfarne utbyttebetalere — legg til selskaper med 15+ år.`
    : `Kort utbyttehistorikk (snitt ${snittAr.toFixed(0)} år). Prioriter etablerte utbyttebetalere for mer stabil inntekt.`;

  // ── Totalscore og helseetikett ────────────────────────────────────────
  const total = d1 + d2 + d3 + d4 + d5;
  const helseLabel = total >= 80 ? 'Utmerket' : total >= 65 ? 'God' : total >= 50 ? 'Middels' : 'Svak';
  const ringFarge  = total >= 75 ? '#22c55e' : total >= 50 ? '#eab308' : '#ef4444';
  const trackFarge = isDark ? '#1f2937' : '#e5e7eb';
  const innerBg    = isDark ? '#111827' : '#ffffff';
  const conicDeg   = (total / 100 * 360).toFixed(1);

  // ── Forbedringspunkter ────────────────────────────────────────────────
  const tips = [];
  if (d1 < 12) tips.push('Legg til aksjer i nye sektorer — se oversikt under <strong>Sektorer</strong>.');
  if (d2 < 12 && storsteSektor.pct > 35) tips.push(`Spre litt ut av <strong>${escHtml(storsteSektor.sektor)}</strong> — bruk <strong>Rebalansering</strong>-fanen for å beregne kjøpsbehov.`);
  if (d2 < 12 && storstePos.pct > 20) tips.push(`Reduser <strong>${storstePos.ticker}</strong> til under 15% av porteføljen.`);
  if (d3 < 12) tips.push('Øk andelen i stabile sektorer som sparebanker, IT-konsulenter eller forsyning.');
  if (d4 < 12) tips.push('Se etter aksjer med payout ratio under 70% og yield i 4–10%-spennet.');
  if (d5 < 12) tips.push('Prioriter selskaper med 15+ år med sammenhengende utbytte — f.eks. etablerte sparebanker.');

  // ── Hjelpefunksjoner for HTML ─────────────────────────────────────────
  function dimFarge(score, max) {
    const r = score / max;
    return r >= 0.75 ? '#15803d' : r >= 0.5 ? '#a16207' : '#b91c1c';
  }
  function dimBar(score, max) {
    const pct = (score / max * 100).toFixed(0);
    const farge = dimFarge(score, max);
    return `<div style="height:6px;background:${trackFarge};border-radius:99px;overflow:hidden;flex:1;">
      <div style="height:100%;width:${pct}%;background:${farge};border-radius:99px;transition:width .3s;"></div>
    </div>`;
  }
  function dimKort(id, tittel, score, max, tekst, detaljHtml) {
    const farge = dimFarge(score, max);
    return `<div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm overflow-hidden">
      <div class="p-4 cursor-pointer select-none" data-analyse-dim="${id}">
        <div class="flex items-center justify-between gap-2 mb-2">
          <span class="text-sm font-semibold text-gray-900 dark:text-gray-100">${tittel}</span>
          <div class="flex items-center gap-2.5 shrink-0">
            <span class="text-sm font-bold tabular-nums" style="color:${farge};">${score}<span class="text-xs font-normal text-gray-400 dark:text-gray-600">&#8202;/&#8202;20</span></span>
            <svg data-analyse-chevron="${id}" style="width:16px;height:16px;color:#9ca3af;transition:transform .2s;flex-shrink:0;" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd"/></svg>
          </div>
        </div>
        <div class="flex items-center gap-2 mb-2.5">${dimBar(score, max)}</div>
        <p class="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">${tekst}</p>
      </div>
      <div class="hidden" data-analyse-panel="${id}">
        <div class="border-t border-gray-100 dark:border-gray-800 px-4 py-3">
          ${detaljHtml}
        </div>
      </div>
    </div>`;
  }

  // ── Detaljpanel D1: Diversifisering ──────────────────────────────────
  const detaljD1 = '<p class="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-2">Sektorfordeling</p>'
    + sektorArr.map(function(s) {
        const aksjer = beholdning.filter(function(a) { return (a.sektor || 'Ukjent') === s.sektor; });
        const sf = s.pct > 35 ? 'color:#ef4444' : s.pct > 25 ? 'color:#d97706' : 'color:#15803d';
        return '<div class="flex items-start gap-2 py-1.5 border-b border-gray-100 dark:border-gray-800 last:border-0">'
          + '<div class="flex-1 min-w-0">'
          + '<span class="text-xs font-medium text-gray-800 dark:text-gray-200">' + escHtml(s.sektor) + '</span>'
          + '<div class="text-xs text-gray-400 dark:text-gray-600 mt-0.5">' + aksjer.map(function(a) { return escHtml(a.ticker); }).join(' · ') + '</div>'
          + '</div>'
          + '<span class="text-xs tabular-nums font-medium shrink-0" style="' + sf + '">' + s.pct.toFixed(0) + '%</span>'
          + '</div>';
      }).join('');

  // ── Detaljpanel D2: Konsentrasjonsrisiko ─────────────────────────────
  const detaljD2 = '<p class="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-2">Posisjoner etter størrelse</p>'
    + posisjoner.map(function(p) {
        const pf = p.pct > 20 ? 'color:#ef4444' : p.pct > 15 ? 'color:#d97706' : 'color:#6b7280';
        const adv = p.pct > 20 ? ' <span style="color:#ef4444;font-size:0.65rem;">⚠ Høy</span>' : p.pct > 15 ? ' <span style="color:#d97706;font-size:0.65rem;">↑</span>' : '';
        return '<div class="flex items-center gap-2 py-1.5 border-b border-gray-100 dark:border-gray-800 last:border-0">'
          + '<span class="text-xs font-medium text-gray-800 dark:text-gray-200 w-14 shrink-0">' + escHtml(p.ticker) + '</span>'
          + '<span class="text-xs text-gray-400 dark:text-gray-600 flex-1 truncate">' + escHtml(p.navn) + '</span>'
          + '<span class="text-xs tabular-nums font-medium shrink-0" style="' + pf + '">' + p.pct.toFixed(1) + '%' + adv + '</span>'
          + '</div>';
      }).join('');

  // ── Detaljpanel D3: Risikoprofil ─────────────────────────────────────
  const sykliskeAksjer = beholdning.filter(function(a) { return SYKLISKE.has(a.sektor); }).sort(function(a, b) { return b.verdi - a.verdi; });
  const stabileAksjer  = beholdning.filter(function(a) { return !SYKLISKE.has(a.sektor); }).sort(function(a, b) { return b.verdi - a.verdi; });
  const detaljD3 = (sykliskeAksjer.length > 0
      ? '<p class="text-xs font-semibold uppercase tracking-widest mb-1.5" style="color:#d97706;">Sykliske — ' + sykliskPct.toFixed(0) + '%</p>'
        + sykliskeAksjer.map(function(a) {
            const pct = totalVerdi > 0 ? (a.verdi / totalVerdi * 100).toFixed(1) : '0.0';
            return '<div class="flex items-center gap-2 py-1 border-b border-gray-100 dark:border-gray-800 last:border-0">'
              + '<span class="text-xs font-medium text-gray-800 dark:text-gray-200 w-14 shrink-0">' + escHtml(a.ticker) + '</span>'
              + '<span class="text-xs text-gray-500 dark:text-gray-400 flex-1">' + escHtml(a.sektor || '') + '</span>'
              + '<span class="text-xs tabular-nums" style="color:#d97706;">' + pct + '%</span>'
              + '</div>';
          }).join('')
        + '<div class="mb-3"></div>'
      : '')
    + (stabileAksjer.length > 0
      ? '<p class="text-xs font-semibold uppercase tracking-widest mb-1.5" style="color:#15803d;">Stabile — ' + (100 - sykliskPct).toFixed(0) + '%</p>'
        + stabileAksjer.map(function(a) {
            const pct = totalVerdi > 0 ? (a.verdi / totalVerdi * 100).toFixed(1) : '0.0';
            return '<div class="flex items-center gap-2 py-1 border-b border-gray-100 dark:border-gray-800 last:border-0">'
              + '<span class="text-xs font-medium text-gray-800 dark:text-gray-200 w-14 shrink-0">' + escHtml(a.ticker) + '</span>'
              + '<span class="text-xs text-gray-500 dark:text-gray-400 flex-1">' + escHtml(a.sektor || '') + '</span>'
              + '<span class="text-xs tabular-nums" style="color:#15803d;">' + pct + '%</span>'
              + '</div>';
          }).join('')
      : '');

  // ── Detaljpanel D4: Yield-bærekraft ──────────────────────────────────
  const d4Rader = beholdning.slice().sort(function(a, b) {
    const ar = ((a.utbytte_yield || 0) > 15 ? 2 : 0) + ((a.payout_ratio || 0) > 80 && (a.payout_ratio || 0) < 400 ? 1 : 0);
    const br = ((b.utbytte_yield || 0) > 15 ? 2 : 0) + ((b.payout_ratio || 0) > 80 && (b.payout_ratio || 0) < 400 ? 1 : 0);
    return br - ar || ((b.payout_ratio || 0) - (a.payout_ratio || 0));
  });
  const detaljD4 = '<p class="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-2">Yield og payout ratio per aksje</p>'
    + d4Rader.map(function(a) {
        const y   = a.utbytte_yield ? a.utbytte_yield.toFixed(1) + '%' : '—';
        const p   = (a.payout_ratio > 0 && a.payout_ratio < 400) ? a.payout_ratio.toFixed(0) + '%' : '—';
        const hiY = (a.utbytte_yield || 0) > 15;
        const hiP = (a.payout_ratio || 0) > 80 && (a.payout_ratio || 0) < 400;
        const yF  = hiY ? 'color:#ef4444' : (a.utbytte_yield || 0) > 10 ? 'color:#d97706' : 'color:#15803d';
        const pF  = hiP ? 'color:#ef4444' : (a.payout_ratio || 0) > 60 ? 'color:#d97706' : 'color:#15803d';
        const adv = hiY ? '<span style="color:#ef4444;font-size:0.65rem;"> ⚠ yield</span>' : hiP ? '<span style="color:#d97706;font-size:0.65rem;"> ⚠ payout</span>' : '';
        return '<div class="flex items-center gap-2 py-1.5 border-b border-gray-100 dark:border-gray-800 last:border-0">'
          + '<span class="text-xs font-medium text-gray-800 dark:text-gray-200 w-14 shrink-0">' + escHtml(a.ticker) + '</span>'
          + '<span class="text-xs tabular-nums shrink-0" style="' + yF + '">Y: ' + y + '</span>'
          + '<span class="text-xs text-gray-300 dark:text-gray-700 shrink-0">·</span>'
          + '<span class="text-xs tabular-nums flex-1" style="' + pF + '">P: ' + p + adv + '</span>'
          + '</div>';
      }).join('')
    + '<p class="text-xs text-gray-400 dark:text-gray-600 mt-2 pt-2 border-t border-gray-100 dark:border-gray-800">Y = utbytteyield &nbsp;·&nbsp; P = payout ratio</p>';

  // ── Detaljpanel D5: Inntektsstabilitet ───────────────────────────────
  const d5Rader = beholdning.slice().sort(function(a, b) { return (a.ar_med_utbytte || 0) - (b.ar_med_utbytte || 0); });
  const detaljD5 = '<p class="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-2">År med utbytte per aksje</p>'
    + d5Rader.map(function(a) {
        const ar   = a.ar_med_utbytte || 0;
        const af   = ar >= 15 ? 'color:#15803d' : ar >= 5 ? 'color:#d97706' : 'color:#ef4444';
        const ikon = ar >= 15 ? '✓' : ar >= 5 ? '→' : '⚠';
        return '<div class="flex items-center gap-2 py-1.5 border-b border-gray-100 dark:border-gray-800 last:border-0">'
          + '<span class="text-xs shrink-0" style="width:1rem;' + af + '">' + ikon + '</span>'
          + '<span class="text-xs font-medium text-gray-800 dark:text-gray-200 w-14 shrink-0">' + escHtml(a.ticker) + '</span>'
          + '<span class="text-xs text-gray-500 dark:text-gray-400 flex-1 truncate">' + escHtml(a.navn || '') + '</span>'
          + '<span class="text-xs tabular-nums font-medium shrink-0" style="' + af + '">' + (ar > 0 ? ar + ' år' : '—') + '</span>'
          + '</div>';
      }).join('');

  const tipsHtml = tips.length > 0
    ? `<div class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 shadow-sm" style="border-left:3px solid #d97706;">
        <p class="text-xs font-semibold uppercase tracking-widest text-gray-500 dark:text-gray-400 mb-2.5">Forbedringspunkter</p>
        <ul class="space-y-2">${tips.map(t =>
          `<li class="flex gap-2 text-xs text-gray-600 dark:text-gray-400 leading-relaxed"><span class="text-yellow-500 dark:text-yellow-400 shrink-0 mt-0.5">→</span><span>${t}</span></li>`
        ).join('')}</ul>
      </div>`
    : '';

  el.innerHTML = `
    <div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-5 shadow-sm">
      <div class="flex items-center gap-6">
        <div style="position:relative;width:88px;height:88px;flex-shrink:0;">
          <div style="width:88px;height:88px;border-radius:50%;background:conic-gradient(${ringFarge} 0deg ${conicDeg}deg, ${trackFarge} ${conicDeg}deg 360deg);"></div>
          <div style="position:absolute;inset:10px;border-radius:50%;background:${innerBg};display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <span class="text-2xl font-bold text-gray-900 dark:text-gray-100">${total}</span>
            <span class="text-xs text-gray-400 dark:text-gray-600">/100</span>
          </div>
        </div>
        <div class="flex-1 min-w-0" style="padding-left:4px;">
          <p class="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-0.5">Porteføljehelse</p>
          <p class="text-xl font-bold text-gray-900 dark:text-gray-100">${helseLabel}</p>
          <p class="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-relaxed">${beholdning.length} aksjer · ${antallSektorer} sektorer</p>
        </div>
      </div>
    </div>
    ${tipsHtml}
    <p class="text-xs font-semibold uppercase tracking-widest text-gray-400 dark:text-gray-500 px-1 pt-1">Dimensjoner</p>
    ${dimKort(1, '1. Diversifisering', d1, 20, d1Tekst, detaljD1)}
    ${dimKort(2, '2. Konsentrasjonsrisiko', d2, 20, d2Tekst, detaljD2)}
    ${dimKort(3, '3. Risikoprofil', d3, 20, d3Tekst, detaljD3)}
    ${dimKort(4, '4. Yield-bærekraft', d4, 20, d4Tekst, detaljD4)}
    ${dimKort(5, '5. Inntektsstabilitet', d5, 20, d5Tekst, detaljD5)}
  `;

  if (!el._analyseKlikkBound) {
    el._analyseKlikkBound = true;
    el.addEventListener('click', function(e) {
      const header = e.target.closest('[data-analyse-dim]');
      if (!header) return;
      const id = header.dataset.analyseDim;
      const panel = el.querySelector('[data-analyse-panel="' + id + '"]');
      const chevron = el.querySelector('[data-analyse-chevron="' + id + '"]');
      if (!panel) return;
      const apner = panel.classList.contains('hidden');
      panel.classList.toggle('hidden', !apner);
      if (chevron) chevron.style.transform = apner ? 'rotate(180deg)' : '';
    });
  }
}

// Node.js test export
if (typeof module !== 'undefined') module.exports = { beregnKostbasis, beregnIRR, beregnTWRSerie };
