import pytest
from mongoengine import DoesNotExist

from tests import common

from core.model_util import Document
from sief.model import fields


class TestReferenceMiss(common.BaseTest):

    def test_reference_miss(self):
        class ToReferencedDoc(Document):
            pass

        class ReferencerDoc(Document):
            ref = fields.ReferenceField(ToReferencedDoc)

        ref = ToReferencedDoc().save()

        # No ref, just return None
        doc = ReferencerDoc().save()
        assert doc.ref is None

        # Add an existing reference
        doc.ref = ref
        doc.save()
        assert isinstance(doc.ref, ToReferencedDoc)
        assert doc.ref == ref

        # Dereference valid DBRef
        doc = ReferencerDoc.objects(id=doc.id).first()
        assert isinstance(doc.ref, ToReferencedDoc)
        assert doc.ref == ref

        # Destroy the referenced document and try to dereference it
        ref.delete()
        doc = ReferencerDoc.objects(id=doc.id).first()
        with pytest.raises(DoesNotExist) as exc:
            # Dereference non-existing field should trigger exception
            doc.ref
        assert str(exc.value).startswith(
            "Trying to dereference unknown document DBRef('to_referenced_doc', ObjectId(")
