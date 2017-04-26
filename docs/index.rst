.. Sief documentation master file, created by
   sphinx-quickstart on Thu Aug  6 18:32:20 2015.

Welcome to Sief's documentation!
================================


1 - Prerequisites
-----------------

- mongoDB > 2.6
- Solr > 5.0 (mandatory for search functionalities)


2 - Installation
----------------

Installing in a virtual env is a good practice ::

	virtualenv -p /usr/bin/python3 venv
	. ./venv/bin/activate

Actually install the dependancies ::

	pip install -r requirements.txt


Once installed, configuration must be loaded though env variable, see
:doc:`config` chapter for more informations.


3 - Initialize the database
---------------------------

The database must be initialized before starting the application ::

	$ ./manage.py init
	Are you sure you want to alter http://localhost:8983/solr/sief [n]: y
	 *** Initialize datamodel version ***
	Datamodel initialized to version 1.0.5
	 *** Loading referentials ***
	Langues ISO-6392-2..... Done !
	Pays ISO-3166.. Done !
	Nationalités ISO-3166.. Done !
	Langues OFPRA. Done !
	 *** Creating first admin ***
	nom: Doe
	prenom: John
	email: admin@test.com
	password:
	confirm password:
	Created admin user 5605335e1d41c84685b8513f (admin@test.com)

The script aims at
- Initializing the datamodel version to handle future datamodel evolutions
- Load default referentials
- Create the first admin user

See part 5 for initializing the broker by creating the queues.


4 - Starting API
----------------

Sief is a wsgi application. Thus any wsgi server can run it.
see :file:`Procfile` for default running command

Run with gunicorn (recommanded) ::

	gunicorn "sief.main:bootstrap_app()" --log-file -

Run with the flask embedded serveur (for test and debug) ::

	./manage.py runserver -rd


5 - Starting Broker
-------------------

First create the queues ::

	./manage.py broker create dna inerec agdref

Then do the actual start ::

	./manage.py broker start dna inerec agdref

See :doc:`broker` for more informations


6 - Populate site&users (not mandatory)
---------------------------------------

You need first to load the site (given some users are linked to them) ::

    ./manage.py import site ./site_base.csv -d ';'

Then you can load the users ::

    ./manage.py import user ./user_base.csv -d ';'


Contents
--------

.. toctree::
   :maxdepth: 2

   config
   broker
   solr
   tests

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
