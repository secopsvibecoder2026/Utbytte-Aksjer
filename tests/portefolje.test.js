// Tests for portefolje logic (beregnKostbasis, beregnIRR, beregnTWRSerie)
const { test } = require('node:test');
const assert = require('node:assert/strict');

// Mock localStorage (needed because storage.js is required by portefolje.js)
global.localStorage = (() => {
  let store = {};
  return {
    getItem: k => store[k] ?? null,
    setItem: (k, v) => store[k] = String(v),
    removeItem: k => delete store[k],
    clear: () => { store = {}; }
  };
})();
global.window = {};
global.document = {
  getElementById: () => null,
  querySelector: () => null,
  querySelectorAll: () => [],
  addEventListener: () => {}
};
global.alleAksjer = [];
global.osebxHistorikk = {};

// portefolje.js needs ui.js globals but only uses beregnKostbasis for our tests
// Stub the ui.js functions that portefolje.js might call at parse time
global.fmt = () => '—';
global.formaterDato = () => '—';
global.yieldKlasse = () => '';
global.payoutKlasse = () => '';
global.vekstKlasse = () => '';
global.beregnScore = () => 5;
global.scoreBadge = () => '';
global.visModal = () => {};
global.SEKTOR_FARGE = {};
global.FARGE_FALLBACK = '#9ca3af';

const { beregnKostbasis, beregnIRR, beregnTWRSerie, beregnUtbyttePrognose, _leggTilMnd } = require('../assets/portefolje.js');

// ── beregnKostbasis ─────────────────────────────────────────────────────────

test('beregnKostbasis: tomme transaksjoner gir nullverdier', () => {
  const result = beregnKostbasis('EQNR', {});
  assert.equal(result.antall, 0);
  assert.equal(result.totalKost, 0);
  assert.equal(result.vwap, 0);
  assert.equal(result.mottattUtbytte, 0);
});

test('beregnKostbasis: enkelt kjøp gir riktig VWAP', () => {
  const txMap = {
    EQNR: [{ id: '1', dato: '2024-01-15', type: 'kjøp', antall: 100, kurs: 300 }]
  };
  const result = beregnKostbasis('EQNR', txMap);
  assert.equal(result.antall, 100);
  assert.equal(result.totalKost, 30000);
  assert.equal(result.vwap, 300);
  assert.equal(result.mottattUtbytte, 0);
});

test('beregnKostbasis: kjøp deretter salg gir riktig gjenværende VWAP', () => {
  const txMap = {
    EQNR: [
      { id: '1', dato: '2024-01-01', type: 'kjøp', antall: 100, kurs: 300 },
      { id: '2', dato: '2024-06-01', type: 'salg', antall: 50, kurs: 320 }
    ]
  };
  const result = beregnKostbasis('EQNR', txMap);
  assert.equal(result.antall, 50);
  // FIFO: 50 av 100 aksjer à 300 kr solgt — gjenværende lott 50 × 300 = 15000
  assert.equal(result.totalKost, 15000);
  assert.equal(result.vwap, 300);
});

test('beregnKostbasis: ekte FIFO — salg forbruker eldste lott først', () => {
  // Kjøp 100 @ 100, kjøp 100 @ 300, selg 100.
  // FIFO (sktl. § 10-36): den eldste lotten (100 @ 100) selges.
  // Gjenværende: 100 @ 300 = 30 000 kr (snittkost-metoden ville gitt 20 000).
  const txMap = {
    EQNR: [
      { id: '1', dato: '2024-01-01', type: 'kjøp', antall: 100, kurs: 100 },
      { id: '2', dato: '2024-03-01', type: 'kjøp', antall: 100, kurs: 300 },
      { id: '3', dato: '2024-06-01', type: 'salg', antall: 100, kurs: 350 }
    ]
  };
  const result = beregnKostbasis('EQNR', txMap);
  assert.equal(result.antall, 100);
  assert.equal(result.totalKost, 30000);
  assert.equal(result.vwap, 300);
});

test('beregnKostbasis: FIFO håndterer salg på tvers av flere lotter', () => {
  // Selg 150: hele lott 1 (100 @ 100) + 50 av lott 2 (@ 300).
  // Gjenværende: 50 @ 300 = 15 000 kr.
  const txMap = {
    EQNR: [
      { id: '1', dato: '2024-01-01', type: 'kjøp', antall: 100, kurs: 100 },
      { id: '2', dato: '2024-03-01', type: 'kjøp', antall: 100, kurs: 300 },
      { id: '3', dato: '2024-06-01', type: 'salg', antall: 150, kurs: 350 }
    ]
  };
  const result = beregnKostbasis('EQNR', txMap);
  assert.equal(result.antall, 50);
  assert.equal(result.totalKost, 15000);
  assert.equal(result.vwap, 300);
});

