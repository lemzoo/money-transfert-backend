from flask import current_app
from datetime import datetime
from mongoengine import ValidationError, EmbeddedDocument

from core.model_util import BaseController, BaseSolrSearcher, BaseDocument
from sief.model import fields
from sief.model.droit import TYPE_DOCUMENT, SOUS_TYPE_DOCUMENT

ALLOWED_STATUS = ("PRETE_EDITION_ATTESTATION",
                  "EN_ATTENTE_INTRODUCTION_OFPRA",
                  "EN_COURS_PROCEDURE_DUBLIN",
                  "EN_COURS_INSTRUCTION_OFPRA",
                  "DECISION_DEFINITIVE",
                  "FIN_PROCEDURE_DUBLIN",
                  "FIN_PROCEDURE",
                  "CLOTURE_OFPRA")


ALLOWED_TYPE = [
    "PREMIERE_DEMANDE_ASILE",
    "REEXAMEN",
    "REOUVERTURE_DOSSIER"
]


MOTIFS_QUALIFICATION_TO_TYPE = {
    'NORMALE': (
        'PNOR',
        'NECD',
        'ND171',
        'ND31'
    ),
    'ACCELEREE': (
        '1C5',
        'REEX',
        'EMPR',
        'FREM',
        'TARD',
        'DILA',
        'MGOP',
        'AECD',
        'AD171',
        'AD31',
    ),
    'DUBLIN': (
        'BDS',
        'FRIF',
        'EAEA',
        'DU172',
        'FAML',
        'DU16',
        'MIE',
    )
}


MOTIFS_QUALIFICATION = (MOTIFS_QUALIFICATION_TO_TYPE['NORMALE'] +
                        MOTIFS_QUALIFICATION_TO_TYPE['ACCELEREE'] +
                        MOTIFS_QUALIFICATION_TO_TYPE['DUBLIN'])

DECISIONS_DEFINITIVES_DESCRIPTIONS = {
    "OFPRA": {
        "CL": "Clôture",
        "CR": "Réfugié statutaire",
        "DC": "Décès",
        "DE": "Désistement",
        "IR": "Irrecevabilité non suivie de recours",
        "RJ": "Rejet de la demande non suivi de recours",
        "TF": "Transf.protect. Etr.vers Frce",
        "DS": "Dessaisissement",
        "PS": "Protection Subsidiaire"
    },
    "CNDA": {
        "IAM": "Irrecevable absence de moyens",
        "IF": "Irrecevable forclusion",
        "ILE": "Irrecevable langue étrangère",
        "IND": "Irrecevable nouvelle demande",
        "INR": "Irrecevable recours non régul.",
        "IR": "Irrecevable",
        "IRR": "Irrecevable recours en révisio",
        "NL": "Non Lieu",
        "NLO": "Non Lieu ordonnance",
        "RJ": "Rejet",
        "NOR": "Rejet par ordonnance",
        "ANP": "Protec. Subsidiaire",
        "AN": "Annulation",
        "ANT": "Annulation d'un refus de transfert",
        "RJO": "Rejet ordonnances nouvelles",
        "DS": "Désistement",
        "DSO": "Désistement ordonnance",
        "RDR": "Exclusion",
        "RIC": "Incompétence",
        "AI": "Autre irrecevabilité",
        "NLE": "Non Lieu en l'état"
    }
}


DECISIONS_DEFINITIVES = {
    # OFPRA
    'CR': 'ACCORD',  # Réfugié statutaire
    'TF': 'ACCORD',  # Transf.protect. Etr.vers Frce
    'PS': 'ACCORD',  # Protection Subsidiaire
    'DC': 'REJET',  # Décès
    'CL': 'REJET',  # Clôture
    'DE': 'REJET',  # Irrecevabilité non suivie de recours
    'DS': 'REJET',  # Rejet de la demande non suivi
    # OFPRA/CNDA
    'IR': 'REJET',  # Irrecevable
    'ANP': 'ACCORD',  # Protec. Subsidiaire
    'AN': 'ACCORD',  # Annulation
    'ANT': 'ACCORD',  # Annulation d'un refus de transfert
    'IAM': 'REJET',  # Irrecevable absence de moyens
    'ILE': 'REJET',  # Irrecevable langue étrangère
    'IND': 'REJET',  # Irrecevable nouvelle demande
    'INR': 'REJET',  # Irrecevable recours non régul.
    'IRR': 'REJET',  # Irrecevable recours en révisio
    'RJ': 'REJET',  # Rejet
    'NOR': 'REJET',  # Rejet par ordonnance
    'RJO': 'REJET',  # Rejet ordonnances nouvelles
    'DSO': 'REJET',  # Désistement ordonnance
    'RIC': 'REJET',  # Incompétence
    'IF': 'REJET',   # Irrecevable forclusion
    'AI': 'REJET',   # Autre irrecevabilité
    'AVI': 'REJET',   # Incompétence
    'RDR': 'REJET',   # Exclusion
    'NL': 'REJET',   # Non lieu (lorsqu'il constate une situation de rejet)
    'NLE': 'REJET',   # Non lieu (lorsqu'il constate une situation de rejet)
    # ERRORS
    'EE': 'ERREUR',  # Erreur d'enregistrement
    'ERR': 'ERREUR',  # Erreur dans la décision
}


