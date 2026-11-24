# Паспорт алгоритма RB-DETECT

## Формулировка для ИАР
«Алгоритм порогово-контекстной детекции аномалий временных рядов» —
автоматизированный анализ **структурированных данных** (недельные батчи прослушиваний)
на основе реализованного алгоритма классификации событий роста.

## Класс алгоритма
Детекция аномалий / классификация событий временного ряда:
пороговые правила + скользящая медиана + контекстные (медиа) признаки + guard-условия.
Не ML: объяснимость важнее точности на холодном старте (нет размеченной выборки прорывов).

## Вход / выход
**Вход:** ListeningStat(week, artist, region, platform, plays); справочники Artist/Track/Platform/Region/TrackPlatform; MediaEvent; конфигурация порогов.
**Выход:** BreakthroughAlert(type ∈ {SLEEPER, NEWCOMER, VIRAL}, confidence, provisional, rule_id) + журнал решений.

## Шаги
1. **Агрегация:** сумма батчей по артисту/региону/неделе с учётом полноты (FR-04) и сброса прав (FR-05) → RegionalChart + ChartEntry.
2. **Извлечение признаков:** position; best_pos за lookback-окно; total_observed; catalog_age; debut_age; growth = plays / median(plays[t-4..t-1]); активное медиа-событие; completeness.
3. **Guard FR-05:** true_total ≥ max_plays ∧ observed < max_plays ∧ rights_reset → подавление.
4. **Классификация (приоритет):** NEWCOMER (FR-02) → SLEEPER (FR-01) → VIRAL (FR-03) → NONE.
5. **Confidence:** 0.9 × completeness × margin(position), clamp [0.3, 0.99].
6. **Дедупликация:** ключ (artist, type, region), окно 8 недель.
7. **Пост-обработка:** ревизия provisional (FR-04); отчёт затухания после end_date (FR-03).

## Псевдокод

for region in regions:
chart = aggregate(week, region)
for entry in chart.top(N):
f = features(entry.artist, week, region)
if guard_rights(f): log(GUARD); continue
type = classify(f) # FR-02 → FR-01 → FR-03
if type and not dedup(artist, type, region):
emit Alert(type, confidence(f), provisional = completeness < 1)

## Сложность
O(R · A log A) на агрегацию недели + O(R · N · W) на признаки (W = lookback).
В бою признаки считаются инкрементально из агрегатов, не из сырых событий.

## Параметры (все — конфигурация, NFR-02)
top_n=5; lookback_months=24; max_plays=50000; catalog_months=12;
newcomer_months=6; growth_factor=2.5; decay_weeks=4.

## Ограничения и развитие
Пороги заданы экспертно; следующий шаг — калибровка по историческим прорывам,
затем ML-скоринг (градиентный бустинг на признаках выше) с сохранением объяснимости
через SHAP и правило-обоснование в алерте.