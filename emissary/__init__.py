from flask import Flask
from flask.ext import restful
from pkgutil import extend_path
from multiprocessing import Queue
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.engine.reflection import Inspector

__path__ = extend_path(__path__, __name__)
__all__ = ["client", "controllers", "models", "resources", "run"]

app = Flask("emissary")
app.config.from_object("emissary.config")

app.version = "1.3"
app.inbox = Queue()
app.feedmanager = None
app.config["HTTP_BASIC_AUTH_REALM"] = "Emissary " + app.version

db = SQLAlchemy(app)
api = restful.Api(app, prefix='/v1')

# Models are imported here to prevent a circular import where we would
# import models and the models would import that db object just above us.
from models import *
from resources import api_key
from resources import feeds
from resources import feedgroups

api.add_resource(api_key.KeyCollection,          "/keys")
api.add_resource(api_key.KeyResource,            "/keys/<string:name>")
api.add_resource(feeds.FeedCollection,           "/feeds")
api.add_resource(feeds.FeedResource,             "/feeds/<string:name>")
api.add_resource(feedgroups.FeedGroupCollection, "/feedgroups")
api.add_resource(feedgroups.FeedGroupResource,   "/feedgroups/<string:name>")

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
