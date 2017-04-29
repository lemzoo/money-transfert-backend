import pytest
import requests
from functools import namedtuple
from datetime import datetime
from dateutil.parser import parse

from connector import (
    find_and_execute, register_processor, ProcessMessageBadResponseError,
    ProcessMessageEventHandlerConfigError, ProcessMessageNoResponseError,
    ProcessMessageError, ProcessMessageNeedWaitError)

from broker.manager import broker_watch_get_state_message, broker_check_state_message
from broker.model import Message

from tests import common
from tests.broker.fixtures import *


Response = namedtuple('Response', ('ok', 'status_code', 'reason', 'text'))


class TestProcessor(common.BaseLegacyBrokerTest):

    def test_processor(self, broker, event_handler_item, message_dump):
        event_handler_item.modify(processor='good_processor')

        @register_processor
        def good_processor(handler, msg):
            return 'ok'
        broker.send(message_dump)
        msg = Message.objects.first()
        handler = broker.event_handler.get(msg.handler)
        assert handler == event_handler_item
        assert msg.status == 'READY'
        broker.event_handler.execute_legacy(msg)
        msg.reload()
        assert msg.status == 'DONE'
        assert msg.processed
        assert msg.processed > msg.created

    def test_error_processor(self, broker, event_handler_item, message_dump):
        event_handler_item.modify(processor='error_processor')

        @register_processor
        def good_processor(msg):
            raise ValueError('expected exception')
        broker.send(message_dump)
        msg = Message.objects.first()
        handler = broker.event_handler.get(msg.handler)
        assert handler == event_handler_item
        assert msg.status == 'READY'
        with pytest.raises(ProcessMessageError):
            broker.event_handler.execute_legacy(msg)
        msg.reload()
        assert msg.status == 'FAILURE'
        assert msg.processed
        assert msg.processed > msg.created

    def test_error_handler(self, broker, event_handler_item, message_dump):
        event_handler_item.modify(processor='error_processor')

        @register_processor
        def good_processor(msg):
            raise ValueError('expected exception')

        broker.send(message_dump)
        msg = Message.objects.first()
        msg.handler = 'I do not exist'
        assert msg.status == 'READY'

        with pytest.raises(ProcessMessageError):
            broker.event_handler.execute_legacy(msg)

        msg.reload()
        assert msg.status == 'FAILURE'
        assert 'Pas de handler pour ce type de message' == msg.status_comment
        assert msg.processed
        assert msg.processed > msg.created

    def test_unknown_processor(self, broker, event_handler_item, message_dump):
        event_handler_item.modify(processor='unknown_processor')
        broker.send(message_dump)
        msg = Message.objects.first()
        handler = broker.event_handler.get(msg.handler)
        assert handler == event_handler_item
        assert msg.status == 'READY'

        with pytest.raises(ProcessMessageError):
            broker.event_handler.execute_legacy(msg)

        msg.reload()
        assert msg.status == 'FAILURE'

    def test_retry_failed(self, broker, event_handler_item, message_dump):
        event_handler_item.modify(processor='good_processor')

        @register_processor
        def good_processor(handler, msg):
            return 'Should not be here'

        broker.send(message_dump)
        msg = Message.objects.first()
        handler = broker.event_handler[msg.handler]
        assert handler == event_handler_item
        assert msg.status == 'READY'
        msg.modify(status='FAILURE')

        with pytest.raises(ProcessMessageError):
            broker.event_handler.execute_legacy(msg)

        msg.reload()
        assert msg.status == 'FAILURE'

    def test_need_wait(self, broker, event_handler_item, message_dump):
        event_handler_item.modify(processor='waiter_processor')

        @register_processor
        def waiter_processor(handler, msg):
            if not msg.next_run:
                raise ProcessMessageNoResponseError('waiting')
            return 'done'

        broker.send(message_dump)
        msg = Message.objects.first()
        handler = broker.event_handler[msg.handler]
        assert handler == event_handler_item
        assert msg.status == 'READY'
        with pytest.raises(ProcessMessageNeedWaitError):
            broker.event_handler.execute_legacy(msg)

        msg.reload()
        assert msg.status == 'READY'
        assert msg.next_run
        assert msg.next_run > datetime.utcnow()

        # Make sure next_run prevent the execution
        with pytest.raises(ProcessMessageNeedWaitError):
            broker.event_handler.execute_legacy(msg)
        msg.reload()
        assert msg.status == 'READY'
        assert msg.next_run

        # If next_run is passed, the execution is done
        msg.next_run = datetime.utcnow()
        broker.event_handler.execute_legacy(msg)
        msg.reload()
        assert msg.status == 'DONE'
        assert not msg.next_run


