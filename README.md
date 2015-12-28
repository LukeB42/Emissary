Emissary
========

A democracy thing for researchers, programmers and news junkies who want personally curated news archives.
Emissary is a web content extractor that has a RESTful API and a scripting system.
Emissary stores the full text of linked articles from RSS feeds or URLs containing links.

Docs available [here](http://docs.psybernetics.org/).

--------
![Alt text](doc/emissary4.png?raw=true "ncurses Client")
![Alt text](doc/emissary3.png?raw=true "Feed Groups")
![Alt text](doc/emissary2.png?raw=true "Articles")
<pre>

Installation requires the python interpreter headers, libevent, libxml2 and libxslt headers.
Optional article compression requires libsnappy. 
All of these can be obtained on debian-based systems with:
sudo apt-get install -y zlib1g-dev libxml2-dev libxslt1-dev python-dev libevent-dev libsnappy-dev

You're then ready to install the package for all users:
sudo python setup.py install


 Usage: python -m emissary.run <args>

  -h, --help            show this help message and exit
  -c, --crontab         Crontab to parse
  --config              (defaults to emissary.config)
  -a, --address         (defaults to 0.0.0.0)
  -p, --port            (defaults to 6362)
  --key                 SSL key file
  --cert                SSL certificate
  --pidfile             (defaults to ./emissary.pid)
  --logfile             (defaults to ./emissary.log)
  --stop                
  --debug               Log to stdout
  -d                    Run in the background
  --run-as              (defaults to the invoking user)
  --scripts-dir         (defaults to ./scripts/)


Some initial setup has to be done before the system will start.
Communication with Emissary is mainly done over HTTPS connections
and for that you're going to need an SSL certificate and a key:

user@host $ openssl genrsa 1024 > key
user@host $ openssl req -new -x509 -nodes -sha1 -days 365 -key key > cert

To prevent your API keys ever getting put into version control for all
the world to see, you need to put a database URI into the environment:

export EMISSARY_DATABASE="sqlite://///home/you/.emissary.db"

Protip: Put that last line in your shells' rc file.

Start an instance in the foreground to obtain your first API key:

user@host $ python -m emissary.run --cert cert --key key

14/06/2015 16:31:30 - Emissary - INFO - Starting Emissary 2.0.0.
e5a59e0a-b457-45c6-9d30-d983419c43e1
14/06/2015 16:31:31 - Emissary - ERROR - /home/luke/scripts isn't a valid system path.
14/06/2015 16:31:31 - Emissary - INFO - Primary: Processing feed groups.
14/06/2015 16:31:31 - Emissary - INFO - Binding to 0.0.0.0:6362
^That UUID is your Primary API key. Add it to this example crontab:

user@host $ cat feeds.txt
apikey: your-api-key-here

# url                                                 name         group     minute  hour    day     month   weekday
http://news.ycombinator.com/rss                       "HN"         "HN"      15!     *       *       *       *
http://mf.feeds.reuters.com/reuters/UKdomesticNews    "Reuters UK" "Reuters" 0       3!      *       *       *

user@host $ python -m emissary.run -c feeds.txt
Using API key "Primary".
Primary: Creating feed group HN.
Primary: HN: Creating feed "HN"
Primary: Creating feed group Reuters.
Primary: Reuters: Creating feed "Reuters UK"


Emissary supports multiple apikey directives in one crontab.
Subsequent feed definitions are associated with the previous key.

Start an instance in the background and connect to it:
user@host $ python -m emissary.run -d --cert cert --key key
user@host $ python -m emissary.repl
Emissary 2.0.0
Psybernetics 2015

(3,204) > help

Check the included hello.py in the scripts/ directory for hints
about pre-store scripts.
</pre>

![Alt text](doc/emissary5.png?raw=true "ncurses programmatic access")

If the prospect of creating an NSA profile of your reading habits is
something that rightfully bothers you then my advice is to subscribe
to many things and then use Emissary to read the things that really 
interest you.
