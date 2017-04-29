from core import CoreResource
from broker.model.queue import QueueManifest
from datetime import datetime, timedelta
from sief.permissions import POLICIES as p


class MonitoringAPI(CoreResource):
    pass


class BrokerCheck(MonitoringAPI):

    @p.monitoring.voir.require(http_exception=403)
    def get(self):
        ret = {}
        ret['globalStatus'] = 'OK'
        ret['details'] = []
        queues_to_check = ['agdref', 'dna', 'inerec', 'analytics']
        delta = {'warning': timedelta(minutes=5),
                 'error': timedelta(minutes=15)
                 }
        db_queues = QueueManifest.objects(
            queue__in=(queues_to_check),
            status__in=('RUNNING', 'FAILURE'))
        if len(db_queues) != len(queues_to_check):
            ret['globalStatus'] = 'ERROR'

        for queue in db_queues:
            local_status = 'OK'
            if queue.status == 'FAILURE':
                local_status = 'ERROR'
                ret['details'].append({'name': "Test broker - %s " % queue.queue,
                                       'label': "Check queue %s" % queue.queue,
                                       'status': 'ERROR',
                                       'reason': 'Queue is in FAILURE state.'
                                       })
            elif abs(datetime.utcnow() - queue.heartbeat) > delta['warning']:
                local_status = 'WARNING'
                if abs(datetime.utcnow() - queue.heartbeat) > delta['error']:
                    local_status = 'ERROR'
                ret['details'].append({'name': "Test broker - %s " % queue.queue,
                                       'label': "Check queue %s" % queue.queue,
                                       'status': local_status,
                                       'reason': 'Queue has not responded for more than %s.' % abs(datetime.utcnow() - queue.heartbeat)
                                       })
            else:
                local_status = 'OK'
                ret['details'].append({'name': "Test broker - %s " % queue.queue,
                                       'label': "Check queue %s" % queue.queue,
                                       'status': local_status,
                                       'reason': 'Queue is running.'
                                       })
            if ret['globalStatus'] != 'ERROR' and local_status != 'OK':
                ret['globalStatus'] = local_status
            queues_to_check.remove(queue.queue)
        for queue in queues_to_check:
            ret['globalStatus'] = 'ERROR'
            ret['details'].append({'name': "Test broker - %s " % queue,
                                   'label': "Check queue %s" % queue,
                                   'status': 'ERROR',
                                   'reason': 'Queue is not running.'
                                   })

        return ret


class APICheck(MonitoringAPI):

    @p.monitoring.voir.require(http_exception=403)
    def get(self):
        from mongoengine.connection import get_connection, ConnectionError
        ret = {}
        ret['details'] = []
        # check access to the DB
        try:
            get_connection()
            ret['globalStatus'] = 'OK'
            ret['details'].append({'name': 'API',
                                   'label': None,
                                   'status': 'OK',
                                   'reason': 'API is running.'
                                   })
        except ConnectionError:
            ret['globalStatus'] = 'ERROR'
            ret['details'].append({'name': 'DB',
                                   'label': None,
                                   'status': 'ERROR',
                                   'reason': 'DB is not connected'
                                   })

        return ret
