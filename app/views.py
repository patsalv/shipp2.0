# App routing
import copy
import traceback
from flask import Blueprint, jsonify, make_response, render_template, redirect, url_for, request, flash, current_app, abort
from app.extensions import db
from app.models import Device, DeviceConfig, User, Policy, Room, RoomPolicy
from app.forms import DeviceForm, EditDeviceTypePolicyForm, EditRoomPolicyForm, LoginForm, HighlevelPolicyForm, RegistrationForm, RoomForm, RoomPolicyForm
from datetime import datetime
from flask_login import login_required, login_user, logout_user
from app.constants import DevicePolicyStatus, DeviceTypeEnum, HighLevelPolicyType, HighLevelPolicyStatus, PolicyType, RoomStatus
from app.models.database_model import DeviceType, DeviceTypePolicy
from app.policy_engine.policy_engine import check_for_device_type_policy_conflicts, check_for_room_policy_conflicts, evaluate_device_types, evaluate_policies_per_device_type, evaluate_room_policies, evaluate_single_device_type_policy
from app.service_integration_api import init_pihole_device, update_pihole_device

bp = Blueprint("main", __name__, template_folder="templates")


@bp.route("/")
def index():
    forwarded_proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    forwarded_host = request.headers.get("X-Forwarded-Host", request.host)
    base_url = f"{forwarded_proto}://{forwarded_host}"
    redirect_url = base_url + "/dash/"

    current_app.logger.info(f"Redirecting to {redirect_url}")
    return redirect(base_url + "/dash/")


@bp.route("/devices")
@login_required
def devices():
    active_devices = db.session.execute(db.select(
        Device.id, Device.device_name, Device.mac_address,Device.device_type, DeviceConfig.ip_address, DeviceConfig.valid_from, )
                                        .join(Device.device_configs).where(DeviceConfig.valid_to == None))  # noqa: E711
    return render_template("devices.html", devices=active_devices)


@login_required
@bp.route("/add-device", methods=["GET", "POST"])#
def add_device():
    form = DeviceForm()
    if form.validate_on_submit(): 
        device = Device(mac_address=form.mac.data, device_name=form.name.data, device_type=form.device_type.data)
        device.device_configs.append(DeviceConfig(ip_address=form.ip.data))
        default_policy = Policy(policy_type=PolicyType.DEFAULT_POLICY.value,
                                item=form.default_policy.data)
        
        device.policies.append(default_policy)
        device.insert_device()
        try:
            init_pihole_device(device)
        except Exception as e:
            current_app.logger.error(f"Error while initializing pihole device: {e}")
        finally:
            return redirect(url_for("main.devices"))
    
    return render_template("add-device.html", form=form)


@bp.route("/edit-device/<int:device_id>", methods=["GET", "POST"])
@login_required
def edit_device(device_id):
    device = db.get_or_404(Device, device_id)
    current_config = device.get_current_config()
    default_policy = device.get_default_policy()
    form = DeviceForm()
    if form.validate_on_submit():
        device.device_name = form.name.data
        device.device_type = form.device_type.data
        if default_policy.item != form.default_policy.data:
            default_policy.item = form.default_policy.data
        if current_config.ip_address != form.ip.data:
            current_config.valid_to = datetime.now()
            current_config.update_device_config()
            device.device_configs.append(DeviceConfig(ip_address=form.ip.data))
        device.update_device()
        try:
            update_pihole_device(device, current_config)
        except Exception as e:
            current_app.logger.error(f"Error while updating pihole device: {e}")
        finally:
            return redirect(url_for("main.devices"))
    form.name.data = device.device_name
    form.mac.data = device.mac_address
    # disable_input_field(form.mac)
    form.ip.data = current_config.ip_address
    form.device_type.data = device.device_type.value
    form.default_policy.data = default_policy.item
    return render_template("edit-device.html", form=form)


@bp.route("/delete-device/<int:device_id>", methods=["DELETE"])
@login_required
def delete_device(device_id):
    device = db.get_or_404(Device, device_id)
    device.delete_device()
    return redirect(url_for("main.devices"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email_address == form.email.data)).scalars().first()
        if user is not None and user.verify_password(form.password.data):
            login_user(user, form.remember_me.data)
            next_page = request.args.get("next")
            if next_page is None or not next_page.startswith("/"):
                return redirect(url_for("main.index"))
            return redirect(next_page)
        flash("Invalid username or password.")
    return render_template("login.html", form=form)


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('main.index'))


@bp.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(email_address=form.email.data,
                    username=form.username.data,
                    password=form.password.data)
        user.insert_user()
        return redirect(url_for("main.login"))
    return render_template("register.html", form=form)


