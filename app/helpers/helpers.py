# might want to have this function in the RoomPolicy class
import datetime
from app.constants import DeviceTypeEnum



# this is not yet perfect.
def is_in_timeframe(start_time: datetime.time, end_time: datetime.time, time_to_check: datetime.time) -> bool:
    '''
    Checks if current time is in the timeframe defined by start_time and end_time
    '''
    before_midnight = datetime.time(23, 59, 59)
    over_midnight= start_time > end_time

    if over_midnight:
        if start_time < time_to_check <= before_midnight:
            return True
        if time_to_check < end_time:
            return True
    else:   
        return start_time < time_to_check < end_time
    

def initialize_mock_device(name:str, mac: str, ip: str,device_type: DeviceTypeEnum):
    from app.models.database_model import Device, DeviceConfig, Policy, DeviceType
    from app.constants import PolicyType
    device = Device(mac_address=mac, device_name=name)
    device.device_configs.append(DeviceConfig(ip_address=ip))
    default_policy = Policy(policy_type=PolicyType.DEFAULT_POLICY.value,
                            item="ALLOW_ALL")
    device.policies.append(default_policy)
    device.device_type = device_type.value
    device.insert_device()