class PaysTraverse(EmbeddedDocument):
    pays = fields.PaysField(required=True)
    date_entree = fields.DateTimeField()
    date_entree_approximative = fields.BooleanField()
    date_sortie = fields.DateTimeField()
    date_sortie_approximative = fields.BooleanField()
    moyen_transport = fields.StringField()
    condition_franchissement = fields.StringField()


class DecisionAttestation(EmbeddedDocument):

    def clean(self):
        if not self.delivrance and not self.motif:
            raise ValidationError(errors={'motif':
                                          "Le motif ne peut etre vide en cas de non délivrance de l'attestation"})

    type_document = fields.StringField(choices=TYPE_DOCUMENT, required=True)
    sous_type_document = fields.StringField(choices=SOUS_TYPE_DOCUMENT, required=True)
    delivrance = fields.BooleanField(default=True, required=True)
    motif = fields.StringField()
    date_decision = fields.DateTimeField(required=True)
    agent_createur = fields.ReferenceField('Utilisateur', required=True)


class DemandeAsileController(BaseController):

    def clean(self):
        if self.document.type_demandeur == 'PRINCIPAL':
            if self.document.demande_asile_principale:
                raise ValidationError(errors={
                    'demande_asile_principale':
                        'Seule une demande conjointe peut avoir ce champ'})
        else:  # Conjoint
            if self.document.enfants_presents_au_moment_de_la_demande:
                raise ValidationError(errors={
                    'enfants_presents_au_moment_de_la_demande':
                        'Seule une demande principale peut avoir ce champ'})

    def cloture_ofpra(self):
        if not self.document.clotures_ofpra:
            raise ValidationError(errors={
                "clotures_ofpra": "Champs requis en statut CLOTURE_OFPRA"
            })
        self.document.statut = "CLOTURE_OFPRA"

    def reouverture(self):
        if not self.document.statut == "CLOTURE_OFPRA":
            raise ValidationError(errors={
                "reouverture": "Possible uniquement au statut cloture ofpra."
            })
        self.document.statut = "PRETE_EDITION_ATTESTATION"


class RequalificationError(Exception):
    pass


def _requalifier_procedure(self, type, acteur, date_notification, motif_qualification=None):
    if type not in ('DUBLIN', 'NORMALE', 'ACCELEREE'):
        raise ValueError('Invalid type value')
    if motif_qualification in ('', None) and acteur != 'OFPRA':
        raise RequalificationError(
            "Le motif de qualification est obligatoire pour une requalification effectuée en préfecture.")
    ancienne_procedure = self.document.procedure
    # OFPRA had to change procedure.type
    if acteur == 'OFPRA' and type == ancienne_procedure.type:
        raise RequalificationError("Impossible de requalifier sans changer"
                                   " le type de procédure")
    # Other can change motif or type + motif
    elif motif_qualification == ancienne_procedure.motif_qualification:
        raise RequalificationError("Impossible de requalifier sans changer"
                                   " le motif de qualification")

    if type == 'DUBLIN':
        self.document.statut = 'EN_COURS_PROCEDURE_DUBLIN'
    elif self.document.statut == 'EN_COURS_PROCEDURE_DUBLIN':
        self.document.statut = 'PRETE_EDITION_ATTESTATION'

    requalifications = ancienne_procedure.requalifications
    requalification = ProcedureRequalification(
        ancien_type=ancienne_procedure.type,
        ancien_acteur=ancienne_procedure.acteur,
        date=datetime.utcnow(),
        ancien_motif_qualification=ancienne_procedure.motif_qualification,
        date_notification=ancienne_procedure.date_notification)
    requalifications.append(requalification)
    self.document.procedure = Procedure(type=type, acteur=acteur,
                                        motif_qualification=motif_qualification,
                                        requalifications=requalifications,
                                        date_notification=date_notification)


