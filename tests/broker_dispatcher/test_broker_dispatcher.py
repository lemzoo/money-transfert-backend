import pytest

from broker_dispatcher import UnknownEventError

from tests import common
from tests.broker_dispatcher.fixtures import *


class TestBrokerDispatcherDispatchMessage:

    def test_message_is_never_sent_on_broker_rabbit_when_ff_is_off(
        self, broker_dispatcher_mocked, event_handler_item):
        # Given
        context = '{"field": "value"}'
        origin = 'my-origin'
        event_handler_item.modify(to_rabbit=True)
        broker_dispatcher_mocked.ff_enable_rabbit = False
        # When
        broker_dispatcher_mocked.dispatch_message(origin, event_handler_item, context)
        # Then
        assert broker_dispatcher_mocked.broker_legacy.send.called
        assert not broker_dispatcher_mocked.broker_rabbit.send.called

    def test_message_is_not_sent_on_broker_rabbit(self, broker_dispatcher_mocked, event_handler_item):
        # Given
        context = '{"field": "value"}'
        origin = 'my-origin'
        # When
        broker_dispatcher_mocked.dispatch_message(origin, event_handler_item, context)
        # Then
        assert broker_dispatcher_mocked.broker_legacy.send.called
        assert not broker_dispatcher_mocked.broker_rabbit.send.called

    def test_message_is_sent_on_broker_rabbit(self, broker_dispatcher_mocked, event_handler_item):
        # Given
        context = '{"field": "value"}'
        origin = 'my-origin'
        event_handler_item.modify(to_rabbit=True)
        broker_dispatcher_mocked.ff_enable_rabbit = True
        # When
        broker_dispatcher_mocked.dispatch_message(origin, event_handler_item, context)
        # Then
        assert not broker_dispatcher_mocked.broker_legacy.send.called
        assert broker_dispatcher_mocked.broker_rabbit.send.called


class TestBrokerDispatcherSend(common.BaseLegacyBrokerTest):

    def test_send_bad_event(self, broker_dispatcher):
        with pytest.raises(UnknownEventError):
            broker_dispatcher.send('event-bad')

    def test_send_event(self, broker_dispatcher, event_handler, event_handler_item):
        # Sent an event no one is interested into
        broker_legacy = broker_dispatcher.broker_legacy
        Message = broker_legacy.model.Message
        Message.drop_collection()
        broker_dispatcher.send(DEFAULT_EVENTS[-1])
        assert Message.objects.count() == 0
        # Now an interesting event
        context = {"field": "value"}
        broker_dispatcher.send(event_handler_item.event,
                               origin='another-origin',
                               context=context)
        msgs = Message.objects()
        assert msgs.count() == 1
        msg = msgs[0]
        handler = broker_dispatcher.event_handler.get(msg.handler)
        assert handler == event_handler_item
        assert msg.queue == event_handler_item.queue
        assert msg.status == 'READY'
        assert msg.context == context
        assert msg.created
        assert msg.origin == 'another-origin'
