#USERS
#username | passhash | admin | active | result_limit | created_at
#SESSIONS
#session_id | username
#POSTS

import hashlib, time
from Utils import uid

class UserError(Exception):
	"""Generic exception thrown by User errors"""
	def __init__(self,value):
		self.value = value

	def __str__(self):
		return repr(self.value)

class User(object):
	def __init__(self,db,config=None, session_id=None, username=None, user_id=None):
		self.db = db
		self.users_table = self.db['users']
		self.session_table = self.db['sessions']
		self.user = None
		if session_id:
			session = self.session_table.find_one(session_id=session_id)
			if session:
				user = self.users_table.find_one(username=session['username'])
				if user:
					self.user = user
		if username:
			self.user = self.users_table.find_one(username=username)
		if user_id:
			user = self.users_table.find_one(id=int(user_id))
			if user:
				self.user = user

	def load(self, username=None, session_id=None, user_id=None):
		if username:
			user = self.users_table.find_one(username=username)
			if user:
				self.user = user
				return True
			else:
				raise UserError('No matching user %s' % username)
		if session_id:
			session = self.session_table.find_one(session_id=session_id)
			if session:
				user = self.users_table.find_one(username=session['username'])
				if user:
					self.user = user
					return True
			else:
				raise UserError('No matching session')
		if user_id:
			user_id = int(user_id)
			user = self.users_table.find_one(id=user_id)
			if user:
				self.user = user
				return self
			else:
				return None

	def check_auth(self, password):
		if self.user:
			if self.user['passhash'] == hashlib.sha256(password).hexdigest():
				return True
		else:
			return None

	def create_user(self, username, password,user=None):
		if user and type(user) == dict:
			username = user['username']
		password = user['password']
		# Check that this username isn't already taken.
		preexisting = self.users_table.find_one(username=username)
		if preexisting:
			return UserError('User %s already exists' % username)
		passhash = hashlib.sha256(password).hexdigest()
		self.user = {'username':username,
					 'passhash':passhash,
					 'created_at':time.time(),
					 'admin':0,
					 'active':1,
					 'result_limit':25,
					 'authenticated':0}
		self.users_table.insert(self.user)
		return True

	def clear_sessions(self):
		if self.user:
			self.session_table.delete(username=self.user['username'])
		else:
			raise UserError('No user loaded on this instance.')

	def delete_user(self):
		if self.user:
			self.users_table.delete(username=self.user['username'])
		else:
			raise UserError('No user loaded on this instance.')

	def is_authenticated(self):
		if self.user:
			return self.user['authenticated']
		else:
			return False

	def is_active(self):
		if self.user:
			return self.user['active']
		else:
			#return None
			raise UserError('No user loaded on this instance.')

	def is_anonymous(self):
		return False

	def get_id(self):
		if self.user:
			return unicode(self.user['id'])
		else:
			return None

	def __getitem__(self, key):
		if self.user:
			return self.user[key]
		else:
			raise UserError('No attr %s' % key)

	def __setitem__(self, key, value):
		# Perform transparent upserts
		# Transparently hash new passwords
		pass

	def is_authenticated(self):
		return True

	def __repr__(self):
		if self.user:
			return "<User object for '%s' at %s>" % (self.user['username'], hex(id(self)))
		else:
			return "<User object at %s>" % hex(id(self))
