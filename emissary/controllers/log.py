# time | program | data | level

# >>> a=[]
# >>> for i in log.get(): a.append(i)
# >>> time.ctime(int(a[0]['time']))
# 'Fri Jan 31 22:37:37 2014'

import logging, time

class Log(object):
	def __init__(self,program, db=None, table='logs', log_file=None, log_stdout=False):
		self.program = program
		self.db = db
		self.log = None
		self.debug = False

		if db:
			self.table = self.db[table]
			self.table_name = table
			self.log = None

		if log_file or log_stdout:
			formatter = logging.Formatter(
				'%(asctime)s - %(name)s - %(levelname)s - %(message)s', '%d/%m/%Y %H:%M:%S'
			)
			self.log = logging.getLogger(program)
			self.log.setLevel(logging.DEBUG)

			if log_stdout:
				ch = logging.StreamHandler()
				ch.setLevel(logging.DEBUG)
				ch.setFormatter(formatter)
				self.log.addHandler(ch)

			if log_file:
				ch = logging.FileHandler(log_file, 'a')
				ch.setLevel(logging.DEBUG)
				ch.setFormatter(formatter)
				self.log.addHandler(ch)

	def __call__(self, data, level='info'):
		if self.db:
			entry = dict(
			time = time.time(),
			program = self.program,
			data = data,
			level=level
			)
			self.table.insert(entry)

		if self.log:
			if level == 'debug': level 		= 10
			if level == 'info': level 		= 20
			if level == 'warning': level 	= 30
			if level == 'error': level 		= 40
			if level == 'critical': level	= 50
			if (level > 15) or (self.debug):
				self.log.log(level,data)

	def __len__(self):
		if self.db:
			return len(self.table)
		return 0

	def get(self, limit=20, skip=0, program=None):
		# TODO: Make use of SQLAlchemy
		if self.db:
			if len(self.table) == 0:
				return None
			if program:
				return self.db.query('SELECT * from %s where program=\'%s\' order by time desc limit %i offset %i' % (self.table_name, program, limit, skip))
			return self.db.query('SELECT * from %s order by time desc limit %i offset %i' % (self.table_name, limit, skip))


