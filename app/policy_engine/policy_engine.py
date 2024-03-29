import time
from app.extensions import db
from app.helpers.helpers import get_start_time_in_unix, is_in_timeframe
from app.models import Device, DeviceConfig, Policy, RoomPolicy, Room, DeviceTypePolicy
from app.constants import DeviceTypeEnum, HighLevelPolicyType, PolicyType, DefaultPolicyValues, RoomStatus
from flask import current_app
from app.models.database_model import DeviceType

from app.policy_engine.database_sync import activate_device_policies, deactivate_device_policies, enforce_device_type_offline_policy, enforce_offline_device_type, enforce_offline_room, relax_device_type_offline_policy, relax_offline_device_type, relax_offline_room, sync_policies_to_pihole
from datetime import datetime
from typing import Union, Tuple



# TODO: consider putting this in helpers.py
def overlapping_timeframes(start_time1: time, end_time1: time, start_time2: time, end_time2: time) -> bool:
    #include_start = False, since we allow to start a new policy at the same time the old one ends
    if is_in_timeframe(start_time1, end_time1, start_time2, include_start=False):
        return True
    if is_in_timeframe(start_time1, end_time1, end_time2,include_start=False):
        return True
    if is_in_timeframe(start_time2, end_time2, start_time1,include_start=False):
        return True
    if is_in_timeframe(start_time2, end_time2, end_time1, include_start=False):
        return True
    
    return False
            

# TODO: adapt to new policies
def check_for_room_policy_conflicts(new_policy: RoomPolicy )-> Union[ None ,RoomPolicy]:
    '''
    Checks if timeframe of new policy to be inserted conflicts with already 
    existing policies
    '''
    # check for conflicts with other room policies
    specific_room_policies = db.session.execute(db.select(RoomPolicy).where(RoomPolicy.room_id == new_policy.room_id)).scalars().all()
    for room_policy in specific_room_policies:
        if overlapping_timeframes(new_policy.start_time, new_policy.end_time, room_policy.start_time, room_policy.end_time):
            return room_policy

    # set with all device types that are in the room
    relevant_device_types = set()
    devices_in_room = db.session.execute(db.select(Device).where(Device.room_id == new_policy.room_id)).scalars().all()
    for device in devices_in_room:
        # device type only added if it is not already in the set (property of sets)
        relevant_device_types.add(device.device_type.value)
    

    for type in relevant_device_types:
        device_type_policies = db.session.execute(db.select(DeviceTypePolicy).where(DeviceTypePolicy.device_type == type)).scalars().all()
        for device_type_policy in device_type_policies:
            if overlapping_timeframes(new_policy.start_time, new_policy.end_time, device_type_policy.start_time, device_type_policy.end_time):
                return device_type_policy

    return None
    
# TODO: improve readability
def check_for_device_type_policy_conflicts(new_policy: DeviceTypePolicy )-> Union[None, DeviceTypePolicy]:
    # get all policies for this device type
    specific_device_type_policies = db.session.execute(db.select(DeviceTypePolicy).where(DeviceTypePolicy.device_type == new_policy.device_type)).scalars().all()
    # check if new policy conflicts with any of the already existing policies
    for device_type_policy in specific_device_type_policies:
        if overlapping_timeframes(new_policy.start_time, new_policy.end_time, device_type_policy.start_time, device_type_policy.end_time):
            return device_type_policy
    
    # else, for each device of this device type, check if device exists in a room.  
    devices_of_type = db.session.execute(db.select(Device).where(Device.device_type == new_policy.device_type)).scalars().all()
    for device in devices_of_type:
        if device.room_id is None:
            continue
         # if device exists in a room, check if there policy conflicts with the the room policies.
        try:
            room_policies = db.session.execute(db.select(RoomPolicy).where(RoomPolicy.room_id == device.room_id)).scalars().all()
        except Exception as e:
            print("No room policies found. Error: ", e )
            return None
        
        if room_policies:
            for room_policy in room_policies:
                if overlapping_timeframes(new_policy.start_time, new_policy.end_time, room_policy.start_time, room_policy.end_time):
                    return room_policy
        
    return None
    


