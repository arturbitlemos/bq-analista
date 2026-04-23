import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import archiver from 'archiver';
import { createRequire } from 'node:module';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const pkgRoot = path.resolve(__dirname, '..');

const require = createRequire(import.meta.url);
const pkg = require(path.join(pkgRoot, 'package.json'));
const version = pkg.version;

const outFile = path.join(pkgRoot, `azzas-mcp-${version}.dxt`);
const output = fs.createWriteStream(outFile);
const archive = archiver('zip', { zlib: { level: 9 } });

output.on('close', () => {
  const sizeKb = (archive.pointer() / 1024).toFixed(1);
  console.log(`✔ Built ${path.basename(outFile)} (${sizeKb} KB)`);
});
archive.on('error', (err) => { throw err; });

archive.pipe(output);
archive.file(path.join(pkgRoot, 'manifest.json'), { name: 'manifest.json' });
archive.file(path.join(pkgRoot, 'icon.png'), { name: 'icon.png' });
archive.file(path.join(pkgRoot, 'dist', 'index.js'), { name: 'dist/index.js' });
await archive.finalize();
