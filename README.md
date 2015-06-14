Emissary
========

A democracy thing for researchers, programmers and news junkies who want personally curated news archives.
Emissary is a web content extractor that has a RESTful API and a scripting system.
Emissary stores the full text of linked articles from RSS feeds or URLs containing links.

--------
<pre>

Installation requires the python interpreter headers, libevent, libxml2 and libxslt headers.
Optional article compression also requires libsnappy. 
All of these can be obtained on debian-based systems with:
sudo apt-get install -y zlib1g-dev libxml2-dev libxslt1-dev python-dev libevent-dev libsnappy-dev

Then to install the package for all users:
sudo python setup.py install


 Usage: python -m emissary.run <args>

  -h, --help            show this help message and exit
  -c, --crontab         Crontab to parse
  --config              (defaults to emissary.config)
  -a, --address         (defaults to 0.0.0.0)
  -p, --port            (defaults to 6362)
  -i, --interactive     Launch interactive console
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
the world to see, we need to put a database URI into the environment:

export EMISSARY_DATABASE="sqlite://///home/YOUR_USERNAME/.emissary.db"

Then start an instance in the foreground to obtain your first API key:

user@host $ python -m emissary.run --cert cert --key key -d


user@host $ cat feeds.txt
apikey: your-api-key-here

# url                                                 name         group     minute  hour    day     month   weekday
http://news.ycombinator.com/rss                       "HN"         "HN"      0       2!      *       *       *
http://mf.feeds.reuters.com/reuters/UKdomesticNews    "Reuters UK" "Reuters" 0       3,9     *       *       *

user@host $ python -m emissary.run -c feeds.txt
user@host $ python -m emissary.repl

(3,189) > help
</pre>

