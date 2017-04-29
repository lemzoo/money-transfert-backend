import pytest

from tests import common
from tests.fixtures import *
from sief.permissions import POLICIES


@pytest.fixture
def da_instruction_ofpra_reexamen(da_instruction_ofpra):
    da_instruction_ofpra.type_demande = 'REEXAMEN'
    da_instruction_ofpra.save()
    return da_instruction_ofpra


class TestRecevabilite(common.BaseTest):

    def test_add_recevabilite(self, user_with_site_affecte, da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [POLICIES.demande_asile.modifier_ofpra.name]
        user.save()

        payload = {
            'date_notification': '01/01/2016',
            'date_qualification': '01/01/2016',
            'recevabilite': True
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 200
        assert 'recevabilites' in r.data
        assert len(r.data['recevabilites']) == 1
        assert r.data['recevabilites'][0]['recevabilite'] is True

    def test_add_recevabilite_no_permissions(self, user_with_site_affecte,
                                             da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)

        payload = {
            'date_notification': '01/01/2016',
            'date_qualification': '01/01/2016',
            'recevabilite': True
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 403
        assert r.data['message'] == 'Permission required'

    def test_no_date_notification(self, user_with_site_affecte, da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [POLICIES.demande_asile.modifier_ofpra.name]
        user.save()

        payload = {
            'date_qualification': '01/01/2016',
            'recevabilite': True
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert 'date_notification' in r.data
        assert len(r.data['date_notification']) > 0
        assert r.data['date_notification'][0].startswith('Missing data')

    def test_no_date_qualification(self, user_with_site_affecte, da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [POLICIES.demande_asile.modifier_ofpra.name]
        user.save()

        payload = {
            'date_notification': '01/01/2016',
            'recevabilite': True
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 200
        assert 'recevabilites' in r.data
        assert len(r.data['recevabilites']) == 1

    def test_no_recevabilite(self, user_with_site_affecte, da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [POLICIES.demande_asile.modifier_ofpra.name]
        user.save()

        payload = {
            'date_qualification': '01/01/2016',
            'date_notification': '01/01/2016'
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert 'recevabilite' in r.data
        assert len(r.data['recevabilite']) > 0
        assert r.data['recevabilite'][0].startswith('Missing data')

    def test_incorrect_date_notification(self, user_with_site_affecte,
                                         da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [POLICIES.demande_asile.modifier_ofpra.name]
        user.save()

        payload = {
            'date_qualification': 'invalid_date',
            'date_notification': '01/01/2016',
            'recevabilite': True
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert 'date_qualification' in r.data
        assert len(r.data['date_qualification']) > 0
        assert r.data['date_qualification'][0] == 'Not a valid datetime.'

    def test_incorrect_date_qualification(self, user_with_site_affecte,
                                          da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [POLICIES.demande_asile.modifier_ofpra.name]
        user.save()

        payload = {
            'date_qualification': '01/01/2016',
            'date_notification': 'invalid_date',
            'recevabilite': True
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert 'date_notification' in r.data
        assert len(r.data['date_notification']) > 0
        assert r.data['date_notification'][0] == 'Not a valid datetime.'

    def test_incorrect_recevabilite(self, user_with_site_affecte, da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [POLICIES.demande_asile.modifier_ofpra.name]
        user.save()

        payload = {
            'date_qualification': '01/01/2016',
            'date_notification': '01-01-2016',
            'recevabilite': 'test'
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
        assert 'recevabilite' in r.data
        assert len(r.data['recevabilite']) > 0
        assert r.data['recevabilite'][0] == 'Not a boolean'

    def test_invalid_type_demande(self, user_with_site_affecte, da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        da_inst.type_demande = 'PREMIERE_DEMANDE_ASILE'
        da_inst.save()
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [POLICIES.demande_asile.modifier_ofpra.name]
        user.save()

        payload = {
            'date_qualification': '01/01/2016',
            'date_notification': '01/01/2016',
            'recevabilite': True
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 400

    def test_different_dates(self, user_with_site_affecte, da_instruction_ofpra_reexamen):
        da_inst = da_instruction_ofpra_reexamen
        user = user_with_site_affecte
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [POLICIES.demande_asile.modifier_ofpra.name]
        user.save()

        payload = {
            'date_qualification': '01/01/2016',
            'date_notification': '02/01/2016',
            'recevabilite': True
        }
        route = 'demandes_asile/{}/recevabilite_ofpra'.format(da_inst.pk)
        r = user_req.post(route, data=payload)
        assert r.status_code == 400
