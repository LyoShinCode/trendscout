from pydantic import BaseModel, ConfigDict, Field
from app.core.enums import AlertStatus, AlertType


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    top_n: int
    lookback_months: int
    max_plays: int
    catalog_months: int
    newcomer_months: int
    decay_weeks: int
    growth_factor: float
    baseline_weeks: int
    popular_rank: int


class ConfigIn(BaseModel):
    top_n: int = Field(5, ge=3, le=10)
    lookback_months: int = Field(24, ge=6, le=36)
    max_plays: int = Field(50000, ge=10000, le=200000)
    catalog_months: int = Field(12, ge=3, le=24)
    newcomer_months: int = Field(6, ge=3, le=12)
    decay_weeks: int = Field(4, ge=1, le=8)
    growth_factor: float = Field(2.5, ge=1.5, le=5.0)
    baseline_weeks: int = Field(8, ge=2, le=26)
    popular_rank: int = Field(5, ge=3, le=50)


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    week: int
    text: str


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    artist_id: str
    artist_name: str = ""
    type: AlertType
    status: AlertStatus
    region_code: str
    week: int
    position: int
    confidence: float
    provisional: bool
    revised: bool
    rule_id: str
    notes: list[NoteOut] = []


class AlertPatch(BaseModel):
    status: AlertStatus
    reason: str | None = Field(default=None, max_length=500)


class ChartEntryOut(BaseModel):
    position: int
    delta_position: int
    artist_id: str
    artist_name: str
    genres: list[str]
    plays: int
    spark: list[int]
    tag: str


class ChartOut(BaseModel):
    region_code: str
    week: int
    completeness: float
    provisional: bool
    entries: list[ChartEntryOut]


class TrackOut(BaseModel):
    isrc: str
    title: str
    release_date: str
    bpm: int | None
    key: str | None


class AvailabilityOut(BaseModel):
    platform: str
    available_since: str
    reset: bool = False


class ArtistOut(BaseModel):
    id: str
    name: str
    genres: list[str]
    debut_date: str
    debut_months: int
    catalog_months: int
    plays_week: int
    total_observed: int
    true_total: int
    position: int
    spark: list[int]
    tracks: list[TrackOut] = []
    availability: list[AvailabilityOut] = []
    alert_ids: list[str] = []


class MediaOut(BaseModel):
    id: str
    title: str
    type: str
    artist_id: str
    artist_name: str
    track_title: str
    start_week: int
    end_week: int
    note: str | None
    state: str
    residual_potential: float


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    week: int
    level: str
    message: str