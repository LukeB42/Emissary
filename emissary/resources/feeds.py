# Feeds require groups.
#POST name, group, url, schedule
from emissary import db
from flask import request
from flask.ext import restful
from emissary.models import Feed
from emissary.resources.api_key import auth
from emissary.controllers.utils import gzipped
from emissary.controllers.cron import CronError, parse_timings

class FeedCollection(restful.Resource):

	@gzipped
	def get(self):
		key = auth()
		
		return {}

	@gzipped
	def put(self):
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("name",type=str, help="", required=True)
		parser.add_argument("group",type=str, help="", required=True)
		parser.add_argument("url",type=str, help="", required=True)
		parser.add_argument("schedule",type=str, help="", required=True)
		parser.add_argument("active",type=bool, default=True, help="Feed is active", required=False)
		args = parser.parse_args()

		fg = [fg for fg in key.feedgroups if fg.name == args.group]
		if not fg:
			return {"message":"Unknown Feed Group %s" % args.group}, 304
		else:
			fg=fg[0]

		# Verify the schedule...
		try:
			parse_timings(args.schedule)
		except CronError, err:
			return {"message": err.message}, 500

		feed = Feed(name=args.name, url=args.url, schedule=args.schedule, active=args.active)
		fg.feeds.append(feed)
		key.feeds.append(feed)

		db.session.add(feed)
		db.session.add(fg)
		db.session.add(key)
		db.session.commit()
		return feed.jsonify(), 201

	@gzipped
	def post(self):
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("name",type=str, help="", required=True)
		parser.add_argument("group",type=str, help="", required=True)
		parser.add_argument("url",type=str, help="", required=True)
		parser.add_argument("schedule",type=str, help="", required=True)
		parser.add_argument("active",type=bool, default=True, help="Feed is active", required=False)
		args = parser.parse_args()

		return {}

	@gzipped
	def delete(self):
		return {}

class FeedResource(restful.Resource):

	@gzipped
	def get(self, name):
		key = auth()
		feed = [feed for feed in key.feeds if feed.name == name]
		if feed:
			return feed[0].jsonify()
		restful.abort(404)
