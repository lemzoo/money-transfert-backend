from uuid import uuid4
from mongoengine import EmbeddedDocument, ValidationError
from enum import Enum

from core.model_util import BaseController, BaseSolrSearcher, BaseDocument
from sief.model import fields, Usager


TYPE_DOCUMENT = ['ATTESTATION_DEMANDE_ASILE', 'CARTE_SEJOUR_TEMPORAIRE',
                 'DOCUMENT_CIRCULATION_MINEUR', 'CARTE_RESIDENT']

SOUS_TYPE_DOCUMENT = ['PREMIERE_DELIVRANCE', 'PREMIER_RENOUVELLEMENT',
                      'EN_RENOUVELLEMENT']


class DroitSearcher(BaseSolrSearcher):
    FIELDS = ('usager', 'demande_origine', 'type_origine', 'type_document',
              'sous_type_document', 'date_debut_validite', 'date_fin_validite',
              'autorisation_travail', 'pourcentage_duree_travail_autorise',
              'agent_createur', 'date_retrait_attestation',
              'date_notification_retrait_attestation', 'motif_retrait_attestation',
              'prefecture_rattachee', 'date_decision_sur_attestation')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def support_map_factory(fn, need_reduce=False):
            def support_map(doc):
                items = [fn(s) for s in doc.supports]
                # Reduce items if there are lists
                if items and isinstance(items[0], (list, tuple)):
                    items = [e for l in items for e in l]
                return items
            return support_map

        self.build_and_register_converter(
            'supports_agent_editeur', Support.agent_editeur,
            aliases=('support_agent_editeur',), multi=True,
            extractor=support_map_factory(lambda u: u.agent_editeur))
        self.build_and_register_converter(
            'supports_date_delivrance', Support.date_delivrance,
            aliases=('support_date_delivrance',), multi=True,
            extractor=support_map_factory(lambda u: u.date_delivrance))
        self.build_and_register_converter(
            'supports_lieu_delivrance', Support.lieu_delivrance,
            aliases=('support_lieu_delivrance',), multi=True,
            extractor=support_map_factory(lambda u: u.lieu_delivrance))
        self.build_and_register_converter(
            'supports_numero_serie', Support.numero_serie,
            aliases=('support_numero_serie',), multi=True,
            extractor=support_map_factory(lambda u: u.numero_serie))
        self.build_and_register_converter(
            'supports_numero_duplicata', Support.numero_duplicata,
            aliases=('support_numero_duplicata',), multi=True,
            extractor=support_map_factory(lambda u: u.numero_duplicata))
        self.build_and_register_converter(
            'supports_motif_annulation', Support.motif_annulation,
            aliases=('support_motif_annulation',), multi=True,
            extractor=support_map_factory(lambda u: u.motif_annulation))

        self.build_and_register_converter('usager_nom', Usager.nom,
                                          extractor=lambda doc: doc.usager.nom)
        self.build_and_register_converter('usager_prenoms', Usager.prenoms,
                                          extractor=lambda doc: doc.usager.prenoms,
                                          aliases=('usager_prenom',))


class DroitController(BaseController):

    def clean(self):
        # TODO: mongoengine bug, remove this dirty fix...
        doc = self.document
        _ = doc.demande_origine  # noqa
        if not doc.prefecture_rattachee:
            doc.prefecture_rattachee = doc.usager.prefecture_rattachee

        # Add constraints to "Droit"s that don't hold a "taxe" (e.g. Droit d'asile).
        # These constraints may be refactor out of the controller by creating a specific model.
        # We are not yet sure how to do that. It is acknowledged as technical debt.
        if not doc.taxe:
            self.validate_droit_asile(doc)

    def validate_droit_asile(self, document):
        if not document.date_debut_validite:
            raise ValidationError(errors={'date_debut_validite': 'Ce champ est obligatoire'})
        if not document.date_fin_validite:
            raise ValidationError(errors={'date_fin_validite': 'Ce champ est obligatoire'})
        if not document.type_document:
            raise ValidationError(errors={'type_document': 'Ce champ est obligatoire'})
        if not document.sous_type_document:
            raise ValidationError(errors={'sous_type_document': 'Ce champ est obligatoire'})

    def creer_support(self, **kwargs):
        if 'numero_serie' not in kwargs:
            kwargs['numero_serie'] = uuid4().hex
        support = Support(**kwargs)
        support.numero_duplicata = str(len(self.document.supports))
        self.document.supports.append(support)
        return support


class Support(EmbeddedDocument):
    agent_editeur = fields.ReferenceField('Utilisateur', required=True)
    date_delivrance = fields.DateTimeField(required=True)
    lieu_delivrance = fields.ReferenceField('Site', required=True)
    numero_serie = fields.StringField(unique=True, sparse=True, required=True)
    numero_duplicata = fields.IntField(min_value=0, default=0)
    motif_annulation = fields.StringField(choices=['PERTE', 'VOL', 'DEGRADATION'])


NUMERO_TIMBRE_FORMAT = r"^\d{16}$"


class Timbre(EmbeddedDocument):
    numero = fields.StringField(null=False, required=True, regex=NUMERO_TIMBRE_FORMAT)
    numero_reservation = fields.StringField(null=False, required=True)


class StatutPaiements(Enum):
    EFFECTUE = 'EFFECTUE'
    EN_COURS = 'EN_COURS'
    ECHOUE = 'ECHOUE'

STATUT_PAIEMENTS = [status.value for status in StatutPaiements]


class Taxe(EmbeddedDocument):
    statut_paiement = fields.StringField(
        choices=STATUT_PAIEMENTS, null=False, required=True)
    montant = fields.FloatField(null=False, required=True)
    devise = fields.StringField(default='EUR')
    date_paiement_effectue = fields.DateTimeField(null=True)
    timbre = fields.EmbeddedDocumentField(Timbre, required=True)


class Droit(BaseDocument):
    meta = {'controller_cls': DroitController,
            'searcher_cls': DroitSearcher,
            'indexes': ['prefecture_rattachee', 'usager']}

    prefecture_rattachee = fields.ReferenceField('Prefecture')
    usager = fields.ReferenceField('Usager', required=True)
    demande_origine = fields.GenericReferenceField(choices=['DemandeAsile'])
    type_document = fields.StringField(choices=TYPE_DOCUMENT)
    sous_type_document = fields.StringField(choices=SOUS_TYPE_DOCUMENT)
    date_debut_validite = fields.DateTimeField()
    date_fin_validite = fields.DateTimeField()
    autorisation_travail = fields.BooleanField()
    pourcentage_duree_travail_autorise = fields.IntField(max_value=100, min_value=0)
    motif_retrait_autorisation_travail = fields.StringField()
    agent_createur = fields.ReferenceField('Utilisateur', required=True)
    supports = fields.ListField(fields.EmbeddedDocumentField(Support), default=list)
    date_retrait_attestation = fields.DateTimeField()
    date_notification_retrait_attestation = fields.DateTimeField()
    motif_retrait_attestation = fields.StringField()
    date_decision_sur_attestation = fields.DateTimeField()
    taxe = fields.EmbeddedDocumentField(Taxe)
