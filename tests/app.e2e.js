const { test, expect } = require('@playwright/test');

const TICKER = 'EQNR';

test.beforeEach(async ({ page }) => {
  // Hopp over onboarding-modal ved å sette flagget før siden lastes
  await page.addInitScript(() => {
    localStorage.setItem('velkommen_vist', '1');
  });
  await page.goto('/');
  // Vent til aksjedata er lastet og minst én aksje vises
  await page.waitForSelector('[data-ticker]', { timeout: 15_000 });
});

test.describe('Søk', () => {
  test('filtrerer aksjer etter ticker', async ({ page }) => {
    await page.fill('#sok', TICKER);
    await expect(page.locator(`[data-ticker="${TICKER}"]`).first()).toBeVisible();
    // Antall synlige rader skal være langt færre enn totalt
    const synlige = await page.locator('tr[data-ticker]').count();
    expect(synlige).toBeLessThanOrEqual(3);
  });

  test('nullstiller filter ved tømt søkefelt', async ({ page }) => {
    await page.fill('#sok', TICKER);
    const etter_sok = await page.locator('tr[data-ticker]').count();
    await page.fill('#sok', '');
    const etter_reset = await page.locator('tr[data-ticker]').count();
    expect(etter_reset).toBeGreaterThan(etter_sok);
  });
});

test.describe('Aksjemodal', () => {
  test('åpner modal ved klikk på aksje', async ({ page }) => {
    await page.fill('#sok', TICKER);
    await page.locator(`[data-ticker="${TICKER}"]`).first().click();
    await expect(page.locator('#modal-overlay')).toBeVisible();
    await expect(page.locator('#modal-aksje-tittel')).toContainText(TICKER);
  });

  test('lukker modal med Escape-tasten', async ({ page }) => {
    await page.fill('#sok', TICKER);
    await page.locator(`[data-ticker="${TICKER}"]`).first().click();
    await expect(page.locator('#modal-overlay')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#modal-overlay')).toBeHidden();
  });

  test('lukker modal ved klikk på lukk-knapp', async ({ page }) => {
    await page.fill('#sok', TICKER);
    await page.locator(`[data-ticker="${TICKER}"]`).first().click();
    await expect(page.locator('#modal-overlay')).toBeVisible();
    await page.locator('#modal-close').click();
    await expect(page.locator('#modal-overlay')).toBeHidden();
  });
});

test.describe('Portefølje', () => {
  test.beforeEach(async ({ page }) => {
    // Gå til Portefølje-fanen
    await page.click('button[data-tab="portfolio"]');
    await expect(page.locator('#pf-legg-til')).toBeVisible();
  });

  test('legger til aksje i portefølje', async ({ page }) => {
    await page.selectOption('#pf-velg-aksje', TICKER);
    await page.fill('#pf-antall', '10');
    await page.fill('#pf-kjoepskurs', '340.50');
    await page.click('#pf-legg-til');

    // Verifiser at aksjen er lagret i localStorage
    const beholdning = await page.evaluate(() => {
      const pfl = JSON.parse(localStorage.getItem('pf_portefoljer') || '{}');
      const aktivId = localStorage.getItem('pf_aktiv') || 'default';
      return pfl[aktivId]?.beholdning || {};
    });
    expect(beholdning[TICKER]).toBe(10);
  });

  test('viser feil ved manglende antall', async ({ page }) => {
    await page.selectOption('#pf-velg-aksje', TICKER);
    // Ikke fyll inn antall
    await page.click('#pf-legg-til');
    await expect(page.locator('#pf-feil')).toBeVisible();
  });

});

test.describe('Fullstendig flyt', () => {
  test('søk → modal → legg i portefølje', async ({ page }) => {
    // 1. Søk opp aksjen og verifiser at tabellrad vises
    await page.fill('#sok', TICKER);
    await expect(page.locator(`tr[data-ticker="${TICKER}"]`)).toBeVisible();

    // 2. Åpne modal og verifiser innhold
    await page.locator(`tr[data-ticker="${TICKER}"]`).click();
    await expect(page.locator('#modal-overlay')).toBeVisible();
    await expect(page.locator('#modal-aksje-tittel')).toContainText(TICKER);
    await page.locator('#modal-close').click();

    // 3. Gå til Portefølje-fanen og legg til
    await page.click('button[data-tab="portfolio"]');
    await page.selectOption('#pf-velg-aksje', TICKER);
    await page.fill('#pf-antall', '5');
    await page.click('#pf-legg-til');

    const beholdning = await page.evaluate(() => {
      const pfl = JSON.parse(localStorage.getItem('pf_portefoljer') || '{}');
      const aktivId = localStorage.getItem('pf_aktiv') || 'default';
      return pfl[aktivId]?.beholdning || {};
    });
    expect(beholdning[TICKER]).toBe(5);
  });
});
