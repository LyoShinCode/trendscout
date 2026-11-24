import { store } from './store.js';

const VIEWS = ['dashboard', 'alerts', 'artists', 'help', 'demo', 'docs'];

export function currentView() {
  const v = (location.hash.replace('#/', '') || 'dashboard').split('/')[0];
  return VIEWS.includes(v) ? v : 'dashboard';
}

export function applyRoute() {
  const v = currentView();
  store.set({ view: v });
  document.body.dataset.view = v;
  document.querySelectorAll('.view').forEach(el => el.classList.toggle('on', el.id === 'view-' + v));
  document.querySelectorAll('#navLinks a[data-view]').forEach(a => {
    a.classList.toggle('on', a.dataset.view === v);
  });
  window.scrollTo({ top: 0 });
}