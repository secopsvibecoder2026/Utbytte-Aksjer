'use strict';
const test = require('node:test');
const assert = require('node:assert');
const k = require('../assets/kursferskhet.js');

const FRI = new Set(['2026-12-24', '2026-12-25', '2026-12-31', '2027-01-01']);
const oslo = (iso, tid) => new Date(`${iso}T${tid}:00+01:00`);   // vintertid

test('gjeldende børsdag: før kl. 09 gjelder forrige børsdag', () => {
  assert.equal(k.kfGjeldendeBorsdag(oslo('2026-11-18', '08:30'), FRI), '2026-11-17');
  assert.equal(k.kfGjeldendeBorsdag(oslo('2026-11-18', '09:30'), FRI), '2026-11-18');
  assert.equal(k.kfGjeldendeBorsdag(oslo('2026-11-23', '08:00'), FRI), '2026-11-20');  // mandag morgen → fredag
  assert.equal(k.kfGjeldendeBorsdag(oslo('2026-11-22', '14:00'), FRI), '2026-11-20');  // søndag
  assert.equal(k.kfGjeldendeBorsdag(oslo('2026-12-28', '08:00'), FRI), '2026-12-23');  // over jul
});

test('ingen varsel for kurs fra i dag eller forrige børsdag', () => {
  assert.equal(k.kursEtterslep('2026-11-18', oslo('2026-11-18', '15:00'), FRI), 0);
  assert.equal(k.kursEtterslep('2026-11-17', oslo('2026-11-18', '15:00'), FRI), 0);
  assert.equal(k.kursEtterslep('2026-11-20', oslo('2026-11-23', '15:00'), FRI), 0);  // fredag → mandag
  assert.equal(k.kursEtterslep('2026-12-23', oslo('2026-12-28', '15:00'), FRI), 0);  // jul er ikke etterslep
});

test('varsel når kursen ligger mer enn én børsdag bak', () => {
  assert.equal(k.kursEtterslep('2026-11-16', oslo('2026-11-18', '15:00'), FRI), 2);
  assert.equal(k.kursEtterslep('2026-11-19', oslo('2026-11-24', '10:00'), FRI), 3);
});

test('ugyldig eller manglende dato gir ikke varsel', () => {
  assert.equal(k.kursEtterslep('', oslo('2026-11-18', '15:00'), FRI), 0);
  assert.equal(k.kursEtterslep(undefined, oslo('2026-11-18', '15:00'), FRI), 0);
});
