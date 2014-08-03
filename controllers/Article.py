#	articles: id | title | url | uid | summary | image_url | time | author | parent_uid | content_uid article_content: id | content_uid | uid | content
import time, urlparse, goose #, newspaper
from Utils import uid, tconv

class ArticleError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return repr(self.message)


class Article(object):
	def __init__(self, db, log, config=None, ref_table="articles", content_table="article_content", uid=None, url=None, title=None):
		self.db = db
		self.log = log
		self.config = config
		if self.config:
			self.ref_t = db[config['article_table']]
			self.content_t = db[config['content_table']]
		else:
			self.ref_t = db[ref_table]
			self.content_t = db[content_table]
		self.article = {}
		self.article_content = {}
		if uid:
			for i in self.ref_t.find(uid=uid):
				if i: self.article = i
		if url:
			for i in self.ref_t.find(url=url):
				if i: self.article = i
		if title:
			for i in self.ref_t.find(title=title):
				if i: self.article = i

	def __getitem__(self, key):
		if key in self.article.keys():
			return self.article[key]
		elif (key == "content") and ('uid' in self.article.keys()):
			for i in self.content_t.find(parent_uid = self.article['uid']):
				if i:
					return i['content']				
				else:
					return None

	def __setitem__(self, key, value):
		pass

	def keys(self):
		ks = self.article.keys()
		if len(ks) > 0:
			ks.append('content')
		return ks

	# Pass {'uid':''} as parent in order to fetch singular resources.
	def create(self, parent, r, e):
#		if not parent['uid']: parent['none'] = '__none__' 
		call_time = time.time()
		try:
			pre_exist = self.ref_t.find(url=e.link).next()
			if pre_exist: self.article = pre_exist
		except StopIteration:
			self.create_entry(parent, r, e, call_time)

	def create_entry(self, parent, r, entry, call_time=None):
		puid = uid()
		cuid = uid()
		g = goose.Goose()

		try:
			self.log("%s: Extracting content from %s" % (parent['name'],r.url))
			# Write a whole-page extractor. (Images, formatting.)
			a = g.extract(raw_html=r.text)
		except:
			self.create_reference(parent, r, entry, call_time)
			return

		stopnum = c = 0
		
		for i,v in enumerate(a.cleaned_text.split()):
			if v.endswith('.'):
				if c >= 2:
					stopnum = i+1
					break
				else:
					c += 1
			
		summary 	= ' '.join(a.cleaned_text.split()[:stopnum])
		urlparsed 	= urlparse.urlparse(r.url)
		img=''
		if a.top_image != None: img = a.top_image.src	
		article 	= dict(
		time 		= time.time(),
		url 		= r.url,
		domain		= urlparsed.netloc,
		image_url 	= img,
		parent_uid 	= parent['uid'],
		uid 		= puid,
		content_uid = cuid,
		summary 	= summary
		)
		if entry.title: article['title'] = entry.title
		else: article['title'] = a.title

		self.ref_t.insert(article)
	
		article_content = dict(
		uid 			= cuid,
		parent_uid 		= puid,
		content 		= a.cleaned_text
		)
		self.content_t.insert(article_content)
		self.article = article
		if call_time:
			if entry.title: self.log('%s: Stored %s "%s" (%s)' % (parent['name'], puid, entry.title, tconv(time.time() - call_time)))
			else: 			self.log('%s: Stored %s "%s" (%s)' % (parent['name'], puid, a.title,	 tconv(time.time() - call_time)))
		else:
			if entry.title: self.log('%s: Stored %s "%s" %s' % (parent['name'], puid, entry.title))
			else: 			self.log('%s: Stored %s "%s" %s' % (parent['name'], puid, a.title))

	def create_reference(self, parent, r, entry, call_time=None):
		puid = uid()
		urlparsed 	= urlparse.urlparse(r.url)
		article 	= dict(
		time 		= time.time(),
		url 		= entry.link,
		domain		= urlparsed.netloc,
		image_url	= '',
		parent_uid	= parent['uid'],
		uid			= puid,
		content_uid	= ''
		)
		if entry.title: article['title'] = entry.title
		else:
			if 'content-type' in r.headers.keys(): article['title'] = "%s %s" % (r.url,r.headers['content-type'])
			else: article['title'] = r.url
		self.ref_t.insert(article)
		self.article = article
		if 'content-type' in r.headers.keys():
			if call_time:
				self.log('%s: Added reference %s "%s" (%s, %s)' % (parent['name'], puid, entry.title, r.headers['content-type'], tconv(time.time() - call_time)))
			else:
				self.log('%s: Added reference %s "%s" (%s)' % (parent['name'], puid, entry.title, r.headers['content-type']))
		else:
			if call_time:
				self.log('%s: Added reference %s "%s" (no content-type, %s)' % (parent['name'], puid, entry.title, tconv(time.time() - call_time)))
			else:
				self.log('%s: Added reference %s "%s" (no content-type)' % (parent['name'], puid, entry.title))

	def adjust(self):
		pass

	def delete(self):
		if self.article:
			self.log("Deleting %s" % self['title'],'warning')
			self.ref_t.delete(uid=self['uid'])
			self.content_t.delete(parent_uid=self['uid'])
			self.article={}
		else:
			raise ArticleError("Nonexistent article.")

	def __repr__(self):
		if self.article:
			return "<Article object '%s' at %s>" % (self.article['url'], hex(id(self)))
		else:
			return "<Article object at %s>" % hex(id(self))