class DemandeAsilePreteEditionAttestationController(DemandeAsileController):

    def passer_en_attente_introduction_ofpra(self):
        self.document.statut = 'EN_ATTENTE_INTRODUCTION_OFPRA'

    def editer_attestation(self, user, date_debut_validite, date_fin_validite,
                           date_decision_sur_attestation=None):
        """
        Method which create a "droit" and return it.

        :param user: The agent that creates the "droit"
        :param date_debut_validite: Droit's start of validity
        :param date_fin_validite: Droit's end of validity
        :param date_decision_sur_attestation: Droit's field
        :returns: A "droit" document. You should call confirm method when you'll need
            to insert it in DB. (eg. After demande_asile save_or_abort method)
        """
        from sief.view.droit_api import lazy_create_droit
        delivrer_droit = True
        if self.document.decisions_attestation:
            for decision in reversed(self.document.decisions_attestation):
                if (decision.type_document == 'ATTESTATION_DEMANDE_ASILE' and
                        decision.sous_type_document == 'PREMIERE_DELIVRANCE'):
                    delivrer_droit = decision.delivrance
                    break

        droit_factory = None
        if delivrer_droit:
            droit_factory = lazy_create_droit(
                type_document='ATTESTATION_DEMANDE_ASILE',
                sous_type_document='PREMIERE_DELIVRANCE',
                date_debut_validite=date_debut_validite,
                date_fin_validite=date_fin_validite,
                date_decision_sur_attestation=date_decision_sur_attestation,
                agent_createur=user,
                demande_origine=self.document,
                usager=self.document.usager)
        if not self.document.procedure or not self.document.procedure.type:
            raise ValueError("La demande d'asile doit avoir une procedure "
                             "qualifiée pour générer une attestation")
        if self.document.procedure.type == 'DUBLIN':
            self.document.statut = "EN_COURS_PROCEDURE_DUBLIN"
        else:  # NORMAL or ACCELEREE
            self.document.statut = "EN_ATTENTE_INTRODUCTION_OFPRA"
        return droit_factory


class DemandeAsileEnAttenteIntroductionOfpraController(DemandeAsileController):
    requalifier_procedure = _requalifier_procedure

    def finir_procedure(self):
        self.document.statut = 'FIN_PROCEDURE'

    def introduire_ofpra(self, identifiant_inerec, date_introduction_ofpra, numero_reexamen=None):
        self.document.identifiant_inerec = identifiant_inerec
        self.document.date_introduction_ofpra = date_introduction_ofpra
        if numero_reexamen and numero_reexamen > 0:
            self.document.type_demande = 'REEXAMEN'
            self.document.numero_reexamen = numero_reexamen
            self.document.date_introduction_ofpra = datetime.utcnow()
        elif numero_reexamen == 0:
            self.document.type_demande = 'PREMIERE_DEMANDE_ASILE'
            self.document.numero_reexamen = None
        self.document.statut = 'EN_COURS_INSTRUCTION_OFPRA'
        self.document.acteur_type_demande = "OFPRA"


class DemandeAsileEnCoursProcedureDublinController(DemandeAsileController):
    requalifier_procedure = _requalifier_procedure

    def finir_procedure(self):
        self.document.statut = 'FIN_PROCEDURE_DUBLIN'


class DemandeAsileEnCoursInstructionOfpraController(DemandeAsileController):
    requalifier_procedure = _requalifier_procedure

    def recevabilite(self, recevabilite, date_notification, date_qualification=None):
        if self.document.type_demande != 'REEXAMEN':
            raise ValidationError(errors={
                "recevabilites": "la demande doit etre une demande de type reexamen"
            })
        if recevabilite:
            if date_qualification is not None and date_qualification != date_notification:
                raise ValidationError({
                    "recevabilites": "Dans le cas d'une recevabilité la date de qualification doit être égale a la date de notification"})
            date_qualification = date_notification
        recev = Recevabilite(recevabilite=recevabilite,
                             date_qualification=date_qualification,
                             date_notification=date_notification)
        if not self.document.recevabilites:
            self.document.recevabilites = [recev]
        else:
            self.document.recevabilites.append(recev)

    def passer_decision_definitive(self):
        self.document.statut = 'DECISION_DEFINITIVE'


