# This file provides the HTTP endpoints for operating on feeds
from emissary import db
from flask import request
from sqlalchemy import desc, and_
from flask.ext import restful
from emissary.models import Article
from emissary.resources.api_key import auth
from emissary.controllers.utils import gzipped
from emissary.controllers.cron import CronError, parse_timings

class ArticleCollection(restful.Resource):

	def get(self):
		"""
		 Review all articles associated with this key.
		"""
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("page",type=int, help="", required=False, default=1)
		parser.add_argument("per_page",type=int, help="", required=False, default=10)
		parser.add_argument("content",type=bool, help="", required=False, default=None)
		args = parser.parse_args()

		# Return a list of the JSONified Articles ordered by descending creation date and paginated.
		if args.content == True:
			return [a.jsonify() for a in \
					Article.query.filter(and_(Article.key == key, Article.content != None))
					.order_by(desc(Article.created)).paginate(args.page, per_page).items
			]
		elif args.content == False:
			return [a.jsonify() for a in \
					Article.query.filter(and_(Article.key == key, Article.content == None))
					.order_by(desc(Article.created)).paginate(args.page, args.per_page).items
			]

		return [a.jsonify() for a in \
				Article.query.filter(Article.key == key)
				.order_by(desc(Article.created)).paginate(args.page, args.per_page).items
		]

	@gzipped
	def put(self):
		"""
		 Fetch an article without an associated feed.
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
		 Delete an article.
		"""
		return {}

class ArticleSearch(restful.Resource):

	def get(self, terms):
		"""
		 Return the amount of articles belonging to an API key.
		"""
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("page",type=int, help="", required=False, default=1)
		parser.add_argument("per_page",type=int, help="", required=False, default=10)
		parser.add_argument("content",type=bool, help="", required=False, default=None)
		args = parser.parse_args()

		if args.content == True:
			response = [a.jsonify() for a in \
					Article.query.filter(
						and_(
							Article.key == key,
							Article.content != None,
							Article.title.like("%" + terms + "%")
						))
					.order_by(desc(Article.created)).paginate(args.page, args.per_page).items
			]

			# This method of manually pruning JSON documents because they
			# don't relate to items that have content can omit them from search
			# completely. They don't have content but they're showing up here in
			# content != None rather than content == None.. You could always just
			# return the list comprehension defined above.
			for doc in response:
				if not doc['content_available']:
					response.remove(doc)
			return response

		elif args.content == False:
			return [a.jsonify() for a in \
					Article.query.filter(
						and_(
							Article.key == key,
							Article.content == None,
							Article.title.like("%" + terms + "%")
						))
					.order_by(desc(Article.created)).paginate(args.page, args.per_page).items
			]

		return [a.jsonify() for a in \
				Article.query.filter(
					and_(Article.key == key, Article.title.like("%" + terms + "%")))
				.order_by(desc(Article.created)).paginate(args.page, args.per_page).items
		]

		return [a.jsonify() for a in Article.query.filter(
			and_(Article.key == key,Article.title.like("%" + terms + "%"))
		).all()]

class ArticleResource(restful.Resource):

	def get(self, uid):
		"""
		 Read an article.
		"""
		key = auth()

		article = Article.query.filter(and_(Article.key == key, Article.uid == uid)).first()
		if article:
			return article.jsonify(summary=True, content=True)

		restful.abort(404)

class ArticleCount(restful.Resource):

	def get(self):
		"""
		 Return the amount of articles belonging to an API key.
		"""
		key = auth()
		return len(key.articles)
