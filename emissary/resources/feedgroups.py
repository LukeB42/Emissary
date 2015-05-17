from emissary import db
from flask import request
from flask.ext import restful
from emissary.models import FeedGroup
from emissary.resources.api_key import auth
from emissary.controllers.utils import gzipped

class FeedGroupCollection(restful.Resource):

	@gzipped
	def get(self):
		return {}

	@gzipped
	def put(self):
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

	@gzipped
	def post(self):
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("name",type=str, help="", required=True)
		parser.add_argument("active",type=bool, default=True, help="Feed is active", required=False)
		args = parser.parse_args()

		return {}

	@gzipped
	def delete(self):
		return {}

class FeedGroupResource(restful.Resource):

	@gzipped
	def get(self, name):
		return {}
