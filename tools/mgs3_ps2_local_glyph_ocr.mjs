#!/usr/bin/env node
// OCR images produced by mgs3_ps2_local_glyph_export.py using local data only.

import fs from 'node:fs/promises';
import path from 'node:path';
import tesseract from '../analysis/japanese_reassembly/ocr_node/node_modules/tesseract.js/src/index.js';

const { createWorker, PSM } = tesseract;

if (process.argv.length !== 4) {
  console.error('usage: node mgs3_ps2_local_glyph_ocr.mjs MANIFEST OUTPUT');
  process.exit(2);
}

const manifestPath = path.resolve(process.argv[2]);
const outputPath = path.resolve(process.argv[3]);
const manifest = JSON.parse(await fs.readFile(manifestPath, 'utf8'));
const root = path.dirname(manifestPath);
const modelRoot = path.resolve('analysis/japanese_reassembly/ocr_node');
const worker = await createWorker('kor', 1, {
  langPath: modelRoot,
  cachePath: modelRoot,
  gzip: false,
  workerPath: path.join(modelRoot, 'node_modules/tesseract.js/src/worker-script/node/index.js'),
  corePath: path.join(modelRoot, 'node_modules/tesseract.js-core'),
});
await worker.setParameters({
  tessedit_pageseg_mode: PSM.SINGLE_CHAR,
});

const rows = [];
for (let index = 0; index < manifest.glyphs.length; index += 1) {
  const glyph = manifest.glyphs[index];
  const result = await worker.recognize(path.join(root, glyph.image));
  rows.push({
    sha256: glyph.sha256,
    image: glyph.image,
    text: result.data.text.trim(),
    confidence: result.data.confidence,
    occurrence_count: glyph.occurrences.length,
    occurrences: glyph.occurrences,
  });
  if ((index + 1) % 50 === 0) console.error(`${index + 1}/${manifest.glyphs.length}`);
}
await worker.terminate();
await fs.writeFile(outputPath, JSON.stringify({ glyphs: rows }, null, 2), 'utf8');
