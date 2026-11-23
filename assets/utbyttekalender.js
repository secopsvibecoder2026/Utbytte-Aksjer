'use strict';
/* Utbyttekalenderen (/utbyttekalender/), 16.11.2026.

   Tabellen ligger ferdig i HTML-en, skrevet av oppdater_utbyttekalender() i
   fetch_stocks.py. Dette skriptet legger søk, sortering, filtre, favoritter,
   .ics, CSV og månedsvisning oppå radene som finnes. Det henter ingen data og
   bygger aldri tabellen: rader skjules, vises og flyttes, aldri tegnes på nytt.
   Uten skriptet viser siden hele tabellen. */

// ── Rene hjelpere (testes i tests/utbyttekalender.test.js) ──────────────────

const KAL_MND = ['januar', 'februar', 'mars', 'april', 'mai', 'juni', 'juli',
  'august', 'september', 'oktober', 'november', 'desember'];
const KAL_FREKVENS_REKKE = { 'Månedlig': 1, 'Kvartalsvis': 2, 'Halvårlig': 3, 'Årlig': 4, 'Uregelmessig': 5 };
const KAL_STATUS_REKKE = { foreslatt: 1, vedtatt: 2, betalt: 3 };
const KAL_STATUS_TEKST = { foreslatt: 'Foreslått', vedtatt: 'Vedtatt', betalt: 'Betalt' };

/** Små bokstaver, uten aksenter: «Vår Ærø» → «var aero». */
function kalNormaliser(s) {
  return String(s || '').toLowerCase()
    .replace(/æ/g, 'ae').replace(/ø/g, 'o').replace(/å/g, 'a')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, ' ').trim();
}

