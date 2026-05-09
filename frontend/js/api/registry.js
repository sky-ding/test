import { resolveApiBase } from '../config.js';

let cachedBase = '';

export function refreshPmApiBase() {
  cachedBase = resolveApiBase().replace(/\/$/, '');
  return cachedBase;
}

export function getPmApiBase() {
  if (!cachedBase) refreshPmApiBase();
  return cachedBase;
}

export function pmApiUrl(path) {
  const base = getPmApiBase();
  return base + (path.indexOf('/') === 0 ? path : '/' + path);
}

export function pmFetch(path, options) {
  const opts = options || {};
  const h = Object.assign({}, opts.headers || {});
  if (opts.body && typeof opts.body === 'string' && !h['Content-Type']) {
    h['Content-Type'] = 'application/json';
  }
  return fetch(pmApiUrl(path), Object.assign({}, opts, { credentials: 'include', headers: h }));
}