@bp.route("/device-policies")
@login_required
def device_policies_overview():
    default_device = db.first_or_404(db.select(Device))
    return redirect(url_for("main.device_policies", device_id=default_device.id))


@bp.route("/device-policies/<int:device_id>", methods=["GET", "POST"])
@login_required
def device_policies(device_id):
    if request.method == 'POST':
        # Handle changes to policies
        data = request.json
        policy_updates = _map_policy_data(data)
        try:
            db.session.execute(db.update(Policy), policy_updates)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"Error while updating policies: {e}")
            db.session.rollback()
            flash("Error while updating policies.", "error")
            abort(500, "Error while updating policies.")
        return redirect(url_for("main.device_policies", device_id=device_id))

    device = db.get_or_404(Device, device_id)
    room = None
    is_offline = False
    if device.room_id is not None:
        room = db.get_or_404(Room, device.room_id)
    if room:
        is_offline = room.status == RoomStatus.OFFLINE.value
    all_devices = db.session.execute(db.select(Device)).scalars().all()
    db_policies = device.policies
    default_policy = None
    policies = []
    for db_policy in db_policies:
        if not db_policy.active:
            continue
        if db_policy.policy_type == PolicyType.DEFAULT_POLICY.value:
            default_policy = db_policy.item
            continue

        policy = dict()
        policy["id"] = db_policy.id
        if db_policy.policy_type == PolicyType.ALLOW.value:
            policy["type"] = "allow"
        elif db_policy.policy_type == PolicyType.BLOCK.value:
            policy["type"] = "block"
        policy["domain"] = db_policy.item
        policy["confirmed"] = db_policy.confirmed
        policies.append(policy)

    return render_template("policies/device-policies.html", device=device, all_devices=all_devices, policies=policies,
                           default_policy=default_policy, is_offline=is_offline)


@bp.route("/rooms", methods=["GET", "DELETE"]) # had to add delete due to the redirect from delete-room. Find proper fix later
@login_required
def rooms():
    all_rooms = Room.query.all()
    return render_template("rooms.html", rooms=all_rooms)

@bp.route("/rooms/<int:room_id>", methods=["GET", "DELETE"]) 
@login_required
def room_by_id(room_id):
    
    room = db.get_or_404(Room, room_id)
    
    return render_template("room.html", room=room)




@bp.route("/add-room", methods=["GET", "POST"])
@login_required
def add_room():
    form = RoomForm()
    if(request.method == "POST" and form.validate_on_submit()):
        # Handle form submission
        room = Room(name=form.name.data)
        for(device_id) in request.form.getlist("devices"):
            device = Device.query.get(device_id)
            device.room_id = room.id
            device.update_device()
            room.devices.append(device)
        
        room.insert_room()
        return redirect(url_for("main.rooms"))

    if(request.method=="GET"):
        unassigned_devices = Device.query.filter(Device.room_id.is_(None)).all()

        return render_template("add-room.html", form=form, devices=unassigned_devices)

@bp.route("/delete-room/<int:room_id>", methods=["DELETE"])
@login_required
def delete_room(room_id):
    room = db.get_or_404(Room, room_id)
    room.delete_room()
    return redirect(url_for("main.rooms"))

