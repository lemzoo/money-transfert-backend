from datetime import datetime, timedelta
from hashlib import sha256

from mongoengine import EmbeddedDocument

from core.auth.login_pwd_auth import LoginPwdDocument
from core.model_util import BaseController, BaseDocument, BaseSolrSearcher
from sief.model import fields
from sief.tasks.email import (default_mail, default_mail_reset, mail,
                              default_subject, default_subject_reset)

# todo: move to role ?
USAGER_PERMISSIONS = []


def is_demandeur(usager):
    from sief.model.demande_asile import DemandeAsile
    return DemandeAsile.objects.filter(usager=usager.id).count()


def is_adult(usager):
    if not usager or not usager.date_naissance:
        return None

    today = datetime.now()
    birthday = usager.date_naissance
    age = today.year - birthday.year
    if today.month < birthday.month or (today.month == birthday.month and today.day < birthday.day):
        age -= 1
    return age >= 18


def generate_identifiant_agdref(usager):
    """
    :param usager: can be a regular Usager :class Document: or
    an :class UsagerRecueil: EmbeddedDocument
    :return: the new identifiant_agdref or None in case of error
    """
    for field in ['nom', 'prenoms', 'date_naissance', 'nationalites', 'sexe']:
        if not getattr(usager, field, None):
            return None
    # TODO: call agdref here
    import random
    usager.date_enregistrement_agdref = datetime.utcnow()
    usager.identifiant_agdref = 'fake-' + ''.join([random.choice('0123456789') for _ in range(5)])
    return usager.date_enregistrement_agdref


class UsagerController(BaseController):
    def get_current_permissions(self):
        return USAGER_PERMISSIONS

    def get_current_site_affecte(self):
        return None

    def get_current_site_rattache(self):
        return None

    def ensure_identifiant_agdref(self, save=False):
        """Create identifiant_agdref if it doesn't already exists"""
        if not self.document.identifiant_agdref:
            generate_identifiant_agdref(self.document)
            if save:
                self.document.save()

    def check_demandeur(self, fields):
        def _is_missing(value):
            return (value is None or
                    (isinstance(value, str) and value == '') or
                    (isinstance(value, (list, tuple, dict)) and not value))

        errors = {}
        if is_demandeur(self.document):
            for f in fields:
                if _is_missing(getattr(self.document, f, None)):
                    errors[f] = 'Champ requis pour un demandeur'
        return errors

    def is_user_valid(self):
        return True

    def init_basic_auth(self):
        self.document.basic_auth = LoginPwdDocument(login=self.document.identifiant_agdref)
        self.generate_password()

    def generate_password(self, length=12):
        from core.auth import encrypt_password, generate_password
        self.document.basic_auth.hashed_password = encrypt_password(generate_password())

    def break_password(self):
        """
        Set the password as dirty. Must be changed at next logon
        """
        self.document.basic_auth.change_password_next_login = True

    def restore_password(self):
        """
        Set the password as clean. Must not be changed at next logon
        """
        self.document.basic_auth.change_password_next_login = False

    def set_password(self, password):
        """Store the password encrypted (i.e. hashed&salted)"""
        from core.auth.tools import encrypt_password, check_password_strength
        if check_password_strength(password):
            self.document.basic_auth.hashed_password = encrypt_password(password)
            # Invalidate token
            self.document.basic_auth.reset_password_token = None
            self.document.basic_auth.reset_password_token_expire = datetime.utcnow()
            self.document.basic_auth.last_change_of_password = datetime.utcnow()
            return True
        return False

    # TODO : Change mail.front_url to match vls-ts url
    def reset_password(self, first=False):
        """ Reset password for a given user. Reset link is sent by mail"""
        hash = sha256()
        hash.update(datetime.utcnow().isoformat().encode())
        hash.update(mail.secret.encode())
        self.document.basic_auth.reset_password_token = hash.hexdigest()
        self.document.basic_auth.reset_password_token_expire = datetime.utcnow() + timedelta(days=1)
        if first:
            mail.send(subject=default_subject,
                      body=default_mail.format(str.join(' ', self.document.prenoms),
                                               self.document.nom,
                                               mail.front_url,
                                               self.document.email,
                                               hash.hexdigest(),
                                               mail.front_url_intranet),
                      recipient=self.document.email)
        else:
            mail.send(subject=default_subject_reset,
                      body=default_mail_reset.format(str.join(' ', self.document.prenoms),
                                                     self.document.nom,
                                                     mail.front_url,
                                                     self.document.email,
                                                     hash.hexdigest(),
                                                     mail.front_url_intranet),
                      recipient=self.document.email)
        if mail.debug:
            return self.document.basic_auth.reset_password_token

    def email_password_link(self):
        """ Lock account and send email to user """
        self.generate_password()
        self.reset_password(first=True)

    def arrived_in_france_at(self, arrival_date):
        self.document.date_entree_en_france = arrival_date

    def add_localisation(self, localisation):
        self.document.localisations.append(localisation)

    def add_coordonnees(self, telephone, email, adresse):
        self.document.telephone = telephone
        self.document.email = email

        localisation = Localisation(adresse=adresse)
        self.add_localisation(localisation)


