"""
This file defines a nifty utility for querying the database,
gzipping requests thanks to a snippet on pocoo.org and unique ID generation.
"""
import gzip
import time
import base64
import datetime
import functools 
from emissary import app
from sqlalchemy import or_, and_
from cStringIO import StringIO as IO
from microauth.resources.models import *
from flask import after_this_request, request

def get(key, cls, attrs=(), page=0, per_page=50, local=True):
#
# Local is a flag that determines whether we only return objects local to the
# calling key's namespace, or whether we will permit global objects with identical names
# to local objects in the response.
#
	if page and per_page:
		if key.systemwide:
			return cls.query.filter(or_(cls.key == None, cls.key == key)).paginate(page, per_page).items
		return cls.query.filter(cls.key == key).paginate(page,per_page).items

	if attrs:
		(attr, identifier) = attrs
		attribute = getattr(cls, attr)
		if attribute:
			if key.systemwide:
				item = cls.query.filter(
					or_(and_(attribute==identifier, cls.key == None),
					and_(attribute==identifier, cls.key == key))
				).all()
				if local:
					if len(item) == 1: return item[0]
					for i in item:
						if i.key == key: return i
				return item
			else:
				item = cls.query.filter(and_(attribute==identifier, cls.key == key)).first()
			return item

		raise Exception('Unrecognised attribute "%s" of %s.' % (attr, repr(cls)))

	if key.systemwide:
		return cls.query.filter(or_(cls.key == None, cls.key == key)).all()
	return cls.query.filter(cls.key == key).all()


def gzipped(f):
	if not app.config['GZIP_HERE']:
		return f

	@functools.wraps(f)
	def view_func(*args, **kwargs):

		@after_this_request
		def zipper(response):
			accept_encoding = request.headers.get('Accept-Encoding', '')

			if 'gzip' not in accept_encoding.lower():
				return response

			response.direct_passthrough = False

			if (response.status_code < 200 or
				response.status_code >= 300 or
				'Content-Encoding' in response.headers):
				return response
			gzip_buffer = IO()
			gzip_file = gzip.GzipFile(mode='wb', 
									  fileobj=gzip_buffer)
			gzip_file.write(response.data)
			gzip_file.close()

			response.data = gzip_buffer.getvalue()
			response.headers['Content-Encoding'] = 'gzip'
			response.headers['Vary'] = 'Accept-Encoding'
			response.headers['Content-Length'] = len(response.data.replace(' ',''))

			return response

		return f(*args, **kwargs)

	return view_func

def uid():
	millis = int(round(time.time() * 1000))
	dt = datetime.datetime.now()
	millis = str(millis)+str(dt.microsecond)
	return str(base64.b64encode(millis)).strip('==')[-7:] # Adjust slicing to suit

