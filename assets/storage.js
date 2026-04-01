'use strict';

// ── LOCALSTORAGE VERSJON ────────────────────────────────────────────────────
const LS_VERSJON = 3;

function sjekkLSVersjon() {
  const lagret = parseInt(localStorage.getItem('ls_versjon') || '0', 10);
  if (lagret === LS_VERSJON) return;

  // v0 → v1: fjern gammel cookie-samtykkenøkkel
  if (lagret < 1) {
    localStorage.removeItem('cookie_consent');
  }

  // v1 → v2: transaksjonslogg innført (ingen datamigrasjon)

  // v2 → v3: migrér pf_beholdning + pf_transaksjoner til pf_portefoljer
  if (lagret < 3) {
    const gammelBeholdning = JSON.parse(localStorage.getItem('pf_beholdning') || '{}');
    const gammelTx         = JSON.parse(localStorage.getItem('pf_transaksjoner') || '{}');
    const eksisterende     = JSON.parse(localStorage.getItem('pf_portefoljer') || '{}');
    if (Object.keys(eksisterende).length === 0) {
      localStorage.setItem('pf_portefoljer', JSON.stringify({
        default: { id: 'default', navn: 'Min portefølje', beholdning: gammelBeholdning, transaksjoner: gammelTx }
      }));
      localStorage.setItem('pf_aktiv', 'default');
    }
    localStorage.removeItem('pf_beholdning');
    localStorage.removeItem('pf_transaksjoner');
  }

  localStorage.setItem('ls_versjon', LS_VERSJON);
}

sjekkLSVersjon();

// Skjermingsrente for inneværende år (oppdateres årlig av Skatteetaten)
const SKJERMINGSRENTE = 0.031; // 3,1 % (2024)
const SKATTESATS      = 0.3784; // 37,84 % effektiv skatt på utbytte (aksjonærmodellen)

// ── PROFIL ─────────────────────────────────────────────────────────────────
function hentProfil() {
  return {
    navn:      localStorage.getItem('profil_navn') || '',
    malMnd:    parseFloat(localStorage.getItem('profil_mal_mnd') || '0'),
    spareMaal: parseFloat(localStorage.getItem('profil_sparemaal') || '0')
  };
}

function lagreProfil(navn, malMnd, spareMaal) {
  localStorage.setItem('profil_navn', navn);
  localStorage.setItem('profil_mal_mnd', malMnd);
  localStorage.setItem('profil_sparemaal', spareMaal);
}

// ── FAVORITTER ─────────────────────────────────────────────────────────────
function hentFav() {
  try { return new Set(JSON.parse(localStorage.getItem('fav_aksjer') || '[]')); } catch { return new Set(); }
}
function lagreFav(fav) { localStorage.setItem('fav_aksjer', JSON.stringify([...fav])); }
function erFavoritt(ticker) { return hentFav().has(ticker); }
function toggleFav(ticker) {
  const fav = hentFav();
  if (fav.has(ticker)) fav.delete(ticker); else fav.add(ticker);
  lagreFav(fav);
}

// ── PORTEFØLJER (multi) ────────────────────────────────────────────────────
function hentPortefoljer() {
  try { return JSON.parse(localStorage.getItem('pf_portefoljer') || '{}'); } catch { return {}; }
}
function lagrePortefoljer(pfl) { localStorage.setItem('pf_portefoljer', JSON.stringify(pfl)); }
function hentAktivPFId() { return localStorage.getItem('pf_aktiv') || 'default'; }
function settAktivPFId(id) { localStorage.setItem('pf_aktiv', id); }

function hentAktivPF() {
  const pfl = hentPortefoljer();
  const id  = hentAktivPFId();
  if (!pfl[id]) {
    pfl[id] = { id, navn: 'Min portefølje', beholdning: {}, transaksjoner: {} };
    lagrePortefoljer(pfl);
  }
  return pfl[id];
}

function hentPF() { return hentAktivPF().beholdning || {}; }

function lagrePF(pf) {
  const pfl = hentPortefoljer();
  const id  = hentAktivPFId();
  if (!pfl[id]) pfl[id] = { id, navn: 'Min portefølje', beholdning: {}, transaksjoner: {} };
  pfl[id].beholdning = pf;
  lagrePortefoljer(pfl);
}

// ── TRANSAKSJONER ──────────────────────────────────────────────────────────
function hentTransaksjoner() { return hentAktivPF().transaksjoner || {}; }

function lagreTransaksjoner(tx) {
  const pfl = hentPortefoljer();
  const id  = hentAktivPFId();
  if (!pfl[id]) pfl[id] = { id, navn: 'Min portefølje', beholdning: {}, transaksjoner: {} };
  pfl[id].transaksjoner = tx;
  lagrePortefoljer(pfl);
}

// ── WATCHLISTER ────────────────────────────────────────────────────────────
function hentWatchlister() {
  try { return JSON.parse(localStorage.getItem('pf_watchlister') || '[]'); } catch { return []; }
}
function lagreWatchlister(wl) { localStorage.setItem('pf_watchlister', JSON.stringify(wl)); }

// ── NOTIF-PREFS ────────────────────────────────────────────────────────────
function hentNotifPrefs() {
  try {
    // Første gang: arv favoritter som standard så listen ikke er tom
    if (localStorage.getItem('notif_aksjer') === null) {
      const fav = hentFav();
      if (fav.size > 0) return fav;
    }
    return new Set(JSON.parse(localStorage.getItem('notif_aksjer') || '[]'));
  } catch { return new Set(); }
}

function lagreNotifPrefs(prefs) {
  localStorage.setItem('notif_aksjer', JSON.stringify([...prefs]));
  if ('caches' in window) {
    caches.open('notif-prefs-v1').then(cache =>
      cache.put('/notif-prefs', new Response(JSON.stringify([...prefs]), {
        headers: { 'Content-Type': 'application/json' },
      }))
    );
  }
}

// ── AKSJE-BRUKERDATA (notat + målpris) ────────────────────────────────────
function hentAlleAksjeData() {
  try { return JSON.parse(localStorage.getItem('aksje_data') || '{}'); } catch { return {}; }
}
function hentAksjeData(ticker) {
  return hentAlleAksjeData()[ticker] || { notat: '', malPris: 0 };
}
function lagreAksjeData(ticker, data) {
  const all = hentAlleAksjeData();
  all[ticker] = { ...all[ticker], ...data };
  localStorage.setItem('aksje_data', JSON.stringify(all));
}

// Node.js test export
if (typeof module !== 'undefined') module.exports = { hentFav, lagreFav, erFavoritt, toggleFav };
