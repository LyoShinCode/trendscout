import { api } from '../api.js';
import { store } from '../store.js';
import { snd } from '../sound.js';
import { badge, cssVar, esc, fmt, palette, sparkline, STATUS_RU, toast } from '../ui.js';

export const RULE_DEFAULTS = {
  top_n: 5, popular_rank: 5, lookback_months: 24,
  newcomer_months: 6, catalog_months: 12, baseline_weeks: 8, max_plays: 50000,
  growth_factor: 2.5, decay_weeks: 4,
};

const GROUPS = [
  { title: 'Кого считаем прорывом', keys: ['top_n', 'popular_rank', 'lookback_months'] },
  { title: 'Новичок и спящий каталог', keys: ['newcomer_months', 'catalog_months', 'baseline_weeks', 'max_plays'] },
  { title: 'Медиа-всплеск', keys: ['growth_factor', 'decay_weeks'] },
];

const PARAMS = {
  top_n: { label: 'Размер топа', min: 3, max: 10, step: 1, unit: v => `топ-${v}`,
    help: 'Сколько верхних строк чарта считаем «популярными». Прорыв ищем только среди них.' },
  popular_rank: { label: 'Порог «уже был популярен»', min: 3, max: 50, step: 1, unit: v => `топ-${v}`,
    help: 'Если исполнитель раньше поднимался выше этой позиции — он не новичок и не «спящий». В демо 12 артистов, поэтому 5; в боевом каталоге — 50.' },
  lookback_months: { label: 'Глубина проверки истории', min: 6, max: 36, step: 1, unit: v => `${v} мес`,
    help: 'За сколько месяцев назад смотрим, попадал ли исполнитель в топ.' },
  newcomer_months: { label: 'Возраст новичка', min: 3, max: 12, step: 1, unit: v => `≤ ${v} мес`,
    help: 'Максимальный срок с дебюта, чтобы сработало правило NEWCOMER.' },
  catalog_months: { label: 'Возраст каталога', min: 3, max: 24, step: 1, unit: v => `≥ ${v} мес`,
    help: 'Минимальный срок доступности каталога на площадках для правила SLEEPER.' },
  baseline_weeks: { label: 'Окно оценки базы', min: 2, max: 26, step: 1, unit: v => `${v} нед`,
    help: 'За сколько недель до текущего всплеска считаем прослушивания. Отделяет «мало слушали» от «уже раскручен».' },
  max_plays: { label: 'Порог «мало слушали»', min: 10000, max: 200000, step: 5000, unit: v => fmt(v),
    help: 'Если за окно базы прослушиваний меньше этого числа — исполнитель считается непопулярным.' },
  growth_factor: { label: 'Порог роста', min: 1.5, max: 5, step: 0.1, unit: v => `×${Number(v).toFixed(1)}`,
    help: 'Во сколько раз текущая неделя должна превысить медиану четырёх предыдущих, чтобы назвать это всплеском.' },
  decay_weeks: { label: 'Окно затухания', min: 1, max: 8, step: 1, unit: v => `${v} нед`,
    help: 'Сколько недель после окончания медиа-события наблюдаем спад и формируем отчёт.' },
};

const TYPE_INFO = {
  SLEEPER: { name: 'Спящий каталог', why: 'Давно доступен, слушали мало — и вдруг вошёл в топ' },
  NEWCOMER: { name: 'Новичок', why: 'Дебютировал недавно и сразу попал в топ' },
  VIRAL: { name: 'Медиа-всплеск', why: 'Рост совпал с фильмом, сериалом или трендом' },
};

const LOG_KIND = { hit: 'Сработало', miss: 'Отказ', guard: 'Проверка', rev: 'Отзыв' };

let resetArmed = false;
let resetTimer = null;

export async function loadDashboard() {
  const s = store.state;
  const [meta, config, dashboard, series] = await Promise.all([
    api.meta(), api.config(), api.dashboard(s.region), api.series(s.region),
  ]);
  store.set({ meta, config, dashboard, series });
}

