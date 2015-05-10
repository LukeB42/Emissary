import gevent.monkey
gevent.monkey.patch_all()
from gevent.queue import Queue
import sys, os, time, pwd, optparse, gevent,
from multiprocessing import Process, Queue as MPQueue

sys.path.append(os.path.curdir)
from controllers import Log, Cron, Feed, Config, Utils, Client, Server

class EmissaryError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return repr(self.message)

class FeedManager(gevent.Greenlet):
	"""Keeps CronTab objects in rotation"""
	def __init__(self):
		self.inbox 		 = None
		self.running 	 = False
		self.crontabs 	 = {}
		self.threads 	 = []
		gevent.Greenlet.__init__(self)

	def __call__(self):
		for i,v in enumerate(self.threads):
			log("%s %s" % (i,v))

	def receive(self, message):
		if type(message) == dict: self.server.put(message)
		else:
			if message == "ping": return
			(cmd,args) = message.split(' ',1)
			cmd=cmd.lower()
			if cmd == 'rescan':
				if len(args.split()) > 1: (id,username) = args.split()
				else: return
				log('rescan event initiated by %s.' % username)
				try:
					self.rescan()
					response = {'success':'RESCAN successfully completed. %s' % id}
					self.server.put(response)
				except Exception, err:
					response = {'error':'RESCAN failed: %s. %s' % (err,id)}
					self.server.put(response)

	def __setitem__(self, name, crontab):
		if name in self.crontabs.keys():
			if crontab.name:
				log("Restarting %s" % crontab.name, "warning")
			else:
				log("Restarting %s" % name, "warning")
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

	def rescan(self):
		"""Iterate through db['feeds']['uid'] vs self.crontabs.keys()"""
		stored_feeds = []
		for f in db[config['feed_table']].find():
			stored_feeds.append(f['uid'])
			if f['uid'] not in self.crontabs.keys():
				log("Scheduling %s" % f['name'])
				feed		 	= Feed.Feed(db,log,config,uid=f['uid'])
				feed.fm		 	= self.inbox
				feed.inbox	 	= Queue()
				t 			 	= Cron.parse_timings(feed['timings'].split())
				e 			 	= Cron.Event(feed, t[0], t[1], t[2], t[3], t[4])
				e.name 		 	= feed['name']
				ct 			 	= Cron.CronTab(e)
				ct.name			= feed['name']
				ct.inbox		= Queue()
				ct.fm			= self.inbox
				self[f['uid']]	= ct
		for f in self.crontabs.keys():
			if f not in stored_feeds:
				if self.crontabs[f].events[0].running: raise EmissaryError("%s is running." % self.crontabs[f].name)
				del self[f]

	def _run(self):
		self.running = True
		while self.running:
			for i in self.crontabs.values(): # init feeds
				if i.started == False:
					i.fm = self.inbox
					i.inbox = Queue()
					g = gevent.spawn(i.run)
					self.threads.append(g)
			gevent.sleep()
			message = self.inbox.get()
			self.receive(message)
			for g in self.crontabs.values():
				if len(g.name.split()) > 1:	continue # Monitor Database Size
				g.inbox.put('ping') 
				if g.started == False: # Restart dead feeds
					f 			 = Feed.Feed(db,log,config,uid=g.name)
					f.fm		 = self.inbox
					f.inbox		 = Queue()
					t 			 = Cron.parse_timings(f['timings'].split())
					e 			 = Cron.Event(f, t[0], t[1], t[2], t[3], t[4])
					e.name 		 = g.name
					ct 			 = Cron.CronTab(e)
					ct.name		 = f['name'] # Logs correct name but is then
					self[g.name] = ct		 # replaced with uid by __setitem__
			for i in self.threads:
				if i.started == False:
					self.threads.remove(i)

# Defined here instead of Cron.py to prevent circular imports
# Where Cron.parse_crontab would import Feed would import Cron.parse_timings
# Cron.parse_crontab_line used here and Server.py
# This keeps Cron.py application agnostic.
def parse_crontab(db,log):
	table = db['feeds']
	crontab = sys.stdin.read()
	feedlines={}
	for index, line in enumerate(crontab.split('\n')):
		if line.startswith('http'):
			index+=1
			feedlines['%s' % index] = line
		elif (line.startswith('#')) or (line == ''): continue
		else: print Utils.parse_option(line,config)
	for lineno, feedline in feedlines.items():
		url=name=timings=None
		try:
			(url,name,timings) = Cron.parse_crontab_line(feedline,lineno)
		except EmissaryError, e:
			print e
		if url and name and timings:
			# Check URL isn't already loaded
			feed = Feed.Feed(db,log,url=url)
			if 'name' in feed.feed.keys():
				if name != feed['name'] or timings != feed['timings']:
					feed.adjust(name,timings)
					sys.stdout.write("Adjusted %s: %s\n" % (name,feed.feed))
			else:
				sys.stdout.write('Adding %s\n' % name)
				feed = Feed.Feed(db,log).create(name,url,timings)
	raise SystemExit

