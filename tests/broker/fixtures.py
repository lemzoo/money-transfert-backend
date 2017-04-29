import pytest
import json

from core import CoreApp

from broker_dispatcher.event_handler import EventHandlerItem, EventHandler

from broker import Broker
from broker.worker import Worker

from tests.common import get_broker_legacy_db_url


@pytest.fixture
def app():
    app = CoreApp(__name__)
    app.debug = True
    app.config['BROKER_DB_ALIAS'] = 'test-broker'
    app.config['BROKER_DB_URL'] = get_broker_legacy_db_url()
    return app


@pytest.fixture
def default_handler(event='event-1', queue='test-queue', processor='webhook'):
    return {'label': 'test-%s' % event,
            'event': event, 'queue': queue,
            'processor': processor}


@pytest.fixture
def broker(app):
    broker = Broker()
    empty_event_handler_item = list()
    event_handler = EventHandler(empty_event_handler_item)
    broker.init_app(app, event_handler)
    return broker


@pytest.fixture
def event_handler(broker, default_handler):
    eh_broker = broker.event_handler

    eh_item = EventHandlerItem(default_handler)
    eh_broker.append(eh_item)

    return eh_broker


@pytest.fixture
def event_handler_item(event_handler):
    eh_item = event_handler.items[0]

    return eh_item


@pytest.fixture
def message_dump(event_handler_item):
    msg_dump = {
        'origin': 'my-origin',
        'queue': event_handler_item.queue,
        'handler': event_handler_item.label,
        'json_context': json.dumps({'field': 'value'})
    }
    return msg_dump


@pytest.fixture
def queue(broker, queue_name='test-queue'):
    queue_cls = broker.model.QueueManifest
    q = queue_cls(queue=queue_name, status='STOPPED').save()

    return q


@pytest.fixture
def worker(broker, queue):
    w = Worker(broker, queue.queue)

    return w


@pytest.fixture
def message(broker, event_handler_item, queue_name='test-queue'):
    msg_cls = broker.model.Message
    msg = msg_cls(queue=queue_name, handler=event_handler_item.label)
    msg.save()

    return msg