def check_for_request_threshold_violation(policy: Union[RoomPolicy, DeviceTypePolicy] ,policy_type:HighLevelPolicyType):
    from app.reporting.email_notification_service import send_threshold_notification_mail
    from app.monitors.pihole_monitor import last_n_minutes_summary
    unix_now = int(datetime.now().timestamp())
    start_time_unix = get_start_time_in_unix(policy.start_time)
    seconds_since_start = unix_now - start_time_unix
    relevant_timeframe_in_seconds = seconds_since_start if seconds_since_start < 3600 else 3600
    
    dataframe = last_n_minutes_summary(relevant_timeframe_in_seconds)
    
    # check if policy is room policy or device type policy
    if(policy_type.value == "ROOM_POLICY"):
        devices = db.session.execute(db.select(Device).where(Device.room_id == policy.room_id)).scalars().all()

    elif policy_type.value == "DEVICE_TYPE_POLICY":
        devices = db.session.execute(db.select(Device).where(Device.device_type == policy.device_type.value)).scalars().all()

    # get all devices affected by the policy & go through each device and check the number of requests
    for device in devices:
        # check if the number of requests for the device exceeds the threshold
        if dataframe[dataframe['client_name'] == device.device_name].shape[0] > policy.request_threshold and not policy.threshold_warning_sent:
            # send email with information about the violation 
            # TODO: gather all violations, if multiple exist, and send them togetehr in one mail
            send_threshold_notification_mail(policy ,device)
            policy.threshold_warning_sent = True
            policy.update_policy()


def evaluate_room_policies(room:Room) -> None:
    '''
    Fetches all room policies from the DB, compares their active timeframe with 
    the actual room status and activates/deactivates them accordingly.
    '''   
    has_active_policy = room.has_active_policy(offline_only=False)
    active_policy = None
    if has_active_policy:
        active_policy = room.get_enforced_room_policy()
        check_for_request_threshold_violation(active_policy, HighLevelPolicyType.ROOM_POLICY)
    
    need_room_update= room.needs_status_update()
    
    if need_room_update:
        try:
            if has_active_policy:
                active_policy.reset_threshold_warning_sent()
                enforce_offline_room(room)
                room.status = RoomStatus.OFFLINE.value
            else: 
                room.status = RoomStatus.ONLINE.value # setting it to online so sync_device_policies works propperly
                relax_offline_room(room.id)
            room.update_room()
        except Exception as e:
            db.rollback()
            current_app.logger.error(f"Error while updating room status: {e}")    

def evaluate_rooms():
    current_app.logger.info("Evaluating rooms")
    all_rooms = Room.query.all()
    for room in all_rooms:
        evaluate_room_policies(room)

def evaluate_policies_per_device_type(device_type: DeviceType):
    '''Evaluates all policies for a given device type and activates/deactivates them accordingly'''
    has_active_policy = device_type.has_active_policy(offline_only=False)
    active_policy = None
    if has_active_policy:
        active_policy = device_type.get_enforced_device_type_policy()
        check_for_request_threshold_violation(active_policy, HighLevelPolicyType.DEVICE_TYPE_POLICY)
    
    need_device_type_update= device_type.needs_status_update()

    if need_device_type_update:
        try:
            if has_active_policy:
                active_policy.reset_threshold_warning_sent()
                enforce_offline_device_type(device_type)
                device_type.offline = True
            else: 
                device_type.offline = False# setting it to online so sync_device_policies works propperly
                relax_offline_device_type(device_type)
            device_type.update()
        except Exception as e:
            db.rollback()
            current_app.logger.error(f"Error while updating room status: {e}")    


def evaluate_device_types():
    current_app.logger.info("Evaluating device type policies")
    all_device_types = DeviceType.query.all()
    for device_type in all_device_types:
        evaluate_policies_per_device_type(device_type) 


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
                # policy.item contains domain
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
