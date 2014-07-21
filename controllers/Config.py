class ConfigError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return repr(self.message)
    
# Should be interchangable with a dictionary of values,
# to simplify working from the repl.
class Config(object):
	def __init__(self, db, log, table='config'):
		self.db = db
		self.log = log
		self.t = self.db[table]
		self.safe = True
		try:
			self.config = self.t.find(id=1).next()
		except StopIteration:
			self.config = {}

	def __setitem__(self,key,value):
		if self.safe:
			if key in self.config.keys() and key != 'id':
				self.config[key] = value
				self.t.upsert({'id':1,key:value},['id'])
			else:
				raise ConfigError('Invalid key %s' % key)
		else:
				self.config[key] = value
				self.t.upsert({'id':1,key:value},['id'])

	def __getitem__(self,key):
		try:
			self.config = self.t.find(id=1).next()
		except StopIteration:
			self.config = {}
		if key in self.config.keys():
			return self.config[key]
		else:
			raise ConfigError('Invalid key %s' % key)

	def keys(self):
		ks = self.config.keys()
		return ks

