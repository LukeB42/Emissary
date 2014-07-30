import time, datetime, base64, re, lxml.html, urlparse

class e: title = None

def parse_option(line,config):
	if ' ' in line:
		output=''
		(directive, option) = line.split(' ',1)
		if directive == 'db_limit':
			amount 	  = option[:-1] 
			scale 	  = option[-1:]
			if scale == 'k': db_limit = int(amount) * 1024
			if scale == 'm': db_limit = int(amount) * 1048576
			if scale == 'g': db_limit = int(amount) * 1073741824
			output += "Setting db_limit to %i bytes\n" % db_limit
			config.safe = False
			try: config['db_limit'] = db_limit
			except Exception, err: output = err.message
			config['issue_warnings'] = 0
			config['no_fetching']    = 0
			config.safe = True
		elif directive == "useragent":
			output = "User-Agent: %s" % option
			config.safe = False
			try: config['useragent'] = option
			except Exception, err: output = err.message
			config.safe = True
		elif options == "store_binaries":
			if option == 'on':
				output = "Storing binaries."
				config.safe = False
				try: config['store_binaries'] = 1
				except Exception, err: output = err.message
				config.safe = True
			if option == 'off':
				output = "Referencing binaries."
				config.safe = False
				try: config['store_binaries'] = 0
				except Exception, err: output = err.message
				config.safe = True
		elif options == "long_threads":
			if option == 'on':
				output = "Long threads enabled."
				config.safe = False
				try: config['long_threads'] = 1
				except Exception, err: output = err.message
				config.safe = True
			if option == 'off':
				output = "Long threads disabled."
				config.safe = False
				try: config['long_threads'] = 0
				except Exception, err: output = err.message
				config.safe = True

		else: output = "Unrecognised directive."
	return output

def uid():
        millis = int(round(time.time() * 1000))
        dt = datetime.datetime.now()
        millis = str(millis)+str(dt.microsecond)
        return str(base64.b64encode(millis)).strip('==')[-7:] # Adjust slicing to suit

def tconv(seconds):
	minutes, seconds = divmod(seconds, 60)
	hours, minutes = divmod(minutes, 60)
	days, hours = divmod(hours, 24)
	weeks, days = divmod(days, 7)
	s=""
	if weeks:
		if weeks == 1:
			s+= "1 week, "
		else:
			s+= "%i weeks, " % (weeks)
	if days:
		if days == 1:
			s+= "1 day, "
		else:
			s+= "%i days, " % (days)
	if hours:
		if hours == 1:
			s+= "1 hour, "
		else:
			s+= "%i hours, " % (hours)
	if minutes:
		if minutes == 1:
			s+= "1 minute"
		else:
			s+= "%i minutes" % (minutes)
	if seconds:
		if len(s) > 0:
			if seconds == 1:
				s+= " and %i second" % (seconds)
			else:
				s+= " and %i seconds" % (seconds)
		else:
			if seconds == 1:
				s+= "1 second"
			else:
				s+= "%i seconds" % (seconds)
	return s

class ParserError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return repr(self.message)

# TODO: Condense to single function
class Parser(object):
	"""
	Mostly for building a list of relevant links from a string of html.
	"""
	def __init__(self,html=None,doc=None,url=None):
		self.html=html
		self.doc=doc
		self.url = url
		self.links=[]

	def root_to_urls(self, doc, titles):
		"""
		Return a list of urls from an lxml root.
		"""
		if doc is None:
			return []

		a_tags = doc.xpath('//a')
		# tries to find titles of link elements via tag text
		if titles:
			return [ (a.get('href'), a.text) for a in a_tags if a.get('href') ]
		return [ a.get('href') for a in a_tags if a.get('href') ]

	def get_urls(self,_input=None,titles=False,regex=False):
		if (not _input) and (not self.html): return []
		if not _input: _input = self.html
		if regex:
			text = re.sub('<[^<]+?>', ' ', _input)
			text = re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', _input)
			text = [i.strip() for i in _input]
			return _input or []
		if isinstance(_input, str) or isinstance(_input, unicode):
			doc = self.fromstring(_input)
		else:
			doc = text
		return self.root_to_urls(doc, titles)

	def fromstring(self, html):
#		html = encodeValue(html)
		try:
			self.doc = lxml.html.fromstring(html)
		except Exception, e:
			return None
		return self.doc

	def parse(self,html=None,url=None):
		"""
		Whittle a list of urls into things we're interested in.
		"""
		if self.links: self.links=[]
		urls = self.get_urls(html)
		if not urls: return urls
		else: urls = set(urls)
		for u in urls:
			if url:
				if u == url: continue
			if self.url:
				if u == self.url: continue
			if u.startswith('#'): continue
			if not u.startswith('http'):
				if url:
					if (url[-1] == '/') and (u[0] == '/'):  u = url + u[1:]
				elif self.url:
					if (self.url[-1] == '/') and (u[0] == '/'):  u = self.url + u[1:]
				else: continue
			self.links.append(u)
		return self.links

class DBError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return repr(self.message)

class DB(object):
	"""
	Provides a dictionary that transparently selects/upserts behind the scenes.
	"""
	def __init__(self,db,table):
		"""Generally, subclassing this is a good idea."""
		self.db = db
		self.t = db[table]
		self.table = table

	def __getitem__(self,*keys):
		for i in self.t.find(keys[0],keys[1]):
			return i
		return DBDictError('%s not found in %s' % (key, self.table))

	def __setitem__(self,key,value):
		pass

	def __delitem__(self,item):
		pass
