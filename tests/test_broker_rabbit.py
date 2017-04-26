import pytest

from broker_dispatcher.event_handler import EventHandlerItem

from sief.permissions import POLICIES as p
from sief.events import EVENTS as e
from sief.events import broker_dispatcher

from tests.broker_rabbit.rabbit_api import get_messages
from tests import common
from tests.fixtures import *
from tests.broker_rabbit.fixtures import *


@pytest.fixture
def sief_event_handler_item(broker_rabbit, default_handler):
    default_handler['event'] = e.usager.modifie.name
    event_h = event_handler(broker_rabbit=broker_rabbit,
                            default_handler=default_handler)
    eh_item = event_h.items[0]
    return eh_item


@pytest.fixture
def sief_message_rabbit(sief_event_handler_item):
    model = broker_dispatcher.broker_rabbit.model.Message
    return message_first_try(model, sief_event_handler_item)


class TestBrokerRabbitAPI(common.BaseRabbitBrokerTest):

    def init_queue_on_rabbit(self, queue):
        # Got the event_handlers
        eh_item = EventHandlerItem({'label': 'usager.modifie',
                                    'queue': queue})
        event_handler = broker_dispatcher.broker_rabbit.event_handler
        event_handler.flush()
        event_handler.append(eh_item)

        broker_rabbit = broker_dispatcher.broker_rabbit
        queues = [queue]
        broker_rabbit.queues = queues
        producer = broker_rabbit._producer_for_rabbit
        producer.init_env_rabbit(queues)

    def test_permissions_rabbit(self, user, sief_message_rabbit):
        user_req = self.make_auth_request(user, user._raw_password)

        queue = sief_message_rabbit.queue
        self.init_queue_on_rabbit(queue)

        # Need permissions to do that
        queue_route = '/rabbit/queues/%s' % queue
        to_test_routes = ('/rabbit/queues',
                          queue_route,
                          queue_route + '/messages',
                          queue_route + '/messages/%s' % sief_message_rabbit.id)

        for route in to_test_routes:
            r = user_req.get(route)
            assert r.status_code == 403, route
        # Provide permissions
        user.permissions = [p.broker.gerer.name]
        user.save()
        for route in to_test_routes:
            r = user_req.get(route)
            assert r.status_code == 200, r

    def test_message_content_rabbit(self, model_message):
        queue = 'my-queue'
        self.init_queue_on_rabbit(queue)
        event = e.usager.modifie
        event_handler = self.app.extensions['broker_dispatcher'].event_handler
        event_handler.flush()
        no_trigger_eh = EventHandlerItem({
            'label': 'no-trigger-event-handler',
            'queue': queue,
            'event': event.name,
            'origin': 'my-origin',
            'to_rabbit': True
        })
        event_handler.append(no_trigger_eh)
        to_trigger_eh = EventHandlerItem({
            'label': 'to-trigger-event-handler',
            'queue': queue,
            'event': event.name,
            'origin': 'other-origin',
            'to_rabbit': True
        })
        event_handler.append(to_trigger_eh)
        event.send(origin='my-origin', field='value')

        msgs = get_messages(client_api_rabbit, VHOST_TEST, queue)
        assert msgs[0].get('message_count') == 0
        msg_gotten = msgs[0]['payload']
        msg = model_message.load(msg_gotten)
        check_handler = event_handler[msg.handler]
        assert check_handler.event == event.name
        assert check_handler == to_trigger_eh
        assert msg.origin == 'my-origin'
        assert msg.context == {
            'field': 'value'
        }

    def test_create_message_rabbit(self, user, usager, model_message,
                                   sief_event_handler_item):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.modifier.name,
                            p.usager.prefecture_rattachee.sans_limite.name]
        user.save()

        self.init_queue_on_rabbit(sief_event_handler_item.queue)

        sief_event_handler_item.event = e.usager.modifie.name
        sief_event_handler_item.to_rabbit = True
        event_handler = self.app.extensions['broker_dispatcher'].event_handler
        print(event_handler.items)
        event_handler.flush()
        event_handler.append(sief_event_handler_item)
        r = user_req.patch('/usagers/%s' % usager.id,
                           data={'email': 'new@email.com'})
        assert r.status_code == 200, r

        msgs = get_messages(client_api_rabbit, VHOST_TEST, sief_event_handler_item.queue)
        assert msgs[0].get('message_count') == 0

        msg_gotten = msgs[0]['payload']
        msg = model_message.load(msg_gotten)
        assert msg.origin == str(user.id)
        check_handler = event_handler[msg.handler]
        assert check_handler.event == sief_event_handler_item.event
        assert check_handler.queue == sief_event_handler_item.queue
        assert check_handler == sief_event_handler_item
