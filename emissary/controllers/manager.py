from gevent.queue import Queue
import sys, os, time, pwd, optparse, gevent, hashlib

from sqlalchemy import and_
from emissary.models import Feed, FeedGroup, APIKey
from emissary.controllers import cron
from emissary.controllers import fetch

class EmissaryError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return repr(self.message)

class FeedManager(object):
	"""Keeps CronTab objects in rotation"""
	def __init__(self, log):
		self.log         = log
		self.app         = None
		self.running     = False
		self.crontabs    = {}
		self.threads     = []
		self.revived     = {} # {name: [amt, time]}

	def load_feeds(self):
		"""
		 Currently just starts all feeds flat, by checking if they and their
		 FeedGroup are active.


		TODO: Start feeds by API key. Where each CronTab corresponds to a FeedGroup.
		"""
		for key in APIKey.query.all():

			if key.reader:
				continue

			if not key.active:
				self.log('API key "%s" marked inactive. Skipped.' % (key.name))
				continue

			self.log("%s: Processing feed groups." % key.name)
			for fg in key.feedgroups:

				if not fg.active:
					self.log('%s: Feed group "%s" marked inactive. Skipped.' % \
						(key.name, fg.name))
					continue

				for feed in fg.feeds:
					if not feed.active:
						self.log('%s:%s: Feed "%s" marked inactive. Skipped.' % \
							(key.name, fg.name, feed.name))
						continue

					self.log('%s: %s: Scheduling "%s" (%s)' % \
						(key.name, fg.name, feed.name, feed.schedule))

					ct = self.create_crontab(feed)
					g = gevent.spawn(ct.run)
					g.name = ct.name
					self.threads.append(g)
					name = self.generate_ct_name(feed)
					self.crontabs[name] = ct

	def run(self):
		"""
		 Receive inbox messages and revive feeds.
		 Also block duplicate crontab execution.....

		 The reason we do this is due to a quirk of
		 using Gevent with multiprocessing.Process.

		 It's why obtaining the article count in the REPL prompt
		 takes a second, but the tradeoff is that Emissary won't
		 overutilise your CPU in this loop.

		 If you run a greenlet in a subprocess we end up with
		 CronTab greenlets executing twice but in the same address space...
		 So I've settled on this solution for now after investigating GIPC,
		 which works with Flask's built in httpd, but that's not as nimble
		 as gevent.WSGIServer.
		"""
		self.running = True
		while self.running:
			while not self.app.inbox.empty():
				self.receive(self.app.inbox.get(block=False))
			# Run feeds
			gevent.sleep()
			for ct in self.crontabs.values():
				if ct.inbox.empty():
					ct.inbox.put("ping")
				# Check if revive needed
				self.revive(ct)
			for i in self.threads:
				if i.started == False:
					self.threads.remove(i)
			# the sleep for 50ms keeps cpu utilisation low
			gevent.sleep()
			time.sleep(0.05)
		self.log("Cleaning up..")

	def create_crontab(self, feed):
		t        = cron.parse_timings(feed.schedule.split())
		evt      = cron.Event(                   # One possible design for these crontabs
					fetch.fetch_feed,            # is to have them correspond to a FeedGroup
					t[0], t[1], t[2], t[3], t[4],# where each event is a member feed
					[feed, self.log])            # and stopping the crontab stops the group.
		evt.feed = feed
		ct       = cron.CronTab(evt)
		ct.name  = self.generate_ct_name(feed)
		ct.inbox = Queue()
		return ct

	def generate_ct_name(self, feed):
		"""
		 Generate a crontab name from a feed object that's
		 hopefully unique between multiple feeds in multiple groups
		 on multiple API keys.

		 Determining the feed.key.key string here proved to be too expensive,
		 so instead it's trusted that the name and creation time are unique enough.

		 Improvements to this implementation are most welcome.
		"""
		return hashlib.sha1("%s %s" % (feed.name, feed.created)).hexdigest()

	def revive(self, ct):
		"""
		 Restart a dead crontab.
		 Permit a ceiling amount of restarts.
		 Only restart a feed once per minute.
		"""
		if ct.name in self.revived:
			now = time.time()
			then = self.revived[ct.name][1]
			if (now - then) < 60:
				return
			self.revived[ct.name][0] += 1
			self.revived[ct.name][1] = now
		else:
			self.revived[ct.name] = [1, time.time()]

		if ct.started == False:
			feed         = ct.events[0].feed
			ct = self.create_crontab(feed)
			self[ct.name] = ct
			gevent.spawn(ct.run)
