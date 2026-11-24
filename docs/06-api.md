```markdown
# API-контракт

Контракт генерируется из кода: `python export_openapi.py` → `docs/openapi.yaml`.
Живая документация: Swagger UI `/docs`, ReDoc `/redoc`, схема `/openapi.json`.

| Метод | Путь | Назначение |
|---|---|---|
| GET | /api/v1/meta | регионы, платформы, неделя, полнота |
| GET/PUT | /api/v1/config | пороги правил (NFR-02) |
| GET | /api/v1/charts/{region} | чарт недели, completeness/provisional |
| GET | /api/v1/charts/{region}/series | ряды Top-5 + окна медиа |
| GET | /api/v1/artists | список с метриками, фильтры, сортировка |
| GET | /api/v1/artists/{id} | каталог ISRC, доступность, алерты |
| GET | /api/v1/alerts | фильтры type/status/region/q/revised, сортировка |
| GET/PATCH/DELETE | /api/v1/alerts/{id} | карточка, workflow (409), удаление |
| GET | /api/v1/media-events | события + остаточный потенциал |
| POST | /api/v1/detection/run | принудительный пересчёт, 202 |
| POST | /api/v1/simulation/week | шаг симуляции |
| POST | /api/v1/simulation/scenario/lag | edge-case FR-04 |
| POST | /api/v1/simulation/scenario/rights | edge-case FR-05 |
| POST | /api/v1/simulation/reset | сброс демо |
| GET | /api/v1/log | журнал rule-engine |
| GET | /api/v1/dashboard | композит для дашборда |

## Ошибки
Единый формат: `{"detail": {"code": "...", "message": "..."}}`.
Коды: NOT_FOUND (404), INVALID_STATUS_TRANSITION (409).

## Статус-машина (UC-01)
NEW → IN_REVIEW → CONFIRMED | REJECTED; REJECTED → NEW; CONFIRMED → IN_REVIEW.
Недопустимый переход → 409. Каждый переход пишется в audit trail.
```