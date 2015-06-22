# _*_ coding: utf-8 _*_
# This file provides the HTTP endpoints for operating on feeds
from emissary import app, db
from flask import request
from flask.ext import restful
from sqlalchemy import desc, and_
from emissary.models import Feed, FeedGroup, Article
from emissary.resources.api_key import auth
from emissary.controllers.utils import gzipped
from emissary.controllers.cron import CronError, parse_timings

class FeedCollection(restful.Resource):

	@gzipped
	def get(self):
		"""
		 Review all feeds associated with this key.
		"""
		key = auth()
		return [feed.jsonify() for feed in key.feeds]

	@gzipped
	def put(self):
		"""
		 Create a new feed providing the name and url are unique.
		 Feeds must be associated with a group.
		"""
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("name",type=str, help="", required=True)
		parser.add_argument("group",type=str, help="", required=True)
		parser.add_argument("url",type=str, help="", required=True)
		parser.add_argument("schedule",type=str, help="", required=True)
		parser.add_argument("active",type=bool, default=True, help="Feed is active", required=False)
		args = parser.parse_args()

		fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == args.group)).first()
		if not fg:
			return {"message":"Unknown Feed Group %s" % args.group}, 304

		# Verify the schedule...
		try:
			parse_timings(args.schedule)
		except CronError, err:
			return {"message": err.message}, 500

		# Check the URL and name is unique.
		if [feed for feed in key.feeds if feed.name == args.name or feed.url == args.url]:
			return {"message": "A feed on this key already exists with this name or url."}, 500

		feed = Feed(name=args.name, url=args.url, schedule=args.schedule, active=args.active)

		# We generally don't want to have objects in this system that don't belong to API keys.
		fg.feeds.append(feed)
		key.feeds.append(feed)

		db.session.add(feed)
		db.session.add(fg)
		db.session.add(key)
		db.session.commit()

		feed = Feed.query.filter(and_(Feed.key == key, Feed.name == args.name)).first()
		if not feed:
			return {"message":"Error saving feed."}, 304

		# Schedule this feed. 0 here is a response
		# queue ID (we're not waiting for a reply)
		app.inbox.put([0, "start", [key,feed.name]])
		return feed.jsonify(), 201

class FeedResource(restful.Resource):

	@gzipped
	def get(self, groupname, name):
		"""
		 Review a feed.
		"""
		key = auth()

		feed = Feed.query.filter(and_(Feed.name == name, Feed.key == key)).first()
		if feed:
			return feed.jsonify()
		restful.abort(404)

	@gzipped
	def post(self, groupname, name):
		"""
		 Modify an existing feed.
		"""
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("name",type=str, help="")
		parser.add_argument("group",type=str, help="")
		parser.add_argument("url",type=str, help="")
		parser.add_argument("schedule",type=str, help="")
		parser.add_argument("active",type=bool, default=None, help="Feed is active")
		args = parser.parse_args()

		feed = Feed.query.filter(and_(Feed.key == key, Feed.name == name)).first()
		if not feed:
			restful.abort(404)

		if args.name:
			if Feed.query.filter(and_(Feed.key == key, Feed.name == args.name)).first():
				return {"message":"A feed already exists with this name."}, 304
			feed.name = args.name

		if args.group:
			pass

		if args.active != None:
			feed.active = args.active

		if args.url:
			feed.url = args.url

		if args.schedule:
			try:
				parse_timings(args.schedule)
			except CronError, err:
				return {"message": err.message}, 500
			feed.schedule = args.schedule

		db.session.add(feed)
		db.session.commit()

		if args.url or args.schedule:
			app.inbox.put([0, "stop", [feed.key, feed.name]])
			app.inbox.put([0, "start", [feed.key, feed.name]])
			
		return feed.jsonify()

	@gzipped
	def delete(self, groupname, name):
		"""
		 Halt and delete a feed.
		 Default to deleting its articles.
		"""
		key = auth()
		feed = Feed.query.filter(and_(Feed.key == key, Feed.name == name)).first()
		if not feed:
			restful.abort(404)
		app.inbox.put([0, "stop", [key, feed.name]])
		app.log('%s: %s: Deleting feed "%s".' % (feed.key.name, feed.group.name, feed.name))
		for a in feed.articles:
			db.session.delete(a)

		db.session.delete(feed)
		db.session.commit()

		return {}

class FeedArticleCollection(restful.Resource):

	def get(self, groupname, name):
		"""
		 Review the articles for a specific feed on this key.
		"""
		key = auth()

		feed = Feed.query.filter(and_(Feed.name == name, Feed.key == key)).first()
		if not feed: abort(404)

		per_page = 10

		parser = restful.reqparse.RequestParser()
		parser.add_argument("page",type=int, help="", required=False, default=1)
		parser.add_argument("content",type=bool, help="", required=False, default=None)
		args = parser.parse_args()

		# Return a list of the JSONified Articles ordered by descending creation date and paginated.
		if args.content == True:
			return [a.jsonify() for a in \
					Article.query.filter(and_(Article.key == key, Article.content != None, Article.feed == feed))
					.order_by(desc(Article.created)).paginate(args.page, per_page).items
			]
		elif args.content == False:
			return [a.jsonify() for a in \
					Article.query.filter(and_(Article.key == key, Article.content == None, Article.feed == feed))
					.order_by(desc(Article.created)).paginate(args.page, per_page).items
			]

		return [a.jsonify() for a in \
				Article.query.filter(and_(Article.key == key, Article.feed == feed))
				.order_by(desc(Article.created)).paginate(args.page, per_page).items
		]

class FeedArticleSearch(restful.Resource):

	def get(self, terms):
		return {}

class FeedStartResource(restful.Resource):

	def post(self, groupname, name):
		key = auth()

		feed = Feed.query.filter(and_(Feed.name == name, Feed.key == key)).first()
		if feed:
			app.inbox.put([0, "start", [key, feed.name]])
			return feed.jsonify()
		restful.abort(404)

class FeedStopResource(restful.Resource):

	def post(self, groupname, name):
		key = auth()

		feed = Feed.query.filter(and_(Feed.name == name, Feed.key == key)).first()
		if feed:
			app.inbox.put([0, "stop", [key, feed.name]])
			return feed.jsonify()
		restful.abort(404)

