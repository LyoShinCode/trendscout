"""Движок наблюдения: недели, сценарии сложных случаев, журнал, сводка для дашборда."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import LogLevel
from app.database import Base, engine, get_db
from app.models import (Artist, BreakthroughAlert, ListeningStat, Platform,
                        RegionalChart, RuleLog, Track, TrackPlatform)
from app.schemas import LogOut
from app.services import aggregation as agg
from app.services import rules
from app.services.alerts import log

router = APIRouter(prefix="/api/v1", tags=["engine"])


def _baseline_by_platform(db: Session, artist_id: str, week: int, weeks: int) -> dict[str, int]:
    """Прослушивания за окно базы в разрезе площадок (без учёта сбросов)."""
    start = max(1, week - weeks)
    rows = db.execute(
        select(ListeningStat.platform_id, func.sum(ListeningStat.plays))
        .where(ListeningStat.artist_id == artist_id,
               ListeningStat.week >= start, ListeningStat.week < week)
        .group_by(ListeningStat.platform_id)
    ).all()
    return {pid: int(total or 0) for pid, total in rows}


def _week_by_platform(db: Session, artist_id: str, week: int, region: str) -> dict[str, int]:
    rows = db.execute(
        select(ListeningStat.platform_id, ListeningStat.plays)
        .where(ListeningStat.artist_id == artist_id,
               ListeningStat.week == week, ListeningStat.region_code == region)
    ).all()
    return {pid: int(v) for pid, v in rows}


@router.post("/detection/run", status_code=202)
def run_detection(week: int | None = None, region: str | None = None,
                  db: Session = Depends(get_db)):
    w = week or agg.state(db).week
    created = rules.evaluate(db, w, [region] if region else None)
    return {"accepted": True, "week": w, "alerts_created": len(created),
            "ids": [a.id for a in created],
            "deduplication": "artist+type+region, окно 8 недель"}


@router.post("/simulation/week")
def advance_week(db: Session = Depends(get_db)):
    st = agg.state(db)
    if st.week >= 52:
        return {"week": st.week, "finished": True, "alerts_created": []}
    st.week += 1
    db.commit()
    if st.lag_platform and (st.lag_until or 0) < st.week:
        log(db, st.week, LogLevel.HIT,
            "FR-04: буфер поздних данных слит в хранилище, полнота восстановлена.")
        st.lag_platform, st.lag_until = None, None
        db.commit()
        agg.rebuild_all(db, st.week)
        rules.revalidate_provisional(db, st.week)
    agg.rebuild_all(db, st.week)
    rules.decay_reports(db, st.week)
    created = rules.evaluate(db, st.week)
    return {"week": st.week, "alerts_created": [a.id for a in created]}


@router.post("/simulation/scenario/lag")
def scenario_lag(db: Session = Depends(get_db)):
    st = agg.state(db)
    if st.lag_platform:
        return {"already_active": True}
    st.lag_platform, st.lag_until = "yandex", st.week + 1
    db.commit()
    agg.rebuild_all(db, st.week)
    log(db, st.week, LogLevel.GUARD,
        "FR-04: «Яндекс Музыка» не прислала выгрузку в срок 72 часа. "
        "Период помечен предварительным, полнота 3 из 4.")
    created = rules.evaluate(db, st.week)
    return {"scenario": "lag", "provisional_alerts": [a.id for a in created]}


@router.post("/simulation/scenario/rights")
def scenario_rights(db: Session = Depends(get_db)):
    """Покупка прав на каталог: подбираем исполнителя, на котором предохранитель
    FR-05 действительно сработает и останется в топе после обнуления счётчика."""
    st = agg.state(db)
    p = rules.params(db)
    platforms = sorted(db.scalars(select(Platform)).all(), key=lambda x: -x.share)
    artists = {a.id: a for a in db.scalars(select(Artist)).all()}
    charts = db.scalars(select(RegionalChart).where(RegionalChart.week == st.week)).all()

    candidate = None
    for ch in charts:
        entries = sorted(ch.entries, key=lambda e: e.position)
        current = {e.artist_id: e.plays for e in entries}
        for e in entries[:p.top_n]:
            a = artists.get(e.artist_id)
            if a is None or a.rights_platform:
                continue
            base = _baseline_by_platform(db, a.id, st.week, p.baseline_weeks)
            true_base = sum(base.values())
            if true_base < p.max_plays:
                continue
            cur = _week_by_platform(db, a.id, st.week, ch.region_code)
            for pl in platforms:
                observed = true_base - base.get(pl.id, 0)
                if observed >= p.max_plays:
                    continue
                new_plays = sum(cur.values()) - cur.get(pl.id, 0)
                rank = 1 + sum(1 for aid, v in current.items() if aid != a.id and v > new_plays)
                if rank <= p.top_n:
                    candidate = (a, pl, ch.region_code, true_base, observed)
                    break
            if candidate:
                break
        if candidate:
            break

    if candidate is None:
        log(db, st.week, LogLevel.MISS,
            "FR-05: в текущем топе нет исполнителя, у которого обнуление счётчика площадки "
            "опустит наблюдаемую базу ниже порога при сохранении места в топе. "
            "Сценарий не применён — продвиньте неделю и повторите.")
        return {"scenario": "rights", "applied": False,
                "message": "Подходящий исполнитель не найден в текущем топе. "
                           "Продвиньте неделю и повторите."}

    a, pl, region, true_base, observed = candidate
    a.rights_platform = pl.id
    a.rights_week = max(1, st.week - p.baseline_weeks)
    for tp in db.scalars(
        select(TrackPlatform).join(Track, TrackPlatform.track_id == Track.id)
        .where(Track.artist_id == a.id, TrackPlatform.platform_id == pl.id)
    ):
        tp.available_since = agg.week_date(a.rights_week).isoformat()
    db.commit()

    agg.rebuild_all(db, st.week)
    log(db, st.week, LogLevel.GUARD,
        f"FR-05: «{pl.name}» приобрела права на каталог «{a.name}» и обнулила счётчик. "
        f"Истинная база за {p.baseline_weeks} нед — {true_base}, "
        f"наблюдаемая — {observed}, порог — {p.max_plays}.")
    rules.evaluate(db, st.week)
    return {"scenario": "rights", "applied": True, "artist": a.name, "platform": pl.name,
            "region": region, "true_baseline": true_base,
            "observed_baseline": observed, "threshold": p.max_plays}


@router.post("/simulation/reset")
def reset(db: Session = Depends(get_db)):
    from app.seed import generate
    db.expunge_all()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    generate(db)
    return {"reset": True}


@router.get("/log", response_model=list[LogOut])
def get_log(limit: int = Query(42, le=200), db: Session = Depends(get_db)):
    return db.scalars(select(RuleLog).order_by(RuleLog.id.desc()).limit(limit)).all()


@router.get("/dashboard")
def dashboard(region: str = "KRD", db: Session = Depends(get_db)):
    from app.api.catalog import build_chart, media_events
    st = agg.state(db)
    artists = db.scalars(select(Artist)).all()
    active = len(db.scalars(select(BreakthroughAlert)
                            .where(BreakthroughAlert.status.in_(["NEW", "IN_REVIEW"]))).all())
    recent = db.scalars(select(BreakthroughAlert)
                        .order_by(BreakthroughAlert.week.desc(), BreakthroughAlert.id.desc())
                        .limit(3)).all()
    return {"week": st.week, "week_label": agg.week_date(st.week).strftime("%d.%m.%Y"),
            "kpis": {"events": sum(agg.total_observed(db, a, st.week + 1) for a in artists),
                     "artists": len(artists), "active_alerts": active},
            "completeness": agg.completeness(db, st.week),
            "chart": build_chart(db, region, st.week, "all", 10),
            "media": media_events(None, db), "log": get_log(30, db),
            "recent_alerts": [{"id": r.id, "artist_id": r.artist_id,
                               "artist_name": db.get(Artist, r.artist_id).name,
                               "type": r.type, "status": r.status, "region_code": r.region_code,
                               "position": r.position, "rule_id": r.rule_id,
                               "provisional": r.provisional} for r in recent]}