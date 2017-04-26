from sief.model.utilisateur import Utilisateur
from sief.model.fichier import Fichier
from sief.model.referentials import LangueIso6392, LangueOfpra, Pays, Nationalite
from sief.model.site import Site, StructureAccueil, GU, Prefecture, Creneau
from sief.model.usager import Usager
from sief.model.recueil_da import RecueilDA
from sief.model.demande_asile import DemandeAsile
from sief.model.droit import Droit
from sief.model.telemOfpra import TelemOfpra
from flask_mail import Mail


def init_app(app):
    pass

__all__ = ('Utilisateur', 'Fichier', 'TelemOfpra',
           'LangueIso6392', 'LangueOfpra', 'Pays', 'Nationalite',
           'Site', 'StructureAccueil', 'GU', 'Prefecture', 'Creneau',
           'Usager', 'RecueilDA', 'DemandeAsile', 'Droit', 'init_app', 'Mail')
