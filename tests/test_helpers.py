import datetime
from app.helpers.helpers import is_in_timeframe
from app.policy_engine.policy_engine import overlapping_timeframes


def test_is_in_timeframe():
    start_time = datetime.time(23, 0, 0)
    end_time = datetime.time(23, 30, 0)

    time_between = datetime.time(23, 15, 0)
    on_start_time = datetime.time(23, 0, 0)
    on_end_time = datetime.time(23, 30, 0)

    assert is_in_timeframe(start_time, end_time, time_between) == True  
    assert is_in_timeframe(start_time, end_time, on_start_time) == True
    assert is_in_timeframe(start_time, end_time, on_end_time) == False


def test_overlapping_time_over_midnight():
    over_midnight = {"start": datetime.time(23, 0, 0), "end": datetime.time(1, 0, 0)}
    overlap_midnight_start = {"start": datetime.time(22, 0, 0), "end": datetime.time(23, 30, 0)}
    overlap_midnight_end = {"start": datetime.time(0, 0, 0), "end": datetime.time(2, 0, 0)}
    overlap_midnight_inside = {"start": datetime.time(23, 30, 0), "end": datetime.time(0, 30, 0)}
    # policy over midnight
    assert overlapping_timeframes(over_midnight["start"],over_midnight["end"], overlap_midnight_start["start"], overlap_midnight_start["end"]) == True
    assert overlapping_timeframes(over_midnight["start"],over_midnight["end"], overlap_midnight_end["start"], overlap_midnight_end["end"]) == True
    assert overlapping_timeframes(over_midnight["start"],over_midnight["end"], overlap_midnight_inside["start"], overlap_midnight_inside["end"]) == True

    # policy over midnight reverse
    assert overlapping_timeframes( overlap_midnight_start["start"], overlap_midnight_start["end"],over_midnight["start"],over_midnight["end"]) == True
    assert overlapping_timeframes( overlap_midnight_end["start"], overlap_midnight_end["end"],over_midnight["start"],over_midnight["end"]) == True
    assert overlapping_timeframes( overlap_midnight_inside["start"], overlap_midnight_inside["end"], over_midnight["start"],over_midnight["end"]) == True


def test_overlaping_time_over_midnight_boundary():
    over_midnight = {"start": datetime.time(23, 0, 0), "end": datetime.time(1, 0, 0)}

    end_on_start = {"start": datetime.time(22, 0, 0), "end": datetime.time(23, 0, 0)}
    start_on_end = {"start": datetime.time(1, 0, 0), "end": datetime.time(2, 0, 0)}

    end_one_after_start = {"start": datetime.time(22, 0, 0), "end": datetime.time(23, 00, 1)}
    start_one_before_end = {"start": datetime.time(0, 59, 59), "end": datetime.time(2, 0, 0)}
    # on boundary
    assert overlapping_timeframes(over_midnight["start"],over_midnight["end"], end_on_start["start"], end_on_start["end"]) == False
    assert overlapping_timeframes(over_midnight["start"],over_midnight["end"], start_on_end["start"], start_on_end["end"]) == False

    # in point
    assert overlapping_timeframes(over_midnight["start"],over_midnight["end"], end_one_after_start["start"], end_one_after_start["end"]) == True
    assert overlapping_timeframes(over_midnight["start"],over_midnight["end"], start_one_before_end["start"], start_one_before_end["end"]) == True


def test_no_overlapping_time_normal():
    normal_time_frame = {"start": datetime.time(10, 0, 0), "end": datetime.time(12, 0, 0)}
    before_normal = {"start": datetime.time(8, 0, 0), "end": datetime.time(9, 0, 0)}
    after_normal = {"start": datetime.time(13, 0, 0), "end": datetime.time(14, 0, 0)}
    
    # fully outside of timeframe
    assert overlapping_timeframes(normal_time_frame["start"],normal_time_frame["end"], before_normal["start"], before_normal["end"]) == False
    assert overlapping_timeframes(normal_time_frame["start"],normal_time_frame["end"], after_normal["start"], after_normal["end"]) == False
    
    # fully outside of timeframe reversed
    assert overlapping_timeframes( before_normal["start"], before_normal["end"], normal_time_frame["start"],normal_time_frame["end"]) == False
    assert overlapping_timeframes( after_normal["start"], after_normal["end"],normal_time_frame["start"],normal_time_frame["end"]) == False
    

def test_no_overlapping_time_boundary():
    normal_time_frame = {"start": datetime.time(10, 0, 0), "end": datetime.time(12, 0, 0)}
    end_on_start = {"start": datetime.time(9, 0, 0), "end": datetime.time(10, 0, 0)}
    start_on_end = {"start": datetime.time(12, 0, 0), "end": datetime.time(13, 0, 0)}

    # overlap
    assert overlapping_timeframes(normal_time_frame["start"],normal_time_frame["end"], end_on_start["start"], end_on_start["end"]) == False
    assert overlapping_timeframes(normal_time_frame["start"],normal_time_frame["end"], start_on_end["start"], start_on_end["end"]) == False

    #overlap reversed
    assert overlapping_timeframes(end_on_start["start"], end_on_start["end"],normal_time_frame["start"],normal_time_frame["end"]) == False
    assert overlapping_timeframes(start_on_end["start"], start_on_end["end"],normal_time_frame["start"],normal_time_frame["end"]) == False
