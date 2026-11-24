import { api } from '../api.js';
import { store } from '../store.js';
import { esc, fmt, toast } from '../ui.js';

const TOTAL = 180;

const STEPS = [
  {
    id: 'prep', start: 0, dur: 15, title: 'Подготовка стенда',
    say: '«Перед демонстрацией привожу стенд к исходному состоянию: неделя 42, пороги по умолчанию.»',
    act: 'Нажать «Выполнить» — демо сбрасывается и открывается дашборд.',
    expect: 'Неделя 42, данные полные, четыре показателя заполнены.',
    run: async () => {
      await api.reset();
      location.hash = '#/dashboard';
      return 'Стенд сброшен: неделя 42, пороги по умолчанию.';
    },
  },
  {
    id: 'intro', start: 15, dur: 20, title: 'Задача и замысел',
    say: '«Задача: находить исполнителей, которые начинают набирать популярность, до того как их заметит рынок. Концертные агентства не знают, где растёт аудитория, лейблы пропускают новичков, маркетинг путает устойчивый рост с хайпом на сериале. Система каждую неделю сравнивает выгрузки площадок по регионам и выдаёт объяснимый сигнал.»',
    act: 'Показать верх дашборда: заголовок, строка состояния, четыре показателя.',
    expect: 'Видно назначение системы и текущую неделю наблюдения.',
    run: async () => { location.hash = '#/dashboard'; return 'Открыт дашборд — постановка задачи.'; },
  },
  {
    id: 'data', start: 35, dur: 25, title: 'Данные и модель',
    say: '«Вход — структурированные недельные выгрузки: двенадцать исполнителей, шесть регионов, четыре площадки, пятьдесят две недели, почти пятнадцать тысяч строк. Модель данных — двенадцать сущностей. Ключевые решения: позиции чарта хранятся реляционно, а не снимком JSON, иначе нельзя построить запрос по динамике; каталог сопоставляется между площадками по коду ISRC; дата появления каталога на площадке хранится отдельно — на ней держится предохранитель.»',
    act: 'Открыть «Исполнители», нажать на карточку «Кассета 90».',
    expect: 'Карточка с каталогом ISRC и датами доступности по площадкам.',
    run: async () => {
      store.state.artistFilters.q = 'Кассета 90';
      location.hash = '#/artists';
      return 'Открыт список исполнителей с фильтром «Кассета 90». Нажмите на карточку.';
    },
  },
  {
    id: 'detect', start: 60, dur: 35, title: 'Алгоритм в действии',
    say: '«Продвигаю наблюдение на три недели. Система пересчитывает чарты и проверяет правила. На сорок четвёртой неделе «Кассета 90» входит в топ Краснодара: каталог доступен с две тысячи девятнадцатого, за окно базы прослушиваний меньше пятидесяти тысяч, за два года в топе не был. Срабатывает правило «спящий каталог». На сорок пятой неделе то же самое в Новосибирске — это уже подсказка для тура.»',
    act: 'Нажать «Выполнить» — три недели прокручиваются автоматически.',
    expect: 'Сигналы SLEEPER по «Кассете 90» в Краснодаре и Новосибирске.',
    run: async () => {
      const created = [];
      let week = null;
      for (let i = 0; i < 3; i++) {
        const r = await api.week();
        week = r.week;
        if (r.alerts_created?.length) created.push(...r.alerts_created);
        if (r.finished) break;
      }
      location.hash = '#/dashboard';
      return created.length
        ? `Неделя ${week}. Созданы сигналы: ${created.join(', ')}.`
        : `Неделя ${week}. Новых сигналов нет — смягчите пороги или сбросьте демо.`;
    },
  },
  {
    id: 'explain', start: 95, dur: 25, title: 'Объяснимость решения',
    say: '«Сигнал — не чёрный ящик. В журнале видно каждую проверку: какое условие выполнено, какое нет. В карточке сигнала — правило, уверенность и полная история решения. Здесь же рабочий процесс: взять на проверку, подтвердить или отклонить. Недопустимый переход сервер отклоняет с кодом 409.»',
    act: 'Открыть «Сигналы», нажать на первый сигнал; затем показать журнал на дашборде.',
    expect: 'Карточка с историей решения и кнопками статуса.',
    run: async () => {
      const list = await api.alerts({ sort: 'date' });
      store.state.alertFilters = { q: '', type: '', status: '', sort: 'date', revised: '' };
      location.hash = '#/alerts';
      return `Сигналов в системе: ${list.length}. Нажмите на верхний, чтобы открыть разбор.`;
    },
  },
  {
    id: 'lag', start: 120, dur: 20, title: 'Сложный случай: задержка данных',
    say: '«Площадка не прислала выгрузку в срок. Система не замалчивает это: чарт помечается предварительным, уверенность снижается. Когда данные приходят, решение пересматривается — подтверждается или автоматически отзывается. В автотесте этот сценарий доводится до автоматического отзыва.»',
    act: 'Нажать «Выполнить» — задержка моделируется и неделя продвигается.',
    expect: 'В журнале запись «Проверка», затем «Отзыв» или подтверждение.',
    run: async () => {
      await api.lag();
      const r = await api.week();
      const log = await api.log();
      const rev = log.find(l => l.level === 'rev');
      const hit = log.find(l => l.level === 'hit' && l.message.includes('FR-04'));
      location.hash = '#/dashboard';
      return rev ? `Неделя ${r.week}. Сигнал отозван: ${rev.message}`
        : hit ? `Неделя ${r.week}. Решение подтверждено полными данными: ${hit.message}`
        : `Неделя ${r.week}. Полнота восстановлена, предварительных решений не осталось.`;
    },
  },
  {
    id: 'rights', start: 140, dur: 15, title: 'Сложный случай: покупка прав',
    say: '«Площадка купила права и обнулила счётчик. Наивная система объявит прорыв у известной звезды. Здесь хранится истинная история: предохранитель сравнивает наблюдаемую базу с истинной и не создаёт ложный сигнал — в журнале видно оба числа и порог.»',
    act: 'Нажать «Выполнить», затем показать журнал, вкладка «Проверка».',
    expect: 'Запись предохранителя с истинной и наблюдаемой базой.',
    run: async () => {
      const r = await api.rights();
      const log = await api.log();
      const guard = log.find(l => l.level === 'guard' && l.message.includes('FR-05'));
      store.set({ logFilter: 'guard' });
      location.hash = '#/dashboard';
      if (r.applied) {
        return `${r.artist}: истинная база ${fmt(r.true_baseline)}, наблюдаемая ${fmt(r.observed_baseline)}, порог ${fmt(r.threshold)}. ${guard ? 'Предохранитель записан в журнал.' : ''}`;
      }
      return r.message || 'Подходящий исполнитель не найден — продвиньте неделю и повторите.';
    },
  },
  {
    id: 'quality', start: 155, dur: 15, title: 'Качество: тесты и контракт',
    say: '«Каждый приёмочный критерий покрыт автотестом — двенадцать тестов, все зелёные. Контракт API генерируется из кода, поэтому документация не расходится с реализацией: шестнадцать эндпоинтов, единый формат ошибок, проверка переходов статусов.»',
    act: 'Открыть вкладку API; в терминале показать вывод pytest -v.',
    expect: 'Swagger со списком эндпоинтов; в терминале «12 passed».',
    run: async () => {
      window.open('/docs', '_blank', 'noopener');
      return 'Swagger открыт в новой вкладке. В терминале выполните: pytest -v';
    },
  },
  {
    id: 'next', start: 170, dur: 10, title: 'Что дальше',
    say: '«Следующий этап — подключение реальных API площадок через слой адаптеров, переход на PostgreSQL с партиционированием, дневные чарты и калибровка порогов по историческим данным. Архитектура к этому готова: правила, признаки и контракт отделены от источника данных.»',
    act: 'Показать раздел «Что дальше» в презентации или ROADMAP в документации.',
    expect: 'Понятен следующий шаг развития проекта.',
    run: async () => {
      window.open('/presentation/', '_blank', 'noopener');
      return 'Презентация открыта — последний слайд содержит план развития.';
    },
  },
];

