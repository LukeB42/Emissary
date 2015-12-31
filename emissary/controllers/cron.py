#!/usr/bin/env python
# From http://stackoverflow.com/questions/373335/suggestions-for-a-cron-like-scheduler-in-python
import gevent
import time, sys
from datetime import datetime, timedelta

class CronError(Exception):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

class days:
    mon = 0
    tue = 1
    wed = 2
    thu = 3
    fri = 4
    sat = 5
    sun = 6

class months:
    jan = 1
    feb = 2
    mar = 3
    apr = 4
    may = 5
    jun = 6
    jul = 7
    aug = 8
    sep = 9
    oct = 10
    nov = 11
    dec = 12

# Turn a list of timing data into raw numeric values
def parse_timings(timings):
    # minute  hour    day month   weekday
    # 0       6,12    *   0-11    mon-sun
    # Currently contains off by one errors.
    if type(timings) == str:
        timings = timings.split()
    if len(timings) != 5:
        print len(timings), timings
        raise CronError('Timings require five fields.')
    minute = hour = day = month = weekday = []
    if timings[0] == '*': minute  = allMatch # range(0,60)
    if timings[1] == '*': hour    = allMatch # range(0,24)
    if timings[2] == '*': day     = allMatch # range(0,32)
    if timings[3] == '*': month   = allMatch # range(0,12)
    if timings[4] == '*': weekday = allMatch # range(0,7)
    for i, v in enumerate(timings):
        if len(v) < 3:
            try:
                r = int(v)
                if i == 0: minute    = [r]
                if i == 1: hour        = [r]
                if i == 2: day        = [r]
                if i == 3: month    = [r]
                if i == 4: weekday    = [r]
            except:
                pass
        if ',' in v:         # TODO: Incorporate lists of days and months.
            t = v.split(',')
            x=[]
            for f in t:
                x.append(int(f))
            if i == 0: minute  = x
            if i == 1: hour    = x
            if i == 2: day     = x
            if i == 3: month   = x
            if i == 4: weekday = x
            del t,f,x
        if v.endswith("!") or v.startswith("*/"):
            s = ""
            for j in v:
                if j.isdigit():
                    s += j
            s = int(s)
            if i == 0: minute  = range(0,60,s)
            if i == 1: hour    = range(0,24,s)
            if i == 2: day     = range(0,32,s)
            if i == 3: month   = range(0,12,s)
            if i == 4: weekday = range(0,7,s)
        if '-' in v and len(v) > 2:
            r = v.split('-')
            for n,m in enumerate(r):
                try:
                    r[n] = int(m)
                except:
                    pass
                if type(r[n]) == int:
                    if i == 0: minute  = range(r[0],int(r[1])+1)
                    if i == 1: hour    = range(r[0],int(r[1])+1)
                    if i == 2: day     = range(r[0],int(r[1])+1)
                    if i == 3: month   = range(r[0],int(r[1])+1)
                    if i == 4: weekday = range(r[0],int(r[1])+1)
                    continue
                else:
                    start = stop = None
                    if i == 3: # Months
                        if hasattr(months,r[0]):
                            start = getattr(months,r[0])
                        if hasattr(months,r[1]):
                            stop  = getattr(months,r[1])
                        if (start and stop) != None:
                            month = range(start,stop+1)
                            del start, stop
                        else:
                            raise CronError('Malformed month data.')
                    if i == 4: # Weekdays
                        if hasattr(days,r[0]):
                            start = getattr(days,r[0])
                        if hasattr(days,r[1]):
                            stop  = getattr(days,r[1])
                        if (start and stop) != None:
                            weekday = range(start,stop+1)
                            del start, stop
                        else:
                            raise CronError('Malformed day-of-the-week data.')
            del v,i,r,n,m,
    return minute, hour, day, month, weekday 

