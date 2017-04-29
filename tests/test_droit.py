from tests import common
import pytest
from datetime import datetime, timedelta

from tests.fixtures import *

from sief.model.droit import Droit
from sief.model.site import Prefecture
from sief.permissions import POLICIES as p


@pytest.fixture
def droit(request, user, da_orientation):
    usager = da_orientation.usager
    droit = Droit(
        demande_origine=da_orientation,
        agent_createur=user,
        type_document='CARTE_SEJOUR_TEMPORAIRE',
        sous_type_document='PREMIERE_DELIVRANCE',
        usager=usager,
        date_fin_validite=datetime.utcnow() + timedelta(180),
        date_debut_validite=datetime.utcnow(),
        prefecture_rattachee=da_orientation.prefecture_rattachee
    ).save()
    return droit


@pytest.fixture
def support_payload(site):
    return {
        'date_delivrance': datetime.utcnow().isoformat(),
        'lieu_delivrance': str(site.pk),
    }


class TestDroit(common.BaseTest):

    def test_links_list(self, user_with_site_affecte):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.droit.voir.name]
        user.save()
        r = user_req.get('/droits')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'root'])
        user.permissions.append(p.droit.creer.name)
        user.save()
        r = user_req.get('/droits')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'create', 'root'])

    def test_links_single(self, user_with_site_affecte, droit):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.droit.voir.name]
        user.save()
        route = '/droits/%s' % droit.pk
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'parent'])
        user.permissions.append(p.droit.retirer.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'retirer', 'parent'])
        user.permissions = [p.droit.voir.name, p.historique.voir.name]
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'history', 'parent'])
        user.permissions.append(p.droit.support.creer.name)
        user.save()
        r = user_req.get(route)
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ['self', 'history', 'parent', 'support_create'])

    def test_create_droit(self, user_with_site_affecte, usager, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        payload = {
            "usager": str(usager.pk),
            "type_document": 'CARTE_SEJOUR_TEMPORAIRE',
            "demande_origine": {'id': str(da_orientation.pk),
                                '_cls': da_orientation._class_name},
            "sous_type_document": 'PREMIER_RENOUVELLEMENT',
            "date_debut_validite": datetime.utcnow().isoformat(),
            "date_fin_validite": (datetime.utcnow() + timedelta(180)).isoformat(),
            "autorisation_travail": True,
            "pourcentage_duree_travail_autorise": 40,
            "date_decision_sur_attestation": "2015-08-22T12:22:24+00:00"
        }
        # Need permission do to it...
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 403, r
        # Provide it
        user.permissions = [p.droit.creer.name]
        user.save()
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r
        # Make sure prefecture_rattache has been inherited
        assert r.data['prefecture_rattachee']['id'] == str(usager.prefecture_rattachee.id)
        assert r.data['type_document'] == 'CARTE_SEJOUR_TEMPORAIRE'
        assert r.data['date_decision_sur_attestation'] == "2015-08-22T12:22:24+00:00"


    def test_bad_demande_origin_create_droit(self, user_with_site_affecte, usager, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.droit.creer.name]
        user.save()
        da_id = str(da_orientation.pk)
        da_cls = da_orientation.__class__.__name__
        payload = {
            "usager": str(usager.pk),
            "type_document": 'CARTE_SEJOUR_TEMPORAIRE',
            "demande_origine": {'id': da_id,
                                '_cls': da_cls},
            "sous_type_document": 'PREMIER_RENOUVELLEMENT',
            "date_debut_validite": (datetime.utcnow() + timedelta(180)).isoformat(),
            "date_fin_validite": datetime.utcnow().isoformat(),
            "autorisation_travail": True,
            "pourcentage_duree_travail_autorise": 40,
        }
        for field in (da_id, None, 'not_an_id', {'id': da_id},
                      {'id': 'not_an_id', '_cls': da_cls},
                      {'id': da_id, '_cls': None}, {'id': None, '_cls': da_cls},
                      {'id': da_id, '_cls': 'not_a_class'}):
            payload['demande_origine'] = field
            r = user_req.post('/droits', data=payload)
            assert r.status_code == 400, r
        del payload['demande_origine']
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 400, r

    def test_annuler_droit(self, user_with_site_affecte, droit):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        payload = {
            'date_retrait_attestation': datetime.utcnow().isoformat(),
            'motif_retrait_attestation': "Didn't respect the 3rd law of robotic"
        }
        route = '/droits/%s/retrait' % droit.pk
        r = user_req.post(route, data=payload)
        assert r.status_code == 403, r
        user.permissions = [p.droit.retirer.name]
        user.save()
        r = user_req.post(route, data=payload)
        assert r.status_code == 200, r
        # POST is no longer allowed
        correction_payload = {
            'date_notification_retrait_attestation': datetime.utcnow().isoformat()
        }
        r = user_req.post(route, data=correction_payload)
        assert r.status_code == 400, r
        # Need to use PATCH
        r = user_req.patch(route, data=correction_payload)
        assert r.status_code == 200, r

    def test_support(self, user_with_site_affecte, droit, support_payload):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/droits/%s/supports' % droit.pk
        # Add a support
        r = user_req.post(route, data=support_payload)
        assert r.status_code == 403, r
        # Provide rights
        user.permissions = [p.droit.support.creer.name]
        user.save()
        r = user_req.post(route, data=support_payload)
        assert len(r.data['supports']) == 1
        first_support, = r.data['supports']
        assert first_support['numero_duplicata'] == 0
        assert r.status_code == 200, r
        # Create another support, numero_duplicata should be incremented
        r = user_req.post(route, data=support_payload)
        assert r.status_code == 200, r
        assert len(r.data['supports']) == 2
        _, second_support = r.data['supports']
        assert second_support['numero_duplicata'] == 1

    def test_annuler_support(self, user_with_site_affecte, droit, support_payload):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        route = '/droits/%s/supports' % droit.pk
        # Add a support
        user.permissions = [p.droit.support.creer.name]
        user.save()
        r = user_req.post(route, data=support_payload)
        assert r.status_code == 200, r
        # Now cancel it
        cancel_payload = {
            'motif_annulation': "PERTE"
        }
        cancel_route = r.data['supports'][-1]['_links']['annuler']
        r = user_req.post(cancel_route, data=cancel_payload)
        assert r.status_code == 403, r
        # Add the right permission
        user.permissions = [p.droit.support.annuler.name]
        user.save()
        r = user_req.post(cancel_route, data=cancel_payload)
        assert r.status_code == 200, r


class TestSitesRattachesDroit(common.BaseTest):

    def test_prefecture_rattachee(self, user, droit, site, site_gu):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.droit.voir.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        # Sanity check
        assert site != droit.prefecture_rattachee
        assert site_gu.autorite_rattachement == droit.prefecture_rattachee

        def _test_view(size):
            r = user_req.get('/droits')
            assert r.status_code == 200, r
            assert len(r.data['_items']) == size
            if len(r.data['_items']) == 1:
                route = r.data['_items'][0]['_links']['self']
                r = user_req.get(route)
                assert r.status_code == 200, r
                assert r.data['id'] == str(droit.id)
        _test_view(0)
        user.test_set_accreditation(site_affecte=site_gu)
        user.save()
        _test_view(1)
        user.test_set_accreditation(site_affecte=None)
        user.permissions.append(p.droit.prefecture_rattachee.sans_limite.name)
        user.save()
        _test_view(1)

    def test_prefecture_rattachee_route(self, user_with_site_affecte, droit, site):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.droit.voir.name]
        user.test_set_accreditation(site_affecte=site)
        user.save()
        # Sanity check
        assert site != droit.prefecture_rattachee
        # Cannot see this droit...
        r = user_req.get('/droits/%s' % droit.id)
        assert r.status_code == 403, r
        # ...but can ask who's it belong to
        r = user_req.get('/droits/%s/prefecture_rattachee' % droit.id)
        assert r.status_code == 200, r
        assert 'prefecture_rattachee' in r.data
        assert r.data['prefecture_rattachee']['id'] == str(droit.prefecture_rattachee.id)

    def test_multiple_renouvellement_droit(self, user_with_site_affecte, usager, da_orientation):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.droit.creer.name]
        user.save()
        payload = {
            "usager": str(usager.pk),
            "type_document": 'CARTE_SEJOUR_TEMPORAIRE',
            "demande_origine": {'id': str(da_orientation.pk),
                                '_cls': da_orientation._class_name},
            "sous_type_document": 'PREMIERE_DELIVRANCE',
            "date_debut_validite": datetime.utcnow().isoformat(),
            "date_fin_validite": (datetime.utcnow() + timedelta(180)).isoformat(),
            "autorisation_travail": True,
            "pourcentage_duree_travail_autorise": 40,
            "date_decision_sur_attestation": "2015-08-22T12:22:24+00:00"
        }
        # Need permission do to it...
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r
        # Make sure prefecture_rattache has been inherited
        payload['sous_type_document'] = 'PREMIER_RENOUVELLEMENT'
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r
        payload['sous_type_document'] = 'EN_RENOUVELLEMENT'
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r
        r = user_req.post('/droits', data=payload)
        assert r.status_code == 201, r