async function refresh() {
  await loadDashboard();
  renderDashboard();
}

/* ---------------- график ---------------- */
function lineChart(series, week, media) {
  const W = 900, H = 300, L = 58, R = 132, T = 18, B = 36;
  const iw = W - L - R, ih = H - T - B;
  const max = Math.max(1, ...series.flatMap(s => s.values));
  const colors = palette();
  const grid = cssVar('--line') || '#E4DFD5';
  const axis = cssVar('--faint') || '#948D82';
  const ink = cssVar('--ink-2') || '#403C36';
  const bandFill = cssVar('--plum-soft') || '#F0EAF8';
  const bandLine = cssVar('--plum') || '#6B3FA0';
  const x = w => L + ((w - 1) / 51) * iw;
  const y = v => T + ih - (v / max) * ih;

  let out = '';
  for (let i = 0; i <= 4; i++) {
    const gy = T + (ih * i) / 4;
    out += `<line x1="${L}" y1="${gy}" x2="${L + iw}" y2="${gy}" stroke="${grid}"/>
      <text x="${L - 10}" y="${gy + 4}" text-anchor="end" font-size="11" font-family="IBM Plex Mono" fill="${axis}">${fmt(max * (1 - i / 4))}</text>`;
  }
  media.forEach(m => {
    if (m.start > week) return;
    const x1 = x(m.start), x2 = x(Math.min(m.end, week));
    out += `<rect x="${x1}" y="${T}" width="${Math.max(2, x2 - x1)}" height="${ih}" fill="${bandFill}" opacity=".85"/>
      <line x1="${x1}" y1="${T}" x2="${x1}" y2="${T + ih}" stroke="${bandLine}" stroke-dasharray="3 3" opacity=".6"/>`;
  });
  [1, 13, 26, 39, 52].forEach(w => {
    out += `<text x="${x(w)}" y="${H - 12}" text-anchor="middle" font-size="11" font-family="IBM Plex Mono" fill="${axis}">нед ${w}</text>`;
  });

  const labels = [];
  series.forEach((s, i) => {
    const c = colors[i % colors.length];
    const pts = s.values.map((v, k) => `${x(k + 1).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
    out += `<polyline points="${pts}" fill="none" stroke="${c}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
    const lastY = y(s.values[s.values.length - 1]);
    out += `<circle cx="${x(s.values.length)}" cy="${lastY}" r="3.5" fill="${c}"/>`;
    labels.push({ y: lastY, name: s.name, color: c });
  });

  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) {
    if (labels[i].y - labels[i - 1].y < 15) labels[i].y = labels[i - 1].y + 15;
  }
  const overflow = labels.length ? labels[labels.length - 1].y - (T + ih) : 0;
  if (overflow > 0) labels.forEach(l => { l.y -= overflow; });
  labels.forEach(l => {
    out += `<text x="${L + iw + 12}" y="${l.y + 4}" font-size="12" font-family="IBM Plex Sans" fill="${ink}">${esc(l.name)}</text>`;
  });

  out += `<line x1="${x(week)}" y1="${T}" x2="${x(week)}" y2="${T + ih}" stroke="${ink}" stroke-dasharray="4 4" opacity=".45"/>`;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Динамика прослушиваний пяти лидеров региона">${out}</svg>`;
}

