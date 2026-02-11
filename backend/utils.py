from datetime import datetime, timedelta
import pytz

CENTRAL_TZ = pytz.timezone("America/Chicago")
NBA_DAY_CUTOFF_HOUR = 1


def get_nba_day():
    now_central = datetime.now(CENTRAL_TZ)
    if now_central.hour < NBA_DAY_CUTOFF_HOUR:
        nba_date = (now_central - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        nba_date = now_central.strftime("%Y-%m-%d")
    return nba_date


def get_nba_day_dates():
    now_central = datetime.now(CENTRAL_TZ)
    nba_date = get_nba_day()
    real_date = now_central.strftime("%Y-%m-%d")
    dates = list(set([nba_date, real_date]))
    dates.sort()
    return dates
