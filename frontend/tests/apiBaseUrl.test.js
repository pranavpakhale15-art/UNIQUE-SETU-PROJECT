import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { resolveApiBaseUrl } from '../src/api/apiBaseUrl.js';

test('production uses the same-origin API proxy even with a stale absolute setting', () => {
  assert.equal(
    resolveApiBaseUrl('https://unique-setu-project.onrender.com/api/v1', false),
    '/api/v1',
  );
});

test('development keeps its local API default and supports an explicit override', () => {
  assert.equal(resolveApiBaseUrl(undefined, true), 'http://127.0.0.1:8000/api/v1');
  assert.equal(resolveApiBaseUrl('http://localhost:8000/api', true), 'http://localhost:8000/api/v1');
});

test('Vercel proxies the production API base to the backend API path', async () => {
  const vercelConfig = JSON.parse(
    await readFile(new URL('../vercel.json', import.meta.url), 'utf8'),
  );
  assert.ok(vercelConfig.rewrites.some((rewrite) => (
    rewrite.source === '/api/:path*'
    && rewrite.destination === 'https://unique-setu-project.onrender.com/api/:path*'
  )));
});
