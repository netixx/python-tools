'''
Module for actions with time related components

'''

DEFAULT_HOUR_PRECISION = 2
DEFAULT_MINUTE_PRECISION = 0

def timedeltaToDecimalHours(timedelta):
    return secondsToDecimalHours(timedelta.total_seconds());

def secondsToDecimalHours(seconds, precision = DEFAULT_HOUR_PRECISION):
    return round(seconds / 3600.0, precision);

def secodeToDecimalMinutes(seconds, precision = DEFAULT_MINUTE_PRECISION):
    return round(seconds, precision)
