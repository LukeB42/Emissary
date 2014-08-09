import SocketServer, select, time, socket, json, string, random, requests, re
from User import User
from Feed import Feed
from Article import Article
from Utils import e, uid
from Cron import parse_crontab_line

def restricted(func):
	"""
	Restrict commands to administrators.
	"""
	def wrapper(self, *args):
		if self.user:
			if self.user['admin']:
				return func(self, *args)
			else:
				return self.handle_echo(json.dumps({"error": "Administrators only."}))
	wrapper.__doc__ = func.__doc__
	return wrapper

class Protocol(SocketServer.BaseRequestHandler):
	def __init__(self,request,client_address,server):
		self.connected_at = time.time()
		self.host = client_address
		self.send_queue = []
		self.fm = server.fm
		self.inbox = None
		self.stream = False
		self.user = None
		self.id = hex(id(self))
		SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)
		
	def handle(self):
		self.server.log("Client connected from %s" % self.host[0], 'debug')
		while True:
			buf = ''
			try:
				ready_to_read, ready_to_write, in_error = select.select([self.request], [], [], 0.1)
			except:
				break

			# Send messages to client
			while self.send_queue:
				try:
					msg = self.send_queue.pop(0)
					msg = msg.encode('utf-8','ignore') + '\n' # ?
					self.request.send(msg + self.server.end_marker)
				except Exception, err:
					self.request.send(str(err) + '\n')
					self.server.log("%s: %s" % (self.host[0],str(e)), 'error')

			# Give clients ten seconds to authenticate.
			if (self.user == None) and ((time.time() - self.connected_at) > 10):
				self.request.send('Connection timed out.\n')
				self.request.close()

			# Check for messages from the client
			if len(ready_to_read) == 1 and ready_to_read[0] == self.request:
				data = self.request.recv(1024)
				if not data:
					break
				elif len(data) > 0:
					buf += str(data)

					# Interpret commands
					while buf.find("\n") != -1:
						line, buf = buf.split("\n", 1)
						line = line.rstrip()

						# Prevent passwords being logged in debug mode
						logline=line
						if line.startswith('auth') and (' ' in line):
							logline = ' '.join(line.split()[:-1])
						self.server.log("From %s: %s" % (self.host[0],logline),'debug')

						response=''
						if ' ' in line:
							command, params = line.split(' ', 1)
						else:
							command = line
							params = ''
						if (self.user == None) and (command.lower() != "auth" and command.lower() != "exit"):
							self.request.send("{'error':'Authenticate first.'}\n")
						else:
							handler = getattr(self, 'handle_%s' % (command.lower()), None)
							if handler:
								response = handler(params)
							else:
								self.send_queue.append('?')
							if response:
								self.request.send(response + '\r\n')

			# See if the FeedManager has any data
			if self.server.inbox:
				if not self.server.inbox.empty():
					message = self.server.inbox.get(block=False)
					if message: self.receive(message)

	def broadcast(self,target,message):
		if (target == '*') or (len(target) == 0):
			if len(self.server.clients) > 0:
				[client.send_queue.append(message) for client in self.server.clients.values()]

	def receive(self,message):
		if message:
			if len(self.server.clients) > 0:
				if type(message) == dict:
					if ('stream' in message.keys()) or ('error' in message.keys()):
						[client.send_queue.append(json.dumps(message)) for client in self.server.clients.values() if client.stream]
					else:
						[client.send_queue.append(json.dumps(message)) for client in self.server.clients.values() if client.id in message.values()[0]]

	@restricted
	def handle_eval(self,params):
		try: self.send_queue.append(str(eval(params)))
		except Exception, err: self.send_queue.append(str(err.message))

	def handle_echo(self, params):
		"""
		"ECHO text"
		"""
		self.send_queue.append(params)

	def handle_auth(self, params):
		"""
		"AUTH username password"
		"""
		if not ' ' in params:
			self.request.close()
			return
		username, password = params.split()
		u = User(self.server.db, username=username).check_auth(password)
		if u:
			self.user = User(self.server.db, username=username)
			if self.user.is_active():
				self.server.clients[repr(self)] = self
				a={'welcome':'Logged in as %s %s' % (self.user['username'], self.server.end_marker)}
				self.request.send(json.dumps(a)+'\n')
			else:
				self.request.close()
		else:
			self.request.close()

	def handle_list(self, params):
		"""
		"LIST feeds | feed_uid | users"
		"""
		args=None
		a={}
		l=[]
		if ' ' in params: (params,args) = params.split()
		if params.lower() == 'feeds':
			t = self.server.db[self.server.config['feed_table']]
			for i in t.find():
				l.append(i)
			a['feeds'] = l
			self.send_queue.append(json.dumps(a))
		elif params.lower() == 'users':
			if self.user['admin']:
				t = self.server.db[self.server.config['user_table']]
				for i in t.find():
					l.append(i)
				a['users'] = l
				self.send_queue.append(json.dumps(a))
			else: self.handle_echo(json.dumps({'error':'Administrators only.'}))
		else:
			f = Feed(self.server.db,None,uid=params)
			if f.feed:
				if args:
					for i in f.articles(int(args)):
						l.append(i.article)
					a['articles'] = l
					self.send_queue.append(json.dumps(a))
				else:
					for i in f.articles():
						l.append(i.article)
					a['articles'] = l
					self.send_queue.append(json.dumps(a))
			else:
				err = {'error':'Unrecognized feed.'}
				self.send_queue.append(json.dumps(err))

	@restricted
	def handle_adjust(self, params): # TODO: Unload modified feeds before issuing RESCAN.
		"""
		"ADJUST feed | user | db_limit | useragent"
		"ADJUST feed uid uid uid, timings=15! * * * * name=laughter cookies"
		"""
		if ' ' in params:
			(command, args) = params.split(' ',1)
			if command == 'feed':
				output={'success':[],'error':[]}
				timings = name = None
				if args.find('timings=') != -1:
					if args.find('name=') == -1: timings = args[args.find('timings=')+len('timings='):]
					else: 						 timings = args[args.find('timings=')+len('timings='):args.find('name=')]
				if args.find('name=') 	 != -1:  name = args[args.find('name=')+len('name='):]
				if (not timings) and (not name):
					self.send_queue.append(get_doc(self.handle_adjust,True))
					return
				args=args.split(',',1)[0].split()
				for uid in args:
					f = Feed(self.server.db,self.server.log,uid=uid)
					print timings
					try:
						f.adjust(name=name,timings=timings)
						output['success'].append(uid)
					except Exception, err:
						print "\n%s\n" % err.message
						output['error'].append(uid)
				self.send_queue.append(json.dumps(output))		
				self.server.fm.put('rescan %s' % self.user['username'])
				return
			elif (command == 'db_limit') or (command == 'useragent'):
				output = Utils.parse_option(params,self.server.config)
				self.send_queue.append(output)
			elif command == 'user':
				pass
			else:
				msg = {'error':'Unknown parameter.'}
				self.send_queue.append(json.dumps(msg))
				return
			self.rescan()
		else:
			msg = {'error':'Need more parameters.'}
			self.send_queue.append(json.dumps(msg))

	@restricted
	def handle_add(self, params):
		"""
		"ADD feed | user"
		"ADD feed http://site.tld/urn 'name' 15! * * * *" would add http://site.tld/urn to be fetched every 15 minutes.
		"ADD user username password" would similarly add "username" with a password of "password".
		"""
		if ' ' in params:
			(command, args) = params.split(' ',1)
			if command == 'feed':
				try:
					(url,name,timings) = parse_crontab_line(''.join(args),tcpd=True)
				except Exception, err:
					self.send_queue.append(json.dumps({'error':err.message}))
					return
				try:
					feed = Feed(self.server.db,self.server.log,self.server.config).create(name,url,timings)
				except:
					self.send_queue.append(json.dumps({'error':"Couldn't create new feed. Possible database contention."}))
					return
				self.send_queue.append(json.dumps({'success':"Created new feed."}))
				self.server.log('Adding %s: %s %s. Added by %s.' % (name, url, timings,self.user['username']))
				self.handle_rescan()
			elif command == 'user':
				pass
			else:
				doc = get_doc(self.handle_add,True)
				self.send_queue.append(doc)
		else:
			doc = get_doc(self.handle_add, True)
			self.send_queue.append(doc)

	# TODO: Multiple uids
	@restricted
	def handle_delete(self, params):
		"""
		"DELETE feed | article | user"
		"DELETE feed feed_id [all]" Optional argument "all" enforces deletion of associated articles.
		"""
		if ' ' in params:
			(command, args) = params.split(' ',1)
			if command == 'feed':
				severity = False
				if ' ' in args: (args, severity) = args.split()
				f = Feed(self.server.db,self.server.log,self.server.config,uid=args)
				f.delete(severity)
				self.handle_rescan()
			elif command == 'article':
				try:
					a = Article(self.server.db,self.server.log,self.server.config,uid=args)
					a.delete()
					response={'success':'Deleted article %s' % args}
				except Exception, err:
					response={'error':'There was an error deleting %s: %s' % (args,err.message)}
				self.send_queue.append(json.dumps(response))
			elif command == 'user':
				pass
			else:
				self.send_queue.append(json.dumps({'error':'Unknown argument.'}))
		else:
			doc = get_doc(self.handle_delete,True)
			self.send_queue.append(doc)

	@restricted
	def handle_rescan(self, params=None):
		"""
		Forces Emissary to pick up on new feeds and detect whether current ones are up to date.
		"""
		self.server.fm.put('rescan %s %s' % (hex(id(self)), self.user['username']))

	# TODO: Multiple uids
	@restricted
	def handle_fetch(self, params):
		"""
		"FETCH article_url | article_uid" stores a new article or refreshes an existing one.
		"""
		if self.server.config['no_fetching']:
			err = {'error':"Database full."}
			self.send_queue.append(json.dumps(err))
			return
		if self.server.config['issue_warnings']:
			err = {'error':'Database 90 percent full.'}
			self.send_queue.append(json.dumps(err))
			return		
		if 'useragent' in self.server.config.config.keys():
			self.h={'User-Agent':self.config['useragent']}
		elif 'version' in self.server.config.config.keys():
			self.h={'User-Agent':'Emissary ' + self.server.config['version']}
		else:
			self.h={'User-Agent':'Emissary'}
		if params.startswith('http://'):
			try: r = requests.get(params,headers=self.h)
			except:
				self.send_queue.append(json.dumps({'error':"Couldn't fetch resource."}))
				return
			f={'uid':'__none__','name':'User "%s"' % self.user['username']}
		else:
			f = Feed(self.server.db,self.server.log,self.server.config,uid=params)
			if not f.feed:
				self.send_queue.append(json.dumps({'error':"Couldn't fetch resource."}))
				return
		a=Article(self.server.db,self.server.log,self.server.config)
		e.link=r.url
		a.create(f,r,e)
		was_streaming = False
		if self.stream:
			was_streaming = True
			self.stream = False
		if a.article:
			self.send_queue.append(json.dumps(a.article))
		else:
			err = {'error':"Couldn't store resource."}
			self.send_queue.append(json.dumps(err))
		if was_streaming:
			self.stream = True
				

	def handle_read(self, params):
		"""
		"READ article_uid" temporarily disables streaming and sends the article over this connection.
		"""
		was_streaming = False
		if self.stream:
			was_streaming = True
			self.stream = False
		a=Article(self.server.db,None,uid=params)
		if a.article:
			a.article['content'] = a['content']
			doc = {'document':a.article}
			self.send_queue.append(json.dumps(doc))
		else:
			err = {'error':'Unrecognized article.'}
			self.send_queue.append(json.dumps(err))
		if was_streaming:
			self.stream = True
			
	def handle_stream(self, params):
		"""
		The stream command, without arguments, will tell you whether you will receive information regarding new articles.
		You can use "STREAM on" and "STREAM off" to enable or disable this feature respectively.
		"""
		if self.user:
			if params.lower() == 'off':
				self.stream = False
				self.send_queue.append(': Streaming disabled.')
			if params.lower() == 'on':
				self.stream = True
				self.send_queue.append(': Streaming enabled.')
			if len(params) == 0:
				self.send_queue.append(': Streaming: %s' % str(self.stream))

	def handle_search(self, params):
		"""
		"SEARCH feed_uid query" or "SEARCH * query" searches titles within a specific feed or all articles.
		"""
		if ' ' in params:
			target, query = params.split(' ',1)
			if target == '*':
				f = Feed(self.server.db,None)
				a = {'results':f.search(query,True)}
				self.send_queue.append(json.dumps(a))
			else:
				f = Feed(self.server.db,None,uid=target)
				a = {'results':f.search(query)}
				self.send_queue.append(json.dumps(a))
		else:
			doc = get_doc(self.handle_search)
			self.send_queue.append(doc)

	def handle_help(self, params):
		"""
		Use "HELP command" to view the documentation for a command.
		"""
		if len(params) == 0:
			doc = get_doc(self.handle_help)
			msg = ": Available commands are:"
			c=[]
			for i in dir(self):
				if i.startswith('handle_'):
					c.append(i)
			l=len(c)
			for i,v in enumerate(c):
				if i != l-1:
					msg += ' %s,' % v[7:].upper()
				else:
					msg += ' %s.' % v[7:].upper()
			self.send_queue.append(doc+'\n'+msg)
		else:
			func = getattr(self, 'handle_%s' % (params.lower()), None)
			if func:
				doc = get_doc(func)
				self.send_queue.append(doc)
			else:
				self.send_queue.append(json.dumps({'error':'Unrecognised command "%s"' % params.upper()}))

	def handle_count(self, params):
		"""
		"COUNT [feed_id]"
		"""
		q = 'SELECT count(*) FROM %s ' % self.server.config['article_table']
		if params: q += 'WHERE parent_uid = "%s"' % params
		r = self.server.db.query(q)
		try:
			i = r.next()
			i=i['count(*)']
		except StopIteration:
			i=0
		r={'count':i}
		self.send_queue.append(json.dumps(r))

	def handle_exit(self, params):
		"""
		Closes this connnection.
		"""
		self.request.close()

class Pool(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
	daemon_threads = True
	reuse_address = True
	def __init__(self, server_address, RequestHandlerClass):
		self.end_marker = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))+'\n'
		self.clients = {}
		self.inbox = None
		self.db = None
		SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)

def get_doc(func, return_json=False):
	"""
	Get and format the docstring of a method.
	"""
	doc = ''
	if not func.__doc__: return "Cannot obtain documentation for %s" % repr(func)
	docs = func.__doc__.split('\n')
	for k, line in enumerate(docs):
		for i,character in enumerate(line):
			if character == '\t':  
				pass
			else:
				if k < len(docs)-2:
					doc += ': '+line[i:] + '\n'
					break
				else:
					doc += ': '+line[i:]
					break
	if not return_json: return doc
	else: return json.dumps({'doc':doc})

