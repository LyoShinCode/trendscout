# TrendScout

**ПО для автоматизированного анализа структурированных данных на основе алгоритма
порогово-контекстной детекции аномалий временных рядов (RB-DETECT).**

Итоговая аттестационная работа · Бородуля Алексей Викторович · 2026

Система еженедельно анализирует выгрузки прослушиваний по регионам и площадкам,
выявляет три типа прорывов исполнителей (новичок, спящий каталог, медиа-всплеск)
и формирует **объяснимый сигнал**: тип, правило, уверенность, текстовый вывод
и журнал каждого проверенного условия. Данные учебные и воспроизводимые
(фиксированное зерно генератора), логика решений — как в промышленной системе.

---

## Быстрый старт

### Требования

- **Python 3.12.x** (на 3.13+ отсутствуют готовые wheel для `pydantic-core 2.27.2`
  и `PyYAML 6.0.2` — установка потребует компилятор)
- Node.js **не нужен**: фронтенд — статические ES-модули без сборки

### Установка и запуск

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate          # PowerShell при ошибке политики:
                                # Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Адреса

| Адрес | Назначение |
|---|---|
| `http://127.0.0.1:8000/` | интерфейс аналитика |
| `http://127.0.0.1:8000/docs` | Swagger UI — живой контракт API |
| `http://127.0.0.1:8000/presentation/` | презентация с таймером доклада |
| `http://127.0.0.1:8000/presentation/slides.html` | компактные слайды для куратора (печать в PDF) |
| `http://127.0.0.1:8000/sa-docs/` | документация в Markdown |

Первые действия: «Следующая неделя» ×3 → сигнал SLEEPER по «Кассете 90»
в Краснодаре; вкладка «Сигналы» → карточка с историей решения;
«Как это работает» → встроенное руководство.

---

## Данные и алгоритм

**Набор:** 12 исполнителей × 6 регионов × 4 площадки × 52 недели = 14 976 строк
недельных выгрузок, seed `20261109`.

**RB-DETECT** — детекция аномалий и классификация событий временного ряда:

| Правило | Условие | Класс |
|---|---|---|
| FR-05 | счётчик площадки обнулён, истинная база ≥ порога > наблюдаемой → сигнал подавляется | предохранитель |
| FR-02 | дебют ≤ 6 мес ∧ ранее вне Top-`popular_rank` | NEWCOMER |
| FR-01 | каталог ≥ 12 мес ∧ база за 8 нед < 50 000 ∧ 24 мес вне топа | SLEEPER |
| FR-03 | медиа-событие активно ∧ рост ≥ ×2.5 к медиане 4 недель | VIRAL |
| FR-04 | полнота выгрузок < 100% → provisional; после прихода данных — ревизия или отзыв | качество решений |

Уверенность = 0.9 × полнота данных × запас по позиции, диапазон 0.3…0.99.
Дедупликация: повтор по ключу «исполнитель + тип + регион» не создаётся 8 недель.
Все 9 порогов — конфигурация в БД (`rule_params`), меняются без пересборки (NFR-02).

Сложность: O(R·A log A) на агрегацию недели, O(R·N·W) на признаки.

---

## Проверки и тесты

```powershell
python check_stage2.py          # целостность данных и инварианты модели
python check_stage5.py          # сборка фронтенда и доступность всех эндпоинтов
python run_week.py --weeks 3    # прокрутка недель без браузера
pytest -v                       # 12 автотестов = приёмочные критерии (AC)
python evaluate.py --report     # метрики качества + docs/15-metrics-report.md
python export_openapi.py        # выгрузка контракта в docs/openapi.yaml
```

**Валидация алгоритма:** 120 размеченных сценариев (по 30 на класс), метка задана
бизнес-семантикой и не зависит от правил; класс NONE состоит из пяти ловушек
(звезда, покупка прав, недавний топ, пограничные сроки, рост без повода).
Метрики: precision / recall / F1 по классам, accuracy, macro-F1, доля отклонённых
ловушек, матрица ошибок 4×4. Область применимости указана в `docs/14-validation.md`.

**Автономный модуль** (без FastAPI, БД и зависимостей, только stdlib):

```powershell
cd submission
python trendscout_analysis.py --out report
```

Выгружает `report/report.md`, `report/metrics.json`, `report/alerts.csv`.

---

## Структура проекта

