import json
from datetime import datetime

from broker_dispatcher.exceptions import UnknownEventError
from broker_dispatcher.event_handler import EventHandler

from broker import Broker
from broker_rabbit import BrokerRabbit


class BrokerDispatcher:

    """Broker Dispatcher which will dispatch the message on
    the broker legacy or on Broker Rabbit.
    """

    def __init__(self, app=None, **kwargs):
        self.broker_legacy = None
        self.broker_rabbit = None
        if app is not None:
            self.init_app(app, **kwargs)

    def init_app(self, app, event_handlers=None, config=None):
        """ Init the Broker Dispatcher by using the given configuration instead
        default settings.

        :param app: Current application context
        :param list event_handlers: Events handlers defined on the SIAEF app
        :param dict config: Config parameters to use for this instance
        """
        if event_handlers is None:
            event_handlers = []
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        if 'broker_dispatcher' not in app.extensions:
            app.extensions['broker_dispatcher'] = self
        else:
            # Raise an exception if extension already initialized as
            # potentially new configuration would not be loaded.
            raise RuntimeError('Extension already initialized')

        self.app = app
        self.event_handler = EventHandler(event_handlers)
        config = config or app.config

        config.setdefault('BROKER_AVAILABLE_EVENTS', [])
        self.events = app.config['BROKER_AVAILABLE_EVENTS']

        config.setdefault('FF_ENABLE_RABBIT', False)
        self.ff_enable_rabbit = app.config['FF_ENABLE_RABBIT']

        self.broker_legacy = Broker()
        self.broker_legacy.init_app(app, self.event_handler)

        if self.ff_enable_rabbit:
            self.broker_rabbit = BrokerRabbit()
            self.broker_rabbit.init_app(app, self.event_handler)

    def send(self, event, origin=None, context=None):
        """Notify the event_handlers who have subscribed to the given event

        :param event: event to trigger
        :param origin: skip the event handlers with similar origin
        :param context: dict of arbitrary data to transfer
        """
        if context is None:
            context = {}

        # Check the coherence of the event
        if event not in self.events:
            raise UnknownEventError('Event %s is not registered' % event)

        event_handlers = self.event_handler.filter(event, origin)
        for eh_item in event_handlers:
            self.dispatch_message(origin, eh_item, context)

    def dispatch_message(self, origin, eh_item, context=None):
        """Route the message to the correct Message Broker by using the feature
        flipping and the configuration file.
        """
        if context is None:
            context = {}
        queue = eh_item.queue
        message_dump = {
            'created': datetime.utcnow().isoformat(),
            'queue': queue,
            'origin': origin,
            'handler': eh_item.label,
            'json_context': json.dumps(context, cls=self.app.json_encoder)
        }

        to_rabbit = eh_item.to_rabbit

        if self.ff_enable_rabbit and to_rabbit:
            message_dump['discriminant'] = self.make_discriminant()
            message_dump['status'] = 'FIRST_TRY'
            return self.broker_rabbit.send(queue, message_dump)
        else:
            message_dump['status'] = 'READY'
            return self.broker_legacy.send(message_dump)

    # Fix Me /!\
    def make_discriminant(self, id=None):
        if id is None:
            return '0123456789'

        return id
