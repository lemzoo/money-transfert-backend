from mongoengine import fields
from datetime import datetime
import json

from core.model_util import Marshallable, LinkedDocument


MESSAGE_STATUS = ('READY', 'FAILURE', 'DONE', 'CANCELLED', 'SKIPPED', 'DELETED')


class Message(Marshallable, LinkedDocument):

    """
    Represent a single message assigned to a queue
    """

    meta = {'db_alias': None,
            'indexes': ['queue', '+created', 'status', [('queue', 1), ('status', 1), ('created', 1)]]}

    queue = fields.StringField(required=True)
    created = fields.DateTimeField(default=datetime.utcnow)
    processed = fields.DateTimeField(null=True)
    status = fields.StringField(choices=MESSAGE_STATUS, default='READY')
    status_comment = fields.StringField(null=True)
    json_context = fields.StringField(default='{}')
    origin = fields.StringField(null=True)
    handler = fields.StringField(required=True)
    next_run = fields.DateTimeField(null=True)

    @property
    def context(self):
        if self.json_context:
            return json.loads(self.json_context)
