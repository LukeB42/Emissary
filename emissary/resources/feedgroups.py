# _*_ coding: utf-8 _*_
# This file provides the /v1/feedgroups endpoint
from emissary import app, db
from flask import request
from sqlalchemy import and_
from flask.ext import restful
from emissary.models import FeedGroup
from emissary.resources.api_key import auth
from emissary.controllers.utils import gzipped

class FeedGroupCollection(restful.Resource):

	@gzipped
	def get(self):
		"""
		 Return an array of JSON objects for each feed group
		 associated with the requesting API key.
		"""
		key = auth()
		return [fg.jsonify() for fg in key.feedgroups]

	@gzipped
	def put(self):
		"""
		 Create a new feed group, providing the name isn't already in use.
		"""
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("name",  type=str, help="", required=True)
		parser.add_argument("active",type=bool, default=True, help="Feed is active", required=False)
		args = parser.parse_args()

		# Check for this name already existing in the groups on this key
		if [fg for fg in key.feedgroups if fg.name == args.name]:
			return {"message":"Feed group %s already exists." % args.name}, 304

		fg = FeedGroup(name=args.name, active=args.active)
		key.feedgroups.append(fg)
		db.session.add(fg)
		db.session.add(key)
		db.session.commit()

		return fg.jsonify(), 201

class FeedGroupResource(restful.Resource):

	@gzipped
	def get(self, groupname):
		"""
		 Review a specific feed group.
		"""
		key = auth()

		fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
		if not fg:
			restful.abort(404)
		return fg.jsonify()


	@gzipped
	def post(self, groupname):
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("name",type=str, help="Rename a feed group",)
		parser.add_argument("active",type=bool, default=None, help="Stop/restart a group of feeds")
		args = parser.parse_args()

		return {}

	@gzipped
	def delete(self, groupname):
		key = auth()
		
		fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
		if not fg:
			restful.abort(404)
		count=0
		for feed in fg.feeds:
			for article in feed.articles:
				count += 1
				db.session.delete(article)
			db.session.delete(feed)
		db.session.delete(fg)
		db.session.commit()
		count = "{:,}".format(count)
		app.log('%s: Deleted feed group "%s". (%s articles)' % (key.name, fg.name, count))

		return {}

class FeedGroupArticles(restful.Resource):

	def get(self, groupname):
		"""
		 Retrieve articles by feedgroup.
		"""

		key = auth()

		fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
		if not fg:
			restful.abort(404)

		return {}

class FeedGroupStart(restful.Resource):

	def post(self, groupname):
		"""
		 Start all feeds within a group.
		"""
		key = auth()

		fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
		if not fg:
			restful.abort(404)

		for feed in fg.feeds:
			app.inbox.put([0, "start", [key,feed.name]])
		return {}

class FeedGroupStop(restful.Resource):

	def post(self, groupname):
		key = auth()

		fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
		if not fg:
			restful.abort(404)

		for feed in fg.feeds:
			app.inbox.put([0, "stop", [key,feed.name]])
		return {}

class FeedGroupSearch(restful.Resource):

	def get(self, groupname):
		key = auth()

		fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
		if not fg:
			restful.abort(404)

		return {}

class FeedGroupCount(restful.Resource):

	def get(self, groupname):
		key = auth()

		fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
		if not fg:
			restful.abort(404)

		return sum(len(f.articles) for f in fg.feeds)
