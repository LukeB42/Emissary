import gevent, requests, feedparser
from Article import Article
from Utils import uid, tconv
from Cron import parse_timings

class FeedError(Exception):
	def __init__(self, message, log = None):
		self.message = message
		self.log = log
	def __str__(self):
		if self.log != None:
			self.log(self.message, "error")
		return repr(self.message)

class Feed(object):
	"""Represents a feed abstractly"""
	def __init__(self, db, log, config=None, table='feeds', url=None, uid=None, name=None):
		self.db = db
		self.log = log
		self.config = config
		# config is optional to simplify creating Feed objects in the REPL.
		if self.config:
			self.t = db[config['feed_table']]
		else:
			self.t = db[table]
		self.timings = []
		self.feed={}
		self.fm = None
		self.threads = []
		if url:
			for i in self.t.find(url=url):
				if i: self.feed = i
		elif uid:
			for i in self.t.find(uid=uid):
				if i: self.feed = i
		if name:
			for i in self.t.find(name=name):
				if i: self.feed = i

	def create(self,name,url,timings):
		parse_timings(timings)
		id = uid()
		entry={'name':name,
			   'url':url,
			   'uid':id,
			   'timings':timings}
		self.t.insert(entry)
		i=None
		try:
			i = self.t.find(url=url).next()
			if i: self.feed = i
		except StopIteration:
			raise FeedError("Couldn't find newly created feed.",self.log)
		return self

	def adjust(self,name=None,timings=None):
		"""A safer method for adjusting feeds than __setitem__"""
		if not name and not timings:
			raise FeedError("Nothing to adjust.")
		if timings:
			if type(timings) == list:
				if len(timings) != 5:
					raise FeedError("Insufficient timing data.")
				timings = ' '.join(timings.split())
		if 'uid' in self.feed.keys():
			i = None
			try:
				i = self.t.find(uid=self.feed['uid']).next()
			except StopIteration:
				raise FeedError("Couldn't find %s. This might be an outdated object." % self.feed['name'])
			if i:
				data=None
				if name and not timings:
					data = dict(id=i['id'],name=name)
				if timings and not name:
					data = dict(id=i['id'],timings=timings)
				if timings and name:
					data = dict(id=i['id'],name=name,timings=timings)
				if data:
					self.t.update(data,['id'])
					try:
						i = self.t.find(uid=self.feed['uid']).next()
						self.feed = i
					except StopIteration:
						raise FeedError("Couldn't find uid %s. The DB write may have failed." % self.feed['uid'])
		else:
			raise FeedError("Not yet associated with a feed.")

	def delete(self, delete_articles=False, article_table='articles'):
		self.log("Deleting %s" % self.feed['name'],'warning')
		self.t.delete(url=self.feed['url'])
		if delete_articles:
			self.log("Deleting articles belonging to %s" % self.feed['name'])
			t = self.db['article_table']
			t.delete(parent_uid=self.feed['uid'])
		self.feed={}

	def __setitem__(self,key,value):
		if key in self.feed.keys() and key != 'id':
			self.feed[key] = value
			self.t.upsert({'id':self.feed['id'],key:value},['id'])
		else:
			raise FeedError('Invalid key %s' % key)

	def __getitem__(self,key):
		if key in self.feed.keys():
			return self.feed[key]
		else:
			raise FeedError('Invalid key %s' % key)

	def __call__(self):
		for t in self.threads:
			if t.started == False:
				self.threads.remove(t)
		if self.config:
			if ('long_threads' in self.config.keys()) and (not self.config['long_threads']) and self.threads:
				while self.threads:
					for t in self.threads:
						t.kill()
						self.threads.remove(t)
				tp = gevent.hub.Hub.threadpool
				print dir(tp)
				print tp
				# Sometimes fetches are still running for articles that are already stored.
			if self.config['no_fetching']:
				self.log("%s: Database has reached 100" % self.feed['name'] + "% capacity.",'error')
				if self.fm:
					self.fm.put('! Database at 100% capacity.')
				return
			if self.config['issue_warnings']:
				if self.fm:
					self.fm.put('! Database 90% full.')
				self.log("%s: Database has reached 90" % self.feed['name'] + "% capacity.",'warning')
		self.log('Fetching %s.' % self.feed['name'])
		if 'useragent' in self.config.config.keys():
			self.h={'User-Agent':self.config['useragent']}
		elif 'version' in self.config.config.keys():
			self.h={'User-Agent':'Emissary ' + self.config['version']}
		else:
			self.h={'User-Agent':'Emissary'}
		r = requests.get(self.feed['url'],headers=self.h)
		# TODO: if not 'xml' in r.headers['content-type']: f = Utils.build_relevant_links(url)
		f = feedparser.parse(r.text)
		for e in f.entries:
			self.threads.append(gevent.spawn(self.fetch,e))
		if len(self.threads) > len(f.entries):
			self.log("%s: Some coroutines from the previous fetch haven't finished. Consider scheduling fetches further apart." % self['name'], 'warning')
		gevent.sleep()

	def fetch(self,e):
		try:    # Guessing the same feed won't have multiple entries under the same name.
			a = Article(self.db, self.log, self.config, title=e.title)
			if not a.article:
				try: r = requests.get(e.link, headers=self.h)
				except Exception, err: 
					#self.log("Couldn't retrieve %s (SSL Error)" % e.link,'error')
					#print err.__class__
					#print err.message
					return
				a.create(self, r, e)
				if self.fm:
					self.fm.put('+ %s %s %s' % (a['uid'], a['url'], a['title']))
			else:
				self.log('%s: Already storing %s "%s"' % (self['name'],a['uid'],a['title']), 'debug')
				return
		except Exception, e:
			self.log(e,'error')

	def articles(self,limit=10, offset=0, order_by="desc", table="articles"):
		if self.feed:
			l=[]
			q = 'SELECT * FROM %s WHERE parent_uid = "%s" ORDER BY time %s' % (table, self['uid'], order_by)
			if limit:
				if offset:
					q += ' LIMIT %s,%s' % (offset,limit)
				else:
					q += ' LIMIT %s' % (limit)
			res = self.db.query(q)
			for i in res:
				a=Article(self.db,self.log,url=i['url'])
				l.append(a)
			return l
		else:
			return []

	def count(self, table="articles"):
		q = 'SELECT count(*) FROM %s WHERE parent_uid = "%s"' % (table, self['uid'])
		r = self.db.query(q)
		try:
			i = r.next()
			return i['count(*)']
		except StopIteration:
			return 0

	def search(self,query,all=False,table='articles'): # TODO: _limit, _skip
		l=[]
		t = self.db[table].table
		if all:
			stmt = t.select(t.c.title.like('%% %s %%' % query))
		else:
			stmt = t.select(t.c.title.like('%% %s %%' % query)).where(t.c.parent_uid == self.feed['uid'])
		result = self.db.query(stmt)
		for i in result:
			l.append(i)
		return l

	def __repr__(self):
		if 'url' in self.feed.keys():
			return "<Feed object '%s' for %s at %s>" % (self.feed['name'],self.feed['url'],hex(id(self)))
		return "<Feed object at %s>" % hex(id(self))
