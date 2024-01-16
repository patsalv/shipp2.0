from app.models import Group, Device, Domainlist, Room
from app.extensions import db
from app.constants import PolicyType, RoomStatus
from flask import current_app

from app.models.database_model import Policy


def sync_policies_to_pihole():
    devices = db.session.execute(db.select(Device)).scalars().all()
    db.session.commit()
    for device in devices:
        sync_device_policies(device)


def sync_device_policies(device):
    '''
    Gets group corresponding to the device from pi-hole and compares the policies of the device 
    instance with the policies of the group instance. Updates policies of the group instance
    such that they match the policies of the device instance.
    '''
    
    if in_offline_room(device):
        # don't sync policies from devices if room is offline
        return
    try:
        policies = device.policies
        db.session.commit()
        pi_group = db.session.execute(db.select(Group).where(Group.name == device.mac_address)).scalars().one()
        pi_domains = pi_group.domains.all()
        pi_domain_map = build_pi_domain_map(pi_domains)
        policy_type_to_pi_type = {PolicyType.ALLOW.value: 0, PolicyType.BLOCK.value: 1}
        print(pi_domain_map)# to debug
        max_date_modified = 0
        if len(pi_domains) > 0:
            max_date_modified = max(pi_domains, key=lambda domain: domain.date_modified).date_modified
        db.session.commit()        
        
        brand_new_policies, update_policies = retreive_policies_demanding_action(policies, max_date_modified,pi_domain_map,policy_type_to_pi_type)

        new_pi_domains = []

        for policy in brand_new_policies:
            type = policy_type_to_pi_type[policy.policy_type]
            domain = policy.item
            new_pi_domains.append(Domainlist(type=type, domain=domain))
        
        # inserting new domains in db
        if len(new_pi_domains) > 0:
            pi_group.domains.extend(new_pi_domains)
            db.session.add(pi_group)
            db.session.flush()

        # update policies (allow,block)
        if len(update_policies):
            update_existing_policies(pi_group, update_policies, pi_domain_map, policy_type_to_pi_type)

        db.session.commit()
    except Exception as e:
        current_app.logger.error(f"Error while syncing device {device.id}'s policies to pihole: {e}")
        db.session.rollback()

def deactivate_device_policies(room: Room ):
    '''Sets all policies of the devices in the room to inactive'''
    try:
        devices= room.devices
        for device in devices: 
            policies = device.policies
            for policy in policies:
                policy.active = False
                policy.update_policy()
    except Exception as e:
        print("An error occured while deactivation_device_policies:  ", e)

def activate_device_policies(room: Room ):
    '''Sets all policies of the devices in the room to active'''
    devices= room.devices
    for device in devices: 
        policies = device.policies
        for policy in policies:
            policy.active = True
            policy.update_policy()


def enforce_offline_room(room: Room):
    '''Blocks all domains for all devices in the room'''
    try:
        
        # get domains which are not yet in pihole from device policies
        for device in room.devices:
            pi_group = db.session.execute(db.select(Group).where(Group.name == device.mac_address)).scalars().one()
            policies = device.policies
            pi_domains = pi_group.domains.all()
            pi_domain_map = build_pi_domain_map(pi_domains)        
            new_pi_domains = get_new_pi_domains(pi_domains, policies, pi_domain_map)
            
            print("pi.domain_map before update: ", pi_domain_map)
            # inserting new domains in db (domain consisting of domain name and type)
            if len(new_pi_domains) > 0:
                print("inserting new domains in db")
                pi_group.domains.extend(new_pi_domains)
                db.session.add(pi_group)
                db.session.flush()
            
            # set already exisiting domains to block
            for domain in pi_domains:
                print("setting already existing domains to BLOCK")
                domain.type = 1 # 0 = allow, 1 = block

            print("pi domains after update: ", build_pi_domain_map(pi_group.domains.all()))
            db.session.commit()    
    except Exception as e:
        current_app.logger.error(f"Error while enforcing offline room: {e}")
        db.session.rollback()        

def relinquish_offline_room(room_id:int):
    '''Restores the policies of the devices in the room'''
    devices = db.session.execute(db.select(Device).where(Device.room_id == room_id)).scalars().all()
    for device in devices:
        sync_device_policies(device)
        pi_group = db.session.execute(db.select(Group).where(Group.name == device.mac_address)).scalars().one()
        pi_domains_after_unblocking = pi_group.domains.all()
        print("pi_domains after relinquish", build_pi_domain_map(pi_domains_after_unblocking))

def in_offline_room(device):
    # room status is None if device is not in a room
    # TODO: doublecheck if this is correct
    if device.room == None or device.room.status == None:
        return False
    
    return device.room.status == RoomStatus.OFFLINE.value

def build_pi_domain_map(pi_domains)->dict:
    pi_domain_map = dict()
    for pi_domain in pi_domains:
        pi_domain_map[pi_domain.domain] = (pi_domain.id, pi_domain.type)
    return pi_domain_map

def update_existing_policies(pi_group, update_policies, pi_domain_map, policy_type_to_pi_type):
    update_pi_domains = []
    for policy in update_policies:
        id = pi_domain_map[policy.item][0]
        pi_domain = pi_group.domains.filter_by(id=id).one()
        pi_domain.type = policy_type_to_pi_type[policy.policy_type]
        update_pi_domains.append(pi_domain)
    db.session.add_all(update_pi_domains)

def get_new_pi_domains(pi_domains, policies, pi_domain_map):
    new_domains = set()    
    max_date_modified = 0
    if len(pi_domains) > 0:
        max_date_modified = max(pi_domains, key=lambda domain: domain.date_modified).date_modified
    newer_policies = {policy for policy in policies if policy.date_modified > max_date_modified}

    # add new policies (for new domains)
    for policy in newer_policies:
        if policy.item not in pi_domain_map and policy.policy_type != PolicyType.DEFAULT_POLICY.value:
            new_domains.add(policy.item)

    new_pi_domains = []
    for domain in new_domains:
        new_pi_domains.append(Domainlist(type=1, domain=domain))

    return new_pi_domains

def retreive_policies_demanding_action(policies:Device.policies, max_date_modified:int, pi_domain_map:dict, policy_type_to_pi_type:dict )->tuple[set, set]:
    """ retreive new policies and old policies that have to be re-enforced after a domain has been blocked by a room policy"""
    brand_new_policies = set()
    policies_demanding_update = set()

    for policy in policies:
        if policy.policy_type == PolicyType.DEFAULT_POLICY.value:
            continue
        elif policy.date_modified > max_date_modified: # new or modified policies
            print("inside new or modified policies")
            if policy.item in pi_domain_map and policy_type_to_pi_type[policy.policy_type] != pi_domain_map[policy.item][1]:
                print("changed policy demanding update")
                policies_demanding_update.add(policy)
            else:
                brand_new_policies.add(policy)
        else: # old unmodified policies
            if policy.item in pi_domain_map and policy_type_to_pi_type[policy.policy_type] != pi_domain_map[policy.item][1]:
                print("old policy demanding domain update")
                policies_demanding_update.add(policy)


    return brand_new_policies, policies_demanding_update
