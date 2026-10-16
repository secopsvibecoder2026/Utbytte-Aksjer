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

const { visDataFerskhet, escHtml, osloDato, borsdag, forrigeBorsdag, kursdag, borsdagerMellom, slaaSammenKurs } = require('../assets/app.js');

// Alderen telles i børsdager, så testene må ha en fast «nå». Med Date.now()
// ville utfallet avhengt av hvilken ukedag testene kjøres. Onsdag 14.10.2026
// kl. 14:00 i Oslo.
const NAA = Date.parse('2026-10-14T12:00:00Z');

/** Bygger et tidsstempel N timer før NAA. */
function timerSiden(t) {
  return new Date(NAA - t * 3600000).toISOString();
}

function kjor(json, naa = NAA) {
  element = lagElement();
  visDataFerskhet(json, naa);
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

test('én børsdag bak er normalt', () => {
  // Tirsdag 14:00 mot onsdag 14:00. 30 timer tilbake ville vært tirsdag 08:00,
  // før børsåpning, altså mandagens kurser: to børsdager bak.
  const el = kjor({ sist_oppdatert: timerSiden(24) });
  assert.ok(!el.textContent.includes('gamle'), el.textContent);
  assert.match(el.textContent, /^Oppdatert /);
  assert.equal(el.classList.contains('text-amber-600'), false);
});

// ── Gamle data ─────────────────────────────────────────────────────────────
test('to børsdager markeres som gammelt', () => {
  const el = kjor({ sist_oppdatert: timerSiden(49) });
  assert.equal(el.textContent, 'Tall 2 børsdager gamle', el.textContent);
  assert.ok(!el.textContent.includes('Oppdatert'), 'alder erstatter datoen, den kommer ikke i tillegg');
  assert.equal(el.classList.contains('text-amber-600'), true);
  assert.ok(el.title.length > 0);
});

test('16 dager — tilfellet som faktisk oppsto i august', () => {
  // 28.09 kl. 14 til 14.10 kl. 14: tolv børsdager.
  const el = kjor({ sist_oppdatert: timerSiden(16 * 24) });
  assert.ok(el.textContent.includes('12 børsdager gamle'), el.textContent);
});

test('fredagens tall er ikke gamle mandag morgen', () => {
  // Datajobben gikk sist fredag 16.10 kl. 21:41 (Oslo). Mandag 19.10 kl. 08:30
  // er det ingen nyere sluttkurs å hente. Med døgn sto det «Tall 2 dager gamle».
  const fredag = '2026-10-16T19:41:00Z';
  const el = kjor({ sist_oppdatert: fredag }, Date.parse('2026-10-19T06:30:00Z'));
  assert.match(el.textContent, /^Oppdatert /);
  assert.equal(el.classList.contains('text-amber-600'), false);
  // Mandag ettermiddag mangler én børsdag. Det er normalt med GitHubs forsinkelser.
  assert.match(kjor({ sist_oppdatert: fredag }, Date.parse('2026-10-19T13:00:00Z')).textContent, /^Oppdatert /);
  // Tirsdag ettermiddag mangler to, og da skal leseren se det.
  assert.equal(kjor({ sist_oppdatert: fredag }, Date.parse('2026-10-20T13:00:00Z')).textContent,
               'Tall 2 børsdager gamle');
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
  assert.equal(el.textContent, 'Tall 2 børsdager gamle', el.textContent);
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

// ── Kurs: den nyeste av aksjer.json og priser.json vinner ─────────────────
// Det ekte tilfellet 09.10.2026: datajobben kom 13:57 UTC med dagens kurs,
// priser.json hadde fortsatt 08.10. Appen viste 08.10-kursen i en time.
const SCATC_0810 = { pris: 98.55, forrige_kurs: 97.1, endring_pct: 1.4933, endring_krs: 1.45,
                     dato: '2026-10-08', forrige_dato: '2026-10-07' };

test('osloDato følger Oslo, ikke UTC', () => {
  assert.equal(osloDato('2026-10-09T22:30:00Z'), '2026-10-10');  // 00:30 i Oslo
  assert.equal(osloDato(''), '');
  assert.equal(osloDato('tull'), '');
});

test('helg hører til fredagen, og dagen før mandag er fredag', () => {
  assert.equal(borsdag('2026-10-10'), '2026-10-09');
  assert.equal(borsdag('2026-10-11'), '2026-10-09');
  assert.equal(forrigeBorsdag('2026-10-12'), '2026-10-09');
  assert.equal(forrigeBorsdag('2026-10-09'), '2026-10-08');
});

test('eldre priser.json skriver ikke over dagens kurs fra aksjer.json', () => {
  const k = slaaSammenKurs(104.2, SCATC_0810, '2026-10-08T21:42:00Z', '2026-10-09T13:57:00Z');
  assert.equal(k.pris, 104.2);
  // Gårsdagens sluttkurs er kjent, så dagens endring kan regnes.
  assert.equal(k.endringKrs, 5.65);
  assert.equal(k.endringPct, 5.7331);
});

test('priser.json fra flere børsdager tilbake gir ingen endring', () => {
  const gammel = { ...SCATC_0810, dato: '2026-10-06' };
  const k = slaaSammenKurs(104.2, gammel, '2026-10-06T21:00:00Z', '2026-10-09T13:57:00Z');
  assert.equal(k.pris, 104.2);
  assert.equal(k.endringPct, undefined);  // ikke tre dagers endring som «i dag»
});

test('nyere priser.json vinner, som før', () => {
  const ny = { ...SCATC_0810, pris: 105, dato: '2026-10-09', forrige_kurs: 98.55 };
  const k = slaaSammenKurs(104.2, ny, '2026-10-09T15:03:00Z', '2026-10-09T13:57:00Z');
  assert.equal(k.pris, 105);
  assert.equal(k.endringPct, ny.endring_pct);
});

test('samme børsdag: den som ble hentet sist, har kursen', () => {
  const p = { pris: 104.0, forrige_kurs: 98.55, endring_pct: 5.53, endring_krs: 5.45, dato: '2026-10-09' };
  const k = slaaSammenKurs(104.2, p, '2026-10-09T12:00:00Z', '2026-10-09T13:57:00Z');
  assert.equal(k.pris, 104.2);
  assert.equal(k.endringKrs, 5.65);  // regnet mot gårsdagens slutt, passer til kursen som vises
});

test('fredagens priser gjelder fortsatt på lørdag', () => {
  const p = { pris: 104.5, forrige_kurs: 98.55, endring_pct: 6.04, endring_krs: 5.95, dato: '2026-10-09' };
  const k = slaaSammenKurs(104.2, p, '2026-10-09T21:25:00Z', '2026-10-09T20:32:00Z');
  assert.equal(k.pris, 104.5);
  assert.equal(k.endringPct, 6.04);
});

test('kursen hentet før børsåpning gjelder forrige børsdag', () => {
  assert.equal(kursdag('2026-10-12T23:21:00Z'), '2026-10-12');  // 01:21 tirsdag i Oslo
  assert.equal(kursdag('2026-10-13T06:59:00Z'), '2026-10-12');  // 08:59
  assert.equal(kursdag('2026-10-13T07:00:00Z'), '2026-10-13');  // 09:00
  assert.equal(kursdag('2026-10-19T05:00:00Z'), '2026-10-16');  // mandag 07:00 → fredag
  assert.equal(kursdag('2026-10-17T10:00:00Z'), '2026-10-16');  // lørdag
  assert.equal(kursdag(''), '');
});

test('datajobben etter midnatt gir ikke 0 % i hele appen', () => {
  // 13.10.2026: aksjer.json skrevet 01:21 Oslo med mandagens sluttkurs 104,20.
  // priser.json har også mandagens kurs, med fredagens sluttkurs som forrige.
  const p = { pris: 104.2, forrige_kurs: 98.55, endring_pct: 5.7331, endring_krs: 5.65,
              dato: '2026-10-12' };
  const k = slaaSammenKurs(104.2, p, '2026-10-12T21:47:00Z', '2026-10-12T23:21:00Z');
  assert.equal(k.pris, 104.2);
  assert.equal(k.endringKrs, 5.65);  // mot fredagen, ikke 0 mot mandagen selv
});

test('børsdager mellom to datoer hopper over helgen', () => {
  assert.equal(borsdagerMellom('2026-10-16', '2026-10-19'), 1);  // fredag → mandag
  assert.equal(borsdagerMellom('2026-10-16', '2026-10-16'), 0);
  assert.equal(borsdagerMellom('2026-10-19', '2026-10-16'), 0);
  assert.equal(borsdagerMellom('2026-10-12', '2026-10-23'), 9);
});

test('uten dato i priser.json eller tidsstempel i aksjer.json: som før', () => {
  const udatert = { pris: 99, endring_pct: 1, endring_krs: 1 };
  assert.equal(slaaSammenKurs(104.2, udatert, '2026-10-08T21:00:00Z', '2026-10-09T13:57:00Z').pris, 99);
  assert.equal(slaaSammenKurs(104.2, SCATC_0810, '2026-10-08T21:00:00Z', '').pris, 98.55);
});
