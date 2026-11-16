'use strict';
const test = require('node:test');
const assert = require('node:assert');
const k = require('../assets/utbyttekalender.js');

const rad = (o) => Object.assign({ ticker: 'X', navn: 'X', sektor: 'Finans', frekvens: 'Årlig', ex: '2026-11-20',
  kjop: '2026-11-19', betaling: '', belop: 1, valuta: 'NOK', yield: 5, status: 'vedtatt' }, o);

test('søket tåler manglende æøå og små skrivefeil', () => {
  assert.ok(k.kalTreffer('var energi', 'Vår Energi', 'VAR'));
  assert.ok(k.kalTreffer('equnor', 'Equinor', 'EQNR'));
  assert.ok(k.kalTreffer('stolt nielsen', 'Stolt-Nielsen', 'SNI'));
  assert.ok(k.kalTreffer('kid', 'Kid', 'KID'));
  assert.ok(!k.kalTreffer('dnb', 'Vår Energi', 'VAR'));
  assert.ok(!k.kalTreffer('xyzqq', 'Equinor', 'EQNR'));
  assert.equal(k.kalNormaliser('Ærø Ølen Ås'), 'aero olen as');
});

test('perioder regnes fra mandag og fra måneden', () => {
  const ons = new Date(2026, 10, 18);            // onsdag 18.11.2026
  assert.deepEqual(k.kalPeriode('uke', ons), ['2026-11-16', '2026-11-22']);
  assert.deepEqual(k.kalPeriode('nesteuke', ons), ['2026-11-23', '2026-11-29']);
  assert.deepEqual(k.kalPeriode('30d', ons), ['2026-11-18', '2026-12-18']);
  assert.deepEqual(k.kalPeriode('maaned', ons), ['2026-11-01', '2026-11-30']);
  assert.deepEqual(k.kalPeriode('velg', ons, '2026-02'), ['2026-02-01', '2026-02-28']);
  assert.equal(k.kalPeriode('aar', ons), null);
});

test('filtrene', () => {
  const idag = '2026-11-16';
  const r = rad({ ticker: 'DNB', navn: 'DNB Bank', yield: 6 });
  assert.ok(k.kalPasser(r, { tid: 'kommende' }, idag));
  assert.ok(!k.kalPasser(r, { tid: 'passerte' }, idag));
  assert.ok(!k.kalPasser(r, { tid: 'alle', minYield: 8 }, idag));
  assert.ok(k.kalPasser(r, { tid: 'alle', sektorer: ['Finans', 'Energi'] }, idag));
  assert.ok(!k.kalPasser(r, { tid: 'alle', sektorer: ['Energi'] }, idag));
  assert.ok(!k.kalPasser(r, { tid: 'alle', mine: true }, idag, new Set(['EQNR'])));
  assert.ok(k.kalPasser(r, { tid: 'alle', mine: true }, idag, new Set(['DNB'])));
  assert.ok(!k.kalPasser(r, { tid: 'alle', intervall: ['2026-12-01', '2026-12-31'] }, idag));
});

test('standardsortering er kommende først, så passerte nyeste først', () => {
  const idag = '2026-11-16';
  const rader = [rad({ ex: '2026-03-01' }), rad({ ex: '2026-12-01' }), rad({ ex: '2026-11-20' }), rad({ ex: '2026-10-01' })];
  const s = rader.slice().sort((a, b) => k.kalSammenlign(a, b, 'ex', 'asc', idag)).map(r => r.ex);
  assert.deepEqual(s, ['2026-11-20', '2026-12-01', '2026-10-01', '2026-03-01']);
  const ned = rader.slice().sort((a, b) => k.kalSammenlign(a, b, 'ex', 'desc', idag)).map(r => r.ex);
  assert.deepEqual(ned, ['2026-12-01', '2026-11-20', '2026-10-01', '2026-03-01']);
  const belop = [rad({ belop: null }), rad({ belop: 2 }), rad({ belop: 5 })]
    .sort((a, b) => k.kalSammenlign(a, b, 'utbytte', 'desc', idag)).map(r => r.belop);
  assert.deepEqual(belop, [5, 2, null]);   // ukjent beløp står sist
});

test('URL-en speiler filtrene og tilbake', () => {
  const t = k.kalFraUrl('?sektor=Energi,Finans&yield=5&periode=30d&tid=alle&sort=yield:desc&mine=1&q=dnb');
  assert.deepEqual(t.sektorer, ['Energi', 'Finans']);
  assert.equal(t.minYield, 5);
  assert.equal(k.kalTilUrl(t), '?q=dnb&periode=30d&tid=alle&sektor=Energi%2CFinans&yield=5&mine=1&sort=yield%3Adesc');
  assert.equal(k.kalTilUrl(k.kalFraUrl('')), '');
});

test('.ics har heldag, påminnelse og brettede linjer', () => {
  const ics = k.kalIcs([rad({ ticker: 'DOF', navn: 'DOF', ex: '2026-11-20', kjop: '2026-11-19', belop: 0.4, valuta: 'USD' })], '20261116T000000Z');
  assert.match(ics, /DTSTART;VALUE=DATE:20261120\r\n/);
  assert.match(ics, /DTEND;VALUE=DATE:20261121\r\n/);
  assert.match(ics, /TRIGGER:-PT39H/);             // kl. 09 dagen før kjøp senest
  assert.match(ics, /UID:DOF-20261120@exday\.no/);
  assert.match(ics, /0\\,40 USD/);
  assert.doesNotMatch(ics, /foreslått/);
  const fore = k.kalIcs([rad({ status: 'foreslatt' })], '20261116T000000Z').replace(/\r\n /g, '');
  assert.match(fore, /foreslått\\, ikke vedtatt/);
  for (const l of ics.split('\r\n')) assert.ok(Buffer.byteLength(l) <= 75, l);
});

test('CSV bruker semikolon og desimalkomma', () => {
  const csv = k.kalCsv([rad({ navn: 'Navn; med semikolon', belop: 1.5, yield: 4.25 })]);
  const linje = csv.split('\r\n')[1];
  assert.ok(linje.startsWith('"Navn; med semikolon";X;Finans;1,5;NOK;4,25;2026-11-20'));
});

test('escaping', () => {
  assert.equal(k.kalEsc('<b a="1">&'), '&lt;b a=&quot;1&quot;&gt;&amp;');
});
