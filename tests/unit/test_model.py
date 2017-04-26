import pytest
from mongoengine import ValidationError as MongoValidationError

from tests import common
from tests.fixtures import *

from core.model_util import (Document, HistorizedDocument, BaseController,
                             ControlledDocument, VersionedDocument, ReadableDocument)
from core.concurrency import ConcurrencyError
from sief.model import fields


class TestRedableDocument(common.BaseTest):
    def test_redable_document(self):
        class Animal(ReadableDocument):
            name = fields.StringField()
            specy = fields.StringField()
            legs_count = fields.IntField()

            def is_duck(self):
                return self.specy == 'duck'

        animal = Animal(name='Daffy', specy='duck', legs_count=2)
        assert 'Animal' in repr(animal)
        assert 'is_duck' not in repr(animal)
        for field in ('name', 'specy', 'legs_count'):
            assert field in repr(animal)


class TestFields(common.BaseTest):
    def test_patronyme_field(self):
        class PatroDoc(Document):
            patro = fields.PatronymeField()
        p = PatroDoc().save()
        try:
            for patro in ['Mickael', "Mickâel", "Mick-ael", "Mick'a'el",
                          'De Mickael']:
                p.patro = patro
                p.save()
        except MongoValidationError:
            assert False, 'Pattern failed "%s"' % patro

    def test_bad_patronyme_field(self):
        class PatroDoc(Document):
            patro = fields.PatronymeField()
        p = PatroDoc().save()
        for bad_patro in ['mickael', ' Mickael', 'Mickael ', 'M1ck4el',
                          '迈克尔', '', "'Mickael", "Mickael'", "-Mick-ael-"]:
            p.patro = bad_patro
            with pytest.raises(MongoValidationError):
                p.save()
                print('Pattern failed "%s"' % bad_patro)


class TestController(common.BaseTest):

    def test_controller(self):
        def controller_factory(document):
            router = {
                'ready': ReadyController,
                'fired': FiredController,
                'reloading': ReloadingController
            }
            return router[document.status](document)
        class ReadyController(BaseController):
            def state(self):
                return "%s is ready to fire" % self.document.name
            def fire(self):
                self.document.status = 'fired'
                self.document.save()
        class FiredController(BaseController):
            def state(self):
                return "%s is empty" % self.document.name
            def reload(self):
                self.document.status = 'reloading'
                self.document.save()
        class ReloadingController(BaseController):
            def state(self):
                return "%s is reloading..." % self.document.name
            def done(self):
                self.document.status = 'ready'
                self.document.save()
        class Gun(ControlledDocument):
            meta = {'controller_cls': controller_factory}
            name = fields.StringField(required=True)
            status = fields.StringField(choices=['ready', 'fired', 'reloading'], required=True)
        doc = Gun(name='gun-1', status='ready')
        doc.save()
        assert isinstance(doc.controller, ReadyController)
        assert hasattr(doc.controller, 'fire')
        assert doc.controller.state() == 'gun-1 is ready to fire'
        doc.controller.fire()
        assert isinstance(doc.controller, FiredController)
        assert doc.controller.state() == 'gun-1 is empty'
        doc.controller.reload()
        assert isinstance(doc.controller, ReloadingController)
        doc.controller.done()

    def test_dualinheritance(self):
        class DualInheritanceController(BaseController):
            def make_v2(self):
                self.document.field = 'v2'
                self.document.save()
        class DualInheritanceDoc(ControlledDocument, HistorizedDocument):
            meta = {'controller_cls': DualInheritanceController}
            field = fields.StringField()
        doc = DualInheritanceDoc(field='v1')
        doc.save()
        # Make sure we have both history and controller functionalities
        assert isinstance(doc.controller, DualInheritanceController)
        doc.controller.make_v2()
        assert hasattr(doc, 'get_history')
        history = doc.get_history()
        assert history.count() == 2


class TestReferentialField(common.BaseTest):
    def test_referential_field(self, ref_nationalites):
        class Doc(Document):
            nationalite = fields.NationaliteField()
        doc = Doc(nationalite={'code': ref_nationalites[0].code})
        doc.save()
        assert doc.nationalite.code == ref_nationalites[0].code
        # Libelle is autofilled
        assert doc.nationalite.libelle == ref_nationalites[0].libelle
        # Changing code changes libelle as well
        doc.nationalite.code = ref_nationalites[1].code
        doc.save()
        assert doc.nationalite.code == ref_nationalites[1].code
        assert doc.nationalite.libelle == ref_nationalites[1].libelle
        # Code is check
        doc.nationalite.code = 'bad_code'
        with pytest.raises(MongoValidationError):
            doc.save()
        # Test crazy fields
        bad_fields = ({}, {'libelle': 'missing code'})
        for bad_field in bad_fields:
            doc.nationalite = bad_field
            with pytest.raises(MongoValidationError):
                doc.save()
                print('Error with bad_field `%s`' % bad_field)
        for bad_field in bad_fields:
            doc = Doc(nationalite=bad_field)
            with pytest.raises(MongoValidationError):
                doc.save()
                print('Error with bad_field `%s`' % bad_field)


class TestConcurrency(common.BaseTest):
    def test_concurrency_save(self):
        class Doc(VersionedDocument):
            field = fields.StringField()
        doc = Doc(field="v1")
        doc.save()
        assert doc.doc_version == 1
        doc_concurrent = Doc.objects(field="v1").first()
        assert doc_concurrent
        doc.field = "v2"
        doc_concurrent.field = "v2_alternate"
        doc_concurrent.save()
        assert doc_concurrent.doc_version == 2
        with pytest.raises(ConcurrencyError):
            doc.save()
        doc.reload()
        assert doc.field == doc_concurrent.field
        assert doc.doc_version == 2

    def test_concurrency_delete(self):
        class Doc(VersionedDocument):
            field = fields.StringField()
        doc = Doc(field="v1")
        doc.save()
        assert doc.doc_version == 1
        doc_concurrent = Doc.objects(field="v1").first()
        assert doc_concurrent
        doc_concurrent.field = "v2"
        doc_concurrent.save()
        assert doc_concurrent.doc_version == 2
        with pytest.raises(ConcurrencyError):
            doc.delete()
        doc.reload()
        doc.delete()
        # Already deleted
        with pytest.raises(ConcurrencyError):
            doc.delete()
        # Cannot update a deleted document
        doc_concurrent.field = "v3"
        with pytest.raises(ConcurrencyError):
            doc_concurrent.save()
