from flask import Flask
from flask.ext import restful
from pkgutil import extend_path
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.engine.reflection import Inspector

__path__ = extend_path(__path__, __name__)
__all__ = ["client", "controllers", "models", "repl", "resources", "run"]

app = Flask("emissary")
#app.config.from_object("emissary.config")

app.version = "1.3"
app.config["HTTP_BASIC_AUTH_REALM"] = "Emissary " + app.version
api = restful.Api(app, prefix='/v1')
db = SQLAlchemy(app)

# Models are imported here to prevent a circular import where we would
# import models here and models would import that db object just above us
from models import *
from resources import api_key

api.add_resource(api_key.KeyCollection,    "/keys")
api.add_resource(api_key.KeyResource,      "/keys/<string:name>")

def init():
	inspector = Inspector.from_engine(db.engine)
	tables = [table_name for table_name in inspector.get_table_names()]

	if 'api_keys' not in tables:
		db.create_all()
		master = models.APIKey(name = app.config['MASTER_KEY_NAME'])
		if app.config['MASTER_KEY']: master.key = app.config['MASTER_KEY']
		else: master.key = master.generate_key_str()
		print master.key
		master.active = True
		db.session.add(master)
		db.session.commit()