test('beregnKostbasis: FIFO sorterer på dato uavhengig av innleggsrekkefølge', () => {
  // Transaksjonene ligger i «feil» rekkefølge i listen — dato skal styre.
  const txMap = {
    EQNR: [
      { id: '3', dato: '2024-06-01', type: 'salg', antall: 100, kurs: 350 },
      { id: '2', dato: '2024-03-01', type: 'kjøp', antall: 100, kurs: 300 },
      { id: '1', dato: '2024-01-01', type: 'kjøp', antall: 100, kurs: 100 }
    ]
  };
  const result = beregnKostbasis('EQNR', txMap);
  assert.equal(result.totalKost, 30000);
});

test('beregnKostbasis: oversalg tømmer beholdningen uten negativt antall', () => {
  const txMap = {
    EQNR: [
      { id: '1', dato: '2024-01-01', type: 'kjøp', antall: 50, kurs: 200 },
      { id: '2', dato: '2024-06-01', type: 'salg', antall: 80, kurs: 220 }
    ]
  };
  const result = beregnKostbasis('EQNR', txMap);
  assert.equal(result.antall, 0);
  assert.equal(result.totalKost, 0);
  assert.equal(result.vwap, 0);
});

test('beregnKostbasis: kjøp pluss utbytte gir riktig mottattUtbytte', () => {
  const txMap = {
    EQNR: [
      { id: '1', dato: '2024-01-01', type: 'kjøp', antall: 100, kurs: 300 },
      { id: '2', dato: '2024-06-15', type: 'utbytte', antall: 100, kurs: 8.5 }
    ]
  };
  const result = beregnKostbasis('EQNR', txMap);
  assert.equal(result.antall, 100);
  assert.equal(result.mottattUtbytte, 850);
});

test('beregnKostbasis: multiple kjøp gir vektet snitt VWAP', () => {
  const txMap = {
    EQNR: [
      { id: '1', dato: '2024-01-01', type: 'kjøp', antall: 100, kurs: 200 },
      { id: '2', dato: '2024-03-01', type: 'kjøp', antall: 100, kurs: 300 }
    ]
  };
  const result = beregnKostbasis('EQNR', txMap);
  assert.equal(result.antall, 200);
  assert.equal(result.totalKost, 50000);
  assert.equal(result.vwap, 250); // (20000 + 30000) / 200
});

test('beregnKostbasis: ukjent ticker returnerer nullverdier', () => {
  const txMap = { EQNR: [] };
  const result = beregnKostbasis('DNB', txMap);
  assert.equal(result.antall, 0);
  assert.equal(result.totalKost, 0);
  assert.equal(result.vwap, 0);
  assert.equal(result.mottattUtbytte, 0);
});

// ── beregnIRR ───────────────────────────────────────────────────────────────

test('beregnIRR: ingen transaksjoner gir harNokData=false', () => {
  global.alleAksjer = [];
  const result = beregnIRR({});
  assert.equal(result.harNokData, false);
});

test('beregnIRR: positiv kontantstrøm gir positiv IRR', () => {
  const tx = { EQNR: [{ id: '1', dato: '2024-01-01', type: 'kjøp', antall: 100, kurs: 100 }] };
  global.alleAksjer = [{ ticker: 'EQNR', pris: 120, navn: 'Equinor' }];
  const result = beregnIRR(tx);
  assert.equal(result.harNokData, true);
  assert.ok(result.irr_ar > 0, 'IRR bør være positiv ved kursgevinst');
});

test('beregnIRR: negativ kontantstrøm gir negativ IRR', () => {
  const tx = { EQNR: [{ id: '1', dato: '2024-01-01', type: 'kjøp', antall: 100, kurs: 100 }] };
  global.alleAksjer = [{ ticker: 'EQNR', pris: 80, navn: 'Equinor' }];
  const result = beregnIRR(tx);
  assert.equal(result.harNokData, true);
  assert.ok(result.irr_ar < 0, 'IRR bør være negativ ved kurstap');
});

