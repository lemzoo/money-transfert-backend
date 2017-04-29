from datetime import datetime
from mongoengine import fields

from core.model_util import (Marshallable, LinkedDocument,
                             ControlledDocument, BaseController)

from broker.exceptions import QueueManifestError


QUEUE_STATUS = ('RUNNING', 'FAILURE', 'STOPPED', 'STOPPING', 'PAUSED',)


class QueueManifestController(BaseController):

    def start(self, worker_id, reason=None):
        doc = self.document
        if doc.status != 'STOPPED':
            last_heartbeat = (datetime.utcnow() - doc.heartbeat).total_seconds()
            raise QueueManifestError(
                "Worker %s (status: %s, last heartbeat: %.fs ago) is already "
                "assigned to this queue" % (doc.connected_worker, doc.status, last_heartbeat))
        reason = reason or 'Worker %s connected' % worker_id
        self.document.modify(status='RUNNING', connected_worker=worker_id,
                             comment=reason, heartbeat=datetime.utcnow())

    def pause(self, reason=None):
        if self.document.status not in ['RUNNING', 'FAILURE']:
            raise QueueManifestError('Queue must be RUNNING or FAILURE to be paused')
        self.document.modify(status='PAUSED', comment=reason,
                             heartbeat=datetime.utcnow())

    def resume(self, reason=None):
        if not self.document.connected_worker:
            raise QueueManifestError('No worker connected')
        if self.document.status not in ['PAUSED', 'FAILURE']:
            raise QueueManifestError('Queue must be PAUSED  or FAILURE to be resumed')
        self.document.modify(status='RUNNING', comment=reason,
                             heartbeat=datetime.utcnow())

    def stopping(self, reason=None):
        if self.document.status == 'STOPPED':
            raise QueueManifestError('Queue already stopped')
        self.document.modify(status='STOPPING', comment=reason,
                             heartbeat=datetime.utcnow())

    def stopped(self, reason=None, force=False):
        if not force and self.document.status != 'STOPPING':
            raise QueueManifestError('Queue must be STOPPING to be stopped')
        self.document.modify(status='STOPPED', connected_worker=None,
                             comment=reason, heartbeat=datetime.utcnow())

    def failure(self, reason=None):
        self.document.modify(status='FAILURE', comment=reason,
                             heartbeat=datetime.utcnow())

    def info(self, reason):
        self.document.modify(comment=reason, heartbeat=datetime.utcnow())

    def heartbeat(self):
        self.document.modify(heartbeat=datetime.utcnow())


class QueueManifest(Marshallable, LinkedDocument, ControlledDocument):

    """
    Represent a Queue in database to handle concurrency and monitoring
    """

    meta = {'db_alias': None, 'controller_cls': QueueManifestController,
            'indexes': ['status', 'queue']}

    queue = fields.StringField(primary_key=True)
    status = fields.StringField(required=True, choices=QUEUE_STATUS, default='STOPPED')
    connected_worker = fields.StringField(null=True)
    heartbeat = fields.DateTimeField(required=True, default=datetime.utcnow)
    comment = fields.StringField(null=True)
    timer = fields.IntField(required=True, default=60)
