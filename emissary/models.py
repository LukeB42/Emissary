"""
Database layout for Emissary.
Luke Brooks 2015, MIT License.
"""
from emissary import db
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

class FeedGroup(db.Model):
	__tablename__ = "feed_groups"
	id      = db.Column(db.Integer(), primary_key=True)
	name    = db.Column(db.String(80))
	feeds   = db.relationship('Feed', backref="group")
	created = db.Column(db.DateTime(), default=db.func.now())

	def __repr__(self):
		return "<FeedGroup>"

	def jsonify(self):
		return {}

class Feed(db.Model):
	__tablename__ = "feeds"
	id       = db.Column(db.Integer(), primary_key=True)
	name     = db.Column(db.String(80))
	url      = db.Column(db.String(80))
	timings  = db.Column(db.String(80))
	articles = db.relationship('Article', backref="feed")
	created  = db.Column(db.DateTime(), default=db.func.now())
	active   = db.Column(db.Boolean())

	def __repr__(self):
		return "<Feed>"

	def jsonify(self):
		return {}

class Article(db.Model):
	__tablename__ = "articles"
	id      = db.Column(db.Integer(), primary_key=True)
	feed_id = db.Column(db.Integer(), db.ForeignKey("feeds.id"))
	name    = db.Column(db.String(80))
	content = db.Column(db.String())
	created = db.Column(db.DateTime(), default=db.func.now())

	def __repr__(self):
		return "<Article>"

	def jsonify(self):
		return {}
