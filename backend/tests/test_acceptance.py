"""Трассировка AC (docs/03-requirements.md) → автотесты."""
from app.models import BreakthroughAlert, RuleParams
from app.services import aggregation as agg
from app.services import rules
from tests import factories as f


def test_ac_01_1_sleeper_fires(db):
    f.base(db); f.fillers(db)
    a = f.artist(db, "t1", true_total=20000)
    f.history(db, a, {w: 100 for w in range(1, 42)}); f.stats(db, a, 42, 50000)
    f.charts(db, 42)
    created = rules.evaluate(db, 42, ["KRD"])
    assert len(created) == 1
    assert created[0].type == "SLEEPER" and created[0].rule_id == "FR-01"


def test_ac_01_2_recent_top_blocks(db):
    f.base(db); f.fillers(db)
    a = f.artist(db, "t1", true_total=20000)
    f.history(db, a, {w: 100 for w in range(1, 42)})
    f.stats(db, a, 32, 90000); f.stats(db, a, 42, 50000)
    f.charts(db, 42)
    assert rules.evaluate(db, 42, ["KRD"]) == []


def test_ac_01_3_thresholds_configurable(db):
    f.base(db); f.fillers(db)
    a = f.artist(db, "t1", true_total=41000)
    f.history(db, a, {w: 5000 for w in range(1, 42)}); f.stats(db, a, 42, 50000)
    f.charts(db, 42)
    assert len(rules.evaluate(db, 42, ["KRD"])) == 1        # база 40 000 < 50 000
    db.get(RuleParams, 1).max_plays = 30000
    db.query(BreakthroughAlert).delete(); db.commit()
    assert rules.evaluate(db, 42, ["KRD"]) == []            # порог изменён без кода


def test_ac_02_1_newcomer_fires(db):
    f.base(db); f.fillers(db)
    a = f.artist(db, "t1", debut="2026-06-01", avail="2026-06-05",
                 kind="newcomer", true_total=500)
    f.history(db, a, {w: 100 for w in range(25, 42)}); f.stats(db, a, 42, 50000)
    f.charts(db, 42)
    assert rules.evaluate(db, 42, ["KRD"])[0].type == "NEWCOMER"


def test_ac_02_2_debut_7_months_not_newcomer(db):
    f.base(db); f.fillers(db)
    a = f.artist(db, "t1", debut="2026-01-15", avail="2026-01-20",
                 kind="newcomer", true_total=500)
    f.history(db, a, {w: 100 for w in range(15, 42)}); f.stats(db, a, 42, 50000)
    f.charts(db, 42)
    assert rules.evaluate(db, 42, ["KRD"]) == []


def test_ac_03_1_viral_with_media(db):
    f.base(db); f.fillers(db)
    a = f.artist(db, "t1", debut="2018-01-01", avail="2018-02-01",
                 kind="viral", true_total=10**6)
    f.history(db, a, {w: 12000 for w in range(1, 42)}); f.stats(db, a, 42, 60000)
    f.media(db, a); f.charts(db, 42)
    created = rules.evaluate(db, 42, ["KRD"])
    assert created[0].type == "VIRAL" and created[0].rule_id == "FR-03"


def test_ac_03_2_no_media_no_viral(db):
    f.base(db); f.fillers(db)
    a = f.artist(db, "t1", debut="2018-01-01", avail="2018-02-01",
                 kind="viral", true_total=10**6)
    f.history(db, a, {w: 12000 for w in range(1, 42)}); f.stats(db, a, 42, 60000)
    f.charts(db, 42)
    assert rules.evaluate(db, 42, ["KRD"]) == []


def test_ac_04_1_lag_provisional_then_revoke(db):
    f.base(db); crowd = f.fillers(db)
    a = f.artist(db, "t1", true_total=20000)
    f.history(db, a, {w: 100 for w in range(1, 42)}); f.stats(db, a, 42, 50000)
    f.charts(db, 42)
    st = agg.state(db); st.lag_platform, st.lag_until = "yandex", 42; db.commit()
    agg.rebuild_chart(db, 42, "KRD")
    created = rules.evaluate(db, 42, ["KRD"])
    assert created and created[0].provisional is True
    st.lag_platform, st.lag_until = None, None; st.week = 43; db.commit()
    f.stats(db, a, 43, 100)
    for x in crowd:
        f.stats(db, x, 43, 10000)
    agg.rebuild_chart(db, 43, "KRD")
    rules.revalidate_provisional(db, 43)
    db.refresh(created[0])
    assert created[0].status == "REJECTED" and created[0].revised is True


def test_ac_05_1_rights_guard_prevents(db):
    f.base(db); f.fillers(db)
    a = f.artist(db, "t1", true_total=900000)
    f.history(db, a, {w: 7000 for w in range(1, 42)}); f.stats(db, a, 42, 7000)
    a.rights_platform, a.rights_week = "vk", 30
    db.commit()
    f.charts(db, 42)
    assert rules.evaluate(db, 42, ["KRD"]) == []