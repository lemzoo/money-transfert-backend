import pytest
from base64 import b64encode
from datetime import datetime, timedelta
import re
import time

from sief.model.utilisateur import AccreditationError
from sief.tasks.email import mail

from tests import common
from tests.fixtures import *


def login(user_req, login, password, auth=False):
    return user_req.post('/agent/login', data={
        'login': login,
        'password': password
    }, auth=auth)


class TestAuthAndLogin(common.BaseTest):

    def test_login(self, user):
        user_req = self.make_auth_request(user)

        ret = login(user_req, user.email, user._raw_password)

        assert ret.status_code == 200

    def test_get_moi(self, user):
        user_req = self.make_auth_request(user)
        ret = login(user_req, user.email, user._raw_password)
        user_req.token = ret.data['token']

        ret = user_req.get('/moi', auth=True)

        assert ret.status_code == 200


class TestAuth(common.BaseTest):

    def test_not_allowed(self):
        assert self.client_app.get('/moi').status_code == 401
        # Dummy try
        assert self.client_app.post('/agent/login').status_code == 400

    def test_authentication_with_not_encoded_token(self, user):
        user_req = self.make_auth_request(user)
        not_encoded_token = '123456781234567812345678'
        user_req.token = not_encoded_token

        ret = user_req.get('/moi', auth=True)

        assert ret.status_code == 401

    def test_authentication(self, user):
        user_req = self.make_auth_request(user)
        # Make sure we can't login through GET
        r = user_req.get('/agent/login', data={
            'login': user.email,
            'password': 'password'
        }, auth=False)
        assert r.status_code == 405, r
        r = login(user_req, user.email, 'P@ssw0rd')
        assert r.status_code == 200, r
        assert 'token' in r.data, r
        # Try to authenticate with the given token
        user_req.token = r.data['token']
        assert user_req.get('/moi').status_code == 200
        # Create a basic authorization : needing because token is no longer fresh
        concat = '%s:%s' % (user.email, user._raw_password)
        authorization = 'Basic ' + b64encode(concat.encode()).decode()
        # Too weak password to change
        r = user_req.post('/agent/login/password', data={'login': user.email, 'password': 'P@ssw0rd', 'new_password': 'tooweak'},
                          headers={'Authorization': authorization}, auth=False)
        assert r.status_code == 409, r
        # Change password but provide wrong password
        r = user_req.post('/agent/login/password', data={'login': user.email, 'password': 'Pssw0rd', 'new_password': 'L337"F|_oOo'},
                          headers={'Authorization': authorization}, auth=False)
        assert r.status_code == 401, r
        # Change password but provide wrong password
        r = user_req.post('/agent/login/password', data={'login': user.email, 'password': 'P@ssw0rd', 'new_password': 'L337"F|_oOo'},
                          headers={'Authorization': authorization}, auth=False)
        assert r.status_code == 200, r
        assert 'token' in r.data, r
        # Old token is no longer valid
        assert user_req.get('/moi').status_code == 401
        # Instead we have to use the given token
        user_req.token = r.data['token']
        assert user_req.get('/moi').status_code == 200

    def test_user_without_accreditation(self, user):
        assert not user.accreditations
        user_req = self.make_auth_request(user)
        ret = login(user_req, user.email, user._raw_password)
        assert ret.status_code == 200

        ret = user_req.get('/moi')

        assert ret.status_code == 200
        assert ret.data['current_accreditation_id'] is None
        assert 'preferences' not in ret.data

    def test_user_with_accreditation(self, user_with_accreditations, site):
        user = user_with_accreditations
        user_req = self.make_auth_request(user)

        user_accreditations = user_with_accreditations.accreditations
        """
        The role of the user_with_accreditation is :
            1. ADMINISTRATEUR_PREFECTURE
            2. RESPONSABLE_GU_ASILE_PREFECTURE
            3. RESPONSABLE_ZONAL
        """
        first_role = 'ADMINISTRATEUR_PREFECTURE'
        second_role = 'RESPONSABLE_GU_ASILE_PREFECTURE'
        third_role = 'RESPONSABLE_ZONAL'

        # By default, we should get the first valid accreditation
        ret = user_req.get('/moi')
        assert ret.status_code == 200
        assert ret.data['current_accreditation_id'] == 1

        # Try to use the first accreditation which is disabled
        first_accr_id = user_accreditations[0].id
        ret = user_req.get('/moi', headers={'X-Use-Accreditation': first_accr_id})
        msg_error = 'Invalid X-Use-Accreditation header'
        assert ret.status_code == 401, msg_error

        # Set the second accreditation as current to use
        second_accr_id = user_accreditations[1].id
        payload = {'preferences': {'current_accreditation_id': second_accr_id}}
        ret = user_req.patch('/moi', data=payload)
        ret.status_code == 200

        "Try to use the second accreditation and check the preference"
        ret = user_req.get('/moi', headers={'X-Use-Accreditation': second_accr_id})
        assert ret.status_code == 200
        assert ret.data['current_accreditation_id'] == second_accr_id
        assert 'preferences' in ret.data
        preferences = ret.data['preferences']
        id_accr_pref = preferences['current_accreditation_id']
        assert id_accr_pref == second_accr_id

        # Check the current role
        returned_role = user_accreditations[id_accr_pref].role
        assert returned_role == second_role

        # Set the third accreditation as current accreditation to use
        third_accr_id = user_accreditations[2].id
        payload = {'preferences': {'current_accreditation_id': third_accr_id}}
        ret = user_req.patch('/moi', data=payload)
        ret.status_code == 200

        # Force use the third accreditation with X-Use-Accreditation header
        ret = user_req.get('/moi', headers={'X-Use-Accreditation': third_accr_id})
        assert ret.status_code == 200
        assert ret.data['current_accreditation_id'] == third_accr_id
        preferences = ret.data['preferences']
        id_accr_pref = preferences['current_accreditation_id']
        assert id_accr_pref == third_accr_id

        # Check the current role
        returned_role = user_accreditations[id_accr_pref].role
        assert returned_role == third_role

    def test_add_expired_accreditation_to_user(self, user):
        user_req = self.make_auth_request(user)
        user.controller.add_accreditation(role='RESPONSABLE_GU_ASILE_PREFECTURE')
        user.controller.add_accreditation(role='ADMINISTRATEUR_PREFECTURE')
        user.save()

        # Invalidate accreditation 0 and check we cannot access it
        user.controller.invalidate_accreditation(0)
        user.save()
        ret = user_req.get('/moi', headers={'X-Use-Accreditation': 0})
        assert ret.status_code == 401

        # However we can still access the use thanks to accreditation 1
        ret = user_req.get('/moi', headers={'X-Use-Accreditation': 1})
        assert ret.status_code == 200

        # Finally invalidate accreditation 1 as well, user should be globally invalidated
        user.controller.invalidate_accreditation(1)
        user.save()
        ret = user_req.get('/moi')
        assert ret.status_code == 401

    def test_invalidate_accreditation(self, user):
        tomorrow = datetime.utcnow() + timedelta(days=1)
        accreditation0_role = 'ADMINISTRATEUR_PREFECTURE'
        accreditation1_role = 'ADMINISTRATEUR_NATIONAL'
        user.controller.add_accreditation(role=accreditation0_role)
        user.controller.add_accreditation(role=accreditation1_role)
        user.save()

        # Check automatically generate accreditations ids
        assert user.accreditations[0].id == 0
        assert user.accreditations[1].id == 1

        # Check
        accr_id = user.controller.get_first_valid_accreditation().id
        user.controller.set_current_accreditation(accr_id)
        assert user.controller.get_current_accreditation().role == accreditation0_role

        # Now invalidate the first accreditation
        user.controller.invalidate_accreditation(0)
        accr_id = user.controller.get_first_valid_accreditation().id
        user.controller.set_current_accreditation(accr_id)
        now = datetime.utcnow()
        assert user.accreditations[0].fin_validite <= now
        assert not user.accreditations[1].fin_validite
        assert user.controller.get_current_accreditation().role == accreditation1_role

        # Cannot re-invalidate an accreditation
        with pytest.raises(AccreditationError):
            user.controller.invalidate_accreditation(0)

        # If we invalidate the 2nd accreditation, the user itself is invalidated
        user.controller.invalidate_accreditation(1)
        assert user.fin_validite

    def test_user_preference(self, user_with_accreditations):
        user = user_with_accreditations
        user_req = self.make_auth_request(user)
        # User should have preference set from the beginning
        assert user.preferences
        assert user.preferences.current_accreditation_id is None
        # Customize preferences and make sure they are passed through /moi route
        user.preferences.current_accreditation_id = 2
        user.save()
        ret = user_req.get('/moi')
        assert ret.status_code == 200
        assert ret.data['preferences']['current_accreditation_id'] == 2

        # User can acces to the route /utilisateurs by using the default
        # accreditation. This route doesn't disclose preferences
        ret = user_req.get('/utilisateurs')
        assert ret.status_code == 200
        assert 'preferences' not in ret.data['_items'][0]
        ret = user_req.get('/utilisateurs')
        assert ret.status_code == 200
        assert 'preferences' not in ret.data


