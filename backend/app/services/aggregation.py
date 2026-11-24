"""Агрегация батчей в региональные чарты. Шаг 1 алгоритма RB-DETECT.
Часть A: календарь, состояние, чтение батчей с учётом FR-04 / FR-05.
"""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import END_DATE, WEEKS
from app.models import Artist, ListeningStat, Platform, SimState


def week_date(week: int) -> date:
    y, m, d = END_DATE
    return date(y, m, d) - timedelta(days=(WEEKS - week) * 7)


def months_between(iso: str, week: int) -> int:
    y, m, d = map(int, iso.split("-"))
    return max(0, round((week_date(week) - date(y, m, d)).days / 30.44))


def state(db: Session) -> SimState:
    return db.get(SimState, 1)


def platform_shares(db: Session) -> dict[str, float]:
    return {p.id: p.share for p in db.scalars(select(Platform))}


def plays_for(db: Session, artist: Artist, week: int, region: str,
              platform: str = "all") -> int:
    """Прослушивания с учётом задержки данных (FR-04) и сброса прав (FR-05)."""
    if week < 1 or week > WEEKS:
        return 0
    rows = db.execute(
        select(ListeningStat.platform_id, ListeningStat.plays)
        .where(ListeningStat.week == week,
               ListeningStat.artist_id == artist.id,
               ListeningStat.region_code == region)
    ).all()
    shares = platform_shares(db)
    per = {pid: 0 for pid in shares}
    for pid, plays in rows:
        per[pid] = plays

    st = state(db)
    if st.lag_platform and week <= (st.lag_until or 0):
        per[st.lag_platform] = 0                      # батч не пришёл в SLA
    if artist.rights_platform and week >= (artist.rights_week or 10**9):
        per[artist.rights_platform] = 0               # счётчик площадки сброшен

    if platform != "all":
        return per.get(platform, 0)
    return sum(per.values())


def completeness(db: Session, week: int) -> float:
    st = state(db)
    return 0.75 if (st.lag_platform and week <= (st.lag_until or 0)) else 1.0

def baseline_plays(db: Session, artist: Artist, week: int, window: int) -> int:
    """База ДО окна детекции: сумма за `window` недель перед текущей.

    Учитывает сброс прав (FR-05): после покупки прав наблюдаемая база занижена,
    что и позволяет guard-правилу отличить ложный прорыв от настоящего.
    """
    total = 0
    for w in range(max(1, week - window), week):
        for code in _region_codes(db):
            total += plays_for(db, artist, w, code)
    return total


def true_baseline(db: Session, artist: Artist, week: int, window: int) -> int:
    """Истинная база за то же окно — без учёта сбросов и задержек."""
    from sqlalchemy import func as sa_func
    row = db.scalar(
        select(sa_func.sum(ListeningStat.plays)).where(
            ListeningStat.artist_id == artist.id,
            ListeningStat.week >= max(1, week - window),
            ListeningStat.week < week)
    )
    return row or 0


def _region_codes(db: Session) -> list[str]:
    from app.models import Region
    return [r.code for r in db.scalars(select(Region))]

# ============ ЧАСТЬ B: агрегация и признаки ============
from statistics import median

from sqlalchemy import func
from sqlalchemy.orm import Session as _S

from app.models import ChartEntry, Region, RegionalChart, Track, TrackPlatform


def rebuild_chart(db: Session, week: int, region: str) -> RegionalChart:
    """Пересчёт чарта недели. Исторические недели не вызываем (D-07)."""
    artists = db.scalars(select(Artist)).all()
    ranked = sorted(((a, plays_for(db, a, week, region)) for a in artists),
                    key=lambda t: t[1], reverse=True)
    prev = db.scalar(select(RegionalChart).where(
        RegionalChart.region_code == region, RegionalChart.week == week - 1))
    prev_pos = {e.artist_id: e.position for e in prev.entries} if prev else {}

    chart = db.scalar(select(RegionalChart).where(
        RegionalChart.region_code == region, RegionalChart.week == week))
    if chart is None:
        chart = RegionalChart(region_code=region, week=week)
        db.add(chart)
        db.flush()
    else:
        db.query(ChartEntry).filter(ChartEntry.chart_id == chart.id).delete()
        db.flush()
    comp = completeness(db, week)
    chart.completeness, chart.provisional = comp, comp < 1.0
    for i, (a, plays) in enumerate(ranked, start=1):
        db.add(ChartEntry(chart_id=chart.id, artist_id=a.id, position=i, plays=plays,
                          delta_position=prev_pos.get(a.id, i) - i))
    db.commit()
    db.refresh(chart)
    return chart


def rebuild_all(db: Session, week: int) -> None:
    for r in db.scalars(select(Region)):
        rebuild_chart(db, week, r.code)


def best_pos(db: Session, artist_id: str, region: str, week: int, lookback_weeks: int) -> int:
    row = db.scalar(
        select(func.min(ChartEntry.position))
        .join(RegionalChart, ChartEntry.chart_id == RegionalChart.id)
        .where(ChartEntry.artist_id == artist_id,
               RegionalChart.region_code == region,
               RegionalChart.week >= max(1, week - lookback_weeks),
               RegionalChart.week < week))
    return row if row is not None else 999


def total_observed(db: Session, artist: Artist, week: int) -> int:
    rows = db.execute(
        select(ListeningStat.week, ListeningStat.platform_id, func.sum(ListeningStat.plays))
        .where(ListeningStat.artist_id == artist.id, ListeningStat.week < week)
        .group_by(ListeningStat.week, ListeningStat.platform_id)).all()
    total = 0
    for w, pid, plays in rows:
        if artist.rights_platform and pid == artist.rights_platform and w >= (artist.rights_week or 10**9):
            continue
        total += plays
    return total


def growth(db: Session, artist: Artist, week: int, region: str) -> float:
    prev = [plays_for(db, artist, week - k, region) for k in (1, 2, 3, 4)]
    return plays_for(db, artist, week, region) / (median(prev) or 1)


def catalog_months(db: Session, artist: Artist, week: int) -> int:
    dates = db.scalars(select(TrackPlatform.available_since)
                       .join(Track, TrackPlatform.track_id == Track.id)
                       .where(Track.artist_id == artist.id)).all()
    return months_between(min(dates), week) if dates else 0