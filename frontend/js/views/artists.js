import { api } from '../api.js';
import { store } from '../store.js';
import { esc, fmt, HUES, openDrawer, sparkline } from '../ui.js';

export async function loadArtists() {
  const f = store.state.artistFilters;
  const p = { region: store.state.region, sort: f.sort };
  if (f.q) p.q = f.q;
  if (f.genre) p.genre = f.genre;
  store.set({ artists: await api.artists(p) });
}

export function renderArtists() {
  const s = store.state;
  const genres = [...new Set(s.artists.flatMap(a => a.genres))].sort();
  const el = document.getElementById('view-artists');
  el.innerHTML = `
  <div class="kicker">Artist · Track · ISRC · TrackPlatform</div>
  <h1>Артисты в <span class="g">мониторинге</span></h1>
  <p class="sub">Каталог с ISRC, доступность по платформам (основа FR-01/FR-05),
  наблюдаемая и истинная база, связанные алерты.</p>
  <div class="filters">
    <input type="text" id="artistSearch" placeholder="Поиск артиста…" value="${esc(s.artistFilters.q)}" style="min-width:210px">
    <select id="genreFilter"><option value="">Все жанры</option>
      ${genres.map(g => `<option ${s.artistFilters.genre === g ? 'selected' : ''}>${g}</option>`).join('')}</select>
    <select id="artistSort">
      <option value="plays">По прослушиваниям</option><option value="pos">По позиции</option>
      <option value="name">По имени</option><option value="debut">По дате дебюта</option></select>
  </div>
  <div class="artistsgrid">${s.artists.map((a, i) => `
    <div class="card acard" data-artist="${a.id}">
      <div style="display:flex;justify-content:space-between;gap:8px">
        <div><div class="nm">${esc(a.name)}</div><div class="agenre">${a.genres.join(' · ')}</div></div>
        <span class="pill">#${a.position}</span></div>
      <div class="mt">
        <span><b>${fmt(a.plays_week)}</b>нед / ${s.region}</span>
        <span><b>${fmt(a.total_observed)}</b>наблюдаемая</span>
        <span><b>${a.debut_months} мес</b>с дебюта</span></div>
      ${sparkline(a.spark, HUES[i % 8], 260, 44)}
    </div>`).join('') || '<div class="empty">Артисты не найдены.</div>'}</div>`;
  const refresh = async () => { await loadArtists(); renderArtists(); };
  const search = el.querySelector('#artistSearch');
  search.oninput = async e => {
    store.state.artistFilters.q = e.target.value; await refresh();
    const x = el.querySelector('#artistSearch'); x.focus(); x.setSelectionRange(x.value.length, x.value.length);
  };
  el.querySelector('#genreFilter').onchange = async e => { store.state.artistFilters.genre = e.target.value; await refresh(); };
  el.querySelector('#artistSort').onchange = async e => { store.state.artistFilters.sort = e.target.value; await refresh(); };
  el.querySelectorAll('[data-artist]').forEach(c => c.onclick = () => openArtist(c.dataset.artist));
}

async function openArtist(id) {
  const a = await api.artist(id, store.state.region);
  openDrawer(`
    <div class="kicker">Artist · ${a.genres.join(' / ')}</div>
    <h1 style="font-size:26px">${esc(a.name)}</h1>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <span class="pill">дебют ${a.debut_date}</span>
      <span class="pill">каталог ${a.catalog_months} мес</span>
      <span class="pill">истинная база ${fmt(a.true_total)}</span>
      <span class="pill">наблюдаемая ${fmt(a.total_observed)}</span></div>
    <div class="dsec"><h3>Каталог · ISRC (natural key)</h3>
      <table><thead><tr><th>ISRC</th><th>Трек</th><th>Релиз</th><th>BPM/Key</th></tr></thead>
      <tbody>${a.tracks.map(t => `<tr><td style="font-family:var(--mono);color:var(--cyan)">${t.isrc}</td>
        <td>${esc(t.title)}</td><td>${t.release_date}</td><td>${t.bpm ?? '—'} · ${t.key ?? '—'}</td></tr>`).join('')}</tbody></table></div>
    <div class="dsec"><h3>TrackPlatform · доступность каталога</h3>
      <div class="avail">${a.availability.map(x =>
        `<span class="${x.reset ? 'new' : ''}">${esc(x.platform)}: с ${x.available_since}${x.reset ? ' ⚠ счётчик сброшен' : ''}</span>`).join('')}</div>
      <p class="hint">available_since — измеримая основа FR-01 и guard-правила FR-05.</p></div>
    <div class="dsec"><h3>Связанные алерты</h3>
      ${a.alert_ids.map(x => `<div class="preview-alert" data-go="#/alerts"><b>${x}</b></div>`).join('')
        || '<div class="empty">Алертов нет.</div>'}</div>`);
  document.querySelectorAll('#drawer [data-go]').forEach(b => b.onclick = () => {
    document.getElementById('drawerWrap').classList.remove('on');
    document.body.style.overflow = '';
    location.hash = b.dataset.go;
  });
}