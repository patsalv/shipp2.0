# might want to have this function in the RoomPolicy class
import datetime


def is_in_timeframe(start_time: datetime.time, end_time: datetime.time, time_to_check: datetime.time) -> bool:
    '''
    Checks if current time is in the timeframe defined by start_time and end_time
    '''
    before_midnight = datetime.time(23, 59, 59)
    over_midnight= start_time > end_time

    if over_midnight:
        if start_time <= time_to_check <= before_midnight:
            return True
        if time_to_check <= end_time:
            return True
    else:   
        return start_time <= time_to_check <= end_time
