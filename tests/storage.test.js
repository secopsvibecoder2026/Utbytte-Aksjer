// Tests for storage logic (toggleFav, erFavoritt)
const { test } = require('node:test');
const assert = require('node:assert/strict');

// Mock localStorage
global.localStorage = (() => {
  let store = {};
  return {
    getItem: k => store[k] ?? null,
    setItem: (k, v) => store[k] = String(v),
    removeItem: k => delete store[k],
    clear: () => { store = {}; }
  };
})();

// Stub out caches (used by lagreNotifPrefs)
global.window = { caches: undefined };

const { hentFav, lagreFav, erFavoritt, toggleFav } = require('../assets/storage.js');

test('hentFav returnerer tom Set når localStorage er tom', () => {
  localStorage.clear();
  const fav = hentFav();
  assert.equal(fav.size, 0);
  assert.ok(fav instanceof Set);
});

test('lagreFav og hentFav roundtrip', () => {
  localStorage.clear();
  const fav = new Set(['EQNR', 'DNB']);
  lagreFav(fav);
  const hentet = hentFav();
  assert.equal(hentet.size, 2);
  assert.ok(hentet.has('EQNR'));
  assert.ok(hentet.has('DNB'));
});

test('erFavoritt returnerer false når ticker ikke er favoritt', () => {
  localStorage.clear();
  assert.equal(erFavoritt('EQNR'), false);
});

test('erFavoritt returnerer true etter at ticker er lagt til', () => {
  localStorage.clear();
  lagreFav(new Set(['EQNR']));
  assert.equal(erFavoritt('EQNR'), true);
});

test('toggleFav legger til ny ticker', () => {
  localStorage.clear();
  toggleFav('EQNR');
  assert.equal(erFavoritt('EQNR'), true);
});

test('toggleFav fjerner eksisterende ticker', () => {
  localStorage.clear();
  lagreFav(new Set(['EQNR']));
  toggleFav('EQNR');
  assert.equal(erFavoritt('EQNR'), false);
});

test('toggleFav toggler frem og tilbake', () => {
  localStorage.clear();
  toggleFav('DNB');
  assert.equal(erFavoritt('DNB'), true);
  toggleFav('DNB');
  assert.equal(erFavoritt('DNB'), false);
  toggleFav('DNB');
  assert.equal(erFavoritt('DNB'), true);
});

test('hentFav returnerer tom Set ved ugyldig JSON', () => {
  localStorage.setItem('fav_aksjer', 'ikke-gyldig-json{{{');
  const fav = hentFav();
  assert.equal(fav.size, 0);
});
