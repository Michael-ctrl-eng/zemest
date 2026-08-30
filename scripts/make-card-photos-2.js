// Regenerate whatsapp + rabbit cards from clean sources
const sharp = require("/home/z/my-project/node_modules/sharp");
const DL = "/home/z/my-project/scripts/photo-search/dl";
const OUT = "/home/z/my-project/public";

const picks = [
  { src: "chat-3b92627ae09b.jpg", out: "zemest-card-whatsapp.avif", sat: 0.98, bri: 1.06, gam: 1.0 },
  { src: "cairo-7ea561c25c82.jpg", out: "zemest-card-rabbit.avif", sat: 0.82, bri: 1.02, gam: 1.05 },
];

(async () => {
  for (const p of picks) {
    const graded = await sharp(`${DL}/${p.src}`)
      .resize(960, 720, { fit: "cover", position: "attention" })
      .modulate({ saturation: p.sat, brightness: p.bri })
      .gamma(p.gam)
      .toBuffer();

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
