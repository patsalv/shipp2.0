# Bundle all sections and expose the Flask APP
from flask import Flask
from config import config
import logging
from flask.logging import default_handler
from sqlalchemy_utils.functions import database_exists
from flask_migrate import stamp
from app.models.database_model import DeviceType
from app.constants import DeviceTypeEnum


def create_app(config_name: str):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    if config_name == "production":
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
        )

    with app.app_context():
        app.logger.setLevel(logging.INFO)

        from app.extensions import db, login_manager, migrate
        db.init_app(app)
        login_manager.init_app(app)
        logging.getLogger('sqlalchemy').addHandler(default_handler)
        import app.models as models # noqa F401

        migrate.init_app(app, db)

        if not database_exists(db.engine.url):
            db.create_all(bind_key=None)
            stamp()
            app.logger.info("Database created")

            try:
                for device_type_enum in DeviceTypeEnum:
                    device_type = DeviceType(type=device_type_enum.value)
                    db.session.add(device_type)
                    db.session.commit()

            except Exception as e:
                app.logger.error(f"Could not initialize device types (might already exist): {e}")

        from app import views
        app.register_blueprint(views.bp)

        from app.dashapp.dashboard import init_dashboard
        try:
            app.logger.info("Initializing dashboard")
            app = init_dashboard(app)
            app.logger.info("Dashboard initialized")
        except Exception as e:
            app.logger.error(f"Could not initialize dashboard: {e}")

        return app
