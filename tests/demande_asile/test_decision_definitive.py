import pytest
from datetime import datetime
import copy

from tests import common
from tests.fixtures import *

from sief.model.demande_asile import DemandeAsile, DecisionDefinitive
from sief.permissions import POLICIES as p


@pytest.fixture
def da_decision_def(request, da_instruction_ofpra):
    da_instruction_ofpra.decisions_definitives = [DecisionDefinitive(
        nature='CR',
        date=datetime.utcnow(),
        date_premier_accord=datetime.utcnow(),
        date_notification=datetime.utcnow(),
        entite='OFPRA')]
    da_instruction_ofpra.controller.passer_decision_definitive()
    da_instruction_ofpra.save()
    return da_instruction_ofpra


class TestDemandeAsileDecisionDefinitive(common.BaseTest):

    def test_links_single(self, user_with_site_affecte, da_decision_def):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s' % da_decision_def.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.modifier_ofpra.name,
                            p.demande_asile.requalifier_procedure.name,
                            p.demande_asile.editer_attestation.name,
                            p.demande_asile.finir_procedure.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'decision_definitive', 'finir_procedure'])

    def test_orientation_update(self, user_with_site_affecte, da_decision_def):
        user = user_with_site_affecte
        # Orientation stuff can no longer be modified
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.orienter.name]
        user.save()
        route = '/demandes_asile/%s/orientation' % da_decision_def.pk
        payload = {
            'hebergement': {
                'date_sortie_hebergement': datetime.utcnow().isoformat()
            },
            'ada': {
                'date_ouverture': datetime.utcnow().isoformat(),
                'montant': 1000.42
            },
            'agent_orientation': 'dn@-agent-007'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r

    def test_add_decision_definitive(self, user_with_site_affecte, da_decision_def):
        user = user_with_site_affecte
        # Can append multiple decision definitives...
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s/decisions_definitives' % da_decision_def.pk
        payload = {
            'nature': 'TF',
            'date': datetime.utcnow().isoformat(),
            'date_premier_accord': datetime.utcnow().isoformat(),
            'date_notification': datetime.utcnow().isoformat(),
            'entite': 'CNDA',
            'numero_skipper': 'Skiango'
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.modifier_ofpra.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert len(r.data['decisions_definitives']) == 2

    def test_decision_definitive_resultat(self, user_with_site_affecte, da_decision_def):
        user = user_with_site_affecte
        # Can append multiple decision definitives...
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.modifier_ofpra.name]
        user.save()
        route = '/demandes_asile/%s' % da_decision_def.pk
        # Add a first decision with accord
        payload = {
            'nature': 'ANP',  # nature for accord
            'date': datetime.utcnow().isoformat(),
            'date_premier_accord': datetime.utcnow().isoformat(),
            'date_notification': datetime.utcnow().isoformat(),
            'entite': 'OFPRA',
        }
        r = user_req.post(route + '/decisions_definitives', data=payload)
        assert r.status_code == 201, r
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data.get('decision_definitive_resultat', '<undefined>') == 'ACCORD'
        # Now another decision with refus should replace the first one
        payload = {
            'nature': 'IAM',  # nature for rejet
            'date': datetime.utcnow().isoformat(),
            'date_premier_accord': datetime.utcnow().isoformat(),
            'date_notification': datetime.utcnow().isoformat(),
            'entite': 'CNDA',
            'numero_skipper': 'Skiango'
        }
        r = user_req.post(route + '/decisions_definitives', data=payload)
        assert r.status_code == 201, r
        route = '/demandes_asile/%s' % da_decision_def.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data.get('decision_definitive_resultat', '<undefined>') == 'REJET'

    def test_fin_procedure(self, user_with_site_affecte, da_decision_def):
        user = user_with_site_affecte
        # Can append multiple decision definitives...
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s/fin_procedure' % da_decision_def.pk
        payload = {
            'motif_refus': 'motif'
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.finir_procedure.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'FIN_PROCEDURE'

    def test_add_decision_definitive_INEREC(self, user_with_site_affecte, da_decision_def):
        user = user_with_site_affecte
        # Can append multiple decision definitives...
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s/decisions_definitives_inerec' % da_decision_def.identifiant_inerec
        payload = {
            'nature': 'TF',
            'date': datetime.utcnow().isoformat(),
            'date_premier_accord': datetime.utcnow().isoformat(),
            'date_notification': datetime.utcnow().isoformat(),
            'entite': 'CNDA',
            'numero_skipper': 'Skiango'
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.modifier_stock_dna.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r
        assert len(r.data['decisions_definitives']) == 2
