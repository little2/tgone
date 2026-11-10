"""项目统一使用固定的 UTC+08:00 时区。"""

from datetime import timedelta, timezone

APP_TIMEZONE = timezone(timedelta(hours=8))
MYSQL_TIMEZONE = "+08:00"
POSTGRES_TIMEZONE = "Etc/GMT-8"
