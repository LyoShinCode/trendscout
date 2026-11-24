"""Проверка сборки: файлы фронтенда/доков/презентации + смоук всех эндпоинтов.
Запуск: python check_stage5.py
"""
from fastapi.testclient import TestClient

from app.config import DOCS_DIR, FRONTEND_DIR, PRESENTATION_DIR, REPO_DIR
from app.main import app

FE = ["index.html", "css/tokens.css", "css/base.css", "css/views.css",
      "js/main.js", "js/router.js", "js/store.js", "js/api.js", "js/ui.js",
      "js/sound.js", "js/md.js", "js/views/dashboard.js", "js/views/alerts.js",
      "js/views/artists.js", "js/views/docs.js"]

DOCS = ["01-vision-scope.md", "02-domain-model.md", "03-requirements.md",
        "04-algorithm.md", "05-architecture.md", "06-api.md", "07-use-case.md",
        "08-bpmn.md", "09-iar-report.md", "diagrams/process.bpmn"]

GET = ["/api/v1/meta", "/api/v1/config", "/api/v1/dashboard?region=KRD",
       "/api/v1/charts/KRD", "/api/v1/charts/KRD/series", "/api/v1/artists",
       "/api/v1/artists/a1", "/api/v1/alerts", "/api/v1/media-events", "/api/v1/log",
       "/", "/js/main.js", "/css/tokens.css", "/presentation/", "/sa-docs/01-vision-scope.md"]


def files_block(title, base, names):
    print(f"\n{title}")
    ok = True
    for n in names:
        p = base / n
        good = p.exists() and p.stat().st_size > 0
        ok &= good
        size = p.stat().st_size if p.exists() else 0
        print(f"  [{'OK  ' if good else 'MISS'}] {n:<34} {size:>7} B")
    return ok


def main():
    ok = files_block("ФРОНТЕНД", FRONTEND_DIR, FE)
    ok &= files_block("ДОКУМЕНТАЦИЯ", DOCS_DIR, DOCS)
    ok &= files_block("ПРЕЗЕНТАЦИЯ", PRESENTATION_DIR, ["index.html"])

    print("\nСОДЕРЖИМОЕ (не заглушки ли)")
    checks = []
    idx = FRONTEND_DIR / "index.html"
    checks.append(("index.html подключает ES-модуль",
                   idx.exists() and 'js/main.js' in idx.read_text(encoding="utf-8")))
    pres = PRESENTATION_DIR / "index.html"
    checks.append(("презентация содержит слайды ИАР",
                   pres.exists() and "Цели и задачи" in pres.read_text(encoding="utf-8")))
    dash = FRONTEND_DIR / "js/views/dashboard.js"
    checks.append(("dashboard: слайдеры baseline/popular_rank",
                   dash.exists() and "baseline_weeks" in dash.read_text(encoding="utf-8")))
    for name, good in checks:
        ok &= good
        print(f"  [{'OK  ' if good else 'FAIL'}] {name}")

    print("\nСМОУК ЭНДПОИНТОВ")
    with TestClient(app) as c:
        for url in GET:
            try:
                r = c.get(url)
                good = r.status_code == 200
            except Exception as e:
                good, r = False, None
                print(f"  [FAIL] {url:<40} {type(e).__name__}: {e}")
                ok = False
                continue
            ok &= good
            print(f"  [{'OK  ' if good else 'FAIL'}] {url:<40} {r.status_code}")
        r = c.post("/api/v1/detection/run", json={})
        print(f"  [{'OK  ' if r.status_code == 202 else 'FAIL'}] POST /detection/run{'':<21} {r.status_code}")
        ok &= r.status_code == 202

    print("\nСБОРКА ГОТОВА К ЗАЩИТЕ" if ok else "\nЕСТЬ ПРОБЕЛЫ — см. MISS/FAIL выше")


if __name__ == "__main__":
    main()