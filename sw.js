'use strict';

// CACHE-VERSJON BYTTES AUTOMATISK AV GITHUB ACTIONS VED HVERT DEPLOY
const CACHE = 'exday-v10';
const NOTIF_CACHE = 'notif-prefs-v1';

const PRECACHE = [
  '/',
  '/app/',
  '/innstillinger/',
  '/assets/storage.js',
  '/assets/ui.js',
  '/assets/portefolje.js',
  '/assets/app.js',
  '/assets/tailwind.css',
  '/assets/style.css',
  '/assets/consent.js',
  '/assets/icon.svg',
  '/data/aksjer.json',
];

// ── INSTALL ───────────────────────────────────────────────────────────────────
self.addEventListener('install', event => {
  // Bruker individuelle put() i stedet for addAll() slik at én feilende fil
  // ikke aborter hele installasjonen og setter gammel SW i lås.
  event.waitUntil(
    caches.open(CACHE).then(cache =>
      Promise.allSettled(
        PRECACHE.map(url =>
          fetch(new Request(url, { cache: 'reload' }))
            .then(resp => { if (resp.ok) cache.put(url, resp); })
            .catch(() => {})
        )
      )
    ).then(() => self.skipWaiting())
  );
});

// ── ACTIVATE ──────────────────────────────────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys.filter(k => k !== CACHE && k !== NOTIF_CACHE).map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── FETCH ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // 1. aksjer.json: alltid nettverks-first
  if (url.pathname === '/data/aksjer.json') {
    event.respondWith(
      fetch(request)
        .then(resp => {
          if (resp.ok) caches.open(CACHE).then(c => c.put(request, resp.clone()));
          return resp;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // 2. HTML-navigasjon: nettverks-first med cache-bypass — brukere ser alltid
  //    siste versjon, og omgår nettleserens egen HTTP-cache (max-age frå GitHub Pages)
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(new Request(request, { cache: 'no-cache' }))
        .then(resp => {
          if (resp.ok) caches.open(CACHE).then(c => c.put(request, resp.clone()));
          return resp;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // 3. JS og CSS: nettverks-first med cache-bypass — samme som HTML-navigasjon
  //    for å omgå nettleserens HTTP-cache (GitHub Pages kan sette max-age)
  if (/\.(js|css)(\?.*)?$/.test(url.pathname)) {
    event.respondWith(
      fetch(new Request(request, { cache: 'no-cache' }))
        .then(resp => {
          if (resp.ok) caches.open(CACHE).then(c => c.put(request, resp.clone()));
          return resp;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // 4. Alt annet (bilder, ikoner): cache-first
  event.respondWith(
    caches.match(request).then(cached => cached || fetch(request))
  );
});

// ── PERIODIC BACKGROUND SYNC (daglig sjekk av ex-datoer) ─────────────────────
self.addEventListener('periodicsync', event => {
  if (event.tag === 'sjekk-ex-datoer') {
    event.waitUntil(sjekkExDatoer());
  }
});

// ── VARSEL-KLIKK: åpne/fokuser appen ─────────────────────────────────────────
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(list => {
      if (list.length > 0) return list[0].focus();
      return clients.openWindow('/');
    })
  );
});

// ── HJELPEFUNKSJONER ──────────────────────────────────────────────────────────
async function cacheGet(key) {
  try {
    const cache = await caches.open(NOTIF_CACHE);
    const resp = await cache.match(key);
    return resp ? resp.json() : null;
  } catch { return null; }
}

async function cachePut(key, data) {
  const cache = await caches.open(NOTIF_CACHE);
  await cache.put(key, new Response(JSON.stringify(data), {
    headers: { 'Content-Type': 'application/json' },
  }));
}

async function sjekkExDatoer() {
  const prefs = await cacheGet('/notif-prefs');
  if (!prefs || !prefs.length) return;

  let data;
  try {
    const resp = await fetch('/data/aksjer.json');
    data = await resp.json();
  } catch { return; }

  const aksjer = data.aksjer || [];
  const idag = new Date(); idag.setHours(0, 0, 0, 0);
  const vist = (await cacheGet('/vist-varsler')) || {};
  const nyVist = { ...vist };

  // Rens nøkler eldre enn 14 dager
  const grense = new Date(idag); grense.setDate(grense.getDate() - 14);
  Object.keys(nyVist).forEach(k => { if (new Date(nyVist[k]) < grense) delete nyVist[k]; });

  for (const a of aksjer) {
    if (!prefs.includes(a.ticker) || !a.ex_dato) continue;

    const exDato = new Date(a.ex_dato); exDato.setHours(0, 0, 0, 0);
    const dager = Math.round((exDato - idag) / (1000 * 60 * 60 * 24));
    if (dager < 0 || dager > 7) continue;

    const key = `${a.ticker}-${a.ex_dato}`;
    if (nyVist[key]) continue;

    const tittel = dager === 0
      ? `${a.ticker} ex-dato er i dag!`
      : `${a.ticker} ex-dato om ${dager} dag${dager === 1 ? '' : 'er'}`;
    const kropp = dager === 0
      ? `${a.navn} – du må eie aksjen i dag for å motta utbytte`
      : `${a.navn} – ex-dato ${new Date(a.ex_dato).toLocaleDateString('nb-NO', { day: 'numeric', month: 'long' })}`;

    await self.registration.showNotification(tittel, {
      body: kropp,
      icon: '/assets/icon.svg',
      badge: '/assets/icon.svg',
      tag: key,
      renotify: false,
      data: { url: '/' },
    });

    nyVist[key] = idag.toISOString();
  }

  await cachePut('/vist-varsler', nyVist);
}