let timer = null;

const mmss = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;

function activeStep(elapsed) {
  return STEPS.find(s => elapsed >= s.start && elapsed < s.start + s.dur) || null;
}

function tick() {
  const d = store.state.demo;
  if (!d.running) return;
  d.elapsed = Math.min(TOTAL, d.elapsed + 1);
  if (d.elapsed >= TOTAL) { d.running = false; stopTimer(); }
  const t = document.getElementById('demoTimer');
  if (t) {
    t.textContent = mmss(d.elapsed) + ' / ' + mmss(TOTAL);
    t.classList.toggle('over', d.elapsed >= TOTAL);
    const bar = document.getElementById('demoBar');
    if (bar) bar.style.width = (d.elapsed / TOTAL * 100) + '%';
    const cur = activeStep(d.elapsed);
    document.querySelectorAll('.step').forEach(el => {
      el.classList.toggle('active', !!cur && el.dataset.step === cur.id);
    });
    const label = document.getElementById('demoNow');
    if (label) label.textContent = cur ? cur.title : 'Сценарий завершён';
  }
  syncHud();
}

function startTimer() {
  stopTimer();
  timer = setInterval(tick, 1000);
}

function stopTimer() {
  if (timer) { clearInterval(timer); timer = null; }
}

export function syncHud() {
  const hud = document.getElementById('demoHud');
  if (!hud) return;
  const d = store.state.demo;
  const show = (d.running || d.elapsed > 0) && store.state.view !== 'demo';
  hud.classList.toggle('on', show);
  if (!show) return;
  const cur = activeStep(d.elapsed);
  hud.innerHTML = `
    <span class="hud-time">${mmss(d.elapsed)} / ${mmss(TOTAL)}</span>
    <span class="hud-step">${esc(cur ? cur.title : 'Сценарий завершён')}</span>
    <button class="btn sm" id="hudToggle">${d.running ? 'Пауза' : 'Продолжить'}</button>
    <a class="btn sm" href="#/demo">Сценарий</a>`;
  const b = document.getElementById('hudToggle');
  if (b) b.onclick = () => {
    d.running = !d.running;
    if (d.running) startTimer(); else stopTimer();
    syncHud();
  };
}