class DemandeAsileDecisionDefinitiveController(DemandeAsileController):

    def finir_procedure(self):
        self.document.statut = 'FIN_PROCEDURE'

    def clean(self):
        super().clean()
        if not self.document.decisions_definitives:
            raise ValidationError(errors={
                "decision_definitive": "Champs requis en statut DECISION_DEFINITIVE"
            })
        errors = {}
        for i, decision in enumerate(self.document.decisions_definitives):
            if decision.entite == 'CNDA' and not decision.numero_skipper:
                errors['decision_definitive.%s.numero_skipper' % i] = \
                    "L'entité CNDA nécessite un numéro skipper"
        if errors:
            raise ValidationError(errors=errors)
        # Automatically store the last decision definitive's resultat
        if self.document.decisions_definitives:
            resultat = self.document.decisions_definitives[-1].resultat
            if resultat != 'ERREUR':
                self.document.decision_definitive_resultat = resultat
            else:  # ERREUR is not a valid value for this field, so set it empty
                self.document.decision_definitive_resultat = None
        else:
            self.document.decision_definitive_resultat = None


class DemandeAsileFinProcedureDublinController(DemandeAsileController):
    pass


class DemandeAsileFinProcedureController(DemandeAsileController):
    pass


def _controller_router(da):
    controllers = {
        'PRETE_EDITION_ATTESTATION': DemandeAsilePreteEditionAttestationController,
        'EN_ATTENTE_INTRODUCTION_OFPRA': DemandeAsileEnAttenteIntroductionOfpraController,
        'EN_COURS_PROCEDURE_DUBLIN': DemandeAsileEnCoursProcedureDublinController,
        'EN_COURS_INSTRUCTION_OFPRA': DemandeAsileEnCoursInstructionOfpraController,
        'DECISION_DEFINITIVE': DemandeAsileDecisionDefinitiveController,
        'FIN_PROCEDURE_DUBLIN': DemandeAsileFinProcedureDublinController,
        'FIN_PROCEDURE': DemandeAsileFinProcedureController,
        "CLOTURE_OFPRA": DemandeAsileController(da)
    }
    if da.statut in controllers:
        return controllers[da.statut](da)
    raise ValueError('demande asile `%s`: wrong statut `%s`' %
                     (da.pk, da.statut))


