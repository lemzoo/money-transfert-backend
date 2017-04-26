import pytest

from tests import common
from tests.broker_dispatcher.fixtures import client
from tests.broker.fixtures import *


class TestQueue(common.BaseLegacyBrokerTest):

    def test_get_list(self, client, worker):
        worker.start()
        r = client.get('/broker/queues')
        assert r.status_code == 200, r
        assert len(r.data['_items']) == 1
        assert sorted(r.data['_links'].keys()) == sorted(['self'])

    def test_get_single(self, client, worker):
        worker.start()
        route = '/broker/queues/%s' % worker.queue
        r = client.get(route)
        assert r.status_code == 200, r
        assert sorted(r.data['_links'].keys()) == \
            sorted(['self', 'messages', 'parent', 'pause'])

    def test_pause(self, client, worker):
        worker.start()
        route = '/broker/queues/%s/pause' % worker.queue
        r = client.post(route)
        assert r.status_code == 200, r
        worker.manifest.reload()
        assert worker.manifest.status == 'PAUSED'
        # Cannot pause two time
        r = client.post(route)
        assert r.status_code == 400

    def test_resume(self, client, worker):
        worker.start()
        worker.manifest.modify(status='PAUSED')
        route = '/broker/queues/%s/resume' % worker.queue
        r = client.post(route)
        assert r.status_code == 200, r
        worker.manifest.reload()
        assert worker.manifest.status == 'RUNNING'
        # Same test in failure
        worker.manifest.modify(status='FAILURE')
        r = client.post(route)
        assert r.status_code == 200, r
        worker.manifest.reload()
        assert worker.manifest.status == 'RUNNING'
        # Cannot resume two time
        r = client.post(route)
        assert r.status_code == 400
