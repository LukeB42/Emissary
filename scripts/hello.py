# _*_ coding: utf-8 _*_
#
# This script creates a named pipe (if it doesn't exist)
# and writes the feed name, article title and url to it
# whenever an article is saved to the database. 
#
# This is useful for composing systems that constantly read
# the FIFO and do things like emit the data to IRC channels.
#
# You could, for instance, perform fuzzy pattern matching and be
# notified when certain keywords are in the news.
#
# Transmission to a natural language processing/translation service
# can also be done in a script or by reading a FIFO like the one here.
#
# Whether you use this system to profit, perform intelligence analysis
# or inform your next vote is hopefully up to you!
#
# Luke Brooks, 2015
# MIT License
# Many big thanks to God, lord of universes.
fifo = "/tmp/emissary.pipe"

cache['app'].log(01)
import os, stat
cache['app'].log(02)
if not stat.S_ISFIFO(os.stat(fifo).st_mode):
	cache['app'].log(03)
	try:
		cache['app'].log(04)
		os.mkfifo(fifo)
		cache['app'].log(05)
	except Exception, e:
		cache['app'].log("Error creating %s: %s" % (fifo, e.message))

cache['app'].log(06)

# Emissary always executes scripts with an article object in the namespace.

# There is also a dictionary named cache, containing the app object.
# Random aside but through the app object you can access the logging interface and the feed manager.
try:
	cache['app'].log(07)
	fd = open(fifo, "w")
	cache['app'].log(08)
	fd.write("%s: %s\n%s\n" % (feed.name, article.title, article.url))
	cache['app'].log(09)
	fd.close()
except Exception, e:
	cache['app'].log(010)
	cache['app'].log("Error writing to %s: %s" % (fifo, e.message))

cache['app'].log(011)
del fd, os, stat, fifo
cache['app'].log(012)
