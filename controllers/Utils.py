import time, datetime, base64

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
