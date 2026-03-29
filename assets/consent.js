'use strict';

(function () {
  var KEY = 'cookie_consent';

  function loadAnalytics() {
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', 'G-X6C9PERKMB');
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=G-X6C9PERKMB';
    document.head.appendChild(s);
  }

  function loadAds() {
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-3981936786393038';
    s.crossOrigin = 'anonymous';
    document.head.appendChild(s);
  }

  function hideBanner() {
    var b = document.getElementById('cookie-banner');
    if (b) b.style.display = 'none';
  }

  function showBanner() {
    var b = document.getElementById('cookie-banner');
    if (b) b.style.display = 'flex';
  }

  function applyConsent(val) {
    localStorage.setItem(KEY, val);
    hideBanner();
    if (val === 'all') {
      loadAnalytics();
      loadAds();
    }
  }

  // Expose to button onclick handlers
  window.cookieConsent = {
    accept: function () { applyConsent('all'); },
    decline: function () { applyConsent('necessary'); }
  };

  var existing = localStorage.getItem(KEY);
  if (existing === 'all') {
    loadAnalytics();
    loadAds();
  } else if (!existing) {
    // Show banner once DOM is ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', showBanner);
    } else {
      showBanner();
    }
  }
})();