@bp.route("/highlevelpolicies", methods=["GET", "POST"])
@login_required
def highlevel_policies():
    form=HighlevelPolicyForm()
    all_rooms = Room.query.all()
    form.rooms.choices= [(room.id,room.name) for room in all_rooms] 
    form.request_threshold.data = 100
    TEMPLATE_PATH = "policies/add-highlevel-policy.html"
    if(request.method=="GET"):
        return render_template(TEMPLATE_PATH, form=form)
    

    form.validate()
    for error in form.errors.items():
        print("Error: ", error)

    if(request.method=="POST" ):
        try:
            # Handle room policy
            if form.policy_type.data == HighLevelPolicyType.ROOM_POLICY.value:
                room_policy = RoomPolicy(name=form.name.data, start_time=form.start_time.data, end_time=form.end_time.data, room_id=form.rooms.data, offline_mode=form.offline_mode.data, request_threshold=form.request_threshold.data)
                is_conflicting, policy_in_conflict = check_for_room_policy_conflicts(room_policy)
                if is_conflicting:
                    raise Exception(f"Device type policy conflicts with policy \"{policy_in_conflict.name}\", active from {policy_in_conflict.start_time} to {policy_in_conflict.end_time}.")
                room_policy.insert_room_policy()
                corresponding_room = db.get_or_404(Room, form.rooms.data)
                evaluate_room_policies(corresponding_room) # ensures room policy gets immediately activated if falling in the current timeframe
                return render_template("room.html", room=corresponding_room, created_policy_name=room_policy.name)    
            
            elif form.policy_type.data == HighLevelPolicyType.DEVICE_TYPE_POLICY.value:
                device_type_policy = DeviceTypePolicy(name=form.name.data, start_time=form.start_time.data, end_time=form.end_time.data, device_type=form.device_types.data, offline_mode=form.offline_mode.data, request_threshold=form.request_threshold.data)
                is_conflicting, policy_in_conflict = check_for_device_type_policy_conflicts(device_type_policy)
                if is_conflicting:
                    raise Exception(f"Room policy conflicts with policy \"{policy_in_conflict.name}\", active from {policy_in_conflict.start_time} to {policy_in_conflict.end_time}.")
                device_type_policy.insert_policy()

                affected_device_type = db.session.execute(db.select(DeviceType).where(DeviceType.type == device_type_policy.device_type)).scalars().first()
                evaluate_policies_per_device_type(affected_device_type)
                return redirect(url_for("main.policy_overview"))
        except Exception as e:
            current_app.logger.error(f"Error while updating highlevel policies: {e}. Stack:  " , traceback.format_exc())
            db.session.rollback()
            return render_template(TEMPLATE_PATH,form=form, error=e)
        
    return render_template(TEMPLATE_PATH,form=form)

@bp.route("/room/<int:room_id>/policies", methods=["GET", "POST"])
@login_required
def room_policy(room_id):
    ADD_ROOM_POLICY_ROUTE = "policies/add-room-policy.html"
    form = RoomPolicyForm()
    room = db.get_or_404(Room, room_id)
    if(request.method== "POST"): # adding new room policy
        if(form.validate_on_submit()):
            try:
                room_policy = RoomPolicy(name=form.name.data, start_time=form.start_time.data, end_time=form.end_time.data, room_id=room_id, offline_mode=form.offline_mode.data, request_threshold=form.request_threshold.data)
                is_conflicting, policy_in_conflict = check_for_room_policy_conflicts(room_policy)
                if is_conflicting:
                    raise Exception(f"Room policy conflicts with policy \"{policy_in_conflict.name}\", active from {policy_in_conflict.start_time} to {policy_in_conflict.end_time}.")
                room_policy.insert_room_policy()
                evaluate_room_policies(room) # ensures room policy gets immediately activated if falling in the current timeframe
                return render_template("room.html", room=room, created_policy_name=room_policy.name)    
            except Exception as e:
                current_app.logger.error(f"Error while updating room policies: {e}")
                db.session.rollback()
                return render_template(ADD_ROOM_POLICY_ROUTE, room_name=room.name ,form=form, error=e)

        return render_template(ADD_ROOM_POLICY_ROUTE, room_name=room.name ,form=form)
    if(request.method =="GET"):
        return render_template(ADD_ROOM_POLICY_ROUTE, room_name=room.name ,form=form)

@bp.route("/room/<int:room_id>/policies/<int:room_policy_id>", methods=["DELETE"])
@login_required
def delete_room_policy(room_id,room_policy_id):
    room_policy = db.get_or_404(RoomPolicy, room_policy_id)
    room_policy.delete_room_policy()
    return redirect(url_for("main.room_by_id", room_id=room_id))




# TODO: add error message
@bp.route("/rooms/policies/<int:policy_id>", methods=["GET", "POST"])
@login_required
def edit_room_policy(policy_id):
    EDIT_POLICY_URL = "policies/edit-room-policy.html"
    policy = db.get_or_404(RoomPolicy, policy_id)
    form = EditRoomPolicyForm() 
    if request.method == "GET":
        form = EditRoomPolicyForm() 
        form.name.data = policy.name
        form.start_time.data = policy.start_time
        form.end_time.data = policy.end_time
        form.offline_mode.data = policy.offline_mode
        form.request_threshold.data = policy.request_threshold
        return render_template(EDIT_POLICY_URL, policy=policy, form=form)
    
    if request.method == "POST" and form.validate_on_submit():
        policy.name = form.name.data
        policy.start_time = form.start_time.data
        policy.start_time = form.start_time.data
        policy.end_time = form.end_time.data  
        policy.offline_mode = form.offline_mode.data
        policy.request_threshold = form.request_threshold.data
        
        is_conflicting, policy_in_conflict = check_for_room_policy_conflicts(policy)
        

        if is_conflicting:
            return render_template(EDIT_POLICY_URL, policy=policy, form=form, error=f"Room policy conflicts with policy \"{policy_in_conflict.name}\", active from {policy_in_conflict.start_time} to {policy_in_conflict.end_time}.")
        else:
            try:
                policy.update_policy()
                
            except Exception as e: 
                current_app.logger.error(f"Error while updating room policy: {e}")
                db.session.rollback()
                return render_template(EDIT_POLICY_URL, policy=policy, form=form, error=e)
            
            evaluate_room_policies(policy.room)
            return redirect(url_for("main.policy_overview"))
    else:
        return render_template(EDIT_POLICY_URL, policy=policy, form=form)



