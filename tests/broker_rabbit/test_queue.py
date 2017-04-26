import pytest

from tests import common
from tests.broker_dispatcher.fixtures import client
from tests.broker_rabbit.fixtures import *


class TestQueueRabbit(common.BaseRabbitBrokerTest):

    def test_get_queues(self, client, event_handler):
        route = '/rabbit/queues'
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data["_items"]) == len(event_handler.items)

    def test_get_empty_list_queue(self, client, broker_rabbit):
        route = '/rabbit/queues'
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data["_items"]) == 0

    def test_get_single_queue(self, client, event_handler_item):
        queue = event_handler_item.queue
        route = '/rabbit/queues/%s' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert ret.data['queue'] == queue

    def test_queue_not_found(self, client, event_handler_item):
        queue = 'undefined-queue'
        route = '/rabbit/queues/%s' % queue
        ret = client.get(route)
        assert ret.status_code == 404
        assert '_error' in ret.data


class TestQueueRabbitCountStatus(common.BaseRabbitBrokerTest):

    def test_get_count_message_by_status(self, client, event_handler_item,
                                         message_first_try, message_retry):
        # Given
        queue = event_handler_item.queue
        route = '/rabbit/queues/%s' % queue
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert ret.data.get('status_count')['FIRST_TRY'] == 1
        assert ret.data.get('status_count')['RETRY'] == 1
