import pytest
from datetime import datetime
from uuid import uuid4
from datetime import datetime

from sief.model.site import Prefecture, GU, StructureAccueil, EnsembleZonal


DEFAULT_SITE_PAYLOAD = {
    "type": "Prefecture",
    "libelle": "Préfecture de Bordeaux",
    "code_departement": "331",
    "adresse": {
        'complement': "appartement 4, 2eme étage",
        'identifiant_ban': "33063_5730_e530d4",
        'numero_voie': "3",
        'voie': "3 Place Lucien Victor Meunier",
        'code_insee': "33000",
        'code_postal': "33000",
        'ville': "Bordeaux",
        'longlat': [-0.586827, 44.84371],
    }
}

DEFAULT_UNKNOWN_ADDRESS_SITE_PAYLOAD = {
    "type": "Prefecture",
    "libelle": "Préfecture de Unknown",
    "code_departement": "331",
    "adresse": {
        "adresse_inconnue": True
    }
}

DEFAULT_SITE_MODELE_PAYLOAD = {
    "libelle": "Modèle QUOTIDIEN n°1",
    "type": "QUOTIDIEN",
    "plages": [{
        "plage_debut": datetime(2015, 6, 22, 12, 44, 32),
        "plage_fin": datetime(2015, 6, 22, 15, 44, 32),
        "plage_guichets": 5,
        "duree_creneau": 45,
        "marge": 30,
        "marge_initiale": False
    }]
}


@pytest.fixture
def site(request):
    return site_prefecture(request)


@pytest.fixture
def site_prefecture(request):
    payload = DEFAULT_SITE_PAYLOAD.copy()
    del payload["type"]
    payload["libelle"] += ' - ' + uuid4().hex
    new_site = Prefecture(**payload)
    new_site.save()
    return new_site


@pytest.fixture
def site_gu(request, site_prefecture):
    payload = {
        "libelle": "GU de Bordeaux - %s" % uuid4().hex,
        "autorite_rattachement": site_prefecture,
        "adresse": DEFAULT_SITE_PAYLOAD["adresse"]
    }
    new_site = GU(**payload)
    new_site.save()
    return new_site


@pytest.fixture
def site_structure_accueil(request, site_gu):
    payload = {
        "libelle": "Structure d'accueil de Bordeaux - %s" % uuid4().hex,
        "adresse": DEFAULT_SITE_PAYLOAD["adresse"],
        "guichets_uniques": [site_gu]
    }
    new_site = StructureAccueil(**payload)
    new_site.save()
    new_site.libelle = "Structure d'accueil de Bordeaux - %s" % new_site.pk
    new_site.save()
    return new_site


@pytest.fixture
def site_ensemble_zonal(request, site_prefecture):
    payload = {
        "libelle": "Ensemble Zonal de Bordeaux - %s" % uuid4().hex,
        "adresse": DEFAULT_SITE_PAYLOAD["adresse"],
        "prefectures": [site_prefecture]
    }
    new_site = EnsembleZonal(**payload)
    new_site.save()
    return new_site