/** Levenshtein-avstand, med tak: større enn `maks` gir maks + 1. */
function kalAvstand(a, b, maks) {
  if (Math.abs(a.length - b.length) > maks) return maks + 1;
  let forrige = Array.from({ length: b.length + 1 }, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const rad = [i];
    let minst = i;
    for (let j = 1; j <= b.length; j++) {
      rad[j] = Math.min(forrige[j] + 1, rad[j - 1] + 1, forrige[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      if (rad[j] < minst) minst = rad[j];
    }
    if (minst > maks) return maks + 1;
    forrige = rad;
  }
  return forrige[b.length];
}

/** Treffer søket selskapet? Hvert ord i søket må passe et ord i navn eller ticker.
    Et ord passer når det står i starten av ordet, eller avviker med én bokstav
    (fra fire bokstaver). «var energi» treffer Vår Energi, «equnor» Equinor. */
function kalTreffer(sok, navn, ticker) {
  const q = kalNormaliser(sok);
  if (!q) return true;
  const tekst = kalNormaliser(`${navn} ${ticker}`);
  if (tekst.includes(q)) return true;
  const ord = tekst.split(' ');
  return q.split(' ').every(t => ord.some(o => {
    if (o.startsWith(t)) return true;
    if (t.length < 4) return false;
    const maks = t.length >= 7 ? 2 : 1;
    return kalAvstand(t, o.slice(0, t.length), maks) <= maks || kalAvstand(t, o, maks) <= maks;
  }));
}

function kalIso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function kalLeggTil(d, dager) {
  const n = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  n.setDate(n.getDate() + dager);
  return n;
}

/** [fra, til] som ISO-datoer for en periode, eller null for hele året. */
function kalPeriode(periode, idag, mnd) {
  const ukedag = (idag.getDay() + 6) % 7;           // mandag = 0
  const mandag = kalLeggTil(idag, -ukedag);
  switch (periode) {
    case 'uke': return [kalIso(mandag), kalIso(kalLeggTil(mandag, 6))];
    case 'nesteuke': return [kalIso(kalLeggTil(mandag, 7)), kalIso(kalLeggTil(mandag, 13))];
    case '30d': return [kalIso(idag), kalIso(kalLeggTil(idag, 30))];
    case 'maaned': {
      const f = new Date(idag.getFullYear(), idag.getMonth(), 1);
      return [kalIso(f), kalIso(new Date(idag.getFullYear(), idag.getMonth() + 1, 0))];
    }
    case 'velg': {
      if (!/^\d{4}-\d{2}$/.test(mnd || '')) return null;
      const [a, m] = mnd.split('-').map(Number);
      return [kalIso(new Date(a, m - 1, 1)), kalIso(new Date(a, m, 0))];
    }
    default: return null;
  }
}

/** Passer raden filtrene? `r` er en enkel post med feltene fra data-attributtene. */
function kalPasser(r, f, idagIso, favoritter) {
  if (f.tid === 'kommende' && r.ex < idagIso) return false;
  if (f.tid === 'passerte' && r.ex >= idagIso) return false;
  if (f.intervall && (r.ex < f.intervall[0] || r.ex > f.intervall[1])) return false;
  if (f.sektorer && f.sektorer.length && !f.sektorer.includes(r.sektor)) return false;
  if (f.minYield && !(r.yield >= f.minYield)) return false;
  if (f.frekvens && r.frekvens !== f.frekvens) return false;
  if (f.status && r.status !== f.status) return false;
  if (f.mine && !(favoritter && favoritter.has(r.ticker))) return false;
  if (f.sok && !kalTreffer(f.sok, r.navn, r.ticker)) return false;
  return true;
}

/** Sammenligner to rader. Standard (ex stigende) er sidens egen rekkefølge:
    kommende først, tidligste først, så passerte, nyeste først. */
function kalSammenlign(a, b, kol, retning, idagIso) {
  const tegn = retning === 'desc' ? -1 : 1;
  const tom = (x) => x === '' || x === null || x === undefined || Number.isNaN(x);
  let x, y;
  switch (kol) {
    case 'ex':
      if (retning !== 'desc') {
        const ka = a.ex >= idagIso, kb = b.ex >= idagIso;
        if (ka !== kb) return ka ? -1 : 1;
        if (a.ex !== b.ex) return ka ? (a.ex < b.ex ? -1 : 1) : (a.ex < b.ex ? 1 : -1);
        return 0;
      }
      x = a.ex; y = b.ex; break;
    case 'selskap': return tegn * a.navn.localeCompare(b.navn, 'nb');
    case 'ticker': return tegn * a.ticker.localeCompare(b.ticker, 'nb');
    case 'sektor': return tegn * a.sektor.localeCompare(b.sektor, 'nb');
    case 'utbytte': x = a.belop; y = b.belop; break;
    case 'yield': x = a.yield; y = b.yield; break;
    case 'kjop': x = a.kjop; y = b.kjop; break;
    case 'betaling': x = a.betaling; y = b.betaling; break;
    case 'frekvens': x = KAL_FREKVENS_REKKE[a.frekvens] || 9; y = KAL_FREKVENS_REKKE[b.frekvens] || 9; break;
    case 'status': x = KAL_STATUS_REKKE[a.status] || 9; y = KAL_STATUS_REKKE[b.status] || 9; break;
    default: return 0;
  }
  // Tomme verdier (ukjent beløp, ingen betalingsdato) står alltid sist.
  if (tom(x) && tom(y)) return 0;
  if (tom(x)) return 1;
  if (tom(y)) return -1;
  return x < y ? -tegn : x > y ? tegn : 0;
}

function kalEsc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function kalIcsTekst(s) {
  return String(s).replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\n/g, '\\n');
}

function kalTall(n, desimaler) {
  return Number(n).toLocaleString('nb-NO', { minimumFractionDigits: desimaler, maximumFractionDigits: 4 });
}

function kalBelopTekst(r) {
  return r.belop ? `${kalTall(r.belop, 2)} ${r.valuta}`.trim() : '';
}

/** Bretter en linje til høyst 75 byte, som RFC 5545 krever. */
function kalIcsBrett(linje) {
  const deler = [];
  let del = '', lengde = 0;
  for (const tegn of linje) {
    const n = new TextEncoder().encode(tegn).length;
    if (lengde + n > (deler.length ? 74 : 75)) { deler.push(del); del = ''; lengde = 0; }
    del += tegn; lengde += n;
  }
  deler.push(del);
  return deler.join('\r\n ');
}

/** Én heldagshendelse per ex-dato, med påminnelse kl. 09 dagen før siste kjøpsdag. */
function kalIcs(rader, stempel) {
  const linjer = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//exday.no//Utbyttekalender//NO',
    'CALSCALE:GREGORIAN', 'METHOD:PUBLISH', 'X-WR-CALNAME:Utbyttekalender exday.no'];
  for (const r of rader) {
    const ex = r.ex.replace(/-/g, '');
    const neste = kalIso(kalLeggTil(new Date(r.ex + 'T00:00:00'), 1)).replace(/-/g, '');
    const dagerFor = Math.round((new Date(r.ex + 'T00:00:00') - new Date(r.kjop + 'T00:00:00')) / 864e5) + 1;
    const belop = kalBelopTekst(r);
    const beskr = [`Siste dag å kjøpe med rett på utbyttet: ${r.kjop.split('-').reverse().join('.')}.`,
      belop ? `Utbytte: ${belop} per aksje.` : '',
      r.status === 'foreslatt' ? 'Utbyttet er foreslått, ikke vedtatt.' : '',
      r.betaling ? `Betaling: ${r.betaling.split('-').reverse().join('.')}.` : '',
      `https://exday.no/aksjer/${r.ticker}/`].filter(Boolean).join('\n');
    linjer.push('BEGIN:VEVENT', `UID:${r.ticker}-${ex}@exday.no`, `DTSTAMP:${stempel}`,
      `DTSTART;VALUE=DATE:${ex}`, `DTEND;VALUE=DATE:${neste}`,
      `SUMMARY:${kalIcsTekst(`Ex-dato ${r.navn} (${r.ticker})${belop ? ` ${belop}` : ''}`)}`,
      `DESCRIPTION:${kalIcsTekst(beskr)}`, `URL:https://exday.no/aksjer/${r.ticker}/`,
      'BEGIN:VALARM', 'ACTION:DISPLAY', `DESCRIPTION:${kalIcsTekst(`Kjøp ${r.ticker} senest i morgen for å få utbyttet`)}`,
      `TRIGGER:-PT${dagerFor * 24 - 9}H`, 'END:VALARM', 'END:VEVENT');
  }
  linjer.push('END:VCALENDAR');
  return linjer.map(kalIcsBrett).join('\r\n') + '\r\n';
}

