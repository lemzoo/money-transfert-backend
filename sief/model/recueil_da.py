from flask import current_app
from datetime import datetime

from mongoengine import ValidationError, EmbeddedDocument

from core.model_util import BaseController, BaseSolrSearcher, BaseDocument

from sief.model.recueil_da_regles import *  # noqa
from sief.model.demande_asile import DemandeAsile, PaysTraverse, MOTIFS_QUALIFICATION, ALLOWED_TYPE
from sief.model.eurodac import generate_eurodac_ids
from random import choice
from sief.model import fields

from sief.model.usager import Vulnerabilite
import services


ALLOWED_STATUS = [
    "BROUILLON",
    "PA_REALISE",
    "DEMANDEURS_IDENTIFIES",
    "EXPLOITE",
    "ANNULE",
    "PURGE"
]

ALLOWED_MOTIFS_ANNULATION = [
    'NON_PRESENTATION_RDV',
    'BESOIN_INFORMATION_COMPLEMENTAIRE',
    'INTERPRETE_NON_DISPONIBLE',
    'RETARD_PRESENTATION_DEMANDEUR',
    'PANNE_INFORMATIQUE',
    'FAIT_EXTERIEUR',
    'ECHEC_PRISE_EMPREINTE',
    'AUTRE'
]


class Refus(EmbeddedDocument):
    motif = fields.StringField(required=True)
    date_notification = fields.DateTimeField(default=datetime.utcnow)


class UsagerRecueil(EmbeddedDocument):
    meta = {'allow_inheritance': True}

    usager_existant = fields.ReferenceField('Usager')
    identifiant_eurodac = fields.EurodacIdField()
    identifiant_agdref = fields.AgdrefIdField()
    identifiant_portail_agdref = fields.StringField(required=False, null=True)
    date_enregistrement_agdref = fields.DateTimeField()
    nom = fields.PatronymeField(max_length=30)
    origine_nom = fields.OrigineNom(null=True)
    nom_usage = fields.PatronymeField(null=True, max_length=30)
    origine_nom_usage = fields.OrigineNom(null=True)
    prenoms = fields.ListField(fields.PatronymeField(max_length=30))
    photo = fields.ReferenceField("Fichier", null=True)
    photo_premier_accueil = fields.ReferenceField("Fichier", null=True)
    sexe = fields.SexeField()
    documents = fields.ListField(fields.ReferenceField("Fichier"))
    date_naissance = fields.DateNaissanceField(null=True)
    date_naissance_approximative = fields.BooleanField(null=True)
    pays_naissance = fields.PaysField(null=True)
    ville_naissance = fields.StringField(min_length=1, null=True, max_length=30)
    nationalites = fields.ListField(fields.NationaliteField())
    nom_pere = fields.PatronymeField(null=True, max_length=30)
    prenom_pere = fields.PatronymeField(null=True, max_length=30)
    nom_mere = fields.PatronymeField(null=True, max_length=30)
    prenom_mere = fields.PatronymeField(null=True, max_length=30)
    type_procedure = fields.StringField(choices=["NORMALE", "ACCELEREE", "DUBLIN"])
    motif_qualification_procedure = fields.StringField(null=True, choices=MOTIFS_QUALIFICATION)
    condition_entree_france = fields.StringField(choices=("REGULIERE", "IRREGULIERE"))
    conditions_exceptionnelles_accueil = fields.BooleanField(null=True)
    motif_conditions_exceptionnelles_accueil = fields.StringField(
        null=True, choices=("VISA_D_ASILE", "REINSTALLATION", "RELOCALISATION", "CAO"))
    visa = fields.StringField(null=True, choices=("AUCUN", "C", "D"))
    indicateur_visa_long_sejour = fields.BooleanField(null=True)
    decision_sur_attestation = fields.BooleanField(null=True)
    date_decision_sur_attestation = fields.DateTimeField(null=True)
    refus = fields.EmbeddedDocumentField(Refus)
    adresse = fields.AddressField(null=True)
    telephone = fields.PhoneField(null=True)
    email = fields.EmailField(null=True, max_length=50)
    langues = fields.ListField(fields.LangueIso6392Field())
    langues_audition_OFPRA = fields.ListField(fields.LangueOfpraField())
    present_au_moment_de_la_demande = fields.BooleanField()
    demandeur = fields.BooleanField()
    demande_asile_resultante = fields.ReferenceField('DemandeAsile', null=True)
    representant_legal_nom = fields.PatronymeField(null=True, max_length=30)
    representant_legal_prenom = fields.PatronymeField(null=True, max_length=30)
    representant_legal_personne_morale = fields.BooleanField(null=True)
    representant_legal_personne_morale_designation = fields.StringField(null=True)
    date_depart = fields.DateTimeField(null=True)
    date_depart_approximative = fields.BooleanField(null=True)
    date_entree_en_france = fields.DateTimeField(null=True)
    date_entree_en_france_approximative = fields.BooleanField(null=True)
    pays_traverses = fields.ListField(fields.EmbeddedDocumentField(PaysTraverse))
    vulnerabilite = fields.EmbeddedDocumentField(Vulnerabilite, null=True)
    # information on reexamen
    type_demande = fields.StringField(choices=ALLOWED_TYPE, default="PREMIERE_DEMANDE_ASILE")
    numero_reexamen = fields.IntField(null=True, min_value=1)
    identite_approchante_select = fields.BooleanField(null=True)