/* ---------------- рендер ---------------- */
export function renderDashboard() {
  const s = store.state;
  const d = s.dashboard, m = s.meta, c = s.config;
  if (!d || !m || !c) return;
  const el = document.getElementById('view-dashboard');
  const total = m.platforms.length;
  const got = Math.round(d.completeness * total);
  const full = d.completeness >= 1;
  const colors = palette();
  const regionName = m.regions.find(r => r.code === s.region)?.name || s.region;

  el.innerHTML = `
  <div class="page-head">
    <div>
      <p class="eyebrow">Рабочий стол аналитика</p>
      <h1>Кто набирает <span class="g">популярность</span></h1>
      <p class="lede">Каждую неделю система сравнивает прослушивания по регионам и сообщает
      о трёх типах прорыва: новичок, спящий каталог и медиа-всплеск. Данные учебные,
      логика принятия решений — как в боевой системе.</p>
    </div>
    <div class="head-actions">
      <a class="btn" href="#/help">Как это работает</a>
      <a class="btn" href="#/demo">Сценарий демо</a>
    </div>
  </div>

  <div class="statusbar">
    <div class="status-main">
      <span class="status-week">Неделя ${d.week}</span>
      <span class="status-date">${esc(d.week_label)}</span>
      <span class="state ${full ? 'ok' : 'warn'}">
        ${full ? '✓ Данные полные' : '⚠ Данные неполные'} · ${got} из ${total} площадок
        ${full ? '' : '· решения предварительные'}
      </span>
    </div>
    <div class="status-actions">
      <button class="btn primary" data-act="week">Следующая неделя →</button>
      <button class="btn" data-act="recalc">Пересчитать правила</button>
      <button class="btn quiet" data-act="reset" id="resetBtn">Сбросить демо</button>
    </div>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="label">Прослушиваний обработано</div>
      <div class="value">${fmt(d.kpis.events)}</div>
      <div class="note">Сумма недельных выгрузок площадок</div>
    </div>
    <div class="stat">
      <div class="label">Исполнителей в наблюдении</div>
      <div class="value">${d.kpis.artists}</div>
      <div class="note">${m.regions.length} региона · ${total} площадки</div>
    </div>
    <div class="stat">
      <div class="label">Сигналов ждут решения</div>
      <div class="value">${d.kpis.active_alerts}</div>
      <div class="note">Статусы «Новый» и «На проверке»</div>
    </div>
    <div class="stat">
      <div class="label">Активных медиа-событий</div>
      <div class="value">${d.media.filter(x => x.state === 'ACTIVE').length}</div>
      <div class="note">Фильмы, сериалы, тренды и фестивали</div>
    </div>
  </div>

  <div class="layout">
    <div class="column">

      <section class="panel-block">
        <div class="block-head">
          <h2>Кого слушают в регионе</h2>
          <p class="block-note">Чарт за текущую неделю. Нажмите на строку, чтобы открыть карточку исполнителя.</p>
        </div>
        <div class="toolbar">
          <label class="hint" for="regionSelect">Регион</label>
          <select id="regionSelect">${m.regions.map(r =>
            `<option value="${r.code}" ${r.code === s.region ? 'selected' : ''}>${esc(r.name)}</option>`).join('')}</select>
          <label class="hint" for="platformSelect">Площадка</label>
          <select id="platformSelect">
            <option value="all">Все площадки</option>
            ${m.platforms.map(p => `<option value="${p.id}" ${p.id === s.platform ? 'selected' : ''}>${esc(p.name)}</option>`).join('')}
          </select>
        </div>
        <div style="overflow-x:auto">
        <table class="chart-table">
          <thead><tr>
            <th>Место</th><th>Исполнитель</th><th>Прослушиваний</th>
            <th>К прошлой неделе</th><th>12 недель</th><th>Сигнал</th>
          </tr></thead>
          <tbody>${d.chart.entries.map(e => {
            const dd = e.delta_position;
            const tag = e.tag === 'catalog'
              ? '<span class="pill">без сигнала</span>'
              : badge(e.tag.replace('?', ''), TYPE_INFO[e.tag.replace('?', '')]?.name || e.tag);
            return `<tr data-artist="${esc(e.artist_name)}">
              <td class="rank ${e.position <= c.top_n ? 'top' : ''}">${e.position}</td>
              <td><div class="artist-name">${esc(e.artist_name)}</div>
                  <div class="artist-genre">${esc(e.genres.join(', '))}</div></td>
              <td class="num">${fmt(e.plays)}</td>
              <td class="delta ${dd > 0 ? 'up' : dd < 0 ? 'down' : 'flat'}">
                ${dd > 0 ? '↑ ' + dd : dd < 0 ? '↓ ' + (-dd) : 'без изменений'}</td>
              <td>${sparkline(e.spark, dd >= 0 ? (cssVar('--moss') || '#2F7A45') : (cssVar('--crimson') || '#B3261E'))}</td>
              <td>${tag}</td>
            </tr>`;
          }).join('')}</tbody>
        </table></div>
      </section>

      <section class="panel-block">
        <div class="block-head">
          <h2>Динамика пяти лидеров · ${esc(regionName)}</h2>
          <p class="block-note">Пунктир — текущая неделя. Цветные полосы — окна медиа-событий:
          видно, какой рост объясняется внешним поводом, а какой нет.</p>
        </div>
        <div class="chart-wrap">${lineChart(s.series.series, d.week, s.series.media)}</div>
        <div class="legend">
          ${s.series.series.map((x, i) =>
            `<span><i style="background:${colors[i % colors.length]}"></i>${esc(x.name)}</span>`).join('')}
          <span><i class="band"></i>окно медиа-события</span>
        </div>
      </section>

      <section class="panel-block">
        <div class="block-head">
          <h2>Сигналы системы</h2>
          <p class="block-note">Что система заметила и почему. Нажмите, чтобы открыть разбор с историей решения.</p>
        </div>
        ${d.recent_alerts.length ? d.recent_alerts.map(a => `
          <div class="signal" data-alert="${esc(a.id)}">
            <div>${badge(a.type, TYPE_INFO[a.type]?.name || a.type)}</div>
            <div>
              <div class="who">${esc(a.artist_name)}</div>
              <div class="why">${esc(TYPE_INFO[a.type]?.why || '')} · ${esc(a.region_code)}, место ${a.position} · правило ${esc(a.rule_id)}${a.provisional ? ' · данные неполные' : ''}</div>
            </div>
            <div>${badge(a.status, STATUS_RU[a.status])}</div>
          </div>`).join('')
          : '<div class="empty">Пока нет сигналов. Нажмите «Следующая неделя», чтобы продвинуть наблюдение.</div>'}
        <div style="margin-top:16px"><a class="btn sm" href="#/alerts">Все сигналы →</a></div>
      </section>

      <section class="panel-block">
        <div class="block-head">
          <h2>Медиа-события</h2>
          <p class="block-note">Внешние поводы для роста. После окончания события система следит
          за спадом: если популярность тает быстро, окно для контракта короткое.</p>
        </div>
        <div class="media-grid">${d.media.map(x => {
          const pct = Math.round(x.residual_potential * 100);
          const stateLabel = x.state === 'ACTIVE' ? 'Идёт сейчас'
            : x.state === 'ENDED' ? 'Завершено · спад' : 'Запланировано';
          const cls = x.state === 'ACTIVE' ? 'b-VIRAL' : x.state === 'ENDED' ? 'b-REJECTED' : 'b-NEW';
          return `<div class="media">
            <div class="title">${esc(x.title)}</div>
            <div class="meta">${esc(x.artist_name)} — «${esc(x.track_title)}»</div>
            <div class="meta">Недели ${x.start_week}–${x.end_week}</div>
            ${badge(cls, stateLabel)}
            <div class="bar"><i style="width:${pct}%"></i></div>
            <div class="meta">Остаточный интерес: ${pct}% от пика</div>
            <div class="hint">${esc(x.note || '')}</div>
          </div>`;
        }).join('')}</div>
      </section>

      <section class="panel-block">
        <div class="block-head">
          <h2>Журнал решений</h2>
          <p class="block-note">Каждая проверка правила записана: что выполнено, что нет и почему
          сигнал не создан. Это основа объяснимости.</p>
        </div>
        <div class="toolbar">
          ${[['all', 'Все записи'], ['hit', 'Сработало'], ['miss', 'Отказ'], ['guard', 'Проверка'], ['rev', 'Отзыв']]
            .map(([k, label]) => `<button class="chip ${s.logFilter === k ? 'on' : ''}" data-log="${k}">${label}</button>`).join('')}
        </div>
        <div class="log">${(() => {
          const rows = d.log.filter(l => s.logFilter === 'all' || l.level === s.logFilter);
          return rows.length ? rows.map(l => `
            <div class="log-row ${l.level}">
              <span class="log-kind">${LOG_KIND[l.level] || l.level} · ${l.week}</span>
              <span class="log-msg">${esc(l.message)}</span>
            </div>`).join('')
            : '<div class="empty">Нет записей этого типа.</div>';
        })()}</div>
      </section>
    </div>

    <aside class="side">
      <section class="card">
        <div class="block-head">
          <h2>Правила детекции</h2>
          <p class="block-note">Пороги хранятся в базе и меняются без перезапуска.
          Изменили значение — нажмите «Пересчитать правила».</p>
        </div>
        ${GROUPS.map(g => `
          <div class="rules-group">
            <h3>${g.title}</h3>
            ${g.keys.map(k => {
              const p = PARAMS[k];
              return `<div class="ctrl">
                <div class="ctrl-top">
                  <label for="p-${k}">${p.label}</label>
                  <output id="o-${k}">${p.unit(c[k])}</output>
                </div>
                <input type="range" id="p-${k}" data-param="${k}"
                  min="${p.min}" max="${p.max}" step="${p.step}" value="${c[k]}">
                <p class="ctrl-help">${p.help}</p>
              </div>`;
            }).join('')}
          </div>`).join('')}
        <div class="side-actions">
          <button class="btn primary" data-act="recalc">Пересчитать правила</button>
          <button class="btn" data-act="defaults">Вернуть значения по умолчанию</button>
        </div>
      </section>

      <section class="card">
        <div class="block-head">
          <h2>Проверка на сложных случаях</h2>
          <p class="block-note">Два сценария, на которых наивная система ошибается.</p>
        </div>
        <div class="scenario">
          <strong>Задержка данных</strong>
          <p>Площадка не прислала выгрузку в срок. Система помечает решения как предварительные,
          а после получения данных пересматривает их.</p>
          <button class="btn warn sm" data-act="lag">Смоделировать задержку</button>
        </div>
        <div class="scenario">
          <strong>Покупка прав на каталог</strong>
          <p>Площадка обнулила счётчик после покупки прав. Наблюдения показывают «мало слушали»,
          но истинная история известна — ложный сигнал не создаётся.</p>
          <button class="btn warn sm" data-act="rights">Смоделировать покупку прав</button>
        </div>
      </section>
    </aside>
  </div>`;

  bind();
}

