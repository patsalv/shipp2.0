import datetime
from dotenv import load_dotenv
from logging.config import dictConfig
import os

dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

from app import create_app
from flask_migrate import upgrade
from app.extensions import db

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

current_config: str = None

if os.getenv('FLASK_ENV') == 'production':
    current_config = "production"
else:
    current_config = "development"

app = create_app(current_config)


@app.cli.command()
def execute_job():
    """Run scheduled job"""
    with app.app_context():
        from app.monitors.pihole_monitor import fetch_query_data_job
        app.logger.info("Starting monitoring job")
        fetch_query_data_job()

@app.cli.command()
def execute_highlevel_policy_evaluation():
    """Run room evaluation"""
    with app.app_context():
        from app.policy_engine.policy_engine import evaluate_device_type_policies
        from app.policy_engine.policy_engine import evaluate_rooms
        app.logger.info("Starting room evaluation")
        evaluate_rooms()
        evaluate_device_type_policies()

@app.cli.command()
def check_threshold():
    """Threshold violation check"""
    with app.app_context():
        from app.policy_engine.policy_engine import check_for_request_threshold_violation
        app.logger.info("Starting room evaluation")
        check_for_request_threshold_violation()


@app.cli.command()
def deploy():
    """Run deployment tasks."""
    # migrate database to latest revision
    upgrade()

@app.cli.command()
def get_current_time():
    """Get current time (to debug)"""
    print("Current time: ", datetime.datetime.now(), "TZ from .env: ", os.getenv('TZ'))
    

@app.cli.command()
def execute_weekly_notifications():
    """Send weekly notification to users"""
    from app.reporting.email_notification_service import send_weekly_emails
    with app.app_context():
        send_weekly_emails()
        app.logger.info("Sent all weekly notifications")


@app.cli.command()
def db_reset():
    """Reset database"""
    with app.app_context():
        db.drop_all()
        db.create_all()
        app.logger.info("Database reset")


@app.cli.command()
def db_add_device_types():
    """Reset database"""
    with app.app_context():
        from app.models.database_model import DeviceType
        from app.constants import DeviceTypeEnum
        for device_type_enum in DeviceTypeEnum:
            device_type = DeviceType(type=device_type_enum.value)
            db.session.add(device_type)
            db.session.commit()

@app.cli.command()
def init_mock_devices():
    """initialize mock devies"""
    with app.app_context():
        from app.constants import DeviceTypeEnum
        from app.helpers.helpers import initialize_mock_device
        initialize_mock_device("Ikea Tradfri Hub","8C:45:00:69:3B:B7", "192.168.188.26", DeviceTypeEnum.LIGHT)
        initialize_mock_device("Security Camera","40:ED:00:20:B3:B1", "192.168.188.29", DeviceTypeEnum.CAMERA)
        initialize_mock_device("Smart Socket Bed","18:DE:50:77:01:4C", "192.168.188.31", DeviceTypeEnum.SOCKET)
        initialize_mock_device("Smart Socket Desk","18:DE:50:76:FD:E9", "192.168.188.34", DeviceTypeEnum.SOCKET)
       

@app.cli.command()
def db_update():
    """Update database with newly added models"""
    with app.app_context():
        db.create_all()
        app.logger.info("Database updated")



@app.shell_context_processor
def make_shell_context():
    from app.models import Device, Policy, DeviceConfig, User, Client, Group, Domainlist
    return dict(db=db, Device=Device, DeviceConfig=DeviceConfig, Policy=Policy, User=User, Client=Client, Group=Group,
                Domainlist=Domainlist)


if __name__ == '__main__':
    app.logger.info("Starting with app.run()..")
    app.run(debug=True, use_debugger=False, use_reloader=False, passthrough_errors=True)