class TestWebhookProcessor:

    def test_working(self, event_handler_item, message):

        # Given url should returns a 200
        event_handler_item.modify(context={'url': 'http://www.example.com'},
                                  processor='webhook')
        ret = find_and_execute(event_handler_item.processor,
                               event_handler_item, message)
        assert ret

    def test_bad_config(self, event_handler_item, message):
        event_handler_item.modify(context={},
                                  processor='webhook')
        with pytest.raises(ProcessMessageEventHandlerConfigError):
            find_and_execute(event_handler_item.processor,
                             event_handler_item, message)

    def test_no_response(self, event_handler_item, message):
        # Given url should not reply
        event_handler_item.modify(context={'url': 'http://127.0.0.1:6666'},
                                  processor='webhook')
        with pytest.raises(ProcessMessageNoResponseError):
            find_and_execute(event_handler_item.processor,
                             event_handler_item, message)

    def test_bad_response(self, event_handler_item, message):
        # Given url should returns a 404
        event_handler_item.modify(
            context={'url': 'http://google.com/should_trigger_404'},
            processor='webhook')
        with pytest.raises(ProcessMessageBadResponseError):
            find_and_execute(event_handler_item.processor,
                             event_handler_item, message)

    def test_request(self, event_handler_item, message):
        # Given url should returns a 200
        event_handler_item.modify(context={'url': 'http://www.example.com',
                                           'headers': {'key': 'value'}},
                                  processor='webhook')
        message.modify(json_context='{"key": "value"}', origin='my-origin')

        # Monkey patch requests lib with a mock
        origin_r = requests.request

        def mock_request(method, url, data=None, headers=None, **kwargs):
            assert method == 'POST'
            assert url == 'http://www.example.com'
            assert headers == {'key': 'value', 'Content-Type': 'application/json; charset=UTF-8'}
            assert type(data) == bytes
            data = json.loads(data.decode('utf-8'))
            assert parse(data['timestamp'])
            assert data['context'] == {'key': 'value'}
            assert data['event'] == event_handler_item.event
            assert data['origin'] == 'my-origin'
            return Response(lambda: True, 200, 'Ok', 'Text for Ok')

        requests.request = mock_request
        ret = find_and_execute(event_handler_item.processor, event_handler_item, message)
        assert ret == 'Serveur http://www.example.com answered:\n200 Ok\nText for Ok'
        requests.request = origin_r

    def test_proxies(self, event_handler_item, message):
        proxies = {'http': 'http://prox.y', 'https': 'https://prox.y'}
        # Given url should returns a 200
        event_handler_item.modify(context={'url': 'http://www.example.com',
                                           'headers': {'key': 'value'},
                                           'proxies': proxies},
                                  processor='webhook')
        # Monkey patch requests lib with a mock
        origin_r = requests.request

        def mock_request(method, url, proxies=None, **kwargs):
            assert proxies == proxies
            return Response(lambda: True, 200, 'Ok', 'Text for Ok')

        requests.request = mock_request
        ret = find_and_execute(event_handler_item.processor,
                               event_handler_item, message)
        requests.request = origin_r

    def test_bad_single_proxy(self, event_handler_item, message):
        single_proxy = 'http://prox.y'
        # Given url should returns a 200
        event_handler_item.modify(context={'url': 'http://www.example.com',
                                           'headers': {'key': 'value'},
                                           'proxies': single_proxy},
                                  processor='webhook')
        # Monkey patch requests lib with a mock
        origin_r = requests.request

        def mock_request(method, url, proxies=None, **kwargs):
            assert proxies != {'http': single_proxy, 'https': single_proxy}
            return Response(lambda: True, 200, 'Ok', 'Text for Ok')

        requests.request = mock_request
        ret = find_and_execute(event_handler_item.processor,
                               event_handler_item, message)
        requests.request = origin_r

    def test_timeout(self, event_handler_item, message):
        # Given url should returns a 200
        event_handler_item.modify(context={'url': 'http://www.example.com',
                                           'headers': {'key': 'value'},
                                           'timeout': 42},
                                  processor='webhook')
        # Monkey patch requests lib with a mock
        origin_r = requests.request

        def mock_request(method, url, timeout=None, **kwargs):
            assert timeout == 42
            raise requests.Timeout('Fake timeout')

        requests.request = mock_request
        with pytest.raises(ProcessMessageNoResponseError):
            ret = find_and_execute(event_handler_item.processor,
                                   event_handler_item, message)
        requests.request = origin_r


class TestWatcher(common.BaseLegacyBrokerTest):

    def test_watch(self, event_handler_item, broker, message, message_dump):
        count = 0

        def alert(ret=False):
            nonlocal count
            count += 1
            assert count == 1

        event_handler_item.modify(context={'url': 'http://www.example.com',
                                           'headers': {'key': 'value'}},
                                  processor='webhook', )

        @register_processor
        def good_processor(handler, msg):
            return 'ok'

        broker.send(message_dump)
        total_done_skipped, total_message = broker_watch_get_state_message()
        total_done_skipped, total_message = broker_check_state_message(
            total_done_skipped, total_message, alert)
        assert count == 0
        msg = Message.objects.first()
        handler = broker.event_handler.get(msg.handler)
        assert handler == event_handler_item
        assert msg.status == 'READY'
        broker.event_handler.execute_legacy(msg)
        total_done_skipped, total_message = broker_check_state_message(
            total_done_skipped, total_message, alert)
        assert count == 0
        msg.reload()
        assert msg.status == 'DONE'
        assert msg.processed
        assert msg.processed > msg.created
        handler = broker.event_handler.get(msg.handler)
        broker.send(message_dump)
        total_done_skipped, total_message = broker_check_state_message(
            total_done_skipped, total_message, alert)
        assert count == 1
