import pytest

from tests import common
from tests.fixtures import *

from sief.model.demande_asile import DemandeAsile
from sief.permissions import POLICIES as p
from sief.model.usager import Vulnerabilite

@pytest.fixture
def demande_asile_payload(exploite, **kwargs):
    payload = {
        'usager': exploite.usager_1.usager_existant,
        'structure_guichet_unique': exploite.structure_guichet_unique,
        'structure_premier_accueil': exploite.structure_accueil,
        'referent_premier_accueil': exploite.agent_accueil,
        'date_demande': exploite.date_transmission,
        'agent_enregistrement': exploite.agent_enregistrement,
        'date_enregistrement': exploite.date_enregistrement,
        'date_entree_en_france': exploite.usager_1.date_entree_en_france,
        'date_depart': exploite.usager_1.date_depart,
        'condition_entree_france': exploite.usager_1.condition_entree_france,
        'conditions_exceptionnelles_accueil': exploite.usager_1.conditions_exceptionnelles_accueil,
        'enfants_presents_au_moment_de_la_demande': [
            e.usager_existant for e in exploite.enfants
            if e.present_au_moment_de_la_demande],
        'procedure': {
            'type': exploite.usager_1.type_procedure,
            'motif_qualification': exploite.usager_1.motif_qualification_procedure
        },
        'prefecture_rattachee': exploite.prefecture_rattachee
    }
    payload.update(kwargs)
    return payload


@pytest.fixture
def demande_asile_mobilite_reduite_false(request, demande_asile_payload):
    da = DemandeAsile(**demande_asile_payload)
    da.usager.vulnerabilite = Vulnerabilite(mobilite_reduite=False)
    da.usager.save()
    da.save()
    return da

@pytest.fixture
def demande_asile_mobilite_reduite_true(request, demande_asile_payload):
    da = DemandeAsile(**demande_asile_payload)
    da.usager.vulnerabilite = Vulnerabilite(mobilite_reduite=True)
    da.usager.save()
    da.save()
    return da

@pytest.fixture
def demande_asile_mobilite_reduite_undefined(request, demande_asile_payload):
    da = DemandeAsile(**demande_asile_payload)
    da.save()
    return da

class TestDemandeAsileVulnerabilite(common.BaseTest):

    def test_demande_asile_mobilite_reduite_has_default_value_set_to_False(self, user_with_site_affecte,
                                                                                  demande_asile_mobilite_reduite_false):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.usager.voir.name]
        user.save()
        route = '/demandes_asile/%s' % demande_asile_mobilite_reduite_false.pk
        r = user_req.get(route)
        assert r.status_code == 200
        route_usager = r.data['usager']['_links']['self']
        r_usager = user_req.get(route_usager)
        assert r_usager.status_code == 200
        assert r_usager.data['vulnerabilite']['mobilite_reduite'] == False

    def test_demande_asile_mobilite_reduite_has_value_set_to_True(self, user_with_site_affecte,
                                                                                  demande_asile_mobilite_reduite_true):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.usager.voir.name]
        user.save()
        route = '/demandes_asile/%s' % demande_asile_mobilite_reduite_true.pk
        r = user_req.get(route)
        assert r.status_code == 200
        route_usager = r.data['usager']['_links']['self']
        r_usager = user_req.get(route_usager)
        assert r_usager.status_code == 200
        assert r_usager.data['vulnerabilite']['mobilite_reduite'] == True

    def test_recueil_da_vulnerabilite__mobilite_is_undefined(self, user_with_site_affecte,
                                                   demande_asile_mobilite_reduite_undefined):

        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.usager.voir.name]
        user.save()
        route = '/demandes_asile/%s' % demande_asile_mobilite_reduite_undefined.pk
        r = user_req.get(route)
        assert r.status_code == 200
        route_usager = r.data['usager']['_links']['self']
        r_usager = user_req.get(route_usager)
        assert r_usager.status_code == 200
