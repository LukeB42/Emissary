# _*_ coding: utf-8 _*_
# This file provides the HTTP endpoints for operating on groups of feeds.
from emissary import app, db
from flask import request
from flask.ext import restful
from sqlalchemy import and_, desc
from emissary.resources.api_key import auth
from emissary.models import FeedGroup, Feed, Article
from emissary.controllers.cron import CronError, parse_timings
from emissary.controllers.utils import cors, gzipped, make_response

class FeedGroupCollection(restful.Resource):

    @cors
    @gzipped
    def get(self):
        """
         Paginate an array of feed groups
         associated with the requesting key.
        """
        key = auth()

        parser = restful.reqparse.RequestParser()
        parser.add_argument("page",     type=int,  default=1)
        parser.add_argument("per_page", type=int,  default=10)
        parser.add_argument("content",  type=bool, default=None)
        args = parser.parse_args()

        query = FeedGroup.query.filter(FeedGroup.key == key)\
                .order_by(desc(FeedGroup.created)).paginate(args.page, args.per_page)

        return make_response(request.url, query)

    @cors
    @gzipped
    def put(self):
        """
         Create a new feed group, providing the name isn't already in use.
        """
        key = auth(forbid_reader_keys=True)

        parser = restful.reqparse.RequestParser()
        parser.add_argument("name",   type=str,  required=True)
        parser.add_argument("active", type=bool, default=True, help="Feed is active", required=False)
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

    @cors
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

    @cors
    @gzipped
    def put(self, groupname):
        """
         Create a new feed providing the name and url are unique.
         Feeds must be associated with a group.
        """
        key = auth(forbid_reader_keys=True)

        parser = restful.reqparse.RequestParser()
        parser.add_argument("name",     type=str, required=True)
        parser.add_argument("url",      type=str, required=True)
        parser.add_argument("schedule", type=str, required=True)
        parser.add_argument("active",   type=bool, default=True, help="Feed is active", required=False)
        args = parser.parse_args()

        fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
        if not fg:
            return {"message":"Unknown Feed Group %s" % groupname}, 304

        # Verify the schedule
        try:
            parse_timings(args.schedule)
        except CronError, err:
            return {"message": err.message}, 500

        # Check the URL isn't already scheduled on this key
        if [feed for feed in key.feeds if feed.url == args.url]:
            return {"message": "A feed on this key already exists with this url."}, 500

        # Check the name is unique to this feedgroup
        if [feed for feed in fg.feeds if feed.name == args.name]:
            return {"message": "A feed in this group already exists with this name."}, 500

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

    @cors
    @gzipped
    def post(self, groupname):
        "Rename a feedgroup or toggle active status"

        key = auth(forbid_reader_keys=True)

        parser = restful.reqparse.RequestParser()
        parser.add_argument("name",   type=str, help="Rename a feed group",)
        parser.add_argument("active", type=bool, default=None)
        args = parser.parse_args()

        fg = FeedGroup.query.filter(
                and_(FeedGroup.key == key, FeedGroup.name == groupname)
            ).first()
        if not fg:
            restful.abort(404)

        if args.name:
            if FeedGroup.query.filter(
                and_(FeedGroup.key == key, FeedGroup.name == args.name)
            ).first():
                return {"message":"A feed already exists with this name."}, 304
            fg.name = args.name

        if args.active or args.active == False:
            fg.active = args.active

        db.session.add(fg)
        db.session.commit()
        return fg.jsonify()

    @cors
    @gzipped
    def delete(self, groupname):
        key = auth(forbid_reader_keys=True)
        
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

    @cors
    def get(self, groupname):
        """
         Retrieve articles by feedgroup.
        """
        key = auth()

        # Summon the group or 404.
        fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
        if not fg: restful.abort(404)

        parser = restful.reqparse.RequestParser()
        parser.add_argument("page",     type=int,  default=1)
        parser.add_argument("per_page", type=int,  default=10)
        parser.add_argument("content",  type=bool, default=None)
        args = parser.parse_args()

        if args.content == True:

            query = Article.query.filter(
                    and_(Article.feed.has(group=fg), Article.content != None))\
                    .order_by(desc(Article.created)).paginate(args.page, args.per_page)

            response = make_response(request.url, query)

#            for doc in response['data']:
#                if not doc['content_available']:
#                    response['data'].remove(doc)
#            return response

        if args.content == False:
            query = Article.query.filter(
                    and_(Article.feed.has(group=fg), Article.content == None))\
                    .order_by(desc(Article.created)).paginate(args.page, args.per_page)

            return make_response(request.url, query)

        query = Article.query.filter(
                Article.feed.has(group=fg))\
                .order_by(desc(Article.created)).paginate(args.page, args.per_page)

        return make_response(request.url, query)

class FeedGroupStart(restful.Resource):

    @cors
    def post(self, groupname):
        """
         Start all feeds within a group.
        """
        key = auth(forbid_reader_keys=True)

        fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
        if not fg:
            restful.abort(404)

        for feed in fg.feeds:
            app.inbox.put([0, "start", [key,feed.name]])
        return {}

class FeedGroupStop(restful.Resource):

    def post(self, groupname):
        key = auth(forbid_reader_keys=True)

        fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
        if not fg:
            restful.abort(404)

        for feed in fg.feeds:
            app.inbox.put([0, "stop", [key,feed.name]])
        return {}

class FeedGroupSearch(restful.Resource):

    def get(self, groupname, terms):
        """
         Return articles on feeds in this group with our search terms in the title.
        """
        key = auth()

        parser = restful.reqparse.RequestParser()
        parser.add_argument("page",     type=int,  default=1)
        parser.add_argument("per_page", type=int,  default=10)
#        parser.add_argument("content",  type=bool, default=None)
        args = parser.parse_args()

        fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
        if not fg:
            restful.abort(404)

        query = Article.query.filter(
                    and_(Article.feed.has(group=fg), Article.title.like("%" + terms + "%")))\
                .order_by(desc(Article.created)).paginate(args.page, args.per_page)
        return make_response(request.url, query)

class FeedGroupCount(restful.Resource):

    def get(self, groupname):
        key = auth()

        fg = FeedGroup.query.filter(and_(FeedGroup.key == key, FeedGroup.name == groupname)).first()
        if not fg:
            restful.abort(404)

        return sum(len(f.articles) for f in fg.feeds)
