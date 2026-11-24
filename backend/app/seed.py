"""Детерминированный генератор синтетических батчей (seed 20261109)."""
import json
import math
import random

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.config import SEED, START_WEEK, WEEKS
from app.core.enums import LogLevel
from app.models import (AlertNote, Artist, BreakthroughAlert, ChartEntry, ListeningStat,
                        MediaEvent, Platform, Region, RegionalChart, RuleParams,
                        SimState, Track, TrackMediaEvent, TrackPlatform)
from app.services.alerts import log
from app.services.aggregation import week_date

from dataclasses import dataclass


@dataclass(frozen=True)
class TrackDef:
    isrc: str
    title: str
    release: str
    bpm: int
    key: str


@dataclass(frozen=True)
class ArtistDef:
    id: str
    name: str
    genres: list[str]
    debut: str
    kind: str
    base: float
    boost: dict[str, float]
    avail: dict[str, str]
    tracks: list[TrackDef]


@dataclass(frozen=True)
class MediaDef:
    id: str
    title: str
    type: str
    artist: str
    track: int
    start: int
    end: int
    note: str
    link: str


REGIONS = [("MOW", "Москва"), ("SPE", "Санкт-Петербург"), ("KRD", "Краснодар"),
           ("EKB", "Екатеринбург"), ("NSK", "Новосибирск"), ("KZN", "Казань")]
PLATFORMS = [("spotify", "Spotify", .32), ("yandex", "Яндекс Музыка", .34),
             ("vk", "VK Музыка", .20), ("apple", "Apple Music", .14)]

