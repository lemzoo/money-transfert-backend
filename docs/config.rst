.. _config:

Configuration Handling
======================


Configuration should be done through environment variable export ::

    $ export PORT=8999
    $ gunicorn "sief.main:bootstrap_app()" --log-file -
    [2015-08-06 12:58:35 +0200] [6590] [INFO] Starting gunicorn 19.3.0
    [2015-08-06 12:58:35 +0200] [6590] [INFO] Listening at: http://0.0.0.0:8999 (6590)
    [2015-08-06 12:58:35 +0200] [6590] [INFO] Using worker: sync
    [2015-08-06 12:58:35 +0200] [6593] [INFO] Booting worker with pid: 6593

Have a look at :file:`sief/default_settings.cfg` for the list of available
configuration variable.

Additional configuration (such as ``PORT``) can be available depending of the
wsgi serveur used (see `here <http://gunicorn-docs.readthedocs.org/en/latest/configure.html>`_
for gunicorn)

Configuration Values
--------------------

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

================================= =========================================
``SECRET_KEY``                    Application secret key
``BACKEND_API_PREFIX``            Backend url prefix for the api, mandatory
                                  if the frontend shares the same domain (default: '')
``FRONTEND_HOSTED``               Host the frontend on the application, if True
                                  the ``static`` folder will be served as the root
                                  (default: ``False``)
``FRONTEND_HOSTED_REDIRECT_URL``  If True, the frontend data will be fetched from
                                  the given url instead of the static folder
``FICHIER_URL_VALIDITY``          Validity of the url to access the ``Fichier``
                                  resource's file (default: 1day)
``FICHIERS_ALLOWED_EXTENSIONS``   List of allowed extensions for ``Fichier`` resource
                                  (default: ``['jpg', 'png', 'jpeg']``)
