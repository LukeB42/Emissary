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
PERMIT_NEW = True
GZIP_HERE = True
COMPRESS_ARTICLES = True
NO_DUPLICATE_TITLES = True
