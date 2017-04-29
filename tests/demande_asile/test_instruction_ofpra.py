import pytest
from datetime import datetime
import copy

from tests import common
from tests.fixtures import *

from sief.model.demande_asile import DemandeAsile
from sief.permissions import POLICIES as p


@pytest.fixture
def da_instruction_ofpra(request, da_attente_ofpra):
    da_attente_ofpra.controller.introduire_ofpra(
        identifiant_inerec='123467890',
        date_introduction_ofpra=datetime.utcnow())
    da_attente_ofpra.save()
    return da_attente_ofpra


class TestDemandeAsileEnCoursDublin(common.BaseTest):

    def test_links_single(self, user_with_site_affecte, da_instruction_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s' % da_instruction_ofpra.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.modifier_ofpra.name,
                            p.demande_asile.requalifier_procedure.name,
                            p.demande_asile.editer_attestation.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'editer_attestation',
                                'requalifier_procedure', 'decision_definitive'])

    def test_orientation_update(self, user_with_site_affecte, da_instruction_ofpra):
        user = user_with_site_affecte
        # Orientation stuff can still be modified
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.orienter.name]
        user.save()
        route = '/demandes_asile/%s/orientation' % da_instruction_ofpra.pk
        payload = {
            'hebergement': {
                'date_sortie_hebergement': datetime.utcnow().isoformat()
            },
            'ada': {
                'date_ouverture': datetime.utcnow().isoformat(),
                'montant': 1000.42
            },
            'agent_orientation': 'dn@-agent-007',
            'date_orientation': '2015-06-11T12:22:37+00:00'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['agent_orientation'] == 'dn@-agent-007'
        assert r.data['date_orientation'] == '2015-06-11T12:22:37+00:00'
        assert 'date_sortie_hebergement' in r.data.get('hebergement', {})
        assert 'ada' in r.data and r.data['ada']['montant'] == 1000.42

    def test_switch_decision_definitive(self, user_with_site_affecte, da_instruction_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s/decisions_definitives' % da_instruction_ofpra.pk
        payload = {
            'nature': 'CR',
            'date': datetime.utcnow().isoformat(),
            'date_premier_accord': datetime.utcnow().isoformat(),
            'date_notification': datetime.utcnow().isoformat(),
            'entite': 'OFPRA'
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.modifier_ofpra.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 201, r

    def test_requalification(self, user_with_site_affecte, da_instruction_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        da_instruction_ofpra.procedure.type = 'NORMALE'
        da_instruction_ofpra.save()
        route = '/demandes_asile/%s/requalifications' % da_instruction_ofpra.pk
        payload = {
            'type': 'ACCELEREE',
            'acteur': 'PREFECTURE',
            'motif_qualification': 'AD171',
            'date_notification': datetime.utcnow().isoformat()
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.requalifier_procedure.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EN_COURS_INSTRUCTION_OFPRA'
        payload['type'] = 'DUBLIN'
        payload['motif_qualification'] = 'FAML'
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EN_COURS_PROCEDURE_DUBLIN'

    def test_requalification_no_motif(self, user_with_site_affecte, da_instruction_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        da_instruction_ofpra.procedure.type = 'NORMALE'
        da_instruction_ofpra.save()
        route = '/demandes_asile/%s/requalifications' % da_instruction_ofpra.pk
        payload = {
            'type': 'ACCELEREE',
            'acteur': 'PREFECTURE',
            'date_notification': datetime.utcnow().isoformat()
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.requalifier_procedure.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r
        assert r.data['_errors'][
            0] == "Le motif de qualification est obligatoire pour une requalification effectuée en préfecture."

    def test_requalification_no_motif_OFPRA(self, user_with_site_affecte, da_instruction_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        da_instruction_ofpra.procedure.type = 'NORMALE'
        da_instruction_ofpra.save()
        route = '/demandes_asile/%s/requalifications' % da_instruction_ofpra.pk
        payload = {
            'type': 'ACCELEREE',
            'acteur': 'OFPRA',
            'date_notification': datetime.utcnow().isoformat()
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.requalifier_procedure.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 200

    # OFPRA had to change procedure.type. Other can change motif or type + motif
    def test_requalification_same_type(self, user_with_site_affecte, da_instruction_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        da_instruction_ofpra.procedure.type = 'NORMALE'
        da_instruction_ofpra.save()
        route = '/demandes_asile/%s/requalifications' % da_instruction_ofpra.pk
        payload = {
            'type': da_instruction_ofpra.procedure.type,
            'motif_qualification': 'ND31',
            'acteur': 'PREFECTURE',
            'date_notification': datetime.utcnow().isoformat()
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.requalifier_procedure.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EN_COURS_INSTRUCTION_OFPRA'

    # OFPRA had to change procedure.type. Other can change motif or type + motif
    def test_requalification_same_type_OFPRA(self, user_with_site_affecte, da_instruction_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        da_instruction_ofpra.procedure.type = 'NORMALE'
        da_instruction_ofpra.save()
        route = '/demandes_asile/%s/requalifications' % da_instruction_ofpra.pk
        payload = {
            'type': da_instruction_ofpra.procedure.type,
            'acteur': 'OFPRA',
            'date_notification': datetime.utcnow().isoformat()
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.requalifier_procedure.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r
        assert r.data['_errors'][
            0] == "Impossible de requalifier sans changer le type de procédure"

    # OFPRA had to change procedure.type. Other can change motif or type + motif
    def test_requalification_same_type_motif(self, user_with_site_affecte, da_instruction_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        da_instruction_ofpra.procedure.type = 'NORMALE'
        da_instruction_ofpra.save()
        route = '/demandes_asile/%s/requalifications' % da_instruction_ofpra.pk
        payload = {
            'type': da_instruction_ofpra.procedure.type,
            'motif_qualification': da_instruction_ofpra.procedure.motif_qualification,
            'acteur': 'PREFECTURE',
            'date_notification': datetime.utcnow().isoformat()
        }
        # Need permission to do it
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.requalifier_procedure.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r
        assert r.data['_errors'][
            0] == "Impossible de requalifier sans changer le motif de qualification"
