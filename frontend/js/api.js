const BASE = '/api/v1';

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const d = err.detail;
    const e = new Error(typeof d === 'object' ? d.message : (d || res.statusText));
    e.status = res.status;
    throw e;
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  meta: () => request('/meta'),
  config: () => request('/config'),
  setConfig: (body) => request('/config', { method: 'PUT', body }),
  dashboard: (region) => request(`/dashboard?region=${region}`),
  chart: (region, platform = 'all') => request(`/charts/${region}?platform=${platform}`),
  series: (region) => request(`/charts/${region}/series`),
  artists: (p) => request('/artists?' + new URLSearchParams(p)),
  artist: (id, region) => request(`/artists/${id}?region=${region}`),
  alerts: (p) => request('/alerts?' + new URLSearchParams(p)),
  alert: (id) => request(`/alerts/${id}`),
  patchAlert: (id, status, reason) => request(`/alerts/${id}`, { method: 'PATCH', body: { status, reason } }),
  deleteAlert: (id) => request(`/alerts/${id}`, { method: 'DELETE' }),
  media: () => request('/media-events'),
  runDetection: () => request('/detection/run', { method: 'POST', body: {} }),
  week: () => request('/simulation/week', { method: 'POST', body: {} }),
  lag: () => request('/simulation/scenario/lag', { method: 'POST', body: {} }),
  rights: () => request('/simulation/scenario/rights', { method: 'POST', body: {} }),
  reset: () => request('/simulation/reset', { method: 'POST', body: {} }),
  log: () => request('/log'),
  doc: (file) => fetch('/sa-docs/' + file).then(r => r.text()),
};