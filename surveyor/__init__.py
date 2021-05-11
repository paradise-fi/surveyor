from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

app = Flask(__name__)
try:
    app.config.from_pyfile('configuration/default.py')
except FileNotFoundError as e:
    app.config.from_envvar('SURVEYOR_CFG')

db = SQLAlchemy(app)
migrate = Migrate(app, db)

from surveyor.admin_cli import *
from surveyor import models
from surveyor import api