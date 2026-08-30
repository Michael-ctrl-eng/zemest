// Post-process Zemest identity images → crisp, small AVIFs.
// Slight contrast/saturation lift keeps the halftone print crisp after AVIF compression.
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const RAW = "/home/z/my-project/identity-raw";
const OUT = "/home/z/my-project/public";

const jobs = [
  { in: "hero-agent.png", out: "zemest-hero-agent.avif", width: 960, q: 55 },
  { in: "usecase-whatsapp.png", out: "zemest-usecase-whatsapp.avif", width: 840, q: 52 },
  { in: "usecase-instagram.png", out: "zemest-usecase-instagram.avif", width: 840, q: 52 },
  { in: "usecase-messenger.png", out: "zemest-usecase-messenger.avif", width: 840, q: 52 },
  { in: "usecase-inventory.png", out: "zemest-usecase-inventory.avif", width: 840, q: 52 },
  { in: "usecase-rabbit.png", out: "zemest-usecase-rabbit.avif", width: 840, q: 52 },
  { in: "footer-cloud.png", out: "zemest-footer-cloud.avif", width: 1344, q: 58 },
];

(async () => {
  for (const j of jobs) {
    const src = path.join(RAW, j.in);
    const dst = path.join(OUT, j.out);
    const buf = await sharp(src)
      .resize({ width: j.width, withoutEnlargement: true })
      .modulate({ saturation: 1.06 })
      .linear(1.06, -8) // gentle contrast lift, keeps halftone dots punchy
      .avif({ quality: j.q, effort: 5 })
      .toBuffer();
    fs.writeFileSync(dst, buf);
    console.log(`${j.out}: ${(buf.length / 1024).toFixed(0)}KB  (from ${(fs.statSync(src).size / 1024).toFixed(0)}KB)`);
  }
})();