/* ---------------- обработчики ---------------- */
function bind() {
  const el = document.getElementById('view-dashboard');

  el.querySelector('#regionSelect').onchange = async e => {
    store.set({ region: e.target.value, platform: 'all' });
    await refresh();
  };
  el.querySelector('#platformSelect').onchange = async e => {
    store.set({ platform: e.target.value });
    const chart = await api.chart(store.state.region, e.target.value);
    store.set({ dashboard: { ...store.state.dashboard, chart } });
    renderDashboard();
  };

  el.querySelectorAll('[data-log]').forEach(b => b.onclick = () => {
    store.set({ logFilter: b.dataset.log });
    renderDashboard();
  });

  el.querySelectorAll('[data-artist]').forEach(tr => tr.onclick = () => {
    store.state.artistFilters.q = tr.dataset.artist;
    location.hash = '#/artists';
  });
  el.querySelectorAll('[data-alert]').forEach(x => x.onclick = () => {
    store.state.alertFilters = { q: x.dataset.alert, type: '', status: '', sort: 'date', revised: '' };
    location.hash = '#/alerts';
  });

  el.querySelectorAll('[data-param]').forEach(inp => {
    const k = inp.dataset.param;
    inp.oninput = () => {
      el.querySelector('#o-' + k).textContent = PARAMS[k].unit(inp.value);
    };
    inp.onchange = async () => {
      const body = { ...store.state.config };
      el.querySelectorAll('[data-param]').forEach(i => { body[i.dataset.param] = Number(i.value); });
      try {
        const config = await api.setConfig(body);
        store.set({ config });
        toast('Правила обновлены', 'Нажмите «Пересчитать правила», чтобы применить новые пороги.', 'ok');
      } catch (e) { toast('Не удалось сохранить', e.message, 'warn'); }
    };
  });

  el.querySelectorAll('[data-act]').forEach(b => b.onclick = () => action(b.dataset.act, b));
}

