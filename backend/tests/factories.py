"""Фикстуры: 4 платформы + массовка, чтобы lookback был осмысленным."""
import json

from app.models import (Artist, ListeningStat, MediaEvent, Platform, Region,
                        RuleParams, SimState, Track, TrackPlatform)
from app.services import aggregation as agg

SHARES = [("spotify", .32), ("yandex", .34), ("vk", .20), ("apple", .14)]


def base(db, week=42, top_n=5, popular_rank=3):
    db.add(Region(code="KRD", name="Краснодар"))
    for pid, sh in SHARES:
        db.add(Platform(id=pid, name=pid, share=sh))
    db.add(RuleParams(id=1, top_n=top_n, popular_rank=popular_rank))
    db.add(SimState(id=1, week=week))
    db.commit()


def artist(db, aid, debut="2019-01-01", avail="2019-02-01", kind="sleeper", true_total=1000):
    a = Artist(id=aid, name=aid.upper(), genres=json.dumps(["test"]), debut_date=debut,
               kind=kind, true_total_plays=true_total)
    db.add(a); db.flush()
    t = Track(artist_id=a.id, isrc=f"ISRC-{aid}", title="T", release_date=debut)
    db.add(t); db.flush()
    for pid, _ in SHARES:
        db.add(TrackPlatform(track_id=t.id, platform_id=pid, available_since=avail))
    db.commit()
    return a


def stats(db, a, week, plays):
    db.query(ListeningStat).filter_by(
        week=week, artist_id=a.id, region_code="KRD").delete()
    for pid, sh in SHARES:
        db.add(ListeningStat(week=week, artist_id=a.id, region_code="KRD",
                             platform_id=pid, plays=round(plays * sh)))
    db.commit()


def history(db, a, mapping):
    for w, p in mapping.items():
        stats(db, a, w, p)


def fillers(db, n=6, plays=10000, upto=42):
    """Массовка держит верх чарта: целевой артист вне popular_rank."""
    out = []
    for i in range(n):
        a = artist(db, f"f{i}", kind="filler", true_total=10**7)
        history(db, a, {w: plays for w in range(1, upto)})
        stats(db, a, upto, 100)
        out.append(a)
    return out


def charts(db, upto):
    for w in range(1, upto + 1):
        agg.rebuild_chart(db, w, "KRD")


def media(db, a, start=36, end=46):
    t = db.query(Track).filter_by(artist_id=a.id).first()
    m = MediaEvent(id="me-t", title="Тест-событие", type="SERIES", artist_id=a.id,
                   track_id=t.id, start_week=start, end_week=end)
    db.add(m); db.commit()
    return m