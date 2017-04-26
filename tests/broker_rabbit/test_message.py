import pytest
import json
from freezegun import freeze_time
from datetime import datetime, timedelta

from tests.broker_dispatcher.fixtures import client
from tests.broker_rabbit.fixtures import *
from tests import common


VALID_DIGITS = 19


class TestMessageRabbit(common.BaseRabbitBrokerTest):

    def test_get_single_message(self, client, message_retry):
        route = '/rabbit/queues/%s/messages/%s' % (
            message_retry.queue, message_retry.id)
        ret = client.get(route)
        assert ret.status_code == 200
        assert ret.data.get('queue') == message_retry.queue
        assert ret.data.get('origin') == message_retry.origin
        assert ret.data.get('handler') == message_retry.handler
        assert ret.data.get('json_context') == message_retry.json_context
        assert ret.data.get('discriminant') == message_retry.discriminant
        assert ret.data.get('status') == message_retry.status
        assert ret.data.get('status_comment') == message_retry.status_comment
        assert ret.data.get('created')[:VALID_DIGITS] == datetime(2017, 4, 11, 15, 10, 30).isoformat()

    def test_update_single_message_on_error(self, client, message_retry):
        route = '/rabbit/queues/%s/messages/%s' % (
            message_retry.queue, message_retry.id)
        # Change the status and the status comment
        new_status = 'RETRY'
        new_comment = 'Message is corrected manually'
        json_context = json.dumps({'key': 'value', 'number': 1})
        payload = {
            'json_context': json_context,
            'status': new_status,
            'status_comment': new_comment
        }
        ret = client.patch(route, data=payload)
        assert ret.status_code == 200
        message_retry.reload()
        assert ret.data.get('queue') == message_retry.queue
        assert ret.data.get('origin') == message_retry.origin
        assert ret.data.get('handler') == message_retry.handler
        assert ret.data.get('discriminant') == message_retry.discriminant
        assert ret.data.get('json_context') == json_context
        assert ret.data.get('status') == new_status
        assert ret.data.get('status_comment') == new_comment
        assert ret.data.get('created')[:VALID_DIGITS] == datetime(2017, 4, 11, 15, 10, 30).isoformat()


