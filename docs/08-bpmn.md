# BPMN · «От прослушивания до решения A&R»

Файл для Camunda Modeler / demo.bpmn.io: `docs/diagrams/process.bpmn`.

## Таблица шагов
| Шаг | Дорожка | Действие | Артефакт |
|---|---|---|---|
| 1 | Ingestion | Таймер: недельный батч; приём событий | ListeningStat |
| 2 | Ingestion | Шлюз «полнота ≥ SLA?» — нет: буфер, provisional | FR-04 |
| 3 | Analytics | Пересчёт RegionalChart + ChartEntry | чарт недели |
| 4 | Analytics | Оценка правил FR-01…05 (guard первым) | журнал правил |
| 5 | Analytics | Шлюз «прорыв?» — да: создать Alert | BreakthroughAlert |
| 6 | Уведомления | Push/e-mail; таймер 72ч → ревизия FR-04 | уведомление |
| 7 | A&R | Разбор: IN_REVIEW → шлюз «подтверждён?» | audit trail |
| 8 | A&R | CONFIRMED → букинг / REJECTED с причиной | решение |