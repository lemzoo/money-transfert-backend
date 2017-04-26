from datetime import datetime, timedelta
from mongoengine import ValidationError, EmbeddedDocument
from hashlib import sha256
from flask import g, current_app
from flask.ext.principal import ActionNeed

from sief.tasks.email import (default_mail, default_mail_reset, mail,
                              default_subject, default_subject_reset)
from sief.model import fields
from sief.roles import ROLES
from core.model_util import (
    BaseController, BaseSolrSearcher, BaseDocument, ControlledDocument, Marshallable)
from core.auth.login_pwd_auth import LoginPwdDocument


class UtilisateurController(BaseController):

    def clean(self):
        if not self.document.basic_auth.hashed_password:
            raise ValidationError(errors={'mot_de_passe':
                                          'Ce champ est obligatoire'})

    def init_basic_auth(self):
        self.document.basic_auth = LoginPwdDocument(login=self.document.email)
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

    def reset_password(self, first=False):
        """Reset password for a given user. Reset link is sent by mail."""
        hash = sha256()
        hash.update(datetime.utcnow().isoformat().encode())
        hash.update(mail.secret.encode())
        self.document.basic_auth.reset_password_token = hash.hexdigest()
        self.document.basic_auth.reset_password_token_expire = datetime.utcnow() + timedelta(days=1)
        if first:
            mail.send(subject=default_subject,
                      body=default_mail.format(self.document.prenom,
                                               self.document.nom,
                                               mail.front_url,
                                               self.document.email,
                                               hash.hexdigest(),
                                               mail.front_url_intranet),
                      recipient=self.document.email)
        else:
            mail.send(subject=default_subject_reset,
                      body=default_mail_reset.format(self.document.prenom,
                                                     self.document.nom,
                                                     mail.front_url,
                                                     self.document.email,
                                                     hash.hexdigest(),
                                                     mail.front_url_intranet),
                      recipient=self.document.email)
        if mail.debug:
            return self.document.basic_auth.reset_password_token

    def email_password_link(self):
        """Lock account and send email to user."""
        self.generate_password()
        self.reset_password(first=True)

    def close_user(self, fin_validite=None):
        if not self.document.fin_validite:
            self.document.fin_validite = fin_validite or datetime.utcnow()
            return True
        else:
            # user already closed
            return False

    def get_accreditation_by_id(self, accr_id):
        """
        Get the accreditation by it id or raises
        AccreditationError if not found.
        """
        for accreditation in self.document.accreditations:
            if accreditation.id == accr_id:
                return accreditation
        else:
            raise AccreditationError("Cette habilitation n'existe pas")

    def set_current_accreditation(self, accreditation_id):
        """
        Set an accreditation to a user by using the accreditation_id by
        using the accreditation id sent on the request form.
        If the accreditation exist then we set the new accreditation
        to the user. If not, raise an AccreditationError.
        """
        try:
            accreditation = self.document.accreditations[accreditation_id]
            if not self.is_accreditation_valid(accreditation):
                raise AccreditationError("Cette habilitation n'est plus valide")
        except IndexError:
            raise AccreditationError("Vous ne disposez pas de cette habilitation"
                                     "dans la liste de vos habilitations")
        g._current_accreditation_id = accreditation_id

    def get_current_accreditation(self):
        current_accreditation_id = getattr(g, '_current_accreditation_id', None)
        if current_accreditation_id is None:
            # Return first valid, mostly usefull for tests
            return self.get_first_valid_accreditation()
        else:
            try:
                current_accreditation = self.document.accreditations[current_accreditation_id]
                if self.is_accreditation_valid(current_accreditation):
                    return current_accreditation
                return Accreditation()
            except IndexError:
                raise AccreditationError('Cette habilitation est invalide')

    def get_first_valid_accreditation(self):
        # No explicit accreditation to use, return first available
        for accreditation in self.document.accreditations:
            if self.is_accreditation_valid(accreditation):
                return accreditation
        # No accreditation found, return a default empty accreditation
        return Accreditation()

    def get_current_role(self):
        """
        Get the current role by using the current accreditation id
        """
        return self.get_current_accreditation().role

    def get_current_site_affecte(self):
        """
        Get the current site affecte by using the current accreditation id
        """
        return self.get_current_accreditation().site_affecte

    def get_current_site_rattache(self):
        """
        Get the current site affecte by using the current accreditation id
        """
        return self.get_current_accreditation().site_rattache

    def get_current_permissions(self):
        permissions = []
        role = self.get_current_role()
        if role:
            role_policies = current_app.config['ROLES'].get(role)
            if role_policies is None:  # Can be empty list
                current_app.logger.warning('user `%s` has unknow role `%s`' %
                                           (self.document.id, role))
            else:
                permissions += [pol.action_need for pol in role_policies]
        permissions += [ActionNeed(name) for name in self.document.permissions]
        return permissions

    def add_accreditation(self, role=None, site_rattache=None,
                          site_affecte=None, fin_validite=None):
        if not role and not site_affecte:
            raise AccreditationError('Un role ou un site affecté est requis')

        accreditations = self.document.accreditations
        accreditation = Accreditation(id=len(self.document.accreditations),
                                      role=role, site_rattache=site_rattache,
                                      site_affecte=site_affecte,
                                      fin_validite=fin_validite)

        if self._find_duplicate_accreditation(accreditations, accreditation):
            raise AccreditationError('Cette habilitation exite déjà')

        self.document.accreditations.append(accreditation)
        self.update_user_fin_validite()
        return accreditation

    def _find_duplicate_accreditation(self, accreditations, accreditation):
        return any(accr for accr in accreditations
                   if (accr.role == accreditation.role and
                       accr.site_affecte == accreditation.site_affecte))

    def invalidate_accreditation(self, accr_id, fin_validite=None):
        """
        Add an end of the validate for the accreditation.
        """
        fin_validite = fin_validite or datetime.utcnow()
        accreditation = self.get_accreditation_by_id(accr_id)
        if accreditation.fin_validite:
            raise AccreditationError('Cette habilitation est déjà invalide')
        accreditation.fin_validite = fin_validite
        self.update_user_fin_validite()
        return accreditation

    def update_user_fin_validite(self):
        fins_validite = [accr.fin_validite
                         for accr in self.document.accreditations]
        if not fins_validite or None in fins_validite:
            self.document.fin_validite = None
        else:
            self.document.fin_validite = sorted(fins_validite)[-1]

    def is_accreditation_valid(self, accreditation):
        return (not accreditation.fin_validite or
                accreditation.fin_validite > datetime.utcnow())

    def is_user_valid(self):
        if self.document.fin_validite:
            return self.document.fin_validite > datetime.utcnow()
        else:
            return True


