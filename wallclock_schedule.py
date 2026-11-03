"""Daily/weekly wall-clock schedules, including daylight-saving transitions."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re


def validate(value):
    if value is None:return None
    if not isinstance(value,dict) or set(value)!={'time','timezone','weekdays'}:
        raise ValueError('Schedule needs time, timezone and weekdays.')
    if not isinstance(value['time'],str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value['time']):
        raise ValueError('Use a 24-hour time such as 08:00.')
    days=value['weekdays']
    if not isinstance(days,list) or not 1<=len(days)<=7 or any(type(d) is not int or not 0<=d<=6 for d in days):
        raise ValueError('Choose weekdays 0 (Monday) to 6 (Sunday).')
    try:ZoneInfo(value['timezone'])
    except (ZoneInfoNotFoundError,TypeError,ValueError):raise ValueError('Choose an installed IANA timezone such as Asia/Kolkata.') from None
    return {'time':value['time'],'timezone':value['timezone'],'weekdays':sorted(set(days))}


def next_run(schedule,now):
    schedule=validate(schedule);zone=ZoneInfo(schedule['timezone'])
    local=datetime.fromtimestamp(now,zone);hour,minute=map(int,schedule['time'].split(':'))
    for offset in range(15):
        day=local.date()+timedelta(days=offset)
        if day.weekday() not in schedule['weekdays']:continue
        candidate=datetime(day.year,day.month,day.day,hour,minute,tzinfo=zone,fold=0)
        # A nonexistent spring-forward time is skipped; a repeated time runs once.
        if candidate.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)!=candidate.replace(tzinfo=None):continue
        if candidate.timestamp()>now:return candidate.timestamp()
    raise ValueError('No valid occurrence in the next two weeks.')


def next_due(item,now):
    return next_run(item['schedule'],now) if item.get('schedule') else now+item['minutes']*60
