import re
import lxml
import urlparse
import feedparser
from goose import Goose

def extract_links(response):
	urls = []
	if ('content-type' in response.headers.keys()) and ('xml' in response.headers['content-type']):
		f = feedparser.parse(response.text)
		for entry in f.entries:
			urls.append({entry.link: entry.title})
	else: # The following is a highly experimental feature.
		p = Parser(r.text,url=self['url'])
		urls = p.parse()
	return urls

class Parser(object):
	"""
	Mostly for building a list of relevant links from a string of html.
	"""
	def __init__(self,html=None,doc=None,url=None):
		self.html=html
		self.doc=doc
		try:    self.url = urlparse.urlparse(url).netloc
		except: self.url = url
		self.links=[]

	def root_to_urls(self, doc, titles):
		"""
		Return a list of urls from an lxml root.
		"""
		if doc is None:
			return []

		a_tags = doc.xpath('//a')
		# tries to find titles of link elements via tag text
		if titles:
			return [ (a.get('href'), a.text) for a in a_tags if a.get('href') ]
		return [ a.get('href') for a in a_tags if a.get('href') ]

	def get_urls(self,_input=None,titles=False,regex=False):
		if (not _input) and (not self.html): return []
		if not _input: _input = self.html
		if regex:
			text = re.sub('<[^<]+?>', ' ', _input)
			text = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', _input)
			text = [i.strip() for i in _input]
			return _input or []
		if isinstance(_input, str) or isinstance(_input, unicode):
			doc = self.fromstring(_input)
		else:
			doc = text
		return self.root_to_urls(doc, titles)

	def fromstring(self, html):
		try:
			self.doc = lxml.html.fromstring(html)
		except Exception, e:
			return None
		return self.doc

	def parse(self,html=None,url=None):
		"""
		Whittle a list of urls into things we're interested in.
		"""
		if self.links: self.links=[]
		urls = self.get_urls(html)
		if not urls: return urls
		else: urls = set(urls)
		if url: url = "http://%s/" % urlparse.urlparse(url).netloc
		for u in urls:
			if url:
				if u == url: continue
			if self.url:
				if u == self.url: continue
			if u.startswith('#'): continue
			if not u.startswith('http'):
				if url:
					if (url[-1] == '/') and (u[0] == '/'):  u = url + u[1:]
					else: u = url+u
				elif self.url:
					if (self.url[-1] == '/') and (u[0] == '/'):  u = self.url + u[1:]
					else: u = self.url+u
				else: continue
			self.links.append(u)
		return self.links

def extract_body(html):
	"""
	 Extract the body text of a web page
	"""
	g = Goose()
	article = g.extract(raw_html=html)
	return article.cleaned_text

def summarise(article):
	stopnum = c = 0
	for i,v in enumerate(article.split()):
		if v.endswith('.'):
			if c >= 2:
				stopnum = i+1
				break
			else:
				c += 1
	return ' '.join(article.split()[:stopnum])
