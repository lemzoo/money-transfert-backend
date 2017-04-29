from tests import common
from tests.broker_dispatcher.fixtures import client
from tests.broker.fixtures import *


class TestMessage(common.BaseLegacyBrokerTest):

    def test_get_messages(self, client, worker, message):
        route = '/broker/queues/%s/messages' % worker.queue
        worker.start()
        r = client.get(route)
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 1
        assert r.data['_items'][0]['id'] == str(message.id)
        assert sorted(r.data['_links'].keys()) == \
            sorted(['self', 'parent'])
        #  Check extended_route informations into _links.self
        assert r.data['_links']['self'] == route + "?per_page=20&page=1&status=READY&status=FAILURE"
        # Get a single message
        r = client.get(r.data['_items'][0]['_links']['self'])
        assert r.status_code == 200
        assert sorted(r.data['_links'].keys()) == \
            sorted(['self', 'parent', 'delete'])

    def test_delete_message(self, client, worker, message):
        route = '/broker/queues/%s/messages/%s' % (message.queue, message.id)
        r = client.get(route)
        assert r.status_code == 200
        worker.start()
        # Cannot remove a message when the worker is running
        r = client.delete(route)
        assert r.status_code == 400
        worker.stopping()
        r = client.delete(route)
        assert r.status_code == 400
        worker.stopped()
        r = client.delete(route)
        assert r.status_code == 204
        r = client.get(route)
        assert r.status_code == 200
        assert r.data['status'] == 'DELETED'

    def test_default_message(self, broker, event_handler_item):
        msg_cls = broker.model.Message
        msg = msg_cls(queue='test-queue', handler=event_handler_item.label).save()

        assert msg.context == {}
        assert not msg.status_comment
        assert msg.created
        assert not msg.processed
        assert not msg.origin
        handler = broker.event_handler.get(msg.handler)
        assert handler == event_handler_item
