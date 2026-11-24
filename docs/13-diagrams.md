# Диаграммы · исходники для правки

SVG-файлы в `docs/diagrams/` собраны из этих источников. Mermaid рендерится
в GitLab и Notion без дополнительных инструментов.

## ER-диаграмма

```mermaid
erDiagram
    Artist ||--o{ Track : "1:M"
    Artist ||--o{ BreakthroughAlert : "1:M (D-01)"
    Artist ||--o{ ChartEntry : "1:M"
    Track ||--o{ TrackPlatform : "1:M"
    Platform ||--o{ TrackPlatform : "1:M"
    Track ||--o{ ListeningStat : "1:M"
    Region ||--o{ ListeningStat : "1:M"
    Platform ||--o{ ListeningStat : "1:M"
    Region ||--o{ RegionalChart : "1:M"
    RegionalChart ||--o{ ChartEntry : "1:M (D-02)"
    RegionalChart ||--o{ BreakthroughAlert : "1:M"
    Track ||--o{ TrackMediaEvent : "1:M"
    MediaEvent ||--o{ TrackMediaEvent : "1:M (D-03)"
    MediaEvent }o--|| Artist : "повод роста"
    BreakthroughAlert ||--o{ AlertNote : "audit trail"
```

## Алгоритм RB-DETECT

```mermaid
flowchart TD
    A[Недельный батч выгрузок] --> B[Агрегация: RegionalChart + ChartEntry]
    B --> C[Признаки Top-N: позиция, история, база, каталог, дебют, рост, медиа]
    C --> D{FR-05: счётчик обнулён и истинная база ≥ порога?}
    D -- да --> E[Журнал «Проверка», сигнал не создаётся]
    D -- нет --> F{FR-02: дебют ≤ N мес и история чистая?}
    F -- да --> G[NEWCOMER]
    F -- нет --> H{FR-01: каталог ≥ 12 мес, база < порога, история чистая?}
    H -- да --> I[SLEEPER]
    H -- нет --> J{FR-03: событие активно и рост ≥ ×2.5?}
    J -- да --> K[VIRAL]
    J -- нет --> L[Журнал «Отказ»]
    G --> M[confidence, дедуп 8 нед, алерт + provisional]
    I --> M
    K --> M
    M --> N[Пост-шаги: ревизия FR-04, отчёт затухания FR-03]
```

## Последовательность: недельный цикл

```mermaid
sequenceDiagram
    participant FE as Фронтенд
    participant API as FastAPI
    participant AGG as Агрегация
    participant RUL as RB-DETECT
    participant DB as База данных
    FE->>API: POST /simulation/week
    API->>DB: week += 1
    API->>AGG: rebuild_all(week)
    AGG->>DB: чарты и позиции
    API->>RUL: evaluate(week)
    RUL->>DB: признаки, guard FR-05
    RUL->>DB: алерты + журнал
    API-->>FE: {week, alerts_created}
    FE->>API: GET /dashboard
    API-->>FE: чарт, сигналы, журнал
```

## Статус-машина

```mermaid
stateDiagram-v2
    [*] --> NEW
    NEW --> IN_REVIEW: взять в работу
    NEW --> REJECTED: отклонить
    IN_REVIEW --> CONFIRMED: подтвердить
    IN_REVIEW --> REJECTED: отклонить
    CONFIRMED --> IN_REVIEW: переоткрыть
    REJECTED --> NEW: восстановить
    NEW --> REJECTED: FR-04 авто-отзыв (пунктир в SVG)
```

## Контекстная диаграмма потоков данных

```mermaid
flowchart LR
    P[Площадки] -->|недельные выгрузки| S[TrendScout]
    M[Медиа-источники] -->|события| S
    C[Конфигурация порогов] --> S
    S -->|алерты и аудит| AR[A&R-менеджер]
    S -->|региональные чарты| AG[Концертное агентство]
    S -->|отчёты затухания| MK[Маркетинг]
```