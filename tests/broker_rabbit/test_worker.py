from connector import register_processor

from tests import common
from tests.broker_dispatcher.fixtures import client
from tests.broker_rabbit.fixtures import *


class TestWorker(common.BaseRabbitBrokerTest):

    def test_message_with_status_done(self, event_handler_item, broker_rabbit,
                                      worker, client, message_dump):
        @register_processor
        def good_processor(handler, message):
            return 'ok'

        event_handler_item.modify(processor='good_processor')

        queue = event_handler_item.queue
        message_dump['queue'] = queue
        message_dump['handler'] = event_handler_item.label

        # Send to rabbitmq server
        broker_rabbit.send(queue, message_dump)

        # Start a worker on the given queue
        worker.queue = queue
        worker.consume_one_message()
        # The message should be saved on mongo
        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 1

        message = ret.data['_items'][0]
        assert message['status'] == 'DONE'
        assert message['status_comment'] == 'ok'

    def test_message_with_status_failure(self, event_handler_item, worker,
                                         broker_rabbit, client, message_dump):

        @register_processor
        def bad_processor(handler, message):
            raise ValueError('expected exception')

        event_handler_item.modify(processor='bad_processor')

        queue = event_handler_item.queue
        message_dump['queue'] = queue
        message_dump['handler'] = event_handler_item.label

        # Send to rabbitmq server
        broker_rabbit.send(queue, message_dump)
        # Start a worker on the given queue
        worker.queue = queue
        worker.consume_one_message()

        # The message should be saved on mongo
        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 1

        message = ret.data['_items'][0]
        assert message['status'] == 'FAILURE'
        assert 'expected exception' in message['status_comment']

    def test_message_fail_to_done(self, event_handler_item, broker_rabbit,
                                  worker, client, message_dump):
        @register_processor
        def bad_processor(handler, message):
            raise ValueError('expected exception')

        @register_processor
        def good_processor(handler, message):
            return 'ok'

        # Register the bad label processor
        event_handler_item.modify(processor='bad_processor')
        queue = event_handler_item.queue
        message_dump['queue'] = queue
        message_dump['handler'] = event_handler_item.label

        # Send to rabbitmq server
        broker_rabbit.send(queue, message_dump)

        # Start a worker on the given queue
        worker.queue = queue
        worker.consume_one_message()

        # The message should be saved on mongo
        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 1

        message = ret.data['_items'][0]
        assert message['status'] == 'FAILURE'

        event_handler_item.modify(processor='good_processor')

        # Update the message
        route = '/rabbit/queues/%s/messages/%s' % (queue, message['id'])
        ret = client.patch(route, data={'status': 'RETRY'})
        assert ret.status_code == 200
        assert ret.data['status'] == 'RETRY'

        worker.consume_one_message()

        ret = client.get(route)
        assert ret.status_code == 200
        assert ret.data['status'] == 'DONE'
        # Consuming existing message should not create duplications
        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 1

    def test_consume_on_empty_queue(self, event_handler_item,
                                    broker_rabbit, worker, message_dump):

        queue = event_handler_item.queue

        # Start a worker on the given queue
        worker.queue = queue
        ret = worker.consume_one_message()
        assert not ret

        message_dump['queue'] = queue
        message_dump['handler'] = event_handler_item.label

        # Send to rabbitmq server
        broker_rabbit.send(queue, message_dump)

        ret = worker.consume_one_message()
        assert ret

        ret = worker.consume_one_message()
        assert not ret


class TestWorkerErrorFolder(common.BaseRabbitBrokerTest):

    def test_messages_fail_and_skip(self, event_handler_item, broker_rabbit,
                                    worker, client, message_dump):
        @register_processor
        def bad_processor(handler, message):
            raise ValueError('expected exception')

        @register_processor
        def good_processor(handler, message):
            return 'ok'

        # Register the bad label processor
        event_handler_item.modify(processor='bad_processor')
        queue = event_handler_item.queue
        message_dump['queue'] = queue
        message_dump['handler'] = event_handler_item.label

        # Send to rabbitmq server
        broker_rabbit.send(queue, message_dump)

        # Start a worker on the given queue
        worker.queue = queue
        worker.consume_one_message()

        # The message should be saved on mongo
        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 1

        message = ret.data['_items'][0]
        assert message['status'] == 'FAILURE'

        event_handler_item.modify(processor='good_processor')

        # Send a second message
        broker_rabbit.send(queue, message_dump)
        worker.consume_one_message()

        # Consuming existing messages
        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 2
        first_message = ret.data['_items'][0]
        second_message = ret.data['_items'][1]

        assert first_message['status'] == 'FAILURE'
        assert second_message['status'] == 'SKIPPED'

    def test_messages_fail_and_done(self, event_handler_item, broker_rabbit,
                                    worker, client, message_dump):
        @register_processor
        def bad_processor(handler, message):
            raise ValueError('expected exception')

        @register_processor
        def good_processor(handler, message):
            return 'ok'

        # Register the bad label processor
        event_handler_item.modify(processor='bad_processor')
        queue = event_handler_item.queue
        message_dump['queue'] = queue
        message_dump['handler'] = event_handler_item.label

        # Send to rabbitmq server
        broker_rabbit.send(queue, message_dump)

        # Start a worker on the given queue
        worker.queue = queue
        worker.consume_one_message()

        # The message should be saved on mongo
        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 1

        message = ret.data['_items'][0]
        assert message['status'] == 'FAILURE'

        event_handler_item.modify(processor='good_processor')

        # Send a second message with another discriminant
        message_dump['discriminant'] = '9876543210'
        broker_rabbit.send(queue, message_dump)
        worker.consume_one_message()

        # Consuming existing messages
        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 2
        first_message = ret.data['_items'][0]
        second_message = ret.data['_items'][1]

        assert first_message['status'] == 'FAILURE'
        assert second_message['status'] == 'DONE'

    def test_messages_done_and_done(self, event_handler_item, broker_rabbit,
                                    worker, client, message_dump):
        @register_processor
        def good_processor(handler, message):
            return 'ok'

        # Register the bad label processor
        event_handler_item.modify(processor='good_processor')
        queue = event_handler_item.queue
        message_dump['queue'] = queue
        message_dump['handler'] = event_handler_item.label

        # Send to rabbitmq server
        broker_rabbit.send(queue, message_dump)

        # Start a worker on the given queue
        worker.queue = queue
        worker.consume_one_message()

        # The message should be saved on mongo
        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 1

        message = ret.data['_items'][0]
        assert message['status'] == 'DONE'

        # Send a second message
        broker_rabbit.send(queue, message_dump)
        # Consuming existing message
        worker.consume_one_message()

        route = '/rabbit/queues/%s/messages' % queue
        ret = client.get(route)
        assert ret.status_code == 200
        assert len(ret.data['_items']) == 2

        first_message = ret.data['_items'][0]
        second_message = ret.data['_items'][1]
        assert first_message['status'] == 'DONE'
        assert second_message['status'] == 'DONE'