/** CSV med semikolon og desimalkomma, som eksporten i appen. */
function kalCsv(rader) {
  const felt = (s) => {
    const t = String(s ?? '');
    return /[";\n]/.test(t) ? `"${t.replace(/"/g, '""')}"` : t;
  };
  const hode = ['Selskap', 'Ticker', 'Sektor', 'Utbytte per aksje', 'Valuta', 'Yield (%)', 'Ex-dato',
    'Kjøp senest', 'Betaling', 'Frekvens', 'Status'];
  const linjer = [hode.join(';')];
  for (const r of rader) {
    linjer.push([r.navn, r.ticker, r.sektor, r.belop ? String(r.belop).replace('.', ',') : '', r.valuta,
      r.yield ? String(r.yield).replace('.', ',') : '', r.ex, r.kjop, r.betaling, r.frekvens,
      KAL_STATUS_TEKST[r.status] || r.status].map(felt).join(';'));
  }
  return '\ufeff' + linjer.join('\r\n') + '\r\n';
}

/** Filtertilstanden ⇄ URL-parametere, så en visning kan deles. */
function kalFraUrl(sok) {
  const p = new URLSearchParams(sok || '');
  const [kol, retning] = (p.get('sort') || 'ex:asc').split(':');
  return {
    sok: p.get('q') || '',
    periode: p.get('periode') || 'aar',
    mnd: p.get('mnd') || '',
    tid: p.get('tid') || 'kommende',
    sektorer: (p.get('sektor') || '').split(',').filter(Boolean),
    minYield: Number(p.get('yield')) || 0,
    frekvens: p.get('frekvens') || '',
    status: p.get('status') || '',
    mine: p.get('mine') === '1',
    kol: kol || 'ex', retning: retning === 'desc' ? 'desc' : 'asc',
    visning: p.get('visning') === 'maaned' ? 'maaned' : 'liste',
  };
}

function kalTilUrl(t) {
  const p = new URLSearchParams();
  if (t.sok) p.set('q', t.sok);
  if (t.periode && t.periode !== 'aar') p.set('periode', t.periode);
  if (t.periode === 'velg' && t.mnd) p.set('mnd', t.mnd);
  if (t.tid && t.tid !== 'kommende') p.set('tid', t.tid);
  if (t.sektorer && t.sektorer.length) p.set('sektor', t.sektorer.join(','));
  if (t.minYield) p.set('yield', String(t.minYield));
  if (t.frekvens) p.set('frekvens', t.frekvens);
  if (t.status) p.set('status', t.status);
  if (t.mine) p.set('mine', '1');
  if (!(t.kol === 'ex' && t.retning === 'asc')) p.set('sort', `${t.kol}:${t.retning}`);
  if (t.visning === 'maaned') p.set('visning', 'maaned');
  const s = p.toString();
  return s ? `?${s}` : '';
}

// ── Siden ────────────────────────────────────────────────────────────────────

function kalStart() {
  const tabell = document.getElementById('kal-tabell');
  const tbody = document.getElementById('kal-rader');
  const kontroller = document.getElementById('kal-kontroller');
  if (!tabell || !tbody || !kontroller) return;

  const idag = new Date();
  const idagIso = kalIso(idag);
  const rader = [...tbody.rows].map((tr, nr) => ({
    tr, nr, ticker: tr.dataset.ticker, navn: tr.dataset.navn || tr.dataset.ticker,
    sektor: tr.dataset.sektor || '', frekvens: tr.dataset.frekvens || '', ex: tr.dataset.ex,
    kjop: tr.dataset.kjop, betaling: tr.dataset.betaling || '', belop: tr.dataset.belop ? Number(tr.dataset.belop) : null,
    valuta: tr.dataset.valuta || '', yield: Number(tr.dataset.yield) || 0, status: tr.dataset.status,
  }));
  // Status følger dagens dato i nettleseren, ikke datoen siden ble bygget.
  for (const r of rader) {
    if (r.status === 'vedtatt' && r.betaling && r.betaling <= idagIso) {
      r.status = 'betalt';
      r.tr.dataset.status = 'betalt';
      const celle = r.tr.cells[9];
      if (celle) { celle.textContent = 'Betalt'; celle.className = 'kal-status kal-status-betalt'; }
    }
  }

  let favoritter;
  try { favoritter = new Set(JSON.parse(localStorage.getItem('fav_aksjer') || '[]')); }
  catch (e) { favoritter = new Set(); }
  const lagreFav = () => {
    try { localStorage.setItem('fav_aksjer', JSON.stringify([...favoritter])); } catch (e) { /* privat modus */ }
  };

  let tilstand = kalFraUrl(location.search);
  const sektorer = [...new Set(rader.map(r => r.sektor).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'nb'));
  const maaneder = [...new Set(rader.map(r => r.ex.slice(0, 7)))].sort();

  // Kontrollene finnes bare med JavaScript; uten det er tabellen alt som trengs.
  const opt = (v, t, valgt) => `<option value="${v}"${valgt ? ' selected' : ''}>${t}</option>`;
  const mndNavn = (ym) => { const [a, m] = ym.split('-').map(Number); return `${KAL_MND[m - 1]} ${a}`; };
  kontroller.innerHTML = `
    <div class="kal-sokrad">
      <label for="kal-sok" class="sr-only">Søk etter selskap eller ticker</label>
      <input id="kal-sok" type="search" class="kal-felt kal-sokfelt" placeholder="Søk etter selskap eller ticker" autocomplete="off" value="">
      <div class="kal-visning" role="group" aria-label="Visning">
        <button type="button" data-visning="liste" class="kal-knapp">Liste</button>
        <button type="button" data-visning="maaned" class="kal-knapp">Måned</button>
      </div>
    </div>
    <details id="kal-filtre" class="kal-filtre">
      <summary class="kal-knapp">Filter <span id="kal-filterantall"></span></summary>
      <div class="kal-filtergrid">
        <label>Periode
          <select id="kal-periode" class="kal-felt">
            ${opt('aar', 'Hele året')}${opt('uke', 'Denne uka')}${opt('nesteuke', 'Neste uke')}
            ${opt('30d', 'Neste 30 dager')}${opt('maaned', 'Denne måneden')}${opt('velg', 'Velg måned')}
          </select>
        </label>
        <label id="kal-mnd-etikett" hidden>Måned
          <select id="kal-mnd" class="kal-felt">${maaneder.map(m => opt(m, mndNavn(m))).join('')}</select>
        </label>
        <label>Vis
          <select id="kal-tid" class="kal-felt">${opt('kommende', 'Kommende')}${opt('passerte', 'Passerte')}${opt('alle', 'Alle')}</select>
        </label>
        <label>Minste yield
          <select id="kal-yield" class="kal-felt">${[0, 3, 5, 8].map(y => opt(y, y ? `${y} %` : 'Alle')).join('')}</select>
        </label>
        <label>Frekvens
          <select id="kal-frekvens" class="kal-felt">${opt('', 'Alle')}${['Årlig', 'Halvårlig', 'Kvartalsvis', 'Månedlig', 'Uregelmessig'].map(f => opt(f, f)).join('')}</select>
        </label>
        <label>Status
          <select id="kal-status" class="kal-felt">${opt('', 'Alle')}${opt('foreslatt', 'Foreslått')}${opt('vedtatt', 'Vedtatt')}${opt('betalt', 'Betalt')}</select>
        </label>
        <label>Sorter
          <select id="kal-sort" class="kal-felt">
            ${opt('ex:asc', 'Ex-dato, kommende først')}${opt('ex:desc', 'Ex-dato, nyeste først')}
            ${opt('selskap:asc', 'Selskap A–Å')}${opt('utbytte:desc', 'Høyest utbytte')}
            ${opt('yield:desc', 'Høyest yield')}${opt('betaling:asc', 'Betalingsdato')}
          </select>
        </label>
        <fieldset class="kal-sektorer"><legend>Sektor</legend>
          ${sektorer.map((s, i) => `<label class="kal-avkrysning"><input type="checkbox" value="${kalEsc(s)}" id="kal-sektor-${i}"> ${kalEsc(s)}</label>`).join('')}
        </fieldset>
        <label class="kal-avkrysning kal-mine"><input type="checkbox" id="kal-mine"> Bare mine aksjer <span class="kal-hint">(stjernemerket her eller i appen)</span></label>
      </div>
    </details>
    <div class="kal-statuslinje">
      <p id="kal-teller" aria-live="polite"></p>
      <div class="kal-handlinger">
        <button type="button" id="kal-nullstill" class="kal-knapp">Nullstill filtre</button>
        <button type="button" id="kal-ics-alle" class="kal-knapp">Legg visningen i kalenderen (.ics)</button>
        <button type="button" id="kal-csv" class="kal-knapp">Last ned CSV</button>
      </div>
    </div>`;
  kontroller.hidden = false;

  const ingen = document.createElement('p');
  ingen.id = 'kal-ingen';
  ingen.className = 'kal-ingen';
  ingen.hidden = true;
  ingen.innerHTML = 'Ingen treff. <button type="button" class="kal-lenkeknapp" id="kal-ingen-nullstill">Nullstill søk og filtre</button>';
  tabell.parentNode.after(ingen);

  const maanedBoks = document.createElement('div');
  maanedBoks.id = 'kal-maaned';
  maanedBoks.className = 'kal-maaned';
  maanedBoks.hidden = true;
  ingen.after(maanedBoks);

  // Stjerne og kalenderknapp i selskapscellen på hver rad.
  for (const r of rader) {
    const celle = r.tr.cells[0];
    const knapper = document.createElement('span');
    knapper.className = 'kal-radknapper';
    knapper.innerHTML =
      `<button type="button" class="kal-ikon kal-stjerne" data-handling="fav" aria-pressed="false" aria-label="Legg ${kalEsc(r.navn)} til i mine aksjer">` +
      '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg></button>' +
      `<button type="button" class="kal-ikon" data-handling="ics" aria-label="Legg ex-datoen for ${kalEsc(r.navn)} i kalenderen (.ics)" title="Legg i kalenderen (.ics)">` +
      '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="5" width="17" height="15" rx="2"/><path d="M8 3v4M16 3v4M3.5 10h17M12 13v4M10 15h4"/></svg></button>';
    celle.prepend(knapper);
  }
  const visStjerner = () => {
    for (const r of rader) {
      const b = r.tr.querySelector('.kal-stjerne');
      const på = favoritter.has(r.ticker);
      b.setAttribute('aria-pressed', String(på));
      b.classList.toggle('kal-stjerne-paa', på);
    }
  };

  // Overskriftene blir knapper, så sorteringen kan brukes med tastatur.
  const kolonner = [...tabell.tHead.rows[0].cells];
  for (const th of kolonner) {
    const knapp = document.createElement('button');
    knapp.type = 'button';
    knapp.className = 'kal-sortknapp';
    knapp.innerHTML = `${th.textContent}<span class="kal-pil" aria-hidden="true"></span>`;
    th.textContent = '';
    th.appendChild(knapp);
    knapp.addEventListener('click', () => {
      const kol = th.dataset.kol;
      if (tilstand.kol === kol) tilstand.retning = tilstand.retning === 'asc' ? 'desc' : 'asc';
      else { tilstand.kol = kol; tilstand.retning = ['utbytte', 'yield'].includes(kol) ? 'desc' : 'asc'; }
      oppdater();
    });
  }

  const $ = (id) => document.getElementById(id);
  const felt = {
    sok: $('kal-sok'), periode: $('kal-periode'), mnd: $('kal-mnd'), tid: $('kal-tid'), yield: $('kal-yield'),
    frekvens: $('kal-frekvens'), status: $('kal-status'), sort: $('kal-sort'), mine: $('kal-mine'),
  };
  const sektorBokser = [...kontroller.querySelectorAll('.kal-sektorer input')];

  const settFelter = () => {
    felt.sok.value = tilstand.sok;
    felt.periode.value = tilstand.periode;
    if (tilstand.mnd && maaneder.includes(tilstand.mnd)) felt.mnd.value = tilstand.mnd;
    else { const naa = idagIso.slice(0, 7); if (maaneder.includes(naa)) felt.mnd.value = naa; }
    felt.tid.value = tilstand.tid;
    felt.yield.value = String(tilstand.minYield);
    felt.frekvens.value = tilstand.frekvens;
    felt.status.value = tilstand.status;
    felt.mine.checked = tilstand.mine;
    for (const b of sektorBokser) b.checked = tilstand.sektorer.includes(b.value);
  };

  const lesFelter = () => {
    tilstand.sok = felt.sok.value.trim();
    tilstand.periode = felt.periode.value;
    tilstand.mnd = felt.mnd.value;
    tilstand.tid = felt.tid.value;
    tilstand.minYield = Number(felt.yield.value) || 0;
    tilstand.frekvens = felt.frekvens.value;
    tilstand.status = felt.status.value;
    tilstand.mine = felt.mine.checked;
    tilstand.sektorer = sektorBokser.filter(b => b.checked).map(b => b.value);
  };

  let synlige = [];
  let visMaaned = idagIso.slice(0, 7);
  let valgtDag = '';

  function oppdater() {
    const f = Object.assign({}, tilstand, { intervall: kalPeriode(tilstand.periode, idag, tilstand.mnd) });
    synlige = [];
    for (const r of rader) {
      const vis = kalPasser(r, f, idagIso, favoritter);
      r.tr.hidden = !vis;
      if (vis) synlige.push(r);
    }
    const sortert = [...rader].sort((a, b) => kalSammenlign(a, b, tilstand.kol, tilstand.retning, idagIso)
      || kalSammenlign(a, b, 'ex', 'asc', idagIso) || a.nr - b.nr);
    synlige = sortert.filter(r => !r.tr.hidden);
    const frag = document.createDocumentFragment();
    for (const r of sortert) frag.appendChild(r.tr);
    tbody.appendChild(frag);

    for (const th of kolonner) {
      const aktiv = th.dataset.kol === tilstand.kol;
      if (aktiv) th.setAttribute('aria-sort', tilstand.retning === 'asc' ? 'ascending' : 'descending');
      else th.removeAttribute('aria-sort');
      th.querySelector('.kal-pil').textContent = aktiv ? (tilstand.retning === 'asc' ? '▲' : '▼') : '';
    }
    felt.sort.value = `${tilstand.kol}:${tilstand.retning}`;
    if (felt.sort.value !== `${tilstand.kol}:${tilstand.retning}`) felt.sort.selectedIndex = -1;
    $('kal-mnd-etikett').hidden = tilstand.periode !== 'velg';

    const aktive = [tilstand.periode !== 'aar', tilstand.tid !== 'kommende', tilstand.sektorer.length > 0,
      tilstand.minYield > 0, !!tilstand.frekvens, !!tilstand.status, tilstand.mine].filter(Boolean).length;
    $('kal-filterantall').textContent = aktive ? `(${aktive})` : '';
    const ord = rader.length === 1 ? 'ex-dato' : 'ex-datoer';
    $('kal-teller').textContent = `Viser ${synlige.length} av ${rader.length} ${ord}`;
    ingen.hidden = synlige.length > 0;
    $('kal-ics-alle').disabled = synlige.length === 0;
    $('kal-csv').disabled = synlige.length === 0;

    const maaned = tilstand.visning === 'maaned';
    tabell.parentNode.hidden = maaned;
    maanedBoks.hidden = !maaned;
    for (const b of kontroller.querySelectorAll('[data-visning]')) {
      b.setAttribute('aria-pressed', String(b.dataset.visning === tilstand.visning));
    }
    if (maaned) tegnMaaned();
    visStjerner();

    const url = location.pathname + kalTilUrl(tilstand) + location.hash;
    if (url !== location.pathname + location.search + location.hash) history.replaceState(null, '', url);
  }

  // Månedsvisningen bygges av radene som er synlige med filtrene, ikke fra data.
  function tegnMaaned() {
    const [aar, m] = visMaaned.split('-').map(Number);
    const forste = new Date(aar, m - 1, 1);
    const dager = new Date(aar, m, 0).getDate();
    const start = (forste.getDay() + 6) % 7;
    const perDag = {};
    for (const r of synlige) if (r.ex.startsWith(visMaaned)) (perDag[r.ex] = perDag[r.ex] || []).push(r);
    let celler = '';
    for (let i = 0; i < start; i++) celler += '<div class="kal-dag kal-dag-tom" aria-hidden="true"></div>';
    for (let d = 1; d <= dager; d++) {
      const iso = `${visMaaned}-${String(d).padStart(2, '0')}`;
      const liste = perDag[iso] || [];
      const merker = liste.slice(0, 3).map(r => `<span class="kal-merke">${r.ticker}</span>`).join('') +
        (liste.length > 3 ? `<span class="kal-merke kal-merke-flere">+${liste.length - 3}</span>` : '');
      celler += liste.length
        ? `<button type="button" class="kal-dag${iso === idagIso ? ' kal-dag-idag' : ''}${iso === valgtDag ? ' kal-dag-valgt' : ''}" data-dag="${iso}" aria-label="${d}. ${KAL_MND[m - 1]}: ${liste.length} ${liste.length === 1 ? 'ex-dato' : 'ex-datoer'}"><span class="kal-dagnr">${d}</span>${merker}</button>`
        : `<div class="kal-dag${iso === idagIso ? ' kal-dag-idag' : ''}"><span class="kal-dagnr">${d}</span></div>`;
    }
    const dagListe = valgtDag && perDag[valgtDag]
      ? `<ul class="kal-dagliste">${perDag[valgtDag].map(r => `<li><a href="/aksjer/${r.ticker}/">${kalEsc(r.navn)}</a> ${r.ticker} · ${kalEsc(kalBelopTekst(r)) || 'beløp ikke meldt'} · kjøp senest ${r.kjop.split('-').reverse().join('.')}</li>`).join('')}</ul>`
      : '<p class="kal-hint">Velg en dag med ex-datoer for å se dem.</p>';
    maanedBoks.innerHTML = `
      <div class="kal-maanedhode">
        <button type="button" class="kal-knapp" data-mnd="-1" aria-label="Forrige måned">‹</button>
        <h3>${KAL_MND[m - 1].charAt(0).toUpperCase() + KAL_MND[m - 1].slice(1)} ${aar}</h3>
        <button type="button" class="kal-knapp" data-mnd="1" aria-label="Neste måned">›</button>
      </div>
      <div class="kal-ukedager" aria-hidden="true"><span>man</span><span>tir</span><span>ons</span><span>tor</span><span>fre</span><span>lør</span><span>søn</span></div>
      <div class="kal-rutenett">${celler}</div>
      ${dagListe}`;
  }

  maanedBoks.addEventListener('click', (e) => {
    const nav = e.target.closest('[data-mnd]');
    if (nav) {
      const [a, m] = visMaaned.split('-').map(Number);
      const ny = new Date(a, m - 1 + Number(nav.dataset.mnd), 1);
      visMaaned = kalIso(ny).slice(0, 7);
      valgtDag = '';
      tegnMaaned();
      return;
    }
    const dag = e.target.closest('[data-dag]');
    if (dag) { valgtDag = dag.dataset.dag; tegnMaaned(); }
  });

  function lastNed(innhold, filnavn, type) {
    const url = URL.createObjectURL(new Blob([innhold], { type }));
    const a = document.createElement('a');
    a.href = url;
    a.download = filnavn;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const stempel = () => new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+/, '');

  tbody.addEventListener('click', (e) => {
    const knapp = e.target.closest('[data-handling]');
    if (!knapp) return;
    const r = rader.find(x => x.tr === knapp.closest('tr'));
    if (!r) return;
    if (knapp.dataset.handling === 'fav') {
      if (favoritter.has(r.ticker)) favoritter.delete(r.ticker); else favoritter.add(r.ticker);
      lagreFav();
      if (tilstand.mine) oppdater(); else visStjerner();
    } else if (knapp.dataset.handling === 'ics') {
      lastNed(kalIcs([r], stempel()), `${r.ticker}-ex-${r.ex}.ics`, 'text/calendar;charset=utf-8');
    }
  });

  let venter;
  felt.sok.addEventListener('input', () => {
    clearTimeout(venter);
    venter = setTimeout(() => { lesFelter(); oppdater(); }, 80);
  });
  for (const el of [felt.periode, felt.mnd, felt.tid, felt.yield, felt.frekvens, felt.status, felt.mine, ...sektorBokser]) {
    el.addEventListener('change', () => { lesFelter(); oppdater(); });
  }
  felt.sort.addEventListener('change', () => {
    const [kol, retning] = felt.sort.value.split(':');
    tilstand.kol = kol; tilstand.retning = retning;
    oppdater();
  });
  for (const b of kontroller.querySelectorAll('[data-visning]')) {
    b.addEventListener('click', () => { tilstand.visning = b.dataset.visning; oppdater(); });
  }
  const nullstill = () => {
    const visning = tilstand.visning;
    tilstand = kalFraUrl('');
    tilstand.visning = visning;
    settFelter();
    oppdater();
  };
  $('kal-nullstill').addEventListener('click', nullstill);
  $('kal-ingen-nullstill').addEventListener('click', nullstill);
  $('kal-ics-alle').addEventListener('click', () => {
    lastNed(kalIcs(synlige, stempel()), 'utbyttekalender-exday.ics', 'text/calendar;charset=utf-8');
  });
  $('kal-csv').addEventListener('click', () => {
    lastNed(kalCsv(synlige), `utbyttekalender-${idagIso}.csv`, 'text/csv;charset=utf-8');
  });

  // Filterpanelet er åpent på store skjermer og lukket på mobil, til brukeren velger selv.
  if (window.matchMedia && window.matchMedia('(min-width: 640px)').matches) $('kal-filtre').open = true;
  if (location.search && /(sektor|yield|frekvens|status|mine|periode|tid)=/.test(location.search)) $('kal-filtre').open = true;

  settFelter();
  oppdater();
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', kalStart);
  else kalStart();
}

if (typeof module !== 'undefined') {
  module.exports = { kalEsc, kalNormaliser, kalAvstand, kalTreffer, kalPeriode, kalPasser, kalSammenlign,
    kalIcs, kalCsv, kalFraUrl, kalTilUrl, kalIso };
}
