"""
MIT License.
Luke Brooks 2015
Database layout for Emissary.
"""
from uuid import uuid4
from emissary import db
from emissary.controllers.utils import uid
# 
#       /--Subprocesses for checking feed timing data
# hermes
#       \_ REST service
#
# Start
# Divide feeds between workers
# process control
# Check if the timings have changed after each fetch.
#

class APIKey(db.Model):
	__tablename__ = 'api_keys'
	id         = db.Column(db.Integer, primary_key=True)
	name       = db.Column(db.String(80))
	key        = db.Column(db.String(120))
	active     = db.Column(db.Boolean())
	created    = db.Column(db.DateTime(), default=db.func.now())
	feedgroups = db.relationship("FeedGroup", backref="key")
	feeds      = db.relationship("Feed", backref="key")
	articles   = db.relationship("Article", backref="key")
#	events = db.relationship("Event", backref="key")

	def generate_key_str(self):
		return str(uuid4())

	def jsonify(self, feedgroups=False, with_key_str=False):
		response = {}
		response['name']       = self.name
		if with_key_str:
			response['apikey'] = self.key
		if feedgroups:
			response['feedgroups'] = [grp.jsonify() for grp in self.feedgroups]
		response['active'] = self.active
		return response

class FeedGroup(db.Model):
	__tablename__ = "feed_groups"
	id      = db.Column(db.Integer(), primary_key=True)
	key_id  = db.Column(db.Integer(), db.ForeignKey("api_keys.id"))
	uid     = db.Column(db.String(), default=uid())
	name    = db.Column(db.String(80))
	feeds   = db.relationship('Feed', backref="group")
	created = db.Column(db.DateTime(), default=db.func.now())
	active  = db.Column(db.Boolean(), default=True)

	def __repr__(self):
		return "<FeedGroup>"

	def jsonify(self):
		return {}

class Feed(db.Model):
	__tablename__ = "feeds"
	id       = db.Column(db.Integer(), primary_key=True)
	key_id   = db.Column(db.Integer(), db.ForeignKey("api_keys.id"))
	group_id = db.Column(db.Integer(), db.ForeignKey("feed_groups.id"))
	uid      = db.Column(db.String(), default=uid())
	name     = db.Column(db.String(80))
	url      = db.Column(db.String(80))
	schedule = db.Column(db.String(80))
	articles = db.relationship('Article', backref="feed")
	created  = db.Column(db.DateTime(), default=db.func.now())
	active   = db.Column(db.Boolean(), default=True)

	def __repr__(self):
		return "<Feed>"

	def jsonify(self):
		return {}

class Article(db.Model):
	__tablename__ = "articles"
	id      = db.Column(db.Integer(), primary_key=True)
	key_id  = db.Column(db.Integer(), db.ForeignKey("api_keys.id"))
	uid     = db.Column(db.String(), default=uid())
	feed_id = db.Column(db.Integer(), db.ForeignKey("feeds.id"))
	title   = db.Column(db.String(80))
	content = db.Column(db.String())
	created = db.Column(db.DateTime(), default=db.func.now())

	def __repr__(self):
		return "<Article>"

	def jsonify(self):
		return {}

class Event(db.Model):
	__tablename__ = "events"
	id = db.Column(db.Integer(), primary_key=True)
	key_id = db.Column(db.Integer(), db.ForeignKey("api_keys.id"))
	created = db.Column(db.DateTime(), default=db.func.now())
	feed_id = db.Column(db.Integer(), db.ForeignKey("feeds.id"))
	success = db.Column(db.Boolean())
	message = db.Column(db.String())

	def __repr__(self):
		return "<Event>"

	def jsonify(self):
		return {}
