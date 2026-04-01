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

const { beregnKostbasis, beregnIRR, beregnTWRSerie } = require('../assets/portefolje.js');

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
  // etter FIFO-forenkling: totalKost = 30000 - 30000 * (50/100) = 15000
  assert.equal(result.totalKost, 15000);
  assert.equal(result.vwap, 300);
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