class DemandeAsileSearcher(BaseSolrSearcher):
    FIELDS = ('statut', 'usager', 'condition_entree_france', 'date_demande',
              'structure_premier_accueil', 'referent_premier_accueil',
              'date_demande', 'agent_enregistrement', 'date_enregistrement',
              'agent_orientation', 'date_orientation',
              'date_introduction_ofpra', 'identifiant_inerec',
              'acceptation_opc', 'renouvellement_attestation', 'visa',
              'condition_entree_france', 'indicateur_visa_long_sejour',
              'decision_sur_attestation', 'date_decision_sur_attestation',
              'type_demandeur', 'demande_asile_principale', 'date_depart',
              'structure_guichet_unique', 'prefecture_rattachee', 'date_entree_en_france',
              'decision_definitive_resultat', 'conditions_exceptionnelles_accueil',
              'motif_conditions_exceptionnelles_accueil', 'type_demande',
              'usager_identifiant_eurodac')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from sief.model import Usager

        # Usager fields
        self.build_and_register_converter('usager_nom', Usager.nom,
                                          extractor=lambda doc: doc.usager.nom)
        self.build_and_register_converter('usager_prenoms', Usager.prenoms,
                                          extractor=lambda doc: doc.usager.prenoms,
                                          aliases=('usager_prenom',))
        self.build_and_register_converter('usager_identifiant_agdref', Usager.identifiant_agdref,
                                          extractor=lambda doc: doc.usager.identifiant_agdref)
        self.build_and_register_converter('usager_identifiant_dna', Usager.identifiant_dna,
                                          extractor=lambda doc: doc.usager.identifiant_dna)
        # Cloture OFPRA fields
        self.build_and_register_converter('da_cloture_ofpra_date_notification', ClotureOFPRA.date_notification,
                                          extractor=lambda doc: doc.clotures_ofpra[-1].date_notification if doc.clotures_ofpra else None)
        # Decision definitive fields
        self.build_and_register_converter('da_decision_definitive_nature', DecisionDefinitive.nature,
                                          extractor=lambda doc: doc.decisions_definitives[-1].nature if doc.decisions_definitives else None)
        self.build_and_register_converter('da_decision_definitive_date', DecisionDefinitive.date,
                                          extractor=lambda doc: doc.decisions_definitives[-1].date if doc.decisions_definitives else None)
        self.build_and_register_converter('da_decision_definitive_date_premier_accord', DecisionDefinitive.date_premier_accord,
                                          extractor=lambda doc: doc.decisions_definitives[-1].date_premier_accord if doc.decisions_definitives else None)
        self.build_and_register_converter('da_decision_definitive_date_notification', DecisionDefinitive.date_notification,
                                          extractor=lambda doc: doc.decisions_definitives[-1].date_notification if doc.decisions_definitives else None)
        self.build_and_register_converter('da_decision_definitive_pays_exclus', DecisionDefinitive.pays_exclus,
                                          extractor=lambda doc: doc.decisions_definitives[-1].pays_exclus if doc.decisions_definitives else None)
        self.build_and_register_converter('da_decision_definitive_entite', DecisionDefinitive.entite,
                                          extractor=lambda doc: doc.decisions_definitives[-1].entite if doc.decisions_definitives else None)

        # Procedure fields
        self.build_and_register_converter('da_procedure_type', Procedure.type,
                                          extractor=lambda doc: doc.procedure.type)
        self.build_and_register_converter('da_procedure_motif_qualification', Procedure.motif_qualification,
                                          extractor=lambda doc: doc.procedure.motif_qualification)
        self.build_and_register_converter('da_procedure_acteur', Procedure.acteur,
                                          extractor=lambda doc: doc.procedure.acteur)

        # Dublin fields
        self.build_and_register_converter('da_dublin_date_demande_em', DublinTransfert.date_demande_EM,
                                          extractor=lambda doc: doc.dublin.date_demande_EM if doc.dublin else None)
        self.build_and_register_converter('da_dublin_date_reponse_em', DublinTransfert.date_reponse_EM,
                                          extractor=lambda doc: doc.dublin.date_reponse_EM if doc.dublin else None)
        self.build_and_register_converter('da_dublin_em', DublinTransfert.EM,
                                          extractor=lambda doc: doc.dublin.EM if doc.dublin else None)
        self.build_and_register_converter('da_dublin_reponse_em', DublinTransfert.reponse_EM,
                                          extractor=lambda doc: doc.dublin.reponse_EM if doc.dublin else None)
        self.build_and_register_converter('da_dublin_date_decision', DublinTransfert.date_decision,
                                          extractor=lambda doc: doc.dublin.date_decision if doc.dublin else None)
        self.build_and_register_converter('da_dublin_execution', DublinTransfert.execution,
                                          extractor=lambda doc: doc.dublin.execution if doc.dublin else None)
        self.build_and_register_converter('da_dublin_date_execution', DublinTransfert.date_execution,
                                          extractor=lambda doc: doc.dublin.date_execution if doc.dublin else None)
        self.build_and_register_converter('da_dublin_delai_depart_volontaire', DublinTransfert.delai_depart_volontaire,
                                          extractor=lambda doc: doc.dublin.delai_depart_volontaire if doc.dublin else None)
        self.build_and_register_converter('da_dublin_contentieux', DublinTransfert.contentieux,
                                          extractor=lambda doc: doc.dublin.contentieux if doc.dublin else None)
        self.build_and_register_converter('da_dublin_decision_contentieux', DublinTransfert.decision_contentieux,
                                          extractor=lambda doc: doc.dublin.decision_contentieux if doc.dublin else None)
        self.build_and_register_converter('da_dublin_date_signalement_fuite', DublinTransfert.date_signalement_fuite,
                                          extractor=lambda doc: doc.dublin.date_signalement_fuite if doc.dublin else None)
        # Recevabilite fields
        self.build_and_register_converter('da_recevabilite', Recevabilite.recevabilite,
                                          extractor=lambda doc: doc.recevabilites[-1].recevabilite if doc.recevabilites else None)


class Alerte(EmbeddedDocument):
    type = fields.StringField(choices=('Orange', 'Rouge'), required=True)
    droit = fields.ReferenceField('Droit', required=True)


