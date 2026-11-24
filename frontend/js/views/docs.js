import { api } from '../api.js';
import { mdToHtml } from '../md.js';
import { toast } from '../ui.js';

const FILES = [
  ['01-vision-scope.md', '01 · Постановка задачи'],
  ['02-domain-model.md', '02 · Модель данных'],
  ['03-requirements.md', '03 · Требования'],
  ['04-algorithm.md', '04 · Алгоритм'],
  ['05-architecture.md', '05 · Архитектура'],
  ['06-api.md', '06 · Контракт API'],
  ['07-use-case.md', '07 · Сценарий работы'],
  ['08-bpmn.md', '08 · Процесс BPMN'],
  ['09-iar-report.md', '09 · Пояснительная записка'],
  ['10-manual.md', '10 · Руководство'],
  ['11-demo-script.md', '11 · Сценарий демо'],
  ['12-supervisor-artifacts.md', '12 · Что показать руководителю'],
];

export async function renderDocs() {
  const el = document.getElementById('view-docs');
  el.innerHTML = `
  <div class="page-head">
    <div>
      <p class="eyebrow">Пакет артефактов</p>
      <h1>Документация <span class="g">проекта</span></h1>
      <p class="lede">Источник правды — файлы в папке <code>docs</code>. Контракт API выгружается
      из кода командой <code>python export_openapi.py</code>. Любой документ можно скопировать
      в Notion или положить в GitLab.</p>
    </div>
    <div class="head-actions"><a class="btn" href="/docs" target="_blank" rel="noopener">Открыть Swagger ↗</a></div>
  </div>
  <div class="docs">
    <nav class="docsnav">${FILES.map(([f, t], i) =>
      `<a data-doc="${i}" class="${i === 0 ? 'on' : ''}">${t}</a>`).join('')}</nav>
    <div id="docsBody"></div>
  </div>`;

  const body = el.querySelector('#docsBody');

  const show = async i => {
    el.querySelectorAll('.docsnav a').forEach((a, k) => a.classList.toggle('on', k === i));
    body.innerHTML = '<div class="empty">Загрузка документа…</div>';
    try {
      const md = await api.doc(FILES[i][0]);
      body.innerHTML = `<div class="card docsec">
        <div class="toolbar" style="justify-content:space-between">
          <span class="eyebrow">${FILES[i][1]}</span>
          <span style="display:flex;gap:8px">
            <button class="btn sm" id="copyMd">Скопировать</button>
            <a class="btn sm" href="/sa-docs/${FILES[i][0]}" download>Скачать .md</a>
          </span>
        </div>
        <div class="md">${mdToHtml(md)}</div></div>`;
      body.querySelector('#copyMd').onclick = () => {
        navigator.clipboard?.writeText(md)
          .then(() => toast('Скопировано', FILES[i][0] + ' — можно вставлять в Notion.', 'ok'))
          .catch(() => toast('Не удалось скопировать', 'Скачайте файл кнопкой рядом.', 'warn'));
      };
    } catch (e) {
      body.innerHTML = `<div class="empty">Файл ${FILES[i][0]} недоступен: ${e.message}</div>`;
    }
  };

  el.querySelectorAll('[data-doc]').forEach(a => a.onclick = () => show(Number(a.dataset.doc)));
  await show(0);
}