class TestMessageRabbitList(common.BaseRabbitBrokerTest):

    def test_get_messages_with_one_message(self, client, message_retry):

        route = '/rabbit/queues/test-queue/messages'
        ret = client.get(route)
        # Given
        data_returned = ret.data.get('_items')[0]
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 1
        assert data_returned.get('queue') == 'test-queue'
        assert data_returned.get('origin') == '9876543210'
        assert data_returned.get('handler') == message_retry.handler
        assert data_returned.get('json_context') == message_retry.json_context
        assert data_returned.get('discriminant') == '0123456789'
        assert data_returned.get('status') == 'RETRY'
        assert data_returned.get('status_comment') == message_retry.status_comment
        assert data_returned.get('created')[:VALID_DIGITS] == datetime(2017, 4, 11, 15, 10, 30).isoformat()

    def test_get_two_messages(self, client, message_first_try, message_retry):

        route = '/rabbit/queues/test-queue/messages'
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 2

    def test_get_messages_with_0_message(self, client, event_handler_item):

        route = '/rabbit/queues/test-queue/messages'
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 0

    def test_get_one_status_retry(self, client, message_first_try, message_retry):
        route = '/rabbit/queues/test-queue/messages?status=RETRY'
        ret = client.get(route)
        assert len(ret.data.get('_items')) == 1
        data_returned = ret.data.get('_items')[0]
        assert data_returned.get('status') == 'RETRY'

    def test_search_messages_by_id(self, client, message_first_try):
        # Given
        route = '/rabbit/queues/test-queue/messages'
        route += '?page=1&per_page=12&q=%s' % message_first_try.pk
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 1

    def test_search_messages_by_discriminant(self, client, message_first_try, message_retry):
        # Given
        discriminant = message_first_try.discriminant
        route = '/rabbit/queues/test-queue/messages?page=1&per_page=12&q=%s' % discriminant
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 1

    def test_search_messages_with_bad_discriminant(self, client, message_first_try, message_retry):
        # Given
        bad_discriminant = 'bad_discriminant'
        route = '/rabbit/queues/test-queue/messages?page=1&per_page=12&q=%s' % bad_discriminant
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 0

    def test_sort_messages(self, client, message_first_try, message_retry):
        # Given
        route = '/rabbit/queues/test-queue/messages'
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 2
        assert ret.data.get('_items')[1]['created'] < ret.data.get('_items')[0]['created']

    def test_search_messages_by_handler(self, client, event_handler_item, message_first_try, message_retry):
        # Given
        handler = event_handler_item.label
        route = '/rabbit/queues/test-queue/messages?page=1&per_page=12&q=%s' % handler
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 2

    def test_search_messages_with_bad_handler(self, client, message_first_try, message_retry):
        # Given
        bad_handler = 'bad_handler'
        route = '/rabbit/queues/test-queue/messages?page=1&per_page=12&q=%s' % bad_handler
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 0

    def test_advanced_search_messages_by_id(self, client, message_retry):
        # Given
        route = '/rabbit/queues/test-queue/messages'
        route += "?page=1&per_page=12&fq=pk:%s" % message_retry.pk
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 1

    def test_advanced_search_messages_with_bad_id(self, client, event_handler_item):
        # Given
        bad_id = 'bad_id'
        route = '/rabbit/queues/test-queue/messages?page=1&per_page=12&fq=pk:%s' % bad_id
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 400

    def test_advanced_search_messages_by_discriminant(self, client, message_first_try, message_retry):
        # Given
        discriminant = message_retry.discriminant
        route = '/rabbit/queues/test-queue/messages?page=1&per_page=12&fq=discriminant:%s' % discriminant
        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 1

    def test_advanced_search_messages_with_bad_discriminant(self, client, message_first_try, message_retry):
        # Given
        bad_discriminant = "N'importe quoi"
        route = '/rabbit/queues/test-queue/messages?page=1&per_page=12&fq=discriminant:%s' % bad_discriminant

        # When
        ret = client.get(route)
        # Then
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 0

    @freeze_time("2017-04-11 15:10:30")
    def test_advanced_search_messages_with_created_date_from_ok(self, client, message_retry):
        date_from = (datetime.now() + timedelta(days=-1)).isoformat()
        route = '/rabbit/queues/test-queue/messages'
        route += "?page=1&per_page=12&fq=created:[%s TO *]" % date_from
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 1

    @freeze_time("2017-04-11 15:10:30")
    def test_advanced_search_messages_with_created_date_from_ko(self, client, message_retry):
        date_from = (datetime.now() + timedelta(days=1)).isoformat()
        route = '/rabbit/queues/test-queue/messages'
        route += "?page=1&per_page=12&fq=created:[%s TO *]" % date_from
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 0

        date_from = "bad_date"
        route = '/rabbit/queues/test-queue/messages'
        route += "?page=1&per_page=12&fq=created:[%s TO *]" % date_from
        ret = client.get(route)
        assert ret.status_code == 400

    @freeze_time("2017-04-11 15:10:30")
    def test_advanced_search_messages_with_created_date_to_ok(self, client, message_retry):
        date_to = (datetime.now() + timedelta(days=1)).isoformat()
        route = '/rabbit/queues/test-queue/messages'
        route += "?page=1&per_page=12&fq=created:[* TO %s]" % date_to
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 1

    @freeze_time("2017-04-11 15:10:30")
    def test_advanced_search_messages_with_created_date_to_ko(self, client, message_retry):
        date_to = (datetime.now() + timedelta(days=-1)).isoformat()
        route = '/rabbit/queues/test-queue/messages'
        route += "?page=1&per_page=12&fq=created:[* TO %s]" % date_to
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 0

        date_to = "bad_date"
        route = '/rabbit/queues/test-queue/messages'
        route += "?page=1&per_page=12&fq=created:[* TO %s]" % date_to
        ret = client.get(route)
        assert ret.status_code == 400

    @freeze_time("2017-04-11 15:10:30")
    def test_advanced_search_messages_with_created_date_interval(self, client, message_first_try, message_retry):
        date_from = (datetime.now() + timedelta(days=-1)).isoformat()
        date_to = (datetime.now() + timedelta(days=1)).isoformat()
        route = '/rabbit/queues/test-queue/messages'
        route += "?page=1&per_page=12&fq=created:[%s TO %s]" % (date_from, date_to)
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data.get('_items')) == 2