class TestPasswordrecovery(common.BaseTest):

    def test_get_link(self, user):
        user_req = self.make_auth_request(user)
        with mail.record_messages() as outbox:
            r = user_req.get(('/agent/login/password_recovery/%s' % user.email), auth=False)
            assert r.status_code == 200
            assert len(outbox) == 1
            assert re.match(
                r'.*(https?://[^/]+/#/reset/[^/]+/[0-9a-f]{64}).*', outbox[0].body, re.DOTALL).group(1)

    def test_get_link_debug(self, user):
        user_req = self.make_auth_request(user)
        mail.debug = True
        with mail.record_messages() as outbox:
            r = user_req.get(('/agent/login/password_recovery/%s' % user.email), auth=False)
            assert r.status_code == 200
            assert r.data
            assert len(outbox) == 1
            email, token = re.match(
                r'.*https?://[^/]+/#/reset/([^/]+)/([0-9a-f]{64}).*', outbox[0].body, re.DOTALL).group(1, 2)
            assert token == r.data.get('token')
        mail.debug = False

    def test_reset_pwd(self, user):
        user_req = self.make_auth_request(user)
        with mail.record_messages() as outbox:
            r = user_req.get(('/agent/login/password_recovery/%s' % user.email), auth=False)
            assert r.status_code == 200
            assert len(outbox) == 1
            email, token = re.match(
                r'.*https?://[^/]+/#/reset/([^/]+)/([0-9a-f]{64}).*', outbox[0].body, re.DOTALL).group(1, 2)
            r = user_req.post(('/agent/login/password_recovery/%s' % email),
                              data={'token': 'INVALID TOKEN', 'password': 'newP@ssW0rd?!'})
            assert r.status_code == 401
            assert "'token': 'Token invalide in r.data'", r
            r = user_req.post(('/agent/login/password_recovery/%s' % email),
                              data={'token': token, 'password': 'newP@ssW0rd?!'})
            assert r.status_code == 200
            r = login(user_req, email, 'newP@ssW0rd?!')
            assert r.status_code == 200, r
            r = user_req.post(('/agent/login/password_recovery/%s' % email),
                              data={'token': token, 'password': 'newP@ssW0rd?!'})
            assert r.status_code == 401
            assert 'Utilisateur inexistant ou token expir' in r.data['_errors'][0]['password']


