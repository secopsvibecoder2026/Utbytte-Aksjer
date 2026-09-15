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
, yieldErDelaar, utbetaltHittil, utbyttesplittStemmer, delaarMotbevist, maanederTekst } = require('../assets/ui.js');

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

// ── yieldErDelaar: speiler yield_er_delaar() i scripts/fetch_stocks.py ─────
//
// Regelen finnes i to språk fordi appen og sidegeneratoren begge trenger den.
// Tilfellene her er de samme som TestYieldErDelaar dekker på Python-siden, så
// et avvik mellom implementasjonene gir rødt i minst én av dem.
test('yieldErDelaar flagger en årsrate som er mindre enn én utbetaling', () => {
  assert.equal(yieldErDelaar({ frekvens: 'Halvårlig', utbytte_per_aksje: 2.2, siste_utbytte: 5.7 }), true);
  assert.equal(yieldErDelaar({ frekvens: 'Kvartalsvis', utbytte_per_aksje: 0.46, siste_utbytte: 5.94 }), true);
  assert.equal(yieldErDelaar({ frekvens: 'Månedlig', utbytte_per_aksje: 0.47, siste_utbytte: 128.2 }), true);
});

test('yieldErDelaar lar en normal betaler i fred', () => {
  assert.equal(yieldErDelaar({ frekvens: 'Kvartalsvis', utbytte_per_aksje: 12, siste_utbytte: 3 }), false);
  assert.equal(yieldErDelaar({ frekvens: 'Halvårlig', utbytte_per_aksje: 10, siste_utbytte: 5 }), false);
});

test('yieldErDelaar sier ingenting om årlige betalere', () => {
  // For en årlig betaler ER én utbetaling hele året, så regelen har ikke
  // grunnlag — den må ikke flagge dem.
  assert.equal(yieldErDelaar({ frekvens: 'Årlig', utbytte_per_aksje: 5, siste_utbytte: 5 }), false);
  assert.equal(yieldErDelaar({ frekvens: 'Uregelmessig', utbytte_per_aksje: 1, siste_utbytte: 9 }), false);
});

test('yieldErDelaar takler manglende og ugyldige verdier', () => {
  for (const a of [null, undefined, {}, { frekvens: 'Kvartalsvis' },
                   { frekvens: 'Kvartalsvis', utbytte_per_aksje: 0, siste_utbytte: 5 },
                   { frekvens: 'Kvartalsvis', utbytte_per_aksje: null, siste_utbytte: 'x' }]) {
    assert.equal(yieldErDelaar(a), false, JSON.stringify(a));
  }
});

// ── utbetaltHittil: speiler utbetalt_hittil() i scripts/fetch_stocks.py ────
//
// Det eneste tallet vi faktisk vet når årsraten er et delår. De to vaktene
// er hele poenget, og begge har et konkret motstykke i datasettet.
const I_AAR = new Date().getFullYear();

function hafni(endring = {}) {
  const rad = Object.assign(
    { ar: I_AAR, utbytte: 8.96, yield: 10.1, maaneder: [3, 6, 9] }, endring);
  return { pris: 88.65, historiske_utbytter: [rad] };
}

test('utbetaltHittil henter årets rad med beløp, antall og yield', () => {
  const f = utbetaltHittil(hafni());
  assert.equal(f.belop, 8.96);
  assert.equal(f.antall, 3);
  assert.equal(f.yield, 10.1);
  assert.equal(f.ar, I_AAR);
});

test('utbetaltHittil gir null uten rad for i år', () => {
  // Januar-tilfellet: fjorårets total må ikke merkes «hittil i år».
  assert.equal(utbetaltHittil(hafni({ ar: I_AAR - 1 })), null);
  assert.equal(utbetaltHittil({ pris: 100, historiske_utbytter: [] }), null);
});

test('utbetaltHittil forkaster et beløp over det dobbelte av kursen', () => {
  // 2020 Bulkers etter kapitalutdelingen: 132,66 på en 4,06-kroners aksje.
  assert.equal(utbetaltHittil({
    pris: 4.06,
    historiske_utbytter: [{ ar: I_AAR, utbytte: 132.66, yield: null, maaneder: [1, 2, 3, 4] }],
  }), null);
});

test('utbetaltHittil krever både yield og kurs', () => {
  assert.equal(utbetaltHittil(hafni({ yield: null })), null);
  assert.equal(utbetaltHittil(hafni({ utbytte: 0 })), null);
  const uten = hafni();
  uten.pris = 0;
  assert.equal(utbetaltHittil(uten), null);
});

test('utbetaltHittil takler søppel', () => {
  for (const a of [null, undefined, {}, { pris: 'x' },
                   { pris: 10, historiske_utbytter: null },
                   { pris: 10, historiske_utbytter: [null] }]) {
    assert.equal(utbetaltHittil(a), null, JSON.stringify(a));
  }
});

test('utbetaltHittil gir antall 0 når maaneder mangler', () => {
  // `maaneder` kommer bare fra en full henting. Beløpet skal vises likevel.
  const rad = hafni();
  delete rad.historiske_utbytter[0].maaneder;
  assert.equal(utbetaltHittil(rad).antall, 0);
});

// ── utbyttesplittStemmer: speiler utbyttesplitt_stemmer() i fetch_stocks.py ──
//
// Sumvakten er hele poenget. En børsmelding vi har lagret er ikke nødvendigvis
// den som hører til siste_utbytte — HUNT annonserte 1,50 med ex-dato fram i tid
// mens siste_utbytte fortsatt var 1,25.
function medSplitt(endring = {}) {
  return Object.assign({
    siste_utbytte: 5.70, valuta: 'NOK',
    utbyttesplitt: { ordinaert: 2.20, ekstraordinaert: 3.50, valuta: 'NOK' },
  }, endring);
}

