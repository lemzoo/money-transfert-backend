import pytest
from datetime import datetime

from tests import common
from tests.fixtures import *
from string import ascii_letters, digits
from random import choice

from sief.model.usager import Usager
from sief.model.fichier import Fichier
from sief.permissions import POLICIES as p


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
def photo(request):
    return Fichier(name='photo.png').save()


class TestRabbitFeatureFlippingDeactivate(common.BaseRabbitBrokerTest):

    def test_update_localisations(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name, p.usager.modifier.name]
        user.save()
        payload = {
            'adresse': {
                "ville": "Saint-Sylvain-d'Anjou",
                "code_insee": "49323",
                "code_postal": "49480",
                "voie": "Rue du Dery",
                "numero_voie": "49",
            },
            "organisme_origine": "PORTAIL"
        }
        route = '/usagers/{}'.format(usager.pk)
        ret = user_req.post(route + '/localisations', data=payload)
        assert ret.status_code == 200, ret


class TestRabbitFeatureFlippingActivate(common.BaseRabbitBrokerTest):

    def setup_class(cls):
        super().setup_class(config={
            'FF_ENABLE_RABBIT': True
        })

    def test_update_localisations(self, user_with_site_affecte, usager):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.usager.voir.name, p.usager.modifier.name]
        user.save()
        payload = {
            'adresse': {
                "ville": "Saint-Sylvain-d'Anjou",
                "code_insee": "49323",
                "code_postal": "49480",
                "voie": "Rue du Dery",
                "numero_voie": "49",
            },
            "organisme_origine": "PORTAIL"
        }
        route = '/usagers/{}'.format(usager.pk)
        ret = user_req.post(route + '/localisations', data=payload)
        assert ret.status_code == 200, ret