```
trendscout/
├── backend/
│   ├── app/
│   │   ├── main.py               # точка входа, lifespan, монтирование статики
│   │   ├── config.py             # пути, seed, горизонт наблюдения
│   │   ├── database.py           # engine, сессии, init_db
│   │   ├── models.py             # 12 сущностей доменной модели
│   │   ├── schemas.py            # Pydantic-контракты API
│   │   ├── seed.py               # детерминированный генератор данных
│   │   ├── core/enums.py         # типы сигналов, статусы, уровни журнала
│   │   ├── services/
│   │   │   ├── aggregation.py    # чарты, признаки, ALL-агрегация
│   │   │   ├── rules.py          # RB-DETECT: guard, классификация, ревизия, затухание
│   │   │   ├── alerts.py         # статус-машина, audit trail, журнал
│   │   │   └── validation.py     # holdout-набор и метрики качества
│   │   └── api/
│   │       ├── catalog.py        # meta, config, charts, artists, media
│   │       ├── alerts.py         # список, карточка, PATCH, DELETE
│   │       ├── engine.py         # недели, сценарии FR-04/FR-05, журнал, dashboard
│   │       └── metrics.py        # GET /api/v1/metrics
│   ├── tests/                    # conftest, factories, 12 автотестов
│   ├── check_stage2.py           # валидатор данных и инвариантов
│   ├── check_stage5.py           # проверка сборки и эндпоинтов
│   ├── run_week.py               # CLI-прокрутка наблюдения
│   ├── evaluate.py               # прогон метрик качества
│   ├── export_openapi.py         # генерация docs/openapi.yaml
│   ├── requirements.txt
│   └── pytest.ini
├── frontend/
│   ├── index.html
│   ├── css/  tokens.css · base.css · views.css
│   └── js/   main · router · store · api · ui · sound · md
│       └── views/  dashboard · alerts · artists · help · demo · docs
├── docs/
│   ├── 01…09                     # vision, модель, требования, алгоритм,
│   │                             # архитектура, API, use case, BPMN, записка ИАР
│   ├── 10-manual.md              # руководство пользователя и оператора
│   ├── 11-demo-script.md         # сценарий демонстрации с таймингом
│   ├── 12-supervisor-artifacts.md# что показать куратору и в каком порядке
│   ├── 13-diagrams.md            # Mermaid-исходники диаграмм
│   ├── 14-validation.md          # протокол валидации
│   ├── 15-metrics-report.md      # генерируется evaluate.py --report
│   ├── 16-er-diagrams.md         # три ER-диаграммы
│   ├── 17-text-presentation.md   # текстовая презентация по 4 разделам ИАР
│   ├── openapi.yaml              # генерируется export_openapi.py
│   └── diagrams/                 # 01-er · 02-algorithm · 03-architecture ·
│                                 # 04-state-machine (.svg) + process.bpmn
├── presentation/
│   ├── index.html                # доклад: таймер 10 минут, заметки, печать в PDF
│   └── slides.html               # 10 слайдов для куратора, печать в PDF
├── submission/
│   ├── trendscout_analysis.py    # автономный модуль анализа (stdlib)
│   └── report/                   # отчёты прогона (генерируются)
├── README.md
└── .gitignore
```

---

## Пакет артефактов ИАР

| Артефакт | Файл |
|---|---|
| Пояснительная записка (цели, задачи, этапы, результат) | `docs/09-iar-report.md` |
| Требования и трассировка «требование → критерий → тест» | `docs/03-requirements.md` |
| Модель данных, 11 архитектурных решений | `docs/02-domain-model.md`, `docs/16-er-diagrams.md` |
| Паспорт алгоритма и блок-схема | `docs/04-algorithm.md`, `docs/diagrams/02-algorithm.svg` |
| Процесс в нотации BPMN 2.0 | `docs/diagrams/process.bpmn` |
| Контракт API | `docs/openapi.yaml`, Swagger `/docs` |
| Метрики качества | `docs/15-metrics-report.md`, `GET /api/v1/metrics` |
| Руководство и сценарий демо | `docs/10-manual.md`, `docs/11-demo-script.md` |
| Текстовая презентация и слайды | `docs/17-text-presentation.md`, `presentation/slides.html` |
| Код и тесты | `backend/`, `frontend/`, `submission/` |

Порядок разговора с куратором и состав архива — в `docs/12-supervisor-artifacts.md`.

---

## Как развивать

| Что меняю | Где |
|---|---|
| Пороги правил | панель дашборда или `PUT /api/v1/config`; дефолты в `app/seed.py` |
| Логика правил | `app/services/rules.py`, функция `classify` (порядок проверок = приоритет) |
| Признаки и агрегация | `app/services/aggregation.py` |
| Демо-данные | `app/seed.py`: исполнители, кривые, медиа-события |
| Новое правило | требование в `docs/03` → проверка в `classify` → тест в `tests/test_acceptance.py` → подпись в `TYPE_INFO` дашборда |
| Цвета и типографика | `frontend/css/tokens.css` — единственный источник значений |
| Диаграммы | `docs/13-diagrams.md` (Mermaid) → экспорт SVG |

Боевой контур следующего этапа: адаптеры реальных API площадок → Kafka →
PostgreSQL с партиционированием по месяцам → Redis (кэш чартов, дедупликация) →
калибровка порогов по истории → градиентный бустинг на тех же признаках с SHAP.

---

## Типовые проблемы

| Симптом | Решение |
|---|---|
| Ошибка сборки wheel при `pip install` | нужен Python 3.12: `py -3.12 -m venv .venv` |
| `ModuleNotFoundError: No module named 'app'` | запускать из `backend/`; папка помечена Sources Root в PyCharm |
| Красные импорты в PyCharm | ПКМ по `backend` → Mark Directory as → Sources Root |
| Порт занят | `uvicorn app.main:app --port 8001` |
| Страница пустая / ошибка загрузки | не запущен бэкенд: `uvicorn app.main:app --reload` |
| Нет сигналов | журнал → «Отказ» покажет причину; продвинуть неделю или смягчить пороги |
| `slides.html` печатает одну страницу | кнопка «Все слайды списком» → Ctrl+P; либо Ctrl+F5 против кэша |
| Папка на GitHub пустая / 404 | вложенный `.git`: удалить его, `git rm --cached <папка>`, `git add <папка>` |
| Данные испорчены экспериментами | «Сбросить демо» (два нажатия) или удалить `backend/trendscout.db` |

---

## Репозиторий

Один репозиторий на проект: `git init` только в корне, вложенные `.git` запрещены —
внешний git воспринимает их как субмодули и публикует пустые папки.

**Автор:** Бородуля Алексей Викторович · a.v.borodulya@mail.ru · telegram: @therandomname
