from datetime import datetime
from freezegun import freeze_time

from tests import common
from tests.broker_rabbit.fixtures import *
from tests.broker_rabbit import rabbit_api


class TestBrokerRabbit(common.BaseRabbitBrokerTest):

    @freeze_time("2017-04-11 15:10:30")
    def test_send_event(self, model_message, broker_rabbit, event_handler_item):
        queue = event_handler_item.queue
        label = event_handler_item.label
        created = datetime.utcnow().isoformat()
        discriminant = '0123456789'
        context = '{"field": "value"}'
        origin = 'my-origin'
        message_dump = {
            'created': created,
            'queue': queue,
            'origin': origin,
            'handler': label,
            'discriminant': discriminant,
            'json_context': context,
            'status': 'FIRST_TRY'
        }
        broker_rabbit.send(queue, message_dump)

        msgs = rabbit_api.get_messages(client_api_rabbit, VHOST_TEST, queue)
        assert msgs[0].get('message_count') == 0
        msg_gotten = msgs[0]['payload']
        msg = model_message.load(msg_gotten)
        assert msg.created.isoformat() == datetime(2017, 4, 11, 15, 10, 30).isoformat()
        assert msg.discriminant == discriminant
        assert msg.origin == origin
        assert msg.queue == queue
        assert msg.json_context == context

    def test_send_multiple_events(self, event_handler_item, broker_rabbit):
        max_sent_msg = 100
        queue = event_handler_item.queue
        for i in range(max_sent_msg):
            value = '%03d' % i
            message_dump = {
                'created': datetime.utcnow().isoformat(),
                'queue': queue,
                'origin': 'my-origin',
                'handler': event_handler_item.label,
                'discriminant': value,
                'json_context': '{"field": "value"}',
                'status': 'FIRST_TRY'
            }
            # Send to rabbitmq server
            broker_rabbit.send(queue, message_dump)
        queue = event_handler_item.queue
        number_msg = rabbit_api.get_number_message_on_queue(client_api_rabbit,
                                                            VHOST_TEST, queue)
        assert number_msg == max_sent_msg