@bp.route("/rooms/policies", methods=["GET"])
@login_required
def filter_room_policies():
    args = request.args
    room_id = args.to_dict()["roomId"]
    policy_status = args.to_dict()["status"]

    if room_id == "ALL":
        filtered_room_policies = RoomPolicy.query.all()
    else:
        filtered_room_policies = RoomPolicy.query.filter(RoomPolicy.room_id == room_id).all()
    
    if policy_status == HighLevelPolicyStatus.ACTIVE.value:
        filtered_room_policies =[ policy for policy in filtered_room_policies if policy.is_active()]
    elif policy_status == HighLevelPolicyStatus.ENABLED.value:
        filtered_room_policies =[ policy for policy in filtered_room_policies if policy.is_enabled()]
    elif policy_status == HighLevelPolicyStatus.DISABLED.value:
        filtered_room_policies =[ policy for policy in filtered_room_policies if not policy.is_enabled()]
    
    policy_ids = [policy.id for policy in filtered_room_policies]
    return jsonify(policy_ids)


@bp.route("/device-types/policies/<int:policy_id>", methods=["DELETE"])
@login_required
def delete_device_type_policy(policy_id):
    device_type_policy = db.get_or_404(DeviceTypePolicy, policy_id)
    device_type_policy.delete_policy()
    return redirect(url_for("main.policy_overview"))
    

@bp.route("/device-types/policies/<int:policy_id>", methods=["GET", "POST"])
def edit_device_type_policies(policy_id):
    EDIT_POLICY_URL = "policies/edit-device-type-policy.html"
    policy = db.get_or_404(DeviceTypePolicy, policy_id)
    form = EditDeviceTypePolicyForm()
    if request.method == "GET":
        form.name.data = policy.name
        form.start_time.data = policy.start_time
        form.end_time.data = policy.end_time
        form.offline_mode.data = policy.offline_mode
        form.request_threshold.data = policy.request_threshold
        return render_template(EDIT_POLICY_URL, policy=policy, form=form)
    
    if request.method == "POST" and form.validate_on_submit():
        policy.name = form.name.data
        policy.start_time = form.start_time.data
        policy.start_time = form.start_time.data
        policy.end_time = form.end_time.data  
        policy.offline_mode = form.offline_mode.data
        policy.request_threshold = form.request_threshold.data
        
        is_conflicting, policy_in_conflict = check_for_device_type_policy_conflicts(policy)

        if is_conflicting:
            return render_template(EDIT_POLICY_URL, policy=policy, form=form, error=f"Device type policy conflicts with policy \"{policy_in_conflict.name}\", active from {policy_in_conflict.start_time} to {policy_in_conflict.end_time}.")
        else:
            try:
                policy.update_policy()
                
            except Exception as e: 
                current_app.logger.error(f"Error while updating device type policy: {e}")
                db.session.rollback()
                return render_template(EDIT_POLICY_URL, policy=policy, form=form, error=e)
            

            affected_device_type = db.session.execute(db.select(DeviceType).where(DeviceType.type == policy.device_type)).scalars().first()
            evaluate_policies_per_device_type(affected_device_type)
            return redirect(url_for("main.policy_overview"))
    else:
        return render_template(EDIT_POLICY_URL, policy=policy, form=form)

    

@bp.route("/device-types/policies", methods=["GET"])
def filter_device_type_policies():
    args = request.args
    device_type = args.to_dict()["device_type"]
    policy_status = args.to_dict()["status"]

    if device_type == "ALL":
        all_policies_for_type = DeviceTypePolicy.query.all()
    else:
        all_policies_for_type = DeviceTypePolicy.query.filter(DeviceTypePolicy.device_type == device_type).all()
    
    if policy_status == HighLevelPolicyStatus.ACTIVE.value:
        filtered_device_type_policies =[ policy for policy in all_policies_for_type if policy.is_active()]
    elif policy_status == HighLevelPolicyStatus.ENABLED.value:
        filtered_device_type_policies =[ policy for policy in all_policies_for_type if policy.is_enabled()]
    elif policy_status == HighLevelPolicyStatus.DISABLED.value:
        filtered_device_type_policies =[ policy for policy in all_policies_for_type if not policy.is_enabled()]
    else:
        filtered_device_type_policies = all_policies_for_type
    
    policy_ids = [policy.id for policy in filtered_device_type_policies]

    return jsonify(policy_ids)