test('beregnIRR: salg og utbytte teller som positive kontantstrømmer', () => {
  const tx = {
    EQNR: [
      { id: '1', dato: '2024-01-01', type: 'kjøp',    antall: 100, kurs: 100 },
      { id: '2', dato: '2024-06-01', type: 'utbytte',  antall: 100, kurs: 5   },
      { id: '3', dato: '2024-09-01', type: 'salg',     antall: 50,  kurs: 110 }
    ]
  };
  global.alleAksjer = [{ ticker: 'EQNR', pris: 105, navn: 'Equinor' }];
  const result = beregnIRR(tx);
  assert.equal(result.harNokData, true);
  assert.ok(typeof result.irr_ar === 'number');
  assert.ok(typeof result.periodeAr === 'number');
});

test('beregnIRR: ingen aksjer med kjent pris gir harNokData=false', () => {
  const tx = { EQNR: [{ id: '1', dato: '2024-01-01', type: 'kjøp', antall: 100, kurs: 100 }] };
  global.alleAksjer = [{ ticker: 'EQNR', pris: 0, navn: 'Equinor' }];
  const result = beregnIRR(tx);
  assert.equal(result.harNokData, false);
});

// ── beregnTWRSerie ──────────────────────────────────────────────────────────

test('beregnTWRSerie: uten transaksjoner = lik prisutvikling', () => {
  const historikk = { '2024-01-01': 100000, '2024-01-02': 105000, '2024-01-03': 110000 };
  const datoer    = ['2024-01-01', '2024-01-02', '2024-01-03'];
  const serie = beregnTWRSerie(historikk, datoer, {});
  assert.equal(serie.length, 3);
  assert.equal(serie[0], 100);
  assert.ok(Math.abs(serie[1] - 105) < 0.01);
  assert.ok(Math.abs(serie[2] - 110) < 0.01);
});

test('beregnTWRSerie: kontantstrøm MELLOM snapshots justeres også ut', () => {
  // Snapshots 1. og 3. jan; kjøp 2. jan (ingen snapshot den dagen).
  // Uten fix ble hele innskuddet talt som avkastning.
  const historikk = { '2024-01-01': 100000, '2024-01-03': 115000 };
  const datoer    = ['2024-01-01', '2024-01-03'];
  const tx = { EQNR: [{ id: '1', dato: '2024-01-02', type: 'kjøp', antall: 50, kurs: 200 }] };
  const serie = beregnTWRSerie(historikk, datoer, tx);
  assert.equal(serie[0], 100);
  // 115000 / (100000 + 10000) * 100 ≈ 104.55 — ikke 115
  assert.ok(Math.abs(serie[1] - (115000 / 110000 * 100)) < 0.01);
});

test('beregnTWRSerie: kontantstrøm på siste snapshot-dato telles med', () => {
  // Kjøp samme dag som siste snapshot: snapshotet inkluderer kjøpet,
  // så innskuddet må inn i nevneren for ikke å telles som avkastning.
  const historikk = { '2024-01-01': 100000, '2024-01-05': 112000 };
  const datoer    = ['2024-01-01', '2024-01-05'];
  const tx = { EQNR: [{ id: '1', dato: '2024-01-05', type: 'kjøp', antall: 50, kurs: 200 }] };
  const serie = beregnTWRSerie(historikk, datoer, tx);
  // 112000 / (100000 + 10000) * 100 ≈ 101.82 — ikke 112
  assert.ok(Math.abs(serie[1] - (112000 / 110000 * 100)) < 0.01);
});

test('beregnTWRSerie: nyttinnskudd justeres ut av TWR', () => {
  // Dag 1: portefølje 100k. Kjøp 50 aksjer à 200 kr = 10k innskudd.
  // Dag 2: portefølje 115k. Uten TWR: 115%. Med TWR: 115/(100+10)*100 ≈ 104.55%
  const historikk = { '2024-01-01': 100000, '2024-01-02': 115000 };
  const datoer    = ['2024-01-01', '2024-01-02'];
  const tx = { EQNR: [{ id: '1', dato: '2024-01-01', type: 'kjøp', antall: 50, kurs: 200 }] };
  const serie = beregnTWRSerie(historikk, datoer, tx);
  assert.equal(serie[0], 100);
  assert.ok(Math.abs(serie[1] - (115000 / 110000 * 100)) < 0.01);
});

// ── beregnUtbyttePrognose («Min utbyttelønn») ───────────────────────────────

test('_leggTilMnd: håndterer årsskifte og klemmer dag til 28', () => {
  assert.equal(_leggTilMnd('2026-11-15', 3), '2027-02-15');
  assert.equal(_leggTilMnd('2026-01-31', 1), '2026-02-28');
  assert.equal(_leggTilMnd('2026-07-01', 12), '2027-07-01');
});

