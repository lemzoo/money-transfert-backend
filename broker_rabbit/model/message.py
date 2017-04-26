import json
from marshmallow_mongoengine import ModelSchema

from core.model_util import BaseDocument, fields


MESSAGE_STATUS = ('FIRST_TRY', 'FAILURE', 'RETRY', 'CANCELLED',
                  'NEED_WAIT', 'SKIPPED', 'DONE', 'DELETED')


class BadMessageFormat(Exception):
    pass


class Message(BaseDocument):

    """
    Represent a single message assigned to a queue for Rabbit
    """

    meta = {'db_alias': None,
            'indexes': ['queue', '-created', 'status', 'discriminant',
                        [('queue', 1), ('status', 1), ('created', 1), ('discriminant', 1)]]}

    created = fields.DateTimeField(required=True)
    queue = fields.StringField(required=True)
    origin = fields.StringField(required=True)
    handler = fields.StringField(required=True)
    discriminant = fields.StringField(required=True)
    json_context = fields.StringField(default='{}')
    status = fields.StringField(choices=MESSAGE_STATUS, default='FIRST_TRY')
    status_comment = fields.StringField(null=True)

    def is_folder_on_error(self):
        param = {
            'discriminant': self.discriminant,
            'status__in': ('RETRY', 'FAILURE')
        }
        if self.pk:
            param.update({'pk__ne': self.pk})
        has_previous_msg_to_process = Message.objects(**param).count() > 0
        return has_previous_msg_to_process

    @property
    def context(self):
        if self.json_context:
            return json.loads(self.json_context)

    def insert_or_update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.save()

    @staticmethod
    def load(raw_data):
        try:
            data = json.loads(raw_data)
        except (ValueError, TypeError) as e:
            raise BadMessageFormat('Error Bad JSON Format of message: %s' % e)
        if 'id' in data:
            msg = Message.objects(id=data['id']).first()
            if not msg:
                raise BadMessageFormat('Message not found in collection, id : %s' % data['id'])
            return msg
        else:
            msg, errors = MessageSchema().load(data)
            if errors:
                raise BadMessageFormat('Bad Message format: %s' % errors)
            return msg


class MessageSchema(ModelSchema):

    class Meta:
        model = Message
