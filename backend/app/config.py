"""Настройки приложения. Пороги правил живут в БД (NFR-02), а не здесь."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
REPO_DIR = BASE_DIR.parent                                 # trendscout/
DB_PATH = BASE_DIR / "trendscout.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

SEED = 20261109          # воспроизводимость синтетических данных
WEEKS = 52               # горизонт симуляции
START_WEEK = 42          # неделя старта демо
END_DATE = (2026, 11, 9) # дата последней недели горизонта

FRONTEND_DIR = REPO_DIR / "frontend"
DOCS_DIR = REPO_DIR / "docs"
PRESENTATION_DIR = REPO_DIR / "presentation"