class UsagerSecondaireRecueil(UsagerRecueil):
    acceptation_opc = fields.BooleanField()


class UsagerPrincipalRecueil(UsagerSecondaireRecueil):
    situation_familiale = fields.FamilyStatusField()


class UsagerEnfantRecueil(UsagerRecueil):
    situation_familiale = fields.FamilyStatusField()
    usager_1 = fields.BooleanField(null=True)
    usager_2 = fields.BooleanField(null=True)


class RendezVousGu(EmbeddedDocument):
    date = fields.DateTimeField(required=True)
    marge = fields.IntField()
    creneaux = fields.ListField(fields.ReferenceField('Creneau'), default=list)
    site = fields.ReferenceField('Site', required=True)
    motif = fields.StringField(required=True, choices=[
        "PREMIER_RDV_GU", "ECHEC_PRISE_EMPREINTES", "DOSSIER_A_COMPLETER",
        "ATTENTE_REPONSE_DUBLIN", "ATTENTE_RETOUR_SIRENE_FRANCE", "RETARD_DEMANDEUR"])
    commentaire = fields.StringField()
    annule = fields.BooleanField()  # Only for `rendez_vous_gu_anciens`


def _controller_router(recueil_da):
    if recueil_da.statut == "BROUILLON":
        return RecueilDABrouillonController(recueil_da)
    elif recueil_da.statut == "PA_REALISE":
        return RecueilDAPARealiseController(recueil_da)
    elif recueil_da.statut == "DEMANDEURS_IDENTIFIES":
        return RecueilDADemandeursIdentifiesController(recueil_da)
    elif recueil_da.statut == "EXPLOITE":
        return RecueilDAExploiteController(recueil_da)
    elif recueil_da.statut == "ANNULE":
        return RecueilDAAnnuleController(recueil_da)
    elif recueil_da.statut == "PURGE":
        return RecueilDAPurgeController(recueil_da)
    else:
        raise ValueError('recueil_da `%s`: wrong statut `%s`'
                         % (recueil_da.pk, recueil_da.statut))


class RecueilDAController(BaseController):
    RULES = None

    def __init__(self, *args, **kwargs):
        # Sanity check
        if not self.RULES:
            raise RuntimeError('RULES must be set')
        super().__init__(*args, **kwargs)

    def get_demandeurs(self):
        demandeurs = []
        if self.document.usager_1 and self.document.usager_1.demandeur:
            demandeurs.append(self.document.usager_1)
        if self.document.usager_2 and self.document.usager_2.demandeur:
            demandeurs.append(self.document.usager_2)
        demandeurs += [c for c in self.document.enfants if c.demandeur]
        return demandeurs

    def clean(self):
        errors = self.RULES.apply(self.document)
        if errors:
            raise ValidationError(errors=errors)

    def update(self, payload):
        raise RuntimeError('Cannot update this document, must replace it')


class RdvError(Exception):
    pass


class DemandeursIdentifiesError(Exception):

    def __init__(self, errors):
        super().__init__()
        self.errors = errors


class ExploiteError(Exception):

    def __init__(self, errors):
        super().__init__()
        self.errors = errors


def _annuler_rendez_vous(controller, lazy=False):
    document = controller.document
    if not document.rendez_vous_gu:
        raise RdvError('Pas de rendez-vous à annuler')
    old_rd = document.rendez_vous_gu
    old_rd.annule = True
    for creneau in old_rd.creneaux:
        creneau.controller.liberer()
    document.rendez_vous_gu_anciens.append(old_rd)
    document.rendez_vous_gu = None

    def commit():
        for creneau in old_rd.creneaux:
            creneau.save()

    if not lazy:
        commit()
    else:
        return commit


