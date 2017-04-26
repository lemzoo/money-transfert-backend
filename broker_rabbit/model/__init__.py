from functools import namedtuple

from broker_rabbit.model.message import Message, MessageSchema

BindedModel = namedtuple('BindedModel', ('Message'))


def bind_model(alias):
    """
    Default model is provided unbinded (i.e. Document's meta.db_alias is None),
    then this function provide a subclass of the original model binded
    to the given mongoengine alias

    :param alias: mongoengine alias to the db
    """
    Message._meta['db_alias'] = alias
    Message._collection = None
    return BindedModel(Message)


__all__ = ('bind_model', 'MessageSchema', 'Message',)
