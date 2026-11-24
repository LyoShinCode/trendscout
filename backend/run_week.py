"""Прокрутка недели без браузера: python run_week.py --weeks 3"""
import sys

from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import Artist, RegionalChart, RuleLog
from app.services import aggregation as agg
from app.services import rules


def main():
    n = int(sys.argv[sys.argv.index("--weeks") + 1]) if "--weeks" in sys.argv else 1
    init_db()
    db = SessionLocal()
    try:
        for _ in range(n):
            st = agg.state(db)
            if st.week >= 52:
                print("Горизонт 52 достигнут")
                break
            st.week += 1
            db.commit()
            if st.lag_platform and (st.lag_until or 0) < st.week:
                st.lag_platform, st.lag_until = None, None
                db.commit()
                agg.rebuild_all(db, st.week)
                rules.revalidate_provisional(db, st.week)
            agg.rebuild_all(db, st.week)
            rules.decay_reports(db, st.week)
            created = rules.evaluate(db, st.week)
            print(f"\n=== НЕДЕЛЯ {st.week} ({agg.week_date(st.week)}) ===")
            ch = db.scalar(select(RegionalChart).where(
                RegionalChart.region_code == "KRD", RegionalChart.week == st.week))
            print("Top-5 Краснодар:")
            for e in sorted(ch.entries, key=lambda x: x.position)[:5]:
                name = db.get(Artist, e.artist_id).name
                print(f"  #{e.position} {name:<18} {e.plays:>8,}".replace(",", " "))
            print(f"Новых алертов: {len(created)}")
            for a in created:
                print(f"  {a.id} {a.type} {db.get(Artist, a.artist_id).name} "
                      f"({a.region_code}) conf={a.confidence} {a.rule_id}")
        print("\nПоследние записи журнала:")
        for l in db.scalars(select(RuleLog).order_by(RuleLog.id.desc()).limit(8)):
            print(f"  [{l.level}] {l.message}")
    finally:
        db.close()


if __name__ == "__main__":
    main()