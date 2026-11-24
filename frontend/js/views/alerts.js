import { api } from '../api.js';
import { store } from '../store.js';
import { snd } from '../sound.js';
import { badge, esc, openDrawer, STATUS_RU, toast } from '../ui.js';

export async function loadAlerts() {
  const f = store.state.alertFilters;
  const p = { sort: f.sort };
  if (f.q) p.q = f.q;
  if (f.type) p.type = f.type;
  if (f.status) p.status = f.status;
  if (f.revised) p.revised = f.revised;
  store.set({ alerts: await api.alerts(p) });
}

export function renderAlerts() {
  const s = store.state;
  const el = document.getElementById('view-alerts');
  el.innerHTML = `
  <div class="kicker">BreakthroughAlert · NEW → IN_REVIEW → CONFIRMED / REJECTED</div>
  <h1>Алерты <span class="g">прорывов</span></h1>
  <p class="sub">Каждый алерт хранит правило, confidence, provisional-флаг и audit trail.
  Переходы статусов валидируются сервером (409 при недопустимом).</p>
  <div class="filters">
    <input type="text" id="alertSearch" placeholder="Поиск: артист, регион, id…" value="${esc(s.alertFilters.q)}" style="min-width:210px">
    ${['', 'SLEEPER', 'NEWCOMER', 'VIRAL'].map(t =>
      `<button class="chip ${s.alertFilters.type === t ? 'on' : ''}" data-type="${t}">${t || 'Все типы'}</button>`).join('')}
    <select id="alertStatus"><option value="">Любой статус</option>
      ${Object.keys(STATUS_RU).map(k => `<option ${s.alertFilters.status === k ? 'selected' : ''}>${k}</option>`).join('')}</select>
    <select id="alertSort">
      <option value="date" ${s.alertFilters.sort === 'date' ? 'selected' : ''}>Сначала новые</option>
      <option value="conf" ${s.alertFilters.sort === 'conf' ? 'selected' : ''}>По confidence</option>
      <option value="name" ${s.alertFilters.sort === 'name' ? 'selected' : ''}>По артисту</option></select>
  </div>
  <div class="filters" style="margin-top:0">
    <span class="pill">Представления:</span>
    <button class="chip" data-saved="new">🔵 Новые</button>
    <button class="chip" data-saved="viralreview">🎬 VIRAL на ревью</button>
    <button class="chip" data-saved="revoked">⚠ Отозванные (FR-04)</button>
    <button class="chip" data-saved="all">✕ Сбросить</button>
  </div>
  <div class="bulkbar ${s.selected.size ? 'on' : ''}">
    <b>${s.selected.size} выбрано</b>
    <button class="btn sm ok" data-bulk="CONFIRMED">✓ Подтвердить</button>
    <button class="btn sm danger" data-bulk="REJECTED">✕ Отклонить</button>
    <button class="btn sm" data-bulk="clear">Снять выбор</button>
  </div>
  <div>${s.alerts.map(a => `
    <div class="alertrow ${s.selected.has(a.id) ? 'sel' : ''}" data-alert="${a.id}">
      <input type="checkbox" data-check="${a.id}" ${s.selected.has(a.id) ? 'checked' : ''}>
      ${badge(a.type)}
      <div><b>${esc(a.artist_name)}</b>
        ${a.provisional ? badge('prov', 'provisional') : ''} ${a.revised ? badge('prov', 'пересмотрен') : ''}
        <div class="agenre">${a.id} · ${a.rule_id} · нед ${a.week}</div></div>
      <div><span class="pill">${a.region_code} · #${a.position}</span></div>
      <div><div class="conf"><i style="width:${Math.round(a.confidence * 100)}%"></i></div>
        <span class="confv">confidence ${a.confidence.toFixed(2)}</span></div>
      <div>${badge(a.status, STATUS_RU[a.status])}</div>
    </div>`).join('') || '<div class="empty">Ничего не найдено.</div>'}</div>`;
  bind();
}