def db_check(config,db_path):
	if 'db_limit' in config.config.keys():
		db_limit = int(config['db_limit'])
		warning_size = int(db_limit * 0.9)
		db_size = os.stat(db_path).st_size
		log(db_size, db_size > db_limit)
		if db_size > warning_size:		# config['issued_warnings']
			if not 'issued_warnings' in config.config.keys():
				log("%s has exceeded 90" % db_path + "% of db_limit.",'warning')
			config.safe = False
			config['issue_warnings'] = 1
			config.safe = True
		if db_size >=  db_limit:
			if not 'issued_warnings' in config.config.keys():
					log("%s has exceeded db_limit." % db_path,'warning')
			config.safe = False
			config['no_fetching'] = 1
			config['issued_warnings'] = 1
			config.safe = True
		if ('issue_warnings' in config.config.keys()) and (db_size < warning_size):
			if config['issue_warnings']: config['issue_warnings'] = 0
		if ('no_fetching' in config.config.keys()) and (db_size < db_limit):
			if config['no_fetching']: config['no_fetching'] = 0
			if config['issued_warnings']: del config.config['issued_warnings']

def halt(pidfile):
		pid = None
		try:
			f = file(pidfile, 'r')
			pid = f.readline().split()
			f.close()
			os.unlink(pidfile)
		except ValueError, e:
			sys.stderr.write("Error in pid file '%s'.\n" % pidfile)
			sys.exit(-1)
		except IOError, e:
			pass
		if pid:
			for id in pid:
				os.kill(int(id), 15)
				sys.stdout.write('Halted Emissary with a process ID of %s.\n' % id)
		else:
			sys.stderr.write("Emissary isn't running, or a PID file wasn't found.\n")
		if not options.restart:
			sys.exit(0)


# Close STDIN, STDOUT and STDERR so we don't tie up the controlling terminal
# Change some defaults so the daemon doesn't tie up dirs, etc.
def daemon(pidfile):
	try:
		pid = os.fork()
		if pid > 0:
			sys.exit(0) # parent
	except OSError, e:
		sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
		sys.exit(-2)
	os.setsid()
	os.umask(0)
	try:
		pid = os.fork()
		if pid > 0:
			try:
				f = file(pidfile, 'w')
				f.write(str(pid))
				f.close()
			except IOError, err:
				log(err,'error')
			sys.exit(0) # parent
	except OSError, e:
		sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
		sys.exit(-2)
	for fd in (0, 1, 2):
		try:
			os.close(fd)
		except OSError:
			pass

VERSION = '1.2'
if __name__ == '__main__':
# parse args
	prog = "Emissary"
	description = "A cronlike program for indexing HTTP resources."
	epilog = "psybernetics.org.uk %s." % Cron.time.asctime().split()[-1]
	parser = optparse.OptionParser(prog=prog,version=VERSION,description=description,epilog=epilog)
	parser.set_usage(__file__ + ' -f')
	parser.add_option("--start", dest="start", action="store_true", default=True, help="(default)")
	parser.add_option("--stop", dest="stop", action="store_true", default=False, help="Stop Emissary.")
	parser.add_option("--restart", dest="restart", action="store_true", default=False)
	parser.add_option("-f", "--foreground", dest="foreground", action="store_true", help="Don't daemonize.")
	parser.add_option("--debug", dest="debug", action="store_true", default=False, help="Enable debugging output.")
	parser.add_option("--add-user", dest="add_user", action="store_true", default=False, help="Add a new user to the system.")
	parser.add_option("-i", "--interactive", dest="interactive", action="store_true", help="Launch interactive shell.")
	parser.add_option("--logfile", dest="logfile", action="store", default='emissary.log', help="(defaults to ./emissary.log)")
	parser.add_option("--pidfile", dest="pidfile", action="store", default='emissary.pid', help="(defaults to ./emissary.pid)")
	parser.add_option("--run-as", dest="run_as",action="store", default=None, help="(defaults to the invoking user)")
	parser.add_option("--driver", dest="driver", action="store", default='sqlite', help="(defaults to sqlite)")
	parser.add_option("--db", dest="db", action="store", default='cache.db', help="(defaults to ./cache.db)")
	parser.add_option("-a", "--address", dest="address", action="store", default='127.0.0.1', help="(defaults to 127.0.0.1)")
	parser.add_option("-p", "--port", dest="port", action="store", default='6362', help="(defaults to 6362)")
	(options, args) = parser.parse_args()