async function action(act, btn) {
  try {
    if (act === 'week') {
      const r = await api.week();
      if (r.finished) {
        toast('Наблюдение завершено', 'Достигнута 52-я неделя. Сбросьте демо, чтобы начать заново.', 'warn');
      } else if (r.alerts_created?.length) {
        snd.alert('SLEEPER');
        toast('Новые сигналы', `${r.alerts_created.join(', ')} · неделя ${r.week}`, 'alert');
      } else {
        snd.tick();
        toast('Неделя ' + r.week, 'Новых сигналов нет — условия правил не выполнены.', '');
      }
      await refresh();
    }

    if (act === 'recalc') {
      const r = await api.runDetection();
      snd.ui();
      await refresh();
      toast('Пересчёт выполнен', `Создано сигналов: ${r.alerts_created}. Повторные сигналы отсекаются окном в 8 недель.`, 'ok');
    }

    if (act === 'defaults') {
      const config = await api.setConfig(RULE_DEFAULTS);
      store.set({ config });
      await refresh();
      toast('Значения восстановлены', 'Пороги правил вернулись к исходным.', 'ok');
    }

    if (act === 'lag') {
      const r = await api.lag();
      snd.warn();
      await refresh();
      toast(r.already_active ? 'Сценарий уже активен' : 'Задержка смоделирована',
        'Нажмите «Следующая неделя»: данные придут, и система пересмотрит предварительные решения.', 'warn');
    }

    if (act === 'rights') {
      const r = await api.rights();
      snd.warn();
      await refresh();
      if (r.applied) {
        toast('Права куплены: ' + r.artist,
          `Площадка «${r.platform}» обнулила счётчик. Истинная база ${fmt(r.true_baseline)}, наблюдаемая ${fmt(r.observed_baseline)} при пороге ${fmt(r.threshold)}. Смотрите журнал — запись «Проверка».`, 'warn');
      } else {
        toast('Сценарий не применён', r.message || 'Подходящий исполнитель не найден.', 'warn');
      }
    }

    if (act === 'reset') {
      if (!resetArmed) {
        resetArmed = true;
        btn.textContent = 'Нажмите ещё раз для сброса';
        btn.classList.add('danger');
        clearTimeout(resetTimer);
        resetTimer = setTimeout(() => {
          resetArmed = false;
          const b = document.getElementById('resetBtn');
          if (b) { b.textContent = 'Сбросить демо'; b.classList.remove('danger'); }
        }, 4000);
        return;
      }
      resetArmed = false;
      clearTimeout(resetTimer);
      await api.reset();
      store.set({ logFilter: 'all' });
      await refresh();
      toast('Демо сброшено', 'Данные и пороги возвращены к исходному состоянию, неделя 42.', 'ok');
    }
  } catch (e) {
    toast('Ошибка', e.message, 'warn');
  }
}