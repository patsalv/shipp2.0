# App routing
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, abort
from app.extensions import db
from app.models import Device, DeviceConfig, User, Policy, Room, RoomPolicy
from app.forms import DeviceForm, LoginForm, RegistrationForm, RoomForm, RoomPolicyForm
from datetime import datetime
from flask_login import login_required, login_user, logout_user
from app.constants import PolicyType, RoomStatus
from app.policy_engine.policy_engine import check_for_room_policy_conflicts
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
        Device.id, Device.device_name, Device.mac_address, DeviceConfig.ip_address, DeviceConfig.valid_from)
                                        .join(Device.device_configs).where(DeviceConfig.valid_to == None))  # noqa: E711
    return render_template("devices.html", devices=active_devices)


@bp.route("/add-device", methods=["GET", "POST"])#@login_required
def add_device():
    form = DeviceForm()
    if form.validate_on_submit(): #not getting into this if statement
        print("add_device form successfully validated")
        device = Device(mac_address=form.mac.data, device_name=form.name.data)
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
    
    print("returning the add-device.html page again... validation failed")    
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
def rooms():
    all_rooms = Room.query.all()
    return render_template("rooms.html", rooms=all_rooms)

@bp.route("/rooms/<int:room_id>", methods=["GET", "DELETE"]) 
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


@bp.route("/room/<int:room_id>/policies", methods=["GET", "POST"])
@login_required
def room_policy(room_id):
    form = RoomPolicyForm()
    room = db.get_or_404(Room, room_id)
    if(request.method== "POST"): # adding new room policy
        if(form.validate_on_submit()):
            try:
                room_policy = RoomPolicy(name=form.name.data, start_time=form.start_time.data, end_time=form.end_time.data, room_id=room_id)
                is_conflicting, conflicting_policy_id = check_for_room_policy_conflicts(room_policy)
                if is_conflicting:
                    raise Exception(f"Room policy conflicts with policy with id {conflicting_policy_id}")
                room_policy.insert_room_policy()
                return redirect(url_for("main.rooms"))    
            except Exception as e:
                current_app.logger.error(f"Error while updating room policies: {e}")
                db.session.rollback()
                flash("Error while updating policies.", "error")

        return render_template("policies/add-room-policy.html", room_name=room.name ,form=form)
    if(request.method =="GET"):
        return render_template("policies/add-room-policy.html", room_name=room.name ,form=form)

@bp.route("/room/<int:room_id>/policies/<int:room_policy_id>", methods=["DELETE"])
@login_required
def delete_room_policy(room_id,room_policy_id):
    print("room_id: ", room_id)
    room_policy = db.get_or_404(RoomPolicy, room_policy_id)
    room_policy.delete_room_policy()
    return redirect(url_for("main.room_by_id", room_id=room_id))
    # return redirect(url_for("main.room", room_id=room_policy.room_id))


@bp.route("/policies")
@login_required
def policies():
    all_room_policies = RoomPolicy.query.all()
    all_devices = Device.query.all()
    return render_template("policies/policy-overview.html", room_policies=all_room_policies, all_devices=all_devices)


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
        policy["item"] = dp["domain"]
        policy["confirmed"] = dp["confirmed"]
        policies.append(policy)
    return policies
