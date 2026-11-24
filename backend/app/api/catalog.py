import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import LogLevel
from app.database import get_db
from app.models import (Artist, BreakthroughAlert, MediaEvent, Platform, Region,
                        RegionalChart, RuleParams, Track, TrackPlatform)
from app.schemas import (ArtistOut, AvailabilityOut, ChartEntryOut, ChartOut,
                         ConfigIn, ConfigOut, MediaOut, TrackOut)
from app.services import aggregation as agg
from app.services.alerts import log
from app.services.rules import active_media, params

router = APIRouter(prefix="/api/v1", tags=["catalog"])


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    st = agg.state(db)
    return {"week": st.week, "week_label": agg.week_date(st.week).strftime("%d.%m.%Y"),
            "regions": [{"code": r.code, "name": r.name} for r in db.scalars(select(Region))],
            "platforms": [{"id": p.id, "name": p.name} for p in db.scalars(select(Platform))],
            "artists_count": len(db.scalars(select(Artist)).all()),
            "completeness": agg.completeness(db, st.week), "lag_active": bool(st.lag_platform)}


@router.get("/config", response_model=ConfigOut)
def get_config(db: Session = Depends(get_db)):
    return db.get(RuleParams, 1)


@router.put("/config", response_model=ConfigOut)
def put_config(body: ConfigIn, db: Session = Depends(get_db)):
    p = db.get(RuleParams, 1)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    log(db, agg.state(db).week, LogLevel.GUARD, f"NFR-02: конфигурация обновлена: {body.model_dump()}")
    return p


def build_chart(db: Session, region: str, week: int, platform: str, limit: int) -> ChartOut:
    ch = db.scalar(select(RegionalChart).where(
        RegionalChart.region_code == region, RegionalChart.week == week))
    if ch is None:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": f"Чарт {region}/{week} не найден"})
    p = params(db)
    entries = []
    for e in sorted(ch.entries, key=lambda x: x.position)[:limit]:
        a = db.get(Artist, e.artist_id)
        me = active_media(db, a.id, week)
        debut = agg.months_between(a.debut_date, week)
        tag = ("VIRAL" if me else "NEWCOMER" if debut <= p.newcomer_months
               else "SLEEPER?" if a.kind.startswith("sleeper") else "catalog")
        entries.append(ChartEntryOut(
            position=e.position, delta_position=e.delta_position, artist_id=a.id,
            artist_name=a.name, genres=json.loads(a.genres),
            plays=agg.plays_for(db, a, week, region, platform),
            spark=[agg.plays_for(db, a, w, region, platform) for w in range(max(1, week - 11), week + 1)],
            tag=tag))
    return ChartOut(region_code=region, week=week, completeness=ch.completeness,
                    provisional=ch.provisional, entries=entries)


@router.get("/charts/{region_code}", response_model=ChartOut)
def chart(region_code: str, week: int | None = None, platform: str = "all",
          limit: int = Query(10, le=50), db: Session = Depends(get_db)):
    return build_chart(db, region_code, week or agg.state(db).week, platform, limit)


@router.get("/charts/{region_code}/series")
def series(region_code: str, db: Session = Depends(get_db)):
    st = agg.state(db)
    ch = db.scalar(select(RegionalChart).where(
        RegionalChart.region_code == region_code, RegionalChart.week == st.week))
    top = sorted(ch.entries, key=lambda e: e.position)[:5]
    out = [{"artist_id": (a := db.get(Artist, e.artist_id)).id, "name": a.name,
            "values": [agg.plays_for(db, a, w, region_code) for w in range(1, st.week + 1)]}
           for e in top]
    media = [{"title": m.title, "start": m.start_week, "end": m.end_week}
             for m in db.scalars(select(MediaEvent))]
    return {"week": st.week, "series": out, "media": media}


def serialize_artist(db: Session, a: Artist, region: str) -> ArtistOut:
    st = agg.state(db)
    ch = db.scalar(select(RegionalChart).where(
        RegionalChart.region_code == region, RegionalChart.week == st.week))
    pos = next((e.position for e in ch.entries if e.artist_id == a.id), 999)
    tracks = db.scalars(select(Track).where(Track.artist_id == a.id)).all()
    tids = [t.id for t in tracks]
    availability = [AvailabilityOut(
        platform=p.name,
        available_since=min((tp.available_since for tp in db.scalars(
            select(TrackPlatform).where(TrackPlatform.track_id.in_(tids),
                                        TrackPlatform.platform_id == p.id))), default="—"),
        reset=bool(a.rights_platform == p.id))
        for p in db.scalars(select(Platform))]
    return ArtistOut(
        id=a.id, name=a.name, genres=json.loads(a.genres), debut_date=a.debut_date,
        debut_months=agg.months_between(a.debut_date, st.week),
        catalog_months=agg.catalog_months(db, a, st.week),
        plays_week=agg.plays_for(db, a, st.week, region),
        total_observed=agg.total_observed(db, a, st.week), true_total=a.true_total_plays,
        position=pos,
        spark=[agg.plays_for(db, a, w, region) for w in range(max(1, st.week - 15), st.week + 1)],
        tracks=[TrackOut(isrc=t.isrc, title=t.title, release_date=t.release_date, bpm=t.bpm, key=t.key)
                for t in tracks],
        availability=availability,
        alert_ids=[al.id for al in db.scalars(select(BreakthroughAlert)
                                              .where(BreakthroughAlert.artist_id == a.id))])


@router.get("/artists", response_model=list[ArtistOut])
def list_artists(region: str = "KRD", q: str | None = None, genre: str | None = None,
                 sort: str = Query("plays", pattern="^(plays|pos|name|debut)$"),
                 db: Session = Depends(get_db)):
    out = [serialize_artist(db, a, region) for a in db.scalars(select(Artist))]
    if q:
        out = [a for a in out if q.lower() in a.name.lower()]
    if genre:
        out = [a for a in out if genre in a.genres]
    keys = {"plays": lambda a: -a.plays_week, "pos": lambda a: a.position,
            "name": lambda a: a.name, "debut": lambda a: a.debut_date}
    return sorted(out, key=keys[sort])


@router.get("/artists/{artist_id}", response_model=ArtistOut)
def get_artist(artist_id: str, region: str = "KRD", db: Session = Depends(get_db)):
    a = db.get(Artist, artist_id)
    if not a:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Артист не найден"})
    return serialize_artist(db, a, region)


@router.get("/media-events", response_model=list[MediaOut])
def media_events(active: bool | None = None, db: Session = Depends(get_db)):
    st = agg.state(db)
    out = []
    for m in db.scalars(select(MediaEvent)):
        is_active = m.start_week <= st.week <= m.end_week
        if active is not None and is_active != active:
            continue
        a = db.get(Artist, m.artist_id)
        peak = max(agg.plays_for(db, a, w, "MOW") for w in range(m.start_week, m.end_week + 1)) or 1
        residual = round(agg.plays_for(db, a, st.week, "MOW") / peak, 2) if st.week > m.end_week else 1.0
        out.append(MediaOut(id=m.id, title=m.title, type=m.type, artist_id=a.id, artist_name=a.name,
                            track_title=db.get(Track, m.track_id).title, start_week=m.start_week,
                            end_week=m.end_week, note=m.note,
                            state="ACTIVE" if is_active else ("ENDED" if st.week > m.end_week else "PLANNED"),
                            residual_potential=residual))
    return out