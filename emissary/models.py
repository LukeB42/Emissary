# _*_ coding: utf-8 _*_
"""
MIT License.
Luke Brooks 2015
Database layout for Emissary.
"""
import time
from uuid import uuid4
from emissary import db, app
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
	events = db.relationship("Event", backref="key")

	def generate_key_str(self):
		return str(uuid4())

	def jsonify(self, feedgroups=False, with_key_str=False):
		response = {}
		response['name']       = self.name
		if with_key_str:
			response['apikey'] = self.key
		if feedgroups:
			response['feedgroups'] = [group.jsonify() for group in self.feedgroups]
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
		if self.name:
			return '<FeedGroup "%s" with %i feeds>' % (self.name, len(self.feeds))
		return "<FeedGroup>"

	def jsonify(self):
		response = {}
		if self.created:
			response['name'] = self.name
			response['uid'] = self.uid
			response['created'] = time.mktime(self.created.timetuple())
			response['active'] = self.active
			response['feeds'] = [feed.jsonify() for feed in self.feeds]
		return response

class Feed(db.Model):
	__tablename__ = "feeds"
	id       = db.Column(db.Integer(), primary_key=True)
	key_id   = db.Column(db.Integer(), db.ForeignKey("api_keys.id"))
	group_id = db.Column(db.Integer(), db.ForeignKey("feed_groups.id"))
	uid      = db.Column(db.String(),  default=uid())
	name     = db.Column(db.String(80))
	url      = db.Column(db.String(80))
	schedule = db.Column(db.String(80))
	active   = db.Column(db.Boolean(), default=True)
	created  = db.Column(db.DateTime(), default=db.func.now())
	articles = db.relationship('Article', backref="feed")

	def __repr__(self):
		if self.name:
			return '<Feed "%s" with %i articles>' % (self.name, len(self.articles))
		return "<Feed>"

	def is_running(self):
		if app.feedmanager:
			pass
		return False

	def jsonify(self, articles=False):
		response = {}
		if self.created:
			response['name'] = self.name
			response['uid'] = self.uid
			response['url'] = self.url
			response['created'] = time.mktime(self.created.timetuple())
			response['schedule'] = self.schedule
			response['active'] = self.active
			response['article_count'] = len(self.articles)
			response['running'] = self.is_running()
		if self.group:
			response['group'] = self.group.name
		else:
			response['group'] = None
		return response


class Article(db.Model):
	__tablename__ = "articles"
	id      = db.Column(db.Integer(), primary_key=True)
	key_id  = db.Column(db.Integer(), db.ForeignKey("api_keys.id"))
	uid     = db.Column(db.String(), default=uid())
	feed_id = db.Column(db.Integer(), db.ForeignKey("feeds.id"))
	title   = db.Column(db.String(80))
	url     = db.Column(db.String())
	content = db.Column(db.String())
	summary = db.Column(db.String())
	created = db.Column(db.DateTime(), default=db.func.now())

	def __repr__(self):
		if self.content:
			return '<Article "%s">' % self.title.encode("utf-8", "ignore")
		if self.url and self.title:
			return "<Article reference to %s>" % self.title.encode("utf-8", "ignore")
		return "<Article>"

	def jsonify(self, summary=False, content=False):
		response = {}
		if self.title:
			response['title'] = self.title
			response['url'] = self.url	
			response['uid'] = self.uid
			response['created'] = time.mktime(self.created.timetuple())
		if self.feed:
			response['feed'] = self.feed.name
		if content and self.content:
			response['content'] = self.content
		if summary and self.summary:
			response['summary'] = self.summary
		return response

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
