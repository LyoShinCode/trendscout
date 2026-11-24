from enum import Enum


class AlertType(str, Enum):
    SLEEPER = "SLEEPER"      # старый каталог, низкая база, внезапный взлёт
    NEWCOMER = "NEWCOMER"    # свежий дебют сразу в топ
    VIRAL = "VIRAL"          # взлёт, сцепленный с медиа-событием


class AlertStatus(str, Enum):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class MediaType(str, Enum):
    SERIES = "SERIES"
    MOVIE = "MOVIE"
    TREND = "TREND"
    FEST = "FEST"


class LogLevel(str, Enum):
    HIT = "hit"        # правило сработало
    MISS = "miss"      # условие не выполнено / дедупликация
    GUARD = "guard"    # предохранитель FR-05 / служебное событие
    REVOKE = "rev"     # отзыв алерта по FR-04