'use strict';

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



function visTransaksjoner() {
  const tx    = hentTransaksjoner();
  const alle  = Object.entries(tx).flatMap(([ticker, liste]) =>
    liste.map(t => ({ ...t, ticker }))
  ).sort((a, b) => b.dato.localeCompare(a.dato));

  const harData = alle.length > 0;
  document.getElementById('tx-tom').classList.toggle('hidden', harData);
  document.getElementById('tx-logg-wrapper').classList.toggle('hidden', !harData);
  document.getElementById('tx-kostbasis-wrapper').classList.toggle('hidden', !harData);

  if (!harData) return;

  const fmtKr = v => v.toLocaleString('nb-NO', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) + ' kr';
  const fmtKurs = v => v.toLocaleString('nb-NO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' kr';

  // Kostbasis-tabell
  const tickers = [...new Set(alle.map(t => t.ticker))];
  let totalKost = 0, totalMarked = 0;

  document.getElementById('tx-kostbasis-body').innerHTML = tickers.map(ticker => {
    const aksje = alleAksjer.find(a => a.ticker === ticker);
    const kb    = beregnKostbasis(ticker);
    if (kb.antall <= 0) return '';
    const marked   = kb.antall * (aksje?.pris || 0);
    const gevinst  = marked - kb.totalKost;
    const gevPct   = kb.totalKost > 0 ? (gevinst / kb.totalKost * 100) : 0;
    const farge    = gevinst >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500';
    totalKost   += kb.totalKost;
    totalMarked += marked;
    return `<tr class="table-row cursor-pointer" data-ticker="${ticker}">
      <td class="px-4 py-3 font-mono font-bold text-brand-700 dark:text-brand-400">${ticker}</td>
      <td class="px-4 py-3 text-right">${kb.antall}</td>
      <td class="px-4 py-3 text-right">${fmtKurs(kb.vwap)}</td>
      <td class="px-4 py-3 text-right">${fmtKr(kb.totalKost)}</td>
      <td class="px-4 py-3 text-right">${aksje ? fmtKr(marked) : '—'}</td>
      <td class="px-4 py-3 text-right ${farge} font-semibold">${aksje ? (gevinst >= 0 ? '+' : '') + fmtKr(gevinst) : '—'}</td>
      <td class="px-4 py-3 text-right ${farge}">${aksje ? (gevPct >= 0 ? '+' : '') + gevPct.toFixed(1) + '%' : '—'}</td>
    </tr>`;
  }).join('');

  // Summer mottatt utbytte per ticker
  let totalMottattUtbytte = 0;
  tickers.forEach(ticker => {
    const kb = beregnKostbasis(ticker);
    totalMottattUtbytte += kb.mottattUtbytte;
  });

  const totalGevinst      = totalMarked - totalKost;
  const totalAvkastning   = totalGevinst + totalMottattUtbytte;
  const totalPct          = totalKost > 0 ? (totalAvkastning / totalKost * 100) : 0;
  const totalFarge        = totalGevinst >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500';
  const avkFarge          = totalAvkastning >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500';
  const utbytteTd         = totalMottattUtbytte > 0
    ? `<span class="text-yellow-600 dark:text-yellow-400">+${fmtKr(totalMottattUtbytte)} utbytte</span>`
    : '';
  document.getElementById('tx-kostbasis-footer').innerHTML = `<tr>
    <td colspan="3" class="px-4 py-3 text-sm text-gray-500">Totalt</td>
    <td class="px-4 py-3 text-right">${fmtKr(totalKost)}</td>
    <td class="px-4 py-3 text-right">${fmtKr(totalMarked)}${utbytteTd ? `<br><span class="text-xs font-normal">${utbytteTd}</span>` : ''}</td>
    <td class="px-4 py-3 text-right ${totalFarge} font-semibold">${(totalGevinst >= 0 ? '+' : '') + fmtKr(totalGevinst)}</td>
    <td class="px-4 py-3 text-right ${avkFarge} font-semibold">${(totalPct >= 0 ? '+' : '') + totalPct.toFixed(1)}%${totalMottattUtbytte > 0 ? '<br><span class="text-xs font-normal">inkl. utbytte</span>' : ''}</td>
  </tr>`;

  // Transaksjonslogg
  document.getElementById('tx-logg-body').innerHTML = alle.map(t => {
    const verdi = t.antall * t.kurs;
    const isKjøp    = t.type === 'kjøp';
    const isUtbytte = t.type === 'utbytte';
    const vergeFarge = isKjøp ? 'text-green-600 dark:text-green-400'
                     : isUtbytte ? 'text-yellow-600 dark:text-yellow-400'
                     : 'text-red-500';
    const badgeKlasse = isKjøp    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                      : isUtbytte ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                      : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400';
    const typeLabel = isKjøp ? 'Kjøp' : isUtbytte ? 'Utbytte' : 'Salg';
    const kursLabel = isUtbytte ? `${fmtKurs(t.kurs)}/aksje` : fmtKurs(t.kurs);
    const [y, m, d] = t.dato.split('-');
    return `<tr>
      <td class="px-4 py-3 text-gray-500">${d}.${m}.${y}</td>
      <td class="px-4 py-3 font-mono font-bold text-brand-700 dark:text-brand-400">${t.ticker}</td>
      <td class="px-4 py-3 text-center"><span class="text-xs font-semibold px-2 py-0.5 rounded-full ${badgeKlasse}">${typeLabel}</span></td>
      <td class="px-4 py-3 text-right">${t.antall}</td>
      <td class="px-4 py-3 text-right">${kursLabel}</td>
      <td class="px-4 py-3 text-right ${vergeFarge} font-semibold">${isKjøp ? '-' : '+'}${fmtKr(verdi)}</td>
      <td class="px-4 py-3 text-center">
        <button class="tx-slett-rad text-gray-400 hover:text-red-500 transition-colors p-1" data-ticker="${t.ticker}" data-id="${t.id}">
          <svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
      </td>
    </tr>`;
  }).join('');

  // Klikk på kostbasis-rad → åpne modal
  document.getElementById('tx-kostbasis-body').onclick = e => {
    const rad = e.target.closest('[data-ticker]');
    if (rad) { const a = alleAksjer.find(x => x.ticker === rad.dataset.ticker); if (a) visModal(a); }
  };

  // Slett enkelt transaksjon
  document.getElementById('tx-logg-body').onclick = e => {
    const btn = e.target.closest('.tx-slett-rad');
    if (!btn) return;
    const { ticker, id } = btn.dataset;
    const txData = hentTransaksjoner();
    if (txData[ticker]) {
      txData[ticker] = txData[ticker].filter(t => t.id !== id);
      if (txData[ticker].length === 0) delete txData[ticker];
    }
    lagreTransaksjoner(txData);
    visTransaksjoner();
    visPortefolje();
  };
}


function initTransaksjoner() {
  // Fyll dropdown med aksjer fra portefølje (og alle)
  const sel = document.getElementById('tx-velg-aksje');
  const fyllTxDropdown = () => {
    const pf = hentPF();
    const valgt = sel.value;
    sel.innerHTML = '<option value="">Velg aksje…</option>';
    const prio = alleAksjer.filter(a => pf[a.ticker]).sort((a, b) => a.ticker.localeCompare(b.ticker));
    const rest = alleAksjer.filter(a => !pf[a.ticker]).sort((a, b) => a.ticker.localeCompare(b.ticker));
    if (prio.length) {
      const grp = document.createElement('optgroup'); grp.label = 'I portefølje';
      prio.forEach(a => { const o = document.createElement('option'); o.value = a.ticker; o.textContent = `${a.ticker} – ${a.navn}`; grp.appendChild(o); });
      sel.appendChild(grp);
    }
    const grp2 = document.createElement('optgroup'); grp2.label = 'Alle aksjer';
    rest.forEach(a => { const o = document.createElement('option'); o.value = a.ticker; o.textContent = `${a.ticker} – ${a.navn}`; grp2.appendChild(o); });
    sel.appendChild(grp2);
    if (valgt) sel.value = valgt;
  };
  fyllTxDropdown();

  // Sett dagens dato som default
  document.getElementById('tx-dato').value = new Date().toISOString().slice(0, 10);

  // Oppdater kurs-hint basert på type
  const typeEl = document.getElementById('tx-type');
  const kursInput = document.getElementById('tx-kurs');
  const kursHint  = document.getElementById('tx-kurs-hint');
  function oppdaterKursHint() {
    if (typeEl.value === 'utbytte') {
      kursInput.placeholder = 'Kr/aksje';
      if (kursHint) kursHint.textContent = 'utbytte per aksje';
    } else {
      kursInput.placeholder = 'Kurs (kr)';
      if (kursHint) kursHint.textContent = 'kurs per aksje';
    }
  }
  typeEl.addEventListener('change', oppdaterKursHint);

  document.getElementById('tx-legg-til').addEventListener('click', () => {
    const ticker = document.getElementById('tx-velg-aksje').value;
    const type   = document.getElementById('tx-type').value;
    const dato   = document.getElementById('tx-dato').value;
    const antall = parseInt(document.getElementById('tx-antall').value, 10);
    const kurs   = parseFloat(document.getElementById('tx-kurs').value);
    const feilEl = document.getElementById('tx-feil');

    feilEl.classList.add('hidden');
    if (!ticker) { feilEl.textContent = 'Velg en aksje.'; feilEl.classList.remove('hidden'); return; }
    if (!dato)   { feilEl.textContent = 'Velg en dato.'; feilEl.classList.remove('hidden'); return; }
    if (!antall || antall < 1) { feilEl.textContent = 'Skriv inn gyldig antall.'; feilEl.classList.remove('hidden'); return; }
    if (!kurs   || kurs <= 0)  { feilEl.textContent = 'Skriv inn gyldig kurs.'; feilEl.classList.remove('hidden'); return; }

    const txData = hentTransaksjoner();
    if (!txData[ticker]) txData[ticker] = [];
    txData[ticker].push({ id: Date.now().toString(), dato, antall, kurs, type });
    txData[ticker].sort((a, b) => a.dato.localeCompare(b.dato));
    lagreTransaksjoner(txData);

    // Oppdater beholdning automatisk ved kjøp hvis ticker ikke er der fra før
    const pf = hentPF();
    if (type === 'kjøp') {
      pf[ticker] = (pf[ticker] || 0) + antall;
    } else if (type === 'salg' && pf[ticker]) {
      pf[ticker] = Math.max(0, (pf[ticker] || 0) - antall);
      if (pf[ticker] === 0) delete pf[ticker];
    }
    lagrePF(pf);

    document.getElementById('tx-antall').value = '';
    document.getElementById('tx-kurs').value   = '';
    fyllTxDropdown();
    visTransaksjoner();
    visPortefolje();
  });

  document.getElementById('tx-slett-alle').addEventListener('click', () => {
    if (!confirm('Slett alle transaksjoner?')) return;
    lagreTransaksjoner({});
    visTransaksjoner();
    visPortefolje();
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
    document.getElementById('pf-sub-transaksjoner').classList.toggle('hidden', tab !== 'transaksjoner');
    document.getElementById('pf-sub-watchlister').classList.toggle('hidden', tab !== 'watchlister');
    if (tab === 'statistikk') visPortefolje();
    if (tab === 'transaksjoner') visTransaksjoner();
    if (tab === 'watchlister') visWatchlister();
  }

  document.getElementById('tab-portfolio').addEventListener('click', e => {
    const btn = e.target.closest('.pf-sub-btn');
    if (btn) byttSubTab(btn.dataset.pfTab);
  });
}


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

  // ── INNTEKTSTELLER-MÅL — åpne innstillinger ved klikk ──────────────────────
  function apneInnstillingerProfil() {
    const modal = document.getElementById('innstillinger-modal');
    if (modal) {
      modal.querySelector('[data-innst-tab="profil"]').click();
      modal.classList.remove('hidden');
      modal.classList.add('flex');
    }
  }

  const settBtn = document.getElementById('pf-inntekt-mal-sett');
  if (settBtn) settBtn.addEventListener('click', apneInnstillingerProfil);

  // Sparemål-sett knapp (i ekstra stats)
  const spareSettBtnInit = document.getElementById('pf-stat-sparemaal-sett');
  if (spareSettBtnInit) spareSettBtnInit.addEventListener('click', apneInnstillingerProfil);
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


function visHistorikkKurve() {
  const wrapper = document.getElementById('pf-historikk-wrapper');
  if (!wrapper) return;

  let historikk = {};
  try { historikk = JSON.parse(localStorage.getItem('pf_historikk') || '{}'); } catch(e) {}

  const datoer = Object.keys(historikk).sort();
  if (datoer.length < 2) { wrapper.classList.add('hidden'); return; }
  wrapper.classList.remove('hidden');

  // Normalisér begge til 100 ved første felles dato
  const verdier = datoer.map(d => historikk[d]);
  const pf0 = verdier[0];
  const pfNorm = verdier.map(v => v / pf0 * 100);

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

  // Samlet min/max over alle normaliserte verdier
  const alleVerdier = [...pfNorm, ...(osebxPts ? osebxPts.map(p => p[1]) : [])];
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

  const pfPts  = pfNorm.map((v, i) => toSvg(i, v));
  const polyline = pfPts.map(p => p.join(',')).join(' ');
  const areaD = `M${pfPts[0][0]},${H} ` + pfPts.map(p => `L${p[0]},${p[1]}`).join(' ') + ` L${pfPts[pfPts.length-1][0]},${H} Z`;

  const endring = pfNorm[pfNorm.length - 1] - 100;
  const endringPct = endring.toFixed(1);
  const positiv = endring >= 0;
  const farge = positiv ? '#16a34a' : '#dc2626';
  const fargeLys = positiv ? '#dcfce7' : '#fee2e2';

  // OSEBX SVG-linje
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

  // Legg til OSEBX-legend hvis tilgjengelig
  const legendEl = document.getElementById('pf-historikk-legend');
  if (legendEl) {
    legendEl.innerHTML = osebxPts
      ? `<span class="flex items-center gap-1"><span class="inline-block w-5 border-t-2 border-dashed border-gray-400"></span> OSEBX</span>`
      : '';
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
  document.getElementById('pf-charts-wrapper').style.display = harBeholdning ? 'grid' : 'none';
  document.getElementById('pf-inntekt-wrapper').classList.toggle('hidden', !harBeholdning);
  document.getElementById('pf-statistikk-tom').classList.toggle('hidden', harBeholdning);
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

    // ── OSEBX-SAMMENLIGNING ───────────────────────────────────────────────────
    const osebxEl     = document.getElementById('pf-stat-osebx');
    const osebxTekst  = document.getElementById('pf-stat-osebx-tekst');
    let historikk = {};
    try { historikk = JSON.parse(localStorage.getItem('pf_historikk') || '{}'); } catch(e) {}
    const pfDatoer = Object.keys(historikk).sort();
    const fellesDatoer = pfDatoer.filter(d => osebxHistorikk[d] != null);
    if (osebxEl && fellesDatoer.length >= 2) {
      const d0 = fellesDatoer[0], dN = fellesDatoer[fellesDatoer.length - 1];
      const pfEndring    = (historikk[dN] - historikk[d0]) / historikk[d0] * 100;
      const osebxEndring = (osebxHistorikk[dN] - osebxHistorikk[d0]) / osebxHistorikk[d0] * 100;
      const diff = pfEndring - osebxEndring;
      const slaer = diff >= 0;
      osebxEl.textContent = slaer ? '✓ Ja' : '✗ Nei';
      osebxEl.className   = 'stat-value text-base ' + (slaer ? 'text-green-600 dark:text-green-400' : 'text-red-500');
      osebxTekst.textContent = (diff >= 0 ? '+' : '') + diff.toFixed(1) + '% vs indeks';
    } else if (osebxEl) {
      osebxEl.textContent  = '—';
      osebxEl.className    = 'stat-value text-base';
      osebxTekst.textContent = 'trenger mer historikk';
    }

    // ── FAKTISK AVKASTNING ────────────────────────────────────────────────────
    const faktiskEl   = document.getElementById('pf-stat-faktisk');
    const faktiskTekst = document.getElementById('pf-stat-faktisk-tekst');
    if (faktiskEl) {
      let invKost = 0, invMottatt = 0, invMarkert = 0, harTx = false;
      alleBeholdning.forEach(a => {
        const kb = beregnKostbasis(a.ticker);
        if (kb.totalKost > 0 || kb.mottattUtbytte > 0) {
          invKost    += kb.totalKost;
          invMottatt += kb.mottattUtbytte;
          invMarkert += kb.antall * (a.pris || 0);
          harTx = true;
        }
      });
      if (harTx && invKost > 0) {
        const totalReturn = invMarkert + invMottatt - invKost;
        const pct = totalReturn / invKost * 100;
        faktiskEl.textContent = (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%';
        faktiskEl.className   = 'stat-value text-base ' + (pct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500');
        if (faktiskTekst) faktiskTekst.textContent = (totalReturn >= 0 ? '+' : '') + fmtKr(totalReturn);
      } else {
        faktiskEl.textContent = '—';
        faktiskEl.className   = 'stat-value text-base';
        if (faktiskTekst) faktiskTekst.textContent = 'trenger transaksjoner';
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

  // ── BEHOLDNINGSTABELL ─────────────────────────────────────────────────────
  const tbody = document.getElementById('pf-tabell-body');
  tbody.innerHTML = beholdning.map(a => {
    const kb = beregnKostbasis(a.ticker);
    const harKb = kb.antall > 0 && kb.totalKost > 0;
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
    return `
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
      <td class="px-4 py-3 text-right hidden lg:table-cell text-sm">${kostTd}</td>
      <td class="px-4 py-3 text-right hidden lg:table-cell text-sm">${gevTd}</td>
      <td class="px-4 py-3 text-center hidden sm:table-cell text-gray-500 text-sm">${a.ex_dato ? formaterDato(a.ex_dato) : '—'}</td>
      <td class="px-4 py-3 text-center hidden sm:table-cell"><span class="frekvens-badge">${a.frekvens}</span></td>
      <td class="px-4 py-3 text-center">
        <button class="pf-slett text-gray-400 hover:text-red-500 transition-colors p-1" data-ticker="${a.ticker}" title="Fjern">
          <svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
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

  document.getElementById('pf-portefolje-ny').addEventListener('click', () => {
    const navn = prompt('Navn på ny portefølje:');
    if (!navn || !navn.trim()) return;
    const id  = 'pf_' + Date.now();
    const pfl = hentPortefoljer();
    pfl[id]   = { id, navn: navn.trim(), beholdning: {}, transaksjoner: {} };
    lagrePortefoljer(pfl);
    settAktivPFId(id);
    oppdaterPortefoljeVelger();
    visPortefolje();
    oppdaterSammendrag();
  });

  document.getElementById('pf-portefolje-gi-navn').addEventListener('click', () => {
    const pfl = hentPortefoljer();
    const id  = hentAktivPFId();
    const navn = prompt('Nytt navn:', pfl[id]?.navn || '');
    if (!navn || !navn.trim()) return;
    pfl[id].navn = navn.trim();
    lagrePortefoljer(pfl);
    oppdaterPortefoljeVelger();
  });

  document.getElementById('pf-portefolje-slett').addEventListener('click', () => {
    const pfl = hentPortefoljer();
    if (Object.keys(pfl).length <= 1) return;
    const id  = hentAktivPFId();
    const navn = pfl[id]?.navn || id;
    if (!confirm(`Slett porteføljen "${navn}"? Dette kan ikke angres.`)) return;
    delete pfl[id];
    lagrePortefoljer(pfl);
    settAktivPFId(Object.keys(pfl)[0]);
    oppdaterPortefoljeVelger();
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
                <button class="wl-legg-til-pf text-gray-400 hover:text-brand-600 dark:hover:text-brand-400 transition-colors p-1" title="Legg til i portefølje"
                        data-ticker="${ticker}">
                  <svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                </button>
              </td>
              <td class="px-4 py-3 text-center">
                <button class="wl-fjern-ticker text-gray-400 hover:text-red-500 transition-colors p-1"
                        data-liste-id="${aktivListe.id}" data-ticker="${ticker}">
                  <svg class="w-4 h-4 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
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
      // Bytt til Transaksjoner-fanen og forhåndsvelg aksjen
      document.querySelector('[data-pf-tab="transaksjoner"]').click();
      const sel = document.getElementById('tx-velg-aksje');
      if (sel) { sel.value = ticker; sel.dispatchEvent(new Event('change')); }
      document.getElementById('tx-antall')?.focus();
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


// Node.js test export
if (typeof module !== 'undefined') module.exports = { beregnKostbasis };
