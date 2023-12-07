from app.extensions import db
from app.models import Device, DeviceConfig, Policy, RoomPolicy, Room
from app.constants import PolicyType, DefaultPolicyValues, RoomStatus
from flask import current_app
from app.policy_engine.database_sync import enforce_offline_room, relinquish_offline_room, sync_policies_to_pihole
import datetime
from typing import Union, Tuple

# might want to have this function in the RoomPolicy class
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

def overlapping_timeframes(start_time1: datetime.time, end_time1: datetime.time, start_time2: datetime.time, end_time2: datetime.time) -> bool:
    # check if start_time1 is in timeframe of start_time2 and end_time2
    if is_in_timeframe(start_time1, end_time1, start_time2):
        return True
    #check if end_time1 is in timeframe of start_time1 and end_time2
    if is_in_timeframe(start_time1, end_time1, end_time2):
        return True
    #check if start_time2 is in timeframe of start_time1 and end_time1
    if is_in_timeframe(start_time2, end_time2, start_time1):
        return True
    #check if end_time2 is in timeframe of start_time1 and end_time1
    if is_in_timeframe(start_time2, end_time2, end_time1):
        return True
    
    return False
# might want to have this function in the Room class
def needs_state_update(room: Room, has_active_policy:bool):
    if room is None:
        raise Exception(f"Room with id {room.id} not found")
    
    if room.status == RoomStatus.OFFLINE.value and not has_active_policy:
        return True
    if room.status == RoomStatus.ONLINE.value and has_active_policy:
        return True
    
    return False

# might want to have this function in the Room class
def room_has_active_policy (room_id:int) -> bool:
    room_policies = db.session.execute(db.select(RoomPolicy).where(RoomPolicy.room_id == room_id)).scalars().all()
    current_time = datetime.datetime.now().time()
    for room_policy in room_policies:
        if is_in_timeframe(room_policy.start_time, room_policy.end_time, current_time) and room_policy.active:
            return True

    return False
            

def check_for_room_policy_conflicts(new_policy: RoomPolicy)-> Union[Tuple[bool, None], Tuple[bool, RoomPolicy]]:
    '''
    Checks if timeframe of new policy to be inserted conflicts with already 
    existing policies
    '''
    specific_room_policies = db.session.execute(db.select(RoomPolicy).where(RoomPolicy.room_id == new_policy.room_id)).scalars().all()
    for room_policy in specific_room_policies:
        if overlapping_timeframes(new_policy.start_time, new_policy.end_time, room_policy.start_time, room_policy.end_time):
            return True, room_policy

    return False, None
    

def activate_room_policies(room:Room):
    '''Block all domains for all the devices in the provided room'''
    enforce_offline_room(room)

def deactivate_room_policies(room_id:int):
    "Re-enforce device specific polices for all the devices in the provided room"
    relinquish_offline_room(room_id)

def evaluate_room_policies(room:Room) -> None:
    '''
    Fetches all room policies from the DB, compares their active timeframe with 
    the actual room status and activates/deactivates them accordingly.
    '''   
    has_active_policy = room_has_active_policy(room.id)
    print("HAS ACTIVE POLICY: ", has_active_policy)

    need_update= needs_state_update(room, has_active_policy)
    print("NEED UPDATE: ", need_update)
    if need_update:
        try:
            if has_active_policy:
                activate_room_policies(room)
                room.status = RoomStatus.OFFLINE.value
            else:
                # BUG: eventhough room is set to online, the db will only be updated after the else statement
                print("deactivating room policies")
                room.status = RoomStatus.ONLINE.value # setting it to online so sync_device_policies works propperly
                deactivate_room_policies(room.id)
    
            room.update_room()
        except Exception as e:
            db.rollback()
            current_app.logger.error(f"Error while updating room status: {e}")    

def evaluate_rooms():
    current_app.logger.info("Evaluating rooms")
    all_rooms = Room.query.all()
    for room in all_rooms:
        evaluate_room_policies(room)

# TODO: if a room policy is active, the policies should not be synced to pihole
def evaluate_monitoring_data(dataset: list):
    current_app.logger.info("Evaluating monitoring data")
    device_to_domains = transform_dataset(dataset)
    device_ips = device_to_domains.keys()
    for device_ip in device_ips:
        device, new_policies = evaluate_device_policies(device_ip, device_to_domains[device_ip])
        if device is not None and new_policies is not None and len(new_policies) > 0:
            insert_policy_rows(device, new_policies) # in device db, not pihole db
    with current_app.app_context():
        sync_policies_to_pihole() # syncs to db used by pihole



def evaluate_device_policies(device_ip: str, domains: set) -> (int, list):
    try:
        device = db.session.execute(db.select(Device).join(Device.device_configs).where(
            DeviceConfig.ip_address == device_ip and DeviceConfig.valid_to == None)).scalars().one_or_none() # noqa E711
        if device is None:
            raise Exception(f"Device with ip {device_ip} not found")
        device_policies = device.policies
        default_policy = None
        new_domains = domains.copy()
        for policy in device_policies:
            if policy.policy_type == PolicyType.DEFAULT_POLICY.value:
                default_policy = policy.item
            elif policy.policy_type == PolicyType.ALLOW.value or policy.policy_type == PolicyType.BLOCK.value:
                # policy.item probably contains domain
                if policy.item in domains:
                    # domain already contained in a policy
                    new_domains.remove(policy.item)
        if default_policy is None:
            raise Exception(f"Default policy for device {device_ip} not found")
        else:
            # if new domain is detected, default policy is applied to it
            # -> new policy inserted for this domain
            insert_policies = []
            for domain in new_domains:
                policy_type = None
                if default_policy == DefaultPolicyValues.ALLOW_ALL.value:
                    policy_type = PolicyType.ALLOW.value
                elif default_policy == DefaultPolicyValues.BLOCK_ALL.value:
                    policy_type = PolicyType.BLOCK.value
                item = domain
                insert_policies.append(Policy(policy_type=policy_type, item=item))
            return device, insert_policies
    except Exception as e:
        current_app.logger.error(f"Error while evaluating device policies: {e}")
        return None, None


def insert_policy_rows(device: Device, new_policies):
    ''' Stores new policies for devices into the database used by pi-hole'''
    try:
        device.policies.extend(new_policies)
        db.session.add(device)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error while inserting policy rows: {e}")
        db.session.rollback()


def transform_dataset(dataset: list):
    client_to_domains = dict()
    for datapoint in dataset:
        client = datapoint[1]
        domain = datapoint[3]
        if client not in client_to_domains:
            client_to_domains[client] = set()
        client_to_domains[client].add(domain)
    return client_to_domains
