# might want to have this function in the RoomPolicy class
import datetime
from app.constants import DeviceTypeEnum


def get_start_time_in_unix(start_time: datetime.time) -> int:
    '''
    Converts start_time to unix time
    '''
   # check if start_time was yesterday or today
    if start_time > datetime.datetime.now().time():
        return int(datetime.datetime.combine(datetime.date.today() - datetime.timedelta(days=1), start_time).timestamp())
    
    return int(datetime.datetime.combine(datetime.date.today(), start_time).timestamp())

# this is not yet perfect.
def is_in_timeframe(start_time: datetime.time, end_time: datetime.time, time_to_check: datetime.time, include_start: bool) -> bool:
    '''
    Checks if current time is in the timeframe defined by start_time and end_time
    '''
    before_midnight = datetime.time(23, 59, 59)
    over_midnight= start_time > end_time

    # if include_start is True, the start_time is included in the timeframe
    match include_start:
        case True:
            if over_midnight:
                if start_time <= time_to_check <= before_midnight:
                    return True
                if time_to_check < end_time:
                    return True
            else:   
                return start_time <= time_to_check < end_time
        case False:
            if over_midnight:
                if start_time < time_to_check <= before_midnight:
                    return True
                if time_to_check < end_time:
                    return True
            else:   
                return start_time < time_to_check < end_time
    

def initialize_mock_device(name:str, mac: str, ip: str,device_type: DeviceTypeEnum):
    from app.models.database_model import Device, DeviceConfig, Policy
    from app.constants import PolicyType
    from app.service_integration_api.pihole_integration_db import init_pihole_device

    device = Device(mac_address=mac, device_name=name)
    device.device_configs.append(DeviceConfig(ip_address=ip))
    default_policy = Policy(policy_type=PolicyType.DEFAULT_POLICY.value,
                            item="ALLOW_ALL")
    device.policies.append(default_policy)
    device.device_type = device_type.value
    device.insert_device()
    init_pihole_device(device)

