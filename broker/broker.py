import mongoengine
import logging
from flask.ext.restful import Resource

from broker.model import bind_model
from broker.view import bind_view
from broker.worker import WorkerPool, repair_queue_worker


DEFAULT_DB_ALIAS = 'default_broker'
DEFAULT_DB_URL = 'mongodb://localhost:27017/broker'
DEFAULT_API_PREFIX = '/broker'


class Broker:

    """
    :param db_url: mongodb url
    :param db_alias: mongoengine db connection alias to use (default: default_broker)
    :param events: list of event names the event_handlers are allowed to register against
    :param api_prefix: prefix all the api routes (default: '/broker')
    :param api_base_resource_cls: flask restful `Resource` cls to use to
        build the api ressources
    """

    def __init__(self, app=None, **kwargs):
        self._connection = None
        if app is not None:
            self.init_app(app, **kwargs)

    def init_app(self, app, event_handler, config=None):
        """
        :param config: Use given config instead of app.config
        """
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        if 'broker' not in app.extensions:
            app.extensions['broker'] = self
        else:
            # Raise an exception if extension already initialized as
            # potentially new configuration would not be loaded.
            raise Exception('Extension already initialized')

        self.app = app
        self.event_handler = event_handler
        config = config or app.config
        config.setdefault('BROKER_DB_URL', DEFAULT_DB_URL)
        config.setdefault('BROKER_DB_ALIAS', DEFAULT_DB_ALIAS)
        config.setdefault('BROKER_API_PREFIX', DEFAULT_API_PREFIX)
        config.setdefault('BROKER_API_BASE_RESOURCE_CLS', Resource)
        self.db_url = app.config['BROKER_DB_URL']
        self.db_alias = app.config['BROKER_DB_ALIAS']
        self.api_prefix = app.config['BROKER_API_PREFIX']
        self.api_base_resource_cls = app.config['BROKER_API_BASE_RESOURCE_CLS']
        self.model = bind_model(self.db_alias)
        self._api = bind_view(self, prefix=self.api_prefix,
                              base_resource_cls=self.api_base_resource_cls)
        self._api.init_app(app)
        # Init connection with the database
        self.connection = mongoengine.connect(
            host=self.app.config['BROKER_DB_URL'],
            alias=self.app.config['BROKER_DB_ALIAS'])
        # Given Models are defined with no db_alias, implicit `ensure_indexes` cannot be done
        self.model.QueueManifest.ensure_indexes()
        self.model.Message.ensure_indexes()

    def send(self, message_dump):
        """Put the message on broker database

        :param message_dump: dump of the message to save on the database
        """

        msg_cls = self.model.Message
        msg_event = msg_cls(**message_dump)

        msg_event.save()

    def drop_queue(self, queue):
        """
        Fully erase a queue from the database
        """
        self.model.Message.objects(queue=queue).delete()
        self.model.QueueManifest.objects(queue=queue).delete()

    def create_queue(self, queue):
        return self.model.QueueManifest(queue=queue).save()

    def run_queues(self, queues, loglevel='INFO', **kwargs):
        """
        Start processing the given queues

        ..note:: This function doesn't return
        """
        numeric_level = getattr(logging, loglevel.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % loglevel)
        print(' *** Processing Queues ***')
        print('Args: %s' % kwargs)
        print('Database: %s' % self.db_url)
        print('Queues: %s' % queues)
        wp = WorkerPool(self, queues, log_level=numeric_level, **kwargs)
        wp.run()

    def repair_queue(self, queue):
        """
        Retrieve and fix (i.e. pass to STOPPED) the queue

        ..note: Use this function after worker crash/cold stop
                Make sure no workers are running on the queue
        """
        return repair_queue_worker(self.model, queue)
