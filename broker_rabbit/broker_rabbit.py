import mongoengine
from flask.ext.restful import Resource

from broker_rabbit.view import bind_view
from broker_rabbit.model import bind_model
from broker_rabbit.rabbit.connection_handler import ConnectionHandler
from broker_rabbit.rabbit.producer import Producer


DEFAULT_API_PREFIX = '/rabbit'
DEFAULT_DB_ALIAS = 'default_broker_rabbit'
DEFAULT_RABBIT_MONGODB_URL = 'mongodb://localhost:27017/siaef-broker-rabbit'
DEFAULT_BROKER_RABBIT_URL = 'amqp://guest:guest@localhost:5672/%2F'
DEFAULT_EXCHANGE = 'SI-AEF'


class BrokerRabbit:

    """This is a  Message Broker which using RabbitMQ process for publishing
    and consuming message on SIAEF application.
    """

    def __init__(self, app=None, **kwargs):
        """Create a new instance of Broker Rabbit by using the given
        parameters to connect to RabbitMQ.
        """
        self._connection_handler = None
        self._producer_for_rabbit = None
        if app is not None:
            self.init_app(app, **kwargs)

    def init_app(self, app, event_handler, config=None):
        """
        Init the application by using the given param

        :param app: Current application context
        :param list event_handlers: Events handlers defined on the SIAEF app
        :param dict config: Config parameters to use for this instance
        """
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        if 'broker_rabbit' not in app.extensions:
            app.extensions['broker_rabbit'] = self
        else:
            # Raise an exception if extension already initialized as
            # potentially new configuration would not be loaded.
            raise Exception('Extension already initialized')

        self.app = app
        self.event_handler = event_handler
        config = config or app.config

        config.setdefault('BROKER_RABBIT_MONGODB_URL', DEFAULT_RABBIT_MONGODB_URL)
        config.setdefault('DISABLE_RABBIT', False)
        config.setdefault('BROKER_RABBIT_URL', DEFAULT_BROKER_RABBIT_URL)
        config.setdefault('BROKER_RABBIT_DB_ALIAS', DEFAULT_DB_ALIAS)
        config.setdefault('BROKER_RABBIT_API_PREFIX', DEFAULT_API_PREFIX)
        config.setdefault('BROKER_API_BASE_RESOURCE_CLS', Resource)
        config.setdefault('BROKER_RABBIT_EXCHANGE', DEFAULT_EXCHANGE)

        self.db_alias = app.config['BROKER_RABBIT_DB_ALIAS']
        self.model = bind_model(self.db_alias)

        self.api_prefix = app.config['BROKER_RABBIT_API_PREFIX']
        self.api_base_resource_cls = app.config['BROKER_API_BASE_RESOURCE_CLS']
        self._api = bind_view(self, prefix=self.api_prefix,
                              base_resource_cls=self.api_base_resource_cls)
        self._api.init_app(app)

        # Init connection with the database
        self.connection = mongoengine.connect(
            host=self.app.config['BROKER_RABBIT_MONGODB_URL'],
            alias=self.app.config['BROKER_RABBIT_DB_ALIAS'])
        # Given Models are defined with no db_alias, implicit `ensure_indexes` cannot be done
        self.model.Message.ensure_indexes()

        self.disable_rabbit = config['DISABLE_RABBIT']
        self.rabbit_url = config['BROKER_RABBIT_URL']

        # Open Connection to RabbitMQ
        self._connection_handler = ConnectionHandler(self.rabbit_url)

        # Setup default producer for rabbit
        self._exchange_name = app.config['BROKER_RABBIT_EXCHANGE']
        self._producer_for_rabbit = Producer(self._connection_handler, self._exchange_name)
        self.queues = self.get_queues()
        self._producer_for_rabbit.init_env_rabbit(self.queues)

    def get_queues(self):
        return list({eh.queue for eh in self.event_handler.items})

    def send(self, queue, message_dump):
        """Send the message to RabbitMQ with the correct payload

        :param str queue: The queue to publish the message
        :param dict message_dump: The content of the message
        """
        if self.disable_rabbit:
            # raise RabbitDisableError('RabbitMQ broker is disabled.')
            return

        self._producer_for_rabbit.publish(queue, message_dump)
