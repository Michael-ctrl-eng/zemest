/**
 * Final hero asset generation — aggressive but visually-lossless compression.
 * The bg sits behind a 50% dark overlay + halftone grain overlay in the hero,
 * so q30 + 0.4px micro-smoothing is invisible. Windows are crisp (q45).
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const SRC = "/home/z/my-project/upload/file_00000000550c81f6acd969362980c3a6.png";
const OUT = "/home/z/my-project/public";
const kb = (n) => `${(n / 1024).toFixed(1)}KB`;

async function main() {
  // ---------- 1. Hero background ----------
  // median(2) removes stipple noise entropy, blur(0.5) smooths; behind 55% overlay
  // the result is visually lossless. q26 keeps the engraved cloud structure.
  const bgBuf = await sharp(SRC)
    .resize(1536)
    .median(2)
    .blur(0.5)
    .avif({ quality: 26, effort: 6 })
    .toBuffer();
  fs.writeFileSync(path.join(OUT, "zemest-hero-bg.avif"), bgBuf);
  console.log("zemest-hero-bg.avif         ", kb(bgBuf.length));

  // ---------- 2. LIVE window: 4:3 sky crop ----------
  const liveBuf = await sharp(SRC)
    .extract({ left: 256, top: 0, width: 1024, height: 768 })
    .resize(960)
    .avif({ quality: 36, effort: 6 })
    .toBuffer();
  fs.writeFileSync(path.join(OUT, "zemest-hero-window-live.avif"), liveBuf);
  console.log("zemest-hero-window-live.avif", kb(liveBuf.length));

  // ---------- 3. MEDIA window: 4:3 water crop ----------
  const mediaBuf = await sharp(SRC)
    .extract({ left: 256, top: 256, width: 1024, height: 768 })
    .resize(840)
    .avif({ quality: 32, effort: 6 })
    .toBuffer();
  fs.writeFileSync(path.join(OUT, "zemest-hero-window-media.avif"), mediaBuf);
  console.log("zemest-hero-window-media.avif", kb(mediaBuf.length));

  // ---------- 4. LQIP (24px blurred JPEG base64, <1KB) ----------
  const lqipBuf = await sharp(SRC).resize(24).blur(3).jpeg({ quality: 40 }).toBuffer();
  const lqip = `data:image/jpeg;base64,${lqipBuf.toString("base64")}`;
  fs.writeFileSync(path.join(OUT, "hero-lqip.txt"), lqip);
  console.log("hero-lqip (base64)          ", kb(lqip.length), "chars");

  // ---------- 5. Auth pages background (darker) ----------
  const authBuf = await sharp(SRC)
    .resize(1200)
    .median(2)
    .blur(0.5)
    .modulate({ brightness: 0.85 })
    .avif({ quality: 28, effort: 6 })
    .toBuffer();
  fs.writeFileSync(path.join(OUT, "zemest-auth-bg.avif"), authBuf);
  console.log("zemest-auth-bg.avif         ", kb(authBuf.length));

  console.log("\nTOTAL hero weight:", kb(bgBuf.length + liveBuf.length + mediaBuf.length));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
