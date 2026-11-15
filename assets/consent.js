/* Samtykke – exday.no
   Samtykket samles inn av Googles samtykkeverktøy (Personvern og meldinger i
   AdSense), som lastes sammen med AdSense-skriptet og sender valget videre til
   Consent Mode v2. Standardverdien «denied» settes i <head> på hver side.

   Fram til 15.11.2026 viste denne filen et eget banner. Med Googles melding i
   tillegg fikk besøkende to, så banneret er fjernet. Filen er beholdt fordi
   alle sidene og malene laster den.

   Det som er igjen:
   - den gamle nøkkelen «cookie_consent» slettes, siden den ikke styrer noe;
   - et element med data-samtykke-endre åpner Googles melding på nytt, slik
     at besøkende kan endre eller trekke tilbake samtykket. */
(function () {
  'use strict';

  try {
    localStorage.removeItem('cookie_consent');
  } catch (e) {
    // localStorage kan være sperret; da er det heller ingenting å rydde.
  }

  function aapneSamtykke() {
    window.googlefc = window.googlefc || {};
    window.googlefc.callbackQueue = window.googlefc.callbackQueue || [];
    window.googlefc.callbackQueue.push({
      CONSENT_API_READY: function () {
        window.googlefc.showRevocationMessage();
      },
    });
  }

  document.addEventListener('click', function (e) {
    var el = e.target && e.target.closest && e.target.closest('[data-samtykke-endre]');
    if (!el) return;
    e.preventDefault();
    aapneSamtykke();
  });

  window.aapneSamtykke = aapneSamtykke;
})();