class UsagerSearcher(BaseSolrSearcher):
    FIELDS = ('identifiant_agdref', 'date_enregistrement_agdref',
              'identifiant_dna', 'date_dna', 'identifiant_famille_dna',
              'ecv_valide',
              'nom', 'nom_usage', 'prenoms', 'sexe', 'date_naissance',
              'date_naissance_approximative', 'date_deces', 'pays_naissance',
              'ville_naissance', 'nationalites', 'date_naturalisation',
              'date_fuite', 'nom_pere', 'prenom_pere', 'identifiant_pere',
              'nom_mere', 'prenom_mere', 'identifiant_mere',
              'enfant_de_refugie', 'situation_familiale',
              'conjoint', 'telephone', 'email', 'langues',
              'langues_audition_OFPRA', 'numero_passeport',
              'date_expiration_passeport', 'sites_suiveurs',
              'representant_legal_nom', 'representant_legal_prenom',
              'date_depart', 'date_entree_en_france', 'prefecture_rattachee',
              'identifiants_eurodac')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.build_and_register_converter(
            'eloignement_date_execution', Eloignement.date_execution,
            extractor=lambda doc: doc.eloignement.date_execution if doc.eloignement else None)
        self.build_and_register_converter(
            'eloignement_date_decision', Eloignement.date_decision,
            extractor=lambda doc: doc.eloignement.date_decision if doc.eloignement else None)
        self.build_and_register_converter(
            'eloignement_execution', Eloignement.execution,
            extractor=lambda doc: doc.eloignement.execution if doc.eloignement else None)
        self.build_and_register_converter(
            'eloignement_delai_depart_volontaire', Eloignement.delai_depart_volontaire,
            extractor=lambda doc: (doc.eloignement.delai_depart_volontaire
                                   if doc.eloignement else None))
        self.build_and_register_converter(
            'eloignement_contentieux', Eloignement.contentieux,
            extractor=lambda doc: doc.eloignement.contentieux if doc.eloignement else None)
        self.build_and_register_converter(
            'eloignement_decision_contentieux', Eloignement.decision_contentieux,
            extractor=lambda doc: (doc.eloignement.decision_contentieux
                                   if doc.eloignement else None))
        self.build_and_register_converter(
            'grossesse_date_terme',
            Vulnerabilite.grossesse_date_terme,
            extractor=lambda doc: (doc.vulnerabilite.grossesse_date_terme
                                   if doc.vulnerabilite else None))

        self.build_and_register_converter(
            'grossesse',
            Vulnerabilite.grossesse,
            extractor=lambda doc: (doc.vulnerabilite.grossesse
                                   if doc.vulnerabilite else None))

        self.build_and_register_converter(
            'malvoyance',
            Vulnerabilite.malvoyance,
            extractor=lambda doc: (doc.vulnerabilite.malvoyance
                                   if doc.vulnerabilite else None))

        self.build_and_register_converter(
            'mobilite_reduite',
            Vulnerabilite.mobilite_reduite,
            extractor=lambda doc: (doc.vulnerabilite.mobilite_reduite
                                   if doc.vulnerabilite else None))

        self.build_and_register_converter(
            'malentendance',
            Vulnerabilite.malentendance,
            extractor=lambda doc: (doc.vulnerabilite.malentendance
                                   if doc.vulnerabilite else None))

        self.build_and_register_converter(
            'interprete_signe',
            Vulnerabilite.interprete_signe,
            extractor=lambda doc: (doc.vulnerabilite.interprete_signe
                                   if doc.vulnerabilite else None))

        self.build_and_register_converter(
            'vulnerabilite_date_saisie',
            Vulnerabilite.date_saisie,
            extractor=lambda doc: doc.vulnerabilite.date_saisie if doc.vulnerabilite else None)
        self.build_and_register_converter(
            'adresse', Localisation.adresse,
            extractor=lambda doc: doc.localisations[0].adresse if doc.localisations else None)


class Eloignement(EmbeddedDocument):
    date_execution = fields.DateTimeField(null=True)
    date_decision = fields.DateTimeField(required=True)
    execution = fields.BooleanField(null=True)
    delai_depart_volontaire = fields.IntField(null=True)
    contentieux = fields.BooleanField(null=True)
    decision_contentieux = fields.StringField(null=True)


