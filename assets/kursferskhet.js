'use strict';
/* Varsel på aksjesidene når kursen er eldre enn én børsdag (2026-11-18).

   Aksjesidene er statiske og bygges av datajobben fire ganger hver børsdag.
   Stopper jobben, står sida med kursen fra siste kjøring, og ingenting sier
   fra. Generatoren skriver børsdagen kursen gjelder (data-kursdag) og
   børsens fridager (data-fridager) på et skjult avsnitt. Dette skriptet
   regner ut hvor mange børsdager som har gått siden, og viser avsnittet når
   kursen ligger mer enn én børsdag bak.

   Børsdagen følger kursdag() i app.js: før kl. 09 i Oslo gjelder forrige
   børsdag. Fridagene kommer fra borsfridager() i fetch_stocks.py, så de to
   kan ikke være uenige om påske og jul. */

const KURS_MAKS_BORSDAGER = 1;
const KF_MND = ['januar', 'februar', 'mars', 'april', 'mai', 'juni', 'juli',
  'august', 'september', 'oktober', 'november', 'desember'];

function kfOsloNaa(naa) {
  const deler = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Oslo', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', hourCycle: 'h23',
  }).formatToParts(naa);
  const v = {};
  deler.forEach(d => { v[d.type] = d.value; });
  return { dato: `${v.year}-${v.month}-${v.day}`, time: Number(v.hour) };
}

function kfLeggTil(iso, dager) {
  const d = new Date(iso + 'T12:00:00Z');
  d.setUTCDate(d.getUTCDate() + dager);
  return d.toISOString().slice(0, 10);
}

function kfErBorsdag(iso, fridager) {
  const ukedag = new Date(iso + 'T12:00:00Z').getUTCDay();
  return ukedag !== 0 && ukedag !== 6 && !fridager.has(iso);
}

/** Børsdagen kursene skal gjelde nå: i dag fra kl. 09, ellers forrige børsdag. */
function kfGjeldendeBorsdag(naa, fridager) {
  const o = kfOsloNaa(naa);
  let d = o.time < 9 ? kfLeggTil(o.dato, -1) : o.dato;
  while (!kfErBorsdag(d, fridager)) d = kfLeggTil(d, -1);
  return d;
}

/** Børsdager etter `fra`, til og med `til`. */
function kfBorsdagerEtter(fra, til, fridager) {
  let n = 0;
  for (let d = kfLeggTil(fra, 1); d <= til; d = kfLeggTil(d, 1)) {
    if (kfErBorsdag(d, fridager)) n++;
  }
  return n;
}

/** Antall børsdager kursen ligger bak, eller 0 når den er fersk nok. */
function kursEtterslep(kursdag, naa, fridager) {
  if (!/^\d{4}-\d\d-\d\d$/.test(kursdag || '')) return 0;
  const n = kfBorsdagerEtter(kursdag, kfGjeldendeBorsdag(naa, fridager || new Set()), fridager || new Set());
  return n > KURS_MAKS_BORSDAGER ? n : 0;
}

function kfDatoLang(iso) {
  const [a, m, d] = iso.split('-').map(Number);
  return `${d}. ${KF_MND[m - 1]} ${a}`;
}

function kfVis() {
  const el = document.getElementById('kurs-varsel');
  if (!el) return;
  const kursdag = el.dataset.kursdag;
  const fridager = new Set((el.dataset.fridager || '').split(',').filter(Boolean));
  if (!kursEtterslep(kursdag, new Date(), fridager)) return;
  el.textContent = `Kursen på denne siden er fra ${kfDatoLang(kursdag)}, og siden er ikke `
    + 'oppdatert siden da. Kurs og direkteavkastning kan ha endret seg. '
    + 'Sjekk siste kurs i appen eller hos megleren din.';
  el.hidden = false;
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', kfVis);
  else kfVis();
}

if (typeof module !== 'undefined') {
  module.exports = { kursEtterslep, kfGjeldendeBorsdag, kfBorsdagerEtter, kfErBorsdag, kfOsloNaa, KURS_MAKS_BORSDAGER };
}
