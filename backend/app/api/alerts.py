from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Artist, BreakthroughAlert
from app.schemas import AlertOut, AlertPatch
from app.services import aggregation as agg
from app.services.alerts import change_status

router = APIRouter(prefix="/api/v1", tags=["alerts"])


def serialize(db: Session, al: BreakthroughAlert) -> AlertOut:
    out = AlertOut.model_validate(al)
    out.artist_name = db.get(Artist, al.artist_id).name
    return out


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(type: str | None = None, status: str | None = None, region: str | None = None,
                q: str | None = None, revised: bool | None = None,
                sort: str = Query("date", pattern="^(date|conf|name)$"),
                db: Session = Depends(get_db)):
    rows = db.scalars(select(BreakthroughAlert)).all()
    if type: rows = [r for r in rows if r.type == type]
    if status: rows = [r for r in rows if r.status == status]
    if region: rows = [r for r in rows if r.region_code == region]
    if revised is not None: rows = [r for r in rows if r.revised == revised]
    out = [serialize(db, r) for r in rows]
    if q:
        out = [r for r in out if q.lower() in r.artist_name.lower()
               or q.lower() in r.id.lower() or q.lower() in r.region_code.lower()]
    keys = {"date": lambda r: (-r.week, r.id), "conf": lambda r: -r.confidence,
            "name": lambda r: r.artist_name}
    return sorted(out, key=keys[sort])


@router.get("/alerts/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: str, db: Session = Depends(get_db)):
    al = db.get(BreakthroughAlert, alert_id)
    if not al:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Алерт не найден"})
    return serialize(db, al)


@router.patch("/alerts/{alert_id}", response_model=AlertOut)
def patch_alert(alert_id: str, body: AlertPatch, db: Session = Depends(get_db)):
    al = db.get(BreakthroughAlert, alert_id)
    if not al:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Алерт не найден"})
    change_status(db, al, body.status, agg.state(db).week, body.reason)
    return serialize(db, al)


@router.delete("/alerts/{alert_id}")
def delete_alert(alert_id: str, db: Session = Depends(get_db)):
    al = db.get(BreakthroughAlert, alert_id)
    if not al:
        raise HTTPException(404, {"code": "NOT_FOUND", "message": "Алерт не найден"})
    db.delete(al)
    db.commit()
    return {"deleted": alert_id}