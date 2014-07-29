import socket, pprint, getpass, json, Queue, time #, curses, readline
import User, Utils
from pydoc import pipepager

class ClientError(Exception):
	def __init__(self, message):
		self.message = message
	def __str__(self):
		return repr(self.message)

class Interface(object):
	# cli or tui..
	def __init__(self,client,db=None,config=None):
		self.client = client
		self.db = db
		self.config = config
		p = pprint.PrettyPrinter(indent=1)
		self.p = p.pprint

	def render(self):
		self.cli()

	def cli(self):
		running = True
		if self.db: count = self.client
		while running:
			if self.config: input = raw_input("({:,}) > ".format(self.count(self.config['article_table'])))
			else: input = raw_input("({:,}) > ".format(self.count()))
			while self.client.stream: print self.client.stream.pop()
			if not input: continue
			if input == 'exit':
				if self.client.connected: self.client('exit')
				running = False
			r = self.client(input)
			if type(r) == dict:
				if 'document' in r.keys(): pipepager(r['document']['content'].encode('utf-8','ignore'),'less')
				else: self.p(r)
			elif r: print r,
		raise SystemExit

	def count(self, table="articles"):
		if self.db:
			q = 'SELECT count(*) FROM %s' % (table)
			try: r = self.db.query(q)
			except: return 0
			try:
				i = r.next()
				return i['count(*)']
			except StopIteration:
				return 0
		else:
			r = self.client('count')
			return r['count']


def get_credentials():
	username = raw_input('Username: ')
	password = getpass.getpass(prompt='Password: ')
	return (username, password)

# reset_passwd and add_user are here rather than in User.py because of their use of getpass.
def reset_passwd(db, table='users'):
	"""Use readline to return a tuple containing a username and password pair."""
	pass

def add_user(db,config=None,table="users"):
	"""Use getpass to add a user to the database."""
	if config: t = db[config['user_table']]
	else: t = db[table]
	admin_present = t.find_one(admin=1)	# We're going to determine if there is at least one administrator.
	username = raw_input('Username: ')
	password = getpass.getpass(prompt="Password: ")
	confirm_password = getpass.getpass(prompt="Confirm password: ")
	if confirm_password == password:
		u = User.User(db)
		result = u.create_user(username, password)
		if result == True:
			if not admin_present:
				print "An administrative account wasn't detected."
				make_admin = raw_input('Make this user an admin? [Y/n]')
				if ('n' not in make_admin): u['admin'] = 1
			print "Added new user %s." % username
		else:
			print "User %s already exists." % username
	else:
		print "Passwords didn't match."
	raise SystemExit

class EmissaryClient(object):
	def __init__(self, host=('127.0.0.1',6362), credentials=()):
		self.send_queue = Queue.Queue()
		self.stream		= Queue.deque()
		self.host 		= host
		self.s 			= socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.buffersize = 8192
		self.end_marker = None
		self.connected	= False
		self.cont_recv	= 1
		self.ign_timeout= 1
		self.data		= []

		# The idea here is to be fast locally or reliable globally.
		if (host[0] == '127.0.0.1') or (host[0] == 'localhost'):
			self.s.settimeout(0.50)
		else:
			self.s.settimeout(2)
		if type(self.host[1]) == str:
			self.host[1] = int(self.host[1])
		try:
			self.s.connect(self.host)
			self.connected = True
		except Exception, e:
			raise ClientError(e)
		self.s.send('auth %s\n' % ' '.join(credentials))
		self.handle()

	def handle(self):
		if not self.send_queue.empty():
			entry = self.send_queue.get(block=False)
			if entry:
				try:
					self.s.send(entry+'\r\n')			
				except Exception, e:
					self.connected = False
					raise ClientError(e)
		self.data=[]
		while self.cont_recv:
			data = self.recv()
			if not data:
				pass
			else:
				self.parse(data)
			try:
				self.cont_recv = self.s.recv(self.buffersize, socket.MSG_PEEK)
			except:
				if self.data:
					return self.data[-1]
				else:
					return None

	def recv(self, timeout=2):
		buffer = []
		data=''
		while 1:
			try:
				data = self.s.recv(self.buffersize)
			except socket.timeout:
				if self.ign_timeout:
					continue
				else:
					raise ClientError('timed out.')
			if not self.end_marker:
				buffer.append(data)
				if len(data) < self.buffersize:
					break
			else:
				if not data: break
				if self.end_marker in data:
					buffer.append(data[:data.find(self.end_marker)])
					break
				buffer.append(data)
				if len(buffer)>1:
					x=buffer[-2]+buffer[-1]
					if self.end_marker in x:
						buffer[-2]=x[:x.find(self.end_marker)]
						buffer.pop()
						break
		return ' '.join(buffer)

	def parse(self, data):
		try:
			d = json.loads(data[:-1])
			if 'welcome' in d.keys():
				self.end_marker = d['welcome'].split()[-1]
			if 'stream' in d.keys():
				self.stream.append(d)
				return
			self.data.append(d)
		except Exception, e:
			self.data.append(data)

	def __call__(self, command):
		self.send_queue.put(command)
		return self.handle()

	def wait_stream(self):
		"""A blocking method that waits for stream items."""
		pass

	def __repr__(self):
		if self.connected:
			return "<EmissaryClient object for %s:%i at %s>" % (self.host[0],self.host[1],hex(id(self)))
		else:
			return "<EmissaryClient object at %s>" % hex(id(self))