# definitively not beautiful but it works
def create_frontend_highlevel_policy_object(policy: RoomPolicy, type: HighLevelPolicyType):
    '''Takes an instance of RoomPolicy and returns a dictionary with the same attributes except for stat'''
    frontend_policy = dict()
    frontend_policy["id"] = policy.id
    frontend_policy["name"] = policy.name
    frontend_policy["start_time"] = policy.start_time
    frontend_policy["end_time"] = policy.end_time
    frontend_policy["offline_mode"] = policy.offline_mode
    frontend_policy["request_threshold"] = policy.request_threshold
    
    frontend_policy["threshold_warning_sent"] = policy.threshold_warning_sent
    
    if(type == HighLevelPolicyType.DEVICE_TYPE_POLICY):
        frontend_policy["device_type"] = policy.device_type

    elif(type == HighLevelPolicyType.ROOM_POLICY): 
        frontend_policy["room_id"] = policy.room_id
        frontend_policy["room_name"] = policy.room.name

    if policy.is_active():
        frontend_policy["status"] = "active"
    elif(policy.is_enabled()):
        frontend_policy["status"] = "enabled"
    else:
        frontend_policy["status"] = "disabled"

    return frontend_policy

# deletion because of redirection accepted. There has to be a better way...
@bp.route("/policies", methods=["GET", "DELETE"])
@login_required
def policy_overview():
    all_room_policies = RoomPolicy.query.all()
    all_room_policies_mapped= [create_frontend_highlevel_policy_object(policy, HighLevelPolicyType.ROOM_POLICY) for policy in all_room_policies]
    all_rooms = Room.query.all()
    all_devices = Device.query.all()
    all_device_type_policies = DeviceTypePolicy.query.all()
    all_device_type_policies_mapped = [create_frontend_highlevel_policy_object(policy, HighLevelPolicyType.DEVICE_TYPE_POLICY) for policy in all_device_type_policies]
    device_types = {device_type.value for device_type in DeviceTypeEnum}
    policy_status = {status.value for status in HighLevelPolicyStatus}
    device_policy_status = {status.value for status in DevicePolicyStatus}
    
    return render_template("policies/policy-overview.html", room_policies=all_room_policies_mapped, all_devices=all_devices, policy_type=PolicyType, all_device_type_policies = all_device_type_policies_mapped, device_types=device_types, policy_states=policy_status, all_rooms=all_rooms, device_policy_status=device_policy_status) 




@bp.route("/devices/policies", methods=["GET"])
def filter_device_policies():
    args = request.args
    device_id = args.to_dict()["deviceId"]
    policy_status = args.to_dict()["status"]
    permission = args.to_dict()["permission"]
    print("SELECTED PERMISSION: ", permission);
    if device_id == "ALL":
        all_policies_for_type = Policy.query.all()
    else:
        all_policies_for_type = Policy.query.filter(Policy.device_id == device_id).all()
    
    if policy_status == DevicePolicyStatus.ACTIVE.value:
        filtered_device_policies =[ policy for policy in all_policies_for_type if policy.active]
    elif policy_status == DevicePolicyStatus.INACTIVE.value:
        filtered_device_policies =[ policy for policy in all_policies_for_type if not policy.active]
    else:
        filtered_device_policies = all_policies_for_type
    
    if permission == "ALLOWED":
        filtered_device_policies =[ policy for policy in filtered_device_policies if policy.policy_type == PolicyType.ALLOW.value]
    elif permission == "BLOCKED":
        filtered_device_policies =[ policy for policy in filtered_device_policies if policy.policy_type == PolicyType.BLOCK.value]

    policy_ids = [policy.id for policy in filtered_device_policies]

    return jsonify(policy_ids)



def disable_input_field(input_field):
    if input_field.render_kw is None:
        input_field.render_kw = {}
    input_field.render_kw["disabled"] = "disabled"


def _map_policy_data(data):
    policies = []
    for dp in data:
        policy = dict()
        policy["id"] = dp["id"]
        if dp["type"] == "allow":
            policy["policy_type"] = PolicyType.ALLOW.value
        elif dp["type"] == "block":
            policy["policy_type"] = PolicyType.BLOCK.value
        policy["confirmed"] = dp["confirmed"]
        policy["item"] = dp["domain"]
        policies.append(policy)
    return policies
