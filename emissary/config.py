import os, getpass
if not 'EMISSARY_DATABASE' in os.environ:
	print 'You need to export a URI for EMISSARY_DATABASE'
	print 'Eg: export EMISSARY_DATABASE="sqlite://///home/%s/.emissary.db"' % getpass.getuser()
	raise SystemExit
else:
	SQLALCHEMY_DATABASE_URI = (
    	os.environ['EMISSARY_DATABASE']
	)

MASTER_KEY = None
MASTER_KEY_NAME = "Primary"
PERMIT_NEW = False
GZIP_HERE = True
COMPRESS_ARTICLES = True
if "NO_DUPLICATE_TITLES" in os.environ:
	NO_DUPLICATE_TITLES = os.environ['DUPLICATE_TITLES']
else:
	NO_DUPLICATE_TITLES = True
ENABLE_WEB_FRONTEND = False
