// Общие примитивы интерфейса: форматирование, метки, спарклайны, тосты, drawer.
export const fmt = n => Math.round(n).toLocaleString('ru-RU');

// Восемь различимых оттенков графиков (совпадают с --c1…--c8).
export const HUES = ['#12494F', '#1F5FD0', '#A96A05', '#6B3FA0', '#2F7A45', '#B3261E', '#4E6E8E', '#8A6A3B'];
export const HUES_DARK = ['#7FB8BC', '#7FA9F0', '#D9A44E', '#B49AD8', '#7DBE8C', '#E08A82', '#93AEC7', '#C0A277'];

export const isDark = () => document.documentElement.dataset.theme === 'dark';
export const palette = () => (isDark() ? HUES_DARK : HUES);
export const cssVar = name =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

export const STATUS_RU = {
  NEW: 'Новый', IN_REVIEW: 'На проверке', CONFIRMED: 'Подтверждён', REJECTED: 'Отклонён',
};

export const esc = s => String(s ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export const badge = (kind, text) => `<span class="badge b-${esc(kind)}">${esc(text ?? kind)}</span>`;

export function sparkline(series, color, w = 132, h = 32) {
  if (!series || series.length < 2) return '';
  const max = Math.max(...series), min = Math.min(...series);
  const span = max - min || 1;
  const x = i => (i / (series.length - 1)) * (w - 4) + 2;
  const y = v => h - 4 - ((v - min) / span) * (h - 8);
  const pts = series.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
  const last = series[series.length - 1];
  return `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">
    <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.75"
      stroke-linejoin="round" stroke-linecap="round"/>
    <circle cx="${x(series.length - 1).toFixed(1)}" cy="${y(last).toFixed(1)}" r="2.5" fill="${color}"/>
  </svg>`;
}

let seq = 0;
const actions = new Map();

export function toast(title, msg, kind = '', action = null) {
  const id = 't' + (++seq);
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.id = id;
  el.innerHTML = `<b>${esc(title)}</b><span>${esc(msg)}</span>` +
    (action ? `<div class="tact"><button class="btn sm" data-toast="${id}">${esc(action.label)}</button></div>` : '');
  if (action) actions.set(id, action.fn);
  document.getElementById('toasts').appendChild(el);
  setTimeout(() => {
    el.classList.add('out');
    setTimeout(() => el.remove(), 300);
  }, action ? 8000 : 4500);
}

document.addEventListener('click', e => {
  const b = e.target.closest('[data-toast]');
  if (!b) return;
  const fn = actions.get(b.dataset.toast);
  if (fn) fn();
  document.getElementById(b.dataset.toast)?.remove();
});

export function openDrawer(html) {
  document.getElementById('drawerBody').innerHTML = html;
  document.getElementById('drawerWrap').classList.add('on');
  document.body.style.overflow = 'hidden';
}

export function closeDrawer() {
  document.getElementById('drawerWrap').classList.remove('on');
  document.body.style.overflow = '';
}

document.getElementById('drawerBack').addEventListener('click', closeDrawer);
document.getElementById('drawerClose').addEventListener('click', closeDrawer);
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });