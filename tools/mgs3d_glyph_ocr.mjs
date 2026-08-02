#!/usr/bin/env node
// Generate review-only Japanese OCR candidates for hash-addressed glyph tiles.

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

// Resolve the review-only dependency from the caller's isolated working dir.
const require = createRequire(path.join(process.cwd(), "package.json"));
const { createWorker, PSM } = require("tesseract.js");

const [catalogPath, tilesPath, outputPath, limitText] = process.argv.slice(2);
if (!catalogPath || !tilesPath || !outputPath) {
  console.error("usage: node mgs3d_glyph_ocr.mjs CATALOG TILES OUTPUT [LIMIT]");
  process.exit(2);
}
const catalog = JSON.parse(fs.readFileSync(catalogPath, "utf8"));
if (catalog.format !== "mgs3d-referenced-glyph-catalog-v1") {
  throw new Error("unsupported glyph catalog");
}
const limit = limitText ? Number(limitText) : catalog.glyphs.length;
const worker = await createWorker("jpn");
await worker.setParameters({
  tessedit_pageseg_mode: PSM.SINGLE_CHAR,
  preserve_interword_spaces: "1",
});
const rows = [];
try {
  for (const item of catalog.glyphs.slice(0, limit)) {
    const filename = `${String(item.sheet_index).padStart(4, "0")}_${item.glyph_sha256}.png`;
    const result = await worker.recognize(path.join(tilesPath, filename));
    const text = result.data.text.replace(/\s+/gu, "").normalize("NFC");
    rows.push({
      glyph_sha256: item.glyph_sha256,
      sheet_index: item.sheet_index,
      occurrences: item.occurrences,
      candidate: [...text][0] || "",
      raw_ocr: text,
      confidence: result.data.confidence,
      disposition: "unresolved-needs-review",
    });
    if (rows.length % 100 === 0) console.error(`OCR ${rows.length}/${limit}`);
  }
} finally {
  await worker.terminate();
}
const document = {
  format: "mgs3d-glyph-ocr-candidates-v1",
  catalog: catalogPath,
  language: "jpn",
  page_segmentation: "single-character",
  note: "OCR output is review evidence only and is never auto-approved.",
  rows,
};
fs.writeFileSync(outputPath, `${JSON.stringify(document, null, 2)}\n`, "utf8");
