# Архитектура

## MVP (реализовано)
```mermaid
flowchart LR
    GEN[Генератор батчей<br/>seed 20261109] --> DB[(SQLite<br/>listening_stats)]
    DB --> AGG[Aggregation<br/>чарты недели]
    AGG --> RULES[RB-DETECT<br/>FR-01…05]
    CFG[(rule_params<br/>NFR-02)] --> RULES
    RULES --> AL[(alerts + audit)]
    AL --> API[FastAPI<br/>OpenAPI 3.0]
    API --> FE[Frontend<br/>ES-модули]
    API --> SW[Swagger UI /docs]
```
## Целевая (боевой путь)

```mermaid
flowchart LR
    P[Площадки] --> ING[Ingestion Service]
    ING --> K[Kafka: listening.raw<br/>key = region+week]
    K --> AN[Analytics Service<br/>rule-engine]
    AN --> PG[(PostgreSQL<br/>партиции по месяцам)]
    AN --> RD[(Redis: кэш чартов,<br/>дедуп алертов)]
    EN[Enrichment: ISRC-матчинг] --> AN
    AN --> NOT[Notifier: push/e-mail]
    PG --> GW[API Gateway] --> C[Агентства / A&R / BI]
```

## Обоснование решений
**Kafka:** пиковые батчи 50 млн событий/нед сглаживаются очередью; consumer groups масштабируют агрегацию горизонтально.
**Redis:** чарт читается на два порядка чаще, чем пересчитывается; дедупликация алертов с TTL 8 недель.
**SQLite → PostgreSQL:** MVP не требует сервера БД; переход = смена DATABASE_URL и партиционирование listening_stats (NFR-03).
**FastAPI:** контракт OpenAPI генерируется из кода — документация не расходится с реализацией.
Масштабирование кода
Новое правило = функция в services/rules.py + запись в docs/03 + тест AC.
Новый эндпоинт = роутер в api/ + схема в schemas.py.
Новое представление фронтенда = модуль в js/views/ + пункт роутера.