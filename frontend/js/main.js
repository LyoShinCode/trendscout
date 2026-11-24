import { store } from './store.js';
import { applyRoute, currentView } from './router.js';
import { setSound, snd } from './sound.js';
import { toast } from './ui.js';
import { loadDashboard, renderDashboard } from './views/dashboard.js';
import { loadAlerts, renderAlerts } from './views/alerts.js';
import { loadArtists, renderArtists } from './views/artists.js';
import { renderDocs } from './views/docs.js';
import { renderHelp } from './views/help.js';
import { renderDemo, syncHud } from './views/demo.js';

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  store.set({ theme });
  try { localStorage.setItem('ts-theme', theme); } catch (e) { /* приватный режим */ }
  const b = document.getElementById('themeBtn');
  b.classList.toggle('on', theme === 'dark');
  b.innerHTML = theme === 'dark' ? '◑ <span>Тёмная</span>' : '◐ <span>Светлая</span>';
}

async function renderCurrent() {
  applyRoute();
  const v = currentView();
  try {
    if (v === 'dashboard') { await loadDashboard(); renderDashboard(); }
    else if (v === 'alerts') { await loadAlerts(); renderAlerts(); }
    else if (v === 'artists') { await loadArtists(); renderArtists(); }
    else if (v === 'help') { renderHelp(); }
    else if (v === 'demo') { await renderDemo(); }
    else if (v === 'docs') { await renderDocs(); }
  } catch (e) {
    console.error(e);
    const el = document.getElementById('view-' + v);
    if (el) {
      el.innerHTML = `<div class="empty">
        <p><strong>Не удалось загрузить данные.</strong></p>
        <p class="hint" style="margin-top:8px">${e.message}</p>
        <p class="hint" style="margin-top:8px">Проверьте, что бэкенд запущен:
        <code>uvicorn app.main:app --reload</code> из папки <code>backend</code>.</p>
      </div>`;
    }
    toast('Бэкенд недоступен', e.message, 'warn');
  }
  syncHud();
}

document.getElementById('themeBtn').onclick = () => {
  applyTheme(store.state.theme === 'dark' ? 'light' : 'dark');
  renderCurrent();
};

document.getElementById('soundBtn').onclick = () => {
  const on = !store.state.sound;
  store.set({ sound: on });
  setSound(on);
  const b = document.getElementById('soundBtn');
  b.classList.toggle('on', on);
  b.innerHTML = on ? '🔊 <span>Звук вкл</span>' : '🔈 <span>Звук выкл</span>';
  if (on) snd.ui();
};

applyTheme(store.state.theme);
setSound(false);
window.addEventListener('hashchange', renderCurrent);
renderCurrent();