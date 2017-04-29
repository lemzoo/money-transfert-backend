import pytest
import json
from freezegun import freeze_time
from datetime import datetime

from core import CoreApp

from broker_dispatcher.event_handler import EventHandlerItem, EventHandler

from broker_rabbit.broker_rabbit import BrokerRabbit
from broker_rabbit.rabbit.connection_handler import ConnectionHandler
from broker_rabbit.rabbit.worker import Worker

from tests.broker_rabbit.rabbit_api import client_rabbit
from tests.common import get_broker_rabbit_db_url, get_rabbit_url, get_rabbit_exchange


DEFAULT_USER_TEST = 'guest'
DEFAULT_PASSWORD_TEST = 'guest'
VHOST_TEST = '/'
RABBIT_URL_FOR_TEST = 'localhost:15672'

client_api_rabbit = client_rabbit(RABBIT_URL_FOR_TEST, DEFAULT_USER_TEST, DEFAULT_PASSWORD_TEST)


@pytest.fixture
def app():
    app = CoreApp(__name__)
    app.debug = True
    app.config['BROKER_RABBIT_DB_ALIAS'] = 'test-broker-rabbit'
    app.config['BROKER_RABBIT_MONGODB_URL'] = get_broker_rabbit_db_url()
    app.config['BROKER_RABBIT_URL'] = get_rabbit_url()
    app.config['BROKER_RABBIT_EXCHANGE'] = get_rabbit_exchange()
    return app


@pytest.fixture
def default_handler(event='event-1', queue='test-queue', processor='webhook'):
    return {'label': 'test-%s' % event,
            'event': event, 'queue': queue,
            'processor': processor}


@pytest.fixture
def broker_rabbit(app):
    broker_rabbit = BrokerRabbit()
    empty_event_handler_item = list()
    event_handler = EventHandler(empty_event_handler_item)
    broker_rabbit.init_app(app, event_handler)
    return broker_rabbit


@pytest.fixture
def model_message(broker_rabbit):
    return broker_rabbit.model.Message


@pytest.fixture
def event_handler(broker_rabbit, default_handler):
    eh_rabbit = broker_rabbit.event_handler
    producer = broker_rabbit._producer_for_rabbit

    eh_item = EventHandlerItem(default_handler)
    eh_rabbit.append(eh_item)

    queue = default_handler['queue']
    new_queues = [queue]
    broker_rabbit.queues = new_queues
    producer.init_env_rabbit(new_queues)

    return eh_rabbit


@pytest.fixture
def event_handler_item(event_handler):
    eh_item = event_handler.items[0]

    return eh_item


@pytest.fixture
@freeze_time("2017-04-11 15:10:30")
def message_retry(model_message, event_handler_item):
    payload = {
        'created': datetime.utcnow().isoformat(),
        'queue': event_handler_item.queue,
        'origin': '9876543210',
        'handler': event_handler_item.label,
        'discriminant': '0123456789',
        'json_context': json.dumps({'key': 'value'}),
        'status': 'RETRY'
    }
    msg = model_message.load(json.dumps(payload))
    msg.save()

    return msg


@pytest.fixture
@freeze_time("2017-04-11 15:20:30")
def message_first_try(model_message, event_handler_item):
    payload = {
        'created': datetime.utcnow().isoformat(),
        'queue': event_handler_item.queue,
        'origin': '9876543210',
        'handler': event_handler_item.label,
        'discriminant': '012345',
        'json_context': json.dumps({'key': 'value'}),
        'status': 'FIRST_TRY'
    }
    msg = model_message.load(json.dumps(payload))
    msg.save()

    return msg


@pytest.fixture
@freeze_time("2017-04-11 15:30:30")
def message_dump():
    return {
        'created': datetime.utcnow().isoformat(),
        'queue': None,
        'origin': 'my-origin',
        'handler': None,
        'discriminant': '0123456789',
        'json_context': '{"field": "value"}',
        'status': 'FIRST_TRY'
    }


@pytest.fixture
def worker(app, model_message, event_handler, queue='test-queue'):
    rabbit_test_url = app.config['BROKER_RABBIT_URL']
    connection_handler = ConnectionHandler(rabbit_test_url)
    worker = Worker(connection_handler, queue, event_handler, model_message)

    return worker
