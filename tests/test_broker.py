import pytest
from copy import copy

from broker_dispatcher.event_handler import EventHandlerItem

from sief.permissions import POLICIES as p
from sief.events import EVENTS as e

from tests import common
from tests.fixtures import *
from tests.broker.fixtures import *


@pytest.fixture
def sief_queue(broker, queue_name='test-queue'):
    return queue(broker=broker, queue_name=queue_name)


@pytest.fixture
def sief_event_handler_item(broker, default_handler):
    default_handler_copy = copy(default_handler)
    default_handler_copy['event'] = e.usager.modifie.name
    event_h = event_handler(broker=broker, default_handler=default_handler_copy)
    # return the first event_handler_item
    eh_item = event_h.items[0]
    return eh_item


@pytest.fixture
def sief_message(broker, sief_event_handler_item):
    return message(broker=broker, event_handler_item=sief_event_handler_item)


class TestBrokerAPI(common.BaseLegacyBrokerTest):

    def test_permissions(self, user, sief_queue, sief_message):
        user_req = self.make_auth_request(user, user._raw_password)
        # Need permissions to do that
        queue_route = '/broker/queues/%s' % sief_message.queue
        to_test_routes = ('/broker/queues',
                          queue_route,
                          queue_route + '/messages',
                          queue_route + '/messages/%s' % sief_message.id)
        for route in to_test_routes:
            r = user_req.get(route)
            assert r.status_code == 403, route
        # Provide permissions
        user.permissions = [p.broker.gerer.name]
        user.save()
        for route in to_test_routes:
            r = user_req.get(route)
            assert r.status_code == 200, r

    def test_message_content(self):
        event = e.usager.modifie
        event_handler = self.app.extensions['broker_dispatcher'].event_handler
        event_handler.flush()
        no_trigger_eh = EventHandlerItem({
            'label': 'no-trigger-event-handler',
            'queue': 'my-queue',
            'event': event.name,
            'origin': 'my-origin'
        })
        event_handler.append(no_trigger_eh)
        to_trigger_eh = EventHandlerItem({
            'label': 'to-trigger-event-handler',
            'queue': 'my-queue',
            'event': event.name,
            'origin': 'other-origin'
        })
        event_handler.append(to_trigger_eh)
        event.send(origin='my-origin', field='value')
        msgs = self.app.extensions['broker'].model.Message.objects()
        assert msgs.count() == 1
        msg = msgs[0]
        check_handler = event_handler[msg.handler]
        assert check_handler.event == event.name
        assert check_handler == to_trigger_eh
        assert msg.origin == 'my-origin'
        assert msg.context == {'field': 'value'}

    def test_create_message(self, user, usager, sief_queue, sief_event_handler_item):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.modifier.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()
        sief_event_handler_item.event = e.usager.modifie.name
        event_handler = self.app.extensions['broker_dispatcher'].event_handler
        print(event_handler.items)
        event_handler.flush()
        event_handler.append(sief_event_handler_item)
        r = user_req.patch('/usagers/%s' % usager.id, data={'email': 'new@email.com'})
        assert r.status_code == 200, r

        msgs = self.app.extensions['broker'].model.Message.objects(queue=sief_queue.queue)
        assert len(msgs) == 1
        msg = msgs[0]
        assert msg.origin == str(user.id)
        assert event_handler[msg.handler] == sief_event_handler_item