class Localisation(EmbeddedDocument):
    adresse = fields.AddressField(required=True)
    date_maj = fields.DateTimeField(required=True, default=datetime.utcnow)
    organisme_origine = fields.StringField(default='PORTAIL',
                                           choices=['DNA', 'AGDREF', 'INEREC', 'PORTAIL'])


class Vulnerabilite(EmbeddedDocument):
    objective = fields.BooleanField(null=True)
    grossesse = fields.BooleanField(null=True)
    grossesse_date_terme = fields.DateTimeField(null=True)
    malvoyance = fields.BooleanField(null=True)
    malentendance = fields.BooleanField(null=True)
    interprete_signe = fields.BooleanField(null=True)
    mobilite_reduite = fields.BooleanField(null=True)
    absence_raison_medicale = fields.BooleanField(null=True)
    date_saisie = fields.DateTimeField(required=True, default=datetime.utcnow)


class Usager(BaseDocument):
    meta = {'controller_cls': UsagerController,
            'searcher_cls': UsagerSearcher,
            'indexes': ['prefecture_rattachee', 'identifiant_famille_dna', 'identifiants_eurodac']}

    id = fields.SequenceField(primary_key=True)
    identifiants_eurodac = fields.ListField(fields.EurodacIdField(), required=False)
    prefecture_rattachee = fields.ReferenceField('Prefecture')  # TODO: required ?
    transferable = fields.BooleanField(default=True)
    identifiant_agdref = fields.AgdrefIdField(null=True, unique=True, sparse=True)
    identifiant_portail_agdref = fields.StringField(required=False, null=True)
    date_enregistrement_agdref = fields.DateTimeField(null=True)
    identifiant_dna = fields.StringField(null=True, unique=True, sparse=True, max_length=19)
    date_dna = fields.DateTimeField(null=True)
    identifiant_famille_dna = fields.StringField(null=True, max_length=19)
    ecv_valide = fields.BooleanField(default=False)

    nom = fields.PatronymeField(required=True, max_length=30)
    origine_nom = fields.OrigineNom(null=True)
    nom_usage = fields.PatronymeField(null=True, max_length=30)
    origine_nom_usage = fields.OrigineNom(null=True)
    prenoms = fields.ListField(field=fields.PatronymeField(max_length=30), required=True)
    photo = fields.ReferenceField("Fichier", null=True)
    sexe = fields.SexeField(required=True)
    documents = fields.ListField(fields.ReferenceField("Fichier"))

    date_naissance = fields.DateNaissanceField(required=True)
    date_naissance_approximative = fields.BooleanField(null=True)
    date_deces = fields.DateTimeField(null=True)
    pays_naissance = fields.PaysField(required=True)
    ville_naissance = fields.StringField(required=True, max_length=30)
    nationalites = fields.ListField(fields.NationaliteField(), required=True)

    date_naturalisation = fields.DateTimeField(null=True)
    eloignement = fields.EmbeddedDocumentField(Eloignement, null=True)
    date_fuite = fields.DateTimeField(null=True)
    date_entree_en_france = fields.DateTimeField(null=True)

    nom_pere = fields.PatronymeField(null=True)
    prenom_pere = fields.PatronymeField(null=True)
    identifiant_pere = fields.ReferenceField('Usager', null=True)
    documents_pere = fields.ListField(fields.ReferenceField("Fichier"))
    nom_mere = fields.PatronymeField(null=True)
    prenom_mere = fields.PatronymeField(null=True)
    identifiant_mere = fields.ReferenceField('Usager', null=True)
    documents_mere = fields.ListField(fields.ReferenceField("Fichier"))

    enfant_de_refugie = fields.BooleanField(null=True)
    situation_familiale = fields.FamilyStatusField(required=True)

    representant_legal_nom = fields.PatronymeField(null=True)
    representant_legal_prenom = fields.PatronymeField(null=True)
    representant_legal_personne_morale = fields.BooleanField(null=True)
    representant_legal_personne_morale_designation = fields.StringField(null=True)
    conjoint = fields.ReferenceField('Usager', null=True)

    localisations = fields.ListField(fields.EmbeddedDocumentField('Localisation'))
    telephone = fields.PhoneField(null=True)
    email = fields.EmailField(null=True, max_length=50)

    langues = fields.ListField(fields.LangueIso6392Field())
    langues_audition_OFPRA = fields.ListField(fields.LangueOfpraField())
    numero_passeport = fields.StringField(null=True)
    date_expiration_passeport = fields.DateTimeField(null=True)

    sites_suiveurs = fields.ListField(fields.ReferenceField("Site"))
    vulnerabilite = fields.EmbeddedDocumentField('Vulnerabilite', null=True)

    basic_auth = fields.EmbeddedDocumentField(LoginPwdDocument, null=True)

    # TODO : move me on the Visa document
    vls_ts_numero_visa = fields.StringField(null=True)
