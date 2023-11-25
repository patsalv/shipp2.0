from app.extensions import db
from app.models import Device, DeviceConfig, Policy, RoomPolicy
from app.constants import PolicyType, DefaultPolicyValues
from flask import current_app
from app.policy_engine.database_sync import sync_policies_to_pihole


def check_room_policies():
    '''
    Fetches all room policies from the DB, compares their active timeframe with 
    the actual room status and activates/deactivates them accordingly.
    '''
    current_app.logger.info("Checking room policies")
    ...

def check_for_room_conflicts(room_id:int, new_policy: RoomPolicy):
    '''
    Checks if timeframe of new policy to be inserted conflicts with already 
    existing policies
    '''
    ...

def activate_room_policies():
    '''Block all domains for all the devices in the provided room'''
    ...

def deactivate_room_policies():
    "Re-enforce device specific polices for all the devices in the provided room"
    ...

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
        sync_policies_to_pihole() #syncs to db used by pihole



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
