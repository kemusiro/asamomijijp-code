// SPDX-License-Identifier: MIT
// Optional verification runtime;never bundled with the physical firmware.
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
export async function loadMicroPython(options) {
  const supplied = process.env.MICROPYTHON_WASM_MODULE;
  if (!supplied) throw new Error('Set MICROPYTHON_WASM_MODULE to the pinned external micropython.mjs;see README.md');
  const url = pathToFileURL(resolve(supplied));
  const lock = JSON.parse(await readFile(new URL('./micropython-wasm-lock.json',import.meta.url),'utf8'));
  for (const [name,expected] of Object.entries(lock.sha256)) {
    const bytes = await readFile(new URL(name,url));
    if (createHash('sha256').update(bytes).digest('hex') !== expected) throw new Error('MicroPython verification runtime hash mismatch: '+name);
  }
  const runtime = await import(url.href);
  return runtime.loadMicroPython(options);
}
