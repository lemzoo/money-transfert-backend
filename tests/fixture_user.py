import pytest
from datetime import datetime
from functools import partial

from sief.model.utilisateur import Utilisateur
from core.auth.login_pwd_auth import LoginPwdDocument

from tests import fixture_site


def set_user_accreditation(user, role=None, site_affecte=None,
                           site_rattache=None, fin_validite=None):
    """
    Helper function to define a single main accreditation for the given user.
    """
    accreditation_kwargs = {}
    if role:
        accreditation_kwargs['role'] = role
    if site_affecte:
        accreditation_kwargs['site_affecte'] = site_affecte
    if site_rattache:
        accreditation_kwargs['site_rattache'] = site_rattache
    if fin_validite:
        accreditation_kwargs['fin_validite'] = fin_validite
    user.accreditations.clear()
    if accreditation_kwargs:
        user.controller.add_accreditation(**accreditation_kwargs)


@pytest.fixture
def user(request, password='P@ssw0rd', nom='User', prenom='John', **kwargs):
    if 'email' not in kwargs:
        kwargs['email'] = '%s.%s@test.com' % (prenom, nom)
    new_user = Utilisateur(nom=nom, prenom=prenom, **kwargs)
    new_user.basic_auth = LoginPwdDocument(login=kwargs['email'])
    new_user.controller.set_password(password)
    new_user.save()
    new_user._raw_password = password
    # Really handy function, better monkeypatch it into user
    new_user.test_set_accreditation = partial(set_user_accreditation, new_user)
    return new_user


@pytest.fixture
def user_with_accreditations(request, site, password='P@ssw0rd',
                             nom='Userwithaccreditations', prenom='Bob',
                             **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    date_in_the_past = datetime(2014, 12, 31)
    new_user.controller.add_accreditation(
        role='ADMINISTRATEUR_PREFECTURE',
        site_affecte=site,
        site_rattache=site,
        fin_validite=date_in_the_past
    )
    new_user.controller.add_accreditation(
        role='RESPONSABLE_GU_ASILE_PREFECTURE',
        site_affecte=site,
        site_rattache=site
    )
    new_user.controller.add_accreditation(
        role='RESPONSABLE_ZONAL',
        site_affecte=site,
        site_rattache=site
    )
    new_user.save()
    return new_user


@pytest.fixture
def user_with_site_affecte(request, site_gu, password='P@ssw0rd',
                           nom="Userwithsiteaffecte", prenom="Jane"):
    new_user = user(request, password, nom, prenom)
    new_user.controller.add_accreditation(site_affecte=site_gu)
    new_user.save()
    return new_user


@pytest.fixture
def another_user(request, password='OtherP@ssw0rd',
                 nom="Anotheruser", prenom="Jane"):
    return user(request, password, nom, prenom)


@pytest.fixture
def administrateur(request, password='P@ssw0rd', nom='Trateur',
                   prenom='Adminis', **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    new_user.controller.add_accreditation(role='ADMINISTRATEUR')
    new_user.save()
    return new_user


@pytest.fixture
def administrateur_national(request, password='P@ssw0rd', nom='National',
                            prenom='Administrateur', **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    new_user.controller.add_accreditation(role='ADMINISTRATEUR_NATIONAL')
    new_user.save()
    return new_user


@pytest.fixture
def administrateur_prefecture(request, site_prefecture, password='P@ssw0rd',
                              nom='Prefecture', prenom='Administrateur',
                              **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    new_user.controller.add_accreditation(role='ADMINISTRATEUR_PREFECTURE',
                                          site_affecte=site_prefecture)
    new_user.save()
    return new_user


@pytest.fixture
def responsable_gu_asile_prefecture(request, site_gu, site_prefecture,
                                    password='P@ssw0rd', nom='Asile-prefect',
                                    prenom='Responsable-gu', **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    new_user.controller.add_accreditation(
        role='RESPONSABLE_GU_ASILE_PREFECTURE', site_affecte=site_gu,
        site_rattache=site_prefecture)
    new_user.save()
    return new_user


@pytest.fixture
def gestionnaire_gu_asile_prefecture(request, site_gu, site_prefecture,
                                     password='P@ssw0rd', nom='Asile-prefect',
                                     prenom='Gestionnaire-gu', **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    new_user.controller.add_accreditation(
        role='GESTIONNAIRE_GU_ASILE_PREFECTURE', site_affecte=site_gu,
        site_rattache=site_prefecture)
    new_user.save()
    return new_user


@pytest.fixture
def administrateur_pa(request, site_structure_accueil, password='P@ssw0rd',
                      nom='Pa', prenom='Administrateur', **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    new_user.controller.add_accreditation(
        role='ADMINISTRATEUR_PA',
        site_affecte=site_structure_accueil)
    new_user.save()
    return new_user


@pytest.fixture
def responsable_pa(request, site_structure_accueil, password='P@ssw0rd',
                   nom='Pa', prenom='Responsable', **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    new_user.controller.add_accreditation(
        role='RESPONSABLE_PA', site_affecte=site_structure_accueil,
        site_rattache=site_structure_accueil)
    new_user.save()
    return new_user


@pytest.fixture
def gestionnaire_pa(request, site_structure_accueil, password='P@ssw0rd',
                    nom='Pa', prenom='Gestionnaire', **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    new_user.controller.add_accreditation(
        role='GESTIONNAIRE_PA', site_affecte=site_structure_accueil,
        site_rattache=site_structure_accueil)
    new_user.save()
    return new_user


@pytest.fixture
def gestionnaire_titres(request, site_prefecture, password='P@ssw0rd',
                 nom='Pa', prenom='Gestionnaire', **kwargs):
    new_user = user(request, password, nom, prenom, **kwargs)
    new_user.controller.add_accreditation(
        role='GESTIONNAIRE_DE_TITRES',
        site_affecte=site_prefecture.id,
        site_rattache=site_prefecture.id
    )
    new_user.save()
    return new_user