class DecisionDefinitive(EmbeddedDocument):

    @property
    def resultat(self):
        try:
            return DECISIONS_DEFINITIVES[self.nature]
        except KeyError:
            current_app.logger.error('Unknown DecisionDefinitive.nature `%s`' % self.nature)
            return 'ERREUR'

    nature = fields.StringField(choices=list(DECISIONS_DEFINITIVES.keys()), required=True)
    date = fields.DateTimeField(required=True)
    date_premier_accord = fields.DateTimeField(null=True)
    date_notification = fields.DateTimeField(required=True)
    pays_exclus = fields.ListField(fields.ReferenceField("Pays"), null=True)
    numero_skipper = fields.StringField(null=True, max_length=8)
    entite = fields.StringField(choices=('OFPRA', 'CNDA'), null=True, max_length=30)


class DublinTransfert(EmbeddedDocument):
    date_demande_EM = fields.DateTimeField(required=True)
    date_reponse_EM = fields.DateTimeField(null=True)
    EM = fields.ReferenceField("Pays", required=True)
    reponse_EM = fields.StringField(null=True)
    date_decision = fields.DateTimeField(null=True)
    execution = fields.BooleanField(null=True)
    date_execution = fields.DateTimeField(null=True)
    delai_depart_volontaire = fields.IntField(null=True)
    contentieux = fields.BooleanField(null=True)
    decision_contentieux = fields.StringField(null=True)
    date_signalement_fuite = fields.DateTimeField(null=True)


class Hebergement(EmbeddedDocument):
    type = fields.StringField(choices=('CADA', 'HUDA'), null=True)
    date_entre_hebergement = fields.DateTimeField(null=True)
    date_sortie_hebergement = fields.DateTimeField(null=True)
    date_refus_hebergement = fields.DateTimeField(null=True)


class Ada(EmbeddedDocument):
    date_ouverture = fields.DateTimeField(null=True)
    date_fermeture = fields.DateTimeField(null=True)
    date_suspension = fields.DateTimeField(null=True)
    montant = fields.DecimalField(min_value=0, precision=2, null=True)


class ProcedureRequalification(EmbeddedDocument):
    date = fields.DateTimeField(required=True)
    date_notification = fields.DateTimeBoundedField(min_date=datetime(1881, 1, 1), required=True)
    ancien_type = fields.StringField(
        choices=('NORMALE', 'ACCELEREE', 'DUBLIN'), required=True)
    ancien_acteur = fields.StringField(
        choices=('PREFECTURE', 'OFPRA', 'GUICHET_UNIQUE'), required=True)
    ancien_motif_qualification = fields.StringField(
        choices=MOTIFS_QUALIFICATION, null=True)


class Procedure(EmbeddedDocument):

    def clean(self):
        valid_motifs = MOTIFS_QUALIFICATION_TO_TYPE.get(self.type) or ()
        if self.motif_qualification in (None, '') and self.acteur != 'OFPRA':
            raise ValidationError(
                errors={'motif_qualification': "Le motif qualification est nécessaire si l'acteur n'est pas l'OFPRA"})
        if self.motif_qualification not in (valid_motifs + (None, '')):
            raise ValidationError(
                errors={
                    'motif_qualification':
                        'Motifs de qualification pour une procédure %s : %s' % (
                            self.type, valid_motifs)
                })

    type = fields.StringField(choices=('NORMALE', 'ACCELEREE', 'DUBLIN'), required=True)
    motif_qualification = fields.StringField(choices=MOTIFS_QUALIFICATION, null=True)
    acteur = fields.StringField(default='GUICHET_UNIQUE',
                                choices=('PREFECTURE', 'OFPRA', 'GUICHET_UNIQUE'), required=True)
    requalifications = fields.ListField(fields.EmbeddedDocumentField(ProcedureRequalification))
    date_notification = fields.DateTimeBoundedField(min_date=datetime(1881, 1, 1))


class Recevabilite(EmbeddedDocument):
    date_notification = fields.DateTimeField(required=True)
    date_qualification = fields.DateTimeField(required=True)
    recevabilite = fields.BooleanField(required=True)


class ClotureOFPRA(EmbeddedDocument):
    date_notification = fields.DateTimeField(required=True)


