import pytest
from random import choice
from string import ascii_letters, digits
from datetime import datetime

from sief.model.fichier import Fichier
from sief.model.usager import Usager


@pytest.fixture
def usager_payload(ref_nationalites, ref_langues_ofpra, ref_langues_iso,
                   ref_pays, site_gu, **kwargs):
    photo = Fichier(name='photo.png').save()
    payload = {
        "nom": "Césaire",
        "origine_nom": "EUROPE",
        "prenoms": ["Aimé", "Fernand", "David"],
        "sexe": "M",
        "identifiant_portail_agdref": ''.join(choice(ascii_letters + digits) for _ in range(12)),
        "photo": str(photo.pk),
        "date_naissance": datetime(1913, 6, 26),
        "pays_naissance": ref_pays[0].to_embedded(),
        "ville_naissance": "Basse-Pointe",
        "nationalites": [{'code': str(ref_nationalites[0].pk)}],
        "situation_familiale": "VEUF",
        "langues": [{'code': str(e.pk)} for e in ref_langues_iso],
        "langues_audition_OFPRA": [{'code': str(ref_langues_ofpra[0].pk)}],
    }
    payload.update(**kwargs)
    return payload


@pytest.fixture
def usager(request, ref_nationalites, ref_langues_ofpra,
           ref_langues_iso, ref_pays, site_gu, **kwargs):
    photo = Fichier(name='photo.png').save()
    payload = {
        "nom": "Césaire",
        "prenoms": ["Aimé", "Fernand", "David"],
        "origine_nom": 'EUROPE',
        "sexe": "M",
        "identifiant_portail_agdref": ''.join(choice(ascii_letters + digits) for _ in range(12)),
        "photo": str(photo.pk),
        "date_naissance": datetime(1913, 6, 26),
        "pays_naissance": ref_pays[0].to_embedded(),
        "ville_naissance": "Basse-Pointe",
        "nationalites": [{'code': str(ref_nationalites[0].pk)}],
        "situation_familiale": "VEUF",
        "langues": [{'code': str(r.pk)} for r in ref_langues_iso],
        "langues_audition_OFPRA": [{'code': str(ref_langues_ofpra[0].pk)}],
        "prefecture_rattachee": site_gu.autorite_rattachement
    }
    payload.update(**kwargs)
    usager = Usager(**payload)
    usager.save()
    return usager


@pytest.fixture
def usager_with_credentials(request, usager_payload, password='P@ssw0rd'):
    usager_payload.update({
        'identifiant_agdref': ''.join(choice(digits) for _ in range(10)),
        'email': 'John.Doe@test.com'}
    )
    usager = Usager(**usager_payload)
    usager.controller
    usager.controller.init_basic_auth()
    usager.controller.set_password(password)
    usager._raw_password = password
    usager.save()
    return usager
