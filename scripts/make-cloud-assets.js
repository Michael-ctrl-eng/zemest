// Process the bluish-white cloud/sea photo into AVIF assets for footer + CTA
const sharp = require("/home/z/my-project/node_modules/sharp");
const SRC = "/home/z/my-project/scripts/photo-search/dl/cloud-2127cfa8c57f.jpg";
const OUT = "/home/z/my-project/public";

(async () => {
  const img = sharp(SRC);
  const meta = await img.metadata();
  console.log("src:", meta.width, "x", meta.height);

  // --- Footer: wide panorama, full-bleed band (clouds fill the frame) ---
  // Take the sky-heavy upper portion, wide crop, then extend to 21:9-ish band
  await sharp(SRC)
    .extract({
      left: 0,
      top: Math.floor(meta.height * 0.05),
      width: meta.width,
      height: Math.floor(meta.height * 0.75),
    })
    .resize(1920, 640, { fit: "cover", position: "attention" })
    .avif({ quality: 42, effort: 5 })
    .toFile(`${OUT}/zemest-cloud-sea-footer.avif`);
  console.log("footer band done");

  // --- CTA background: full 16:9 scene ---
  await sharp(SRC)
    .resize(1920, 1080, { fit: "cover", position: "attention" })
    .avif({ quality: 40, effort: 5 })
    .toFile(`${OUT}/zemest-cloud-sea-cta.avif`);
  console.log("cta bg done");

  for (const f of ["zemest-cloud-sea-footer.avif", "zemest-cloud-sea-cta.avif"]) {
    const s = require("fs").statSync(`${OUT}/${f}`);
    console.log(f, Math.round(s.size / 1024) + "KB");
  }
})();