def parse_crontab_line(line,lineno=None,tcpd=False):
    url=line.split()[0]
    f=line.split()[1:]
    for i,w in enumerate(f):
        if w.endswith("'"): break
    name = ' '.join(f[:i+1]).strip("'")
    timings = ' '.join(f[i+1:])     # Minutes Hour Day Month Weekday
    parse_timings(timings)
    if not tcpd:
        if lineno:
            print "Line %s. %s: %s %s" % (lineno,name,url,timings)
        else:
            print "%s: %s %s" % (name,url,timings)
    return (url,name,timings)

# Some utility classes / functions first
class AllMatch(set):
    """Universal set - match everything"""
    def __contains__(self, item): return True

allMatch = AllMatch()

def conv_to_set(obj):  # Allow single integer to be provided
    if isinstance(obj, (int,long)):
        return set([obj])  # Single item
    if not isinstance(obj, set):
        obj = set(obj)
    return obj

class Event(object):
    def __init__(self, action, min=allMatch, hour=allMatch,
                       day=allMatch, month=allMatch, dow=allMatch,
                       args=(), kwargs={}):
        self.mins = conv_to_set(min)
        self.hours= conv_to_set(hour)
        self.days = conv_to_set(day)
        self.months = conv_to_set(month)
        self.dow = conv_to_set(dow)
        self.action = action
        self.args = args
        self.kwargs = kwargs
        self.running = False
        self.name = None

    def matchtime(self, t):
        """Return True if this event should trigger at the specified datetime"""
        return ((t.minute     in self.mins) and
                (t.hour       in self.hours) and
                (t.day        in self.days) and
                (t.month      in self.months) and
                (t.weekday()  in self.dow))

    def check(self, t):
        if self.matchtime(t):
            self.running = True
            self.action(*self.args, **self.kwargs)
            self.running = False

class CronTab(gevent.Greenlet):
    def __init__(self, *events):
        self.events = events
        self.name = None
        gevent.Greenlet.__init__(self)

    def _run(self):
        t=datetime(*datetime.now().timetuple()[:5])
        while 1:
            for e in self.events:
#                print zip([i for i in dir(self)], [getattr(self,i) for i in dir(self)])
                if self.inbox:               # This .get() blocks, preventing duplicate greenlets running
                    msg = self.inbox.get() # in the same addr due to our use of multiprocessing.Process
                e.check(t)
            t += timedelta(minutes=1)
            n = datetime.now()
            while n < t:
                s = (t - n).seconds + 1
                time.sleep(s)
                n = datetime.now()

    def __repr__(self):
        if self.name:
            return "<CronTab object '%s' at %s>" % (self.name, hex(id(self)))
        else:
            return "<CronTab object at %s>" % hex(id(self))

def parse_crontab(db,log):
    table = db['feeds']

    crontab = sys.stdin.read()
    feedlines={}

    for index, line in enumerate(crontab.split('\n')):
        if line.startswith('http'):
            index+=1
            feedlines['%s' % index] = line
        elif (line.startswith('#')) or (line == ''): continue
        else: print Utils.parse_option(line,config)

    for lineno, feedline in feedlines.items():
        url=name=timings=None
        try:
            (url,name,timings) = Cron.parse_crontab_line(feedline,lineno)
        except EmissaryError, e:
            print e

        if url and name and timings:
            # Check URL isn't already loaded
            feed = Feed.Feed(db,log,url=url)
            if 'name' in feed.feed.keys():
                if name != feed['name'] or timings != feed['timings']:
                    feed.adjust(name,timings)
                    sys.stdout.write("Adjusted %s: %s\n" % (name,feed.feed))
            else:
                sys.stdout.write('Adding %s\n' % name)
                feed = Feed.Feed(db,log).create(name,url,timings)

    raise SystemExit

#if __name__ == '__main__':
#    c = CronTab(Event(lambda x: print "Hello", range(0,59), range(0,23), dow=range(0,5)))
#    c.run()

