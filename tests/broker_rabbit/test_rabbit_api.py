import pytest
import json

from pyrabbit.api import Client

from tests import common

from tests.broker_rabbit.rabbit_api import (
    create_exchange, create_queue, create_binding, publish, get_messages,
    client_rabbit, purge_queues, get_queues)

USERNAME = 'guest'
PASSWORD = 'guest'
RABBIT_URL_FOR_TEST = 'localhost:15672'
VHOST = '/'


class TestRabbitAPI(common.BaseRabbitBrokerTest):

    def test_get_single_message(self):
        client = Client('localhost:15672', USERNAME, PASSWORD)

        # 1. create exchange
        exchange = 'exchange-test'
        create_exchange(client, VHOST, exchange)

        # 2. create queue
        queue = 'queue-test'
        create_queue(client, VHOST, queue)

        # 3. Bind exchange to the queue
        create_binding(client, VHOST, exchange, queue)

        # 4. publish a message on this queue
        payload = {'key': 'value'}
        payload_rabbit = json.dumps(payload)
        ret = publish(client, VHOST, exchange, queue, payload_rabbit)
        assert ret

        # 5. get message
        messages = get_messages(client, VHOST, queue)
        message = messages[0]
        assert payload_rabbit == message['payload']

        payload_to_compare = json.loads(message['payload'])
        assert payload == payload_to_compare

    def test_purge_queue(self):
        client = client_rabbit(RABBIT_URL_FOR_TEST, USERNAME, PASSWORD)
        queues = get_queues(client)
        ret = purge_queues(client, VHOST, queues)
        assert ret
