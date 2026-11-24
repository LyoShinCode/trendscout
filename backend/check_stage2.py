"""Самопроверка этапа 2. Запуск: python check_stage2.py

Проверяет не только количества строк, но и согласованность фикстур
с бизнес-правилами FR-01 / FR-03 / FR-05 (трассировка данные ↔ требования).
"""
from sqlalchemy import func, select

from app.database import SessionLocal, init_db
from app.models import (AlertNote, Artist, BreakthroughAlert, ChartEntry,
                        ListeningStat, MediaEvent, Platform, Region, RegionalChart,
                        RuleParams, SimState, Track, TrackMediaEvent, TrackPlatform)
from app.seed import generate
from app.services.aggregation import baseline_plays, true_baseline

EXPECTED = [
    (Artist, 12),
    (Track, 14),
    (Platform, 4),
    (Region, 6),
    (TrackPlatform, 56),
    (ListeningStat, 14976),
    (RegionalChart, 252),
    (ChartEntry, 3024),          # 252 чарта × 12 артистов
    (MediaEvent, 3),
    (TrackMediaEvent, 3),
    (BreakthroughAlert, 4),
    (AlertNote, 8),
    (RuleParams, 1),
    (SimState, 1),
]


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.get(SimState, 1) is None:
            print("БД пуста — генерирую данные…")
            generate(db)

        print(f"\n{'ТАБЛИЦА':<22}{'ФАКТ':>8}{'ОЖИДАНИЕ':>10}   СТАТУС")
        ok = True
        for model, expected in EXPECTED:
            actual = db.scalar(select(func.count()).select_from(model))
            good = actual == expected
            ok &= good
            print(f"{model.__tablename__:<22}{actual:>8}{expected:>10}   {'OK' if good else 'FAIL'}")

        st = db.get(SimState, 1)
        p = db.get(RuleParams, 1)
        print(f"\nТекущая неделя: {st.week}")
        print(f"Пороги правил: Top-{p.top_n}, lookback {p.lookback_months} мес, "
              f"max_plays {p.max_plays:,}".replace(",", " "))

        print("\nБаза артистов: истинная за всё время / наблюдаемая за окно "
              f"{p.baseline_weeks} нед (признак FR-01):")
        for a in db.scalars(select(Artist).order_by(Artist.id)):
            obs = baseline_plays(db, a, st.week, p.baseline_weeks)
            tru = true_baseline(db, a, st.week, p.baseline_weeks)
            debut_m = __import__("app.services.aggregation", fromlist=["months_between"]) \
                .months_between(a.debut_date, st.week)
            if debut_m <= p.newcomer_months:
                mark = "  ← NEWCOMER"
            elif obs < p.max_plays:
                mark = "  ← SLEEPER-кандидат"
            else:
                mark = ""
            rights = (f" [права: {a.rights_platform}, нед {a.rights_week}]"
                      if a.rights_platform else "")
            print(f"  {a.id:<4} {a.name:<18} всего {a.true_total_plays:>9,} | "
                  f"окно: набл {obs:>7,} / ист {tru:>7,}{mark}{rights}".replace(",", " "))

        # --- Инварианты доменной модели и согласованность с правилами ---
        sleeper_ok = True
        viral_ok = True
        rejected_sleeper_has_reason = True
        for al in db.scalars(select(BreakthroughAlert)):
            a = db.get(Artist, al.artist_id)
            if al.type == "SLEEPER" and al.status != "REJECTED":
                sleeper_ok &= baseline_plays(db, a, al.week, p.baseline_weeks) < p.max_plays
            if al.type == "SLEEPER" and al.status == "REJECTED" and al.rule_id == "FR-05":
                rejected_sleeper_has_reason &= a.rights_platform is not None
            if al.type == "VIRAL":
                me = db.scalar(select(MediaEvent).where(
                    MediaEvent.artist_id == a.id,
                    MediaEvent.start_week <= al.week,
                    MediaEvent.end_week >= al.week))
                viral_ok &= me is not None

        dup_batches = db.scalar(select(func.count()).select_from(
            select(ListeningStat.week, ListeningStat.artist_id,
                   ListeningStat.region_code, ListeningStat.platform_id)
            .group_by(ListeningStat.week, ListeningStat.artist_id,
                      ListeningStat.region_code, ListeningStat.platform_id)
            .having(func.count() > 1).subquery()))

        checks = [
            ("У каждого трека 4 площадки",
             db.scalar(select(func.count()).select_from(TrackPlatform)) ==
             db.scalar(select(func.count()).select_from(Track)) * 4),
            ("ISRC уникальны",
             db.scalar(select(func.count(func.distinct(Track.isrc)))) ==
             db.scalar(select(func.count()).select_from(Track))),
            ("Нет дублей батчей", dup_batches == 0),
            ("У каждого алерта есть audit trail",
             all(len(al.notes) > 0 for al in db.scalars(select(BreakthroughAlert)))),
            ("Все алерты ссылаются на существующий чарт",
             all(db.get(RegionalChart, al.chart_id) is not None
                 for al in db.scalars(select(BreakthroughAlert)))),
            ("Позиции в каждом чарте: 1..12 без пропусков",
             all(sorted(e.position for e in ch.entries) == list(range(1, 13))
                 for ch in db.scalars(select(RegionalChart)))),
            ("FR-01: активные SLEEPER имеют базу < max_plays", sleeper_ok),
            ("FR-03: VIRAL привязан к активному медиа-событию", viral_ok),
            ("FR-05: отклонённый SLEEPER имеет причину (сброс прав)", rejected_sleeper_has_reason),
        ]

        print("\nИнварианты:")
        for name, passed in checks:
            ok &= passed
            print(f"  [{'OK' if passed else 'FAIL'}] {name}")

        print("\nЭТАП 2 ПРОЙДЕН" if ok else "\nЕСТЬ РАСХОЖДЕНИЯ — пришли вывод ментору")
    finally:
        db.close()


if __name__ == "__main__":
    main()