// Process real photos for the 5 use-case cards — cohesive premium grade + AVIF
const sharp = require("/home/z/my-project/node_modules/sharp");
const DL = "/home/z/my-project/scripts/photo-search/dl";
const OUT = "/home/z/my-project/public";

const picks = [
  { src: "whatsapp-a32d4dae81ef.jpg", out: "zemest-card-whatsapp.avif" },
  { src: "instagram-31cbafb36dbe.jpg", out: "zemest-card-instagram.avif" },
  { src: "messenger-4bd30a863525.jpg", out: "zemest-card-messenger.avif" },
  { src: "inventory-71852aff342e.jpg", out: "zemest-card-inventory.avif" },
  { src: "arabic-bde012b1f86f.jpg", out: "zemest-card-rabbit.avif" },
];

(async () => {
  for (const p of picks) {
    // Cohesive editorial grade: slight desaturation + gentle contrast,
    // so 5 different photos read as one premium set.
    const graded = await sharp(`${DL}/${p.src}`)
      .resize(960, 720, { fit: "cover", position: "attention" })
      .modulate({ saturation: 0.82, brightness: 1.02 })
      .gamma(1.05)
      .toBuffer();

    // Fine film grain for the analog identity (subtle, not noisy)
    const { width, height } = await sharp(graded).metadata();
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

    await sharp(graded)
      .composite([{ input: noise, blend: "overlay" }])
      .avif({ quality: 55, effort: 5 })
      .toFile(`${OUT}/${p.out}`);

    const s = require("fs").statSync(`${OUT}/${p.out}`);
    console.log(p.out, Math.round(s.size / 1024) + "KB");
  }
})();
