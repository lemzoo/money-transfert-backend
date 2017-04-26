from functools import namedtuple

from broker.model.message import Message
from broker.model.queue import QueueManifest


BindedModel = namedtuple('BindedModel', ('QueueManifest', 'Message'))


def bind_model(alias):
    """
    Default model is provided unbinded (i.e. Document's meta.db_alias is None),
    then this function provide a subclass of the original model binded
    to the given mongoengine alias

    :param alias: mongoengine alias to the db
    """
    Message._meta['db_alias'] = alias
    Message._collection = None
    QueueManifest._meta['db_alias'] = alias
    QueueManifest._collection = None
    return BindedModel(QueueManifest, Message)


__all__ = ('bind_model', )
