import assert from 'node:assert/strict';
import test from 'node:test';
import constants from 'next/constants.js';
import config from '../next.config.mjs';

test('a production build cannot overwrite a running dev server cache', () => {
  const dev = config(constants.PHASE_DEVELOPMENT_SERVER);
  const build = config(constants.PHASE_PRODUCTION_BUILD);
  const start = config(constants.PHASE_PRODUCTION_SERVER);
  assert.equal(dev.distDir, '.next-dev');
  assert.notEqual(dev.distDir, build.distDir);
  assert.equal(build.distDir, start.distDir);
  assert.equal(start.distDir, '.next');
});
