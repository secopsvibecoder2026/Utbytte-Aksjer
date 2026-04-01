// Tests for UI helper functions
const { test } = require('node:test');
const assert = require('node:assert/strict');

// Mock DOM / browser globals needed by ui.js
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
  addEventListener: () => {},
  documentElement: { classList: { toggle: () => {}, contains: () => false } }
};

// ui.js uses alleAksjer global — stub it
global.alleAksjer = [];

const {
  fmt,
  formaterDato,
  yieldKlasse,
  payoutKlasse,
  vekstKlasse,
  beregnScore,
  beregnYtdInntekt
} = require('../assets/ui.js');

// ── fmt ────────────────────────────────────────────────────────────────────
test('fmt returnerer — for null', () => {
  assert.equal(fmt(null), '—');
});

test('fmt returnerer — for 0', () => {
  assert.equal(fmt(0), '—');
});

test('fmt formaterer positivt tall med to desimaler', () => {
  const resultat = fmt(12.5);
  assert.ok(resultat.includes('12'), `forventet "12" i "${resultat}"`);
});

// ── formaterDato ────────────────────────────────────────────────────────────
test('formaterDato returnerer — for tom streng', () => {
  assert.equal(formaterDato(''), '—');
});

test('formaterDato returnerer — for null', () => {
  assert.equal(formaterDato(null), '—');
});

test('formaterDato formaterer ISO dato', () => {
  const resultat = formaterDato('2025-01-15');
  assert.ok(typeof resultat === 'string' && resultat.length > 0);
  assert.ok(resultat.includes('2025') || resultat.includes('jan'));
});

// ── yieldKlasse ─────────────────────────────────────────────────────────────
test('yieldKlasse: yield >= 10 er hoy', () => {
  assert.equal(yieldKlasse(10), 'yield-hoy');
  assert.equal(yieldKlasse(15), 'yield-hoy');
});

test('yieldKlasse: yield >= 6 er god', () => {
  assert.equal(yieldKlasse(6), 'yield-god');
  assert.equal(yieldKlasse(8), 'yield-god');
});

test('yieldKlasse: yield >= 3 er middels', () => {
  assert.equal(yieldKlasse(3), 'yield-middels');
  assert.equal(yieldKlasse(5), 'yield-middels');
});

test('yieldKlasse: yield < 3 er lav', () => {
  assert.equal(yieldKlasse(2), 'yield-lav');
  assert.equal(yieldKlasse(0), 'yield-lav');
});

// ── payoutKlasse ────────────────────────────────────────────────────────────
test('payoutKlasse: payout <= 0 er grå', () => {
  assert.ok(payoutKlasse(0).includes('gray'));
});

test('payoutKlasse: payout <= 50 er normal', () => {
  const k = payoutKlasse(50);
  assert.ok(k.includes('gray-7') || k.includes('gray-3'));
});

test('payoutKlasse: payout <= 75 er advarsel', () => {
  const k = payoutKlasse(75);
  assert.ok(k.includes('amber'));
});

test('payoutKlasse: payout > 75 er rød', () => {
  const k = payoutKlasse(80);
  assert.ok(k.includes('red'));
});

// ── vekstKlasse ─────────────────────────────────────────────────────────────
test('vekstKlasse: vekst > 10 er emerald', () => {
  assert.ok(vekstKlasse(11).includes('emerald'));
});

test('vekstKlasse: vekst > 0 er grå', () => {
  assert.ok(vekstKlasse(5).includes('gray'));
});

test('vekstKlasse: vekst < 0 er rød', () => {
  assert.ok(vekstKlasse(-1).includes('red'));
});

test('vekstKlasse: vekst === 0 er grå', () => {
  assert.ok(vekstKlasse(0).includes('gray'));
});

// ── beregnScore ─────────────────────────────────────────────────────────────
test('beregnScore er mellom 1 og 10', () => {
  const a = { utbytte_yield: 5, payout_ratio: 40, utbytte_vekst_5ar: 3, ar_med_utbytte: 7, snitt_yield_5ar: 4.8 };
  const score = beregnScore(a);
  assert.ok(score >= 1 && score <= 10, `score ${score} er utenfor [1, 10]`);
});

test('beregnScore: perfekt aksje gir høy score', () => {
  const a = { utbytte_yield: 12, payout_ratio: 40, utbytte_vekst_5ar: 15, ar_med_utbytte: 15, snitt_yield_5ar: 11.5 };
  const score = beregnScore(a);
  assert.ok(score >= 8, `forventet score >= 8, fikk ${score}`);
});

test('beregnScore: dårlig aksje gir lav score', () => {
  const a = { utbytte_yield: 1, payout_ratio: 95, utbytte_vekst_5ar: -5, ar_med_utbytte: 1, snitt_yield_5ar: 0 };
  const score = beregnScore(a);
  assert.ok(score <= 3, `forventet score <= 3, fikk ${score}`);
});

// ── beregnYtdInntekt ────────────────────────────────────────────────────────
test('beregnYtdInntekt returnerer 0 for tom beholdning', () => {
  assert.equal(beregnYtdInntekt([]), 0);
});

test('beregnYtdInntekt inkluderer betaling som har passert i år', () => {
  const idag = new Date();
  const forrigeManed = new Date(idag);
  forrigeManed.setMonth(idag.getMonth() - 1);
  const datoStr = forrigeManed.toISOString().slice(0, 10);
  const beholdning = [{
    antall: 100,
    siste_utbytte: 5,
    betaling_dato: datoStr,
    frekvens: 'Årlig',
    utbytte_per_aksje: 5,
    historiske_utbytter: []
  }];
  const total = beregnYtdInntekt(beholdning);
  assert.equal(total, 500);
});