class TestPasswordExpiry(common.BaseTest):

    @classmethod
    def setup_class(cls, config={}):
        super().setup_class(config={'PASSWORD_EXPIRY_DATE': 2})

    def test_same_password_reject(self, user):
        user_req = self.make_auth_request(user)
        r = user_req.post(
            '/agent/login/password', data={
                'new_password': 'L337"F|_oOo',
                'login': user.email,
                'password': 'L337"F|_oOo'}, auth=False)
        assert r.status_code == 409, r

    def test_tooweak_password(self, user):
        user_req = self.make_auth_request(user)
        r = user_req.post(
            '/agent/login/password', data={
                'new_password': 'tooweak',
                'login': user.email,
                'password': 'P@ssw0rd'}, auth=False)
        assert r.status_code == 409, r

    def test_success_change(self, user):
        user_req = self.make_auth_request(user)
        r = user_req.post(
            '/agent/login/password', data={
                'new_password': 'L337"F|_oOo',
                'login': user.email,
                'password': 'P@ssw0rd'}, auth=False)
        assert r.status_code == 200, r
        assert 'token' in r.data, r
        user_req.token = r.data['token']
        assert user_req.get('/moi').status_code == 200

    def test_expiry_password(self, user):
        user_req = self.make_auth_request(user)
        r = login(user_req, user.email, 'P@ssw0rd')
        assert r.status_code == 200, r
        time.sleep(3)
        user_req = self.make_auth_request(user)
        r = login(user_req, user.email, 'P@ssw0rd')
        assert r.status_code == 401, r
        assert 'Password must be refreshed' in r.data['_errors'][0]['password']


class TestValidatePasswordStrength(common.BaseTest):

    def setup_class(self):
        super().setup_class()
        self.route = '/agent/login/password/validate_strength'

    def test_empty_payload(self, user):
        user_req = self.make_auth_request(user)
        response = user_req.post(self.route, data={})
        assert response.status_code == 400, response

    def test_weak_password(self, user):
        user_req = self.make_auth_request(user)
        payload = {'password': 'password'}
        response = user_req.post(self.route, data=payload)
        assert response.status_code == 200, response
        assert not response.data['is_valid']

    def test_strong_password(self, user):
        user_req = self.make_auth_request(user)
        payload = {'password': 'Password01!'}
        response = user_req.post(self.route, data=payload)
        assert response.status_code == 200, response
        assert response.data['is_valid']