test('prognose: kvartalsvis med annonsert fremtidig betalingsdato gir 4 betalinger', () => {
  const beholdning = [{
    ticker: 'EQNR', navn: 'Equinor', antall: 100, forv_ar: 1448,
    frekvens: 'Kvartalsvis', ex_dato: '2026-08-13', betaling_dato: '2026-08-27'
  }];
  const p = beregnUtbyttePrognose(beholdning, '2026-07-05');
  assert.equal(p.utbetalinger.length, 4);
  assert.equal(p.utbetalinger[0].dato, '2026-08-27');
  assert.equal(p.utbetalinger[0].annonsert, true);
  assert.equal(p.utbetalinger[1].annonsert, false);
  assert.ok(Math.abs(p.utbetalinger[0].belop - 362) < 0.01);
  assert.ok(Math.abs(p.bruttoAr - 1448) < 0.01);
});

test('prognose: passert betalingsdato rulles frem og mister annonsert-status', () => {
  const beholdning = [{
    ticker: 'TEL', navn: 'Telenor', antall: 50, forv_ar: 500,
    frekvens: 'Halvårlig', betaling_dato: '2026-05-20'
  }];
  const p = beregnUtbyttePrognose(beholdning, '2026-07-05');
  assert.equal(p.utbetalinger.length, 2);
  assert.equal(p.utbetalinger[0].dato, '2026-11-20');  // +6 mnd fra passert dato
  assert.equal(p.utbetalinger[0].annonsert, false);
});

test('prognose: årlig betaler nøyaktig én gang på 12 måneder', () => {
  const beholdning = [{
    ticker: 'ORK', navn: 'Orkla', antall: 10, forv_ar: 100,
    frekvens: 'Årlig', betaling_dato: '2026-04-15'
  }];
  const p = beregnUtbyttePrognose(beholdning, '2026-07-05');
  assert.equal(p.utbetalinger.length, 1);
  assert.equal(p.utbetalinger[0].dato, '2027-04-15');
});

test('prognose: uten datoer brukes typiske måneder som estimat', () => {
  const beholdning = [{
    ticker: 'X', navn: 'X ASA', antall: 10, forv_ar: 400, frekvens: 'Kvartalsvis'
  }];
  const p = beregnUtbyttePrognose(beholdning, '2026-07-05');
  assert.equal(p.utbetalinger.length, 4);
  assert.ok(p.utbetalinger.every(u => u.annonsert === false));
  assert.equal(p.utbetalinger[0].dato, '2026-09-15');  // neste default-kvartalsmåned
});

test('prognose: uregelmessig uten dato havner i utenDato-listen', () => {
  const beholdning = [{
    ticker: 'Y', navn: 'Y ASA', antall: 5, forv_ar: 250, frekvens: 'Uregelmessig'
  }];
  const p = beregnUtbyttePrognose(beholdning, '2026-07-05');
  assert.equal(p.utbetalinger.length, 0);
  assert.equal(p.utenDato.length, 1);
  assert.equal(p.utenDato[0].belop, 250);
});

test('prognose: månedssummer dekker 12 rullerende måneder og summerer til brutto', () => {
  const beholdning = [
    { ticker: 'A', navn: 'A', antall: 1, forv_ar: 1200, frekvens: 'Månedlig', betaling_dato: '2026-07-20' },
    { ticker: 'B', navn: 'B', antall: 1, forv_ar: 400,  frekvens: 'Kvartalsvis', betaling_dato: '2026-09-10' }
  ];
  const p = beregnUtbyttePrognose(beholdning, '2026-07-05');
  assert.equal(p.mndSum.length, 12);
  assert.equal(p.mndSum[0].key, '2026-07');
  assert.equal(p.mndSum[11].key, '2027-06');
  const sumMnd = p.mndSum.reduce((s, m) => s + m.belop, 0);
  assert.ok(Math.abs(sumMnd - p.bruttoAr) < 0.01);
  assert.ok(Math.abs(p.bruttoAr - 1600) < 0.01);  // 12×100 + 4×100
});

test('prognose: aksjer uten utbytte bidrar ikke', () => {
  const p = beregnUtbyttePrognose([{ ticker: 'Z', navn: 'Z', antall: 10, forv_ar: 0, frekvens: 'Årlig' }], '2026-07-05');
  assert.equal(p.utbetalinger.length, 0);
  assert.equal(p.bruttoAr, 0);
});
