import pytest
from datetime import datetime
import copy

from tests import common
from tests.fixtures import *

from sief.model.demande_asile import DemandeAsile
from sief.permissions import POLICIES as p


@pytest.fixture
def da_fin_dublin(request, da_en_cours_dublin):
    da_en_cours_dublin.controller.finir_procedure()
    da_en_cours_dublin.save()
    return da_en_cours_dublin


class TestDemandeAsileFinProcedure(common.BaseTest):

    def test_links_single(self, user_with_site_affecte, da_fin_dublin):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s' % da_fin_dublin.pk
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.modifier_dublin.name,
                            p.demande_asile.requalifier_procedure.name,
                            p.demande_asile.editer_attestation.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])

    def test_no_requalification(self, user_with_site_affecte, da_fin_dublin):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.requalifier_procedure.name]
        user.save()
        route = '/demandes_asile/%s/requalifications' % da_fin_dublin.pk
        payload = {
            'type': 'NORMALE',
            'acteur': 'OFPRA',
            'date_notification': datetime.utcnow().isoformat()
        }
        user.permissions.append(p.demande_asile.requalifier_procedure.name)
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r

    def test_orientation_update(self, user_with_site_affecte, da_fin_dublin):
        user = user_with_site_affecte
        # Even orientation stuff can no longer be modified
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.orienter.name]
        user.save()
        route = '/demandes_asile/%s/orientation' % da_fin_dublin.pk
        payload = {
            'hebergement': {
                'date_sortie_hebergement': "2015-06-10T03:12:58+00:00"
            },
            'ada': {
                'date_ouverture': "2015-06-10T03:12:58+00:00",
                'montant': 1000.42
            },
            'agent_orientation': 'dn@-agent-007'
        }
        r = user_req.post(route, data=payload)
        assert r.status_code == 400, r

    def test_no_update_dublin(self, user_with_site_affecte, da_fin_dublin, ref_pays):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.modifier_dublin.name]
        user.save()
        route = '/demandes_asile/%s/dublin' % da_fin_dublin.pk
        payload = {
            'EM': str(ref_pays[0].pk),
            'date_demande_EM': '2015-06-11T03:22:43Z+00:00'
        }
        r = user_req.patch(route, data=payload)
        assert r.status_code == 400, r

    def test_no_fin_procedure_dublin(self, user_with_site_affecte, da_fin_dublin):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
        				    p.demande_asile.finir_procedure.name]
        user.save()
        route = '/demandes_asile/%s/fin_procedure' % da_fin_dublin.pk
        r = user_req.post(route)
        assert r.status_code == 400, r
