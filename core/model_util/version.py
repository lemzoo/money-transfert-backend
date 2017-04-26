from datetime import datetime
from flask.ext.mongoengine import mongoengine, Document
from mongoengine import signals
from mongoengine.errors import OperationError
from mongoengine.common import _import_class
import pymongo

from core.concurrency import ConcurrencyError
from core.auth import current_user


def _get_current_user():
    try:
        return current_user.id
    except (RuntimeError, AttributeError):
        # If working outside flask context (i.g. init test for exemple)
        # there is no current user
        return None


class VersionedDocument(Document):

    """
    Mongoengine abstract document handling version, udpated and created fields
    as long as concurrent modifications handling
    """
    doc_version = mongoengine.IntField(required=True, default=1)
    doc_updated = mongoengine.DateTimeField(default=datetime.utcnow)
    doc_created = mongoengine.DateTimeField(default=datetime.utcnow)
    meta = {'abstract': True, '_version_bootstrapped': False, 'unversionned_fields': ()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bootstrap_version()

    @staticmethod
    def _version_pre_save(sender, document, **kwargs):
        """
        Update version and modified date on document change
        """
        if document.pk and document._need_versionning():
            document.doc_updated = datetime.utcnow()
            document.doc_version += 1

    @classmethod
    def _bootstrap_version(cls):
        if not cls._meta['_version_bootstrapped']:
            cls._meta['_version_bootstrapped'] = True
            # Signal to update metadata on document change
            mongoengine.signals.pre_save.connect(cls._version_pre_save, sender=cls)
            # User can provide fields that should not be versionned
            ufields = set(cls._meta['unversionned_fields'])
            if ufields:
                # Sanity check for currently unsupported feature
                assert not any(f for f in ufields if '.' in f), 'Cannot unversion nested field'
                cls._need_versionning = lambda s: bool(set(s._get_changed_fields()) - ufields)
            else:
                cls._need_versionning = lambda s: True

    def save(self, *args, **kwargs):
        # Check for race condition on insert
        if self.pk:
            if 'save_condition' not in kwargs:
                kwargs['save_condition'] = {}
            if 'doc_version' not in kwargs['save_condition']:
                kwargs['save_condition']['doc_version'] = self.doc_version
        try:
            return super().save(*args, **kwargs)
        except mongoengine.errors.SaveConditionError:
            raise ConcurrencyError()

    def delete(self, **write_concern):
        # mongoengine.Document.delete doesn't have `save_condition` parameter,
        # need to do it ourself by reimplementing `delete` method
        signals.pre_delete.send(self.__class__, document=self)

        # Delete FileFields separately
        FileField = _import_class('FileField')
        for name, field in self._fields.items():
            if isinstance(field, FileField):
                getattr(self, name).delete()

        try:
            deleted_count = self._qs.filter(doc_version=self.doc_version, **self._object_key).\
                delete(write_concern=write_concern, _from_doc_delete=True)
            if deleted_count != 1:
                raise ConcurrencyError()
        except pymongo.errors.OperationFailure as err:
            message = 'Could not delete document (%s)' % err.message
            raise OperationError(message)
        signals.post_delete.send(self.__class__, document=self)


class HistorizedDocument(VersionedDocument):

    """
    Mongoengine abstract document handling history and race condition
    """
    meta = {'abstract': True, 'history_cls': None, }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.history_cls = self._bootstrap_history_cls()
        # Shorthand to get the history of the current document
        self.get_history = lambda *args, **kwargs: \
            self.history_cls.objects(*args, origin=self, **kwargs).order_by('version')

    @classmethod
    def get_collection_history(cls):
        """Return history class for the document's collection"""
        return cls._bootstrap_history_cls()

    @staticmethod
    def _history_post_delete(sender, document):
        """Create HistoryItem on delete"""
        if not document._need_versionning():
            return

        version = document.doc_version + 1
        history_cls = sender._meta['history_cls']
        item = history_cls(origin=document, author=_get_current_user(),
                           action='DELETE', version=version,
                           date=datetime.utcnow())
        item.save()

    @staticmethod
    def _history_post_save(sender, document, created):
        """Create HistoryItem document modification"""
        if not created and not document._need_versionning():
            return

        history_cls = sender._meta['history_cls']
        item = history_cls(origin=document,
                           author=_get_current_user(),
                           action='CREATE' if created else 'UPDATE',
                           # content=document.to_mongo().to_dict(),
                           content=document.to_json(),
                           version=document.doc_version,
                           date=document.doc_updated)
        item.save()

    @classmethod
    def _bootstrap_history_cls(cls):
        if cls._meta['history_cls']:
            return cls._meta['history_cls']
        collection = cls._meta['collection'] + '.history'
        assert collection != '.history', cls

        # Create history class with a dynamic name
        HistoryItem = type(cls.__name__ + 'History', (Document, ), {
            'meta': {'collection': collection,
                     'indexes': ['origin', 'date', ('origin', 'date')], },
            'origin': mongoengine.ReferenceField(cls, required=True),
            'author': mongoengine.ReferenceField('Utilisateur'),
            # 'content': mongoengine.DictField(),
            'content': mongoengine.StringField(),
            'action': mongoengine.StringField(
                choices=['CREATE', 'UPDATE', 'DELETE'], required=True),
            'version': mongoengine.IntField(required=True),
            'date': mongoengine.DateTimeField(required=True),
        })

        cls._meta['history_cls'] = HistoryItem
        # Register signals to trigger history creation
        mongoengine.signals.post_save.connect(cls._history_post_save, sender=cls)
        mongoengine.signals.post_delete.connect(cls._history_post_delete, sender=cls)
        return cls._meta['history_cls']
