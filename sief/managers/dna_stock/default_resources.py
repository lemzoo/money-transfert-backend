from datetime import datetime

from sief.model.site import Prefecture, GU
from sief.model.utilisateur import Utilisateur
from sief.model.fichier import Fichier
from sief.model.fields import (AddressEmbeddedDocument,
                               ReferentialPaysEmbeddedDocument,
                               ReferentialLangueOfpraEmbeddedDocument,
                               ReferentialNationaliteEmbeddedDocument)


DEFAULT_PHOTO_DATA = b"""
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
"""


class DefaultRessources:

    """
    Retreive or create the resources needed to fill the required
    fields for the import
    """

    def __init__(self, prefix='loader', verbose=False):
        if verbose:
            self._verbose_print = print
        else:
            self._verbose_print = lambda *args, **kwargs: None
        self.now = datetime.utcnow()
        self.prefix = prefix
        self._verbose_print('Checking for Prefecture... ', end='', flush=True)
        self.pref = Prefecture.objects(libelle=prefix + '-Prefecture').first()
        self._verbose_print('Ok !' if self.pref else 'KO')
        self._verbose_print('Checking for GU... ', end='', flush=True)
        self.gu = GU.objects(libelle=prefix + '-GU').first()
        self._verbose_print('Ok !' if self.gu else 'KO')
        self._verbose_print('Checking for Utilisateur... ', end='', flush=True)
        self.user = Utilisateur.objects(email=prefix + '@system.com').first()
        self._verbose_print('Ok !' if self.user else 'KO')
        self._verbose_print('Checking for default Photo... ', end='', flush=True)
        self.photo = Fichier.objects(name=prefix + '-default-photo.png').first()
        self._verbose_print('Ok !' if self.photo else 'KO')
        self.pays_naissance = ReferentialPaysEmbeddedDocument(code='XXX')
        self.langue_OFPRA = ReferentialLangueOfpraEmbeddedDocument(code='FRE')
        self.nationalite = ReferentialNationaliteEmbeddedDocument(code='ZZZ')

    @property
    def has_missing(self):
        return not self.pref or not self.gu or not self.user or not self.photo

    def create_missing(self):
        from core.auth import generate_password
        if not self.pref:
            self._verbose_print('-> Creating missing Prefecture... ', end='', flush=True)
            self.pref = Prefecture(libelle=self.prefix + '-Prefecture', code_departement='000',
                                   adresse=AddressEmbeddedDocument(adresse_inconnue=True)).save()
            self._verbose_print('Ok !')
        if not self.gu:
            self._verbose_print('-> Creating missing GU... ', end='', flush=True)
            self.gu = GU(libelle=self.prefix + '-GU', autorite_rattachement=self.pref,
                         adresse=AddressEmbeddedDocument(adresse_inconnue=True)).save()
            self._verbose_print('Ok !')
        if not self.user:
            self._verbose_print('-> Creating missing Utilisateur... ', end='', flush=True)
            pwd = generate_password()
            self.user = Utilisateur(email=self.prefix + '@system.com',
                                    nom=self.prefix.capitalize(), prenom='System')
            self.user.controller.init_basic_auth()
            self.user.controller.set_password(pwd)
            self.user.save()
            self._verbose_print('Ok ! user : %s | password : %s' % (self.user.email, pwd))

        if not self.photo:
            self._verbose_print('-> Creating missing default photo... ', end='', flush=True)
            from base64 import decodebytes
            data = decodebytes(DEFAULT_PHOTO_DATA)
            self.photo = Fichier(name=self.prefix + '-default-photo.png',
                                 data=data).save()
            self._verbose_print('Ok !')
