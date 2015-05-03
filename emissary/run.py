#!/usr/bin/env python
import os
import sys
import pwd
import time
import optparse
from emissary import app

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
	epilog = "psybernetics.org.uk %s" % time.asctime().split()[-1]
	parser = optparse.OptionParser(prog=prog,version=app.version,description=description,epilog=epilog)

	parser.set_usage('python -m emissary.run')
	parser.add_option("-p", "--port", dest="port", action="store", default='6362')
	parser.add_option("--key", dest="key", action="store", default=None, help="SSL key file")
	parser.add_option("--cert", dest="cert", action="store", default=None, help="SSL certificate")
	parser.add_option("--pidfile", dest="pidfile", action="store", default="emissary.pid", help="Defaults to ./emissary.pid")
	parser.add_option("--stop", dest="stop", action="store_true", default=False)
	parser.add_option("--debug", dest="debug", action="store_true", default=False, help="Log debug messages")
	parser.add_option("-d", dest="daemonise", action="store_true", default=False, help="Run in the background")
	(options,args) = parser.parse_args()

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

	if (pwd.getpwuid(os.getuid())[2] == 0):
		print "Running as root is not permitted.\nExecute this as a different user."
		raise SystemExit

	if options.daemonise: Daemonise(options.pidfile)

	# Initialise the feed manager and run the httpd.
	app.run(host="0.0.0.0", port=int(options.port), debug=options.debug,
		ssl_context=(options.cert, options.key))