def _prendre_rendez_vous(controller, creneaux=None, motif='PREMIER_RDV_GU'):
    document = controller.document
    if document.rendez_vous_gu:
        raise RdvError('Un rendez-vous a déjà été pris')
    site = document.structure_accueil
    booking = None
    if not creneaux:
        if len(document.controller.get_demandeurs()) > 1:
            for gu in site.guichets_uniques:
                booking = gu.controller.reserver_creneaux(
                    document, family=True,
                    limite_rdv_jrs=gu.limite_rdv_jrs)
                if booking.ok:
                    break
        else:
            for gu in site.guichets_uniques:
                booking = gu.controller.reserver_creneaux(
                    document, limite_rdv_jrs=gu.limite_rdv_jrs)
                if booking.ok:
                    break
        if not booking or not booking.ok:
            raise RdvError('Pas de créneaux disponibles pour le moment')
        creneaux = booking.creneaux
    else:
        from sief.model.site import CreneauxBooking
        booking = CreneauxBooking(creneaux=creneaux, do_check=False)
    # Now fill the document
    document.rendez_vous_gu = RendezVousGu(motif=motif,
                                           date=creneaux[0].date_debut, creneaux=creneaux,
                                           marge=creneaux[0].marge, site=creneaux[0].site)
    document.structure_guichet_unique = creneaux[0].site
    return booking


class RecueilDABrouillonController(RecueilDAController):
    RULES = RuleManager((
        rgl_brouillon_champs_obligatoires,
        rgl_brouillon_champs_interdits,
        # Note that brouillon state accepts inconsistent state in usagers
    ))

    prendre_rendez_vous = _prendre_rendez_vous

    def check_pa_realiser(self):
        rules = RuleManager((
            rgl_au_moins_un_demandeur_est_requis,
            rgl_champs_obligatoires_usagers_base,
            rgl_champs_interdits_usagers_non_present,
            rgl_pa_realise_champs_obligatoires_usagers_demandeur,
            rgl_pa_realise_champs_photo_demandeur,
            rgl_situation_familiale,
            rgl_present_au_moment_de_la_demande,
            rgl_no_modif_usager_existant,
            rgl_date_depart_et_entree,
            rgl_pays_traverses,
            rgl_reexamen_numero_reexamen_requis

        ))
        errors = rules.apply(self.document)
        if errors:
            raise ValidationError(errors=errors)

    def pa_realiser(self, creneaux=None):
        self.document.date_transmission = datetime.utcnow()
        self.document.statut = 'PA_REALISE'
        booking = self.prendre_rendez_vous(creneaux=creneaux)
        # Automatically connect the recueil to the selected GU's prefecture
        self.document.prefecture_rattachee = self.document.structure_guichet_unique.autorite_rattachement
        return booking


