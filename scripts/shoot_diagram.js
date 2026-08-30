// Screenshot the architecture diagram HTML at 2x device scale for print quality.
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1360, height: 780 },
    deviceScaleFactor: 2,
  });
  await page.goto('file://' + path.resolve(__dirname, 'assets/diagram.html'));
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.resolve(__dirname, 'assets/diagram.png'), fullPage: false });
  await browser.close();
  console.log('diagram.png rendered');
})();
