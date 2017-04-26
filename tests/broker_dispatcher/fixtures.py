import pytest
from unittest.mock import Mock
from functools import namedtuple
import json

from core import CoreApp

from broker_dispatcher.event_handler import EventHandlerItem
from broker_dispatcher import BrokerDispatcher

DEFAULT_EVENTS = ['event-1', 'event-2', 'event-3']


@pytest.fixture
def app(events=DEFAULT_EVENTS):
    app = CoreApp(__name__)
    app.debug = True
    app.config['BROKER_AVAILABLE_EVENTS'] = events
    return app


@pytest.fixture
def client(request, app):
    CookedResponse = namedtuple('CookedResponse', ['status_code', 'headers', 'data'])

    class Client:

        def __init__(self, test_client):
            self.test_client = test_client

        def __getattr__(self, name):
            if name in ('get', 'post', 'put', 'patch', 'delete'):
                return self.request(name)
            return getattr(self.test_client, name)

        def request(self, verb):
            test_client_f = getattr(self.test_client, verb)

            def f(route, headers=None, data=None):
                params = {}
                if data:
                    data = json.dumps(data)
                    params['headers'] = headers
                    params['content_type'] = 'application/json'
                    params['content_length'] = len(data)
                r = test_client_f(route, data=data, **params)
                data = r.data.decode('utf-8')
                if data:
                    data = json.loads(data)
                return CookedResponse(r.status_code, r.headers, data)
            return f

    return Client(app.test_client())


@pytest.fixture
def broker_dispatcher(app):
    return BrokerDispatcher(app)


@pytest.fixture
def broker_dispatcher_mocked(broker_dispatcher):
    broker_dispatcher.broker_legacy = Mock()
    broker_dispatcher.broker_rabbit = Mock()
    return broker_dispatcher


@pytest.fixture
def default_handler(event='event-1', queue='test-queue', processor='webhook', origin='my-origin'):
    return {'label': 'test-%s' % event, 'event': event, 'queue': queue,
            'origin': origin, 'processor': processor}


@pytest.fixture
def event_handler(broker_dispatcher, default_handler):
    eh_broker_dispatcher = broker_dispatcher.event_handler
    eh_item = EventHandlerItem(default_handler)
    eh_broker_dispatcher.append(eh_item)

    return eh_broker_dispatcher


@pytest.fixture
def event_handler_item(event_handler):
    eh_item = event_handler.items[0]

    return eh_item
