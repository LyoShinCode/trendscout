"""Контрактные тесты на изолированной БД (не трогают демо-данные)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import (AlertNote, Artist, BreakthroughAlert, RegionalChart,
                        RuleParams, SimState)


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    db.add(RuleParams(id=1))
    db.add(SimState(id=1, week=42))
    db.add(Artist(id="a2", name="Neon Pravda", genres="[]",
                  debut_date="2026-05-20", kind="newcomer"))
    db.add(RegionalChart(id=1, region_code="MOW", week=42))
    db.flush()
    db.add(BreakthroughAlert(id="AL-1043", artist_id="a2", chart_id=1, type="NEWCOMER",
                             status="NEW", region_code="MOW", week=42, position=4,
                             confidence=.88, provisional=False, revised=False, rule_id="FR-02"))
    db.add(AlertNote(alert_id="AL-1043", week=42, text="Создан"))
    db.commit()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    db.close()


def test_invalid_transition_409(client):
    r = client.patch("/api/v1/alerts/AL-1043", json={"status": "CONFIRMED"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "INVALID_STATUS_TRANSITION"


def test_valid_transition_and_audit(client):
    r = client.patch("/api/v1/alerts/AL-1043", json={"status": "IN_REVIEW"})
    assert r.status_code == 200 and r.json()["status"] == "IN_REVIEW"
    assert len(r.json()["notes"]) >= 2


def test_contract_paths(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ("/api/v1/charts/{region_code}", "/api/v1/artists/{artist_id}", "/api/v1/alerts",
              "/api/v1/alerts/{alert_id}", "/api/v1/media-events", "/api/v1/detection/run"):
        assert p in paths