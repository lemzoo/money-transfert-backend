from tests import common
import pytest
from marshmallow import Schema
from io import BytesIO

from tests.test_auth import user

from sief.model.fichier import Fichier
from sief.permissions import POLICIES as p


class TestParametrage(common.BaseTest):

    def test_get(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        # Parametrage is readable for anyone authenticated...
        r = user_req.get('/parametrage')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'root'))
        # ...but needs right to be altered
        r = user_req.patch('/parametrage', data={'field': 'value'})
        assert r.status_code == 403, r
        user.permissions = [p.parametrage.gerer.name]
        user.save()
        r = user_req.patch('/parametrage', data={'field': 'value'})
        assert r.status_code == 200, r
        r = user_req.get('/parametrage')
        assert r.status_code == 200, r
        common.assert_response_contains_links(r, ('self', 'root', 'update'))

    def test_if_match(self, user):
        user_req = self.make_auth_request(user, user._raw_password)
        user.permissions = [p.parametrage.gerer.name]
        user.save()
        r = user_req.get('/parametrage')
        assert r.status_code == 200, r
        assert r.data['_version'] == 1
        r = user_req.patch('/parametrage', data={'field': 'value'}, headers={'If-Match': '1'})
        assert r.status_code == 200, r
        assert r.data['_version'] == 2
        # Bad if-match
        r = user_req.patch('/parametrage', data={'field': 'value'}, headers={'If-Match': '1'})
        assert r.status_code == 412, r
