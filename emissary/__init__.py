# _*_ coding: utf-8 _*_
import time
from flask import Flask
from flask.ext import restful
from pkgutil import extend_path
from multiprocessing import Queue, cpu_count
from flask.ext.sqlalchemy import SQLAlchemy
from sqlalchemy.engine.reflection import Inspector

__path__ = extend_path(__path__, __name__)
__all__ = ["client", "controllers", "models", "resources", "run", "repl"]

app = Flask("emissary")

# This config is the default and can be overridden by
# using options.config in run.py (python -m emissary.run -c somefile.py)
app.config.from_object("emissary.config")

app.version = "1.3"
app.inbox = Queue()
app.feedmanager = None
app.config["HTTP_BASIC_AUTH_REALM"] = "Emissary " + app.version

# These are response queues that enable the main thread of execution to
# share data with the REST interface. Mainly for reporting the status of crontabs.
app.queues = []
for i in range(cpu_count() * 2):
	q = Queue()
	q.access = time.time()
	app.queues.append(q)

db = SQLAlchemy(app)
api = restful.Api(app, prefix='/v1')

def init():
	# Models are imported here to prevent a circular import where we would
	# import models and the models would import that db object just above us.

	# They're also imported here in this function because they implicitly
	# monkey-patch the threading module, and we might not need that if all we want
	# from the namespace is something like app.version, like in repl.py for example.
	from models import APIKey
	from models import FeedGroup
	from models import Feed
	from models import Article
	from models import Event

	from resources import api_key
	from resources import feeds
	from resources import feedgroups
	from resources import articles

	api.add_resource(api_key.KeyCollection,          "/keys")
	api.add_resource(api_key.KeyResource,            "/keys/<string:name>")
	api.add_resource(feeds.FeedCollection,           "/feeds")
	api.add_resource(feeds.FeedResource,             "/feeds/<string:name>")
	api.add_resource(feedgroups.FeedGroupCollection, "/feedgroups")
	api.add_resource(feedgroups.FeedGroupResource,   "/feedgroups/<string:name>")
	api.add_resource(articles.ArticleCollection,     "/articles")
	api.add_resource(articles.ArticleResource,       "/articles/<string:uid>")

	# Create the database schema if it's not already laid out.
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
