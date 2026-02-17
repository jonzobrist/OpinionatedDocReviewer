import process from 'node:process';
import { chromium } from 'playwright';

const baseUrl = process.env.SMOKE_BASE_URL || 'http://127.0.0.1:3000';

function assertVisible(value, message) {
  if (!value) {
    throw new Error(message);
  }
}

async function expectHeading(page, text) {
  const locator = page.getByText(text, { exact: false }).first();
  await locator.waitFor({ state: 'visible', timeout: 10000 });
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error)));
  const topNav = page.locator('.top-actions');

  try {
    await page.goto(`${baseUrl}/`, { waitUntil: 'networkidle', timeout: 30000 });
    await expectHeading(page, 'Drop files to start a review');

    await topNav.getByRole('button', { name: 'Library', exact: true }).click();
    await expectHeading(page, 'Review Ledger');

    await topNav.getByRole('button', { name: 'Agents', exact: true }).click();
    await expectHeading(page, 'Agent Studio');

    await topNav.getByRole('button', { name: 'History', exact: true }).click();
    await expectHeading(page, 'Review Runs');
    await expectHeading(page, 'Document Commits');

    await topNav.getByRole('button', { name: 'System', exact: true }).click();
    await expectHeading(page, 'System Configuration');

    await topNav.getByRole('button', { name: 'Admin', exact: true }).click();
    await expectHeading(page, 'Administrator');

    assertVisible(pageErrors.length === 0, `Unexpected page errors:\n${pageErrors.join('\n')}`);
    // eslint-disable-next-line no-console
    console.log('Smoke nav checks passed.');
  } finally {
    await browser.close();
  }
}

run().catch((error) => {
  // eslint-disable-next-line no-console
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
});