function bind() {
  const el = document.getElementById('view-alerts');
  const refresh = async () => { await loadAlerts(); renderAlerts(); };
  const search = el.querySelector('#alertSearch');
  search.oninput = async e => {
    store.state.alertFilters.q = e.target.value;
    await refresh();
    const s = el.querySelector('#alertSearch'); s.focus(); s.setSelectionRange(s.value.length, s.value.length);
  };
  el.querySelector('#alertStatus').onchange = async e => { store.state.alertFilters.status = e.target.value; await refresh(); };
  el.querySelector('#alertSort').onchange = async e => { store.state.alertFilters.sort = e.target.value; await refresh(); };
  el.querySelectorAll('[data-type]').forEach(b => b.onclick = async () => {
    store.state.alertFilters.type = b.dataset.type; store.state.alertFilters.revised = ''; await refresh();
  });
  el.querySelectorAll('[data-saved]').forEach(b => b.onclick = async () => {
    const m = b.dataset.saved;
    store.state.alertFilters = m === 'new' ? { q: '', type: '', status: 'NEW', sort: 'date', revised: '' }
      : m === 'viralreview' ? { q: '', type: 'VIRAL', status: 'IN_REVIEW', sort: 'date', revised: '' }
      : m === 'revoked' ? { q: '', type: '', status: '', sort: 'date', revised: 'true' }
      : { q: '', type: '', status: '', sort: 'date', revised: '' };
    await refresh();
  });
  el.querySelectorAll('[data-check]').forEach(c => c.onclick = e => {
    e.stopPropagation();
    c.checked ? store.state.selected.add(c.dataset.check) : store.state.selected.delete(c.dataset.check);
    renderAlerts();
  });
  el.querySelectorAll('[data-alert]').forEach(r => r.onclick = () => openAlert(r.dataset.alert));
  el.querySelectorAll('[data-bulk]').forEach(b => b.onclick = async () => {
    const t = b.dataset.bulk;
    if (t === 'clear') { store.state.selected.clear(); renderAlerts(); return; }
    let n = 0;
    for (const id of [...store.state.selected]) {
      const al = store.state.alerts.find(x => x.id === id);
      if (al && (al.status === 'NEW' || al.status === 'IN_REVIEW')) {
        try { await api.patchAlert(id, t); n++; } catch (e) { /* 409 пропускаем */ }
      }
    }
    store.state.selected.clear(); await refresh();
    toast('Bulk-операция', `${n} алерт(ов) → ${STATUS_RU[t]}.`, 'ok');
  });
}

async function openAlert(id) {
  const a = await api.alert(id);
  snd.ui();
  const acts = {
    NEW: [['IN_REVIEW', '👁 Взять в работу', 'pri'], ['REJECTED', '✕ Отклонить', 'danger']],
    IN_REVIEW: [['CONFIRMED', '✓ Подтвердить', 'ok'], ['REJECTED', '✕ Отклонить', 'danger']],
    CONFIRMED: [['IN_REVIEW', '↩ Переоткрыть', '']],
    REJECTED: [['NEW', '↩ Восстановить', '']],
  }[a.status];
  openDrawer(`
    <div class="kicker">${a.id} · правило ${a.rule_id}</div>
    <h1 style="font-size:24px">${esc(a.artist_name)}</h1>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin:8px 0">
      ${badge(a.type)}${badge(a.status, STATUS_RU[a.status])}
      ${a.provisional ? badge('prov', 'provisional · FR-04') : ''}${a.revised ? badge('prov', 'пересмотрен') : ''}
      <span class="pill">${a.region_code} · #${a.position} · нед ${a.week}</span></div>
    <div class="dsec"><h3>Confidence</h3>
      <div class="conf" style="height:9px"><i style="width:${Math.round(a.confidence * 100)}%"></i></div>
      <span class="confv">${a.confidence.toFixed(2)} = базовая × полнота данных × маржа позиции</span></div>
    <div class="dsec"><h3>Audit trail</h3>
      ${a.notes.map(n => `<div class="note"><b>нед ${n.week}:</b> ${esc(n.text)}</div>`).join('')}</div>
    <div class="dsec"><h3>Действия A&R-менеджера</h3>
      <div style="display:flex;gap:9px;flex-wrap:wrap">
        ${acts.map(([s, l, c]) => `<button class="btn ${c}" data-status="${s}">${l}</button>`).join('')}
        <button class="btn danger" data-del="1">🗑 Удалить</button></div></div>`);
  document.querySelectorAll('#drawer [data-status]').forEach(b => b.onclick = async () => {
    try {
      await api.patchAlert(a.id, b.dataset.status);
      snd.ui(); await loadAlerts(); renderAlerts(); await openAlert(a.id);
      if (b.dataset.status === 'REJECTED') {
        toast('Отклонён', a.id, 'warn', { label: 'Отменить', fn: async () => {
          await api.patchAlert(a.id, 'NEW'); await loadAlerts(); renderAlerts(); } });
      }
    } catch (e) { toast('409 · недопустимый переход', e.message, 'warn'); }
  });
  document.querySelector('#drawer [data-del]').onclick = async () => {
    await api.deleteAlert(a.id);
    document.getElementById('drawerWrap').classList.remove('on');
    document.body.style.overflow = '';
    await loadAlerts(); renderAlerts(); toast('Алерт удалён', a.id, 'warn');
  };
}