class DemandeAsile(BaseDocument):
    meta = {'controller_cls': _controller_router,
            'searcher_cls': DemandeAsileSearcher,
            'indexes': ['prefecture_rattachee', 'usager', 'identifiant_inerec']}

    id = fields.SequenceField(primary_key=True)

    usager = fields.ReferenceField("Usager", required=True)
    prefecture_rattachee = fields.ReferenceField('Prefecture')

    # Recueil
    recueil_da_origine = fields.ReferenceField("RecueilDA", null=True)
    # structure_accueil
    structure_premier_accueil = fields.ReferenceField("Site", required=True)
    structure_guichet_unique = fields.ReferenceField("GU", required=True)
    # agent_accueil
    referent_premier_accueil = fields.ReferenceField("Utilisateur", required=True)
    # date_transmission
    date_demande = fields.DateTimeField(required=True)
    agent_enregistrement = fields.ReferenceField("Utilisateur", required=True)
    date_enregistrement = fields.DateTimeField(required=True)
    agent_orientation = fields.StringField(max_length=100)  # External agent provided by dn@
    date_orientation = fields.DateTimeField()

    identifiant_inerec = fields.StringField(max_length=9)
    date_introduction_ofpra = fields.DateTimeField()

    alerte = fields.EmbeddedDocumentField(Alerte, null=True)

    acceptation_opc = fields.BooleanField(null=True)

    documents = fields.ListField(fields.ReferenceField("Fichier"))

    statut = fields.StringField(
        choices=ALLOWED_STATUS, default="PRETE_EDITION_ATTESTATION", required=True)

    decisions_definitives = fields.ListField(fields.EmbeddedDocumentField(DecisionDefinitive))
    decision_definitive_resultat = fields.StringField(choices=('ACCORD', 'REJET'), null=True)
    dublin = fields.EmbeddedDocumentField(DublinTransfert, null=True)

    hebergement = fields.EmbeddedDocumentField(Hebergement, null=True)
    ada = fields.EmbeddedDocumentField(Ada, null=True)
    procedure = fields.EmbeddedDocumentField(Procedure, required=True)

    condition_entree_france = fields.StringField(
        choices=("REGULIERE", "IRREGULIERE"), required=True)
    visa = fields.StringField(choices=("AUCUN", "C", "D"))
    conditions_exceptionnelles_accueil = fields.BooleanField(default=False, required=True)
    motif_conditions_exceptionnelles_accueil = fields.StringField(null=True,
                                                                  choices=("VISA_D_ASILE",
                                                                           "REINSTALLATION",
                                                                           "RELOCALISATION",
                                                                           "CAO"))
    indicateur_visa_long_sejour = fields.BooleanField(null=True)

    type_demandeur = fields.StringField(choices=('PRINCIPAL', 'CONJOINT'),
                                        default='PRINCIPAL', required=True)

    demande_asile_principale = fields.ReferenceField('DemandeAsile', null=True)
    enfants_presents_au_moment_de_la_demande = fields.ListField(fields.ReferenceField("Usager"))
    demandes_rattachees = fields.ListField(fields.ReferenceField('DemandeAsile'))

    date_depart = fields.DateTimeField(null=True)
    date_depart_approximative = fields.BooleanField()
    date_entree_en_france = fields.DateTimeField(null=True)
    date_entree_en_france_approximative = fields.BooleanField()
    pays_traverses = fields.ListField(fields.EmbeddedDocumentField(PaysTraverse), null=True)
    type_demande = fields.StringField(choices=ALLOWED_TYPE, default="PREMIERE_DEMANDE_ASILE",
                                      required=True)
    acteur_type_demande = fields.StringField(choices=("PREFECTURE", "OFPRA"), default="PREFECTURE",
                                             required=True)
    numero_reexamen = fields.IntField(null=True, min_value=1)
    usager_identifiant_eurodac = fields.EurodacIdField()

    renouvellement_attestation = fields.IntField(default=1, required=True)
    decision_sur_attestation = fields.BooleanField(null=True)  # must be cleaned ?
    date_decision_sur_attestation = fields.DateTimeField(null=True)  # must be cleaned?
    decisions_attestation = fields.ListField(
        fields.EmbeddedDocumentField(DecisionAttestation), null=True)

    recevabilites = fields.ListField(fields.EmbeddedDocumentField(Recevabilite), null=True)
    clotures_ofpra = fields.ListField(fields.EmbeddedDocumentField(ClotureOFPRA), null=True)
    # in case of reexamen asylum we need to know when the asylum change from status EN_ATTENTE_INTRODUCTION_OFPRA
    # to EN_COURS_INSTRUCTION_OFPRA for agdref flow
    date_instruction_ofpra = fields.DateTimeField(null=True)
