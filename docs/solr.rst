.. solr:

Solr
====

`Solr <http://lucene.apache.org/solr/>`_ is a search oriented database. It
is used as a non critical helping database to provide fuzzy search.

Bootstrap
---------

Install & run solr ::

    wget http://wwwftp.ciril.fr/pub/apache/lucene/solr/5.1.0/solr-5.1.0.tgz
    tar xf solr-5.1.0.tgz
    cd solr-5.1.0
    ./bin/solr start

Create solr cores for the application ::

    ./bin/solr create -c sief
    ./bin/solr create -c sief-test  # optional test core

Configure each core with :file:`misc/schema.xml` and :file:`misc/solrconfig.xml` ::

    cp ~/<sief-back-repo>/misc/schema.xml ./server/solr/sief/conf/managed-schema
    cp ~/<sief-back-repo>/misc/solrconfig.xml ./server/solr/sief/conf/solrconfig.xml

Manage
------

It can be controlled through the ``./manage.py solr`` command

Examples
--------

Initial build of the solr database::

    ./manage.py solr build

Rebuild the solr database (after a restoration of the mongoDB
database for example) ::

    ./manage.py solr rebuild

Partial rebuild of the solr database ::

    ./manage.py solr rebuild --since 2015-08-20T23:12:34

Full clean of the solr database ::

    ./manage.py solr clear

.. note::

     * the documents modified in the application are automatically
       created/updated in solr (i.e. there is no need of running a
       build periodically)