_ARTISTS_RAW = [
    dict(id="a1", name="Кассета 90", genres=["synthwave", "retrowave"], debut="2019-03-15",
         kind="sleeper", base=150, boost={"KRD": 1.7, "NSK": 1.4, "EKB": 1.2},
         avail={"spotify": "2019-04-01", "yandex": "2021-06-01", "vk": "2019-05-01", "apple": "2020-02-01"},
         tracks=[("RU-A1B-19-00001", "Ночной эфир", "2019-04-12", 104, "Am"),
                 ("RU-A1B-19-00002", "Автобан", "2019-04-12", 118, "Fm")]),
    dict(id="a2", name="Neon Pravda", genres=["electro-punk"], debut="2026-05-20",
         kind="newcomer", base=40, boost={"MOW": 1.6, "SPE": 1.5},
         avail={p: "2026-05-25" for p, _, _ in PLATFORMS},
         tracks=[("RU-N7P-26-00014", "Сигнал", "2026-05-25", 142, "Em")]),
    dict(id="a3", name="Мираж-9", genres=["dream-pop"], debut="2018-09-01",
         kind="viral", base=900, boost={"MOW": 1.3, "KZN": 1.3},
         avail={"spotify": "2018-10-01", "yandex": "2019-01-01", "vk": "2018-10-01", "apple": "2019-03-01"},
         tracks=[("RU-M9X-18-00031", "Северный ветер", "2018-10-05", 92, "Cm"),
                 ("RU-M9X-21-00007", "Стеклянный город", "2021-04-16", 88, "Gm")]),
    dict(id="a4", name="Гроза FM", genres=["indie-rock"], debut="2015-04-01",
         kind="star", base=5200, boost={"SPE": 1.3},
         avail={"spotify": "2015-05-01", "yandex": "2016-01-01", "vk": "2015-05-01", "apple": "2016-06-01"},
         tracks=[("RU-G4F-15-00102", "Частота", "2015-05-10", 126, "Dm")]),
    dict(id="a5", name="Полярные Волны", genres=["ambient", "electronics"], debut="2017-02-01",
         kind="mid", base=2600, boost={"NSK": 1.5, "EKB": 1.2},
         avail={"spotify": "2017-03-01", "yandex": "2018-01-01", "vk": "2017-04-01", "apple": "2018-05-01"},
         tracks=[("RU-P2V-17-00044", "Ледостав", "2017-03-12", 70, "A")]),
    dict(id="a6", name="Лунный Причал", genres=["folktronica"], debut="2020-08-01",
         kind="sleeper2", base=120, boost={"KZN": 1.6, "KRD": 1.3},
         avail={"spotify": "2020-09-01", "yandex": "2022-03-01", "vk": "2020-09-01", "apple": "2021-01-01"},
         tracks=[("RU-L8P-20-00009", "Прилив", "2020-09-14", 96, "D")]),
    dict(id="a7", name="DJ Периметр", genres=["techno"], debut="2016-06-01",
         kind="mid", base=3100, boost={"MOW": 1.4, "EKB": 1.3},
         avail={"spotify": "2016-07-01", "yandex": "2017-05-01", "vk": "2016-07-01", "apple": "2017-09-01"},
         tracks=[("RU-D1P-16-00210", "Контур", "2016-07-20", 132, "F#m")]),
    dict(id="a8", name="Вера и Космос", genres=["art-pop"], debut="2019-11-01",
         kind="mid", base=2100, boost={"SPE": 1.4, "MOW": 1.2},
         avail={"spotify": "2019-12-01", "yandex": "2020-04-01", "vk": "2019-12-01", "apple": "2020-08-01"},
         tracks=[("RU-V5K-19-00077", "Орбита", "2019-12-09", 100, "Bm")]),
    dict(id="a9", name="Стальные Птицы", genres=["metal"], debut="2014-01-01",
         kind="niche", base=1300, boost={"EKB": 1.6, "NSK": 1.3},
         avail={"spotify": "2014-03-01", "yandex": "2016-06-01", "vk": "2014-03-01", "apple": "2015-01-01"},
         tracks=[("RU-S3P-14-00301", "Высота", "2014-03-18", 150, "Em")]),
    dict(id="a10", name="Тихий Час", genres=["lo-fi"], debut="2021-05-01",
         kind="niche", base=420, boost={"KRD": 1.2},
         avail={"spotify": "2021-06-01", "yandex": "2023-01-01", "vk": "2021-06-01", "apple": "2022-02-01"},
         tracks=[("RU-T6C-21-00012", "Полдень", "2021-06-07", 74, "C")]),
    dict(id="a11", name="Фотон", genres=["hyperpop"], debut="2026-08-10",
         kind="newcomer2", base=15, boost={"MOW": 1.8, "SPE": 1.4},
         avail={p: "2026-08-15" for p, _, _ in PLATFORMS},
         tracks=[("RU-F2T-26-00003", "Вспышка", "2026-08-15", 160, "G#m")]),
    dict(id="a12", name="Эхо Двора", genres=["rap"], debut="2018-03-01",
         kind="niche", base=1100, boost={"KRD": 1.4, "KZN": 1.2},
         avail={"spotify": "2018-04-01", "yandex": "2019-02-01", "vk": "2018-04-01", "apple": "2019-07-01"},
         tracks=[("RU-E8D-18-00140", "Район", "2018-04-22", 88, "Dm")]),
]

ARTISTS: list[ArtistDef] = [
    ArtistDef(
        id=d["id"], name=d["name"], genres=d["genres"], debut=d["debut"],
        kind=d["kind"], base=d["base"], boost=d["boost"], avail=d["avail"],
        tracks=[TrackDef(*t) for t in d["tracks"]],
    )
    for d in _ARTISTS_RAW
]

_MEDIA_RAW = [
    dict(id="me1", title="Сериал «Трасса-2»", type="SERIES", artist="a3", track=0,
         start=36, end=46, note="Титры финала каждой серии", link="soundtrack"),
    dict(id="me2", title="TikTok-челлендж #ночнойэфир", type="TREND", artist="a1", track=0,
         start=40, end=49, note="Органический UGC-всплеск", link="ugc_trend"),
    dict(id="me3", title="Фестиваль «Юг.Звук»", type="FEST", artist="a4", track=0,
         start=48, end=49, note="Хедлайнер, Краснодар", link="live"),
]

MEDIA: list[MediaDef] = [MediaDef(**m) for m in _MEDIA_RAW]

