const listeners = new Set();

export const store = {
  state: {
    view: 'dashboard',
    meta: null, config: null,
    region: 'KRD', platform: 'all',
    dashboard: null, series: null,
    logFilter: 'all',
    alerts: [],
    alertFilters: { q: '', type: '', status: '', sort: 'date', revised: '' },
    selected: new Set(),
    artists: [],
    artistFilters: { q: '', genre: '', sort: 'plays' },
    sound: false,
    theme: document.documentElement.dataset.theme || 'light',
    demo: { running: false, elapsed: 0, done: {}, results: {} },
  },
  set(patch) {
    Object.assign(this.state, patch);
    listeners.forEach(fn => fn(this.state));
  },
  subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
};