class UtilisateurSearcher(BaseSolrSearcher):
    FIELDS = ('email', 'nom', 'fin_validite',
              'prenom', 'telephone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def accreditation_map_factory(fn, need_reduce=False):
            def accreditation_map(doc):
                items = [fn(s) for s in doc.accreditations]
                return items
            return accreditation_map

        self.build_and_register_converter(
            'accreditations_role', Accreditation.role,
            aliases=('accreditation_role',), multi=True,
            extractor=accreditation_map_factory(lambda accre: accre.role))
        self.build_and_register_converter(
            'accreditations_site_affecte', Accreditation.site_affecte,
            aliases=('accreditation_site_affecte',), multi=True,
            extractor=accreditation_map_factory(lambda accre: accre.site_affecte))
        self.build_and_register_converter(
            'accreditations_site_rattache', Accreditation.site_rattache,
            aliases=('accreditation_site_rattache',), multi=True,
            extractor=accreditation_map_factory(lambda accre: accre.site_rattache))
        self.build_and_register_converter(
            'accreditations_fin_validite', Accreditation.fin_validite,
            aliases=('accreditation_fin_validite',), multi=True,
            extractor=accreditation_map_factory(lambda accre: accre.fin_validite))


class AccreditationError(Exception):
    pass


class Accreditation(EmbeddedDocument):
    """
    Accreditation is corresponding to acces right
    """
    id = fields.IntField(required=True)
    role = fields.StringField(choices=list(ROLES.keys()), null=True)
    site_rattache = fields.ReferenceField('Site', null=True)
    site_affecte = fields.ReferenceField('Site', null=True)
    fin_validite = fields.DateTimeField(null=True)


class Preferences(EmbeddedDocument):
    """
    User preferences which will contains all the preferences of the user
    to enhance a user experience.
    """
    current_accreditation_id = fields.IntField(null=True)


class Utilisateur(BaseDocument):
    meta = {'controller_cls': UtilisateurController,
            'searcher_cls': UtilisateurSearcher,
            'unversionned_fields': ('preferences', ),
            'db_alias': 'default'}

    email = fields.EmailField(max_length=255, required=True, unique=True)
    permissions = fields.ListField(fields.StringField(), default=list)
    nom = fields.PatronymeField(required=True, min_length=1)
    prenom = fields.PatronymeField(required=True, min_length=1)
    telephone = fields.PhoneField(null=True)
    adresse = fields.AddressField(null=True)
    fin_validite = fields.DateTimeField(null=True)
    system_account = fields.BooleanField(null=False)

    accreditations = fields.ListField(fields.EmbeddedDocumentField(Accreditation), default=list)
    preferences = fields.EmbeddedDocumentField(Preferences, default=Preferences)
    # TODO : Delete this field with a migration script to clean database
    localisation = fields.AddressField(null=True)

    basic_auth = fields.EmbeddedDocumentField(LoginPwdDocument, null=True)

    # TODO : delete this fields after the datamodel migration
    password = fields.StringField(max_length=255)
    reset_password_token = fields.StringField(null=True)
    reset_password_token_expire = fields.DateTimeField(null=True)
    change_password_next_login = fields.BooleanField(null=True)
    last_change_of_password = fields.DateTimeField(null=True, default=datetime.utcnow)
