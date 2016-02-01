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

snappy = None
if app.config['COMPRESS_ARTICLES']:
    try:
        import snappy
    except ImportError:
        pass


# This is a little globally-available (as far as coroutines calling this are concerned)
# dictionary of urls we've already visited. It permits us to only try a url
# four times every half an hour. If we see it again after half an hour we'll
# try it again, otherwise it stays in the seen dictionary. It also needs periodically
# emptying, lest it grow infinitely.
seen = {}

def get(url):
    headers = {"User-Agent": "Emissary "+ app.version}
    return requests.get(url, headers=headers, verify=False)

# Fetch a feed.url, parse the links, visit the links and store articles.
def fetch_feed(feed, log):

    if feed.group:
        log("%s: %s: Fetching %s." % \
            (feed.key.name, feed.group.name, feed.name))
    else:
        log("%s: Fetching %s." % (feed.key.name, feed.name))
    try:
        r = get(feed.url)
    except Exception, e:
        log("%s: %s: Error fetching %s: %s" % \
            (feed.key.name, feed.group.name, feed.name, e.message[0]))
        return

    # Fetch the links and create articles
    links = parser.extract_links(r)
    title = None
    for link in links:
#        try:
        fetch_and_store(link, feed, log)
#        except Exception, e:
#            log("%s: %s: Error with %s: %s" % \
#                (feed.key.name, feed.name, link, e.message), "error")

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
        url   = link
        title = None

    # Skip this url if we've already extracted and stored it for this feed, unless we're overwriting.
    if Article.query.filter(and_(Article.url == url, Article.feed == feed)).first():
        if overwrite:
            log("%s: %s/%s: Preparing to overwrite existing copy of %s" % \
                (feed.key.name, feed.group.name, feed.name, url), "debug")
        else:
            log("%s: %s/%s: Already storing %s" % (feed.key.name, feed.group.name, feed.name, url), "debug")
            return

    # Fix links with no schema
    if not "://" in url:
        url = "http://" + url

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

    # Prune seen URLs older than a day.
    for url in seen.copy():
        if int(time.time()) - seen[url][1] > 86400:
            del seen[url]

    try:
        document = get(url)
    except Exception, e:
        log("%s: %s/%s: Error fetching %s: %s" % \
            (feed.key.name, feed.group.name, feed.name, url, e.message[0]))
        return

    # Mimetype detection.
    if 'content-type' in document.headers:
        if 'application' in document.headers['content-type']:
            if not title:
                title = url
            article = Article(
                url=url,
                title=title,
            )
            if not "://" in article.url:
                article.url = "http://" + article.url
            commit_to_feed(feed, article)
            log("%s: %s/%s: Stored %s, reference to %s (%s)" % \
                (feed.key.name, feed.group.name, feed.name, article.uid, url, document.headers['content-type']))
            return

    # Document parsing.
    try:
        article_content = parser.extract_body(document.text)
        summary      = parser.summarise(article_content)
    except Exception, e:
        log("%s: %s: Error parsing %s: %s" % (feed.key.name, feed.group.name, url, e.message))
        return

    # Ensure a title and disregard dupes
    if not title:
        title = parser.extract_title(document.text)

    if app.config['NO_DUPLICATE_TITLES']:
        if Article.query.filter(
            and_(Article.title == title, Article.key == feed.key)
        ).first():
            return

    # Initial article object
    article = Article(
        url=url,
        title=title,
        summary=summary
    )

    # Determine whether to store the full content or a compressed copy
    if not app.config['COMPRESS_ARTICLES']:
        article.content=article_content
    else:
        article.ccontent = snappy.compress(article_content.encode("utf-8", "ignore"))
        article.compressed = True

    #
    # We execute scripts before committing articles to the database
    # it runs the risk of a singular script halting the entire thing
    # in return we get to modify articles (ie machine translation) before storing.

    # Non-blocking IO will result in the most reliable performance within your scripts.
    #
    for s in app.scripts.scripts.values():
        try:
            s.execute(env={'article':article, 'feed':feed})
            article = s['article']
        except Exception, e:
            log("Error executing %s: %s" % (s.file, e.message), "error")

    commit_to_feed(feed, article)

    now = int(time.time())
    duration = tconv(now-then)
    log('%s: %s/%s: Stored %s "%s" (%s)' % \
        (feed.key.name, feed.group.name, feed.name, article.uid, article.title, duration))
    del then, now, duration, feed, article, url, title
    return

def fetch_feedless_article(key, url, overwrite=False):
    """
     Given a URL, create an Article and attach it to a Key.
    """
    then = int(time.time())
    log  = app.log

    if Article.query.filter(Article.url == url).first():
        if overwrite:
            log("%s: Preparing to overwrite existing copy of %s" % (key.name,url), "debug")
        else:
            log("%s: Already storing %s" % (key.name, url), "debug")
            return

    try:
        response = get(url)
    except Exception, e:
        log("%s: Error fetching %s: %s." % (key.name, url, e.message))
        return

    article_content = parser.extract_body(response.text)
    title           = parser.extract_title(response.text)
    summary         = parser.summarise(article_content)
    article = Article(
            url=url,
            title=title,
            summary=summary
    )

    if not app.config['COMPRESS_ARTICLES']:
        article.content = article_content
    else:
        article.ccontent = snappy.compress(article_content.encode("utf-8", "ignore"))
        article.compress = True

    for s in app.scripts.scripts.values():
        try:
            s.execute(env={'article':article, 'feed':None})
            article = s['article']
        except Exception, e:
            log("Error executing %s: %s" % (s.file, e.message), "error")

    key.articles.append(article)

    article.uid = uid()

    db.session.add(article)
    db.session.add(key)
    db.session.commit()

    now      = int(time.time())
    duration = tconv(now-then)
    log('%s: Stored %s "%s" (%s)' % (key.name, article.uid, article.title, duration))
    return article

def commit_to_feed(feed, article):
    """
     Place a new article on the api key of a feed, the feed itself,
     and commit changes.
    """

    # We give articles UIDs manually to ensure unique time data is used.
    article.uid = uid()

    session = feed._sa_instance_state.session
    feed.articles.append(article)
    feed.key.articles.append(article)

    session.add(article)
    session.add(feed)
    session.commit()
    del article, feed, session