``MONGODB_URL``                   mogodb database for the application
                                  (default: ``mongodb://localhost:27017/sief``)
``MONGODB_TEST_URL``              mongodb database for the test
                                  (default: ``mongodb://localhost:27017/sief-test``)
``MONGODB_HOST``                  Not configurable (=MONGODB_URL)
                                  (Flask-mongoengine use MONGODB_HOST variable to configure mongodb connection)
``MONGOPATCHER_PATCHES_DIR``      Folder where datamodel patches are store
                                  (default: ""path.abspath(path.dirname(__file__)) + '/../datamodel_patches'"")
``BROKER_DB_URL``                 mongodb database for the broker
                                  (default: ``mongodb://localhost:27017/broker``)
``BROKER_TEST_DB_URL``            mongodb database for the broker in test
                                  (default: ``mongodb://localhost:27017/test-broker``)
``DISABLE_SOLR``                  If set to true, Solr will not be used (default: False)
``SOLR_URL``                      Solr database to use (default:
                                  ``http://localhost:8983/solr/sief``)
``SOLR_TEST_URL``                 Solr test database (default:
                                  ``http://localhost:8983/solr/sief-test``)
``TOKEN_VALIDITY``                Validity of authentification token (default: 1day)
``REMEMBER_ME_TOKEN_VALIDITY``    Validity of remember-me token (default: 1month)
``TOKEN_FRESHNESS_VALIDITY``      Time before a fresh token (i.e. which can be
                                  used to change password) turn non-fresh (disable by default)
``CORS_ORIGINS``                  Allowed origin urls (``;`` separated) for CORS
                                  (default: ``http://localhost:9000``)
``CORS_ALLOW_HEADERS``            Allowed CORS hedears
``CORS_EXPOSE_HEADERS``           Not configurable (=CORS_ALLOW_HEADERS) variable seems not to be used
``CORS_MAX_AGE``                  CORS headers duration
``CORS_SUPPORTS_CREDENTIALS``     Allow credentials into incoming request
``REFERENTIALS_CACHE_TIMEOUT``    Cache timeout for the queries to the referentials
                                  (default: 600, use 0 to disable)
``ENABLE_CACHE``                  Enable cache functionalities (default: false)
``CACHE_DIR``                     Directory where to store the cached elements
                                  (default: '/tmp/sief-cache')
``BACKEND_URL``                   Not configurable (=BACKEND_URL_DOMAIN+BROKER_API_PREFIX)
``BACKEND_URL_DOMAIN``            Domain name of the backend service
                                  (default: “http://127.0.0.1:5000”)
``BROKER_API_PREFIX``             Backend url prefix for the api, mandatory if the frontend shares
                                  the same domain (default: "")
``FRONTEND_DOMAIN``               Use to set web link to frontend page into e-mail to set new password
                                  (default: ""https://asile.dgef.interieur.gouv.fr"")
``FRONTEND_DOMAIN_INTRANET``      Use to set intranet link to frontend page into e-mail to set new password
                                  (default: ""https://asile.dgef.minint.fr"")
``POPULATE_DB``                   Must be set to False, set it to True if you really want to launch a
                                  populate of the DB
``PASSWORD_EXPIRY_DATE``          Time a normal user password is valid for
``SYSTEM_PASSWORD_EXPIRY_DATE``   Time a system account is valid for
================================= =========================================


Connectors service
------------------

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

================================== =========================================
``CONNECTORS_API_PREFIX``           The prefix part of the URI of the backend (between the domain name and
                                    the effective route. default : /api/)
``CONNECTORS_DEBUG``                Allow the connector to log information and enables the debug routes.
                                    Use with caution because personal data might be logged
``CONNECTOR_AGDREF_TESTING_STUB``   Do not disable FNE connector but simulate requests
``CONNECTOR_AGDREF_USERNAME``       AGDREF username for back end connection
``CONNECTOR_AGDREF_PASSWORD``       AGDREF password for back end connection
``CONNECTOR_AGDREF_EXPOSED_URL``    URL that AGDREF should use to talk with us
``CONNECTOR_AGDREF_URL``            URL to the AGDREF service
``CONNECTOR_AGDREF_HTTP_PROXY``     AGDREF HTTP proxy to use for requests
``CONNECTOR_AGDREF_HTTPS_PROXY``    AGDREF HTTPS proxy to use for requests
``CONNECTOR_AGDREF_PARTIAL``        Launch the AGDREF connector with only no "to-skip" components
``CONNECTOR_AGDREF_PREFIX``         Part of the URL between the domain name and the effective route
                                    of AGDREF connectors. defaults to : /connectors/agdref
``AGDREF_NUM_TESTING_STUB``         AGDREF identifiant query service simulation
``AGDREF_NUM_URL``                  URL to the AGDREF identifiant query service
``EURODAC_PREFIX``                  Prefix use for the generation of eurodac number, must be 3 digits
``CONNECTOR_DNA_USERNAME``          DNA username for back end connection
``CONNECTOR_DNA_PASSWORD``          DNA password for back end connection
``CONNECTOR_DNA_HTTP_PROXY``        DNA HTTP proxy to use for requests
``CONNECTOR_DNA_HTTPS_PROXY``       DNA HTTPS proxy to use for requests
``CONNECTOR_DNA_EXPOSED_URL``       URL that DNA should use to talk with us
``CONNECTOR_DNA_PREFIX``            Part of the URL between the domain name and the effective route of DNA
                                    connectors. defaults to : /connectors/dna
``CONNECTOR_DNA_URL``               URL of the DNA output connector (i.e. The URL of the DNA server)

``CONNECTOR_INEREC_USERNAME``       INEREC username for back end connection
``CONNECTOR_INEREC_URL``            INEREC username for back end connection
``CONNECTOR_INEREC_HTTP_PROXY``     INEREC HTTP proxy to use for requests
``CONNECTOR_INEREC_HTTPS_PROXY``    INEREC HTTPS proxy to use for requests
``DISABLE_AGDREF_NUM``              Disable AGDREF identifiant query service
``DISABLE_CONNECTOR_DNA``           Disable DNA connector
``DISABLE_CONNECTOR_AGDREF_INPUT``  Disable the input connector of AGDREF
``DISABLE_CONNECTOR_DNA_INPUT``     Disable the input DNA connector
``DISABLE_CONNECTOR_AGDREF``        Disable AGDREF connector
================================== =========================================

.. note::
There is no need for CONNECTOR_INEREC_PASSWORD given we don't have to expose
a WebService for INEREC.


Mail service
-----------

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

================================= =========================================
``DISABLE_MAIL``                  Enable or disable mail feature
``MAIL_SERVER``                   Mail server (IP or FQDN)
``MAIL_PORT``                     Mail server listening port
``MAIL_USE_TLS``                  Toggle TLS
``MAIL_USE_SSL``                  Toggle SSL
``MAIL_DEBUG``                    Toggle debug mode
``MAIL_USERNAME``                 User to use to authenticate against mail server
``MAIL_PASSWORD``                 User's password
``MAIL_DEFAULT_SENDER``           Sender address
``MAIL_ALERT_SENDER``             Sender address for alerts
================================= =========================================


FPR service
-----------

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

================================= =========================================
``DISABLE_FPR``                     Enable or disable FPR interrogation
``FPR_TESTING_STUB``                Don't actually do the interrogation to the FPR
``FPR_WSDL_URL``                    URL of WSDL describing the FPR SOAP service
``FPR_FORCE_QUERY_URL``             If set, overwrite the FPR service's URL provided in it WSDL
``FPR_CERTIFICATE``                 Path to the FPR server's client ceritificate
``FPR_HTTP_PROXY``                  HTTP proxy to use for communication with the FPR
``FPR_HTTPS_PROXY``                 HTTPS proxy to use for communication with the FPR
``FPR_IDENTIFICATION_APPLICATION``  Configuration passed to the FPR request
``FPR_IDENTIFICATION_PARAMETRE``    Configuration passed to the FPR request
``FPR_IDENTIFICATION_COMMANDE``     Configuration passed to the FPR request
``FPR_INFOTRACE_IDENTIFIANT``       Configuration passed to the FPR request
``FPR_INFOTRACE_POSTE``             Configuration passed to the FPR request
``FPR_INFOTRACE_SCOM``              Configuration passed to the FPR request
``FPR_CACHE_TIMEOUT``               Cache timeout for the request to the FPR
                                    (default: 600, use 0 to disable)
``FPR_CONTACT_TIMEOUT``             Set the timeout when trying to contacting the FPR
================================= =========================================


FNE service
-----------

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

================================= =========================================
``DISABLE_FNE``                   Disable FNE connector
``FNE_TESTING_STUB``              Do not disable FNE connector but simulate requests
``FNE_URL``                       Url to the FNE service
``FNE_HTTP_PROXY``                FNE HTTP proxy to use for requests
``FNE_HTTPS_PROXY``               FNE HTTPS proxy to use for requests
``FNE_CACHE_TIMEOUT``             Cache timeout for the request to the FNE
                                  (default: 600, use 0 to disable)
================================= =========================================

ANTS PFTD service
-----------

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

================================= =========================================
``DISABLE_PFTD``                  Disable PFTD connector
``PFTD_TESTING_STUB``             Do not disable PFTD connector but simulate requests
``PFTD_URL``                      Url to the PFTD service
``PFTD_CERTIFICATE``              Path to the PFTD server's client certificate
``PFTD_HTTP_PROXY``               PFTD HTTP proxy to use for requests
``PFTD_HTTPS_PROXY``              PFTD HTTPS proxy to use for requests
``PFTD_CANAL_TYPE``               Configuration passed to the PFTD request
``PFTD_CANAL_ID``                 Configuration passed to the PFTD request
``PFTD_RETRY``                    Number of retry to use for requests
``PFTD_RETRY_BACKOFF_FACTOR``     A backoff factor to apply between attempts after the
                                  second retry
                                  ex : 0.2 will sleep for [0.0s, 0.4s, 0.8s] between retries
                                  (default: 0.2, use 0 to disable)
``PFTD_TIMEOUT``                  Cache timeout for the request to the PFTD
                                  (default: 30, use 0 to disable)
================================= =========================================
