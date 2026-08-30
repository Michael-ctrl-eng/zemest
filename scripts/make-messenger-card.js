// Messenger card from the user's uploaded wireframe-hands jpg (B&W, 600x390).
// NO cropping: the source's hands span the full width, so a 4:3 cover-crop
// would clip their fingertips. Instead: scale to 960x624 (full frame kept) and
// extend 96px at the TOP with the source's own flat top-gray (118) — a
// guaranteed seamless band (top rows of the source are uniformly 118).
// Then the shared card treatment: gentle grade + 6% film grain + AVIF q55.
const sharp = require("/home/z/my-project/node_modules/sharp");
const SRC = "/home/z/my-project/upload/1000015353.jpg";
const OUT = "/home/z/my-project/public/zemest-card-messenger.avif";

(async () => {
  // 1) full frame, aspect preserved
  const base = await sharp(SRC)
    .toColourspace("srgb") // src is 1-channel b-w -> 3-channel
    .resize(960, 624, { fit: "fill" }) // 600x390 == 960x624 exactly (same ratio) — pure scale
    .linear(1.04, -5) // gentle contrast lift
    .toBuffer();

  // 2) seamless top extension: 96px of the source's flat top gray
  const extended = await sharp(base)
    .extend({ top: 96, bottom: 0, left: 0, right: 0, background: { r: 118, g: 118, b: 118 } })
    .toBuffer();

  // 3) shared film-grain treatment (matches the other card photos)
  const { width, height } = await sharp(extended).metadata();
  const noise = await sharp({
    create: { width, height, channels: 3, background: { r: 128, g: 128, b: 128 } },
  })
    .composite([
      {
        input: Buffer.from(
          `<svg width="${width}" height="${height}"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter><rect width="100%" height="100%" filter="url(#n)" opacity="0.06"/></svg>`
        ),
      },
    ])
    .png()
    .toBuffer();

  await sharp(extended)
    .composite([{ input: noise, blend: "overlay" }])
    .avif({ quality: 55, effort: 5 })
    .toFile(OUT);

  const s = require("fs").statSync(OUT);
  console.log(OUT, Math.round(s.size / 1024) + "KB");
})();
