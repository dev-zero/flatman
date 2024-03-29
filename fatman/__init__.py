
import logging

from flask import Flask, g
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_uploads import UploadSet, configure_uploads, ALL as ALL_EXTENSIONS
from flask_security import Security, SQLAlchemyUserDatastore
from flask_caching import Cache
from flask_httpauth import HTTPBasicAuth
from flask_security.utils import verify_password as fs_verify_password
from celery import Celery
from blinker import Namespace  # Flask already implements signals using blinker
from flask_marshmallow import Marshmallow


app = Flask(__name__)
app.config.from_object('fatman.default_settings')
app.config.from_pyfile('fatman.cfg', silent=True)
app.config.from_pyfile('../fatman.cfg', silent=True)
app.config.from_envvar('FATMAN_SETTINGS', silent=True)

if 'SECURITY_POST_LOGIN_VIEW' not in app.config:
    app.config['SECURITY_POST_LOGIN_VIEW'] = app.config['APPLICATION_ROOT']
if 'SECURITY_POST_LOGOUT_VIEW' not in app.config:
    app.config['SECURITY_POST_LOGOUT_VIEW'] = app.config['APPLICATION_ROOT']


def configure_db_logger():
    logger = logging.getLogger('sqlalchemy.engine')
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

if app.config.get('DATABASE_LOG_QUERIES', False):
    configure_db_logger()


signals = Namespace()
calculation_finished = signals.signal('calculation-finished')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
ma = Marshmallow(app)

resultfiles = UploadSet('results', extensions=ALL_EXTENSIONS)
configure_uploads(app, (resultfiles,))

# initialize Flask-Caching
cache = Cache(app)


# initialize Celery
def setup_celery():
    # we need pickle support to serialize exceptions from
    # tasks, otherwise we would need a catch-all handler in them.
    app.config['CELERY_ACCEPT_CONTENT'] = ['pickle', 'json']

    capp = Celery(app.import_name,
                  backend=app.config['CELERY_BACKEND'],
                  broker=app.config['CELERY_BROKER_URL'])
    capp.conf.update(app.config)

    TaskBase = capp.Task

    # Inject the Flask context in Celery tasks
    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    capp.Task = ContextTask

    return capp

capp = setup_celery()


from .models import User, Role
user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)

# will be replaced by a MultiAuth using tokens later
apiauth = HTTPBasicAuth(realm=app.name)


@apiauth.verify_password
def verify_password(username, password):
    g.user = None
    try:
        user = (User.query
                .filter_by(email=username)
                .one())

        if fs_verify_password(password, user.password):
            g.user = user
            return True

    except:
        pass

    return False


# The imports are deliberately at this place.
# They import this file itself, but need all other global objects to be ready.
# On the other hand we import them here to hook them up into Flask.
from . import models, views, admin, api, api_v2, cli, notifications
