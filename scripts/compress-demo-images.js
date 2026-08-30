/**
 * Compress fetched demo product images -> public/demo-products/*.jpg
 * Target: 640px square-ish, q72 JPEG, ~30-50KB each (fast chat image loading).
 */
const sharp = require("sharp");
const fs = require("fs");
const path = require("path");

const MAP = {
  "nike-white": "nike-white-air.jpg",
  "nike-black": "nike-black-runner.jpg",
  "sneakers-red": "adidas-red.jpg",
  "tshirt-white": "tshirt-white.jpg",
  "hoodie-black": "hoodie-black.jpg",
  "perfume-oud": "perfume-oud.jpg",
  "perfume-floral": "perfume-floral.jpg",
  shampoo: "shampoo-argan.jpg",
  "face-cream": "face-cream.jpg",
  "bag-leather": "bag-leather.jpg",
  watch: "watch-black.jpg",
  earbuds: "earbuds.jpg",
  "phone-case": "phone-case.jpg",
  sunglasses: "sunglasses.jpg",
  dress: "dress-floral.jpg",
};

const OUT = "/home/z/my-project/public/demo-products";
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  let total = 0;
  for (const [src, dst] of Object.entries(MAP)) {
    const inPath = `/tmp/demo-img/${src}.img`;
    if (!fs.existsSync(inPath)) {
      console.log(`MISSING ${src}`);
      continue;
    }
    const buf = await sharp(inPath)
      .resize(640, 640, { fit: "cover", position: "centre" })
      .jpeg({ quality: 72, mozjpeg: true })
      .toBuffer();
    fs.writeFileSync(path.join(OUT, dst), buf);
    total += buf.length;
    console.log(`${dst.padEnd(24)} ${(buf.length / 1024).toFixed(0)}KB`);
  }
  console.log(`\nTOTAL: ${(total / 1024).toFixed(0)}KB for 15 products`);
})();
