import re
import time

from sief.tasks.email import mail

from tests import common
from tests.fixtures import *


class TestAuth(common.BaseTest):

    def test_not_allowed(self):
        assert self.client_app.post('/usager/login').status_code == 400

    def test_authentication(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user)
        # Make sure we can't login through GET
        r = user_req.get('/usager/login', data={
            'login': user.identifiant_agdref,
            'password': 'password'
        }, auth=False)
        assert r.status_code == 405, r
        r = user_req.post('/usager/login', data={
            'login': user.identifiant_agdref,
            'password': user._raw_password
        }, auth=False)
        assert r.status_code == 200, r
        assert 'token' in r.data, r

    def test_too_weak_password_to_change(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user)

        # Change password but provide too weak password
        r = user_req.post('/usager/login/password',
                          data={'login': user.identifiant_agdref,
                                'password': user._raw_password,
                                'new_password': 'tooweak'},
                          auth=False)
        assert r.status_code == 409, r

        # Change password but provide wrong password
        r = user_req.post('/usager/login/password',
                            data={'login': user.identifiant_agdref,
                                  'password': "Pssw0rd",
                                  'new_password': 'L337"F|_oOo'},
                            auth=False)
        assert r.status_code == 401, r

        # Change password but provide good password
        r = user_req.post('/usager/login/password',
                            data={'login': user.identifiant_agdref,
                                  'password': user._raw_password,
                                  'new_password': 'L337"F|_oOo'},
                            auth=False)
        assert r.status_code == 200, r
        assert 'token' in r.data, r

        # TODO : Decomment this whenever /moi is implemented for usager

        # # Old token is no longer valid
        # assert user_req.get('/moi').status_code == 401
        # # Instead we have to use the given token
        # user_req.token = r.data['token']
        # assert user_req.get('/moi').status_code == 200


class TestPasswordrecovery(common.BaseTest):

    def test_get_link(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user)
        with mail.record_messages() as outbox:
            r = user_req.get((
                '/usager/login/password_recovery/%s' % user.identifiant_agdref),
                auth=False)
            assert r.status_code == 200
            assert len(outbox) == 1
            assert re.match(r'.*(https?://[^/]+/#/reset/[^/]+/[0-9a-f]{64}).*',
                            outbox[0].body, re.DOTALL).group(1)

    def test_get_link_debug(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user)
        mail.debug = True
        with mail.record_messages() as outbox:
            r = user_req.get((
                '/usager/login/password_recovery/%s' % user.identifiant_agdref),
                auth=False)
            assert r.status_code == 200
            assert r.data
            assert len(outbox) == 1
            email, token = re.match(r'.*https?://[^/]+/#/reset/([^/]+)/([0-9a-f]{64}).*',
                                    outbox[0].body, re.DOTALL).group(1, 2)
            assert token == r.data.get('token')
        mail.debug = False

    def test_reset_pwd(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user)
        with mail.record_messages() as outbox:
            r = user_req.get((
                '/usager/login/password_recovery/%s' % user.identifiant_agdref),
                auth=False)
            assert r.status_code == 200
            assert len(outbox) == 1
            email, token = re.match(r'.*https?://[^/]+/#/reset/([^/]+)/([0-9a-f]{64}).*',
                                    outbox[0].body, re.DOTALL).group(1, 2)
            r = user_req.post((
                '/usager/login/password_recovery/%s' % user.identifiant_agdref),
                data={'token': 'INVALID TOKEN', 'password': 'newP@ssW0rd?!'})
            assert r.status_code == 401
            assert "'token': 'Token invalide in r.data'", r
            r = user_req.post((
                '/usager/login/password_recovery/%s' % user.identifiant_agdref),
                data={'token': token, 'password': 'newP@ssW0rd?!'})
            assert r.status_code == 200
            r = user_req.post('/usager/login', data={
                'login': user.identifiant_agdref,
                'password': 'newP@ssW0rd?!'
            }, auth=False)
            assert r.status_code == 200, r
            r = user_req.post((
                '/usager/login/password_recovery/%s' % user.identifiant_agdref),
                data={'token': token, 'password': 'newP@ssW0rd?!'})
            assert r.status_code == 401
            assert 'Utilisateur inexistant ou token expir' in r.data['_errors'][0]['password']


class TestPasswordExpiry(common.BaseTest):

    @classmethod
    def setup_class(cls, config={}):
        super().setup_class(config={'PASSWORD_EXPIRY_DATE': 2})

    def test_same_password_reject(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user)
        r = user_req.post(
            '/usager/login/password', data={
                'new_password': 'L337"F|_oOo',
                'login': user.identifiant_agdref,
                'password': 'L337"F|_oOo'}, auth=False)
        assert r.status_code == 409, r

    def test_tooweak_password(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user)
        r = user_req.post(
            '/usager/login/password', data={
                'new_password': 'tooweak',
                'login': user.identifiant_agdref,
                'password': 'P@ssw0rd'}, auth=False)
        assert r.status_code == 409, r

    def test_success_change(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user)
        r = user_req.post(
            '/usager/login/password', data={
                'new_password': 'L337"F|_oOo',
                'login': user.identifiant_agdref,
                'password': 'P@ssw0rd'}, auth=False)
        assert r.status_code == 200, r
        assert 'token' in r.data, r

    def test_expiry_password(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user)
        r = user_req.post('/usager/login', data={
            'login': user.identifiant_agdref,
            'password': 'P@ssw0rd'
        }, auth=False)
        assert r.status_code == 200, r
        time.sleep(3)
        user_req = self.make_auth_request(user)
        r = user_req.post('/usager/login', data={
            'login': user.identifiant_agdref,
            'password': 'P@ssw0rd'
        }, auth=False)
        assert r.status_code == 401, r
        assert 'Password must be refreshed' in r.data['_errors'][0]['password']


class TestValidatePasswordStrength(common.BaseTest):

    def setup_class(self):
        super().setup_class()
        self.route = '/usager/login/password/validate_strength'

    def test_empty_payload(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user, user._raw_password)
        response = user_req.post(self.route, data={})
        assert response.status_code == 400, response

    def test_weak_password(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user, user._raw_password)
        payload = {'password': 'password'}
        response = user_req.post(self.route, data=payload)
        assert response.status_code == 200, response
        assert not response.data['is_valid']

    def test_strong_password(self, usager_with_credentials):
        user = usager_with_credentials
        user_req = self.make_auth_request(user, user._raw_password)
        payload = {'password': 'Password01!'}
        response = user_req.post(self.route, data=payload)
        assert response.status_code == 200, response
        assert response.data['is_valid']
