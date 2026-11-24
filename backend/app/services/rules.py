"""RB-DETECT: порогово-контекстная детекция аномалий временных рядов.
Паспорт: docs/04-algorithm.md. Порядок: guard → FR-02 → FR-01 → FR-03.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import AlertType, LogLevel
from app.models import Artist, BreakthroughAlert, MediaEvent, RegionalChart, Region, RuleParams
from app.services import aggregation as agg
from app.services.alerts import log, note

DEDUP_WINDOW_WEEKS = 8


def params(db: Session) -> RuleParams:
    return db.get(RuleParams, 1)


def active_media(db: Session, artist_id: str, week: int) -> MediaEvent | None:
    return db.scalar(select(MediaEvent).where(
        MediaEvent.artist_id == artist_id,
        MediaEvent.start_week <= week, MediaEvent.end_week >= week))


def confidence(pos: int, top_n: int, comp: float) -> float:
    margin = min(1.05, max(0.7, 0.7 + (top_n - pos + 1) / top_n * 0.35))
    return round(min(0.99, max(0.3, 0.9 * comp * margin)), 2)


def classify(db: Session, a: Artist, week: int, region: str, pos: int, p: RuleParams):
    lb = round(p.lookback_months * 4.345)
    bp = agg.best_pos(db, a.id, region, week, lb)
    obs = agg.baseline_plays(db, a, week, p.baseline_weeks)
    tru = agg.true_baseline(db, a, week, p.baseline_weeks)
    age = agg.catalog_months(db, a, week)
    debut = agg.months_between(a.debut_date, week)

    # FR-05 guard: наблюдаемая база занижена сбросом счётчика площадки
    if a.rights_platform and tru >= p.max_plays > obs:
        log(db, week, LogLevel.GUARD,
            f"FR-05 {a.name} ({region}): наблюдаемая база {obs} < {p.max_plays}, "
            f"истинная {tru} ≥ порога — площадка «{a.rights_platform}» сбросила счётчик. "
            f"Ложный прорыв ПРЕДОТВРАЩЁН.")
        return None

    if debut <= p.newcomer_months and bp > p.popular_rank:
        return (AlertType.NEWCOMER, "FR-02",
                [f"дебют {debut} мес ≤ {p.newcomer_months}",
                 f"ранее вне Top-{p.popular_rank} (best #{bp if bp != 999 else '—'})"])

    if age >= p.catalog_months and obs < p.max_plays and bp > p.popular_rank:
        return (AlertType.SLEEPER, "FR-01",
                [f"Top-{p.top_n}: #{pos}",
                 f"lookback {p.lookback_months} мес: best #{bp if bp != 999 else '—'}",
                 f"каталог {age} мес ≥ {p.catalog_months}",
                 f"база за {p.baseline_weeks} нед {obs} < {p.max_plays}"])

    me = active_media(db, a.id, week)
    gr = agg.growth(db, a, week, region)
    if me and gr >= p.growth_factor:
        return (AlertType.VIRAL, "FR-03",
                [f"событие «{me.title}» активно", f"рост ×{gr:.1f} ≥ {p.growth_factor}",
                 f"Top-{p.top_n}: #{pos}"])

    log(db, week, LogLevel.MISS,
        f"FR-01/02 {a.name} ({region}): #{pos} ✓, best #{bp if bp != 999 else '—'} "
        f"{'✓' if bp > p.popular_rank else '✗'}, каталог {age}м "
        f"{'✓' if age >= p.catalog_months else '✗'}, база {obs} "
        f"{'✓' if obs < p.max_plays else '✗'} → алерт не создан")
    return None


def evaluate(db: Session, week: int, regions: list[str] | None = None,
             quiet: bool = False) -> list[BreakthroughAlert]:
    p = params(db)
    regions = regions or [r.code for r in db.scalars(select(Region))]
    st = agg.state(db)
    comp = agg.completeness(db, week)
    created = []
    for region in regions:
        chart = db.scalar(select(RegionalChart).where(
            RegionalChart.region_code == region, RegionalChart.week == week))
        if chart is None:
            chart = agg.rebuild_chart(db, week, region)
        for entry in sorted(chart.entries, key=lambda e: e.position)[:p.top_n]:
            a = db.get(Artist, entry.artist_id)
            res = classify(db, a, week, region, entry.position, p)
            if res is None:
                continue
            atype, rule_id, checks = res
            dupe = db.scalar(select(BreakthroughAlert).where(
                BreakthroughAlert.artist_id == a.id, BreakthroughAlert.type == atype,
                BreakthroughAlert.region_code == region,
                BreakthroughAlert.status != "REJECTED",
                BreakthroughAlert.week >= week - DEDUP_WINDOW_WEEKS))
            if dupe:
                if not quiet:
                    log(db, week, LogLevel.MISS,
                        f"{rule_id} {a.name} ({region}): дедупликация — активный алерт "
                        f"за последние {DEDUP_WINDOW_WEEKS} нед.")
                continue
            st.alert_seq += 1
            al = BreakthroughAlert(
                id=f"AL-{st.alert_seq}", artist_id=a.id, chart_id=chart.id, type=atype.value,
                status="NEW", region_code=region, week=week, position=entry.position,
                confidence=confidence(entry.position, p.top_n, comp),
                provisional=comp < 1.0, revised=False, rule_id=rule_id)
            db.add(al)
            db.flush()
            text = f"Создан: {'; '.join(checks)}."
            if al.provisional:
                text += " Данные неполные (3/4) — provisional по FR-04."
            note(db, al, week, text)
            if not quiet:
                log(db, week, LogLevel.HIT,
                    f"{rule_id} {a.name} ({region}): {' · '.join(checks)} → ALERT {al.id}"
                    + (" [provisional]" if al.provisional else ""))
            created.append(al)
    db.commit()
    return created


def revalidate_provisional(db: Session, week: int) -> None:
    p = params(db)
    pending = db.scalars(select(BreakthroughAlert).where(
        BreakthroughAlert.provisional == True, BreakthroughAlert.week < week,  # noqa: E712
        BreakthroughAlert.status != "REJECTED")).all()
    for al in pending:
        chart = db.scalar(select(RegionalChart).where(
            RegionalChart.region_code == al.region_code, RegionalChart.week == week))
        pos = next((e.position for e in chart.entries if e.artist_id == al.artist_id), 999)
        al.provisional = False
        a = db.get(Artist, al.artist_id)
        if pos > p.top_n:
            al.status, al.revised = "REJECTED", True
            al.confidence = round(al.confidence * 0.4, 2)
            note(db, al, week, f"FR-04: поздние данные получены. Пересчёт: #{pos} вне "
                               f"Top-{p.top_n}. Алерт автоматически отозван.")
            log(db, week, LogLevel.REVOKE,
                f"FR-04 {al.id} {a.name}: полные данные изменили чарт (#{pos}) → ОТОЗВАН.")
        else:
            al.confidence = min(0.99, round(al.confidence / 0.75, 2))
            note(db, al, week, "FR-04: прорыв подтверждён полными данными (4/4).")
            log(db, week, LogLevel.HIT, f"FR-04 {al.id}: подтверждён, confidence {al.confidence}.")
    db.commit()


def decay_reports(db: Session, week: int) -> None:
    p = params(db)
    for me in db.scalars(select(MediaEvent)).all():
        related = db.scalars(select(BreakthroughAlert).where(
            BreakthroughAlert.artist_id == me.artist_id,
            BreakthroughAlert.type == "VIRAL",
            BreakthroughAlert.status != "REJECTED")).all()
        if not related:
            continue
        a = db.get(Artist, me.artist_id)
        if week == me.end_week + 1:
            for al in related:
                note(db, al, week, f"FR-03: событие «{me.title}» завершилось. Мониторинг "
                                   f"затухания {p.decay_weeks} нед. Потенциал скоропортящийся.")
            log(db, week, LogLevel.GUARD, f"FR-03 «{me.title}»: окно закрыто → мониторинг затухания.")
        if week == me.end_week + 1 + p.decay_weeks:
            peak = max(agg.plays_for(db, a, w, "MOW")
                       for w in range(me.start_week, me.end_week + 1)) or 1
            drop = round((1 - agg.plays_for(db, a, week, "MOW") / peak) * 100)
            verdict = ("Окно возможностей ≤ 2 нед: букингу действовать немедленно."
                       if drop > 40 else "Хвост устойчив: возможен переход в каталог.")
            for al in related:
                note(db, al, week, f"FR-03: отчёт затухания — падение {drop}% от пика. {verdict}")
            log(db, week, LogLevel.REVOKE if drop > 40 else LogLevel.HIT,
                f"FR-03 {a.name}: затухание {drop}% после «{me.title}». {verdict}")
    db.commit()