class RecueilDAPARealiseController(RecueilDAController):
    RULES = RuleManager((
        rgl_au_moins_un_demandeur_est_requis,
        rgl_pa_realise_champs_obligatoires,
        rgl_pa_realise_champs_interdits,
        rgl_champs_obligatoires_usagers_base,
        rgl_champs_interdits_usagers_non_present,
        rgl_pa_realise_champs_obligatoires_usagers_demandeur,
        rgl_pa_realise_champs_photo_demandeur,
        rgl_situation_familiale,
        rgl_present_au_moment_de_la_demande,
        rgl_no_modif_usager_existant,
        rgl_date_depart_et_entree,
        rgl_pays_traverses,
        rgl_aucune_demande_asile,
        rgl_reexamen_numero_reexamen_requis
    ))

    def annuler(self, agent, motif):
        self.document.statut = 'ANNULE'
        self.document.agent_annulation = agent
        self.document.motif_annulation = motif
        self.document.date_annulation = datetime.utcnow()
        # TODO: Create associate usager ?

    def verifier_statut_fne_demandeurs(self):

        errors = {}

        try:
            if self.document.usager_1 and self.document.usager_1.demandeur:
                if self.document.usager_1.type_demande == 'PREMIERE_DEMANDE_ASILE':
                    usager = self.document.usager_1.usager_existant or self.document.usager_1
                    if usager and usager.identifiant_agdref:
                        check = services.lookup_fne(identifiant_agdref=usager.identifiant_agdref)
                        if check and check.get('indicateurPresenceDemandeAsile') == 'O':
                            errors['usager_1'] = {
                                'identifiant_agdref': "Usager déjà titulaire d'une demande d'asile."}

            if self.document.usager_2 and self.document.usager_2.demandeur:
                if self.document.usager_2.type_demande == 'PREMIERE_DEMANDE_ASILE':
                    usager = self.document.usager_2.usager_existant or self.document.usager_2
                    if usager and usager.identifiant_agdref:
                        check = services.lookup_fne(identifiant_agdref=usager.identifiant_agdref)
                        if check and check.get('indicateurPresenceDemandeAsile') == 'O':
                            errors['usager_2'] = {
                                'identifiant_agdref': "Usager déjà titulaire d'une demande d'asile."}

            for id, child in enumerate(self.document.enfants):
                usager = child.usager_existant or child
                if usager and usager.identifiant_agdref:
                    if usager.type_demande == 'PREMIERE_DEMANDE_ASILE':
                        check = services.lookup_fne(identifiant_agdref=usager.identifiant_agdref)
                        if check and check.get('indicateurPresenceDemandeAsile') == 'O':
                            if not errors.get('enfants'):
                                errors['enfants'][id] = {
                                    'identifiant_agdref': "Usager déjà titulaire d'une demande d'asile."}

        except services.fne.FNEDisabledError:
            errors = {"code": 503, "libelle": 'Connecteur FNE desactive'}
        except services.fne.FNEConnectionError:
            errors = {"code": 503, "libelle": 'Le service n\'a pas reussi a se connecter au FNE'}
        except services.fne.FNEBadRequestError:
            errors = {"code": 400, "libelle":
                      "Le FNE n'est pas en mesure de traiter notre requête actuellement. Veuillez réessayer ultérieurement."}
        return errors

    def identifier_demandeurs(self, save_recueil=False, if_match=None):

        def id_abort(code, *args, **errors):
            if args:
                errors = args[0]
            raise DemandeursIdentifiesError(errors)

        # Switching to DEMANDEURS_IDENTIFIES means each demandeur has
        # a valid `identifiant_agdref`
        from services.agdref import enregistrement_agdref
        self.document.controller.save_or_abort(if_match=if_match, abort=id_abort)

        def agdref_error_msg(obj_name, func):
            from services.agdref import AGDREFRequiredFieldsError

            def wrapper(*args, **kwargs):
                try:
                    func(*args, **kwargs)
                except AGDREFRequiredFieldsError as excp:
                    error = {}
                    if obj_name is 'usager_1' or obj_name is 'usager_2':
                        error[obj_name] = excp.errors
                    else:
                        error['enfants'] = {}
                        error['enfants'][obj_name] = excp.errors
                    raise AGDREFRequiredFieldsError(error)

            return wrapper

        def check_agdref_registered(usager):
            from string import ascii_letters, digits
            if not usager or not usager.demandeur:
                # Not demandeur or doesn't exist, do nothing
                return
            if usager.usager_existant:
                if not usager.usager_existant.identifiant_portail_agdref:
                    usager.usager_existant.identifiant_portail_agdref = ''.join(
                        choice(ascii_letters + digits) for _ in range(12))
                    usager.usager_existant.save()
                if not usager.usager_existant.identifiant_agdref:
                    # Make sure the already created usager has an identifiant_agdref
                    # Do this because services agdref needs it. Never saved in DB.
                    usager.usager_existant.date_entree_en_france = usager.date_entree_en_france
                    agdref_info = enregistrement_agdref(
                        usager.usager_existant,
                        self.document.structure_guichet_unique.autorite_rattachement.code_departement)
                    del usager.usager_existant.date_entree_en_france
                    usager.usager_existant.identifiant_agdref = agdref_info.identifiant_agdref
                    usager.usager_existant.date_enregistrement_agdref = agdref_info.date_enregistrement_agdref
                    usager.usager_existant.save()
            else:
                if not usager.identifiant_portail_agdref:
                    usager.identifiant_portail_agdref = ''.join(
                        choice(ascii_letters + digits) for _ in range(12))
                if not usager.identifiant_agdref:
                    # Ask for a new identifiant_agdref for the current usager
                    agdref_info = enregistrement_agdref(
                        usager, self.document.structure_guichet_unique.autorite_rattachement.code_departement)
                    usager.identifiant_agdref = agdref_info.identifiant_agdref
                    usager.date_enregistrement_agdref = agdref_info.date_enregistrement_agdref
                if save_recueil:
                    self.document.save()

        agdref_error_msg("usager_1", check_agdref_registered)(self.document.usager_1)
        # Do this because services agdref needs it. Never saved in DB.
        if self.document.usager_2:
            self.document.usager_2.situation_familiale = self.document.usager_1.situation_familiale
            agdref_error_msg("usager_2", check_agdref_registered)(self.document.usager_2)
            del self.document.usager_2.situation_familiale
        for id, child in enumerate(self.document.enfants):
            agdref_error_msg(id, check_agdref_registered)(child)
        self.document.statut = 'DEMANDEURS_IDENTIFIES'
        self.document.controller.save_or_abort()
        return self.document.doc_version

    annuler_rendez_vous = _annuler_rendez_vous
    prendre_rendez_vous = _prendre_rendez_vous

    def generate_identifiant_eurodac(self):
        eurodac_id_setters = []
        if self.document.usager_1 and self.document.usager_1.demandeur and not self.document.usager_1.identifiant_eurodac:
            eurodac_id_setters.append(self.document.usager_1)
        if self.document.usager_2 and self.document.usager_2.demandeur and not self.document.usager_2.identifiant_eurodac:
            eurodac_id_setters.append(self.document.usager_2)

        # traitement pour le cas des enfants
        if self.document.enfants is not None:
            for enfant in self.document.enfants:
                if enfant.demandeur and not enfant.identifiant_eurodac:
                    eurodac_id_setters.append(enfant)

        for index, eid in enumerate(generate_eurodac_ids(generate_number=len(eurodac_id_setters))):
            setattr(eurodac_id_setters[index], 'identifiant_eurodac', eid)
        return self.document


