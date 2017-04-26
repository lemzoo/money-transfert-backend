import pytest
from datetime import datetime
import copy

from tests import common
from tests.fixtures import *

from sief.model.demande_asile import DemandeAsile
from sief.permissions import POLICIES as p


@pytest.fixture
def da_en_cours_dublin(request, da_prete_ea):
    u = user(request, nom='EditionAttestation', prenom='Setter')
    u.save()
    da_prete_ea.procedure.type = 'DUBLIN'
    da_prete_ea.procedure.motif_qualification = 'EAEA'
    payload = {'date_debut_validite': datetime.utcnow(),
               'date_fin_validite': datetime.utcnow()}
    da_prete_ea.controller.editer_attestation(u, **payload)
    da_prete_ea.save()
    return da_prete_ea


class TestDemandeAsileEnCoursDublin(common.BaseTest):

    def test_links_single(self, user_with_site_affecte, da_en_cours_dublin):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s' % da_en_cours_dublin.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.modifier_dublin.name,
                            p.demande_asile.requalifier_procedure.name,
                            p.demande_asile.editer_attestation.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent', 'editer_attestation',
                                'finir_procedure', 'requalifier_procedure',
                                'modifier_dublin'])

    def test_requalification(self, user_with_site_affecte, da_en_cours_dublin):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s/requalifications' % da_en_cours_dublin.pk
        payload = {
            'type': 'NORMALE',
            'acteur': 'PREFECTURE',
            'motif_qualification': 'ND171',
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
        assert r.data['statut'] == 'PRETE_EDITION_ATTESTATION'

    def test_bad_requalification(self, user_with_site_affecte, da_en_cours_dublin):
        user = user_with_site_affecte
        # Cannot switch to any state !
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.requalifier_procedure.name]
        user.save()
        route = '/demandes_asile/%s/requalifications' % da_en_cours_dublin.pk
        default_payload = {
            'type': 'NORMALE',
            'acteur': 'OFPRA',
            'date_notification': datetime.utcnow().isoformat()
        }
        for (key, value) in (
                ('type', common.NOT_SET), ('acteur', common.NOT_SET),
                ('date_notification', common.NOT_SET),
                ('date_notification', None),
                ('bad', 'field'), ('type', None), ('acteur', None),
                ('type', 'bad'), ('date_notification', 'not a date'),
                # Cannot have a requalification leading to the same procedure
                ('type', 'DUBLIN')
        ):
            payload = copy.deepcopy(default_payload)
            common.update_payload(payload, key, value)
            r = user_req.post(route, data=payload)
            assert r.status_code == 400, (key, value)
            da_en_cours_dublin.reload()
            assert da_en_cours_dublin.statut == 'EN_COURS_PROCEDURE_DUBLIN'

    def test_orientation_update(self, user_with_site_affecte, da_en_cours_dublin):
        user = user_with_site_affecte
        # Orientation stuff can still be modified
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.orienter.name]
        user.save()
        route = '/demandes_asile/%s/orientation' % da_en_cours_dublin.pk
        payload = {
            'hebergement': {
                'date_sortie_hebergement': "2015-06-10T03:12:58+00:00"
            },
            'ada': {
                'date_ouverture': "2015-06-10T03:12:58+00:00",
                'montant': 1000.42
            },
            'agent_orientation': 'dn@-agent-007',
            'date_orientation': '2015-06-11T12:22:37+00:00'
        }
        # POST is no longer allowed
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['agent_orientation'] == 'dn@-agent-007'
        assert r.data['date_orientation'] == '2015-06-11T12:22:37+00:00'
        assert 'date_sortie_hebergement' in r.data.get('hebergement', {})
        assert 'ada' in r.data and r.data['ada']['montant'] == 1000.42

    def test_update_dublin(self, user_with_site_affecte, da_en_cours_dublin, ref_pays):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s/dublin' % da_en_cours_dublin.pk
        payload = {
            'EM': str(ref_pays[0].pk),
            'date_demande_EM': '2015-06-11T03:22:43Z+00:00'
        }
        # Need permission to do it
        r = user_req.patch(route, data=payload)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.modifier_dublin.name)
        user.save()
        r = user_req.patch(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EN_COURS_PROCEDURE_DUBLIN'
        assert 'dublin' in r.data

    def test_fin_procedure_dublin(self, user_with_site_affecte, da_en_cours_dublin):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s/fin_procedure' % da_en_cours_dublin.pk
        # Need permission to do it
        r = user_req.post(route, data={})
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.finir_procedure.name)
        user.save()
        r = user_req.post(route, data={})
        assert r.status_code == 200, r
        assert r.data['statut'] == 'FIN_PROCEDURE_DUBLIN'
