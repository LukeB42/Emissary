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

import os, stat
if not stat.S_ISFIFO(os.stat(fifo).st_mode):
	os.mkfifo(fifo)

# Emissary always executes scripts with an article object in the namespace.

# There is also a dictionary named cache, containing the app object.
# Random aside but through the app object you can access the logging interface and the feed manager.
fd = open(fifo, "w")
fd.write("%s: %s\n%s\n" % (article.feed.name, article.title, article.url))
fd.close()
