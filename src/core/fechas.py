from datetime import date, datetime, timedelta, timezone


def hoy_bolivia() -> date:
    return datetime.now(timezone(timedelta(hours=-4))).date()
