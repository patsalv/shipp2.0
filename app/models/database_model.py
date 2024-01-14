from sqlalchemy import Enum
from app.extensions import db, cipher_suite, login_manager
from app.constants import DeviceType, PolicyType,RoomStatus
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app.helpers.helpers import is_in_timeframe

class Device(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.String(17), unique=True, nullable=False)
    device_name = db.Column(db.String(64))
    device_type = db.Column(Enum(DeviceType), nullable=False)
    device_configs = db.relationship('DeviceConfig', backref='device', lazy="dynamic")
    policies = db.relationship("Policy", backref='device', lazy="dynamic")
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=True)
    
    def get_current_config(self):
        return self.device_configs.filter_by(valid_to=None).first()

    def get_active_policies(self):
        return self.policies.filter_by(active=True).all()

    def get_default_policy(self):
        return self.policies.filter_by(policy_type=PolicyType.DEFAULT_POLICY.value).one()

    def insert_device(self):
        db.session.add(self)
        db.session.commit()

    def update_device(self):
        db.session.add(self)
        db.session.commit()

    def delete_device(self):
        for config in self.device_configs.all():
            db.session.delete(config)
        db.session.flush()
        for policy in self.policies.all():
            db.session.delete(policy)
        db.session.flush()
        db.session.delete(self)
        db.session.commit()

    def __repr__(self):
        return '<Device %r>' % self.mac_address


class DeviceConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    valid_from = db.Column(db.DateTime, default=datetime.now(), nullable=False)
    valid_to = db.Column(db.DateTime, index=True)
    ip_address = db.Column(db.String(39), nullable=False)

    def insert_device_config(self):
        db.session.add(self)
        db.session.commit()

    def update_device_config(self):
        db.session.add(self)
        db.session.commit()

    def delete_device_config(self):
        db.session.delete(self)
        db.session.commit()

    def __repr__(self):
        return '<DeviceConfig %r>' % self.id


class Policy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey('device.id'), nullable=False)
    policy_type = db.Column(db.Uuid, nullable=False, index=True)
    item = db.Column(db.String(64))
    active = db.Column(db.Boolean, default=True, nullable=False)
    confirmed = db.Column(db.Boolean, default=False, nullable=False)
    date_modified = db.Column(db.Integer, nullable=False, default=db.func.strftime('%s', 'now'), onupdate=db.func.strftime('%s', 'now'))

    def insert_policy(self):
        db.session.add(self)
        db.session.commit()

    def update_policy(self):
        db.session.add(self)
        db.session.commit()

    def delete_policy(self):
        db.session.delete(self)
        db.session.commit()

    def __repr__(self):
        return '<Policy %r>' % self.id


class MonitoringReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_source = db.Column(db.Uuid, nullable=False, index=True)
    interval_start = db.Column(db.DateTime, nullable=False)
    interval_end = db.Column(db.DateTime, nullable=False)
    total_queries = db.Column(db.Integer, nullable=False)
    unique_domains = db.Column(db.Integer, nullable=False)
    queries_blocked = db.Column(db.Integer, nullable=False)
    evt_create = db.Column(db.DateTime, nullable=False, default=datetime.now())


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email_address = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    api_keys = db.relationship('UserApiKey', backref='user', lazy="dynamic")

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def insert_user(self):
        db.session.add(self)
        db.session.commit()

    def update_user(self):
        db.session.add(self)
        db.session.commit()

    def delete_user(self):
        db.session.delete(self)
        db.session.commit()

    def __repr__(self):
        return '<User %r>' % self.username


# Needed for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).where(User.id == user_id)).scalar_one_or_none()


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(64), default=RoomStatus.ONLINE.value, nullable=False)
    policies = db.relationship("RoomPolicy", backref='room', lazy="dynamic")
    devices = db.relationship("Device", backref='room', lazy="dynamic")

    def insert_room(self):
        db.session.add(self)
        db.session.commit()

    def update_room(self):
        db.session.add(self)
        db.session.commit()

    # TODO: implement better deletion logic. Should first delete all room_policies that exist for this 
    # room as well as remove the rooms from the devices
    def delete_room(self):
        db.session.delete(self)
        db.session.commit() 

    def has_active_offline_policy (self) -> bool:
        room_policies = db.session.execute(db.select(RoomPolicy).where(RoomPolicy.room_id == self.id)).scalars().all()
        current_time = datetime.now().time()
        for room_policy in room_policies:
            if not(room_policy.offline_mode):
                continue
            if is_in_timeframe(room_policy.start_time, room_policy.end_time, current_time) and room_policy.active:
                return True

        return False    

    def needs_status_update(self):
        has_active_offline_policy = self.has_active_offline_policy()
        if self.status == RoomStatus.OFFLINE.value and not has_active_offline_policy:
            return True
        if self.status == RoomStatus.ONLINE.value and has_active_offline_policy:
            return True
    
        return False

class RoomPolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    offline_mode = db.Column(db.Boolean, default=True, nullable=False)
    request_threshold = db.Column(db.Integer, nullable=True, default=None)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)

    def insert_room_policy(self):
        db.session.add(self)
        db.session.commit()

    def update_room_policy(self):
        db.session.add(self)
        db.session.commit()

    def delete_room_policy(self):
        db.session.delete(self)
        db.session.commit()


class DeviceTypePolicy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    offline_mode = db.Column(db.Boolean, default=True, nullable=False)
    request_threshold = db.Column(db.Integer, nullable=True, default=None)
    device_type = db.Column(Enum(DeviceType), nullable=False)

    def insert_policy(self):
        db.session.add(self)
        db.session.commit()

    def update_policy(self):
        db.session.add(self)
        db.session.commit()

    def delete_policy(self):
        db.session.delete(self)
        db.session.commit()

# TODO: Evaluate if this is needed or if we just use env variables (Would need API type / Base URL / Auth type...)
class UserApiKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    ext_system = db.Column(db.Uuid, nullable=False)
    encrypted_api_key = db.Column(db.String(128), nullable=False)

    @property
    def api_key(self):
        decrypted_api_key = cipher_suite.decrypt(self.encrypted_api_key.encode())
        return decrypted_api_key.decode()

    @api_key.setter
    def api_key(self, api_key):
        self.encrypted_api_key = cipher_suite.encrypt(api_key.encode())

    def insert_api_key(self):
        db.session.add(self)
        db.session.commit()

    def update_api_key(self):
        db.session.add(self)
        db.session.commit()

    def delete_api_key(self):
        db.session.delete(self)
        db.session.commit()
