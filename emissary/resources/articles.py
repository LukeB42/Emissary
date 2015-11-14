"""
This file determines how articles are accessed.
Yoy may also want to examine the Article class in emissary/models.py
"""
from emissary import db
from flask import request
from sqlalchemy import desc, and_
from flask.ext import restful
from emissary.models import Article
from emissary.resources.api_key import auth
from emissary.controllers.utils import gzipped, make_response
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

		# Construct a query for  Articles ordered by descending creation date and paginated.
		if args.content == True:
			query = Article.query.filter(and_(Article.key == key, Article.content != None))\
					.order_by(desc(Article.created)).paginate(args.page, args.per_page)
		elif args.content == False:
			query = Article.query.filter(and_(Article.key == key, Article.content == None))\
					.order_by(desc(Article.created)).paginate(args.page, args.per_page)
		else:
			query = Article.query.filter(Article.key == key)\
					.order_by(desc(Article.created)).paginate(args.page, args.per_page)

		# Attach links to help consuming applications
		response = make_response(request.url, query)
		return response

#	@gzipped
#	def put(self):
#		"""
#		 Fetch an article without an associated feed.
#		"""
#		key = auth()

#		parser = restful.reqparse.RequestParser()
#		parser.add_argument("feed",type=str, help="", required=False)
#		parser.add_argument("url",type=str, help="", required=True)
#		args = parser.parse_args()
#		return {}, 201

class ArticleSearch(restful.Resource):

	def get(self, terms):
		"""
		 The /v1/articles/search/<terms> endpoint.
		"""
		key = auth()

		parser = restful.reqparse.RequestParser()
		parser.add_argument("page",type=int, help="", required=False, default=1)
		parser.add_argument("per_page",type=int, help="", required=False, default=10)
		parser.add_argument("content",type=bool, help="", required=False, default=None)
		args = parser.parse_args()

		if args.content == True:
			query = Article.query.filter(
						and_(
							Article.key == key,
							Article.content != None,
							Article.title.like("%" + terms + "%")
						))\
					.order_by(desc(Article.created)).paginate(args.page, args.per_page)

			response = make_response(request.url, query)

			# This method of manually pruning JSON documents because they
			# don't relate to items that have content can omit them from search
			# completely. They don't have content but they're showing up here in
			# content != None rather than content == None.. You could always just
			# comment out this next for loop
			for doc in response['data']:
				if not doc['content_available']:
					response['data'].remove(doc)
			return response

		elif args.content == False:
			query = Article.query.filter(
						and_(
							Article.key == key,
							Article.content == None,
							Article.title.like("%" + terms + "%")
						))\
					.order_by(desc(Article.created)).paginate(args.page, args.per_page)
			return make_response(request.url, query)

		query = Article.query.filter(
					and_(Article.key == key, Article.title.like("%" + terms + "%")))\
				.order_by(desc(Article.created)).paginate(args.page, args.per_page)
		return make_response(request.url, query)

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

	@gzipped
	def delete(self, uid):
		"""
		 Delete an article.
		"""
		key = auth(forbid_reader_keys=True)

		article = Article.query.filter(and_(Article.key == key, Article.uid == uid)).first()
		if article:
			db.session.delete(article)
			db.session.commit()
			return {}

		restful.abort(404)

class ArticleCount(restful.Resource):

	def get(self):
		"""
		 Return the amount of articles belonging to an API key.
		"""
		key = auth()
		return len(key.articles)

