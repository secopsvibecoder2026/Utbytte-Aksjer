// Tester for app.js — ferskhetsindikatoren og escHtml.
//
// visDataFerskhet() er skrevet fordi datoen var usynlig i praksis: elementet
// hadde `hidden sm:block`, så «kan være utdatert» viste seg aldri på mobil.
// Testene her holder på de tre beslutningene som er lette å rote bort igjen:
// ett døgn er normalt (helg), antall_feil skal ikke nevnes i det hele tatt,
// og et manglende felt skal gi ingen tekst framfor «Invalid Date».
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');

// ── Minimal DOM slik ui.test.js gjør det ──────────────────────────────────
function lagElement() {
  const klasser = new Set();
  return {
    textContent: '',
    title: '',
    classList: {
      toggle(navn, paa) { paa ? klasser.add(navn) : klasser.delete(navn); },
      contains: navn => klasser.has(navn),
    },
  };
}

let element = lagElement();

global.localStorage = {
  getItem: () => null, setItem() {}, removeItem() {}, clear() {},
};
global.document = {
  addEventListener() {},
  getElementById: id => (id === 'sist-oppdatert' ? element : null),
  querySelector: () => null,
  body: {},
};
global.window = {
  addEventListener() {},
  matchMedia: () => ({ matches: false, addEventListener() {} }),
};
// Merk: ingen `global.navigator = {}` her. Den er skrivebeskyttet i nyere
// Node og kaster «Cannot set property navigator». app.js rører den ikke ved
// import — bare inne i funksjoner som testene ikke kaller.

const { visDataFerskhet, escHtml } = require('../assets/app.js');

/** Bygger et tidsstempel N timer tilbake i tid. */
function timerSiden(t) {
  return new Date(Date.now() - t * 3600000).toISOString();
}

function kjor(json) {
  element = lagElement();
  visDataFerskhet(json);
  return element;
}

// ── Ferske data ────────────────────────────────────────────────────────────
test('fersk henting viser dato uten advarsel', () => {
  const el = kjor({ sist_oppdatert: timerSiden(2) });
  assert.match(el.textContent, /^Oppdatert /);
  assert.ok(!el.textContent.includes('gamle'), el.textContent);
  assert.equal(el.classList.contains('text-amber-600'), false);
  // title bærer alltid hele tidsstempelet — det er der detaljene bor når
  // den synlige teksten må være kort nok for 390 px.
  assert.match(el.title, /Tallene ble hentet/);
});

test('ett døgn er normalt — børsen er stengt i helgene', () => {
  const el = kjor({ sist_oppdatert: timerSiden(30) });
  assert.ok(!el.textContent.includes('gamle'), el.textContent);
  assert.match(el.textContent, /^Oppdatert /);
  assert.equal(el.classList.contains('text-amber-600'), false);
});

// ── Gamle data ─────────────────────────────────────────────────────────────
test('to døgn markeres som gammelt', () => {
  const el = kjor({ sist_oppdatert: timerSiden(49) });
  assert.equal(el.textContent, 'Tall 2 dager gamle', el.textContent);
  assert.ok(!el.textContent.includes('Oppdatert'), 'alder erstatter datoen, den kommer ikke i tillegg');
  assert.equal(el.classList.contains('text-amber-600'), true);
  assert.ok(el.title.length > 0);
});

test('16 dager — tilfellet som faktisk oppsto i august', () => {
  const el = kjor({ sist_oppdatert: timerSiden(16 * 24) });
  assert.ok(el.textContent.includes('16 dager gamle'), el.textContent);
});

// ── Feilede tickere nevnes ikke ────────────────────────────────────────────
// «N feilet» sto i topplinjen til 17.09.2026. Det er et tall om hentejobben,
// ikke om aksjene leseren ser på, og det navnga aldri hvilken aksje det
// gjaldt. Testene under holder det borte — også fra `title`, som er samme
// påstand i samme element.
test('antall_feil vises ikke i teksten', () => {
  const flere = kjor({ sist_oppdatert: timerSiden(1), antall_feil: 6 });
  assert.ok(!flere.textContent.includes('feilet'), flere.textContent);
  assert.ok(!/kunne ikke hentes/.test(flere.title), flere.title);

  const en = kjor({ sist_oppdatert: timerSiden(1), antall_feil: 1 });
  assert.ok(!en.textContent.includes('feilet'), en.textContent);
});

test('antall_feil farger ikke advarselen når dataene er ferske', () => {
  const el = kjor({ sist_oppdatert: timerSiden(1), antall_feil: 3 });
  assert.equal(el.classList.contains('text-amber-600'), false);
  assert.equal(el.classList.contains('text-gray-500'), true);
});

test('alderen varsler fortsatt, uavhengig av antall_feil', () => {
  const el = kjor({ sist_oppdatert: timerSiden(49), antall_feil: 0 });
  assert.equal(el.textContent, 'Tall 2 dager gamle', el.textContent);
  assert.equal(el.classList.contains('text-amber-600'), true);
});

// ── Robusthet ──────────────────────────────────────────────────────────────
test('manglende eller ugyldig tidsstempel gir ingen tekst', () => {
  for (const json of [null, undefined, {}, { sist_oppdatert: '' },
                      { sist_oppdatert: 'ikke-en-dato' }]) {
    const el = kjor(json);
    assert.equal(el.textContent, '', JSON.stringify(json));
  }
});

test('skriver ingenting når elementet ikke finnes', () => {
  const gammelt = global.document.getElementById;
  global.document.getElementById = () => null;
  assert.doesNotThrow(() => visDataFerskhet({ sist_oppdatert: timerSiden(1) }));
  global.document.getElementById = gammelt;
});

// ── escHtml: XSS-vakten hele nettstedet hviler på ─────────────────────────
test('escHtml escaper alle fem tegnene', () => {
  assert.equal(escHtml('<script>'), '&lt;script&gt;');
  assert.equal(escHtml('a & b'), 'a &amp; b');
  assert.equal(escHtml('"x"'), '&quot;x&quot;');
  assert.equal(escHtml("'x'"), '&#x27;x&#x27;');
});

test('escHtml escaper ampersand først, ikke dobbelt', () => {
  // Rekkefølgen er kritisk: escapes < før &, blir &lt; til &amp;lt;
  assert.equal(escHtml('&lt;'), '&amp;lt;');
});

test('escHtml takler null og undefined uten å skrive «null»', () => {
  assert.equal(escHtml(null), '');
  assert.equal(escHtml(undefined), '');
  assert.equal(escHtml(0), '0');
});

test('gråfargen slås av når advarselen slås på', () => {
  // text-gray-500 og text-amber-600 har samme spesifisitet. Står begge på,
  // avgjør rekkefølgen i stilarket — og da sto advarselen grå.
  const gammel = kjor({ sist_oppdatert: timerSiden(49) });
  assert.equal(gammel.classList.contains('text-amber-600'), true);
  assert.equal(gammel.classList.contains('text-gray-500'), false);

  const fersk = kjor({ sist_oppdatert: timerSiden(1) });
  assert.equal(fersk.classList.contains('text-gray-500'), true);
  assert.equal(fersk.classList.contains('text-amber-600'), false);
});
