import { test, expect } from '@playwright/test';

// Simple network mock for the detect API
async function mockDetectRoute(page) {
  await page.route('**/api/form/detect**', async route => {
    const json = {
      image: { width: 800, height: 1000 },
      normalized_scale: 1000,
      boxes: [
        { box_2d: [200, 150, 240, 450] },
        { box_2d: [300, 150, 340, 550] }
      ],
      texts: ['John Doe', 'x'],
      timings_ms: { total_ms: 1234 }
    };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(json)
    });
  });
}

// Helper to ensure the page is loaded and canvas is available
async function getCanvasObjectCount(page) {
  return await page.evaluate(() => window.canvas.getObjects().length);
}

// Tests

test.describe('Fill My Paperwork UI (mocked backend)', () => {
  test.beforeEach(async ({ page }) => {
    await mockDetectRoute(page);
  });

  test('loads and adds text with current UI font params', async ({ page }) => {
    await page.goto('/index.html');
    // Ensure initial main canvas is visible
    await expect(page.locator('#c')).toBeVisible();

    const before = await getCanvasObjectCount(page);
    await page.getByText('Add Text').click();
    const after = await getCanvasObjectCount(page);
    expect(after).toBeGreaterThan(before);

    // Change font params and add again
    await page.locator('#fontSelect').selectOption({ label: 'Typed' });
    await page.fill('#fontSize', '22');
    await page.locator('#colorSelect').selectOption('#D32F2F');
    await page.getByText('Add Text').click();
    const after2 = await getCanvasObjectCount(page);
    expect(after2).toBeGreaterThan(after);
  });

  test('detect fields places overlays and text (mocked)', async ({ page }) => {
    await page.goto('/index.html');

    // Load a sample image by setting PRELOAD_URL to an inline image; then reload
    await page.addInitScript(() => {
      // tiny 1x1 transparent PNG
      (window as any).PRELOAD_URL = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMB/edQxGUAAAAASUVORK5CYII=';
    });
    await page.reload();

    // Click detect and wait for status
    await page.getByText('Detect Fields').click();
    await expect(page.getByText(/Done in/)).toBeVisible();

    // Should have added text objects
    const count = await getCanvasObjectCount(page);
    expect(count).toBeGreaterThan(0);
  });

  test('prev/next arrows disabled for single-page', async ({ page }) => {
    await page.goto('/index.html');
    const prev = page.locator('#prevBtn');
    const next = page.locator('#nextBtn');
    await expect(prev).toBeDisabled();
    await expect(next).toBeDisabled();
  });
});