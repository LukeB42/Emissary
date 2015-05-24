import urlparse
import requests
import feedparser
from emissary import db
from emissary.models import Article
from emissary.controllers import parser

# Fetch feed.url and get the links
def fetch_feed(feed, log):
	if feed.group:
		log("%s: Fetching %s." % (feed.group.name, feed.name))
	else:
		log("Fetching %s." % (feed.name))
	try:
		r = requests.get(feed.url)
		log("%s: %i" % (feed.name, r.status_code))
	except Exception, e:
		log("%s: Error fetching %s, %s" % (feed.group.name, feed.name, e.message))

# Fetch the links and create articles