test('utbyttesplittStemmer godtar når summen stemmer', () => {
  const r = utbyttesplittStemmer(medSplitt());
  assert.equal(r.ordinaert, 2.20);
  assert.equal(r.ekstraordinaert, 3.50);
  assert.equal(r.valuta, 'NOK');
});

test('utbyttesplittStemmer forkaster en melding om en annen utbetaling', () => {
  assert.equal(utbyttesplittStemmer(medSplitt({ siste_utbytte: 1.25 })), null);
});

test('utbyttesplittStemmer godtar hele utbetalingen som ekstraordinær', () => {
  const a = medSplitt({
    siste_utbytte: 1.25,
    utbyttesplitt: { ordinaert: 0, ekstraordinaert: 1.25, valuta: 'NOK' },
  });
  assert.equal(utbyttesplittStemmer(a).ekstraordinaert, 1.25);
});

test('utbyttesplittStemmer krever en ekstraordinær del', () => {
  const a = medSplitt({
    siste_utbytte: 2.20,
    utbyttesplitt: { ordinaert: 2.20, ekstraordinaert: 0, valuta: 'NOK' },
  });
  assert.equal(utbyttesplittStemmer(a), null);
});

test('utbyttesplittStemmer takler søppel', () => {
  for (const a of [null, undefined, {}, { utbyttesplitt: 'nei' },
                   { siste_utbytte: 0, utbyttesplitt: { ordinaert: 1, ekstraordinaert: 1 } },
                   { siste_utbytte: 5, utbyttesplitt: { ordinaert: 'x', ekstraordinaert: null } }]) {
    assert.equal(utbyttesplittStemmer(a), null, JSON.stringify(a));
  }
});

// ── delaarMotbevist: speiler delaar_motbevist() i fetch_stocks.py ───────────
//
// Var en del av utbetalingen ekstraordinær, faller slutningen «årsraten er
// mindre enn én utbetaling, altså et delår». En engangsutdeling kan godt
// overstige et helt års ordinære utbytte uten at årsraten er feil.
const KOG = {
  frekvens: 'Halvårlig', utbytte_per_aksje: 4.40, siste_utbytte: 5.70,
  utbytte_yield: 1.44, valuta: 'NOK',
  utbyttesplitt: { ordinaert: 2.20, ekstraordinaert: 3.50, valuta: 'NOK' },
};
const HUNT_A = {
  frekvens: 'Kvartalsvis', utbytte_per_aksje: 0.30, siste_utbytte: 1.25,
  utbytte_yield: 1.73, valuta: 'NOK',
  utbyttesplitt: { ordinaert: 0, ekstraordinaert: 1.25, valuta: 'NOK' },
};

test('delaarMotbevist: årsraten dekker den ordinære delen', () => {
  assert.equal(delaarMotbevist(KOG), true);
});

test('delaarMotbevist: hele utbetalingen ekstraordinær motbeviser alltid', () => {
  assert.equal(delaarMotbevist(HUNT_A), true);
});

test('delaarMotbevist: uten splitt motbevises ingenting', () => {
  const uten = Object.assign({}, KOG);
  delete uten.utbyttesplitt;
  assert.equal(delaarMotbevist(uten), false);
});

test('delaarMotbevist: årsrate under den ordinære delen står ved lag', () => {
  assert.equal(delaarMotbevist(Object.assign({}, KOG, { utbytte_per_aksje: 1.00 })), false);
});

test('delaarMotbevist: flagget og regelen er fortsatt uenige med vilje', () => {
  // yieldErDelaar skal fortsatt slå ut — den er delt med valider_data.py og
  // Sjekk 7 skal melde fra i loggen. Det er bare leseren som skjermes.
  assert.equal(yieldErDelaar(KOG), true);
  assert.equal(yieldErDelaar(KOG) && !delaarMotbevist(KOG), false);
});

// ── maanederTekst: erstatter «årlig / 12» i modalen ───────────────────────
//
// Et flatt månedssnitt antyder jevn inntekt. 47 % av norske utbetalinger ligger
// i mars–mai, så for de aller fleste er det usant.
test('maanederTekst skriver månedene som prosa', () => {
  assert.equal(maanederTekst({ utbetalingsmaaneder: [5, 11] }), 'mai og november');
  assert.equal(maanederTekst({ utbetalingsmaaneder: [4] }), 'april');
  assert.equal(maanederTekst({ utbetalingsmaaneder: [3, 5, 11] }), 'mars, mai og november');
});

test('maanederTekst sorterer og fjerner duplikater', () => {
  assert.equal(maanederTekst({ utbetalingsmaaneder: [11, 5, 5] }), 'mai og november');
});

test('maanederTekst kortes ned for hyppige betalere', () => {
  // Tolv månedsnavn på rad ville sprengt kortet i modalen.
  assert.equal(maanederTekst({ utbetalingsmaaneder: [1,2,3,4,5,6,7,8,9,10,11,12] }), '12 måneder i året');
});

test('maanederTekst gir tom streng uten mønster', () => {
  // Tom streng, ikke en halv setning — kalleren faller tilbake på snittet.
  for (const a of [null, undefined, {}, { utbetalingsmaaneder: [] },
                   { utbetalingsmaaneder: 'tull' }, { utbetalingsmaaneder: [0, 13] }]) {
    assert.equal(maanederTekst(a), '', JSON.stringify(a));
  }
});
