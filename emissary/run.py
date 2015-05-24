#!/usr/bin/env python
# _*_ coding: utf-8 _*_

import gevent
from gevent.socket import socket
from gevent.wsgi import WSGIServer
from gevent import monkey; monkey.patch_all()
from gevent.queue import Queue

import os
import sys
import pwd
import time
import _socket
import optparse
from multiprocessing import Process


from emissary import app, init, db
from emissary.controllers.log import Log
from emissary.controllers.manager import FeedManager

try:
	import setproctitle
	setproctitle.setproctitle("emissary")
except ImportError:
	pass

def Daemonise(pidfile):
	try:
		pid = os.fork()
		if pid > 0:
			sys.exit(0) # End parent
	except OSError, e:
		sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
		sys.exit(-2)
	os.setsid()
	os.umask(0)
	try:
		pid = os.fork()
		if pid > 0:
			try:
				# TODO: Read the file first and determine if already running.
				f = file(pidfile, 'w')
				f.write(str(pid))
				f.close()
			except IOError, e:
				logging.error(e)
				sys.stderr.write(repr(e))
			sys.exit(0) # End parent
	except OSError, e:
		sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
		sys.exit(-2)
	for fd in (0, 1, 2):
		try:
			os.close(fd)
		except OSError:
			pass

if __name__ == "__main__":
	prog = "Emissary"
	description = "A cronlike program for indexing HTTP resources."
	epilog = "Psybernetics %s" % time.asctime().split()[-1]
	parser = optparse.OptionParser(prog=prog,version=app.version,description=description,epilog=epilog)

	parser.set_usage('python -m emissary.run [options]')
	parser.add_option("-c", dest="config", action="store", default=None, help="(defaults to emissary.config)")
	parser.add_option("-a", "--address", dest="address", action="store", default='0.0.0.0', help="(defaults to 0.0.0.0)")
	parser.add_option("-p", "--port", dest="port", action="store", default='6362', help="(defaults to 6362)")
	parser.add_option("-i", "--interactive", dest="interactive", action="store_true", default=False, help="Launch interactive console")
	parser.add_option("--key", dest="key", action="store", default=None, help="SSL key file")
	parser.add_option("--cert", dest="cert", action="store", default=None, help="SSL certificate")
	parser.add_option("--pidfile", dest="pidfile", action="store", default="emissary.pid", help="(defaults to ./emissary.pid)")
	parser.add_option("--logfile", dest="logfile", action="store", default="emissary.log", help="(defaults to ./emissary.log)")
	parser.add_option("--stop", dest="stop", action="store_true", default=False)
	parser.add_option("--debug", dest="debug", action="store_true", default=False, help="Log to stdout")
	parser.add_option("-d", dest="daemonise", action="store_true", default=False, help="Run in the background")
	parser.add_option("--run-as", dest="run_as", action="store",default=None, help="(defaults to the invoking user)")
	(options,args) = parser.parse_args()

	if options.config:
		app.config.from_object(options.config)

	app.debug = options.debug

	# Build logger from config
	log = Log("Emissary", log_file=options.logfile, log_stdout=options.debug)
	app.log = log

	if options.stop:
		pid = None
		try:
			f = file(options.pidfile, 'r')
			pid = int(f.readline())
			f.close()
			os.unlink(options.pidfile)
		except ValueError, e:   
			sys.stderr.write('Error in pid file "%s". Aborting\n' % options.pidfile)
			sys.exit(-1)
		except IOError, e:
			pass
		if pid:
			os.kill(pid, 15)
			print "Killed process with ID %i." % pid
		else:
			sys.stderr.write('Emissary not running or no PID file found\n')
		sys.exit(0)

#	if options.interactive:
#		repl.run()

	if not options.key and not options.cert:
		print "SSL cert and key required. (--key and --cert)"
		print "Keys and certs can be generated with:"
		print "$ openssl genrsa 1024 > key"
		print "$ openssl req -new -x509 -nodes -sha1 -days 365 -key key > cert"
		raise SystemExit

	if '~' in options.cert: options.cert = os.path.expanduser(options.cert)
	if '~' in options.key:  options.key  = os.path.expanduser(options.key)

	if not os.path.isfile(options.cert):
		sys.exit("Certificate not found at %s" % options.cert)

	if not os.path.isfile(options.key):
		sys.exit("Key not found at %s" % options.key)

	if (pwd.getpwuid(os.getuid())[2] == 0) and not options.run_as:
		print "Running as root is not permitted.\nExecute this as a different user."
		raise SystemExit

	sock = (options.address, int(options.port))

	if options.run_as:
		sock = socket(family=_socket.AF_INET)
		try:
			sock.bind((options.address, int(options.port)))
		except _socket.error:
			ex = sys.exc_info()[1]
			strerror = getattr(ex, 'strerror', None)
			if strerror is not None:
				ex.strerror = strerror + ': ' + repr(options.address+':'+options.port)
			raise
		sock.listen(50)
		sock.setblocking(0)
		uid = pwd.getpwnam(options.run_as)[2]
		try:
			os.setuid(uid)
			log("Now running as %s." % options.run_as)
		except Exception, e: raise

	# Create the database schema and insert an administrative key
	init()

	if options.daemonise: Daemonise(options.pidfile)

	# Initialise the feed manager with the logger, load feeds and create inter-process
	# communication channels.
	fm = FeedManager(log)
	fm.load_feeds()
	fm.server       = app.inbox
	app.feedmanager = fm.inbox

	# Start the REST interface
	httpd = WSGIServer(sock, app, certfile=options.cert, keyfile=options.key)
	httpd_process = Process(target=httpd.serve_forever)
	log("Binding to %s:%s" % (options.address, options.port))
	httpd_process.start()

	if options.daemonise:
		f = file(options.pidfile, 'a')
		f.write(' %i' % p.pid)
		f.close()

	try:
		fm.run()
	except KeyboardInterrupt:
		log("Stopping...")
		httpd_process.terminate()
