# _*_ coding: utf-8 _*_
# This file provides the HTTP endpoints for operating on individual feeds
from emissary import app, db
from flask import request
from flask.ext import restful
from sqlalchemy import desc, and_
from emissary.models import Feed, FeedGroup, Article
from emissary.resources.api_key import auth
from emissary.controllers.cron import CronError, parse_timings
from emissary.controllers.utils import make_response, gzipped, cors

class FeedResource(restful.Resource):

    @cors
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

    @cors
    @gzipped
    def post(self, groupname, name):
        """
         Modify an existing feed.
        """
        key = auth(forbid_reader_keys=True)

        parser = restful.reqparse.RequestParser()
        parser.add_argument("name",     type=str)
        parser.add_argument("group",    type=str)
        parser.add_argument("url",      type=str)
        parser.add_argument("schedule", type=str)
        parser.add_argument("active",   type=bool, default=None, help="Feed is active")
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

    @cors
    @gzipped
    def delete(self, groupname, name):
        """
         Halt and delete a feed.
         Default to deleting its articles.
        """
        key = auth(forbid_reader_keys=True)
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

    @cors
    def get(self, groupname, name):
        """
         Review the articles for a specific feed on this key.
        """
        key = auth()

        feed = Feed.query.filter(and_(Feed.name == name, Feed.key == key)).first()
        if not feed: abort(404)

        parser = restful.reqparse.RequestParser()
        parser.add_argument("page",     type=int,  default=1)
        parser.add_argument("per_page", type=int,  default=10)
        parser.add_argument("content",  type=bool, default=None)
        args = parser.parse_args()

        # Return a list of the JSONified Articles ordered by descending creation date and paginated.
        if args.content == True:
            query = Article.query.filter(and_(Article.key == key, Article.content != None, Article.feed == feed))\
                    .order_by(desc(Article.created)).paginate(args.page, args.per_page)

            return make_response(request.url, query)

        elif args.content == False:
            query = Article.query.filter(and_(Article.key == key, Article.content == None, Article.feed == feed))\
                    .order_by(desc(Article.created)).paginate(args.page, args.per_page)

            return make_response(request.url, query)

        query = Article.query.filter(and_(Article.key == key, Article.feed == feed))\
                .order_by(desc(Article.created)).paginate(args.page, args.per_page)

        return make_response(request.url, query)

class FeedSearch(restful.Resource):

    @cors
    def get(self, groupname, name, terms):
        """
        Search for articles within a feed.
        """
        key = auth()

        parser = restful.reqparse.RequestParser()
        parser.add_argument("page",     type=int,  default=1)
        parser.add_argument("per_page", type=int,  default=10)
#        parser.add_argument("content", type=bool, default=None)
        args = parser.parse_args()

        fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
        if not fg:
            restful.abort(404)

        f = [f for f in fg.feeds if f.name == name]
        if not f: abort(404)

        f = f[0]

        query = Article.query.filter(
                and_(Article.feed == f, Article.title.like("%" + terms + "%")))\
                .order_by(desc(Article.created)).paginate(args.page, args.per_page)

        return make_response(request.url, query)

class FeedStartResource(restful.Resource):

    @cors
    def post(self, groupname, name):
        key = auth(forbid_reader_keys=True)

        feed = Feed.query.filter(and_(Feed.name == name, Feed.key == key)).first()
        if feed:
            app.inbox.put([0, "start", [key, feed.name]])
            return feed.jsonify()
        restful.abort(404)

class FeedStopResource(restful.Resource):

    @cors
    def post(self, groupname, name):
        key = auth(forbid_reader_keys=True)

        feed = Feed.query.filter(and_(Feed.name == name, Feed.key == key)).first()
        if feed:
            app.inbox.put([0, "stop", [key, feed.name]])
            return feed.jsonify()
        restful.abort(404)