#			if feed.name in self.crontabs.keys():
#				self.log("Restarting %s" % ct.name, "warning")
			
#			name = self.generate_ct_name(feed)
#			self.crontabs[name] = ct
#			self.log(self.crontabs)

	def receive(self, payload):
		"""
		The Feed manager is an actor with an inbox that responds to commands
		issued by the HTTPD process. We accept a list containing a queue ID
		a command name that corresponds to FeedManager.handle_<command> and
		arguments, even if it's just a None.
		"""
		if len(payload) < 3 or type(payload) != list: return
		qid, command, args = payload
		func = getattr(self, "handle_" + command, None)
		# Execute on messages with a Queue ID of zero without emitting a response
		if func and not qid: return(func(args))
		# Otherwise, use response queues based on access times
		elif func:
			# We do a double comparison here in order to sort the queue out of the loop
			q = [q for q in self.app.queues if hex(id(q)) == qid]
			if not q:
				self.log("Couldn't find response queue at %s." % id)
				return
			q=q[0]
			# Put our response on the queue and rotate its priority.
			try:
				q.put(func(args))
			except Exception,e:
				self.app.log(e.message,'warning')
			q.access = time.time()
			self.app.queues.sort(key=lambda q: q.access, reverse=True)
			return
		return

	def handle_check(self, feed):
		"""
		 Return whether we have a feed running or not.
		"""
		name = self.generate_ct_name(feed)
		if name in self.crontabs and self.crontabs[name].started:
			return True
		return False

	def handle_start(self, args):
		"""
		 Schedule a feed.

		We look the feed up here because for some reason freshly
		created ones aren't great at journeying over IPC queues.
		"""
		key, name = args
		feed = Feed.query.filter(and_(Feed.key == key, Feed.name == name)).first()
		if not feed: return

		self.app.log('%s: %s: Scheduling "%s" (%s)' % \
			(key.name, feed.group.name, feed.name, feed.schedule))
		ct = self.create_crontab(feed)
		self.crontabs[ct.name] = ct
		g = gevent.spawn(ct.run)
		g.name = ct.name
		self.threads.append(g)
		return True

	def handle_stop(self, args):
		"""
		 Halt a feed.

		We can't look the feed up from the database here because we may have
		already deleted it from our records, so instead we iterate through
		all of our green threads until something sticks.
		"""
		key, name = args

		for id, ct in self.crontabs.items():
			feed = ct.events[0].feed
			if feed.name == name and feed.key.key == key.key:
				if self.app.debug:
					self.app.log('%s: %s: Unscheduling "%s". [thread %s]' % \
						(key.name, feed.group.name, feed.name, id))
				else:
					self.app.log('%s: %s: Unscheduling "%s".' % \
						(key.name, feed.group.name, feed.name))
				for t in self.threads:
					if t.name == id:
						gevent.kill(t)
						break
				self.threads.remove(t)
				del ct
				del self.crontabs[id]
				return True
		return False

	def __setitem__(self, name, crontab):
		if name in self.crontabs.keys():
			if crontab.name:
				self.log("Restarting %s" % crontab.name, "warning")
			else:
				self.log("Restarting %s" % name, "warning")
		crontab.name = name
		self.crontabs[name] = crontab
		gevent.spawn(crontab)

	def __getitem__(self, name):
		if name in self.crontabs.keys():
			return self.crontabs[name]
		else:
			raise KeyError('Invalid CronTab')

	def __delitem__(self, name):
		"""Halt crontab, delete"""
		if name in self.crontabs.keys():
			self.crontabs[name].kill()
			del self.crontabs[name]

	def keys(self):
		return self.crontabs.keys()
