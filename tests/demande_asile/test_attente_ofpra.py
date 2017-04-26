import pytest
from datetime import datetime
import copy

from tests import common
from tests.fixtures import *

from sief.model.demande_asile import DemandeAsile
from sief.permissions import POLICIES as p


@pytest.fixture
def da_attente_ofpra(request, da_prete_ea):
    u = user(request, nom='EditionAttestation', prenom='Setter')
    u.save()
    da_prete_ea.procedure.type = 'NORMALE'
    payload = {'date_debut_validite': datetime.utcnow(),
               'date_fin_validite': datetime.utcnow()}
    da_prete_ea.controller.editer_attestation(u, **payload)
    da_prete_ea.save()
    return da_prete_ea


class TestDemandeAsileEnCoursDublin(common.BaseTest):

    def test_links_single(self, user_with_site_affecte, da_attente_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s' % da_attente_ofpra.pk
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
                                'finir_procedure', 'requalifier_procedure',
                                'introduire_ofpra'])

    def test_orientation_update(self, user_with_site_affecte, da_attente_ofpra):
        user = user_with_site_affecte
        # Orientation stuff can still be modified
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.orienter.name]
        user.save()
        route = '/demandes_asile/%s/orientation' % da_attente_ofpra.pk
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
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['agent_orientation'] == 'dn@-agent-007'
        assert r.data['date_orientation'] == '2015-06-11T12:22:37+00:00'
        assert 'date_sortie_hebergement' in r.data.get('hebergement', {})
        assert 'ada' in r.data and r.data['ada']['montant'] == 1000.42

    def test_manuel_insert_inerec_id(self, user_with_site_affecte, da_attente_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.modifier.name]
        user.save()
        date = datetime.utcnow().isoformat()
        r = user_req.patch('/demandes_asile/%s' % da_attente_ofpra.pk,
            data={'identifiant_inerec': '123456789', 'date_introduction_ofpra': date})
        assert r.status_code == 400, r

    def test_switch_en_cours_ofpra(self, user_with_site_affecte, da_attente_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s/introduction_ofpra' % da_attente_ofpra.pk
        # Need permission to do it
        r = user_req.post(route)
        assert r.status_code == 403, r
        # Provide permission
        user.permissions.append(p.demande_asile.modifier_ofpra.name)
        user.save()
        # Test with incorrect payload
        date = datetime.utcnow().isoformat()
        for bad_payload in (
            None, {}, {'identifiant_inerec': '123456789'},
            {'date_introduction_inerec': date},
            {'identifiant_inerec': '123456789',
                'date_introduction_ofpra': date, 'bad_field': 'dummy'}
        ):
            r = user_req.post(route, data=bad_payload)
            assert r.status_code == 400, r
        # Correct request
        r = user_req.post(route, data={'identifiant_inerec': '123456789',
                                       'date_introduction_ofpra': date})
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EN_COURS_INSTRUCTION_OFPRA'

    def test_no_decision_definitive(self, user_with_site_affecte, da_attente_ofpra):
        user = user_with_site_affecte
        # Cannot add decision definitive in this status
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.modifier_ofpra.name]
        user.save()
        route = '/demandes_asile/%s/decisions_definitives' % da_attente_ofpra.pk
        # Need permission to do it
        r = user_req.post(route, data={
            'nature': 'CHANGE_ME!',
            'date': '2015-06-10T23:22:43+00.00',
            'date_premier_accord': '2015-06-10T23:22:43+00.00',
            'date_notification': '2015-06-10T23:22:43+00.00',
            'entite': 'OFPRA'
        })
        assert r.status_code == 400, r

    def test_requalification(self, user_with_site_affecte, da_attente_ofpra):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name]
        user.save()
        route = '/demandes_asile/%s/requalifications' % da_attente_ofpra.pk
        payload = {
            'type': 'ACCELEREE',
            'acteur': 'OFPRA',
            'motif_qualification': 'DILA',
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
        assert da_attente_ofpra.statut == 'EN_ATTENTE_INTRODUCTION_OFPRA'
        # Now switch to Dublin
        payload['type'] = 'DUBLIN'
        payload['motif_qualification'] = 'FAML'
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        assert r.data['statut'] == 'EN_COURS_PROCEDURE_DUBLIN'

    def test_bad_requalification(self, user_with_site_affecte, da_attente_ofpra):
        user = user_with_site_affecte
        # Cannot switch to any state !
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.demande_asile.voir.name,
                            p.demande_asile.requalifier_procedure.name]
        user.save()
        route = '/demandes_asile/%s/requalifications' % da_attente_ofpra.pk
        default_payload = {
            'type': 'DUBLIN',
            'acteur': 'PREFECTURE',
            'motif_qualification': 'DU172',
            'date_notification': datetime.utcnow().isoformat()
        }
        for (key, value) in (
                ('type', common.NOT_SET), ('acteur', common.NOT_SET),
                ('date_notification', common.NOT_SET),
                ('date_notification', None),
                ('bad', 'field'), ('type', None), ('acteur', None),
                ('type', 'bad'), ('date_notification', 'not a date'),
                ('motif_qualification', None), ('motif_qualification', 'BAD'),
                ('motif_qualification', 'FREM')  # Bad type for this qualif
        ):
            payload = copy.deepcopy(default_payload)
            common.update_payload(payload, key, value)
            r = user_req.post(route, data=payload)
            assert r.status_code == 400, (key, value)
            da_attente_ofpra.reload()
            assert da_attente_ofpra.statut == 'EN_ATTENTE_INTRODUCTION_OFPRA'
