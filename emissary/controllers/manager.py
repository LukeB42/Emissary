from gevent.queue import Queue
import sys, os, time, pwd, optparse, gevent, hashlib

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
#		gevent.Greenlet.__init__(self)

	def load_feeds(self):
		"""
		 Currently just starts all feeds flat, by checking if they and their
		 FeedGroup are active.


		TODO: Start feeds by API key. Where each CronTab corresponds to a FeedGroup.
		"""
		for key in APIKey.query.all():
			if not key.active:
				self.log('API key "%s" marked inactive. Skipped.' % (key.name))
				continue
			self.log("%s: Processing feed groups." % key.name)
			for fg in key.feedgroups:
				if not fg.active:
					self.log('%s: Feed group "%s" marked inactive. Skipped.' % \
						(key.name, fg.name))
					continue
#				self.log('%s: Starting feeds in group "%s"' % (key.name, fg.name))
				for feed in fg.feeds:
					if not feed.active:
						self.log('%s:%s: Feed "%s" marked inactive. Skipped.' % \
							(key.name, fg.name, feed.name))
						continue
					self.log('%s: %s: Scheduling "%s" (%s)' % \
						(key.name, fg.name, feed.name, feed.schedule))
					ct = self.create_crontab(feed)
					g  = gevent.spawn(ct.run)
					self.threads.append(g)
					self.crontabs[ct.name] = ct

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
		 fetch greenlets executing twice but in the same address space...
		 So I've settled on this solution from now after investigating GIPC,
		 which works with Flask's built in httpd, but that's not as nimble
		 as gevent.WSGIServer.

		"""
		self.running = True
		while self.running:
			gevent.sleep()
			for ct in self.crontabs.values():
				if ct.inbox.empty():
					ct.inbox.put("ping")
				# Check if revive needed

				self.revive(ct)
			for i in self.threads:
				if i.started == False:
					self.threads.remove(i)
			try:
				# Deal with incoming requests from the REST API:
				self.receive(self.app.inbox.get(block=False))
			except:
				pass
			# the sleep for 50ms keeps cpu utilisation low
			gevent.sleep()
			time.sleep(0.05)
		self.log("Cleaning up..")

	def create_crontab(self, feed):
		t        = cron.parse_timings(feed.schedule.split())
		evt      = cron.Event(fetch.fetch_feed,t[0], t[1], t[2], t[3], t[4], [feed, self.log])
		evt.feed = feed
		ct       = cron.CronTab(evt)
		ct.name  = self.generate_ct_name(feed)
		ct.inbox = Queue()
		return ct

	def generate_ct_name(self, feed):
		"""Generate a crontab name from a feed object"""
		return hashlib.sha1(
			feed.name + str(
				time.mktime(
					feed.created.timetuple()
				)
			)
		).hexdigest()
		name = feed.name
		if feed.group:
			name = feed.group.name + name
		if feed.key:
			name = feed.key.key + name
		return hashlib.sha1(name).hexdigest()

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
			self[feed.name] = ct
			if feed.name in self.crontabs.keys():
				self.log("Restarting %s" % ct.name, "warning")
			self.crontabs[ct.name] = ct
			self.log(self.crontabs)

	def __call__(self):
		for i,v in enumerate(self.threads):
			self.log("%s %s" % (i,v))

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
		if func and not qid: return(func(args))
		elif func:
			# We do a double comparison here in order to sort the queue out of the loop
			q = [q for q in self.app.queues if hex(id(q)) == qid]
			if not q:
				self.log("Couldn't find response queue at %s." % id)
				return
			q=q[0]
			# Put our response on the queue and rotate its priority.
			q.put(func(args))
			q.access = time.time()
			self.app.queues.sort(key=lambda q: q.access, reverse=True)
			return
		return

	def handle_check(self, feed):
		"""
		 Return whether we have a feed running or not.
		"""
		if self.generate_ct_name(feed) in self.crontabs:
			return True
		return False


	def handle_start(self, feed):
		"""
		 Schedule a feed.
		"""
		print "starting..."
		print feed
		ct = self.create_crontab(feed)
		name = self.generate_crontab_name(ct)
		self.crontabs[name] = ct
		return True

	def handle_stop(self, feed):
		"""
		 Halt a feed.
		"""
		print feed
		name = self.generate_ct_name(feed)
		ct = self.crontabs[name]
		ct.kill()
		print ct
		del self.crontabs[name]
		return True

	def __setitem__(self, name, crontab):
		if name in self.crontabs.keys():
			if crontab.name:
				self.log("Restarting %s" % crontab.name, "warning")
			else:
				self.log("Restarting %s" % name, "warning")
		crontab.name = name
		self.crontabs[name] = crontab

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
