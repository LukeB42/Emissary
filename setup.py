#!/usr/bin/env python
# _*_ coding: utf-8 _*_
from setuptools import setup, find_packages
import os
import imp

banner = """
██████╗ ███████╗██╗   ██╗██████╗ ███████╗██████╗ ███╗   ██╗███████╗████████╗██╗ ██████╗███████╗   
██╔══██╗██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗████╗  ██║██╔════╝╚══██╔══╝██║██╔════╝██╔════╝   
██████╔╝███████╗ ╚████╔╝ ██████╔╝█████╗  ██████╔╝██╔██╗ ██║█████╗     ██║   ██║██║     ███████╗   
██╔═══╝ ╚════██║  ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗██║╚██╗██║██╔══╝     ██║   ██║██║     ╚════██║   
██║     ███████║   ██║   ██████╔╝███████╗██║  ██║██║ ╚████║███████╗   ██║   ██║╚██████╗███████║██╗
╚═╝     ╚══════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝   ╚═╝   ╚═╝ ╚═════╝╚══════╝╚═╝
"""
print banner

def non_python_files(path):
    """ Return all non-python-file filenames in path """
    result = []
    all_results = []
    module_suffixes = [info[0] for info in imp.get_suffixes()]
    ignore_dirs = ['cvs']
    for item in os.listdir(path):
        name = os.path.join(path, item)
        if (
            os.path.isfile(name) and
            os.path.splitext(item)[1] not in module_suffixes
            ):
            result.append(name)
        elif os.path.isdir(name) and item.lower() not in ignore_dirs:
            all_results.extend(non_python_files(name))
    if result:
        all_results.append((path, result))
    return all_results

data_files = (
#    non_python_files('emissary') +
#    non_python_files(os.path.join('Emissary', 'doc'))
    )

setup(name='Emissary',
      version="2.0.0",
      description='A microservice for indexing the plain text of articles and essays',
      author='Luke Brooks',
      author_email='luke@psybernetics.org.uk',
      url='http://psybernetics.org.uk/emissary',
      download_url = 'https://github.com/LukeB42/Emissary/tarball/2.0.0',
      data_files = data_files,
      packages=['emissary', 'emissary.resources', 'emissary.controllers'],
      include_package_data=True,
      install_requires=[
          "setproctitle",
          "goose-extractor",
          "lxml",
          "gevent",
          "Flask-RESTful",
          "Flask-SQLAlchemy",
          "cssselect",
          "BeautifulSoup",
          "feedparser",
          "python-snappy",
          "requests",
          "pygments",
          "window",
      ],
      keywords=["text extraction","document archival","document retrieval"]
)
