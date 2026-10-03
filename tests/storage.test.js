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

const { hentFav, lagreFav, erFavoritt, toggleFav, hentPortefoljer, hentAktivPF, lagrePF, skjermingsrenteFor } = require('../assets/storage.js');

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


// ── Porteføljelager som inneholder gyldig JSON av feil type ────────────────
// JSON.parse('null') kaster ikke, så try/catch fanget det aldri. hentAktivPF()
// krasjet da på pfl[id] hver gang porteføljefanen åpnet.
for (const verdi of ['null', '[]', '42', '"tekst"']) {
  test(`pf_portefoljer = ${verdi} gir tom portefølje, ikke krasj`, () => {
    localStorage.clear();
    localStorage.setItem('pf_portefoljer', verdi);
    assert.deepEqual(hentPortefoljer(), {});
    assert.doesNotThrow(() => hentAktivPF());
    assert.doesNotThrow(() => lagrePF({ EQNR: 10 }));
    assert.deepEqual(hentAktivPF().beholdning, { EQNR: 10 });
  });
}

// Skjermingsrenten er ulik per år — Skatteetaten, kontrollert 03.10.2026.
test('skjermingsrenteFor: fastsatte satser, og siste sats som anslag ellers', () => {
  assert.deepEqual(skjermingsrenteFor(2024), { sats: 0.039, fastsatt: true, aar: 2024 });
  assert.deepEqual(skjermingsrenteFor(2025), { sats: 0.036, fastsatt: true, aar: 2025 });
  assert.deepEqual(skjermingsrenteFor(2026), { sats: 0.036, fastsatt: false, aar: 2025 });
});