class RecueilDADemandeursIdentifiesController(RecueilDAController):

    """
    DEMANDEURS_IDENTIFIES is basically the same as PA_REALISE, only
    each usager demandeur must have a agdref number set
    """

    RULES = RuleManager((
        rgl_au_moins_un_demandeur_est_requis,
        rgl_demandeurs_identifies_champs_obligatoires,
        rgl_demandeurs_identifies_champs_interdits,
        rgl_champs_obligatoires_usagers_base,
        rgl_champs_interdits_usagers_non_present,
        rgl_demandeurs_identifies_champs_obligatoires_usagers_demandeur,
        rgl_situation_familiale,
        rgl_present_au_moment_de_la_demande,
        rgl_mineur_isole_representant_legal,
        rgl_no_modif_usager_existant,
        rgl_date_depart_et_entree,
        rgl_pays_traverses,
        rgl_aucune_demande_asile,
        rgl_demandeurs_identifies_numero_eurodac_demandeur,
        rgl_identite_approchante_select,
        rgl_reexamen_numero_reexamen_requis
    ))

    def annuler(self, agent, motif):
        self.document.statut = 'ANNULE'
        self.document.agent_annulation = agent
        self.document.motif_annulation = motif
        self.document.date_annulation = datetime.utcnow()

    def exploiter(self, agent):
        # First make sure the current document is in a correct state
        doc = self.document
        if current_app.config['ENFORCE_ID_FAMILLE_DNA'] and not doc.identifiant_famille_dna:
            ExploiteError({
                "identifiant_famille_dna":
                    "Cet identifiant est nécéssaire pour le passage en statut exploité"
            })
        doc.agent_enregistrement = agent
        doc.date_enregistrement = datetime.utcnow()
        doc.statut = 'EXPLOITE'
        prefecture_rattachee = doc.prefecture_rattachee
        try:
            RecueilDAExploiteController(doc).clean()
        except ValidationError as exc:
            raise ExploiteError(exc.to_dict())
        # Keep a trace of every create document to be able to revert
        # them in case of error
        created_documents = []
        context = ""

        def revert_creations(code, *args, **errors):
            for doc in created_documents:
                doc.delete()
            if args:
                errors = args[0]
            errors = "Erreur lors de la création de %s motif: %s" % (context, errors)
            raise ExploiteError(errors)

        def create_usager(usager_raw, situation_familiale=None, **kwargs):
            # Update identifiants_eurodac if the usager already exists
            if not usager_raw:
                return
            if usager_raw.usager_existant is not None:
                # gestion de l'usager existant pour eurodac
                if usager_raw.demandeur:
                    if not usager_raw.identifiant_eurodac:
                        usager_raw.identifiants_eurodac = []
                    usager_raw.usager_existant.identifiants_eurodac.append(
                        usager_raw.identifiant_eurodac)
                    usager_raw.usager_existant.controller.save_or_abort()

                return usager_raw.usager_existant
            # Copy the needed fields from the recueil_da to a new Usager
            from sief.model.usager import Usager, Localisation
            for field in RECUEIL_DA_TO_USAGER_FIELDS:
                value = getattr(usager_raw, field, None)
                if field == 'situation_familiale':
                    kwargs['situation_familiale'] = situation_familiale or value
                elif value is not None:
                    if field == 'adresse':
                        kwargs['localisations'] = [Localisation(
                            adresse=value, date_maj=datetime.utcnow())]
                    else:
                        kwargs[field] = value
            if usager_raw.demandeur and usager_raw.identifiant_eurodac:
                kwargs['identifiants_eurodac'] = [usager_raw.identifiant_eurodac]

            usager = Usager(prefecture_rattachee=prefecture_rattachee, **kwargs)
            usager.controller.save_or_abort(abort=revert_creations)
            usager_raw.usager_existant = usager
            created_documents.append(usager)
            return usager

        def create_da(recueil, usager_raw, type_demandeur='PRINCIPAL'):
            if not usager_raw or not usager_raw.demandeur:
                return None
            from sief.model.demande_asile import DemandeAsile, Procedure, DecisionAttestation
            if (type_demandeur == 'PRINCIPAL' and
                    not isinstance(usager_raw, UsagerEnfantRecueil)):
                # Add the children
                linked_children = [c.usager_existant for c in recueil.enfants
                                   if c.present_au_moment_de_la_demande]
                # Sanity check
                if None in linked_children:
                    raise ValueError("All usager_existant should have been "
                                     "created before running create_da")
            else:
                linked_children = None
            da = DemandeAsile(
                prefecture_rattachee=prefecture_rattachee,
                usager=usager_raw.usager_existant,
                recueil_da_origine=self.document,
                structure_premier_accueil=recueil.structure_accueil,
                structure_guichet_unique=recueil.structure_guichet_unique,
                referent_premier_accueil=recueil.agent_accueil,
                date_demande=recueil.date_transmission,
                agent_enregistrement=recueil.agent_enregistrement,
                date_enregistrement=recueil.date_enregistrement,
                condition_entree_france=usager_raw.condition_entree_france,
                visa=usager_raw.visa,
                conditions_exceptionnelles_accueil=usager_raw.conditions_exceptionnelles_accueil,
                motif_conditions_exceptionnelles_accueil=usager_raw.motif_conditions_exceptionnelles_accueil,
                indicateur_visa_long_sejour=usager_raw.indicateur_visa_long_sejour,
                procedure=Procedure(type=usager_raw.type_procedure,
                                    motif_qualification=usager_raw.motif_qualification_procedure,
                                    date_notification=usager_raw.date_decision_sur_attestation),
                type_demandeur=type_demandeur,
                enfants_presents_au_moment_de_la_demande=linked_children,
                pays_traverses=usager_raw.pays_traverses,
                date_depart=usager_raw.date_depart,
                date_depart_approximative=usager_raw.date_depart_approximative,
                date_entree_en_france=usager_raw.date_entree_en_france,
                date_entree_en_france_approximative=usager_raw.date_entree_en_france_approximative,
                type_demande=usager_raw.type_demande,
                numero_reexamen=usager_raw.numero_reexamen,
                usager_identifiant_eurodac=usager_raw.identifiant_eurodac,
                decision_sur_attestation=usager_raw.decision_sur_attestation,
                date_decision_sur_attestation=usager_raw.date_decision_sur_attestation,
            )
            if usager_raw.refus:
                da.decisions_attestation = [DecisionAttestation(motif=usager_raw.refus.motif,
                                                                date_decision=usager_raw.refus.date_notification if usager_raw.refus.date_notification else datetime.utcnow(
                                                                ),
                                                                type_document='ATTESTATION_DEMANDE_ASILE',
                                                                sous_type_document='PREMIERE_DELIVRANCE',
                                                                delivrance=False,
                                                                agent_createur=agent)]

                da.controller.editer_attestation(user=agent,
                                                 date_debut_validite=datetime.utcnow(),
                                                 date_fin_validite=datetime.utcnow(),
                                                 date_decision_sur_attestation=da.date_decision_sur_attestation)

            da.controller.save_or_abort(abort=revert_creations)
            usager_raw.demande_asile_resultante = da
            created_documents.append(da)
            return da

        ret = {'usager_1': {}, 'usager_2': {}, 'enfants': []}
        # Now create the usager/demande_asile
        context = "Usager 1"
        usager_1 = create_usager(
            doc.usager_1, identifiant_famille_dna=doc.identifiant_famille_dna)
        if usager_1:
            ret['usager_1'] = {'usager': usager_1}
        context = "Usager 2"
        usager_2 = create_usager(
            doc.usager_2, usager_1.situation_familiale,
            identifiant_famille_dna=doc.identifiant_famille_dna)
        if usager_2:
            ret['usager_2'] = {'usager': usager_2}
            # Set conjoint
            usager_1.conjoint = usager_2
            usager_1.controller.save_or_abort(abort=revert_creations)
            usager_2.conjoint = usager_1
            usager_2.controller.save_or_abort(abort=revert_creations)
        for child in doc.enfants:
            kwargs = {'identifiant_famille_dna': doc.identifiant_famille_dna}
            for is_child_of, usager_parent in ((child.usager_1, usager_1),
                                               (child.usager_2, usager_2)):
                if is_child_of and usager_parent:
                    if usager_parent.sexe == 'M':
                        kwargs['identifiant_pere'] = usager_parent
                    else:
                        kwargs['identifiant_mere'] = usager_parent
            context = "Enfants"
            enfant_ret = {'usager': create_usager(child, **kwargs)}
            enfant_da = create_da(doc, child)
            if enfant_da:
                enfant_ret['demande_asile'] = enfant_da
            ret['enfants'].append(enfant_ret)
        da_usager_1 = create_da(doc, doc.usager_1)
        if da_usager_1:
            ret['usager_1']['demande_asile'] = da_usager_1
        da_usager_2 = create_da(doc, doc.usager_2, type_demandeur='CONJOINT')
        if da_usager_2:
            ret['usager_2']['demande_asile'] = da_usager_2
        return ret

    annuler_rendez_vous = _annuler_rendez_vous
    prendre_rendez_vous = _prendre_rendez_vous