SEED_ALERTS = [
    ("AL-1042", "a3", "VIRAL", "MOW", 38, 2, .94, "CONFIRMED", "FR-03", False,
     [(38, "Создан: рост ×3.1 к медиане 4 недель, активное событие «Трасса-2»."),
      (39, "A&R: взят в работу."),
      (40, "Подтверждён. Передано в букинг: тур MOW/SPE.")]),
    ("AL-1043", "a2", "NEWCOMER", "MOW", 42, 4, .88, "NEW", "FR-02", False,
     [(42, "Создан: дебют 3 мес назад, первое попадание в Top-5, ранее вне Top-50.")]),
    ("AL-1041", "a6", "SLEEPER", "KZN", 41, 5, .71, "IN_REVIEW", "FR-01", False,
     [(41, "Создан: локальный всплеск в KZN, каталог 72 мес, база ниже порога."),
      (42, "A&R: проверяем, не фестиваль ли это — взят в работу.")]),
    ("AL-1039", "a10", "SLEEPER", "KRD", 39, 5, .52, "REJECTED", "FR-05", True,
     [(39, "Создан по наблюдаемым данным."),
      (39, "FR-05: VK приобрела права, счётчик площадки обнулён. Наблюдаемая база "
           "занижена относительно истинной — ложный прорыв, отклонён системой.")]),
]

# Неделя, с которой VK «купила права» на каталог «Тихого Часа».
# Применяется только к текущей/будущим неделям: история не переписывается (D-07).
RIGHTS_HISTORY = {"artist": "a10", "platform": "vk", "week": START_WEEK}

def curve(kind: str, base: float, t: int) -> float:
    """Форма траектории артиста. Синтетика, но правдоподобная."""
    if kind == "sleeper":
        return base * (1 if t < 38 else 1 + ((t - 37) / 2.4) ** 2.1)
    if kind == "sleeper2":
        return base * (1 if t < 44 else 1 + ((t - 43) / 2.8) ** 2)
    if kind == "newcomer":
        return 0 if t < 33 else base * 1.34 ** (t - 33)
    if kind == "newcomer2":
        return 0 if t < 45 else base * 1.42 ** (t - 45)
    if kind == "viral":
        if 36 <= t <= 46:
            return base * (1 + 3.4 * math.sin(math.pi * (t - 35) / 12))
        if t > 46:
            return base * (1 + 2.2 * math.exp(-(t - 46) / 2.2))
        return base
    if kind == "star":
        return base * (1 + .12 * math.sin(t / 5))
    if kind == "mid":
        return base * (1 + .18 * math.sin(t / 7 + base))
    return base


def build_stats(rnd: random.Random) -> tuple[list[dict], dict[str, int]]:
    """Чистая функция: батчи и истинная база за ВСЕ недели горизонта."""
    rows: list[dict] = []
    totals: dict[str, int] = {}
    for d in ARTISTS:
        total = 0
        for w in range(1, WEEKS + 1):
            v = curve(d.kind, d.base, w)
            for code, _ in REGIONS:
                boost = d.boost.get(code, 1.0)
                noise = 1 + (rnd.random() - .5) * .24
                region_plays = max(0, round(v * boost * noise / len(REGIONS) * 2.2))
                for pid, _, share in PLATFORMS:
                    plays = round(region_plays * share)
                    rows.append(dict(week=w, artist_id=d.id, region_code=code,
                                     platform_id=pid, plays=plays))
                    total += plays
        totals[d.id] = total          # ← теперь тип ключа известен: str
    return rows, totals


