"""ORM-модель = доменная модель v2 (docs/02-domain-model.md).

Решения:
  D-01 Alert: M:1 к Artist, статус-машина вместо булева флага.
  D-02 ChartEntry реляционно, а не JSON-blob.
  D-03 Junction-таблицы с атрибутами (available_since, link_type).
  D-04 ISRC — natural key трека.
  D-05 ListeningEvent в MVP = недельный батч listening_stats;
       в бою — сырые события с партиционированием по месяцам.
"""
from sqlalchemy import (Boolean, Column, Float, ForeignKey, Integer, String,
                        Text, UniqueConstraint)
from sqlalchemy.orm import relationship

from app.database import Base


class Artist(Base):
    __tablename__ = "artists"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    genres = Column(String, nullable=False)          # JSON-список
    debut_date = Column(String, nullable=False)      # ISO date
    kind = Column(String, nullable=False)            # профиль генератора
    true_total_plays = Column(Integer, default=0)    # истинная база (FR-05)
    rights_platform = Column(String, nullable=True)  # сценарий покупки прав
    rights_week = Column(Integer, nullable=True)
    tracks = relationship("Track", back_populates="artist", cascade="all, delete-orphan")


class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    artist_id = Column(String, ForeignKey("artists.id"), nullable=False)
    isrc = Column(String, nullable=False, unique=True)   # D-04 natural key
    title = Column(String, nullable=False)
    release_date = Column(String, nullable=False)
    bpm = Column(Integer)
    key = Column(String)
    artist = relationship("Artist", back_populates="tracks")


class Platform(Base):
    __tablename__ = "platforms"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    share = Column(Float, nullable=False)            # доля площадки в батче


class Region(Base):
    __tablename__ = "regions"
    code = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class TrackPlatform(Base):
    """Junction M:M Track↔Platform с атрибутом доступности (FR-01 / FR-05)."""
    __tablename__ = "track_platform"
    track_id = Column(Integer, ForeignKey("tracks.id"), primary_key=True)
    platform_id = Column(String, ForeignKey("platforms.id"), primary_key=True)
    external_id = Column(String)
    available_since = Column(String, nullable=False)


class ListeningStat(Base):
    """Недельный батч площадки — структурированные данные для алгоритма."""
    __tablename__ = "listening_stats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    week = Column(Integer, nullable=False, index=True)
    artist_id = Column(String, ForeignKey("artists.id"), nullable=False)
    region_code = Column(String, ForeignKey("regions.code"), nullable=False)
    platform_id = Column(String, ForeignKey("platforms.id"), nullable=False)
    plays = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("week", "artist_id", "region_code", "platform_id"),)


class RegionalChart(Base):
    __tablename__ = "regional_charts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    region_code = Column(String, ForeignKey("regions.code"), nullable=False)
    week = Column(Integer, nullable=False, index=True)
    completeness = Column(Float, default=1.0)
    provisional = Column(Boolean, default=False)
    entries = relationship("ChartEntry", back_populates="chart",
                           cascade="all, delete-orphan", order_by="ChartEntry.position")
    __table_args__ = (UniqueConstraint("region_code", "week"),)


class ChartEntry(Base):
    """D-02: позиции реляционно, чтобы работал SQL по динамике."""
    __tablename__ = "chart_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chart_id = Column(Integer, ForeignKey("regional_charts.id"), nullable=False)
    artist_id = Column(String, ForeignKey("artists.id"), nullable=False)
    position = Column(Integer, nullable=False)
    plays = Column(Integer, nullable=False)
    delta_position = Column(Integer, default=0)
    chart = relationship("RegionalChart", back_populates="entries")


class MediaEvent(Base):
    __tablename__ = "media_events"
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    type = Column(String, nullable=False)
    artist_id = Column(String, ForeignKey("artists.id"), nullable=False)
    track_id = Column(Integer, ForeignKey("tracks.id"), nullable=False)
    start_week = Column(Integer, nullable=False)
    end_week = Column(Integer, nullable=False)
    note = Column(String)


class TrackMediaEvent(Base):
    __tablename__ = "track_media_events"
    track_id = Column(Integer, ForeignKey("tracks.id"), primary_key=True)
    media_event_id = Column(String, ForeignKey("media_events.id"), primary_key=True)
    link_type = Column(String, nullable=False)       # soundtrack / ugc_trend / live


class BreakthroughAlert(Base):
    __tablename__ = "alerts"
    id = Column(String, primary_key=True)
    artist_id = Column(String, ForeignKey("artists.id"), nullable=False)
    chart_id = Column(Integer, ForeignKey("regional_charts.id"), nullable=False)
    type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="NEW")
    region_code = Column(String, nullable=False)
    week = Column(Integer, nullable=False)
    position = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    provisional = Column(Boolean, default=False)
    revised = Column(Boolean, default=False)
    rule_id = Column(String, nullable=False)
    notes = relationship("AlertNote", back_populates="alert",
                         cascade="all, delete-orphan", order_by="AlertNote.id")


class AlertNote(Base):
    """Audit trail (NFR-05)."""
    __tablename__ = "alert_notes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String, ForeignKey("alerts.id"), nullable=False)
    week = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    alert = relationship("BreakthroughAlert", back_populates="notes")


class RuleLog(Base):
    __tablename__ = "rule_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    week = Column(Integer, nullable=False)
    level = Column(String, nullable=False)
    message = Column(Text, nullable=False)


class RuleParams(Base):
    """Единая строка конфигурации порогов (NFR-02: смена без redeploy)."""
    __tablename__ = "rule_params"
    id = Column(Integer, primary_key=True, default=1)
    top_n = Column(Integer, default=5)
    lookback_months = Column(Integer, default=24)
    max_plays = Column(Integer, default=50000)
    catalog_months = Column(Integer, default=12)
    newcomer_months = Column(Integer, default=6)
    decay_weeks = Column(Integer, default=4)
    growth_factor = Column(Float, default=2.5)
    baseline_weeks = Column(Integer, default=8)   # окно оценки исторической базы
    baseline_weeks = Column(Integer, default=8)    # окно оценки базы (D-09)
    popular_rank = Column(Integer, default=50)     # порог «был популярен» (D-10)


class SimState(Base):
    __tablename__ = "sim_state"
    id = Column(Integer, primary_key=True, default=1)
    week = Column(Integer, default=42)
    lag_platform = Column(String, nullable=True)
    lag_until = Column(Integer, nullable=True)
    alert_seq = Column(Integer, default=1044)