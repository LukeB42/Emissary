# This file provides the HTTP endpoints for operating on feeds
from emissary import db
from flask import request
from flask.ext import restful
from emissary.models import Article
from emissary.resources.api_key import auth
from emissary.controllers.utils import gzipped
from emissary.controllers.cron import CronError, parse_timings

class ArticleCollection(restful.Resource):

	@gzipped
	def get(self):
		"""
		 Review all articles associated with this key.
		"""
		key = auth()
		return [article.jsonify() for article in key.articles]

	@gzipped
	def put(self):
		"""
		 Create a new feed providing the name and url are unique.
		 Feeds must be associated with a group.
		"""
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("feed",type=str, help="", required=True)
		parser.add_argument("url",type=str, help="", required=True)
		args = parser.parse_args()
		return {}, 201

	@gzipped
	def delete(self):
		"""
		 Halt and delete a feed.
		 Default to deleting its articles.
		"""
		return {}

class ArticleResource(restful.Resource):

	@gzipped
	def get(self, uid):
		"""
		 Read an article.
		"""
		key = auth()
		article = [article for article in key.articles if article.uid == uid]
		if article:
			return article[0].jsonify(summary=True, content=True)
		restful.abort(404)