def generate(db: Session) -> None:
    rnd = random.Random(SEED)

    for code, name in REGIONS:
        db.add(Region(code=code, name=name))
    for pid, name, share in PLATFORMS:
        db.add(Platform(id=pid, name=name, share=share))
    db.add(RuleParams(id=1, popular_rank=5))  # демо-каталог: 12 артистов
    db.add(SimState(id=1, week=START_WEEK))
    db.flush()

    # --- артисты, треки, доступность каталога ---
    track_ids: dict[str, list[int]] = {}
    for d in ARTISTS:
        a = Artist(id=d.id, name=d.name,
                   genres=json.dumps(d.genres, ensure_ascii=False),
                   debut_date=d.debut, kind=d.kind)
        db.add(a)
        db.flush()
        track_ids[a.id] = []
        for tr in d.tracks:
            t = Track(artist_id=a.id, isrc=tr.isrc, title=tr.title,
                      release_date=tr.release, bpm=tr.bpm, key=tr.key)
            db.add(t)
            db.flush()
            track_ids[a.id].append(t.id)
            for pid, _, _ in PLATFORMS:
                db.add(TrackPlatform(track_id=t.id, platform_id=pid,
                                     external_id=f"{pid}:{tr.isrc}",
                                     available_since=d.avail[pid]))
    db.flush()

    # --- батчи прослушиваний (bulk insert) ---
    rows, totals = build_stats(rnd)
    db.execute(insert(ListeningStat), rows)
    for aid, total in totals.items():
        db.get(Artist, aid).true_total_plays = total

    # Исторический эпизод покупки прав: обосновывает сид-алерт AL-1039 (FR-05)
    rh = RIGHTS_HISTORY
    reset_artist = db.get(Artist, rh["artist"])
    reset_artist.rights_platform = rh["platform"]
    reset_artist.rights_week = rh["week"]
    reset_date = week_date(rh["week"]).isoformat()
    for tp in db.scalars(
        select(TrackPlatform)
        .join(Track, TrackPlatform.track_id == Track.id)
        .where(Track.artist_id == rh["artist"], TrackPlatform.platform_id == rh["platform"])
    ):
        tp.available_since = reset_date
    db.commit()

    # --- медиа-события и связи M:M ---
    for m in MEDIA:
        tid = track_ids[m.artist][m.track]
        db.add(MediaEvent(id=m.id, title=m.title, type=m.type,
                          artist_id=m.artist, track_id=tid,
                          start_week=m.start, end_week=m.end, note=m.note))
        db.add(TrackMediaEvent(track_id=tid, media_event_id=m.id, link_type=m.link))
    db.commit()

    # --- чарты с реальными позициями: lookback (FR-01/02) работает с первого запуска ---
    from sqlalchemy import func as sa_func
    artists = db.scalars(select(Artist)).all()
    prev_pos: dict[str, dict[str, int]] = {code: {} for code, _ in REGIONS}
    for w in range(1, START_WEEK + 1):
        for code, _ in REGIONS:
            per_region = dict(db.execute(
                select(ListeningStat.artist_id, sa_func.sum(ListeningStat.plays))
                .where(ListeningStat.week == w, ListeningStat.region_code == code)
                .group_by(ListeningStat.artist_id)
            ).all())
            ranked = sorted(artists, key=lambda a: per_region.get(a.id, 0), reverse=True)
            chart = RegionalChart(region_code=code, week=w, completeness=1.0, provisional=False)
            db.add(chart)
            db.flush()
            for i, a in enumerate(ranked, start=1):
                db.add(ChartEntry(chart_id=chart.id, artist_id=a.id, position=i,
                                  plays=per_region.get(a.id, 0),
                                  delta_position=prev_pos[code].get(a.id, i) - i))
            prev_pos[code] = {a.id: i for i, a in enumerate(ranked, start=1)}
    db.commit()

    # --- стартовые алерты: разные типы и статусы для демонстрации workflow ---
    for aid, artist, atype, region, week, pos, conf, status, rule, revised, notes in SEED_ALERTS:
        chart = db.scalar(select(RegionalChart).where(
            RegionalChart.region_code == region, RegionalChart.week == week))
        al = BreakthroughAlert(id=aid, artist_id=artist, chart_id=chart.id, type=atype,
                               status=status, region_code=region, week=week, position=pos,
                               confidence=conf, provisional=False, revised=revised, rule_id=rule)
        db.add(al)
        db.flush()
        for w, text in notes:
            db.add(AlertNote(alert_id=aid, week=w, text=text))
    db.commit()

    log(db, START_WEEK, LogLevel.HIT,
        f"Система инициализирована: {len(ARTISTS)} артистов, {len(REGIONS)} регионов, "
        f"{len(PLATFORMS)} платформы, {len(rows)} строк батчей. Неделя {START_WEEK}. "
        f"Правила FR-01…05 загружены из конфигурации (seed {SEED}).")