# Republishing the default fields...
from mongoengine.fields import *  # noqa

from bson import DBRef
from mongoengine import DoesNotExist


class ReferenceField(ReferenceField):
    """
    Overload original ReferenceField to make it throw an exception
    when dereferencing an unknown document.
    """

    def __get__(self, instance, owner):
        value = super().__get__(instance, owner)
        if isinstance(value, DBRef):
            raise DoesNotExist(
                'Trying to dereference unknown document %s' % value)
        return value
