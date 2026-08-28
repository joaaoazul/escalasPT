/**
 * Fails the build if anything in dist/ points at an external origin.
 *
 * The app runs inside a tailnet, offline, under `default-src 'self'`. A stray
 * Google Fonts link or CDN script does not throw at build time and does not log
 * an obvious error at runtime — the page just silently loses its typeface or a
 * feature. This turns that into a build failure.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const DIST = 'dist';
const FORBIDDEN = [
  'fonts.googleapis.com',
  'fonts.gstatic.com',
  'cdn.jsdelivr.net',
  'cdnjs.cloudflare.com',
  'unpkg.com',
  'googletagmanager.com',
];
const TEXT_EXTENSIONS = ['.html', '.js', '.css', '.json', '.webmanifest'];

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) yield* walk(path);
    else yield path;
  }
}

const offences = [];
for (const file of walk(DIST)) {
  if (!TEXT_EXTENSIONS.some((ext) => file.endsWith(ext))) continue;
  const contents = readFileSync(file, 'utf8');
  for (const needle of FORBIDDEN) {
    if (contents.includes(needle)) offences.push(`${file} → ${needle}`);
  }
}

if (offences.length > 0) {
  console.error('\nBuild rejected — dist/ references external origins:');
  for (const offence of offences) console.error(`  ${offence}`);
  console.error(
    '\nThis app must ship every asset it uses (docs/PLANO.md §3.2).\n',
  );
  process.exit(1);
}

console.log('check:offline — no external origins in dist/');
