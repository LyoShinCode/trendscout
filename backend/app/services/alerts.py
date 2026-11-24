"""Workflow алертов, audit trail, журнал правил (NFR-05)."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.enums import AlertStatus, LogLevel
from app.models import AlertNote, BreakthroughAlert, RuleLog

# UC-01: допустимые переходы статус-машины
TRANSITIONS: dict[str, set[str]] = {
    AlertStatus.NEW: {AlertStatus.IN_REVIEW, AlertStatus.REJECTED},
    AlertStatus.IN_REVIEW: {AlertStatus.CONFIRMED, AlertStatus.REJECTED},
    AlertStatus.CONFIRMED: {AlertStatus.IN_REVIEW},
    AlertStatus.REJECTED: {AlertStatus.NEW},
}

STATUS_RU = {
    "NEW": "Новый", "IN_REVIEW": "На ревью",
    "CONFIRMED": "Подтверждён", "REJECTED": "Отклонён",
}


def log(db: Session, week: int, level: LogLevel, message: str) -> None:
    db.add(RuleLog(week=week, level=level.value, message=message))
    db.commit()


def note(db: Session, alert: BreakthroughAlert, week: int, text: str) -> None:
    db.add(AlertNote(alert_id=alert.id, week=week, text=text))
    db.commit()


def change_status(db: Session, alert: BreakthroughAlert, new: str,
                  week: int, reason: str | None = None, actor: str = "A&R") -> BreakthroughAlert:
    if new not in TRANSITIONS.get(alert.status, set()):
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_STATUS_TRANSITION",
                    "message": f"Переход {alert.status} → {new} недопустим (UC-01)"},
        )
    old = alert.status
    alert.status = new
    text = f"Статус: {STATUS_RU[old]} → {STATUS_RU[new]} (оператор: {actor})."
    if reason:
        text += f" Причина: {reason}"
    note(db, alert, week, text)
    db.commit()
    return alert