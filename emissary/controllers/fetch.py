import urlparse
import requests
import feedparser
from emissary import app, db
from sqlalchemy import and_, or_
from emissary.models import Article
from emissary.controllers import parser
requests.packages.urllib3.disable_warnings()

def get(url):
	headers = {"User-Agent": "Emissary "+ app.version}
	return requests.get(url, headers=headers, verify=False)

# Fetch a feed.url, parse the links, visit the links and store articles.
def fetch_feed(feed, log):

	if feed.group:
		log("%s: Fetching %s." % (feed.group.name, feed.name))
	else:
		log("Fetching %s." % (feed.name))
	try:
		r = get(feed.url)
	except Exception, e:
		log("%s: Error fetching %s: %s" % (feed.group.name, feed.name, e.message[0]))
		return

	# Fetch the links and create articles
	links = parser.extract_links(r)
	title = None
	for link in links: 
		# If the feed was XML data then we probably have a dictionary of
		# url:title pairs, otherwise we have a list of urls.
		if type(link) == dict:
			for url, title in link.items(): continue
		else:
			url = link

		# Skip this url if we've already extracted and stored it for this feed.
		if Article.query.filter(and_(Article.url == url), Article.feed == feed).first():
			continue

		try:
			document = get(url)
		except Exception, e:
			log("%s/%s: Error fetching %s: %s" % (feed.group.name,feed.name,url,e.message[0]))
			continue

		# Mimetype detection.
		if 'content-type' in document.headers:
			if 'application' in document.headers['content-type']:
				article = Article(
					url=url,
					title=title,
				)
				commit(feed, article)
				log("%s/%s: Storing reference to %s (%s)" % \
					(feed.group.name, feed.name, url, document.headers['content-type']))
				continue

		if title:
			log('%s/%s: Extracting "%s"' % (feed.group.name, feed.name, title))
		else:
			log("%s/%s: Extracting %s" % (feed.group.name, feed.name, url))

		article_text = parser.extract_body(document.text)
		summary      = parser.summarise(article_text)

		article = Article(
			url=url,
			title=title,
			content=article_text,
			summary=summary
		)

		commit(feed, article)
		log('%s/%s: Stored "%s"' % (feed.group.name,feed.name,article.title))

def commit(feed, article):
	"""
	 Place a new article on the api key of a feed, the feed itself,
	 and commit changes.
	"""
	session = feed._sa_instance_state.session
	feed.articles.append(article)
	feed.key.articles.append(article)

	session.add(article)
	session.add(feed)
	session.commit()

