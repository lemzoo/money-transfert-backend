import pytest
from datetime import datetime
from freezegun import freeze_time

from tests import common
from tests.fixtures import *

from sief.model.demande_asile import DemandeAsile
from sief.permissions import POLICIES as p


@freeze_time("2000-01-01")
@pytest.fixture
def da_orientation_payload(exploite, **kwargs):
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
            'motif_qualification': exploite.usager_1.motif_qualification_procedure,
            'date_notification': datetime.utcnow()
        },
        'prefecture_rattachee': exploite.prefecture_rattachee,
        'recueil_da_origine': exploite.id
    }
    payload.update(kwargs)
    return payload


@pytest.fixture
def da_orientation(request, da_orientation_payload):
    da = DemandeAsile(**da_orientation_payload)
    da.usager.identifiant_dna = "23456789"
    da.usager.save()
    da.save()
    return da


@pytest.fixture
def da_orientation_conjoint(request, exploite, da_orientation):
    payload = {
        'usager': exploite.usager_2.usager_existant,
        'type_demandeur': 'CONJOINT',
        'structure_guichet_unique': exploite.structure_guichet_unique,
        'structure_premier_accueil': exploite.structure_accueil,
        'referent_premier_accueil': exploite.agent_accueil,
        'date_demande': exploite.date_transmission,
        'agent_enregistrement': exploite.agent_enregistrement,
        'date_enregistrement': exploite.date_enregistrement,
        'condition_entree_france': exploite.usager_2.condition_entree_france,
        'conditions_exceptionnelles_accueil': exploite.usager_2.conditions_exceptionnelles_accueil,
        'motif_conditions_exceptionnelles_accueil': exploite.usager_2.motif_conditions_exceptionnelles_accueil,
        'demande_asile_principale': da_orientation,
        'procedure': {
            'type': exploite.usager_2.type_procedure,
            'motif_qualification': exploite.usager_2.motif_qualification_procedure
        },
        'prefecture_rattachee': exploite.prefecture_rattachee
    }
    da = DemandeAsile(**payload)
    da.save()
    return da


class TestDemandeAsileOrientation(common.BaseTest):

    def test_links_list(self, user_with_site_affecte):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        r = user_req.get('/demandes_asile')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'root'])

    def test_links_single(self, user_with_site_affecte, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s' % da_orientation.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])
        user.permissions.append(p.demande_asile.orienter.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'orienter'])
        user.permissions = [p.demande_asile.voir.name, p.historique.voir.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'history', 'parent'])

    def test_opc(self, user, da_orientation, da_orientation_conjoint):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.prefecture_rattachee.sans_limite.name]
        # Need rights
        r = user_req.patch('/demandes_asile/%s' % da_orientation.pk, data={
            'acceptation_opc': True})
        assert r.status_code == 403, r
        # Provide them
        user.permissions.append(p.demande_asile.modifier.name)
        user.save()
        # Principal cannot be linked to a conjoint
        r = user_req.patch('/demandes_asile/%s' % da_orientation.pk, data={
            'acceptation_opc': True})
        assert r.status_code == 200, r
        assert r.data['acceptation_opc'] == True
        # Can change it multiple times
        r = user_req.patch('/demandes_asile/%s' % da_orientation.pk, data={
            'acceptation_opc': False})
        assert r.status_code == 200, r
        assert r.data['acceptation_opc'] == False

    def test_bad_fields(self, user_with_site_affecte, da_orientation, da_orientation_conjoint):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.modifier.name]
        user.save()
        # Principal cannot be linked to a conjoint
        r = user_req.patch('/demandes_asile/%s' % da_orientation.pk, data={
            'demande_asile_principale': str(da_orientation_conjoint.id)})
        assert r.status_code == 400, r
        # Conjoint cannot have children
        r = user_req.patch('/demandes_asile/%s' % da_orientation_conjoint.pk, data={
            'enfants_presents_au_moment_de_la_demande': [
                str(e.id) for e in da_orientation['enfants_presents_au_moment_de_la_demande']]})
        assert r.status_code == 400, r

    def test_bad_orientation(self, user_with_site_affecte, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.orienter.name]
        user.save()
        payload = {
            'hebergement': {
                'type': 'CADA',
                'date_entre_hebergement': "2015-06-10T03:12:58+00:00"
            },
            'date_orientation': '2015-06-11T12:22:37+00:00'
            # missing agent_orientation
        }
        route = '/demandes_asile/%s/orientation' % da_orientation.pk
        user.save()
        payload['agent_orientation'] = 'dn@-agent-007'
        payload['date_orientation'] = '2015-06-11T12:22:37+00:00'
        # OPC is not part of the orientation
        payload['acceptation_opc'] = True,
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r
        # Finally make sure we can do the orientation
        del payload['acceptation_opc']
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r

    def test_do_orientation(self, user_with_site_affecte, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        payload = {
            'hebergement': {
                'type': 'CADA',
                'date_entre_hebergement': "2015-06-10T03:12:58+00:00"
            },
            'agent_orientation': 'dn@-agent-007',
            'date_orientation': '2015-06-11T12:22:33+00:00'
        }
        route = '/demandes_asile/%s/orientation' % da_orientation.pk
        # Need permission...
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # ...provide them
        user.permissions.append(p.demande_asile.orienter.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'PRETE_EDITION_ATTESTATION'
        assert r.data['agent_orientation'] == 'dn@-agent-007'
        assert r.data['date_orientation'] == '2015-06-11T12:22:33+00:00'
        assert r.data.get('hebergement', '<not_set>') == payload['hebergement']
        # Finally, Can redo the orientation if needed
        payload = {
            'hebergement': {
                'date_sortie_hebergement': "2015-06-10T03:12:58+00:00"
            },
            'ada': {
                'date_ouverture': "2015-06-10T03:12:58+00:00",
                'montant': 1000.42
            },
            'date_orientation': '2015-06-11T12:22:37+00:00'
            # agent_orientation is missing so far...
        }
        user.permissions.append(p.demande_asile.orienter.name)
        user.save()
        # Provide it and we're good to go
        payload['agent_orientation'] = 'dn@-agent-008'
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['date_orientation'] == '2015-06-11T12:22:37+00:00'
        assert r.data['agent_orientation'] == 'dn@-agent-008'
        assert 'date_sortie_hebergement' in r.data.get('hebergement', {})
        assert 'ada' in r.data and r.data['ada']['montant'] == 1000.42


class TestPaginationDemandeAsile(common.BaseTest):

    def test_paginate_da(self, user_with_site_affecte, da_orientation_payload):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        DemandeAsile.drop_collection()
        # Start by creating a lot of da
        for i in range(50):
            da = DemandeAsile(**da_orientation_payload)
            da.save()
        # Now let's test the pagination !
        common.pagination_testbed(user_req, '/demandes_asile')