class TestExportDroit(common.BaseSolrTest):

    def test_export_droits(self, user_with_site_affecte, usager, da_orientation, support_payload):
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.droit.creer.name, p.droit.support.creer.name, p.droit.export.name]
        user.save()
        payload = {
            "usager": str(usager.pk),
            "type_document": 'CARTE_SEJOUR_TEMPORAIRE',
            "demande_origine": {'id': str(da_orientation.pk),
                                '_cls': da_orientation._class_name},
            "sous_type_document": 'PREMIER_RENOUVELLEMENT',
            "date_debut_validite": datetime.utcnow().isoformat(),
            "date_fin_validite": (datetime.utcnow() + timedelta(180)).isoformat(),
            "autorisation_travail": True,
            "pourcentage_duree_travail_autorise": 40,
            "date_decision_sur_attestation": "2015-08-22T12:22:24+00:00"
        }
        for i in range(0, 25):
            r = user_req.post('/droits', data=payload)
            assert r.status_code == 201, r
            route = '/droits/%s/supports' % r.data['id']
            # Add a support
            r = user_req.post(route, data=support_payload)
            assert r.status_code == 200, r
            r = user_req.post(route, data=support_payload)
            assert r.status_code == 200, r

        # Ensure solr documents are available
        self.app.solr.commit(waitFlush=True)
        route = '/droits/export'
        r = user_req.get(route)
        assert r.status_code == 200, r
        assert r.data['_links'].get('next', None) == '/droits/export?per_page=20&page=2'
        assert r.data['_meta']['total'] == 25
        assert 'agent_editeur' not in r.data['_data']
        assert 'numero_serie' not in r.data['_data']
