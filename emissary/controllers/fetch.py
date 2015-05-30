import time
import urlparse
import requests
import feedparser
from emissary import app, db
from sqlalchemy import and_, or_
from emissary.models import Article
from emissary.controllers import parser
from emissary.controllers.utils import uid, tconv
requests.packages.urllib3.disable_warnings()

seen = {}

def get(url):
	headers = {"User-Agent": "Emissary "+ app.version}
	return requests.get(url, headers=headers, verify=False)

# Fetch a feed.url, parse the links, visit the links and store articles.
def fetch_feed(feed, log):

	if feed.group:
		log("%s:%s: Fetching %s." % \
			(feed.key.name, feed.group.name, feed.name))
	else:
		log("%s: Fetching %s." % (feed.key.name, feed.name))
	try:
		r = get(feed.url)
	except Exception, e:
		log("%s:%s: Error fetching %s: %s" % \
			(feed.key.name, feed.group.name, feed.name, e.message[0]))
		return

	# Fetch the links and create articles
	links = parser.extract_links(r)
	title = None
	for link in links:
		fetch_and_store(link, feed, log)

def fetch_and_store(link, feed, log, key=None, overwrite=False):
	"""
	 Fetches, extracts and stores a URL.
	 link can be a list of urls or a dictionary of url/title pairs.
	"""
	then = int(time.time())
	# If the feed was XML data then we probably have a dictionary of
	# url:title pairs, otherwise we have a list of urls.
	if type(link) == dict:
		for url, title in link.items(): continue
	else:
		url = link

	# Skip this url if we've already extracted and stored it for this feed, unless we're overwriting.
	if Article.query.filter(and_(Article.url == url), Article.feed == feed).first():
		if overwrite:
			log("%s:%s/%s: Preparing to overwrite existing copy of %s" % \
				(feed.key.name, feed.group.name,feed.name,url), "debug")
		else:
			log("%s:%s/%s: Already storing %s" % (feed.key.name, feed.group.name,feed.name,url), "debug")
			return

	# Store our awareness of this url during this run in a globally available dictionary,
	# in the form [counter, timestamp].
	if url not in seen:
		seen[url]  = [1, int(time.time())]
	else:
		# If we haven't modified the counter for half an hour, reset it.
		now = int(time.time())
		if (now - seen[url][1]) > 60*30:
			seen[url] = [1, int(time.time())]
		# If we have tried this URL four times, disregard it.
		# We might reset its counter in half an hour anyway.
		if seen[url][0] >= 4:
			return
		# Otherwise increment and continue with storing.
		seen[url][0] += 1
		seen[url][1] = int(time.time())

	try:
		document = get(url)
	except Exception, e:
		log("%s:%s/%s: Error fetching %s: %s" % \
			(feed.key.name, feed.group.name,feed.name,url,e.message[0]))
		return

	# Mimetype detection.
	if 'content-type' in document.headers:
		if 'application' in document.headers['content-type']:
			article = Article(
				url=url,
				title=title,
			)
			commit_to_feed(feed, article)
			log("%s:%s/%s: Storing %s, reference to %s (%s)" % \
				(feed.key.name, feed.group.name, feed.name, article.uid, url, document.headers['content-type']))
			return

#	if title:
#		log('%s:%s: Extracting "%s"' % (feed.group.name, feed.name, title))
#	else:
#		log("%s:%s: Extracting %s" % (feed.group.name, feed.name, url))
	try:
		article_text = parser.extract_body(document.text)
		summary      = parser.summarise(article_text)
	except Exception, e:
		log("%s:%s: Error parsing %s: %s" % (feed.key.name, feed.group.name, url, e.message))
		return

	article = Article(
		url=url,
		title=title,
		content=article_text,
		summary=summary
	)

	commit_to_feed(feed, article)
	now = int(time.time())
	duration = tconv(now-then)
	log('%s:%s/%s: Stored %s "%s" (%s)' % \
		(feed.key.name, feed.group.name, feed.name, article.uid, article.title, duration))

def fetch_article(key):
	pass

def commit_to_feed(feed, article):
	"""
	 Place a new article on the api key of a feed, the feed itself,
	 and commit changes.
	"""

	article.uid = uid()

	session = feed._sa_instance_state.session
	feed.articles.append(article)
	feed.key.articles.append(article)

	session.add(article)
	session.add(feed)
	session.commit()
