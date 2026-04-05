/* Cookie Consent – exday.no
   Consent Mode v2: oppdaterer GA når bruker godtar.
   Lagrer valg i localStorage('cookie_consent'). */
(function () {
  'use strict';

  var STORAGE_KEY = 'cookie_consent';

  function updateConsent(value) {
    if (typeof gtag !== 'function') return;
    gtag('consent', 'update', {
      analytics_storage: value,
      ad_storage: value,
      ad_user_data: value,
      ad_personalization: value,
    });
  }

  // Sjekk lagret valg og oppdater GA umiddelbart
  var stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'granted') {
    updateConsent('granted');
    return; // Ingen banner nødvendig
  }
  if (stored === 'denied') {
    return; // Allerede avslått, ikke vis banner
  }

  // Vis banner etter at DOM er klar
  function visBanner() {
    if (localStorage.getItem(STORAGE_KEY)) return; // Allerede valgt

    var banner = document.createElement('div');
    banner.id = 'cookie-banner';
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-label', 'Informasjonskapsler');
    banner.style.cssText = [
      'position:fixed',
      'bottom:0',
      'left:0',
      'right:0',
      'z-index:9999',
      'background:#fff',
      'border-top:1px solid #d1fae5',
      'padding:1rem 1.25rem',
      'box-shadow:0 -4px 12px rgba(0,0,0,0.08)',
      'font-family:system-ui,sans-serif',
      'font-size:0.875rem',
      'color:#374151',
      'display:flex',
      'align-items:center',
      'gap:1rem',
      'flex-wrap:wrap',
    ].join(';');

    banner.innerHTML =
      '<p style="margin:0;flex:1;min-width:200px">' +
        'Vi bruker informasjonskapsler for å forstå hvordan nettsiden brukes. ' +
        'Les mer i vår <a href="/personvern/" style="color:#16a34a;text-decoration:underline">personvernerklæring</a>.' +
      '</p>' +
      '<div style="display:flex;gap:0.5rem;flex-shrink:0">' +
        '<button id="cookie-decline" style="' +
          'padding:0.4rem 0.85rem;border:1px solid #d1d5db;border-radius:0.375rem;' +
          'background:#fff;color:#374151;cursor:pointer;font-size:0.8rem' +
        '">Kun nødvendige</button>' +
        '<button id="cookie-accept" style="' +
          'padding:0.4rem 0.85rem;border:none;border-radius:0.375rem;' +
          'background:#16a34a;color:#fff;cursor:pointer;font-size:0.8rem;font-weight:600' +
        '">Godta alle</button>' +
      '</div>';

    document.body.appendChild(banner);

    document.getElementById('cookie-accept').addEventListener('click', function () {
      localStorage.setItem(STORAGE_KEY, 'granted');
      updateConsent('granted');
      banner.remove();
    });

    document.getElementById('cookie-decline').addEventListener('click', function () {
      localStorage.setItem(STORAGE_KEY, 'denied');
      banner.remove();
    });

    // Mørk modus
    if (document.documentElement.classList.contains('dark')) {
      banner.style.background = '#1f2937';
      banner.style.borderTopColor = '#374151';
      banner.style.color = '#d1d5db';
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', visBanner);
  } else {
    visBanner();
  }
})();