# handle rc.d
	if options.stop or options.restart:
		halt(options.pidfile)

# init db
	db = dataset.connect(options.driver + ':///' + options.db)

# init logging
	log = Log.Log(__file__,log_file=options.logfile,log_stdout=options.foreground) # Logging to db possible but causes contentions.
	log.debug = options.debug
	log('Emissary %s started.' % VERSION)

	if (pwd.getpwuid(os.getuid())[2] == 0) and (options.run_as == None):
		log("Running as root is not permitted here.",'warning')
		log("Use the --run-as option to drop privileges.",'warning')
		raise SystemExit

	config = Config.Config(db,log)
	# if options.config: load configuration from json file.
	if (not 'version' in config.config.keys()) or (VERSION != config['version']):
		config.safe = False
	config['version'] 		= VERSION
	config['feed_table'] 	= 'feeds'
	config['article_table']	= 'articles'
	config['content_table']	= 'article_content'
	config['user_table'] 	= 'users'
	config['long_threads']	= False
	config.safe = True

# drop privs
	if options.run_as:
		try:
			uid = pwd.getpwnam(options.run_as)[2]
			os.setuid(uid)
			log("Now running as %s." % options.run_as)
		except:
			log("Couldn't switch to user %s" % options.run_as)
			raise SystemExit

# read crontab and exit
	if not sys.stdin.isatty():
		parse_crontab(db,log)

# add a user
	if options.add_user:
		Client.add_user(db,config)

# run interactively
	if options.interactive:
		host = (options.address,int(options.port))
		c = Client.get_credentials()
		try: ec = Client.EmissaryClient(host, c)
		except Client.ClientError, e:
			print e.message
			raise SystemExit
		if ec.connected:
			if options.address == '127.0.0.1': ui = Client.Interface(ec,db,config)
			else: ui = Client.Interface(ec)
			ui.render()
		else:
			print "Invalid username or password."
			raise SystemExit

# daemonise
	if not options.foreground:
		daemon(options.pidfile)

# fm init
	fm 		  = FeedManager()
	fm.config = config
	fm.inbox  = Queue()
	feeds=[]
	for f in db['feeds'].find():
		feed 		= Feed.Feed(db,log,config,uid=f['uid'])
		feed.config = config
		feed.fm 	= fm.inbox
		log("Scheduling %s" % feed['name'])
		feeds.append(feed)

	if len(feeds) == 0:
		log("There are no feeds to fetch.", 'warning')

# determine values for db_ceiling and db_warning_size
	if options.driver == 'sqlite':
		db_ct = Cron.CronTab(Cron.Event(db_check, Cron.allMatch, Cron.allMatch, Cron.allMatch, Cron.allMatch, Cron.allMatch, args=(config, options.db)))
		fm['Monitor Database Size'] = db_ct

# init coroutines for each crontab/feed group
	for f in feeds:
		t = Cron.parse_timings(f['timings'].split())
		e = Cron.Event(f, t[0], t[1], t[2], t[3], t[4])
		e.name = f['name']
		ct = Cron.CronTab(e)
		ct.name = f['name']
		fm[f['uid']] = ct

# socketserver init
	server 			= Server.Pool((options.address, int(options.port)), Server.Protocol)
	server.inbox	= MPQueue()
	server.db 		= db
	server.log 		= log
	server.config	= config
	fm.server 		= server.inbox
	server.fm 		= fm.inbox

# fm spawn
	log('Starting FeedManager')
	threads = []
	threads.append(gevent.spawn(fm.run))
	gevent.sleep()

# socketserver spawn
	log('Listening on %s:%s' % (options.address,options.port))
	p = Process(target=server.serve_forever)
	p.start()
	if not options.foreground:
		f = file(options.pidfile, 'a')
		f.write(' %i'%p.pid)
		f.close()

# revolve
	while True:
		try:
			time.sleep(10)
			fm.inbox.put('ping') # Keeps things _run'n
		except KeyboardInterrupt:
			p.terminate()
			log('Stopping.')
			raise SystemExit
