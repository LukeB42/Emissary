# _*_ coding: utf-8 _*_
# This file defines a nifty utility for querying the database,
# gzipping requests thanks to a snippet on pocoo.org and unique ID generation.
import gzip
import uuid
import urllib
import hashlib
import urlparse
import functools 
from emissary import app, db
from sqlalchemy import or_, and_
from cStringIO import StringIO as IO
from flask import after_this_request, request
from emissary.controllers.cron import parse_timings

def sha1sum(text):
    return(hashlib.sha1(text).hexdigest())

def cors(f):
    if not 'ENABLE_CORS' in app.config or not app.config['ENABLE_CORS']:
        return f

    @functools.wraps(f)
    def view_func(*args, **kwargs):
        @after_this_request
        def enable_cors(response):
            response.headers['Access-Control-Allow-Headers'] = "Cache-Control, Pragma, Origin, Authorization, Content-Type, X-Requested-With, Accept"
            response.headers['Access-Control-Allow-Methods'] = "OPTIONS, GET, POST, PUT, DELETE"
            response.headers['Access-Control-Allow-Origin']  = "*"

            return response
        
        return f(*args, **kwargs)
    
    return view_func

def gzipped(f):
    if not 'GZIP_HERE' in app.config or not app.config['GZIP_HERE']:
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

def uid(): return str(uuid.uuid4())

def tconv(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes   = divmod(minutes, 60)
    days, hours      = divmod(hours, 24)
    weeks, days      = divmod(days, 7)
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

def spaceparse(string):
    """
    Return strings surrounded in quotes as a list, or dict if they're key="value".
    """
    results = []
    quotes = string.count('"')
    quoted = quotes / 2
    keyvalue = False

    # Return an empty resultset if there are an uneven number of quotation marks
    if quotes % 2 != 0:
        return results

    # for every quoted phrase determine if it's an assignment and include the variable name
    # disregard it from the string we're working with and continue onto the next quoted part
    for phrase in range(0,quoted+1):
        if not string: break
        start = string.find('"')
        end = string.find('"', start+1)

        if start > 0 and string[start-1] == '=':
            keyvalue = True
            for i in range(start,-1,-1):
                if string[i] == ' ' or i == 0:
                    results.append(string[i:end])
                    break
        else:
            results.append(string[start+1:end])
        string = string[end+1:]
    if keyvalue:
        res = {}
        for item in results:
            k,v = item.split('=')
            if k.startswith(' '):
                k=k[1:]
            if v.startswith('"'):
                v=v[1:]
            res[k]=v
        return res
    return results

def update_url(url, params):
    url_parts = list(urlparse.urlparse(request.url))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urllib.urlencode(query)
    return urlparse.urlunparse(url_parts)

def make_response(url, query, jsonify=True):
    """
     Take a paginated SQLAlchemy query and return
     a response that's more easily reasoned about
     by other programs.
    """
    response = {}
    if jsonify:
        response['data'] = [i.jsonify() for i in query.items]

    response['links'] = {}
    response['links']['self'] = url
    if query.has_next:
        response['links']['next'] = update_url(url, {"page": str(query.next_num)})
    return response