class RecueilDAExploiteController(RecueilDAController):

    RULES = RuleManager((
        rgl_au_moins_un_demandeur_est_requis,
        rgl_exploite_champs_obligatoires,
        rgl_exploite_champs_interdits,
        rgl_champs_obligatoires_usagers_base,
        rgl_champs_interdits_usagers_non_present,
        rgl_exploite_champs_obligatoires_usagers_demandeur,
        rgl_situation_familiale,
        rgl_present_au_moment_de_la_demande,
        rgl_mineur_isole_representant_legal,
        rgl_date_depart_et_entree,
        rgl_pays_traverses,
        rgl_reexamen_numero_reexamen_requis
        # Once created, recueil's usager can have both usager related fields
        # and a usager_existant, hence don't use `rgl_no_modif_usager_existant`
    ))


class RecueilDAAnnuleController(RecueilDAController):
    RULES = RuleManager((rgl_annule_champs_obligatoires,))

    def purger(self):
        self.document.statut = 'PURGE'


class RecueilDAPurgeController(RecueilDAController):
    RULES = RuleManager((rgl_purger_champs_obligatoires,))


class RecueilDASearcher(BaseSolrSearcher):
    FIELDS = ('structure_accueil', 'agent_accueil', 'date_transmission',
              'structure_guichet_unique', 'agent_enregistrement',
              'date_enregistrement', 'statut', 'type', 'date_annulation',
              'motif_annulation', 'agent_annulation',
              'demande_asile_resultante', 'profil_demande',
              'prefecture_rattachee')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.build_and_register_converter(
            'rendez_vous_gu_date', RendezVousGu.date,
            extractor=lambda doc: doc.rendez_vous_gu.date if doc.rendez_vous_gu else None)
        self.build_and_register_converter(
            'rendez_vous_gu_creneaux', RendezVousGu.creneaux,
            extractor=lambda doc: doc.rendez_vous_gu.creneaux if doc.rendez_vous_gu else None,
            aliases=('rendez_vous_gu_creneau',))
        self.build_and_register_converter(
            'rendez_vous_gu_site', RendezVousGu.site,
            extractor=lambda doc: doc.rendez_vous_gu.site if doc.rendez_vous_gu else None)
        self.build_and_register_converter(
            'rendez_vous_gu_motif', RendezVousGu.motif,
            extractor=lambda doc: doc.rendez_vous_gu.motif if doc.rendez_vous_gu else None)

        def usagers_map_factory(fn):
            def usagers_map(doc):
                items = [fn(u) for u in [doc.usager_1, doc.usager_2] + doc.enfants if u]
                # Reduce items if there are lists
                if items and isinstance(items[0], (list, tuple)):
                    items = [e for l in items for e in l]
                return items

            return usagers_map

        def get_usager_field(field):
            def func(u):
                if field == 'adresse':
                    if u.usager_existant:
                        if u.usager_existant.localisations:
                            return u.usager_existant.localisations[-1].adresse
                        else:
                            return None
                    else:
                        return u.adresse

                # Handle all fields not present in usager_existant (da fields)
                if field in ['date_entree_en_france', 'date_depart', 'identifiant_eurodac']:
                    return getattr(u, field)

                return getattr(u.usager_existant if u.usager_existant else u, field)

            return func

        self.build_and_register_converter('usagers', UsagerRecueil.usager_existant,
                                          extractor=usagers_map_factory(
                                              lambda u: u.usager_existant),
                                          aliases=('usager',), multi=True)
        self.build_and_register_converter('usagers_nom_usage', UsagerRecueil.nom_usage,
                                          extractor=usagers_map_factory(
                                              get_usager_field('nom_usage')),
                                          aliases=('nom_usage',), multi=True)
        self.build_and_register_converter('usagers_nom', UsagerRecueil.nom,
                                          extractor=usagers_map_factory(get_usager_field('nom')),
                                          aliases=('nom',), multi=True)
        self.build_and_register_converter('usagers_prenoms', UsagerRecueil.prenoms,
                                          extractor=usagers_map_factory(
                                              get_usager_field('prenoms')),
                                          aliases=('prenom',), multi=True)
        self.build_and_register_converter('usagers_date_naissance',
                                          UsagerRecueil.date_naissance, aliases=('date_naissance',),
                                          multi=True,
                                          extractor=usagers_map_factory(
                                              get_usager_field('date_naissance')))
        self.build_and_register_converter('usagers_nationalites',
                                          UsagerRecueil.nationalites, aliases=('nationalite',),
                                          multi=True,
                                          extractor=usagers_map_factory(
                                              get_usager_field('nationalites')))
        self.build_and_register_converter('usagers_pays_naissance',
                                          UsagerRecueil.pays_naissance, aliases=('pays_naissance',),
                                          multi=True,
                                          extractor=usagers_map_factory(
                                              get_usager_field('pays_naissance')))
        self.build_and_register_converter('usagers_email', UsagerRecueil.email,
                                          extractor=usagers_map_factory(get_usager_field('email')),
                                          aliases=('email',), multi=True)
        self.build_and_register_converter('usagers_langues', UsagerRecueil.langues,
                                          extractor=usagers_map_factory(
                                              get_usager_field('langues')),
                                          aliases=('langue',), multi=True)
        self.build_and_register_converter('usagers_adresses', UsagerRecueil.adresse,
                                          extractor=usagers_map_factory(
                                              get_usager_field('adresse')),
                                          aliases=('adresse',), multi=True)
        self.build_and_register_converter('usagers_date_entree_en_france',
                                          UsagerRecueil.date_entree_en_france, aliases=(
                                              'date_entree_en_france',),
                                          multi=True,
                                          extractor=usagers_map_factory(
                                              get_usager_field('date_entree_en_france')))
        self.build_and_register_converter('usagers_date_depart',
                                          UsagerRecueil.date_depart, aliases=('date_depart',),
                                          multi=True,
                                          extractor=usagers_map_factory(
                                              get_usager_field('date_depart')))
        self.build_and_register_converter('usagers_identifiant_agdref',
                                          UsagerRecueil.identifiant_agdref, aliases=(
                                              'identifiant_agdref',),
                                          multi=True,
                                          extractor=usagers_map_factory(
                                              get_usager_field('identifiant_agdref')))
        self.build_and_register_converter('usagers_representant_legal_nom',
                                          UsagerPrincipalRecueil.representant_legal_nom, aliases=(
                                              'representant_legal_nom',),
                                          multi=True,
                                          extractor=usagers_map_factory(
                                              get_usager_field('representant_legal_nom')))
        self.build_and_register_converter('usagers_representant_legal_prenom',
                                          UsagerPrincipalRecueil.representant_legal_prenom,
                                          aliases=('representant_legal_prenom',),
                                          multi=True,
                                          extractor=usagers_map_factory(
                                              get_usager_field('representant_legal_prenom')))
        self.build_and_register_converter('usagers_identifiant_eurodac',
                                          UsagerRecueil.identifiant_eurodac,
                                          aliases=('identifiant_eurodac',),
                                          multi=True,
                                          extractor=usagers_map_factory(
                                              get_usager_field('identifiant_eurodac')))