export async function renderDemo() {
  const el = document.getElementById('view-demo');
  const d = store.state.demo;
  const cur = activeStep(d.elapsed);

  el.innerHTML = `
  <div class="page-head">
    <div>
      <p class="eyebrow">Запись экрана · 3 минуты</p>
      <h1>Сценарий <span class="g">демонстрации</span></h1>
      <p class="lede">Девять шагов с таймингом, текстом для озвучки и кнопками, которые
      реально выполняют действия. Таймер продолжает идти при переходе на другие экраны —
      внизу слева остаётся компактная панель.</p>
    </div>
    <div class="head-actions">
      <a class="btn" href="/sa-docs/11-demo-script.md" download>Скачать сценарий</a>
      <button class="btn" onclick="window.print()">Печать</button>
    </div>
  </div>

  <div class="demo-top">
    <div>
      <div class="timer ${d.elapsed >= TOTAL ? 'over' : ''}" id="demoTimer">${mmss(d.elapsed)} / ${mmss(TOTAL)}</div>
      <div class="timer-label">Текущий шаг: <strong id="demoNow">${esc(cur ? cur.title : (d.elapsed >= TOTAL ? 'Сценарий завершён' : 'не начат'))}</strong></div>
      <div class="demo-progress"><i id="demoBar" style="width:${d.elapsed / TOTAL * 100}%"></i></div>
    </div>
    <div class="head-actions">
      <button class="btn primary" id="demoStart">${d.running ? 'Пауза' : (d.elapsed > 0 ? 'Продолжить' : 'Начать отсчёт')}</button>
      <button class="btn" id="demoReset">Сбросить таймер</button>
      <button class="btn" id="demoPrep">Подготовить стенд</button>
    </div>
  </div>

  ${STEPS.map(s => `
    <section class="step ${cur && cur.id === s.id ? 'active' : ''} ${d.done[s.id] ? 'done' : ''}" data-step="${s.id}">
      <div>
        <div class="step-time">${mmss(s.start)}</div>
        <div class="step-dur">${s.dur} секунд</div>
      </div>
      <div>
        <h3>${esc(s.title)}</h3>
        <p class="say">${esc(s.say)}</p>
        <p class="do"><strong>Действие:</strong> ${esc(s.act)}</p>
        <p class="expect"><strong>На экране:</strong> ${esc(s.expect)}</p>
        ${d.results[s.id] ? `<p class="step-result"><strong>Результат:</strong> ${esc(d.results[s.id])}</p>` : ''}
      </div>
      <div class="step-actions">
        <button class="btn sm primary" data-run="${s.id}">Выполнить</button>
        <button class="btn sm" data-done="${s.id}">${d.done[s.id] ? '✓ Пройден' : 'Отметить пройденным'}</button>
      </div>
    </section>`).join('')}

  <section class="panel-block" style="margin-top:24px">
    <div class="block-head">
      <h2>Настройки записи</h2>
      <p class="block-note">Чтобы запись читалась на проекторе и в мессенджере.</p>
    </div>
    <ul style="margin-left:20px;list-style:disc;color:var(--ink-2)">
      <li>Разрешение 1920×1080, масштаб браузера 100%, светлая тема.</li>
      <li>Скрыть панель закладок; оставить только вкладку приложения и вкладку API.</li>
      <li>Звук уведомлений выключен — озвучка идёт голосом.</li>
      <li>Терминал с выводом <code>pytest -v</code> подготовить заранее и держать в соседнем окне.</li>
      <li>Курсор двигать плавно, после каждого клика делать паузу в одну секунду.</li>
    </ul>
  </section>`;

  el.querySelector('#demoStart').onclick = () => {
    d.running = !d.running;
    if (d.running) startTimer(); else stopTimer();
    renderDemo();
  };
  el.querySelector('#demoReset').onclick = () => {
    stopTimer();
    store.state.demo = { running: false, elapsed: 0, done: {}, results: {} };
    renderDemo(); syncHud();
  };
  el.querySelector('#demoPrep').onclick = async () => {
    try {
      await api.reset();
      store.state.demo.results.prep = 'Стенд сброшен: неделя 42.';
      store.state.demo.done.prep = true;
      toast('Стенд готов', 'Данные сброшены к неделе 42.', 'ok');
      renderDemo();
    } catch (e) { toast('Ошибка', e.message, 'warn'); }
  };

  el.querySelectorAll('[data-done]').forEach(b => b.onclick = () => {
    const id = b.dataset.done;
    d.done[id] = !d.done[id];
    renderDemo();
  });

  el.querySelectorAll('[data-run]').forEach(b => b.onclick = async () => {
    const step = STEPS.find(s => s.id === b.dataset.run);
    if (!step) return;
    b.disabled = true;
    b.textContent = 'Выполняется…';
    try {
      const result = await step.run();
      d.results[step.id] = result;
      d.done[step.id] = true;
      toast(step.title, result, 'ok');
    } catch (e) {
      d.results[step.id] = 'Ошибка: ' + e.message;
      toast('Шаг не выполнен', e.message, 'warn');
    } finally {
      if (store.state.view === 'demo') renderDemo();
      syncHud();
    }
  });

  if (d.running) startTimer();
  syncHud();
}