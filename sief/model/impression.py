from mongoengine.fields import IntField, DateTimeField
from core.model_util import BaseController, ControlledDocument
from core.model_util.version import VersionedDocument
from datetime import datetime


class ImpressionDocumentController(BaseController):

    def get_printing_id(self, save=False):
        if datetime.utcnow().date() > self.document.date_derniere_demande.date():
            self.document.compteur_journalier = 1
        else:
            self.document.compteur_journalier += 1
        self.document.date_derniere_demande = datetime.utcnow()
        if save:
            self.document.save()
        return self.document.id


class ImpressionDocument(VersionedDocument, ControlledDocument):
    meta = {'controller_cls': ImpressionDocumentController}

    compteur_journalier = IntField(required=True, default=0)
    date_derniere_demande = DateTimeField(default=datetime.utcnow)