class RecueilDA(BaseDocument):
    meta = {'controller_cls': _controller_router,
            'searcher_cls': RecueilDASearcher,
            'indexes': ['prefecture_rattachee']}

    id = fields.SequenceField(primary_key=True)
    prefecture_rattachee = fields.ReferenceField('Prefecture')
    identifiant_famille_dna = fields.StringField(null=True, max_length=19)

    # Note that structure_accueil can contain a GU if the recueil is directly created in PA_REALISE
    structure_accueil = fields.ReferenceField('Site', required=True)
    structure_guichet_unique = fields.ReferenceField('GU', null=True)
    agent_accueil = fields.ReferenceField("Utilisateur", required=True)
    date_transmission = fields.DateTimeField()
    agent_enregistrement = fields.ReferenceField("Utilisateur")
    date_enregistrement = fields.DateTimeField()
    statut = fields.StringField(choices=ALLOWED_STATUS, default="BROUILLON", required=True)

    rendez_vous_gu = fields.EmbeddedDocumentField(RendezVousGu, null=True)
    rendez_vous_gu_anciens = fields.ListField(fields.EmbeddedDocumentField(RendezVousGu))

    motif_annulation = fields.StringField(choices=ALLOWED_MOTIFS_ANNULATION)
    date_annulation = fields.DateTimeField()
    agent_annulation = fields.ReferenceField("Utilisateur")

    profil_demande = fields.StringField(choices=(
        'FAMILLE', 'MINEUR_ISOLE', 'MINEUR_ACCOMPAGNANT', 'ADULTE_ISOLE'))
    usager_1 = fields.EmbeddedDocumentField(UsagerPrincipalRecueil)
    usager_2 = fields.EmbeddedDocumentField(UsagerSecondaireRecueil)
    enfants = fields.ListField(fields.EmbeddedDocumentField(UsagerEnfantRecueil))
